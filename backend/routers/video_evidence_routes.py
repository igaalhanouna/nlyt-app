"""
Video Evidence Routes — API for ingesting and viewing video conference attendance data.

Endpoints:
- POST /api/video-evidence/{appointment_id}/ingest  — Ingest attendance data (organizer)
- GET  /api/video-evidence/{appointment_id}         — Get video evidence (organizer)
- GET  /api/video-evidence/{appointment_id}/logs     — Get ingestion logs (organizer)
- GET  /api/video-evidence/{appointment_id}/log/{id} — Get specific ingestion log (organizer)
- POST /api/video-evidence/webhook/{provider}        — Webhook endpoint (future)
"""
from fastapi import APIRouter, HTTPException, Request
from pymongo import MongoClient
from pydantic import BaseModel
from typing import Optional
import os
import sys

sys.path.append('/app/backend')
from middleware.auth_middleware import get_current_user
from services.video_evidence_service import (
    ingest_video_attendance,
    get_video_evidence_for_appointment,
    get_ingestion_log,
)

router = APIRouter()

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
client = MongoClient(MONGO_URL)
db = client[DB_NAME]


class VideoIngestionRequest(BaseModel):
    provider: str
    external_meeting_id: Optional[str] = None
    meeting_join_url: Optional[str] = None
    raw_payload: dict


@router.post("/{appointment_id}/ingest")
async def ingest_video_evidence(
    appointment_id: str,
    body: VideoIngestionRequest,
    request: Request,
):
    """
    Ingest video conference attendance data for an appointment.
    The organizer uploads the attendance report from Zoom/Teams/Meet.
    """
    user = await get_current_user(request)

    appointment = db.appointments.find_one(
        {"appointment_id": appointment_id}, {"_id": 0}
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

    if appointment.get("organizer_id") != user["user_id"]:
        raise HTTPException(
            status_code=403,
            detail="Seul l'organisateur peut ingérer les preuves vidéo",
        )

    # Store meeting_join_url if provided
    if body.meeting_join_url and not appointment.get("meeting_join_url"):
        db.appointments.update_one(
            {"appointment_id": appointment_id},
            {"$set": {"meeting_join_url": body.meeting_join_url}},
        )

    result = ingest_video_attendance(
        appointment_id=appointment_id,
        provider_name=body.provider,
        raw_payload=body.raw_payload,
        ingested_by=user["user_id"],
        external_meeting_id=body.external_meeting_id,
    )

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/{appointment_id}")
async def get_video_evidence(appointment_id: str, request: Request):
    """Get all video evidence for an appointment."""
    user = await get_current_user(request)

    appointment = db.appointments.find_one(
        {"appointment_id": appointment_id}, {"_id": 0}
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

    membership = db.workspace_memberships.find_one(
        {
            "workspace_id": appointment["workspace_id"],
            "user_id": user["user_id"],
        },
        {"_id": 0},
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Accès refusé")

    return get_video_evidence_for_appointment(appointment_id)


@router.get("/{appointment_id}/logs")
async def get_ingestion_logs(appointment_id: str, request: Request):
    """Get ingestion logs for an appointment."""
    user = await get_current_user(request)

    appointment = db.appointments.find_one(
        {"appointment_id": appointment_id}, {"_id": 0}
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

    if appointment.get("organizer_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="Accès réservé à l'organisateur")

    logs = list(
        db.video_ingestion_logs.find(
            {"appointment_id": appointment_id},
            {"_id": 0, "raw_payload": 0},
        ).sort("ingested_at", -1)
    )

    return {"appointment_id": appointment_id, "logs": logs}


@router.get("/{appointment_id}/log/{ingestion_log_id}")
async def get_single_ingestion_log(
    appointment_id: str,
    ingestion_log_id: str,
    request: Request,
):
    """Get a specific ingestion log with full details."""
    user = await get_current_user(request)

    appointment = db.appointments.find_one(
        {"appointment_id": appointment_id}, {"_id": 0}
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

    if appointment.get("organizer_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="Accès réservé à l'organisateur")

    log = get_ingestion_log(ingestion_log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log d'ingestion introuvable")

    if log.get("appointment_id") != appointment_id:
        raise HTTPException(status_code=403, detail="Log ne correspond pas au rendez-vous")

    return log


@router.post("/webhook/{provider}")
async def webhook_endpoint(provider: str, request: Request):
    """
    Webhook endpoint for video providers (Zoom, Teams).
    V1: Scaffolded — logs the webhook payload for future implementation.
    Authentication/verification to be added per provider.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Payload JSON invalide")

    # V1: Log the webhook for analysis, no auto-processing
    import logging
    import uuid
    from utils.date_utils import now_utc

    logger = logging.getLogger(__name__)
    logger.info(f"[WEBHOOK] Received {provider} webhook: {str(body)[:500]}")

    webhook_log = {
        "webhook_id": str(uuid.uuid4()),
        "provider": provider,
        "payload": body,
        "received_at": now_utc().isoformat(),
        "processed": False,
        "notes": "V1: logged for analysis, not auto-processed",
    }
    db.video_webhook_logs.insert_one(webhook_log)

    # Return 200 to acknowledge receipt (required by most webhook providers)
    return {"status": "received", "webhook_id": webhook_log["webhook_id"]}
