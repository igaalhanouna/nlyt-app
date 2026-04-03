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


@router.delete("/users/{user_id}")
async def admin_delete_user(request: Request, user_id: str):
    """Delete a user permanently."""
    admin = await require_admin(request)

    target = db.users.find_one({"user_id": user_id}, {"_id": 0, "user_id": 1, "email": 1})
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if target["user_id"] == admin["user_id"]:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas supprimer votre propre compte")

    db.users.delete_one({"user_id": user_id})

    logger.info(f"[ADMIN] User {target['email']} deleted by {admin['email']}")
    return {"message": f"Utilisateur {target['email']} supprimé définitivement"}


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



# ═══════════════════════════════════════════════════════════════════
# Scheduler Health Monitoring
# ═══════════════════════════════════════════════════════════════════

def _format_interval(seconds: int) -> str:
    if seconds >= 86400:
        return f"{seconds // 86400}j"
    if seconds >= 3600:
        return f"{seconds // 3600}h"
    return f"{seconds // 60}min"


@router.get("/scheduler-health")
async def scheduler_health(request: Request):
    """
    Scheduler health dashboard — admin only.

    Returns per-job status and a global summary for quick diagnosis.

    Health logic:
      ok      — last run succeeded, no anomaly
      warning — never executed, or lock held > 80% of TTL
      error   — last run failed
    """
    await require_admin(request)

    from scheduler import scheduler as apscheduler, JOB_REGISTRY
    from services.distributed_lock import INSTANCE_ID

    now = datetime.now(timezone.utc)

    # Fetch all execution histories and active locks in bulk
    histories = {
        h["job_id"]: h
        for h in db.scheduler_job_history.find({}, {"_id": 0})
    }
    active_locks = {
        lk["job_id"]: lk
        for lk in db.scheduler_locks.find(
            {"expires_at": {"$gt": now}},
            {"_id": 0}
        )
    }

    # Build next_run map from APScheduler
    next_runs = {}
    for job in apscheduler.get_jobs():
        # job.id is like "attendance_evaluation_job", strip the "_job" suffix
        jid = job.id.removesuffix("_job")
        if job.next_run_time:
            next_runs[jid] = job.next_run_time.isoformat()

    jobs = []
    counts = {"ok": 0, "warning": 0, "error": 0}

    for job_id, meta in JOB_REGISTRY.items():
        hist = histories.get(job_id)
        lock = active_locks.get(job_id)
        ttl = meta["ttl_seconds"]

        # ── Determine current state ─────────────────────────
        if lock:
            current_state = "running"
            locked_at = lock.get("locked_at")
            expires_at = lock.get("expires_at")

            # Check if lock is stale (held > 80% of TTL)
            if locked_at:
                elapsed = (now - locked_at.replace(tzinfo=timezone.utc) if locked_at.tzinfo is None else now - locked_at).total_seconds()
                lock_stale = elapsed > ttl * 0.8
            else:
                lock_stale = False

            ttl_remaining_raw = (
                (expires_at.replace(tzinfo=timezone.utc) if expires_at.tzinfo is None else expires_at) - now
            ).total_seconds() if expires_at else 0
            ttl_remaining = max(0, int(ttl_remaining_raw))

            lock_info = {
                "locked_by": lock.get("locked_by"),
                "ttl_remaining_seconds": int(ttl_remaining),
                "stale": lock_stale,
            }
        else:
            current_state = "idle"
            lock_info = None
            lock_stale = False

        # ── Determine health status ─────────────────────────
        if hist is None:
            health_status = "warning"
            health_reason = "Jamais execute depuis le demarrage"
        elif hist.get("current_status") == "error":
            health_status = "error"
            health_reason = hist.get("last_error", "Erreur inconnue")
        elif lock_stale:
            health_status = "warning"
            health_reason = f"Lock tenu depuis plus de {int(ttl * 0.8)}s (TTL={ttl}s)"
        else:
            health_status = "ok"
            health_reason = None

        counts[health_status] += 1

        # ── Build last_run info ─────────────────────────────
        last_run = None
        if hist and hist.get("last_completed_at"):
            completed_at = hist["last_completed_at"]
            if completed_at.tzinfo is None:
                completed_at = completed_at.replace(tzinfo=timezone.utc)
            ago_seconds = int((now - completed_at).total_seconds())
            last_run = {
                "at": completed_at.isoformat(),
                "ago_seconds": ago_seconds,
                "duration_ms": hist.get("last_duration_ms", 0),
                "result": hist.get("current_status", "unknown"),
            }

        # ── Build job entry ─────────────────────────────────
        jobs.append({
            "job_id": job_id,
            "name": meta["name"],
            "interval": _format_interval(meta["interval_seconds"]),
            "interval_seconds": meta["interval_seconds"],
            "ttl_seconds": ttl,
            "health_status": health_status,
            "health_reason": health_reason,
            "current_state": current_state,
            "last_run": last_run,
            "next_run": next_runs.get(job_id),
            "lock": lock_info,
            "stats": {
                "total_runs": hist.get("total_runs", 0) if hist else 0,
                "successful_runs": hist.get("successful_runs", 0) if hist else 0,
                "failed_runs": hist.get("failed_runs", 0) if hist else 0,
            },
        })

    # Sort: errors first, then warnings, then ok
    priority = {"error": 0, "warning": 1, "ok": 2}
    jobs.sort(key=lambda j: (priority.get(j["health_status"], 3), j["job_id"]))

    total = len(JOB_REGISTRY)
    if counts["error"] > 0:
        global_status = "error"
    elif counts["warning"] > 0:
        global_status = "warning"
    else:
        global_status = "ok"

    return {
        "global_status": global_status,
        "instance_id": INSTANCE_ID,
        "checked_at": now.isoformat(),
        "summary": {
            "total_jobs": total,
            "ok": counts["ok"],
            "warning": counts["warning"],
            "error": counts["error"],
        },
        "jobs": jobs,
    }


