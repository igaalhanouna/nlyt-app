"""
P0 Bug Fix Tests - Iteration 126
Tests for idempotency guard on initialize_declarative_phase and is_self_declaration preservation.

Bug: Decision engine blocked for 2-participant appointments. Both users submitted their presence 
sheets but no dispute was created. Root cause: initialize_declarative_phase() was not idempotent - 
it always overwrote declarative_phase to 'collecting' even if called twice.

Fixes tested:
1. Idempotency guard on initialize_declarative_phase (lines 40-54)
2. is_self_declaration field preserved in submit_sheet (lines 179-198)
3. Full 1v1 disagreement flow creates dispute
4. Full 1v1 agreement flow auto-resolves
5. Strong proof lockdown still works (GPS/QR/Video → no manual_review)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
USER1_EMAIL = "testuser_audit@nlyt.app"
USER1_PASSWORD = "TestAudit123!"
USER2_EMAIL = "igaal.hanouna@gmail.com"
USER2_PASSWORD = "OrgTest123!"
USER3_EMAIL = "igaal@hotmail.com"
USER3_PASSWORD = "Test123!"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def user1_token(api_client):
    """Get auth token for user 1"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": USER1_EMAIL,
        "password": USER1_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"User 1 auth failed: {response.status_code}")


@pytest.fixture(scope="module")
def user2_token(api_client):
    """Get auth token for user 2"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": USER2_EMAIL,
        "password": USER2_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"User 2 auth failed: {response.status_code}")


@pytest.fixture(scope="module")
def user3_token(api_client):
    """Get auth token for user 3"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": USER3_EMAIL,
        "password": USER3_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"User 3 auth failed: {response.status_code}")


