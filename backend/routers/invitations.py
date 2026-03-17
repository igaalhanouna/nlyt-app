"""
Invitation Router
Handles public invitation viewing and participant responses (accept/decline)
"""
from fastapi import APIRouter, HTTPException, Request
from pymongo import MongoClient
from pydantic import BaseModel
from typing import Optional
import os
import sys
sys.path.append('/app/backend')
from utils.date_utils import now_utc
from datetime import datetime, timezone

router = APIRouter()

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
client = MongoClient(MONGO_URL)
db = client[DB_NAME]


class InvitationResponse(BaseModel):
    action: str  # "accept" or "decline"


def parse_datetime(dt_str: str) -> datetime:
    """Parse datetime string to datetime object"""
    try:
        if '+' in dt_str or 'Z' in dt_str:
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
    except:
        return None


@router.get("/{token}")
async def get_invitation_details(token: str):
    """
    Public endpoint to view invitation details via secure token.
    No authentication required.
    """
    # Find participant by invitation token
    participant = db.participants.find_one(
        {"invitation_token": token},
        {"_id": 0}
    )
    
    if not participant:
        raise HTTPException(status_code=404, detail="Invitation non trouvée ou expirée")
    
    # Get appointment details
    appointment = db.appointments.find_one(
        {"appointment_id": participant['appointment_id']},
        {"_id": 0}
    )
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous associé introuvable")
    
    # Get organizer info (limited for privacy)
    organizer = db.users.find_one(
        {"user_id": appointment['organizer_id']},
        {"_id": 0, "first_name": 1, "last_name": 1}
    )
    organizer_name = "Organisateur"
    if organizer:
        organizer_name = f"{organizer.get('first_name', '')} {organizer.get('last_name', '')}".strip()
    
    # Get policy snapshot for rules
    policy_snapshot = None
    if appointment.get('policy_snapshot_id'):
        policy_snapshot = db.policy_snapshots.find_one(
            {"snapshot_id": appointment['policy_snapshot_id']},
            {"_id": 0}
        )
    
    # Get other participants (limited info - just count and names)
    other_participants = list(db.participants.find(
        {
            "appointment_id": participant['appointment_id'],
            "participant_id": {"$ne": participant['participant_id']}
        },
        {"_id": 0, "first_name": 1, "last_name": 1, "status": 1}
    ))
    
    # Parse date for display
    start_dt = parse_datetime(appointment.get('start_datetime', ''))
    formatted_date = None
    if start_dt:
        formatted_date = start_dt.strftime("%A %d %B %Y à %H:%M")
    
    # Calculate cancellation deadline
    cancellation_deadline = None
    cancellation_deadline_dt = None
    can_cancel = False
    deadline_passed = False
    
    if start_dt and appointment.get('cancellation_deadline_hours'):
        from datetime import timedelta
        cancellation_deadline_dt = start_dt - timedelta(hours=appointment['cancellation_deadline_hours'])
        cancellation_deadline = cancellation_deadline_dt.strftime("%A %d %B %Y à %H:%M")
        
        # Check if participant can still cancel (deadline not passed)
        now = datetime.now(timezone.utc)
        deadline_passed = now >= cancellation_deadline_dt
        
        # Can cancel if: accepted AND deadline not passed
        if participant.get('status') == 'accepted' and not deadline_passed:
            can_cancel = True
    
    # Build response with limited, privacy-conscious data
    return {
        "invitation_token": token,
        "participant": {
            "participant_id": participant['participant_id'],
            "first_name": participant.get('first_name', ''),
            "last_name": participant.get('last_name', ''),
            "email": participant.get('email', ''),
            "status": participant.get('status', 'invited'),
            "accepted_at": participant.get('accepted_at'),
            "declined_at": participant.get('declined_at'),
            "cancelled_at": participant.get('cancelled_at')
        },
        "appointment": {
            "appointment_id": appointment['appointment_id'],
            "title": appointment.get('title', ''),
            "appointment_type": appointment.get('appointment_type', ''),
            "location": appointment.get('location', ''),
            "meeting_provider": appointment.get('meeting_provider', ''),
            "start_datetime": appointment.get('start_datetime', ''),
            "formatted_date": formatted_date,
            "duration_minutes": appointment.get('duration_minutes', 60),
            "status": appointment.get('status', '')
        },
        "organizer": {
            "name": organizer_name
        },
        "engagement_rules": {
            "cancellation_deadline_hours": appointment.get('cancellation_deadline_hours', 24),
            "cancellation_deadline_formatted": cancellation_deadline,
            "cancellation_deadline_passed": deadline_passed,
            "can_cancel": can_cancel,
            "tolerated_delay_minutes": appointment.get('tolerated_delay_minutes', 0),
            "penalty_amount": appointment.get('penalty_amount', 0),
            "penalty_currency": appointment.get('penalty_currency', 'EUR').upper(),
            "affected_compensation_percent": appointment.get('affected_compensation_percent', 70),
            "platform_commission_percent": appointment.get('platform_commission_percent', 30)
        },
        "other_participants": [
            {
                "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or "Participant",
                "status": p.get('status', 'invited')
            }
            for p in other_participants
        ],
        "policy_summary": policy_snapshot.get('summary') if policy_snapshot else None
    }


