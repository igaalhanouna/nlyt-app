"""
Notification routes — in-app notification system.
"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from middleware.auth_middleware import get_current_user
from services.notification_service import (
    get_unread_counts,
    mark_as_read,
    mark_read_by_reference,
    get_unread_reference_ids,
)

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("/counts")
async def get_counts(request: Request):
    """Get unread notification counts by category."""
    user = await get_current_user(request)
    counts = get_unread_counts(user["user_id"])
    return counts


class MarkReadBody(BaseModel):
    event_type: str
    reference_id: str


@router.post("/mark-read")
async def mark_read(body: MarkReadBody, request: Request):
    """Mark notifications as read by event_type + reference_id."""
    user = await get_current_user(request)
    count = mark_read_by_reference(user["user_id"], body.event_type, body.reference_id)
    return {"marked": count}


@router.get("/unread-ids/{event_type}")
async def get_unread_ids(event_type: str, request: Request):
    """Get list of unread reference_ids for a given event_type."""
    user = await get_current_user(request)
    valid_types = ("decision", "dispute_update", "modification")
    if event_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Type invalide. Valeurs: {', '.join(valid_types)}")
    ids = get_unread_reference_ids(user["user_id"], event_type)
    return {"unread_ids": ids}
