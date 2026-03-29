"""
Test suite for the unified dashboard timeline feature.
Tests GET /api/appointments/my-timeline endpoint which merges organizer + participant items.
Uses session-scoped login to avoid rate limiting.
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://litigation-mgmt.preview.emergentagent.com')

# Test credentials
TEST_USER_EMAIL = "testuser_audit@nlyt.app"
TEST_USER_PASSWORD = "Test123!"


@pytest.fixture(scope="module")
def auth_session():
    """Module-scoped authenticated session to avoid rate limiting"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Wait a bit to avoid rate limit from previous runs
    time.sleep(2)
    
    # Login to get token
    login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD
    })
    
    if login_resp.status_code == 429:
        # Rate limited, wait and retry
        time.sleep(60)
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
    
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json().get("access_token")
    assert token, "No token in login response"
    session.headers.update({"Authorization": f"Bearer {token}"})
    
    return session


@pytest.fixture(scope="module")
def timeline_data(auth_session):
    """Fetch timeline data once for all tests"""
    resp = auth_session.get(f"{BASE_URL}/api/appointments/my-timeline")
    assert resp.status_code == 200, f"Timeline fetch failed: {resp.text}"
    return resp.json()


class TestUnifiedTimeline:
    """Tests for the unified dashboard timeline endpoint"""
    
    def test_my_timeline_endpoint_returns_200(self, auth_session):
        """Test that GET /api/appointments/my-timeline returns 200"""
        resp = auth_session.get(f"{BASE_URL}/api/appointments/my-timeline")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print("✅ GET /api/appointments/my-timeline returns 200")
    
    def test_my_timeline_returns_three_buckets(self, timeline_data):
        """Test that response contains action_required, upcoming, past buckets"""
        assert "action_required" in timeline_data, "Missing 'action_required' bucket"
        assert "upcoming" in timeline_data, "Missing 'upcoming' bucket"
        assert "past" in timeline_data, "Missing 'past' bucket"
        assert isinstance(timeline_data["action_required"], list), "action_required should be a list"
        assert isinstance(timeline_data["upcoming"], list), "upcoming should be a list"
        assert isinstance(timeline_data["past"], list), "past should be a list"
        print(f"✅ Timeline has 3 buckets: action_required={len(timeline_data['action_required'])}, upcoming={len(timeline_data['upcoming'])}, past={len(timeline_data['past'])}")
    
    def test_my_timeline_returns_counts(self, timeline_data):
        """Test that response contains counts object"""
        assert "counts" in timeline_data, "Missing 'counts' object"
        counts = timeline_data["counts"]
        assert "action_required" in counts, "Missing action_required count"
        assert "upcoming" in counts, "Missing upcoming count"
        assert "past" in counts, "Missing past count"
        assert "total" in counts, "Missing total count"
        
        # Verify counts match actual list lengths
        assert counts["action_required"] == len(timeline_data["action_required"]), "action_required count mismatch"
        assert counts["upcoming"] == len(timeline_data["upcoming"]), "upcoming count mismatch"
        assert counts["past"] == len(timeline_data["past"]), "past count mismatch"
        print(f"✅ Counts object correct: {counts}")
    
    def test_timeline_item_has_required_fields(self, timeline_data):
        """Test that each timeline item has all required fields"""
        all_items = timeline_data["action_required"] + timeline_data["upcoming"] + timeline_data["past"]
        
        if len(all_items) == 0:
            pytest.skip("No timeline items to test field structure")
        
        required_fields = [
            "appointment_id", "role", "status", "action_required", "starts_at",
            "sort_date", "counterparty_name", "is_user_organizer", "is_user_participant",
            "actions", "title"
        ]
        
        for item in all_items[:5]:  # Test first 5 items
            for field in required_fields:
                assert field in item, f"Missing required field '{field}' in item {item.get('appointment_id')}"
        
        print(f"✅ All {len(all_items)} timeline items have required fields")
    
    def test_organizer_items_have_correct_role(self, timeline_data):
        """Test that organizer items have role='organizer' and is_user_organizer=True"""
        all_items = timeline_data["action_required"] + timeline_data["upcoming"] + timeline_data["past"]
        organizer_items = [i for i in all_items if i.get("is_user_organizer")]
        
        if len(organizer_items) == 0:
            pytest.skip("No organizer items to test")
        
        for item in organizer_items:
            assert item["role"] == "organizer", f"Organizer item should have role='organizer', got {item['role']}"
            assert item["is_user_organizer"] == True, "is_user_organizer should be True"
            assert item["is_user_participant"] == False, "is_user_participant should be False for organizer"
        
        print(f"✅ {len(organizer_items)} organizer items have correct role='organizer'")
    
    def test_participant_items_have_correct_role(self, timeline_data):
        """Test that participant items have role='participant' and is_user_participant=True"""
        all_items = timeline_data["action_required"] + timeline_data["upcoming"] + timeline_data["past"]
        participant_items = [i for i in all_items if i.get("is_user_participant")]
        
        if len(participant_items) == 0:
            pytest.skip("No participant items to test")
        
        for item in participant_items:
            assert item["role"] == "participant", f"Participant item should have role='participant', got {item['role']}"
            assert item["is_user_participant"] == True, "is_user_participant should be True"
            assert item["is_user_organizer"] == False, "is_user_organizer should be False for participant"
            # Participant items should have counterparty_name (organizer name)
            assert item["counterparty_name"], "Participant item should have counterparty_name (organizer)"
        
        print(f"✅ {len(participant_items)} participant items have correct role='participant'")
    
    def test_organizer_pending_items_have_action_required(self, timeline_data):
        """Test that organizer items with pending participants have action_required=True"""
        action_required_items = timeline_data["action_required"]
        organizer_action_items = [i for i in action_required_items if i.get("is_user_organizer")]
        
        for item in organizer_action_items:
            assert item["action_required"] == True, "Organizer action item should have action_required=True"
            # Should have pending_label like "En attente de réponse (N)"
            if item.get("pending_count", 0) > 0:
                assert item.get("pending_label"), "Organizer with pending should have pending_label"
                assert "En attente" in item["pending_label"], f"Expected 'En attente' in pending_label, got {item['pending_label']}"
        
        print(f"✅ {len(organizer_action_items)} organizer action items have correct action_required=True")
    
    def test_participant_invited_items_have_action_required(self, timeline_data):
        """Test that participant items with status=invited have action_required=True"""
        action_required_items = timeline_data["action_required"]
        participant_invited_items = [
            i for i in action_required_items 
            if i.get("is_user_participant") and i.get("status") == "invited"
        ]
        
        for item in participant_invited_items:
            assert item["action_required"] == True, "Participant invited item should have action_required=True"
            # Should have pending_label "Votre réponse est attendue"
            assert item.get("pending_label") == "Votre réponse est attendue", \
                f"Expected 'Votre réponse est attendue', got {item.get('pending_label')}"
            # Should have accept/decline actions
            assert "accept" in item.get("actions", []), "Participant invited should have 'accept' action"
            assert "decline" in item.get("actions", []), "Participant invited should have 'decline' action"
        
        print(f"✅ {len(participant_invited_items)} participant invited items have correct action_required=True and actions")
    
    def test_organizer_items_have_remind_action_when_pending(self, timeline_data):
        """Test that organizer items with pending participants have 'remind' action"""
        all_items = timeline_data["action_required"] + timeline_data["upcoming"]
        organizer_with_pending = [
            i for i in all_items 
            if i.get("is_user_organizer") and i.get("pending_count", 0) > 0
        ]
        
        for item in organizer_with_pending:
            assert "remind" in item.get("actions", []), \
                f"Organizer with pending should have 'remind' action, got {item.get('actions')}"
        
        print(f"✅ {len(organizer_with_pending)} organizer items with pending have 'remind' action")
    
    def test_no_duplicate_items(self, timeline_data):
        """Test that there are no duplicate appointment_ids in the timeline"""
        all_items = timeline_data["action_required"] + timeline_data["upcoming"] + timeline_data["past"]
        apt_ids = [i["appointment_id"] for i in all_items]
        
        # Check for duplicates
        seen = set()
        duplicates = []
        for apt_id in apt_ids:
            if apt_id in seen:
                duplicates.append(apt_id)
            seen.add(apt_id)
        
        assert len(duplicates) == 0, f"Found duplicate appointment_ids: {duplicates}"
        print(f"✅ No duplicate items in timeline ({len(all_items)} unique items)")
    
    def test_items_sorted_by_date(self, timeline_data):
        """Test that items within each bucket are sorted by date"""
        # Action required and upcoming should be ascending
        for bucket_name in ["action_required", "upcoming"]:
            bucket = timeline_data[bucket_name]
            if len(bucket) > 1:
                dates = [i["sort_date"] for i in bucket]
                assert dates == sorted(dates), f"{bucket_name} items not sorted ascending"
        
        # Past should be descending (most recent first)
        past = timeline_data["past"]
        if len(past) > 1:
            dates = [i["sort_date"] for i in past]
            assert dates == sorted(dates, reverse=True), "past items not sorted descending"
        
        print("✅ Items correctly sorted by date in each bucket")


