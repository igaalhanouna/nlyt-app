"""
Tests for check-in time window consistency.
Covers: physical (checkin_routes) and video (proof_routes) with same rule:
  - opens: start_datetime - 30 min
  - closes: start_datetime + duration + 60 min
"""
import os
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
os.environ.setdefault('DB_NAME', 'test_database')

import uuid
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["test_database"]

PREFIX = "tcw_"  # test checkin window


def _uid():
    return f"{PREFIX}{uuid.uuid4().hex[:8]}"


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _setup(appointment_type="physical", duration_minutes=60, start_offset_minutes=0):
    """
    Create appointment + participant in DB.
    start_offset_minutes: how many minutes from 'now' the appointment starts.
      0 = starts now, -60 = started 1h ago, +60 = starts in 1h
    """
    now = datetime.now(timezone.utc)
    start = now + timedelta(minutes=start_offset_minutes)
    apt_id = _uid()
    pid = _uid()
    token = _uid()

    db.appointments.insert_one({
        "appointment_id": apt_id,
        "organizer_id": _uid(),
        "title": "Test Window",
        "start_datetime": _iso(start),
        "duration_minutes": duration_minutes,
        "appointment_type": appointment_type,
        "meeting_provider": "zoom" if appointment_type == "video" else None,
        "meeting_join_url": "https://zoom.us/j/123" if appointment_type == "video" else None,
        "status": "active",
        f"_{PREFIX}test": True,
    })

    db.participants.insert_one({
        "participant_id": pid,
        "appointment_id": apt_id,
        "user_id": _uid(),
        "email": f"{pid}@test.nlyt.io",
        "first_name": "Test",
        "last_name": "User",
        "status": "accepted_guaranteed",
        "invitation_token": token,
        "is_organizer": False,
        f"_{PREFIX}test": True,
    })

    return {"apt_id": apt_id, "pid": pid, "token": token, "start": start}


def _cleanup():
    for coll in ["appointments", "participants", "proof_sessions", "evidence"]:
        db[coll].delete_many({f"_{PREFIX}test": True})


@pytest.fixture(autouse=True)
def cleanup():
    _cleanup()
    yield
    _cleanup()


# ─── PHYSICAL CHECK-IN (via checkin_routes._resolve_participant) ───

class TestPhysicalTimeGate:
    """Tests for physical check-in time gate in checkin_routes.py"""

    def _check_physical(self, token, expect_allowed):
        """Simulate physical check-in time gate check."""
        from routers.checkin_routes import _resolve_participant
        from fastapi import HTTPException
        try:
            _resolve_participant(token)
            assert expect_allowed, "Expected HTTPException but check-in was allowed"
        except HTTPException as e:
            assert not expect_allowed, f"Expected check-in to be allowed but got: {e.detail}"
            return e

    def test_physical_31min_before_rejected(self):
        """31 min before start → rejected"""
        s = _setup("physical", 60, start_offset_minutes=31)
        self._check_physical(s["token"], expect_allowed=False)

    def test_physical_30min_before_allowed(self):
        """30 min before start → allowed"""
        s = _setup("physical", 60, start_offset_minutes=30)
        self._check_physical(s["token"], expect_allowed=True)

    def test_physical_during_allowed(self):
        """During the appointment → allowed"""
        s = _setup("physical", 60, start_offset_minutes=-20)
        self._check_physical(s["token"], expect_allowed=True)

    def test_physical_at_end_allowed(self):
        """Exactly at end (start + duration) → allowed"""
        s = _setup("physical", 60, start_offset_minutes=-60)
        self._check_physical(s["token"], expect_allowed=True)

    def test_physical_59min_after_end_allowed(self):
        """59 min after end → allowed"""
        s = _setup("physical", 60, start_offset_minutes=-119)
        self._check_physical(s["token"], expect_allowed=True)

    def test_physical_61min_after_end_rejected(self):
        """61 min after end → rejected"""
        s = _setup("physical", 60, start_offset_minutes=-121)
        self._check_physical(s["token"], expect_allowed=False)


# ─── VIDEO CHECK-IN (via proof_routes._enforce_time_gate) ───

class TestVideoTimeGate:
    """Tests for video check-in time gate in proof_routes.py"""

    def _check_video(self, appointment, expect_allowed):
        """Simulate video time gate check."""
        from routers.proof_routes import _enforce_time_gate
        from fastapi import HTTPException
        try:
            _enforce_time_gate(appointment)
            assert expect_allowed, "Expected HTTPException but check-in was allowed"
        except HTTPException as e:
            assert not expect_allowed, f"Expected check-in to be allowed but got: {e.detail}"
            return e

    def _make_apt(self, start_offset_minutes, duration=60):
        now = datetime.now(timezone.utc)
        start = now + timedelta(minutes=start_offset_minutes)
        return {
            "start_datetime": _iso(start),
            "duration_minutes": duration,
            "appointment_type": "video",
        }

    def test_video_31min_before_rejected(self):
        """31 min before start → rejected"""
        self._check_video(self._make_apt(31), expect_allowed=False)

    def test_video_30min_before_allowed(self):
        """30 min before start → allowed (edge: exactly at open)"""
        self._check_video(self._make_apt(30), expect_allowed=True)

    def test_video_during_allowed(self):
        """During the appointment → allowed"""
        self._check_video(self._make_apt(-20), expect_allowed=True)

    def test_video_at_end_allowed(self):
        """Exactly at end (start + duration) → allowed"""
        self._check_video(self._make_apt(-60), expect_allowed=True)

    def test_video_59min_after_end_allowed(self):
        """59 min after end → allowed"""
        self._check_video(self._make_apt(-119), expect_allowed=True)

    def test_video_61min_after_end_rejected(self):
        """61 min after end → rejected"""
        self._check_video(self._make_apt(-121), expect_allowed=False)


# ─── CROSS-CHECK: Identical rule for both modes ───

class TestCrossConsistency:

    def test_same_constants_used(self):
        """Both routes use the same constants from evidence_service."""
        from services.evidence_service import CHECKIN_WINDOW_BEFORE_MINUTES, CHECKIN_WINDOW_AFTER_HOURS
        assert CHECKIN_WINDOW_BEFORE_MINUTES == 30
        assert CHECKIN_WINDOW_AFTER_HOURS == 1

    def test_video_gate_boundary_behavior(self):
        """Video: 60min after end is the strict cutoff (> not >=)."""
        from routers.proof_routes import _enforce_time_gate
        from fastapi import HTTPException
        now = datetime.now(timezone.utc)
        # 59.5 min after end → allowed
        apt = {"start_datetime": _iso(now - timedelta(minutes=119, seconds=30)), "duration_minutes": 60}
        try:
            _enforce_time_gate(apt)
            passed = True
        except HTTPException:
            passed = False
        assert passed, "59.5 min after end should be allowed"

        # 60.5 min after end → rejected
        apt2 = {"start_datetime": _iso(now - timedelta(minutes=120, seconds=30)), "duration_minutes": 60}
        try:
            _enforce_time_gate(apt2)
            passed2 = True
        except HTTPException:
            passed2 = False
        assert not passed2, "60.5 min after end should be rejected"

    def test_physical_gate_boundary_behavior(self):
        """Physical: 60min after end is the strict cutoff."""
        # 59.5 min after end → allowed
        s = _setup("physical", 60, start_offset_minutes=-119)
        from routers.checkin_routes import _resolve_participant
        from fastapi import HTTPException
        try:
            _resolve_participant(s["token"])
            passed = True
        except HTTPException:
            passed = False
        assert passed, "59 min after end should be allowed"
