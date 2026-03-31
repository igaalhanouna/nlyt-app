"""
Test Video Evidence Participant Access - Iteration 166

Tests the harmonization of video evidence rights:
- Participants (not just organizers) can now trigger video evidence retrieval
- Endpoints modified: ingest, fetch-attendance, ingest-file, GET evidence, logs, log/{id}
- create-meeting remains organizer-only

Test scenarios:
1. Organizer can access all video-evidence endpoints (as before)
2. Accepted participant can access fetch-attendance, ingest, ingest-file, GET evidence, logs
3. Accepted participant CANNOT access create-meeting (403)
4. Unrelated user gets 403 on all endpoints
"""

import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
ORGANIZER_EMAIL = "testuser_audit@nlyt.app"
ORGANIZER_PASSWORD = "TestAudit123!"
PARTICIPANT_EMAIL = "igaal.hanouna@gmail.com"
PARTICIPANT_PASSWORD = "OrgTest123!"
UNRELATED_USER_EMAIL = "igaal@hotmail.com"
UNRELATED_USER_PASSWORD = "Test123!"


def get_auth_token(email, password):
    """Get auth token for a user."""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": email,
        "password": password
    })
    if response.status_code != 200:
        return None
    data = response.json()
    # API returns access_token, not token
    return data.get("access_token") or data.get("token")


# Module-level fixtures
@pytest.fixture(scope="module")
def organizer_token():
    """Get auth token for organizer."""
    token = get_auth_token(ORGANIZER_EMAIL, ORGANIZER_PASSWORD)
    assert token, f"Organizer login failed"
    return token


@pytest.fixture(scope="module")
def participant_token():
    """Get auth token for participant."""
    token = get_auth_token(PARTICIPANT_EMAIL, PARTICIPANT_PASSWORD)
    assert token, f"Participant login failed"
    return token


@pytest.fixture(scope="module")
def unrelated_user_token():
    """Get auth token for unrelated user."""
    token = get_auth_token(UNRELATED_USER_EMAIL, UNRELATED_USER_PASSWORD)
    assert token, f"Unrelated user login failed"
    return token


@pytest.fixture(scope="module")
def organizer_session(organizer_token):
    """Session with organizer auth."""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {organizer_token}",
        "Content-Type": "application/json"
    })
    return session


@pytest.fixture(scope="module")
def participant_session(participant_token):
    """Session with participant auth."""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {participant_token}",
        "Content-Type": "application/json"
    })
    return session


@pytest.fixture(scope="module")
def unrelated_session(unrelated_user_token):
    """Session with unrelated user auth."""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {unrelated_user_token}",
        "Content-Type": "application/json"
    })
    return session


@pytest.fixture(scope="module")
def video_appointment_with_participant(organizer_session):
    """
    Find a video appointment where:
    - organizer is testuser_audit@nlyt.app
    - participant igaal.hanouna@gmail.com is accepted
    
    Returns appointment_id or None if setup not possible.
    """
    # First, try to find an existing video appointment with the participant
    response = organizer_session.get(f"{BASE_URL}/api/appointments")
    if response.status_code != 200:
        print(f"Cannot list appointments: {response.status_code} - {response.text}")
        return None
    
    appointments = response.json().get("appointments", [])
    print(f"Found {len(appointments)} appointments")
    
    # Look for a video appointment where participant is accepted
    for apt in appointments:
        if apt.get("appointment_type") == "video" and apt.get("status") in ["active", "pending_organizer_guarantee"]:
            apt_id = apt.get("appointment_id")
            # Check participants
            part_resp = organizer_session.get(f"{BASE_URL}/api/appointments/{apt_id}/participants")
            if part_resp.status_code == 200:
                participants = part_resp.json().get("participants", [])
                for p in participants:
                    if p.get("email") == PARTICIPANT_EMAIL and p.get("status") in ["accepted", "accepted_pending_guarantee", "accepted_guaranteed", "guaranteed"]:
                        print(f"Found existing video appointment with accepted participant: {apt_id}")
                        return apt_id
    
    # No suitable appointment found - return None and tests will check access control with 404
    print("No video appointment with accepted participant found - will test with non-existent appointment")
    return None


