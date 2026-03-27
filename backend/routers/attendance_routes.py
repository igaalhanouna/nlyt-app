"""
Attendance Routes — Post-appointment presence detection API
Endpoints for evaluating, viewing, and reclassifying attendance outcomes.
"""
from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel
from typing import Optional
import os
import sys
sys.path.append('/app/backend')
from middleware.auth_middleware import get_current_user
from database import db
from services.attendance_service import (
    evaluate_appointment,
    reevaluate_appointment,
    reclassify_participant,
    run_attendance_evaluation_job
)

router = APIRouter()



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


@router.post("/reevaluate/{appointment_id}")
async def trigger_reevaluate(appointment_id: str, request: Request):
    """Re-evaluate attendance with fresh evidence. Preserves manual reclassifications."""
    user = await get_current_user(request)

    appointment = db.appointments.find_one(
        {"appointment_id": appointment_id}, {"_id": 0}
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

    if appointment.get('organizer_id') != user['user_id']:
        raise HTTPException(
            status_code=403,
            detail="Seul l'organisateur peut déclencher la re-évaluation"
        )

    result = reevaluate_appointment(appointment_id)
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

    # V3 Trustless: block reclassification if organizer has financial conflict of interest
    if body.new_outcome in ('no_show', 'late'):
        # Check: is the organizer a beneficiary of this reclassification?
        reclassified_participant = db.participants.find_one(
            {"participant_id": record['participant_id']},
            {"_id": 0, "is_organizer": 1, "user_id": 1}
        )
        if reclassified_participant and not reclassified_participant.get('is_organizer', False):
            logger.warning(f"[TRUSTLESS][CONFLIT] Reclassification bloquée: organizer {user['user_id']} tentait de reclassifier {record['participant_id']} → {body.new_outcome} (conflit d'intérêt)")
            raise HTTPException(
                status_code=403,
                detail="Conflit d'interet : vous etes beneficiaire financier de cette decision. Ce litige sera arbitre par la plateforme."
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
    """Get all attendance records requiring manual review for the current user.
    Returns enriched data for the Disputes page."""
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
        {"_id": 0, "appointment_id": 1, "title": 1, "start_datetime": 1,
         "duration_minutes": 1, "appointment_type": 1, "gps_radius_meters": 1,
         "tolerated_delay_minutes": 1}
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

    # Enrich each record with participant info, evidence summary, and timeout
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    REVIEW_TIMEOUT_DAYS = 15

    for r in records:
        apt = apt_map.get(r['appointment_id'], {})
        r['appointment_title'] = apt.get('title', '')
        r['appointment_datetime'] = apt.get('start_datetime', '')
        r['appointment_type'] = apt.get('appointment_type', 'physical')
        r['duration_minutes'] = apt.get('duration_minutes', 60)

        # Participant info
        participant = db.participants.find_one(
            {"participant_id": r.get('participant_id')},
            {"_id": 0, "first_name": 1, "last_name": 1, "email": 1}
        )
        if participant:
            name = " ".join(filter(None, [participant.get('first_name'), participant.get('last_name')]))
            r['participant_name'] = name or participant.get('email', '')
            r['participant_email'] = participant.get('email', '')
        else:
            r['participant_name'] = r.get('participant_id', '')[:8]
            r['participant_email'] = ''

        # Evidence summary
        evidence = list(db.evidence_items.find(
            {
                "appointment_id": r['appointment_id'],
                "participant_id": r['participant_id']
            },
            {"_id": 0, "source": 1, "derived_facts": 1}
        ))
        evidence_sources = []
        for e in evidence:
            facts = e.get('derived_facts', {})
            if e['source'] == 'manual_checkin':
                if facts.get('latitude'):
                    dist = facts.get('distance_meters')
                    evidence_sources.append(f"GPS ({int(dist)}m)" if dist else "GPS")
                else:
                    evidence_sources.append("Check-in manuel (sans GPS)")
            elif e['source'] == 'gps':
                dist = facts.get('distance_meters')
                evidence_sources.append(f"GPS {int(dist)}m" if dist else "GPS")
            elif e['source'] == 'qr':
                evidence_sources.append("QR code")
            elif e['source'] == 'video_conference':
                evidence_sources.append(f"Video ({facts.get('provider', '?')})")
            else:
                evidence_sources.append(e['source'])
        r['evidence_sources'] = evidence_sources
        r['evidence_count'] = len(evidence)

        # Timeout calculation
        decided_at = r.get('decided_at')
        if decided_at:
            try:
                decided_dt = datetime.fromisoformat(decided_at.replace('Z', '+00:00'))
                timeout_dt = decided_dt + timedelta(days=REVIEW_TIMEOUT_DAYS)
                days_remaining = max(0, (timeout_dt - now).days)
                r['days_remaining'] = days_remaining
                r['timeout_date'] = timeout_dt.isoformat()
            except Exception:
                r['days_remaining'] = REVIEW_TIMEOUT_DAYS
                r['timeout_date'] = None
        else:
            r['days_remaining'] = REVIEW_TIMEOUT_DAYS
            r['timeout_date'] = None

    return {"pending_reviews": records, "count": len(records)}
