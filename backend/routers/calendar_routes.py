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
from adapters.outlook_calendar_adapter import OutlookCalendarAdapter
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
    """Google OAuth callback URI."""
    return f"{FRONTEND_URL}/api/calendar/oauth/google/callback"


def _get_outlook_redirect_uri():
    """Outlook OAuth callback URI."""
    return f"{FRONTEND_URL}/api/calendar/oauth/outlook/callback"


def _get_adapter(provider: str):
    """Return the right adapter for a provider."""
    if provider == 'google':
        return GoogleCalendarAdapter
    elif provider == 'outlook':
        return OutlookCalendarAdapter
    return None


def _build_event_data(appointment, calendar_tz):
    """Build event data dict from an appointment (shared between providers)."""
    start_dt = datetime.fromisoformat(appointment['start_datetime'].replace('Z', '+00:00'))
    end_dt = start_dt + timedelta(minutes=appointment.get('duration_minutes', 60))

    location = appointment.get('location', '')
    if not location and appointment.get('meeting_provider'):
        location = f"Visio - {appointment.get('meeting_provider')}"

    description_lines = [
        "Rendez-vous organisé via NLYT.",
        "",
    ]

    if appointment.get('description'):
        description_lines.append(appointment['description'])
        description_lines.append("")

    description_lines.extend([
        f"Délai d'annulation : {appointment.get('cancellation_deadline_hours', 24)}h",
        f"Retard toléré : {appointment.get('tolerated_delay_minutes', 0)} min",
        f"Pénalité : {appointment.get('penalty_amount', 0)} {appointment.get('penalty_currency', 'EUR').upper()}",
    ])

    return {
        "title": f"[NLYT] {appointment['title']}",
        "description": "\n".join(description_lines),
        "location": location,
        "start_datetime": start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
        "end_datetime": end_dt.strftime('%Y-%m-%dT%H:%M:%S'),
        "timeZone": calendar_tz
    }


# Calendar fields that trigger auto-update when changed
CALENDAR_FIELDS = {"title", "start_datetime", "duration_minutes", "location", "meeting_provider", "description"}


def _resolve_timezone(adapter, connection):
    """Get the calendar timezone: try API first, fallback to stored browser timezone."""
    on_refresh = _make_token_refresh_callback(connection['connection_id'])
    api_tz = adapter.get_calendar_timezone(
        connection['access_token'], connection.get('refresh_token'),
        connection_update_callback=on_refresh
    )
    if api_tz and api_tz != 'UTC':
        return api_tz
    # Fallback to timezone stored at connection time (from browser)
    stored_tz = connection.get('calendar_timezone')
    if stored_tz and stored_tz != 'UTC':
        return stored_tz
    return api_tz or 'UTC'


def _make_token_refresh_callback(connection_id):
    """Create a token refresh callback that updates or expires the connection."""
    def on_token_refresh(new_token):
        if new_token:
            db.calendar_connections.update_one(
                {"connection_id": connection_id},
                {"$set": {"access_token": new_token, "updated_at": now_utc().isoformat()}}
            )
        else:
            db.calendar_connections.update_one(
                {"connection_id": connection_id},
                {"$set": {"status": "expired", "updated_at": now_utc().isoformat()}}
            )
    return on_token_refresh


# ── Google OAuth ────────────────────────────────────────────

@router.get("/connect/google")
async def connect_google_calendar(request: Request, timezone: str = None):
    """
    Initiate Google Calendar OAuth flow.
    Returns the authorization URL the frontend should redirect the user to.
    """
    user = await get_current_user(request)

    if not os.environ.get('GOOGLE_CLIENT_ID'):
        raise HTTPException(status_code=500, detail="Google Calendar n'est pas configuré (GOOGLE_CLIENT_ID manquant)")

    # Encode user_id in state so the callback can link the connection
    state_payload = json.dumps({"user_id": user['user_id'], "nonce": str(uuid.uuid4()), "timezone": timezone or "UTC"})
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
        user_timezone = state_payload.get("timezone", "UTC")
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
            "calendar_timezone": user_timezone,
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


# ── Outlook / Microsoft 365 OAuth ───────────────────────────