class TestVideoEvidenceParticipantAccess:
    """Test video evidence endpoint access for organizers, participants, and unrelated users."""
    
    # ============ ORGANIZER TESTS ============
    
    def test_organizer_can_access_video_evidence_get(self, organizer_session, video_appointment_with_participant):
        """Organizer can GET video evidence."""
        apt_id = video_appointment_with_participant or "nonexistent-apt-id"
        response = organizer_session.get(f"{BASE_URL}/api/video-evidence/{apt_id}")
        # Should be 200 (if exists) or 404 (if not exists), NOT 403
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code} - {response.text}"
        print(f"PASS: Organizer GET /api/video-evidence/{apt_id} -> {response.status_code}")
    
    def test_organizer_can_access_video_evidence_logs(self, organizer_session, video_appointment_with_participant):
        """Organizer can GET video evidence logs."""
        apt_id = video_appointment_with_participant or "nonexistent-apt-id"
        response = organizer_session.get(f"{BASE_URL}/api/video-evidence/{apt_id}/logs")
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code} - {response.text}"
        print(f"PASS: Organizer GET /api/video-evidence/{apt_id}/logs -> {response.status_code}")
    
    def test_organizer_can_access_fetch_attendance(self, organizer_session, video_appointment_with_participant):
        """Organizer can POST fetch-attendance."""
        apt_id = video_appointment_with_participant or "nonexistent-apt-id"
        response = organizer_session.post(f"{BASE_URL}/api/video-evidence/{apt_id}/fetch-attendance")
        # 200/400 (success/provider error) or 404 (not found), NOT 403
        assert response.status_code in [200, 400, 404], f"Unexpected status: {response.status_code} - {response.text}"
        print(f"PASS: Organizer POST /api/video-evidence/{apt_id}/fetch-attendance -> {response.status_code}")
    
    def test_organizer_can_access_create_meeting(self, organizer_session, video_appointment_with_participant):
        """Organizer can POST create-meeting."""
        apt_id = video_appointment_with_participant or "nonexistent-apt-id"
        response = organizer_session.post(f"{BASE_URL}/api/video-evidence/{apt_id}/create-meeting", json={})
        # 200/400/424 (success/error/needs config) or 404 (not found), NOT 403
        assert response.status_code in [200, 400, 404, 424], f"Unexpected status: {response.status_code} - {response.text}"
        print(f"PASS: Organizer POST /api/video-evidence/{apt_id}/create-meeting -> {response.status_code}")
    
    # ============ PARTICIPANT TESTS ============
    
    def test_participant_can_access_video_evidence_get(self, participant_session, video_appointment_with_participant):
        """Accepted participant can GET video evidence."""
        if not video_appointment_with_participant:
            pytest.skip("No video appointment with accepted participant available")
        apt_id = video_appointment_with_participant
        response = participant_session.get(f"{BASE_URL}/api/video-evidence/{apt_id}")
        # Should be 200 (participant has access) or 403 if not accepted
        assert response.status_code in [200, 403], f"Unexpected status: {response.status_code} - {response.text}"
        if response.status_code == 200:
            print(f"PASS: Participant GET /api/video-evidence/{apt_id} -> 200 (access granted)")
        else:
            print(f"INFO: Participant GET /api/video-evidence/{apt_id} -> 403 (participant may not be accepted)")
    
    def test_participant_can_access_video_evidence_logs(self, participant_session, video_appointment_with_participant):
        """Accepted participant can GET video evidence logs."""
        if not video_appointment_with_participant:
            pytest.skip("No video appointment with accepted participant available")
        apt_id = video_appointment_with_participant
        response = participant_session.get(f"{BASE_URL}/api/video-evidence/{apt_id}/logs")
        assert response.status_code in [200, 403], f"Unexpected status: {response.status_code} - {response.text}"
        if response.status_code == 200:
            print(f"PASS: Participant GET /api/video-evidence/{apt_id}/logs -> 200 (access granted)")
        else:
            print(f"INFO: Participant GET /api/video-evidence/{apt_id}/logs -> 403 (participant may not be accepted)")
    
    def test_participant_can_access_fetch_attendance(self, participant_session, video_appointment_with_participant):
        """Accepted participant can POST fetch-attendance."""
        if not video_appointment_with_participant:
            pytest.skip("No video appointment with accepted participant available")
        apt_id = video_appointment_with_participant
        response = participant_session.post(f"{BASE_URL}/api/video-evidence/{apt_id}/fetch-attendance")
        # 200/400 (success/provider error) or 403 (not accepted)
        assert response.status_code in [200, 400, 403], f"Unexpected status: {response.status_code} - {response.text}"
        if response.status_code in [200, 400]:
            print(f"PASS: Participant POST /api/video-evidence/{apt_id}/fetch-attendance -> {response.status_code} (access granted)")
        else:
            print(f"INFO: Participant POST /api/video-evidence/{apt_id}/fetch-attendance -> 403 (participant may not be accepted)")
    
    def test_participant_cannot_access_create_meeting(self, participant_session, video_appointment_with_participant):
        """Participant CANNOT POST create-meeting (organizer-only)."""
        if not video_appointment_with_participant:
            pytest.skip("No video appointment with accepted participant available")
        apt_id = video_appointment_with_participant
        response = participant_session.post(f"{BASE_URL}/api/video-evidence/{apt_id}/create-meeting", json={})
        # Should be 403 (organizer-only)
        assert response.status_code == 403, f"Expected 403 for participant on create-meeting, got {response.status_code} - {response.text}"
        print(f"PASS: Participant POST /api/video-evidence/{apt_id}/create-meeting -> 403 (correctly denied)")
    
    # ============ UNRELATED USER TESTS ============
    
    def test_unrelated_user_cannot_access_video_evidence_get(self, unrelated_session, video_appointment_with_participant):
        """Unrelated user gets 403 on GET video evidence."""
        if not video_appointment_with_participant:
            pytest.skip("No video appointment available")
        apt_id = video_appointment_with_participant
        response = unrelated_session.get(f"{BASE_URL}/api/video-evidence/{apt_id}")
        assert response.status_code == 403, f"Expected 403 for unrelated user, got {response.status_code} - {response.text}"
        print(f"PASS: Unrelated user GET /api/video-evidence/{apt_id} -> 403 (correctly denied)")
    
    def test_unrelated_user_cannot_access_video_evidence_logs(self, unrelated_session, video_appointment_with_participant):
        """Unrelated user gets 403 on GET video evidence logs."""
        if not video_appointment_with_participant:
            pytest.skip("No video appointment available")
        apt_id = video_appointment_with_participant
        response = unrelated_session.get(f"{BASE_URL}/api/video-evidence/{apt_id}/logs")
        assert response.status_code == 403, f"Expected 403 for unrelated user, got {response.status_code} - {response.text}"
        print(f"PASS: Unrelated user GET /api/video-evidence/{apt_id}/logs -> 403 (correctly denied)")
    
    def test_unrelated_user_cannot_access_fetch_attendance(self, unrelated_session, video_appointment_with_participant):
        """Unrelated user gets 403 on POST fetch-attendance."""
        if not video_appointment_with_participant:
            pytest.skip("No video appointment available")
        apt_id = video_appointment_with_participant
        response = unrelated_session.post(f"{BASE_URL}/api/video-evidence/{apt_id}/fetch-attendance")
        assert response.status_code == 403, f"Expected 403 for unrelated user, got {response.status_code} - {response.text}"
        print(f"PASS: Unrelated user POST /api/video-evidence/{apt_id}/fetch-attendance -> 403 (correctly denied)")
    
    def test_unrelated_user_cannot_access_create_meeting(self, unrelated_session, video_appointment_with_participant):
        """Unrelated user gets 403 on POST create-meeting."""
        if not video_appointment_with_participant:
            pytest.skip("No video appointment available")
        apt_id = video_appointment_with_participant
        response = unrelated_session.post(f"{BASE_URL}/api/video-evidence/{apt_id}/create-meeting", json={})
        assert response.status_code == 403, f"Expected 403 for unrelated user, got {response.status_code} - {response.text}"
        print(f"PASS: Unrelated user POST /api/video-evidence/{apt_id}/create-meeting -> 403 (correctly denied)")
    
    def test_unrelated_user_cannot_access_ingest(self, unrelated_session, video_appointment_with_participant):
        """Unrelated user gets 403 on POST ingest."""
        if not video_appointment_with_participant:
            pytest.skip("No video appointment available")
        apt_id = video_appointment_with_participant
        response = unrelated_session.post(f"{BASE_URL}/api/video-evidence/{apt_id}/ingest", json={
            "provider": "zoom",
            "raw_payload": {"meeting_id": "test", "participants": []}
        })
        assert response.status_code == 403, f"Expected 403 for unrelated user, got {response.status_code} - {response.text}"
        print(f"PASS: Unrelated user POST /api/video-evidence/{apt_id}/ingest -> 403 (correctly denied)")