@router.post("/{token}/respond")
async def respond_to_invitation(token: str, response: InvitationResponse):
    """
    Public endpoint to accept or decline an invitation.
    No authentication required - uses token for security.
    """
    if response.action not in ["accept", "decline"]:
        raise HTTPException(status_code=400, detail="Action invalide. Utilisez 'accept' ou 'decline'.")
    
    # Find participant by token
    participant = db.participants.find_one(
        {"invitation_token": token},
        {"_id": 0}
    )
    
    if not participant:
        raise HTTPException(status_code=404, detail="Invitation non trouvée ou expirée")
    
    # Check if already responded
    current_status = participant.get('status', 'invited')
    if current_status in ['accepted', 'declined']:
        raise HTTPException(
            status_code=400, 
            detail=f"Vous avez déjà répondu à cette invitation (statut actuel: {current_status})"
        )
    
    # Get appointment to check if still valid
    appointment = db.appointments.find_one(
        {"appointment_id": participant['appointment_id']},
        {"_id": 0}
    )
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous associé introuvable")
    
    # Check if appointment is still active
    if appointment.get('status') in ['cancelled', 'completed']:
        raise HTTPException(status_code=400, detail="Ce rendez-vous n'est plus actif")
    
    # Check if appointment hasn't started yet
    start_dt = parse_datetime(appointment.get('start_datetime', ''))
    if start_dt and datetime.now(timezone.utc) >= start_dt:
        raise HTTPException(status_code=400, detail="Ce rendez-vous a déjà commencé")
    
    now = now_utc().isoformat()
    
    if response.action == "accept":
        update_data = {
            "status": "accepted",
            "accepted_at": now,
            "updated_at": now
        }
        message = "Invitation acceptée avec succès"
    else:
        update_data = {
            "status": "declined",
            "declined_at": now,
            "updated_at": now
        }
        message = "Invitation déclinée"
    
    # Update participant status
    db.participants.update_one(
        {"invitation_token": token},
        {"$set": update_data}
    )
    
    # Get updated participant
    updated_participant = db.participants.find_one(
        {"invitation_token": token},
        {"_id": 0}
    )
    
    return {
        "success": True,
        "message": message,
        "status": update_data['status'],
        "participant": {
            "participant_id": updated_participant['participant_id'],
            "first_name": updated_participant.get('first_name', ''),
            "last_name": updated_participant.get('last_name', ''),
            "status": updated_participant['status'],
            "accepted_at": updated_participant.get('accepted_at'),
            "declined_at": updated_participant.get('declined_at')
        }
    }