@router.get("/connect/outlook")
async def connect_outlook_calendar(request: Request, timezone: str = None):
    """Initiate Outlook OAuth flow."""
    user = await get_current_user(request)

    if not os.environ.get('MICROSOFT_CLIENT_ID'):
        raise HTTPException(status_code=500, detail="Outlook Calendar n'est pas configuré (MICROSOFT_CLIENT_ID manquant)")

    import base64
    state_payload = json.dumps({"user_id": user['user_id'], "nonce": str(uuid.uuid4()), "timezone": timezone or "UTC"})
    state = base64.urlsafe_b64encode(state_payload.encode()).decode()
    state = base64.urlsafe_b64encode(state_payload.encode()).decode()

    redirect_uri = _get_outlook_redirect_uri()
    auth_url, _ = OutlookCalendarAdapter.get_authorization_url(redirect_uri, state=state)

    db.oauth_states.update_one(
        {"user_id": user['user_id'], "provider": "outlook"},
        {"$set": {"state": state, "created_at": now_utc().isoformat()}},
        upsert=True
    )

    return {"authorization_url": auth_url}


@router.get("/oauth/outlook/callback")
async def outlook_oauth_callback(code: str = None, state: str = None, error: str = None, error_description: str = None):
    """Outlook OAuth callback."""
    if error:
        reason = error_description or error
        return RedirectResponse(url=f"{FRONTEND_URL}/settings/integrations?outlook=error&reason={reason}")

    if not state or not code:
        return RedirectResponse(url=f"{FRONTEND_URL}/settings/integrations?outlook=error&reason=missing_params")

    import base64
    try:
        state_payload = json.loads(base64.urlsafe_b64decode(state.encode()))
        user_id = state_payload.get("user_id")
        user_timezone = state_payload.get("timezone", "UTC")
    except Exception:
        return RedirectResponse(url=f"{FRONTEND_URL}/settings/integrations?outlook=error&reason=invalid_state")

    if not user_id:
        return RedirectResponse(url=f"{FRONTEND_URL}/settings/integrations?outlook=error&reason=no_user")

    stored = db.oauth_states.find_one({"user_id": user_id, "provider": "outlook", "state": state})
    if not stored:
        return RedirectResponse(url=f"{FRONTEND_URL}/settings/integrations?outlook=error&reason=state_mismatch")

    db.oauth_states.delete_one({"_id": stored["_id"]})

    redirect_uri = _get_outlook_redirect_uri()
    tokens = OutlookCalendarAdapter.exchange_code_for_tokens(code, redirect_uri)

    if not tokens:
        return RedirectResponse(url=f"{FRONTEND_URL}/settings/integrations?outlook=error&reason=token_exchange_failed")

    connection_id = str(uuid.uuid4())

    # Try to get timezone from mailboxSettings first, fallback to browser timezone
    detected_tz = OutlookCalendarAdapter.get_calendar_timezone(
        tokens['access_token'], tokens['refresh_token']
    )
    calendar_timezone = detected_tz if detected_tz != 'UTC' else user_timezone

    db.calendar_connections.update_one(
        {"user_id": user_id, "provider": "outlook"},
        {"$set": {
            "connection_id": connection_id,
            "user_id": user_id,
            "provider": "outlook",
            "outlook_email": tokens['user_email'],
            "outlook_name": tokens.get('user_name', ''),
            "access_token": tokens['access_token'],
            "refresh_token": tokens['refresh_token'],
            "calendar_timezone": calendar_timezone,
            "status": "connected",
            "connected_at": now_utc().isoformat(),
            "updated_at": now_utc().isoformat()
        }},
        upsert=True
    )

    return RedirectResponse(url=f"{FRONTEND_URL}/settings/integrations?outlook=connected")


@router.delete("/connections/outlook")
async def disconnect_outlook_calendar(request: Request):
    """Disconnect Outlook Calendar."""
    user = await get_current_user(request)

    connection = db.calendar_connections.find_one(
        {"user_id": user['user_id'], "provider": "outlook"},
        {"_id": 0}
    )

    if not connection:
        raise HTTPException(status_code=404, detail="Aucune connexion Outlook Calendar trouvée")

    db.calendar_connections.delete_one({"user_id": user['user_id'], "provider": "outlook"})
    db.calendar_sync_logs.delete_many({"connection_id": connection.get('connection_id')})

    return {"success": True, "message": "Outlook Calendar déconnecté"}



# ── Auto-Sync Settings ──────────────────────────────────────

