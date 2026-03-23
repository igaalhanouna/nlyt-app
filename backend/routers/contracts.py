from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
import os
import sys
sys.path.append('/app/backend')
from models.schemas import AcceptanceCreate
from middleware.auth_middleware import get_optional_user
from utils.date_utils import now_utc
from services.contract_service import ContractService

from database import db
router = APIRouter()


@router.get("/invitation/{invitation_token}")
async def get_invitation_details(invitation_token: str):
    participant = db.participants.find_one({"invitation_token": invitation_token}, {"_id": 0})
    
    if not participant:
        raise HTTPException(status_code=404, detail="Invitation introuvable")
    
    appointment = db.appointments.find_one({"appointment_id": participant['appointment_id']}, {"_id": 0})
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    
    snapshot = db.policy_snapshots.find_one({"snapshot_id": appointment['policy_snapshot_id']}, {"_id": 0})
    
    organizer = db.users.find_one({"user_id": appointment['organizer_id']}, {"_id": 0, "password_hash": 0})
    
    return {
        "participant": participant,
        "appointment": appointment,
        "policy_snapshot": snapshot,
        "organizer": organizer
    }

@router.get("/contract/{appointment_id}/html", response_class=HTMLResponse)
async def get_contract_html(appointment_id: str, participant_id: str):
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    
    snapshot = db.policy_snapshots.find_one({"snapshot_id": appointment['policy_snapshot_id']}, {"_id": 0})
    participant = db.participants.find_one({"participant_id": participant_id}, {"_id": 0})
    
    if not snapshot or not participant:
        raise HTTPException(status_code=404, detail="Données introuvables")
    
    html = ContractService.generate_html_contract(snapshot, participant)
    return HTMLResponse(content=html)

@router.post("/accept")
async def accept_contract(acceptance: AcceptanceCreate, request: Request):
    participant = db.participants.find_one({"participant_id": acceptance.participant_id}, {"_id": 0})
    
    if not participant:
        raise HTTPException(status_code=404, detail="Participant introuvable")
    
    if participant['status'] == 'accepted':
        raise HTTPException(status_code=400, detail="Contrat déjà accepté")
    
    appointment = db.appointments.find_one({"appointment_id": acceptance.appointment_id}, {"_id": 0})
    snapshot = db.policy_snapshots.find_one({"snapshot_id": appointment['policy_snapshot_id']}, {"_id": 0})
    
    acceptance_record = ContractService.record_acceptance(
        appointment_id=acceptance.appointment_id,
        participant_id=acceptance.participant_id,
        snapshot_id=appointment['policy_snapshot_id'],
        ip_address=acceptance.ip_address,
        user_agent=acceptance.user_agent,
        locale=acceptance.locale,
        timezone=acceptance.timezone,
        signer_name=f"{participant['first_name']} {participant['last_name']}",
        signer_email=participant['email']
    )
    
    db.participants.update_one(
        {"participant_id": acceptance.participant_id},
        {"$set": {"status": "accepted", "accepted_at": now_utc().isoformat()}}
    )
    
    return {
        "acceptance_id": acceptance_record['acceptance_id'],
        "message": "Contrat accepté avec succès"
    }

@router.get("/acceptance/{acceptance_id}")
async def get_acceptance(acceptance_id: str):
    acceptance = db.acceptances.find_one({"acceptance_id": acceptance_id}, {"_id": 0})
    
    if not acceptance:
        raise HTTPException(status_code=404, detail="Acceptation introuvable")
    
    return acceptance