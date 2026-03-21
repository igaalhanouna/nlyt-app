"""
Background Scheduler for NLYT
Runs periodic tasks like reminder emails

Two types of reminders:
1. Cancellation deadline reminder (reminder_service.py) - 1h before deadline
2. Event reminders (event_reminder_service.py) - 10min/1h/1day before RDV
"""
import asyncio
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def cancellation_deadline_reminder_job():
    """Job to send reminders 1h before cancellation deadline"""
    try:
        from services.reminder_service import run_reminder_job
        await run_reminder_job()
    except Exception as e:
        logger.error(f"[SCHEDULER] Cancellation deadline reminder job failed: {str(e)}")


async def event_reminder_job():
    """Job to send event reminders (10min/1h/1day before RDV)"""
    try:
        from services.event_reminder_service import run_event_reminder_job
        await run_event_reminder_job()
    except Exception as e:
        logger.error(f"[SCHEDULER] Event reminder job failed: {str(e)}")


async def attendance_evaluation_job():
    """Job to evaluate attendance for ended appointments"""
    try:
        from services.attendance_service import run_attendance_evaluation_job
        run_attendance_evaluation_job()
    except Exception as e:
        logger.error(f"[SCHEDULER] Attendance evaluation job failed: {str(e)}")


def start_scheduler():
    """Start the background scheduler"""
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
    
    # Job 3: Attendance evaluation (every 10 minutes)
    scheduler.add_job(
        attendance_evaluation_job,
        trigger=IntervalTrigger(minutes=10),
        id='attendance_evaluation_job',
        name='Evaluate attendance for ended appointments',
        replace_existing=True
    )

    scheduler.start()
    logger.info("[SCHEDULER] Background scheduler started")
    logger.info("[SCHEDULER]    - Cancellation deadline reminders: every 5 minutes")
    logger.info("[SCHEDULER]    - Event reminders (10min/1h/1day): every 2 minutes")
    logger.info("[SCHEDULER]    - Attendance evaluation: every 10 minutes")


def stop_scheduler():
    """Stop the scheduler"""
    scheduler.shutdown()
    logger.info("[SCHEDULER] Scheduler stopped")
