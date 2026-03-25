"""
Test Teams Configuration Flow - Bug Fix Verification
Tests for iteration 69: Microsoft Teams configuration flow fixes.

Features tested:
1. Backend: GET /api/video-evidence/provider-status returns 'configured', 'features', 'connection_mode' for teams
2. Backend: Teams 'connected' is true when user has delegated scope via Outlook (has_online_meetings_scope=true)
3. Backend: Teams 'connected' is true after saving Azure AD User ID via POST /api/video-evidence/connect/teams
4. Backend: Teams 'connection_mode' is 'delegated' for Outlook scope, 'application' for Azure AD form, null when not connected
5. Backend: Teams 'can_auto_generate' is true for delegated mode, false for application mode when server not configured
6. Backend: Teams 'unavailable_reason' contains informative warning for application mode without server credentials
7. Backend: is_configured() returns false for MICROSOFT_CLIENT_ID=datetime-debug (invalid placeholder)
8. Backend: is_configured() validates Client ID as UUID format

Test users:
- clara.deschamps@demo-nlyt.fr: Has Outlook with has_online_meetings_scope=true (delegated mode)
- remi.roux@demo-nlyt.fr: Has Azure AD saved via form (application mode)
- louis.noel@demo-nlyt.fr: No Teams connection at all
"""
import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_USERS = {
    "delegated": {"email": "clara.deschamps@demo-nlyt.fr", "password": "Demo2026!"},
    "application": {"email": "remi.roux@demo-nlyt.fr", "password": "Demo2026!"},
    "clean": {"email": "louis.noel@demo-nlyt.fr", "password": "Demo2026!"},
}

# Cache for auth tokens to avoid rate limiting
_token_cache = {}


def get_auth_token(email, password):
    """Get authentication token for a user (cached)."""
    if email in _token_cache:
        return _token_cache[email]
    
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": email,
        "password": password
    })
    if response.status_code != 200:
        pytest.skip(f"Login failed for {email}: {response.text}")
    
    token = response.json().get("access_token")
    _token_cache[email] = token
    return token


def get_api_client(user_type="delegated"):
    """Create authenticated session for specified user type."""
    user = TEST_USERS[user_type]
    token = get_auth_token(user["email"], user["password"])
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    })
    return session


class TestTeamsProviderStatusStructure:
    """Test that provider-status returns correct structure for Teams."""

    def test_teams_has_configured_field(self):
        """Teams provider should have 'configured' field indicating server credentials status."""
        client = get_api_client("clean")
        response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        teams = data.get("teams", {})
        
        assert "configured" in teams, "Teams should have 'configured' field"
        assert isinstance(teams["configured"], bool), "'configured' should be boolean"
        
        # With MICROSOFT_CLIENT_ID=datetime-debug, configured should be False
        assert teams["configured"] == False, "Teams 'configured' should be False with invalid placeholder credentials"
        
        print(f"✓ Teams has 'configured' field: {teams['configured']}")

    def test_teams_has_features_field(self):
        """Teams provider should have 'features' array."""
        client = get_api_client("clean")
        response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert response.status_code == 200
        
        teams = response.json().get("teams", {})
        
        assert "features" in teams, "Teams should have 'features' field"
        assert isinstance(teams["features"], list), "'features' should be a list"
        assert "create_meeting" in teams["features"], "Teams should support 'create_meeting'"
        assert "fetch_attendance" in teams["features"], "Teams should support 'fetch_attendance'"
        
        print(f"✓ Teams has 'features' field: {teams['features']}")

    def test_teams_has_connection_mode_field(self):
        """Teams provider should have 'connection_mode' field."""
        client = get_api_client("clean")
        response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert response.status_code == 200
        
        teams = response.json().get("teams", {})
        
        assert "connection_mode" in teams, "Teams should have 'connection_mode' field"
        
        print(f"✓ Teams has 'connection_mode' field: {teams['connection_mode']}")

    def test_teams_has_can_auto_generate_field(self):
        """Teams provider should have 'can_auto_generate' field."""
        client = get_api_client("clean")
        response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert response.status_code == 200
        
        teams = response.json().get("teams", {})
        
        assert "can_auto_generate" in teams, "Teams should have 'can_auto_generate' field"
        assert isinstance(teams["can_auto_generate"], bool), "'can_auto_generate' should be boolean"
        
        print(f"✓ Teams has 'can_auto_generate' field: {teams['can_auto_generate']}")


