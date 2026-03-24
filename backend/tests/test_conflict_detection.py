"""Tests for conflict detection logic — _check_overlap and _generate_suggestions."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta, timezone
from routers.appointments import (
    _check_overlap, _generate_suggestions, _parse_dt,
    ConflictItem, BUFFER_MINUTES, MIN_FUTURE_MINUTES,
)


def _make_eng(title, start_iso, duration=60):
    return {"title": title, "start_datetime": start_iso, "duration_minutes": duration}


def _dt(h, m=0, day=25, month=3, year=2026):
    return datetime(year, month, day, h, m, tzinfo=timezone.utc)


# ── _check_overlap tests ──

def test_exact_overlap():
    """Proposed slot is exactly the same as existing → conflict."""
    conflicts, warnings = _check_overlap(
        _dt(14, 0), _dt(15, 0),
        [_make_eng("Meeting", "2026-03-25T14:00:00+00:00", 60)]
    )
    assert len(conflicts) == 1
    assert len(warnings) == 0
    print("PASS: exact overlap → conflict")


def test_partial_overlap_start():
    """Proposed starts during an existing event → conflict."""
    conflicts, _ = _check_overlap(
        _dt(14, 30), _dt(15, 30),
        [_make_eng("Meeting", "2026-03-25T14:00:00+00:00", 60)]
    )
    assert len(conflicts) == 1
    print("PASS: partial overlap at start → conflict")


def test_partial_overlap_end():
    """Proposed ends during an existing event → conflict."""
    conflicts, _ = _check_overlap(
        _dt(13, 30), _dt(14, 30),
        [_make_eng("Meeting", "2026-03-25T14:00:00+00:00", 60)]
    )
    assert len(conflicts) == 1
    print("PASS: partial overlap at end → conflict")


def test_proposed_contains_existing():
    """Proposed fully contains an existing event → conflict."""
    conflicts, _ = _check_overlap(
        _dt(13, 0), _dt(16, 0),
        [_make_eng("Meeting", "2026-03-25T14:00:00+00:00", 60)]
    )
    assert len(conflicts) == 1
    print("PASS: proposed contains existing → conflict")


def test_existing_contains_proposed():
    """Existing event fully contains proposed → conflict."""
    conflicts, _ = _check_overlap(
        _dt(14, 15), _dt(14, 45),
        [_make_eng("Meeting", "2026-03-25T14:00:00+00:00", 60)]
    )
    assert len(conflicts) == 1
    print("PASS: existing contains proposed → conflict")


def test_edge_to_edge_no_conflict():
    """Proposed starts exactly when existing ends → NO conflict (edge-to-edge)."""
    conflicts, warnings = _check_overlap(
        _dt(15, 0), _dt(16, 0),
        [_make_eng("Meeting", "2026-03-25T14:00:00+00:00", 60)]
    )
    assert len(conflicts) == 0
    print("PASS: edge-to-edge → no conflict")


def test_edge_to_edge_warning():
    """Proposed starts right when existing ends → warning (0 min buffer)."""
    _, warnings = _check_overlap(
        _dt(15, 0), _dt(16, 0),
        [_make_eng("Meeting", "2026-03-25T14:00:00+00:00", 60)]
    )
    assert len(warnings) == 1
    print("PASS: edge-to-edge → warning (0 min buffer)")


def test_buffer_warning():
    """Proposed starts 15 min after existing ends → warning (<30 min buffer)."""
    conflicts, warnings = _check_overlap(
        _dt(15, 15), _dt(16, 15),
        [_make_eng("Meeting", "2026-03-25T14:00:00+00:00", 60)]
    )
    assert len(conflicts) == 0
    assert len(warnings) == 1
    print("PASS: 15 min gap → warning")


def test_sufficient_buffer_no_warning():
    """Proposed starts 45 min after existing ends → no warning."""
    conflicts, warnings = _check_overlap(
        _dt(15, 45), _dt(16, 45),
        [_make_eng("Meeting", "2026-03-25T14:00:00+00:00", 60)]
    )
    assert len(conflicts) == 0
    assert len(warnings) == 0
    print("PASS: 45 min gap → available")


def test_multi_conflicts():
    """Proposed overlaps two events → 2 conflicts."""
    conflicts, _ = _check_overlap(
        _dt(14, 0), _dt(17, 0),
        [
            _make_eng("Meeting A", "2026-03-25T14:00:00+00:00", 60),
            _make_eng("Meeting B", "2026-03-25T16:00:00+00:00", 60),
        ]
    )
    assert len(conflicts) == 2
    print("PASS: overlapping 2 events → 2 conflicts")


# ── _generate_suggestions tests ──

def test_suggestions_never_in_past():
    """All suggestions must be in the future (> now + MIN_FUTURE_MINUTES)."""
    now = datetime.now(timezone.utc)
    proposed = now - timedelta(hours=1)  # Proposed is in the past
    engs = [_make_eng("Busy", (now + timedelta(hours=1)).isoformat(), 60)]
    suggestions = _generate_suggestions(proposed, 60, engs, count=5)
    min_allowed = now + timedelta(minutes=MIN_FUTURE_MINUTES)
    for s in suggestions:
        dt = _parse_dt(s.datetime_str)
        assert dt >= min_allowed, f"Suggestion {s.datetime_str} is in the past!"
    print(f"PASS: all {len(suggestions)} suggestions are in the future")


def test_suggestions_respect_duration():
    """No suggestion's [start, start+duration) should overlap with a busy slot."""
    now = datetime.now(timezone.utc)
    busy_start = now + timedelta(hours=2)
    busy_end = busy_start + timedelta(minutes=60)
    engs = [_make_eng("Busy", busy_start.isoformat(), 60)]
    suggestions = _generate_suggestions(busy_start, 60, engs, count=5)
    for s in suggestions:
        dt = _parse_dt(s.datetime_str)
        dt_end = dt + timedelta(minutes=60)
        assert not (dt < busy_end and dt_end > busy_start), \
            f"Suggestion {s.datetime_str} conflicts with busy slot!"
    print(f"PASS: all {len(suggestions)} suggestions respect full duration")


