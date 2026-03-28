"""
Test Dispute Declarants Feature - Iteration 118
Tests the new declarants array in declaration_summary for dispute cards UX improvement.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_USER_EMAIL = "testuser_audit@nlyt.app"
TEST_USER_PASSWORD = "TestAudit123!"
DISPUTE_ID = "619c6d07-d42f-46ea-8d8b-c64a26225ff5"


class TestDisputeDeclarantsAPI:
    """Tests for dispute declarants feature in API responses"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip(f"Authentication failed: {login_response.status_code}")
    
    def test_disputes_mine_returns_declarants_array(self):
        """GET /api/disputes/mine should return declarants array in declaration_summary"""
        response = self.session.get(f"{BASE_URL}/api/disputes/mine")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "disputes" in data, "Response should contain 'disputes' key"
        assert len(data["disputes"]) > 0, "Should have at least one dispute"
        
        dispute = data["disputes"][0]
        assert "declaration_summary" in dispute, "Dispute should have declaration_summary"
        
        summary = dispute["declaration_summary"]
        assert "declarants" in summary, "declaration_summary should have 'declarants' array"
        assert isinstance(summary["declarants"], list), "declarants should be a list"
    
    def test_disputes_mine_declarants_have_required_fields(self):
        """Each declarant should have first_name and declared_status"""
        response = self.session.get(f"{BASE_URL}/api/disputes/mine")
        
        assert response.status_code == 200
        
        data = response.json()
        dispute = data["disputes"][0]
        declarants = dispute["declaration_summary"]["declarants"]
        
        if len(declarants) > 0:
            for declarant in declarants:
                assert "first_name" in declarant, "Declarant should have first_name"
                assert "declared_status" in declarant, "Declarant should have declared_status"
                assert isinstance(declarant["first_name"], str), "first_name should be string"
                assert declarant["declared_status"] in ["absent", "present_on_time", "present_late", "unknown"], \
                    f"Invalid declared_status: {declarant['declared_status']}"
    
    def test_dispute_detail_returns_declarants_array(self):
        """GET /api/disputes/:id should return declarants array in declaration_summary"""
        response = self.session.get(f"{BASE_URL}/api/disputes/{DISPUTE_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "declaration_summary" in data, "Response should have declaration_summary"
        
        summary = data["declaration_summary"]
        assert "declarants" in summary, "declaration_summary should have 'declarants' array"
        assert isinstance(summary["declarants"], list), "declarants should be a list"
    
    def test_dispute_detail_declarants_have_required_fields(self):
        """Each declarant in detail view should have first_name and declared_status"""
        response = self.session.get(f"{BASE_URL}/api/disputes/{DISPUTE_ID}")
        
        assert response.status_code == 200
        
        data = response.json()
        declarants = data["declaration_summary"]["declarants"]
        
        if len(declarants) > 0:
            for declarant in declarants:
                assert "first_name" in declarant, "Declarant should have first_name"
                assert "declared_status" in declarant, "Declarant should have declared_status"
    
    def test_dispute_detail_has_igaal_as_declarant(self):
        """The specific dispute should have Igaal as a declarant who declared absent"""
        response = self.session.get(f"{BASE_URL}/api/disputes/{DISPUTE_ID}")
        
        assert response.status_code == 200
        
        data = response.json()
        declarants = data["declaration_summary"]["declarants"]
        
        # Find Igaal in declarants
        igaal_found = False
        for declarant in declarants:
            if declarant["first_name"] == "Igaal":
                igaal_found = True
                assert declarant["declared_status"] == "absent", \
                    f"Igaal should have declared absent, got {declarant['declared_status']}"
                break
        
        assert igaal_found, "Igaal should be in the declarants list"
    
    def test_declaration_summary_counts_match_declarants(self):
        """The counts in declaration_summary should match the declarants array"""
        response = self.session.get(f"{BASE_URL}/api/disputes/{DISPUTE_ID}")
        
        assert response.status_code == 200
        
        data = response.json()
        summary = data["declaration_summary"]
        declarants = summary["declarants"]
        
        # Count by status
        absent_count = sum(1 for d in declarants if d["declared_status"] == "absent")
        present_count = sum(1 for d in declarants if d["declared_status"] in ["present_on_time", "present_late"])
        
        assert summary["declared_absent_count"] == absent_count, \
            f"Absent count mismatch: {summary['declared_absent_count']} vs {absent_count}"
        assert summary["declared_present_count"] == present_count, \
            f"Present count mismatch: {summary['declared_present_count']} vs {present_count}"


class TestDisputeDetailPageElements:
    """Tests for dispute detail page data-testid elements"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip(f"Authentication failed: {login_response.status_code}")
    
    def test_dispute_detail_no_reclassification_actions(self):
        """Dispute detail should not have reclassification or declaration actions"""
        response = self.session.get(f"{BASE_URL}/api/disputes/{DISPUTE_ID}")
        
        assert response.status_code == 200
        
        data = response.json()
        
        # These fields should not exist or be false
        assert data.get("can_reclassify") is None or data.get("can_reclassify") == False, \
            "Dispute should not have can_reclassify action"
        assert data.get("can_declare") is None or data.get("can_declare") == False, \
            "Dispute should not have can_declare action"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