@router.post("/{token}/cancel")
async def cancel_participation(token: str):
    """
    Public endpoint to cancel participation after acceptance.
    Only allowed if cancellation deadline has not passed.
    No authentication required - uses token for security.
    """
    # Find participant by token
    participant = db.participants.find_one(
        {"invitation_token": token},
        {"_id": 0}
    )
    
    if not participant:
        raise HTTPException(status_code=404, detail="Invitation non trouvée ou expirée")
    
    # Check if participant has accepted
    current_status = participant.get('status', 'invited')
    if current_status != 'accepted':
        raise HTTPException(
            status_code=400, 
            detail="Seule une invitation acceptée peut être annulée"
        )
    
    # Get appointment to check cancellation deadline
    appointment = db.appointments.find_one(
        {"appointment_id": participant['appointment_id']},
        {"_id": 0}
    )
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous associé introuvable")
    
    # Check if appointment is still active
    if appointment.get('status') in ['cancelled', 'completed']:
        raise HTTPException(status_code=400, detail="Ce rendez-vous n'est plus actif")
    
    # Calculate and check cancellation deadline
    start_dt = parse_datetime(appointment.get('start_datetime', ''))
    if not start_dt:
        raise HTTPException(status_code=400, detail="Date du rendez-vous invalide")
    
    from datetime import timedelta
    cancellation_deadline_hours = appointment.get('cancellation_deadline_hours', 24)
    cancellation_deadline_dt = start_dt - timedelta(hours=cancellation_deadline_hours)
    
    now = datetime.now(timezone.utc)
    
    if now >= cancellation_deadline_dt:
        raise HTTPException(
            status_code=400, 
            detail="Le délai d'annulation est dépassé. Vous ne pouvez plus annuler en ligne."
        )
    
    # Check if appointment hasn't started yet
    if now >= start_dt:
        raise HTTPException(status_code=400, detail="Ce rendez-vous a déjà commencé")
    
    now_str = now_utc().isoformat()
    
    update_data = {
        "status": "cancelled_by_participant",
        "cancelled_at": now_str,
        "updated_at": now_str
    }
    
    # Update participant status
    db.participants.update_one(
        {"invitation_token": token},
        {"$set": update_data}
    )
    
    # Get updated participant
    updated_participant = db.participants.find_one(
        {"invitation_token": token},
        {"_id": 0}
    )
    
    # Send notification email to organizer
    try:
        from services.email_service import EmailService
        
        # Get organizer details
        organizer = db.users.find_one(
            {"user_id": appointment['organizer_id']},
            {"_id": 0, "email": 1, "first_name": 1, "last_name": 1}
        )
        
        if organizer:
            organizer_name = f"{organizer.get('first_name', '')} {organizer.get('last_name', '')}".strip() or "Organisateur"
            participant_name = f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip() or participant.get('email', 'Participant')
            
            # Build appointment link
            frontend_url = os.environ.get('FRONTEND_URL', '').rstrip('/')
            appointment_link = f"{frontend_url}/dashboard" if frontend_url else None
            
            await EmailService.send_participant_cancellation_notification(
                organizer_email=organizer['email'],
                organizer_name=organizer_name,
                participant_name=participant_name,
                participant_email=participant.get('email', ''),
                appointment_title=appointment.get('title', 'Rendez-vous'),
                appointment_datetime=appointment.get('start_datetime', ''),
                location=appointment.get('location') or appointment.get('meeting_provider'),
                appointment_link=appointment_link
            )
    except Exception as e:
        # Log error but don't fail the cancellation
        import logging
        logging.error(f"Failed to send cancellation notification: {e}")
    
    return {
        "success": True,
        "message": "Votre participation a bien été annulée.",
        "status": "cancelled_by_participant",
        "participant": {
            "participant_id": updated_participant['participant_id'],
            "first_name": updated_participant.get('first_name', ''),
            "last_name": updated_participant.get('last_name', ''),
            "status": updated_participant['status'],
            "accepted_at": updated_participant.get('accepted_at'),
            "cancelled_at": updated_participant.get('cancelled_at')
        }
    }


@router.post("/{token}/resend")
async def resend_invitation(token: str, request: Request):
    """
    Resend invitation email (requires organizer auth).
    """
    from middleware.auth_middleware import get_current_user
    from services.email_service import EmailService
    
    user = await get_current_user(request)
    
    # Find participant
    participant = db.participants.find_one(
        {"invitation_token": token},
        {"_id": 0}
    )
    
    if not participant:
        raise HTTPException(status_code=404, detail="Participant introuvable")
    
    # Get appointment and verify organizer
    appointment = db.appointments.find_one(
        {"appointment_id": participant['appointment_id']},
        {"_id": 0}
    )
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    
    if appointment['organizer_id'] != user['user_id']:
        raise HTTPException(status_code=403, detail="Seul l'organisateur peut renvoyer une invitation")
    
    # Build invitation link
    frontend_url = os.environ.get('FRONTEND_URL', '').rstrip('/')
    invitation_link = f"{frontend_url}/invitation/{token}"
    
    # Get organizer name
    organizer_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    
    # Build participant name
    participant_name = f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip()
    if not participant_name:
        participant_name = participant.get('email', '').split('@')[0]
    
    # Send email
    result = await EmailService.send_invitation_email(
        to_email=participant['email'],
        to_name=participant_name,
        organizer_name=organizer_name,
        appointment_title=appointment['title'],
        appointment_datetime=appointment.get('start_datetime', ''),
        invitation_link=invitation_link
    )
    
    if result.get('success'):
        # Update last sent timestamp
        db.participants.update_one(
            {"invitation_token": token},
            {"$set": {"last_invitation_sent_at": now_utc().isoformat()}}
        )
        return {"success": True, "message": "Invitation renvoyée avec succès"}
    else:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'envoi: {result.get('error')}")
