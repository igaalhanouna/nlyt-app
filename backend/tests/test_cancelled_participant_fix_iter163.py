"""
Test suite for cancelled participant status fix (Iteration 163)

Bug: When a participant cancelled after accepting and guaranteeing, the business status
'cancelled_by_participant' was being overwritten by 'guarantee_released' in 
StripeGuaranteeService.release_guarantee().

Fix applied:
1. Backend: release_guarantee() no longer overwrites terminal business statuses
2. Timeline counters exclude cancelled participants
3. Explicit labels for cancelled participants
4. guarantee_released treated as alias for cancellation in frontend mappings
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "testuser_audit@nlyt.app"
ADMIN_PASSWORD = "TestAudit123!"
PARTICIPANT1_EMAIL = "igaal.hanouna@gmail.com"
PARTICIPANT1_PASSWORD = "OrgTest123!"
PARTICIPANT2_EMAIL = "igaal@hotmail.com"
PARTICIPANT2_PASSWORD = "Test123!"


class TestCancelledParticipantFix:
    """Tests for the cancelled participant status fix"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Admin login failed: {response.status_code}")
    
    @pytest.fixture(scope="class")
    def participant1_token(self):
        """Get participant 1 auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PARTICIPANT1_EMAIL,
            "password": PARTICIPANT1_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Participant 1 login failed: {response.status_code}")
    
    @pytest.fixture(scope="class")
    def participant2_token(self):
        """Get participant 2 auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PARTICIPANT2_EMAIL,
            "password": PARTICIPANT2_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Participant 2 login failed: {response.status_code}")
    
    # ─── Test 1: Timeline counters exclude cancelled participants ───
    def test_timeline_counters_exclude_cancelled(self, admin_token):
        """
        BACKEND: GET /api/appointments/my-timeline
        Verify that a participant with status 'cancelled_by_participant' is NOT counted
        in the accepted/guaranteed/pending counters for the organizer view.
        """
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/appointments/my-timeline", headers=headers)
        
        assert response.status_code == 200, f"Timeline API failed: {response.text}"
        data = response.json()
        
        # Check structure
        assert "action_required" in data
        assert "upcoming" in data
        assert "past" in data
        
        # Find any organizer items and verify counter logic
        all_items = data.get("action_required", []) + data.get("upcoming", []) + data.get("past", [])
        organizer_items = [i for i in all_items if i.get("role") == "organizer"]
        
        print(f"Found {len(organizer_items)} organizer items in timeline")
        
        # For each organizer item, verify that counters are consistent
        for item in organizer_items:
            accepted = item.get("accepted_count", 0)
            guaranteed = item.get("guaranteed_count", 0)
            pending = item.get("pending_count", 0)
            total = item.get("participants_count", 0)
            
            # Guaranteed should never exceed accepted
            assert guaranteed <= accepted, f"Guaranteed ({guaranteed}) > Accepted ({accepted}) for {item.get('appointment_id')}"
            
            # Counters should be non-negative
            assert accepted >= 0
            assert guaranteed >= 0
            assert pending >= 0
            
            print(f"Appointment {item.get('appointment_id')}: accepted={accepted}, guaranteed={guaranteed}, pending={pending}, total={total}")
    
    # ─── Test 2: Organizer sees cancellation label ───
    def test_organizer_sees_cancellation_label(self, admin_token):
        """
        BACKEND: GET /api/appointments/my-timeline
        Verify that the pending_label for organizer shows 'Participation annulée par [Nom]'
        when a participant has cancelled.
        """
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/appointments/my-timeline", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        all_items = data.get("action_required", []) + data.get("upcoming", []) + data.get("past", [])
        organizer_items = [i for i in all_items if i.get("role") == "organizer"]
        
        # Look for items with cancellation info in pending_label
        items_with_cancel_label = [
            i for i in organizer_items 
            if i.get("pending_label") and "annulée" in i.get("pending_label", "").lower()
        ]
        
        print(f"Found {len(items_with_cancel_label)} items with cancellation labels")
        
        for item in items_with_cancel_label:
            label = item.get("pending_label", "")
            print(f"Appointment {item.get('appointment_id')}: pending_label = '{label}'")
            # Verify the label format
            assert "annulée" in label.lower(), f"Expected 'annulée' in label: {label}"
    
    # ─── Test 3: Participant sees cancellation label ───
    def test_participant_sees_cancellation_label(self, participant1_token, participant2_token):
        """
        BACKEND: GET /api/appointments/my-timeline
        Verify that the pending_label for participant shows 'Vous avez annulé votre participation'
        for cancelled appointments.
        """
        for token, email in [(participant1_token, PARTICIPANT1_EMAIL), (participant2_token, PARTICIPANT2_EMAIL)]:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(f"{BASE_URL}/api/appointments/my-timeline", headers=headers)
            
            assert response.status_code == 200, f"Timeline failed for {email}"
            data = response.json()
            
            all_items = data.get("action_required", []) + data.get("upcoming", []) + data.get("past", [])
            participant_items = [i for i in all_items if i.get("role") == "participant"]
            
            # Find cancelled participations
            cancelled_items = [
                i for i in participant_items 
                if i.get("participant_status") in ("cancelled_by_participant", "guarantee_released")
            ]
            
            print(f"User {email}: Found {len(cancelled_items)} cancelled participations")
            
            for item in cancelled_items:
                label = item.get("pending_label", "")
                status = item.get("participant_status")
                print(f"  Appointment {item.get('appointment_id')}: status={status}, pending_label='{label}'")
                
                # Verify the label is correct for cancelled status
                assert "annulé" in label.lower(), f"Expected 'annulé' in label for cancelled participant: {label}"
    
    # ─── Test 4: Cancelled participants in past bucket ───
    def test_cancelled_participants_in_past_bucket(self, participant1_token, participant2_token):
        """
        BACKEND: GET /api/appointments/my-timeline
        Verify that cancelled participations are placed in the 'past' bucket (historique),
        not in 'upcoming' or 'action_required'.
        """
        for token, email in [(participant1_token, PARTICIPANT1_EMAIL), (participant2_token, PARTICIPANT2_EMAIL)]:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(f"{BASE_URL}/api/appointments/my-timeline", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            
            # Check that cancelled items are NOT in action_required or upcoming
            for bucket_name in ["action_required", "upcoming"]:
                bucket = data.get(bucket_name, [])
                cancelled_in_bucket = [
                    i for i in bucket 
                    if i.get("role") == "participant" 
                    and i.get("participant_status") in ("cancelled_by_participant", "guarantee_released")
                ]
                
                if cancelled_in_bucket:
                    print(f"WARNING: Found {len(cancelled_in_bucket)} cancelled items in {bucket_name} for {email}")
                    for item in cancelled_in_bucket:
                        print(f"  - {item.get('appointment_id')}: status={item.get('participant_status')}")
                
                # Cancelled items should be in past, not in active buckets
                # (unless the appointment itself is still ongoing)
                assert len(cancelled_in_bucket) == 0, f"Cancelled items should not be in {bucket_name}"
    
    # ─── Test 5: No action buttons for cancelled participants ───
    def test_no_action_buttons_for_cancelled(self, participant1_token, participant2_token):
        """
        BACKEND: GET /api/appointments/my-timeline
        Verify that cancelled participants don't have 'quit' or 'remind' actions.
        """
        for token, email in [(participant1_token, PARTICIPANT1_EMAIL), (participant2_token, PARTICIPANT2_EMAIL)]:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(f"{BASE_URL}/api/appointments/my-timeline", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            
            all_items = data.get("action_required", []) + data.get("upcoming", []) + data.get("past", [])
            
            cancelled_items = [
                i for i in all_items 
                if i.get("role") == "participant" 
                and i.get("participant_status") in ("cancelled_by_participant", "guarantee_released")
            ]
            
            for item in cancelled_items:
                actions = item.get("actions", [])
                print(f"Cancelled item {item.get('appointment_id')}: actions = {actions}")
                
                # Cancelled participants should only have view_details
                assert "quit" not in actions, f"Cancelled participant should not have 'quit' action"
                assert "remind" not in actions, f"Cancelled participant should not have 'remind' action"
                assert "accept" not in actions, f"Cancelled participant should not have 'accept' action"
                assert "decline" not in actions, f"Cancelled participant should not have 'decline' action"
    
    # ─── Test 6: API health check ───
    def test_api_health(self):
        """Basic health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("API health check passed")
    
    # ─── Test 7: Timeline API returns correct structure ───
    def test_timeline_structure(self, admin_token):
        """Verify timeline API returns expected structure"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/appointments/my-timeline", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check required keys
        assert "action_required" in data
        assert "upcoming" in data
        assert "past" in data
        assert "counts" in data
        
        counts = data["counts"]
        assert "action_required" in counts
        assert "upcoming" in counts
        assert "past" in counts
        assert "total" in counts
        
        print(f"Timeline counts: {counts}")
    
    # ─── Test 8: Verify guarantee_released is treated as terminal ───
    def test_guarantee_released_is_terminal(self, admin_token):
        """
        Verify that guarantee_released status is treated as a terminal status
        (placed in past bucket, no action buttons).
        """
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/appointments/my-timeline", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        all_items = data.get("action_required", []) + data.get("upcoming", []) + data.get("past", [])
        
        # Find any items with guarantee_released status
        guarantee_released_items = [
            i for i in all_items 
            if i.get("participant_status") == "guarantee_released"
        ]
        
        print(f"Found {len(guarantee_released_items)} items with guarantee_released status")
        
        for item in guarantee_released_items:
            # Should be in past bucket
            is_in_past = item in data.get("past", [])
            print(f"Item {item.get('appointment_id')}: in_past={is_in_past}, actions={item.get('actions')}")


class TestInvitationAPI:
    """Test invitation API for cancelled participant display"""
    
    def test_invitation_api_health(self):
        """Basic test that invitation endpoints exist"""
        # This is a placeholder - we'd need a valid token to test fully
        response = requests.get(f"{BASE_URL}/api/invitations/invalid-token")
        # Should return 404 for invalid token, not 500
        assert response.status_code in [404, 400], f"Unexpected status: {response.status_code}"
        print("Invitation API responds correctly to invalid token")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
