from fastapi import APIRouter, HTTPException, Request
from pymongo import MongoClient
import os
import uuid
import sys
sys.path.append('/app/backend')
from models.schemas import AppointmentCreate, AppointmentResponse
from middleware.auth_middleware import get_current_user
from utils.date_utils import now_utc
from services.contract_service import ContractService

# System constant — platform commission is NOT user-editable
PLATFORM_COMMISSION_PERCENT = float(os.environ.get('PLATFORM_COMMISSION_PERCENT', '20'))
VALID_CURRENCIES = {"eur", "usd", "gbp", "chf"}

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
async def create_appointment(appointment: AppointmentCreate, request: Request):
    user = await get_current_user(request)
    
    membership = db.workspace_memberships.find_one({
        "workspace_id": appointment.workspace_id,
        "user_id": user['user_id']
    }, {"_id": 0})
    
    if not membership:
        raise HTTPException(status_code=403, detail="Accès refusé au workspace")
    
    # --- Server-side validations ---
    # Currency validation
    if appointment.penalty_currency.lower() not in VALID_CURRENCIES:
        raise HTTPException(status_code=400, detail=f"Devise invalide. Devises acceptées : {', '.join(VALID_CURRENCIES)}")
    
    # Platform commission is a SYSTEM value — override any client-sent value
    platform_pct = PLATFORM_COMMISSION_PERCENT
    
    # Validate distribution: participant + charity must equal (100 - platform) for total = 100%
    max_distributable = 100 - platform_pct
    total_distributed = round(appointment.affected_compensation_percent + appointment.charity_percent, 2)
    if total_distributed != max_distributable:
        raise HTTPException(
            status_code=400,
            detail=f"La somme compensation ({appointment.affected_compensation_percent}%) + charité ({appointment.charity_percent}%) doit être exactement {max_distributable}%. Commission plateforme fixée à {platform_pct}%."
        )
    
    # Validate charity association if charity > 0
    if appointment.charity_percent > 0 and appointment.charity_association_id:
        from routers.charity_associations import is_valid_association
        if not is_valid_association(appointment.charity_association_id):
            raise HTTPException(status_code=400, detail="Association caritative non valide")
    
    # Resolve charity association name for snapshot
    charity_association_name = None
    if appointment.charity_association_id:
        from routers.charity_associations import get_association_name
        charity_association_name = get_association_name(appointment.charity_association_id)
    
    appointment_id = str(uuid.uuid4())
    
    # Prepare event_reminders config (default: all enabled for better UX)
    event_reminders_config = None
    if appointment.event_reminders:
        event_reminders_config = {
            "ten_minutes_before": appointment.event_reminders.ten_minutes_before,
            "one_hour_before": appointment.event_reminders.one_hour_before,
            "one_day_before": appointment.event_reminders.one_day_before
        }
    else:
        # Default: enable all reminders (zéro friction - automatic)
        event_reminders_config = {
            "ten_minutes_before": True,
            "one_hour_before": True,
            "one_day_before": True
        }
    
    appointment_doc = {
        "appointment_id": appointment_id,
        "workspace_id": appointment.workspace_id,
        "organizer_id": user['user_id'],
        "title": appointment.title,
        "appointment_type": appointment.appointment_type,
        "location": appointment.location,
        "location_latitude": appointment.location_latitude,
        "location_longitude": appointment.location_longitude,
        "location_place_id": appointment.location_place_id,
        "meeting_provider": appointment.meeting_provider,
        "start_datetime": appointment.start_datetime,
        "duration_minutes": appointment.duration_minutes,
        "tolerated_delay_minutes": appointment.tolerated_delay_minutes,
        "cancellation_deadline_hours": appointment.cancellation_deadline_hours,
        "penalty_amount": appointment.penalty_amount,
        "penalty_currency": appointment.penalty_currency.lower(),
        "affected_compensation_percent": appointment.affected_compensation_percent,
        "platform_commission_percent": platform_pct,  # SYSTEM value — never from client
        "charity_percent": appointment.charity_percent,
        "charity_association_id": appointment.charity_association_id,
        "charity_association_name": charity_association_name,
        "policy_template_id": appointment.policy_template_id,
        "policy_snapshot_id": None,
        "event_reminders": event_reminders_config,
        "event_reminders_sent": {},
        "status": "draft",
        "created_at": now_utc().isoformat(),
        "updated_at": now_utc().isoformat()
    }
    
    db.appointments.insert_one(appointment_doc)
    
    # Save participants from step 1 of the wizard and send invitation emails
    if appointment.participants:
        for p in appointment.participants:
            if p.email and p.email.strip():
                invitation_token = str(uuid.uuid4())
                participant_doc = {
                    "participant_id": str(uuid.uuid4()),
                    "appointment_id": appointment_id,
                    "email": p.email.strip(),
                    "first_name": p.first_name or "",
                    "last_name": p.last_name or "",
                    "name": p.name or "",  # Kept for backward compatibility
                    "role": p.role or "participant",
                    "status": "invited",
                    "invitation_token": invitation_token,
                    "user_id": None,
                    "invited_at": now_utc().isoformat(),
                    "created_at": now_utc().isoformat()
                }
                db.participants.insert_one(participant_doc)
                
                # Send invitation email
                try:
                    from services.email_service import EmailService
                    organizer = db.users.find_one({"user_id": user['user_id']}, {"_id": 0})
                    organizer_name = f"{organizer.get('first_name', '')} {organizer.get('last_name', '')}"
                    base_url = get_frontend_url(request)
                    invitation_link = f"{base_url}/invitation/{invitation_token}"
                    ics_link = f"{base_url}/api/calendar/export/ics/{appointment_id}"
                    
                    # Build participant name from first_name + last_name
                    participant_name = f"{p.first_name or ''} {p.last_name or ''}".strip()
                    if not participant_name:
                        participant_name = p.name or p.email.split('@')[0]
                    
                    await EmailService.send_invitation_email(
                        to_email=p.email.strip(),
                        to_name=participant_name,
                        organizer_name=organizer_name,
                        appointment_title=appointment.title,
                        appointment_datetime=appointment.start_datetime,
                        invitation_link=invitation_link,
                        location=appointment.location or appointment.meeting_provider,
                        penalty_amount=appointment.penalty_amount,
                        penalty_currency=appointment.penalty_currency,
                        cancellation_deadline_hours=appointment.cancellation_deadline_hours,
                        appointment_id=appointment_id,
                        ics_link=ics_link
                    )
                except Exception as e:
                    # Log error but don't fail the appointment creation
                    print(f"Failed to send invitation to {p.email}: {e}")
    
    organizer = db.users.find_one({"user_id": user['user_id']}, {"_id": 0})
    snapshot = ContractService.generate_policy_snapshot(appointment_id, appointment_doc, organizer)
    
    db.appointments.update_one(
        {"appointment_id": appointment_id},
        {"$set": {"policy_snapshot_id": snapshot['snapshot_id'], "status": "active"}}
    )
    
    # Auto-sync to calendar if enabled (non-blocking)
    try:
        from routers.calendar_routes import perform_auto_sync
        appointment_doc["status"] = "active"
        perform_auto_sync(user['user_id'], appointment_id, appointment_doc)
    except Exception as e:
        print(f"[AUTO-SYNC] Error during auto-sync: {e}")
    
    return {
        "appointment_id": appointment_id,
        "policy_snapshot_id": snapshot['snapshot_id'],
        "message": "Rendez-vous créé avec succès"
    }

