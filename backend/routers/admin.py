"""
Admin Routes — NLYT V1

Provides admin endpoints for arbitration, user management, payouts, and webhooks.
Routes are protected by granular permissions via utils/permissions.py.
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime, timezone
import logging
import os

from middleware.auth_middleware import get_current_user
from utils.permissions import require_permission, ALL_ROLES
from database import db

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Admin guard (kept for backward compat + routes that need full admin) ──

async def require_admin(request: Request) -> dict:
    return await require_permission(request, "admin:users")


# ── Models ───────────────────────────────────────────────────

class ArbitrationResolveBody(BaseModel):
    final_outcome: str  # on_time | no_show | late_penalized
    resolution_note: str


# ── Routes ───────────────────────────────────────────────────

@router.get("/arbitration")
async def list_disputes_for_admin(request: Request, filter: str = "escalated"):
    """List disputes for admin arbitration, filtered by category."""
    await require_permission(request, "admin:arbitration")

    from services.admin_arbitration_service import get_disputes_for_admin
    disputes = get_disputes_for_admin(filter)
    return {"disputes": disputes, "count": len(disputes), "filter": filter}


@router.get("/arbitration/stats")
async def get_arbitration_stats(request: Request):
    """Get KPI stats for the admin arbitration dashboard."""
    await require_permission(request, "admin:arbitration")

    from services.admin_arbitration_service import get_arbitration_stats
    return get_arbitration_stats()


@router.get("/arbitration/{dispute_id}")
async def get_dispute_for_arbitration(dispute_id: str, request: Request):
    """Get full detail of an escalated dispute for admin arbitration."""
    await require_permission(request, "admin:arbitration")

    from services.admin_arbitration_service import get_dispute_detail_for_admin
    detail = get_dispute_detail_for_admin(dispute_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Litige introuvable")
    return detail


@router.post("/arbitration/{dispute_id}/resolve")
async def resolve_escalated_dispute(dispute_id: str, body: ArbitrationResolveBody, request: Request):
    """Resolve an escalated dispute through admin arbitration.
    
    The admin rules within strict constraints:
    - No proof → no_show (default)
    - Contradiction → examine and rule
    - Always requires a written note for traceability
    """
    user = await require_permission(request, "admin:arbitration")

    valid_outcomes = ("on_time", "no_show", "late_penalized")
    if body.final_outcome not in valid_outcomes:
        raise HTTPException(status_code=400, detail=f"Outcome invalide. Valeurs: {', '.join(valid_outcomes)}")

    if not body.resolution_note or len(body.resolution_note.strip()) < 5:
        raise HTTPException(status_code=400, detail="Une note d'arbitrage est obligatoire (min 5 caracteres)")

    # Verify dispute exists and is escalated
    dispute = db.declarative_disputes.find_one({"dispute_id": dispute_id}, {"_id": 0})
    if not dispute:
        raise HTTPException(status_code=404, detail="Litige introuvable")
    if dispute.get("status") != "escalated":
        raise HTTPException(status_code=400, detail="Ce litige n'est pas en attente d'arbitrage")

    from services.declarative_service import resolve_dispute
    result = resolve_dispute(
        dispute_id,
        body.final_outcome,
        f"[Arbitrage admin — {user['first_name']} {user['last_name']}] {body.resolution_note.strip()}",
        resolved_by="admin_arbitration"
    )

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    logger.info(f"[ADMIN] Dispute {dispute_id} resolved by {user['email']}: {body.final_outcome}")
    return {"success": True, "outcome": body.final_outcome}


# ── Legacy routes (kept for backward compat) ────────────────

@router.get("/cases/review")
async def get_cases_for_review(request: Request):
    await require_admin(request)
    cases = list(db.violation_cases.find(
        {"status": "manual_review"},
        {"_id": 0}
    ).sort("created_at", -1))
    return {"cases": cases}


@router.get("/analytics/overview")
async def get_admin_analytics(request: Request):
    await require_admin(request)
    from services.admin_arbitration_service import get_arbitration_stats
    arb_stats = get_arbitration_stats()

    total_appointments = db.appointments.count_documents({})
    active_appointments = db.appointments.count_documents({"status": "active"})
    total_guarantees = db.payment_guarantees.count_documents({})
    active_guarantees = db.payment_guarantees.count_documents({"status": "authorization_active"})

    return {
        "appointments": {"total": total_appointments, "active": active_appointments},
        "guarantees": {"total": total_guarantees, "active": active_guarantees},
        "arbitration": arb_stats,
    }


@router.get("/stripe-events")
async def get_stripe_events(limit: int = 50, request: Request = None):
    await require_admin(request)
    events = list(db.stripe_events.find(
        {}, {"_id": 0}
    ).sort("received_at", -1).limit(limit))
    return {"events": events}


# ── User Management ──────────────────────────────────────────


class UpdateRoleBody(BaseModel):
    role: str


@router.get("/users")
async def admin_list_users(request: Request):
    """List all users with key info for admin management."""
    await require_admin(request)
    users = list(db.users.find(
        {},
        {"_id": 0, "user_id": 1, "email": 1, "first_name": 1, "last_name": 1,
         "role": 1, "is_verified": 1, "auth_provider": 1, "google_id": 1,
         "microsoft_id": 1, "created_at": 1}
    ).sort("created_at", -1))

    for u in users:
        u.setdefault("role", "user")
        u.setdefault("auth_provider", "email")
        providers = []
        if u.get("google_id"):
            providers.append("google")
        if u.get("microsoft_id"):
            providers.append("microsoft")
        if u.get("password_hash") is not None or not providers:
            providers.insert(0, "email")
        u["providers"] = providers
        u.pop("google_id", None)
        u.pop("microsoft_id", None)

    return {"users": users, "count": len(users)}


@router.patch("/users/{user_id}/role")
async def admin_update_user_role(request: Request, user_id: str, body: UpdateRoleBody):
    """Change a user's role."""
    admin = await require_admin(request)

    if body.role not in ALL_ROLES:
        raise HTTPException(status_code=400, detail=f"Role invalide. Valeurs acceptees: {ALL_ROLES}")

    target = db.users.find_one({"user_id": user_id}, {"_id": 0, "user_id": 1, "email": 1})
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if target["user_id"] == admin["user_id"]:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas modifier votre propre role")

    from utils.date_utils import now_utc_iso
    db.users.update_one(
        {"user_id": user_id},
        {"$set": {"role": body.role, "updated_at": now_utc_iso()}}
    )

    logger.info(f"[ADMIN] User {target['email']} role changed to {body.role} by {admin['email']}")
    return {"user_id": user_id, "email": target["email"], "role": body.role}


