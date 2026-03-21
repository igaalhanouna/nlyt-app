from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, RedirectResponse
from pymongo import MongoClient
import os
import uuid
import json
import sys
sys.path.append('/app/backend')
from middleware.auth_middleware import get_current_user
from adapters.google_calendar_adapter import GoogleCalendarAdapter
from adapters.ics_generator import ICSGenerator
from utils.date_utils import now_utc
from datetime import datetime, timedelta

router = APIRouter()

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
FRONTEND_URL = os.environ.get('FRONTEND_URL', '').rstrip('/')

client = MongoClient(MONGO_URL)
db = client[DB_NAME]


def _get_redirect_uri():
    """Stable OAuth callback URI derived from FRONTEND_URL."""
    return f"{FRONTEND_URL}/api/calendar/oauth/google/callback"


# ── Google OAuth ────────────────────────────────────────────

@router.get("/connect/google")
async def connect_google_calendar(request: Request):
    """
    Initiate Google Calendar OAuth flow.
    Returns the authorization URL the frontend should redirect the user to.
    """
    user = await get_current_user(request)

    if not os.environ.get('GOOGLE_CLIENT_ID'):
        raise HTTPException(status_code=500, detail="Google Calendar n'est pas configuré (GOOGLE_CLIENT_ID manquant)")

    # Encode user_id in state so the callback can link the connection
    state_payload = json.dumps({"user_id": user['user_id'], "nonce": str(uuid.uuid4())})
    import base64
    state = base64.urlsafe_b64encode(state_payload.encode()).decode()

    redirect_uri = _get_redirect_uri()
    auth_url, _ = GoogleCalendarAdapter.get_authorization_url(redirect_uri, state=state)

    # Persist state for CSRF validation
    db.oauth_states.update_one(
        {"user_id": user['user_id'], "provider": "google"},
        {"$set": {
            "state": state,
            "created_at": now_utc().isoformat()
        }},
        upsert=True
    )

    return {"authorization_url": auth_url}


@router.get("/oauth/google/callback")
async def google_oauth_callback(code: str, state: str = None, error: str = None):
    """
    Google OAuth callback. Exchanges the code for tokens,
    stores the connection, then redirects the browser to the frontend.
    """
    # Handle denial
    if error:
        return RedirectResponse(url=f"{FRONTEND_URL}/settings/integrations?google=error&reason={error}")

    if not state:
        return RedirectResponse(url=f"{FRONTEND_URL}/settings/integrations?google=error&reason=missing_state")

    # Decode user_id from state
    import base64
    try:
        state_payload = json.loads(base64.urlsafe_b64decode(state.encode()))
        user_id = state_payload.get("user_id")
    except Exception:
        return RedirectResponse(url=f"{FRONTEND_URL}/settings/integrations?google=error&reason=invalid_state")

    if not user_id:
        return RedirectResponse(url=f"{FRONTEND_URL}/settings/integrations?google=error&reason=no_user")

    # CSRF: verify state matches what we stored
    stored = db.oauth_states.find_one({"user_id": user_id, "provider": "google", "state": state})
    if not stored:
        return RedirectResponse(url=f"{FRONTEND_URL}/settings/integrations?google=error&reason=state_mismatch")

    # Clean up used state
    db.oauth_states.delete_one({"_id": stored["_id"]})

    # Exchange code for tokens
    redirect_uri = _get_redirect_uri()
    tokens = GoogleCalendarAdapter.exchange_code_for_tokens(code, redirect_uri)

    if not tokens:
        return RedirectResponse(url=f"{FRONTEND_URL}/settings/integrations?google=error&reason=token_exchange_failed")

    connection_id = str(uuid.uuid4())

    db.calendar_connections.update_one(
        {"user_id": user_id, "provider": "google"},
        {"$set": {
            "connection_id": connection_id,
            "user_id": user_id,
            "provider": "google",
            "google_email": tokens['user_email'],
            "google_name": tokens.get('user_name', ''),
            "access_token": tokens['access_token'],
            "refresh_token": tokens['refresh_token'],
            "status": "connected",
            "connected_at": now_utc().isoformat(),
            "updated_at": now_utc().isoformat()
        }},
        upsert=True
    )

    return RedirectResponse(url=f"{FRONTEND_URL}/settings/integrations?google=connected")


@router.get("/connections")
async def list_connections(request: Request):
    """List calendar connections for the current user (tokens excluded)."""
    user = await get_current_user(request)

    connections = list(db.calendar_connections.find(
        {"user_id": user['user_id']},
        {"_id": 0, "access_token": 0, "refresh_token": 0, "oauth_state": 0}
    ))

    return {"connections": connections}


