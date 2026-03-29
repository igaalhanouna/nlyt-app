"""
Test Disputes UX Refonte - Iteration 129

Tests for the new disputes list page UX with:
- Backend enrichment: appointment_type, appointment_location, appointment_meeting_provider, appointment_duration_minutes
- Frontend grouping by appointment_id
- Global status badges
- Resolved disputes filtering
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
TEST_USER_EMAIL = "igaal@hotmail.com"
TEST_USER_PASSWORD = "Test123!"


class TestDisputesUXRefonte:
    """Tests for disputes UX refonte - backend API enrichment"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.token = None
        
    def _login(self, email=TEST_USER_EMAIL, password=TEST_USER_PASSWORD):
        """Login and get access token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": password
        })
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            return True
        return False
    
    def test_01_health_check(self):
        """Test API is accessible"""
        response = self.session.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        print("PASS: API health check")
    
    def test_02_login_success(self):
        """Test login with test user credentials"""
        result = self._login()
        assert result, "Login failed"
        assert self.token is not None, "No access token received"
        print(f"PASS: Login successful, token received")
    
    def test_03_disputes_mine_returns_new_fields(self):
        """Test GET /api/disputes/mine returns new appointment enrichment fields"""
        assert self._login(), "Login required"
        
        response = self.session.get(f"{BASE_URL}/api/disputes/mine")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        disputes = data.get("disputes", [])
        count = data.get("count", 0)
        
        print(f"Found {count} disputes for user {TEST_USER_EMAIL}")
        
        # Should have at least 1 dispute
        assert len(disputes) > 0, "Expected at least 1 dispute"
        
        # Check first dispute has new fields
        d = disputes[0]
        
        # Required fields from enrichment
        assert "appointment_id" in d, "Missing appointment_id"
        assert "appointment_title" in d, "Missing appointment_title"
        assert "appointment_date" in d, "Missing appointment_date"
        
        # New enrichment fields
        assert "appointment_type" in d, "Missing appointment_type (new field)"
        assert "appointment_location" in d, "Missing appointment_location (new field)"
        assert "appointment_meeting_provider" in d, "Missing appointment_meeting_provider (new field)"
        assert "appointment_duration_minutes" in d, "Missing appointment_duration_minutes (new field)"
        
        print(f"PASS: Dispute has all new enrichment fields")
        print(f"  - appointment_type: {d.get('appointment_type')}")
        print(f"  - appointment_location: {d.get('appointment_location')}")
        print(f"  - appointment_meeting_provider: {d.get('appointment_meeting_provider')}")
        print(f"  - appointment_duration_minutes: {d.get('appointment_duration_minutes')}")
        
        # Check computed fields
        assert "display_state" in d, "Missing display_state"
        assert "can_submit_position" in d, "Missing can_submit_position"
        assert "target_name" in d, "Missing target_name"
        
        print(f"PASS: Dispute has computed fields (display_state={d.get('display_state')}, can_submit_position={d.get('can_submit_position')})")
    
    def test_04_disputes_mine_has_multiple_disputes(self):
        """Test that user has expected number of disputes (4 total, 2 active)"""
        assert self._login(), "Login required"
        
        response = self.session.get(f"{BASE_URL}/api/disputes/mine")
        assert response.status_code == 200
        
        data = response.json()
        disputes = data.get("disputes", [])
        
        # Actual data: 4 disputes total, 2 resolved, 2 active (both in arbitration)
        # The API returns all disputes, frontend filters resolved
        print(f"Total disputes returned: {len(disputes)}")
        
        # Count by display_state
        resolved_count = sum(1 for d in disputes if d.get("display_state") == "resolved")
        active_count = sum(1 for d in disputes if d.get("display_state") != "resolved")
        
        print(f"  - Resolved: {resolved_count}")
        print(f"  - Active: {active_count}")
        
        # Should have at least 2 active disputes
        assert active_count >= 2, f"Expected at least 2 active disputes, got {active_count}"
        print(f"PASS: User has {active_count} active disputes")
    
    def test_05_disputes_grouped_by_appointment(self):
        """Test that disputes can be grouped by appointment_id (2 disputes for same RDV)"""
        assert self._login(), "Login required"
        
        response = self.session.get(f"{BASE_URL}/api/disputes/mine")
        assert response.status_code == 200
        
        data = response.json()
        disputes = data.get("disputes", [])
        
        # Group by appointment_id
        groups = {}
        for d in disputes:
            apt_id = d.get("appointment_id")
            if apt_id not in groups:
                groups[apt_id] = []
            groups[apt_id].append(d)
        
        print(f"Disputes grouped into {len(groups)} appointments:")
        for apt_id, apt_disputes in groups.items():
            apt_title = apt_disputes[0].get("appointment_title", "Unknown")
            print(f"  - {apt_title}: {len(apt_disputes)} dispute(s)")
        
        # According to context: 'test dispute' appointment has 2 disputes
        multi_dispute_groups = [g for g in groups.values() if len(g) > 1]
        print(f"Groups with multiple disputes: {len(multi_dispute_groups)}")
        
        # At least one group should have multiple disputes
        assert len(multi_dispute_groups) >= 1, "Expected at least one appointment with multiple disputes"
        print(f"PASS: Found {len(multi_dispute_groups)} appointment(s) with multiple disputes")
    
    def test_06_dispute_detail_returns_new_fields(self):
        """Test GET /api/disputes/{id} returns new appointment enrichment fields"""
        assert self._login(), "Login required"
        
        # First get list to find a dispute_id
        response = self.session.get(f"{BASE_URL}/api/disputes/mine")
        assert response.status_code == 200
        
        disputes = response.json().get("disputes", [])
        assert len(disputes) > 0, "No disputes found"
        
        dispute_id = disputes[0].get("dispute_id")
        assert dispute_id, "No dispute_id in first dispute"
        
        # Get detail
        response = self.session.get(f"{BASE_URL}/api/disputes/{dispute_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        d = response.json()
        
        # Check new enrichment fields
        assert "appointment_id" in d, "Missing appointment_id"
        assert "appointment_type" in d, "Missing appointment_type (new field)"
        assert "appointment_location" in d, "Missing appointment_location (new field)"
        assert "appointment_meeting_provider" in d, "Missing appointment_meeting_provider (new field)"
        assert "appointment_duration_minutes" in d, "Missing appointment_duration_minutes (new field)"
        
        print(f"PASS: Dispute detail has all new enrichment fields")
        print(f"  - appointment_id: {d.get('appointment_id')}")
        print(f"  - appointment_type: {d.get('appointment_type')}")
        print(f"  - appointment_location: {d.get('appointment_location')}")
        print(f"  - appointment_meeting_provider: {d.get('appointment_meeting_provider')}")
        print(f"  - appointment_duration_minutes: {d.get('appointment_duration_minutes')}")
    
    def test_07_dispute_detail_has_appointment_id_for_link(self):
        """Test dispute detail has appointment_id for 'Voir le rendez-vous' link"""
        assert self._login(), "Login required"
        
        # Get list to find a dispute_id
        response = self.session.get(f"{BASE_URL}/api/disputes/mine")
        assert response.status_code == 200
        
        disputes = response.json().get("disputes", [])
        assert len(disputes) > 0, "No disputes found"
        
        dispute_id = disputes[0].get("dispute_id")
        
        # Get detail
        response = self.session.get(f"{BASE_URL}/api/disputes/{dispute_id}")
        assert response.status_code == 200
        
        d = response.json()
        
        # appointment_id is required for the link
        assert "appointment_id" in d, "Missing appointment_id for link navigation"
        assert d.get("appointment_id"), "appointment_id is empty"
        
        print(f"PASS: Dispute detail has appointment_id for link: {d.get('appointment_id')}")
    
    def test_08_disputes_have_display_state_for_filtering(self):
        """Test disputes have display_state field for frontend filtering"""
        assert self._login(), "Login required"
        
        response = self.session.get(f"{BASE_URL}/api/disputes/mine")
        assert response.status_code == 200
        
        disputes = response.json().get("disputes", [])
        
        # All disputes should have display_state
        for d in disputes:
            assert "display_state" in d, f"Missing display_state in dispute {d.get('dispute_id')}"
        
        # Check display_state values
        states = set(d.get("display_state") for d in disputes)
        print(f"Display states found: {states}")
        
        # Valid states: waiting_both, waiting_other, arbitration, resolved
        valid_states = {"waiting_both", "waiting_other", "arbitration", "resolved"}
        for state in states:
            assert state in valid_states, f"Invalid display_state: {state}"
        
        print(f"PASS: All disputes have valid display_state")
    
    def test_09_disputes_have_can_submit_position_for_global_status(self):
        """Test disputes have can_submit_position for global status calculation"""
        assert self._login(), "Login required"
        
        response = self.session.get(f"{BASE_URL}/api/disputes/mine")
        assert response.status_code == 200
        
        disputes = response.json().get("disputes", [])
        
        # All disputes should have can_submit_position
        for d in disputes:
            assert "can_submit_position" in d, f"Missing can_submit_position in dispute {d.get('dispute_id')}"
        
        # Count disputes where action is needed
        action_needed = sum(1 for d in disputes if d.get("can_submit_position"))
        print(f"Disputes requiring action: {action_needed}")
        
        print(f"PASS: All disputes have can_submit_position field")
    
    def test_10_disputes_have_target_name_for_sub_cards(self):
        """Test disputes have target_name for sub-card display"""
        assert self._login(), "Login required"
        
        response = self.session.get(f"{BASE_URL}/api/disputes/mine")
        assert response.status_code == 200
        
        disputes = response.json().get("disputes", [])
        
        # All disputes should have target_name
        for d in disputes:
            assert "target_name" in d, f"Missing target_name in dispute {d.get('dispute_id')}"
            print(f"  - Dispute {d.get('dispute_id')}: target_name='{d.get('target_name')}'")
        
        print(f"PASS: All disputes have target_name field")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
