from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, RedirectResponse
from pymongo import MongoClient
import os
import uuid
import sys
sys.path.append('/app/backend')
from middleware.auth_middleware import get_current_user
from adapters.google_calendar_adapter import GoogleCalendarAdapter
from adapters.outlook_adapter import OutlookAdapter
from adapters.ics_generator import ICSGenerator
from utils.date_utils import now_utc
from datetime import datetime, timedelta

router = APIRouter()

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
client = MongoClient(MONGO_URL)
db = client[DB_NAME]

@router.get("/connect/google")
async def connect_google_calendar(request: Request):
    user = await get_current_user(request)
    
    redirect_uri = f"{str(request.base_url).rstrip('/')}/api/calendar/oauth/google/callback"
    auth_url, state = GoogleCalendarAdapter.get_authorization_url(redirect_uri)
    
    db.calendar_connections.update_one(
        {"user_id": user['user_id'], "provider": "google"},
        {"$set": {"oauth_state": state, "updated_at": now_utc().isoformat()}},
        upsert=True
    )
    
    return {"authorization_url": auth_url}

@router.get("/oauth/google/callback")
async def google_oauth_callback(code: str, state: str = None, request: Request = None):
    redirect_uri = f"{str(request.base_url).rstrip('/')}/api/calendar/oauth/google/callback"
    tokens = GoogleCalendarAdapter.exchange_code_for_tokens(code, redirect_uri)
    
    if not tokens:
        raise HTTPException(status_code=400, detail="Échec de l'authentification Google")
    
    connection_id = str(uuid.uuid4())
    
    db.calendar_connections.update_one(
        {"user_email": tokens['user_email'], "provider": "google"},
        {"$set": {
            "connection_id": connection_id,
            "provider": "google",
            "user_email": tokens['user_email'],
            "access_token": tokens['access_token'],
            "refresh_token": tokens['refresh_token'],
            "status": "connected",
            "connected_at": now_utc().isoformat(),
            "updated_at": now_utc().isoformat()
        }},
        upsert=True
    )
    
    return RedirectResponse(url=f"{str(request.base_url).rstrip('/')}/settings/integrations?success=google")

@router.get("/connect/outlook")
async def connect_outlook_calendar(request: Request):
    user = await get_current_user(request)
    
    redirect_uri = f"{str(request.base_url).rstrip('/')}/api/calendar/oauth/outlook/callback"
    auth_url = OutlookAdapter.get_authorization_url(redirect_uri)
    
    return {"authorization_url": auth_url}

@router.get("/oauth/outlook/callback")
async def outlook_oauth_callback(code: str, request: Request):
    redirect_uri = f"{str(request.base_url).rstrip('/')}/api/calendar/oauth/outlook/callback"
    tokens = OutlookAdapter.exchange_code_for_tokens(code, redirect_uri)
    
    if not tokens:
        raise HTTPException(status_code=400, detail="Échec de l'authentification Outlook")
    
    connection_id = str(uuid.uuid4())
    
    db.calendar_connections.update_one(
        {"user_email": tokens['user_email'], "provider": "outlook"},
        {"$set": {
            "connection_id": connection_id,
            "provider": "outlook",
            "user_email": tokens['user_email'],
            "access_token": tokens['access_token'],
            "refresh_token": tokens['refresh_token'],
            "status": "connected",
            "connected_at": now_utc().isoformat(),
            "updated_at": now_utc().isoformat()
        }},
        upsert=True
    )
    
    return RedirectResponse(url=f"{str(request.base_url).rstrip('/')}/settings/integrations?success=outlook")

@router.get("/connections")
async def list_connections(request: Request):
    user = await get_current_user(request)
    
    connections = list(db.calendar_connections.find(
        {"user_email": user['email']},
        {"_id": 0, "access_token": 0, "refresh_token": 0}
    ))
    
    return {"connections": connections}