class TestTimelineItemFields:
    """Tests for specific field values in timeline items"""
    
    def test_organizer_item_fields(self, timeline_data):
        """Test that organizer items have all expected fields"""
        all_items = timeline_data["action_required"] + timeline_data["upcoming"] + timeline_data["past"]
        organizer_items = [i for i in all_items if i.get("is_user_organizer")]
        
        if len(organizer_items) == 0:
            pytest.skip("No organizer items to test")
        
        item = organizer_items[0]
        
        # Check organizer-specific fields
        assert "participants_count" in item, "Missing participants_count"
        assert "accepted_count" in item, "Missing accepted_count"
        assert "pending_count" in item, "Missing pending_count"
        assert "appointment_type" in item, "Missing appointment_type"
        assert "duration_minutes" in item, "Missing duration_minutes"
        assert "penalty_amount" in item, "Missing penalty_amount"
        assert "penalty_currency" in item, "Missing penalty_currency"
        
        print(f"✅ Organizer item has all expected fields")
    
    def test_participant_item_fields(self, timeline_data):
        """Test that participant items have all expected fields"""
        all_items = timeline_data["action_required"] + timeline_data["upcoming"] + timeline_data["past"]
        participant_items = [i for i in all_items if i.get("is_user_participant")]
        
        if len(participant_items) == 0:
            pytest.skip("No participant items to test")
        
        item = participant_items[0]
        
        # Check participant-specific fields
        assert "participant_status" in item, "Missing participant_status"
        assert "participant_id" in item, "Missing participant_id"
        assert "invitation_token" in item, "Missing invitation_token"
        
        print(f"✅ Participant item has all expected fields")


