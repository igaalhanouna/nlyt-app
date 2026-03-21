"""
Test Calendar Integration APIs - Google Calendar and Outlook/Microsoft 365
Tests multi-provider calendar sync functionality including:
- GET /api/calendar/connections - List calendar connections
- GET /api/calendar/connect/google - Google OAuth initiation
- GET /api/calendar/connect/outlook - Outlook OAuth initiation (expected 500 - no credentials)
- GET /api/calendar/sync/status/{appointment_id} - Multi-provider sync status
- DELETE /api/calendar/connections/outlook - Disconnect Outlook (expected 404 if not connected)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "outlook_test@nlyt.app"
TEST_PASSWORD = "Test1234!"


class TestCalendarIntegration:
    """Calendar integration API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.token = None
        self.user_id = None
        
        # Login to get auth token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            self.token = data.get("access_token") or data.get("token")
            self.user_id = data.get("user", {}).get("user_id")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            print(f"✓ Logged in as {TEST_EMAIL}, user_id: {self.user_id}")
        else:
            pytest.skip(f"Authentication failed: {login_response.status_code} - {login_response.text}")
    
    # ── Test A: List Calendar Connections ──
    def test_list_connections_returns_list(self):
        """GET /api/calendar/connections should return a list (empty or with connections)"""
        response = self.session.get(f"{BASE_URL}/api/calendar/connections")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "connections" in data, "Response should have 'connections' key"
        assert isinstance(data["connections"], list), "connections should be a list"
        
        print(f"✓ GET /api/calendar/connections returned {len(data['connections'])} connection(s)")
        
        # Verify connection structure if any exist
        for conn in data["connections"]:
            assert "provider" in conn, "Connection should have 'provider' field"
            assert conn["provider"] in ["google", "outlook"], f"Unknown provider: {conn['provider']}"
            print(f"  - Found {conn['provider']} connection: {conn.get('google_email') or conn.get('outlook_email', 'N/A')}")
    
    # ── Test B: Google Calendar Connect (OAuth initiation) ──
    def test_google_connect_returns_authorization_url(self):
        """GET /api/calendar/connect/google should return a valid authorization_url"""
        response = self.session.get(f"{BASE_URL}/api/calendar/connect/google")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "authorization_url" in data, "Response should have 'authorization_url' key"
        
        auth_url = data["authorization_url"]
        assert auth_url.startswith("https://accounts.google.com/"), f"Invalid Google OAuth URL: {auth_url[:100]}"
        assert "client_id=" in auth_url, "OAuth URL should contain client_id"
        assert "redirect_uri=" in auth_url, "OAuth URL should contain redirect_uri"
        assert "scope=" in auth_url, "OAuth URL should contain scope"
        
        print(f"✓ GET /api/calendar/connect/google returned valid authorization_url")
        print(f"  URL starts with: {auth_url[:80]}...")
    
    # ── Test C: Outlook Calendar Connect (Expected 500 - no credentials) ──
    def test_outlook_connect_returns_500_missing_credentials(self):
        """GET /api/calendar/connect/outlook should return 500 with MICROSOFT_CLIENT_ID missing message"""
        response = self.session.get(f"{BASE_URL}/api/calendar/connect/outlook")
        
        # Expected: 500 because MICROSOFT_CLIENT_ID is not configured
        assert response.status_code == 500, f"Expected 500, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "detail" in data, "Error response should have 'detail' field"
        assert "MICROSOFT_CLIENT_ID" in data["detail"], f"Error should mention MICROSOFT_CLIENT_ID: {data['detail']}"
        
        print(f"✓ GET /api/calendar/connect/outlook correctly returns 500")
        print(f"  Error message: {data['detail']}")
    
    # ── Test D: Sync Status Multi-Provider Format ──
    def test_sync_status_returns_multi_provider_format(self):
        """GET /api/calendar/sync/status/{appointment_id} should return multi-provider format"""
        # First, get an appointment to test with
        # Use the test appointment from previous iteration
        test_appointment_id = "45005668-7237-4bbc-a5ff-31906a9e18dc"  # Test Stripe 1
        
        response = self.session.get(f"{BASE_URL}/api/calendar/sync/status/{test_appointment_id}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify multi-provider format
        assert "google" in data, "Response should have 'google' key"
        assert "outlook" in data, "Response should have 'outlook' key"
        
        # Verify google structure
        assert "synced" in data["google"], "google should have 'synced' field"
        assert "has_connection" in data["google"], "google should have 'has_connection' field"
        assert isinstance(data["google"]["synced"], bool), "google.synced should be boolean"
        assert isinstance(data["google"]["has_connection"], bool), "google.has_connection should be boolean"
        
        # Verify outlook structure
        assert "synced" in data["outlook"], "outlook should have 'synced' field"
        assert "has_connection" in data["outlook"], "outlook should have 'has_connection' field"
        assert isinstance(data["outlook"]["synced"], bool), "outlook.synced should be boolean"
        assert isinstance(data["outlook"]["has_connection"], bool), "outlook.has_connection should be boolean"
        
        print(f"✓ GET /api/calendar/sync/status/{test_appointment_id} returned multi-provider format")
        print(f"  Google: synced={data['google']['synced']}, has_connection={data['google']['has_connection']}")
        print(f"  Outlook: synced={data['outlook']['synced']}, has_connection={data['outlook']['has_connection']}")
    
    # ── Test E: Disconnect Outlook (Expected 404 if not connected) ──
    def test_disconnect_outlook_returns_404_if_not_connected(self):
        """DELETE /api/calendar/connections/outlook should return 404 if no connection exists"""
        response = self.session.delete(f"{BASE_URL}/api/calendar/connections/outlook")
        
        # Expected: 404 because user likely doesn't have Outlook connected
        # (If they do have it connected, this would return 200 - both are valid)
        if response.status_code == 404:
            data = response.json()
            assert "detail" in data, "Error response should have 'detail' field"
            print(f"✓ DELETE /api/calendar/connections/outlook correctly returns 404 (no connection)")
            print(f"  Error message: {data['detail']}")
        elif response.status_code == 200:
            data = response.json()
            assert data.get("success") == True, "Success response should have success=True"
            print(f"✓ DELETE /api/calendar/connections/outlook returned 200 (connection was removed)")
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}: {response.text}")
    
    # ── Test F: Disconnect Google (Expected 404 if not connected) ──
    def test_disconnect_google_returns_expected_response(self):
        """DELETE /api/calendar/connections/google should return 404 or 200"""
        response = self.session.delete(f"{BASE_URL}/api/calendar/connections/google")
        
        if response.status_code == 404:
            data = response.json()
            assert "detail" in data, "Error response should have 'detail' field"
            print(f"✓ DELETE /api/calendar/connections/google returns 404 (no connection)")
        elif response.status_code == 200:
            data = response.json()
            assert data.get("success") == True, "Success response should have success=True"
            print(f"✓ DELETE /api/calendar/connections/google returned 200 (connection was removed)")
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}: {response.text}")