@router.delete("/connections/google")
async def disconnect_google_calendar(request: Request):
    """Disconnect Google Calendar and revoke tokens."""
    user = await get_current_user(request)

    connection = db.calendar_connections.find_one(
        {"user_id": user['user_id'], "provider": "google"},
        {"_id": 0}
    )

    if not connection:
        raise HTTPException(status_code=404, detail="Aucune connexion Google Calendar trouvée")

    # Revoke token at Google (best-effort)
    if connection.get('access_token'):
        GoogleCalendarAdapter.revoke_token(connection['access_token'])

    # Delete from DB
    db.calendar_connections.delete_one({"user_id": user['user_id'], "provider": "google"})

    # Delete related sync logs
    db.calendar_sync_logs.delete_many({"connection_id": connection.get('connection_id')})

    return {"success": True, "message": "Google Calendar déconnecté"}


# ── Sync appointment to Google Calendar ─────────────────────

@router.post("/sync/appointment/{appointment_id}")
async def sync_appointment_to_calendar(appointment_id: str, request: Request):
    """
    Sync an appointment to the organizer's connected Google Calendar.
    Creates a Google Calendar event with NLYT engagement rules in the description.
    """
    user = await get_current_user(request)

    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

    connection = db.calendar_connections.find_one(
        {"user_id": user['user_id'], "provider": "google", "status": "connected"}
    )
    if not connection:
        raise HTTPException(status_code=400, detail="Google Calendar non connecté")

    # Check if already synced
    existing_sync = db.calendar_sync_logs.find_one({
        "appointment_id": appointment_id,
        "connection_id": connection['connection_id'],
        "sync_status": "synced"
    })
    if existing_sync:
        return {
            "sync_status": "already_synced",
            "external_event_id": existing_sync.get('external_event_id'),
            "html_link": existing_sync.get('html_link')
        }

    # Token refresh callback
    def on_token_refresh(new_token):
        db.calendar_connections.update_one(
            {"connection_id": connection['connection_id']},
            {"$set": {"access_token": new_token, "updated_at": now_utc().isoformat()}}
        )

    # Build event data
    start_dt = datetime.fromisoformat(appointment['start_datetime'].replace('Z', '+00:00'))
    end_dt = start_dt + timedelta(minutes=appointment.get('duration_minutes', 60))

    location = appointment.get('location', '')
    if not location and appointment.get('meeting_provider'):
        location = f"Visio - {appointment.get('meeting_provider')}"

    description_lines = [
        f"Rendez-vous organisé via NLYT.",
        "",
        f"Délai d'annulation : {appointment.get('cancellation_deadline_hours', 24)}h",
        f"Retard toléré : {appointment.get('tolerated_delay_minutes', 0)} min",
        f"Pénalité : {appointment.get('penalty_amount', 0)} {appointment.get('penalty_currency', 'EUR').upper()}",
    ]

    # Get the user's Google Calendar timezone (not hardcoded UTC)
    calendar_tz = GoogleCalendarAdapter.get_calendar_timezone(
        connection['access_token'],
        connection.get('refresh_token'),
        connection_update_callback=on_token_refresh
    )

    event_data = {
        "title": f"[NLYT] {appointment['title']}",
        "description": "\n".join(description_lines),
        "location": location,
        "start_datetime": start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
        "end_datetime": end_dt.strftime('%Y-%m-%dT%H:%M:%S'),
        "timeZone": calendar_tz
    }

    result = GoogleCalendarAdapter.create_event(
        connection['access_token'],
        connection.get('refresh_token'),
        event_data,
        connection_update_callback=on_token_refresh
    )

    sync_status = "synced" if result else "failed"

    sync_log = {
        "log_id": str(uuid.uuid4()),
        "appointment_id": appointment_id,
        "connection_id": connection['connection_id'],
        "provider": "google",
        "external_event_id": result.get('event_id') if result else None,
        "html_link": result.get('html_link') if result else None,
        "sync_status": sync_status,
        "synced_at": now_utc().isoformat()
    }
    db.calendar_sync_logs.insert_one(sync_log)

    if not result:
        raise HTTPException(status_code=502, detail="Échec de la synchronisation avec Google Calendar")

    return {
        "sync_status": sync_status,
        "external_event_id": result.get('event_id'),
        "html_link": result.get('html_link')
    }


@router.get("/sync/status/{appointment_id}")
async def get_sync_status(appointment_id: str, request: Request):
    """Check if an appointment has been synced to Google Calendar."""
    user = await get_current_user(request)

    connection = db.calendar_connections.find_one(
        {"user_id": user['user_id'], "provider": "google"},
        {"_id": 0, "connection_id": 1}
    )

    if not connection:
        return {"synced": False, "has_connection": False}

    sync_log = db.calendar_sync_logs.find_one(
        {"appointment_id": appointment_id, "connection_id": connection['connection_id'], "sync_status": "synced"},
        {"_id": 0}
    )

    return {
        "synced": sync_log is not None,
        "has_connection": True,
        "external_event_id": sync_log.get('external_event_id') if sync_log else None,
        "html_link": sync_log.get('html_link') if sync_log else None
    }



