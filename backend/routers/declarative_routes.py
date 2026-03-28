"""
Declarative Routes — Attendance Sheets API
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List
import logging

from middleware.auth_middleware import get_current_user
from database import db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/pending")
async def get_pending_sheets(request: Request):
    """List appointments where the current user has an attendance sheet to fill."""
    user = await get_current_user(request)
    user_id = user['user_id']

    # Find all sheets for this user that are still pending
    sheets = list(db.attendance_sheets.find(
        {"submitted_by_user_id": user_id},
        {"_id": 0}
    ))

    if not sheets:
        return {"pending_sheets": [], "count": 0}

    # Group by appointment and enrich
    apt_ids = list({s['appointment_id'] for s in sheets})
    appointments = {
        a['appointment_id']: a
        for a in db.appointments.find(
            {"appointment_id": {"$in": apt_ids}},
            {"_id": 0, "appointment_id": 1, "title": 1, "start_datetime": 1,
             "duration_minutes": 1, "declarative_phase": 1, "declarative_deadline": 1}
        )
    }

    result = []
    for sheet in sheets:
        apt = appointments.get(sheet['appointment_id'])
        if not apt:
            continue
        # Only include if the appointment is still in collecting phase
        if apt.get('declarative_phase') != 'collecting':
            continue

        targets = [d for d in sheet.get('declarations', []) if d.get('target_participant_id')]

        if not targets:
            continue

        # Enrich target names
        for t in targets:
            if t.get('is_self_declaration'):
                t['target_name'] = 'Vous-même'
            else:
                p = db.participants.find_one(
                    {"participant_id": t['target_participant_id']},
                    {"_id": 0, "first_name": 1, "last_name": 1, "email": 1}
                )
                if p:
                    t['target_name'] = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or p.get('email', '')

        result.append({
            "appointment_id": sheet['appointment_id'],
            "sheet_id": sheet.get('sheet_id'),
            "title": apt.get('title', 'Sans titre'),
            "start_datetime": apt.get('start_datetime'),
            "duration_minutes": apt.get('duration_minutes'),
            "declarative_deadline": apt.get('declarative_deadline'),
            "targets_count": len(targets),
            "targets": targets,
            "already_submitted": sheet.get('status') == 'submitted',
        })

    # Sort: pending first, then by deadline
    result.sort(key=lambda x: (x['already_submitted'], x.get('declarative_deadline') or ''))

    pending_count = sum(1 for r in result if not r['already_submitted'])
    return {"pending_sheets": result, "count": pending_count}



class DeclarationItem(BaseModel):
    target_participant_id: str
    declared_status: str  # present_on_time | present_late | absent | unknown


class SubmitSheetBody(BaseModel):
    declarations: List[DeclarationItem]


@router.get("/{appointment_id}")
async def get_my_sheet(appointment_id: str, request: Request):
    """Get current user's attendance sheet for this appointment."""
    user = await get_current_user(request)

    sheet = db.attendance_sheets.find_one(
        {"appointment_id": appointment_id, "submitted_by_user_id": user['user_id']},
        {"_id": 0}
    )
    if not sheet:
        raise HTTPException(status_code=404, detail="Aucune feuille de presence trouvee")

    # Enrich targets with names
    for d in sheet.get('declarations', []):
        if d.get('is_self_declaration'):
            d['target_name'] = 'Vous-même'
        else:
            p = db.participants.find_one(
                {"participant_id": d['target_participant_id']},
                {"_id": 0, "first_name": 1, "last_name": 1, "email": 1}
            )
            if p:
                d['target_name'] = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or p.get('email', '')

    return sheet


@router.get("/{appointment_id}/status")
async def get_sheet_status(appointment_id: str, request: Request):
    """Get global status of attendance sheets."""
    await get_current_user(request)
    from services.declarative_service import get_sheet_status
    return get_sheet_status(appointment_id)


@router.post("/{appointment_id}/submit")
async def submit_sheet(appointment_id: str, body: SubmitSheetBody, request: Request):
    """Submit attendance sheet."""
    user = await get_current_user(request)

    from services.declarative_service import submit_sheet as do_submit
    result = do_submit(
        appointment_id,
        user['user_id'],
        [d.model_dump() for d in body.declarations]
    )

    if result.get('error'):
        raise HTTPException(status_code=400, detail=result['error'])

    return result
