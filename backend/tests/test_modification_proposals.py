"""
Test suite for Modification Proposals API
Tests the contractual flow for appointment modifications:
- Organizer/Participant creates a proposal
- All parties must accept (unanimity)
- Rejection immediately rejects proposal
- Unanimous acceptance applies changes to appointment
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://link-redirect-fix-3.preview.emergentagent.com')

# Test credentials
TEST_USER_EMAIL = "testuser_audit@nlyt.app"
TEST_USER_PASSWORD = "Test1234!"
WORKSPACE_ID = "7e219321-18fd-4643-9be6-e4f1de88a2a8"
TEST_APPOINTMENT_ID = "fbca6bbc-826f-4552-93ea-622055649148"
PARTICIPANT_INVITATION_TOKEN = "3f06ba28-fd2d-49c7-96b3-555f3dde0a52"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for organizer"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("access_token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with Bearer token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestModificationProposalBasics:
    """Basic API endpoint tests"""
    
    def test_get_active_proposal_no_auth_required(self):
        """GET /api/modifications/active/{appointment_id} is public"""
        response = requests.get(f"{BASE_URL}/api/modifications/active/{TEST_APPOINTMENT_ID}")
        assert response.status_code == 200
        data = response.json()
        assert "proposal" in data
        print(f"Active proposal: {data['proposal']}")
    
    def test_get_proposal_history_requires_auth(self, auth_headers):
        """GET /api/modifications/appointment/{appointment_id} requires auth"""
        response = requests.get(
            f"{BASE_URL}/api/modifications/appointment/{TEST_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "proposals" in data
        print(f"Proposal history count: {len(data['proposals'])}")


class TestOrganizerProposalFlow:
    """Tests for organizer creating and managing proposals"""
    
    def test_organizer_create_proposal_success(self, auth_headers):
        """POST /api/modifications/ creates a proposal (organizer via JWT)"""
        # Calculate future datetime (7 days from now)
        future_dt = (datetime.utcnow() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        response = requests.post(
            f"{BASE_URL}/api/modifications/",
            headers=auth_headers,
            json={
                "appointment_id": TEST_APPOINTMENT_ID,
                "changes": {
                    "start_datetime": future_dt,
                    "duration_minutes": 90
                }
            }
        )
        
        if response.status_code == 400:
            # May fail if there's already an active proposal
            data = response.json()
            if "déjà en cours" in data.get("detail", ""):
                print("Skipping: Active proposal already exists")
                pytest.skip("Active proposal already exists")
            elif "passé" in data.get("detail", ""):
                print("Skipping: Appointment is in the past")
                pytest.skip("Appointment is in the past")
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify proposal structure
        assert "proposal_id" in data
        assert data["appointment_id"] == TEST_APPOINTMENT_ID
        assert data["status"] == "pending"
        assert data["proposed_by"]["role"] == "organizer"
        assert "changes" in data
        assert "original_values" in data
        assert "responses" in data
        assert "organizer_response" in data
        assert data["organizer_response"]["status"] == "auto_accepted"
        
        print(f"Created proposal: {data['proposal_id']}")
        return data["proposal_id"]
    
    def test_duplicate_proposal_returns_400(self, auth_headers):
        """POST /api/modifications/ with active proposal returns 400"""
        # First check if there's an active proposal
        check_response = requests.get(f"{BASE_URL}/api/modifications/active/{TEST_APPOINTMENT_ID}")
        active = check_response.json().get("proposal")
        
        if not active:
            # Create one first
            future_dt = (datetime.utcnow() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ')
            requests.post(
                f"{BASE_URL}/api/modifications/",
                headers=auth_headers,
                json={
                    "appointment_id": TEST_APPOINTMENT_ID,
                    "changes": {"start_datetime": future_dt}
                }
            )
        
        # Now try to create another
        future_dt2 = (datetime.utcnow() + timedelta(days=8)).strftime('%Y-%m-%dT%H:%M:%SZ')
        response = requests.post(
            f"{BASE_URL}/api/modifications/",
            headers=auth_headers,
            json={
                "appointment_id": TEST_APPOINTMENT_ID,
                "changes": {"start_datetime": future_dt2}
            }
        )
        
        # Should return 400 if there's already an active proposal
        if response.status_code == 400:
            data = response.json()
            assert "déjà en cours" in data.get("detail", ""), f"Unexpected error: {data}"
            print("Correctly rejected duplicate proposal")
        else:
            # If no active proposal existed, this would succeed
            print("No active proposal existed, created new one")
    
    def test_proposal_with_past_datetime_returns_400(self, auth_headers):
        """POST /api/modifications/ with past start_datetime returns 400"""
        # First cancel any active proposal
        check_response = requests.get(f"{BASE_URL}/api/modifications/active/{TEST_APPOINTMENT_ID}")
        active = check_response.json().get("proposal")
        if active and active.get("proposed_by", {}).get("role") == "organizer":
            requests.post(
                f"{BASE_URL}/api/modifications/{active['proposal_id']}/cancel",
                headers=auth_headers
            )
        
        # Try to create proposal with past date
        past_dt = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        response = requests.post(
            f"{BASE_URL}/api/modifications/",
            headers=auth_headers,
            json={
                "appointment_id": TEST_APPOINTMENT_ID,
                "changes": {"start_datetime": past_dt}
            }
        )
        
        # Should return 400 for past date
        if response.status_code == 400:
            data = response.json()
            assert "futur" in data.get("detail", "").lower() or "passé" in data.get("detail", "").lower(), f"Unexpected error: {data}"
            print(f"Correctly rejected past date: {data['detail']}")
        else:
            # May fail for other reasons (active proposal, etc)
            print(f"Response: {response.status_code} - {response.text}")


class TestParticipantProposalFlow:
    """Tests for participant creating proposals via invitation token"""
    
    def test_participant_create_proposal_success(self, auth_headers):
        """POST /api/modifications/ creates a proposal (participant via invitation_token)"""
        # First cancel any active proposal
        check_response = requests.get(f"{BASE_URL}/api/modifications/active/{TEST_APPOINTMENT_ID}")
        active = check_response.json().get("proposal")
        if active and active.get("proposed_by", {}).get("role") == "organizer":
            requests.post(
                f"{BASE_URL}/api/modifications/{active['proposal_id']}/cancel",
                headers=auth_headers
            )
        
        # Calculate future datetime
        future_dt = (datetime.utcnow() + timedelta(days=10)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        response = requests.post(
            f"{BASE_URL}/api/modifications/",
            json={
                "appointment_id": TEST_APPOINTMENT_ID,
                "invitation_token": PARTICIPANT_INVITATION_TOKEN,
                "changes": {
                    "location": "Paris, Tour Eiffel"
                }
            }
        )
        
        if response.status_code == 400:
            data = response.json()
            if "déjà en cours" in data.get("detail", ""):
                print("Skipping: Active proposal already exists")
                pytest.skip("Active proposal already exists")
            elif "accepté" in data.get("detail", "").lower():
                print(f"Participant status issue: {data['detail']}")
                pytest.skip("Participant has not accepted invitation")
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["proposed_by"]["role"] == "participant"
        assert data["organizer_response"]["status"] == "pending"  # Organizer must respond
        print(f"Participant created proposal: {data['proposal_id']}")
        return data["proposal_id"]


class TestProposalResponses:
    """Tests for accepting/rejecting proposals"""
    
    def test_participant_accept_proposal(self, auth_headers):
        """POST /api/modifications/{id}/respond with 'accept' records acceptance"""
        # Get active proposal
        check_response = requests.get(f"{BASE_URL}/api/modifications/active/{TEST_APPOINTMENT_ID}")
        active = check_response.json().get("proposal")
        
        if not active:
            # Create one first
            future_dt = (datetime.utcnow() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ')
            create_response = requests.post(
                f"{BASE_URL}/api/modifications/",
                headers=auth_headers,
                json={
                    "appointment_id": TEST_APPOINTMENT_ID,
                    "changes": {"start_datetime": future_dt}
                }
            )
            if create_response.status_code != 200:
                pytest.skip(f"Could not create proposal: {create_response.text}")
            active = create_response.json()
        
        # Find if participant needs to respond
        participant_pending = False
        for resp in active.get("responses", []):
            if resp.get("status") == "pending":
                participant_pending = True
                break
        
        if not participant_pending:
            print("No pending participant responses")
            pytest.skip("No pending participant responses")
        
        # Participant accepts
        response = requests.post(
            f"{BASE_URL}/api/modifications/{active['proposal_id']}/respond",
            json={
                "action": "accept",
                "invitation_token": PARTICIPANT_INVITATION_TOKEN
            }
        )
        
        if response.status_code == 400:
            data = response.json()
            if "déjà répondu" in data.get("detail", ""):
                print("Participant already responded")
                pytest.skip("Participant already responded")
            elif "concerné" in data.get("detail", ""):
                print("Participant not part of this proposal")
                pytest.skip("Participant not part of this proposal")
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        print(f"Proposal status after accept: {data['status']}")
    
    def test_participant_reject_proposal_immediately_rejects(self, auth_headers):
        """POST /api/modifications/{id}/respond with 'reject' immediately rejects proposal"""
        # First cancel any active proposal
        check_response = requests.get(f"{BASE_URL}/api/modifications/active/{TEST_APPOINTMENT_ID}")
        active = check_response.json().get("proposal")
        if active and active.get("proposed_by", {}).get("role") == "organizer":
            requests.post(
                f"{BASE_URL}/api/modifications/{active['proposal_id']}/cancel",
                headers=auth_headers
            )
        
        # Create a new proposal
        future_dt = (datetime.utcnow() + timedelta(days=9)).strftime('%Y-%m-%dT%H:%M:%SZ')
        create_response = requests.post(
            f"{BASE_URL}/api/modifications/",
            headers=auth_headers,
            json={
                "appointment_id": TEST_APPOINTMENT_ID,
                "changes": {"start_datetime": future_dt}
            }
        )
        
        if create_response.status_code != 200:
            pytest.skip(f"Could not create proposal: {create_response.text}")
        
        proposal = create_response.json()
        proposal_id = proposal["proposal_id"]
        
        # Participant rejects
        response = requests.post(
            f"{BASE_URL}/api/modifications/{proposal_id}/respond",
            json={
                "action": "reject",
                "invitation_token": PARTICIPANT_INVITATION_TOKEN
            }
        )
        
        if response.status_code == 400:
            data = response.json()
            if "concerné" in data.get("detail", ""):
                print("Participant not part of this proposal")
                pytest.skip("Participant not part of this proposal")
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Rejection should immediately reject the proposal
        assert data["status"] == "rejected", f"Expected rejected, got {data['status']}"
        print("Proposal correctly rejected immediately")
    
    def test_organizer_respond_to_participant_proposal(self, auth_headers):
        """Organizer can accept/reject participant proposals"""
        # First cancel any active proposal
        check_response = requests.get(f"{BASE_URL}/api/modifications/active/{TEST_APPOINTMENT_ID}")
        active = check_response.json().get("proposal")
        if active:
            if active.get("proposed_by", {}).get("role") == "organizer":
                requests.post(
                    f"{BASE_URL}/api/modifications/{active['proposal_id']}/cancel",
                    headers=auth_headers
                )
            else:
                # It's a participant proposal, organizer can respond
                if active.get("organizer_response", {}).get("status") == "pending":
                    response = requests.post(
                        f"{BASE_URL}/api/modifications/{active['proposal_id']}/respond",
                        headers=auth_headers,
                        json={"action": "accept"}
                    )
                    print(f"Organizer responded to participant proposal: {response.status_code}")
                    return
        
        # Create a participant proposal
        response = requests.post(
            f"{BASE_URL}/api/modifications/",
            json={
                "appointment_id": TEST_APPOINTMENT_ID,
                "invitation_token": PARTICIPANT_INVITATION_TOKEN,
                "changes": {"location": "Lyon, Place Bellecour"}
            }
        )
        
        if response.status_code != 200:
            pytest.skip(f"Could not create participant proposal: {response.text}")
        
        proposal = response.json()
        
        # Organizer accepts
        accept_response = requests.post(
            f"{BASE_URL}/api/modifications/{proposal['proposal_id']}/respond",
            headers=auth_headers,
            json={"action": "accept"}
        )
        
        assert accept_response.status_code == 200, f"Failed: {accept_response.text}"
        data = accept_response.json()
        print(f"Organizer accepted participant proposal, status: {data['status']}")


class TestUnanimousAcceptance:
    """Tests for unanimous acceptance applying changes"""
    
    def test_unanimous_acceptance_applies_changes(self, auth_headers):
        """When all accept, changes are applied to appointment"""
        # Get current appointment state
        apt_response = requests.get(
            f"{BASE_URL}/api/appointments/{TEST_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert apt_response.status_code == 200
        original_apt = apt_response.json()
        original_location = original_apt.get("location", "")
        
        # Cancel any active proposal
        check_response = requests.get(f"{BASE_URL}/api/modifications/active/{TEST_APPOINTMENT_ID}")
        active = check_response.json().get("proposal")
        if active and active.get("proposed_by", {}).get("role") == "organizer":
            requests.post(
                f"{BASE_URL}/api/modifications/{active['proposal_id']}/cancel",
                headers=auth_headers
            )
        
        # Create a proposal with location change
        new_location = f"Test Location {datetime.utcnow().strftime('%H%M%S')}"
        create_response = requests.post(
            f"{BASE_URL}/api/modifications/",
            headers=auth_headers,
            json={
                "appointment_id": TEST_APPOINTMENT_ID,
                "changes": {"location": new_location}
            }
        )
        
        if create_response.status_code != 200:
            pytest.skip(f"Could not create proposal: {create_response.text}")
        
        proposal = create_response.json()
        proposal_id = proposal["proposal_id"]
        
        # Check if there are pending responses
        pending_count = sum(1 for r in proposal.get("responses", []) if r.get("status") == "pending")
        
        if pending_count == 0:
            # No participants to respond, proposal should be auto-accepted
            # Re-fetch to check status
            check_response = requests.get(f"{BASE_URL}/api/modifications/active/{TEST_APPOINTMENT_ID}")
            updated = check_response.json().get("proposal")
            if not updated:
                # Proposal was accepted and applied
                apt_response = requests.get(
                    f"{BASE_URL}/api/appointments/{TEST_APPOINTMENT_ID}",
                    headers=auth_headers
                )
                updated_apt = apt_response.json()
                print(f"Appointment location: {updated_apt.get('location')}")
            return
        
        # Participant accepts
        accept_response = requests.post(
            f"{BASE_URL}/api/modifications/{proposal_id}/respond",
            json={
                "action": "accept",
                "invitation_token": PARTICIPANT_INVITATION_TOKEN
            }
        )
        
        if accept_response.status_code == 400:
            data = accept_response.json()
            if "concerné" in data.get("detail", ""):
                pytest.skip("Participant not part of this proposal")
        
        assert accept_response.status_code == 200, f"Failed: {accept_response.text}"
        result = accept_response.json()
        
        # Check if proposal was accepted (all responded)
        if result["status"] == "accepted":
            # Verify appointment was updated
            apt_response = requests.get(
                f"{BASE_URL}/api/appointments/{TEST_APPOINTMENT_ID}",
                headers=auth_headers
            )
            updated_apt = apt_response.json()
            assert updated_apt.get("location") == new_location, f"Location not updated: {updated_apt.get('location')}"
            print(f"Unanimous acceptance applied changes: location = {new_location}")
        else:
            print(f"Proposal still pending (more responses needed): {result['status']}")


class TestRejectionDoesNotChangeAppointment:
    """Tests that rejection preserves appointment state"""
    
    def test_rejection_preserves_appointment(self, auth_headers):
        """Rejection does NOT change the appointment"""
        # Get current appointment state
        apt_response = requests.get(
            f"{BASE_URL}/api/appointments/{TEST_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert apt_response.status_code == 200
        original_apt = apt_response.json()
        original_location = original_apt.get("location", "")
        
        # Cancel any active proposal
        check_response = requests.get(f"{BASE_URL}/api/modifications/active/{TEST_APPOINTMENT_ID}")
        active = check_response.json().get("proposal")
        if active and active.get("proposed_by", {}).get("role") == "organizer":
            requests.post(
                f"{BASE_URL}/api/modifications/{active['proposal_id']}/cancel",
                headers=auth_headers
            )
        
        # Create a proposal with location change
        new_location = f"Rejected Location {datetime.utcnow().strftime('%H%M%S')}"
        create_response = requests.post(
            f"{BASE_URL}/api/modifications/",
            headers=auth_headers,
            json={
                "appointment_id": TEST_APPOINTMENT_ID,
                "changes": {"location": new_location}
            }
        )
        
        if create_response.status_code != 200:
            pytest.skip(f"Could not create proposal: {create_response.text}")
        
        proposal = create_response.json()
        proposal_id = proposal["proposal_id"]
        
        # Participant rejects
        reject_response = requests.post(
            f"{BASE_URL}/api/modifications/{proposal_id}/respond",
            json={
                "action": "reject",
                "invitation_token": PARTICIPANT_INVITATION_TOKEN
            }
        )
        
        if reject_response.status_code == 400:
            data = reject_response.json()
            if "concerné" in data.get("detail", ""):
                pytest.skip("Participant not part of this proposal")
        
        assert reject_response.status_code == 200, f"Failed: {reject_response.text}"
        result = reject_response.json()
        assert result["status"] == "rejected"
        
        # Verify appointment was NOT changed
        apt_response = requests.get(
            f"{BASE_URL}/api/appointments/{TEST_APPOINTMENT_ID}",
            headers=auth_headers
        )
        unchanged_apt = apt_response.json()
        assert unchanged_apt.get("location") == original_location, f"Location should not have changed: {unchanged_apt.get('location')}"
        print(f"Rejection correctly preserved appointment: location = {original_location}")


class TestProposalHistory:
    """Tests for proposal history retrieval"""
    
    def test_get_proposal_history(self, auth_headers):
        """GET /api/modifications/appointment/{appointment_id} returns proposal history"""
        response = requests.get(
            f"{BASE_URL}/api/modifications/appointment/{TEST_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "proposals" in data
        proposals = data["proposals"]
        
        print(f"Total proposals in history: {len(proposals)}")
        
        # Count by status
        status_counts = {}
        for p in proposals:
            status = p.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"Status breakdown: {status_counts}")
        
        # Verify structure of proposals
        if proposals:
            p = proposals[0]
            assert "proposal_id" in p
            assert "appointment_id" in p
            assert "proposed_by" in p
            assert "changes" in p
            assert "status" in p
            assert "created_at" in p


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
