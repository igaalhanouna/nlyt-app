"""
API-level integration tests for Declarative Engine V5 changes.
Tests the /api/disputes/mine and /api/attendance-sheets/pending endpoints.
Also verifies regression on existing dispute resolution flows.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
ADMIN_EMAIL = "testuser_audit@nlyt.app"
ADMIN_PASSWORD = "TestAudit123!"
USER_EMAIL = "igaal@hotmail.com"
USER_PASSWORD = "Test123!"


class TestAPIAuth:
    """Test authentication and basic API access."""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token."""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    @pytest.fixture(scope="class")
    def user_token(self):
        """Get regular user auth token."""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": USER_EMAIL, "password": USER_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip(f"User login failed: {response.status_code} - {response.text}")
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    def test_admin_login(self, admin_token):
        """Verify admin can login."""
        assert admin_token is not None
        assert len(admin_token) > 0
        print(f"PASS: Admin login successful, token length: {len(admin_token)}")
    
    def test_user_login(self, user_token):
        """Verify regular user can login."""
        assert user_token is not None
        assert len(user_token) > 0
        print(f"PASS: User login successful, token length: {len(user_token)}")


class TestDisputesAPI:
    """Test /api/disputes endpoints."""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for API calls."""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip(f"Login failed: {response.status_code}")
        data = response.json()
        token = data.get("access_token") or data.get("token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_disputes_mine_endpoint(self, auth_headers):
        """Test /api/disputes/mine returns data correctly."""
        response = requests.get(
            f"{BASE_URL}/api/disputes/mine",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "disputes" in data, "Response should contain 'disputes' key"
        assert "count" in data, "Response should contain 'count' key"
        assert isinstance(data["disputes"], list), "'disputes' should be a list"
        assert isinstance(data["count"], int), "'count' should be an integer"
        
        print(f"PASS: /api/disputes/mine returned {data['count']} disputes")
        
        # Verify dispute structure if any exist
        if data["disputes"]:
            dispute = data["disputes"][0]
            expected_fields = ["dispute_id", "appointment_id", "target_participant_id", "status"]
            for field in expected_fields:
                assert field in dispute, f"Dispute should contain '{field}'"
            print(f"PASS: Dispute structure validated with fields: {list(dispute.keys())[:10]}...")
    
    def test_disputes_decisions_mine_endpoint(self, auth_headers):
        """Test /api/disputes/decisions/mine returns data correctly."""
        response = requests.get(
            f"{BASE_URL}/api/disputes/decisions/mine",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "decisions" in data, "Response should contain 'decisions' key"
        assert "count" in data, "Response should contain 'count' key"
        
        print(f"PASS: /api/disputes/decisions/mine returned {data['count']} decisions")


class TestAttendanceSheetsAPI:
    """Test /api/attendance-sheets endpoints."""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for API calls."""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip(f"Login failed: {response.status_code}")
        data = response.json()
        token = data.get("access_token") or data.get("token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_pending_sheets_endpoint(self, auth_headers):
        """Test /api/attendance-sheets/pending returns data correctly."""
        response = requests.get(
            f"{BASE_URL}/api/attendance-sheets/pending",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "pending_sheets" in data, "Response should contain 'pending_sheets' key"
        assert "count" in data, "Response should contain 'count' key"
        assert isinstance(data["pending_sheets"], list), "'pending_sheets' should be a list"
        
        print(f"PASS: /api/attendance-sheets/pending returned {data['count']} pending sheets")
        
        # Verify sheet structure if any exist
        if data["pending_sheets"]:
            sheet = data["pending_sheets"][0]
            expected_fields = ["appointment_id", "sheet_id", "title", "targets"]
            for field in expected_fields:
                assert field in sheet, f"Sheet should contain '{field}'"
            print(f"PASS: Sheet structure validated")


class TestHealthAndBasicEndpoints:
    """Test basic health and status endpoints."""
    
    def test_health_endpoint(self):
        """Test /api/health returns OK."""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        print("PASS: /api/health returns 200")
    
    def test_backend_accessible(self):
        """Verify backend is accessible."""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200
        print(f"PASS: Backend accessible at {BASE_URL}")


class TestDisputeResolutionRegression:
    """Regression tests for existing dispute resolution flows."""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for API calls."""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip(f"Login failed: {response.status_code}")
        data = response.json()
        token = data.get("access_token") or data.get("token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_dispute_detail_endpoint_structure(self, auth_headers):
        """Test dispute detail endpoint returns correct structure."""
        # First get list of disputes
        list_response = requests.get(
            f"{BASE_URL}/api/disputes/mine",
            headers=auth_headers
        )
        if list_response.status_code != 200:
            pytest.skip("Could not get disputes list")
        
        disputes = list_response.json().get("disputes", [])
        if not disputes:
            pytest.skip("No disputes available to test detail endpoint")
        
        # Get detail of first dispute
        dispute_id = disputes[0]["dispute_id"]
        detail_response = requests.get(
            f"{BASE_URL}/api/disputes/{dispute_id}",
            headers=auth_headers
        )
        
        assert detail_response.status_code == 200, f"Detail endpoint failed: {detail_response.status_code}"
        
        detail = detail_response.json()
        # Verify enriched fields exist
        expected_fields = ["dispute_id", "status", "my_role", "can_submit_position", "declaration_summary"]
        for field in expected_fields:
            assert field in detail, f"Detail should contain '{field}'"
        
        print(f"PASS: Dispute detail endpoint returns correct structure for {dispute_id}")
    
    def test_position_submission_validation(self, auth_headers):
        """Test position submission validates input correctly."""
        # Try to submit invalid position to non-existent dispute
        response = requests.post(
            f"{BASE_URL}/api/disputes/non-existent-id/position",
            headers=auth_headers,
            json={"position": "invalid_position"}
        )
        
        # Should return 400 (invalid position) or 404 (not found)
        assert response.status_code in [400, 404], f"Expected 400 or 404, got {response.status_code}"
        print(f"PASS: Position submission validation works (returned {response.status_code})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
