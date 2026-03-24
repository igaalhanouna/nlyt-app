"""
Tests for the timezone fix in calendar sync.

ROOT CAUSE: _build_event_data() was passing UTC datetime values with a non-UTC
timezone (e.g., "Europe/Paris"), causing calendar APIs to interpret UTC times
as local times → 1-2h offset.

FIX: Always use timeZone="UTC" in _build_event_data().
"""
import pytest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


# ── Test 1: _build_event_data always returns UTC ─────────────

def test_build_event_data_always_utc():
    """Verify that _build_event_data returns UTC datetimes and timeZone='UTC'."""
    import sys
    sys.path.insert(0, '/app/backend')
    from routers.calendar_routes import _build_event_data

    appointment = {
        "title": "Test Rendez-vous",
        "start_datetime": "2026-03-24T13:00:00.000Z",  # 13:00 UTC = 14:00 Paris (CET)
        "duration_minutes": 60,
        "cancellation_deadline_hours": 24,
        "tolerated_delay_minutes": 15,
        "penalty_amount": 50,
        "penalty_currency": "EUR",
    }

    # Even with a non-UTC calendar_tz, the output must be UTC
    result = _build_event_data(appointment, calendar_tz="Europe/Paris")

    assert result["timeZone"] == "UTC", f"Expected UTC, got {result['timeZone']}"
    assert result["start_datetime"] == "2026-03-24T13:00:00", \
        f"Expected 13:00:00 UTC, got {result['start_datetime']}"
    assert result["end_datetime"] == "2026-03-24T14:00:00", \
        f"Expected 14:00:00 UTC, got {result['end_datetime']}"


def test_build_event_data_utc_with_windows_tz():
    """Ensure Windows timezone is ignored and UTC is used."""
    import sys
    sys.path.insert(0, '/app/backend')
    from routers.calendar_routes import _build_event_data

    appointment = {
        "title": "Test",
        "start_datetime": "2026-06-15T10:00:00Z",  # Summer: CEST = UTC+2, so 10 UTC = 12 Paris
        "duration_minutes": 30,
        "cancellation_deadline_hours": 24,
        "tolerated_delay_minutes": 0,
        "penalty_amount": 0,
        "penalty_currency": "EUR",
    }

    result = _build_event_data(appointment, calendar_tz="Romance Standard Time")

    assert result["timeZone"] == "UTC"
    assert result["start_datetime"] == "2026-06-15T10:00:00"
    assert result["end_datetime"] == "2026-06-15T10:30:00"


def test_build_event_data_no_tz_param():
    """Works correctly even with no calendar_tz argument."""
    import sys
    sys.path.insert(0, '/app/backend')
    from routers.calendar_routes import _build_event_data

    appointment = {
        "title": "No TZ",
        "start_datetime": "2026-01-15T08:00:00Z",
        "duration_minutes": 45,
        "cancellation_deadline_hours": 24,
        "tolerated_delay_minutes": 0,
        "penalty_amount": 0,
        "penalty_currency": "EUR",
    }

    result = _build_event_data(appointment)

    assert result["timeZone"] == "UTC"
    assert result["start_datetime"] == "2026-01-15T08:00:00"
    assert result["end_datetime"] == "2026-01-15T08:45:00"


# ── Test 2: normalize_to_utc correctness ──────────────────────

def test_normalize_to_utc_already_utc():
    """String ending with Z should pass through unchanged."""
    import sys
    sys.path.insert(0, '/app/backend')
    from utils.date_utils import normalize_to_utc

    assert normalize_to_utc("2026-03-24T13:00:00.000Z") == "2026-03-24T13:00:00.000Z"
    assert normalize_to_utc("2026-03-24T13:00:00Z") == "2026-03-24T13:00:00Z"


def test_normalize_to_utc_with_offset():
    """String with +offset should be converted to UTC Z format."""
    import sys
    sys.path.insert(0, '/app/backend')
    from utils.date_utils import normalize_to_utc

    # 14:00 CET (UTC+1) = 13:00 UTC
    result = normalize_to_utc("2026-03-24T14:00:00+01:00")
    assert result == "2026-03-24T13:00:00Z"


def test_normalize_to_utc_naive_string():
    """Naive string (no tz info) should be interpreted as Europe/Paris and converted to UTC."""
    import sys
    sys.path.insert(0, '/app/backend')
    from utils.date_utils import normalize_to_utc

    # Naive 14:00 → interpreted as Paris (CET, UTC+1) → 13:00 UTC
    # (January = CET = UTC+1)
    result = normalize_to_utc("2026-01-15T14:00:00")
    assert result == "2026-01-15T13:00:00Z"


# ── Test 3: localInputToUTC (frontend) correctness ───────────

def test_local_input_to_utc_concept():
    """
    Simulate what JavaScript's new Date("2026-03-24T14:00").toISOString() does
    for a user in Europe/Paris timezone (CET = UTC+1, CEST = UTC+2).
    
    March 24 is still CET (DST starts March 29 in 2026).
    14:00 CET = 13:00 UTC → toISOString() returns "2026-03-24T13:00:00.000Z"
    """
    # Simulate the user's local time
    paris = ZoneInfo("Europe/Paris")
    local_time = datetime(2026, 3, 24, 14, 0, 0, tzinfo=paris)
    utc_time = local_time.astimezone(timezone.utc)
    iso_string = utc_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    assert iso_string == "2026-03-24T13:00:00.000Z"


