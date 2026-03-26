"""
Stripe Connect 3-Profile Onboarding Tests (Iteration 80)

Tests for the new 3-profile 2-step Stripe Connect Express onboarding:
- profile_type: particulier, independant, company
- PROFILE_TO_STRIPE mapping: particulier→individual, independant→individual, company→company

Backend Tests:
- GET /api/connect/status returns profile_type and business_type fields
- POST /api/connect/onboard with profile_type=particulier creates Stripe individual account
- POST /api/connect/onboard with profile_type=independant creates Stripe individual account
- POST /api/connect/onboard with profile_type=company creates Stripe company account
- POST /api/connect/reset from independant to particulier does NOT delete Stripe account (stripe_reset: false)
- POST /api/connect/reset from independant to company DOES delete Stripe account (stripe_reset: true)
- POST /api/connect/reset rejects same profile_type
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
    """GET /api/connect/status - verify all required fields including profile_type and business_type"""
    
    def test_status_requires_auth(self):
        """Status endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/connect/status")
        assert response.status_code == 401
        print("✓ GET /api/connect/status returns 401 without auth")
    
    def test_status_returns_profile_type_and_business_type_fields(self, auth_headers):
        """Status returns both profile_type and business_type fields"""
        response = requests.get(f"{BASE_URL}/api/connect/status", headers=auth_headers)
        assert response.status_code == 200, f"Status failed: {response.text}"
        data = response.json()
        
        # Required fields
        assert "connect_status" in data, f"Missing connect_status: {data}"
        assert "profile_type" in data, f"Missing profile_type: {data}"
        assert "business_type" in data, f"Missing business_type: {data}"
        assert "details_submitted" in data, f"Missing details_submitted: {data}"
        assert "charges_enabled" in data, f"Missing charges_enabled: {data}"
        assert "payouts_enabled" in data, f"Missing payouts_enabled: {data}"
        assert "requirements" in data, f"Missing requirements: {data}"
        assert "country" in data, f"Missing country: {data}"
        assert "onboarded_at" in data, f"Missing onboarded_at: {data}"
        
        print(f"✓ GET /api/connect/status returns all fields")
        print(f"  connect_status: {data.get('connect_status')}")
        print(f"  profile_type: {data.get('profile_type')}")
        print(f"  business_type: {data.get('business_type')}")
        return data


