"""
Test Proof Availability Enhancement
Tests the meeting_provider_metadata.creator_email field for different appointment types
to verify correct proof availability detection (Gmail personal vs Workspace vs Teams/Zoom)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test appointment IDs
MEET_PERSONAL_ID = "10c355e4-2796-4aaf-b163-74a912d71957"  # creator_email: igaal.hanouna@gmail.com
TEAMS_ID = "87c58ee3-a512-4c17-a8ca-381d5519d98f"  # creator_email: igaal@hotmail.com
PHYSICAL_ID = "35df4fb0-91ac-4d6a-a56b-cfd6e06b4111"  # No meeting_provider_metadata


class TestProofAvailability:
    """Tests for proof availability based on meeting provider metadata"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "testuser_audit@nlyt.app", "password": "Test1234!"}
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_meet_personal_has_gmail_creator_email(self):
        """Meet appointment (Gmail personal) should have creator_email ending with @gmail.com"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/{MEET_PERSONAL_ID}",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed to get Meet appointment: {response.text}"
        
        data = response.json()
        assert data.get("meeting_provider") == "meet", "Expected meeting_provider to be 'meet'"
        
        metadata = data.get("meeting_provider_metadata")
        assert metadata is not None, "meeting_provider_metadata should not be None"
        
        creator_email = metadata.get("creator_email")
        assert creator_email is not None, "creator_email should not be None"
        assert creator_email.endswith("@gmail.com"), f"Expected creator_email to end with @gmail.com, got: {creator_email}"
        
        print(f"✓ Meet personal creator_email: {creator_email}")
    
    def test_teams_has_non_gmail_creator_email(self):
        """Teams appointment should have creator_email NOT ending with @gmail.com"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/{TEAMS_ID}",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed to get Teams appointment: {response.text}"
        
        data = response.json()
        assert data.get("meeting_provider") == "teams", "Expected meeting_provider to be 'teams'"
        
        metadata = data.get("meeting_provider_metadata")
        assert metadata is not None, "meeting_provider_metadata should not be None"
        
        creator_email = metadata.get("creator_email")
        assert creator_email is not None, "creator_email should not be None"
        assert not creator_email.endswith("@gmail.com"), f"Expected creator_email to NOT end with @gmail.com, got: {creator_email}"
        assert not creator_email.endswith("@googlemail.com"), f"Expected creator_email to NOT end with @googlemail.com, got: {creator_email}"
        
        print(f"✓ Teams creator_email: {creator_email}")
    
    def test_physical_has_no_meeting_provider_metadata(self):
        """Physical appointment should have no meeting_provider_metadata"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/{PHYSICAL_ID}",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed to get Physical appointment: {response.text}"
        
        data = response.json()
        assert data.get("appointment_type") == "physical", "Expected appointment_type to be 'physical'"
        assert data.get("meeting_provider") is None, "Expected meeting_provider to be None for physical"
        
        metadata = data.get("meeting_provider_metadata")
        assert metadata is None, f"Expected meeting_provider_metadata to be None for physical, got: {metadata}"
        
        print("✓ Physical appointment has no meeting_provider_metadata")
    
    def test_meet_personal_appointment_type_is_video(self):
        """Meet appointment should have appointment_type = 'video'"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/{MEET_PERSONAL_ID}",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("appointment_type") == "video", f"Expected appointment_type to be 'video', got: {data.get('appointment_type')}"
        
        print("✓ Meet appointment has appointment_type = 'video'")
    
    def test_teams_appointment_type_is_video(self):
        """Teams appointment should have appointment_type = 'video'"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/{TEAMS_ID}",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("appointment_type") == "video", f"Expected appointment_type to be 'video', got: {data.get('appointment_type')}"
        
        print("✓ Teams appointment has appointment_type = 'video'")
    
    def test_meet_has_meeting_join_url(self):
        """Meet appointment should have meeting_join_url"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/{MEET_PERSONAL_ID}",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        meeting_join_url = data.get("meeting_join_url")
        assert meeting_join_url is not None, "Expected meeting_join_url to be present"
        assert len(meeting_join_url) > 0, "Expected meeting_join_url to be non-empty"
        
        print(f"✓ Meet has meeting_join_url: {meeting_join_url[:50]}...")
    
    def test_teams_has_meeting_join_url(self):
        """Teams appointment should have meeting_join_url"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/{TEAMS_ID}",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        meeting_join_url = data.get("meeting_join_url")
        assert meeting_join_url is not None, "Expected meeting_join_url to be present"
        assert len(meeting_join_url) > 0, "Expected meeting_join_url to be non-empty"
        
        print(f"✓ Teams has meeting_join_url: {meeting_join_url[:50]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