def test_dst_summer_time():
    """
    In summer (CEST = UTC+2): 14:00 Paris = 12:00 UTC.
    June 15 is in CEST.
    """
    paris = ZoneInfo("Europe/Paris")
    local_time = datetime(2026, 6, 15, 14, 0, 0, tzinfo=paris)
    utc_time = local_time.astimezone(timezone.utc)
    iso_string = utc_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    assert iso_string == "2026-06-15T12:00:00.000Z"


# ── Test 4: End-to-end flow simulation ────────────────────────

def test_end_to_end_winter_time():
    """
    Full flow: User in Paris selects 14:00 on March 24 (CET, UTC+1).
    Expected: event in calendar at 14:00 Paris time.
    
    Previous bug: event appeared at 13:00 Paris (1h early).
    """
    import sys
    sys.path.insert(0, '/app/backend')
    from routers.calendar_routes import _build_event_data

    # Step 1: Frontend sends UTC
    frontend_utc = "2026-03-24T13:00:00.000Z"  # 14:00 CET → 13:00 UTC

    # Step 2: Backend stores as-is
    stored_utc = frontend_utc  # normalize_to_utc passes through Z strings

    # Step 3: Calendar sync builds event data
    appointment = {
        "title": "RDV Hiver",
        "start_datetime": stored_utc,
        "duration_minutes": 60,
        "cancellation_deadline_hours": 24,
        "tolerated_delay_minutes": 0,
        "penalty_amount": 0,
        "penalty_currency": "EUR",
    }
    event = _build_event_data(appointment, "Europe/Paris")

    # Step 4: Verify the event data sent to calendar API
    # With timeZone="UTC", the API will create the event at 13:00 UTC = 14:00 Paris
    assert event["timeZone"] == "UTC"
    assert event["start_datetime"] == "2026-03-24T13:00:00"

    # Verify: a Paris user looking at their calendar sees 14:00
    utc_dt = datetime(2026, 3, 24, 13, 0, 0, tzinfo=timezone.utc)
    paris_dt = utc_dt.astimezone(ZoneInfo("Europe/Paris"))
    assert paris_dt.hour == 14, f"Expected 14:00 Paris, got {paris_dt.hour}:00"


def test_end_to_end_summer_time():
    """
    Full flow: User in Paris selects 14:00 on June 15 (CEST, UTC+2).
    Expected: event in calendar at 14:00 Paris time.
    """
    import sys
    sys.path.insert(0, '/app/backend')
    from routers.calendar_routes import _build_event_data

    frontend_utc = "2026-06-15T12:00:00.000Z"  # 14:00 CEST → 12:00 UTC

    appointment = {
        "title": "RDV Été",
        "start_datetime": frontend_utc,
        "duration_minutes": 60,
        "cancellation_deadline_hours": 24,
        "tolerated_delay_minutes": 0,
        "penalty_amount": 0,
        "penalty_currency": "EUR",
    }
    event = _build_event_data(appointment, "Romance Standard Time")

    assert event["timeZone"] == "UTC"
    assert event["start_datetime"] == "2026-06-15T12:00:00"

    # Verify: Paris user sees 14:00
    utc_dt = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    paris_dt = utc_dt.astimezone(ZoneInfo("Europe/Paris"))
    assert paris_dt.hour == 14, f"Expected 14:00 Paris, got {paris_dt.hour}:00"


# ── Test 5: Outlook adapter timezone mapping ──────────────────

def test_to_windows_timezone_utc():
    """Verify that 'UTC' maps to 'UTC' in the Windows timezone mapping."""
    import sys
    sys.path.insert(0, '/app/backend')
    from adapters.outlook_calendar_adapter import to_windows_timezone

    assert to_windows_timezone("UTC") == "UTC"


def test_to_windows_timezone_iana():
    """Verify IANA → Windows mapping for common timezones."""
    import sys
    sys.path.insert(0, '/app/backend')
    from adapters.outlook_calendar_adapter import to_windows_timezone

    assert to_windows_timezone("Europe/Paris") == "Romance Standard Time"
    assert to_windows_timezone("America/New_York") == "Eastern Standard Time"


# ── Test 6: ICS generation correctness ────────────────────────

def test_ics_generator_utc():
    """Verify ICS generates proper UTC timestamps with Z suffix."""
    import sys
    sys.path.insert(0, '/app/backend')
    from adapters.ics_generator import ICSGenerator

    event_data = {
        "appointment_id": "test-123",
        "title": "Test ICS",
        "start_datetime": "2026-03-24T13:00:00Z",
        "end_datetime": "2026-03-24T14:00:00Z",
    }
    ics_content = ICSGenerator.generate_ics(event_data)

    assert "DTSTART:20260324T130000Z" in ics_content
    assert "DTEND:20260324T140000Z" in ics_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
