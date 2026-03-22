"""
Tests for meeting_provider validation rules:
- Physical appointments: meeting_provider must be None/ignored
- Video appointments: meeting_provider must be a valid enum value
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from models.schemas import AppointmentCreate, MeetingProvider
from pydantic import ValidationError


# --- PHYSICAL APPOINTMENTS ---

def test_physical_without_meeting_provider():
    """Physical RDV without meeting_provider → OK"""
    apt = AppointmentCreate(
        workspace_id="ws-1", title="Physique", appointment_type="physical",
        location="12 rue de Paris", start_datetime="2026-06-01T10:00:00",
        duration_minutes=30, penalty_amount=20, affected_compensation_percent=80,
        charity_percent=0, participants=[{"first_name": "A", "last_name": "B", "email": "a@b.com"}]
    )
    assert apt.meeting_provider is None


def test_physical_with_empty_string_meeting_provider():
    """Physical RDV with meeting_provider='' → converted to None, OK"""
    apt = AppointmentCreate(
        workspace_id="ws-1", title="Physique", appointment_type="physical",
        location="12 rue de Paris", meeting_provider="",
        start_datetime="2026-06-01T10:00:00", duration_minutes=30,
        penalty_amount=20, affected_compensation_percent=80, charity_percent=0,
        participants=[{"first_name": "A", "last_name": "B", "email": "a@b.com"}]
    )
    assert apt.meeting_provider is None


def test_physical_with_valid_provider_is_nullified():
    """Physical RDV with meeting_provider='zoom' → forced to None"""
    apt = AppointmentCreate(
        workspace_id="ws-1", title="Physique", appointment_type="physical",
        location="12 rue de Paris", meeting_provider="zoom",
        start_datetime="2026-06-01T10:00:00", duration_minutes=30,
        penalty_amount=20, affected_compensation_percent=80, charity_percent=0,
        participants=[{"first_name": "A", "last_name": "B", "email": "a@b.com"}]
    )
    assert apt.meeting_provider is None


# --- VIDEO APPOINTMENTS ---

def test_video_with_valid_provider():
    """Video RDV with valid provider → OK"""
    for provider in ['zoom', 'teams', 'meet', 'external']:
        apt = AppointmentCreate(
            workspace_id="ws-1", title="Visio", appointment_type="video",
            meeting_provider=provider, start_datetime="2026-06-01T10:00:00",
            duration_minutes=30, penalty_amount=20, affected_compensation_percent=80,
            charity_percent=0, participants=[{"first_name": "A", "last_name": "B", "email": "a@b.com"}]
        )
        assert apt.meeting_provider == MeetingProvider(provider)


def test_video_without_provider_fails():
    """Video RDV without meeting_provider → ValidationError"""
    with pytest.raises(ValidationError) as exc_info:
        AppointmentCreate(
            workspace_id="ws-1", title="Visio", appointment_type="video",
            start_datetime="2026-06-01T10:00:00", duration_minutes=30,
            penalty_amount=20, affected_compensation_percent=80, charity_percent=0,
            participants=[{"first_name": "A", "last_name": "B", "email": "a@b.com"}]
        )
    assert "meeting_provider" in str(exc_info.value).lower()


def test_video_with_empty_string_provider_fails():
    """Video RDV with meeting_provider='' → empty→None→fail"""
    with pytest.raises(ValidationError) as exc_info:
        AppointmentCreate(
            workspace_id="ws-1", title="Visio", appointment_type="video",
            meeting_provider="", start_datetime="2026-06-01T10:00:00",
            duration_minutes=30, penalty_amount=20, affected_compensation_percent=80,
            charity_percent=0, participants=[{"first_name": "A", "last_name": "B", "email": "a@b.com"}]
        )
    assert "meeting_provider" in str(exc_info.value).lower()


def test_video_with_invalid_provider_fails():
    """Video RDV with meeting_provider='skype' → ValidationError"""
    with pytest.raises(ValidationError) as exc_info:
        AppointmentCreate(
            workspace_id="ws-1", title="Visio", appointment_type="video",
            meeting_provider="skype", start_datetime="2026-06-01T10:00:00",
            duration_minutes=30, penalty_amount=20, affected_compensation_percent=80,
            charity_percent=0, participants=[{"first_name": "A", "last_name": "B", "email": "a@b.com"}]
        )
    assert "meeting_provider" in str(exc_info.value).lower() or "input should be" in str(exc_info.value).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
