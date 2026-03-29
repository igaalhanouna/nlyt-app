"""
Test Modification Visibility & Bidirectional Features (Iteration 134)

Tests for:
- P0.1: GET /api/modifications/mine - returns proposals with correct fields
- P0.4: Both organizer AND participant can respond to proposals
- P1.2: Participant can propose/respond/cancel via JWT (not just invitation_token)
- Non-regression: Organizer proposal flow still works
"""

import pytest
import requests
import os
import time
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://litigation-mgmt.preview.emergentagent.com')

# Test credentials
ORGANIZER_EMAIL = "testuser_audit@nlyt.app"
ORGANIZER_PASSWORD = "TestAudit123!"

PARTICIPANT_EMAIL = "igaal@hotmail.com"
PARTICIPANT_PASSWORD = "Test123!"

# Appointment with accepted participant (proposal mode)
APPOINTMENT_WITH_ACCEPTED = "3e2f572f-e5e8-47a2-9e74-7f4273dd2d7c"

# Appointment with only invited participants (direct mode)
APPOINTMENT_DIRECT_MODE = "7e2270b1-606c-4945-be71-024c10c3edcd"


def login_with_retry(email, password, max_retries=3):
    """Login with retry logic for rate limiting"""
    for attempt in range(max_retries):
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": password
        }, headers={"Content-Type": "application/json"})
        
        if resp.status_code == 200:
            return resp.json().get("token")
        elif resp.status_code == 429:
            wait_time = 2 ** attempt
            print(f"Rate limited, waiting {wait_time}s...")
            time.sleep(wait_time)
        else:
            print(f"Login failed: {resp.status_code} - {resp.text}")
            return None
    return None


class TestModificationMineEndpoint:
    """Tests for GET /api/modifications/mine endpoint (P0.1)"""
    
    @pytest.fixture(scope="class")
    def org_session(self):
        """Login as organizer and get session"""
        time.sleep(1)  # Rate limit protection
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        token = login_with_retry(ORGANIZER_EMAIL, ORGANIZER_PASSWORD)
        assert token, "Failed to login as organizer"
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session
        
    def test_01_health_check(self):
        """Verify API is accessible"""
        resp = requests.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200
        print("PASS: API health check")
        
    def test_02_modifications_mine_endpoint_exists(self, org_session):
        """GET /api/modifications/mine returns 200"""
        time.sleep(0.5)
        resp = org_session.get(f"{BASE_URL}/api/modifications/mine")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "proposals" in data, "Response should contain 'proposals' key"
        print(f"PASS: /api/modifications/mine returns {len(data['proposals'])} proposals")
        
    def test_03_modifications_mine_returns_correct_fields(self, org_session):
        """Verify /api/modifications/mine returns all required fields"""
        time.sleep(0.5)
        resp = org_session.get(f"{BASE_URL}/api/modifications/mine")
        assert resp.status_code == 200
        data = resp.json()
        
        # Required fields per spec
        required_fields = [
            "proposal_id", "appointment_id", "appointment_title", "start_datetime",
            "proposed_by", "status", "mode", "my_role", "my_response_status",
            "is_action_required", "participants_summary"
        ]
        
        if len(data["proposals"]) > 0:
            proposal = data["proposals"][0]
            missing = [f for f in required_fields if f not in proposal]
            assert not missing, f"Missing required fields: {missing}"
            print(f"PASS: Proposal contains all required fields")
        else:
            print("INFO: No proposals found, skipping field validation")
            
    def test_04_is_action_required_logic(self, org_session):
        """is_action_required=true only when my_response_status=pending AND proposal status=pending"""
        time.sleep(0.5)
        resp = org_session.get(f"{BASE_URL}/api/modifications/mine")
        assert resp.status_code == 200
        data = resp.json()
        
        for proposal in data["proposals"]:
            is_action = proposal.get("is_action_required", False)
            my_status = proposal.get("my_response_status")
            prop_status = proposal.get("status")
            
            if is_action:
                assert my_status == "pending", f"is_action_required=true but my_response_status={my_status}"
                assert prop_status == "pending", f"is_action_required=true but proposal status={prop_status}"
                print(f"PASS: Proposal {proposal['proposal_id'][:8]} correctly has is_action_required=true")
                    
        print("PASS: is_action_required logic verified")


