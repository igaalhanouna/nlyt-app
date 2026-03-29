"""
Test Decisions Feature - Iteration 139
Tests for:
- GET /api/disputes/decisions/mine - List resolved disputes with financial impact
- GET /api/disputes/{dispute_id} - Dispute detail with financial_context, declaration_summary
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
ADMIN_EMAIL = "testuser_audit@nlyt.app"
ADMIN_PASSWORD = "TestAudit123!"
USER_EMAIL = "igaal@hotmail.com"
USER_PASSWORD = "Test123!"

# Known dispute IDs from agent context
KNOWN_DISPUTE_IDS = [
    "ef842aec-cb81-4c4f-9b57-64cddeee4c17",
    "23f75310-958e-4597-baf8-cc3ea0c1470b",
    "e0c1b7a4-8d82-4759-81cf-b0e1092419e7",
    "01c6bd80-b2a7-43d5-8604-f371b5229db4",
    "619c6d07-d42f-46ea-8d8b-c64a26225ff5"
]


class TestDecisionsAPI:
    """Test the Decisions API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.admin_token = None
        self.user_token = None
    
    def login(self, email, password):
        """Login and return token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": password
        })
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        return None
    
    def test_01_login_admin_user(self):
        """Test admin user can login"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        self.admin_token = data["access_token"]
        print(f"PASS - Admin login successful, role={data.get('user', {}).get('role', 'N/A')}")
    
    def test_02_get_my_decisions_requires_auth(self):
        """Test that /api/disputes/decisions/mine requires authentication"""
        response = self.session.get(f"{BASE_URL}/api/disputes/decisions/mine")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS - /api/disputes/decisions/mine requires authentication")
    
    def test_03_get_my_decisions_returns_list(self):
        """Test GET /api/disputes/decisions/mine returns resolved disputes"""
        token = self.login(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token, "Failed to login"
        
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        response = self.session.get(f"{BASE_URL}/api/disputes/decisions/mine")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "decisions" in data, "Response missing 'decisions' field"
        assert "count" in data, "Response missing 'count' field"
        assert isinstance(data["decisions"], list), "decisions should be a list"
        
        print(f"PASS - GET /api/disputes/decisions/mine returns {data['count']} decisions")
        return data
    
    def test_04_decisions_have_required_fields(self):
        """Test that each decision has required fields"""
        token = self.login(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token, "Failed to login"
        
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        response = self.session.get(f"{BASE_URL}/api/disputes/decisions/mine")
        
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] == 0:
            pytest.skip("No decisions available to test")
        
        required_fields = [
            "dispute_id",
            "appointment_title",
            "final_outcome",
            "financial_impact",
            "my_role",
            "target_name",
            "resolved_at"
        ]
        
        for decision in data["decisions"]:
            for field in required_fields:
                assert field in decision, f"Decision missing required field: {field}"
            
            # Validate financial_impact structure
            fi = decision.get("financial_impact", {})
            assert "type" in fi, "financial_impact missing 'type'"
            assert "label" in fi, "financial_impact missing 'label'"
            assert fi["type"] in ["neutral", "credit", "debit"], f"Invalid financial_impact type: {fi['type']}"
        
        print(f"PASS - All {data['count']} decisions have required fields")
    
    def test_05_decisions_only_resolved_statuses(self):
        """Test that decisions only include resolved disputes"""
        token = self.login(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token, "Failed to login"
        
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        response = self.session.get(f"{BASE_URL}/api/disputes/decisions/mine")
        
        assert response.status_code == 200
        data = response.json()
        
        resolved_statuses = ["resolved", "agreed_present", "agreed_absent", "agreed_late_penalized"]
        
        for decision in data["decisions"]:
            status = decision.get("status")
            assert status in resolved_statuses, f"Decision has non-resolved status: {status}"
        
        print(f"PASS - All decisions have resolved status")
    
    def test_06_get_dispute_detail_requires_auth(self):
        """Test that /api/disputes/{id} requires authentication"""
        if not KNOWN_DISPUTE_IDS:
            pytest.skip("No known dispute IDs")
        
        response = self.session.get(f"{BASE_URL}/api/disputes/{KNOWN_DISPUTE_IDS[0]}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS - /api/disputes/{id} requires authentication")
    
    def test_07_get_dispute_detail_returns_data(self):
        """Test GET /api/disputes/{id} returns dispute detail"""
        token = self.login(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token, "Failed to login"
        
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # First get a valid dispute ID from decisions
        decisions_response = self.session.get(f"{BASE_URL}/api/disputes/decisions/mine")
        if decisions_response.status_code != 200 or decisions_response.json().get("count", 0) == 0:
            pytest.skip("No decisions available to test detail")
        
        dispute_id = decisions_response.json()["decisions"][0]["dispute_id"]
        
        response = self.session.get(f"{BASE_URL}/api/disputes/{dispute_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "dispute_id" in data, "Response missing dispute_id"
        assert data["dispute_id"] == dispute_id, "Dispute ID mismatch"
        
        print(f"PASS - GET /api/disputes/{dispute_id} returns dispute detail")
        return data
    
    def test_08_dispute_detail_has_financial_context(self):
        """Test that dispute detail includes financial_context"""
        token = self.login(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token, "Failed to login"
        
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get a valid dispute ID
        decisions_response = self.session.get(f"{BASE_URL}/api/disputes/decisions/mine")
        if decisions_response.status_code != 200 or decisions_response.json().get("count", 0) == 0:
            pytest.skip("No decisions available to test")
        
        dispute_id = decisions_response.json()["decisions"][0]["dispute_id"]
        response = self.session.get(f"{BASE_URL}/api/disputes/{dispute_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "financial_context" in data, "Response missing financial_context"
        fc = data["financial_context"]
        
        expected_fc_fields = [
            "penalty_amount",
            "penalty_currency",
            "platform_commission_percent",
            "charity_percent",
            "platform_amount",
            "charity_amount",
            "compensation_amount"
        ]
        
        for field in expected_fc_fields:
            assert field in fc, f"financial_context missing field: {field}"
        
        print(f"PASS - Dispute detail has financial_context with all required fields")
    
    def test_09_dispute_detail_has_declaration_summary(self):
        """Test that dispute detail includes declaration_summary"""
        token = self.login(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token, "Failed to login"
        
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get a valid dispute ID
        decisions_response = self.session.get(f"{BASE_URL}/api/disputes/decisions/mine")
        if decisions_response.status_code != 200 or decisions_response.json().get("count", 0) == 0:
            pytest.skip("No decisions available to test")
        
        dispute_id = decisions_response.json()["decisions"][0]["dispute_id"]
        response = self.session.get(f"{BASE_URL}/api/disputes/{dispute_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "declaration_summary" in data, "Response missing declaration_summary"
        ds = data["declaration_summary"]
        
        expected_ds_fields = [
            "declared_absent_count",
            "declared_present_count",
            "has_tech_evidence"
        ]
        
        for field in expected_ds_fields:
            assert field in ds, f"declaration_summary missing field: {field}"
        
        print(f"PASS - Dispute detail has declaration_summary with required fields")
    
    def test_10_dispute_detail_has_evidence_count(self):
        """Test that dispute detail includes evidence_submissions_count"""
        token = self.login(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token, "Failed to login"
        
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get a valid dispute ID
        decisions_response = self.session.get(f"{BASE_URL}/api/disputes/decisions/mine")
        if decisions_response.status_code != 200 or decisions_response.json().get("count", 0) == 0:
            pytest.skip("No decisions available to test")
        
        dispute_id = decisions_response.json()["decisions"][0]["dispute_id"]
        response = self.session.get(f"{BASE_URL}/api/disputes/{dispute_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "evidence_submissions_count" in data, "Response missing evidence_submissions_count"
        assert isinstance(data["evidence_submissions_count"], int), "evidence_submissions_count should be int"
        
        print(f"PASS - Dispute detail has evidence_submissions_count: {data['evidence_submissions_count']}")
    
    def test_11_non_existent_dispute_returns_404(self):
        """Test that non-existent dispute returns 404"""
        token = self.login(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token, "Failed to login"
        
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        response = self.session.get(f"{BASE_URL}/api/disputes/non-existent-id-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        print("PASS - Non-existent dispute returns 404")
    
    def test_12_regular_user_can_access_decisions(self):
        """Test that regular user can access their own decisions"""
        token = self.login(USER_EMAIL, USER_PASSWORD)
        assert token, "Failed to login as regular user"
        
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        response = self.session.get(f"{BASE_URL}/api/disputes/decisions/mine")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "decisions" in data, "Response missing 'decisions' field"
        assert "count" in data, "Response missing 'count' field"
        
        print(f"PASS - Regular user can access decisions (count: {data['count']})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
