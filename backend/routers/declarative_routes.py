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

    # Fallback: also find sheets linked by participant_id (auto-linkage may not have run yet)
    if not sheets:
        my_pids = [p["participant_id"] for p in db.participants.find(
            {"user_id": user_id},
            {"_id": 0, "participant_id": 1}
        )]
        if my_pids:
            sheets = list(db.attendance_sheets.find(
                {"submitted_by_participant_id": {"$in": my_pids}},
                {"_id": 0}
            ))
            # Fix linkage for future lookups
            for s in sheets:
                if s.get("submitted_by_user_id") != user_id:
                    db.attendance_sheets.update_one(
                        {"sheet_id": s["sheet_id"]},
                        {"$set": {"submitted_by_user_id": user_id}}
                    )

    if not sheets:
        return {"pending_sheets": [], "count": 0}

    # Group by appointment and enrich
    apt_ids = list({s['appointment_id'] for s in sheets})
    appointments = {
        a['appointment_id']: a
        for a in db.appointments.find(
            {"appointment_id": {"$in": apt_ids}},
            {"_id": 0, "appointment_id": 1, "title": 1, "start_datetime": 1,
             "duration_minutes": 1, "declarative_phase": 1, "declarative_deadline": 1,
             "appointment_type": 1, "location": 1, "location_display_name": 1,
             "meeting_provider": 1}
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

        # Retroactive filter: exclude sheets where ALL non-self targets are terminal
        TERMINAL_STATUSES = {'cancelled_by_participant', 'declined', 'guarantee_released'}
        non_self_targets = [t for t in targets if not t.get('is_self_declaration')]
        if non_self_targets:
            # Check each non-self target's current participant status
            target_pids = [t['target_participant_id'] for t in non_self_targets]
            target_participants = {
                tp['participant_id']: tp
                for tp in db.participants.find(
                    {"participant_id": {"$in": target_pids}},
                    {"_id": 0, "participant_id": 1, "status": 1}
                )
            }
            relevant_non_self = [
                t for t in non_self_targets
                if target_participants.get(t['target_participant_id'], {}).get('status') not in TERMINAL_STATUSES
            ]
            if not relevant_non_self:
                # All non-self targets are terminal → sheet no longer useful
                continue
        else:
            # Only self-declarations remain → no dispute to resolve
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
            "appointment_type": apt.get('appointment_type', ''),
            "appointment_location": apt.get('location_display_name') or apt.get('location', ''),
            "appointment_meeting_provider": apt.get('meeting_provider', ''),
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

    # Enrich with appointment context
    apt = db.appointments.find_one(
        {"appointment_id": appointment_id},
        {"_id": 0, "title": 1, "start_datetime": 1, "duration_minutes": 1,
         "appointment_type": 1, "location": 1, "location_display_name": 1,
         "meeting_provider": 1}
    )
    if apt:
        sheet['appointment_title'] = apt.get('title', '')
        sheet['appointment_start_datetime'] = apt.get('start_datetime', '')
        sheet['appointment_duration_minutes'] = apt.get('duration_minutes', 0)
        sheet['appointment_type'] = apt.get('appointment_type', '')
        sheet['appointment_location'] = apt.get('location_display_name') or apt.get('location', '')
        sheet['appointment_meeting_provider'] = apt.get('meeting_provider', '')

    # Enrich targets with names
    for d in sheet.get('declarations', []):
        if d.get('is_self_declaration'):
            d['target_name'] = 'Vous-meme'
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