@router.get("/")
async def list_appointments(workspace_id: str = None, request: Request = None):
    user = await get_current_user(request)
    
    query = {}
    if workspace_id:
        membership = db.workspace_memberships.find_one({
            "workspace_id": workspace_id,
            "user_id": user['user_id']
        }, {"_id": 0})
        
        if not membership:
            raise HTTPException(status_code=403, detail="Accès refusé")
        
        query["workspace_id"] = workspace_id
    else:
        memberships = list(db.workspace_memberships.find({"user_id": user['user_id']}, {"_id": 0}))
        workspace_ids = [m['workspace_id'] for m in memberships]
        query["workspace_id"] = {"$in": workspace_ids}
    
    # Sort by start_datetime ascending (closest to today first)
    # Exclude deleted appointments from listing
    query["status"] = {"$ne": "deleted"}
    appointments = list(db.appointments.find(query, {"_id": 0}).sort("start_datetime", 1))
    
    # Add participants with status to each appointment
    for apt in appointments:
        participants = list(db.participants.find(
            {"appointment_id": apt['appointment_id']}, 
            {"_id": 0, "participant_id": 1, "email": 1, "name": 1, "first_name": 1, "last_name": 1, "role": 1, "status": 1, "accepted_at": 1, "declined_at": 1, "cancelled_at": 1, "invitation_token": 1}
        ))
        apt['participants'] = participants
        apt['participants_count'] = len(participants)
        
        # Add summary of participant statuses
        status_summary = {"invited": 0, "accepted": 0, "declined": 0, "cancelled_by_participant": 0}
        for p in participants:
            status = p.get('status', 'invited')
            if status in ('accepted', 'accepted_pending_guarantee', 'accepted_guaranteed'):
                status_summary['accepted'] += 1
            elif status in status_summary:
                status_summary[status] += 1
            else:
                status_summary['invited'] += 1
        apt['participants_status_summary'] = status_summary
    
    return {"appointments": appointments}