@router.get("/auto-sync/settings")
async def get_auto_sync_settings(request: Request):
    """Get the user's auto-sync preferences."""
    user = await get_current_user(request)
    settings = db.users.find_one(
        {"user_id": user['user_id']},
        {"_id": 0, "auto_sync_enabled": 1, "auto_sync_provider": 1}
    )
    return {
        "auto_sync_enabled": settings.get("auto_sync_enabled", False) if settings else False,
        "auto_sync_provider": settings.get("auto_sync_provider", None) if settings else None
    }


@router.put("/auto-sync/settings")
async def update_auto_sync_settings(request: Request):
    """Update the user's auto-sync preferences."""
    user = await get_current_user(request)
    body = await request.json()

    enabled = body.get("auto_sync_enabled", False)
    provider = body.get("auto_sync_provider", None)

    if enabled and not provider:
        raise HTTPException(status_code=400, detail="Veuillez choisir un provider pour l'auto-sync.")

    if enabled and provider not in ("google", "outlook"):
        raise HTTPException(status_code=400, detail="Provider invalide. Choisissez 'google' ou 'outlook'.")

    if enabled:
        connection = db.calendar_connections.find_one(
            {"user_id": user['user_id'], "provider": provider, "status": "connected"},
            {"_id": 0, "connection_id": 1}
        )
        if not connection:
            label = "Google Calendar" if provider == "google" else "Outlook Calendar"
            raise HTTPException(status_code=400, detail=f"{label} n'est pas connecté. Connectez-le d'abord.")

    db.users.update_one(
        {"user_id": user['user_id']},
        {"$set": {
            "auto_sync_enabled": enabled,
            "auto_sync_provider": provider if enabled else None,
            "updated_at": now_utc().isoformat()
        }}
    )

    return {
        "success": True,
        "auto_sync_enabled": enabled,
        "auto_sync_provider": provider if enabled else None
    }


def perform_auto_sync(user_id: str, appointment_id: str, appointment_doc: dict):
    """
    Internal function: auto-sync an appointment to the user's preferred calendar.
    Called from appointments.py after an appointment becomes active.
    Non-blocking: logs errors but never raises.
    """
    try:
        user_settings = db.users.find_one(
            {"user_id": user_id},
            {"_id": 0, "auto_sync_enabled": 1, "auto_sync_provider": 1}
        )
        if not user_settings or not user_settings.get("auto_sync_enabled"):
            return
        provider = user_settings.get("auto_sync_provider")
        if not provider:
            return

        connection = db.calendar_connections.find_one(
            {"user_id": user_id, "provider": provider, "status": "connected"}
        )
        if not connection:
            print(f"[AUTO-SYNC] No active {provider} connection for user {user_id}")
            return

        # Idempotency check
        existing = db.calendar_sync_logs.find_one({
            "appointment_id": appointment_id,
            "connection_id": connection['connection_id'],
            "sync_status": "synced"
        })
        if existing:
            return

        adapter = _get_adapter(provider)
        on_refresh = _make_token_refresh_callback(connection['connection_id'])

        calendar_tz = _resolve_timezone(adapter, connection)
        event_data = _build_event_data(appointment_doc, calendar_tz)
        result = adapter.create_event(
            connection['access_token'], connection.get('refresh_token'),
            event_data, connection_update_callback=on_refresh
        )

        sync_status = "synced" if result else "failed"
        sync_log = {
            "log_id": str(uuid.uuid4()),
            "appointment_id": appointment_id,
            "connection_id": connection['connection_id'],
            "provider": provider,
            "external_event_id": result.get('event_id') if result else None,
            "html_link": result.get('html_link') if result else None,
            "sync_status": sync_status,
            "sync_source": "auto",
            "synced_at": now_utc().isoformat()
        }
        db.calendar_sync_logs.insert_one(sync_log)

        if result:
            print(f"[AUTO-SYNC] Appointment {appointment_id} synced to {provider}")
        else:
            print(f"[AUTO-SYNC] Failed to sync appointment {appointment_id} to {provider}")
    except Exception as e:
        print(f"[AUTO-SYNC] Error for appointment {appointment_id}: {e}")


def has_calendar_fields_changed(old_doc: dict, update_data: dict) -> bool:
    """Check if any calendar-visible field has changed."""
    for field in CALENDAR_FIELDS:
        if field in update_data and str(update_data[field]) != str(old_doc.get(field, '')):
            return True
    return False


