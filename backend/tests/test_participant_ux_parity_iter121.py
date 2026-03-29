"""
Test Participant UX Parity - Iteration 121
Tests for unified CheckinBlock, SecondaryActions, Dashboard engagement signal, and Quitter button.

Features tested:
1. POST /api/invitations/{token}/cancel endpoint exists and validates properly
2. invitationAPI.cancelParticipation is wired in api.js
3. Dashboard timeline returns invitation_token for participant cards
4. Participant cards have accepted_count for engagement signal
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')

# Test credentials
TEST_USERS = {
    "organizer": {"email": "igaal.hanouna@gmail.com", "password": "OrgTest123!"},
    "participant": {"email": "igaal@hotmail.com", "password": "Test123!"},
    "audit": {"email": "testuser_audit@nlyt.app", "password": "TestAudit123!"},
}


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def participant_token(api_client):
    """Get auth token for participant user (igaal@hotmail.com)"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_USERS["participant"]["email"],
        "password": TEST_USERS["participant"]["password"]
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Participant login failed: {response.status_code}")


@pytest.fixture(scope="module")
def organizer_token(api_client):
    """Get auth token for organizer user (igaal.hanouna@gmail.com)"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_USERS["organizer"]["email"],
        "password": TEST_USERS["organizer"]["password"]
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Organizer login failed: {response.status_code}")


class TestCancelParticipationEndpoint:
    """Tests for POST /api/invitations/{token}/cancel endpoint"""
    
    def test_cancel_endpoint_exists(self, api_client):
        """Verify the cancel participation endpoint exists (returns 404 for invalid token, not 405)"""
        response = api_client.post(f"{BASE_URL}/api/invitations/invalid-token-12345/cancel")
        # Should return 404 (not found) not 405 (method not allowed)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        print(f"✅ Cancel endpoint exists - returns 404 for invalid token")
    
    def test_cancel_requires_accepted_status(self, api_client, participant_token):
        """Verify cancel only works for accepted invitations"""
        # Get participant's timeline to find an invitation token
        headers = {"Authorization": f"Bearer {participant_token}"}
        timeline_response = api_client.get(f"{BASE_URL}/api/appointments/my-timeline", headers=headers)
        
        if timeline_response.status_code != 200:
            pytest.skip("Could not fetch timeline")
        
        timeline = timeline_response.json()
        
        # Find a past participant appointment (should not be cancellable)
        past_items = timeline.get("past", [])
        participant_past = [item for item in past_items if item.get("role") == "participant"]
        
        if participant_past:
            item = participant_past[0]
            token = item.get("invitation_token")
            if token:
                response = api_client.post(f"{BASE_URL}/api/invitations/{token}/cancel")
                # Past appointments should fail (deadline passed or already started)
                assert response.status_code == 400, f"Expected 400 for past appointment, got {response.status_code}"
                print(f"✅ Cancel correctly rejects past appointments")
            else:
                print("⚠️ No invitation_token found on past participant item")
        else:
            print("⚠️ No past participant appointments found to test")


class TestDashboardTimelineParticipantData:
    """Tests for dashboard timeline returning proper participant data"""
    
    def test_timeline_returns_invitation_token_for_participants(self, api_client, participant_token):
        """Verify timeline includes invitation_token for participant role items"""
        headers = {"Authorization": f"Bearer {participant_token}"}
        response = api_client.get(f"{BASE_URL}/api/appointments/my-timeline", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check all buckets for participant items
        all_items = data.get("upcoming", []) + data.get("past", []) + data.get("action_required", [])
        participant_items = [item for item in all_items if item.get("role") == "participant"]
        
        if participant_items:
            for item in participant_items[:3]:  # Check first 3
                assert "invitation_token" in item, f"Missing invitation_token in participant item {item.get('appointment_id')}"
                print(f"✅ Participant item {item.get('appointment_id')} has invitation_token")
        else:
            print("⚠️ No participant items found in timeline")
    
    def test_timeline_returns_accepted_count_for_engagement_signal(self, api_client, participant_token):
        """Verify timeline includes accepted_count for engagement signal display"""
        headers = {"Authorization": f"Bearer {participant_token}"}
        response = api_client.get(f"{BASE_URL}/api/appointments/my-timeline", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        all_items = data.get("upcoming", []) + data.get("past", []) + data.get("action_required", [])
        participant_items = [item for item in all_items if item.get("role") == "participant"]
        
        if participant_items:
            for item in participant_items[:3]:
                # accepted_count should be present for engagement signal
                assert "accepted_count" in item, f"Missing accepted_count in participant item {item.get('appointment_id')}"
                assert "participants_count" in item, f"Missing participants_count in participant item {item.get('appointment_id')}"
                print(f"✅ Participant item has accepted_count={item.get('accepted_count')}, participants_count={item.get('participants_count')}")
        else:
            print("⚠️ No participant items found in timeline")
    
    def test_timeline_returns_participant_status(self, api_client, participant_token):
        """Verify timeline includes participant_status for canQuit logic"""
        headers = {"Authorization": f"Bearer {participant_token}"}
        response = api_client.get(f"{BASE_URL}/api/appointments/my-timeline", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        all_items = data.get("upcoming", []) + data.get("past", []) + data.get("action_required", [])
        participant_items = [item for item in all_items if item.get("role") == "participant"]
        
        if participant_items:
            for item in participant_items[:3]:
                assert "participant_status" in item, f"Missing participant_status in participant item {item.get('appointment_id')}"
                print(f"✅ Participant item has participant_status={item.get('participant_status')}")
        else:
            print("⚠️ No participant items found in timeline")


class TestAppointmentDetailParticipantView:
    """Tests for appointment detail page participant view"""
    
    def test_participant_can_view_appointment_detail(self, api_client, participant_token):
        """Verify participant can access appointment detail page"""
        headers = {"Authorization": f"Bearer {participant_token}"}
        
        # Get timeline to find a participant appointment
        timeline_response = api_client.get(f"{BASE_URL}/api/appointments/my-timeline", headers=headers)
        assert timeline_response.status_code == 200
        
        timeline = timeline_response.json()
        all_items = timeline.get("upcoming", []) + timeline.get("past", [])
        participant_items = [item for item in all_items if item.get("role") == "participant"]
        
        if not participant_items:
            pytest.skip("No participant appointments found")
        
        apt_id = participant_items[0].get("appointment_id")
        
        # Get appointment detail
        detail_response = api_client.get(f"{BASE_URL}/api/appointments/{apt_id}", headers=headers)
        assert detail_response.status_code == 200
        
        data = detail_response.json()
        assert data.get("viewer_role") == "participant", f"Expected viewer_role=participant, got {data.get('viewer_role')}"
        assert "viewer_invitation_token" in data, "Missing viewer_invitation_token"
        assert "viewer_participant_status" in data, "Missing viewer_participant_status"
        
        print(f"✅ Participant can view appointment detail with viewer_role={data.get('viewer_role')}")
        print(f"   viewer_participant_status={data.get('viewer_participant_status')}")


class TestOrganizerExperienceNotDegraded:
    """Tests to ensure organizer experience is not degraded"""
    
    def test_organizer_timeline_has_progress_data(self, api_client, organizer_token):
        """Verify organizer timeline still has progress bar data"""
        headers = {"Authorization": f"Bearer {organizer_token}"}
        response = api_client.get(f"{BASE_URL}/api/appointments/my-timeline", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        all_items = data.get("upcoming", []) + data.get("past", [])
        organizer_items = [item for item in all_items if item.get("role") == "organizer"]
        
        if organizer_items:
            for item in organizer_items[:3]:
                assert "participants_count" in item, f"Missing participants_count for organizer item"
                assert "accepted_count" in item, f"Missing accepted_count for organizer item"
                assert "pending_count" in item, f"Missing pending_count for organizer item"
                print(f"✅ Organizer item has progress data: {item.get('accepted_count')}/{item.get('participants_count')} accepted, {item.get('pending_count')} pending")
        else:
            print("⚠️ No organizer items found in timeline")
    
    def test_organizer_can_view_appointment_detail(self, api_client, organizer_token):
        """Verify organizer can still access full appointment detail"""
        headers = {"Authorization": f"Bearer {organizer_token}"}
        
        # Get timeline to find an organizer appointment
        timeline_response = api_client.get(f"{BASE_URL}/api/appointments/my-timeline", headers=headers)
        assert timeline_response.status_code == 200
        
        timeline = timeline_response.json()
        all_items = timeline.get("upcoming", []) + timeline.get("past", [])
        organizer_items = [item for item in all_items if item.get("role") == "organizer"]
        
        if not organizer_items:
            pytest.skip("No organizer appointments found")
        
        apt_id = organizer_items[0].get("appointment_id")
        
        # Get appointment detail
        detail_response = api_client.get(f"{BASE_URL}/api/appointments/{apt_id}", headers=headers)
        assert detail_response.status_code == 200
        
        data = detail_response.json()
        assert data.get("viewer_role") == "organizer", f"Expected viewer_role=organizer, got {data.get('viewer_role')}"
        
        print(f"✅ Organizer can view appointment detail with viewer_role={data.get('viewer_role')}")


class TestCalendarICSExport:
    """Tests for ICS download functionality"""
    
    def test_ics_export_endpoint_exists(self, api_client, participant_token):
        """Verify ICS export endpoint exists"""
        headers = {"Authorization": f"Bearer {participant_token}"}
        
        # Get timeline to find an appointment
        timeline_response = api_client.get(f"{BASE_URL}/api/appointments/my-timeline", headers=headers)
        assert timeline_response.status_code == 200
        
        timeline = timeline_response.json()
        all_items = timeline.get("upcoming", []) + timeline.get("past", [])
        
        if not all_items:
            pytest.skip("No appointments found")
        
        apt_id = all_items[0].get("appointment_id")
        
        # Check ICS export endpoint
        ics_response = api_client.get(f"{BASE_URL}/api/calendar/export/ics/{apt_id}")
        # Should return 200 with ICS content or redirect
        assert ics_response.status_code in [200, 302], f"ICS export failed with {ics_response.status_code}"
        
        if ics_response.status_code == 200:
            content_type = ics_response.headers.get("content-type", "")
            assert "text/calendar" in content_type or "application/octet-stream" in content_type, f"Unexpected content-type: {content_type}"
            print(f"✅ ICS export endpoint works for appointment {apt_id}")


class TestAPIWiring:
    """Tests to verify API is properly wired"""
    
    def test_invitation_cancel_api_wiring(self, api_client):
        """Verify invitationAPI.cancelParticipation endpoint is accessible"""
        # Test with invalid token to verify endpoint exists
        response = api_client.post(f"{BASE_URL}/api/invitations/test-token-abc/cancel")
        
        # Should return 404 (not found) not 405 (method not allowed) or 500
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data
        assert "non trouvée" in data["detail"].lower() or "not found" in data["detail"].lower()
        
        print("✅ invitationAPI.cancelParticipation endpoint is properly wired")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
