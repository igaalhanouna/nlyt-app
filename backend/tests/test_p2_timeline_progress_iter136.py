"""
Test P2.1 (Timeline History) and P2.2 (Vote Progress Bar) features
Iteration 136 - Testing modification proposals timeline and progress bars
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ORGANIZER_EMAIL = "testuser_audit@nlyt.app"
ORGANIZER_PASSWORD = "TestAudit123!"
PARTICIPANT1_EMAIL = "igaal.hanouna@gmail.com"
PARTICIPANT1_PASSWORD = "OrgTest123!"
PARTICIPANT2_EMAIL = "igaal@hotmail.com"
PARTICIPANT2_PASSWORD = "Test123!"

# Known appointment with modifications
APPOINTMENT_ID = "3e2f572f-e5e8-47a2-9e74-7f4273dd2d7c"


class TestHealthAndAuth:
    """Basic health and authentication tests"""
    
    def test_01_health_check(self):
        """Verify API is accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("PASS: API health check")
    
    def test_02_login_organizer(self):
        """Login as organizer"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ORGANIZER_EMAIL,
            "password": ORGANIZER_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        print(f"PASS: Organizer login successful")
        return data["access_token"]
    
    def test_03_login_participant1(self):
        """Login as participant 1"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PARTICIPANT1_EMAIL,
            "password": PARTICIPANT1_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        print(f"PASS: Participant 1 login successful")
        return data["access_token"]


class TestModificationMineEndpoint:
    """Test GET /api/modifications/mine endpoint for P2.2 progress bar data"""
    
    @pytest.fixture
    def auth_token(self):
        """Get organizer auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ORGANIZER_EMAIL,
            "password": ORGANIZER_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_04_modifications_mine_returns_participants_summary(self, auth_token):
        """P2.2: Verify /api/modifications/mine returns participants_summary field"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/modifications/mine", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        proposals = data.get("proposals", [])
        print(f"Found {len(proposals)} modification proposals")
        
        # Check that each proposal has participants_summary
        for prop in proposals:
            assert "participants_summary" in prop, f"Missing participants_summary in proposal {prop.get('proposal_id')}"
            summary = prop["participants_summary"]
            # Format should be "X/Y"
            assert "/" in summary, f"participants_summary should be in X/Y format, got: {summary}"
            parts = summary.split("/")
            assert len(parts) == 2, f"participants_summary should have 2 parts, got: {summary}"
            # Both parts should be numeric
            assert parts[0].isdigit(), f"First part should be numeric: {parts[0]}"
            assert parts[1].isdigit(), f"Second part should be numeric: {parts[1]}"
            print(f"  Proposal {prop.get('proposal_id')}: participants_summary = {summary}")
        
        print("PASS: /api/modifications/mine returns participants_summary field")
    
    def test_05_modifications_mine_fields_structure(self, auth_token):
        """Verify all required fields for P2.1 and P2.2 are present"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/modifications/mine", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        proposals = data.get("proposals", [])
        if len(proposals) == 0:
            pytest.skip("No proposals found to test structure")
        
        required_fields = [
            "proposal_id", "appointment_id", "appointment_title",
            "proposed_by", "changes", "original_values", "status",
            "is_action_required", "participants_summary"
        ]
        
        for prop in proposals:
            for field in required_fields:
                assert field in prop, f"Missing field '{field}' in proposal"
            
            # Verify proposed_by structure
            proposed_by = prop.get("proposed_by", {})
            assert "role" in proposed_by, "proposed_by should have 'role'"
            assert proposed_by["role"] in ["organizer", "participant"], f"Invalid role: {proposed_by['role']}"
            
            # Verify changes and original_values are dicts
            assert isinstance(prop.get("changes"), dict), "changes should be a dict"
            assert isinstance(prop.get("original_values"), dict), "original_values should be a dict"
        
        print("PASS: All required fields present in /api/modifications/mine response")


class TestModificationAppointmentEndpoint:
    """Test GET /api/modifications/appointment/{id} for P2.1 timeline history"""
    
    @pytest.fixture
    def auth_token(self):
        """Get organizer auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ORGANIZER_EMAIL,
            "password": ORGANIZER_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_06_get_appointment_proposals_history(self, auth_token):
        """P2.1: Verify /api/modifications/appointment/{id} returns proposal history"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/modifications/appointment/{APPOINTMENT_ID}", headers=headers)
        
        # May return 404 if appointment doesn't exist or 403 if no access
        if response.status_code == 404:
            pytest.skip(f"Appointment {APPOINTMENT_ID} not found")
        if response.status_code == 403:
            pytest.skip(f"No access to appointment {APPOINTMENT_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        proposals = data.get("proposals", [])
        print(f"Found {len(proposals)} proposals for appointment {APPOINTMENT_ID}")
        
        for prop in proposals:
            # P2.1: Each proposal should have fields for timeline display
            assert "proposal_id" in prop
            assert "status" in prop
            assert "created_at" in prop
            assert "proposed_by" in prop
            assert "changes" in prop
            assert "original_values" in prop
            
            # Check responses array for vote display
            if "responses" in prop:
                for resp in prop["responses"]:
                    assert "status" in resp, "Each response should have status"
            
            # Check organizer_response for vote display
            if "organizer_response" in prop:
                org_resp = prop["organizer_response"]
                assert "status" in org_resp, "organizer_response should have status"
            
            print(f"  Proposal {prop['proposal_id']}: status={prop['status']}, created_at={prop.get('created_at')}")
        
        print("PASS: /api/modifications/appointment/{id} returns proper history structure")
    
    def test_07_proposal_status_values(self, auth_token):
        """P2.1: Verify proposal status values match timeline dot colors"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/modifications/appointment/{APPOINTMENT_ID}", headers=headers)
        
        if response.status_code != 200:
            pytest.skip("Cannot access appointment proposals")
        
        data = response.json()
        proposals = data.get("proposals", [])
        
        valid_statuses = ["pending", "accepted", "rejected", "expired", "cancelled", "auto_applied"]
        
        for prop in proposals:
            status = prop.get("status")
            assert status in valid_statuses, f"Invalid status '{status}', expected one of {valid_statuses}"
            print(f"  Proposal {prop['proposal_id']}: status={status}")
        
        print("PASS: All proposal statuses are valid for timeline display")


