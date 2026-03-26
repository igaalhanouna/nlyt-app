"""
Test suite for Stripe status fix verification
Tests: A-I from the bug fix requirements

Tests verify:
- Backend GET /api/invitations/{token} returns guaranteed_at and guarantee_id
- Backend participants_status_summary groups accepted statuses correctly
- Backend POST /api/invitations/{token}/respond handles accept flow with penalty
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://evidence-labels-fix.preview.emergentagent.com')

# Test data
GUARANTEED_INVITATION_TOKEN = "df4600be-e050-4c9c-a8fe-250950227052"
TEST_APPOINTMENT_ID = "45005668-7237-4bbc-a5ff-31906a9e18dc"
TEST_WORKSPACE_ID = "7e219321-18fd-4643-9be6-e4f1de88a2a8"
TEST_USER_EMAIL = "testuser_audit@nlyt.app"
TEST_USER_PASSWORD = "TestPassword123!"


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def auth_token(api_client):
    """Get authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Authentication failed - skipping authenticated tests")


@pytest.fixture
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


class TestInvitationEndpoint:
    """Test F: Backend GET /api/invitations/{token} returns guaranteed_at and guarantee_id"""
    
    def test_get_invitation_returns_guaranteed_fields(self, api_client):
        """Test that GET invitation returns guaranteed_at and guarantee_id for accepted_guaranteed participant"""
        response = api_client.get(f"{BASE_URL}/api/invitations/{GUARANTEED_INVITATION_TOKEN}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        participant = data.get("participant", {})
        
        # Verify status is accepted_guaranteed
        assert participant.get("status") == "accepted_guaranteed", \
            f"Expected status 'accepted_guaranteed', got '{participant.get('status')}'"
        
        # Verify guaranteed_at is present and not None
        assert participant.get("guaranteed_at") is not None, \
            "guaranteed_at should be present for accepted_guaranteed participant"
        
        # Verify guarantee_id is present and not None
        assert participant.get("guarantee_id") is not None, \
            "guarantee_id should be present for accepted_guaranteed participant"
        
        print(f"✓ Test F PASSED: guaranteed_at={participant.get('guaranteed_at')}, guarantee_id={participant.get('guarantee_id')}")
    
    def test_get_invitation_can_cancel_for_guaranteed(self, api_client):
        """Test that can_cancel is correctly set for accepted_guaranteed status"""
        response = api_client.get(f"{BASE_URL}/api/invitations/{GUARANTEED_INVITATION_TOKEN}")
        
        assert response.status_code == 200
        
        data = response.json()
        engagement_rules = data.get("engagement_rules", {})
        
        # can_cancel should be False if deadline passed, True otherwise
        # For this test appointment, deadline has passed
        assert "can_cancel" in engagement_rules, "can_cancel should be in engagement_rules"
        
        # Verify the logic: can_cancel should be based on deadline, not just status
        deadline_passed = engagement_rules.get("cancellation_deadline_passed", False)
        can_cancel = engagement_rules.get("can_cancel", False)
        
        if deadline_passed:
            assert can_cancel == False, "can_cancel should be False when deadline passed"
        
        print(f"✓ can_cancel={can_cancel}, deadline_passed={deadline_passed}")


class TestAppointmentsListEndpoint:
    """Test G: Backend participants_status_summary groups accepted statuses correctly"""
    
    def test_appointments_list_status_summary(self, authenticated_client):
        """Test that participants_status_summary counts accepted_guaranteed under 'accepted'"""
        response = authenticated_client.get(
            f"{BASE_URL}/api/appointments/",
            params={"workspace_id": TEST_WORKSPACE_ID}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        appointments = data.get("appointments", [])
        
        # Find the test appointment
        test_appointment = None
        for apt in appointments:
            if apt.get("appointment_id") == TEST_APPOINTMENT_ID:
                test_appointment = apt
                break
        
        assert test_appointment is not None, f"Test appointment {TEST_APPOINTMENT_ID} not found"
        
        # Check participants_status_summary
        status_summary = test_appointment.get("participants_status_summary", {})
        
        # Verify accepted count includes accepted_guaranteed
        accepted_count = status_summary.get("accepted", 0)
        
        # Check individual participant statuses
        participants = test_appointment.get("participants", [])
        guaranteed_count = sum(1 for p in participants if p.get("status") == "accepted_guaranteed")
        pending_guarantee_count = sum(1 for p in participants if p.get("status") == "accepted_pending_guarantee")
        plain_accepted_count = sum(1 for p in participants if p.get("status") == "accepted")
        
        expected_accepted = guaranteed_count + pending_guarantee_count + plain_accepted_count
        
        assert accepted_count == expected_accepted, \
            f"Expected accepted count {expected_accepted}, got {accepted_count}. " \
            f"(guaranteed={guaranteed_count}, pending={pending_guarantee_count}, plain={plain_accepted_count})"
        
        print(f"✓ Test G PASSED: accepted={accepted_count} (includes {guaranteed_count} guaranteed)")


class TestInvitationRespond:
    """Test I: Backend POST /api/invitations/{token}/respond handles accept flow with penalty"""
    
    def test_respond_endpoint_exists(self, api_client):
        """Test that the respond endpoint exists and returns proper error for invalid token"""
        response = api_client.post(
            f"{BASE_URL}/api/invitations/invalid-token-12345/respond",
            json={"action": "accept"}
        )
        
        # Should return 404 for invalid token, not 500
        assert response.status_code == 404, f"Expected 404 for invalid token, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data, "Response should contain error detail"
        
        print(f"✓ Respond endpoint returns proper 404 for invalid token")
    
    def test_respond_endpoint_validates_action(self, api_client):
        """Test that respond endpoint validates action parameter"""
        response = api_client.post(
            f"{BASE_URL}/api/invitations/{GUARANTEED_INVITATION_TOKEN}/respond",
            json={"action": "invalid_action"}
        )
        
        # Should return 400 for invalid action
        assert response.status_code == 400, f"Expected 400 for invalid action, got {response.status_code}"
        
        print(f"✓ Respond endpoint validates action parameter")
    
    def test_respond_already_responded(self, api_client):
        """Test that respond endpoint returns error for already responded invitation"""
        response = api_client.post(
            f"{BASE_URL}/api/invitations/{GUARANTEED_INVITATION_TOKEN}/respond",
            json={"action": "accept"}
        )
        
        # Should return 400 because already responded
        assert response.status_code == 400, f"Expected 400 for already responded, got {response.status_code}"
        
        data = response.json()
        assert "déjà répondu" in data.get("detail", "").lower() or "already" in data.get("detail", "").lower(), \
            f"Expected 'already responded' error, got: {data.get('detail')}"
        
        print(f"✓ Respond endpoint returns proper error for already responded invitation")


class TestGuaranteeStatus:
    """Test guarantee-status endpoint"""
    
    def test_guarantee_status_endpoint(self, api_client):
        """Test that guarantee-status endpoint returns correct status"""
        response = api_client.get(
            f"{BASE_URL}/api/invitations/{GUARANTEED_INVITATION_TOKEN}/guarantee-status"
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        assert data.get("status") == "accepted_guaranteed", \
            f"Expected status 'accepted_guaranteed', got '{data.get('status')}'"
        
        assert data.get("is_guaranteed") == True, \
            f"Expected is_guaranteed=True, got {data.get('is_guaranteed')}"
        
        assert data.get("guarantee_id") is not None, \
            "guarantee_id should be present"
        
        print(f"✓ Guarantee status endpoint returns correct data")


class TestParticipantsList:
    """Test participants list endpoint"""
    
    def test_participants_list_shows_status(self, authenticated_client):
        """Test that participants list shows correct status for guaranteed participant"""
        response = authenticated_client.get(
            f"{BASE_URL}/api/participants/",
            params={"appointment_id": TEST_APPOINTMENT_ID}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        participants = data.get("participants", [])
        
        # Find participant with accepted_guaranteed status
        guaranteed_participant = None
        for p in participants:
            if p.get("status") == "accepted_guaranteed":
                guaranteed_participant = p
                break
        
        assert guaranteed_participant is not None, \
            "Should have at least one participant with accepted_guaranteed status"
        
        print(f"✓ Participants list shows accepted_guaranteed status correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