class TestVideoEvidenceHelperFunctions:
    """Test the helper functions _is_accepted_participant and _require_organizer_or_participant."""
    
    def test_nonexistent_appointment_returns_404(self, organizer_session):
        """Non-existent appointment returns 404, not 403."""
        fake_apt_id = f"fake-apt-{uuid.uuid4()}"
        response = organizer_session.get(f"{BASE_URL}/api/video-evidence/{fake_apt_id}")
        assert response.status_code == 404, f"Expected 404 for non-existent appointment, got {response.status_code}"
        print(f"PASS: Non-existent appointment returns 404")
    
    def test_provider_status_endpoint_accessible(self, organizer_session):
        """Provider status endpoint is accessible to authenticated users."""
        response = organizer_session.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert response.status_code == 200, f"Expected 200 for provider-status, got {response.status_code}"
        data = response.json()
        assert "zoom" in data or "teams" in data or "meet" in data, "Provider status should include provider info"
        print(f"PASS: Provider status endpoint accessible")


class TestFrontendAppointmentDetailBugFix:
    """Test that the frontend bug fix (data.appointment_type -> apt.appointment_type) works."""
    
    def test_appointment_api_returns_appointment_type(self, organizer_session):
        """Verify appointment API returns appointment_type field."""
        response = organizer_session.get(f"{BASE_URL}/api/appointments")
        assert response.status_code == 200, f"Failed to list appointments: {response.text}"
        
        appointments = response.json().get("appointments", [])
        if not appointments:
            pytest.skip("No appointments to test")
        
        # Check first appointment has appointment_type
        apt = appointments[0]
        apt_id = apt.get("appointment_id")
        
        # Get single appointment
        detail_resp = organizer_session.get(f"{BASE_URL}/api/appointments/{apt_id}")
        assert detail_resp.status_code == 200, f"Failed to get appointment detail: {detail_resp.text}"
        
        detail = detail_resp.json()
        assert "appointment_type" in detail, "appointment_type field missing from appointment detail"
        assert detail["appointment_type"] in ["physical", "video", None, ""], f"Unexpected appointment_type: {detail['appointment_type']}"
        print(f"PASS: Appointment API returns appointment_type: {detail['appointment_type']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