class TestExistingFeaturesRegression:
    """Regression tests to ensure existing features still work"""
    
    def test_analytics_stats_still_works(self, auth_session):
        """Test that GET /api/appointments/analytics/stats still works"""
        resp = auth_session.get(f"{BASE_URL}/api/appointments/analytics/stats")
        assert resp.status_code == 200, f"Analytics stats failed: {resp.text}"
        data = resp.json()
        assert "total_engagements" in data, "Missing total_engagements"
        assert "global_message" in data, "Missing global_message"
        print(f"✅ Analytics stats endpoint works: {data.get('total_engagements')} engagements")
    
    def test_wallet_impact_still_works(self, auth_session):
        """Test that GET /api/wallet/impact still works"""
        resp = auth_session.get(f"{BASE_URL}/api/wallet/impact")
        assert resp.status_code == 200, f"Wallet impact failed: {resp.text}"
        data = resp.json()
        assert "total_charity_cents" in data, "Missing total_charity_cents"
        print(f"✅ Wallet impact endpoint works: {data.get('total_charity_cents')} cents")
    
    def test_appointments_list_still_works(self, auth_session):
        """Test that GET /api/appointments/ still works"""
        resp = auth_session.get(f"{BASE_URL}/api/appointments/")
        assert resp.status_code == 200, f"Appointments list failed: {resp.text}"
        data = resp.json()
        assert "items" in data, "Missing items"
        assert "total" in data, "Missing total"
        print(f"✅ Appointments list endpoint works: {data.get('total')} appointments")
    
    def test_workspaces_list_still_works(self, auth_session):
        """Test that GET /api/workspaces/ still works"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/")
        assert resp.status_code == 200, f"Workspaces list failed: {resp.text}"
        data = resp.json()
        # Workspaces endpoint returns {"workspaces": [...]}
        workspaces = data.get("workspaces", data) if isinstance(data, dict) else data
        assert isinstance(workspaces, list), "Workspaces should return a list"
        print(f"✅ Workspaces list endpoint works: {len(workspaces)} workspaces")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
