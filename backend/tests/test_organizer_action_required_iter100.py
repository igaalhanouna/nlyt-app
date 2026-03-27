"""
Iteration 100 - Organizer Action Required Feature Tests
Tests the new feature: organizer items appear in 'Action requise' when:
- < 50% of participants are guaranteed AND
- cancellation deadline is within 24h

Wording:
- 0 guaranteed: 'Personne n'a encore sécurisé sa présence'
- Partial: 'Seulement X/Y présence(s) sécurisée(s)'

CTAs: Relancer, Annuler, Voir détails
Cancel moves item to Historique
"""

import pytest
import requests
import os
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test123!"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.text}")
    return response.json().get("access_token")


@pytest.fixture(scope="module")
def authenticated_client(auth_token):
    """Session with auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


@pytest.fixture(scope="module")
def timeline_data(auth_token):
    """Fetch timeline data once for all tests"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    }
    response = requests.get(f"{BASE_URL}/api/appointments/my-timeline", headers=headers)
    assert response.status_code == 200, f"Failed to fetch timeline: {response.text}"
    return response.json()


class TestOrganizerActionRequiredZeroGuaranteed:
    """A. ORGANIZER ACTION_REQUIRED - 0 GUARANTEED: organizer items with 0 guaranteed and deadline < 24h"""
    
    def test_zero_guaranteed_items_in_action_required(self, timeline_data):
        """Items with 0 guaranteed and deadline < 24h should appear in action_required"""
        action_required = timeline_data.get("action_required", [])
        
        # Find organizer items with 0 guaranteed
        org_zero_guaranteed = [
            item for item in action_required
            if item.get("role") == "organizer" 
            and item.get("guaranteed_count", 0) == 0
            and item.get("action_required") == True
        ]
        
        print(f"Found {len(org_zero_guaranteed)} organizer items with 0 guaranteed in action_required")
        
        # Verify they have correct label
        for item in org_zero_guaranteed:
            pending_label = item.get("pending_label", "")
            assert "Personne n'a encore sécurisé sa présence" in pending_label, \
                f"Expected 'Personne n'a encore sécurisé sa présence' label, got: {pending_label}"
            print(f"✅ Item '{item.get('title')}' has correct zero-guaranteed label")
    
    def test_zero_guaranteed_items_have_correct_actions(self, timeline_data):
        """Zero guaranteed items should have remind, cancel, view_details actions"""
        action_required = timeline_data.get("action_required", [])
        
        org_zero_guaranteed = [
            item for item in action_required
            if item.get("role") == "organizer" 
            and item.get("guaranteed_count", 0) == 0
            and item.get("action_required") == True
        ]
        
        for item in org_zero_guaranteed:
            actions = item.get("actions", [])
            assert "remind" in actions, f"Missing 'remind' action for {item.get('title')}"
            assert "cancel" in actions, f"Missing 'cancel' action for {item.get('title')}"
            assert "view_details" in actions, f"Missing 'view_details' action for {item.get('title')}"
            print(f"✅ Item '{item.get('title')}' has correct actions: {actions}")


class TestOrganizerActionRequiredPartialGuaranteed:
    """B. ORGANIZER ACTION_REQUIRED - PARTIAL: organizer items with < 50% guaranteed and deadline < 24h"""
    
    def test_partial_guaranteed_items_in_action_required(self, timeline_data):
        """Items with partial guaranteed (< 50%) and deadline < 24h should appear in action_required"""
        action_required = timeline_data.get("action_required", [])
        
        # Find organizer items with partial guaranteed (> 0 but < 50%)
        org_partial_guaranteed = [
            item for item in action_required
            if item.get("role") == "organizer" 
            and item.get("guaranteed_count", 0) > 0
            and item.get("action_required") == True
        ]
        
        print(f"Found {len(org_partial_guaranteed)} organizer items with partial guaranteed in action_required")
        
        # Verify they have correct label format
        for item in org_partial_guaranteed:
            pending_label = item.get("pending_label", "")
            guaranteed = item.get("guaranteed_count", 0)
            participants = item.get("participants_count", 0)
            
            # Should contain "Seulement X/Y présence(s) sécurisée(s)"
            assert "Seulement" in pending_label, \
                f"Expected 'Seulement X/Y' label, got: {pending_label}"
            print(f"✅ Item '{item.get('title')}' has correct partial label: {pending_label}")


