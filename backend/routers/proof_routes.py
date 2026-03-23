"""
Proof Sessions — NLYT internal attendance proof system.
Independent of video provider APIs.

Endpoints:
- POST /api/proof/{appointment_id}/checkin   — Start proof session (token auth)
- POST /api/proof/{appointment_id}/heartbeat — Record heartbeat ping
- POST /api/proof/{appointment_id}/checkout  — End proof session + compute score
- GET  /api/proof/{appointment_id}/sessions  — List all sessions (organizer only)
- POST /api/proof/{appointment_id}/validate  — Validate session status (organizer only)
- GET  /api/proof/{appointment_id}/info      — Get appointment info for check-in page (token auth)
"""

import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from pymongo import MongoClient

from middleware.auth_middleware import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "nlyt_db")
mongo_client = MongoClient(MONGO_URL)
db = mongo_client[DB_NAME]

HEARTBEAT_INTERVAL_SECONDS = 30
MAX_HEARTBEAT_GAP_SECONDS = 90  # If gap > 90s, user was inactive


# ── Models ──────────────────────────────────────────────────────

class CheckinRequest(BaseModel):
    token: str  # invitation_token

class HeartbeatRequest(BaseModel):
    session_id: str

class CheckoutRequest(BaseModel):
    session_id: str

class ValidateRequest(BaseModel):
    session_id: str
    final_status: str  # "present" | "partial" | "absent"


# ── Helpers ─────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc)


def _compute_active_duration(heartbeats: list) -> int:
    """Compute active duration from heartbeat timestamps."""
    if len(heartbeats) < 2:
        return HEARTBEAT_INTERVAL_SECONDS if heartbeats else 0

    total = 0
    for i in range(1, len(heartbeats)):
        prev = datetime.fromisoformat(heartbeats[i - 1])
        curr = datetime.fromisoformat(heartbeats[i])
        gap = (curr - prev).total_seconds()
        if gap <= MAX_HEARTBEAT_GAP_SECONDS:
            total += gap
    return int(total)


def _compute_score(session: dict, appointment: dict) -> dict:
    """Compute proof score (0-100) from session data."""
    score_breakdown = {"checkin_points": 0, "duration_points": 0, "video_api_points": 0}

    # 1. Check-in on time (+30 pts)
    start_str = appointment.get("start_datetime", "")
    tolerated = appointment.get("tolerated_delay_minutes", 10)
    try:
        apt_start = datetime.fromisoformat(start_str).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        apt_start = None

    if apt_start and session.get("checked_in_at"):
        checkin_time = datetime.fromisoformat(session["checked_in_at"])
        delay_minutes = (checkin_time - apt_start).total_seconds() / 60
        if delay_minutes <= tolerated:
            score_breakdown["checkin_points"] = 30
        elif delay_minutes <= tolerated * 2:
            score_breakdown["checkin_points"] = 15
        else:
            score_breakdown["checkin_points"] = 5  # Late but present

    # 2. Duration ratio (+40 pts)
    expected = appointment.get("duration_minutes", 30) * 60
    actual = session.get("active_duration_seconds", 0)
    if expected > 0:
        ratio = min(actual / expected, 1.0)
        score_breakdown["duration_points"] = int(ratio * 40)

    # 3. Video API confirmation (+30 pts) — extensible, always 0 for now
    # Future: check if video_evidence confirms this participant

    total = sum(score_breakdown.values())

    # Determine proof level
    if total >= 60:
        proof_level = "strong"
        suggested = "present"
    elif total >= 30:
        proof_level = "medium"
        suggested = "partial"
    else:
        proof_level = "weak"
        suggested = "absent"

    return {
        "score": total,
        "score_breakdown": score_breakdown,
        "proof_level": proof_level,
        "suggested_status": suggested,
    }


def _resolve_participant(appointment_id: str, token: str):
    """Find participant by invitation_token."""
    participant = db.participants.find_one(
        {"appointment_id": appointment_id, "invitation_token": token},
        {"_id": 0},
    )
    return participant


# ── Endpoints ───────────────────────────────────────────────────

@router.get("/{appointment_id}/info")
async def get_proof_info(appointment_id: str, token: str = Query(...)):
    """Get appointment info for the check-in page. Token-authenticated."""
    participant = _resolve_participant(appointment_id, token)
    if not participant:
        raise HTTPException(status_code=404, detail="Lien de check-in invalide ou expiré")

    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

    # NLYT Proof is only for video appointments
    if appointment.get("appointment_type") != "video":
        raise HTTPException(status_code=400, detail="Le système de preuve NLYT Proof est réservé aux rendez-vous en visioconférence")

    # Check if session already exists
    existing = db.proof_sessions.find_one(
        {"appointment_id": appointment_id, "participant_id": participant["participant_id"], "checked_out_at": None},
        {"_id": 0},
    )

    return {
        "appointment": {
            "appointment_id": appointment["appointment_id"],
            "title": appointment.get("title", ""),
            "start_datetime": appointment.get("start_datetime", ""),
            "duration_minutes": appointment.get("duration_minutes", 30),
            "meeting_join_url": appointment.get("meeting_join_url", ""),
            "meeting_provider": appointment.get("meeting_provider", ""),
            "status": appointment.get("status", ""),
        },
        "participant": {
            "participant_id": participant["participant_id"],
            "first_name": participant.get("first_name", ""),
            "last_name": participant.get("last_name", ""),
            "email": participant.get("email", ""),
            "role": participant.get("role", "participant"),
        },
        "active_session": {
            "session_id": existing["session_id"],
            "checked_in_at": existing["checked_in_at"],
            "heartbeat_count": existing.get("heartbeat_count", 0),
        } if existing else None,
    }


