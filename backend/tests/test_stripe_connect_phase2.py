"""
Stripe Connect Phase 2 - Express Onboarding Tests

Tests for:
- POST /api/connect/onboard - Start/resume Connect Express onboarding (dev mode)
- GET /api/connect/status - Get Connect status details
- POST /api/connect/dashboard - Get Stripe Express dashboard link
- Webhook handlers existence verification (account.updated, account.application.deauthorized)
- Wallet integration with stripe_connect_status
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
    # Auth token field is 'access_token' not 'token'
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


class TestConnectOnboard:
    """POST /api/connect/onboard tests"""
    
    def test_onboard_requires_auth(self):
        """Onboard endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/connect/onboard")
        assert response.status_code == 401
        print("✓ POST /api/connect/onboard returns 401 without auth")
    
    def test_onboard_creates_simulated_account(self, auth_headers):
        """Onboard creates simulated active Connect account in dev mode"""
        response = requests.post(f"{BASE_URL}/api/connect/onboard", headers=auth_headers)
        assert response.status_code == 200, f"Onboard failed: {response.text}"
        data = response.json()
        
        # Dev mode should return success with active status
        assert data.get("success") is True, f"Expected success=True, got: {data}"
        assert data.get("connect_status") == "active", f"Expected active status, got: {data.get('connect_status')}"
        # Dev mode returns no onboarding_url (already active)
        assert data.get("onboarding_url") is None, f"Expected no onboarding_url in dev mode, got: {data.get('onboarding_url')}"
        # Dev mode message
        assert "[DEV MODE]" in data.get("message", "") or "déjà" in data.get("message", "").lower(), f"Expected dev mode or already active message, got: {data.get('message')}"
        print(f"✓ POST /api/connect/onboard returns simulated active account: {data.get('message')}")
    
    def test_onboard_is_idempotent(self, auth_headers):
        """Second onboard call doesn't create duplicate - returns same status"""
        # First call
        response1 = requests.post(f"{BASE_URL}/api/connect/onboard", headers=auth_headers)
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second call
        response2 = requests.post(f"{BASE_URL}/api/connect/onboard", headers=auth_headers)
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Both should return success with active status
        assert data1.get("success") is True
        assert data2.get("success") is True
        assert data1.get("connect_status") == data2.get("connect_status")
        print("✓ POST /api/connect/onboard is idempotent (no duplicate accounts)")


class TestConnectStatus:
    """GET /api/connect/status tests"""
    
    def test_status_requires_auth(self):
        """Status endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/connect/status")
        assert response.status_code == 401
        print("✓ GET /api/connect/status returns 401 without auth")
    
    def test_status_returns_full_details(self, auth_headers):
        """Status returns full Connect status details"""
        response = requests.get(f"{BASE_URL}/api/connect/status", headers=auth_headers)
        assert response.status_code == 200, f"Status failed: {response.text}"
        data = response.json()
        
        # Required fields
        assert "connect_status" in data, f"Missing connect_status: {data}"
        assert "details_submitted" in data, f"Missing details_submitted: {data}"
        assert "charges_enabled" in data, f"Missing charges_enabled: {data}"
        assert "payouts_enabled" in data, f"Missing payouts_enabled: {data}"
        assert "requirements" in data, f"Missing requirements: {data}"
        
        # After dev mode onboarding, should be active
        assert data.get("connect_status") == "active", f"Expected active status, got: {data.get('connect_status')}"
        assert data.get("details_submitted") is True, f"Expected details_submitted=True, got: {data.get('details_submitted')}"
        assert data.get("charges_enabled") is True, f"Expected charges_enabled=True, got: {data.get('charges_enabled')}"
        assert data.get("payouts_enabled") is True, f"Expected payouts_enabled=True, got: {data.get('payouts_enabled')}"
        
        print(f"✓ GET /api/connect/status returns full details: status={data.get('connect_status')}")


class TestConnectDashboard:
    """POST /api/connect/dashboard tests"""
    
    def test_dashboard_requires_auth(self):
        """Dashboard endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/connect/dashboard")
        assert response.status_code == 401
        print("✓ POST /api/connect/dashboard returns 401 without auth")
    
    def test_dashboard_returns_url_for_active_account(self, auth_headers):
        """Dashboard returns dev dashboard URL for active accounts"""
        response = requests.post(f"{BASE_URL}/api/connect/dashboard", headers=auth_headers)
        assert response.status_code == 200, f"Dashboard failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True, f"Expected success=True, got: {data}"
        assert "dashboard_url" in data, f"Missing dashboard_url: {data}"
        # Dev mode returns frontend URL with dev_dashboard param
        assert data.get("dashboard_url") is not None, f"Expected dashboard_url, got None"
        print(f"✓ POST /api/connect/dashboard returns URL: {data.get('dashboard_url')}")


