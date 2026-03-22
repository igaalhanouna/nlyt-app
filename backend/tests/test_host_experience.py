"""
Test Host Experience Improvements:
1. Teams: lobbyBypassSettings.scope='everyone' + allowedPresenters='organizer' in meeting creation payload
2. Meet: creator_email and creator_name in appointment metadata
3. Zoom: host_url vs join_url distinction (meeting_host_url field)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"

# Test appointment IDs
TEAMS_LOBBY_APT_ID = "87c58ee3-a512-4c17-a8ca-381d5519d98f"  # Teams with lobby bypass
MEET_CREATOR_APT_ID = "10c355e4-2796-4aaf-b163-74a912d71957"  # Meet with creator email
TEAMS_OLD_APT_ID = "32df02d5-2ddf-4e46-92f5-f555b7351ef6"  # Teams without lobby settings (pre-fix)


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=15
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("access_token")


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Authenticated requests session"""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    })
    return session


class TestTeamsLobbyBypassSettings:
    """Test Teams meeting creation includes lobbyBypassSettings and allowedPresenters"""
    
    def test_teams_appointment_has_lobby_bypass_scope(self, api_client):
        """Teams appointment metadata should contain lobby_bypass_scope='everyone'"""
        response = api_client.get(f"{BASE_URL}/api/appointments/{TEAMS_LOBBY_APT_ID}")
        assert response.status_code == 200, f"Failed to get appointment: {response.text}"
        
        data = response.json()
        metadata = data.get("meeting_provider_metadata", {})
        
        assert metadata.get("lobby_bypass_scope") == "everyone", \
            f"Expected lobby_bypass_scope='everyone', got: {metadata.get('lobby_bypass_scope')}"
    
    def test_teams_appointment_has_allowed_presenters(self, api_client):
        """Teams appointment metadata should contain allowed_presenters='organizer'"""
        response = api_client.get(f"{BASE_URL}/api/appointments/{TEAMS_LOBBY_APT_ID}")
        assert response.status_code == 200
        
        data = response.json()
        metadata = data.get("meeting_provider_metadata", {})
        
        assert metadata.get("allowed_presenters") == "organizer", \
            f"Expected allowed_presenters='organizer', got: {metadata.get('allowed_presenters')}"
    
    def test_teams_appointment_has_valid_join_url(self, api_client):
        """Teams appointment should have a valid teams.microsoft.com join URL"""
        response = api_client.get(f"{BASE_URL}/api/appointments/{TEAMS_LOBBY_APT_ID}")
        assert response.status_code == 200
        
        data = response.json()
        join_url = data.get("meeting_join_url")
        
        assert join_url is not None, "meeting_join_url should not be None"
        assert "teams.microsoft.com" in join_url, f"Expected teams.microsoft.com URL, got: {join_url}"
    
    def test_teams_appointment_has_no_host_url(self, api_client):
        """Teams appointments should have meeting_host_url=None (Teams doesn't have separate host URL)"""
        response = api_client.get(f"{BASE_URL}/api/appointments/{TEAMS_LOBBY_APT_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("meeting_host_url") is None, \
            f"Teams should not have meeting_host_url, got: {data.get('meeting_host_url')}"
    
    def test_old_teams_appointment_no_lobby_settings(self, api_client):
        """Previously created Teams appointment should NOT have lobby settings (pre-fix)"""
        response = api_client.get(f"{BASE_URL}/api/appointments/{TEAMS_OLD_APT_ID}")
        assert response.status_code == 200
        
        data = response.json()
        metadata = data.get("meeting_provider_metadata", {})
        
        # Old appointment should not have the new lobby settings
        assert "lobby_bypass_scope" not in metadata or metadata.get("lobby_bypass_scope") is None, \
            f"Old appointment should not have lobby_bypass_scope, got: {metadata}"


class TestMeetCreatorEmail:
    """Test Google Meet appointment includes creator_email and creator_name"""
    
    def test_meet_appointment_has_creator_email(self, api_client):
        """Meet appointment metadata should contain creator_email"""
        response = api_client.get(f"{BASE_URL}/api/appointments/{MEET_CREATOR_APT_ID}")
        assert response.status_code == 200, f"Failed to get appointment: {response.text}"
        
        data = response.json()
        metadata = data.get("meeting_provider_metadata", {})
        
        assert metadata.get("creator_email") is not None, \
            f"Expected creator_email in metadata, got: {metadata}"
        assert metadata.get("creator_email") == "igaal.hanouna@gmail.com", \
            f"Expected creator_email='igaal.hanouna@gmail.com', got: {metadata.get('creator_email')}"
    
    def test_meet_appointment_has_creator_name(self, api_client):
        """Meet appointment metadata should contain creator_name"""
        response = api_client.get(f"{BASE_URL}/api/appointments/{MEET_CREATOR_APT_ID}")
        assert response.status_code == 200
        
        data = response.json()
        metadata = data.get("meeting_provider_metadata", {})
        
        assert metadata.get("creator_name") is not None, \
            f"Expected creator_name in metadata, got: {metadata}"
    
    def test_meet_appointment_has_valid_join_url(self, api_client):
        """Meet appointment should have a valid meet.google.com join URL"""
        response = api_client.get(f"{BASE_URL}/api/appointments/{MEET_CREATOR_APT_ID}")
        assert response.status_code == 200
        
        data = response.json()
        join_url = data.get("meeting_join_url")
        
        assert join_url is not None, "meeting_join_url should not be None"
        assert "meet.google.com" in join_url, f"Expected meet.google.com URL, got: {join_url}"
    
    def test_meet_appointment_has_no_host_url(self, api_client):
        """Meet appointments should have meeting_host_url=None (Meet doesn't have separate host URL)"""
        response = api_client.get(f"{BASE_URL}/api/appointments/{MEET_CREATOR_APT_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("meeting_host_url") is None, \
            f"Meet should not have meeting_host_url, got: {data.get('meeting_host_url')}"


class TestMeetingProviderMetadataAPI:
    """Test that GET appointment returns meeting_provider_metadata with all new fields"""
    
    def test_teams_returns_full_metadata(self, api_client):
        """Teams appointment should return complete meeting_provider_metadata"""
        response = api_client.get(f"{BASE_URL}/api/appointments/{TEAMS_LOBBY_APT_ID}")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify all expected fields are present
        assert "meeting_provider_metadata" in data, "Response should include meeting_provider_metadata"
        assert "meeting_join_url" in data, "Response should include meeting_join_url"
        assert "meeting_host_url" in data, "Response should include meeting_host_url"
        assert "external_meeting_id" in data, "Response should include external_meeting_id"
        
        metadata = data["meeting_provider_metadata"]
        assert "lobby_bypass_scope" in metadata, "Teams metadata should include lobby_bypass_scope"
        assert "allowed_presenters" in metadata, "Teams metadata should include allowed_presenters"
    
    def test_meet_returns_full_metadata(self, api_client):
        """Meet appointment should return complete meeting_provider_metadata"""
        response = api_client.get(f"{BASE_URL}/api/appointments/{MEET_CREATOR_APT_ID}")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify all expected fields are present
        assert "meeting_provider_metadata" in data, "Response should include meeting_provider_metadata"
        assert "meeting_join_url" in data, "Response should include meeting_join_url"
        assert "meeting_host_url" in data, "Response should include meeting_host_url"
        assert "external_meeting_id" in data, "Response should include external_meeting_id"
        
        metadata = data["meeting_provider_metadata"]
        assert "creator_email" in metadata, "Meet metadata should include creator_email"
        assert "creator_name" in metadata, "Meet metadata should include creator_name"


class TestBackendCodeReview:
    """Verify backend code has correct implementation"""
    
    def test_teams_client_has_lobby_bypass_in_payload(self):
        """TeamsMeetingClient.create_meeting() should include lobbyBypassSettings in payload"""
        import re
        
        with open("/app/backend/services/meeting_provider_service.py", "r") as f:
            content = f.read()
        
        # Check for lobbyBypassSettings in Teams create_meeting
        assert "lobbyBypassSettings" in content, "Code should include lobbyBypassSettings"
        assert '"scope": "everyone"' in content or "'scope': 'everyone'" in content, \
            "lobbyBypassSettings should have scope='everyone'"
    
    def test_teams_client_has_allowed_presenters_in_payload(self):
        """TeamsMeetingClient.create_meeting() should include allowedPresenters in payload"""
        with open("/app/backend/services/meeting_provider_service.py", "r") as f:
            content = f.read()
        
        assert '"allowedPresenters": "organizer"' in content or "'allowedPresenters': 'organizer'" in content, \
            "Code should include allowedPresenters='organizer'"
    
    def test_teams_metadata_includes_lobby_settings(self):
        """Teams metadata should include lobby_bypass_scope and allowed_presenters"""
        with open("/app/backend/services/meeting_provider_service.py", "r") as f:
            content = f.read()
        
        assert "lobby_bypass_scope" in content, "Metadata should include lobby_bypass_scope"
        assert "allowed_presenters" in content, "Metadata should include allowed_presenters"
    
    def test_meet_enrichment_has_creator_email(self):
        """create_meeting_for_appointment() should enrich Meet metadata with creator_email"""
        with open("/app/backend/services/meeting_provider_service.py", "r") as f:
            content = f.read()
        
        assert "creator_email" in content, "Code should include creator_email enrichment"
        assert "google_email" in content, "Code should fetch google_email from calendar_connections"
    
    def test_meet_enrichment_has_creator_name(self):
        """create_meeting_for_appointment() should enrich Meet metadata with creator_name"""
        with open("/app/backend/services/meeting_provider_service.py", "r") as f:
            content = f.read()
        
        assert "creator_name" in content, "Code should include creator_name enrichment"
        assert "google_name" in content, "Code should fetch google_name from calendar_connections"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
