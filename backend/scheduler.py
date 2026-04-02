"""
Background Scheduler for NLYT
Runs periodic tasks like reminder emails

All jobs are protected by a distributed MongoDB lock to prevent
concurrent execution across multiple pods/instances.
"""
import asyncio
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from services.distributed_lock import acquire_lock, release_lock

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


# ═══════════════════════════════════════════════════════════════════
# Job definitions — each protected by distributed lock
# ═══════════════════════════════════════════════════════════════════

async def cancellation_deadline_reminder_job():
    """Job to send reminders 1h before cancellation deadline"""
    if not acquire_lock("cancellation_deadline_reminder", ttl_seconds=240):
        return
    try:
        from services.reminder_service import run_reminder_job
        await run_reminder_job()
    except Exception as e:
        logger.error(f"[SCHEDULER] Cancellation deadline reminder job failed: {str(e)}")
    finally:
        release_lock("cancellation_deadline_reminder")


async def event_reminder_job():
    """Job to send event reminders (10min/1h/1day before RDV)"""
    if not acquire_lock("event_reminder", ttl_seconds=90):
        return
    try:
        from services.event_reminder_service import run_event_reminder_job
        await run_event_reminder_job()
    except Exception as e:
        logger.error(f"[SCHEDULER] Event reminder job failed: {str(e)}")
    finally:
        release_lock("event_reminder")


async def attendance_evaluation_job():
    """Job to evaluate attendance for ended appointments"""
    if not acquire_lock("attendance_evaluation", ttl_seconds=90):
        return
    try:
        from services.attendance_service import run_attendance_evaluation_job
        run_attendance_evaluation_job()
    except Exception as e:
        logger.error(f"[SCHEDULER] Attendance evaluation job failed: {str(e)}")
    finally:
        release_lock("attendance_evaluation")


async def review_timeout_job():
    """Job to auto-resolve stale review_required records after 15 days"""
    if not acquire_lock("review_timeout", ttl_seconds=1800):
        return
    try:
        from services.attendance_service import run_review_timeout_job
        run_review_timeout_job()
    except Exception as e:
        logger.error(f"[SCHEDULER] Review timeout job failed: {str(e)}")
    finally:
        release_lock("review_timeout")


async def declarative_deadline_job():
    """Job to enforce 48h deadline on attendance sheets"""
    if not acquire_lock("declarative_deadline", ttl_seconds=240):
        return
    try:
        from services.declarative_service import run_declarative_deadline_job
        run_declarative_deadline_job()
    except Exception as e:
        logger.error(f"[SCHEDULER] Declarative deadline job failed: {str(e)}")
    finally:
        release_lock("declarative_deadline")


async def dispute_escalation_job():
    """Job to escalate disputes past 7-day deadline"""
    if not acquire_lock("dispute_escalation", ttl_seconds=600):
        return
    try:
        from services.declarative_service import run_dispute_deadline_job
        run_dispute_deadline_job()
    except Exception as e:
        logger.error(f"[SCHEDULER] Dispute escalation job failed: {str(e)}")
    finally:
        release_lock("dispute_escalation")


async def auto_fetch_attendance_job():
    """Job to auto-fetch video attendance from Zoom/Teams after meetings end"""
    if not acquire_lock("auto_fetch_attendance", ttl_seconds=240):
        return
    try:
        from services.auto_fetch_attendance_service import run_auto_fetch_attendance_job
        run_auto_fetch_attendance_job()
    except Exception as e:
        logger.error(f"[SCHEDULER] Auto-fetch attendance job failed: {str(e)}")
    finally:
        release_lock("auto_fetch_attendance")


async def distribution_hold_expiry_job():
    """Job to finalize distributions whose 15-day hold period has expired"""
    if not acquire_lock("distribution_hold_expiry", ttl_seconds=600):
        return
    try:
        from services.distribution_service import finalize_expired_holds
        finalize_expired_holds()
    except Exception as e:
        logger.error(f"[SCHEDULER] Distribution hold expiry job failed: {str(e)}")
    finally:
        release_lock("distribution_hold_expiry")


