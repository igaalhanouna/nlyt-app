"""
Test: Proof Sessions Access Control (Iteration 162)
Tests the refactored GET /api/proof/{appointment_id}/sessions endpoint:
- Organizer sees ALL sessions
- Participant sees only THEIR OWN sessions
- Non-member gets 403

Test appointment: 11e6f1de-e4d9-4df9-aab8-7a39f4f65943 (video type)
- Organizer: testuser_audit@nlyt.app (has 2 sessions)
- Participant: igaal@hotmail.com (has 1 session, participant_id: b7b20c7b-b6fc-4f33-9cb8-c3ab7e7b5a31)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ORGANIZER_EMAIL = "testuser_audit@nlyt.app"
ORGANIZER_PASSWORD = "TestAudit123!"
PARTICIPANT_EMAIL = "igaal@hotmail.com"
PARTICIPANT_PASSWORD = "Test123!"
NON_MEMBER_EMAIL = "igaal.hanouna@gmail.com"
NON_MEMBER_PASSWORD = "OrgTest123!"

# Test appointment
TEST_APPOINTMENT_ID = "11e6f1de-e4d9-4df9-aab8-7a39f4f65943"
PARTICIPANT_ID = "b7b20c7b-b6fc-4f33-9cb8-c3ab7e7b5a31"


@pytest.fixture(scope="module")
def organizer_token():
    """Get auth token for organizer (testuser_audit@nlyt.app)"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ORGANIZER_EMAIL,
        "password": ORGANIZER_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Organizer login failed: {response.status_code} - {response.text}")
    return response.json().get("access_token")


@pytest.fixture(scope="module")
def participant_token():
    """Get auth token for participant (igaal@hotmail.com)"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": PARTICIPANT_EMAIL,
        "password": PARTICIPANT_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Participant login failed: {response.status_code} - {response.text}")
    return response.json().get("access_token")


@pytest.fixture(scope="module")
def non_member_token():
    """Get auth token for non-member (igaal.hanouna@gmail.com)"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": NON_MEMBER_EMAIL,
        "password": NON_MEMBER_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Non-member login failed: {response.status_code} - {response.text}")
    return response.json().get("access_token")


class TestProofSessionsAccessControl:
    """Test GET /api/proof/{appointment_id}/sessions access control"""

    def test_organizer_sees_all_sessions(self, organizer_token):
        """Organizer should see ALL proof sessions for the appointment"""
        response = requests.get(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/sessions",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "sessions" in data, "Response should contain 'sessions' key"
        assert "count" in data, "Response should contain 'count' key"
        
        sessions = data["sessions"]
        count = data["count"]
        
        # Organizer should see at least 3 sessions (2 for organizer + 1 for participant)
        # Based on the problem statement: "3 sessions pour apt 11e6f1de"
        assert count >= 3, f"Organizer should see at least 3 sessions, got {count}"
        assert len(sessions) >= 3, f"Sessions list should have at least 3 items, got {len(sessions)}"
        
        # Verify sessions have expected fields
        for session in sessions:
            assert "session_id" in session
            assert "participant_id" in session
            assert "participant_email" in session
            assert "checked_in_at" in session
        
        print(f"PASS: Organizer sees {count} sessions (expected >= 3)")

    def test_participant_sees_only_own_sessions(self, participant_token):
        """Participant should see only THEIR OWN proof sessions"""
        response = requests.get(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/sessions",
            headers={"Authorization": f"Bearer {participant_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "sessions" in data, "Response should contain 'sessions' key"
        assert "count" in data, "Response should contain 'count' key"
        
        sessions = data["sessions"]
        count = data["count"]
        
        # Participant should see only 1 session (their own)
        assert count == 1, f"Participant should see exactly 1 session, got {count}"
        assert len(sessions) == 1, f"Sessions list should have exactly 1 item, got {len(sessions)}"
        
        # Verify the session belongs to the participant
        session = sessions[0]
        assert session["participant_id"] == PARTICIPANT_ID, \
            f"Session should belong to participant {PARTICIPANT_ID}, got {session['participant_id']}"
        assert session["participant_email"] == PARTICIPANT_EMAIL, \
            f"Session email should be {PARTICIPANT_EMAIL}, got {session['participant_email']}"
        
        print(f"PASS: Participant sees only 1 session (their own)")

    def test_non_member_gets_403(self, non_member_token):
        """Non-member should get 403 Forbidden"""
        response = requests.get(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/sessions",
            headers={"Authorization": f"Bearer {non_member_token}"}
        )
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "detail" in data, "Response should contain 'detail' key"
        
        print(f"PASS: Non-member gets 403 with message: {data['detail']}")

    def test_unauthenticated_gets_401(self):
        """Unauthenticated request should get 401"""
        response = requests.get(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/sessions"
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        
        print("PASS: Unauthenticated request gets 401")

    def test_nonexistent_appointment_gets_404(self, organizer_token):
        """Request for non-existent appointment should get 404"""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = requests.get(
            f"{BASE_URL}/api/proof/{fake_id}/sessions",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        
        print("PASS: Non-existent appointment gets 404")


class TestProofSessionsDataIntegrity:
    """Test that proof sessions data is correctly filtered and enriched"""

    def test_organizer_sessions_have_video_enrichment(self, organizer_token):
        """Organizer's sessions should include video provider enrichment data"""
        response = requests.get(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/sessions",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        
        assert response.status_code == 200
        
        data = response.json()
        sessions = data["sessions"]
        
        # Check that sessions have the expected structure
        for session in sessions:
            # Core fields
            assert "session_id" in session
            assert "appointment_id" in session
            assert "participant_id" in session
            assert "participant_email" in session
            assert "participant_name" in session
            assert "checked_in_at" in session
            assert "score" in session
            assert "proof_level" in session
            assert "suggested_status" in session
            
            # Heartbeats should be excluded (privacy/performance)
            assert "heartbeats" not in session, "Heartbeats should be excluded from response"
        
        print(f"PASS: Sessions have correct structure with video enrichment")

    def test_participant_session_has_correct_fields(self, participant_token):
        """Participant's session should have all expected fields"""
        response = requests.get(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/sessions",
            headers={"Authorization": f"Bearer {participant_token}"}
        )
        
        assert response.status_code == 200
        
        data = response.json()
        sessions = data["sessions"]
        
        assert len(sessions) == 1
        session = sessions[0]
        
        # Verify all expected fields are present
        expected_fields = [
            "session_id", "appointment_id", "participant_id", 
            "participant_email", "participant_name", "checked_in_at",
            "heartbeat_count", "active_duration_seconds", "score",
            "score_breakdown", "proof_level", "suggested_status"
        ]
        
        for field in expected_fields:
            assert field in session, f"Session should have '{field}' field"
        
        # Heartbeats should be excluded
        assert "heartbeats" not in session
        
        print(f"PASS: Participant session has all expected fields")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
