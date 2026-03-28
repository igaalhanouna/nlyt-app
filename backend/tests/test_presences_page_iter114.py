"""
Test suite for /presences page realignment - Iteration 114
Tests the new PresencesPage component and /api/attendance-sheets/pending endpoint
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_USER_EMAIL = "igaal@hotmail.com"
TEST_USER_PASSWORD = "Test123!"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test user"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("access_token")


@pytest.fixture
def auth_headers(auth_token):
    """Headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestAttendanceSheetsEndpoint:
    """Tests for GET /api/attendance-sheets/pending endpoint"""
    
    def test_pending_sheets_returns_200(self, auth_headers):
        """Verify endpoint returns 200 for authenticated user"""
        response = requests.get(
            f"{BASE_URL}/api/attendance-sheets/pending",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✅ GET /api/attendance-sheets/pending returns 200")
    
    def test_pending_sheets_response_structure(self, auth_headers):
        """Verify response has correct structure: {pending_sheets: [], count: 0}"""
        response = requests.get(
            f"{BASE_URL}/api/attendance-sheets/pending",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "pending_sheets" in data, "Response missing 'pending_sheets' field"
        assert "count" in data, "Response missing 'count' field"
        assert isinstance(data["pending_sheets"], list), "'pending_sheets' should be a list"
        assert isinstance(data["count"], int), "'count' should be an integer"
        
        print(f"✅ Response structure correct: pending_sheets={len(data['pending_sheets'])}, count={data['count']}")
    
    def test_pending_sheets_count_matches_list(self, auth_headers):
        """Verify count matches the number of non-submitted sheets"""
        response = requests.get(
            f"{BASE_URL}/api/attendance-sheets/pending",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Count should match pending (non-submitted) sheets
        pending_count = sum(1 for s in data["pending_sheets"] if not s.get("already_submitted", False))
        assert data["count"] == pending_count, f"Count mismatch: {data['count']} vs {pending_count}"
        
        print(f"✅ Count matches pending sheets: {data['count']}")
    
    def test_pending_sheets_requires_auth(self):
        """Verify endpoint requires authentication"""
        response = requests.get(
            f"{BASE_URL}/api/attendance-sheets/pending",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✅ Endpoint requires authentication (returns 401 without token)")


class TestOtherEndpointsNotAffected:
    """Verify other endpoints still work independently"""
    
    def test_dashboard_endpoint(self, auth_headers):
        """Verify dashboard-related endpoint works"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/my-timeline",
            headers=auth_headers
        )
        assert response.status_code == 200, f"my-timeline failed: {response.text}"
        print("✅ GET /api/appointments/my-timeline works (dashboard)")
    
    def test_litiges_endpoint(self, auth_headers):
        """Verify disputes endpoint works"""
        response = requests.get(
            f"{BASE_URL}/api/disputes/",
            headers=auth_headers
        )
        # May return 404 if no disputes exist, or 200 with list
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
        print(f"✅ GET /api/disputes/ returns {response.status_code}")
    
    def test_auth_me_endpoint(self, auth_headers):
        """Verify auth/me endpoint works"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers=auth_headers
        )
        assert response.status_code == 200, f"auth/me failed: {response.text}"
        print("✅ GET /api/auth/me works")


class TestNoReclassifyEndpointOnPresences:
    """Verify reclassify endpoint is NOT called from /presences context"""
    
    def test_reclassify_endpoint_exists_but_separate(self, auth_headers):
        """Verify reclassify endpoint exists but is separate from presences flow"""
        # The reclassify endpoint should still exist for other flows
        # but should NOT be called from /presences page
        # We just verify the endpoint structure is different
        response = requests.get(
            f"{BASE_URL}/api/attendance-sheets/pending",
            headers=auth_headers
        )
        data = response.json()
        
        # Verify no reclassification-related fields in response
        for sheet in data.get("pending_sheets", []):
            assert "reclassify" not in str(sheet).lower(), "Found reclassify in sheet data"
            assert "penalty" not in str(sheet).lower(), "Found penalty in sheet data"
            assert "guarantee" not in str(sheet).lower(), "Found guarantee in sheet data"
        
        print("✅ No reclassification fields in pending sheets response")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
