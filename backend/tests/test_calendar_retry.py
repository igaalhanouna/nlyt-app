"""
Tests for Calendar Retry Service (Auto-update Calendar V2)

Tests the exponential backoff retry mechanism for failed calendar sync operations.
"""
import pytest
import sys
sys.path.insert(0, '/app/backend')

from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from services.calendar_retry_service import (
    get_next_retry_delay,
    schedule_retry,
    run_calendar_retry_job,
    MAX_RETRIES,
    RETRY_BACKOFF_MINUTES,
)
from utils.date_utils import now_utc


# ═══════════════════════════════════════════════════════════════
# Test backoff schedule
# ═══════════════════════════════════════════════════════════════

class TestBackoffSchedule:

    def test_backoff_delays(self):
        """Verify the backoff schedule: 2, 5, 15, 60 minutes."""
        assert get_next_retry_delay(0) == timedelta(minutes=2)
        assert get_next_retry_delay(1) == timedelta(minutes=5)
        assert get_next_retry_delay(2) == timedelta(minutes=15)
        assert get_next_retry_delay(3) == timedelta(minutes=60)

    def test_max_retries(self):
        """After max retries, delay is zero (no more retries)."""
        assert MAX_RETRIES == 4
        assert get_next_retry_delay(MAX_RETRIES) == timedelta(0)

    def test_backoff_is_exponential(self):
        """Each delay is strictly greater than the previous one."""
        for i in range(1, MAX_RETRIES):
            assert RETRY_BACKOFF_MINUTES[i] > RETRY_BACKOFF_MINUTES[i - 1]


# ═══════════════════════════════════════════════════════════════
# Test schedule_retry
# ═══════════════════════════════════════════════════════════════

class TestScheduleRetry:

    @patch('services.calendar_retry_service.db')
    def test_schedule_first_retry(self, mock_db):
        """First retry should be scheduled in 2 minutes."""
        schedule_retry("log-1", 0, "API error")

        mock_db.calendar_sync_logs.update_one.assert_called_once()
        call_args = mock_db.calendar_sync_logs.update_one.call_args
        update = call_args[0][1]["$set"]

        assert update["sync_status"] == "retry_pending"
        assert update["retry_count"] == 0
        assert update["max_retries_reached"] is False
        assert update["next_retry_at"] is not None
        # Verify the next_retry_at is ~2 minutes from now
        next_retry = datetime.fromisoformat(update["next_retry_at"])
        diff = (next_retry - now_utc()).total_seconds()
        assert 100 < diff < 140  # ~2 minutes

    @patch('services.calendar_retry_service.db')
    def test_schedule_third_retry(self, mock_db):
        """Third retry should be scheduled in 15 minutes."""
        schedule_retry("log-1", 2, "Timeout")

        call_args = mock_db.calendar_sync_logs.update_one.call_args
        update = call_args[0][1]["$set"]

        assert update["sync_status"] == "retry_pending"
        assert update["retry_count"] == 2
        next_retry = datetime.fromisoformat(update["next_retry_at"])
        diff = (next_retry - now_utc()).total_seconds()
        assert 850 < diff < 920  # ~15 minutes

    @patch('services.calendar_retry_service.db')
    def test_max_retries_reached(self, mock_db):
        """After max retries, status should be permanently_failed."""
        schedule_retry("log-1", MAX_RETRIES, "Final error")

        call_args = mock_db.calendar_sync_logs.update_one.call_args
        update = call_args[0][1]["$set"]

        assert update["sync_status"] == "permanently_failed"
        assert update["max_retries_reached"] is True
        assert update["next_retry_at"] is None
        assert "Max retries" in update["sync_error_reason"]


# ═══════════════════════════════════════════════════════════════
# Test run_calendar_retry_job
# ═══════════════════════════════════════════════════════════════

class TestRetryJob:

    @patch('services.calendar_retry_service.db')
    def test_no_pending_retries(self, mock_db):
        """Job should do nothing when there are no pending retries."""
        mock_db.calendar_sync_logs.find.return_value = []
        run_calendar_retry_job()
        # Should not attempt any sync
        mock_db.appointments.find_one.assert_not_called()

    @patch('services.calendar_retry_service.db')
    def test_skips_cancelled_appointments(self, mock_db):
        """Retry should skip cancelled appointments."""
        mock_db.calendar_sync_logs.find.return_value = [{
            "log_id": "log-1",
            "appointment_id": "apt-1",
            "provider": "google",
            "connection_id": "conn-1",
            "external_event_id": None,
            "retry_count": 0,
            "sync_source": "auto",
        }]
        mock_db.appointments.find_one.return_value = {
            "appointment_id": "apt-1",
            "status": "cancelled",
        }

        run_calendar_retry_job()

        # Should update to cancelled status
        mock_db.calendar_sync_logs.update_one.assert_called_once()
        call_args = mock_db.calendar_sync_logs.update_one.call_args
        assert call_args[0][1]["$set"]["sync_status"] == "cancelled"

    @patch('services.calendar_retry_service.db')
    def test_skips_missing_appointments(self, mock_db):
        """Retry should mark as permanently_failed if appointment not found."""
        mock_db.calendar_sync_logs.find.return_value = [{
            "log_id": "log-1",
            "appointment_id": "apt-missing",
            "provider": "google",
            "connection_id": "conn-1",
            "external_event_id": None,
            "retry_count": 0,
            "sync_source": "auto",
        }]
        mock_db.appointments.find_one.return_value = None

        run_calendar_retry_job()

        call_args = mock_db.calendar_sync_logs.update_one.call_args
        assert call_args[0][1]["$set"]["sync_status"] == "permanently_failed"


# ═══════════════════════════════════════════════════════════════
# Test integration with perform_auto_sync
# ═══════════════════════════════════════════════════════════════

class TestAutoSyncRetryIntegration:

    def test_perform_auto_sync_structure(self):
        """Verify perform_auto_sync function exists and is callable."""
        from routers.calendar_routes import perform_auto_sync
        assert callable(perform_auto_sync)

    def test_perform_auto_update_structure(self):
        """Verify perform_auto_update function exists and is callable."""
        from routers.calendar_routes import perform_auto_update
        assert callable(perform_auto_update)


# ═══════════════════════════════════════════════════════════════
# Test sync status endpoint includes retry fields
# ═══════════════════════════════════════════════════════════════

class TestSyncStatusRetryFields:

    def test_sync_status_retry_fields_in_code(self):
        """Verify the sync status endpoint handles retry_pending and permanently_failed."""
        import inspect
        from routers.calendar_routes import get_sync_status
        source = inspect.getsource(get_sync_status)
        assert "retry_pending" in source
        assert "permanently_failed" in source
        assert "retry_count" in source
        assert "max_retries_reached" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
