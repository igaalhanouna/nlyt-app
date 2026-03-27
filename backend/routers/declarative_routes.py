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