def test_suggestions_not_same_as_proposed():
    """Suggestions should not include the same slot the user proposed."""
    now = datetime.now(timezone.utc)
    proposed = now + timedelta(hours=2)
    proposed = proposed.replace(minute=0, second=0, microsecond=0)
    engs = [_make_eng("Busy", proposed.isoformat(), 60)]
    suggestions = _generate_suggestions(proposed, 60, engs, count=5)
    for s in suggestions:
        dt = _parse_dt(s.datetime_str)
        assert abs((dt - proposed).total_seconds()) >= 60, \
            f"Suggestion {s.datetime_str} is same as proposed!"
    print(f"PASS: no suggestion matches proposed slot")


def test_suggestions_sorted_and_realistic():
    """Suggestions should have valid labels."""
    now = datetime.now(timezone.utc)
    proposed = now + timedelta(hours=3)
    proposed = proposed.replace(minute=0, second=0, microsecond=0)
    engs = [_make_eng("Busy", proposed.isoformat(), 60)]
    suggestions = _generate_suggestions(proposed, 60, engs, count=5)
    valid_labels = {"optimal", "comfortable", "tight"}
    for s in suggestions:
        assert s.label in valid_labels, f"Invalid label: {s.label}"
    print(f"PASS: all labels valid ({[s.label for s in suggestions]})")


if __name__ == "__main__":
    test_exact_overlap()
    test_partial_overlap_start()
    test_partial_overlap_end()
    test_proposed_contains_existing()
    test_existing_contains_proposed()
    test_edge_to_edge_no_conflict()
    test_edge_to_edge_warning()
    test_buffer_warning()
    test_sufficient_buffer_no_warning()
    test_multi_conflicts()
    test_suggestions_never_in_past()
    test_suggestions_respect_duration()
    test_suggestions_not_same_as_proposed()
    test_suggestions_sorted_and_realistic()
    print("\n✅ ALL 14 TESTS PASSED")
