"""
Iteration 105 - DisputeCenter, Navbar Badge, Dashboard Banner Tests
Tests for:
1. GET /api/attendance/pending-reviews/list - enriched data with participant_name, evidence_sources, days_remaining
2. PUT /api/attendance/reclassify/{record_id} - reclassification from disputes page
3. Verify pending review count decreases after reclassification
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from iteration 104
ORGANIZER_EMAIL = "igaal.hanouna@gmail.com"
ORGANIZER_PASSWORD = "OrgTest123!"


class TestDisputesFeatures:
    """Tests for DisputeCenter page and related features"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for organizer"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ORGANIZER_EMAIL,
            "password": ORGANIZER_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token") or data.get("token")
        pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_01_pending_reviews_list_endpoint_exists(self, auth_headers):
        """Test that GET /api/attendance/pending-reviews/list endpoint exists and returns correct structure"""
        response = requests.get(f"{BASE_URL}/api/attendance/pending-reviews/list", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "pending_reviews" in data, "Response should have 'pending_reviews' key"
        assert "count" in data, "Response should have 'count' key"
        assert isinstance(data["pending_reviews"], list), "pending_reviews should be a list"
        assert isinstance(data["count"], int), "count should be an integer"
        
        print(f"✅ Pending reviews endpoint works. Count: {data['count']}")
    
    def test_02_pending_reviews_enriched_data(self, auth_headers):
        """Test that pending reviews contain enriched data fields"""
        response = requests.get(f"{BASE_URL}/api/attendance/pending-reviews/list", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] == 0:
            pytest.skip("No pending reviews to test enriched data")
        
        # Check first review has all required enriched fields
        review = data["pending_reviews"][0]
        
        # Required fields from original record
        assert "record_id" in review, "Missing record_id"
        assert "appointment_id" in review, "Missing appointment_id"
        assert "participant_id" in review, "Missing participant_id"
        
        # Enriched fields for DisputeCenter
        assert "participant_name" in review, "Missing participant_name (enriched field)"
        assert "evidence_sources" in review, "Missing evidence_sources (enriched field)"
        assert "days_remaining" in review, "Missing days_remaining (enriched field)"
        assert "appointment_title" in review, "Missing appointment_title (enriched field)"
        assert "appointment_datetime" in review, "Missing appointment_datetime (enriched field)"
        assert "appointment_type" in review, "Missing appointment_type (enriched field)"
        
        # Validate types
        assert isinstance(review["evidence_sources"], list), "evidence_sources should be a list"
        assert isinstance(review["days_remaining"], int), "days_remaining should be an integer"
        
        print(f"✅ Enriched data present: participant_name='{review['participant_name']}', "
              f"evidence_sources={review['evidence_sources']}, days_remaining={review['days_remaining']}")
    
    def test_03_pending_reviews_has_decision_basis(self, auth_headers):
        """Test that pending reviews include decision_basis for UI display"""
        response = requests.get(f"{BASE_URL}/api/attendance/pending-reviews/list", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] == 0:
            pytest.skip("No pending reviews to test decision_basis")
        
        review = data["pending_reviews"][0]
        assert "decision_basis" in review, "Missing decision_basis field"
        
        print(f"✅ decision_basis present: '{review['decision_basis']}'")
    
    def test_04_reclassify_endpoint_exists(self, auth_headers):
        """Test that PUT /api/attendance/reclassify/{record_id} endpoint exists"""
        # First get a pending review record_id
        response = requests.get(f"{BASE_URL}/api/attendance/pending-reviews/list", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] == 0:
            pytest.skip("No pending reviews to test reclassify endpoint")
        
        record_id = data["pending_reviews"][0]["record_id"]
        
        # Test with invalid outcome to verify endpoint exists without modifying data
        response = requests.put(
            f"{BASE_URL}/api/attendance/reclassify/{record_id}",
            headers=auth_headers,
            json={"new_outcome": "invalid_outcome_test"}
        )
        
        # Should return 400 for invalid outcome, not 404
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}: {response.text}"
        
        print(f"✅ Reclassify endpoint exists for record_id: {record_id}")
    
    def test_05_reclassify_on_time_flow(self, auth_headers):
        """Test reclassifying a record as 'on_time' (Present button)"""
        # Get pending reviews
        response = requests.get(f"{BASE_URL}/api/attendance/pending-reviews/list", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        initial_count = data["count"]
        
        if initial_count == 0:
            pytest.skip("No pending reviews to test reclassify flow")
        
        record_id = data["pending_reviews"][0]["record_id"]
        participant_name = data["pending_reviews"][0].get("participant_name", "Unknown")
        
        print(f"Testing reclassify on_time for record: {record_id}, participant: {participant_name}")
        
        # Reclassify as on_time (Present)
        response = requests.put(
            f"{BASE_URL}/api/attendance/reclassify/{record_id}",
            headers=auth_headers,
            json={"new_outcome": "on_time"}
        )
        
        assert response.status_code == 200, f"Reclassify failed: {response.status_code} - {response.text}"
        
        result = response.json()
        assert result.get("success") == True or "record_id" in result, f"Unexpected response: {result}"
        
        # Verify count decreased
        response = requests.get(f"{BASE_URL}/api/attendance/pending-reviews/list", headers=auth_headers)
        assert response.status_code == 200
        new_data = response.json()
        new_count = new_data["count"]
        
        assert new_count < initial_count, f"Count should decrease after reclassify. Was {initial_count}, now {new_count}"
        
        print(f"✅ Reclassify on_time successful. Count: {initial_count} -> {new_count}")
    
    def test_06_empty_state_when_no_reviews(self, auth_headers):
        """Test that endpoint returns empty list gracefully"""
        response = requests.get(f"{BASE_URL}/api/attendance/pending-reviews/list", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should always have these fields even if empty
        assert "pending_reviews" in data
        assert "count" in data
        assert data["count"] == len(data["pending_reviews"])
        
        print(f"✅ Empty state handled correctly. Current count: {data['count']}")


class TestReclassifyNoShow:
    """Test reclassifying as no_show (Absent button) - separate class to avoid conflicts"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for organizer"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ORGANIZER_EMAIL,
            "password": ORGANIZER_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token") or data.get("token")
        pytest.skip(f"Authentication failed: {response.status_code}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_reclassify_no_show_flow(self, auth_headers):
        """Test reclassifying a record as 'no_show' (Absent button)"""
        # Get pending reviews
        response = requests.get(f"{BASE_URL}/api/attendance/pending-reviews/list", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] == 0:
            pytest.skip("No pending reviews to test no_show reclassify")
        
        record_id = data["pending_reviews"][0]["record_id"]
        initial_count = data["count"]
        
        # Reclassify as no_show (Absent)
        response = requests.put(
            f"{BASE_URL}/api/attendance/reclassify/{record_id}",
            headers=auth_headers,
            json={"new_outcome": "no_show"}
        )
        
        assert response.status_code == 200, f"Reclassify no_show failed: {response.status_code} - {response.text}"
        
        # Verify count decreased
        response = requests.get(f"{BASE_URL}/api/attendance/pending-reviews/list", headers=auth_headers)
        new_count = response.json()["count"]
        
        assert new_count < initial_count, f"Count should decrease. Was {initial_count}, now {new_count}"
        
        print(f"✅ Reclassify no_show successful. Count: {initial_count} -> {new_count}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
