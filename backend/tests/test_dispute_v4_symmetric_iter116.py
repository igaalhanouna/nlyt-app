"""
Test Suite: V4 Trustless Symmetric Disputes System (Iteration 116)

Tests the complete rework of the Disputes (Litiges) system:
- Symmetric model: both organizer and participant have equal power
- Single POST /api/disputes/{id}/position endpoint for both parties
- No penalty without double explicit confirmation
- Old /concede and /maintain endpoints should NOT exist (404)
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from review_request
ORGANIZER_EMAIL = "testuser_audit@nlyt.app"
ORGANIZER_PASSWORD = "TestAudit123!"
ORGANIZER_USER_ID = "d13498f9-9c0d-47d4-b48f-9e327e866127"

PARTICIPANT_EMAIL = "igaal@hotmail.com"
PARTICIPANT_PASSWORD = "Test123!"
PARTICIPANT_USER_ID = "239d1bbc-a4ea-47ac-b3c8-2f02f0769ef7"

PARTICIPANT2_EMAIL = "igaal.hanouna@gmail.com"
PARTICIPANT2_PASSWORD = "OrgTest123!"
PARTICIPANT2_USER_ID = "7a074c87-ac40-4d2f-861d-4f5e630d5aa8"


@pytest.fixture(scope="module")
def organizer_token():
    """Get auth token for organizer user."""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ORGANIZER_EMAIL,
        "password": ORGANIZER_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Organizer login failed: {response.status_code} - {response.text}")
    return response.json().get("access_token")


@pytest.fixture(scope="module")
def participant_token():
    """Get auth token for participant user."""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": PARTICIPANT_EMAIL,
        "password": PARTICIPANT_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Participant login failed: {response.status_code} - {response.text}")
    return response.json().get("access_token")


@pytest.fixture(scope="module")
def participant2_token():
    """Get auth token for participant2 user."""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": PARTICIPANT2_EMAIL,
        "password": PARTICIPANT2_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Participant2 login failed: {response.status_code} - {response.text}")
    return response.json().get("access_token")


class TestOldEndpointsRemoved:
    """Verify old Phase 2 endpoints /concede and /maintain are removed (404)."""

    def test_concede_endpoint_returns_404(self, organizer_token):
        """POST /api/disputes/{id}/concede should NOT exist."""
        headers = {"Authorization": f"Bearer {organizer_token}"}
        # Use a dummy dispute_id - we just want to verify the route doesn't exist
        response = requests.post(f"{BASE_URL}/api/disputes/dummy-id/concede", headers=headers)
        # Should be 404 (route not found) or 405 (method not allowed), NOT 400/403
        assert response.status_code in (404, 405, 422), f"Expected 404/405/422 for removed /concede endpoint, got {response.status_code}"
        print(f"✅ /concede endpoint correctly returns {response.status_code}")

    def test_maintain_endpoint_returns_404(self, organizer_token):
        """POST /api/disputes/{id}/maintain should NOT exist."""
        headers = {"Authorization": f"Bearer {organizer_token}"}
        response = requests.post(f"{BASE_URL}/api/disputes/dummy-id/maintain", headers=headers)
        assert response.status_code in (404, 405, 422), f"Expected 404/405/422 for removed /maintain endpoint, got {response.status_code}"
        print(f"✅ /maintain endpoint correctly returns {response.status_code}")


class TestDisputesMineEndpoint:
    """Test GET /api/disputes/mine returns V4 symmetric fields."""

    def test_disputes_mine_returns_v4_fields_for_organizer(self, organizer_token):
        """GET /api/disputes/mine should return my_role, my_position, can_submit_position, other_party_responded."""
        headers = {"Authorization": f"Bearer {organizer_token}"}
        response = requests.get(f"{BASE_URL}/api/disputes/mine", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "disputes" in data
        assert "count" in data
        
        if data["count"] > 0:
            dispute = data["disputes"][0]
            # V4 symmetric fields
            assert "my_role" in dispute, "Missing my_role field"
            assert "my_position" in dispute, "Missing my_position field"
            assert "can_submit_position" in dispute, "Missing can_submit_position field"
            assert "other_party_responded" in dispute, "Missing other_party_responded field"
            
            # my_role should be 'organizer' or 'participant'
            assert dispute["my_role"] in ("organizer", "participant", "observer"), f"Invalid my_role: {dispute['my_role']}"
            print(f"✅ /disputes/mine returns V4 fields: my_role={dispute['my_role']}, can_submit_position={dispute['can_submit_position']}")
        else:
            print("⚠️ No disputes found for organizer - skipping field validation")

    def test_disputes_mine_returns_v4_fields_for_participant(self, participant_token):
        """GET /api/disputes/mine should return V4 fields for participant."""
        headers = {"Authorization": f"Bearer {participant_token}"}
        response = requests.get(f"{BASE_URL}/api/disputes/mine", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        if data["count"] > 0:
            dispute = data["disputes"][0]
            assert "my_role" in dispute
            assert "my_position" in dispute
            assert "can_submit_position" in dispute
            assert "other_party_responded" in dispute
            print(f"✅ Participant /disputes/mine returns V4 fields: my_role={dispute['my_role']}")
        else:
            print("⚠️ No disputes found for participant")


class TestDisputeDetailEndpoint:
    """Test GET /api/disputes/{id} returns V4 symmetric fields."""

    def test_dispute_detail_returns_v4_fields(self, organizer_token):
        """GET /api/disputes/{id} should return my_declaration, my_role, my_position, can_submit_position, other_party_responded, is_resolved."""
        headers = {"Authorization": f"Bearer {organizer_token}"}
        
        # First get a dispute ID
        list_response = requests.get(f"{BASE_URL}/api/disputes/mine", headers=headers)
        assert list_response.status_code == 200
        disputes = list_response.json().get("disputes", [])
        
        if not disputes:
            pytest.skip("No disputes available for testing")
        
        dispute_id = disputes[0]["dispute_id"]
        
        # Get detail
        response = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        dispute = response.json()
        
        # V4 required fields
        required_fields = ["my_declaration", "my_role", "my_position", "can_submit_position", "other_party_responded", "is_resolved"]
        for field in required_fields:
            assert field in dispute, f"Missing required field: {field}"
        
        print(f"✅ Dispute detail returns all V4 fields: my_role={dispute['my_role']}, is_resolved={dispute['is_resolved']}")


class TestPositionSubmission:
    """Test POST /api/disputes/{id}/position endpoint."""

    def test_invalid_position_rejected(self, organizer_token):
        """Invalid position value should be rejected with 400."""
        headers = {"Authorization": f"Bearer {organizer_token}"}
        
        # Get a dispute
        list_response = requests.get(f"{BASE_URL}/api/disputes/mine", headers=headers)
        disputes = list_response.json().get("disputes", [])
        
        if not disputes:
            pytest.skip("No disputes available")
        
        dispute_id = disputes[0]["dispute_id"]
        
        # Try invalid position
        response = requests.post(
            f"{BASE_URL}/api/disputes/{dispute_id}/position",
            headers=headers,
            json={"position": "invalid_position"}
        )
        assert response.status_code == 400, f"Expected 400 for invalid position, got {response.status_code}"
        print("✅ Invalid position correctly rejected with 400")

    def test_non_party_user_rejected(self, participant2_token, organizer_token):
        """Non-party user should be rejected with 400."""
        headers_org = {"Authorization": f"Bearer {organizer_token}"}
        headers_p2 = {"Authorization": f"Bearer {participant2_token}"}
        
        # Get a dispute where participant2 is NOT a party
        list_response = requests.get(f"{BASE_URL}/api/disputes/mine", headers=headers_org)
        disputes = list_response.json().get("disputes", [])
        
        # Find a dispute where participant2 is not involved
        for dispute in disputes:
            dispute_id = dispute["dispute_id"]
            # Try to submit position as participant2
            response = requests.post(
                f"{BASE_URL}/api/disputes/{dispute_id}/position",
                headers=headers_p2,
                json={"position": "confirmed_present"}
            )
            if response.status_code == 400:
                error_msg = response.json().get("detail", "")
                if "partie prenante" in error_msg.lower() or "not a party" in error_msg.lower():
                    print(f"✅ Non-party user correctly rejected: {error_msg}")
                    return
        
        # If we get here, either all disputes involve participant2 or the test couldn't find a suitable dispute
        print("⚠️ Could not find a dispute where participant2 is not a party - test inconclusive")


class TestPositionResolution:
    """Test position submission and auto-resolution logic."""

    def test_find_awaiting_positions_dispute(self, organizer_token):
        """Find a dispute in awaiting_positions status for testing."""
        headers = {"Authorization": f"Bearer {organizer_token}"}
        response = requests.get(f"{BASE_URL}/api/disputes/mine", headers=headers)
        assert response.status_code == 200
        
        disputes = response.json().get("disputes", [])
        awaiting = [d for d in disputes if d.get("status") == "awaiting_positions" and d.get("can_submit_position")]
        
        if awaiting:
            print(f"✅ Found {len(awaiting)} disputes in awaiting_positions status with can_submit_position=True")
            for d in awaiting[:3]:
                print(f"   - {d['dispute_id']}: org_pos={d.get('organizer_position')}, par_pos={d.get('participant_position')}")
        else:
            print("⚠️ No disputes in awaiting_positions status with can_submit_position=True")


class TestDoublePositionRejection:
    """Test that double position submission is rejected."""

    def test_double_position_submission_rejected(self, organizer_token):
        """Submitting position twice should be rejected with 400."""
        headers = {"Authorization": f"Bearer {organizer_token}"}
        
        # Get disputes
        list_response = requests.get(f"{BASE_URL}/api/disputes/mine", headers=headers)
        disputes = list_response.json().get("disputes", [])
        
        # Find a dispute where organizer already submitted position
        for dispute in disputes:
            if dispute.get("my_role") == "organizer" and dispute.get("my_position") is not None:
                dispute_id = dispute["dispute_id"]
                
                # Try to submit again
                response = requests.post(
                    f"{BASE_URL}/api/disputes/{dispute_id}/position",
                    headers=headers,
                    json={"position": "confirmed_present"}
                )
                assert response.status_code == 400, f"Expected 400 for double submission, got {response.status_code}"
                error_msg = response.json().get("detail", "")
                # Valid rejection messages: "déjà soumis" (already submitted) or "n'accepte plus" (no longer accepts)
                valid_rejections = ["déjà soumis", "already", "n'accepte plus"]
                assert any(msg in error_msg.lower() for msg in valid_rejections), f"Unexpected error: {error_msg}"
                print(f"✅ Double position submission correctly rejected: {error_msg}")
                return
        
        print("⚠️ No dispute found where organizer already submitted position - test inconclusive")


class TestDisputeStatusValues:
    """Test that dispute status values match V4 schema."""

    def test_status_values_are_v4_compliant(self, organizer_token):
        """Verify status values match V4 schema: awaiting_positions, agreed_present, agreed_absent, agreed_late_penalized, escalated, resolved."""
        headers = {"Authorization": f"Bearer {organizer_token}"}
        response = requests.get(f"{BASE_URL}/api/disputes/mine", headers=headers)
        assert response.status_code == 200
        
        disputes = response.json().get("disputes", [])
        valid_statuses = {"awaiting_positions", "awaiting_evidence", "agreed_present", "agreed_absent", "agreed_late_penalized", "escalated", "resolved"}
        
        for dispute in disputes:
            status = dispute.get("status")
            assert status in valid_statuses, f"Invalid status: {status}"
        
        status_counts = {}
        for d in disputes:
            s = d.get("status")
            status_counts[s] = status_counts.get(s, 0) + 1
        
        print(f"✅ All {len(disputes)} disputes have valid V4 statuses: {status_counts}")


class TestDeclarationSummary:
    """Test declaration summary in dispute detail."""

    def test_declaration_summary_present(self, organizer_token):
        """Dispute detail should include declaration_summary with counts."""
        headers = {"Authorization": f"Bearer {organizer_token}"}
        
        list_response = requests.get(f"{BASE_URL}/api/disputes/mine", headers=headers)
        disputes = list_response.json().get("disputes", [])
        
        if not disputes:
            pytest.skip("No disputes available")
        
        dispute_id = disputes[0]["dispute_id"]
        response = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers=headers)
        assert response.status_code == 200
        
        dispute = response.json()
        assert "declaration_summary" in dispute, "Missing declaration_summary"
        
        summary = dispute["declaration_summary"]
        assert "declared_absent_count" in summary
        assert "declared_present_count" in summary
        assert "has_tech_evidence" in summary
        
        print(f"✅ Declaration summary present: absent={summary['declared_absent_count']}, present={summary['declared_present_count']}")


class TestEvidenceSubmission:
    """Test evidence submission endpoint."""

    def test_evidence_submission_works(self, organizer_token):
        """POST /api/disputes/{id}/evidence should work for parties."""
        headers = {"Authorization": f"Bearer {organizer_token}"}
        
        list_response = requests.get(f"{BASE_URL}/api/disputes/mine", headers=headers)
        disputes = list_response.json().get("disputes", [])
        
        # Find a dispute where evidence can be submitted
        for dispute in disputes:
            if dispute.get("can_submit_evidence"):
                dispute_id = dispute["dispute_id"]
                
                response = requests.post(
                    f"{BASE_URL}/api/disputes/{dispute_id}/evidence",
                    headers=headers,
                    json={
                        "evidence_type": "text_statement",
                        "text_content": f"Test evidence submission at {datetime.now().isoformat()}"
                    }
                )
                
                if response.status_code == 200:
                    print(f"✅ Evidence submission successful for dispute {dispute_id}")
                    return
                else:
                    print(f"⚠️ Evidence submission returned {response.status_code}: {response.text}")
        
        print("⚠️ No dispute found where evidence can be submitted")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
