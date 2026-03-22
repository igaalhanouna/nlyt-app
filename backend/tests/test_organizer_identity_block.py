"""
Test Unified Organizer Identity Block Feature
Tests:
1. Backend: GET /api/appointments/{teams_id} returns meeting_provider_metadata.creator_email
2. Backend: GET /api/appointments/{meet_id} returns meeting_provider_metadata.creator_email
3. Backend: Physical appointments don't have meeting_provider_metadata
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"

# Test appointment IDs from the review request
TEAMS_APPOINTMENT_ID = "87c58ee3-a512-4c17-a8ca-381d5519d98f"
MEET_APPOINTMENT_ID = "10c355e4-2796-4aaf-b163-74a912d71957"
EXPECTED_TEAMS_CREATOR_EMAIL = "igaal@hotmail.com"
EXPECTED_MEET_CREATOR_EMAIL = "igaal.hanouna@gmail.com"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for API calls"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=15
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text[:200]}")


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Create authenticated session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestOrganizerIdentityBlockBackend:
    """Backend API tests for organizer identity block feature"""

    def test_teams_appointment_has_creator_email(self, api_client):
        """Teams appointment should return meeting_provider_metadata.creator_email = igaal@hotmail.com"""
        response = api_client.get(f"{BASE_URL}/api/appointments/{TEAMS_APPOINTMENT_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:300]}"
        
        data = response.json()
        assert "meeting_provider_metadata" in data, "Response should contain meeting_provider_metadata"
        
        metadata = data.get("meeting_provider_metadata") or {}
        creator_email = metadata.get("creator_email")
        
        assert creator_email is not None, f"Teams appointment should have creator_email in metadata. Got metadata: {metadata}"
        assert creator_email == EXPECTED_TEAMS_CREATOR_EMAIL, f"Expected creator_email '{EXPECTED_TEAMS_CREATOR_EMAIL}', got '{creator_email}'"
        
        # Also verify it's a Teams appointment
        assert data.get("meeting_provider", "").lower() in ["teams", "microsoft teams"], f"Expected Teams provider, got {data.get('meeting_provider')}"
        
        print(f"✓ Teams appointment has creator_email: {creator_email}")

    def test_meet_appointment_has_creator_email(self, api_client):
        """Meet appointment should return meeting_provider_metadata.creator_email = igaal.hanouna@gmail.com"""
        response = api_client.get(f"{BASE_URL}/api/appointments/{MEET_APPOINTMENT_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:300]}"
        
        data = response.json()
        assert "meeting_provider_metadata" in data, "Response should contain meeting_provider_metadata"
        
        metadata = data.get("meeting_provider_metadata") or {}
        creator_email = metadata.get("creator_email")
        
        assert creator_email is not None, f"Meet appointment should have creator_email in metadata. Got metadata: {metadata}"
        assert creator_email == EXPECTED_MEET_CREATOR_EMAIL, f"Expected creator_email '{EXPECTED_MEET_CREATOR_EMAIL}', got '{creator_email}'"
        
        # Also verify it's a Meet appointment
        assert data.get("meeting_provider", "").lower() in ["meet", "google meet"], f"Expected Meet provider, got {data.get('meeting_provider')}"
        
        print(f"✓ Meet appointment has creator_email: {creator_email}")

    def test_teams_appointment_has_meeting_join_url(self, api_client):
        """Teams appointment should have meeting_join_url"""
        response = api_client.get(f"{BASE_URL}/api/appointments/{TEAMS_APPOINTMENT_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("meeting_join_url"), f"Teams appointment should have meeting_join_url. Got: {data.get('meeting_join_url')}"
        print(f"✓ Teams appointment has meeting_join_url: {data.get('meeting_join_url')[:50]}...")

    def test_meet_appointment_has_meeting_join_url(self, api_client):
        """Meet appointment should have meeting_join_url"""
        response = api_client.get(f"{BASE_URL}/api/appointments/{MEET_APPOINTMENT_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("meeting_join_url"), f"Meet appointment should have meeting_join_url. Got: {data.get('meeting_join_url')}"
        print(f"✓ Meet appointment has meeting_join_url: {data.get('meeting_join_url')[:50]}...")

    def test_get_physical_appointment_no_meeting_metadata(self, api_client):
        """Physical appointments should not have meeting_provider_metadata with creator_email"""
        # First, get list of appointments to find a physical one
        response = api_client.get(f"{BASE_URL}/api/appointments/")
        assert response.status_code == 200
        
        data = response.json()
        appointments = data.get("appointments", [])
        
        # Find a physical appointment
        physical_apt = None
        for apt in appointments:
            if apt.get("appointment_type") == "physical":
                physical_apt = apt
                break
        
        if not physical_apt:
            pytest.skip("No physical appointment found for testing")
        
        # Get full appointment details
        apt_id = physical_apt.get("appointment_id")
        detail_response = api_client.get(f"{BASE_URL}/api/appointments/{apt_id}")
        assert detail_response.status_code == 200
        
        detail_data = detail_response.json()
        
        # Physical appointments should not have meeting_provider_metadata with creator_email
        metadata = detail_data.get("meeting_provider_metadata") or {}
        
        # It's OK if metadata is empty or None, or if it doesn't have creator_email
        assert not metadata.get("creator_email"), f"Physical appointment should not have creator_email. Got: {metadata}"
        
        print(f"✓ Physical appointment '{detail_data.get('title')}' does not have creator_email in metadata")


class TestZoomHostUrlDistinction:
    """Test that Zoom appointments correctly distinguish host_url from join_url"""

    def test_zoom_appointment_has_host_url_if_exists(self, api_client):
        """If a Zoom appointment exists, it should have meeting_host_url distinct from meeting_join_url"""
        # Get list of appointments to find a Zoom one
        response = api_client.get(f"{BASE_URL}/api/appointments/")
        assert response.status_code == 200
        
        data = response.json()
        appointments = data.get("appointments", [])
        
        # Find a Zoom appointment
        zoom_apt = None
        for apt in appointments:
            provider = (apt.get("meeting_provider") or "").lower()
            if provider == "zoom":
                zoom_apt = apt
                break
        
        if not zoom_apt:
            pytest.skip("No Zoom appointment found for testing")
        
        # Get full appointment details
        apt_id = zoom_apt.get("appointment_id")
        detail_response = api_client.get(f"{BASE_URL}/api/appointments/{apt_id}")
        assert detail_response.status_code == 200
        
        detail_data = detail_response.json()
        
        # Zoom should have both host_url and join_url
        host_url = detail_data.get("meeting_host_url")
        join_url = detail_data.get("meeting_join_url")
        
        if host_url:
            assert host_url != join_url, "Zoom host_url should be different from join_url"
            print(f"✓ Zoom appointment has distinct host_url and join_url")
        else:
            print(f"⚠ Zoom appointment found but no host_url (may not have been created via API)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
