"""
Evidence Service — Collects, validates, and aggregates presence proofs.

Evidence sources: qr, gps, manual_checkin, system
Confidence scoring: low / medium / high
Aggregation: strong / medium / weak proof strength

Philosophy:
- No single party is the source of truth
- Evidence is symmetric and verifiable
- No proof → no automatic penalty
- Ambiguity → manual_review

V2: Smart scoring with temporal + geographic consistency.
"""
import os
import uuid
import hmac
import hashlib
import logging
import math
import requests
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from utils.date_utils import now_utc

logger = logging.getLogger(__name__)

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
client = MongoClient(MONGO_URL)
db = client[DB_NAME]

QR_SECRET = os.environ.get('JWT_SECRET', 'nlyt_default_secret')
QR_ROTATION_SECONDS = 60
QR_TOLERANCE_WINDOWS = 2
DEFAULT_GPS_RADIUS_METERS = 200

# --- Temporal windows ---
CHECKIN_WINDOW_BEFORE_HOURS = 2    # Valid check-in starts 2h before RDV
CHECKIN_WINDOW_AFTER_HOURS = 1     # Valid check-in ends 1h after RDV end

# --- Geographic thresholds (meters) ---
GEO_CLOSE_METERS = 500             # "close" — strong signal
GEO_NEARBY_METERS = 5000           # "nearby" — acceptable
GEO_FAR_METERS = 50000             # "far" — suspicious
# > 50km = "incoherent"


# ============================================================
# GEOCODING (Nominatim / OpenStreetMap — best effort, cached)
# ============================================================

def _nominatim_headers():
    return {"User-Agent": "NLYT-SaaS/1.0 (contact@nlyt.io)"}


def geocode_address(address: str) -> dict:
    """Forward geocode: address string → {lat, lon, display_name}. Best effort."""
    if not address:
        return {}
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1, "addressdetails": 0},
            headers=_nominatim_headers(),
            timeout=5
        )
        if resp.status_code == 200 and resp.json():
            r = resp.json()[0]
            return {
                "latitude": float(r['lat']),
                "longitude": float(r['lon']),
                "display_name": r.get('display_name', '')
            }
    except Exception as e:
        logger.warning(f"[GEOCODE] Forward geocoding failed for '{address[:50]}': {e}")
    return {}


def reverse_geocode(lat: float, lon: float) -> str:
    """Reverse geocode: lat/lon → human-readable address label. Best effort."""
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "json", "zoom": 14, "addressdetails": 0},
            headers=_nominatim_headers(),
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get('display_name', '')
    except Exception as e:
        logger.warning(f"[GEOCODE] Reverse geocoding failed for {lat},{lon}: {e}")
    return ""


def resolve_appointment_coordinates(appointment: dict) -> tuple:
    """
    Ensure appointment has lat/lon. Geocode from address if missing.
    Returns (lat, lon) or (None, None).
    """
    apt_lat = appointment.get('location_latitude')
    apt_lon = appointment.get('location_longitude')
    if apt_lat is not None and apt_lon is not None:
        return float(apt_lat), float(apt_lon)

    # Try geocoding from address
    address = appointment.get('location', '')
    if not address:
        return None, None

    geo = geocode_address(address)
    if geo.get('latitude'):
        # Cache in DB
        db.appointments.update_one(
            {"appointment_id": appointment['appointment_id']},
            {"$set": {
                "location_latitude": geo['latitude'],
                "location_longitude": geo['longitude'],
                "location_geocoded": True,
                "location_display_name": geo.get('display_name', '')
            }}
        )
        logger.info(f"[GEOCODE] Cached coordinates for apt {appointment['appointment_id'][:8]}: {geo['latitude']}, {geo['longitude']}")
        return geo['latitude'], geo['longitude']

    return None, None


# ============================================================
# TEMPORAL CONSISTENCY
# ============================================================

