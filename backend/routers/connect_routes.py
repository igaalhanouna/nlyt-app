"""
Stripe Connect Express — API routes

POST /api/connect/onboard    → Start/resume onboarding
GET  /api/connect/status     → Get Connect status
POST /api/connect/dashboard  → Get Stripe Express dashboard link
"""
import sys
sys.path.append('/app/backend')

from fastapi import APIRouter, HTTPException, Request
from middleware.auth_middleware import get_current_user
from services.connect_service import (
    start_onboarding,
    get_connect_status,
    create_dashboard_link,
)

router = APIRouter()


@router.post("/onboard")
async def onboard_connect(request: Request):
    """Start or resume Stripe Connect Express onboarding."""
    user = await get_current_user(request)

    result = start_onboarding(user["user_id"])
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Erreur onboarding"))

    return result


@router.get("/status")
async def connect_status(request: Request):
    """Get current Stripe Connect status."""
    user = await get_current_user(request)
    status = get_connect_status(user["user_id"])
    status["user_id"] = user["user_id"]
    return status


@router.post("/dashboard")
async def connect_dashboard(request: Request):
    """Generate Stripe Express Dashboard link."""
    user = await get_current_user(request)

    result = create_dashboard_link(user["user_id"])
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Erreur dashboard"))

    return result