# ═══════════════════════════════════════════════════════════════════
# Stripe Webhook Monitoring
# ═══════════════════════════════════════════════════════════════════

@router.get("/stripe-webhook-status")
async def stripe_webhook_status(request: Request):
    """
    Stripe webhook monitoring — admin only.

    Shows recent events, error rates, and active admin alerts.
    """
    await require_admin(request)

    now = datetime.now(timezone.utc)

    # Last 50 webhook events received
    recent_events = list(db.stripe_events.find(
        {},
        {"_id": 0}
    ).sort("received_at", -1).limit(50))

    # Format events for display
    events_by_type = {}
    for ev in recent_events:
        etype = ev.get("event_type", "unknown")
        events_by_type.setdefault(etype, 0)
        events_by_type[etype] += 1

    # Active admin alerts (unresolved)
    active_alerts = list(db.admin_alerts.find(
        {"resolved": False},
        {"_id": 0}
    ).sort("created_at", -1).limit(20))

    # Sanitize ObjectId if present
    for alert in active_alerts:
        alert.pop("_id", None)

    # Stats
    total_events_24h = db.stripe_events.count_documents({
        "received_at": {"$gte": (now - __import__('datetime').timedelta(hours=24)).isoformat()}
    })
    total_events_all = db.stripe_events.count_documents({})

    # Guarantees status summary
    guarantee_statuses = {}
    pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    for g in db.payment_guarantees.aggregate(pipeline):
        guarantee_statuses[g["_id"] or "unknown"] = g["count"]

    # Frozen wallets
    frozen_count = db.wallets.count_documents({"frozen": True})

    return {
        "checked_at": now.isoformat(),
        "events": {
            "total_all_time": total_events_all,
            "last_24h": total_events_24h,
            "by_type_last_50": events_by_type,
            "recent": [
                {
                    "event_id": ev.get("event_id"),
                    "type": ev.get("event_type"),
                    "received_at": ev.get("received_at"),
                }
                for ev in recent_events[:10]
            ],
        },
        "alerts": {
            "active_count": len(active_alerts),
            "items": active_alerts,
        },
        "guarantees": guarantee_statuses,
        "frozen_wallets": frozen_count,
    }
