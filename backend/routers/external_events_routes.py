"""
Routes for external calendar event import and management.
Prefix: /api/external-events
"""
from fastapi import APIRouter, HTTPException, Request
import sys
sys.path.append('/app/backend')
from middleware.auth_middleware import get_current_user
from services.external_events_service import (
    sync_provider, get_import_settings, update_import_setting, list_external_events,
    get_prefill_data
)
from database import db

router = APIRouter()


@router.get("/import-settings")
async def get_settings(request: Request):
    """Return import sync settings for all connected providers."""
    user = await get_current_user(request)
    return get_import_settings(user["user_id"])


@router.put("/import-settings")
async def update_settings(request: Request):
    """Toggle import sync for a provider.
    Body: {"provider": "google"|"outlook", "enabled": true|false}
    """
    user = await get_current_user(request)
    body = await request.json()

    provider = body.get("provider")
    enabled = body.get("enabled")

    if provider not in ("google", "outlook"):
        raise HTTPException(status_code=400, detail="Provider invalide")
    if not isinstance(enabled, bool):
        raise HTTPException(status_code=400, detail="'enabled' doit être un booléen")

    result = update_import_setting(user["user_id"], provider, enabled)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Erreur"))

    # If enabling, trigger immediate sync
    if enabled:
        sync_result = sync_provider(user["user_id"], provider, force=True)
        result["sync"] = sync_result

    return result


@router.post("/sync")
async def sync_events(request: Request):
    """Sync external events from all enabled providers.
    Optional body: {"force": true} to bypass cache.
    """
    user = await get_current_user(request)
    user_id = user["user_id"]

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    force = body.get("force", False)

    # Find active import providers
    connections = list(db.calendar_connections.find(
        {"user_id": user_id, "status": "connected", "import_sync_enabled": True},
        {"_id": 0, "provider": 1}
    ))

    results = {}
    for conn in connections:
        provider = conn["provider"]
        results[provider] = sync_provider(user_id, provider, force=force)

    return {"results": results}


@router.get("/{external_event_id}/prefill")
async def get_prefill(external_event_id: str, request: Request):
    """Get pre-fill data for the NLYT wizard from an imported external event."""
    user = await get_current_user(request)
    result = get_prefill_data(user["user_id"], external_event_id)

    if result is None:
        raise HTTPException(status_code=404, detail="Événement externe introuvable")

    if result.get("error") == "already_converted":
        raise HTTPException(status_code=409, detail="Cet événement a déjà été converti en engagement NLYT")

    if result.get("error") == "not_convertible":
        raise HTTPException(status_code=400, detail="Cet événement n'est pas convertible")

    return result


@router.get("/")
async def list_events(request: Request):
    """List imported external events for the current user.
    Only returns events from providers with active import toggle.
    """
    user = await get_current_user(request)
    user_id = user["user_id"]

    # Find active import providers
    connections = list(db.calendar_connections.find(
        {"user_id": user_id, "status": "connected", "import_sync_enabled": True},
        {"_id": 0, "provider": 1}
    ))
    active_providers = [c["provider"] for c in connections]

    if not active_providers:
        return {"events": [], "providers": []}

    events = list_external_events(user_id, active_providers)
    return {"events": events, "providers": active_providers}
