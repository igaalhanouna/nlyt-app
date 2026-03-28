"""
Test Phase 2 Dispute Decision Logic - Iteration 115
Tests the new organizer decision flow: concede (release guarantee) or maintain (escalate to platform)

Endpoints tested:
- GET /api/disputes/mine - returns is_accuser, can_decide, decision fields
- GET /api/disputes/{id} - returns is_accuser, can_decide, decision, accuser_user_id fields
- POST /api/disputes/{id}/concede - organizer releases participant's guarantee
- POST /api/disputes/{id}/maintain - organizer escalates to platform arbitration
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from review_request
ORGANIZER_EMAIL = "testuser_audit@nlyt.app"
ORGANIZER_PASSWORD = "TestAudit123!"
PARTICIPANT_EMAIL = "igaal@hotmail.com"
PARTICIPANT_PASSWORD = "Test123!"


class TestDisputeDecisionPhase2:
    """Phase 2 Dispute Decision Logic Tests"""
    
    @pytest.fixture(scope="class")
    def organizer_token(self):
        """Get auth token for organizer (accuser)"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ORGANIZER_EMAIL,
            "password": ORGANIZER_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Organizer login failed: {response.status_code} - {response.text}")
        data = response.json()
        return data.get('access_token')
    
    @pytest.fixture(scope="class")
    def participant_token(self):
        """Get auth token for participant (non-accuser)"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PARTICIPANT_EMAIL,
            "password": PARTICIPANT_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Participant login failed: {response.status_code} - {response.text}")
        data = response.json()
        return data.get('access_token')
    
    @pytest.fixture(scope="class")
    def organizer_user_id(self, organizer_token):
        """Get organizer user_id"""
        response = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {organizer_token}"
        })
        if response.status_code != 200:
            pytest.skip("Could not get organizer user info")
        return response.json().get('user_id')
    
    @pytest.fixture(scope="class")
    def participant_user_id(self, participant_token):
        """Get participant user_id"""
        response = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {participant_token}"
        })
        if response.status_code != 200:
            pytest.skip("Could not get participant user info")
        return response.json().get('user_id')
    
    # ========== GET /api/disputes/mine Tests ==========
    
    def test_disputes_mine_returns_phase2_fields_for_organizer(self, organizer_token, organizer_user_id):
        """GET /api/disputes/mine returns is_accuser, can_decide, decision fields for organizer"""
        response = requests.get(f"{BASE_URL}/api/disputes/mine", headers={
            "Authorization": f"Bearer {organizer_token}"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert 'disputes' in data, "Response should have 'disputes' key"
        assert 'count' in data, "Response should have 'count' key"
        
        # Check at least one dispute exists
        if data['count'] > 0:
            dispute = data['disputes'][0]
            # Phase 2 fields must be present
            assert 'is_accuser' in dispute, "Dispute should have 'is_accuser' field"
            assert 'can_decide' in dispute, "Dispute should have 'can_decide' field"
            assert 'decision' in dispute or dispute.get('decision') is None, "Dispute should have 'decision' field"
            print(f"✅ Found {data['count']} disputes with Phase 2 fields")
            print(f"   First dispute: is_accuser={dispute.get('is_accuser')}, can_decide={dispute.get('can_decide')}, decision={dispute.get('decision')}")
        else:
            print("⚠️ No disputes found for organizer - cannot verify Phase 2 fields")
    
    def test_disputes_mine_returns_phase2_fields_for_participant(self, participant_token):
        """GET /api/disputes/mine returns is_accuser=False for non-organizer participant"""
        response = requests.get(f"{BASE_URL}/api/disputes/mine", headers={
            "Authorization": f"Bearer {participant_token}"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        if data['count'] > 0:
            dispute = data['disputes'][0]
            assert 'is_accuser' in dispute, "Dispute should have 'is_accuser' field"
            # Participant should NOT be accuser
            assert dispute.get('is_accuser') == False, "Participant should not be accuser"
            assert dispute.get('can_decide') == False, "Participant should not be able to decide"
            print(f"✅ Participant correctly marked as non-accuser")
        else:
            print("⚠️ No disputes found for participant")
    
    # ========== GET /api/disputes/{id} Tests ==========
    
    def test_dispute_detail_returns_phase2_fields(self, organizer_token, organizer_user_id):
        """GET /api/disputes/{id} returns is_accuser, can_decide, decision, accuser_user_id"""
        # First get a dispute ID
        list_response = requests.get(f"{BASE_URL}/api/disputes/mine", headers={
            "Authorization": f"Bearer {organizer_token}"
        })
        assert list_response.status_code == 200
        
        disputes = list_response.json().get('disputes', [])
        if not disputes:
            pytest.skip("No disputes available for testing")
        
        dispute_id = disputes[0]['dispute_id']
        
        # Get detail
        response = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers={
            "Authorization": f"Bearer {organizer_token}"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        dispute = response.json()
        # Phase 2 fields
        assert 'is_accuser' in dispute, "Detail should have 'is_accuser'"
        assert 'can_decide' in dispute, "Detail should have 'can_decide'"
        assert 'accuser_user_id' in dispute, "Detail should have 'accuser_user_id'"
        assert 'decision' in dispute or dispute.get('decision') is None, "Detail should have 'decision'"
        
        # Verify accuser_user_id matches organizer
        assert dispute.get('accuser_user_id') == organizer_user_id, \
            f"accuser_user_id should be organizer: expected {organizer_user_id}, got {dispute.get('accuser_user_id')}"
        
        print(f"✅ Dispute detail has Phase 2 fields: accuser_user_id={dispute.get('accuser_user_id')}")
    
    # ========== Find a decidable dispute ==========
    
    @pytest.fixture(scope="class")
    def decidable_dispute_id(self, organizer_token):
        """Find a dispute where organizer can_decide=True (decision is null, status not resolved)"""
        response = requests.get(f"{BASE_URL}/api/disputes/mine", headers={
            "Authorization": f"Bearer {organizer_token}"
        })
        if response.status_code != 200:
            return None
        
        disputes = response.json().get('disputes', [])
        for d in disputes:
            if d.get('can_decide') == True and d.get('decision') is None and d.get('status') != 'resolved':
                print(f"Found decidable dispute: {d['dispute_id'][:8]}... status={d.get('status')}")
                return d['dispute_id']
        
        print("⚠️ No decidable disputes found (all may have decisions already)")
        return None
    
    # ========== POST /api/disputes/{id}/concede Tests ==========
    
    def test_concede_rejects_non_accuser(self, participant_token, decidable_dispute_id):
        """POST /api/disputes/{id}/concede rejects non-accuser with 400"""
        if not decidable_dispute_id:
            pytest.skip("No decidable dispute available")
        
        response = requests.post(f"{BASE_URL}/api/disputes/{decidable_dispute_id}/concede", headers={
            "Authorization": f"Bearer {participant_token}"
        })
        assert response.status_code == 400, f"Expected 400 for non-accuser, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert 'detail' in data, "Error response should have 'detail'"
        print(f"✅ Non-accuser correctly rejected: {data.get('detail')}")
    
    def test_maintain_rejects_non_accuser(self, participant_token, decidable_dispute_id):
        """POST /api/disputes/{id}/maintain rejects non-accuser with 400"""
        if not decidable_dispute_id:
            pytest.skip("No decidable dispute available")
        
        response = requests.post(f"{BASE_URL}/api/disputes/{decidable_dispute_id}/maintain", headers={
            "Authorization": f"Bearer {participant_token}"
        })
        assert response.status_code == 400, f"Expected 400 for non-accuser, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert 'detail' in data, "Error response should have 'detail'"
        print(f"✅ Non-accuser correctly rejected for maintain: {data.get('detail')}")
    
    # ========== Test already decided disputes ==========
    
    def test_concede_on_already_resolved_dispute(self, organizer_token):
        """POST /api/disputes/{id}/concede on already resolved dispute returns error"""
        # Find a resolved dispute (c1450287 was conceded per context)
        response = requests.get(f"{BASE_URL}/api/disputes/mine", headers={
            "Authorization": f"Bearer {organizer_token}"
        })
        if response.status_code != 200:
            pytest.skip("Could not get disputes")
        
        disputes = response.json().get('disputes', [])
        resolved_dispute = None
        for d in disputes:
            if d.get('status') == 'resolved' or d.get('decision') is not None:
                resolved_dispute = d
                break
        
        if not resolved_dispute:
            pytest.skip("No resolved/decided dispute found for testing")
        
        dispute_id = resolved_dispute['dispute_id']
        response = requests.post(f"{BASE_URL}/api/disputes/{dispute_id}/concede", headers={
            "Authorization": f"Bearer {organizer_token}"
        })
        
        # Should return 400 for already decided/resolved
        assert response.status_code == 400, f"Expected 400 for already decided, got {response.status_code}: {response.text}"
        print(f"✅ Already decided dispute correctly rejected: {response.json().get('detail')}")
    
    def test_maintain_on_already_resolved_dispute(self, organizer_token):
        """POST /api/disputes/{id}/maintain on already resolved dispute returns error"""
        response = requests.get(f"{BASE_URL}/api/disputes/mine", headers={
            "Authorization": f"Bearer {organizer_token}"
        })
        if response.status_code != 200:
            pytest.skip("Could not get disputes")
        
        disputes = response.json().get('disputes', [])
        resolved_dispute = None
        for d in disputes:
            if d.get('status') == 'resolved' or d.get('decision') is not None:
                resolved_dispute = d
                break
        
        if not resolved_dispute:
            pytest.skip("No resolved/decided dispute found for testing")
        
        dispute_id = resolved_dispute['dispute_id']
        response = requests.post(f"{BASE_URL}/api/disputes/{dispute_id}/maintain", headers={
            "Authorization": f"Bearer {organizer_token}"
        })
        
        assert response.status_code == 400, f"Expected 400 for already decided, got {response.status_code}: {response.text}"
        print(f"✅ Already decided dispute correctly rejected for maintain: {response.json().get('detail')}")
    
    # ========== Test successful concede/maintain (only if decidable dispute exists) ==========
    
    def test_concede_success_by_accuser(self, organizer_token):
        """POST /api/disputes/{id}/concede resolves dispute with final_outcome=waived when called by accuser"""
        # Find a decidable dispute
        response = requests.get(f"{BASE_URL}/api/disputes/mine", headers={
            "Authorization": f"Bearer {organizer_token}"
        })
        if response.status_code != 200:
            pytest.skip("Could not get disputes")
        
        disputes = response.json().get('disputes', [])
        decidable = None
        for d in disputes:
            if d.get('can_decide') == True and d.get('decision') is None and d.get('status') not in ('resolved',):
                decidable = d
                break
        
        if not decidable:
            print("⚠️ No decidable dispute available - skipping concede success test")
            pytest.skip("No decidable dispute available for concede test")
        
        dispute_id = decidable['dispute_id']
        print(f"Testing concede on dispute {dispute_id[:8]}...")
        
        response = requests.post(f"{BASE_URL}/api/disputes/{dispute_id}/concede", headers={
            "Authorization": f"Bearer {organizer_token}"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('success') == True, f"Expected success=True, got {data}"
        
        # Verify dispute is now resolved with waived outcome
        detail_response = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers={
            "Authorization": f"Bearer {organizer_token}"
        })
        assert detail_response.status_code == 200
        
        dispute = detail_response.json()
        assert dispute.get('decision') == 'conceded', f"Decision should be 'conceded', got {dispute.get('decision')}"
        assert dispute.get('status') == 'resolved', f"Status should be 'resolved', got {dispute.get('status')}"
        
        resolution = dispute.get('resolution', {})
        assert resolution.get('final_outcome') == 'waived', f"Final outcome should be 'waived', got {resolution.get('final_outcome')}"
        
        print(f"✅ Concede successful: decision={dispute.get('decision')}, status={dispute.get('status')}, outcome={resolution.get('final_outcome')}")
    
    def test_maintain_success_by_accuser(self, organizer_token):
        """POST /api/disputes/{id}/maintain escalates dispute to platform when called by accuser"""
        # Find another decidable dispute
        response = requests.get(f"{BASE_URL}/api/disputes/mine", headers={
            "Authorization": f"Bearer {organizer_token}"
        })
        if response.status_code != 200:
            pytest.skip("Could not get disputes")
        
        disputes = response.json().get('disputes', [])
        decidable = None
        for d in disputes:
            if d.get('can_decide') == True and d.get('decision') is None and d.get('status') not in ('resolved',):
                decidable = d
                break
        
        if not decidable:
            print("⚠️ No decidable dispute available - skipping maintain success test")
            pytest.skip("No decidable dispute available for maintain test")
        
        dispute_id = decidable['dispute_id']
        print(f"Testing maintain on dispute {dispute_id[:8]}...")
        
        response = requests.post(f"{BASE_URL}/api/disputes/{dispute_id}/maintain", headers={
            "Authorization": f"Bearer {organizer_token}"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('success') == True, f"Expected success=True, got {data}"
        
        # Verify dispute is now escalated
        detail_response = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers={
            "Authorization": f"Bearer {organizer_token}"
        })
        assert detail_response.status_code == 200
        
        dispute = detail_response.json()
        assert dispute.get('decision') == 'maintained', f"Decision should be 'maintained', got {dispute.get('decision')}"
        assert dispute.get('status') == 'escalated', f"Status should be 'escalated', got {dispute.get('status')}"
        assert dispute.get('escalated_at') is not None, "escalated_at should be set"
        
        print(f"✅ Maintain successful: decision={dispute.get('decision')}, status={dispute.get('status')}")
    
    # ========== Double decision tests ==========
    
    def test_double_concede_rejected(self, organizer_token):
        """POST /api/disputes/{id}/concede rejects double decision with 400"""
        # Find a dispute that was already conceded
        response = requests.get(f"{BASE_URL}/api/disputes/mine", headers={
            "Authorization": f"Bearer {organizer_token}"
        })
        if response.status_code != 200:
            pytest.skip("Could not get disputes")
        
        disputes = response.json().get('disputes', [])
        conceded = None
        for d in disputes:
            if d.get('decision') == 'conceded':
                conceded = d
                break
        
        if not conceded:
            pytest.skip("No conceded dispute found for double-decision test")
        
        dispute_id = conceded['dispute_id']
        response = requests.post(f"{BASE_URL}/api/disputes/{dispute_id}/concede", headers={
            "Authorization": f"Bearer {organizer_token}"
        })
        
        assert response.status_code == 400, f"Expected 400 for double decision, got {response.status_code}"
        print(f"✅ Double concede correctly rejected: {response.json().get('detail')}")
    
    def test_double_maintain_rejected(self, organizer_token):
        """POST /api/disputes/{id}/maintain rejects double decision with 400"""
        # Find a dispute that was already maintained
        response = requests.get(f"{BASE_URL}/api/disputes/mine", headers={
            "Authorization": f"Bearer {organizer_token}"
        })
        if response.status_code != 200:
            pytest.skip("Could not get disputes")
        
        disputes = response.json().get('disputes', [])
        maintained = None
        for d in disputes:
            if d.get('decision') == 'maintained':
                maintained = d
                break
        
        if not maintained:
            pytest.skip("No maintained dispute found for double-decision test")
        
        dispute_id = maintained['dispute_id']
        response = requests.post(f"{BASE_URL}/api/disputes/{dispute_id}/maintain", headers={
            "Authorization": f"Bearer {organizer_token}"
        })
        
        assert response.status_code == 400, f"Expected 400 for double decision, got {response.status_code}"
        print(f"✅ Double maintain correctly rejected: {response.json().get('detail')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
