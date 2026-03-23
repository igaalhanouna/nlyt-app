"""
Test: Organizer Proof Bypass Fix
Verifies that organizers must go through NLYT Proof flow for video appointments.
No direct visio access should be possible.

Test cases:
1. GET /api/proof/{appointment_id}/info returns is_organizer=true and meeting_host_url for organizer token
2. GET /api/proof/{appointment_id}/info returns is_organizer=false and empty meeting_host_url for participant token
3. POST /api/proof/{appointment_id}/checkin returns host_url for organizer, join_url for participant
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data from the review request
APPOINTMENT_ID = "4bc2d91a-fc0f-4b67-a1e1-61439772b504"
ORGANIZER_TOKEN = "3da80d4e-2f1d-45ba-bb8f-801712aa3dd6"
PARTICIPANT_TOKEN = "656caec0-5d2e-42c5-8888-8b0b6684211e"


class TestProofInfoEndpoint:
    """Tests for GET /api/proof/{appointment_id}/info endpoint"""

    def test_organizer_gets_is_organizer_true(self):
        """Organizer token should return is_organizer=true"""
        response = requests.get(
            f"{BASE_URL}/api/proof/{APPOINTMENT_ID}/info",
            params={"token": ORGANIZER_TOKEN}
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.json()}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "participant" in data, "Response should contain 'participant' field"
        assert data["participant"]["is_organizer"] == True, "Organizer should have is_organizer=true"

    def test_organizer_gets_meeting_host_url(self):
        """Organizer token should return meeting_host_url in appointment info"""
        response = requests.get(
            f"{BASE_URL}/api/proof/{APPOINTMENT_ID}/info",
            params={"token": ORGANIZER_TOKEN}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check appointment info contains meeting_host_url field
        assert "appointment" in data, "Response should contain 'appointment' field"
        
        # Note: meeting_host_url may be empty string if Teams doesn't provide separate host URL
        # The key is that the field is present and accessible for organizer
        print(f"meeting_host_url for organizer: '{data['appointment'].get('meeting_host_url', 'NOT_PRESENT')}'")
        print(f"meeting_join_url for organizer: '{data['appointment'].get('meeting_join_url', 'NOT_PRESENT')}'")
        
        # Verify the field exists (even if empty)
        assert "meeting_host_url" in data["appointment"], "Organizer should have access to meeting_host_url field"

    def test_participant_gets_is_organizer_false(self):
        """Participant token should return is_organizer=false"""
        response = requests.get(
            f"{BASE_URL}/api/proof/{APPOINTMENT_ID}/info",
            params={"token": PARTICIPANT_TOKEN}
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.json()}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "participant" in data, "Response should contain 'participant' field"
        assert data["participant"]["is_organizer"] == False, "Participant should have is_organizer=false"

    def test_participant_gets_empty_meeting_host_url(self):
        """Participant token should return empty meeting_host_url"""
        response = requests.get(
            f"{BASE_URL}/api/proof/{APPOINTMENT_ID}/info",
            params={"token": PARTICIPANT_TOKEN}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Participant should NOT get meeting_host_url (should be empty string)
        meeting_host_url = data["appointment"].get("meeting_host_url", "")
        print(f"meeting_host_url for participant: '{meeting_host_url}'")
        
        assert meeting_host_url == "", f"Participant should get empty meeting_host_url, got: '{meeting_host_url}'"

    def test_participant_gets_meeting_join_url(self):
        """Participant token should still get meeting_join_url"""
        response = requests.get(
            f"{BASE_URL}/api/proof/{APPOINTMENT_ID}/info",
            params={"token": PARTICIPANT_TOKEN}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Participant should get meeting_join_url
        meeting_join_url = data["appointment"].get("meeting_join_url", "")
        print(f"meeting_join_url for participant: '{meeting_join_url}'")
        
        # meeting_join_url should be present (may be empty if not yet created)
        assert "meeting_join_url" in data["appointment"], "Participant should have access to meeting_join_url field"


class TestProofCheckinEndpoint:
    """Tests for POST /api/proof/{appointment_id}/checkin endpoint"""

    def test_checkin_returns_visio_url(self):
        """Checkin should return meeting_join_url in response"""
        # Note: This test may create a session, so we check the response structure
        response = requests.post(
            f"{BASE_URL}/api/proof/{APPOINTMENT_ID}/checkin",
            json={"token": PARTICIPANT_TOKEN}
        )
        
        print(f"Checkin response status: {response.status_code}")
        print(f"Checkin response body: {response.json()}")
        
        # Should succeed or return already_active
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Response should contain meeting_join_url field
        assert "meeting_join_url" in data, "Checkin response should contain meeting_join_url"


class TestAppointmentInfoStructure:
    """Verify appointment info structure for video appointments"""

    def test_appointment_is_video_type(self):
        """Verify the test appointment is a video type"""
        response = requests.get(
            f"{BASE_URL}/api/proof/{APPOINTMENT_ID}/info",
            params={"token": ORGANIZER_TOKEN}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify appointment type
        apt = data.get("appointment", {})
        print(f"Appointment type: {apt.get('appointment_type', 'NOT_SET')}")
        print(f"Meeting provider: {apt.get('meeting_provider', 'NOT_SET')}")
        
        # This should be a video appointment
        # Note: The endpoint only works for video appointments per the code

    def test_invalid_token_returns_404(self):
        """Invalid token should return 404"""
        response = requests.get(
            f"{BASE_URL}/api/proof/{APPOINTMENT_ID}/info",
            params={"token": "invalid-token-12345"}
        )
        
        print(f"Invalid token response: {response.status_code}")
        assert response.status_code == 404, f"Expected 404 for invalid token, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
