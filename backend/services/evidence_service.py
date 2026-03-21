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
"""
import os
import uuid
import hmac
import hashlib
import logging
import math
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
QR_TOLERANCE_WINDOWS = 2  # Accept current + 1 previous window
DEFAULT_GPS_RADIUS_METERS = 200


def _get_qr_window(ts: datetime = None) -> int:
    """Get the current QR time window (rotates every QR_ROTATION_SECONDS)."""
    if ts is None:
        ts = now_utc()
    return int(ts.timestamp()) // QR_ROTATION_SECONDS


def generate_qr_token(appointment_id: str, window: int = None) -> str:
    """Generate a signed QR token for an appointment."""
    if window is None:
        window = _get_qr_window()
    payload = f"{appointment_id}:{window}"
    signature = hmac.new(
        QR_SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()[:16]
    return f"NLYT:{appointment_id}:{window}:{signature}"


def verify_qr_token(token: str) -> dict:
    """Verify a QR token. Returns {valid, appointment_id, window, reason}."""
    try:
        parts = token.strip().split(':')
        if len(parts) != 4 or parts[0] != 'NLYT':
            return {"valid": False, "reason": "Format QR invalide"}

        _, appointment_id, window_str, signature = parts
        window = int(window_str)

        # Verify signature
        payload = f"{appointment_id}:{window}"
        expected = hmac.new(
            QR_SECRET.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()[:16]

        if not hmac.compare_digest(signature, expected):
            return {"valid": False, "reason": "Signature QR invalide"}

        # Check time window (allow current + previous windows)
        current_window = _get_qr_window()
        if window < current_window - QR_TOLERANCE_WINDOWS:
            return {"valid": False, "reason": "QR expiré"}

        if window > current_window + 1:
            return {"valid": False, "reason": "QR pas encore valide"}

        return {"valid": True, "appointment_id": appointment_id, "window": window}

    except (ValueError, IndexError):
        return {"valid": False, "reason": "QR illisible"}


def haversine_distance(lat1, lon1, lat2, lon2) -> float:
    """Calculate distance in meters between two GPS coordinates."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


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
    """Create and store an evidence item."""
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
    logger.info(f"[EVIDENCE] Created {source} evidence for participant {participant_id[:8]} on apt {appointment_id[:8]}")
    return {k: v for k, v in evidence.items() if k != '_id'}


def process_manual_checkin(
    appointment_id: str,
    participant_id: str,
    device_info: str = None,
    latitude: float = None,
    longitude: float = None,
) -> dict:
    """Process a manual 'Je suis arrivé' check-in."""
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        return {"error": "Rendez-vous introuvable"}

    # Check for duplicate checkin
    existing = db.evidence_items.find_one({
        "appointment_id": appointment_id,
        "participant_id": participant_id,
        "source": "manual_checkin"
    })
    if existing:
        return {"error": "Check-in déjà effectué", "already_checked_in": True}

    derived_facts = {"device_info": device_info}
    confidence = "medium"

    # GPS analysis if coordinates provided
    if latitude is not None and longitude is not None:
        derived_facts["latitude"] = latitude
        derived_facts["longitude"] = longitude

        apt_lat = appointment.get('location_latitude')
        apt_lon = appointment.get('location_longitude')

        if apt_lat is not None and apt_lon is not None:
            distance = haversine_distance(latitude, longitude, apt_lat, apt_lon)
            derived_facts["distance_meters"] = round(distance, 1)
            radius = appointment.get('gps_radius_meters', DEFAULT_GPS_RADIUS_METERS)
            derived_facts["gps_radius_meters"] = radius
            derived_facts["gps_within_radius"] = distance <= radius
            if distance <= radius:
                confidence = "high"
            else:
                confidence = "low"
        else:
            derived_facts["gps_no_reference"] = True

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
    """Process a QR scan check-in."""
    verification = verify_qr_token(qr_token)
    if not verification['valid']:
        return {"error": verification['reason']}

    appointment_id = verification['appointment_id']

    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        return {"error": "Rendez-vous introuvable"}

    # Check participant belongs to this appointment
    participant = db.participants.find_one({
        "participant_id": participant_id,
        "appointment_id": appointment_id
    })
    if not participant:
        return {"error": "Participant non associé à ce rendez-vous"}

    # Check for duplicate QR checkin
    existing = db.evidence_items.find_one({
        "appointment_id": appointment_id,
        "participant_id": participant_id,
        "source": "qr"
    })
    if existing:
        return {"error": "Check-in QR déjà effectué", "already_checked_in": True}

    derived_facts = {
        "qr_window": verification['window'],
        "qr_valid": True,
    }
    if scanner_participant_id and scanner_participant_id != participant_id:
        derived_facts["scanned_by"] = scanner_participant_id

    evidence = create_evidence(
        appointment_id=appointment_id,
        participant_id=participant_id,
        source="qr",
        created_by="participant",
        confidence_score="high",
        derived_facts=derived_facts,
    )

    return {"success": True, "evidence": evidence, "appointment_id": appointment_id}


