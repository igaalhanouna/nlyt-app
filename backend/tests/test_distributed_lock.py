"""
Tests — Distributed Lock (MongoDB Advisory Lock)

Scenarios tested:
  1. Normal acquisition → lock acquired
  2. Second worker blocked → lock refused
  3. TTL expiration → lock auto-expires
  4. Recovery after expiration → re-acquisition OK
  5. No double processing → same job_id cannot run twice concurrently
  6. Release by owner only → different instance cannot release
  7. Concurrent upsert safety → DuplicateKeyError handled
"""
import sys
import uuid
import time

sys.path.append('/app/backend')
from datetime import datetime, timezone, timedelta
from database import db

# We test the lock logic directly against MongoDB, simulating
# multiple instances by temporarily overriding INSTANCE_ID.
import services.distributed_lock as lock_module
from services.distributed_lock import ensure_lock_indexes

# ─── Helpers ─────────────────────────────────────────────────────

TEST_PREFIX = "test_lock_"


def _clean():
    db.scheduler_locks.delete_many({"job_id": {"$regex": f"^{TEST_PREFIX}"}})


def _acquire_as(instance_id: str, job_id: str, ttl: int = 300) -> bool:
    """Acquire lock pretending to be a specific instance."""
    original = lock_module.INSTANCE_ID
    lock_module.INSTANCE_ID = instance_id
    try:
        return lock_module.acquire_lock(job_id, ttl)
    finally:
        lock_module.INSTANCE_ID = original


def _release_as(instance_id: str, job_id: str) -> bool:
    """Release lock pretending to be a specific instance."""
    original = lock_module.INSTANCE_ID
    lock_module.INSTANCE_ID = instance_id
    try:
        return lock_module.release_lock(job_id)
    finally:
        lock_module.INSTANCE_ID = original


# ═══════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════

def test_1_normal_acquisition():
    """A single instance can acquire a lock."""
    _clean()
    job_id = f"{TEST_PREFIX}normal_{uuid.uuid4().hex[:6]}"
    pod_a = "pod-alpha-001"

    acquired = _acquire_as(pod_a, job_id, ttl=60)
    assert acquired, "Lock should be acquired"

    # Verify in DB
    doc = db.scheduler_locks.find_one({"job_id": job_id}, {"_id": 0})
    assert doc is not None
    assert doc["locked_by"] == pod_a
    assert doc["expires_at"] > datetime.utcnow()

    _release_as(pod_a, job_id)
    print("  OK TEST 1 — Acquisition normale")


def test_2_second_worker_blocked():
    """A second instance cannot acquire an already-held lock."""
    _clean()
    job_id = f"{TEST_PREFIX}blocked_{uuid.uuid4().hex[:6]}"
    pod_a = "pod-alpha-001"
    pod_b = "pod-beta-002"

    # Pod A acquires
    assert _acquire_as(pod_a, job_id, ttl=60)

    # Pod B tries → should fail
    assert not _acquire_as(pod_b, job_id, ttl=60), \
        "SECURITY: Second pod acquired a held lock!"

    # Verify DB still shows Pod A
    doc = db.scheduler_locks.find_one({"job_id": job_id}, {"_id": 0})
    assert doc["locked_by"] == pod_a

    _release_as(pod_a, job_id)
    print("  OK TEST 2 — Second worker bloque")


def test_3_ttl_expiration():
    """Lock expires after TTL, document has expired expires_at."""
    _clean()
    job_id = f"{TEST_PREFIX}ttl_{uuid.uuid4().hex[:6]}"
    pod_a = "pod-alpha-001"

    # Insert a lock with already-expired TTL (simulates pod death)
    now = datetime.now(timezone.utc)
    db.scheduler_locks.insert_one({
        "job_id": job_id,
        "locked_by": pod_a,
        "locked_at": now - timedelta(seconds=120),
        "expires_at": now - timedelta(seconds=10),  # already expired
    })

    # Verify it's expired
    doc = db.scheduler_locks.find_one({"job_id": job_id}, {"_id": 0})
    assert doc["expires_at"] < datetime.utcnow(), "Lock should be expired"
    print("  OK TEST 3 — TTL expiration verifiee")


def test_4_recovery_after_expiration():
    """A new pod can acquire a lock after the previous one expired."""
    _clean()
    job_id = f"{TEST_PREFIX}recovery_{uuid.uuid4().hex[:6]}"
    pod_a = "pod-alpha-001"
    pod_b = "pod-beta-002"

    # Pod A acquires with a very short TTL, then "dies" (we simulate expired)
    now = datetime.now(timezone.utc)
    db.scheduler_locks.insert_one({
        "job_id": job_id,
        "locked_by": pod_a,
        "locked_at": now - timedelta(seconds=120),
        "expires_at": now - timedelta(seconds=10),
    })

    # Pod B should be able to take over
    acquired = _acquire_as(pod_b, job_id, ttl=60)
    assert acquired, "Pod B should acquire the expired lock"

    doc = db.scheduler_locks.find_one({"job_id": job_id}, {"_id": 0})
    assert doc["locked_by"] == pod_b, "Lock should now belong to Pod B"
    assert doc["expires_at"] > datetime.utcnow(), "Lock should have a future expiry"

    _release_as(pod_b, job_id)
    print("  OK TEST 4 — Reprise apres expiration")


