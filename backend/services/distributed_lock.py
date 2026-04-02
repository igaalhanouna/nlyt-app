"""
Distributed Lock — MongoDB Advisory Lock for Scheduler Jobs

Prevents concurrent execution of the same scheduler job across multiple
pods/instances in a Kubernetes environment.

Mechanism:
  - Collection `scheduler_locks` with a unique index on `job_id`
  - Atomic `find_one_and_update` with upsert for lock acquisition
  - TTL-based automatic expiration if the holding pod dies
  - Only the instance that acquired the lock can release it

Security guarantees:
  - No double execution: only one pod runs a given job at a time
  - No deadlock: locks expire automatically after TTL
  - No starvation: next scheduled interval will re-acquire
"""
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from pymongo import ReturnDocument, ASCENDING
from pymongo.errors import DuplicateKeyError

from database import db

logger = logging.getLogger(__name__)

# Unique identifier for this pod/process — survives job runs but not restarts
INSTANCE_ID = f"{os.environ.get('HOSTNAME', 'local')}-{os.getpid()}-{uuid.uuid4().hex[:6]}"


def ensure_lock_indexes():
    """Create required indexes for scheduler_locks. Idempotent."""
    db.scheduler_locks.create_index("job_id", unique=True)
    db.scheduler_locks.create_index("expires_at", expireAfterSeconds=0)
    logger.info(f"[LOCK] Indexes ensured. Instance ID: {INSTANCE_ID}")


def acquire_lock(job_id: str, ttl_seconds: int = 300) -> bool:
    """
    Try to atomically acquire a distributed lock for `job_id`.

    Returns True if acquired, False if another instance holds it.

    Logic:
      1. If no lock document exists → upsert creates one → acquired
      2. If lock exists but expired (expires_at <= now) → update → acquired
      3. If lock exists and active → filter misses → upsert raises
         DuplicateKeyError (unique index on job_id) → not acquired
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
        logger.info(f"[LOCK] Acquired: {job_id} (ttl={ttl_seconds}s, instance={INSTANCE_ID})")
    else:
        logger.debug(f"[LOCK] Skipped: {job_id} (locked by another instance)")

    return acquired


def release_lock(job_id: str) -> bool:
    """
    Release a lock. Only the instance that acquired it can release it.
    Returns True if released, False if it was already expired or held by another.
    """
    result = db.scheduler_locks.delete_one({
        "job_id": job_id,
        "locked_by": INSTANCE_ID,
    })
    released = result.deleted_count > 0
    if released:
        logger.debug(f"[LOCK] Released: {job_id}")
    return released