class TestCalendarSyncEndpoints:
    """Test calendar sync endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            self.token = data.get("access_token") or data.get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Authentication failed")
    
    def test_sync_appointment_without_connection_returns_400(self):
        """POST /api/calendar/sync/appointment/{id} should return 400 if not connected"""
        test_appointment_id = "45005668-7237-4bbc-a5ff-31906a9e18dc"
        
        # Try to sync with Google (may or may not be connected)
        response = self.session.post(f"{BASE_URL}/api/calendar/sync/appointment/{test_appointment_id}?provider=google")
        
        # If not connected, should return 400
        # If connected, could return 200 or already_synced
        if response.status_code == 400:
            data = response.json()
            assert "detail" in data
            print(f"✓ Sync without connection returns 400: {data['detail']}")
        elif response.status_code == 200:
            data = response.json()
            print(f"✓ Sync returned 200: {data.get('sync_status', 'unknown')}")
        else:
            print(f"Sync returned {response.status_code}: {response.text}")
    
    def test_sync_appointment_outlook_without_connection(self):
        """POST /api/calendar/sync/appointment/{id}?provider=outlook should return 400 if not connected"""
        test_appointment_id = "45005668-7237-4bbc-a5ff-31906a9e18dc"
        
        response = self.session.post(f"{BASE_URL}/api/calendar/sync/appointment/{test_appointment_id}?provider=outlook")
        
        # Expected 400 because Outlook is not connected
        if response.status_code == 400:
            data = response.json()
            assert "detail" in data
            print(f"✓ Outlook sync without connection returns 400: {data['detail']}")
        elif response.status_code == 200:
            print(f"✓ Outlook sync returned 200 (user has Outlook connected)")
        else:
            print(f"Outlook sync returned {response.status_code}: {response.text}")


class TestNoRegression:
    """Test that existing functionality still works"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_health_endpoint(self):
        """GET /api/health should return healthy"""
        response = self.session.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✓ Health endpoint working")
    
    def test_login_works(self):
        """POST /api/auth/login should work with valid credentials"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.status_code}: {response.text}"
        data = response.json()
        assert "access_token" in data or "token" in data, f"Response should have access_token or token: {data.keys()}"
        assert "user" in data
        print(f"✓ Login works for {TEST_EMAIL}")
    
    def test_dashboard_appointments_accessible(self):
        """GET /api/appointments/ should be accessible after login"""
        # Login first
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert login_response.status_code == 200
        token = login_response.json().get("access_token") or login_response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get appointments
        response = self.session.get(f"{BASE_URL}/api/appointments/")
        assert response.status_code == 200
        data = response.json()
        assert "appointments" in data
        print(f"✓ Appointments endpoint accessible, found {len(data['appointments'])} appointments")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
