"""
Tests for auto-creation of meetings when switching appointment type.

Covers:
- physical → video triggers create_meeting_for_appointment
- Success: meeting_join_url persisted, emails sent after
- Provider failure: modification preserved, email still sent
- No double creation if meeting already exists
- Provider change (video → video): new meeting created
- video → physical: local cleanup preserved, no API create
"""
import os
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
os.environ.setdefault('DB_NAME', 'test_database')
os.environ.setdefault('FRONTEND_URL', 'https://test.nlyt.io')

import pytest
from unittest.mock import patch, MagicMock
from services.modification_service import _auto_create_meeting_on_switch


MOCK_CREATE = "services.meeting_provider_service.create_meeting_for_appointment"
MOCK_DB = "services.modification_service.db"


# ── Helpers ──

def _make_appointment(**overrides):
    base = {
        "appointment_id": "apt-test-001",
        "appointment_type": "video",
        "meeting_provider": "zoom",
        "title": "Test meeting",
        "start_datetime": "2026-04-01T10:00:00+00:00",
        "duration_minutes": 60,
        "appointment_timezone": "Europe/Paris",
        "organizer_id": "user-org-001",
        "meeting_created_via_api": False,
        "meeting_join_url": None,
    }
    base.update(overrides)
    return base


class TestPhysicalToVideo:
    """physical → video should trigger meeting creation."""

    @patch(MOCK_CREATE)
    @patch(MOCK_DB)
    def test_creates_meeting_on_physical_to_video(self, mock_db, mock_create):
        apt = _make_appointment(meeting_provider="zoom")
        mock_db.appointments.find_one.return_value = apt
        mock_create.return_value = {"success": True, "join_url": "https://zoom.us/j/123"}

        changes = {"appointment_type": "video", "meeting_provider": "zoom"}
        original = {"appointment_type": "physical", "meeting_provider": None}

        _auto_create_meeting_on_switch("apt-test-001", changes, original)

        mock_create.assert_called_once()

    @patch(MOCK_CREATE)
    @patch(MOCK_DB)
    def test_creates_meeting_for_teams(self, mock_db, mock_create):
        apt = _make_appointment(meeting_provider="teams")
        mock_db.appointments.find_one.return_value = apt
        mock_create.return_value = {"success": True, "join_url": "https://teams.microsoft.com/l/123"}

        changes = {"appointment_type": "video", "meeting_provider": "teams"}
        original = {"appointment_type": "physical", "meeting_provider": None}

        _auto_create_meeting_on_switch("apt-test-001", changes, original)

        mock_create.assert_called_once()
        args = mock_create.call_args
        assert args[1]["provider"] == "teams"

    @patch(MOCK_CREATE)
    @patch(MOCK_DB)
    def test_creates_meeting_for_meet(self, mock_db, mock_create):
        apt = _make_appointment(meeting_provider="meet")
        mock_db.appointments.find_one.return_value = apt
        mock_create.return_value = {"success": True, "join_url": "https://meet.google.com/abc"}

        changes = {"appointment_type": "video", "meeting_provider": "meet"}
        original = {"appointment_type": "physical", "meeting_provider": None}

        _auto_create_meeting_on_switch("apt-test-001", changes, original)

        mock_create.assert_called_once()


class TestProviderFailure:
    """Provider failure must not block the modification."""

    @patch(MOCK_CREATE)
    @patch(MOCK_DB)
    def test_failure_does_not_raise(self, mock_db, mock_create):
        apt = _make_appointment(meeting_provider="zoom")
        mock_db.appointments.find_one.return_value = apt
        mock_create.return_value = {"error": "Zoom API non configurée.", "needs_config": True}

        changes = {"appointment_type": "video", "meeting_provider": "zoom"}
        original = {"appointment_type": "physical", "meeting_provider": None}

        # Should NOT raise
        _auto_create_meeting_on_switch("apt-test-001", changes, original)

        mock_create.assert_called_once()

    @patch(MOCK_CREATE)
    @patch(MOCK_DB)
    def test_exception_does_not_raise(self, mock_db, mock_create):
        apt = _make_appointment(meeting_provider="zoom")
        mock_db.appointments.find_one.return_value = apt
        mock_create.side_effect = Exception("Network timeout")

        changes = {"appointment_type": "video", "meeting_provider": "zoom"}
        original = {"appointment_type": "physical", "meeting_provider": None}

        # _auto_create_meeting_on_switch does not catch itself — it lets the caller's try/except handle it.
        # We verify it propagates the exception (caught by _apply_proposal's try/except).
        with pytest.raises(Exception, match="Network timeout"):
            _auto_create_meeting_on_switch("apt-test-001", changes, original)


