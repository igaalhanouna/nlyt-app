"""
Test NLYT Proof System and Provider Mode Changes
Tests:
1. Provider status endpoint returns Zoom as mode='user' (not 'central')
2. NLYT Proof full E2E: info, checkin, heartbeat, checkout
3. Organizer view: sessions endpoint
4. Organizer validation: validate endpoint
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"
WORKSPACE_ID = "7e219321-18fd-4643-9be6-e4f1de88a2a8"
TEST_APPOINTMENT_ID = "35df4fb0-91ac-4d6a-a56b-cfd6e06b4111"
TEST_PARTICIPANT_TOKEN = "2ee6406d-9682-4f07-8228-89177ecb0d02"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for organizer"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestProviderStatusModeChanges:
    """Test that Zoom is now mode='user' instead of mode='central'"""

    def test_provider_status_endpoint_returns_200(self, auth_headers):
        """Provider status endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/video-evidence/provider-status", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: Provider status endpoint returns 200")

    def test_zoom_mode_is_user_not_central(self, auth_headers):
        """Zoom should have mode='user' (not 'central' anymore)"""
        response = requests.get(f"{BASE_URL}/api/video-evidence/provider-status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "zoom" in data, "Response should contain 'zoom' key"
        zoom_info = data["zoom"]
        
        # CRITICAL: Zoom mode should be 'user' not 'central'
        assert zoom_info.get("mode") == "user", f"Zoom mode should be 'user', got '{zoom_info.get('mode')}'"
        print(f"PASS: Zoom mode is 'user' (not 'central')")

    def test_teams_mode_is_user(self, auth_headers):
        """Teams should have mode='user'"""
        response = requests.get(f"{BASE_URL}/api/video-evidence/provider-status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "teams" in data, "Response should contain 'teams' key"
        teams_info = data["teams"]
        assert teams_info.get("mode") == "user", f"Teams mode should be 'user', got '{teams_info.get('mode')}'"
        print(f"PASS: Teams mode is 'user'")

    def test_meet_mode_is_user(self, auth_headers):
        """Meet should have mode='user'"""
        response = requests.get(f"{BASE_URL}/api/video-evidence/provider-status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "meet" in data, "Response should contain 'meet' key"
        meet_info = data["meet"]
        assert meet_info.get("mode") == "user", f"Meet mode should be 'user', got '{meet_info.get('mode')}'"
        print(f"PASS: Meet mode is 'user'")

    def test_zoom_has_no_universal_flag(self, auth_headers):
        """Zoom should NOT have universal=true anymore (decoupled from central mode)"""
        response = requests.get(f"{BASE_URL}/api/video-evidence/provider-status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        zoom_info = data.get("zoom", {})
        # universal flag should not be present or should be False
        universal = zoom_info.get("universal", False)
        assert universal is False or "universal" not in zoom_info, f"Zoom should not have universal=true, got {zoom_info}"
        print(f"PASS: Zoom does not have universal=true")


class TestNLYTProofInfoEndpoint:
    """Test GET /api/proof/{apt_id}/info (token auth, no JWT required)"""

    def test_proof_info_returns_200_with_valid_token(self):
        """Proof info endpoint should return 200 with valid participant token"""
        response = requests.get(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/info",
            params={"token": TEST_PARTICIPANT_TOKEN}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: Proof info endpoint returns 200")

    def test_proof_info_returns_appointment_data(self):
        """Proof info should return appointment details"""
        response = requests.get(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/info",
            params={"token": TEST_PARTICIPANT_TOKEN}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "appointment" in data, "Response should contain 'appointment' key"
        apt = data["appointment"]
        assert apt.get("appointment_id") == TEST_APPOINTMENT_ID
        assert "title" in apt
        assert "start_datetime" in apt
        assert "duration_minutes" in apt
        print(f"PASS: Proof info returns appointment data: {apt.get('title')}")

    def test_proof_info_returns_participant_data(self):
        """Proof info should return participant details"""
        response = requests.get(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/info",
            params={"token": TEST_PARTICIPANT_TOKEN}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "participant" in data, "Response should contain 'participant' key"
        participant = data["participant"]
        assert "participant_id" in participant
        assert "first_name" in participant
        assert "last_name" in participant
        assert "email" in participant
        print(f"PASS: Proof info returns participant data: {participant.get('first_name')} {participant.get('last_name')}")

    def test_proof_info_returns_active_session_if_exists(self):
        """Proof info should return active_session field (null or session data)"""
        response = requests.get(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/info",
            params={"token": TEST_PARTICIPANT_TOKEN}
        )
        assert response.status_code == 200
        data = response.json()
        
        # active_session can be null or an object
        assert "active_session" in data, "Response should contain 'active_session' key"
        print(f"PASS: Proof info returns active_session field: {data.get('active_session')}")

    def test_proof_info_rejects_invalid_token(self):
        """Proof info should return 404 for invalid token"""
        response = requests.get(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/info",
            params={"token": "invalid-token-12345"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Proof info rejects invalid token with 404")


class TestNLYTProofCheckinEndpoint:
    """Test POST /api/proof/{apt_id}/checkin"""

    def test_checkin_creates_session(self):
        """Checkin should create a new proof session"""
        response = requests.post(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/checkin",
            json={"token": TEST_PARTICIPANT_TOKEN}
        )
        # Can be 200 (new session) or 200 with already_active=True
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "session_id" in data, "Response should contain 'session_id'"
        print(f"PASS: Checkin returns session_id: {data.get('session_id')}, already_active: {data.get('already_active')}")
        return data.get("session_id")

    def test_checkin_returns_meeting_join_url(self):
        """Checkin should return meeting_join_url if available"""
        response = requests.post(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/checkin",
            json={"token": TEST_PARTICIPANT_TOKEN}
        )
        assert response.status_code == 200
        data = response.json()
        
        # meeting_join_url can be empty string or URL
        assert "meeting_join_url" in data, "Response should contain 'meeting_join_url'"
        print(f"PASS: Checkin returns meeting_join_url: {data.get('meeting_join_url', '(empty)')}")

    def test_checkin_rejects_invalid_token(self):
        """Checkin should return 404 for invalid token"""
        response = requests.post(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/checkin",
            json={"token": "invalid-token-12345"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Checkin rejects invalid token with 404")


class TestNLYTProofHeartbeatEndpoint:
    """Test POST /api/proof/{apt_id}/heartbeat"""

    def test_heartbeat_requires_session_id(self):
        """Heartbeat should require session_id"""
        response = requests.post(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/heartbeat",
            json={}
        )
        # Should fail validation (422) or return 404 if session not found
        assert response.status_code in [404, 422], f"Expected 404 or 422, got {response.status_code}"
        print("PASS: Heartbeat requires session_id")

    def test_heartbeat_with_valid_session(self):
        """Heartbeat should work with valid session_id"""
        # First, get or create a session
        checkin_response = requests.post(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/checkin",
            json={"token": TEST_PARTICIPANT_TOKEN}
        )
        if checkin_response.status_code != 200:
            pytest.skip("Could not create session for heartbeat test")
        
        session_id = checkin_response.json().get("session_id")
        
        # Send heartbeat
        response = requests.post(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/heartbeat",
            json={"session_id": session_id}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("status") == "ok", f"Expected status='ok', got {data.get('status')}"
        assert "heartbeat_count" in data, "Response should contain 'heartbeat_count'"
        print(f"PASS: Heartbeat successful, count: {data.get('heartbeat_count')}")


class TestNLYTProofCheckoutEndpoint:
    """Test POST /api/proof/{apt_id}/checkout"""

    def test_checkout_computes_score(self):
        """Checkout should compute score and return proof level"""
        # First, get or create a session
        checkin_response = requests.post(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/checkin",
            json={"token": TEST_PARTICIPANT_TOKEN}
        )
        if checkin_response.status_code != 200:
            pytest.skip("Could not create session for checkout test")
        
        session_id = checkin_response.json().get("session_id")
        
        # Send a few heartbeats
        for _ in range(2):
            requests.post(
                f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/heartbeat",
                json={"session_id": session_id}
            )
            time.sleep(0.5)
        
        # Checkout
        response = requests.post(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/checkout",
            json={"session_id": session_id}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "session_id" in data
        assert "score" in data, "Response should contain 'score'"
        assert "proof_level" in data, "Response should contain 'proof_level'"
        assert "suggested_status" in data, "Response should contain 'suggested_status'"
        assert "active_duration_seconds" in data, "Response should contain 'active_duration_seconds'"
        
        print(f"PASS: Checkout computed score={data.get('score')}, proof_level={data.get('proof_level')}, suggested={data.get('suggested_status')}")


class TestNLYTProofSessionsEndpoint:
    """Test GET /api/proof/{apt_id}/sessions (organizer only, requires auth)"""

    def test_sessions_requires_auth(self):
        """Sessions endpoint should require authentication"""
        response = requests.get(f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/sessions")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Sessions endpoint requires auth")

    def test_sessions_returns_list(self, auth_headers):
        """Sessions endpoint should return list of sessions"""
        response = requests.get(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/sessions",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "sessions" in data, "Response should contain 'sessions' key"
        assert "count" in data, "Response should contain 'count' key"
        assert isinstance(data["sessions"], list), "sessions should be a list"
        
        print(f"PASS: Sessions endpoint returns {data.get('count')} sessions")
        
        # Verify session structure if any exist
        if data["sessions"]:
            session = data["sessions"][0]
            assert "session_id" in session
            assert "participant_email" in session
            assert "checked_in_at" in session
            print(f"PASS: Session structure verified: {session.get('participant_email')}")


class TestNLYTProofValidateEndpoint:
    """Test POST /api/proof/{apt_id}/validate (organizer only)"""

    def test_validate_requires_auth(self):
        """Validate endpoint should require authentication"""
        response = requests.post(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/validate",
            json={"session_id": "test", "final_status": "present"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Validate endpoint requires auth")

    def test_validate_rejects_invalid_status(self, auth_headers):
        """Validate should reject invalid final_status values"""
        # First get a session
        sessions_response = requests.get(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/sessions",
            headers=auth_headers
        )
        if sessions_response.status_code != 200 or not sessions_response.json().get("sessions"):
            pytest.skip("No sessions available for validation test")
        
        session_id = sessions_response.json()["sessions"][0]["session_id"]
        
        response = requests.post(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/validate",
            headers=auth_headers,
            json={"session_id": session_id, "final_status": "invalid_status"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: Validate rejects invalid status")

    def test_validate_accepts_valid_status(self, auth_headers):
        """Validate should accept valid final_status values (present, partial, absent)"""
        # First get a session
        sessions_response = requests.get(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/sessions",
            headers=auth_headers
        )
        if sessions_response.status_code != 200 or not sessions_response.json().get("sessions"):
            pytest.skip("No sessions available for validation test")
        
        session_id = sessions_response.json()["sessions"][0]["session_id"]
        
        # Validate as 'present'
        response = requests.post(
            f"{BASE_URL}/api/proof/{TEST_APPOINTMENT_ID}/validate",
            headers=auth_headers,
            json={"session_id": session_id, "final_status": "present"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("session_id") == session_id
        assert data.get("final_status") == "present"
        print(f"PASS: Validate accepted status 'present' for session {session_id[:8]}")


class TestHealthCheck:
    """Basic health check"""

    def test_health_endpoint(self):
        """Health endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("PASS: Health endpoint returns 200")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