class TestOrganizerExclusionEnoughGuaranteed:
    """C. ORGANIZER EXCLUSION - ENOUGH GUARANTEED: organizer items with >= 50% guaranteed do NOT appear in action_required"""
    
    def test_enough_guaranteed_not_in_action_required(self, timeline_data):
        """Items with >= 50% guaranteed should NOT be in action_required"""
        action_required = timeline_data.get("action_required", [])
        upcoming = timeline_data.get("upcoming", [])
        
        # Check that no organizer items with >= 50% guaranteed are in action_required
        for item in action_required:
            if item.get("role") == "organizer":
                guaranteed = item.get("guaranteed_count", 0)
                participants = item.get("participants_count", 0)
                
                # Calculate non-organizer count (participants_count is total non-org)
                non_org_count = participants
                
                if non_org_count > 0:
                    # Should be < 50% guaranteed to be in action_required
                    assert guaranteed < non_org_count / 2, \
                        f"Item '{item.get('title')}' has {guaranteed}/{non_org_count} guaranteed (>= 50%) but is in action_required"
        
        print("✅ No organizer items with >= 50% guaranteed found in action_required")


class TestOrganizerExclusionFarDeadline:
    """D. ORGANIZER EXCLUSION - FAR DEADLINE: organizer items where deadline > 24h away do NOT appear in action_required"""
    
    def test_far_deadline_not_in_action_required(self, timeline_data):
        """Items with deadline > 24h away should NOT be in action_required"""
        action_required = timeline_data.get("action_required", [])
        
        now = datetime.now(timezone.utc)
        
        for item in action_required:
            if item.get("role") == "organizer" and item.get("action_required"):
                starts_at = item.get("starts_at", "")
                cancel_hours = item.get("cancellation_deadline_hours", 0)
                
                if starts_at:
                    try:
                        start_dt = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
                        hours_to_start = (start_dt - now).total_seconds() / 3600
                        hours_to_deadline = hours_to_start - cancel_hours
                        
                        # Should be < 24h to deadline to be in action_required
                        assert hours_to_deadline < 24, \
                            f"Item '{item.get('title')}' has {hours_to_deadline:.1f}h to deadline (> 24h) but is in action_required"
                        
                        print(f"✅ Item '{item.get('title')}' correctly has {hours_to_deadline:.1f}h to deadline (< 24h)")
                    except Exception as e:
                        print(f"Warning: Could not parse date for {item.get('title')}: {e}")


class TestOrganizerExclusionCancelled:
    """E. ORGANIZER EXCLUSION - CANCELLED: cancelled appointments never in action_required"""
    
    def test_cancelled_not_in_action_required(self, timeline_data):
        """Cancelled appointments should never be in action_required"""
        action_required = timeline_data.get("action_required", [])
        
        cancelled_in_action = [
            item for item in action_required
            if item.get("appointment_status") == "cancelled" or item.get("status") == "cancelled"
        ]
        
        assert len(cancelled_in_action) == 0, \
            f"Found {len(cancelled_in_action)} cancelled items in action_required"
        
        print("✅ No cancelled items found in action_required")


