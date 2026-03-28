"""
Test Dispute Deadlock Fix - Iteration 119

Tests the fix for dispute deadlock when target=organizer (same user_id for both).
The counterpart (igaal@hotmail.com) was locked out as 'observer'. 
Fix adds fallback role determination: if organizer_user_id == target_user_id 
AND user submitted a declaration about the target → user gets 'participant' role.

Also tests new 5-case display_state logic: waiting_both, waiting_other, arbitration, resolved.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ORGANIZER_EMAIL = "testuser_audit@nlyt.app"
ORGANIZER_PASSWORD = "TestAudit123!"
COUNTERPART_EMAIL = "igaal@hotmail.com"
COUNTERPART_PASSWORD = "Test123!"

# Test dispute ID (organizer_user_id == target_user_id deadlock case)
DEADLOCK_DISPUTE_ID = "619c6d07-d42f-46ea-8d8b-c64a26225ff5"


@pytest.fixture(scope="module")
def organizer_token():
    """Get auth token for organizer (testuser_audit@nlyt.app)"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ORGANIZER_EMAIL,
        "password": ORGANIZER_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Organizer login failed: {response.status_code} - {response.text}")
    return response.json().get("access_token")


@pytest.fixture(scope="module")
def counterpart_token():
    """Get auth token for counterpart (igaal@hotmail.com)"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": COUNTERPART_EMAIL,
        "password": COUNTERPART_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Counterpart login failed: {response.status_code} - {response.text}")
    return response.json().get("access_token")


class TestDisputeDeadlockFix:
    """Tests for the dispute deadlock fix when target=organizer"""

    def test_dispute_detail_returns_display_state(self, organizer_token):
        """GET /api/disputes/:id returns display_state field"""
        response = requests.get(
            f"{BASE_URL}/api/disputes/{DEADLOCK_DISPUTE_ID}",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "display_state" in data, "Response should contain display_state field"
        assert data["display_state"] in ["waiting_both", "waiting_other", "arbitration", "resolved"], \
            f"display_state should be one of the 5 valid states, got: {data['display_state']}"
        print(f"✅ display_state returned: {data['display_state']}")

    def test_dispute_detail_returns_other_party_name(self, organizer_token):
        """GET /api/disputes/:id returns other_party_name field"""
        response = requests.get(
            f"{BASE_URL}/api/disputes/{DEADLOCK_DISPUTE_ID}",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "other_party_name" in data, "Response should contain other_party_name field"
        # For organizer in deadlock case, other_party_name should be the counterpart (Igaal)
        print(f"✅ other_party_name returned: '{data['other_party_name']}'")

    def test_organizer_sees_correct_other_party_name_in_deadlock(self, organizer_token):
        """In deadlock case, organizer should see counterpart's name (Igaal), not target's name (Test)"""
        response = requests.get(
            f"{BASE_URL}/api/disputes/{DEADLOCK_DISPUTE_ID}",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        other_name = data.get("other_party_name", "")
        my_role = data.get("my_role", "")
        
        # Organizer should see "Igaal" as other party, not "Test" (the target)
        assert my_role == "organizer", f"Expected my_role='organizer', got '{my_role}'"
        # The other party name should be the counterpart who submitted declaration
        assert other_name.lower() != "test", \
            f"Organizer should NOT see 'Test' as other party in deadlock case, got: '{other_name}'"
        print(f"✅ Organizer sees other_party_name='{other_name}' (not 'Test')")

    def test_counterpart_gets_participant_role_in_deadlock(self, counterpart_token):
        """In deadlock case, counterpart (igaal) should get my_role='participant', not 'observer'"""
        response = requests.get(
            f"{BASE_URL}/api/disputes/{DEADLOCK_DISPUTE_ID}",
            headers={"Authorization": f"Bearer {counterpart_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        my_role = data.get("my_role")
        
        # CRITICAL: counterpart should NOT be 'observer' in deadlock case
        assert my_role == "participant", \
            f"Counterpart should have my_role='participant' in deadlock case, got: '{my_role}'"
        print(f"✅ Counterpart (igaal) has my_role='participant' in deadlock case")

    def test_counterpart_can_submit_position_in_deadlock(self, counterpart_token):
        """In deadlock case, counterpart (igaal) should have can_submit_position=True"""
        response = requests.get(
            f"{BASE_URL}/api/disputes/{DEADLOCK_DISPUTE_ID}",
            headers={"Authorization": f"Bearer {counterpart_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        can_submit = data.get("can_submit_position")
        my_position = data.get("my_position")
        status = data.get("status")
        
        # If status is awaiting_positions and counterpart hasn't submitted yet
        if status == "awaiting_positions" and my_position is None:
            assert can_submit is True, \
                f"Counterpart should have can_submit_position=True, got: {can_submit}"
            print(f"✅ Counterpart can_submit_position=True")
        else:
            print(f"ℹ️ Counterpart already submitted or dispute not in awaiting_positions state. "
                  f"status={status}, my_position={my_position}, can_submit={can_submit}")

    def test_counterpart_sees_organizer_as_other_party(self, counterpart_token):
        """Counterpart should see organizer's name as other_party_name"""
        response = requests.get(
            f"{BASE_URL}/api/disputes/{DEADLOCK_DISPUTE_ID}",
            headers={"Authorization": f"Bearer {counterpart_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        other_name = data.get("other_party_name", "")
        my_role = data.get("my_role", "")
        
        assert my_role == "participant", f"Expected my_role='participant', got '{my_role}'"
        # Counterpart should see the organizer's name
        assert other_name != "", f"other_party_name should not be empty for counterpart"
        print(f"✅ Counterpart sees other_party_name='{other_name}'")


class TestDisplayStateLogic:
    """Tests for the 5-case display_state logic"""

    def test_display_state_values_are_valid(self, organizer_token):
        """display_state should be one of: waiting_both, waiting_other, arbitration, resolved"""
        response = requests.get(
            f"{BASE_URL}/api/disputes/{DEADLOCK_DISPUTE_ID}",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        valid_states = ["waiting_both", "waiting_other", "arbitration", "resolved"]
        assert data["display_state"] in valid_states, \
            f"display_state should be one of {valid_states}, got: {data['display_state']}"
        print(f"✅ display_state '{data['display_state']}' is valid")

    def test_display_state_matches_positions(self, organizer_token):
        """display_state should reflect the actual position states"""
        response = requests.get(
            f"{BASE_URL}/api/disputes/{DEADLOCK_DISPUTE_ID}",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        org_pos = data.get("organizer_position")
        par_pos = data.get("participant_position")
        status = data.get("status")
        display_state = data.get("display_state")
        
        # Verify display_state logic
        if status in ["resolved", "agreed_present", "agreed_absent", "agreed_late_penalized"]:
            assert display_state == "resolved", f"Expected 'resolved' for status={status}"
        elif status == "escalated":
            assert display_state == "arbitration", f"Expected 'arbitration' for status=escalated"
        elif org_pos is not None and par_pos is not None:
            assert display_state == "arbitration", \
                f"Expected 'arbitration' when both positions submitted but disagreed"
        elif org_pos is not None or par_pos is not None:
            assert display_state == "waiting_other", \
                f"Expected 'waiting_other' when one position submitted"
        else:
            assert display_state == "waiting_both", \
                f"Expected 'waiting_both' when no positions submitted"
        
        print(f"✅ display_state '{display_state}' matches position states "
              f"(org_pos={org_pos}, par_pos={par_pos}, status={status})")


class TestDisputeListDisplayState:
    """Tests for display_state in disputes list"""

    def test_disputes_mine_returns_display_state(self, organizer_token):
        """GET /api/disputes/mine returns display_state for each dispute"""
        response = requests.get(
            f"{BASE_URL}/api/disputes/mine",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        disputes = data.get("disputes", [])
        
        for dispute in disputes:
            assert "display_state" in dispute, \
                f"Dispute {dispute.get('dispute_id')} should have display_state"
            assert dispute["display_state"] in ["waiting_both", "waiting_other", "arbitration", "resolved"], \
                f"Invalid display_state: {dispute['display_state']}"
        
        print(f"✅ All {len(disputes)} disputes have valid display_state")

    def test_disputes_mine_returns_other_party_name(self, organizer_token):
        """GET /api/disputes/mine returns other_party_name for each dispute"""
        response = requests.get(
            f"{BASE_URL}/api/disputes/mine",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        disputes = data.get("disputes", [])
        
        for dispute in disputes:
            assert "other_party_name" in dispute, \
                f"Dispute {dispute.get('dispute_id')} should have other_party_name"
        
        print(f"✅ All {len(disputes)} disputes have other_party_name field")


class TestPositionSubmissionEndpoint:
    """Tests for POST /api/disputes/:id/position endpoint (without actually submitting)"""

    def test_position_endpoint_exists(self, counterpart_token):
        """POST /api/disputes/:id/position endpoint should exist"""
        # Send an invalid position to test endpoint exists without changing state
        response = requests.post(
            f"{BASE_URL}/api/disputes/{DEADLOCK_DISPUTE_ID}/position",
            headers={"Authorization": f"Bearer {counterpart_token}"},
            json={"position": "invalid_position_for_test"}
        )
        # Should return 400 (invalid position) not 404 (endpoint not found)
        assert response.status_code in [400, 200], \
            f"Expected 400 or 200, got {response.status_code}: {response.text}"
        
        if response.status_code == 400:
            data = response.json()
            # Should mention invalid position, not "endpoint not found"
            assert "invalide" in data.get("detail", "").lower() or "position" in data.get("detail", "").lower(), \
                f"Expected position validation error, got: {data}"
            print(f"✅ Position endpoint exists and validates input")
        else:
            print(f"ℹ️ Position endpoint returned 200 (position may have been accepted)")

    def test_counterpart_not_blocked_from_position_endpoint(self, counterpart_token):
        """Counterpart should not get 'not a party' error in deadlock case"""
        # First check if counterpart can submit
        detail_response = requests.get(
            f"{BASE_URL}/api/disputes/{DEADLOCK_DISPUTE_ID}",
            headers={"Authorization": f"Bearer {counterpart_token}"}
        )
        assert detail_response.status_code == 200
        
        data = detail_response.json()
        my_role = data.get("my_role")
        can_submit = data.get("can_submit_position")
        my_position = data.get("my_position")
        
        # Counterpart should be recognized as participant
        assert my_role == "participant", \
            f"Counterpart should be 'participant', got '{my_role}'"
        
        # If they haven't submitted yet and dispute is awaiting_positions
        if my_position is None and data.get("status") == "awaiting_positions":
            assert can_submit is True, \
                f"Counterpart should be able to submit position, can_submit={can_submit}"
            print(f"✅ Counterpart is recognized as participant and can submit position")
        else:
            print(f"ℹ️ Counterpart already submitted or dispute not awaiting positions")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