# ── Stale Payouts ────────────────────────────────────────────

@router.get("/stale-payouts")
async def get_stale_payouts(request: Request):
    """List all payouts currently in 'stale' or 'processing' > 24h status."""
    await require_permission(request, "admin:stale-payouts")

    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    stale_payouts = list(db.payouts.find(
        {"$or": [
            {"status": "stale"},
            {"status": "processing", "updated_at": {"$lt": cutoff}},
        ]},
        {"_id": 0}
    ))

    # Enrich with user email
    user_ids = list({p.get("user_id") for p in stale_payouts if p.get("user_id")})
    user_map = {}
    if user_ids:
        users = db.users.find({"user_id": {"$in": user_ids}}, {"_id": 0, "user_id": 1, "email": 1})
        user_map = {u["user_id"]: u["email"] for u in users}

    for p in stale_payouts:
        p["user_email"] = user_map.get(p.get("user_id"), None)

    stale_payouts.sort(key=lambda x: x.get("updated_at", ""), reverse=False)

    return {"stale_payouts": stale_payouts, "count": len(stale_payouts)}


# ── Video Webhook Management ─────────────────────────────────

@router.post("/webhooks/teams-subscribe")
async def create_teams_subscription(request: Request):
    """Create a Microsoft Graph subscription for call records (admin only)."""
    await require_admin(request)
    from routers.video_webhooks import create_graph_subscription
    result = create_graph_subscription()
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.get("/webhooks/status")
async def get_webhook_status(request: Request):
    """Get status of video webhook integrations (admin only)."""
    await require_admin(request)
    from datetime import timedelta

    # Zoom webhook events (last 24h)
    cutoff_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    zoom_events = db.video_webhook_events.count_documents({
        "provider": "zoom", "received_at": {"$gte": cutoff_24h}
    })
    zoom_processed = db.video_webhook_events.count_documents({
        "provider": "zoom", "processed": True, "received_at": {"$gte": cutoff_24h}
    })

    # Teams webhook events (last 24h)
    teams_events = db.video_webhook_events.count_documents({
        "provider": "teams", "received_at": {"$gte": cutoff_24h}
    })
    teams_processed = db.video_webhook_events.count_documents({
        "provider": "teams", "processed": True, "received_at": {"$gte": cutoff_24h}
    })

    # Graph subscriptions
    graph_subs = list(db.graph_subscriptions.find({}, {"_id": 0}))

    zoom_secret_configured = bool(os.environ.get("ZOOM_WEBHOOK_SECRET_TOKEN"))

    return {
        "zoom": {
            "secret_configured": zoom_secret_configured,
            "webhook_url": f"{os.environ.get('FRONTEND_URL', '')}/api/webhooks/zoom",
            "events_24h": zoom_events,
            "processed_24h": zoom_processed,
        },
        "teams": {
            "client_configured": bool(os.environ.get("MICROSOFT_CLIENT_ID")),
            "webhook_url": f"{os.environ.get('FRONTEND_URL', '')}/api/webhooks/teams",
            "events_24h": teams_events,
            "processed_24h": teams_processed,
            "subscriptions": graph_subs,
        },
    }
