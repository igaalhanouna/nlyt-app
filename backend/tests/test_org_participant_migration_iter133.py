"""
Test: Organizer Participant Migration (Iteration 133)

Verifies that the migration script correctly added organizer participant records
to appointments that were missing them, and that the modification flow still works correctly.

Key tests:
1. Migrated org-participant has correct fields (is_organizer=True, role='organizer', status='accepted_pending_guarantee', migrated_at exists)
2. GET /api/participants/ includes organizer with is_organizer=True for migrated appointments
3. POST /api/modifications/ on appointment with 0 accepted non-org participants returns mode='direct'
4. POST /api/modifications/ on appointment with accepted non-org participants returns status='pending' (proposal mode)
5. Non-regression: appointments list and detail work correctly
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test appointments from the migration
APPOINTMENT_0_ACCEPTED = "7e2270b1-606c-4945-be71-024c10c3edcd"  # Should be direct mode
APPOINTMENT_1_ACCEPTED = "3e2f572f-e5e8-47a2-9e74-7f4273dd2d7c"  # Should be proposal mode

# Test credentials
TEST_USER_EMAIL = "testuser_audit@nlyt.app"
TEST_USER_PASSWORD = "TestAudit123!"


class TestOrgParticipantMigration:
    """Tests for organizer participant migration verification"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for test user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    # ─── Test 1: Health Check ───
    def test_01_health_check(self):
        """Verify API is accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        print("PASS: API health check")
    
    # ─── Test 2: Login Success ───
    def test_02_login_success(self, auth_token):
        """Verify login works"""
        assert auth_token is not None, "Auth token should not be None"
        print(f"PASS: Login successful, token obtained")
    
    # ─── Test 3: Verify Migrated Org-Participant Fields for Appointment 7e2270b1 ───
    def test_03_migrated_org_participant_fields(self, auth_headers):
        """
        Verify that the migrated org-participant for appointment 7e2270b1 has correct fields:
        - is_organizer=True
        - role='organizer'
        - status='accepted_pending_guarantee'
        - migrated_at exists
        """
        response = requests.get(
            f"{BASE_URL}/api/participants/",
            params={"appointment_id": APPOINTMENT_0_ACCEPTED},
            headers=auth_headers
        )
        assert response.status_code == 200, f"GET participants failed: {response.status_code} - {response.text}"
        
        data = response.json()
        participants = data.get("participants", [])
        
        # Find the organizer participant
        org_participant = None
        for p in participants:
            if p.get("is_organizer") == True:
                org_participant = p
                break
        
        assert org_participant is not None, f"No organizer participant found in {len(participants)} participants"
        
        # Verify fields
        assert org_participant.get("is_organizer") == True, "is_organizer should be True"
        assert org_participant.get("role") == "organizer", f"role should be 'organizer', got '{org_participant.get('role')}'"
        assert org_participant.get("status") == "accepted_pending_guarantee", f"status should be 'accepted_pending_guarantee', got '{org_participant.get('status')}'"
        assert org_participant.get("migrated_at") is not None, "migrated_at should exist for migrated records"
        
        print(f"PASS: Migrated org-participant has correct fields:")
        print(f"  - is_organizer: {org_participant.get('is_organizer')}")
        print(f"  - role: {org_participant.get('role')}")
        print(f"  - status: {org_participant.get('status')}")
        print(f"  - migrated_at: {org_participant.get('migrated_at')}")
        print(f"  - email: {org_participant.get('email')}")
    
    # ─── Test 4: GET Participants Includes Organizer ───
    def test_04_participants_includes_organizer(self, auth_headers):
        """
        Verify GET /api/participants/?appointment_id=7e2270b1 includes the organizer
        """
        response = requests.get(
            f"{BASE_URL}/api/participants/",
            params={"appointment_id": APPOINTMENT_0_ACCEPTED},
            headers=auth_headers
        )
        assert response.status_code == 200, f"GET participants failed: {response.status_code}"
        
        data = response.json()
        participants = data.get("participants", [])
        
        # Check that at least one participant has is_organizer=True
        has_organizer = any(p.get("is_organizer") == True for p in participants)
        assert has_organizer, "Participants list should include organizer with is_organizer=True"
        
        print(f"PASS: Participants list includes organizer (total: {len(participants)} participants)")
    
    # ─── Test 5: Cancel Any Pending Proposal for Appointment 7e2270b1 ───
    def test_05_cleanup_pending_proposal_apt1(self, auth_headers):
        """Cancel any pending proposal for appointment 7e2270b1 before testing"""
        response = requests.get(
            f"{BASE_URL}/api/modifications/active/{APPOINTMENT_0_ACCEPTED}",
            headers=auth_headers
        )
        if response.status_code == 200:
            data = response.json()
            proposal = data.get("proposal")
            if proposal and proposal.get("status") == "pending":
                cancel_response = requests.post(
                    f"{BASE_URL}/api/modifications/{proposal['proposal_id']}/cancel",
                    headers=auth_headers
                )
                print(f"Cancelled pending proposal: {cancel_response.status_code}")
        print("PASS: Cleanup complete for appointment 7e2270b1")
    
    # ─── Test 6: Direct Modification Mode for Appointment with 0 Accepted Non-Org ───
    def test_06_direct_modification_mode(self, auth_headers):
        """
        POST /api/modifications/ on appointment 7e2270b1 should return mode='direct'
        because the migrated org-participant has is_organizer=True and is excluded
        from non_org_accepted count.
        """
        # Create a modification proposal
        response = requests.post(
            f"{BASE_URL}/api/modifications/",
            json={
                "appointment_id": APPOINTMENT_0_ACCEPTED,
                "changes": {"duration_minutes": 45}
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"POST modifications failed: {response.status_code} - {response.text}"
        
        data = response.json()
        
        # Verify direct mode
        assert data.get("mode") == "direct", f"Expected mode='direct', got '{data.get('mode')}'"
        assert data.get("status") == "auto_applied", f"Expected status='auto_applied', got '{data.get('status')}'"
        
        print(f"PASS: Direct modification mode works correctly:")
        print(f"  - mode: {data.get('mode')}")
        print(f"  - status: {data.get('status')}")
        print(f"  - proposal_id: {data.get('proposal_id')}")
    
    # ─── Test 7: Verify Participants for Appointment 3e2f572f ───
    def test_07_participants_apt2_has_accepted_non_org(self, auth_headers):
        """
        Verify appointment 3e2f572f has at least one accepted non-org participant
        """
        response = requests.get(
            f"{BASE_URL}/api/participants/",
            params={"appointment_id": APPOINTMENT_1_ACCEPTED},
            headers=auth_headers
        )
        assert response.status_code == 200, f"GET participants failed: {response.status_code}"
        
        data = response.json()
        participants = data.get("participants", [])
        
        accepted_statuses = ["accepted", "guaranteed", "accepted_pending_guarantee", "accepted_guaranteed"]
        non_org_accepted = [p for p in participants if not p.get("is_organizer") and p.get("status") in accepted_statuses]
        
        assert len(non_org_accepted) > 0, f"Expected at least 1 accepted non-org participant, got {len(non_org_accepted)}"
        
        print(f"PASS: Appointment 3e2f572f has {len(non_org_accepted)} accepted non-org participant(s)")
        for p in non_org_accepted:
            print(f"  - {p.get('email')}: status={p.get('status')}")
    
    # ─── Test 8: Cancel Any Pending Proposal for Appointment 3e2f572f ───
    def test_08_cleanup_pending_proposal_apt2(self, auth_headers):
        """Cancel any pending proposal for appointment 3e2f572f before testing"""
        response = requests.get(
            f"{BASE_URL}/api/modifications/active/{APPOINTMENT_1_ACCEPTED}",
            headers=auth_headers
        )
        if response.status_code == 200:
            data = response.json()
            proposal = data.get("proposal")
            if proposal and proposal.get("status") == "pending":
                cancel_response = requests.post(
                    f"{BASE_URL}/api/modifications/{proposal['proposal_id']}/cancel",
                    headers=auth_headers
                )
                print(f"Cancelled pending proposal: {cancel_response.status_code}")
        print("PASS: Cleanup complete for appointment 3e2f572f")
    
    # ─── Test 9: Proposal Mode for Appointment with Accepted Non-Org ───
    def test_09_proposal_mode(self, auth_headers):
        """
        POST /api/modifications/ on appointment 3e2f572f should return status='pending'
        because it has accepted non-org participants who need to vote.
        """
        response = requests.post(
            f"{BASE_URL}/api/modifications/",
            json={
                "appointment_id": APPOINTMENT_1_ACCEPTED,
                "changes": {"duration_minutes": 90}
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"POST modifications failed: {response.status_code} - {response.text}"
        
        data = response.json()
        
        # Verify proposal mode (not direct)
        assert data.get("mode") != "direct", f"Expected proposal mode (not direct), got mode='{data.get('mode')}'"
        assert data.get("status") == "pending", f"Expected status='pending', got '{data.get('status')}'"
        assert len(data.get("responses", [])) > 0, "Expected responses array with pending votes"
        
        print(f"PASS: Proposal mode works correctly:")
        print(f"  - mode: {data.get('mode', 'proposal')}")
        print(f"  - status: {data.get('status')}")
        print(f"  - responses: {len(data.get('responses', []))} pending votes")
    
    # ─── Test 10: Cleanup Pending Proposal After Test ───
    def test_10_cleanup_after_test(self, auth_headers):
        """Cancel the pending proposal created in test_09"""
        response = requests.get(
            f"{BASE_URL}/api/modifications/active/{APPOINTMENT_1_ACCEPTED}",
            headers=auth_headers
        )
        if response.status_code == 200:
            data = response.json()
            proposal = data.get("proposal")
            if proposal and proposal.get("status") == "pending":
                cancel_response = requests.post(
                    f"{BASE_URL}/api/modifications/{proposal['proposal_id']}/cancel",
                    headers=auth_headers
                )
                print(f"Cancelled pending proposal: {cancel_response.status_code}")
        print("PASS: Cleanup complete")
    
    # ─── Test 11: Non-Regression - Appointments List ───
    def test_11_appointments_list(self, auth_headers):
        """Verify GET /api/appointments/ still works"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/",
            headers=auth_headers
        )
        assert response.status_code == 200, f"GET appointments failed: {response.status_code}"
        
        data = response.json()
        # API returns 'items' not 'appointments'
        appointments = data.get("items", data.get("appointments", []))
        
        assert len(appointments) > 0, "Expected at least 1 appointment"
        print(f"PASS: Appointments list works ({len(appointments)} appointments)")
    
    # ─── Test 12: Non-Regression - Appointment Detail ───
    def test_12_appointment_detail(self, auth_headers):
        """Verify GET /api/appointments/{id} still works"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/{APPOINTMENT_0_ACCEPTED}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"GET appointment detail failed: {response.status_code}"
        
        data = response.json()
        assert data.get("appointment_id") == APPOINTMENT_0_ACCEPTED, "appointment_id mismatch"
        
        print(f"PASS: Appointment detail works (title: {data.get('title', 'N/A')})")
    
    # ─── Test 13: Verify Org-Participant for Appointment 3e2f572f ───
    def test_13_org_participant_apt2(self, auth_headers):
        """
        Verify appointment 3e2f572f also has an organizer participant
        """
        response = requests.get(
            f"{BASE_URL}/api/participants/",
            params={"appointment_id": APPOINTMENT_1_ACCEPTED},
            headers=auth_headers
        )
        assert response.status_code == 200, f"GET participants failed: {response.status_code}"
        
        data = response.json()
        participants = data.get("participants", [])
        
        org_participant = None
        for p in participants:
            if p.get("is_organizer") == True:
                org_participant = p
                break
        
        assert org_participant is not None, "Appointment 3e2f572f should have an organizer participant"
        
        print(f"PASS: Appointment 3e2f572f has organizer participant:")
        print(f"  - email: {org_participant.get('email')}")
        print(f"  - is_organizer: {org_participant.get('is_organizer')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