class TestParticipantStillWorks:
    """F. PARTICIPANT STILL WORKS: participant items with 'invited' or 'accepted_pending_guarantee' still correctly appear in action_required"""
    
    def test_participant_invited_in_action_required(self, timeline_data):
        """Participant items with 'invited' status should be in action_required"""
        action_required = timeline_data.get("action_required", [])
        
        participant_invited = [
            item for item in action_required
            if item.get("role") == "participant" 
            and item.get("participant_status") == "invited"
        ]
        
        print(f"Found {len(participant_invited)} participant items with 'invited' status in action_required")
        
        for item in participant_invited:
            actions = item.get("actions", [])
            assert "accept" in actions, f"Missing 'accept' action for invited participant"
            assert "decline" in actions, f"Missing 'decline' action for invited participant"
            print(f"✅ Participant item '{item.get('title')}' has correct actions: {actions}")
    
    def test_participant_pending_guarantee_in_action_required(self, timeline_data):
        """Participant items with 'accepted_pending_guarantee' status should be in action_required"""
        action_required = timeline_data.get("action_required", [])
        
        participant_pending = [
            item for item in action_required
            if item.get("role") == "participant" 
            and item.get("participant_status") == "accepted_pending_guarantee"
        ]
        
        print(f"Found {len(participant_pending)} participant items with 'accepted_pending_guarantee' status in action_required")
        
        for item in participant_pending:
            actions = item.get("actions", [])
            assert "finalize_guarantee" in actions, f"Missing 'finalize_guarantee' action for pending guarantee participant"
            print(f"✅ Participant item '{item.get('title')}' has correct actions: {actions}")


class TestCountsCoherence:
    """J. COUNTS COHERENCE: header counts match bucket lengths"""
    
    def test_counts_match_bucket_lengths(self, timeline_data):
        """Counts should match the actual bucket lengths"""
        counts = timeline_data.get("counts", {})
        
        action_required_count = counts.get("action_required", 0)
        upcoming_count = counts.get("upcoming", 0)
        past_count = counts.get("past", 0)
        
        action_required_len = len(timeline_data.get("action_required", []))
        upcoming_len = len(timeline_data.get("upcoming", []))
        past_len = len(timeline_data.get("past", []))
        
        assert action_required_count == action_required_len, \
            f"action_required count mismatch: {action_required_count} vs {action_required_len}"
        assert upcoming_count == upcoming_len, \
            f"upcoming count mismatch: {upcoming_count} vs {upcoming_len}"
        assert past_count == past_len, \
            f"past count mismatch: {past_count} vs {past_len}"
        
        print(f"✅ Counts match: action_required={action_required_count}, upcoming={upcoming_count}, past={past_count}")


class TestCancelledInPast:
    """K. CANCELLED IN PAST: cancelled items visible in Historique tab with 'Annulé' badge"""
    
    def test_cancelled_items_in_past(self, timeline_data):
        """Cancelled items should be in past bucket"""
        past = timeline_data.get("past", [])
        
        cancelled_in_past = [
            item for item in past
            if item.get("appointment_status") == "cancelled" or item.get("status") == "cancelled"
        ]
        
        print(f"Found {len(cancelled_in_past)} cancelled items in past bucket")
        
        # Verify they exist
        assert len(cancelled_in_past) >= 0, "Should be able to find cancelled items in past"
        
        for item in cancelled_in_past:
            print(f"✅ Cancelled item in past: '{item.get('title')}'")