def assess_temporal_consistency(evidence_ts: datetime, appointment: dict) -> dict:
    """
    Assess if evidence timestamp is within a reasonable window of the RDV.
    Returns: {consistency: "valid"|"too_early"|"too_late", hours_offset: float, detail: str}
    """
    start_str = appointment.get('start_datetime', '')
    try:
        start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return {"consistency": "unknown", "hours_offset": None, "detail": "Impossible de parser la date du RDV"}

    if evidence_ts.tzinfo is None:
        evidence_ts = evidence_ts.replace(tzinfo=timezone.utc)

    duration = appointment.get('duration_minutes', 60)
    end_dt = start_dt + timedelta(minutes=duration)

    window_start = start_dt - timedelta(hours=CHECKIN_WINDOW_BEFORE_HOURS)
    window_end = end_dt + timedelta(hours=CHECKIN_WINDOW_AFTER_HOURS)

    hours_before_start = (start_dt - evidence_ts).total_seconds() / 3600
    hours_after_end = (evidence_ts - end_dt).total_seconds() / 3600

    if evidence_ts < window_start:
        return {
            "consistency": "too_early",
            "hours_offset": round(hours_before_start, 1),
            "detail": f"{round(hours_before_start, 1)}h avant le début du RDV"
        }
    elif evidence_ts > window_end:
        return {
            "consistency": "too_late",
            "hours_offset": round(hours_after_end, 1),
            "detail": f"{round(hours_after_end, 1)}h après la fin du RDV"
        }
    else:
        if evidence_ts <= start_dt:
            return {
                "consistency": "valid",
                "hours_offset": round(-hours_before_start, 1),
                "detail": f"Arrivé {round(hours_before_start * 60)}min avant le RDV"
            }
        elif evidence_ts <= end_dt:
            tolerated = appointment.get('tolerated_delay_minutes', 0)
            late_by = (evidence_ts - start_dt).total_seconds() / 60
            if late_by <= tolerated:
                return {
                    "consistency": "valid",
                    "hours_offset": round(late_by / 60, 2),
                    "detail": f"Arrivé {round(late_by)}min après le début (tolérance: {tolerated}min)"
                }
            else:
                return {
                    "consistency": "valid_late",
                    "hours_offset": round(late_by / 60, 2),
                    "detail": f"Arrivé {round(late_by)}min en retard (tolérance: {tolerated}min)"
                }
        else:
            return {
                "consistency": "valid",
                "hours_offset": round(hours_after_end, 1),
                "detail": "Enregistré après la fin du RDV mais dans la fenêtre"
            }


# ============================================================
# GEOGRAPHIC CONSISTENCY
# ============================================================

def assess_geographic_consistency(lat: float, lon: float, apt_lat: float, apt_lon: float) -> dict:
    """
    Assess geographic consistency between evidence GPS and RDV location.
    Returns: {consistency, distance_meters, distance_km, detail}
    """
    if apt_lat is None or apt_lon is None:
        return {"consistency": "no_reference", "distance_meters": None, "distance_km": None, "detail": "Pas de coordonnées de référence pour le RDV"}

    distance = haversine_distance(lat, lon, apt_lat, apt_lon)
    distance_km = round(distance / 1000, 1)

    if distance <= GEO_CLOSE_METERS:
        return {
            "consistency": "close",
            "distance_meters": round(distance, 0),
            "distance_km": distance_km,
            "detail": f"À {round(distance)}m du lieu du RDV"
        }
    elif distance <= GEO_NEARBY_METERS:
        return {
            "consistency": "nearby",
            "distance_meters": round(distance, 0),
            "distance_km": distance_km,
            "detail": f"À {distance_km}km du lieu du RDV"
        }
    elif distance <= GEO_FAR_METERS:
        return {
            "consistency": "far",
            "distance_meters": round(distance, 0),
            "distance_km": distance_km,
            "detail": f"À {distance_km}km du lieu du RDV — suspect"
        }
    else:
        return {
            "consistency": "incoherent",
            "distance_meters": round(distance, 0),
            "distance_km": distance_km,
            "detail": f"À {distance_km}km du lieu du RDV — incohérent"
        }


