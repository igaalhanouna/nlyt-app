"""
Service for importing and managing external calendar events.
Handles sync, deduplication, and CRUD for external_events collection.
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone

from database import db
from adapters.google_calendar_adapter import GoogleCalendarAdapter
from adapters.outlook_calendar_adapter import OutlookCalendarAdapter
from utils.date_utils import now_utc

IMPORT_WINDOW_DAYS = 30
CACHE_TTL_SECONDS = 300  # 5 minutes


def _make_token_refresh_callback(connection_id: str):
    """Create a callback that persists refreshed tokens or marks connection expired."""
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


def _compute_event_hash(ev: dict) -> str:
    """Compute a stable hash of event content to detect changes."""
    payload = json.dumps({
        "title": ev.get("title", ""),
        "start": ev.get("start", ""),
        "end": ev.get("end", ""),
        "location": ev.get("location") or "",
        "attendees": sorted([a.get("email", "") for a in (ev.get("attendees") or [])]),
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _parse_dt(s: str):
    """Parse ISO datetime string to aware UTC datetime."""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _get_nlyt_external_ids(connection_ids: list) -> set:
    """Collect all external_event_ids of events pushed from NLYT."""
    nlyt_ids = set()
    if not connection_ids:
        return nlyt_ids
    sync_logs = db.calendar_sync_logs.find(
        {"connection_id": {"$in": connection_ids}, "sync_status": {"$in": ["synced", "retry_pending"]}},
        {"_id": 0, "external_event_id": 1}
    )
    for sl in sync_logs:
        eid = sl.get("external_event_id")
        if eid:
            nlyt_ids.add(eid)
    return nlyt_ids


def _get_converted_external_ids(user_id: str) -> set:
    """Collect external_event_ids already converted to NLYT."""
    converted = set()
    docs = db.external_events.find(
        {"imported_by_user_id": user_id, "status": "converted"},
        {"_id": 0, "external_event_id": 1}
    )
    for d in docs:
        converted.add(d["external_event_id"])
    return converted


def sync_provider(user_id: str, provider: str, force: bool = False) -> dict:
    """
    Sync external events from a single provider.
    Returns {synced: bool, event_count: int, error: str|None}.
    Respects cache TTL unless force=True.
    """
    connection = db.calendar_connections.find_one(
        {"user_id": user_id, "provider": provider, "status": "connected"},
        {"_id": 0}
    )
    if not connection:
        return {"synced": False, "event_count": 0, "error": f"{provider} non connecté"}

    # Check import toggle
    if not connection.get("import_sync_enabled"):
        return {"synced": False, "event_count": 0, "error": "Import désactivé"}

    # Check cache TTL
    if not force:
        last_sync = connection.get("import_last_synced_at")
        if last_sync:
            last_dt = _parse_dt(last_sync)
            if last_dt and (datetime.now(timezone.utc) - last_dt).total_seconds() < CACHE_TTL_SECONDS:
                count = connection.get("import_event_count", 0)
                return {"synced": True, "event_count": count, "error": None, "cached": True}

    # Compute time window
    now = datetime.now(timezone.utc)
    window_start = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    window_end = (now + timedelta(days=IMPORT_WINDOW_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Fetch events from provider
    connection_id = connection["connection_id"]
    on_refresh = _make_token_refresh_callback(connection_id)

    raw_events = None
    if provider == "google":
        raw_events = GoogleCalendarAdapter.list_events(
            connection["access_token"], connection.get("refresh_token"),
            window_start, window_end, connection_update_callback=on_refresh
        )
    elif provider == "outlook":
        raw_events = OutlookCalendarAdapter.list_events(
            connection["access_token"], connection.get("refresh_token"),
            window_start, window_end, connection_update_callback=on_refresh
        )

    if raw_events is None:
        # Check if token expired
        refreshed = db.calendar_connections.find_one(
            {"connection_id": connection_id}, {"_id": 0, "status": 1}
        )
        if refreshed and refreshed.get("status") == "expired":
            return {"synced": False, "event_count": 0, "error": f"Session {provider} expirée. Reconnectez dans Paramètres > Intégrations."}
        return {"synced": False, "event_count": 0, "error": f"Erreur lors de la récupération des événements {provider}"}

    # Deduplication: collect NLYT-pushed event IDs + already converted
    nlyt_external_ids = _get_nlyt_external_ids([connection_id])
    converted_ids = _get_converted_external_ids(user_id)

    imported_count = 0
    for ev in raw_events:
        event_id = ev.get("event_id")
        if not event_id:
            continue

        # Skip NLYT-origin events (pushed from NLYT to calendar)
        if event_id in nlyt_external_ids:
            continue

        # Skip events with [NLYT] prefix (safety net)
        title = ev.get("title", "")
        if title.startswith("[NLYT]"):
            continue

        # Skip all-day events
        if ev.get("is_all_day"):
            continue

        # Skip already converted events
        if event_id in converted_ids:
            continue

        # Parse dates
        start_dt = _parse_dt(ev["start"])
        end_dt = _parse_dt(ev["end"])
        if not start_dt or not end_dt:
            continue

        duration_minutes = max(int((end_dt - start_dt).total_seconds() / 60), 1)
        event_hash = _compute_event_hash(ev)

        doc = {
            "external_event_id": event_id,
            "source": provider,
            "connection_id": connection_id,
            "imported_by_user_id": user_id,
            "title": title,
            "description": ev.get("description"),
            "start_datetime": start_dt.isoformat(),
            "end_datetime": end_dt.isoformat(),
            "duration_minutes": duration_minutes,
            "location": ev.get("location"),
            "organizer_email": (ev.get("organizer") or {}).get("email"),
            "organizer_name": (ev.get("organizer") or {}).get("name"),
            "attendees": ev.get("attendees") or [],
            "conference_url": ev.get("conference_url"),
            "conference_provider": ev.get("conference_provider"),
            "is_nlyt_origin": False,
            "status": "imported",
            "nlyt_appointment_id": None,
            "last_synced_at": now_utc().isoformat(),
            "raw_event_hash": event_hash,
        }

        # Upsert: update if hash changed, insert if new
        existing = db.external_events.find_one(
            {"external_event_id": event_id, "source": provider},
            {"_id": 0, "raw_event_hash": 1, "status": 1}
        )

        if existing:
            if existing.get("status") == "converted":
                continue  # Don't overwrite converted events
            if existing.get("raw_event_hash") != event_hash:
                db.external_events.update_one(
                    {"external_event_id": event_id, "source": provider},
                    {"$set": {
                        "title": doc["title"],
                        "description": doc["description"],
                        "start_datetime": doc["start_datetime"],
                        "end_datetime": doc["end_datetime"],
                        "duration_minutes": doc["duration_minutes"],
                        "location": doc["location"],
                        "organizer_email": doc["organizer_email"],
                        "organizer_name": doc["organizer_name"],
                        "attendees": doc["attendees"],
                        "conference_url": doc["conference_url"],
                        "conference_provider": doc["conference_provider"],
                        "last_synced_at": doc["last_synced_at"],
                        "raw_event_hash": event_hash,
                    }}
                )
        else:
            doc["first_imported_at"] = now_utc().isoformat()
            db.external_events.insert_one(doc)

        imported_count += 1

    # Mark events no longer returned by API as deleted_externally
    # (only for events from this provider that were NOT converted)
    returned_ids = {ev["event_id"] for ev in raw_events if ev.get("event_id")}
    stale = db.external_events.find(
        {
            "imported_by_user_id": user_id,
            "source": provider,
            "status": "imported",
            "external_event_id": {"$nin": list(returned_ids)},
            "start_datetime": {"$gte": window_start},
        },
        {"_id": 0, "external_event_id": 1}
    )
    stale_ids = [s["external_event_id"] for s in stale]
    if stale_ids:
        db.external_events.update_many(
            {"external_event_id": {"$in": stale_ids}, "source": provider, "status": "imported"},
            {"$set": {"status": "deleted_externally", "last_synced_at": now_utc().isoformat()}}
        )

    # Update connection metadata
    db.calendar_connections.update_one(
        {"connection_id": connection_id},
        {"$set": {
            "import_last_synced_at": now_utc().isoformat(),
            "import_event_count": imported_count,
        }}
    )

    return {"synced": True, "event_count": imported_count, "error": None}


def get_import_settings(user_id: str) -> dict:
    """Return import sync status for all connected providers."""
    connections = list(db.calendar_connections.find(
        {"user_id": user_id, "status": "connected"},
        {"_id": 0, "provider": 1, "import_sync_enabled": 1,
         "import_last_synced_at": 1, "import_event_count": 1}
    ))

    providers = {}
    for c in connections:
        p = c["provider"]
        providers[p] = {
            "connected": True,
            "import_enabled": c.get("import_sync_enabled", False),
            "last_synced_at": c.get("import_last_synced_at"),
            "event_count": c.get("import_event_count", 0),
        }

    return {"providers": providers}


def update_import_setting(user_id: str, provider: str, enabled: bool) -> dict:
    """Toggle import sync for a provider."""
    result = db.calendar_connections.update_one(
        {"user_id": user_id, "provider": provider, "status": "connected"},
        {"$set": {"import_sync_enabled": enabled, "updated_at": now_utc().isoformat()}}
    )
    if result.matched_count == 0:
        return {"success": False, "error": f"{provider} non connecté"}
    return {"success": True, "provider": provider, "import_enabled": enabled}


def get_prefill_data(user_id: str, external_event_id: str) -> dict:
    """Get pre-fill data for the NLYT wizard from an external event."""
    event = db.external_events.find_one(
        {"external_event_id": external_event_id, "imported_by_user_id": user_id},
        {"_id": 0}
    )
    if not event:
        return None

    if event.get("status") == "converted":
        return {"error": "already_converted", "nlyt_appointment_id": event.get("nlyt_appointment_id")}

    if event.get("status") != "imported":
        return {"error": "not_convertible"}

    # Best-effort name split for attendees
    suggested_participants = []
    for att in (event.get("attendees") or []):
        email = att.get("email", "").strip()
        if not email:
            continue
        name = att.get("name", "").strip()
        if name:
            parts = name.split(" ", 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""
        else:
            first_name = email.split("@")[0]
            last_name = ""
        suggested_participants.append({
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
        })

    # Determine appointment type
    appointment_type = "physical"
    meeting_provider = None
    if event.get("conference_url"):
        appointment_type = "video"
        meeting_provider = event.get("conference_provider")

    # Convert ISO datetime to local input format for the wizard
    start_dt = event.get("start_datetime", "")
    local_start = ""
    if start_dt:
        try:
            dt = datetime.fromisoformat(start_dt.replace("Z", "+00:00"))
            local_start = dt.strftime("%Y-%m-%dT%H:%M")
        except Exception:
            local_start = start_dt[:16] if len(start_dt) >= 16 else ""

    return {
        "prefill": {
            "title": event.get("title", ""),
            "appointment_type": appointment_type,
            "location": event.get("location") or "",
            "meeting_provider": meeting_provider,
            "conference_url": event.get("conference_url") or "",
            "start_datetime": local_start,
            "duration_minutes": event.get("duration_minutes", 60),
            "suggested_participants": suggested_participants,
        },
        "source": event.get("source"),
        "external_event_id": external_event_id,
    }


def mark_as_converted(user_id: str, external_event_id: str, nlyt_appointment_id: str) -> dict:
    """Atomically mark an external event as converted. Returns error dict or success."""
    # Explicit check for clear error messages
    event = db.external_events.find_one(
        {"external_event_id": external_event_id, "imported_by_user_id": user_id},
        {"_id": 0, "status": 1}
    )
    if not event:
        return {"error": "not_found"}
    if event["status"] == "converted":
        return {"error": "already_converted"}
    if event["status"] != "imported":
        return {"error": "not_convertible"}

    # Atomic update with status condition (optimistic lock)
    result = db.external_events.update_one(
        {
            "external_event_id": external_event_id,
            "imported_by_user_id": user_id,
            "status": "imported",
        },
        {"$set": {
            "status": "converted",
            "nlyt_appointment_id": nlyt_appointment_id,
            "converted_at": now_utc().isoformat(),
        }}
    )
    if result.modified_count == 0:
        return {"error": "already_converted"}

    return {"success": True}


def list_external_events(user_id: str, active_providers: list = None) -> list:
    """List imported external events for the user, filtered by active providers."""
    query = {
        "imported_by_user_id": user_id,
        "status": "imported",
        "start_datetime": {"$gte": datetime.now(timezone.utc).isoformat()},
    }
    if active_providers:
        query["source"] = {"$in": active_providers}

    events = list(db.external_events.find(
        query,
        {"_id": 0}
    ).sort("start_datetime", 1).limit(100))

    return events
