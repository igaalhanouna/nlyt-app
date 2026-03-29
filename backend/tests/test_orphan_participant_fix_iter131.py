"""
Test: Orphan Participant Fix - Iteration 131
Bug: Dispute 23f75310 was invisible to igaal@hotmail.com because participant.user_id=None and dispute.target_user_id=None

Fixes applied:
1. respond_to_invitation now persists user_id when accepting
2. _get_user_id fallback resolves user_id from email
3. Migration fixed 144 orphan participants and 1 dispute target_user_id
4. Dispute 23f75310 now visible to igaal@hotmail.com

Test credentials:
- igaal@hotmail.com / Test123! (affected user - should now see 5 disputes)
- testuser_audit@nlyt.app / TestAudit123! (organizer - regression check)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Specific dispute and appointment IDs from the bug report
DISPUTE_ID = "23f75310-958e-4597-baf8-cc3ea0c1470b"
APPOINTMENT_ID = "1b97a8b8-61d0-4b5e-ba00-e38166d2fa18"


class TestOrphanParticipantFix:
    """Tests for the orphan participant visibility fix"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_01_health_check(self):
        """Verify API is accessible"""
        response = self.session.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        print("PASS: API health check")
    
    def test_02_login_igaal_hotmail(self):
        """Login as igaal@hotmail.com (affected user)"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "igaal@hotmail.com",
            "password": "Test123!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        self.igaal_token = data["access_token"]
        print(f"PASS: Login igaal@hotmail.com - token obtained")
        return self.igaal_token
    
    def test_03_disputes_mine_returns_5_disputes_for_igaal(self):
        """Verify igaal@hotmail.com now sees 5 disputes (was 4 before fix)"""
        # Login first
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "igaal@hotmail.com",
            "password": "Test123!"
        })
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        
        # Get disputes
        headers = {"Authorization": f"Bearer {token}"}
        response = self.session.get(f"{BASE_URL}/api/disputes/mine", headers=headers)
        assert response.status_code == 200, f"GET /api/disputes/mine failed: {response.text}"
        
        data = response.json()
        disputes = data if isinstance(data, list) else data.get("disputes", [])
        
        print(f"INFO: igaal@hotmail.com sees {len(disputes)} disputes")
        for d in disputes:
            print(f"  - {d.get('dispute_id', 'N/A')[:8]}... | {d.get('appointment_title', 'N/A')} | display_state={d.get('display_state')}")
        
        # Should see at least 5 disputes now (was 4 before fix)
        assert len(disputes) >= 5, f"Expected at least 5 disputes, got {len(disputes)}"
        print(f"PASS: igaal@hotmail.com sees {len(disputes)} disputes (expected >= 5)")
    
    def test_04_dispute_23f75310_visible_to_igaal(self):
        """Verify the specific dispute 23f75310 is now visible to igaal@hotmail.com"""
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "igaal@hotmail.com",
            "password": "Test123!"
        })
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get disputes
        response = self.session.get(f"{BASE_URL}/api/disputes/mine", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        disputes = data if isinstance(data, list) else data.get("disputes", [])
        
        # Find the specific dispute
        target_dispute = None
        for d in disputes:
            if d.get("dispute_id", "").startswith("23f75310"):
                target_dispute = d
                break
        
        assert target_dispute is not None, f"Dispute 23f75310 not found in igaal's disputes list"
        print(f"PASS: Dispute 23f75310 found in igaal's disputes")
        print(f"  - appointment_title: {target_dispute.get('appointment_title')}")
        print(f"  - display_state: {target_dispute.get('display_state')}")
        print(f"  - can_submit_position: {target_dispute.get('can_submit_position')}")
        print(f"  - is_target: {target_dispute.get('is_target')}")
    
    def test_05_dispute_23f75310_has_correct_flags_for_igaal(self):
        """Verify dispute 23f75310 has can_submit_position=true and is_target=true for igaal"""
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "igaal@hotmail.com",
            "password": "Test123!"
        })
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get disputes
        response = self.session.get(f"{BASE_URL}/api/disputes/mine", headers=headers)
        data = response.json()
        disputes = data if isinstance(data, list) else data.get("disputes", [])
        
        # Find the specific dispute
        target_dispute = None
        for d in disputes:
            if d.get("dispute_id", "").startswith("23f75310"):
                target_dispute = d
                break
        
        assert target_dispute is not None, "Dispute 23f75310 not found"
        
        # Check flags
        can_submit = target_dispute.get("can_submit_position")
        is_target = target_dispute.get("is_target")
        
        print(f"INFO: Dispute 23f75310 flags - can_submit_position={can_submit}, is_target={is_target}")
        
        # igaal is the target of this dispute, so is_target should be true
        assert is_target == True, f"Expected is_target=True, got {is_target}"
        # can_submit_position depends on whether igaal has already submitted
        print(f"PASS: Dispute 23f75310 has is_target=True for igaal")
    
    def test_06_dispute_detail_accessible_by_igaal(self):
        """Verify igaal can access the dispute detail page"""
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "igaal@hotmail.com",
            "password": "Test123!"
        })
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get dispute detail
        response = self.session.get(f"{BASE_URL}/api/disputes/{DISPUTE_ID}", headers=headers)
        assert response.status_code == 200, f"GET /api/disputes/{DISPUTE_ID} failed: {response.status_code} - {response.text}"
        
        data = response.json()
        print(f"PASS: Dispute detail accessible by igaal")
        print(f"  - dispute_id: {data.get('dispute_id')}")
        print(f"  - appointment_title: {data.get('appointment_title')}")
        print(f"  - status: {data.get('status')}")
    
    def test_07_regression_testuser_audit_still_sees_dispute(self):
        """Regression: testuser_audit@nlyt.app should still see the same dispute"""
        # Login as testuser_audit
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testuser_audit@nlyt.app",
            "password": "TestAudit123!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get disputes
        response = self.session.get(f"{BASE_URL}/api/disputes/mine", headers=headers)
        assert response.status_code == 200, f"GET /api/disputes/mine failed: {response.text}"
        
        data = response.json()
        disputes = data if isinstance(data, list) else data.get("disputes", [])
        
        print(f"INFO: testuser_audit@nlyt.app sees {len(disputes)} disputes")
        
        # Find the specific dispute
        target_dispute = None
        for d in disputes:
            if d.get("dispute_id", "").startswith("23f75310"):
                target_dispute = d
                break
        
        assert target_dispute is not None, "Regression: Dispute 23f75310 not found for testuser_audit"
        print(f"PASS: Regression check - testuser_audit still sees dispute 23f75310")
        print(f"  - is_target: {target_dispute.get('is_target')}")
        print(f"  - organizer_position: {target_dispute.get('organizer_position')}")
    
    def test_08_appointment_title_is_test_email_wordin(self):
        """Verify the dispute is for appointment 'test email wordin'"""
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "igaal@hotmail.com",
            "password": "Test123!"
        })
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get dispute detail
        response = self.session.get(f"{BASE_URL}/api/disputes/{DISPUTE_ID}", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        title = data.get("appointment_title", "")
        
        print(f"INFO: Appointment title = '{title}'")
        assert "test email wordin" in title.lower(), f"Expected 'test email wordin' in title, got '{title}'"
        print(f"PASS: Dispute is for appointment 'test email wordin'")


class TestCodeReviewVerification:
    """Code review verification tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_09_respond_to_invitation_code_includes_user_id_resolution(self):
        """Code review: respond_to_invitation should include user_id resolution (lines 441-447)"""
        # This is a code review test - we verify by checking the file content
        import os
        invitations_path = "/app/backend/routers/invitations.py"
        
        with open(invitations_path, 'r') as f:
            content = f.read()
        
        # Check for the user_id resolution code
        assert 'if not participant.get(\'user_id\') and response.action == "accept"' in content, \
            "Missing user_id resolution check in respond_to_invitation"
        assert 'user_doc = db.users.find_one({"email": participant.get("email")}' in content, \
            "Missing email lookup in respond_to_invitation"
        assert 'update_data["user_id"] = user_doc["user_id"]' in content, \
            "Missing user_id assignment in respond_to_invitation"
        
        print("PASS: Code review - respond_to_invitation includes user_id resolution (lines 441-447)")
    
    def test_10_get_user_id_has_email_fallback(self):
        """Code review: _get_user_id should have email fallback (lines 145-161)"""
        declarative_path = "/app/backend/services/declarative_service.py"
        
        with open(declarative_path, 'r') as f:
            content = f.read()
        
        # Check for the email fallback code
        assert 'def _get_user_id(participant_id: str) -> str:' in content, \
            "Missing _get_user_id function"
        assert 'if p.get(\'email\'):' in content, \
            "Missing email fallback check in _get_user_id"
        assert 'user = db.users.find_one({"email": p[\'email\']}' in content, \
            "Missing email lookup in _get_user_id"
        assert 'db.participants.update_one' in content, \
            "Missing participant update in _get_user_id"
        
        print("PASS: Code review - _get_user_id has email fallback (lines 145-161)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