# ============================================================
# SMART CONFIDENCE SCORING
# ============================================================

def compute_smart_confidence(source: str, temporal: dict, geographic: dict) -> str:
    """
    Compute evidence confidence based on source, temporal, and geographic consistency.
    Returns: "high" | "medium" | "low"
    """
    # Base score by source type
    base_scores = {"qr": 3, "manual_checkin": 2, "gps": 1, "system": 1}
    score = base_scores.get(source, 1)

    # Temporal modifiers
    tc = temporal.get('consistency', 'unknown')
    if tc == 'too_early':
        hours = abs(temporal.get('hours_offset', 0))
        if hours > 24:
            score -= 3  # Days early → catastrophic
        elif hours > 6:
            score -= 2
        else:
            score -= 1
    elif tc == 'too_late':
        score -= 1
    elif tc == 'valid_late':
        pass  # No penalty, just late
    elif tc == 'valid':
        score += 1  # Bonus for good timing

    # Geographic modifiers
    gc = geographic.get('consistency', 'no_reference')
    if gc == 'close':
        score += 2
    elif gc == 'nearby':
        score += 1
    elif gc == 'far':
        score -= 1
    elif gc == 'incoherent':
        score -= 3  # Hundreds of km away → catastrophic
    # no_reference → no modifier

    # Map score to confidence
    if score >= 4:
        return "high"
    elif score >= 2:
        return "medium"
    else:
        return "low"


# ============================================================
# QR TOKEN
# ============================================================

def _get_qr_window(ts: datetime = None) -> int:
    if ts is None:
        ts = now_utc()
    return int(ts.timestamp()) // QR_ROTATION_SECONDS


