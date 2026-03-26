"""
Test suite for External Events API endpoints (Phase 1 V2 Calendar Import)
Tests: GET /api/external-events/import-settings, PUT /api/external-events/import-settings,
       POST /api/external-events/sync, GET /api/external-events/
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "stripe-test@nlyt.io"
TEST_PASSWORD = "Test123!"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        # API returns access_token, not token
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture
def auth_headers(auth_token):
    """Headers with Bearer token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestExternalEventsAuth:
    """Test that all external events endpoints require authentication"""

    def test_import_settings_requires_auth(self):
        """GET /api/external-events/import-settings returns 401 without token"""
        response = requests.get(f"{BASE_URL}/api/external-events/import-settings")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ GET /import-settings requires auth (401 without token)")

    def test_update_import_settings_requires_auth(self):
        """PUT /api/external-events/import-settings returns 401 without token"""
        response = requests.put(f"{BASE_URL}/api/external-events/import-settings", json={
            "provider": "google",
            "enabled": True
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ PUT /import-settings requires auth (401 without token)")

    def test_sync_requires_auth(self):
        """POST /api/external-events/sync returns 401 without token"""
        response = requests.post(f"{BASE_URL}/api/external-events/sync")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ POST /sync requires auth (401 without token)")

    def test_list_events_requires_auth(self):
        """GET /api/external-events/ returns 401 without token"""
        response = requests.get(f"{BASE_URL}/api/external-events/")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ GET / (list events) requires auth (401 without token)")


class TestExternalEventsImportSettings:
    """Test GET /api/external-events/import-settings endpoint"""

    def test_get_import_settings_success(self, auth_headers):
        """GET /api/external-events/import-settings returns providers object"""
        response = requests.get(f"{BASE_URL}/api/external-events/import-settings", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "providers" in data, "Response should contain 'providers' key"
        assert isinstance(data["providers"], dict), "'providers' should be a dict"
        
        # Test user has no calendar connections, so providers should be empty
        print(f"✅ GET /import-settings returns providers: {data['providers']}")
        print(f"   (Empty providers expected since test user has no calendar connections)")

    def test_get_import_settings_structure(self, auth_headers):
        """Verify import settings response structure"""
        response = requests.get(f"{BASE_URL}/api/external-events/import-settings", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        providers = data.get("providers", {})
        
        # If there are connected providers, verify structure
        for provider, info in providers.items():
            assert provider in ("google", "outlook"), f"Unknown provider: {provider}"
            assert "connected" in info, f"Provider {provider} missing 'connected' field"
            assert "import_enabled" in info, f"Provider {provider} missing 'import_enabled' field"
            assert "last_synced_at" in info, f"Provider {provider} missing 'last_synced_at' field"
            assert "event_count" in info, f"Provider {provider} missing 'event_count' field"
        
        print("✅ Import settings response structure is valid")


class TestExternalEventsUpdateSettings:
    """Test PUT /api/external-events/import-settings endpoint"""

    def test_update_settings_invalid_provider(self, auth_headers):
        """PUT with invalid provider returns 400"""
        response = requests.put(
            f"{BASE_URL}/api/external-events/import-settings",
            headers=auth_headers,
            json={"provider": "invalid_provider", "enabled": True}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✅ PUT /import-settings rejects invalid provider (400)")

    def test_update_settings_missing_enabled(self, auth_headers):
        """PUT without 'enabled' field returns 400"""
        response = requests.put(
            f"{BASE_URL}/api/external-events/import-settings",
            headers=auth_headers,
            json={"provider": "google"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✅ PUT /import-settings rejects missing 'enabled' field (400)")

    def test_update_settings_invalid_enabled_type(self, auth_headers):
        """PUT with non-boolean 'enabled' returns 400"""
        response = requests.put(
            f"{BASE_URL}/api/external-events/import-settings",
            headers=auth_headers,
            json={"provider": "google", "enabled": "yes"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✅ PUT /import-settings rejects non-boolean 'enabled' (400)")

    def test_update_settings_no_connection(self, auth_headers):
        """PUT for provider without connection returns 400"""
        # Test user has no Google/Outlook connections
        response = requests.put(
            f"{BASE_URL}/api/external-events/import-settings",
            headers=auth_headers,
            json={"provider": "google", "enabled": True}
        )
        # Should return 400 because user has no Google connection
        assert response.status_code == 400, f"Expected 400 (no connection), got {response.status_code}"
        data = response.json()
        assert "detail" in data or "error" in data, "Should have error message"
        print("✅ PUT /import-settings returns 400 when provider not connected")


class TestExternalEventsSync:
    """Test POST /api/external-events/sync endpoint"""

    def test_sync_returns_results(self, auth_headers):
        """POST /api/external-events/sync returns results object"""
        response = requests.post(
            f"{BASE_URL}/api/external-events/sync",
            headers=auth_headers,
            json={}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "results" in data, "Response should contain 'results' key"
        assert isinstance(data["results"], dict), "'results' should be a dict"
        
        # Test user has no enabled providers, so results should be empty
        print(f"✅ POST /sync returns results: {data['results']}")
        print(f"   (Empty results expected since test user has no enabled providers)")

    def test_sync_with_force_flag(self, auth_headers):
        """POST /api/external-events/sync with force=true works"""
        response = requests.post(
            f"{BASE_URL}/api/external-events/sync",
            headers=auth_headers,
            json={"force": True}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "results" in data
        print("✅ POST /sync with force=true works correctly")

    def test_sync_without_body(self, auth_headers):
        """POST /api/external-events/sync without body works"""
        response = requests.post(
            f"{BASE_URL}/api/external-events/sync",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "results" in data
        print("✅ POST /sync without body works correctly")


class TestExternalEventsList:
    """Test GET /api/external-events/ endpoint"""

    def test_list_events_returns_structure(self, auth_headers):
        """GET /api/external-events/ returns events array and providers list"""
        response = requests.get(f"{BASE_URL}/api/external-events/", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "events" in data, "Response should contain 'events' key"
        assert "providers" in data, "Response should contain 'providers' key"
        assert isinstance(data["events"], list), "'events' should be a list"
        assert isinstance(data["providers"], list), "'providers' should be a list"
        
        # Test user has no enabled providers, so both should be empty
        print(f"✅ GET / returns events: {len(data['events'])}, providers: {data['providers']}")
        print(f"   (Empty expected since test user has no enabled providers)")

    def test_list_events_empty_when_no_providers(self, auth_headers):
        """GET /api/external-events/ returns empty when no providers enabled"""
        response = requests.get(f"{BASE_URL}/api/external-events/", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        # Test user has no calendar connections, so should be empty
        assert data["events"] == [], "Events should be empty for user without connections"
        assert data["providers"] == [], "Providers should be empty for user without connections"
        print("✅ GET / returns empty arrays when no providers enabled")


class TestHealthAndRegression:
    """Basic health check and regression tests"""

    def test_health_endpoint(self):
        """Health endpoint works"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✅ Health endpoint returns healthy")

    def test_auth_login_works(self):
        """Login endpoint works with test credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.status_code}"
        data = response.json()
        assert "access_token" in data or "token" in data, "Login should return access_token"
        assert "user" in data, "Login should return user"
        print("✅ Login works with test credentials")

    def test_workspaces_list_works(self, auth_headers):
        """Workspaces list endpoint works (regression)"""
        response = requests.get(f"{BASE_URL}/api/workspaces/", headers=auth_headers)
        assert response.status_code == 200, f"Workspaces list failed: {response.status_code}"
        print("✅ Workspaces list endpoint works")

    def test_calendar_connections_list_works(self, auth_headers):
        """Calendar connections list endpoint works (regression)"""
        response = requests.get(f"{BASE_URL}/api/calendar/connections", headers=auth_headers)
        assert response.status_code == 200, f"Calendar connections failed: {response.status_code}"
        data = response.json()
        assert "connections" in data, "Should return connections array"
        print(f"✅ Calendar connections list works (found {len(data['connections'])} connections)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
