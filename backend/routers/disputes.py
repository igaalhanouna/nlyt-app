from fastapi import APIRouter, HTTPException, Request
import os
import uuid
import sys
sys.path.append('/app/backend')
from models.schemas import DisputeCreate
from middleware.auth_middleware import get_current_user
from utils.date_utils import now_utc

from database import db
router = APIRouter()


@router.post("/")
async def create_dispute(dispute: DisputeCreate, request: Request):
    user = await get_current_user(request)
    
    violation_case = db.violation_cases.find_one({"case_id": dispute.violation_case_id}, {"_id": 0})
    
    if not violation_case:
        raise HTTPException(status_code=404, detail="Cas de violation introuvable")
    
    dispute_id = str(uuid.uuid4())
    
    dispute_doc = {
        "dispute_id": dispute_id,
        "violation_case_id": dispute.violation_case_id,
        "participant_id": dispute.participant_id,
        "filed_by_user_id": user['user_id'],
        "reason": dispute.reason,
        "description": dispute.description,
        "status": "open",
        "created_at": now_utc().isoformat(),
        "updated_at": now_utc().isoformat(),
        "resolved_at": None,
        "resolution": None
    }
    
    db.disputes.insert_one(dispute_doc)
    
    return {
        "dispute_id": dispute_id,
        "message": "Contestation créée avec succès"
    }

@router.get("/")
async def list_disputes(appointment_id: str = None, request: Request = None):
    user = await get_current_user(request)
    
    query = {}
    
    if appointment_id:
        violation_cases = list(db.violation_cases.find({"appointment_id": appointment_id}, {"_id": 0}))
        case_ids = [vc['case_id'] for vc in violation_cases]
        query["violation_case_id"] = {"$in": case_ids}
    
    disputes = list(db.disputes.find(query, {"_id": 0}).sort("created_at", -1))
    
    return {"disputes": disputes}

@router.get("/{dispute_id}")
async def get_dispute(dispute_id: str, request: Request):
    user = await get_current_user(request)
    
    dispute = db.disputes.find_one({"dispute_id": dispute_id}, {"_id": 0})
    
    if not dispute:
        raise HTTPException(status_code=404, detail="Contestation introuvable")
    
    return dispute

@router.patch("/{dispute_id}")
async def update_dispute_status(dispute_id: str, status: str, resolution: str = None, request: Request = None):
    user = await get_current_user(request)
    
    dispute = db.disputes.find_one({"dispute_id": dispute_id}, {"_id": 0})
    
    if not dispute:
        raise HTTPException(status_code=404, detail="Contestation introuvable")
    
    update_data = {
        "status": status,
        "updated_at": now_utc().isoformat()
    }
    
    if status == "resolved" and resolution:
        update_data["resolution"] = resolution
        update_data["resolved_at"] = now_utc().isoformat()
    
    db.disputes.update_one(
        {"dispute_id": dispute_id},
        {"$set": update_data}
    )
    
    return {"message": "Contestation mise à jour"}