def process_gps_checkin(
    appointment_id: str,
    participant_id: str,
    latitude: float,
    longitude: float,
) -> dict:
    """Process a GPS-only check-in (complementary evidence)."""
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

    apt_lat = appointment.get('location_latitude')
    apt_lon = appointment.get('location_longitude')
    derived_facts = {"latitude": latitude, "longitude": longitude}
    confidence = "low"

    if apt_lat is not None and apt_lon is not None:
        distance = haversine_distance(latitude, longitude, apt_lat, apt_lon)
        radius = appointment.get('gps_radius_meters', DEFAULT_GPS_RADIUS_METERS)
        derived_facts["distance_meters"] = round(distance, 1)
        derived_facts["gps_radius_meters"] = radius
        derived_facts["gps_within_radius"] = distance <= radius
        confidence = "medium" if distance <= radius else "low"
    else:
        derived_facts["gps_no_reference"] = True

    evidence = create_evidence(
        appointment_id=appointment_id,
        participant_id=participant_id,
        source="gps",
        created_by="participant",
        confidence_score=confidence,
        derived_facts=derived_facts,
    )

    return {"success": True, "evidence": evidence}


def get_evidence_for_participant(appointment_id: str, participant_id: str) -> list:
    """Get all evidence items for a specific participant in an appointment."""
    return list(db.evidence_items.find(
        {"appointment_id": appointment_id, "participant_id": participant_id},
        {"_id": 0}
    ))


def get_evidence_for_appointment(appointment_id: str) -> list:
    """Get all evidence items for an appointment."""
    return list(db.evidence_items.find(
        {"appointment_id": appointment_id},
        {"_id": 0}
    ))


def aggregate_evidence(appointment_id: str, participant_id: str, appointment: dict) -> dict:
    """
    Aggregate evidence for a participant and produce a proof strength.

    Returns: {
        strength: "strong" | "medium" | "weak" | "none",
        signals: [...],
        timing: "on_time" | "late" | None,
        confidence: "high" | "medium" | "low"
    }
    """
    evidence_items = get_evidence_for_participant(appointment_id, participant_id)

    if not evidence_items:
        return {
            "strength": "none",
            "signals": [],
            "timing": None,
            "confidence": "low",
            "evidence_count": 0
        }

    signals = []
    has_qr = False
    has_gps_match = False
    has_checkin = False
    earliest_timestamp = None

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
            if facts.get('gps_within_radius'):
                has_gps_match = True
                signals.append("gps_match_on_checkin")
        if source == 'gps' and facts.get('gps_within_radius'):
            has_gps_match = True
            signals.append("gps_match")

    # Determine proof strength
    signal_count = sum([has_qr, has_gps_match, has_checkin])

    if signal_count >= 2:
        strength = "strong"
        confidence = "high"
    elif signal_count == 1:
        strength = "medium"
        confidence = "medium"
    else:
        strength = "weak"
        confidence = "low"

    # Determine timing relative to appointment
    timing = None
    if earliest_timestamp:
        start_str = appointment.get('start_datetime', '')
        try:
            start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)

            tolerated_delay = appointment.get('tolerated_delay_minutes', 0)
            deadline = start_dt + timedelta(minutes=tolerated_delay)

            if earliest_timestamp <= deadline:
                timing = "on_time"
            else:
                timing = "late"
        except (ValueError, TypeError):
            pass

    return {
        "strength": strength,
        "signals": signals,
        "timing": timing,
        "confidence": confidence,
        "evidence_count": len(evidence_items),
        "earliest_evidence": earliest_timestamp.isoformat() if earliest_timestamp else None
    }
