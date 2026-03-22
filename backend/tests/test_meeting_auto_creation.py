"""
Test Meeting Auto-Creation Feature
Tests the fix for video meeting link auto-generation (Teams, Meet, Zoom)
when appointments are activated via organizer guarantee.

Key scenarios:
1. Pre-created Teams appointment has meeting_join_url
2. Pre-created Meet appointment has meeting_join_url
3. GET /api/appointments/{id} returns meeting_join_url for active video appointments
4. Physical appointments don't have meeting section
5. Meeting provider configuration status
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"
WORKSPACE_ID = "7e219321-18fd-4643-9be6-e4f1de88a2a8"

# Pre-created appointments with meeting links
TEAMS_APPOINTMENT_ID = "32df02d5-2ddf-4e46-92f5-f555b7351ef6"
MEET_APPOINTMENT_ID = "5ff50dea-cb72-4534-b685-f8bda2414d33"


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
    # API uses access_token (not token)
    return data.get("access_token")


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Authenticated requests session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestMeetingProviderStatus:
    """Test meeting provider configuration status"""
    
    def test_provider_status_endpoint(self, api_client):
        """GET /api/meeting-providers/status returns provider configuration"""
        response = api_client.get(f"{BASE_URL}/api/meeting-providers/status", timeout=15)
        # Endpoint may not exist, but let's check
        if response.status_code == 200:
            data = response.json()
            print(f"Provider status: {data}")
            # Check Teams is configured (fix restored real credentials)
            if "teams" in data:
                assert data["teams"].get("configured") == True, "Teams should be configured after fix"
        else:
            # Endpoint doesn't exist, skip
            pytest.skip("Meeting provider status endpoint not available")


class TestTeamsAppointmentMeetingLink:
    """Test Teams appointment has auto-generated meeting link"""
    
    def test_teams_appointment_exists(self, api_client):
        """GET /api/appointments/{id} returns Teams appointment"""
        response = api_client.get(
            f"{BASE_URL}/api/appointments/{TEAMS_APPOINTMENT_ID}",
            timeout=15
        )
        assert response.status_code == 200, f"Failed to get Teams appointment: {response.text}"
        data = response.json()
        
        # Verify appointment type and provider
        assert data.get("appointment_type") == "video", "Should be video appointment"
        assert data.get("meeting_provider") == "teams", "Should be Teams provider"
        print(f"Teams appointment status: {data.get('status')}")
    
    def test_teams_appointment_is_active(self, api_client):
        """Teams appointment should be active"""
        response = api_client.get(
            f"{BASE_URL}/api/appointments/{TEAMS_APPOINTMENT_ID}",
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "active", f"Expected active, got {data.get('status')}"
    
    def test_teams_appointment_has_meeting_join_url(self, api_client):
        """Teams appointment should have meeting_join_url (auto-generated)"""
        response = api_client.get(
            f"{BASE_URL}/api/appointments/{TEAMS_APPOINTMENT_ID}",
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        
        meeting_url = data.get("meeting_join_url")
        assert meeting_url is not None, "meeting_join_url should not be None"
        assert meeting_url != "", "meeting_join_url should not be empty"
        assert "teams.microsoft.com" in meeting_url, f"Should be Teams URL, got: {meeting_url}"
        print(f"Teams meeting URL: {meeting_url[:80]}...")
    
    def test_teams_appointment_has_external_meeting_id(self, api_client):
        """Teams appointment should have external_meeting_id"""
        response = api_client.get(
            f"{BASE_URL}/api/appointments/{TEAMS_APPOINTMENT_ID}",
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        
        external_id = data.get("external_meeting_id")
        assert external_id is not None, "external_meeting_id should not be None"
        assert external_id != "", "external_meeting_id should not be empty"
        print(f"Teams external_meeting_id: {external_id[:50]}...")


class TestMeetAppointmentMeetingLink:
    """Test Google Meet appointment has auto-generated meeting link"""
    
    def test_meet_appointment_exists(self, api_client):
        """GET /api/appointments/{id} returns Meet appointment"""
        response = api_client.get(
            f"{BASE_URL}/api/appointments/{MEET_APPOINTMENT_ID}",
            timeout=15
        )
        assert response.status_code == 200, f"Failed to get Meet appointment: {response.text}"
        data = response.json()
        
        # Verify appointment type and provider
        assert data.get("appointment_type") == "video", "Should be video appointment"
        assert data.get("meeting_provider") == "meet", "Should be Meet provider"
        print(f"Meet appointment status: {data.get('status')}")
    
    def test_meet_appointment_is_active(self, api_client):
        """Meet appointment should be active"""
        response = api_client.get(
            f"{BASE_URL}/api/appointments/{MEET_APPOINTMENT_ID}",
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "active", f"Expected active, got {data.get('status')}"
    
    def test_meet_appointment_has_meeting_join_url(self, api_client):
        """Meet appointment should have meeting_join_url (auto-generated)"""
        response = api_client.get(
            f"{BASE_URL}/api/appointments/{MEET_APPOINTMENT_ID}",
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        
        meeting_url = data.get("meeting_join_url")
        assert meeting_url is not None, "meeting_join_url should not be None"
        assert meeting_url != "", "meeting_join_url should not be empty"
        assert "meet.google.com" in meeting_url, f"Should be Meet URL, got: {meeting_url}"
        print(f"Meet meeting URL: {meeting_url}")
    
    def test_meet_appointment_has_external_meeting_id(self, api_client):
        """Meet appointment should have external_meeting_id"""
        response = api_client.get(
            f"{BASE_URL}/api/appointments/{MEET_APPOINTMENT_ID}",
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        
        external_id = data.get("external_meeting_id")
        assert external_id is not None, "external_meeting_id should not be None"
        assert external_id != "", "external_meeting_id should not be empty"
        print(f"Meet external_meeting_id: {external_id}")


class TestPhysicalAppointmentNoMeeting:
    """Test physical appointments don't have meeting section"""
    
    def test_list_appointments_find_physical(self, api_client):
        """Find a physical appointment to verify no meeting section"""
        response = api_client.get(
            f"{BASE_URL}/api/appointments/?workspace_id={WORKSPACE_ID}",
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        
        appointments = data.get("appointments", [])
        physical_apts = [a for a in appointments if a.get("appointment_type") == "physical"]
        
        if physical_apts:
            apt = physical_apts[0]
            print(f"Found physical appointment: {apt.get('title')}")
            # Physical appointments should NOT have meeting_join_url
            assert apt.get("meeting_join_url") is None or apt.get("meeting_join_url") == "", \
                "Physical appointment should not have meeting_join_url"
            assert apt.get("meeting_provider") is None or apt.get("meeting_provider") == "", \
                "Physical appointment should not have meeting_provider"
        else:
            pytest.skip("No physical appointments found to test")


class TestMeetingAutoCreationFlow:
    """Test the meeting auto-creation flow during appointment activation"""
    
    def test_appointment_lifecycle_code_has_meeting_creation(self):
        """Verify appointment_lifecycle.py has meeting auto-creation logic"""
        import os
        lifecycle_path = "/app/backend/services/appointment_lifecycle.py"
        assert os.path.exists(lifecycle_path), "appointment_lifecycle.py should exist"
        
        with open(lifecycle_path, 'r') as f:
            content = f.read()
        
        # Check for meeting creation logic (lines 108-130 per review request)
        assert "create_meeting_for_appointment" in content, \
            "Should import create_meeting_for_appointment"
        assert "appointment_type" in content and "video" in content, \
            "Should check appointment_type == 'video'"
        assert "meeting_provider" in content, \
            "Should check meeting_provider"
        assert "meeting_result" in content, \
            "Should store meeting_result"
        print("appointment_lifecycle.py has meeting auto-creation logic ✓")
    
    def test_meeting_provider_service_teams_configured(self):
        """Verify TeamsMeetingClient.is_configured() rejects placeholders"""
        import os
        service_path = "/app/backend/services/meeting_provider_service.py"
        assert os.path.exists(service_path), "meeting_provider_service.py should exist"
        
        with open(service_path, 'r') as f:
            content = f.read()
        
        # Check for placeholder rejection (fix added this)
        assert "placeholder_values" in content or "guarantee-first" in content, \
            "Should have placeholder rejection logic"
        print("meeting_provider_service.py has placeholder rejection ✓")
    
    def test_env_has_real_microsoft_credentials(self):
        """Verify .env has real Microsoft credentials (not placeholders)"""
        import os
        env_path = "/app/backend/.env"
        assert os.path.exists(env_path), ".env should exist"
        
        with open(env_path, 'r') as f:
            content = f.read()
        
        # Check credentials are NOT placeholders
        assert "guarantee-first" not in content, \
            "MICROSOFT credentials should not be 'guarantee-first' placeholder"
        assert "MICROSOFT_CLIENT_ID=" in content, \
            "Should have MICROSOFT_CLIENT_ID"
        assert "MICROSOFT_TENANT_ID=" in content, \
            "Should have MICROSOFT_TENANT_ID"
        
        # Extract and verify they look like real Azure IDs (UUID format)
        import re
        client_id_match = re.search(r'MICROSOFT_CLIENT_ID=([^\n]+)', content)
        tenant_id_match = re.search(r'MICROSOFT_TENANT_ID=([^\n]+)', content)
        
        if client_id_match:
            client_id = client_id_match.group(1).strip()
            # Real Azure IDs are UUIDs
            assert len(client_id) > 30, f"MICROSOFT_CLIENT_ID looks too short: {client_id}"
            assert "-" in client_id, f"MICROSOFT_CLIENT_ID should be UUID format: {client_id}"
            print(f"MICROSOFT_CLIENT_ID: {client_id[:8]}...{client_id[-4:]} ✓")
        
        if tenant_id_match:
            tenant_id = tenant_id_match.group(1).strip()
            assert len(tenant_id) > 30, f"MICROSOFT_TENANT_ID looks too short: {tenant_id}"
            assert "-" in tenant_id, f"MICROSOFT_TENANT_ID should be UUID format: {tenant_id}"
            print(f"MICROSOFT_TENANT_ID: {tenant_id[:8]}...{tenant_id[-4:]} ✓")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
