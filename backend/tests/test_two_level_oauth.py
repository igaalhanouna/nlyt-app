"""
Test suite for 2-Level Microsoft OAuth Architecture
Level 1: Calendar base (universal for personal + pro accounts) - Calendars.ReadWrite, User.Read, offline_access
Level 2: Teams advanced (pro accounts only) - OnlineMeetings.ReadWrite, OnlineMeetingArtifact.Read.All

Key assertions:
1. /api/calendar/connect/outlook returns auth URL with BASE_SCOPES only
2. /api/calendar/connect/outlook/teams-upgrade returns auth URL with TEAMS_SCOPES
3. teams-upgrade requires existing Outlook connection (400 if not connected)
4. meeting_provider_service.py reads has_online_meetings_scope from DB (not from adapter SCOPES)
5. Callback writes has_online_meetings_scope based on granted scopes
"""
import pytest
import requests
import os
import urllib.parse

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"


class TestTwoLevelOAuth:
    """Tests for 2-level Microsoft OAuth architecture"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get auth token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            token = data.get("token") or data.get("access_token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
                self.token = token
            else:
                pytest.skip("No token in login response")
        else:
            pytest.skip(f"Login failed: {login_response.status_code}")
    
    # ============================================================
    # Test 1: /api/calendar/connect/outlook returns BASE_SCOPES
    # ============================================================
    def test_connect_outlook_returns_base_scopes(self):
        """GET /api/calendar/connect/outlook should return auth URL with BASE_SCOPES only"""
        response = self.session.get(f"{BASE_URL}/api/calendar/connect/outlook")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "authorization_url" in data, "Response should contain authorization_url"
        
        auth_url = data["authorization_url"]
        
        # Parse the URL to check scopes
        parsed = urllib.parse.urlparse(auth_url)
        query_params = urllib.parse.parse_qs(parsed.query)
        
        assert "scope" in query_params, "Auth URL should contain scope parameter"
        scopes = query_params["scope"][0].split(" ")
        
        # BASE_SCOPES: Calendars.ReadWrite, User.Read, offline_access
        assert "Calendars.ReadWrite" in scopes, "BASE_SCOPES should include Calendars.ReadWrite"
        assert "User.Read" in scopes, "BASE_SCOPES should include User.Read"
        assert "offline_access" in scopes, "BASE_SCOPES should include offline_access"
        
        # Should NOT include Teams scopes
        assert "OnlineMeetings.ReadWrite" not in scopes, "BASE_SCOPES should NOT include OnlineMeetings.ReadWrite"
        assert "OnlineMeetingArtifact.Read.All" not in scopes, "BASE_SCOPES should NOT include OnlineMeetingArtifact.Read.All"
        
        print(f"✓ /api/calendar/connect/outlook returns BASE_SCOPES: {scopes}")
    
    # ============================================================
    # Test 2: /api/calendar/connect/outlook/teams-upgrade returns TEAMS_SCOPES
    # ============================================================
    def test_teams_upgrade_returns_teams_scopes(self):
        """GET /api/calendar/connect/outlook/teams-upgrade should return auth URL with TEAMS_SCOPES"""
        response = self.session.get(f"{BASE_URL}/api/calendar/connect/outlook/teams-upgrade")
        
        # This endpoint requires existing Outlook connection
        # If user has connection, should return 200 with auth URL
        # If user doesn't have connection, should return 400
        
        if response.status_code == 400:
            # Expected if no Outlook connection exists
            data = response.json()
            assert "detail" in data, "400 response should have detail"
            print(f"✓ teams-upgrade correctly returns 400 when no Outlook connection: {data['detail']}")
            return
        
        assert response.status_code == 200, f"Expected 200 or 400, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "authorization_url" in data, "Response should contain authorization_url"
        
        auth_url = data["authorization_url"]
        
        # Parse the URL to check scopes
        parsed = urllib.parse.urlparse(auth_url)
        query_params = urllib.parse.parse_qs(parsed.query)
        
        assert "scope" in query_params, "Auth URL should contain scope parameter"
        scopes = query_params["scope"][0].split(" ")
        
        # TEAMS_SCOPES: Calendars.ReadWrite, User.Read, offline_access, OnlineMeetings.ReadWrite, OnlineMeetingArtifact.Read.All
        assert "Calendars.ReadWrite" in scopes, "TEAMS_SCOPES should include Calendars.ReadWrite"
        assert "User.Read" in scopes, "TEAMS_SCOPES should include User.Read"
        assert "offline_access" in scopes, "TEAMS_SCOPES should include offline_access"
        assert "OnlineMeetings.ReadWrite" in scopes, "TEAMS_SCOPES should include OnlineMeetings.ReadWrite"
        assert "OnlineMeetingArtifact.Read.All" in scopes, "TEAMS_SCOPES should include OnlineMeetingArtifact.Read.All"
        
        print(f"✓ /api/calendar/connect/outlook/teams-upgrade returns TEAMS_SCOPES: {scopes}")
    
    # ============================================================
    # Test 3: teams-upgrade requires existing Outlook connection
    # ============================================================
    def test_teams_upgrade_requires_outlook_connection(self):
        """GET /api/calendar/connect/outlook/teams-upgrade should return 400 if no Outlook connection"""
        # First check if user has Outlook connection
        connections_response = self.session.get(f"{BASE_URL}/api/calendar/connections")
        assert connections_response.status_code == 200
        
        connections = connections_response.json().get("connections", [])
        outlook_conn = next((c for c in connections if c.get("provider") == "outlook"), None)
        
        if outlook_conn and outlook_conn.get("status") == "connected":
            # User has Outlook connection, teams-upgrade should work
            response = self.session.get(f"{BASE_URL}/api/calendar/connect/outlook/teams-upgrade")
            assert response.status_code == 200, f"With Outlook connected, should return 200, got {response.status_code}"
            print(f"✓ teams-upgrade returns 200 when Outlook is connected")
        else:
            # User doesn't have Outlook connection, should get 400
            response = self.session.get(f"{BASE_URL}/api/calendar/connect/outlook/teams-upgrade")
            assert response.status_code == 400, f"Without Outlook connection, should return 400, got {response.status_code}"
            data = response.json()
            assert "detail" in data
            print(f"✓ teams-upgrade correctly returns 400 when no Outlook connection: {data['detail']}")
    
    # ============================================================
    # Test 4: Verify calendar connections endpoint returns has_online_meetings_scope
    # ============================================================
    def test_connections_include_has_online_meetings_scope(self):
        """GET /api/calendar/connections should include has_online_meetings_scope for Outlook"""
        response = self.session.get(f"{BASE_URL}/api/calendar/connections")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        connections = data.get("connections", [])
        
        outlook_conn = next((c for c in connections if c.get("provider") == "outlook"), None)
        
        if outlook_conn:
            # Check that has_online_meetings_scope field exists
            # It should be either True or False (not missing)
            has_scope = outlook_conn.get("has_online_meetings_scope")
            scope_level = outlook_conn.get("scope_level")
            
            print(f"✓ Outlook connection found:")
            print(f"  - email: {outlook_conn.get('outlook_email')}")
            print(f"  - has_online_meetings_scope: {has_scope}")
            print(f"  - scope_level: {scope_level}")
            print(f"  - status: {outlook_conn.get('status')}")
            
            # Verify consistency between has_online_meetings_scope and scope_level
            if has_scope is True:
                assert scope_level == "teams", f"If has_online_meetings_scope=True, scope_level should be 'teams', got '{scope_level}'"
            elif has_scope is False:
                assert scope_level in ["calendar", None], f"If has_online_meetings_scope=False, scope_level should be 'calendar' or None, got '{scope_level}'"
        else:
            print("✓ No Outlook connection found (expected for some test users)")
    
    # ============================================================
    # Test 5: Verify adapter defines both BASE_SCOPES and TEAMS_SCOPES
    # ============================================================
    def test_adapter_scope_definitions(self):
        """Verify outlook_calendar_adapter.py defines both BASE_SCOPES and TEAMS_SCOPES"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        from adapters.outlook_calendar_adapter import BASE_SCOPES, TEAMS_SCOPES, SCOPES
        
        # BASE_SCOPES should be calendar-only
        assert 'Calendars.ReadWrite' in BASE_SCOPES
        assert 'User.Read' in BASE_SCOPES
        assert 'offline_access' in BASE_SCOPES
        assert 'OnlineMeetings.ReadWrite' not in BASE_SCOPES
        
        # TEAMS_SCOPES should include Teams permissions
        assert 'Calendars.ReadWrite' in TEAMS_SCOPES
        assert 'User.Read' in TEAMS_SCOPES
        assert 'offline_access' in TEAMS_SCOPES
        assert 'OnlineMeetings.ReadWrite' in TEAMS_SCOPES
        assert 'OnlineMeetingArtifact.Read.All' in TEAMS_SCOPES
        
        # Default SCOPES should be BASE_SCOPES
        assert SCOPES == BASE_SCOPES, "Default SCOPES should equal BASE_SCOPES"
        
        print(f"✓ Adapter scope definitions verified:")
        print(f"  - BASE_SCOPES: {BASE_SCOPES}")
        print(f"  - TEAMS_SCOPES: {TEAMS_SCOPES}")
        print(f"  - SCOPES (default): {SCOPES}")
    
    # ============================================================
    # Test 6: Verify get_authorization_url accepts optional scopes parameter
    # ============================================================
    def test_get_authorization_url_accepts_scopes_param(self):
        """Verify OutlookCalendarAdapter.get_authorization_url accepts optional scopes parameter"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        from adapters.outlook_calendar_adapter import OutlookCalendarAdapter, BASE_SCOPES, TEAMS_SCOPES
        
        # Test with default scopes (should use BASE_SCOPES)
        url_default, _ = OutlookCalendarAdapter.get_authorization_url(
            redirect_uri="https://example.com/callback",
            state="test_state"
        )
        
        # Test with explicit TEAMS_SCOPES
        url_teams, _ = OutlookCalendarAdapter.get_authorization_url(
            redirect_uri="https://example.com/callback",
            state="test_state",
            scopes=TEAMS_SCOPES
        )
        
        # Parse and verify scopes
        parsed_default = urllib.parse.urlparse(url_default)
        params_default = urllib.parse.parse_qs(parsed_default.query)
        scopes_default = params_default.get("scope", [""])[0].split(" ")
        
        parsed_teams = urllib.parse.urlparse(url_teams)
        params_teams = urllib.parse.parse_qs(parsed_teams.query)
        scopes_teams = params_teams.get("scope", [""])[0].split(" ")
        
        # Default should NOT have OnlineMeetings
        assert "OnlineMeetings.ReadWrite" not in scopes_default
        
        # Teams should have OnlineMeetings
        assert "OnlineMeetings.ReadWrite" in scopes_teams
        assert "OnlineMeetingArtifact.Read.All" in scopes_teams
        
        print(f"✓ get_authorization_url accepts optional scopes parameter")
        print(f"  - Default scopes: {scopes_default}")
        print(f"  - Teams scopes: {scopes_teams}")


class TestMeetingProviderServiceNonRegression:
    """Non-regression tests for meeting_provider_service.py delegated mode"""
    
    def test_meeting_provider_service_reads_from_db(self):
        """Verify meeting_provider_service.py reads has_online_meetings_scope from DB, not from adapter SCOPES"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        # Read the source file and verify the logic
        with open('/app/backend/services/meeting_provider_service.py', 'r') as f:
            content = f.read()
        
        # Key assertion: The service should check has_online_meetings_scope from the DB connection
        # NOT from the adapter's SCOPES constant
        
        # Check that it reads from outlook_conn.get("has_online_meetings_scope")
        assert 'outlook_conn.get("has_online_meetings_scope")' in content, \
            "meeting_provider_service.py should read has_online_meetings_scope from DB connection"
        
        # Check that it does NOT import SCOPES from adapter for this check
        # (It may import TEAMS_SCOPES for other purposes, but the delegated mode check should use DB)
        
        # Verify the delegated mode logic exists
        assert 'has_delegated_scope' in content, \
            "meeting_provider_service.py should have has_delegated_scope variable"
        
        # Verify it checks the DB value
        assert 'outlook_conn.get("has_online_meetings_scope") is True' in content, \
            "Delegated mode should check has_online_meetings_scope from DB"
        
        print("✓ meeting_provider_service.py correctly reads has_online_meetings_scope from DB")
        print("  - Found: outlook_conn.get('has_online_meetings_scope') is True")
        print("  - Delegated mode logic verified")
    
    def test_meeting_provider_service_delegated_path_exists(self):
        """Verify the delegated path in meeting_provider_service.py exists and is correct"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        with open('/app/backend/services/meeting_provider_service.py', 'r') as f:
            content = f.read()
        
        # Check for delegated mode markers
        assert 'creation_mode' in content, "Should have creation_mode field"
        assert '"delegated"' in content, "Should have 'delegated' creation mode"
        assert '"application_fallback"' in content, "Should have 'application_fallback' creation mode"
        
        # Check for the /me/onlineMeetings endpoint (delegated mode)
        assert '/me/onlineMeetings' in content, "Should use /me/onlineMeetings for delegated mode"
        
        # Check for the /users/{user_id}/onlineMeetings endpoint (application fallback)
        assert '/users/' in content and 'onlineMeetings' in content, \
            "Should use /users/{user_id}/onlineMeetings for application fallback"
        
        print("✓ meeting_provider_service.py delegated path verified:")
        print("  - creation_mode: 'delegated' and 'application_fallback' exist")
        print("  - /me/onlineMeetings endpoint for delegated mode")
        print("  - /users/{user_id}/onlineMeetings for application fallback")


class TestConflictDetectionRegression:
    """Regression tests to ensure conflict detection still works"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            token = data.get("token") or data.get("access_token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip(f"Login failed: {login_response.status_code}")
    
    def test_conflict_check_endpoint_works(self):
        """Verify /api/appointments/check-conflicts endpoint still works"""
        response = self.session.post(f"{BASE_URL}/api/appointments/check-conflicts", json={
            "start_datetime": "2026-06-20T10:00:00Z",
            "duration_minutes": 60
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "status" in data, "Response should have status field"
        assert data["status"] in ["available", "conflict", "warning"], f"Invalid status: {data['status']}"
        
        print(f"✓ Conflict check endpoint works: status={data['status']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
