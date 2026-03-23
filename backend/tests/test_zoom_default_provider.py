"""
Test Zoom as Default Provider Feature
=====================================
Tests for the new Zoom-as-default-provider feature:
- GET /api/video-evidence/provider-status returns correct structure for zoom, teams, meet
- Zoom has mode='central', universal=true
- Teams has mode='user'
- Meet has mode='user'
- Each provider has 'description' field
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test user."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=15
    )
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.status_code} - {response.text[:200]}")
    data = response.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestProviderStatusEndpoint:
    """Tests for GET /api/video-evidence/provider-status"""

    def test_provider_status_returns_200(self, auth_headers):
        """Provider status endpoint should return 200."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers,
            timeout=15
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        print("PASS: Provider status endpoint returns 200")

    def test_provider_status_has_zoom(self, auth_headers):
        """Provider status should include zoom provider."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers,
            timeout=15
        )
        data = response.json()
        assert "zoom" in data, f"Expected 'zoom' in response, got keys: {list(data.keys())}"
        print("PASS: Provider status includes 'zoom'")

    def test_provider_status_has_teams(self, auth_headers):
        """Provider status should include teams provider."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers,
            timeout=15
        )
        data = response.json()
        assert "teams" in data, f"Expected 'teams' in response, got keys: {list(data.keys())}"
        print("PASS: Provider status includes 'teams'")

    def test_provider_status_has_meet(self, auth_headers):
        """Provider status should include meet provider."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers,
            timeout=15
        )
        data = response.json()
        assert "meet" in data, f"Expected 'meet' in response, got keys: {list(data.keys())}"
        print("PASS: Provider status includes 'meet'")


class TestZoomProviderStructure:
    """Tests for Zoom provider structure in provider-status response."""

    def test_zoom_has_mode_central(self, auth_headers):
        """Zoom should have mode='central' (platform-level config, no user account required)."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers,
            timeout=15
        )
        data = response.json()
        zoom = data.get("zoom", {})
        assert zoom.get("mode") == "central", f"Expected zoom.mode='central', got '{zoom.get('mode')}'"
        print("PASS: Zoom has mode='central'")

    def test_zoom_has_universal_true(self, auth_headers):
        """Zoom should have universal=true (no user account required)."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers,
            timeout=15
        )
        data = response.json()
        zoom = data.get("zoom", {})
        assert zoom.get("universal") is True, f"Expected zoom.universal=True, got '{zoom.get('universal')}'"
        print("PASS: Zoom has universal=True")

    def test_zoom_has_description(self, auth_headers):
        """Zoom should have a description field."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers,
            timeout=15
        )
        data = response.json()
        zoom = data.get("zoom", {})
        assert "description" in zoom, f"Expected 'description' in zoom, got keys: {list(zoom.keys())}"
        assert isinstance(zoom["description"], str), f"Expected description to be string, got {type(zoom['description'])}"
        assert len(zoom["description"]) > 0, "Expected non-empty description"
        print(f"PASS: Zoom has description: '{zoom['description']}'")

    def test_zoom_has_label(self, auth_headers):
        """Zoom should have label='Zoom'."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers,
            timeout=15
        )
        data = response.json()
        zoom = data.get("zoom", {})
        assert zoom.get("label") == "Zoom", f"Expected zoom.label='Zoom', got '{zoom.get('label')}'"
        print("PASS: Zoom has label='Zoom'")

    def test_zoom_connected_status(self, auth_headers):
        """Zoom connected status should be boolean (false if not configured)."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers,
            timeout=15
        )
        data = response.json()
        zoom = data.get("zoom", {})
        assert "connected" in zoom, f"Expected 'connected' in zoom, got keys: {list(zoom.keys())}"
        assert isinstance(zoom["connected"], bool), f"Expected connected to be bool, got {type(zoom['connected'])}"
        print(f"PASS: Zoom has connected={zoom['connected']} (bool)")


class TestTeamsProviderStructure:
    """Tests for Teams provider structure in provider-status response."""

    def test_teams_has_mode_user(self, auth_headers):
        """Teams should have mode='user' (requires user account)."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers,
            timeout=15
        )
        data = response.json()
        teams = data.get("teams", {})
        assert teams.get("mode") == "user", f"Expected teams.mode='user', got '{teams.get('mode')}'"
        print("PASS: Teams has mode='user'")

    def test_teams_has_description(self, auth_headers):
        """Teams should have a description field."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers,
            timeout=15
        )
        data = response.json()
        teams = data.get("teams", {})
        assert "description" in teams, f"Expected 'description' in teams, got keys: {list(teams.keys())}"
        assert isinstance(teams["description"], str), f"Expected description to be string, got {type(teams['description'])}"
        print(f"PASS: Teams has description: '{teams['description']}'")

    def test_teams_has_label(self, auth_headers):
        """Teams should have label='Microsoft Teams'."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers,
            timeout=15
        )
        data = response.json()
        teams = data.get("teams", {})
        assert teams.get("label") == "Microsoft Teams", f"Expected teams.label='Microsoft Teams', got '{teams.get('label')}'"
        print("PASS: Teams has label='Microsoft Teams'")

    def test_teams_connected_status(self, auth_headers):
        """Teams connected status should be boolean."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers,
            timeout=15
        )
        data = response.json()
        teams = data.get("teams", {})
        assert "connected" in teams, f"Expected 'connected' in teams, got keys: {list(teams.keys())}"
        assert isinstance(teams["connected"], bool), f"Expected connected to be bool, got {type(teams['connected'])}"
        print(f"PASS: Teams has connected={teams['connected']} (bool)")


class TestMeetProviderStructure:
    """Tests for Meet provider structure in provider-status response."""

    def test_meet_has_mode_user(self, auth_headers):
        """Meet should have mode='user' (requires Google account)."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers,
            timeout=15
        )
        data = response.json()
        meet = data.get("meet", {})
        assert meet.get("mode") == "user", f"Expected meet.mode='user', got '{meet.get('mode')}'"
        print("PASS: Meet has mode='user'")

    def test_meet_has_description(self, auth_headers):
        """Meet should have a description field."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers,
            timeout=15
        )
        data = response.json()
        meet = data.get("meet", {})
        assert "description" in meet, f"Expected 'description' in meet, got keys: {list(meet.keys())}"
        assert isinstance(meet["description"], str), f"Expected description to be string, got {type(meet['description'])}"
        print(f"PASS: Meet has description: '{meet['description']}'")

    def test_meet_has_label(self, auth_headers):
        """Meet should have label='Google Meet'."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers,
            timeout=15
        )
        data = response.json()
        meet = data.get("meet", {})
        assert meet.get("label") == "Google Meet", f"Expected meet.label='Google Meet', got '{meet.get('label')}'"
        print("PASS: Meet has label='Google Meet'")

    def test_meet_connected_status(self, auth_headers):
        """Meet connected status should be boolean."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers,
            timeout=15
        )
        data = response.json()
        meet = data.get("meet", {})
        assert "connected" in meet, f"Expected 'connected' in meet, got keys: {list(meet.keys())}"
        assert isinstance(meet["connected"], bool), f"Expected connected to be bool, got {type(meet['connected'])}"
        print(f"PASS: Meet has connected={meet['connected']} (bool)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
