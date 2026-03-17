from fastapi import APIRouter, HTTPException, Request
from pymongo import MongoClient
import os
import uuid
import sys
sys.path.append('/app/backend')
from models.schemas import ParticipantAdd
from middleware.auth_middleware import get_current_user
from utils.date_utils import now_utc
from services.email_service import EmailService

router = APIRouter()

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
client = MongoClient(MONGO_URL)
db = client[DB_NAME]

def get_frontend_url(request: Request) -> str:
    """Get FRONTEND_URL from env, fallback to request.base_url"""
    frontend_url = os.environ.get('FRONTEND_URL', '')
    if frontend_url:
        return frontend_url.rstrip('/')
    return str(request.base_url).rstrip('/')

@router.post("/")
async def add_participant(participant: ParticipantAdd, appointment_id: str, request: Request):
    user = await get_current_user(request)
    
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    
    if appointment['organizer_id'] != user['user_id']:
        raise HTTPException(status_code=403, detail="Seul l'organisateur peut ajouter des participants")
    
    existing = db.participants.find_one({
        "appointment_id": appointment_id,
        "email": participant.email
    }, {"_id": 0})
    
    if existing:
        raise HTTPException(status_code=400, detail="Ce participant est déjà invité")
    
    participant_id = str(uuid.uuid4())
    invitation_token = str(uuid.uuid4())
    
    participant_doc = {
        "participant_id": participant_id,
        "appointment_id": appointment_id,
        "email": participant.email,
        "first_name": participant.first_name,
        "last_name": participant.last_name,
        "role": participant.role,
        "status": "invited",
        "invitation_token": invitation_token,
        "invited_at": now_utc().isoformat(),
        "accepted_at": None
    }
    
    db.participants.insert_one(participant_doc)
    
    base_url = get_frontend_url(request)
    invitation_link = f"{base_url}/invitation/{invitation_token}"
    
    organizer = db.users.find_one({"user_id": user['user_id']}, {"_id": 0})
    organizer_name = f"{organizer['first_name']} {organizer['last_name']}"
    
    await EmailService.send_invitation_email(
        to_email=participant.email,
        to_name=f"{participant.first_name} {participant.last_name}",
        organizer_name=organizer_name,
        appointment_title=appointment['title'],
        appointment_datetime=appointment['start_datetime'],
        invitation_link=invitation_link
    )
    
    return {
        "participant_id": participant_id,
        "invitation_token": invitation_token,
        "message": "Participant ajouté et invité"
    }

@router.get("/")
async def list_participants(appointment_id: str, request: Request):
    user = await get_current_user(request)
    
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    
    membership = db.workspace_memberships.find_one({
        "workspace_id": appointment['workspace_id'],
        "user_id": user['user_id']
    }, {"_id": 0})
    
    if not membership:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    participants = list(db.participants.find({"appointment_id": appointment_id}, {"_id": 0}))
    
    return {"participants": participants}

@router.get("/{participant_id}")
async def get_participant(participant_id: str, request: Request):
    user = await get_current_user(request)
    
    participant = db.participants.find_one({"participant_id": participant_id}, {"_id": 0})
    
    if not participant:
        raise HTTPException(status_code=404, detail="Participant introuvable")
    
    appointment = db.appointments.find_one({"appointment_id": participant['appointment_id']}, {"_id": 0})
    
    membership = db.workspace_memberships.find_one({
        "workspace_id": appointment['workspace_id'],
        "user_id": user['user_id']
    }, {"_id": 0})
    
    if not membership:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    return participant