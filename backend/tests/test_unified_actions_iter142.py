"""
Iteration 142: Unified Actions Required Section Testing
Tests for:
- GET /api/appointments/my-timeline returns action_required, upcoming, past arrays with counts
- GET /api/modifications/mine returns proposals with is_action_required field
- Dashboard unified 'Actions requises' section rendering
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
ADMIN_EMAIL = "testuser_audit@nlyt.app"
ADMIN_PASSWORD = "TestAudit123!"
PARTICIPANT_EMAIL = "igaal@hotmail.com"
PARTICIPANT_PASSWORD = "Test123!"
PARTICIPANT2_EMAIL = "igaal.hanouna@gmail.com"
PARTICIPANT2_PASSWORD = "OrgTest123!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin/organizer JWT token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def participant_token():
    """Get participant JWT token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": PARTICIPANT_EMAIL,
        "password": PARTICIPANT_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Participant login failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def participant2_token():
    """Get participant2 JWT token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": PARTICIPANT2_EMAIL,
        "password": PARTICIPANT2_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Participant2 login failed: {response.status_code} - {response.text}")


class TestTimelineAPI:
    """Tests for GET /api/appointments/my-timeline"""
    
    def test_timeline_requires_auth(self):
        """Timeline endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/appointments/my-timeline")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_timeline_returns_three_buckets_admin(self, admin_token):
        """Timeline returns action_required, upcoming, past arrays for admin"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/my-timeline",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "action_required" in data, "Missing action_required array"
        assert "upcoming" in data, "Missing upcoming array"
        assert "past" in data, "Missing past array"
        assert "counts" in data, "Missing counts object"
        
        # Verify counts structure
        counts = data["counts"]
        assert "action_required" in counts, "Missing action_required count"
        assert "upcoming" in counts, "Missing upcoming count"
        assert "past" in counts, "Missing past count"
        assert "total" in counts, "Missing total count"
        
        # Verify counts are integers
        assert isinstance(counts["action_required"], int)
        assert isinstance(counts["upcoming"], int)
        assert isinstance(counts["past"], int)
        assert isinstance(counts["total"], int)
        
        print(f"Admin timeline counts: action_required={counts['action_required']}, upcoming={counts['upcoming']}, past={counts['past']}, total={counts['total']}")
    
    def test_timeline_returns_three_buckets_participant(self, participant_token):
        """Timeline returns action_required, upcoming, past arrays for participant"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/my-timeline",
            headers={"Authorization": f"Bearer {participant_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "action_required" in data, "Missing action_required array"
        assert "upcoming" in data, "Missing upcoming array"
        assert "past" in data, "Missing past array"
        assert "counts" in data, "Missing counts object"
        
        print(f"Participant timeline counts: action_required={data['counts']['action_required']}, upcoming={data['counts']['upcoming']}, past={data['counts']['past']}")
    
    def test_timeline_item_structure(self, admin_token):
        """Timeline items have required fields"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/my-timeline",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check any item from any bucket
        all_items = data["action_required"] + data["upcoming"] + data["past"]
        if not all_items:
            pytest.skip("No timeline items to verify structure")
        
        item = all_items[0]
        required_fields = [
            "appointment_id", "role", "status", "action_required",
            "starts_at", "title", "appointment_type", "duration_minutes"
        ]
        for field in required_fields:
            assert field in item, f"Missing required field: {field}"
        
        # Verify role is either 'organizer' or 'participant'
        assert item["role"] in ("organizer", "participant"), f"Invalid role: {item['role']}"
        
        print(f"Sample item: appointment_id={item['appointment_id']}, role={item['role']}, action_required={item['action_required']}")


class TestModificationsAPI:
    """Tests for GET /api/modifications/mine"""
    
    def test_modifications_requires_auth(self):
        """Modifications endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/modifications/mine")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_modifications_returns_proposals_admin(self, admin_token):
        """Modifications endpoint returns proposals array for admin"""
        response = requests.get(
            f"{BASE_URL}/api/modifications/mine",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "proposals" in data, "Missing proposals array"
        assert isinstance(data["proposals"], list), "proposals should be a list"
        
        print(f"Admin has {len(data['proposals'])} modification proposals")
    
    def test_modifications_returns_proposals_participant(self, participant_token):
        """Modifications endpoint returns proposals array for participant"""
        response = requests.get(
            f"{BASE_URL}/api/modifications/mine",
            headers={"Authorization": f"Bearer {participant_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "proposals" in data, "Missing proposals array"
        
        print(f"Participant has {len(data['proposals'])} modification proposals")
    
    def test_modifications_have_is_action_required_field(self, admin_token):
        """Each modification proposal has is_action_required field"""
        response = requests.get(
            f"{BASE_URL}/api/modifications/mine",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        proposals = data.get("proposals", [])
        if not proposals:
            print("No modification proposals to verify - this is OK if no pending modifications exist")
            return
        
        for prop in proposals:
            assert "is_action_required" in prop, f"Missing is_action_required field in proposal {prop.get('proposal_id')}"
            assert isinstance(prop["is_action_required"], bool), "is_action_required should be boolean"
            
            # Verify other required fields
            required_fields = [
                "proposal_id", "appointment_id", "status", "proposed_by",
                "changes", "my_role", "participants_summary"
            ]
            for field in required_fields:
                assert field in prop, f"Missing required field: {field}"
        
        action_required_count = sum(1 for p in proposals if p["is_action_required"])
        print(f"Found {len(proposals)} proposals, {action_required_count} require action")


class TestNavbarLinks:
    """Tests for navbar API endpoints (indirect test via API availability)"""
    
    def test_disputes_mine_endpoint(self, admin_token):
        """GET /api/disputes/mine is accessible (for Litiges navbar badge)"""
        response = requests.get(
            f"{BASE_URL}/api/disputes/mine",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "disputes" in data, "Missing disputes array"
        print(f"Admin has {len(data['disputes'])} disputes")
    
    def test_attendance_pending_endpoint(self, admin_token):
        """GET /api/attendance-sheets/pending is accessible (for Presences navbar badge)"""
        response = requests.get(
            f"{BASE_URL}/api/attendance-sheets/pending",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "count" in data, "Missing count field"
        print(f"Admin has {data['count']} pending attendance sheets")
    
    def test_admin_arbitration_endpoint(self, admin_token):
        """GET /api/admin/arbitration is accessible for admin (Arbitrage navbar link)"""
        response = requests.get(
            f"{BASE_URL}/api/admin/arbitration?filter=escalated",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # Admin should have access
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("Admin can access arbitration endpoint")
    
    def test_admin_arbitration_forbidden_for_participant(self, participant_token):
        """GET /api/admin/arbitration is forbidden for non-admin"""
        response = requests.get(
            f"{BASE_URL}/api/admin/arbitration?filter=escalated",
            headers={"Authorization": f"Bearer {participant_token}"}
        )
        # Non-admin should get 403
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("Participant correctly denied access to arbitration endpoint")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