async def contestation_timeout_job():
    """Job to auto-reject stale contestations after 30 days"""
    if not acquire_lock("contestation_timeout", ttl_seconds=1800):
        return
    try:
        from services.distribution_service import run_contestation_timeout_job
        run_contestation_timeout_job()
    except Exception as e:
        logger.error(f"[SCHEDULER] Contestation timeout job failed: {str(e)}")
    finally:
        release_lock("contestation_timeout")


async def ledger_reconciliation_job():
    """Job to verify wallet balances match the ledger"""
    if not acquire_lock("ledger_reconciliation", ttl_seconds=1800):
        return
    try:
        from services.wallet_service import run_reconciliation_job
        run_reconciliation_job()
    except Exception as e:
        logger.error(f"[SCHEDULER] Ledger reconciliation job failed: {str(e)}")
    finally:
        release_lock("ledger_reconciliation")


async def impact_stats_refresh_job():
    """Job to refresh cached public impact statistics"""
    if not acquire_lock("impact_stats_refresh", ttl_seconds=900):
        return
    try:
        from services.distribution_service import refresh_impact_stats
        refresh_impact_stats()
    except Exception as e:
        logger.error(f"[SCHEDULER] Impact stats refresh job failed: {str(e)}")
    finally:
        release_lock("impact_stats_refresh")


async def proposal_expiration_job():
    """Job to expire stale modification proposals (24h timeout)"""
    if not acquire_lock("proposal_expiration", ttl_seconds=240):
        return
    try:
        from services.modification_service import expire_stale_proposals
        expire_stale_proposals()
    except Exception as e:
        logger.error(f"[SCHEDULER] Proposal expiration job failed: {str(e)}")
    finally:
        release_lock("proposal_expiration")


async def modification_vote_reminder_job():
    """Job to send vote reminders for proposals expiring within 1 hour"""
    if not acquire_lock("modification_vote_reminder", ttl_seconds=600):
        return
    try:
        from services.modification_service import send_modification_vote_reminders
        send_modification_vote_reminders()
    except Exception as e:
        logger.error(f"[SCHEDULER] Vote reminder job failed: {str(e)}")
    finally:
        release_lock("modification_vote_reminder")


async def calendar_retry_job():
    """Job to retry failed/out_of_sync calendar sync operations with exponential backoff"""
    if not acquire_lock("calendar_retry", ttl_seconds=90):
        return
    try:
        from services.calendar_retry_service import run_calendar_retry_job
        run_calendar_retry_job()
    except Exception as e:
        logger.error(f"[SCHEDULER] Calendar retry job failed: {str(e)}")
    finally:
        release_lock("calendar_retry")


async def stale_payout_detection_job():
    """Job to detect payouts stuck in processing for more than 24h"""
    if not acquire_lock("stale_payout_detection", ttl_seconds=1800):
        return
    try:
        from services.stale_payout_detector import scan_stale_payouts
        scan_stale_payouts()
    except Exception as e:
        logger.error(f"[SCHEDULER] Stale payout detection job failed: {str(e)}")
    finally:
        release_lock("stale_payout_detection")


async def graph_subscription_renewal_job():
    """Job to renew Microsoft Graph webhook subscriptions before expiry"""
    if not acquire_lock("graph_subscription_renewal", ttl_seconds=1800):
        return
    try:
        from routers.video_webhooks import renew_all_graph_subscriptions
        renew_all_graph_subscriptions()
    except Exception as e:
        logger.error(f"[SCHEDULER] Graph subscription renewal job failed: {str(e)}")
    finally:
        release_lock("graph_subscription_renewal")