class TestWalletConnectIntegration:
    """Wallet API integration with Connect status"""
    
    def test_wallet_includes_connect_status(self, auth_headers):
        """GET /api/wallet includes stripe_connect_status field"""
        response = requests.get(f"{BASE_URL}/api/wallet/", headers=auth_headers)
        assert response.status_code == 200, f"Wallet failed: {response.text}"
        data = response.json()
        
        assert "stripe_connect_status" in data, f"Missing stripe_connect_status: {data}"
        # After dev mode onboarding, should be active
        assert data.get("stripe_connect_status") == "active", f"Expected active, got: {data.get('stripe_connect_status')}"
        print(f"✓ GET /api/wallet includes stripe_connect_status: {data.get('stripe_connect_status')}")
    
    def test_wallet_can_payout_with_active_status(self, auth_headers):
        """can_payout depends on balance AND active status"""
        response = requests.get(f"{BASE_URL}/api/wallet/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        available = data.get("available_balance", 0)
        minimum = data.get("minimum_payout", 500)
        status = data.get("stripe_connect_status")
        can_payout = data.get("can_payout")
        
        # can_payout should be True only if balance >= minimum AND status == active
        expected_can_payout = (available >= minimum) and (status == "active")
        assert can_payout == expected_can_payout, f"can_payout mismatch: expected {expected_can_payout}, got {can_payout}"
        print(f"✓ can_payout logic correct: balance={available}, minimum={minimum}, status={status}, can_payout={can_payout}")


class TestWalletTransactions:
    """GET /api/wallet/transactions tests"""
    
    def test_transactions_returns_structure(self, auth_headers):
        """Transactions endpoint returns correct structure"""
        response = requests.get(f"{BASE_URL}/api/wallet/transactions", headers=auth_headers)
        assert response.status_code == 200, f"Transactions failed: {response.text}"
        data = response.json()
        
        assert "transactions" in data, f"Missing transactions: {data}"
        assert "total" in data, f"Missing total: {data}"
        assert "limit" in data, f"Missing limit: {data}"
        assert "skip" in data, f"Missing skip: {data}"
        assert isinstance(data.get("transactions"), list), f"transactions should be list: {data}"
        print(f"✓ GET /api/wallet/transactions returns correct structure: {len(data.get('transactions', []))} transactions")


class TestWebhookHandlersExist:
    """Verify webhook handlers exist in code (not live webhook testing)"""
    
    def test_webhook_endpoint_exists(self):
        """Webhook endpoint exists (will fail signature verification)"""
        # Send empty body - should fail with signature error, not 404
        response = requests.post(f"{BASE_URL}/api/webhooks/stripe", 
                                 headers={"Content-Type": "application/json"},
                                 json={})
        # Should return 400 (invalid signature) not 404 (not found)
        assert response.status_code in [400, 500], f"Unexpected status: {response.status_code}"
        print(f"✓ POST /api/webhooks/stripe endpoint exists (returns {response.status_code} for invalid request)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