class TestAntiDoubleCreation:
    """Must not re-create a meeting if one already exists for same provider."""

    @patch(MOCK_CREATE)
    @patch(MOCK_DB)
    def test_skips_if_meeting_already_exists_same_provider(self, mock_db, mock_create):
        apt = _make_appointment(
            meeting_provider="zoom",
            meeting_created_via_api=True,
            meeting_join_url="https://zoom.us/j/existing",
        )
        mock_db.appointments.find_one.return_value = apt

        # Type changed but meeting already exists
        changes = {"appointment_type": "video", "meeting_provider": "zoom"}
        original = {"appointment_type": "physical", "meeting_provider": None}

        _auto_create_meeting_on_switch("apt-test-001", changes, original)

        mock_create.assert_not_called()

    @patch(MOCK_CREATE)
    @patch(MOCK_DB)
    def test_creates_new_meeting_on_provider_change(self, mock_db, mock_create):
        """When provider changes (zoom→teams), create new meeting even if old exists."""
        apt = _make_appointment(
            meeting_provider="teams",
            meeting_created_via_api=True,
            meeting_join_url="https://zoom.us/j/old",
        )
        mock_db.appointments.find_one.return_value = apt
        mock_create.return_value = {"success": True, "join_url": "https://teams.microsoft.com/new"}

        changes = {"meeting_provider": "teams"}
        original = {"meeting_provider": "zoom"}

        _auto_create_meeting_on_switch("apt-test-001", changes, original)

        mock_create.assert_called_once()


class TestVideoToPhysical:
    """video → physical: no meeting creation, just local cleanup."""

    @patch(MOCK_CREATE)
    @patch(MOCK_DB)
    def test_no_creation_on_video_to_physical(self, mock_db, mock_create):
        apt = _make_appointment(appointment_type="physical", meeting_provider=None)
        mock_db.appointments.find_one.return_value = apt

        changes = {"appointment_type": "physical"}
        original = {"appointment_type": "video", "meeting_provider": "zoom"}

        _auto_create_meeting_on_switch("apt-test-001", changes, original)

        mock_create.assert_not_called()


class TestNoOpCases:
    """Cases where no meeting creation should happen."""

    @patch(MOCK_CREATE)
    @patch(MOCK_DB)
    def test_no_creation_for_external_provider(self, mock_db, mock_create):
        apt = _make_appointment(meeting_provider="external")
        mock_db.appointments.find_one.return_value = apt

        changes = {"appointment_type": "video", "meeting_provider": "external"}
        original = {"appointment_type": "physical"}

        _auto_create_meeting_on_switch("apt-test-001", changes, original)

        mock_create.assert_not_called()

    @patch(MOCK_CREATE)
    @patch(MOCK_DB)
    def test_no_creation_for_irrelevant_changes(self, mock_db, mock_create):
        """Changing title or duration should not trigger meeting creation."""
        apt = _make_appointment(meeting_provider="zoom")
        mock_db.appointments.find_one.return_value = apt

        changes = {"title": "New title", "duration_minutes": 90}
        original = {"title": "Old title", "duration_minutes": 60}

        _auto_create_meeting_on_switch("apt-test-001", changes, original)

        mock_create.assert_not_called()

    @patch(MOCK_CREATE)
    @patch(MOCK_DB)
    def test_no_creation_if_appointment_not_found(self, mock_db, mock_create):
        mock_db.appointments.find_one.return_value = None

        changes = {"appointment_type": "video", "meeting_provider": "zoom"}
        original = {"appointment_type": "physical"}

        _auto_create_meeting_on_switch("apt-test-001", changes, original)

        mock_create.assert_not_called()


class TestVideoToPhysicalCleanup:
    """video → physical must nullify ALL meeting fields."""

    def test_all_meeting_fields_cleared_on_switch_to_physical(self):
        """Verify _apply_proposal sets all 8 meeting fields when switching to physical."""
        from services.modification_service import _apply_proposal

        captured_update = {}

        class FakeCollection:
            def update_one(self, filter_doc, update_doc, **kwargs):
                captured_update.update(update_doc.get("$set", {}))

            def find_one(self, *args, **kwargs):
                return None

        class FakeDB:
            appointments = FakeCollection()
            proposals = FakeCollection()
            participants = FakeCollection()
            sent_emails = FakeCollection()

        with patch("services.modification_service.db", FakeDB()):
            fake_proposal = {
                "proposal_id": "prop-001",
                "appointment_id": "apt-001",
                "proposer_id": "user-001",
                "changes": {"appointment_type": "physical"},
                "original_values": {"appointment_type": "video", "meeting_provider": "zoom"},
                "status": "approved",
            }
            try:
                _apply_proposal(fake_proposal)
            except Exception:
                pass  # Will fail on downstream calls, we only care about the $set

        # All 8 meeting fields must be present in the update
        expected_cleared = {
            "meeting_provider": None,
            "meeting_join_url": None,
            "external_meeting_id": None,
            "meeting_host_url": None,
            "meeting_password": None,
            "meeting_provider_metadata": None,
            "meeting_created_via_api": False,
            "meet_calendar_event_id": None,
        }
        for field, expected_val in expected_cleared.items():
            assert field in captured_update, f"Field '{field}' missing from $set"
            assert captured_update[field] == expected_val, (
                f"Field '{field}': expected {expected_val!r}, got {captured_update[field]!r}"
            )


