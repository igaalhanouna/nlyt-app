"""
Test suite for safeFetchJson migration verification.
Tests that all API endpoints return valid JSON responses.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://litigation-mgmt.preview.emergentagent.com')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "TestAudit123!"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for protected endpoints."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert "access_token" in data
    return data["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    """Headers with authentication token."""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestLoginAPI:
    """Test POST /api/auth/login returns valid JSON."""
    
    def test_login_success(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == TEST_EMAIL
    
    def test_login_invalid_credentials(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "invalid@test.com", "password": "wrongpass"}
        )
        # Should return 401 with valid JSON error
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data


class TestTimelineAPI:
    """Test GET /api/appointments/my-timeline returns valid JSON."""
    
    def test_timeline_returns_json(self, auth_headers):
        response = requests.get(
            f"{BASE_URL}/api/appointments/my-timeline",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        # Timeline should have these keys
        assert "action_required" in data
        assert "upcoming" in data
        assert "past" in data
        assert "counts" in data


class TestUserSettingsAPI:
    """Test GET /api/user-settings/me returns valid JSON."""
    
    def test_user_settings_returns_json(self, auth_headers):
        response = requests.get(
            f"{BASE_URL}/api/user-settings/me",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        # User settings should have these keys
        assert "email" in data
        assert "first_name" in data
        assert "last_name" in data
    
    def test_appointment_defaults_returns_json(self, auth_headers):
        response = requests.get(
            f"{BASE_URL}/api/user-settings/me/appointment-defaults",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        # Should have platform commission
        assert "platform_commission_percent" in data


class TestInvitationRespondAPI:
    """Test POST /api/invitations/{token}/respond returns valid JSON even on error."""
    
    def test_invalid_token_returns_json_error(self):
        response = requests.post(
            f"{BASE_URL}/api/invitations/invalid-token-test/respond",
            json={"action": "accept"},
            headers={"Content-Type": "application/json"}
        )
        # Should return 404 with valid JSON
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


class TestCharityAssociationsAPI:
    """Test GET /api/charity-associations/ returns valid JSON."""
    
    def test_associations_list_returns_json(self):
        response = requests.get(f"{BASE_URL}/api/charity-associations/")
        assert response.status_code == 200
        data = response.json()
        assert "associations" in data
        assert isinstance(data["associations"], list)


class TestMicrosoftOAuthAPI:
    """Test GET /api/auth/microsoft/login returns valid JSON."""
    
    def test_microsoft_login_returns_json(self):
        response = requests.get(f"{BASE_URL}/api/auth/microsoft/login")
        assert response.status_code == 200
        data = response.json()
        assert "authorization_url" in data


class TestPaymentMethodAPI:
    """Test GET /api/user-settings/me/payment-method returns valid JSON."""
    
    def test_payment_method_returns_json(self, auth_headers):
        response = requests.get(
            f"{BASE_URL}/api/user-settings/me/payment-method",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "has_payment_method" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