def generate_qr_token(appointment_id: str, window: int = None) -> str:
    if window is None:
        window = _get_qr_window()
    payload = f"{appointment_id}:{window}"
    signature = hmac.new(
        QR_SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()[:16]
    return f"NLYT:{appointment_id}:{window}:{signature}"


def verify_qr_token(token: str) -> dict:
    try:
        parts = token.strip().split(':')
        if len(parts) != 4 or parts[0] != 'NLYT':
            return {"valid": False, "reason": "Format QR invalide"}
        _, appointment_id, window_str, signature = parts
        window = int(window_str)
        payload = f"{appointment_id}:{window}"
        expected = hmac.new(
            QR_SECRET.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()[:16]
        if not hmac.compare_digest(signature, expected):
            return {"valid": False, "reason": "Signature QR invalide"}
        current_window = _get_qr_window()
        if window < current_window - QR_TOLERANCE_WINDOWS:
            return {"valid": False, "reason": "QR expiré"}
        if window > current_window + 1:
            return {"valid": False, "reason": "QR pas encore valide"}
        return {"valid": True, "appointment_id": appointment_id, "window": window}
    except (ValueError, IndexError):
        return {"valid": False, "reason": "QR illisible"}


def haversine_distance(lat1, lon1, lat2, lon2) -> float:
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ============================================================
# EVIDENCE CRUD
# ============================================================

def create_evidence(
    appointment_id: str,
    participant_id: str,
    source: str,
    created_by: str,
    source_timestamp: str = None,
    derived_facts: dict = None,
    raw_payload_reference: str = None,
    confidence_score: str = "medium"
) -> dict:
    now = now_utc()
    evidence = {
        "evidence_id": str(uuid.uuid4()),
        "appointment_id": appointment_id,
        "participant_id": participant_id,
        "source": source,
        "source_timestamp": source_timestamp or now.isoformat(),
        "created_at": now.isoformat(),
        "confidence_score": confidence_score,
        "derived_facts": derived_facts or {},
        "raw_payload_reference": raw_payload_reference,
        "created_by": created_by,
    }
    db.evidence_items.insert_one(evidence)
    logger.info(f"[EVIDENCE] Created {source} evidence for participant {participant_id[:8]} on apt {appointment_id[:8]} (confidence={confidence_score})")
    return {k: v for k, v in evidence.items() if k != '_id'}


# ============================================================
# PROCESS CHECK-INS
# ============================================================

def process_manual_checkin(
    appointment_id: str,
    participant_id: str,
    device_info: str = None,
    latitude: float = None,
    longitude: float = None,
) -> dict:
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        return {"error": "Rendez-vous introuvable"}

    existing = db.evidence_items.find_one({
        "appointment_id": appointment_id,
        "participant_id": participant_id,
        "source": "manual_checkin"
    })
    if existing:
        return {"error": "Check-in déjà effectué", "already_checked_in": True}

    now = now_utc()
    derived_facts = {"device_info": device_info}

    # Temporal assessment
    temporal = assess_temporal_consistency(now, appointment)
    derived_facts["temporal_consistency"] = temporal['consistency']
    derived_facts["temporal_detail"] = temporal['detail']

    # Resolve appointment coordinates (geocode if needed)
    apt_lat, apt_lon = resolve_appointment_coordinates(appointment)

    # Geographic assessment
    geographic = {"consistency": "no_reference", "distance_meters": None, "distance_km": None}
    if latitude is not None and longitude is not None:
        derived_facts["latitude"] = latitude
        derived_facts["longitude"] = longitude

        geographic = assess_geographic_consistency(latitude, longitude, apt_lat, apt_lon)
        derived_facts["geographic_consistency"] = geographic['consistency']
        derived_facts["geographic_detail"] = geographic['detail']
        derived_facts["distance_meters"] = geographic['distance_meters']
        derived_facts["distance_km"] = geographic['distance_km']

        if apt_lat is not None:
            derived_facts["gps_within_radius"] = geographic['consistency'] in ('close', 'nearby')
            derived_facts["gps_radius_meters"] = appointment.get('gps_radius_meters', DEFAULT_GPS_RADIUS_METERS)
        else:
            derived_facts["gps_no_reference"] = True

        # Reverse geocode for display
        address = reverse_geocode(latitude, longitude)
        if address:
            derived_facts["address_label"] = address
    else:
        derived_facts["geographic_consistency"] = "no_gps"

    # Smart confidence
    confidence = compute_smart_confidence("manual_checkin", temporal, geographic)
    derived_facts["confidence_factors"] = f"temporal={temporal['consistency']}, geographic={geographic['consistency']}"

    evidence = create_evidence(
        appointment_id=appointment_id,
        participant_id=participant_id,
        source="manual_checkin",
        created_by="participant",
        confidence_score=confidence,
        derived_facts=derived_facts,
    )

    return {"success": True, "evidence": evidence}


def process_qr_checkin(
    qr_token: str,
    participant_id: str,
    scanner_participant_id: str = None,
) -> dict:
    verification = verify_qr_token(qr_token)
    if not verification['valid']:
        return {"error": verification['reason']}

    appointment_id = verification['appointment_id']
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        return {"error": "Rendez-vous introuvable"}

    participant = db.participants.find_one({
        "participant_id": participant_id,
        "appointment_id": appointment_id
    })
    if not participant:
        return {"error": "Participant non associé à ce rendez-vous"}

    existing = db.evidence_items.find_one({
        "appointment_id": appointment_id,
        "participant_id": participant_id,
        "source": "qr"
    })
    if existing:
        return {"error": "Check-in QR déjà effectué", "already_checked_in": True}

    now = now_utc()
    temporal = assess_temporal_consistency(now, appointment)

    derived_facts = {
        "qr_window": verification['window'],
        "qr_valid": True,
        "temporal_consistency": temporal['consistency'],
        "temporal_detail": temporal['detail'],
    }
    if scanner_participant_id and scanner_participant_id != participant_id:
        derived_facts["scanned_by"] = scanner_participant_id

    # QR is inherently a strong signal but temporal matters
    confidence = compute_smart_confidence("qr", temporal, {"consistency": "no_reference"})

    evidence = create_evidence(
        appointment_id=appointment_id,
        participant_id=participant_id,
        source="qr",
        created_by="participant",
        confidence_score=confidence,
        derived_facts=derived_facts,
    )

    return {"success": True, "evidence": evidence, "appointment_id": appointment_id}


def process_gps_checkin(
    appointment_id: str,
    participant_id: str,
    latitude: float,
    longitude: float,
) -> dict:
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        return {"error": "Rendez-vous introuvable"}

    existing = db.evidence_items.find_one({
        "appointment_id": appointment_id,
        "participant_id": participant_id,
        "source": "gps"
    })
    if existing:
        return {"error": "Preuve GPS déjà enregistrée", "already_checked_in": True}

    now = now_utc()
    temporal = assess_temporal_consistency(now, appointment)
    apt_lat, apt_lon = resolve_appointment_coordinates(appointment)
    geographic = assess_geographic_consistency(latitude, longitude, apt_lat, apt_lon)

    derived_facts = {
        "latitude": latitude,
        "longitude": longitude,
        "temporal_consistency": temporal['consistency'],
        "temporal_detail": temporal['detail'],
        "geographic_consistency": geographic['consistency'],
        "geographic_detail": geographic['detail'],
        "distance_meters": geographic['distance_meters'],
        "distance_km": geographic['distance_km'],
    }

    if apt_lat is not None:
        derived_facts["gps_within_radius"] = geographic['consistency'] in ('close', 'nearby')
        derived_facts["gps_radius_meters"] = appointment.get('gps_radius_meters', DEFAULT_GPS_RADIUS_METERS)
    else:
        derived_facts["gps_no_reference"] = True

    # Reverse geocode
    address = reverse_geocode(latitude, longitude)
    if address:
        derived_facts["address_label"] = address

    confidence = compute_smart_confidence("gps", temporal, geographic)
    derived_facts["confidence_factors"] = f"temporal={temporal['consistency']}, geographic={geographic['consistency']}"

    evidence = create_evidence(
        appointment_id=appointment_id,
        participant_id=participant_id,
        source="gps",
        created_by="participant",
        confidence_score=confidence,
        derived_facts=derived_facts,
    )

    return {"success": True, "evidence": evidence}


# ============================================================
# READ
# ============================================================

def get_evidence_for_participant(appointment_id: str, participant_id: str) -> list:
    return list(db.evidence_items.find(
        {"appointment_id": appointment_id, "participant_id": participant_id},
        {"_id": 0}
    ))


def get_evidence_for_appointment(appointment_id: str) -> list:
    return list(db.evidence_items.find(
        {"appointment_id": appointment_id},
        {"_id": 0}
    ))


# ============================================================
# AGGREGATE
# ============================================================

def aggregate_evidence(appointment_id: str, participant_id: str, appointment: dict) -> dict:
    """
    Aggregate evidence for a participant with smart scoring.
    Factors: signal count, temporal consistency, geographic consistency.
    """
    evidence_items = get_evidence_for_participant(appointment_id, participant_id)

    if not evidence_items:
        return {
            "strength": "none",
            "signals": [],
            "timing": None,
            "confidence": "low",
            "evidence_count": 0,
            "temporal_flag": None,
            "geographic_flag": None,
        }

    signals = []
    has_qr = False
    has_gps_close = False
    has_checkin = False
    earliest_timestamp = None
    worst_temporal = "valid"
    best_geographic = "no_reference"

    geo_rank = {"close": 4, "nearby": 3, "far": 2, "incoherent": 1, "no_reference": 0, "no_gps": 0}
    temporal_rank = {"valid": 4, "valid_late": 3, "too_late": 2, "too_early": 1, "unknown": 0}

    for item in evidence_items:
        source = item.get('source')
        facts = item.get('derived_facts', {})
        ts_str = item.get('source_timestamp', '')

        try:
            ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if earliest_timestamp is None or ts < earliest_timestamp:
                earliest_timestamp = ts
        except (ValueError, TypeError):
            pass

        if source == 'qr' and facts.get('qr_valid'):
            has_qr = True
            signals.append("qr_valid")
        if source == 'manual_checkin':
            has_checkin = True
            signals.append("manual_checkin")
        if source == 'gps' or (source == 'manual_checkin' and facts.get('latitude')):
            gc = facts.get('geographic_consistency', 'no_reference')
            if gc in ('close', 'nearby'):
                has_gps_close = True
                signals.append("gps_close")
            elif gc in ('far', 'incoherent'):
                signals.append(f"gps_{gc}")

        # Track worst/best consistency
        tc = facts.get('temporal_consistency', 'unknown')
        if temporal_rank.get(tc, 0) < temporal_rank.get(worst_temporal, 4):
            worst_temporal = tc
        gc = facts.get('geographic_consistency', 'no_reference')
        if geo_rank.get(gc, 0) > geo_rank.get(best_geographic, 0):
            best_geographic = gc

    # --- Smart strength calculation ---
    positive_signals = sum([has_qr, has_gps_close, has_checkin])

    # Start with signal-based strength
    if positive_signals >= 2:
        strength = "strong"
    elif positive_signals == 1:
        strength = "medium"
    else:
        strength = "weak"

    # Degrade for temporal issues
    if worst_temporal == 'too_early':
        # Find how early from the temporal_detail fields
        early_hours = 0
        for item in evidence_items:
            item_tc = item.get('derived_facts', {}).get('temporal_consistency', '')
            if item_tc == 'too_early':
                detail_str = item.get('derived_facts', {}).get('temporal_detail', '')
                try:
                    offset = abs(float(detail_str.split('h')[0]))
                    early_hours = max(early_hours, offset)
                except (ValueError, IndexError):
                    early_hours = 24

        if early_hours > 24:
            strength = "weak"  # Days early → always weak
        elif early_hours > 6:
            strength = "weak" if strength in ("strong", "medium") else strength
        else:
            if strength == "strong":
                strength = "medium"

    if worst_temporal == 'too_late':
        if strength == "strong":
            strength = "medium"

    # Degrade for geographic incoherence
    if best_geographic == 'incoherent':
        strength = "weak"  # Hundreds of km away → always weak
    elif best_geographic == 'far':
        if strength == "strong":
            strength = "medium"
        elif strength == "medium":
            strength = "weak"

    # Determine timing
    timing = None
    if earliest_timestamp:
        start_str = appointment.get('start_datetime', '')
        try:
            start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            tolerated_delay = appointment.get('tolerated_delay_minutes', 0)
            deadline = start_dt + timedelta(minutes=tolerated_delay)
            timing = "on_time" if earliest_timestamp <= deadline else "late"
        except (ValueError, TypeError):
            pass

    # Additional: if timing says "on_time" but temporal is "too_early", flag it
    if worst_temporal == 'too_early' and timing == 'on_time':
        timing = None  # Cannot determine timing if check-in was way too early

    confidence_map = {"strong": "high", "medium": "medium", "weak": "low", "none": "low"}

    return {
        "strength": strength,
        "signals": signals,
        "timing": timing,
        "confidence": confidence_map.get(strength, "low"),
        "evidence_count": len(evidence_items),
        "earliest_evidence": earliest_timestamp.isoformat() if earliest_timestamp else None,
        "temporal_flag": worst_temporal,
        "geographic_flag": best_geographic,
    }