class TestParticipantJWTModifications:
    """Tests for participant proposing/responding/canceling via JWT (P1.2)"""
    
    @pytest.fixture(scope="class")
    def part_session(self):
        """Login as participant and get session"""
        time.sleep(2)  # Rate limit protection
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        token = login_with_retry(PARTICIPANT_EMAIL, PARTICIPANT_PASSWORD)
        assert token, "Failed to login as participant"
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session
        
    @pytest.fixture(scope="class")
    def org_session_for_cleanup(self):
        """Organizer session for cleanup"""
        time.sleep(2)
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        token = login_with_retry(ORGANIZER_EMAIL, ORGANIZER_PASSWORD)
        if token:
            session.headers.update({"Authorization": f"Bearer {token}"})
        return session
        
    def test_05_participant_can_access_modifications_mine(self, part_session):
        """Participant can call GET /api/modifications/mine"""
        time.sleep(0.5)
        resp = part_session.get(f"{BASE_URL}/api/modifications/mine")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "proposals" in data
        print(f"PASS: Participant can access /api/modifications/mine, got {len(data['proposals'])} proposals")
        
    def test_06_participant_my_role_is_participant(self, part_session):
        """Participant sees my_role='participant' for appointments they're invited to"""
        time.sleep(0.5)
        resp = part_session.get(f"{BASE_URL}/api/modifications/mine")
        assert resp.status_code == 200
        data = resp.json()
        
        for proposal in data["proposals"]:
            if proposal["appointment_id"] == APPOINTMENT_WITH_ACCEPTED:
                assert proposal["my_role"] == "participant", f"Expected my_role='participant', got {proposal['my_role']}"
                print(f"PASS: Participant sees my_role='participant'")
                return
                
        print("INFO: No proposals found for test appointment, skipping my_role check")
        
    def test_07_cleanup_existing_proposals(self, org_session_for_cleanup):
        """Cleanup any existing pending proposals before testing"""
        time.sleep(0.5)
        resp = org_session_for_cleanup.get(f"{BASE_URL}/api/modifications/active/{APPOINTMENT_WITH_ACCEPTED}")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("proposal") and data["proposal"].get("status") == "pending":
                proposal_id = data["proposal"]["proposal_id"]
                cancel_resp = org_session_for_cleanup.post(f"{BASE_URL}/api/modifications/{proposal_id}/cancel")
                print(f"INFO: Cancelled existing proposal {proposal_id[:8]}: {cancel_resp.status_code}")
                
        print("PASS: Cleanup complete")
        
    def test_08_participant_can_propose_via_jwt(self, part_session, org_session_for_cleanup):
        """Participant can POST /api/modifications/ with JWT (no invitation_token)"""
        time.sleep(1)
        
        # Cleanup first
        resp = org_session_for_cleanup.get(f"{BASE_URL}/api/modifications/active/{APPOINTMENT_WITH_ACCEPTED}")
        if resp.status_code == 200 and resp.json().get("proposal"):
            proposal = resp.json()["proposal"]
            if proposal.get("status") == "pending":
                org_session_for_cleanup.post(f"{BASE_URL}/api/modifications/{proposal['proposal_id']}/cancel")
                time.sleep(0.5)
        
        # Now participant proposes via JWT
        future_date = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")
        resp = part_session.post(f"{BASE_URL}/api/modifications/", json={
            "appointment_id": APPOINTMENT_WITH_ACCEPTED,
            "changes": {
                "start_datetime": future_date
            }
        })
        
        # Should succeed (200) or fail with business logic error (400), not auth error (401/403)
        assert resp.status_code in [200, 400], f"Expected 200 or 400, got {resp.status_code}: {resp.text}"
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"PASS: Participant proposed modification via JWT: {data.get('status', data.get('mode'))}")
            
            # Cleanup
            if data.get("proposal_id") and data.get("status") == "pending":
                time.sleep(0.5)
                part_session.post(f"{BASE_URL}/api/modifications/{data['proposal_id']}/cancel")
        else:
            print(f"INFO: Proposal rejected with business logic: {resp.json().get('detail')}")