@router.get("/{appointment_id}")
async def get_appointment(appointment_id: str, request: Request):
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
    
    return appointment

@router.patch("/{appointment_id}")
async def update_appointment(appointment_id: str, update_data: dict, request: Request):
    user = await get_current_user(request)
    
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    
    if appointment['organizer_id'] != user['user_id']:
        raise HTTPException(status_code=403, detail="Seul l'organisateur peut modifier ce rendez-vous")
    
    has_acceptances = db.acceptances.find_one({"appointment_id": appointment_id})
    if has_acceptances:
        raise HTTPException(status_code=400, detail="Impossible de modifier un rendez-vous déjà accepté")
    
    # Whitelist: only these fields can be updated
    ALLOWED_FIELDS = {
        "title", "description", "appointment_type", "location", "location_latitude",
        "location_longitude", "location_place_id", "meeting_provider",
        "start_datetime", "duration_minutes", "tolerated_delay_minutes",
        "cancellation_deadline_hours", "penalty_amount", "penalty_currency",
        "affected_compensation_percent", "charity_percent",
        "charity_association_id", "event_reminders"
    }
    
    safe_data = {k: v for k, v in update_data.items() if k in ALLOWED_FIELDS}
    
    if not safe_data:
        raise HTTPException(status_code=400, detail="Aucun champ modifiable fourni")
    
    # platform_commission_percent is NEVER user-editable
    safe_data.pop("platform_commission_percent", None)
    safe_data['updated_at'] = now_utc().isoformat()
    
    db.appointments.update_one(
        {"appointment_id": appointment_id},
        {"$set": safe_data}
    )
    
    # Auto-update calendar events if calendar-visible fields changed (non-blocking)
    try:
        from routers.calendar_routes import has_calendar_fields_changed, perform_auto_update
        if has_calendar_fields_changed(appointment, safe_data):
            updated_doc = {**appointment, **safe_data}
            perform_auto_update(user['user_id'], appointment_id, updated_doc)
    except Exception as e:
        print(f"[AUTO-UPDATE] Error during auto-update: {e}")
    
    return {"message": "Rendez-vous mis à jour"}


