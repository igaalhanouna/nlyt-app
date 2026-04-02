"""
Distributed Lock — MongoDB Advisory Lock for Scheduler Jobs

Prevents concurrent execution of the same scheduler job across multiple
pods/instances in a Kubernetes environment.

Also provides execution tracking (start/end/duration/errors) for the
scheduler health endpoint.

Mechanism:
  - Collection `scheduler_locks` with unique index on `job_id`
  - Atomic `find_one_and_update` with upsert for lock acquisition
  - TTL-based automatic expiration if the holding pod dies
  - Only the instance that acquired the lock can release it
  - Execution history tracked in `scheduler_job_history`
"""
import os
import uuid
import time
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from database import db

logger = logging.getLogger(__name__)

INSTANCE_ID = f"{os.environ.get('HOSTNAME', 'local')}-{os.getpid()}-{uuid.uuid4().hex[:6]}"


def ensure_lock_indexes():
    """Create required indexes. Idempotent."""
    db.scheduler_locks.create_index("job_id", unique=True)
    db.scheduler_locks.create_index("expires_at", expireAfterSeconds=0)
    db.scheduler_job_history.create_index("job_id", unique=True)
    logger.info(f"[LOCK] Indexes ensured. Instance ID: {INSTANCE_ID}")


# ═══════════════════════════════════════════════════════════════════
# Lock acquisition / release
# ═══════════════════════════════════════════════════════════════════

def acquire_lock(job_id: str, ttl_seconds: int = 300) -> bool:
    """
    Atomically acquire a distributed lock for `job_id`.
    Returns True if acquired, False if another instance holds it.
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ttl_seconds)

    try:
        result = db.scheduler_locks.find_one_and_update(
            {
                "job_id": job_id,
                "expires_at": {"$lte": now},
            },
            {
                "$set": {
                    "locked_by": INSTANCE_ID,
                    "locked_at": now,
                    "expires_at": expires_at,
                }
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        acquired = result is not None and result.get("locked_by") == INSTANCE_ID
    except DuplicateKeyError:
        acquired = False

    if acquired:
        logger.info(f"[LOCK] Acquired: {job_id} (ttl={ttl_seconds}s)")
    else:
        logger.debug(f"[LOCK] Skipped: {job_id} (locked by another instance)")

    return acquired


def release_lock(job_id: str) -> bool:
    """Release a lock. Only the owning instance can release it."""
    result = db.scheduler_locks.delete_one({
        "job_id": job_id,
        "locked_by": INSTANCE_ID,
    })
    released = result.deleted_count > 0
    if released:
        logger.debug(f"[LOCK] Released: {job_id}")
    return released


# ═══════════════════════════════════════════════════════════════════
# Execution tracking
# ═══════════════════════════════════════════════════════════════════

def _record_start(job_id: str):
    now = datetime.now(timezone.utc)
    db.scheduler_job_history.update_one(
        {"job_id": job_id},
        {
            "$set": {
                "current_status": "running",
                "current_run_started_at": now,
                "running_on": INSTANCE_ID,
            },
            "$inc": {"total_runs": 1},
        },
        upsert=True,
    )


def _record_end(job_id: str, success: bool, error_msg: str = None, duration_ms: int = 0):
    now = datetime.now(timezone.utc)
    update_set = {
        "current_status": "ok" if success else "error",
        "last_completed_at": now,
        "last_duration_ms": duration_ms,
        "current_run_started_at": None,
        "running_on": None,
    }
    update_inc = {}

    if success:
        update_set["last_error"] = None
        update_inc["successful_runs"] = 1
    else:
        update_set["last_error"] = str(error_msg)[:500]
        update_inc["failed_runs"] = 1

    update = {"$set": update_set}
    if update_inc:
        update["$inc"] = update_inc

    db.scheduler_job_history.update_one({"job_id": job_id}, update, upsert=True)


# ═══════════════════════════════════════════════════════════════════
# High-level runner (lock + tracking in one call)
# ═══════════════════════════════════════════════════════════════════

async def run_locked_job(job_id: str, ttl_seconds: int, fn):
    """
    Execute `fn` under distributed lock with execution tracking.

    - Acquires lock (skips silently if another instance holds it)
    - Records start time, end time, duration, success/failure
    - Releases lock in finally block
    - Handles both sync and async callables
    """
    if not acquire_lock(job_id, ttl_seconds):
        return

    _record_start(job_id)
    start = time.monotonic()
    try:
        result = fn()
        if asyncio.iscoroutine(result):
            await result
        duration_ms = int((time.monotonic() - start) * 1000)
        _record_end(job_id, True, duration_ms=duration_ms)
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        _record_end(job_id, False, str(e), duration_ms=duration_ms)
        logger.error(f"[SCHEDULER] {job_id} failed: {e}")
    finally:
        release_lock(job_id)