class TestActiveProposalEndpoint:
    """Test GET /api/modifications/active/{appointment_id}"""
    
    def test_08_get_active_proposal(self):
        """Verify active proposal endpoint returns proper structure"""
        response = requests.get(f"{BASE_URL}/api/modifications/active/{APPOINTMENT_ID}")
        assert response.status_code == 200
        data = response.json()
        
        proposal = data.get("proposal")
        if proposal is None:
            print("No active proposal for this appointment")
        else:
            # Verify structure for VoteProgressBar
            assert "proposal_id" in proposal
            assert "status" in proposal
            assert "responses" in proposal or "organizer_response" in proposal
            
            # Check responses for vote counting
            responses = proposal.get("responses", [])
            for resp in responses:
                assert "status" in resp
                assert resp["status"] in ["pending", "accepted", "rejected"]
            
            print(f"Active proposal: {proposal['proposal_id']}, status={proposal['status']}")
            print(f"  Responses: {len(responses)}")
        
        print("PASS: Active proposal endpoint returns proper structure")


class TestParticipantAccess:
    """Test participant access to modification endpoints"""
    
    @pytest.fixture
    def participant_token(self):
        """Get participant auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PARTICIPANT1_EMAIL,
            "password": PARTICIPANT1_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Participant authentication failed")
    
    def test_09_participant_can_access_modifications_mine(self, participant_token):
        """Verify participant can access their modifications"""
        headers = {"Authorization": f"Bearer {participant_token}"}
        response = requests.get(f"{BASE_URL}/api/modifications/mine", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        proposals = data.get("proposals", [])
        print(f"Participant has {len(proposals)} modification proposals")
        
        # Check is_action_required field for participant
        action_required_count = sum(1 for p in proposals if p.get("is_action_required"))
        print(f"  Action required: {action_required_count}")
        
        print("PASS: Participant can access /api/modifications/mine")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
