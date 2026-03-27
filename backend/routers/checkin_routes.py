"""
Check-in Routes — Participant check-in, QR generation/verification, GPS evidence.
Public endpoints (token-based auth via invitation_token) + authenticated endpoints.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
from slowapi import Limiter
from slowapi.util import get_remote_address
from datetime import timedelta
import os
import sys
import io
import base64
import logging

from database import db
from services.evidence_service import _parse_appointment_start, now_utc, CHECKIN_WINDOW_BEFORE_MINUTES, CHECKIN_WINDOW_AFTER_HOURS
logger = logging.getLogger(__name__)

sys.path.append('/app/backend')
from middleware.auth_middleware import get_current_user
from services.evidence_service import (
    generate_qr_token,
    verify_qr_token,
    process_manual_checkin,
    process_qr_checkin,
    process_gps_checkin,
    get_evidence_for_appointment,
    get_evidence_for_participant,
    aggregate_evidence,
    _get_qr_window,
    QR_ROTATION_SECONDS,
)
from rate_limiter import limiter

router = APIRouter()



class ManualCheckinRequest(BaseModel):
    invitation_token: str
    device_info: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    gps_consent: Optional[bool] = False


class QRVerifyRequest(BaseModel):
    qr_code: str
    invitation_token: str


class GPSCheckinRequest(BaseModel):
    invitation_token: str
    latitude: float
    longitude: float


def _resolve_participant(invitation_token: str) -> tuple:
    """
    Resolve participant and appointment from invitation token.
    Returns (participant, appointment) or raises.

    !! ZONE PROTÉGÉE — Chaîne de preuves de présence !!
    Voir /app/backend/docs/EVIDENCE_CHAIN.md pour la documentation complète.
    Tests de non-régression : /app/backend/tests/test_evidence_chain.py
    Toute modification doit être signalée dans le summary de livraison.

    INVARIANTS :
    - Statuts autorisés : accepted, accepted_pending_guarantee, accepted_guaranteed
    - Aucune distinction organisateur / participant
    - Le rendez-vous doit être 'active'
    """
    participant = db.participants.find_one(
        {"invitation_token": invitation_token}, {"_id": 0}
    )
    if not participant:
        raise HTTPException(status_code=404, detail="Invitation invalide")

    if participant.get('status') not in ('accepted', 'accepted_pending_guarantee', 'accepted_guaranteed'):
        raise HTTPException(status_code=400, detail="Vous devez avoir accepté l'invitation pour effectuer un check-in")

    appointment = db.appointments.find_one(
        {"appointment_id": participant['appointment_id']}, {"_id": 0}
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

    if appointment.get('status') != 'active':
        raise HTTPException(status_code=400, detail="Ce rendez-vous n'est plus actif")

    # Hard time gate: check-in window = [start - 30min, end + 1h]
    try:
        start_utc = _parse_appointment_start(appointment)
        current = now_utc()
        duration = appointment.get("duration_minutes", 60)
        opens_at = start_utc - timedelta(minutes=CHECKIN_WINDOW_BEFORE_MINUTES)
        closes_at = start_utc + timedelta(minutes=duration) + timedelta(hours=CHECKIN_WINDOW_AFTER_HOURS)
        if current < opens_at:
            minutes_left = int((opens_at - current).total_seconds() / 60)
            raise HTTPException(
                status_code=400,
                detail=f"Le check-in ouvre 30 minutes avant le rendez-vous. Revenez dans {minutes_left} min."
            )
        if current > closes_at:
            raise HTTPException(
                status_code=400,
                detail="Le check-in est termine. La fenetre de check-in a expire (1h apres la fin du rendez-vous)."
            )
    except HTTPException:
        raise
    except (ValueError, TypeError):
        pass  # If date parsing fails, don't block — let evidence assessment handle it

    return participant, appointment


# --- PUBLIC ENDPOINTS (token-based) ---

@router.post("/manual")
@limiter.limit("20/minute")
async def manual_checkin(request: Request, body: ManualCheckinRequest):
    """Participant manual check-in: 'Je suis arrivé'"""
    participant, appointment = _resolve_participant(body.invitation_token)

    logger.info(f"[CHECKIN:MANUAL] participant={participant['participant_id'][:8]} apt={appointment['appointment_id'][:8]} gps_consent={body.gps_consent} lat={body.latitude} lon={body.longitude}")

    kwargs = {
        "appointment_id": appointment['appointment_id'],
        "participant_id": participant['participant_id'],
        "device_info": body.device_info,
    }
    if body.gps_consent and body.latitude is not None and body.longitude is not None:
        kwargs["latitude"] = body.latitude
        kwargs["longitude"] = body.longitude

    result = process_manual_checkin(**kwargs)

    if result.get('error'):
        status = 409 if result.get('already_checked_in') else 400
        logger.warning(f"[CHECKIN:MANUAL] Error for participant={participant['participant_id'][:8]}: {result['error']} (status={status})")
        raise HTTPException(status_code=status, detail=result['error'])

    ev = result.get('evidence', {})
    facts = ev.get('derived_facts', {})
    logger.info(f"[CHECKIN:MANUAL] Success participant={participant['participant_id'][:8]} source={ev.get('source')} distance_km={facts.get('distance_km')} confidence={ev.get('confidence_score')}")

    # Notify other participants (non-blocking, idempotent)
    from services.checkin_notification_service import notify_checkin
    ev = result.get('evidence', {})
    checkin_time = ev.get('source_timestamp')
    facts = ev.get('derived_facts', {})
    evidence_details = {
        'source': ev.get('source', 'manual_checkin'),
        'latitude': facts.get('latitude'),
        'longitude': facts.get('longitude'),
        'address_label': facts.get('address_label'),
        'distance_km': facts.get('distance_km'),
    }
    await notify_checkin(participant['participant_id'], appointment['appointment_id'], checkin_time, evidence_details)

    return result


@router.post("/qr/verify")
@limiter.limit("30/minute")
async def qr_verify(request: Request, body: QRVerifyRequest):
    """Verify a scanned QR code and create evidence."""
    participant, appointment = _resolve_participant(body.invitation_token)

    result = process_qr_checkin(
        qr_token=body.qr_code,
        participant_id=participant['participant_id'],
    )

    if result.get('error'):
        status = 409 if result.get('already_checked_in') else 400
        raise HTTPException(status_code=status, detail=result['error'])

    # Notify other participants
    from services.checkin_notification_service import notify_checkin
    ev = result.get('evidence', {})
    checkin_time = ev.get('source_timestamp')
    evidence_details = {'source': 'qr'}
    await notify_checkin(participant['participant_id'], appointment['appointment_id'], checkin_time, evidence_details)

    return result


@router.post("/gps")
@limiter.limit("20/minute")
async def gps_checkin(request: Request, body: GPSCheckinRequest):
    """Submit GPS evidence (complementary proof)."""
    participant, appointment = _resolve_participant(body.invitation_token)

    logger.info(f"[CHECKIN:GPS] participant={participant['participant_id'][:8]} apt={appointment['appointment_id'][:8]} lat={body.latitude} lon={body.longitude}")

    result = process_gps_checkin(
        appointment_id=appointment['appointment_id'],
        participant_id=participant['participant_id'],
        latitude=body.latitude,
        longitude=body.longitude,
    )

    if result.get('error'):
        status = 409 if result.get('already_checked_in') else 400
        logger.warning(f"[CHECKIN:GPS] Error for participant={participant['participant_id'][:8]}: {result['error']} (status={status})")
        raise HTTPException(status_code=status, detail=result['error'])

    # Notify other participants
    from services.checkin_notification_service import notify_checkin
    ev = result.get('evidence', {})
    checkin_time = ev.get('source_timestamp')
    facts = ev.get('derived_facts', {})
    logger.info(f"[CHECKIN:GPS] Success participant={participant['participant_id'][:8]} distance_km={facts.get('distance_km')} confidence={ev.get('confidence_score')}")
    evidence_details = {
        'source': 'gps',
        'latitude': facts.get('latitude') or body.latitude,
        'longitude': facts.get('longitude') or body.longitude,
        'address_label': facts.get('address_label'),
        'distance_km': facts.get('distance_km'),
    }
    await notify_checkin(participant['participant_id'], appointment['appointment_id'], checkin_time, evidence_details)

    return result


@router.get("/qr/{appointment_id}")
async def get_qr_code(appointment_id: str, invitation_token: str):
    """Generate a dynamic QR code for an appointment. Accessible to any participant."""
    participant = db.participants.find_one(
        {"invitation_token": invitation_token}, {"_id": 0}
    )
    if not participant:
        raise HTTPException(status_code=404, detail="Invitation invalide")

    if participant.get('appointment_id') != appointment_id:
        raise HTTPException(status_code=403, detail="Token ne correspond pas au rendez-vous")

    if participant.get('status') not in ('accepted', 'accepted_pending_guarantee', 'accepted_guaranteed'):
        raise HTTPException(status_code=400, detail="Invitation non acceptée")

    # Generate QR token
    window = _get_qr_window()
    qr_token = generate_qr_token(appointment_id, window)

    # Generate QR code image as base64
    import qrcode
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(qr_token)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    return {
        "qr_token": qr_token,
        "qr_image_base64": qr_base64,
        "appointment_id": appointment_id,
        "window": window,
        "rotation_seconds": QR_ROTATION_SECONDS,
        "valid_for_seconds": QR_ROTATION_SECONDS,
    }


@router.get("/status/{appointment_id}")
async def get_checkin_status(appointment_id: str, invitation_token: str):
    """Get check-in status for the current participant."""
    participant = db.participants.find_one(
        {"invitation_token": invitation_token}, {"_id": 0}
    )
    if not participant:
        raise HTTPException(status_code=404, detail="Invitation invalide")

    if participant.get('appointment_id') != appointment_id:
        raise HTTPException(status_code=403, detail="Token ne correspond pas au rendez-vous")

    evidence = get_evidence_for_participant(appointment_id, participant['participant_id'])

    has_checkin = any(e['source'] == 'manual_checkin' for e in evidence)
    has_qr = any(e['source'] == 'qr' for e in evidence)
    has_gps = any(e['source'] == 'gps' for e in evidence)
    has_video = any(e['source'] == 'video_conference' for e in evidence)

    earliest = None
    for e in evidence:
        ts = e.get('source_timestamp')
        if ts and (earliest is None or ts < earliest):
            earliest = ts

    return {
        "checked_in": has_checkin or has_qr or has_gps or has_video,  # INVARIANT: toute preuve = checked_in (voir EVIDENCE_CHAIN.md)
        "has_manual_checkin": has_checkin,
        "has_qr_checkin": has_qr,
        "has_gps": has_gps,
        "has_video": has_video,
        "evidence_count": len(evidence),
        "earliest_checkin": earliest,
        "evidence": evidence,
    }


# --- AUTHENTICATED ENDPOINTS (organizer + participant) ---

@router.get("/evidence/{appointment_id}")
async def get_appointment_evidence(appointment_id: str, request: Request):
    """
    Get all evidence for an appointment.
    Accessible by workspace members (organizer) AND participants.

    !! ZONE PROTÉGÉE — Chaîne de preuves de présence !!
    Voir /app/backend/docs/EVIDENCE_CHAIN.md

    INVARIANTS :
    - Retourne UNE entrée par participant (pas de fusion, pas d'omission)
    - Inclut l'organisateur (PAS de filtre sur is_organizer)
    - Filtre par statut : accepted, accepted_pending_guarantee, accepted_guaranteed
    - Structure : { participants: [{ participant_id, participant_name, evidence: [...], aggregation }] }
    - Même information pour tous (transparence), actions différenciées côté frontend
    """
    user = await get_current_user(request)

    appointment = db.appointments.find_one(
        {"appointment_id": appointment_id}, {"_id": 0}
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

    # Access: workspace member OR participant
    has_access = False
    membership = db.workspace_memberships.find_one({
        "workspace_id": appointment['workspace_id'],
        "user_id": user['user_id']
    }, {"_id": 0})
    if membership:
        has_access = True
    else:
        participant_match = db.participants.find_one({
            "appointment_id": appointment_id,
            "$or": [
                {"user_id": user["user_id"]},
                {"email": user.get("email", "")}
            ]
        }, {"_id": 0, "participant_id": 1})
        if participant_match:
            has_access = True

    if not has_access:
        raise HTTPException(status_code=403, detail="Accès refusé")

    evidence = get_evidence_for_appointment(appointment_id)

    # Get participants for name mapping
    participants = list(db.participants.find(
        {"appointment_id": appointment_id},
        {"_id": 0, "participant_id": 1, "first_name": 1, "last_name": 1, "email": 1, "status": 1}
    ))

    # Aggregate per participant
    aggregated = []
    for p in participants:
        if p.get('status') not in ('accepted', 'accepted_pending_guarantee', 'accepted_guaranteed'):
            continue
        agg = aggregate_evidence(appointment_id, p['participant_id'], appointment)
        p_evidence = [e for e in evidence if e['participant_id'] == p['participant_id']]
        aggregated.append({
            "participant_id": p['participant_id'],
            "participant_name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
            "participant_email": p.get('email', ''),
            "evidence": p_evidence,
            "aggregation": agg,
        })

    return {
        "appointment_id": appointment_id,
        "participants": aggregated,
        "total_evidence": len(evidence),
    }
