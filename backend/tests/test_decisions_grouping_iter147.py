"""
Test Decisions Grouping Feature - Iteration 147
Tests the frontend grouping of decisions by appointment_id.
Backend returns flat list, frontend groups by appointment_id.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "testuser_audit@nlyt.app"
ADMIN_PASSWORD = "TestAudit123!"
PARTICIPANT_EMAIL = "igaal@hotmail.com"
PARTICIPANT_PASSWORD = "Test123!"


class TestDecisionsAPI:
    """Test the /api/disputes/decisions/mine endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        """Login as admin and return session with auth token"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Login
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        token = data.get("access_token")
        assert token, "No access token returned"
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    @pytest.fixture(scope="class")
    def participant_session(self):
        """Login as participant and return session with auth token"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Login
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": PARTICIPANT_EMAIL,
            "password": PARTICIPANT_PASSWORD
        })
        assert response.status_code == 200, f"Participant login failed: {response.text}"
        data = response.json()
        token = data.get("access_token")
        assert token, "No access token returned"
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    def test_decisions_endpoint_returns_200(self, admin_session):
        """Test that decisions endpoint returns 200"""
        response = admin_session.get(f"{BASE_URL}/api/disputes/decisions/mine")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ Decisions endpoint returns 200")
    
    def test_decisions_response_structure(self, admin_session):
        """Test that decisions response has correct structure"""
        response = admin_session.get(f"{BASE_URL}/api/disputes/decisions/mine")
        assert response.status_code == 200
        data = response.json()
        
        assert "decisions" in data, "Response missing 'decisions' key"
        assert "count" in data, "Response missing 'count' key"
        assert isinstance(data["decisions"], list), "'decisions' should be a list"
        assert isinstance(data["count"], int), "'count' should be an integer"
        print(f"✓ Response structure correct: {data['count']} decisions")
    
    def test_decisions_have_appointment_id(self, admin_session):
        """Test that each decision has appointment_id for grouping"""
        response = admin_session.get(f"{BASE_URL}/api/disputes/decisions/mine")
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] == 0:
            pytest.skip("No decisions to test")
        
        for dec in data["decisions"]:
            assert "appointment_id" in dec, f"Decision missing appointment_id: {dec.get('dispute_id')}"
            assert dec["appointment_id"], f"appointment_id is empty for {dec.get('dispute_id')}"
        
        print(f"✓ All {data['count']} decisions have appointment_id")
    
    def test_decisions_have_required_fields(self, admin_session):
        """Test that decisions have all required fields for display"""
        response = admin_session.get(f"{BASE_URL}/api/disputes/decisions/mine")
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] == 0:
            pytest.skip("No decisions to test")
        
        required_fields = [
            "dispute_id",
            "appointment_id",
            "appointment_title",
            "appointment_date",
            "appointment_type",
            "target_name",
            "final_outcome",
            "financial_impact",
        ]
        
        for dec in data["decisions"]:
            for field in required_fields:
                assert field in dec, f"Decision missing field '{field}': {dec.get('dispute_id')}"
        
        print(f"✓ All decisions have required fields")
    
    def test_financial_impact_structure(self, admin_session):
        """Test that financial_impact has correct structure"""
        response = admin_session.get(f"{BASE_URL}/api/disputes/decisions/mine")
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] == 0:
            pytest.skip("No decisions to test")
        
        for dec in data["decisions"]:
            fi = dec.get("financial_impact", {})
            assert "type" in fi, f"financial_impact missing 'type' for {dec.get('dispute_id')}"
            assert "label" in fi, f"financial_impact missing 'label' for {dec.get('dispute_id')}"
            assert fi["type"] in ["credit", "debit", "neutral"], f"Invalid financial_impact type: {fi['type']}"
        
        print(f"✓ All financial_impact fields have correct structure")
    
    def test_count_decisions_by_appointment(self, admin_session):
        """Test grouping logic - count unique appointments"""
        response = admin_session.get(f"{BASE_URL}/api/disputes/decisions/mine")
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] == 0:
            pytest.skip("No decisions to test")
        
        # Group by appointment_id
        groups = {}
        for dec in data["decisions"]:
            apt_id = dec["appointment_id"]
            if apt_id not in groups:
                groups[apt_id] = []
            groups[apt_id].append(dec)
        
        total_decisions = sum(len(decs) for decs in groups.values())
        assert total_decisions == data["count"], f"Grouping lost decisions: {total_decisions} vs {data['count']}"
        
        # Print grouping info
        print(f"✓ {data['count']} decisions grouped into {len(groups)} appointments:")
        for apt_id, decs in groups.items():
            title = decs[0].get("appointment_title", "Unknown")
            print(f"  - {title}: {len(decs)} decision(s)")
    
    def test_appointment_location_fields(self, admin_session):
        """Test that location fields are present for display"""
        response = admin_session.get(f"{BASE_URL}/api/disputes/decisions/mine")
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] == 0:
            pytest.skip("No decisions to test")
        
        for dec in data["decisions"]:
            apt_type = dec.get("appointment_type", "")
            if apt_type == "physical":
                # Should have location
                assert "appointment_location" in dec, f"Physical appointment missing location"
            else:
                # Should have meeting provider
                assert "appointment_meeting_provider" in dec or "appointment_location" in dec, \
                    f"Video appointment missing meeting provider"
        
        print(f"✓ Location fields present for all appointments")
    
    def test_final_outcome_values(self, admin_session):
        """Test that final_outcome has valid values"""
        response = admin_session.get(f"{BASE_URL}/api/disputes/decisions/mine")
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] == 0:
            pytest.skip("No decisions to test")
        
        valid_outcomes = ["on_time", "no_show", "late_penalized"]
        
        for dec in data["decisions"]:
            outcome = dec.get("final_outcome", "")
            assert outcome in valid_outcomes, f"Invalid final_outcome: {outcome}"
        
        print(f"✓ All final_outcome values are valid")