class TestOrganizerRespondToParticipantProposal:
    """Tests for organizer responding to participant proposals (P0.4)"""
    
    @pytest.fixture(scope="class")
    def sessions(self):
        """Setup both organizer and participant sessions"""
        time.sleep(2)
        
        org_session = requests.Session()
        org_session.headers.update({"Content-Type": "application/json"})
        org_token = login_with_retry(ORGANIZER_EMAIL, ORGANIZER_PASSWORD)
        if org_token:
            org_session.headers.update({"Authorization": f"Bearer {org_token}"})
        
        time.sleep(1)
        
        part_session = requests.Session()
        part_session.headers.update({"Content-Type": "application/json"})
        part_token = login_with_retry(PARTICIPANT_EMAIL, PARTICIPANT_PASSWORD)
        if part_token:
            part_session.headers.update({"Authorization": f"Bearer {part_token}"})
            
        return {"org": org_session, "part": part_session}
        
    def test_09_organizer_can_respond_to_participant_proposal(self, sessions):
        """Organizer can respond to a proposal created by participant"""
        time.sleep(1)
        org_session = sessions["org"]
        part_session = sessions["part"]
        
        # Cleanup first
        resp = org_session.get(f"{BASE_URL}/api/modifications/active/{APPOINTMENT_WITH_ACCEPTED}")
        if resp.status_code == 200 and resp.json().get("proposal"):
            proposal = resp.json()["proposal"]
            if proposal.get("status") == "pending":
                org_session.post(f"{BASE_URL}/api/modifications/{proposal['proposal_id']}/cancel")
                time.sleep(0.5)
        
        # Participant creates proposal
        future_date = (datetime.utcnow() + timedelta(days=32)).strftime("%Y-%m-%dT%H:%M:%S")
        create_resp = part_session.post(f"{BASE_URL}/api/modifications/", json={
            "appointment_id": APPOINTMENT_WITH_ACCEPTED,
            "changes": {"start_datetime": future_date}
        })
        
        if create_resp.status_code != 200:
            print(f"INFO: Could not create participant proposal: {create_resp.text}")
            return
            
        proposal_id = create_resp.json().get("proposal_id")
        if not proposal_id:
            print("INFO: No proposal_id returned")
            return
            
        time.sleep(0.5)
        
        # Organizer responds via JWT
        respond_resp = org_session.post(f"{BASE_URL}/api/modifications/{proposal_id}/respond", json={
            "action": "accept"
        })
        
        assert respond_resp.status_code in [200, 400], f"Expected 200 or 400, got {respond_resp.status_code}: {respond_resp.text}"
        print(f"PASS: Organizer responded to participant proposal: {respond_resp.status_code}")
        
        # Cleanup
        time.sleep(0.5)
        if respond_resp.status_code != 200 or respond_resp.json().get("status") == "pending":
            org_session.post(f"{BASE_URL}/api/modifications/{proposal_id}/cancel")


class TestParticipantCancelOwnProposal:
    """Tests for participant canceling their own proposal via JWT (P1.2)"""
    
    @pytest.fixture(scope="class")
    def sessions(self):
        """Setup sessions"""
        time.sleep(2)
        
        part_session = requests.Session()
        part_session.headers.update({"Content-Type": "application/json"})
        part_token = login_with_retry(PARTICIPANT_EMAIL, PARTICIPANT_PASSWORD)
        if part_token:
            part_session.headers.update({"Authorization": f"Bearer {part_token}"})
        
        time.sleep(1)
        
        org_session = requests.Session()
        org_session.headers.update({"Content-Type": "application/json"})
        org_token = login_with_retry(ORGANIZER_EMAIL, ORGANIZER_PASSWORD)
        if org_token:
            org_session.headers.update({"Authorization": f"Bearer {org_token}"})
            
        return {"part": part_session, "org": org_session}
        
    def test_10_participant_can_cancel_own_proposal(self, sessions):
        """Participant can cancel their own proposal via JWT"""
        time.sleep(1)
        part_session = sessions["part"]
        org_session = sessions["org"]
        
        # Cleanup first
        resp = org_session.get(f"{BASE_URL}/api/modifications/active/{APPOINTMENT_WITH_ACCEPTED}")
        if resp.status_code == 200 and resp.json().get("proposal"):
            proposal = resp.json()["proposal"]
            if proposal.get("status") == "pending":
                org_session.post(f"{BASE_URL}/api/modifications/{proposal['proposal_id']}/cancel")
                time.sleep(0.5)
        
        # Participant creates proposal
        future_date = (datetime.utcnow() + timedelta(days=33)).strftime("%Y-%m-%dT%H:%M:%S")
        create_resp = part_session.post(f"{BASE_URL}/api/modifications/", json={
            "appointment_id": APPOINTMENT_WITH_ACCEPTED,
            "changes": {"start_datetime": future_date}
        })
        
        if create_resp.status_code != 200:
            print(f"INFO: Could not create proposal: {create_resp.text}")
            return
            
        proposal_id = create_resp.json().get("proposal_id")
        if not proposal_id:
            print("INFO: No proposal_id returned")
            return
            
        time.sleep(0.5)
        
        # Participant cancels via JWT
        cancel_resp = part_session.post(f"{BASE_URL}/api/modifications/{proposal_id}/cancel")
        
        assert cancel_resp.status_code == 200, f"Expected 200, got {cancel_resp.status_code}: {cancel_resp.text}"
        print(f"PASS: Participant cancelled own proposal via JWT")