@router.post("/{appointment_id}/cancel")
async def cancel_appointment(appointment_id: str, request: Request):
    """
    Cancel an appointment (soft cancel - keeps history).
    Notifies all participants via email.
    """
    user = await get_current_user(request)
    
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    
    if appointment['organizer_id'] != user['user_id']:
        raise HTTPException(status_code=403, detail="Seul l'organisateur peut annuler ce rendez-vous")
    
    # Check if already cancelled
    if appointment.get('status') == 'cancelled':
        raise HTTPException(status_code=400, detail="Ce rendez-vous est déjà annulé")
    
    # Update appointment status to cancelled
    now = now_utc().isoformat()
    db.appointments.update_one(
        {"appointment_id": appointment_id},
        {"$set": {
            "status": "cancelled",
            "cancelled_at": now,
            "cancelled_by": user['user_id'],
            "updated_at": now
        }}
    )
    
    # Get organizer info for email
    organizer = db.users.find_one({"user_id": user['user_id']}, {"_id": 0})
    organizer_name = f"{organizer.get('first_name', '')} {organizer.get('last_name', '')}".strip() or "L'organisateur"
    
    # Release all active guarantees for this appointment
    guaranteed_participants = list(db.participants.find(
        {"appointment_id": appointment_id, "status": "accepted_guaranteed"},
        {"_id": 0, "guarantee_id": 1}
    ))
    for gp in guaranteed_participants:
        if gp.get('guarantee_id'):
            try:
                from services.stripe_guarantee_service import StripeGuaranteeService
                StripeGuaranteeService.release_guarantee(
                    gp['guarantee_id'],
                    "appointment_cancelled_by_organizer"
                )
            except Exception as e:
                import logging
                logging.error(f"Failed to release guarantee {gp['guarantee_id']}: {e}")
    
    # Notify all participants
    participants = list(db.participants.find({"appointment_id": appointment_id}, {"_id": 0}))
    notifications_sent = 0
    
    from services.email_service import EmailService
    
    for participant in participants:
        try:
            participant_name = f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip()
            if not participant_name:
                participant_name = participant.get('email', '').split('@')[0]
            
            await EmailService.send_appointment_cancelled_notification(
                participant_email=participant['email'],
                participant_name=participant_name,
                organizer_name=organizer_name,
                appointment_title=appointment.get('title', 'Rendez-vous'),
                appointment_datetime=appointment.get('start_datetime', ''),
                location=appointment.get('location') or appointment.get('meeting_provider')
            )
            notifications_sent += 1
        except Exception as e:
            import logging
            logging.error(f"Failed to send cancellation notification to {participant.get('email')}: {e}")
    
    # Delete calendar events across all connected providers (best-effort)
    try:
        from adapters.google_calendar_adapter import GoogleCalendarAdapter
        from adapters.outlook_calendar_adapter import OutlookCalendarAdapter
        adapters = {"google": GoogleCalendarAdapter, "outlook": OutlookCalendarAdapter}

        for provider, adapter in adapters.items():
            connection = db.calendar_connections.find_one(
                {"user_id": user['user_id'], "provider": provider, "status": "connected"}
            )
            if not connection:
                continue
            sync_log = db.calendar_sync_logs.find_one({
                "appointment_id": appointment_id,
                "connection_id": connection['connection_id'],
                "sync_status": "synced"
            })
            if sync_log and sync_log.get('external_event_id'):
                deleted = adapter.delete_event(
                    connection['access_token'],
                    connection.get('refresh_token'),
                    sync_log['external_event_id']
                )
                if deleted:
                    db.calendar_sync_logs.update_one(
                        {"log_id": sync_log['log_id']},
                        {"$set": {"sync_status": "deleted", "deleted_at": now}}
                    )
    except Exception as e:
        import logging
        logging.error(f"Failed to delete calendar events: {e}")

    return {
        "success": True,
        "message": "Rendez-vous annulé avec succès",
        "participants_notified": notifications_sent,
        "total_participants": len(participants)
    }


@router.delete("/{appointment_id}")
async def delete_appointment(appointment_id: str, request: Request):
    """
    Delete an appointment (soft delete).
    Notifies all participants via email.
    """
    user = await get_current_user(request)
    
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    
    # Check if user is organizer OR has admin role in workspace
    membership = db.workspace_memberships.find_one({
        "workspace_id": appointment['workspace_id'],
        "user_id": user['user_id']
    }, {"_id": 0})
    
    if not membership:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    if appointment['organizer_id'] != user['user_id'] and membership.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Seul l'organisateur peut supprimer ce rendez-vous")
    
    # Get organizer info for email
    organizer = db.users.find_one({"user_id": appointment['organizer_id']}, {"_id": 0})
    organizer_name = f"{organizer.get('first_name', '')} {organizer.get('last_name', '')}".strip() or "L'organisateur"
    
    # Notify all participants before deletion
    participants = list(db.participants.find({"appointment_id": appointment_id}, {"_id": 0}))
    
    from services.email_service import EmailService
    
    for participant in participants:
        try:
            participant_name = f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip()
            if not participant_name:
                participant_name = participant.get('email', '').split('@')[0]
            
            await EmailService.send_appointment_deleted_notification(
                participant_email=participant['email'],
                participant_name=participant_name,
                organizer_name=organizer_name,
                appointment_title=appointment.get('title', 'Rendez-vous'),
                appointment_datetime=appointment.get('start_datetime', ''),
                location=appointment.get('location') or appointment.get('meeting_provider')
            )
        except Exception as e:
            import logging
            logging.error(f"Failed to send deletion notification to {participant.get('email')}: {e}")
    
    # Soft delete: mark as deleted instead of hard delete
    now = now_utc().isoformat()
    db.appointments.update_one(
        {"appointment_id": appointment_id},
        {"$set": {
            "status": "deleted",
            "deleted_at": now,
            "deleted_by": user['user_id'],
            "updated_at": now
        }}
    )
    
    # Also mark participants as belonging to deleted appointment
    db.participants.update_many(
        {"appointment_id": appointment_id},
        {"$set": {"appointment_deleted": True, "updated_at": now}}
    )
    
    return {"message": "Rendez-vous supprimé avec succès"}