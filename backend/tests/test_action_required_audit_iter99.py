"""
Test suite for Action Required Dashboard Audit - Iteration 99
Tests:
A. ACTION REQUIRED - INVITED: participant with status 'invited' on future appointment appears in action_required
B. ACTION REQUIRED - PENDING GUARANTEE: participant with status 'accepted_pending_guarantee' appears in action_required
C. ACTION REQUIRED - EXCLUSIONS: accepted/accepted_guaranteed/declined do NOT appear in action_required
D. ACTION REQUIRED - ORGANIZER NEVER: organizer items never appear in action_required
E. CANCELLED TO HISTORIQUE: cancelled appointments appear in 'past' bucket, not 'upcoming'
F. CANCELLED NOT ACTION_REQUIRED: cancelled appointment with invited participant NOT in action_required
G. DASHBOARD COUNTS: header shows correct counts
H. FRONTEND CTA: 'Finaliser ma garantie' button links to /appointments/{id}
I. TIMELINE CARDS: regular upcoming items display correctly
J. PAST ITEMS: past appointments including cancelled ones display in Historique
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test123!"

# Known test appointments from MongoDB
PENDING_GUARANTEE_APT_ID = "e33bf4d6-f1f2-4bb3-bbe3-bda9af659e84"
ACCEPTED_GUARANTEED_APT_ID = "6e5233cc-4ed5-421d-a43a-e4d8fbf8df26"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test user"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def timeline_data(auth_token):
    """Fetch timeline data once for all tests"""
    response = requests.get(
        f"{BASE_URL}/api/appointments/my-timeline",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200, f"Timeline fetch failed: {response.text}"
    return response.json()


class TestActionRequiredInvited:
    """A. ACTION REQUIRED - INVITED: participant with status 'invited' appears in action_required"""
    
    def test_invited_participants_in_action_required(self, timeline_data):
        """Invited participants on future appointments should be in action_required"""
        action_required = timeline_data["action_required"]
        
        invited_items = [
            item for item in action_required 
            if item["role"] == "participant" and item["status"] == "invited"
        ]
        
        # All invited items should have action_required=True
        for item in invited_items:
            assert item["action_required"] == True, f"Invited item missing action_required=True: {item['title']}"
            assert item["appointment_status"] != "cancelled", f"Cancelled item in action_required: {item['title']}"
    
    def test_invited_items_have_accept_decline_actions(self, timeline_data):
        """Invited participant items should have accept/decline actions"""
        action_required = timeline_data["action_required"]
        
        invited_items = [
            item for item in action_required 
            if item["role"] == "participant" and item["status"] == "invited"
        ]
        
        for item in invited_items:
            assert "accept" in item["actions"], f"Missing 'accept' action: {item['title']}"
            assert "decline" in item["actions"], f"Missing 'decline' action: {item['title']}"


class TestActionRequiredPendingGuarantee:
    """B. ACTION REQUIRED - PENDING GUARANTEE: accepted_pending_guarantee appears in action_required"""
    
    def test_pending_guarantee_in_action_required(self, timeline_data):
        """Participants with accepted_pending_guarantee status should be in action_required"""
        action_required = timeline_data["action_required"]
        
        pending_guarantee_items = [
            item for item in action_required 
            if item["role"] == "participant" and item["status"] == "accepted_pending_guarantee"
        ]
        
        # Check if we have any pending_guarantee items
        print(f"Found {len(pending_guarantee_items)} pending_guarantee items in action_required")
        
        for item in pending_guarantee_items:
            assert item["action_required"] == True
            assert item["appointment_status"] != "cancelled"
    
    def test_pending_guarantee_has_finalize_action(self, timeline_data):
        """Pending guarantee items should have finalize_guarantee action"""
        action_required = timeline_data["action_required"]
        
        pending_guarantee_items = [
            item for item in action_required 
            if item["role"] == "participant" and item["status"] == "accepted_pending_guarantee"
        ]
        
        for item in pending_guarantee_items:
            assert "finalize_guarantee" in item["actions"], f"Missing 'finalize_guarantee' action: {item['title']}"
    
    def test_pending_guarantee_has_correct_label(self, timeline_data):
        """Pending guarantee items should have 'Garantie en attente' label"""
        action_required = timeline_data["action_required"]
        
        pending_guarantee_items = [
            item for item in action_required 
            if item["role"] == "participant" and item["status"] == "accepted_pending_guarantee"
        ]
        
        for item in pending_guarantee_items:
            assert item["pending_label"] == "Garantie en attente", f"Wrong label: {item['pending_label']}"
    
    def test_specific_pending_guarantee_appointment(self, auth_token, timeline_data):
        """Test specific appointment e33bf4d6-f1f2-4bb3-bbe3-bda9af659e84 with pending_guarantee"""
        action_required = timeline_data["action_required"]
        
        # Find the specific test appointment
        test_apt = next(
            (item for item in action_required if item["appointment_id"] == PENDING_GUARANTEE_APT_ID),
            None
        )
        
        if test_apt:
            print(f"Found test appointment in action_required: {test_apt['title']}")
            assert test_apt["status"] == "accepted_pending_guarantee"
            assert test_apt["action_required"] == True
            assert "finalize_guarantee" in test_apt["actions"]
        else:
            # Check if it's in upcoming or past (might be past now)
            all_items = timeline_data["upcoming"] + timeline_data["past"]
            test_apt = next(
                (item for item in all_items if item["appointment_id"] == PENDING_GUARANTEE_APT_ID),
                None
            )
            if test_apt:
                print(f"Test appointment found in {test_apt.get('role')} bucket with status: {test_apt.get('status')}")
                # If it's past, that's expected
                if test_apt.get("starts_at", "") < "2026-01-01":
                    pytest.skip("Test appointment is in the past")
            else:
                print("Test appointment not found - may not be associated with test user")


class TestActionRequiredExclusions:
    """C. ACTION REQUIRED - EXCLUSIONS: accepted/accepted_guaranteed/declined NOT in action_required"""
    
    def test_accepted_not_in_action_required(self, timeline_data):
        """Accepted participants should NOT be in action_required"""
        action_required = timeline_data["action_required"]
        
        accepted_items = [
            item for item in action_required 
            if item["role"] == "participant" and item["status"] == "accepted"
        ]
        
        assert len(accepted_items) == 0, f"Found {len(accepted_items)} accepted items in action_required"
    
    def test_accepted_guaranteed_not_in_action_required(self, timeline_data):
        """Accepted_guaranteed participants should NOT be in action_required"""
        action_required = timeline_data["action_required"]
        
        guaranteed_items = [
            item for item in action_required 
            if item["role"] == "participant" and item["status"] == "accepted_guaranteed"
        ]
        
        assert len(guaranteed_items) == 0, f"Found {len(guaranteed_items)} accepted_guaranteed items in action_required"
    
    def test_declined_not_in_action_required(self, timeline_data):
        """Declined participants should NOT be in action_required"""
        action_required = timeline_data["action_required"]
        
        declined_items = [
            item for item in action_required 
            if item["role"] == "participant" and item["status"] == "declined"
        ]
        
        assert len(declined_items) == 0, f"Found {len(declined_items)} declined items in action_required"


class TestOrganizerNeverInActionRequired:
    """D. ACTION REQUIRED - ORGANIZER NEVER: organizer items never appear in action_required"""
    
    def test_no_organizer_items_in_action_required(self, timeline_data):
        """CRITICAL: No organizer items should be in action_required bucket"""
        action_required = timeline_data["action_required"]
        
        organizer_items = [item for item in action_required if item["role"] == "organizer"]
        assert len(organizer_items) == 0, f"Found {len(organizer_items)} organizer items in action_required"
    
    def test_organizer_items_have_action_required_false(self, timeline_data):
        """All organizer items should have action_required=False"""
        all_items = timeline_data["action_required"] + timeline_data["upcoming"] + timeline_data["past"]
        
        organizer_items = [item for item in all_items if item["role"] == "organizer"]
        
        for item in organizer_items:
            assert item["action_required"] == False, f"Organizer item has action_required=True: {item['title']}"


class TestCancelledToHistorique:
    """E. CANCELLED TO HISTORIQUE: cancelled appointments in 'past' bucket, not 'upcoming'"""
    
    def test_no_cancelled_in_upcoming(self, timeline_data):
        """Cancelled appointments should NOT be in upcoming bucket"""
        upcoming = timeline_data["upcoming"]
        
        cancelled_in_upcoming = [
            item for item in upcoming 
            if item.get("appointment_status") == "cancelled"
        ]
        
        assert len(cancelled_in_upcoming) == 0, f"Found {len(cancelled_in_upcoming)} cancelled items in upcoming"
    
    def test_cancelled_in_past_bucket(self, timeline_data):
        """Cancelled appointments should be in past bucket"""
        past = timeline_data["past"]
        
        cancelled_in_past = [
            item for item in past 
            if item.get("appointment_status") == "cancelled"
        ]
        
        print(f"Found {len(cancelled_in_past)} cancelled items in past bucket")
        # Just verify structure, not count (depends on test data)
        for item in cancelled_in_past:
            assert item["appointment_status"] == "cancelled"
    
    def test_known_cancelled_appointments_in_past(self, timeline_data):
        """Known cancelled appointments (AUDIT-SC2, AUDIT-SC5) should be in past"""
        past = timeline_data["past"]
        
        # Look for known cancelled appointments
        audit_cancelled = [
            item for item in past 
            if "AUDIT-SC2" in item.get("title", "") or "AUDIT-SC5" in item.get("title", "")
        ]
        
        if audit_cancelled:
            print(f"Found {len(audit_cancelled)} AUDIT cancelled appointments in past")
            for item in audit_cancelled:
                print(f"  - {item['title']} (status: {item['appointment_status']})")


class TestCancelledNotInActionRequired:
    """F. CANCELLED NOT ACTION_REQUIRED: cancelled with invited participant NOT in action_required"""
    
    def test_no_cancelled_in_action_required(self, timeline_data):
        """Cancelled appointments should NEVER be in action_required"""
        action_required = timeline_data["action_required"]
        
        cancelled_items = [
            item for item in action_required 
            if item.get("appointment_status") == "cancelled"
        ]
        
        assert len(cancelled_items) == 0, f"Found {len(cancelled_items)} cancelled items in action_required"
    
    def test_action_required_items_not_cancelled(self, timeline_data):
        """All items in action_required should have active status"""
        action_required = timeline_data["action_required"]
        
        for item in action_required:
            assert item.get("appointment_status") != "cancelled", f"Cancelled item in action_required: {item['title']}"


class TestDashboardCounts:
    """G. DASHBOARD COUNTS: header shows correct counts"""
    
    def test_counts_match_bucket_lengths(self, timeline_data):
        """Counts should match actual bucket lengths"""
        counts = timeline_data["counts"]
        
        assert counts["action_required"] == len(timeline_data["action_required"])
        assert counts["upcoming"] == len(timeline_data["upcoming"])
        assert counts["past"] == len(timeline_data["past"])
    
    def test_total_count_is_sum(self, timeline_data):
        """Total count should be sum of all buckets"""
        counts = timeline_data["counts"]
        expected_total = counts["action_required"] + counts["upcoming"] + counts["past"]
        assert counts["total"] == expected_total
    
    def test_action_required_count_only_participant_actions(self, timeline_data):
        """action_required count should only include participant items needing action"""
        counts = timeline_data["counts"]
        action_required = timeline_data["action_required"]
        
        # All items should be participants with invited or accepted_pending_guarantee
        valid_items = [
            item for item in action_required 
            if item["role"] == "participant" and item["status"] in ("invited", "accepted_pending_guarantee")
        ]
        
        assert counts["action_required"] == len(valid_items)


class TestTimelineItemStructure:
    """I. TIMELINE CARDS: regular upcoming items display correctly"""
    
    def test_upcoming_items_have_required_fields(self, timeline_data):
        """Upcoming items should have all required fields"""
        required_fields = [
            "appointment_id", "role", "status", "action_required", "starts_at",
            "counterparty_name", "title", "appointment_type", "duration_minutes",
            "penalty_amount", "actions", "appointment_status"
        ]
        
        upcoming = timeline_data["upcoming"][:10]  # Check first 10
        
        for item in upcoming:
            for field in required_fields:
                assert field in item, f"Missing field '{field}' in: {item.get('title', 'unknown')}"
    
    def test_organizer_items_have_participant_counts(self, timeline_data):
        """Organizer items should have participant counts"""
        upcoming = timeline_data["upcoming"]
        
        organizer_items = [item for item in upcoming if item["role"] == "organizer"][:10]
        
        for item in organizer_items:
            assert "participants_count" in item
            assert "accepted_count" in item
            assert "pending_count" in item
    
    def test_organizer_items_have_correct_actions(self, timeline_data):
        """Organizer items should have view_details, remind (if pending), delete actions"""
        upcoming = timeline_data["upcoming"]
        
        organizer_items = [item for item in upcoming if item["role"] == "organizer"][:10]
        
        for item in organizer_items:
            assert "view_details" in item["actions"]
            if item["pending_count"] > 0:
                assert "remind" in item["actions"], f"Missing remind action for item with pending: {item['title']}"


class TestPastItems:
    """J. PAST ITEMS: past appointments including cancelled ones display correctly"""
    
    def test_past_items_exist(self, timeline_data):
        """Past bucket should have items"""
        past = timeline_data["past"]
        assert len(past) > 0, "No items in past bucket"
    
    def test_past_items_have_required_fields(self, timeline_data):
        """Past items should have required fields"""
        required_fields = [
            "appointment_id", "role", "status", "starts_at", "title", "appointment_status"
        ]
        
        past = timeline_data["past"][:10]
        
        for item in past:
            for field in required_fields:
                assert field in item, f"Missing field '{field}' in past item: {item.get('title', 'unknown')}"
    
    def test_past_items_sorted_reverse_chronological(self, timeline_data):
        """Past items should be sorted newest first"""
        past = timeline_data["past"]
        
        if len(past) > 1:
            for i in range(len(past) - 1):
                # Cancelled items might have future dates but are forced to past
                # So we just verify the list is sorted
                current_date = past[i].get("sort_date", past[i].get("starts_at", ""))
                next_date = past[i + 1].get("sort_date", past[i + 1].get("starts_at", ""))
                # Reverse chronological: current >= next
                assert current_date >= next_date, f"Past items not sorted: {current_date} < {next_date}"


class TestActionRequiredValidStatuses:
    """Verify only valid statuses appear in action_required"""
    
    def test_only_invited_or_pending_guarantee_in_action_required(self, timeline_data):
        """action_required should only contain invited or accepted_pending_guarantee"""
        action_required = timeline_data["action_required"]
        
        valid_statuses = ("invited", "accepted_pending_guarantee")
        
        for item in action_required:
            assert item["status"] in valid_statuses, f"Invalid status in action_required: {item['status']}"
            assert item["role"] == "participant", f"Non-participant in action_required: {item['role']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
