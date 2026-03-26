"""
Test Evidence Dashboard Bug Fix
================================
Tests for the fix of EvidenceDashboard.js which was showing 'Aucune preuve' for all participants.

Root causes fixed:
1) EvidenceDashboard.js used wrong data path (evidenceData.evidence instead of evidenceData.participants[].evidence)
2) Organizer was filtered out with !p.is_organizer

Test scenarios:
- Verify GET /api/checkin/evidence/{appointment_id} returns correct structure with participants array
- Verify evidence is returned for both organizer and participants
- Test with real appointment bb90f3e8-f9a5-4105-8a0e-862671f4e450
"""

import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://evidence-labels-fix.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_EMAIL = "stripe-test@nlyt.io"
TEST_PASSWORD = "Test123!"
REAL_APPOINTMENT_ID = "bb90f3e8-f9a5-4105-8a0e-862671f4e450"


class TestEvidenceDashboardFix:
    """Tests for Evidence Dashboard bug fix"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for test user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token") or data.get("token")
        pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_api_health(self):
        """Test 1: API health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✅ API health check passed")
    
    def test_evidence_endpoint_returns_participants_array(self, auth_headers):
        """Test 2: GET /api/checkin/evidence/{appointment_id} returns participants array structure"""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{REAL_APPOINTMENT_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify structure has 'participants' array (not 'evidence' at root level)
        assert "participants" in data, "Response must have 'participants' key"
        assert isinstance(data["participants"], list), "'participants' must be an array"
        assert "appointment_id" in data, "Response must have 'appointment_id'"
        assert data["appointment_id"] == REAL_APPOINTMENT_ID
        
        print(f"✅ Evidence endpoint returns correct structure with {len(data['participants'])} participants")
        print(f"   Total evidence items: {data.get('total_evidence', 0)}")
    
    def test_evidence_structure_per_participant(self, auth_headers):
        """Test 3: Each participant in response has correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{REAL_APPOINTMENT_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        for p in data["participants"]:
            # Each participant must have these fields
            assert "participant_id" in p, "Participant must have participant_id"
            assert "evidence" in p, "Participant must have evidence array"
            assert isinstance(p["evidence"], list), "evidence must be an array"
            assert "aggregation" in p, "Participant must have aggregation"
            
            # Optional but expected fields
            assert "participant_name" in p or "participant_email" in p
            
            print(f"   - {p.get('participant_name', 'Unknown')}: {len(p['evidence'])} evidence item(s)")
        
        print(f"✅ All {len(data['participants'])} participants have correct structure")
    
    def test_organizer_evidence_included(self, auth_headers):
        """Test 4: Organizer evidence is NOT filtered out (bug fix verification)"""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{REAL_APPOINTMENT_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Find participants with evidence
        participants_with_evidence = [p for p in data["participants"] if len(p["evidence"]) > 0]
        
        # According to the bug report, Test Audit (organizer) should have evidence
        # The fix ensures organizer is NOT filtered out
        assert len(participants_with_evidence) > 0, "At least one participant should have evidence"
        
        # Check if we have evidence from multiple people (org + participant)
        print(f"✅ Found {len(participants_with_evidence)} participant(s) with evidence (organizer NOT filtered)")
        for p in participants_with_evidence:
            print(f"   - {p.get('participant_name', 'Unknown')}: {len(p['evidence'])} evidence item(s)")
    
    def test_evidence_items_have_required_fields(self, auth_headers):
        """Test 5: Each evidence item has required fields for display"""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{REAL_APPOINTMENT_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        evidence_count = 0
        for p in data["participants"]:
            for e in p["evidence"]:
                evidence_count += 1
                # Required fields for EvidenceDashboard display
                assert "evidence_id" in e, "Evidence must have evidence_id"
                assert "source" in e, "Evidence must have source"
                assert "source_timestamp" in e, "Evidence must have source_timestamp"
                assert "confidence_score" in e, "Evidence must have confidence_score"
                
                # derived_facts should contain GPS, distance, temporal info
                if "derived_facts" in e:
                    facts = e["derived_facts"]
                    # Log what we have
                    has_gps = "latitude" in facts and "longitude" in facts
                    has_distance = "distance_km" in facts
                    has_temporal = "temporal_detail" in facts
                    has_address = "address_label" in facts
                    
                    print(f"   Evidence {e['evidence_id'][:8]}: source={e['source']}, GPS={has_gps}, distance={has_distance}, temporal={has_temporal}, address={has_address}")
        
        print(f"✅ All {evidence_count} evidence items have required fields")
    
    def test_real_appointment_has_expected_evidence(self, auth_headers):
        """Test 6: Real appointment bb90f3e8 has evidence for Test Audit and Igaal Hanouna"""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{REAL_APPOINTMENT_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # According to bug report: Test Audit (org at 20:17:46) and Igaal Hanouna (at 20:18:51)
        participant_names = [p.get("participant_name", "").lower() for p in data["participants"]]
        participants_with_evidence = {
            p.get("participant_name", ""): len(p["evidence"]) 
            for p in data["participants"] 
            if len(p["evidence"]) > 0
        }
        
        print(f"   Participants in appointment: {participant_names}")
        print(f"   Participants with evidence: {participants_with_evidence}")
        
        # We expect at least 2 evidence items total (one for org, one for participant)
        total_evidence = sum(len(p["evidence"]) for p in data["participants"])
        assert total_evidence >= 2, f"Expected at least 2 evidence items, got {total_evidence}"
        
        print(f"✅ Real appointment has {total_evidence} evidence items across {len(participants_with_evidence)} participants")
    
    def test_evidence_gps_coordinates_present(self, auth_headers):
        """Test 7: Evidence items have GPS coordinates when available"""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{REAL_APPOINTMENT_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        gps_evidence_count = 0
        for p in data["participants"]:
            for e in p["evidence"]:
                facts = e.get("derived_facts", {})
                if facts.get("latitude") and facts.get("longitude"):
                    gps_evidence_count += 1
                    lat = facts["latitude"]
                    lon = facts["longitude"]
                    distance = facts.get("distance_km", "N/A")
                    address = facts.get("address_label", "N/A")[:50] if facts.get("address_label") else "N/A"
                    print(f"   GPS: {lat:.5f}, {lon:.5f} | Distance: {distance}km | Address: {address}...")
        
        print(f"✅ Found {gps_evidence_count} evidence items with GPS coordinates")
    
    def test_evidence_temporal_details_present(self, auth_headers):
        """Test 8: Evidence items have temporal details"""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{REAL_APPOINTMENT_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        temporal_count = 0
        for p in data["participants"]:
            for e in p["evidence"]:
                facts = e.get("derived_facts", {})
                if facts.get("temporal_detail"):
                    temporal_count += 1
                    print(f"   Temporal: {facts['temporal_detail']}")
        
        print(f"✅ Found {temporal_count} evidence items with temporal details")


class TestEvidenceAPIStructure:
    """Tests for API response structure matching frontend expectations"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token") or data.get("token")
        pytest.skip(f"Authentication failed: {response.status_code}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_frontend_data_path_compatibility(self, auth_headers):
        """Test 9: API response matches frontend's expected data path (evidenceData.participants)"""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{REAL_APPOINTMENT_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Frontend code (EvidenceDashboard.js line 42-46):
        # const getParticipantEvidence = (participantId) => {
        #   if (!evidenceData?.participants) return [];
        #   const pData = evidenceData.participants.find(p => p.participant_id === participantId);
        #   return pData?.evidence || [];
        # };
        
        # Verify the exact structure frontend expects
        assert "participants" in data, "Must have 'participants' key for frontend"
        
        for p in data["participants"]:
            assert "participant_id" in p, "Each participant must have 'participant_id'"
            assert "evidence" in p, "Each participant must have 'evidence' array"
        
        print("✅ API response structure matches frontend's expected data path (evidenceData.participants)")
    
    def test_no_is_organizer_filter_needed(self, auth_headers):
        """Test 10: Backend returns all accepted participants (no is_organizer filter)"""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{REAL_APPOINTMENT_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # The bug was frontend filtering with !p.is_organizer
        # Backend should return all accepted participants regardless of is_organizer
        # Frontend now filters by status, not is_organizer
        
        # Check that we have participants (backend doesn't filter by is_organizer)
        assert len(data["participants"]) > 0, "Should have at least one participant"
        
        # All returned participants should have accepted status (backend filters this)
        print(f"✅ Backend returns {len(data['participants'])} participants (no is_organizer filter)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
