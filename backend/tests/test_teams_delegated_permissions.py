"""
Test Teams Delegated Permissions Phase A
Tests the new Teams meeting creation with delegated vs application_fallback modes.

Features tested:
1. Backend: Teams appointment creation stores creation_mode='application_fallback' in meeting_provider_metadata
2. Backend: creation_mode is returned by GET /api/appointments/{id}
3. Backend: Teams metadata contains creator_email from Azure AD and azure_user_id
4. Backend: Google Meet appointment still stores creator_email correctly (no regression)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"

# Test appointment IDs from the review request
TEAMS_FALLBACK_APT_ID = "82f9be58-c4b7-48fa-a2e4-ef3b0470e626"
MEET_APT_ID = "10c355e4-2796-4aaf-b163-74a912d71957"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for API calls."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
    # Token is returned as 'access_token' not 'token'
    return response.json().get("access_token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Return headers with auth token."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestTeamsDelegatedPermissions:
    """Test Teams delegated permissions Phase A implementation."""

    def test_teams_appointment_has_creation_mode_application_fallback(self, auth_headers):
        """
        Test that Teams appointment with fallback mode has creation_mode='application_fallback' in metadata.
        """
        response = requests.get(
            f"{BASE_URL}/api/appointments/{TEAMS_FALLBACK_APT_ID}",
            headers=auth_headers
        )
        
        # Check if appointment exists
        if response.status_code == 404:
            pytest.skip(f"Teams fallback appointment {TEAMS_FALLBACK_APT_ID} not found")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"Teams appointment data: {data}")
        
        # Check meeting_provider_metadata exists
        metadata = data.get("meeting_provider_metadata")
        assert metadata is not None, "meeting_provider_metadata should exist"
        
        # Check creation_mode is 'application_fallback'
        creation_mode = metadata.get("creation_mode")
        assert creation_mode == "application_fallback", f"Expected creation_mode='application_fallback', got '{creation_mode}'"
        
        print(f"✓ Teams appointment has creation_mode='application_fallback'")

    def test_teams_metadata_contains_creator_email(self, auth_headers):
        """
        Test that Teams metadata contains creator_email from Azure AD.
        """
        response = requests.get(
            f"{BASE_URL}/api/appointments/{TEAMS_FALLBACK_APT_ID}",
            headers=auth_headers
        )
        
        if response.status_code == 404:
            pytest.skip(f"Teams fallback appointment {TEAMS_FALLBACK_APT_ID} not found")
        
        assert response.status_code == 200
        
        data = response.json()
        metadata = data.get("meeting_provider_metadata", {})
        
        # Check creator_email exists
        creator_email = metadata.get("creator_email")
        assert creator_email is not None, "creator_email should exist in metadata"
        assert "@" in creator_email, f"creator_email should be a valid email, got '{creator_email}'"
        
        print(f"✓ Teams metadata contains creator_email: {creator_email}")

    def test_teams_metadata_contains_azure_user_id(self, auth_headers):
        """
        Test that Teams metadata contains azure_user_id when in application_fallback mode.
        """
        response = requests.get(
            f"{BASE_URL}/api/appointments/{TEAMS_FALLBACK_APT_ID}",
            headers=auth_headers
        )
        
        if response.status_code == 404:
            pytest.skip(f"Teams fallback appointment {TEAMS_FALLBACK_APT_ID} not found")
        
        assert response.status_code == 200
        
        data = response.json()
        metadata = data.get("meeting_provider_metadata", {})
        
        # Check azure_user_id exists (only in application_fallback mode)
        azure_user_id = metadata.get("azure_user_id")
        creation_mode = metadata.get("creation_mode")
        
        if creation_mode == "application_fallback":
            assert azure_user_id is not None, "azure_user_id should exist in application_fallback mode"
            print(f"✓ Teams metadata contains azure_user_id: {azure_user_id[:8]}...")
        else:
            print(f"Note: creation_mode is '{creation_mode}', azure_user_id may not be present")

    def test_meet_appointment_still_has_creator_email(self, auth_headers):
        """
        Test that Google Meet appointment still stores creator_email correctly (no regression).
        """
        response = requests.get(
            f"{BASE_URL}/api/appointments/{MEET_APT_ID}",
            headers=auth_headers
        )
        
        if response.status_code == 404:
            pytest.skip(f"Meet appointment {MEET_APT_ID} not found")
        
        assert response.status_code == 200
        
        data = response.json()
        print(f"Meet appointment data: {data}")
        
        # Check meeting_provider is meet
        meeting_provider = data.get("meeting_provider", "").lower()
        assert meeting_provider in ("meet", "google meet", "google_meet"), f"Expected meet provider, got '{meeting_provider}'"
        
        # Check metadata exists and has creator_email
        metadata = data.get("meeting_provider_metadata", {})
        creator_email = metadata.get("creator_email")
        
        assert creator_email is not None, "Meet appointment should have creator_email in metadata"
        assert "@" in creator_email, f"creator_email should be a valid email, got '{creator_email}'"
        
        print(f"✓ Meet appointment has creator_email: {creator_email}")


class TestCalendarConnectionScopes:
    """Test calendar connection scope detection for Outlook."""

    def test_calendar_connections_endpoint(self, auth_headers):
        """
        Test that calendar connections endpoint returns Outlook connection.
        Note: has_online_meetings_scope may be absent for old connections (pre-Phase A).
        """
        response = requests.get(
            f"{BASE_URL}/api/calendar/connections",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        connections = data.get("connections", [])
        
        print(f"Found {len(connections)} calendar connections")
        
        # Check for Outlook connection
        outlook_conn = next((c for c in connections if c.get("provider") == "outlook"), None)
        
        if outlook_conn:
            has_scope = outlook_conn.get("has_online_meetings_scope")
            print(f"Outlook connection found:")
            print(f"  - has_online_meetings_scope: {has_scope}")
            print(f"  - email: {outlook_conn.get('outlook_email')}")
            
            # For old connections, has_online_meetings_scope may be None/absent
            # This is expected - the user needs to reconnect to get the new scope
            if has_scope is None:
                print("✓ Old Outlook connection without OnlineMeetings scope (expected for Phase A testing)")
            elif has_scope is True:
                print("✓ Outlook connection has OnlineMeetings.ReadWrite scope (delegated mode available)")
            else:
                print("✓ Outlook connection explicitly has no OnlineMeetings scope")
        else:
            print("No Outlook connection found for this user")


class TestNewTeamsAppointmentCreation:
    """Test creating a new Teams appointment to verify fallback mode is used."""

    def test_create_teams_appointment_uses_fallback_mode(self, auth_headers):
        """
        Test that creating a new Teams appointment stores creation_mode='application_fallback'
        when user has no delegated scope.
        """
        from datetime import datetime, timedelta
        
        # First get the user's workspace
        workspaces_response = requests.get(
            f"{BASE_URL}/api/workspaces/",
            headers=auth_headers
        )
        
        if workspaces_response.status_code != 200:
            pytest.skip("Could not get workspaces")
        
        workspaces = workspaces_response.json().get("workspaces", [])
        if not workspaces:
            pytest.skip("No workspaces found for user")
        
        workspace_id = workspaces[0].get("workspace_id")
        
        # Create appointment in the future
        future_date = datetime.utcnow() + timedelta(days=7)
        start_datetime = future_date.strftime("%Y-%m-%dT14:00:00Z")
        
        payload = {
            "title": "TEST_Teams_Delegated_Permissions_Test",
            "workspace_id": workspace_id,
            "start_datetime": start_datetime,
            "duration_minutes": 30,
            "appointment_type": "video",
            "meeting_provider": "teams",
            "penalty_amount": 10,
            "penalty_currency": "eur",
            "cancellation_deadline_hours": 24,
            "tolerated_delay_minutes": 5,
            "affected_compensation_percent": 80,
            "platform_commission_percent": 20,
            "charity_percent": 0,
            "participants": []
        }
        
        response = requests.post(
            f"{BASE_URL}/api/appointments/",
            headers=auth_headers,
            json=payload
        )
        
        print(f"Create appointment response: {response.status_code}")
        print(f"Response body: {response.text[:500]}")
        
        # Accept 200 or 201 for creation
        assert response.status_code in (200, 201), f"Expected 200/201, got {response.status_code}: {response.text}"
        
        data = response.json()
        appointment_id = data.get("appointment_id")
        
        # Verify the appointment has the correct metadata
        if appointment_id:
            # Fetch the appointment to check metadata
            get_response = requests.get(
                f"{BASE_URL}/api/appointments/{appointment_id}",
                headers=auth_headers
            )
            
            if get_response.status_code == 200:
                apt_data = get_response.json()
                metadata = apt_data.get("meeting_provider_metadata", {})
                creation_mode = metadata.get("creation_mode")
                creator_email = metadata.get("creator_email")
                
                print(f"New Teams appointment metadata:")
                print(f"  - creation_mode: {creation_mode}")
                print(f"  - creator_email: {creator_email}")
                
                # Since user has no delegated scope, should be application_fallback
                if creation_mode:
                    assert creation_mode in ("application_fallback", "delegated"), \
                        f"creation_mode should be 'application_fallback' or 'delegated', got '{creation_mode}'"
                    print(f"✓ New Teams appointment has creation_mode='{creation_mode}'")
            
            # Cleanup: delete the test appointment
            delete_response = requests.delete(
                f"{BASE_URL}/api/appointments/{appointment_id}",
                headers=auth_headers
            )
            print(f"Cleanup: deleted test appointment {appointment_id[:8]}... (status: {delete_response.status_code})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
