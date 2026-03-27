"""
Test suite for Action Required Fix - Iteration 94
Tests that action_required bucket contains ONLY participant invitations (status=invited)
and NOT organizer items with pending participants.

Also tests new fields: location_display_name, tolerated_delay_minutes, cancellation_deadline_hours
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test123!"


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


class TestActionRequiredFix:
    """Tests for the action_required bucket fix"""
    
    def test_timeline_endpoint_returns_200(self, auth_token):
        """Test that my-timeline endpoint returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/my-timeline",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
    
    def test_timeline_has_three_buckets(self, timeline_data):
        """Test that timeline has action_required, upcoming, past buckets"""
        assert "action_required" in timeline_data
        assert "upcoming" in timeline_data
        assert "past" in timeline_data
        assert "counts" in timeline_data
    
    def test_action_required_contains_only_participant_items(self, timeline_data):
        """CRITICAL: action_required must contain ONLY participant items with status=invited"""
        action_required = timeline_data["action_required"]
        
        for item in action_required:
            # Must be a participant item
            assert item["role"] == "participant", f"Found organizer item in action_required: {item['title']}"
            assert item["is_user_participant"] == True, f"Item is not participant: {item['title']}"
            assert item["is_user_organizer"] == False, f"Item is organizer: {item['title']}"
            # Must have status=invited
            assert item["status"] == "invited", f"Participant status is not 'invited': {item['status']}"
            # action_required flag must be True
            assert item["action_required"] == True
    
    def test_no_organizer_items_in_action_required(self, timeline_data):
        """CRITICAL: No organizer items should be in action_required bucket"""
        action_required = timeline_data["action_required"]
        
        organizer_items = [item for item in action_required if item["role"] == "organizer"]
        assert len(organizer_items) == 0, f"Found {len(organizer_items)} organizer items in action_required"
    
    def test_organizer_items_with_pending_in_upcoming(self, timeline_data):
        """Organizer items with pending participants should be in upcoming bucket"""
        upcoming = timeline_data["upcoming"]
        
        organizer_with_pending = [
            item for item in upcoming 
            if item["role"] == "organizer" and item.get("pending_count", 0) > 0
        ]
        
        # Should have organizer items with pending in upcoming
        assert len(organizer_with_pending) > 0, "No organizer items with pending found in upcoming"
        
        # All should have action_required=False
        for item in organizer_with_pending:
            assert item["action_required"] == False, f"Organizer item has action_required=True: {item['title']}"
    
    def test_organizer_items_have_pending_label(self, timeline_data):
        """Organizer items with pending should have 'En attente de réponse (N)' label"""
        upcoming = timeline_data["upcoming"]
        
        organizer_with_pending = [
            item for item in upcoming 
            if item["role"] == "organizer" and item.get("pending_count", 0) > 0
        ]
        
        for item in organizer_with_pending:
            pending_count = item["pending_count"]
            expected_label = f"En attente de réponse ({pending_count})"
            assert item["pending_label"] == expected_label, f"Wrong pending_label: {item['pending_label']}"
    
    def test_organizer_items_have_remind_action(self, timeline_data):
        """Organizer items with pending should have 'remind' action"""
        upcoming = timeline_data["upcoming"]
        
        organizer_with_pending = [
            item for item in upcoming 
            if item["role"] == "organizer" and item.get("pending_count", 0) > 0
        ]
        
        for item in organizer_with_pending:
            assert "remind" in item["actions"], f"Missing 'remind' action for: {item['title']}"


class TestNewTimelineFields:
    """Tests for new fields: location_display_name, tolerated_delay_minutes, cancellation_deadline_hours"""
    
    def test_timeline_items_have_location_display_name(self, timeline_data):
        """All timeline items should have location_display_name field"""
        all_items = timeline_data["action_required"] + timeline_data["upcoming"] + timeline_data["past"][:10]
        
        for item in all_items:
            assert "location_display_name" in item, f"Missing location_display_name in: {item['title']}"
    
    def test_timeline_items_have_tolerated_delay_minutes(self, timeline_data):
        """All timeline items should have tolerated_delay_minutes field"""
        all_items = timeline_data["action_required"] + timeline_data["upcoming"] + timeline_data["past"][:10]
        
        for item in all_items:
            assert "tolerated_delay_minutes" in item, f"Missing tolerated_delay_minutes in: {item['title']}"
            assert isinstance(item["tolerated_delay_minutes"], (int, float)), "tolerated_delay_minutes should be numeric"
    
    def test_timeline_items_have_cancellation_deadline_hours(self, timeline_data):
        """All timeline items should have cancellation_deadline_hours field"""
        all_items = timeline_data["action_required"] + timeline_data["upcoming"] + timeline_data["past"][:10]
        
        for item in all_items:
            assert "cancellation_deadline_hours" in item, f"Missing cancellation_deadline_hours in: {item['title']}"
            assert isinstance(item["cancellation_deadline_hours"], (int, float)), "cancellation_deadline_hours should be numeric"


class TestDashboardCounts:
    """Tests for dashboard header counts"""
    
    def test_counts_match_bucket_lengths(self, timeline_data):
        """Counts should match actual bucket lengths"""
        counts = timeline_data["counts"]
        
        assert counts["action_required"] == len(timeline_data["action_required"])
        assert counts["upcoming"] == len(timeline_data["upcoming"])
        assert counts["past"] == len(timeline_data["past"])
        assert counts["total"] == counts["action_required"] + counts["upcoming"] + counts["past"]
    
    def test_action_required_count_is_participant_invitations_only(self, timeline_data):
        """action_required count should only include participant invitations"""
        counts = timeline_data["counts"]
        action_required = timeline_data["action_required"]
        
        # Count participant invitations
        participant_invitations = [
            item for item in action_required 
            if item["role"] == "participant" and item["status"] == "invited"
        ]
        
        assert counts["action_required"] == len(participant_invitations)


class TestTimelineItemStructure:
    """Tests for timeline item structure"""
    
    def test_participant_items_have_required_fields(self, timeline_data):
        """Participant items should have all required fields"""
        required_fields = [
            "appointment_id", "role", "status", "action_required", "starts_at",
            "counterparty_name", "is_user_organizer", "is_user_participant",
            "title", "appointment_type", "duration_minutes", "penalty_amount",
            "penalty_currency", "actions", "pending_label",
            "location_display_name", "tolerated_delay_minutes", "cancellation_deadline_hours"
        ]
        
        participant_items = [
            item for item in timeline_data["action_required"] + timeline_data["upcoming"]
            if item["role"] == "participant"
        ]
        
        for item in participant_items:
            for field in required_fields:
                assert field in item, f"Missing field '{field}' in participant item: {item.get('title', 'unknown')}"
    
    def test_organizer_items_have_required_fields(self, timeline_data):
        """Organizer items should have all required fields including participant counts"""
        required_fields = [
            "appointment_id", "role", "status", "action_required", "starts_at",
            "counterparty_name", "is_user_organizer", "is_user_participant",
            "title", "appointment_type", "duration_minutes", "penalty_amount",
            "penalty_currency", "actions", "pending_label",
            "participants_count", "accepted_count", "pending_count",
            "location_display_name", "tolerated_delay_minutes", "cancellation_deadline_hours"
        ]
        
        organizer_items = [
            item for item in timeline_data["upcoming"]
            if item["role"] == "organizer"
        ][:10]  # Check first 10
        
        for item in organizer_items:
            for field in required_fields:
                assert field in item, f"Missing field '{field}' in organizer item: {item.get('title', 'unknown')}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
