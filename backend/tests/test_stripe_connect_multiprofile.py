"""
Stripe Connect Multi-Profile Onboarding Tests

Tests for multi-profile Stripe Connect Express onboarding:
- GET /api/connect/status returns correct fields including business_type
- POST /api/connect/onboard with business_type=individual creates Stripe Express account
- POST /api/connect/onboard with business_type=company creates Stripe Express account
- POST /api/connect/reset changes business_type and deletes old Stripe account
- POST /api/connect/reset blocks if same business_type requested
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials - clean wallet state user
TEST_EMAIL = "stripe-test@nlyt.io"
TEST_PASSWORD = "Test123!"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    token = data.get("access_token")
    assert token, f"No access_token in response: {data}"
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestHealthCheck:
    """Basic health check"""
    
    def test_health_endpoint(self):
        """Health check returns 200"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✓ Health check passed")


class TestConnectStatusFields:
    """GET /api/connect/status - verify all required fields including business_type"""
    
    def test_status_requires_auth(self):
        """Status endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/connect/status")
        assert response.status_code == 401
        print("✓ GET /api/connect/status returns 401 without auth")
    
    def test_status_returns_business_type_field(self, auth_headers):
        """Status returns business_type field"""
        response = requests.get(f"{BASE_URL}/api/connect/status", headers=auth_headers)
        assert response.status_code == 200, f"Status failed: {response.text}"
        data = response.json()
        
        # Required fields
        assert "connect_status" in data, f"Missing connect_status: {data}"
        assert "business_type" in data, f"Missing business_type: {data}"
        assert "details_submitted" in data, f"Missing details_submitted: {data}"
        assert "charges_enabled" in data, f"Missing charges_enabled: {data}"
        assert "payouts_enabled" in data, f"Missing payouts_enabled: {data}"
        assert "requirements" in data, f"Missing requirements: {data}"
        assert "country" in data, f"Missing country: {data}"
        assert "onboarded_at" in data, f"Missing onboarded_at: {data}"
        
        print(f"✓ GET /api/connect/status returns all fields including business_type: {data.get('business_type')}")
        print(f"  connect_status: {data.get('connect_status')}")
        return data


class TestConnectOnboardIndividual:
    """POST /api/connect/onboard with business_type=individual"""
    
    def test_onboard_requires_auth(self):
        """Onboard endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/connect/onboard", json={"business_type": "individual"})
        assert response.status_code == 401
        print("✓ POST /api/connect/onboard returns 401 without auth")
    
    def test_onboard_individual_creates_account(self, auth_headers):
        """Onboard with business_type=individual creates Stripe Express account"""
        response = requests.post(
            f"{BASE_URL}/api/connect/onboard",
            headers=auth_headers,
            json={"business_type": "individual"}
        )
        assert response.status_code == 200, f"Onboard failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True, f"Expected success=True, got: {data}"
        # Real Stripe returns onboarding_url, dev mode returns active status
        onboarding_url = data.get("onboarding_url")
        
        if onboarding_url:
            # Real Stripe mode - URL should be a Stripe Connect URL
            assert "stripe.com" in onboarding_url, f"Expected Stripe URL, got: {onboarding_url}"
            print(f"✓ POST /api/connect/onboard (individual) returns onboarding URL: {onboarding_url[:60]}...")
        else:
            # Dev mode - should be active
            assert data.get("connect_status") == "active", f"Expected active status in dev mode, got: {data}"
            print(f"✓ POST /api/connect/onboard (individual) returns active status (dev mode)")
    
    def test_status_shows_individual_type(self, auth_headers):
        """After onboarding, status shows business_type=individual"""
        response = requests.get(f"{BASE_URL}/api/connect/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # business_type should be set to individual
        business_type = data.get("business_type")
        assert business_type == "individual", f"Expected business_type=individual, got: {business_type}"
        print(f"✓ Status shows business_type=individual after onboarding")


class TestConnectResetToCompany:
    """POST /api/connect/reset - change from individual to company"""
    
    def test_reset_requires_auth(self):
        """Reset endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/connect/reset", json={"new_business_type": "company"})
        assert response.status_code == 401
        print("✓ POST /api/connect/reset returns 401 without auth")
    
    def test_reset_to_company_succeeds(self, auth_headers):
        """Reset from individual to company succeeds"""
        response = requests.post(
            f"{BASE_URL}/api/connect/reset",
            headers=auth_headers,
            json={"new_business_type": "company"}
        )
        assert response.status_code == 200, f"Reset failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True, f"Expected success=True, got: {data}"
        assert data.get("new_business_type") == "company", f"Expected new_business_type=company, got: {data}"
        print(f"✓ POST /api/connect/reset to company succeeded: {data.get('message')}")
    
    def test_status_shows_company_type_after_reset(self, auth_headers):
        """After reset, status shows business_type=company and not_started"""
        response = requests.get(f"{BASE_URL}/api/connect/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        business_type = data.get("business_type")
        connect_status = data.get("connect_status")
        
        assert business_type == "company", f"Expected business_type=company, got: {business_type}"
        assert connect_status == "not_started", f"Expected connect_status=not_started after reset, got: {connect_status}"
        print(f"✓ Status shows business_type=company and connect_status=not_started after reset")


class TestConnectOnboardCompany:
    """POST /api/connect/onboard with business_type=company"""
    
    def test_onboard_company_creates_account(self, auth_headers):
        """Onboard with business_type=company creates Stripe Express account"""
        response = requests.post(
            f"{BASE_URL}/api/connect/onboard",
            headers=auth_headers,
            json={"business_type": "company"}
        )
        assert response.status_code == 200, f"Onboard failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True, f"Expected success=True, got: {data}"
        onboarding_url = data.get("onboarding_url")
        
        if onboarding_url:
            # Real Stripe mode - URL should be a Stripe Connect URL
            assert "stripe.com" in onboarding_url, f"Expected Stripe URL, got: {onboarding_url}"
            print(f"✓ POST /api/connect/onboard (company) returns onboarding URL: {onboarding_url[:60]}...")
        else:
            # Dev mode - should be active
            assert data.get("connect_status") == "active", f"Expected active status in dev mode, got: {data}"
            print(f"✓ POST /api/connect/onboard (company) returns active status (dev mode)")


class TestConnectResetBlocksSameType:
    """POST /api/connect/reset - blocks if same business_type requested"""
    
    def test_reset_same_type_blocked(self, auth_headers):
        """Reset to same business_type is blocked"""
        # First get current type
        status_response = requests.get(f"{BASE_URL}/api/connect/status", headers=auth_headers)
        current_type = status_response.json().get("business_type")
        
        # Try to reset to same type
        response = requests.post(
            f"{BASE_URL}/api/connect/reset",
            headers=auth_headers,
            json={"new_business_type": current_type}
        )
        
        # Should return 400 error
        assert response.status_code == 400, f"Expected 400 for same type reset, got: {response.status_code}"
        data = response.json()
        
        # Error message should indicate same type
        detail = data.get("detail", "")
        assert "déjà" in detail.lower() or "same" in detail.lower() or "already" in detail.lower(), \
            f"Expected error about same type, got: {detail}"
        print(f"✓ POST /api/connect/reset blocks same type: {detail}")


class TestConnectResetInvalidType:
    """POST /api/connect/reset - validates business_type"""
    
    def test_reset_invalid_type_rejected(self, auth_headers):
        """Reset with invalid business_type is rejected"""
        response = requests.post(
            f"{BASE_URL}/api/connect/reset",
            headers=auth_headers,
            json={"new_business_type": "invalid_type"}
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid type, got: {response.status_code}"
        print(f"✓ POST /api/connect/reset rejects invalid business_type")


class TestConnectOnboardInvalidType:
    """POST /api/connect/onboard - validates business_type"""
    
    def test_onboard_invalid_type_rejected(self, auth_headers):
        """Onboard with invalid business_type is rejected"""
        response = requests.post(
            f"{BASE_URL}/api/connect/onboard",
            headers=auth_headers,
            json={"business_type": "invalid_type"}
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid type, got: {response.status_code}"
        print(f"✓ POST /api/connect/onboard rejects invalid business_type")


class TestCleanupResetToIndividual:
    """Cleanup: Reset back to individual for clean state"""
    
    def test_reset_back_to_individual(self, auth_headers):
        """Reset back to individual for clean state"""
        # Get current status
        status_response = requests.get(f"{BASE_URL}/api/connect/status", headers=auth_headers)
        current_type = status_response.json().get("business_type")
        
        if current_type != "individual":
            response = requests.post(
                f"{BASE_URL}/api/connect/reset",
                headers=auth_headers,
                json={"new_business_type": "individual"}
            )
            if response.status_code == 200:
                print(f"✓ Cleanup: Reset back to individual")
            else:
                print(f"⚠ Cleanup: Could not reset to individual: {response.text}")
        else:
            print(f"✓ Cleanup: Already individual, no reset needed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
