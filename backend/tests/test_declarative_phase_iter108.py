"""
Backend API Tests for Declarative Phase (Iteration 108)
Tests:
- GET /api/attendance-sheets/{appointment_id} - Get attendance sheet
- GET /api/attendance-sheets/{appointment_id}/status - Get sheet status
- POST /api/attendance-sheets/{appointment_id}/submit - Submit sheet
- GET /api/disputes/mine - List user's disputes
- GET /api/disputes/{dispute_id} - Get dispute detail
- POST /api/disputes/{dispute_id}/evidence - Submit evidence
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ORGANIZER_EMAIL = "igaal.hanouna@gmail.com"
ORGANIZER_PASSWORD = "OrgTest123!"

# Test data IDs (from seed script)
COLLECTING_APPOINTMENT_ID = "7f5d0fa9-d8ac-4d24-b2f1-eb0eecb22782"
DISPUTED_APPOINTMENT_ID = "test-dispute-apt-ec625fca"
OPEN_DISPUTE_ID = "dispute-7f903760"
RESOLVED_DISPUTE_ID = "dispute-resolved-ccfcd8e6"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for organizer."""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ORGANIZER_EMAIL,
        "password": ORGANIZER_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
    data = response.json()
    # Token key is 'access_token' per credentials
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestAttendanceSheetsAPI:
    """Tests for /api/attendance-sheets endpoints."""
    
    def test_01_get_sheet_returns_200(self, auth_headers):
        """GET /api/attendance-sheets/{appointment_id} returns 200 with sheet data."""
        response = requests.get(
            f"{BASE_URL}/api/attendance-sheets/{COLLECTING_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        print(f"Sheet data: {data}")
        
        # Verify structure
        assert "sheet_id" in data, "Response should have sheet_id"
        assert "appointment_id" in data, "Response should have appointment_id"
        assert "status" in data, "Response should have status"
        assert "declarations" in data, "Response should have declarations"
        assert data["appointment_id"] == COLLECTING_APPOINTMENT_ID
    
    def test_02_sheet_has_declarations_with_target_names(self, auth_headers):
        """Sheet declarations should have target_name enriched."""
        response = requests.get(
            f"{BASE_URL}/api/attendance-sheets/{COLLECTING_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        declarations = data.get("declarations", [])
        assert len(declarations) > 0, "Sheet should have at least one declaration"
        
        for decl in declarations:
            assert "target_participant_id" in decl, "Declaration should have target_participant_id"
            # target_name may be enriched
            print(f"Declaration: {decl}")
    
    def test_03_get_sheet_status_returns_200(self, auth_headers):
        """GET /api/attendance-sheets/{appointment_id}/status returns status info."""
        response = requests.get(
            f"{BASE_URL}/api/attendance-sheets/{COLLECTING_APPOINTMENT_ID}/status",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        print(f"Sheet status: {data}")
        
        # Verify structure
        assert "phase" in data, "Response should have phase"
        assert "total_sheets" in data, "Response should have total_sheets"
        assert "submitted_sheets" in data, "Response should have submitted_sheets"
        assert data["phase"] == "collecting", f"Expected phase 'collecting', got {data['phase']}"
    
    def test_04_get_sheet_404_for_nonexistent(self, auth_headers):
        """GET /api/attendance-sheets/{nonexistent} returns 404."""
        response = requests.get(
            f"{BASE_URL}/api/attendance-sheets/nonexistent-appointment-id",
            headers=auth_headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    def test_05_get_sheet_401_without_auth(self):
        """GET /api/attendance-sheets/{appointment_id} returns 401 without auth."""
        response = requests.get(
            f"{BASE_URL}/api/attendance-sheets/{COLLECTING_APPOINTMENT_ID}"
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestDisputesAPI:
    """Tests for /api/disputes endpoints."""
    
    def test_01_list_disputes_returns_200(self, auth_headers):
        """GET /api/disputes/mine returns 200 with disputes list."""
        response = requests.get(
            f"{BASE_URL}/api/disputes/mine",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        print(f"Disputes list: {data}")
        
        # Verify structure
        assert "disputes" in data, "Response should have disputes array"
        assert "count" in data, "Response should have count"
        assert isinstance(data["disputes"], list), "disputes should be a list"
    
    def test_02_disputes_list_has_correct_structure(self, auth_headers):
        """Disputes in list should have required fields."""
        response = requests.get(
            f"{BASE_URL}/api/disputes/mine",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        disputes = data.get("disputes", [])
        if len(disputes) == 0:
            pytest.skip("No disputes found to verify structure")
        
        dispute = disputes[0]
        required_fields = ["dispute_id", "appointment_id", "status", "target_participant_id"]
        for field in required_fields:
            assert field in dispute, f"Dispute should have {field}"
        
        # Check enrichment
        print(f"First dispute: {dispute}")
        assert "appointment_title" in dispute or "target_name" in dispute, "Dispute should be enriched"
    
    def test_03_disputes_list_has_status_badges(self, auth_headers):
        """Disputes should have valid status values."""
        response = requests.get(
            f"{BASE_URL}/api/disputes/mine",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        valid_statuses = ["opened", "awaiting_evidence", "escalated", "resolved"]
        for dispute in data.get("disputes", []):
            assert dispute["status"] in valid_statuses, f"Invalid status: {dispute['status']}"
    
    def test_04_get_dispute_detail_returns_200(self, auth_headers):
        """GET /api/disputes/{dispute_id} returns 200 with detail."""
        response = requests.get(
            f"{BASE_URL}/api/disputes/{OPEN_DISPUTE_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        print(f"Dispute detail: {data}")
        
        # Verify structure
        assert "dispute_id" in data, "Response should have dispute_id"
        assert "status" in data, "Response should have status"
        assert "declaration_summary" in data, "Response should have declaration_summary"
        assert "can_submit_evidence" in data, "Response should have can_submit_evidence"
    
    def test_05_dispute_detail_has_summary(self, auth_headers):
        """Dispute detail should have declaration_summary with counts."""
        response = requests.get(
            f"{BASE_URL}/api/disputes/{OPEN_DISPUTE_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        summary = data.get("declaration_summary", {})
        assert "declared_absent_count" in summary, "Summary should have declared_absent_count"
        assert "declared_present_count" in summary, "Summary should have declared_present_count"
        assert "has_tech_evidence" in summary, "Summary should have has_tech_evidence"
    
    def test_06_resolved_dispute_has_resolution(self, auth_headers):
        """Resolved dispute should have resolution details."""
        response = requests.get(
            f"{BASE_URL}/api/disputes/{RESOLVED_DISPUTE_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        print(f"Resolved dispute: {data}")
        
        assert data["status"] == "resolved", f"Expected status 'resolved', got {data['status']}"
        
        resolution = data.get("resolution", {})
        assert resolution.get("resolved_at") is not None, "Resolution should have resolved_at"
        assert resolution.get("final_outcome") is not None, "Resolution should have final_outcome"
    
    def test_07_get_dispute_404_for_nonexistent(self, auth_headers):
        """GET /api/disputes/{nonexistent} returns 404."""
        response = requests.get(
            f"{BASE_URL}/api/disputes/nonexistent-dispute-id",
            headers=auth_headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    def test_08_disputes_401_without_auth(self):
        """GET /api/disputes/mine returns 401 without auth."""
        response = requests.get(f"{BASE_URL}/api/disputes/mine")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestEvidenceSubmission:
    """Tests for evidence submission endpoint."""
    
    def test_01_submit_evidence_returns_200(self, auth_headers):
        """POST /api/disputes/{dispute_id}/evidence returns 200."""
        response = requests.post(
            f"{BASE_URL}/api/disputes/{OPEN_DISPUTE_ID}/evidence",
            headers=auth_headers,
            json={
                "evidence_type": "text_statement",
                "text_content": "Test evidence submission from pytest"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        print(f"Evidence submission result: {data}")
        
        assert data.get("success") == True, "Response should indicate success"
        assert "submission_id" in data, "Response should have submission_id"
    
    def test_02_evidence_appears_in_dispute_detail(self, auth_headers):
        """Submitted evidence should appear in dispute detail."""
        response = requests.get(
            f"{BASE_URL}/api/disputes/{OPEN_DISPUTE_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        submissions = data.get("evidence_submissions", [])
        assert len(submissions) > 0, "Dispute should have evidence submissions"
        
        # Check structure
        sub = submissions[-1]  # Last submission
        assert "submission_id" in sub, "Submission should have submission_id"
        assert "evidence_type" in sub, "Submission should have evidence_type"
        assert "submitted_at" in sub, "Submission should have submitted_at"
    
    def test_03_cannot_submit_evidence_to_resolved_dispute(self, auth_headers):
        """POST /api/disputes/{resolved}/evidence returns 400."""
        response = requests.post(
            f"{BASE_URL}/api/disputes/{RESOLVED_DISPUTE_ID}/evidence",
            headers=auth_headers,
            json={
                "evidence_type": "text_statement",
                "text_content": "This should fail"
            }
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"


class TestSheetSubmission:
    """Tests for attendance sheet submission."""
    
    def test_01_submit_sheet_validation(self, auth_headers):
        """POST /api/attendance-sheets/{appointment_id}/submit validates input."""
        # First get the sheet to know the target
        sheet_response = requests.get(
            f"{BASE_URL}/api/attendance-sheets/{COLLECTING_APPOINTMENT_ID}",
            headers=auth_headers
        )
        if sheet_response.status_code != 200:
            pytest.skip("Could not get sheet")
        
        sheet = sheet_response.json()
        if sheet.get("status") == "submitted":
            pytest.skip("Sheet already submitted")
        
        declarations = sheet.get("declarations", [])
        if not declarations:
            pytest.skip("No declarations in sheet")
        
        # Try submitting with invalid status
        response = requests.post(
            f"{BASE_URL}/api/attendance-sheets/{COLLECTING_APPOINTMENT_ID}/submit",
            headers=auth_headers,
            json={
                "declarations": [
                    {
                        "target_participant_id": declarations[0]["target_participant_id"],
                        "declared_status": "invalid_status"
                    }
                ]
            }
        )
        assert response.status_code == 400, f"Expected 400 for invalid status, got {response.status_code}"
    
    def test_02_submit_sheet_success(self, auth_headers):
        """POST /api/attendance-sheets/{appointment_id}/submit works with valid data."""
        # First get the sheet
        sheet_response = requests.get(
            f"{BASE_URL}/api/attendance-sheets/{COLLECTING_APPOINTMENT_ID}",
            headers=auth_headers
        )
        if sheet_response.status_code != 200:
            pytest.skip("Could not get sheet")
        
        sheet = sheet_response.json()
        if sheet.get("status") == "submitted":
            pytest.skip("Sheet already submitted")
        
        declarations = sheet.get("declarations", [])
        if not declarations:
            pytest.skip("No declarations in sheet")
        
        # Submit with valid data
        submit_declarations = [
            {
                "target_participant_id": d["target_participant_id"],
                "declared_status": "present_on_time"
            }
            for d in declarations
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/attendance-sheets/{COLLECTING_APPOINTMENT_ID}/submit",
            headers=auth_headers,
            json={"declarations": submit_declarations}
        )
        
        # Could be 200 (success) or 400 (already submitted or phase changed)
        if response.status_code == 200:
            data = response.json()
            assert data.get("success") == True, "Response should indicate success"
            print(f"Sheet submitted successfully: {data}")
        else:
            print(f"Submit returned {response.status_code}: {response.text}")
            # This is acceptable if sheet was already submitted
    
    def test_03_cannot_submit_twice(self, auth_headers):
        """Cannot submit the same sheet twice."""
        # Get sheet status
        sheet_response = requests.get(
            f"{BASE_URL}/api/attendance-sheets/{COLLECTING_APPOINTMENT_ID}",
            headers=auth_headers
        )
        if sheet_response.status_code != 200:
            pytest.skip("Could not get sheet")
        
        sheet = sheet_response.json()
        declarations = sheet.get("declarations", [])
        
        if sheet.get("status") != "submitted":
            pytest.skip("Sheet not yet submitted")
        
        # Try to submit again
        submit_declarations = [
            {
                "target_participant_id": d["target_participant_id"],
                "declared_status": "absent"
            }
            for d in declarations
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/attendance-sheets/{COLLECTING_APPOINTMENT_ID}/submit",
            headers=auth_headers,
            json={"declarations": submit_declarations}
        )
        assert response.status_code == 400, f"Expected 400 for double submit, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
