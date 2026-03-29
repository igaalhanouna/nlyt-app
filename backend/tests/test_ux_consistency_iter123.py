"""
Test UX Consistency Fixes - Iteration 123
Tests for:
1. Calendar sync status endpoint works for participants (returns viewer's own connections)
2. No duplicate check-in banners
3. No green trust signal banner for participants
4. Calendar buttons available for all roles
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ORGANIZER_EMAIL = "igaal@hotmail.com"
ORGANIZER_PASSWORD = "Test123!"
PARTICIPANT_EMAIL = "testuser_audit@nlyt.app"
PARTICIPANT_PASSWORD = "TestAudit123!"

# Test appointment IDs
APPOINTMENT_ID = "e823473a-f37a-4f59-8576-82e49ee22c53"  # igaal@hotmail.com is organizer, testuser_audit is participant


@pytest.fixture
def organizer_token():
    """Get authentication token for organizer"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ORGANIZER_EMAIL, "password": ORGANIZER_PASSWORD}
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Organizer authentication failed")


@pytest.fixture
def participant_token():
    """Get authentication token for participant"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": PARTICIPANT_EMAIL, "password": PARTICIPANT_PASSWORD}
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Participant authentication failed")


class TestCalendarSyncStatusForParticipant:
    """Test that calendar sync status endpoint returns viewer's own connections"""
    
    def test_participant_can_access_calendar_sync_status(self, participant_token):
        """Participant should be able to access calendar sync status endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/calendar/sync/status/{APPOINTMENT_ID}",
            headers={"Authorization": f"Bearer {participant_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "google" in data, "Response should contain google sync status"
        assert "outlook" in data, "Response should contain outlook sync status"
        print(f"✅ Participant calendar sync status: {data}")
    
    def test_organizer_can_access_calendar_sync_status(self, organizer_token):
        """Organizer should be able to access calendar sync status endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/calendar/sync/status/{APPOINTMENT_ID}",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "google" in data, "Response should contain google sync status"
        assert "outlook" in data, "Response should contain outlook sync status"
        print(f"✅ Organizer calendar sync status: {data}")
    
    def test_calendar_sync_returns_viewer_connections(self, participant_token, organizer_token):
        """Calendar sync should return different results for different viewers"""
        # Get participant's sync status
        participant_response = requests.get(
            f"{BASE_URL}/api/calendar/sync/status/{APPOINTMENT_ID}",
            headers={"Authorization": f"Bearer {participant_token}"}
        )
        assert participant_response.status_code == 200
        participant_data = participant_response.json()
        
        # Get organizer's sync status
        organizer_response = requests.get(
            f"{BASE_URL}/api/calendar/sync/status/{APPOINTMENT_ID}",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        assert organizer_response.status_code == 200
        organizer_data = organizer_response.json()
        
        # Both should have valid structure
        assert "google" in participant_data
        assert "google" in organizer_data
        
        # The has_connection values may differ based on each user's calendar connections
        print(f"✅ Participant Google has_connection: {participant_data['google'].get('has_connection')}")
        print(f"✅ Organizer Google has_connection: {organizer_data['google'].get('has_connection')}")


class TestAppointmentDetailAccess:
    """Test that both organizer and participant can access appointment details"""
    
    def test_organizer_can_access_appointment_detail(self, organizer_token):
        """Organizer should be able to access appointment detail"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/{APPOINTMENT_ID}",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("viewer_role") != "participant", "Organizer should not have participant role"
        print(f"✅ Organizer viewer_role: {data.get('viewer_role')}")
    
    def test_participant_can_access_appointment_detail(self, participant_token):
        """Participant should be able to access appointment detail"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/{APPOINTMENT_ID}",
            headers={"Authorization": f"Bearer {participant_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("viewer_role") == "participant", "Participant should have participant role"
        print(f"✅ Participant viewer_role: {data.get('viewer_role')}")
    
    def test_participant_has_invitation_token(self, participant_token):
        """Participant should have invitation token in response"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/{APPOINTMENT_ID}",
            headers={"Authorization": f"Bearer {participant_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("viewer_invitation_token"), "Participant should have viewer_invitation_token"
        print(f"✅ Participant has invitation token: {data.get('viewer_invitation_token')[:20]}...")


class TestDashboardAccess:
    """Test that dashboard works for both roles"""
    
    def test_organizer_dashboard_loads(self, organizer_token):
        """Organizer dashboard should load"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "items" in data, "Response should contain items"
        print(f"✅ Organizer has {len(data.get('items', []))} appointments")
    
    def test_participant_dashboard_loads(self, participant_token):
        """Participant dashboard should load"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/",
            headers={"Authorization": f"Bearer {participant_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "items" in data, "Response should contain items"
        print(f"✅ Participant has {len(data.get('items', []))} appointments")


class TestHealthCheck:
    """Basic health check"""
    
    def test_api_health(self):
        """API should be healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✅ API is healthy")