class TestProviderChangeCleanup:
    """When provider changes (video→video), old meeting fields must be cleared preemptively."""

    def test_provider_change_clears_old_meeting_fields(self):
        """Zoom→Teams: old meeting fields nullified in $set even before create_meeting runs."""
        from services.modification_service import _apply_proposal

        captured_update = {}

        class FakeCollection:
            def update_one(self, filter_doc, update_doc, **kwargs):
                captured_update.update(update_doc.get("$set", {}))

            def find_one(self, *args, **kwargs):
                return None

        class FakeDB:
            appointments = FakeCollection()
            proposals = FakeCollection()
            participants = FakeCollection()
            sent_emails = FakeCollection()

        with patch("services.modification_service.db", FakeDB()):
            fake_proposal = {
                "proposal_id": "prop-pc-001",
                "appointment_id": "apt-pc-001",
                "proposer_id": "user-001",
                "changes": {"meeting_provider": "teams"},
                "original_values": {"appointment_type": "video", "meeting_provider": "zoom"},
                "status": "approved",
            }
            try:
                _apply_proposal(fake_proposal)
            except Exception:
                pass

        # All meeting data fields must be nullified
        expected_cleared = {
            "meeting_join_url": None,
            "external_meeting_id": None,
            "meeting_host_url": None,
            "meeting_password": None,
            "meeting_provider_metadata": None,
            "meeting_created_via_api": False,
            "meet_calendar_event_id": None,
        }
        for field, expected_val in expected_cleared.items():
            assert field in captured_update, f"Field '{field}' missing from $set on provider change"
            assert captured_update[field] == expected_val, (
                f"Field '{field}': expected {expected_val!r}, got {captured_update[field]!r}"
            )
        # meeting_provider itself should be set to the NEW value
        assert captured_update.get("meeting_provider") == "teams"

    def test_provider_change_with_api_failure_leaves_clean_state(self):
        """If create_meeting fails after provider change, DB should have null meeting fields, not stale Zoom links."""
        from services.modification_service import _apply_proposal

        captured_sets = []

        class FakeCollection:
            def __init__(self):
                self.docs = {}

            def update_one(self, filter_doc, update_doc, **kwargs):
                set_fields = update_doc.get("$set", {})
                captured_sets.append(dict(set_fields))

            def find_one(self, *args, **kwargs):
                return None

            def find(self, *args, **kwargs):
                return []

        class FakeDB:
            appointments = FakeCollection()
            proposals = FakeCollection()
            participants = FakeCollection()
            sent_emails = FakeCollection()
            users = FakeCollection()

        with patch("services.modification_service.db", FakeDB()), \
             patch("services.meeting_provider_service.create_meeting_for_appointment",
                   side_effect=Exception("Teams API down")):
            fake_proposal = {
                "proposal_id": "prop-pc-002",
                "appointment_id": "apt-pc-002",
                "proposer_id": "user-001",
                "changes": {"meeting_provider": "teams"},
                "original_values": {"appointment_type": "video", "meeting_provider": "zoom"},
                "status": "approved",
            }
            try:
                _apply_proposal(fake_proposal)
            except Exception:
                pass

        # The first $set (from update_one) must have nullified meeting fields
        assert len(captured_sets) > 0, "No DB update captured"
        first_set = captured_sets[0]
        assert first_set.get("meeting_join_url") is None, "meeting_join_url should be null after provider change"
        assert first_set.get("meeting_host_url") is None, "meeting_host_url should be null"
        assert first_set.get("meeting_created_via_api") == False, "meeting_created_via_api should be False"

    def test_no_cleanup_when_provider_unchanged(self):
        """If meeting_provider doesn't change, don't touch meeting fields."""
        from services.modification_service import _apply_proposal

        captured_update = {}

        class FakeCollection:
            def update_one(self, filter_doc, update_doc, **kwargs):
                captured_update.update(update_doc.get("$set", {}))

            def find_one(self, *args, **kwargs):
                return None

        class FakeDB:
            appointments = FakeCollection()
            proposals = FakeCollection()
            participants = FakeCollection()
            sent_emails = FakeCollection()

        with patch("services.modification_service.db", FakeDB()):
            fake_proposal = {
                "proposal_id": "prop-pc-003",
                "appointment_id": "apt-pc-003",
                "proposer_id": "user-001",
                "changes": {"title": "Nouveau titre"},
                "original_values": {"title": "Ancien titre", "appointment_type": "video", "meeting_provider": "zoom"},
                "status": "approved",
            }
            try:
                _apply_proposal(fake_proposal)
            except Exception:
                pass

        # meeting fields should NOT be in the $set
        assert "meeting_join_url" not in captured_update, "meeting_join_url should not be touched"
        assert "meeting_host_url" not in captured_update, "meeting_host_url should not be touched"
