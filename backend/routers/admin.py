from fastapi import APIRouter, HTTPException, Request
import os
import sys
sys.path.append('/app/backend')
from middleware.auth_middleware import get_current_user

from database import db
router = APIRouter()


@router.get("/cases/review")
async def get_cases_for_review(request: Request):
    user = await get_current_user(request)
    
    cases = list(db.violation_cases.find(
        {"status": "manual_review"},
        {"_id": 0}
    ).sort("created_at", -1))
    
    return {"cases": cases}

@router.get("/disputes/pending")
async def get_pending_disputes(request: Request):
    user = await get_current_user(request)
    
    disputes = list(db.disputes.find(
        {"status": {"$in": ["open", "under_review"]}},
        {"_id": 0}
    ).sort("created_at", -1))
    
    return {"disputes": disputes}

@router.get("/analytics/overview")
async def get_admin_analytics(request: Request):
    user = await get_current_user(request)
    
    total_appointments = db.appointments.count_documents({})
    active_appointments = db.appointments.count_documents({"status": "active"})
    total_participants = db.participants.count_documents({})
    accepted_participants = db.participants.count_documents({"status": "accepted"})
    
    total_guarantees = db.payment_guarantees.count_documents({})
    active_guarantees = db.payment_guarantees.count_documents({"status": "authorization_active"})
    
    total_disputes = db.disputes.count_documents({})
    pending_disputes = db.disputes.count_documents({"status": {"$in": ["open", "under_review"]}})
    
    return {
        "appointments": {
            "total": total_appointments,
            "active": active_appointments
        },
        "participants": {
            "total": total_participants,
            "accepted": accepted_participants
        },
        "guarantees": {
            "total": total_guarantees,
            "active": active_guarantees
        },
        "disputes": {
            "total": total_disputes,
            "pending": pending_disputes
        }
    }

@router.get("/stripe-events")
async def get_stripe_events(limit: int = 50, request: Request = None):
    user = await get_current_user(request)
    
    events = list(db.stripe_events.find(
        {},
        {"_id": 0}
    ).sort("received_at", -1).limit(limit))
    
    return {"events": events}