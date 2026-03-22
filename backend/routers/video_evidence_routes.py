"""
Video Evidence Routes — API for ingesting and viewing video conference attendance data.

Endpoints:
- POST /api/video-evidence/{appointment_id}/ingest  — Ingest attendance data (organizer)
- POST /api/video-evidence/{appointment_id}/ingest-file — Ingest from CSV/JSON file upload
- GET  /api/video-evidence/{appointment_id}         — Get video evidence (organizer)
- GET  /api/video-evidence/{appointment_id}/logs     — Get ingestion logs (organizer)
- GET  /api/video-evidence/{appointment_id}/log/{id} — Get specific ingestion log (organizer)
- POST /api/video-evidence/{appointment_id}/create-meeting — Create meeting via provider API
- POST /api/video-evidence/{appointment_id}/fetch-attendance — Fetch attendance via provider API
- GET  /api/video-evidence/provider-status — Check which providers are configured
- POST /api/video-evidence/webhook/{provider}        — Webhook endpoint (future)
"""
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from pymongo import MongoClient
from pydantic import BaseModel
from typing import Optional
import os
import sys
import csv
import io
import json

sys.path.append('/app/backend')
from middleware.auth_middleware import get_current_user
from services.video_evidence_service import (
    ingest_video_attendance,
    get_video_evidence_for_appointment,
    get_ingestion_log,
)
from services.meeting_provider_service import (
    create_meeting_for_appointment,
    fetch_attendance_for_appointment,
    get_provider_status,
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


class CreateMeetingRequest(BaseModel):
    provider: Optional[str] = None  # Override provider from appointment


@router.post("/{appointment_id}/create-meeting")
async def create_meeting(appointment_id: str, body: CreateMeetingRequest = None, request: Request = None):
    """Create a meeting via the provider API (Zoom/Teams/Meet)."""
    user = await get_current_user(request)

    appointment = db.appointments.find_one(
        {"appointment_id": appointment_id}, {"_id": 0}
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    if appointment.get("organizer_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="Seul l'organisateur peut créer la réunion")

    # Already has a meeting created?
    if appointment.get("meeting_created_via_api") and appointment.get("meeting_join_url"):
        return {
            "already_exists": True,
            "external_meeting_id": appointment.get("external_meeting_id"),
            "join_url": appointment.get("meeting_join_url"),
            "host_url": appointment.get("meeting_host_url"),
        }

    provider = (body.provider if body and body.provider else appointment.get("meeting_provider") or "").strip().lower()
    if not provider:
        raise HTTPException(status_code=400, detail="Aucun provider de visioconférence spécifié")

    result = create_meeting_for_appointment(
        appointment_id=appointment_id,
        provider=provider,
        title=appointment.get("title", "NLYT Meeting"),
        start_datetime=appointment.get("start_datetime", ""),
        duration_minutes=appointment.get("duration_minutes", 60),
        timezone_str=appointment.get("appointment_timezone", "UTC"),
        organizer_user_id=user["user_id"],
    )

    if result.get("error"):
        status_code = 424 if result.get("needs_config") else 400
        raise HTTPException(status_code=status_code, detail=result["error"])

    return result


@router.post("/{appointment_id}/fetch-attendance")
async def fetch_attendance(appointment_id: str, request: Request):
    """Fetch attendance report from provider API (Zoom/Teams) and auto-ingest."""
    user = await get_current_user(request)

    appointment = db.appointments.find_one(
        {"appointment_id": appointment_id}, {"_id": 0}
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    if appointment.get("organizer_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="Seul l'organisateur peut récupérer les présences")

    result = fetch_attendance_for_appointment(appointment_id)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    # Auto-ingest the fetched data
    if result.get("raw_payload"):
        ingest_result = ingest_video_attendance(
            appointment_id=appointment_id,
            provider_name=result["provider"],
            raw_payload=result["raw_payload"],
            ingested_by=user["user_id"],
            external_meeting_id=appointment.get("external_meeting_id"),
        )
        return {
            "success": True,
            "provider": result["provider"],
            "fetch_source": "api",
            "ingestion_result": ingest_result,
        }

    return result


@router.post("/{appointment_id}/ingest-file")
async def ingest_file(
    appointment_id: str,
    request: Request,
    file: UploadFile = File(...),
    provider: str = Form("zoom"),
):
    """
    Ingest attendance from a CSV or JSON file upload.
    Supports:
    - Zoom CSV export (Name, Email, Join Time, Leave Time, Duration)
    - JSON format (same as manual JSON input)
    """
    user = await get_current_user(request)

    appointment = db.appointments.find_one(
        {"appointment_id": appointment_id}, {"_id": 0}
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    if appointment.get("organizer_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="Seul l'organisateur peut importer les preuves")

    content = await file.read()
    filename = (file.filename or "").lower()

    try:
        if filename.endswith(".csv"):
            raw_payload = _parse_csv_to_payload(content, provider)
        elif filename.endswith(".json"):
            raw_payload = json.loads(content.decode("utf-8"))
        else:
            # Try JSON first, then CSV
            try:
                raw_payload = json.loads(content.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                raw_payload = _parse_csv_to_payload(content, provider)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur de parsing du fichier: {str(e)}")

    result = ingest_video_attendance(
        appointment_id=appointment_id,
        provider_name=provider,
        raw_payload=raw_payload,
        ingested_by=user["user_id"],
        external_meeting_id=appointment.get("external_meeting_id"),
    )

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/provider-status")
async def provider_status_endpoint(request: Request):
    """Check which video providers are configured and ready."""
    await get_current_user(request)
    return get_provider_status()


def _parse_csv_to_payload(content: bytes, provider: str) -> dict:
    """Parse CSV file to standard attendance payload format."""
    text = content.decode("utf-8-sig")  # Handle BOM
    reader = csv.DictReader(io.StringIO(text))

    participants = []
    for row in reader:
        # Normalize column names (Zoom CSV format varies)
        name = row.get("Name (Original Name)") or row.get("Name") or row.get("Nom") or row.get("name") or ""
        email = row.get("User Email") or row.get("Email") or row.get("email") or row.get("Email Address") or ""
        join_time = row.get("Join Time") or row.get("join_time") or row.get("Heure d'arrivée") or ""
        leave_time = row.get("Leave Time") or row.get("leave_time") or row.get("Heure de départ") or ""
        duration_str = row.get("Duration (Minutes)") or row.get("Duration") or row.get("duration") or row.get("Durée (Minutes)") or ""

        # Convert duration to seconds if in minutes
        duration_seconds = None
        if duration_str:
            try:
                duration_val = float(duration_str.strip())
                if duration_val < 500:  # Likely minutes
                    duration_seconds = int(duration_val * 60)
                else:
                    duration_seconds = int(duration_val)
            except ValueError:
                pass

        if name.strip() or email.strip():
            p = {"name": name.strip(), "email": email.strip()}
            if join_time.strip():
                p["join_time"] = join_time.strip()
            if leave_time.strip():
                p["leave_time"] = leave_time.strip()
            if duration_seconds is not None:
                p["duration"] = duration_seconds
            participants.append(p)

    if not participants:
        raise ValueError("Aucun participant trouvé dans le fichier CSV")

    return {"meeting_id": "csv-import", "participants": participants}



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