class TestHealthAndAuth:
    """Basic health and auth tests"""
    
    def test_health_endpoint(self, api_client):
        """Test health endpoint is accessible"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✅ Health endpoint working")
    
    def test_auth_user1(self, api_client, user1_token):
        """Test user 1 can authenticate"""
        assert user1_token is not None
        assert len(user1_token) > 0
        print(f"✅ User 1 authenticated: {USER1_EMAIL}")
    
    def test_auth_user2(self, api_client, user2_token):
        """Test user 2 can authenticate"""
        assert user2_token is not None
        assert len(user2_token) > 0
        print(f"✅ User 2 authenticated: {USER2_EMAIL}")
    
    def test_auth_user3(self, api_client, user3_token):
        """Test user 3 can authenticate"""
        assert user3_token is not None
        assert len(user3_token) > 0
        print(f"✅ User 3 authenticated: {USER3_EMAIL}")


class TestPresencesAPI:
    """Test /api/attendance-sheets endpoints"""
    
    def test_get_pending_sheets_user1(self, api_client, user1_token):
        """Test GET /api/attendance-sheets/pending for user 1"""
        response = api_client.get(
            f"{BASE_URL}/api/attendance-sheets/pending",
            headers={"Authorization": f"Bearer {user1_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "pending_sheets" in data
        assert "count" in data
        print(f"✅ GET /api/attendance-sheets/pending: {data.get('count')} pending sheets for user 1")
    
    def test_get_pending_sheets_user2(self, api_client, user2_token):
        """Test GET /api/attendance-sheets/pending for user 2"""
        response = api_client.get(
            f"{BASE_URL}/api/attendance-sheets/pending",
            headers={"Authorization": f"Bearer {user2_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "pending_sheets" in data
        print(f"✅ GET /api/attendance-sheets/pending: {data.get('count')} pending sheets for user 2")
    
    def test_get_pending_sheets_user3(self, api_client, user3_token):
        """Test GET /api/attendance-sheets/pending for user 3"""
        response = api_client.get(
            f"{BASE_URL}/api/attendance-sheets/pending",
            headers={"Authorization": f"Bearer {user3_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "pending_sheets" in data
        print(f"✅ GET /api/attendance-sheets/pending: {data.get('count')} pending sheets for user 3")
    
    def test_get_sheet_for_nonexistent_appointment(self, api_client, user1_token):
        """Test GET /api/attendance-sheets/{appointment_id} for non-existent appointment"""
        response = api_client.get(
            f"{BASE_URL}/api/attendance-sheets/nonexistent-appointment-id",
            headers={"Authorization": f"Bearer {user1_token}"}
        )
        assert response.status_code == 404
        print("✅ GET /api/attendance-sheets/{nonexistent} returns 404")
    
    def test_get_sheet_status_for_nonexistent_appointment(self, api_client, user1_token):
        """Test GET /api/attendance-sheets/{appointment_id}/status for non-existent appointment"""
        response = api_client.get(
            f"{BASE_URL}/api/attendance-sheets/nonexistent-appointment-id/status",
            headers={"Authorization": f"Bearer {user1_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("phase") == "not_needed"
        print("✅ GET /api/attendance-sheets/{nonexistent}/status returns phase=not_needed")
    
    def test_submit_sheet_invalid_appointment(self, api_client, user1_token):
        """Test POST /api/attendance-sheets/{appointment_id}/submit for invalid appointment"""
        response = api_client.post(
            f"{BASE_URL}/api/attendance-sheets/nonexistent-appointment-id/submit",
            headers={"Authorization": f"Bearer {user1_token}"},
            json={"declarations": []}
        )
        # Should return 400 (no sheet found) or 404
        assert response.status_code in [400, 404]
        print("✅ POST /api/attendance-sheets/{nonexistent}/submit returns error")


class TestDisputesAPI:
    """Test /api/disputes endpoints"""
    
    def test_get_disputes_user1(self, api_client, user1_token):
        """Test GET /api/disputes/mine for user 1"""
        response = api_client.get(
            f"{BASE_URL}/api/disputes/mine",
            headers={"Authorization": f"Bearer {user1_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "disputes" in data
        print(f"✅ GET /api/disputes/mine: {len(data.get('disputes', []))} disputes for user 1")
    
    def test_get_disputes_user2(self, api_client, user2_token):
        """Test GET /api/disputes/mine for user 2"""
        response = api_client.get(
            f"{BASE_URL}/api/disputes/mine",
            headers={"Authorization": f"Bearer {user2_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "disputes" in data
        print(f"✅ GET /api/disputes/mine: {len(data.get('disputes', []))} disputes for user 2")
    
    def test_submit_position_invalid_dispute(self, api_client, user1_token):
        """Test POST /api/disputes/{id}/positions for invalid dispute"""
        response = api_client.post(
            f"{BASE_URL}/api/disputes/nonexistent-dispute-id/positions",
            headers={"Authorization": f"Bearer {user1_token}"},
            json={"position": "confirmed_present"}
        )
        # Should return 400 or 404
        assert response.status_code in [400, 404]
        print("✅ POST /api/disputes/{nonexistent}/positions returns error")


class TestIdempotencyGuardUnit:
    """Unit tests for idempotency guard - run via direct Python import"""
    
    def test_idempotency_guard_tests_pass(self, api_client):
        """Verify the idempotency guard unit tests pass"""
        import subprocess
        result = subprocess.run(
            ["python3", "tests/test_idempotency_guard.py"],
            cwd="/app/backend",
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Idempotency guard tests failed:\n{result.stdout}\n{result.stderr}"
        assert "9 PASSED, 0 FAILED" in result.stdout
        print("✅ All 9 idempotency guard unit tests pass")
    
    def test_presences_flow_tests_pass(self, api_client):
        """Verify the presences flow tests pass"""
        import subprocess
        result = subprocess.run(
            ["python3", "tests/test_presences_flow.py"],
            cwd="/app/backend",
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Presences flow tests failed:\n{result.stdout}\n{result.stderr}"
        assert "ALL TESTS PASSED" in result.stdout
        print("✅ All presences flow tests pass")
    
    def test_strong_proof_lockdown_tests_pass(self, api_client):
        """Verify the strong proof lockdown tests pass"""
        import subprocess
        result = subprocess.run(
            ["python3", "tests/test_strong_proof_lockdown.py"],
            cwd="/app/backend",
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Strong proof lockdown tests failed:\n{result.stdout}\n{result.stderr}"
        assert "ALL LOCK-DOWN TESTS PASSED" in result.stdout
        print("✅ All strong proof lockdown tests pass")


class TestAttendanceAPI:
    """Test /api/attendance endpoints"""
    
    def test_get_attendance_records(self, api_client, user1_token):
        """Test GET /api/attendance endpoint"""
        response = api_client.get(
            f"{BASE_URL}/api/attendance",
            headers={"Authorization": f"Bearer {user1_token}"}
        )
        # Should return 200 or 404 if no records
        assert response.status_code in [200, 404]
        print(f"✅ GET /api/attendance: status {response.status_code}")


class TestAppointmentsAPI:
    """Test /api/appointments endpoints"""
    
    def test_get_appointments_user1(self, api_client, user1_token):
        """Test GET /api/appointments/ for user 1"""
        response = api_client.get(
            f"{BASE_URL}/api/appointments/",
            headers={"Authorization": f"Bearer {user1_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        print(f"✅ GET /api/appointments/: {len(data.get('items', []))} appointments for user 1")
    
    def test_get_appointments_user2(self, api_client, user2_token):
        """Test GET /api/appointments/ for user 2"""
        response = api_client.get(
            f"{BASE_URL}/api/appointments/",
            headers={"Authorization": f"Bearer {user2_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        print(f"✅ GET /api/appointments/: {len(data.get('items', []))} appointments for user 2")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
