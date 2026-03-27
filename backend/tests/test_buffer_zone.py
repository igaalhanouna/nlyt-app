"""
Tests for Buffer Zone (2 minutes) in evaluate_participant().
10 boundary tests covering all delay/tolerance/proof combinations.
"""
import os
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
os.environ.setdefault('DB_NAME', 'test_database')

import uuid
import pytest
from unittest.mock import patch
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["test_database"]

BUFFER = 2  # Must match BUFFER_ZONE_MINUTES in attendance_service.py


def _clean():
    for coll in ["attendance_records", "appointments", "participants",
                 "evidence_items", "proof_sessions"]:
        db[coll].delete_many({"_test_buffer": True})


@pytest.fixture(autouse=True)
def cleanup():
    _clean()
    yield
    _clean()


def _evaluate(delay_minutes, tolerated_delay=0, has_admissible_proof=True):
    """
    Call evaluate_participant with controlled inputs.
    Mocks _has_admissible_proof and _aggregate_evidence to isolate the 3-way split.
    """
    from services.attendance_service import evaluate_participant

    apt_id = f"buf-apt-{uuid.uuid4().hex[:8]}"
    pid = f"buf-pid-{uuid.uuid4().hex[:8]}"

    appointment = {
        "appointment_id": apt_id,
        "appointment_type": "physical",
        "tolerated_delay_minutes": tolerated_delay,
        "_test_buffer": True,
    }
    participant = {
        "participant_id": pid,
        "appointment_id": apt_id,
        "user_id": f"uid-{uuid.uuid4().hex[:8]}",
        "status": "accepted_guaranteed",
        "_test_buffer": True,
    }

    aggregation = {
        "evidence_count": 1,
        "delay_minutes": delay_minutes,
        "timing": "late" if delay_minutes > 0 else "on_time",
        "strength": "strong" if has_admissible_proof else "none",
        "proof_level": 1 if has_admissible_proof else 4,
    }

    with patch("services.attendance_service._has_admissible_proof", return_value=has_admissible_proof), \
         patch("services.evidence_service.aggregate_evidence", return_value=aggregation):
        return evaluate_participant(participant, appointment)


# ═══════════════════════════════════════════════════════════════════
# 10 Boundary Tests
# ═══════════════════════════════════════════════════════════════════

class TestBufferZone:

    def test_1_negative_delay_on_time(self):
        """delay=-5, tolerated=0, proof=yes → on_time (unchanged by buffer)"""
        r = _evaluate(delay_minutes=-5, tolerated_delay=0)
        assert r["outcome"] == "on_time"
        assert r["delay_minutes"] == -5
        assert r["effective_delay_minutes"] == 0
        assert r["buffer_zone_applied"] is True

    def test_2_zero_delay_on_time(self):
        """delay=0, tolerated=0, proof=yes → on_time (unchanged by buffer)"""
        r = _evaluate(delay_minutes=0, tolerated_delay=0)
        assert r["outcome"] == "on_time"
        assert r["delay_minutes"] == 0
        assert r["effective_delay_minutes"] == 0
        assert r["buffer_zone_applied"] is False

    def test_3_one_min_absorbed(self):
        """delay=1, tolerated=0, proof=yes → on_time (buffer absorbs)"""
        r = _evaluate(delay_minutes=1, tolerated_delay=0)
        assert r["outcome"] == "on_time"
        assert r["delay_minutes"] == 1
        assert r["effective_delay_minutes"] == 0
        assert r["buffer_zone_applied"] is True

    def test_4_exact_buffer_absorbed(self):
        """delay=2, tolerated=0, proof=yes → on_time (buffer absorbs exactly)"""
        r = _evaluate(delay_minutes=2, tolerated_delay=0)
        assert r["outcome"] == "on_time"
        assert r["delay_minutes"] == 2
        assert r["effective_delay_minutes"] == 0
        assert r["buffer_zone_applied"] is True

    def test_5_beyond_buffer_no_tolerance(self):
        """delay=2.5, tolerated=0, proof=yes → late_penalized (buffer partial, no tolerance)"""
        r = _evaluate(delay_minutes=2.5, tolerated_delay=0)
        assert r["outcome"] == "late_penalized"
        assert r["delay_minutes"] == 2.5
        assert r["effective_delay_minutes"] == 0.5
        assert r["buffer_zone_applied"] is True

    def test_6_within_tolerance_after_buffer(self):
        """delay=3, tolerated=5, proof=yes → late (effective=1, within tolerance)"""
        r = _evaluate(delay_minutes=3, tolerated_delay=5)
        assert r["outcome"] == "late"
        assert r["delay_minutes"] == 3
        assert r["effective_delay_minutes"] == 1
        assert r["buffer_zone_applied"] is True

    def test_7_exact_tolerance_boundary(self):
        """delay=7, tolerated=5, proof=yes → late (effective=5, exactly at tolerance)"""
        r = _evaluate(delay_minutes=7, tolerated_delay=5)
        assert r["outcome"] == "late"
        assert r["delay_minutes"] == 7
        assert r["effective_delay_minutes"] == 5

    def test_8_beyond_tolerance(self):
        """delay=7.1, tolerated=5, proof=yes → late_penalized (effective=5.1, over tolerance)"""
        r = _evaluate(delay_minutes=7.1, tolerated_delay=5)
        assert r["outcome"] == "late_penalized"
        assert r["delay_minutes"] == 7.1
        assert abs(r["effective_delay_minutes"] - 5.1) < 0.01

    def test_9_no_proof_one_min_delay(self):
        """delay=1, tolerated=0, proof=NO → manual_review (buffer irrelevant)"""
        r = _evaluate(delay_minutes=1, tolerated_delay=0, has_admissible_proof=False)
        assert r["outcome"] == "manual_review"
        assert r["review_required"] is True
        # Buffer fields should NOT be present (exit before 3-way split)
        assert "effective_delay_minutes" not in r

    def test_10_no_proof_zero_delay(self):
        """delay=0, tolerated=0, proof=NO → manual_review (buffer irrelevant)"""
        r = _evaluate(delay_minutes=0, tolerated_delay=0, has_admissible_proof=False)
        assert r["outcome"] == "manual_review"
        assert r["review_required"] is True
        assert "effective_delay_minutes" not in r
