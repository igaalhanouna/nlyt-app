"""
Background Scheduler for NLYT

All jobs are protected by a distributed MongoDB lock and their execution
is tracked (start, duration, success/failure) for the health endpoint.
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from services.distributed_lock import run_locked_job

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

# ═══════════════════════════════════════════════════════════════════
# Job Registry — single source of truth for all scheduler metadata
# ═══════════════════════════════════════════════════════════════════

JOB_REGISTRY = {
    "cancellation_deadline_reminder": {
        "name": "Rappels deadline annulation",
        "interval_seconds": 300,
        "ttl_seconds": 240,
    },
    "event_reminder": {
        "name": "Rappels evenement (10min/1h/1j)",
        "interval_seconds": 120,
        "ttl_seconds": 90,
    },
    "attendance_evaluation": {
        "name": "Evaluation presences RDV termines",
        "interval_seconds": 120,
        "ttl_seconds": 90,
    },
    "proposal_expiration": {
        "name": "Expiration propositions modification (24h)",
        "interval_seconds": 300,
        "ttl_seconds": 240,
    },
    "modification_vote_reminder": {
        "name": "Rappels votes propositions",
        "interval_seconds": 900,
        "ttl_seconds": 600,
    },
    "auto_fetch_attendance": {
        "name": "Fetch auto presence Zoom/Teams",
        "interval_seconds": 300,
        "ttl_seconds": 240,
    },
    "distribution_hold_expiry": {
        "name": "Finalisation distributions (15j hold)",
        "interval_seconds": 900,
        "ttl_seconds": 600,
    },
    "impact_stats_refresh": {
        "name": "Rafraichissement stats impact",
        "interval_seconds": 1800,
        "ttl_seconds": 900,
    },
    "calendar_retry": {
        "name": "Retry sync calendrier (backoff)",
        "interval_seconds": 120,
        "ttl_seconds": 90,
    },
    "review_timeout": {
        "name": "Timeout reviews (15 jours)",
        "interval_seconds": 21600,
        "ttl_seconds": 1800,
    },
    "declarative_deadline": {
        "name": "Deadline feuilles de presence (48h)",
        "interval_seconds": 300,
        "ttl_seconds": 240,
    },
    "dispute_escalation": {
        "name": "Escalade litiges (7 jours)",
        "interval_seconds": 900,
        "ttl_seconds": 600,
    },
    "contestation_timeout": {
        "name": "Timeout contestations (30 jours)",
        "interval_seconds": 43200,
        "ttl_seconds": 1800,
    },
    "ledger_reconciliation": {
        "name": "Reconciliation wallet/ledger",
        "interval_seconds": 21600,
        "ttl_seconds": 1800,
    },
    "stale_payout_detection": {
        "name": "Detection payouts bloques (>24h)",
        "interval_seconds": 21600,
        "ttl_seconds": 1800,
    },
    "graph_subscription_renewal": {
        "name": "Renouvellement webhooks Teams",
        "interval_seconds": 86400,
        "ttl_seconds": 1800,
    },
    "sheet_reminder": {
        "name": "Rappels feuilles presence (<12h)",
        "interval_seconds": 1800,
        "ttl_seconds": 900,
    },
    "stale_guarantee_cleanup": {
        "name": "Cleanup garanties abandonnees (>1h)",
        "interval_seconds": 900,
        "ttl_seconds": 600,
    },
}


# ═══════════════════════════════════════════════════════════════════
# Job definitions
# ═══════════════════════════════════════════════════════════════════

async def cancellation_deadline_reminder_job():
    from services.reminder_service import run_reminder_job
    await run_locked_job("cancellation_deadline_reminder", 240, run_reminder_job)


async def event_reminder_job():
    from services.event_reminder_service import run_event_reminder_job
    await run_locked_job("event_reminder", 90, run_event_reminder_job)


async def attendance_evaluation_job():
    from services.attendance_service import run_attendance_evaluation_job
    await run_locked_job("attendance_evaluation", 90, run_attendance_evaluation_job)


async def review_timeout_job():
    from services.attendance_service import run_review_timeout_job
    await run_locked_job("review_timeout", 1800, run_review_timeout_job)


async def declarative_deadline_job():
    from services.declarative_service import run_declarative_deadline_job
    await run_locked_job("declarative_deadline", 240, run_declarative_deadline_job)


async def dispute_escalation_job():
    from services.declarative_service import run_dispute_deadline_job
    await run_locked_job("dispute_escalation", 600, run_dispute_deadline_job)


async def auto_fetch_attendance_job():
    from services.auto_fetch_attendance_service import run_auto_fetch_attendance_job
    await run_locked_job("auto_fetch_attendance", 240, run_auto_fetch_attendance_job)


async def distribution_hold_expiry_job():
    from services.distribution_service import finalize_expired_holds
    await run_locked_job("distribution_hold_expiry", 600, finalize_expired_holds)


async def contestation_timeout_job():
    from services.distribution_service import run_contestation_timeout_job
    await run_locked_job("contestation_timeout", 1800, run_contestation_timeout_job)


async def ledger_reconciliation_job():
    from services.wallet_service import run_reconciliation_job
    await run_locked_job("ledger_reconciliation", 1800, run_reconciliation_job)


async def impact_stats_refresh_job():
    from services.distribution_service import refresh_impact_stats
    await run_locked_job("impact_stats_refresh", 900, refresh_impact_stats)


async def proposal_expiration_job():
    from services.modification_service import expire_stale_proposals
    await run_locked_job("proposal_expiration", 240, expire_stale_proposals)


async def modification_vote_reminder_job():
    from services.modification_service import send_modification_vote_reminders
    await run_locked_job("modification_vote_reminder", 600, send_modification_vote_reminders)


async def calendar_retry_job():
    from services.calendar_retry_service import run_calendar_retry_job
    await run_locked_job("calendar_retry", 90, run_calendar_retry_job)


async def stale_payout_detection_job():
    from services.stale_payout_detector import scan_stale_payouts
    await run_locked_job("stale_payout_detection", 1800, scan_stale_payouts)


async def graph_subscription_renewal_job():
    from routers.video_webhooks import renew_all_graph_subscriptions
    await run_locked_job("graph_subscription_renewal", 1800, renew_all_graph_subscriptions)


async def sheet_reminder_job():
    from services.declarative_service import run_sheet_reminder_job
    await run_locked_job("sheet_reminder", 900, run_sheet_reminder_job)


async def stale_guarantee_cleanup_job():
    from services.stale_guarantee_cleanup import run_stale_guarantee_cleanup
    await run_locked_job("stale_guarantee_cleanup", 600, run_stale_guarantee_cleanup)


# ═══════════════════════════════════════════════════════════════════
# Scheduler setup
# ═══════════════════════════════════════════════════════════════════

# Maps job_id → (function, APScheduler trigger kwargs)
_JOB_SCHEDULE = {
    "cancellation_deadline_reminder": (cancellation_deadline_reminder_job, {"minutes": 5}),
    "event_reminder": (event_reminder_job, {"minutes": 2}),
    "attendance_evaluation": (attendance_evaluation_job, {"minutes": 2}),
    "proposal_expiration": (proposal_expiration_job, {"minutes": 5}),
    "modification_vote_reminder": (modification_vote_reminder_job, {"minutes": 15}),
    "auto_fetch_attendance": (auto_fetch_attendance_job, {"minutes": 5}),
    "distribution_hold_expiry": (distribution_hold_expiry_job, {"minutes": 15}),
    "impact_stats_refresh": (impact_stats_refresh_job, {"minutes": 30}),
    "calendar_retry": (calendar_retry_job, {"minutes": 2}),
    "review_timeout": (review_timeout_job, {"hours": 6}),
    "declarative_deadline": (declarative_deadline_job, {"minutes": 5}),
    "dispute_escalation": (dispute_escalation_job, {"minutes": 15}),
    "contestation_timeout": (contestation_timeout_job, {"hours": 12}),
    "ledger_reconciliation": (ledger_reconciliation_job, {"hours": 6}),
    "stale_payout_detection": (stale_payout_detection_job, {"hours": 6}),
    "graph_subscription_renewal": (graph_subscription_renewal_job, {"hours": 24}),
    "sheet_reminder": (sheet_reminder_job, {"minutes": 30}),
    "stale_guarantee_cleanup": (stale_guarantee_cleanup_job, {"minutes": 15}),
}


def start_scheduler():
    """Start the background scheduler with distributed locking."""
    from services.distributed_lock import ensure_lock_indexes
    ensure_lock_indexes()

    for job_id, (fn, trigger_kw) in _JOB_SCHEDULE.items():
        meta = JOB_REGISTRY[job_id]
        scheduler.add_job(
            fn,
            trigger=IntervalTrigger(**trigger_kw),
            id=f"{job_id}_job",
            name=meta["name"],
            replace_existing=True,
        )

    scheduler.start()
    logger.info("[SCHEDULER] Background scheduler started (distributed locks enabled)")
    for job_id, meta in JOB_REGISTRY.items():
        iv = meta["interval_seconds"]
        if iv >= 3600:
            label = f"{iv // 3600}h"
        else:
            label = f"{iv // 60}min"
        logger.info(f"[SCHEDULER]    - {meta['name']}: every {label}")


def stop_scheduler():
    """Stop the scheduler"""
    scheduler.shutdown()
    logger.info("[SCHEDULER] Scheduler stopped")
