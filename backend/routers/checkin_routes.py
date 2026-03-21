"""
Check-in Routes — Participant check-in, QR generation/verification, GPS evidence.
Public endpoints (token-based auth via invitation_token) + authenticated endpoints.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pymongo import MongoClient
from pydantic import BaseModel
from typing import Optional
import os
import sys
import io
import base64

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

router = APIRouter()

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
client = MongoClient(MONGO_URL)
db = client[DB_NAME]


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
    """Resolve participant and appointment from invitation token. Returns (participant, appointment) or raises."""
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

    return participant, appointment


# --- PUBLIC ENDPOINTS (token-based) ---

@router.post("/manual")
async def manual_checkin(body: ManualCheckinRequest):
    """Participant manual check-in: 'Je suis arrivé'"""
    participant, appointment = _resolve_participant(body.invitation_token)

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
        raise HTTPException(status_code=status, detail=result['error'])

    return result


@router.post("/qr/verify")
async def qr_verify(body: QRVerifyRequest):
    """Verify a scanned QR code and create evidence."""
    participant, appointment = _resolve_participant(body.invitation_token)

    result = process_qr_checkin(
        qr_token=body.qr_code,
        participant_id=participant['participant_id'],
    )

    if result.get('error'):
        status = 409 if result.get('already_checked_in') else 400
        raise HTTPException(status_code=status, detail=result['error'])

    return result


@router.post("/gps")
async def gps_checkin(body: GPSCheckinRequest):
    """Submit GPS evidence (complementary proof)."""
    participant, appointment = _resolve_participant(body.invitation_token)

    result = process_gps_checkin(
        appointment_id=appointment['appointment_id'],
        participant_id=participant['participant_id'],
        latitude=body.latitude,
        longitude=body.longitude,
    )

    if result.get('error'):
        status = 409 if result.get('already_checked_in') else 400
        raise HTTPException(status_code=status, detail=result['error'])

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

    earliest = None
    for e in evidence:
        ts = e.get('source_timestamp')
        if ts and (earliest is None or ts < earliest):
            earliest = ts

    return {
        "checked_in": has_checkin or has_qr,
        "has_manual_checkin": has_checkin,
        "has_qr_checkin": has_qr,
        "has_gps": has_gps,
        "evidence_count": len(evidence),
        "earliest_checkin": earliest,
        "evidence": evidence,
    }


# --- AUTHENTICATED ENDPOINTS (organizer) ---

@router.get("/evidence/{appointment_id}")
async def get_appointment_evidence(appointment_id: str, request: Request):
    """Get all evidence for an appointment (organizer view)."""
    user = await get_current_user(request)

    appointment = db.appointments.find_one(
        {"appointment_id": appointment_id}, {"_id": 0}
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

    membership = db.workspace_memberships.find_one({
        "workspace_id": appointment['workspace_id'],
        "user_id": user['user_id']
    }, {"_id": 0})
    if not membership:
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
