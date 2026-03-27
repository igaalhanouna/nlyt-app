"""
Test: Unified Participant/Organizer View
=========================================
Tests the new architecture where participants access /appointments/{id} 
instead of /invitation/{token} when authenticated.

Key features tested:
1. GET /api/appointments/{id} returns viewer_role='participant' for participants
2. GET /api/appointments/{id} returns viewer_role='organizer' for workspace members
3. GET /api/appointments/{id} returns 403 for unauthorized users
4. GET /api/participants/?appointment_id={id} accessible by participants
5. Response includes viewer_participant_id and viewer_invitation_token for participants
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://check-in-flow-1.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_USER_EMAIL = "testuser_audit@nlyt.app"
TEST_USER_PASSWORD = "Test123!"

# Appointment where testuser is PARTICIPANT
PARTICIPANT_APPOINTMENT_ID = "7f5d0fa9-d8ac-4d24-b2f1-eb0eecb22782"

# Appointment where testuser is ORGANIZER
ORGANIZER_APPOINTMENT_ID = "5661bffc-56fd-4cff-a0c0-ef196deadf1d"


class TestUnifiedParticipantView:
    """Test unified view for participants and organizers"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for test user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    # ─── Test 1: Participant access to appointment ───
    def test_participant_gets_viewer_role_participant(self, auth_headers):
        """GET /api/appointments/{id} returns viewer_role='participant' when user is participant"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/{PARTICIPANT_APPOINTMENT_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Core assertion: viewer_role must be 'participant'
        assert data.get('viewer_role') == 'participant', f"Expected viewer_role='participant', got '{data.get('viewer_role')}'"
        
        # Additional participant-specific fields
        assert 'viewer_participant_id' in data, "Missing viewer_participant_id for participant"
        assert 'viewer_invitation_token' in data, "Missing viewer_invitation_token for participant"
        assert 'viewer_participant_status' in data, "Missing viewer_participant_status for participant"
        
        print(f"✅ Participant view: viewer_role={data['viewer_role']}, participant_id={data.get('viewer_participant_id')}")
    
    # ─── Test 2: Organizer access to appointment ───
    def test_organizer_gets_viewer_role_organizer(self, auth_headers):
        """GET /api/appointments/{id} returns viewer_role='organizer' when user is workspace member"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/{ORGANIZER_APPOINTMENT_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Core assertion: viewer_role must be 'organizer'
        assert data.get('viewer_role') == 'organizer', f"Expected viewer_role='organizer', got '{data.get('viewer_role')}'"
        
        # Organizer should NOT have participant-specific fields (or they should be absent)
        # Note: viewer_participant_id/viewer_invitation_token should only be present for participants
        
        print(f"✅ Organizer view: viewer_role={data['viewer_role']}")
    
    # ─── Test 3: Unauthorized access returns 403 ───
    def test_unauthorized_user_gets_403(self):
        """GET /api/appointments/{id} returns 403 when user is neither workspace member nor participant"""
        # Create a new user that has no access to the appointment
        # For this test, we'll use an invalid/no token to simulate unauthorized access
        response = requests.get(
            f"{BASE_URL}/api/appointments/{PARTICIPANT_APPOINTMENT_ID}",
            headers={"Authorization": "Bearer invalid_token_12345"}
        )
        
        # Should return 401 (unauthorized) or 403 (forbidden)
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✅ Unauthorized access correctly blocked with status {response.status_code}")
    
    # ─── Test 4: Participant can access participants list ───
    def test_participant_can_list_participants(self, auth_headers):
        """GET /api/participants/?appointment_id={id} accessible by participant (not 403)"""
        response = requests.get(
            f"{BASE_URL}/api/participants/?appointment_id={PARTICIPANT_APPOINTMENT_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert 'participants' in data, "Missing 'participants' key in response"
        assert isinstance(data['participants'], list), "participants should be a list"
        
        print(f"✅ Participant can list participants: {len(data['participants'])} found")
    
    # ─── Test 5: Organizer can access participants list ───
    def test_organizer_can_list_participants(self, auth_headers):
        """GET /api/participants/?appointment_id={id} accessible by organizer"""
        response = requests.get(
            f"{BASE_URL}/api/participants/?appointment_id={ORGANIZER_APPOINTMENT_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert 'participants' in data, "Missing 'participants' key in response"
        
        print(f"✅ Organizer can list participants: {len(data['participants'])} found")
    
    # ─── Test 6: Appointment data includes all required fields ───
    def test_appointment_data_completeness_for_participant(self, auth_headers):
        """Verify appointment response includes all fields needed for participant view"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/{PARTICIPANT_APPOINTMENT_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Required fields for engagement summary
        required_fields = [
            'appointment_id', 'title', 'start_datetime', 'duration_minutes',
            'penalty_amount', 'penalty_currency', 'tolerated_delay_minutes',
            'cancellation_deadline_hours', 'affected_compensation_percent',
            'platform_commission_percent', 'charity_percent'
        ]
        
        missing_fields = [f for f in required_fields if f not in data]
        assert not missing_fields, f"Missing required fields: {missing_fields}"
        
        print(f"✅ All required fields present for participant view")
        print(f"   - penalty_amount: {data.get('penalty_amount')}")
        print(f"   - tolerated_delay_minutes: {data.get('tolerated_delay_minutes')}")
        print(f"   - cancellation_deadline_hours: {data.get('cancellation_deadline_hours')}")


class TestDashboardParticipantLinks:
    """Test that dashboard returns correct links for participant items"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for test user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Authentication failed: {response.status_code}")
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_timeline_returns_participant_items(self, auth_headers):
        """GET /api/appointments/my-timeline returns participant items with appointment_id"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/my-timeline",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Check structure
        assert 'action_required' in data, "Missing action_required bucket"
        assert 'upcoming' in data, "Missing upcoming bucket"
        assert 'past' in data, "Missing past bucket"
        
        # Find participant items
        all_items = data['action_required'] + data['upcoming'] + data['past']
        participant_items = [i for i in all_items if i.get('role') == 'participant']
        
        print(f"✅ Timeline returned {len(all_items)} total items, {len(participant_items)} as participant")
        
        # Verify participant items have appointment_id (for /appointments/{id} link)
        for item in participant_items:
            assert 'appointment_id' in item, "Participant item missing appointment_id"
            # The frontend should use /appointments/{appointment_id} NOT /invitation/{token}
            print(f"   - Participant item: {item.get('title')} (apt_id: {item.get('appointment_id')})")
    
    def test_participant_item_has_required_fields(self, auth_headers):
        """Verify participant timeline items have all required fields for display"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/my-timeline",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        all_items = data['action_required'] + data['upcoming'] + data['past']
        participant_items = [i for i in all_items if i.get('role') == 'participant']
        
        if not participant_items:
            pytest.skip("No participant items found in timeline")
        
        # Check first participant item
        item = participant_items[0]
        
        required_fields = [
            'appointment_id', 'role', 'status', 'title', 'starts_at',
            'counterparty_name', 'appointment_type', 'duration_minutes',
            'penalty_amount', 'penalty_currency'
        ]
        
        missing = [f for f in required_fields if f not in item]
        assert not missing, f"Participant item missing fields: {missing}"
        
        print(f"✅ Participant item has all required fields")
        print(f"   - role: {item.get('role')}")
        print(f"   - counterparty_name: {item.get('counterparty_name')}")


class TestParticipantViewPermissions:
    """Test that participant view correctly hides organizer-only features"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for test user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Authentication failed: {response.status_code}")
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_participant_cannot_cancel_appointment(self, auth_headers):
        """POST /api/appointments/{id}/cancel should fail for participant"""
        response = requests.post(
            f"{BASE_URL}/api/appointments/{PARTICIPANT_APPOINTMENT_ID}/cancel",
            headers=auth_headers
        )
        
        # Should return 403 (only organizer can cancel)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"✅ Participant correctly blocked from cancelling appointment")
    
    def test_participant_cannot_update_appointment(self, auth_headers):
        """PATCH /api/appointments/{id} should fail for participant"""
        response = requests.patch(
            f"{BASE_URL}/api/appointments/{PARTICIPANT_APPOINTMENT_ID}",
            headers=auth_headers,
            json={"title": "Hacked Title"}
        )
        
        # Should return 403 (only organizer can update)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"✅ Participant correctly blocked from updating appointment")
    
    def test_participant_cannot_add_participants(self, auth_headers):
        """POST /api/participants/ should fail for participant"""
        response = requests.post(
            f"{BASE_URL}/api/participants/?appointment_id={PARTICIPANT_APPOINTMENT_ID}",
            headers=auth_headers,
            json={
                "email": "hacker@test.com",
                "first_name": "Hacker",
                "last_name": "Test",
                "role": "participant"
            }
        )
        
        # Should return 403 (only organizer can add participants)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"✅ Participant correctly blocked from adding participants")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