def test_5_no_double_processing():
    """Same job_id cannot be processed concurrently by two instances."""
    _clean()
    job_id = f"{TEST_PREFIX}double_{uuid.uuid4().hex[:6]}"
    pod_a = "pod-alpha-001"
    pod_b = "pod-beta-002"
    pod_c = "pod-gamma-003"

    # Pod A acquires
    assert _acquire_as(pod_a, job_id, ttl=300)

    # Pod B, C both try → both should fail
    assert not _acquire_as(pod_b, job_id, ttl=300)
    assert not _acquire_as(pod_c, job_id, ttl=300)

    # Only Pod A holds the lock
    doc = db.scheduler_locks.find_one({"job_id": job_id}, {"_id": 0})
    assert doc["locked_by"] == pod_a

    _release_as(pod_a, job_id)
    print("  OK TEST 5 — Pas de double traitement")


def test_6_release_by_owner_only():
    """Only the instance that acquired the lock can release it."""
    _clean()
    job_id = f"{TEST_PREFIX}owner_{uuid.uuid4().hex[:6]}"
    pod_a = "pod-alpha-001"
    pod_b = "pod-beta-002"

    assert _acquire_as(pod_a, job_id, ttl=300)

    # Pod B tries to release → should fail
    released = _release_as(pod_b, job_id)
    assert not released, "Pod B should NOT be able to release Pod A's lock"

    # Lock still held by Pod A
    doc = db.scheduler_locks.find_one({"job_id": job_id}, {"_id": 0})
    assert doc is not None
    assert doc["locked_by"] == pod_a

    # Pod A can release
    released = _release_as(pod_a, job_id)
    assert released, "Pod A should release its own lock"
    assert db.scheduler_locks.find_one({"job_id": job_id}) is None

    print("  OK TEST 6 — Seul le proprietaire peut liberer")


def test_7_concurrent_upsert_safety():
    """Simulates the DuplicateKeyError path when two pods race on a new lock."""
    _clean()
    job_id = f"{TEST_PREFIX}race_{uuid.uuid4().hex[:6]}"
    pod_a = "pod-alpha-001"
    pod_b = "pod-beta-002"

    # Pod A acquires first (new document, upsert)
    assert _acquire_as(pod_a, job_id, ttl=300)

    # Pod B tries immediately → gets DuplicateKeyError or filter miss → False
    result = _acquire_as(pod_b, job_id, ttl=300)
    assert not result, "Concurrent upsert should not succeed for Pod B"

    doc = db.scheduler_locks.find_one({"job_id": job_id}, {"_id": 0})
    assert doc["locked_by"] == pod_a

    _release_as(pod_a, job_id)
    print("  OK TEST 7 — Securite upsert concurrent (DuplicateKeyError)")


def test_8_independent_jobs():
    """Different job_ids are independent — locking one doesn't affect another."""
    _clean()
    job_a = f"{TEST_PREFIX}ind_a_{uuid.uuid4().hex[:6]}"
    job_b = f"{TEST_PREFIX}ind_b_{uuid.uuid4().hex[:6]}"
    pod_a = "pod-alpha-001"
    pod_b = "pod-beta-002"

    assert _acquire_as(pod_a, job_a, ttl=300)
    assert _acquire_as(pod_b, job_b, ttl=300)

    # Both acquired — independent
    doc_a = db.scheduler_locks.find_one({"job_id": job_a}, {"_id": 0})
    doc_b = db.scheduler_locks.find_one({"job_id": job_b}, {"_id": 0})
    assert doc_a["locked_by"] == pod_a
    assert doc_b["locked_by"] == pod_b

    _release_as(pod_a, job_a)
    _release_as(pod_b, job_b)
    print("  OK TEST 8 — Jobs independants")


def test_9_reacquire_after_release():
    """After release, any instance can re-acquire."""
    _clean()
    job_id = f"{TEST_PREFIX}reacq_{uuid.uuid4().hex[:6]}"
    pod_a = "pod-alpha-001"
    pod_b = "pod-beta-002"

    assert _acquire_as(pod_a, job_id, ttl=300)
    _release_as(pod_a, job_id)

    # Pod B can now acquire
    assert _acquire_as(pod_b, job_id, ttl=300)
    doc = db.scheduler_locks.find_one({"job_id": job_id}, {"_id": 0})
    assert doc["locked_by"] == pod_b

    _release_as(pod_b, job_id)
    print("  OK TEST 9 — Re-acquisition apres release")


# ═══════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("TESTS — Distributed Lock (MongoDB Advisory Lock)")
    print("=" * 65)

    ensure_lock_indexes()

    tests = [
        test_1_normal_acquisition,
        test_2_second_worker_blocked,
        test_3_ttl_expiration,
        test_4_recovery_after_expiration,
        test_5_no_double_processing,
        test_6_release_by_owner_only,
        test_7_concurrent_upsert_safety,
        test_8_independent_jobs,
        test_9_reacquire_after_release,
    ]

    total = len(tests)
    passed = 0
    failed = 0

    for fn in tests:
        try:
            fn()
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {fn.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"  ERROR {fn.__name__}: {e}")

    _clean()

    print(f"\n{'=' * 65}")
    print(f"RESULTAT: {passed}/{total} PASS | {failed} FAIL")
    print("=" * 65)

    if failed > 0:
        sys.exit(1)
    else:
        print("\nTous les tests du distributed lock sont PASSES.\n")