async def sheet_reminder_job():
    """Job to send reminders for pending attendance sheets approaching deadline"""
    if not acquire_lock("sheet_reminder", ttl_seconds=900):
        return
    try:
        from services.declarative_service import run_sheet_reminder_job
        run_sheet_reminder_job()
    except Exception as e:
        logger.error(f"[SCHEDULER] Sheet reminder job failed: {str(e)}")
    finally:
        release_lock("sheet_reminder")


# ═══════════════════════════════════════════════════════════════════
# Scheduler setup
# ═══════════════════════════════════════════════════════════════════

def start_scheduler():
    """Start the background scheduler with distributed locking."""
    from services.distributed_lock import ensure_lock_indexes
    ensure_lock_indexes()

    # Job 1: Cancellation deadline reminders (every 5 minutes)
    scheduler.add_job(
        cancellation_deadline_reminder_job,
        trigger=IntervalTrigger(minutes=5),
        id='cancellation_deadline_reminder_job',
        name='Send reminder emails 1h before cancellation deadline',
        replace_existing=True
    )
    
    # Job 2: Event reminders - 10min/1h/1day before RDV (every 2 minutes for precision)
    scheduler.add_job(
        event_reminder_job,
        trigger=IntervalTrigger(minutes=2),
        id='event_reminder_job',
        name='Send event reminders (10min/1h/1day before RDV)',
        replace_existing=True
    )
    
    # Job 3: Attendance evaluation (every 2 minutes)
    scheduler.add_job(
        attendance_evaluation_job,
        trigger=IntervalTrigger(minutes=2),
        id='attendance_evaluation_job',
        name='Evaluate attendance for ended appointments',
        replace_existing=True
    )

    # Job 4: Modification proposal expiration (every 5 minutes)
    scheduler.add_job(
        proposal_expiration_job,
        trigger=IntervalTrigger(minutes=5),
        id='proposal_expiration_job',
        name='Expire stale modification proposals (24h timeout)',
        replace_existing=True
    )

    # Job 4b: Vote reminder for proposals expiring within 1h (every 15 minutes)
    scheduler.add_job(
        modification_vote_reminder_job,
        trigger=IntervalTrigger(minutes=15),
        id='modification_vote_reminder_job',
        name='Send vote reminders for expiring proposals',
        replace_existing=True
    )

    # Job 5: Auto-fetch video attendance from Zoom/Teams (every 5 minutes)
    scheduler.add_job(
        auto_fetch_attendance_job,
        trigger=IntervalTrigger(minutes=5),
        id='auto_fetch_attendance_job',
        name='Auto-fetch Zoom/Teams attendance after meeting ends',
        replace_existing=True
    )

    # Job 6: Distribution hold expiry (every 15 minutes)
    scheduler.add_job(
        distribution_hold_expiry_job,
        trigger=IntervalTrigger(minutes=15),
        id='distribution_hold_expiry_job',
        name='Finalize distributions after 15-day hold period',
        replace_existing=True
    )

    # Job 7: Impact stats refresh (every 30 minutes)
    scheduler.add_job(
        impact_stats_refresh_job,
        trigger=IntervalTrigger(minutes=30),
        id='impact_stats_refresh_job',
        name='Refresh public impact statistics cache',
        replace_existing=True
    )

    # Job 8: Calendar sync retry with exponential backoff (every 2 minutes)
    scheduler.add_job(
        calendar_retry_job,
        trigger=IntervalTrigger(minutes=2),
        id='calendar_retry_job',
        name='Retry failed calendar sync operations (exponential backoff)',
        replace_existing=True
    )

    # Job 9: Review timeout — auto-resolve stale reviews after 15 days (every 6 hours)
    scheduler.add_job(
        review_timeout_job,
        trigger=IntervalTrigger(hours=6),
        id='review_timeout_job',
        name='Auto-resolve stale review_required records (15-day timeout)',
        replace_existing=True
    )

    # Job 10: Declarative deadline — enforce 48h sheet deadline (every 5 minutes)
    scheduler.add_job(
        declarative_deadline_job,
        trigger=IntervalTrigger(minutes=5),
        id='declarative_deadline_job',
        name='Enforce 48h attendance sheet deadline',
        replace_existing=True
    )

    # Job 11: Dispute escalation — escalate disputes past 7-day deadline (every 15 minutes)
    scheduler.add_job(
        dispute_escalation_job,
        trigger=IntervalTrigger(minutes=15),
        id='dispute_escalation_job',
        name='Escalate disputes past 7-day deadline',
        replace_existing=True
    )

    # Job 12: Contestation timeout — auto-reject stale contestations after 30 days (every 12 hours)
    scheduler.add_job(
        contestation_timeout_job,
        trigger=IntervalTrigger(hours=12),
        id='contestation_timeout_job',
        name='Auto-reject stale contestations (30-day timeout)',
        replace_existing=True
    )

    # Job 13: Ledger reconciliation — verify wallet balances vs ledger (every 6 hours)
    scheduler.add_job(
        ledger_reconciliation_job,
        trigger=IntervalTrigger(hours=6),
        id='ledger_reconciliation_job',
        name='Verify wallet balances match ledger (reconciliation)',
        replace_existing=True
    )

    # Job 14: Stale payout detection — flag payouts stuck in processing > 24h (every 6 hours)
    scheduler.add_job(
        stale_payout_detection_job,
        trigger=IntervalTrigger(hours=6),
        id='stale_payout_detection_job',
        name='Detect stale payouts stuck in processing > 24h',
        replace_existing=True
    )

    # Job 15: Graph subscription renewal — renew Teams webhook subscriptions (every 24 hours)
    scheduler.add_job(
        graph_subscription_renewal_job,
        trigger=IntervalTrigger(hours=24),
        id='graph_subscription_renewal_job',
        name='Renew Microsoft Graph webhook subscriptions',
        replace_existing=True
    )

    # Job 16: Sheet reminder — remind participants with pending sheets < 12h before deadline (every 30 minutes)
    scheduler.add_job(
        sheet_reminder_job,
        trigger=IntervalTrigger(minutes=30),
        id='sheet_reminder_job',
        name='Remind participants with pending attendance sheets',
        replace_existing=True
    )

    scheduler.start()
    logger.info("[SCHEDULER] Background scheduler started (distributed locks enabled)")
    logger.info("[SCHEDULER]    - Cancellation deadline reminders: every 5 minutes")
    logger.info("[SCHEDULER]    - Event reminders (10min/1h/1day): every 2 minutes")
    logger.info("[SCHEDULER]    - Attendance evaluation: every 2 minutes")
    logger.info("[SCHEDULER]    - Auto-fetch video attendance (Zoom/Teams): every 5 minutes")
    logger.info("[SCHEDULER]    - Distribution hold expiry: every 15 minutes")
    logger.info("[SCHEDULER]    - Impact stats refresh: every 30 minutes")
    logger.info("[SCHEDULER]    - Calendar sync retry (backoff): every 2 minutes")
    logger.info("[SCHEDULER]    - Review timeout (15 days): every 6 hours")
    logger.info("[SCHEDULER]    - Contestation timeout (30 days): every 12 hours")
    logger.info("[SCHEDULER]    - Ledger reconciliation: every 6 hours")
    logger.info("[SCHEDULER]    - Declarative deadline: every 5 minutes")
    logger.info("[SCHEDULER]    - Dispute escalation: every 15 minutes")
    logger.info("[SCHEDULER]    - Sheet reminder (<12h): every 30 minutes")
    logger.info("[SCHEDULER]    - Stale payout detection (>24h): every 6 hours")
    logger.info("[SCHEDULER]    - Graph subscription renewal: every 24 hours")


def stop_scheduler():
    """Stop the scheduler"""
    scheduler.shutdown()
    logger.info("[SCHEDULER] Scheduler stopped")