def perform_auto_update(user_id: str, appointment_id: str, updated_appointment: dict):
    """
    Update calendar events for all providers already synced for this appointment.
    Non-blocking: logs errors but never raises. Sets out_of_sync on failure.
    """
    try:
        sync_logs = list(db.calendar_sync_logs.find({
            "appointment_id": appointment_id,
            "sync_status": "synced"
        }))

        if not sync_logs:
            return

        for sync_log in sync_logs:
            provider = sync_log.get('provider')
            external_event_id = sync_log.get('external_event_id')
            connection_id = sync_log.get('connection_id')

            if not external_event_id or not connection_id:
                continue

            connection = db.calendar_connections.find_one(
                {"connection_id": connection_id, "status": "connected"}
            )
            if not connection:
                db.calendar_sync_logs.update_one(
                    {"log_id": sync_log['log_id']},
                    {"$set": {
                        "sync_status": "out_of_sync",
                        "sync_error_reason": "Connexion calendrier déconnectée ou expirée",
                        "updated_at": now_utc().isoformat()
                    }}
                )
                print(f"[AUTO-UPDATE] Connection {connection_id} not active for {provider}")
                continue

            try:
                adapter = _get_adapter(provider)
                on_refresh = _make_token_refresh_callback(connection_id)

                calendar_tz = _resolve_timezone(adapter, connection)
                event_data = _build_event_data(updated_appointment, calendar_tz)

                result = adapter.update_event(
                    connection['access_token'], connection.get('refresh_token'),
                    external_event_id, event_data,
                    connection_update_callback=on_refresh
                )

                if result:
                    db.calendar_sync_logs.update_one(
                        {"log_id": sync_log['log_id']},
                        {"$set": {
                            "sync_status": "synced",
                            "sync_error_reason": None,
                            "updated_at": now_utc().isoformat()
                        }}
                    )
                    print(f"[AUTO-UPDATE] Appointment {appointment_id} updated on {provider}")
                else:
                    db.calendar_sync_logs.update_one(
                        {"log_id": sync_log['log_id']},
                        {"$set": {
                            "sync_status": "out_of_sync",
                            "sync_error_reason": f"Échec de la mise à jour sur {provider}",
                            "updated_at": now_utc().isoformat()
                        }}
                    )
                    print(f"[AUTO-UPDATE] Failed to update on {provider} for {appointment_id}")
            except Exception as e:
                db.calendar_sync_logs.update_one(
                    {"log_id": sync_log['log_id']},
                    {"$set": {
                        "sync_status": "out_of_sync",
                        "sync_error_reason": str(e)[:200],
                        "updated_at": now_utc().isoformat()
                    }}
                )
                print(f"[AUTO-UPDATE] Error updating {provider} for {appointment_id}: {e}")
    except Exception as e:
        print(f"[AUTO-UPDATE] Fatal error for appointment {appointment_id}: {e}")


# ── Sync appointment to calendar (multi-provider) ──────────

