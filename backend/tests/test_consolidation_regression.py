"""
Regression tests for code consolidation:
1. Centralized MongoClient in database.py (32 files migrated)
2. AppointmentDetail.js split into 5 sub-components
3. Dead enums removed (AUTH_NOW/AUTH_LATER)
4. debug.py protected with require_admin

Tests verify all existing functionality still works after refactoring.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"
VALID_INVITATION_TOKEN = "3488744e-989d-43d5-b96f-2522e5701d7a"


def get_auth_token():
    """Helper to get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    return None


def get_session_with_auth():
    """Get a session with auth token that handles redirects properly"""
    session = requests.Session()
    token = get_auth_token()
    if token:
        session.headers.update({"Authorization": f"Bearer {token}"})
    return session, token


class TestHealthAndBasicEndpoints:
    """Test basic API health and connectivity"""
    
    def test_health_check(self):
        """Backend health check returns 200"""
        response = requests.get(f"{BASE_URL}/api/health", allow_redirects=True)
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        print("✓ Health check passed")


class TestAuthentication:
    """Test authentication endpoints work after MongoClient migration"""
    
    def test_login_success(self):
        """Login endpoint works with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        }, allow_redirects=True)
        assert response.status_code == 200, f"Login failed: {response.status_code} - {response.text}"
        data = response.json()
        assert "access_token" in data, "Response missing access_token"
        assert "user" in data, "Response missing user"
        print(f"✓ Login successful for {TEST_EMAIL}")
    
    def test_login_invalid_credentials(self):
        """Login fails with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "invalid@example.com",
            "password": "wrongpassword"
        }, allow_redirects=True)
        assert response.status_code in [401, 404], f"Expected 401/404, got {response.status_code}"
        print("✓ Invalid login correctly rejected")


class TestAppointmentsAPI:
    """Test appointments API after MongoClient migration"""
    
    def test_get_appointments_list(self):
        """GET /api/appointments returns appointments list"""
        session, token = get_session_with_auth()
        assert token, "Failed to get auth token"
        
        # Use trailing slash to avoid redirect issues
        response = session.get(f"{BASE_URL}/api/appointments/", allow_redirects=True)
        assert response.status_code == 200, f"Failed to get appointments: {response.status_code} - {response.text}"
        data = response.json()
        assert "appointments" in data, "Response missing appointments key"
        print(f"✓ Got {len(data['appointments'])} appointments")
    
    def test_get_appointment_detail(self):
        """GET /api/appointments/{id} returns appointment details"""
        session, token = get_session_with_auth()
        assert token, "Failed to get auth token"
        
        # First get list to find an appointment ID
        list_response = session.get(f"{BASE_URL}/api/appointments/", allow_redirects=True)
        if list_response.status_code != 200:
            pytest.skip("Could not get appointments list")
        
        appointments = list_response.json().get("appointments", [])
        if not appointments:
            pytest.skip("No appointments found to test detail view")
        
        apt_id = appointments[0].get("appointment_id")
        response = session.get(f"{BASE_URL}/api/appointments/{apt_id}", allow_redirects=True)
        assert response.status_code == 200, f"Failed to get appointment detail: {response.status_code}"
        data = response.json()
        assert "appointment_id" in data, "Response missing appointment_id"
        print(f"✓ Got appointment detail for {apt_id}")


class TestCheckinAPI:
    """Test check-in API after MongoClient migration"""
    
    def test_manual_checkin_invalid_token(self):
        """POST /api/checkin/manual with invalid token returns 404"""
        response = requests.post(f"{BASE_URL}/api/checkin/manual", json={
            "appointment_id": "nonexistent",
            "invitation_token": "invalid-token-12345",
            "device_info": "pytest"
        }, allow_redirects=True)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Invalid token correctly returns 404")


class TestInvitationsAPI:
    """Test invitations API after MongoClient migration"""
    
    def test_get_invitation_by_token(self):
        """GET /api/invitations/{token} works for valid token"""
        response = requests.get(f"{BASE_URL}/api/invitations/{VALID_INVITATION_TOKEN}", allow_redirects=True)
        # Token may be valid or expired, but endpoint should work
        assert response.status_code in [200, 404, 410], f"Unexpected status: {response.status_code}"
        print(f"✓ Invitation endpoint returned {response.status_code}")


class TestDebugEndpointsProtection:
    """Test debug endpoints are protected with admin auth"""
    
    def test_debug_email_attempts_requires_auth(self):
        """Debug endpoint without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/debug/email-attempts", allow_redirects=True)
        assert response.status_code in [401, 403, 422], f"Expected 401/403/422, got {response.status_code}"
        print("✓ Debug endpoint correctly requires auth")
    
    def test_debug_users_requires_auth(self):
        """Debug users endpoint without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/debug/users-debug", allow_redirects=True)
        assert response.status_code in [401, 403, 422], f"Expected 401/403/422, got {response.status_code}"
        print("✓ Debug users endpoint correctly requires auth")
    
    def test_debug_headers_no_auth_required(self):
        """Debug headers endpoint works without auth (for debugging)"""
        response = requests.get(f"{BASE_URL}/api/debug/headers", allow_redirects=True)
        assert response.status_code == 200, f"Headers debug should work: {response.status_code}"
        print("✓ Debug headers endpoint works without auth")
    
    def test_debug_endpoint_with_auth(self):
        """Debug endpoint with auth user returns 200 or 403"""
        session, token = get_session_with_auth()
        assert token, "Failed to get auth token"
        
        response = session.get(f"{BASE_URL}/api/debug/email-attempts", allow_redirects=True)
        # testuser_audit may or may not be admin - check for proper response
        assert response.status_code in [200, 403], f"Expected 200 or 403, got {response.status_code}"
        if response.status_code == 403:
            print("✓ Non-admin user correctly rejected with 403")
        else:
            print("✓ Admin user correctly allowed access")


class TestDatabaseConnection:
    """Test database connection via centralized database.py"""
    
    def test_workspaces_endpoint(self):
        """Workspaces endpoint works (uses db from database.py)"""
        session, token = get_session_with_auth()
        assert token, "Failed to get auth token"
        
        response = session.get(f"{BASE_URL}/api/workspaces/", allow_redirects=True)
        assert response.status_code == 200, f"Workspaces failed: {response.status_code}"
        print("✓ Workspaces endpoint works")
    
    def test_participants_endpoint(self):
        """Participants endpoint works (uses db from database.py)"""
        session, token = get_session_with_auth()
        assert token, "Failed to get auth token"
        
        # Get an appointment first
        apt_response = session.get(f"{BASE_URL}/api/appointments/", allow_redirects=True)
        if apt_response.status_code != 200:
            pytest.skip("Could not get appointments")
        
        appointments = apt_response.json().get("appointments", [])
        if not appointments:
            pytest.skip("No appointments to test participants")
        
        apt_id = appointments[0].get("appointment_id")
        # Correct endpoint: /api/participants?appointment_id=...
        response = session.get(f"{BASE_URL}/api/participants/", params={"appointment_id": apt_id}, allow_redirects=True)
        assert response.status_code == 200, f"Participants failed: {response.status_code}"
        data = response.json()
        assert "participants" in data, "Response missing participants key"
        print(f"✓ Participants endpoint works - got {len(data['participants'])} participants")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