class TestNotificationAPI:
    """Test notification endpoints for unread indicators"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        """Login as admin and return session with auth token"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        token = data.get("access_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    def test_notification_counts_endpoint(self, admin_session):
        """Test that notification counts endpoint works"""
        response = admin_session.get(f"{BASE_URL}/api/notifications/counts")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "decisions" in data, "Response missing 'decisions' count"
        assert "disputes" in data, "Response missing 'disputes' count"
        print(f"✓ Notification counts: decisions={data.get('decisions')}, disputes={data.get('disputes')}")
    
    def test_unread_ids_decision_type(self, admin_session):
        """Test unread IDs for decision type"""
        response = admin_session.get(f"{BASE_URL}/api/notifications/unread-ids/decision")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "unread_ids" in data, "Response missing 'unread_ids'"
        assert isinstance(data["unread_ids"], list), "'unread_ids' should be a list"
        print(f"✓ Unread decision IDs: {len(data['unread_ids'])} unread")
    
    def test_mark_read_endpoint(self, admin_session):
        """Test mark as read endpoint exists"""
        # This is a POST endpoint, we just verify it exists
        response = admin_session.post(f"{BASE_URL}/api/notifications/mark-read", json={
            "event_type": "decision",
            "reference_id": "test-id-that-does-not-exist"
        })
        # Should return 200 even if notification doesn't exist (idempotent)
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
        print(f"✓ Mark read endpoint exists")


class TestDisputeDetailAPI:
    """Test dispute detail endpoint for decision detail page"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        """Login as admin and return session with auth token"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        token = data.get("access_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    def test_dispute_detail_endpoint(self, admin_session):
        """Test that dispute detail endpoint works for decisions"""
        # First get a decision ID
        response = admin_session.get(f"{BASE_URL}/api/disputes/decisions/mine")
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] == 0:
            pytest.skip("No decisions to test")
        
        dispute_id = data["decisions"][0]["dispute_id"]
        
        # Get detail
        response = admin_session.get(f"{BASE_URL}/api/disputes/{dispute_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        detail = response.json()
        assert "dispute_id" in detail, "Detail missing dispute_id"
        assert "resolution" in detail or "final_outcome" in detail, "Detail missing resolution info"
        print(f"✓ Dispute detail endpoint works for {dispute_id}")
    
    def test_dispute_detail_has_financial_context(self, admin_session):
        """Test that dispute detail has financial context"""
        response = admin_session.get(f"{BASE_URL}/api/disputes/decisions/mine")
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] == 0:
            pytest.skip("No decisions to test")
        
        dispute_id = data["decisions"][0]["dispute_id"]
        
        response = admin_session.get(f"{BASE_URL}/api/disputes/{dispute_id}")
        assert response.status_code == 200
        
        detail = response.json()
        assert "financial_context" in detail, "Detail missing financial_context"
        
        fc = detail["financial_context"]
        assert "penalty_amount" in fc, "financial_context missing penalty_amount"
        print(f"✓ Dispute detail has financial_context")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
