"""
Test PATCH /api/appointments/{id} past date validation
- PATCH with past start_datetime returns 400
- PATCH with future start_datetime returns 200
- PATCH with non-date field (e.g. title) returns 200 (no date validation triggered)
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"
WORKSPACE_ID = "7e219321-18fd-4643-9be6-e4f1de88a2a8"
EDITABLE_APPOINTMENT_ID = "ee6a3d00-f7ad-4d0f-859f-4b2271784878"


class TestPatchPastDateValidation:
    """Test PATCH endpoint past date validation for existing appointments"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: authenticate and get token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code != 200:
            pytest.skip(f"Authentication failed: {login_response.status_code} - {login_response.text}")
        
        token = login_response.json().get("access_token")
        if not token:
            pytest.skip("No access_token in login response")
        
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.token = token
        
    def test_api_health(self):
        """Test API is accessible"""
        response = self.session.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        print("API health check: PASSED")
    
    def test_patch_with_past_date_returns_400(self):
        """PATCH with past start_datetime should return 400"""
        # Create a past datetime (1 day ago)
        past_datetime = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
        
        response = self.session.patch(
            f"{BASE_URL}/api/appointments/{EDITABLE_APPOINTMENT_ID}",
            json={"start_datetime": past_datetime}
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        
        # Check error message
        data = response.json()
        expected_message = "Impossible de modifier un rendez-vous vers une date dans le passé"
        assert expected_message in data.get("detail", ""), f"Expected error message not found: {data}"
        print(f"PATCH with past date (1 day ago): PASSED - Got 400 with correct message")
    
    def test_patch_with_past_hour_returns_400(self):
        """PATCH with past start_datetime (2 hours ago) should return 400"""
        # Create a past datetime (2 hours ago)
        past_datetime = (datetime.utcnow() - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")
        
        response = self.session.patch(
            f"{BASE_URL}/api/appointments/{EDITABLE_APPOINTMENT_ID}",
            json={"start_datetime": past_datetime}
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print(f"PATCH with past date (2 hours ago): PASSED - Got 400")
    
    def test_patch_with_future_date_returns_200(self):
        """PATCH with future start_datetime should return 200"""
        # Create a future datetime (7 days ahead)
        future_datetime = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
        
        response = self.session.patch(
            f"{BASE_URL}/api/appointments/{EDITABLE_APPOINTMENT_ID}",
            json={"start_datetime": future_datetime}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"PATCH with future date (7 days ahead): PASSED - Got 200")
    
    def test_patch_with_future_hour_returns_200(self):
        """PATCH with future start_datetime (3 hours ahead) should return 200"""
        # Create a future datetime (3 hours ahead)
        future_datetime = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S")
        
        response = self.session.patch(
            f"{BASE_URL}/api/appointments/{EDITABLE_APPOINTMENT_ID}",
            json={"start_datetime": future_datetime}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"PATCH with future date (3 hours ahead): PASSED - Got 200")
    
    def test_patch_non_date_field_returns_200(self):
        """PATCH with non-date field (title) should return 200 without date validation"""
        response = self.session.patch(
            f"{BASE_URL}/api/appointments/{EDITABLE_APPOINTMENT_ID}",
            json={"title": "Test Title Update - Validation Test"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"PATCH with non-date field (title): PASSED - Got 200")
        
        # Restore original title
        self.session.patch(
            f"{BASE_URL}/api/appointments/{EDITABLE_APPOINTMENT_ID}",
            json={"title": "Test Appointment for Edit"}
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