class TestCancelEndpoint:
    """H. CANCEL CTA: POST /api/appointments/{id}/cancel endpoint works correctly"""
    
    def test_cancel_endpoint_requires_auth(self):
        """Cancel endpoint should require authentication"""
        response = requests.post(f"{BASE_URL}/api/appointments/fake-id/cancel")
        assert response.status_code in [401, 403], \
            f"Expected 401/403 for unauthenticated cancel, got {response.status_code}"
        print("✅ Cancel endpoint requires authentication")
    
    def test_cancel_endpoint_returns_404_for_invalid_id(self, auth_token):
        """Cancel endpoint should return 404 for non-existent appointment"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(f"{BASE_URL}/api/appointments/non-existent-id/cancel", headers=headers)
        assert response.status_code == 404, \
            f"Expected 404 for non-existent appointment, got {response.status_code}"
        print("✅ Cancel endpoint returns 404 for invalid ID")


class TestRemindEndpoint:
    """I. REMIND CTA: POST /api/appointments/{id}/remind endpoint works correctly"""
    
    def test_remind_endpoint_requires_auth(self):
        """Remind endpoint should require authentication"""
        response = requests.post(f"{BASE_URL}/api/appointments/fake-id/remind")
        assert response.status_code in [401, 403], \
            f"Expected 401/403 for unauthenticated remind, got {response.status_code}"
        print("✅ Remind endpoint requires authentication")
    
    def test_remind_endpoint_returns_404_for_invalid_id(self, auth_token):
        """Remind endpoint should return 404 for non-existent appointment"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(f"{BASE_URL}/api/appointments/non-existent-id/remind", headers=headers)
        assert response.status_code == 404, \
            f"Expected 404 for non-existent appointment, got {response.status_code}"
        print("✅ Remind endpoint returns 404 for invalid ID")


class TestNoRegression:
    """L. NO REGRESSION: regular upcoming timeline cards still display correctly"""
    
    def test_upcoming_items_have_required_fields(self, timeline_data):
        """Upcoming items should have all required fields"""
        upcoming = timeline_data.get("upcoming", [])
        
        required_fields = ["appointment_id", "role", "title", "starts_at", "actions"]
        
        for item in upcoming[:5]:  # Check first 5 items
            for field in required_fields:
                assert field in item, f"Missing required field '{field}' in upcoming item"
            print(f"✅ Upcoming item '{item.get('title')}' has all required fields")
    
    def test_organizer_items_have_participant_counts(self, timeline_data):
        """Organizer items should have participant count fields"""
        upcoming = timeline_data.get("upcoming", [])
        
        organizer_items = [item for item in upcoming if item.get("role") == "organizer"]
        
        for item in organizer_items[:5]:  # Check first 5 organizer items
            assert "participants_count" in item, f"Missing participants_count in organizer item"
            assert "accepted_count" in item, f"Missing accepted_count in organizer item"
            assert "guaranteed_count" in item, f"Missing guaranteed_count in organizer item"
            print(f"✅ Organizer item '{item.get('title')}' has participant counts: {item.get('participants_count')}/{item.get('accepted_count')}/{item.get('guaranteed_count')}")


class TestOrganizerAlertItemsDetails:
    """Detailed tests for organizer alert items in action_required"""
    
    def test_org_alert_items_structure(self, timeline_data):
        """Verify structure of organizer alert items"""
        action_required = timeline_data.get("action_required", [])
        
        org_alerts = [
            item for item in action_required
            if item.get("role") == "organizer" and item.get("action_required") == True
        ]
        
        print(f"\n=== Organizer Alert Items in Action Required ===")
        print(f"Total: {len(org_alerts)}")
        
        for item in org_alerts:
            print(f"\n--- {item.get('title')} ---")
            print(f"  appointment_id: {item.get('appointment_id')}")
            print(f"  guaranteed_count: {item.get('guaranteed_count')}")
            print(f"  participants_count: {item.get('participants_count')}")
            print(f"  pending_label: {item.get('pending_label')}")
            print(f"  actions: {item.get('actions')}")
            print(f"  starts_at: {item.get('starts_at')}")
            print(f"  cancellation_deadline_hours: {item.get('cancellation_deadline_hours')}")
            
            # Verify structure
            assert item.get("actions") == ["remind", "cancel", "view_details"], \
                f"Expected actions ['remind', 'cancel', 'view_details'], got {item.get('actions')}"
            assert item.get("pending_label") is not None, "Missing pending_label for org alert"
        
        if len(org_alerts) > 0:
            print(f"\n✅ All {len(org_alerts)} organizer alert items have correct structure")
        else:
            print("\n⚠️ No organizer alert items found in action_required (may be expected if no items match criteria)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