@router.delete("/sync/appointment/{appointment_id}")
async def unsync_appointment_from_calendar(appointment_id: str, request: Request):
    """
    Delete the Google Calendar event when a RDV is cancelled.
    Called internally or by the organizer.
    """
    user = await get_current_user(request)

    connection = db.calendar_connections.find_one(
        {"user_id": user['user_id'], "provider": "google", "status": "connected"}
    )
    if not connection:
        return {"success": False, "reason": "no_connection"}

    sync_log = db.calendar_sync_logs.find_one({
        "appointment_id": appointment_id,
        "connection_id": connection['connection_id'],
        "sync_status": "synced"
    })
    if not sync_log:
        return {"success": False, "reason": "not_synced"}

    def on_token_refresh(new_token):
        db.calendar_connections.update_one(
            {"connection_id": connection['connection_id']},
            {"$set": {"access_token": new_token, "updated_at": now_utc().isoformat()}}
        )

    deleted = GoogleCalendarAdapter.delete_event(
        connection['access_token'],
        connection.get('refresh_token'),
        sync_log['external_event_id'],
        connection_update_callback=on_token_refresh
    )

    if deleted:
        db.calendar_sync_logs.update_one(
            {"log_id": sync_log['log_id']},
            {"$set": {"sync_status": "deleted", "deleted_at": now_utc().isoformat()}}
        )

    return {"success": deleted}


# ── ICS Export (unchanged, public) ──────────────────────────

@router.get("/export/ics/{appointment_id}")
async def export_appointment_ics(appointment_id: str):
    """Generate and download ICS file for an appointment (public, no auth)."""
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})

    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

    is_cancelled = appointment.get('status') in ['cancelled', 'deleted']

    start_dt = datetime.fromisoformat(appointment['start_datetime'].replace('Z', '+00:00'))
    end_dt = start_dt + timedelta(minutes=appointment['duration_minutes'])

    organizer = db.users.find_one({"user_id": appointment.get('organizer_id')}, {"_id": 0, "first_name": 1, "last_name": 1})
    organizer_name = "L'organisateur"
    if organizer:
        organizer_name = f"{organizer.get('first_name', '')} {organizer.get('last_name', '')}".strip() or "L'organisateur"

    if is_cancelled:
        description_lines = [
            "CE RENDEZ-VOUS A ETE ANNULE",
            "",
            f"Rendez-vous initialement organisé par {organizer_name}.",
            "---",
            "Généré par NLYT"
        ]
    else:
        description_lines = [
            f"Rendez-vous organisé via NLYT par {organizer_name}.",
            "",
            "=== REGLES D'ENGAGEMENT ===",
            f"Délai d'annulation : {appointment.get('cancellation_deadline_hours', 24)}h avant le rendez-vous",
            f"Retard toléré : {appointment.get('tolerated_delay_minutes', 0)} minute(s)",
            f"Pénalité en cas d'absence : {appointment.get('penalty_amount', 0)} {appointment.get('penalty_currency', 'EUR').upper()}",
            "",
            "En acceptant ce rendez-vous, vous vous engagez à respecter ces conditions.",
            "---",
            "Généré par NLYT"
        ]
    description = "\\n".join(description_lines)

    location = appointment.get('location', '')
    if not location and appointment.get('meeting_provider'):
        location = f"Visio - {appointment.get('meeting_provider')}"

    title = appointment['title']
    if is_cancelled:
        title = f"[ANNULE] {title}"

    event_data = {
        "appointment_id": appointment_id,
        "title": title,
        "description": description,
        "location": location,
        "start_datetime": start_dt.isoformat(),
        "end_datetime": end_dt.isoformat(),
        "status": "CANCELLED" if is_cancelled else "CONFIRMED"
    }

    ics_content = ICSGenerator.generate_ics_bytes(event_data)

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


@router.get("/feed/{user_id}.ics")
async def get_ics_subscription_feed(user_id: str, token: str = None):
    """ICS subscription feed for a user's appointments."""
    user = db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    organizer_appointments = list(db.appointments.find(
        {"organizer_id": user_id, "status": {"$nin": ["deleted"]}},
        {"_id": 0}
    ))

    participant_records = list(db.participants.find(
        {"email": user.get('email'), "status": {"$in": ["accepted", "accepted_guaranteed"]}},
        {"_id": 0, "appointment_id": 1}
    ))
    participant_apt_ids = [p['appointment_id'] for p in participant_records]

    participant_appointments = list(db.appointments.find(
        {"appointment_id": {"$in": participant_apt_ids}, "status": {"$nin": ["deleted"]}},
        {"_id": 0}
    )) if participant_apt_ids else []

    all_appointments = {apt['appointment_id']: apt for apt in organizer_appointments + participant_appointments}

    ics_content = ICSGenerator.generate_feed(list(all_appointments.values()), user.get('first_name', 'NLYT'))

    return Response(
        content=ics_content.encode('utf-8'),
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Type": "text/calendar; charset=utf-8",
            "Cache-Control": "no-cache, no-store, must-revalidate"
        }
    )
