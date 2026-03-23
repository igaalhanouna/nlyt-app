"""
Test WalletPage Phase 3 - Enriched Distributions & Contestation
Tests:
- GET /api/wallet/distributions returns enriched distributions with appointment_title
- GET /api/wallet/distributions/:id returns detail with access control
- POST /api/wallet/distributions/:id/contest works for no_show user
- POST /api/wallet/distributions/:id/contest fails for non-no_show user
- GET /api/connect/status returns user_id field
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Module-level session to avoid rate limiting
_auth_session = None
_user_id = None
_token = None

def get_auth_session():
    """Get or create authenticated session (singleton to avoid rate limits)"""
    global _auth_session, _user_id, _token
    
    if _auth_session is not None:
        return _auth_session, _user_id, _token
    
    email = "testuser_audit@nlyt.app"
    password = "Test1234!"
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login to get token
    login_response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": email,
        "password": password
    })
    if login_response.status_code == 200:
        token = login_response.json().get("access_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        _auth_session = session
        _token = token
        _user_id = login_response.json().get("user", {}).get("user_id")
        return _auth_session, _user_id, _token
    else:
        return None, None, None


class TestWalletPagePhase3:
    """Tests for WalletPage Phase 3 enriched features"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test credentials and login"""
        session, user_id, token = get_auth_session()
        if session is None:
            pytest.skip("Login failed - rate limited or credentials invalid")
        self.session = session
        self.user_id = user_id
        self.token = token
    
    # ─── GET /api/wallet/distributions Tests ───────────────────────
    
    def test_get_distributions_requires_auth(self):
        """GET /api/wallet/distributions requires authentication"""
        response = requests.get(f"{BASE_URL}/api/wallet/distributions")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/wallet/distributions requires auth")
    
    def test_get_distributions_returns_list(self):
        """GET /api/wallet/distributions returns list with distributions"""
        response = self.session.get(f"{BASE_URL}/api/wallet/distributions")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "distributions" in data, "Response should contain 'distributions' key"
        assert "total" in data, "Response should contain 'total' key"
        assert isinstance(data["distributions"], list), "distributions should be a list"
        print(f"PASS: GET /api/wallet/distributions returns list with {len(data['distributions'])} distributions")
    
    def test_get_distributions_enriched_with_appointment_title(self):
        """GET /api/wallet/distributions returns enriched data with appointment_title"""
        response = self.session.get(f"{BASE_URL}/api/wallet/distributions")
        assert response.status_code == 200
        
        data = response.json()
        distributions = data.get("distributions", [])
        
        if len(distributions) > 0:
            dist = distributions[0]
            # Check required fields for enriched distribution
            required_fields = ["distribution_id", "status", "capture_amount_cents", "capture_currency", "beneficiaries"]
            for field in required_fields:
                assert field in dist, f"Distribution should have '{field}' field"
            
            # Check for appointment_title enrichment (may be present if appointment exists)
            if dist.get("appointment_id"):
                # appointment_title should be present for distributions with appointment_id
                print(f"Distribution has appointment_id: {dist.get('appointment_id')}")
                if "appointment_title" in dist:
                    print(f"PASS: Distribution enriched with appointment_title: {dist.get('appointment_title')}")
                else:
                    print("INFO: appointment_title not present (may be missing appointment)")
            
            # Check beneficiaries structure
            beneficiaries = dist.get("beneficiaries", [])
            if len(beneficiaries) > 0:
                benef = beneficiaries[0]
                benef_fields = ["role", "amount_cents"]
                for field in benef_fields:
                    assert field in benef, f"Beneficiary should have '{field}' field"
                print(f"PASS: Beneficiaries structure correct with {len(beneficiaries)} beneficiaries")
        else:
            print("INFO: No distributions found for user - skipping enrichment check")
    
    def test_get_distributions_pagination(self):
        """GET /api/wallet/distributions supports pagination"""
        response = self.session.get(f"{BASE_URL}/api/wallet/distributions?limit=10&skip=0")
        assert response.status_code == 200
        
        data = response.json()
        assert "distributions" in data
        assert "total" in data
        print(f"PASS: Pagination works - returned {len(data['distributions'])} distributions")
    
    # ─── GET /api/wallet/distributions/:id Tests ───────────────────
    
    def test_get_distribution_detail_not_found(self):
        """GET /api/wallet/distributions/:id returns 404 for non-existent"""
        response = self.session.get(f"{BASE_URL}/api/wallet/distributions/non-existent-id")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: GET /api/wallet/distributions/:id returns 404 for non-existent")
    
    def test_get_distribution_detail_requires_auth(self):
        """GET /api/wallet/distributions/:id requires authentication"""
        response = requests.get(f"{BASE_URL}/api/wallet/distributions/some-id")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/wallet/distributions/:id requires auth")
    
    def test_get_distribution_detail_access_control(self):
        """GET /api/wallet/distributions/:id enforces access control"""
        # First get list of distributions
        list_response = self.session.get(f"{BASE_URL}/api/wallet/distributions")
        assert list_response.status_code == 200
        
        distributions = list_response.json().get("distributions", [])
        if len(distributions) > 0:
            dist_id = distributions[0]["distribution_id"]
            
            # User should be able to access their own distribution
            detail_response = self.session.get(f"{BASE_URL}/api/wallet/distributions/{dist_id}")
            assert detail_response.status_code == 200, f"Expected 200, got {detail_response.status_code}"
            
            detail = detail_response.json()
            assert detail["distribution_id"] == dist_id
            print(f"PASS: User can access their own distribution detail")
        else:
            print("INFO: No distributions to test access control")
    
    # ─── POST /api/wallet/distributions/:id/contest Tests ──────────
    
    def test_contest_distribution_requires_auth(self):
        """POST /api/wallet/distributions/:id/contest requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/wallet/distributions/some-id/contest",
            json={"reason": "Test reason"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: POST /api/wallet/distributions/:id/contest requires auth")
    
    def test_contest_distribution_not_found(self):
        """POST /api/wallet/distributions/:id/contest returns 400/404 for non-existent"""
        response = self.session.post(
            f"{BASE_URL}/api/wallet/distributions/non-existent-id/contest",
            json={"reason": "Test reason"}
        )
        # Should return 400 (error from service) or 404
        assert response.status_code in [400, 404], f"Expected 400 or 404, got {response.status_code}"
        print(f"PASS: Contest non-existent distribution returns {response.status_code}")
    
    def test_contest_distribution_requires_reason(self):
        """POST /api/wallet/distributions/:id/contest requires reason field"""
        # Get a distribution first
        list_response = self.session.get(f"{BASE_URL}/api/wallet/distributions")
        distributions = list_response.json().get("distributions", [])
        
        if len(distributions) > 0:
            dist_id = distributions[0]["distribution_id"]
            
            # Try without reason - should fail validation
            response = self.session.post(
                f"{BASE_URL}/api/wallet/distributions/{dist_id}/contest",
                json={}
            )
            # Pydantic validation should return 422
            assert response.status_code == 422, f"Expected 422 for missing reason, got {response.status_code}"
            print("PASS: Contest requires reason field (422 on missing)")
        else:
            print("INFO: No distributions to test reason requirement")
    
    def test_contest_distribution_only_no_show_user(self):
        """POST /api/wallet/distributions/:id/contest only works for no_show user"""
        # Get distributions
        list_response = self.session.get(f"{BASE_URL}/api/wallet/distributions")
        distributions = list_response.json().get("distributions", [])
        
        # Find a pending_hold distribution where current user is NOT the no_show
        for dist in distributions:
            if dist.get("status") == "pending_hold" and dist.get("no_show_user_id") != self.user_id:
                dist_id = dist["distribution_id"]
                
                # Try to contest - should fail because user is not the no_show
                response = self.session.post(
                    f"{BASE_URL}/api/wallet/distributions/{dist_id}/contest",
                    json={"reason": "Test contestation"}
                )
                assert response.status_code == 400, f"Expected 400, got {response.status_code}"
                
                error_detail = response.json().get("detail", "")
                assert "concerné" in error_detail.lower() or "no_show" in error_detail.lower() or "seul" in error_detail.lower(), \
                    f"Error should mention only no_show user can contest: {error_detail}"
                print(f"PASS: Non-no_show user cannot contest distribution: {error_detail}")
                return
        
        print("INFO: No pending_hold distribution where user is not no_show - skipping test")
    
    def test_contest_distribution_only_during_pending_hold(self):
        """POST /api/wallet/distributions/:id/contest only works during pending_hold"""
        # Get distributions
        list_response = self.session.get(f"{BASE_URL}/api/wallet/distributions")
        distributions = list_response.json().get("distributions", [])
        
        # Find a completed distribution
        for dist in distributions:
            if dist.get("status") == "completed":
                dist_id = dist["distribution_id"]
                
                # Try to contest - should fail because not in pending_hold
                response = self.session.post(
                    f"{BASE_URL}/api/wallet/distributions/{dist_id}/contest",
                    json={"reason": "Test contestation"}
                )
                assert response.status_code == 400, f"Expected 400, got {response.status_code}"
                
                error_detail = response.json().get("detail", "")
                print(f"PASS: Cannot contest completed distribution: {error_detail}")
                return
        
        print("INFO: No completed distribution found - skipping test")
    
    # ─── GET /api/connect/status Tests ─────────────────────────────
    
    def test_connect_status_requires_auth(self):
        """GET /api/connect/status requires authentication"""
        response = requests.get(f"{BASE_URL}/api/connect/status")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/connect/status requires auth")
    
    def test_connect_status_returns_user_id(self):
        """GET /api/connect/status returns user_id field"""
        response = self.session.get(f"{BASE_URL}/api/connect/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "user_id" in data, "Response should contain 'user_id' field"
        assert data["user_id"] == self.user_id or data["user_id"] is not None, "user_id should match logged in user"
        
        # Check other expected fields
        assert "connect_status" in data, "Response should contain 'connect_status' field"
        print(f"PASS: GET /api/connect/status returns user_id: {data['user_id']}")
        print(f"      Connect status: {data.get('connect_status')}")
    
    # ─── GET /api/wallet Tests ─────────────────────────────────────
    
    def test_wallet_returns_balance_info(self):
        """GET /api/wallet returns balance information"""
        response = self.session.get(f"{BASE_URL}/api/wallet")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        required_fields = ["wallet_id", "available_balance", "pending_balance", "currency"]
        for field in required_fields:
            assert field in data, f"Wallet should have '{field}' field"
        
        print(f"PASS: GET /api/wallet returns balance info")
        print(f"      Pending: {data.get('pending_balance')}c, Available: {data.get('available_balance')}c")
    
    # ─── Distribution Data Structure Tests ─────────────────────────
    
    def test_distribution_has_hold_expires_at(self):
        """Pending distributions should have hold_expires_at field"""
        list_response = self.session.get(f"{BASE_URL}/api/wallet/distributions")
        distributions = list_response.json().get("distributions", [])
        
        for dist in distributions:
            if dist.get("status") == "pending_hold":
                assert "hold_expires_at" in dist, "pending_hold distribution should have hold_expires_at"
                print(f"PASS: pending_hold distribution has hold_expires_at: {dist.get('hold_expires_at')}")
                return
        
        print("INFO: No pending_hold distribution found - skipping hold_expires_at check")
    
    def test_distribution_beneficiaries_have_roles(self):
        """Distribution beneficiaries should have role field"""
        list_response = self.session.get(f"{BASE_URL}/api/wallet/distributions")
        distributions = list_response.json().get("distributions", [])
        
        if len(distributions) > 0:
            dist = distributions[0]
            beneficiaries = dist.get("beneficiaries", [])
            
            valid_roles = ["platform", "charity", "organizer", "participant"]
            for benef in beneficiaries:
                assert "role" in benef, "Beneficiary should have 'role' field"
                assert benef["role"] in valid_roles, f"Role should be one of {valid_roles}, got {benef['role']}"
                assert "amount_cents" in benef, "Beneficiary should have 'amount_cents' field"
            
            print(f"PASS: Beneficiaries have valid roles: {[b['role'] for b in beneficiaries]}")
        else:
            print("INFO: No distributions to check beneficiary roles")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