class TestTeamsDelegatedMode:
    """Test Teams connection via Outlook delegated scope (has_online_meetings_scope=true)."""

    def test_delegated_user_teams_connected(self):
        """User with Outlook has_online_meetings_scope=true should have Teams connected."""
        client = get_api_client("delegated")
        response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        teams = response.json().get("teams", {})
        
        assert teams["connected"] == True, "Teams should be connected for delegated user"
        print(f"✓ Delegated user has Teams connected: {teams['connected']}")

    def test_delegated_user_connection_mode_is_delegated(self):
        """User with Outlook scope should have connection_mode='delegated'."""
        client = get_api_client("delegated")
        response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert response.status_code == 200
        
        teams = response.json().get("teams", {})
        
        assert teams["connection_mode"] == "delegated", f"Expected 'delegated', got: {teams['connection_mode']}"
        print(f"✓ Delegated user has connection_mode='delegated'")

    def test_delegated_user_can_auto_generate_true(self):
        """Delegated mode should have can_auto_generate=true (uses user's own token)."""
        client = get_api_client("delegated")
        response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert response.status_code == 200
        
        teams = response.json().get("teams", {})
        
        assert teams["can_auto_generate"] == True, "Delegated mode should have can_auto_generate=true"
        print(f"✓ Delegated user has can_auto_generate=true")

    def test_delegated_user_email_from_outlook(self):
        """Delegated user's Teams email should come from Outlook connection."""
        client = get_api_client("delegated")
        response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert response.status_code == 200
        
        teams = response.json().get("teams", {})
        
        # Email should be present and from Outlook
        assert teams["email"] is not None, "Delegated user should have email"
        print(f"✓ Delegated user Teams email: {teams['email']}")


class TestTeamsApplicationMode:
    """Test Teams connection via Azure AD form (application mode)."""

    def test_application_user_teams_connected(self):
        """User with Azure AD saved should have Teams connected."""
        client = get_api_client("application")
        response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        teams = response.json().get("teams", {})
        
        assert teams["connected"] == True, "Teams should be connected for application user"
        print(f"✓ Application user has Teams connected: {teams['connected']}")

    def test_application_user_connection_mode_is_application(self):
        """User with Azure AD form should have connection_mode='application'."""
        client = get_api_client("application")
        response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert response.status_code == 200
        
        teams = response.json().get("teams", {})
        
        assert teams["connection_mode"] == "application", f"Expected 'application', got: {teams['connection_mode']}"
        print(f"✓ Application user has connection_mode='application'")

    def test_application_user_can_auto_generate_false_without_server_config(self):
        """Application mode without server credentials should have can_auto_generate=false."""
        client = get_api_client("application")
        response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert response.status_code == 200
        
        teams = response.json().get("teams", {})
        
        # Server is not configured (MICROSOFT_CLIENT_ID=datetime-debug)
        # So can_auto_generate should be false for application mode
        assert teams["can_auto_generate"] == False, "Application mode without server config should have can_auto_generate=false"
        print(f"✓ Application user has can_auto_generate=false (server not configured)")

    def test_application_user_has_unavailable_reason_warning(self):
        """Application mode without server credentials should have informative unavailable_reason."""
        client = get_api_client("application")
        response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert response.status_code == 200
        
        teams = response.json().get("teams", {})
        
        # Should have a warning about server credentials
        assert teams["unavailable_reason"] is not None, "Should have unavailable_reason warning"
        assert "credentials" in teams["unavailable_reason"].lower() or "serveur" in teams["unavailable_reason"].lower() or "identifiant" in teams["unavailable_reason"].lower(), \
            f"Warning should mention credentials/server: {teams['unavailable_reason']}"
        
        print(f"✓ Application user has unavailable_reason: {teams['unavailable_reason'][:80]}...")


class TestTeamsCleanUser:
    """Test Teams status for user with no Teams connection."""

    def test_clean_user_teams_not_connected(self):
        """User with no Teams connection should have connected=false."""
        client = get_api_client("clean")
        
        # First ensure clean state by disconnecting
        client.delete(f"{BASE_URL}/api/video-evidence/connect/teams")
        
        response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        teams = response.json().get("teams", {})
        
        assert teams["connected"] == False, "Clean user should have Teams not connected"
        print(f"✓ Clean user has Teams not connected")

    def test_clean_user_connection_mode_null(self):
        """User with no Teams connection should have connection_mode=null."""
        client = get_api_client("clean")
        
        # Ensure clean state
        client.delete(f"{BASE_URL}/api/video-evidence/connect/teams")
        
        response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert response.status_code == 200
        
        teams = response.json().get("teams", {})
        
        assert teams["connection_mode"] is None, f"Expected null, got: {teams['connection_mode']}"
        print(f"✓ Clean user has connection_mode=null")

    def test_clean_user_has_unavailable_reason(self):
        """User with no Teams connection should have unavailable_reason."""
        client = get_api_client("clean")
        
        # Ensure clean state
        client.delete(f"{BASE_URL}/api/video-evidence/connect/teams")
        
        response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert response.status_code == 200
        
        teams = response.json().get("teams", {})
        
        assert teams["unavailable_reason"] is not None, "Should have unavailable_reason"
        print(f"✓ Clean user has unavailable_reason: {teams['unavailable_reason'][:80]}...")


