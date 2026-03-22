"""
Test Meeting Provider Validation
Tests for the MeetingProvider enum validation in appointment creation:
1. Valid enum values (zoom, teams, meet, external) should be accepted
2. Invalid values (e.g., 'skype') should return Pydantic validation error
3. External provider requires meeting_join_url
4. Provider status endpoint returns correct connection status
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"
WORKSPACE_ID = "7e219321-18fd-4643-9be6-e4f1de88a2a8"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
    data = response.json()
    return data.get("access_token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


def get_future_datetime():
    """Get a datetime 2 days in the future"""
    future = datetime.now() + timedelta(days=2)
    return future.strftime("%Y-%m-%dT%H:%M:%S")


class TestMeetingProviderValidation:
    """Tests for MeetingProvider enum validation"""

    def test_valid_provider_zoom(self, auth_headers):
        """Test 1: POST /api/appointments/ with meeting_provider='zoom' (valid enum) should create appointment"""
        payload = {
            "workspace_id": WORKSPACE_ID,
            "title": "TEST_Zoom Meeting Provider Test",
            "appointment_type": "video",
            "meeting_provider": "zoom",
            "start_datetime": get_future_datetime(),
            "duration_minutes": 30,
            "tolerated_delay_minutes": 10,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "affected_compensation_percent": 80,
            "charity_percent": 0,
            "participants": [
                {"first_name": "Test", "last_name": "User", "email": "test@example.com", "role": "participant"}
            ]
        }
        response = requests.post(f"{BASE_URL}/api/appointments/", json=payload, headers=auth_headers)
        
        # Should succeed (201 or 200) - meeting creation may fail but appointment should be created
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        data = response.json()
        assert "appointment_id" in data, "Response should contain appointment_id"
        print(f"✓ Zoom provider accepted, appointment created: {data.get('appointment_id')}")

    def test_valid_provider_teams(self, auth_headers):
        """Test: POST /api/appointments/ with meeting_provider='teams' (valid enum) should create appointment"""
        payload = {
            "workspace_id": WORKSPACE_ID,
            "title": "TEST_Teams Meeting Provider Test",
            "appointment_type": "video",
            "meeting_provider": "teams",
            "start_datetime": get_future_datetime(),
            "duration_minutes": 30,
            "tolerated_delay_minutes": 10,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "affected_compensation_percent": 80,
            "charity_percent": 0,
            "participants": [
                {"first_name": "Test", "last_name": "User", "email": "test@example.com", "role": "participant"}
            ]
        }
        response = requests.post(f"{BASE_URL}/api/appointments/", json=payload, headers=auth_headers)
        
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        data = response.json()
        assert "appointment_id" in data, "Response should contain appointment_id"
        print(f"✓ Teams provider accepted, appointment created: {data.get('appointment_id')}")

    def test_valid_provider_meet(self, auth_headers):
        """Test: POST /api/appointments/ with meeting_provider='meet' (valid enum) should create appointment"""
        payload = {
            "workspace_id": WORKSPACE_ID,
            "title": "TEST_Meet Meeting Provider Test",
            "appointment_type": "video",
            "meeting_provider": "meet",
            "start_datetime": get_future_datetime(),
            "duration_minutes": 30,
            "tolerated_delay_minutes": 10,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "affected_compensation_percent": 80,
            "charity_percent": 0,
            "participants": [
                {"first_name": "Test", "last_name": "User", "email": "test@example.com", "role": "participant"}
            ]
        }
        response = requests.post(f"{BASE_URL}/api/appointments/", json=payload, headers=auth_headers)
        
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        data = response.json()
        assert "appointment_id" in data, "Response should contain appointment_id"
        print(f"✓ Meet provider accepted, appointment created: {data.get('appointment_id')}")

    def test_invalid_provider_skype(self, auth_headers):
        """Test 2: POST /api/appointments/ with meeting_provider='skype' (invalid) should return Pydantic validation error"""
        payload = {
            "workspace_id": WORKSPACE_ID,
            "title": "TEST_Invalid Provider Test",
            "appointment_type": "video",
            "meeting_provider": "skype",  # Invalid - not in MeetingProvider enum
            "start_datetime": get_future_datetime(),
            "duration_minutes": 30,
            "tolerated_delay_minutes": 10,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "affected_compensation_percent": 80,
            "charity_percent": 0,
            "participants": [
                {"first_name": "Test", "last_name": "User", "email": "test@example.com", "role": "participant"}
            ]
        }
        response = requests.post(f"{BASE_URL}/api/appointments/", json=payload, headers=auth_headers)
        
        # Should fail with 422 Unprocessable Entity (Pydantic validation error)
        assert response.status_code == 422, f"Expected 422 for invalid provider, got {response.status_code}: {response.text}"
        data = response.json()
        # Check that error mentions meeting_provider or enum validation
        error_str = str(data).lower()
        assert "meeting_provider" in error_str or "enum" in error_str or "value is not a valid" in error_str, \
            f"Error should mention meeting_provider validation: {data}"
        print(f"✓ Invalid provider 'skype' correctly rejected with 422: {data}")

    def test_external_provider_without_url(self, auth_headers):
        """Test 3: POST /api/appointments/ with meeting_provider='external' without meeting_join_url should return 400"""
        payload = {
            "workspace_id": WORKSPACE_ID,
            "title": "TEST_External Without URL Test",
            "appointment_type": "video",
            "meeting_provider": "external",
            # No meeting_join_url provided
            "start_datetime": get_future_datetime(),
            "duration_minutes": 30,
            "tolerated_delay_minutes": 10,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "affected_compensation_percent": 80,
            "charity_percent": 0,
            "participants": [
                {"first_name": "Test", "last_name": "User", "email": "test@example.com", "role": "participant"}
            ]
        }
        response = requests.post(f"{BASE_URL}/api/appointments/", json=payload, headers=auth_headers)
        
        # Should fail with 400 Bad Request
        assert response.status_code == 400, f"Expected 400 for external without URL, got {response.status_code}: {response.text}"
        data = response.json()
        # Check error message mentions URL requirement
        error_detail = data.get("detail", "")
        assert "url" in error_detail.lower() or "lien" in error_detail.lower(), \
            f"Error should mention URL requirement: {data}"
        print(f"✓ External provider without URL correctly rejected with 400: {data}")

    def test_external_provider_with_url(self, auth_headers):
        """Test 4: POST /api/appointments/ with meeting_provider='external' + meeting_join_url should create appointment"""
        payload = {
            "workspace_id": WORKSPACE_ID,
            "title": "TEST_External With URL Test",
            "appointment_type": "video",
            "meeting_provider": "external",
            "meeting_join_url": "https://zoom.us/j/123456789",  # External URL provided
            "start_datetime": get_future_datetime(),
            "duration_minutes": 30,
            "tolerated_delay_minutes": 10,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "affected_compensation_percent": 80,
            "charity_percent": 0,
            "participants": [
                {"first_name": "Test", "last_name": "User", "email": "test@example.com", "role": "participant"}
            ]
        }
        response = requests.post(f"{BASE_URL}/api/appointments/", json=payload, headers=auth_headers)
        
        # Should succeed
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        data = response.json()
        assert "appointment_id" in data, "Response should contain appointment_id"
        print(f"✓ External provider with URL accepted, appointment created: {data.get('appointment_id')}")


class TestProviderStatusEndpoint:
    """Tests for GET /api/video-evidence/provider-status"""

    def test_provider_status_returns_all_providers(self, auth_headers):
        """Test 5: GET /api/video-evidence/provider-status should return meet/zoom/teams with status"""
        response = requests.get(f"{BASE_URL}/api/video-evidence/provider-status", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should have meet, zoom, teams keys
        assert "meet" in data, "Response should contain 'meet' provider"
        assert "zoom" in data, "Response should contain 'zoom' provider"
        assert "teams" in data, "Response should contain 'teams' provider"
        
        # Each provider should have 'connected' field
        for provider in ["meet", "zoom", "teams"]:
            assert "connected" in data[provider], f"{provider} should have 'connected' field"
            assert isinstance(data[provider]["connected"], bool), f"{provider}.connected should be boolean"
        
        print(f"✓ Provider status endpoint returns all providers: meet={data['meet']['connected']}, zoom={data['zoom']['connected']}, teams={data['teams']['connected']}")

    def test_meet_connected_via_google_calendar(self, auth_headers):
        """Test: Google Meet should show connected if Google Calendar is connected"""
        response = requests.get(f"{BASE_URL}/api/video-evidence/provider-status", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # For test user, Google Calendar is connected, so Meet should be connected
        meet_info = data.get("meet", {})
        assert meet_info.get("connected") == True, f"Meet should be connected via Google Calendar: {meet_info}"
        
        # Should have label indicating it's via Google Calendar
        label = meet_info.get("label", "")
        assert "google" in label.lower() or "calendar" in label.lower() or meet_info.get("via_google_calendar"), \
            f"Meet should indicate it's via Google Calendar: {meet_info}"
        
        print(f"✓ Google Meet connected via Google Calendar: {meet_info}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
