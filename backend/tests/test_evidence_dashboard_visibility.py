"""
Test: Evidence Dashboard Visibility Fix
Tests that the evidence-dashboard section is hidden for video appointments
and shown for physical appointments (when evidence exists).

This is a frontend-focused test, but we verify the backend API returns
correct appointment_type values.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestEvidenceDashboardVisibility:
    """Tests for evidence dashboard visibility based on appointment type"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "testuser_audit@nlyt.app", "password": "Test1234!"}
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_health_endpoint(self):
        """Test: Backend health check returns 200"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        print("SUCCESS: GET /api/health returns 200")
    
    def test_video_appointment_returns_correct_type(self):
        """Test: Video appointment API returns appointment_type='video'"""
        # Video appointment ID from test data
        video_apt_id = "4bc2d91a-fc0f-4b67-a1e1-61439772b504"
        
        response = requests.get(
            f"{BASE_URL}/api/appointments/{video_apt_id}",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed to get video appointment: {response.text}"
        
        data = response.json()
        assert data.get("appointment_type") == "video", \
            f"Expected appointment_type='video', got '{data.get('appointment_type')}'"
        print(f"SUCCESS: Video appointment {video_apt_id} has appointment_type='video'")
    
    def test_physical_appointment_returns_correct_type(self):
        """Test: Physical appointment API returns appointment_type='physical'"""
        # Physical appointment ID from test data
        physical_apt_id = "06d1b01e-ec89-42f2-9dbe-a06a4877db43"
        
        response = requests.get(
            f"{BASE_URL}/api/appointments/{physical_apt_id}",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed to get physical appointment: {response.text}"
        
        data = response.json()
        assert data.get("appointment_type") == "physical", \
            f"Expected appointment_type='physical', got '{data.get('appointment_type')}'"
        print(f"SUCCESS: Physical appointment {physical_apt_id} has appointment_type='physical'")
    
    def test_appointments_list_includes_type(self):
        """Test: Appointments list includes appointment_type field"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed to get appointments list: {response.text}"
        
        data = response.json()
        appointments = data.get("appointments", [])
        assert len(appointments) > 0, "No appointments found"
        
        # Check that all appointments have appointment_type field
        for apt in appointments[:5]:  # Check first 5
            assert "appointment_type" in apt, f"Appointment {apt.get('appointment_id')} missing appointment_type"
            assert apt["appointment_type"] in ["video", "physical"], \
                f"Invalid appointment_type: {apt['appointment_type']}"
        
        print(f"SUCCESS: All appointments have valid appointment_type field")
    
    def test_evidence_endpoint_for_physical(self):
        """Test: Evidence endpoint returns data for physical appointment"""
        physical_apt_id = "06d1b01e-ec89-42f2-9dbe-a06a4877db43"
        
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{physical_apt_id}",
            headers=self.headers
        )
        # Evidence endpoint should return 200 (may have empty data)
        assert response.status_code == 200, f"Evidence endpoint failed: {response.text}"
        
        data = response.json()
        # Physical appointment with evidence should have participants data
        if data.get("participants"):
            print(f"SUCCESS: Evidence endpoint returns participant data for physical appointment")
        else:
            print(f"INFO: Evidence endpoint returns empty data (no evidence yet)")
    
    def test_evidence_endpoint_for_video(self):
        """Test: Evidence endpoint works for video appointment"""
        video_apt_id = "4bc2d91a-fc0f-4b67-a1e1-61439772b504"
        
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{video_apt_id}",
            headers=self.headers
        )
        # Evidence endpoint should return 200
        assert response.status_code == 200, f"Evidence endpoint failed: {response.text}"
        print(f"SUCCESS: Evidence endpoint works for video appointment")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