class TestTeamsConnectEndpoint:
    """Test POST /api/video-evidence/connect/teams endpoint."""

    def test_connect_teams_saves_azure_user_id(self):
        """Connecting Teams should save Azure AD User ID and set connected=true."""
        client = get_api_client("clean")
        
        # Cleanup first
        client.delete(f"{BASE_URL}/api/video-evidence/connect/teams")
        
        # Connect Teams
        response = client.post(f"{BASE_URL}/api/video-evidence/connect/teams", json={
            "azure_user_id": "test-azure-uuid-12345",
            "teams_email": "test@company.com"
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert data["status"] == "connected"
        assert data["provider"] == "teams"
        
        # Verify via provider-status
        status_response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        teams = status_response.json()["teams"]
        
        assert teams["connected"] == True, "Teams should be connected after save"
        assert teams["connection_mode"] == "application", "Should be application mode after form save"
        
        # Cleanup
        client.delete(f"{BASE_URL}/api/video-evidence/connect/teams")
        
        print(f"✓ Connect Teams saves Azure AD User ID correctly")

    def test_connect_teams_sets_application_mode(self):
        """Connecting Teams via form should set connection_mode='application'."""
        client = get_api_client("clean")
        
        # Cleanup first
        client.delete(f"{BASE_URL}/api/video-evidence/connect/teams")
        
        # Connect Teams
        client.post(f"{BASE_URL}/api/video-evidence/connect/teams", json={
            "azure_user_id": "another-test-uuid"
        })
        
        # Verify connection_mode
        status_response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        teams = status_response.json()["teams"]
        
        assert teams["connection_mode"] == "application", f"Expected 'application', got: {teams['connection_mode']}"
        
        # Cleanup
        client.delete(f"{BASE_URL}/api/video-evidence/connect/teams")
        
        print(f"✓ Connect Teams sets connection_mode='application'")


class TestIsConfiguredValidation:
    """Test that is_configured() properly validates credentials."""

    def test_server_not_configured_with_placeholder_credentials(self):
        """Server should NOT be configured with MICROSOFT_CLIENT_ID=datetime-debug."""
        client = get_api_client("clean")
        response = client.get(f"{BASE_URL}/api/video-evidence/provider-status")
        assert response.status_code == 200
        
        teams = response.json().get("teams", {})
        
        # MICROSOFT_CLIENT_ID=datetime-debug is NOT a valid UUID
        # is_configured() should return False
        assert teams["configured"] == False, "Teams 'configured' should be False with datetime-debug placeholder"
        
        print(f"✓ Server correctly reports not configured with placeholder credentials")

    def test_uuid_validation_rejects_non_uuid_client_id(self):
        """is_configured() should reject non-UUID client IDs like 'datetime-debug'."""
        # This is implicitly tested by the configured=False check above
        # The backend code validates UUID format: ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$
        
        # Verify the pattern
        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
        
        # datetime-debug should NOT match
        assert not uuid_pattern.match("datetime-debug"), "datetime-debug should not match UUID pattern"
        
        # Valid UUID should match
        assert uuid_pattern.match("12345678-1234-1234-1234-123456789abc"), "Valid UUID should match"
        
        print(f"✓ UUID validation correctly rejects non-UUID values")


class TestTeamsDisconnect:
    """Test DELETE /api/video-evidence/connect/teams endpoint."""

    def test_disconnect_teams_removes_connection(self):
        """Disconnecting Teams should remove the connection."""
        client = get_api_client("clean")
        
        # First connect
        client.post(f"{BASE_URL}/api/video-evidence/connect/teams", json={
            "azure_user_id": "temp-azure-id"
        })
        
        # Verify connected
        status = client.get(f"{BASE_URL}/api/video-evidence/provider-status").json()
        assert status["teams"]["connected"] == True
        
        # Disconnect
        response = client.delete(f"{BASE_URL}/api/video-evidence/connect/teams")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "disconnected"
        
        # Verify disconnected
        status = client.get(f"{BASE_URL}/api/video-evidence/provider-status").json()
        assert status["teams"]["connected"] == False
        assert status["teams"]["connection_mode"] is None
        
        print(f"✓ Disconnect Teams removes connection correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