@router.post("/sync/appointment/{appointment_id}")
async def sync_appointment_to_calendar(appointment_id: str, request: Request, provider: str = "google"):
    """
    Sync an appointment to the organizer's connected calendar.
    Provider: 'google' or 'outlook' (query param).
    """
    user = await get_current_user(request)

    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

    provider_label = "Google Calendar" if provider == "google" else "Outlook Calendar"

    connection = db.calendar_connections.find_one(
        {"user_id": user['user_id'], "provider": provider}
    )
    if not connection:
        raise HTTPException(status_code=400, detail=f"{provider_label} non connecté")
    if connection.get('status') == 'expired':
        raise HTTPException(status_code=401, detail=f"Session {provider_label} expirée. Reconnectez dans Paramètres > Intégrations.")
    if connection.get('status') != 'connected':
        raise HTTPException(status_code=400, detail=f"{provider_label} non connecté")

    # Idempotency check - already synced
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

    # Check for out_of_sync event — update instead of creating new
    out_of_sync_log = db.calendar_sync_logs.find_one({
        "appointment_id": appointment_id,
        "connection_id": connection['connection_id'],
        "sync_status": "out_of_sync"
    })

    adapter = _get_adapter(provider)
    on_refresh = _make_token_refresh_callback(connection['connection_id'])

    calendar_tz = _resolve_timezone(adapter, connection)

    event_data = _build_event_data(appointment, calendar_tz)

    if out_of_sync_log and out_of_sync_log.get('external_event_id'):
        # Re-sync: update the existing calendar event
        result = adapter.update_event(
            connection['access_token'], connection.get('refresh_token'),
            out_of_sync_log['external_event_id'], event_data,
            connection_update_callback=on_refresh
        )
        if result:
            db.calendar_sync_logs.update_one(
                {"log_id": out_of_sync_log['log_id']},
                {"$set": {
                    "sync_status": "synced",
                    "sync_error_reason": None,
                    "synced_at": now_utc().isoformat()
                }}
            )
            return {
                "sync_status": "synced",
                "external_event_id": out_of_sync_log['external_event_id'],
                "html_link": out_of_sync_log.get('html_link')
            }
        # If update fails, fall through to create a new event

    result = adapter.create_event(
        connection['access_token'], connection.get('refresh_token'),
        event_data, connection_update_callback=on_refresh
    )

    sync_status = "synced" if result else "failed"
    sync_log = {
        "log_id": str(uuid.uuid4()),
        "appointment_id": appointment_id,
        "connection_id": connection['connection_id'],
        "provider": provider,
        "external_event_id": result.get('event_id') if result else None,
        "html_link": result.get('html_link') if result else None,
        "sync_status": sync_status,
        "sync_source": "manual",
        "synced_at": now_utc().isoformat()
    }
    db.calendar_sync_logs.insert_one(sync_log)

    if not result:
        refreshed = db.calendar_connections.find_one({"connection_id": connection['connection_id']}, {"_id": 0, "status": 1})
        if refreshed and refreshed.get('status') == 'expired':
            raise HTTPException(status_code=401, detail=f"Session {provider_label} expirée. Reconnectez dans Paramètres > Intégrations.")
        raise HTTPException(status_code=502, detail=f"Échec de la synchronisation avec {provider_label}")

    return {
        "sync_status": sync_status,
        "external_event_id": result.get('event_id'),
        "html_link": result.get('html_link')
    }


@router.get("/sync/status/{appointment_id}")
async def get_sync_status(appointment_id: str, request: Request):
    """Check sync status for all connected providers."""
    user = await get_current_user(request)

    connections = list(db.calendar_connections.find(
        {"user_id": user['user_id']},
        {"_id": 0, "connection_id": 1, "provider": 1, "status": 1}
    ))

    result = {"google": {"synced": False, "has_connection": False}, "outlook": {"synced": False, "has_connection": False}}

    for conn in connections:
        provider = conn['provider']
        if provider not in result:
            continue
        result[provider]["has_connection"] = conn.get('status') == 'connected'

        sync_log = db.calendar_sync_logs.find_one(
            {"appointment_id": appointment_id, "connection_id": conn['connection_id'],
             "sync_status": {"$in": ["synced", "out_of_sync"]}},
            {"_id": 0},
            sort=[("synced_at", -1)]
        )
        if sync_log:
            result[provider]["synced"] = sync_log.get('sync_status') == 'synced'
            result[provider]["out_of_sync"] = sync_log.get('sync_status') == 'out_of_sync'
            result[provider]["external_event_id"] = sync_log.get('external_event_id')
            result[provider]["html_link"] = sync_log.get('html_link')
            result[provider]["sync_source"] = sync_log.get('sync_source', 'manual')
            if sync_log.get('sync_error_reason'):
                result[provider]["sync_error_reason"] = sync_log['sync_error_reason']

    return result


@router.delete("/sync/appointment/{appointment_id}")
async def unsync_appointment_from_calendar(appointment_id: str, request: Request):
    """Delete calendar events for this appointment across all connected providers."""
    user = await get_current_user(request)
    results = {}

    for provider in ['google', 'outlook']:
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
        if not sync_log:
            continue

        adapter = _get_adapter(provider)
        on_refresh = _make_token_refresh_callback(connection['connection_id'])

        deleted = adapter.delete_event(
            connection['access_token'], connection.get('refresh_token'),
            sync_log['external_event_id'], connection_update_callback=on_refresh
        )

        if deleted:
            db.calendar_sync_logs.update_one(
                {"log_id": sync_log['log_id']},
                {"$set": {"sync_status": "deleted", "deleted_at": now_utc().isoformat()}}
            )
        results[provider] = deleted

    return {"success": True, "deleted": results}


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