@router.post("/sync/appointment/{appointment_id}")
async def sync_appointment_to_calendar(appointment_id: str, connection_id: str, request: Request):
    user = await get_current_user(request)
    
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    connection = db.calendar_connections.find_one({"connection_id": connection_id}, {"_id": 0})
    
    if not appointment or not connection:
        raise HTTPException(status_code=404, detail="Données introuvables")
    
    start_dt = datetime.fromisoformat(appointment['start_datetime'].replace('Z', '+00:00'))
    end_dt = start_dt + timedelta(minutes=appointment['duration_minutes'])
    
    event_data = {
        "title": appointment['title'],
        "description": f"Rendez-vous NLYT avec engagement. Retard toléré: {appointment['tolerated_delay_minutes']} min",
        "location": appointment.get('location', ''),
        "start_datetime": start_dt.isoformat(),
        "end_datetime": end_dt.isoformat()
    }
    
    external_event_id = None
    sync_status = "failed"
    error_message = None
    
    try:
        if connection['provider'] == 'google':
            result = GoogleCalendarAdapter.create_event(
                connection['access_token'],
                connection['refresh_token'],
                event_data
            )
            if result:
                external_event_id = result['event_id']
                sync_status = "synced"
                if result.get('new_access_token'):
                    db.calendar_connections.update_one(
                        {"connection_id": connection_id},
                        {"$set": {"access_token": result['new_access_token']}}
                    )
        
        elif connection['provider'] == 'outlook':
            result = OutlookAdapter.create_event(connection['access_token'], event_data)
            if result:
                external_event_id = result['event_id']
                sync_status = "synced"
    
    except Exception as e:
        error_message = str(e)
    
    sync_log_id = str(uuid.uuid4())
    db.calendar_sync_logs.insert_one({
        "log_id": sync_log_id,
        "appointment_id": appointment_id,
        "connection_id": connection_id,
        "provider": connection['provider'],
        "external_event_id": external_event_id,
        "sync_status": sync_status,
        "error_message": error_message,
        "synced_at": now_utc().isoformat()
    })
    
    return {
        "sync_status": sync_status,
        "external_event_id": external_event_id,
        "error": error_message
    }

@router.get("/export/ics/{appointment_id}")
async def export_appointment_ics(appointment_id: str):
    """
    Generate and download ICS file for an appointment.
    Public endpoint - no authentication required (useful for email links).
    Compatible with Google Calendar, Outlook, Apple Calendar.
    """
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    
    # Parse start datetime and calculate end
    start_dt = datetime.fromisoformat(appointment['start_datetime'].replace('Z', '+00:00'))
    end_dt = start_dt + timedelta(minutes=appointment['duration_minutes'])
    
    # Get organizer info for description
    organizer = db.users.find_one({"user_id": appointment.get('organizer_id')}, {"_id": 0, "first_name": 1, "last_name": 1})
    organizer_name = "L'organisateur"
    if organizer:
        organizer_name = f"{organizer.get('first_name', '')} {organizer.get('last_name', '')}".strip() or "L'organisateur"
    
    # Build comprehensive description with engagement rules
    description_lines = [
        f"Rendez-vous organisé via NLYT par {organizer_name}.",
        "",
        "=== RÈGLES D'ENGAGEMENT ===",
        f"• Délai d'annulation : {appointment.get('cancellation_deadline_hours', 24)}h avant le rendez-vous",
        f"• Retard toléré : {appointment.get('tolerated_delay_minutes', 0)} minute(s)",
        f"• Pénalité en cas d'absence : {appointment.get('penalty_amount', 0)} {appointment.get('penalty_currency', 'EUR').upper()}",
        "",
        "En acceptant ce rendez-vous, vous vous engagez à respecter ces conditions.",
        "",
        "---",
        "Généré par NLYT - nlyt.app"
    ]
    description = "\\n".join(description_lines)
    
    # Determine location
    location = appointment.get('location', '')
    if not location and appointment.get('meeting_provider'):
        location = f"Visio - {appointment.get('meeting_provider')}"
    
    # Build event data
    event_data = {
        "appointment_id": appointment_id,
        "title": appointment['title'],
        "description": description,
        "location": location,
        "start_datetime": start_dt.isoformat(),
        "end_datetime": end_dt.isoformat()
    }
    
    ics_content = ICSGenerator.generate_ics_bytes(event_data)
    
    # Clean filename (remove special characters)
    safe_title = "".join(c if c.isalnum() or c in ' -_' else '' for c in appointment['title'])[:30]
    filename = f"nlyt_{safe_title}_{appointment_id[:8]}.ics"
    
    return Response(
        content=ics_content,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/calendar; charset=utf-8"
        }
    )