@router.post("/{appointment_id}/checkin")
async def checkin(appointment_id: str, req: CheckinRequest):
    """Start a proof session. Opens visio in parallel."""
    participant = _resolve_participant(appointment_id, req.token)
    if not participant:
        raise HTTPException(status_code=404, detail="Token de check-in invalide")

    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

    # NLYT Proof is only for video appointments
    if appointment.get("appointment_type") != "video":
        raise HTTPException(status_code=400, detail="Le système de preuve NLYT Proof est réservé aux rendez-vous en visioconférence")

    if appointment.get("status") == "cancelled":
        raise HTTPException(status_code=400, detail="Ce rendez-vous a été annulé")

    # Check for existing active session
    existing = db.proof_sessions.find_one(
        {"appointment_id": appointment_id, "participant_id": participant["participant_id"], "checked_out_at": None},
        {"_id": 0},
    )
    if existing:
        return {"session_id": existing["session_id"], "already_active": True, "meeting_join_url": appointment.get("meeting_join_url", "")}

    now = _now()
    session_id = str(uuid.uuid4())

    session_doc = {
        "session_id": session_id,
        "appointment_id": appointment_id,
        "participant_id": participant["participant_id"],
        "participant_email": participant.get("email", ""),
        "participant_name": f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip(),
        "role": participant.get("role", "participant"),
        "checked_in_at": now.isoformat(),
        "heartbeats": [now.isoformat()],
        "last_heartbeat": now.isoformat(),
        "heartbeat_count": 1,
        "checked_out_at": None,
        "active_duration_seconds": 0,
        "score": 0,
        "score_breakdown": {"checkin_points": 0, "duration_points": 0, "video_api_points": 0},
        "proof_level": "weak",
        "suggested_status": "absent",
        "final_status": None,
        "validated_by": None,
        "validated_at": None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    db.proof_sessions.insert_one(session_doc)

    logger.info(f"[PROOF] Check-in: {participant.get('email')} for apt {appointment_id} (session {session_id})")

    return {
        "session_id": session_id,
        "already_active": False,
        "checked_in_at": now.isoformat(),
        "meeting_join_url": appointment.get("meeting_join_url", ""),
    }


@router.post("/{appointment_id}/heartbeat")
async def heartbeat(appointment_id: str, req: HeartbeatRequest):
    """Record a heartbeat ping. Called every 30s by the client."""
    session = db.proof_sessions.find_one(
        {"session_id": req.session_id, "appointment_id": appointment_id, "checked_out_at": None},
        {"_id": 0},
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable ou déjà terminée")

    now = _now()
    db.proof_sessions.update_one(
        {"session_id": req.session_id},
        {
            "$push": {"heartbeats": now.isoformat()},
            "$set": {"last_heartbeat": now.isoformat(), "updated_at": now.isoformat()},
            "$inc": {"heartbeat_count": 1},
        },
    )

    return {"status": "ok", "heartbeat_count": session.get("heartbeat_count", 0) + 1}


@router.post("/{appointment_id}/checkout")
async def checkout(appointment_id: str, req: CheckoutRequest):
    """End proof session and compute score."""
    session = db.proof_sessions.find_one(
        {"session_id": req.session_id, "appointment_id": appointment_id},
        {"_id": 0},
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable")

    if session.get("checked_out_at"):
        return {"session_id": req.session_id, "already_closed": True, "score": session.get("score", 0), "proof_level": session.get("proof_level")}

    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})

    now = _now()
    heartbeats = session.get("heartbeats", [])
    heartbeats.append(now.isoformat())

    active_duration = _compute_active_duration(heartbeats)

    updated_session = {**session, "heartbeats": heartbeats, "active_duration_seconds": active_duration, "checked_out_at": now.isoformat()}
    scoring = _compute_score(updated_session, appointment or {})

    db.proof_sessions.update_one(
        {"session_id": req.session_id},
        {
            "$set": {
                "checked_out_at": now.isoformat(),
                "active_duration_seconds": active_duration,
                "heartbeats": heartbeats,
                **scoring,
                "updated_at": now.isoformat(),
            }
        },
    )

    logger.info(f"[PROOF] Checkout: session {req.session_id} | score={scoring['score']} | level={scoring['proof_level']}")

    return {
        "session_id": req.session_id,
        "active_duration_seconds": active_duration,
        **scoring,
    }


@router.get("/{appointment_id}/sessions")
async def get_sessions(appointment_id: str, user=Depends(get_current_user)):
    """Get all proof sessions for an appointment (organizer only)."""
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    if appointment.get("organizer_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="Accès réservé à l'organisateur")

    sessions = list(db.proof_sessions.find(
        {"appointment_id": appointment_id},
        {"_id": 0, "heartbeats": 0},
    ))

    return {"sessions": sessions, "count": len(sessions)}


@router.post("/{appointment_id}/validate")
async def validate_session(appointment_id: str, req: ValidateRequest, user=Depends(get_current_user)):
    """Organizer validates/overrides the suggested status."""
    if req.final_status not in ("present", "partial", "absent"):
        raise HTTPException(status_code=400, detail="Statut invalide. Valeurs: present, partial, absent")

    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    if appointment.get("organizer_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="Accès réservé à l'organisateur")

    session = db.proof_sessions.find_one({"session_id": req.session_id, "appointment_id": appointment_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable")

    now = _now()
    db.proof_sessions.update_one(
        {"session_id": req.session_id},
        {
            "$set": {
                "final_status": req.final_status,
                "validated_by": user["user_id"],
                "validated_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
        },
    )

    logger.info(f"[PROOF] Validated: session {req.session_id} → {req.final_status} by {user['user_id']}")

    return {"session_id": req.session_id, "final_status": req.final_status}
