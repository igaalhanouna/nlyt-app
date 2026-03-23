"""
Wallet API Tests — Phase 1 Stripe Connect
Tests for GET /api/wallet and GET /api/wallet/transactions endpoints.

Features tested:
- Wallet balance retrieval with correct fields
- Wallet auto-creation (idempotent ensure_wallet)
- Transaction history retrieval
- Auth required on all endpoints
- minimum_payout = 500 centimes (5€)
- can_payout logic (available_balance >= 500 AND stripe_connect_status == 'active')
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"


@pytest.fixture(scope="module")
def auth_session():
    """Create authenticated session for all tests"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    token = data.get("access_token")
    assert token, f"No access_token in response: {data}"
    session.headers.update({"Authorization": f"Bearer {token}"})
    
    return session


@pytest.fixture(scope="module")
def unauth_session():
    """Create unauthenticated session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestWalletAPI:
    """Wallet endpoint tests for Phase 1 Stripe Connect"""
    
    # ─── Health Check ───────────────────────────────────────────
    
    def test_health_check(self, unauth_session):
        """Verify backend is running"""
        response = unauth_session.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✅ Health check passed")
    
    # ─── Auth Required Tests ────────────────────────────────────
    
    def test_wallet_returns_401_without_auth(self, unauth_session):
        """GET /api/wallet returns 401 without auth token"""
        response = unauth_session.get(f"{BASE_URL}/api/wallet/")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("✅ GET /api/wallet returns 401 without auth")
    
    def test_wallet_transactions_returns_401_without_auth(self, unauth_session):
        """GET /api/wallet/transactions returns 401 without auth token"""
        response = unauth_session.get(f"{BASE_URL}/api/wallet/transactions")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("✅ GET /api/wallet/transactions returns 401 without auth")
    
    # ─── Wallet Endpoint Tests ──────────────────────────────────
    
    def test_wallet_returns_correct_fields(self, auth_session):
        """GET /api/wallet returns wallet with all required fields"""
        response = auth_session.get(f"{BASE_URL}/api/wallet/")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify all required fields are present
        required_fields = [
            "wallet_id",
            "available_balance",
            "pending_balance",
            "total_balance",
            "currency",
            "stripe_connect_status",
            "can_payout",
            "minimum_payout"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Verify field types
        assert isinstance(data["wallet_id"], str), "wallet_id should be string"
        assert isinstance(data["available_balance"], int), "available_balance should be int (centimes)"
        assert isinstance(data["pending_balance"], int), "pending_balance should be int (centimes)"
        assert isinstance(data["total_balance"], int), "total_balance should be int (centimes)"
        assert isinstance(data["currency"], str), "currency should be string"
        assert isinstance(data["stripe_connect_status"], str), "stripe_connect_status should be string"
        assert isinstance(data["can_payout"], bool), "can_payout should be boolean"
        assert isinstance(data["minimum_payout"], int), "minimum_payout should be int (centimes)"
        
        print(f"✅ GET /api/wallet returns all required fields: {list(data.keys())}")
    
    def test_wallet_minimum_payout_is_500(self, auth_session):
        """minimum_payout field equals 500 (5€ in centimes)"""
        response = auth_session.get(f"{BASE_URL}/api/wallet/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["minimum_payout"] == 500, f"Expected minimum_payout=500, got {data['minimum_payout']}"
        print("✅ minimum_payout equals 500 centimes (5€)")
    
    def test_wallet_total_balance_calculation(self, auth_session):
        """total_balance = available_balance + pending_balance"""
        response = auth_session.get(f"{BASE_URL}/api/wallet/")
        assert response.status_code == 200
        
        data = response.json()
        expected_total = data["available_balance"] + data["pending_balance"]
        assert data["total_balance"] == expected_total, \
            f"total_balance mismatch: {data['total_balance']} != {expected_total}"
        print(f"✅ total_balance ({data['total_balance']}) = available ({data['available_balance']}) + pending ({data['pending_balance']})")
    
    def test_wallet_can_payout_false_when_balance_zero(self, auth_session):
        """can_payout=false when balance is 0 and stripe_connect_status=not_started"""
        response = auth_session.get(f"{BASE_URL}/api/wallet/")
        assert response.status_code == 200
        
        data = response.json()
        
        # For a new wallet with 0 balance and not_started status, can_payout should be false
        if data["available_balance"] < 500 or data["stripe_connect_status"] != "active":
            assert data["can_payout"] == False, \
                f"can_payout should be False when balance < 500 or status != active. Got: {data}"
            print(f"✅ can_payout=False (balance={data['available_balance']}, status={data['stripe_connect_status']})")
        else:
            # If balance >= 500 and status is active, can_payout should be True
            assert data["can_payout"] == True, \
                f"can_payout should be True when balance >= 500 and status == active. Got: {data}"
            print(f"✅ can_payout=True (balance={data['available_balance']}, status={data['stripe_connect_status']})")
    
    def test_wallet_idempotent_same_wallet_id(self, auth_session):
        """Multiple calls to GET /api/wallet return the same wallet_id (idempotent)"""
        # First call
        response1 = auth_session.get(f"{BASE_URL}/api/wallet/")
        assert response1.status_code == 200
        wallet_id_1 = response1.json()["wallet_id"]
        
        # Second call
        response2 = auth_session.get(f"{BASE_URL}/api/wallet/")
        assert response2.status_code == 200
        wallet_id_2 = response2.json()["wallet_id"]
        
        # Third call
        response3 = auth_session.get(f"{BASE_URL}/api/wallet/")
        assert response3.status_code == 200
        wallet_id_3 = response3.json()["wallet_id"]
        
        assert wallet_id_1 == wallet_id_2 == wallet_id_3, \
            f"wallet_id should be same across calls: {wallet_id_1}, {wallet_id_2}, {wallet_id_3}"
        print(f"✅ Wallet is idempotent - same wallet_id returned: {wallet_id_1}")
    
    def test_wallet_currency_is_eur(self, auth_session):
        """Wallet currency should be EUR"""
        response = auth_session.get(f"{BASE_URL}/api/wallet/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["currency"] == "eur", f"Expected currency='eur', got {data['currency']}"
        print("✅ Wallet currency is EUR")
    
    # ─── Transactions Endpoint Tests ────────────────────────────
    
    def test_wallet_transactions_returns_correct_structure(self, auth_session):
        """GET /api/wallet/transactions returns transactions array with total count"""
        response = auth_session.get(f"{BASE_URL}/api/wallet/transactions")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify required fields
        assert "transactions" in data, "Missing 'transactions' field"
        assert "total" in data, "Missing 'total' field"
        assert "limit" in data, "Missing 'limit' field"
        assert "skip" in data, "Missing 'skip' field"
        
        # Verify types
        assert isinstance(data["transactions"], list), "transactions should be a list"
        assert isinstance(data["total"], int), "total should be int"
        assert isinstance(data["limit"], int), "limit should be int"
        assert isinstance(data["skip"], int), "skip should be int"
        
        print(f"✅ GET /api/wallet/transactions returns correct structure (total={data['total']}, limit={data['limit']})")
    
    def test_wallet_transactions_pagination_params(self, auth_session):
        """GET /api/wallet/transactions respects limit and skip params"""
        # Test with custom limit
        response = auth_session.get(f"{BASE_URL}/api/wallet/transactions?limit=10&skip=0")
        assert response.status_code == 200
        
        data = response.json()
        assert data["limit"] == 10, f"Expected limit=10, got {data['limit']}"
        assert data["skip"] == 0, f"Expected skip=0, got {data['skip']}"
        
        print("✅ Transactions endpoint respects pagination params")
    
    def test_wallet_transactions_limit_capped_at_100(self, auth_session):
        """GET /api/wallet/transactions caps limit at 100"""
        # Request with limit > 100
        response = auth_session.get(f"{BASE_URL}/api/wallet/transactions?limit=200")
        assert response.status_code == 200
        
        data = response.json()
        assert data["limit"] == 100, f"Expected limit capped at 100, got {data['limit']}"
        
        print("✅ Transactions limit is capped at 100")
    
    # ─── Login Endpoint Test ────────────────────────────────────
    
    def test_login_returns_access_token(self, unauth_session):
        """POST /api/auth/login returns access_token (not token)"""
        response = unauth_session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        
        data = response.json()
        # Login returns access_token directly (no success field)
        assert "access_token" in data, f"Expected 'access_token' in response, got: {list(data.keys())}"
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0
        assert "user" in data, "Expected 'user' in response"
        
        print("✅ Login returns access_token correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
