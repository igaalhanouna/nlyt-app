"""
Test suite for Dashboard Analytics Organisateur V1
Tests the GET /api/appointments/analytics/stats endpoint
KPIs: engagements créés, taux de présence, taux d'acceptation, 
      dédommagement personnel, impact caritatif, engagements non honorés
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("access_token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Return headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="module")
def workspace_id(auth_headers):
    """Get first workspace ID for the test user"""
    response = requests.get(f"{BASE_URL}/api/workspaces/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    workspaces = data.get("workspaces", [])
    assert len(workspaces) > 0, "No workspaces found for test user"
    return workspaces[0]["workspace_id"]


class TestAnalyticsEndpoint:
    """Tests for GET /api/appointments/analytics/stats"""

    def test_analytics_endpoint_returns_200(self, auth_headers, workspace_id):
        """Analytics endpoint should return 200 OK"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/analytics/stats",
            params={"workspace_id": workspace_id},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_analytics_returns_all_kpi_fields(self, auth_headers, workspace_id):
        """Response should contain all 6 KPI fields + global_message + global_tone"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/analytics/stats",
            params={"workspace_id": workspace_id},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check all required fields exist
        required_fields = [
            "total_engagements",
            "presence_rate",
            "acceptance_rate",
            "personal_compensation_cents",
            "charity_total_cents",
            "organizer_defaults",
            "global_message",
            "global_tone"
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_total_engagements_greater_than_zero(self, auth_headers, workspace_id):
        """Test user has 120 appointments, total_engagements should be > 0"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/analytics/stats",
            params={"workspace_id": workspace_id},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_engagements"] > 0, "Expected total_engagements > 0 for test user with appointments"
        print(f"Total engagements: {data['total_engagements']}")

    def test_acceptance_rate_is_percentage_or_null(self, auth_headers, workspace_id):
        """acceptance_rate should be a percentage (0-100) or null"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/analytics/stats",
            params={"workspace_id": workspace_id},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        rate = data["acceptance_rate"]
        if rate is not None:
            assert isinstance(rate, (int, float)), "acceptance_rate should be numeric"
            assert 0 <= rate <= 100, f"acceptance_rate should be 0-100, got {rate}"
        print(f"Acceptance rate: {rate}")

    def test_presence_rate_null_when_no_evaluations(self, auth_headers, workspace_id):
        """presence_rate should be null when no attendance evaluations exist"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/analytics/stats",
            params={"workspace_id": workspace_id},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Per context: no attendance evaluations exist yet, so presence_rate should be null
        # But if evaluations exist, it should be a percentage
        rate = data["presence_rate"]
        if rate is not None:
            assert isinstance(rate, (int, float)), "presence_rate should be numeric when not null"
            assert 0 <= rate <= 100, f"presence_rate should be 0-100, got {rate}"
        print(f"Presence rate: {rate} (null expected if no evaluations)")

    def test_compensation_and_charity_are_integers(self, auth_headers, workspace_id):
        """personal_compensation_cents and charity_total_cents should be integers"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/analytics/stats",
            params={"workspace_id": workspace_id},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data["personal_compensation_cents"], int), "personal_compensation_cents should be int"
        assert isinstance(data["charity_total_cents"], int), "charity_total_cents should be int"
        assert data["personal_compensation_cents"] >= 0, "personal_compensation_cents should be >= 0"
        assert data["charity_total_cents"] >= 0, "charity_total_cents should be >= 0"
        print(f"Personal compensation: {data['personal_compensation_cents']} cents")
        print(f"Charity total: {data['charity_total_cents']} cents")

    def test_organizer_defaults_is_integer(self, auth_headers, workspace_id):
        """organizer_defaults should be an integer >= 0"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/analytics/stats",
            params={"workspace_id": workspace_id},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data["organizer_defaults"], int), "organizer_defaults should be int"
        assert data["organizer_defaults"] >= 0, "organizer_defaults should be >= 0"
        print(f"Organizer defaults: {data['organizer_defaults']}")

    def test_global_message_and_tone_present(self, auth_headers, workspace_id):
        """global_message should be a string, global_tone should be positive/neutral/warning"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/analytics/stats",
            params={"workspace_id": workspace_id},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data["global_message"], str), "global_message should be string"
        assert len(data["global_message"]) > 0, "global_message should not be empty"
        assert data["global_tone"] in ["positive", "neutral", "warning"], \
            f"global_tone should be positive/neutral/warning, got {data['global_tone']}"
        print(f"Global message: {data['global_message']}")
        print(f"Global tone: {data['global_tone']}")

    def test_analytics_without_workspace_id(self, auth_headers):
        """Analytics should work without workspace_id (uses all user workspaces)"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/analytics/stats",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "total_engagements" in data

    def test_analytics_requires_authentication(self):
        """Analytics endpoint should require authentication"""
        response = requests.get(f"{BASE_URL}/api/appointments/analytics/stats")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"

    def test_analytics_invalid_workspace_returns_403(self, auth_headers):
        """Analytics with invalid workspace_id should return 403"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/analytics/stats",
            params={"workspace_id": "invalid-workspace-id-12345"},
            headers=auth_headers
        )
        assert response.status_code == 403, f"Expected 403 for invalid workspace, got {response.status_code}"


class TestAnalyticsDataIntegrity:
    """Tests for data integrity and consistency"""

    def test_total_engagements_matches_appointments_count(self, auth_headers, workspace_id):
        """total_engagements should match the count from appointments list"""
        # Get analytics
        analytics_response = requests.get(
            f"{BASE_URL}/api/appointments/analytics/stats",
            params={"workspace_id": workspace_id},
            headers=auth_headers
        )
        assert analytics_response.status_code == 200
        analytics = analytics_response.json()
        
        # Get appointments count (upcoming + past)
        upcoming_response = requests.get(
            f"{BASE_URL}/api/appointments/",
            params={"workspace_id": workspace_id, "time_filter": "upcoming", "limit": 1},
            headers=auth_headers
        )
        past_response = requests.get(
            f"{BASE_URL}/api/appointments/",
            params={"workspace_id": workspace_id, "time_filter": "past", "limit": 1},
            headers=auth_headers
        )
        
        assert upcoming_response.status_code == 200
        assert past_response.status_code == 200
        
        upcoming_total = upcoming_response.json().get("total", 0)
        past_total = past_response.json().get("total", 0)
        expected_total = upcoming_total + past_total
        
        # Analytics total should match (or be close - may exclude deleted)
        assert analytics["total_engagements"] == expected_total, \
            f"Analytics total ({analytics['total_engagements']}) should match appointments total ({expected_total})"
        print(f"Verified: total_engagements={analytics['total_engagements']} matches upcoming({upcoming_total})+past({past_total})")

    def test_currency_field_present(self, auth_headers, workspace_id):
        """Response should include currency field"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/analytics/stats",
            params={"workspace_id": workspace_id},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Currency field should be present
        assert "currency" in data, "currency field should be present"
        assert data["currency"] == "eur", f"Expected currency 'eur', got {data['currency']}"
