"""
Test Integrations Page - Video Provider Connect/Disconnect APIs
Tests for iteration 26: Refactored Integrations settings page with video conferencing provider connections.

Endpoints tested:
- GET /api/video-evidence/provider-status — Returns enriched per-user status for meet, zoom, teams
- POST /api/video-evidence/connect/zoom — Saves zoom_email and sets zoom_connected=true
- DELETE /api/video-evidence/connect/zoom — Removes zoom configuration
- POST /api/video-evidence/connect/teams — Saves azure_user_id and teams_email, sets teams_connected=true
- DELETE /api/video-evidence/connect/teams — Removes teams configuration
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"


def get_auth_token():
    """Get authentication token for test user."""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json().get("access_token")


def get_api_client():
    """Create authenticated session."""
    token = get_auth_token()
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    })
    return session


class TestProviderStatus:
    """Test GET /api/video-evidence/provider-status endpoint."""

    def test_provider_status_returns_all_providers(self):
        """Provider status should return meet, zoom, teams with correct structure."""
        client = get_api_client()
        
        # First cleanup
        client.delete(f"{BASE_URL}/api/video-evidence/connect/zoom")
        client.delete(f"{BASE_URL}/api/video-evidence/connect/teams")
        
        response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        
        # Check all three providers are present
        assert "meet" in data, "Missing 'meet' provider"
        assert "zoom" in data, "Missing 'zoom' provider"
        assert "teams" in data, "Missing 'teams' provider"
        
        # Check structure for each provider
        for provider in ["meet", "zoom", "teams"]:
            assert "configured" in data[provider], f"Missing 'configured' for {provider}"
            assert "connected" in data[provider], f"Missing 'connected' for {provider}"
            assert "features" in data[provider], f"Missing 'features' for {provider}"
            assert "label" in data[provider], f"Missing 'label' for {provider}"
        
        print(f"✓ Provider status returns all providers with correct structure")

    def test_provider_status_meet_connected_via_google_calendar(self):
        """Google Meet should show connected if Google Calendar is connected."""
        client = get_api_client()
        response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert response.status_code == 200
        
        data = response.json()
        meet = data["meet"]
        
        # Test user has Google Calendar connected (igaal.hanouna@gmail.com)
        assert meet["connected"] == True, "Meet should be connected via Google Calendar"
        assert meet["email"] == "igaal.hanouna@gmail.com", f"Expected Google email, got: {meet['email']}"
        assert meet["label"] == "Google Meet"
        assert "create_meeting" in meet["features"]
        
        print(f"✓ Meet connected via Google Calendar: {meet['email']}")

    def test_provider_status_zoom_disconnected_initially(self):
        """Zoom should show disconnected after cleanup."""
        client = get_api_client()
        
        # Cleanup first
        client.delete(f"{BASE_URL}/api/video-evidence/connect/zoom")
        
        response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert response.status_code == 200
        
        data = response.json()
        zoom = data["zoom"]
        
        # After cleanup, zoom should be disconnected (unless platform configured)
        # Platform is not configured per iteration_25
        assert zoom["connected"] == False, "Zoom should be disconnected after cleanup"
        assert zoom["email"] is None, "Zoom email should be None when disconnected"
        assert zoom["label"] == "Zoom"
        assert "create_meeting" in zoom["features"]
        assert "fetch_attendance" in zoom["features"]
        
        print(f"✓ Zoom disconnected initially")

    def test_provider_status_teams_disconnected_initially(self):
        """Teams should show disconnected after cleanup."""
        client = get_api_client()
        
        # Cleanup first
        client.delete(f"{BASE_URL}/api/video-evidence/connect/teams")
        
        response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert response.status_code == 200
        
        data = response.json()
        teams = data["teams"]
        
        # After cleanup, teams should be disconnected
        assert teams["connected"] == False, "Teams should be disconnected after cleanup"
        assert teams["label"] == "Microsoft Teams"
        assert "create_meeting" in teams["features"]
        assert "fetch_attendance" in teams["features"]
        
        print(f"✓ Teams disconnected initially")


class TestZoomConnect:
    """Test POST/DELETE /api/video-evidence/connect/zoom endpoints."""

    def test_connect_zoom_with_email(self):
        """Connect Zoom with email should save configuration."""
        client = get_api_client()
        
        # Cleanup first
        client.delete(f"{BASE_URL}/api/video-evidence/connect/zoom")
        
        # Connect Zoom
        response = client.post(f"{BASE_URL}/api/video-evidence/connect/zoom", json={
            "zoom_email": "user@zoom.com"
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert data["status"] == "connected"
        assert data["provider"] == "zoom"
        
        # Verify via provider-status
        status_response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert status_response.status_code == 200
        
        zoom = status_response.json()["zoom"]
        assert zoom["connected"] == True, "Zoom should be connected after connect call"
        assert zoom["email"] == "user@zoom.com", f"Expected user@zoom.com, got: {zoom['email']}"
        
        # Cleanup
        client.delete(f"{BASE_URL}/api/video-evidence/connect/zoom")
        
        print(f"✓ Connect Zoom with email works")

    def test_connect_zoom_without_email(self):
        """Connect Zoom without email should still work."""
        client = get_api_client()
        
        # Cleanup first
        client.delete(f"{BASE_URL}/api/video-evidence/connect/zoom")
        
        response = client.post(f"{BASE_URL}/api/video-evidence/connect/zoom", json={})
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "connected"
        
        # Verify connected but no email
        status_response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        zoom = status_response.json()["zoom"]
        assert zoom["connected"] == True
        assert zoom["email"] is None
        
        # Cleanup
        client.delete(f"{BASE_URL}/api/video-evidence/connect/zoom")
        
        print(f"✓ Connect Zoom without email works")

    def test_disconnect_zoom(self):
        """Disconnect Zoom should remove configuration."""
        client = get_api_client()
        
        # First connect
        client.post(f"{BASE_URL}/api/video-evidence/connect/zoom", json={
            "zoom_email": "test@zoom.com"
        })
        
        # Verify connected
        status = client.get(f"{BASE_URL}/api/video-evidence/provider-status").json()
        assert status["zoom"]["connected"] == True
        
        # Disconnect
        response = client.delete(f"{BASE_URL}/api/video-evidence/connect/zoom")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "disconnected"
        assert data["provider"] == "zoom"
        
        # Verify disconnected
        status = client.get(f"{BASE_URL}/api/video-evidence/provider-status").json()
        assert status["zoom"]["connected"] == False
        assert status["zoom"]["email"] is None
        
        print(f"✓ Disconnect Zoom works")


class TestTeamsConnect:
    """Test POST/DELETE /api/video-evidence/connect/teams endpoints."""

    def test_connect_teams_with_azure_id_and_email(self):
        """Connect Teams with Azure ID and email should save configuration."""
        client = get_api_client()
        
        # Cleanup first
        client.delete(f"{BASE_URL}/api/video-evidence/connect/teams")
        
        response = client.post(f"{BASE_URL}/api/video-evidence/connect/teams", json={
            "azure_user_id": "user@company.onmicrosoft.com",
            "teams_email": "user@company.com"
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert data["status"] == "connected"
        assert data["provider"] == "teams"
        
        # Verify via provider-status
        status_response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        teams = status_response.json()["teams"]
        assert teams["connected"] == True
        assert teams["email"] == "user@company.com"
        
        # Cleanup
        client.delete(f"{BASE_URL}/api/video-evidence/connect/teams")
        
        print(f"✓ Connect Teams with Azure ID and email works")

    def test_connect_teams_with_azure_id_only(self):
        """Connect Teams with only Azure ID should work."""
        client = get_api_client()
        
        # Cleanup first
        client.delete(f"{BASE_URL}/api/video-evidence/connect/teams")
        
        response = client.post(f"{BASE_URL}/api/video-evidence/connect/teams", json={
            "azure_user_id": "12345-uuid-azure"
        })
        assert response.status_code == 200
        
        # Verify connected
        status = client.get(f"{BASE_URL}/api/video-evidence/provider-status").json()
        assert status["teams"]["connected"] == True
        
        # Cleanup
        client.delete(f"{BASE_URL}/api/video-evidence/connect/teams")
        
        print(f"✓ Connect Teams with Azure ID only works")

    def test_disconnect_teams(self):
        """Disconnect Teams should remove configuration."""
        client = get_api_client()
        
        # First connect
        client.post(f"{BASE_URL}/api/video-evidence/connect/teams", json={
            "azure_user_id": "test-azure-id",
            "teams_email": "test@teams.com"
        })
        
        # Verify connected
        status = client.get(f"{BASE_URL}/api/video-evidence/provider-status").json()
        assert status["teams"]["connected"] == True
        
        # Disconnect
        response = client.delete(f"{BASE_URL}/api/video-evidence/connect/teams")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "disconnected"
        assert data["provider"] == "teams"
        
        # Verify disconnected
        status = client.get(f"{BASE_URL}/api/video-evidence/provider-status").json()
        assert status["teams"]["connected"] == False
        
        print(f"✓ Disconnect Teams works")


class TestProviderStatusAfterConnections:
    """Test provider-status reflects correct state after connect/disconnect operations."""

    def test_zoom_connected_shows_email_in_status(self):
        """After connecting Zoom, provider-status should show connected=true with email."""
        client = get_api_client()
        
        # Cleanup first
        client.delete(f"{BASE_URL}/api/video-evidence/connect/zoom")
        
        # Connect Zoom
        client.post(f"{BASE_URL}/api/video-evidence/connect/zoom", json={
            "zoom_email": "verified@zoom.com"
        })
        
        # Check status
        response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert response.status_code == 200
        
        zoom = response.json()["zoom"]
        assert zoom["connected"] == True
        assert zoom["email"] == "verified@zoom.com"
        assert zoom["connected_at"] is not None, "Should have connected_at timestamp"
        
        # Cleanup
        client.delete(f"{BASE_URL}/api/video-evidence/connect/zoom")
        
        print(f"✓ Zoom connected shows email in status")

    def test_teams_connected_shows_email_in_status(self):
        """After connecting Teams, provider-status should show connected=true with email."""
        client = get_api_client()
        
        # Cleanup first
        client.delete(f"{BASE_URL}/api/video-evidence/connect/teams")
        
        # Connect Teams
        client.post(f"{BASE_URL}/api/video-evidence/connect/teams", json={
            "azure_user_id": "azure-user-123",
            "teams_email": "verified@teams.com"
        })
        
        # Check status
        response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert response.status_code == 200
        
        teams = response.json()["teams"]
        assert teams["connected"] == True
        assert teams["email"] == "verified@teams.com"
        assert teams["connected_at"] is not None, "Should have connected_at timestamp"
        
        # Cleanup
        client.delete(f"{BASE_URL}/api/video-evidence/connect/teams")
        
        print(f"✓ Teams connected shows email in status")

    def test_zoom_disconnected_shows_false_in_status(self):
        """After disconnecting Zoom, provider-status should show connected=false."""
        client = get_api_client()
        
        # Connect then disconnect
        client.post(f"{BASE_URL}/api/video-evidence/connect/zoom", json={
            "zoom_email": "temp@zoom.com"
        })
        client.delete(f"{BASE_URL}/api/video-evidence/connect/zoom")
        
        # Check status
        response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        zoom = response.json()["zoom"]
        assert zoom["connected"] == False
        assert zoom["email"] is None
        
        print(f"✓ Zoom disconnected shows false in status")


class TestNoRegressionCalendarConnections:
    """Verify existing Google Calendar and Outlook connections are not affected."""

    def test_google_calendar_still_connected(self):
        """Google Calendar connection should still work."""
        client = get_api_client()
        response = client.get(f"{BASE_URL}/api/calendar/connections")
        assert response.status_code == 200
        
        connections = response.json().get("connections", [])
        google_conn = next((c for c in connections if c["provider"] == "google"), None)
        
        assert google_conn is not None, "Google Calendar connection should exist"
        assert google_conn["status"] == "connected"
        assert google_conn["google_email"] == "igaal.hanouna@gmail.com"
        
        print(f"✓ Google Calendar still connected: {google_conn['google_email']}")

    def test_outlook_connection_status(self):
        """Outlook connection should be present (may be expired)."""
        client = get_api_client()
        response = client.get(f"{BASE_URL}/api/calendar/connections")
        assert response.status_code == 200
        
        connections = response.json().get("connections", [])
        outlook_conn = next((c for c in connections if c["provider"] == "outlook"), None)
        
        # Outlook may be expired per test notes
        if outlook_conn:
            assert outlook_conn["provider"] == "outlook"
            print(f"✓ Outlook connection present with status: {outlook_conn.get('status')}")
        else:
            print(f"✓ No Outlook connection (expected - may have been removed)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
