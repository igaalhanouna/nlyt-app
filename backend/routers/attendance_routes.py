"""
Attendance Routes — Post-appointment presence detection API
Endpoints for evaluating, viewing, and reclassifying attendance outcomes.
"""
from fastapi import APIRouter, HTTPException, Request, Query
from pymongo import MongoClient
from pydantic import BaseModel
from typing import Optional
import os
import sys
sys.path.append('/app/backend')
from middleware.auth_middleware import get_current_user
from services.attendance_service import (
    evaluate_appointment,
    reclassify_participant,
    run_attendance_evaluation_job
)

router = APIRouter()

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
client = MongoClient(MONGO_URL)
db = client[DB_NAME]


class ReclassifyRequest(BaseModel):
    new_outcome: str
    notes: Optional[str] = None


@router.post("/evaluate/{appointment_id}")
async def trigger_evaluate(appointment_id: str, request: Request):
    """Manually trigger attendance evaluation for a specific appointment."""
    user = await get_current_user(request)

    appointment = db.appointments.find_one(
        {"appointment_id": appointment_id}, {"_id": 0}
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

    if appointment.get('organizer_id') != user['user_id']:
        raise HTTPException(
            status_code=403,
            detail="Seul l'organisateur peut déclencher l'évaluation"
        )

    result = evaluate_appointment(appointment_id)
    return result


@router.get("/{appointment_id}")
async def get_attendance(appointment_id: str, request: Request):
    """Get attendance records for a specific appointment."""
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

    records = list(db.attendance_records.find(
        {"appointment_id": appointment_id},
        {"_id": 0}
    ))

    return {
        "appointment_id": appointment_id,
        "evaluated": appointment.get('attendance_evaluated', False),
        "evaluated_at": appointment.get('attendance_evaluated_at'),
        "summary": appointment.get('attendance_summary', {}),
        "records": records
    }


@router.put("/reclassify/{record_id}")
async def reclassify(record_id: str, body: ReclassifyRequest, request: Request):
    """Manually reclassify a participant's attendance outcome."""
    user = await get_current_user(request)

    record = db.attendance_records.find_one(
        {"record_id": record_id}, {"_id": 0}
    )
    if not record:
        raise HTTPException(status_code=404, detail="Enregistrement introuvable")

    appointment = db.appointments.find_one(
        {"appointment_id": record['appointment_id']}, {"_id": 0}
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

    if appointment.get('organizer_id') != user['user_id']:
        raise HTTPException(
            status_code=403,
            detail="Seul l'organisateur peut reclassifier"
        )

    result = reclassify_participant(
        record_id=record_id,
        new_outcome=body.new_outcome,
        notes=body.notes,
        reviewer_id=user['user_id']
    )

    if result.get('error'):
        raise HTTPException(status_code=400, detail=result['error'])

    return result


@router.get("/pending-reviews/list")
async def get_pending_reviews(request: Request):
    """Get all attendance records requiring manual review for the current user."""
    user = await get_current_user(request)

    memberships = list(db.workspace_memberships.find(
        {"user_id": user['user_id']}, {"_id": 0}
    ))
    workspace_ids = [m['workspace_id'] for m in memberships]

    appointments = list(db.appointments.find(
        {
            "workspace_id": {"$in": workspace_ids},
            "organizer_id": user['user_id'],
            "attendance_evaluated": True
        },
        {"_id": 0, "appointment_id": 1, "title": 1, "start_datetime": 1}
    ))
    apt_ids = [a['appointment_id'] for a in appointments]
    apt_map = {a['appointment_id']: a for a in appointments}

    records = list(db.attendance_records.find(
        {
            "appointment_id": {"$in": apt_ids},
            "review_required": True
        },
        {"_id": 0}
    ))

    for r in records:
        apt = apt_map.get(r['appointment_id'], {})
        r['appointment_title'] = apt.get('title', '')
        r['appointment_datetime'] = apt.get('start_datetime', '')

    return {"pending_reviews": records, "count": len(records)}