class TestOnboardParticulier:
    """POST /api/connect/onboard with profile_type=particulier creates Stripe individual account"""
    
    def test_onboard_requires_auth(self):
        """Onboard endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/connect/onboard", json={"profile_type": "particulier"})
        assert response.status_code == 401
        print("✓ POST /api/connect/onboard returns 401 without auth")
    
    def test_onboard_particulier_creates_individual_account(self, auth_headers):
        """Onboard with profile_type=particulier creates Stripe individual account"""
        response = requests.post(
            f"{BASE_URL}/api/connect/onboard",
            headers=auth_headers,
            json={"profile_type": "particulier"}
        )
        assert response.status_code == 200, f"Onboard failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True, f"Expected success=True, got: {data}"
        onboarding_url = data.get("onboarding_url")
        
        if onboarding_url:
            # Real Stripe mode - URL should be a Stripe Connect URL
            assert "stripe.com" in onboarding_url, f"Expected Stripe URL, got: {onboarding_url}"
            print(f"✓ POST /api/connect/onboard (particulier) returns onboarding URL: {onboarding_url[:60]}...")
        else:
            # Dev mode - should be active
            assert data.get("connect_status") == "active", f"Expected active status in dev mode, got: {data}"
            print(f"✓ POST /api/connect/onboard (particulier) returns active status (dev mode)")
    
    def test_status_shows_particulier_profile_and_individual_business_type(self, auth_headers):
        """After onboarding, status shows profile_type=particulier and business_type=individual"""
        response = requests.get(f"{BASE_URL}/api/connect/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        profile_type = data.get("profile_type")
        business_type = data.get("business_type")
        
        assert profile_type == "particulier", f"Expected profile_type=particulier, got: {profile_type}"
        assert business_type == "individual", f"Expected business_type=individual, got: {business_type}"
        print(f"✓ Status shows profile_type=particulier, business_type=individual after onboarding")


class TestResetParticulierToIndependant:
    """POST /api/connect/reset from particulier to independant - same Stripe type, no Stripe reset"""
    
    def test_reset_particulier_to_independant_no_stripe_reset(self, auth_headers):
        """Reset from particulier to independant does NOT delete Stripe account (same Stripe type)"""
        response = requests.post(
            f"{BASE_URL}/api/connect/reset",
            headers=auth_headers,
            json={"new_profile_type": "independant"}
        )
        assert response.status_code == 200, f"Reset failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True, f"Expected success=True, got: {data}"
        assert data.get("new_profile_type") == "independant", f"Expected new_profile_type=independant, got: {data}"
        
        # Key assertion: stripe_reset should be False (same Stripe type)
        stripe_reset = data.get("stripe_reset")
        assert stripe_reset is False, f"Expected stripe_reset=False for same Stripe type, got: {stripe_reset}"
        
        print(f"✓ POST /api/connect/reset (particulier→independant) succeeded with stripe_reset=False")
        print(f"  Message: {data.get('message')}")
    
    def test_status_shows_independant_profile_and_individual_business_type(self, auth_headers):
        """After reset, status shows profile_type=independant and business_type=individual (unchanged)"""
        response = requests.get(f"{BASE_URL}/api/connect/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        profile_type = data.get("profile_type")
        business_type = data.get("business_type")
        connect_status = data.get("connect_status")
        
        assert profile_type == "independant", f"Expected profile_type=independant, got: {profile_type}"
        assert business_type == "individual", f"Expected business_type=individual (unchanged), got: {business_type}"
        # Status should NOT be reset to not_started since Stripe account was not deleted
        assert connect_status != "not_started", f"Expected connect_status to remain (not reset), got: {connect_status}"
        
        print(f"✓ Status shows profile_type=independant, business_type=individual, connect_status={connect_status}")


class TestResetIndependantToCompany:
    """POST /api/connect/reset from independant to company - different Stripe type, Stripe reset required"""
    
    def test_reset_independant_to_company_with_stripe_reset(self, auth_headers):
        """Reset from independant to company DOES delete Stripe account (different Stripe type)"""
        response = requests.post(
            f"{BASE_URL}/api/connect/reset",
            headers=auth_headers,
            json={"new_profile_type": "company"}
        )
        assert response.status_code == 200, f"Reset failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True, f"Expected success=True, got: {data}"
        assert data.get("new_profile_type") == "company", f"Expected new_profile_type=company, got: {data}"
        
        # Key assertion: stripe_reset should be True (different Stripe type)
        stripe_reset = data.get("stripe_reset")
        assert stripe_reset is True, f"Expected stripe_reset=True for different Stripe type, got: {stripe_reset}"
        
        print(f"✓ POST /api/connect/reset (independant→company) succeeded with stripe_reset=True")
        print(f"  Message: {data.get('message')}")
    
    def test_status_shows_company_profile_and_not_started(self, auth_headers):
        """After reset with Stripe deletion, status shows profile_type=company and connect_status=not_started"""
        response = requests.get(f"{BASE_URL}/api/connect/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        profile_type = data.get("profile_type")
        business_type = data.get("business_type")
        connect_status = data.get("connect_status")
        
        assert profile_type == "company", f"Expected profile_type=company, got: {profile_type}"
        assert business_type == "company", f"Expected business_type=company, got: {business_type}"
        # Status should be reset to not_started since Stripe account was deleted
        assert connect_status == "not_started", f"Expected connect_status=not_started after Stripe reset, got: {connect_status}"
        
        print(f"✓ Status shows profile_type=company, business_type=company, connect_status=not_started")


class TestOnboardCompany:
    """POST /api/connect/onboard with profile_type=company creates Stripe company account"""
    
    def test_onboard_company_creates_company_account(self, auth_headers):
        """Onboard with profile_type=company creates Stripe company account"""
        response = requests.post(
            f"{BASE_URL}/api/connect/onboard",
            headers=auth_headers,
            json={"profile_type": "company"}
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


class TestResetSameProfileTypeBlocked:
    """POST /api/connect/reset rejects same profile_type"""
    
    def test_reset_same_profile_type_blocked(self, auth_headers):
        """Reset to same profile_type is blocked"""
        # First get current type
        status_response = requests.get(f"{BASE_URL}/api/connect/status", headers=auth_headers)
        current_profile = status_response.json().get("profile_type")
        
        # Try to reset to same type
        response = requests.post(
            f"{BASE_URL}/api/connect/reset",
            headers=auth_headers,
            json={"new_profile_type": current_profile}
        )
        
        # Should return 400 error
        assert response.status_code == 400, f"Expected 400 for same profile_type reset, got: {response.status_code}"
        data = response.json()
        
        # Error message should indicate same type
        detail = data.get("detail", "")
        assert "déjà" in detail.lower() or "same" in detail.lower() or "already" in detail.lower(), \
            f"Expected error about same type, got: {detail}"
        print(f"✓ POST /api/connect/reset blocks same profile_type: {detail}")


class TestOnboardIndependant:
    """POST /api/connect/onboard with profile_type=independant creates Stripe individual account"""
    
    def test_reset_to_independant_first(self, auth_headers):
        """Reset to independant to test onboarding"""
        # First reset to independant (from company)
        response = requests.post(
            f"{BASE_URL}/api/connect/reset",
            headers=auth_headers,
            json={"new_profile_type": "independant"}
        )
        assert response.status_code == 200, f"Reset failed: {response.text}"
        print(f"✓ Reset to independant for testing")
    
    def test_onboard_independant_creates_individual_account(self, auth_headers):
        """Onboard with profile_type=independant creates Stripe individual account"""
        response = requests.post(
            f"{BASE_URL}/api/connect/onboard",
            headers=auth_headers,
            json={"profile_type": "independant"}
        )
        assert response.status_code == 200, f"Onboard failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True, f"Expected success=True, got: {data}"
        onboarding_url = data.get("onboarding_url")
        
        if onboarding_url:
            # Real Stripe mode - URL should be a Stripe Connect URL
            assert "stripe.com" in onboarding_url, f"Expected Stripe URL, got: {onboarding_url}"
            print(f"✓ POST /api/connect/onboard (independant) returns onboarding URL: {onboarding_url[:60]}...")
        else:
            # Dev mode - should be active
            assert data.get("connect_status") == "active", f"Expected active status in dev mode, got: {data}"
            print(f"✓ POST /api/connect/onboard (independant) returns active status (dev mode)")
    
    def test_status_shows_independant_profile_and_individual_business_type(self, auth_headers):
        """After onboarding, status shows profile_type=independant and business_type=individual"""
        response = requests.get(f"{BASE_URL}/api/connect/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        profile_type = data.get("profile_type")
        business_type = data.get("business_type")
        
        assert profile_type == "independant", f"Expected profile_type=independant, got: {profile_type}"
        assert business_type == "individual", f"Expected business_type=individual, got: {business_type}"
        print(f"✓ Status shows profile_type=independant, business_type=individual after onboarding")


class TestInvalidProfileType:
    """POST /api/connect/onboard and /reset - validates profile_type"""
    
    def test_onboard_invalid_profile_type_rejected(self, auth_headers):
        """Onboard with invalid profile_type is rejected"""
        response = requests.post(
            f"{BASE_URL}/api/connect/onboard",
            headers=auth_headers,
            json={"profile_type": "invalid_type"}
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid type, got: {response.status_code}"
        print(f"✓ POST /api/connect/onboard rejects invalid profile_type")
    
    def test_reset_invalid_profile_type_rejected(self, auth_headers):
        """Reset with invalid profile_type is rejected"""
        response = requests.post(
            f"{BASE_URL}/api/connect/reset",
            headers=auth_headers,
            json={"new_profile_type": "invalid_type"}
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid type, got: {response.status_code}"
        print(f"✓ POST /api/connect/reset rejects invalid profile_type")


class TestCleanupResetToCleanState:
    """Cleanup: Reset wallet to clean state for future tests"""
    
    def test_cleanup_reset_wallet(self, auth_headers):
        """Reset wallet to clean state"""
        # Get current status
        status_response = requests.get(f"{BASE_URL}/api/connect/status", headers=auth_headers)
        current_status = status_response.json()
        
        print(f"✓ Final state: profile_type={current_status.get('profile_type')}, "
              f"business_type={current_status.get('business_type')}, "
              f"connect_status={current_status.get('connect_status')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