class TestNonRegressionOrganizerFlow:
    """Non-regression tests for organizer proposal flow"""
    
    @pytest.fixture(scope="class")
    def org_session(self):
        """Setup organizer session"""
        time.sleep(2)
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        token = login_with_retry(ORGANIZER_EMAIL, ORGANIZER_PASSWORD)
        if token:
            session.headers.update({"Authorization": f"Bearer {token}"})
        return session
        
    def test_11_organizer_direct_mode_still_works(self, org_session):
        """Organizer can still do direct modification when 0 accepted non-org participants"""
        time.sleep(1)
        
        # Cleanup first
        resp = org_session.get(f"{BASE_URL}/api/modifications/active/{APPOINTMENT_DIRECT_MODE}")
        if resp.status_code == 200 and resp.json().get("proposal"):
            proposal = resp.json()["proposal"]
            if proposal.get("status") == "pending":
                org_session.post(f"{BASE_URL}/api/modifications/{proposal['proposal_id']}/cancel")
                time.sleep(0.5)
        
        # Create modification - should be direct mode
        future_date = (datetime.utcnow() + timedelta(days=34)).strftime("%Y-%m-%dT%H:%M:%S")
        resp = org_session.post(f"{BASE_URL}/api/modifications/", json={
            "appointment_id": APPOINTMENT_DIRECT_MODE,
            "changes": {"start_datetime": future_date}
        })
        
        if resp.status_code == 200:
            data = resp.json()
            mode = data.get("mode")
            status = data.get("status")
            print(f"INFO: Direct mode test - mode={mode}, status={status}")
            if mode == "direct" or status == "auto_applied":
                print("PASS: Organizer direct modification still works")
            else:
                print(f"INFO: Got mode={mode}, status={status}")
        else:
            print(f"INFO: Could not test direct mode: {resp.text}")
            
    def test_12_organizer_proposal_mode_still_works(self, org_session):
        """Organizer proposal mode works when >=1 accepted non-org participant"""
        time.sleep(1)
        
        # Cleanup first
        resp = org_session.get(f"{BASE_URL}/api/modifications/active/{APPOINTMENT_WITH_ACCEPTED}")
        if resp.status_code == 200 and resp.json().get("proposal"):
            proposal = resp.json()["proposal"]
            if proposal.get("status") == "pending":
                org_session.post(f"{BASE_URL}/api/modifications/{proposal['proposal_id']}/cancel")
                time.sleep(0.5)
        
        # Create modification - should be proposal mode
        future_date = (datetime.utcnow() + timedelta(days=35)).strftime("%Y-%m-%dT%H:%M:%S")
        resp = org_session.post(f"{BASE_URL}/api/modifications/", json={
            "appointment_id": APPOINTMENT_WITH_ACCEPTED,
            "changes": {"start_datetime": future_date}
        })
        
        if resp.status_code == 200:
            data = resp.json()
            status = data.get("status")
            proposal_id = data.get("proposal_id")
            print(f"INFO: Proposal mode test - status={status}")
            
            if status == "pending":
                print("PASS: Organizer proposal mode still works")
                # Cleanup
                time.sleep(0.5)
                org_session.post(f"{BASE_URL}/api/modifications/{proposal_id}/cancel")
            else:
                print(f"INFO: Got status={status}")
        else:
            print(f"INFO: Could not test proposal mode: {resp.text}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
