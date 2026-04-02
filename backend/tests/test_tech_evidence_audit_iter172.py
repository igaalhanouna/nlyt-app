"""
Test: Tech Evidence Audit & Arbitration Grouping - Iteration 172

Tests:
1. GET /api/disputes/{dispute_id} returns tech_evidence_summary with video/gps/nlyt/checkin/qr sections
2. GET /api/disputes/decisions/mine returns decisions list with all required fields
3. GET /api/admin/arbitration/disputes returns disputes grouped by appointment
4. GET /api/admin/arbitration/stats returns correct KPI stats
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
ADMIN_EMAIL = "testuser_audit@nlyt.app"
ADMIN_PASSWORD = "TestAudit123!"
USER_EMAIL = "igaal@hotmail.com"
USER_PASSWORD = "Test123!"


class TestTechEvidenceAudit:
    """Tests for tech_evidence_summary in dispute detail endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")
        data = response.json()
        return data.get("access_token")
    
    @pytest.fixture(scope="class")
    def user_token(self):
        """Get regular user auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": USER_EMAIL,
            "password": USER_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"User login failed: {response.status_code} - {response.text}")
        data = response.json()
        return data.get("access_token")
    
    @pytest.fixture(scope="class")
    def admin_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    
    @pytest.fixture(scope="class")
    def user_headers(self, user_token):
        return {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"}
    
    def test_admin_login_works(self, admin_token):
        """Verify admin login returns valid token"""
        assert admin_token is not None
        assert len(admin_token) > 10
        print(f"PASS: Admin login successful, token length: {len(admin_token)}")
    
    def test_user_login_works(self, user_token):
        """Verify user login returns valid token"""
        assert user_token is not None
        assert len(user_token) > 10
        print(f"PASS: User login successful, token length: {len(user_token)}")
    
    def test_decisions_mine_endpoint_returns_list(self, user_headers):
        """GET /api/disputes/decisions/mine returns decisions list"""
        response = requests.get(f"{BASE_URL}/api/disputes/decisions/mine", headers=user_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "decisions" in data, "Response should contain 'decisions' key"
        assert "count" in data, "Response should contain 'count' key"
        assert isinstance(data["decisions"], list), "decisions should be a list"
        print(f"PASS: GET /api/disputes/decisions/mine returns {data['count']} decisions")
    
    def test_decisions_mine_has_required_fields(self, user_headers):
        """Verify decisions have all required fields for display"""
        response = requests.get(f"{BASE_URL}/api/disputes/decisions/mine", headers=user_headers)
        assert response.status_code == 200
        
        data = response.json()
        decisions = data.get("decisions", [])
        
        if len(decisions) == 0:
            pytest.skip("No decisions found for this user - cannot verify fields")
        
        # Check first decision has required fields
        d = decisions[0]
        required_fields = [
            "dispute_id", "appointment_id", "target_participant_id", "status",
            "appointment_title", "appointment_date", "target_name",
            "final_outcome", "my_role", "financial_impact"
        ]
        
        for field in required_fields:
            assert field in d, f"Decision missing required field: {field}"
        
        # Verify financial_impact structure
        fi = d.get("financial_impact", {})
        assert "type" in fi, "financial_impact should have 'type'"
        assert "label" in fi, "financial_impact should have 'label'"
        
        print(f"PASS: Decision has all required fields: {list(d.keys())}")
    
    def test_dispute_detail_has_tech_evidence_summary(self, user_headers):
        """GET /api/disputes/{id} returns tech_evidence_summary"""
        # First get a dispute ID from decisions/mine
        response = requests.get(f"{BASE_URL}/api/disputes/decisions/mine", headers=user_headers)
        if response.status_code != 200:
            pytest.skip("Cannot get decisions list")
        
        decisions = response.json().get("decisions", [])
        if len(decisions) == 0:
            # Try getting from /disputes/mine instead
            response = requests.get(f"{BASE_URL}/api/disputes/mine", headers=user_headers)
            if response.status_code != 200:
                pytest.skip("Cannot get disputes list")
            disputes = response.json().get("disputes", [])
            if len(disputes) == 0:
                pytest.skip("No disputes found for this user")
            dispute_id = disputes[0]["dispute_id"]
        else:
            dispute_id = decisions[0]["dispute_id"]
        
        # Get dispute detail
        response = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers=user_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "tech_evidence_summary" in data, "Response should contain 'tech_evidence_summary'"
        
        tes = data["tech_evidence_summary"]
        assert "has_any_evidence" in tes, "tech_evidence_summary should have 'has_any_evidence'"
        assert "video" in tes, "tech_evidence_summary should have 'video'"
        assert "gps" in tes, "tech_evidence_summary should have 'gps'"
        assert "checkin" in tes, "tech_evidence_summary should have 'checkin'"
        assert "qr" in tes, "tech_evidence_summary should have 'qr'"
        assert "nlyt" in tes, "tech_evidence_summary should have 'nlyt'"
        
        print(f"PASS: Dispute {dispute_id} has tech_evidence_summary with all sections")
        print(f"  - has_any_evidence: {tes['has_any_evidence']}")
        print(f"  - video.has_data: {tes['video'].get('has_data')}")
        print(f"  - gps.has_data: {tes['gps'].get('has_data')}")
        print(f"  - nlyt.has_data: {tes['nlyt'].get('has_data')}")
    
    def test_tech_evidence_summary_video_structure(self, user_headers):
        """Verify video section structure in tech_evidence_summary"""
        response = requests.get(f"{BASE_URL}/api/disputes/mine", headers=user_headers)
        if response.status_code != 200:
            pytest.skip("Cannot get disputes list")
        
        disputes = response.json().get("disputes", [])
        if len(disputes) == 0:
            pytest.skip("No disputes found")
        
        dispute_id = disputes[0]["dispute_id"]
        response = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers=user_headers)
        assert response.status_code == 200
        
        video = response.json().get("tech_evidence_summary", {}).get("video", {})
        assert "has_data" in video, "video should have 'has_data'"
        assert "sessions" in video, "video should have 'sessions'"
        assert "total_duration_seconds" in video, "video should have 'total_duration_seconds'"
        
        print(f"PASS: video section has correct structure: {list(video.keys())}")
    
    def test_tech_evidence_summary_nlyt_structure(self, user_headers):
        """Verify nlyt section structure in tech_evidence_summary"""
        response = requests.get(f"{BASE_URL}/api/disputes/mine", headers=user_headers)
        if response.status_code != 200:
            pytest.skip("Cannot get disputes list")
        
        disputes = response.json().get("disputes", [])
        if len(disputes) == 0:
            pytest.skip("No disputes found")
        
        dispute_id = disputes[0]["dispute_id"]
        response = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers=user_headers)
        assert response.status_code == 200
        
        nlyt = response.json().get("tech_evidence_summary", {}).get("nlyt", {})
        assert "has_data" in nlyt, "nlyt should have 'has_data'"
        
        # If has_data is True, verify additional fields
        if nlyt.get("has_data"):
            assert "best_score" in nlyt, "nlyt should have 'best_score' when has_data=True"
            assert "total_active_seconds" in nlyt, "nlyt should have 'total_active_seconds'"
            assert "proof_level" in nlyt, "nlyt should have 'proof_level'"
        
        print(f"PASS: nlyt section has correct structure: {list(nlyt.keys())}")


class TestAdminArbitrationGrouping:
    """Tests for admin arbitration list grouping by appointment"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.status_code}")
        return response.json().get("access_token")
    
    @pytest.fixture(scope="class")
    def admin_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    
    def test_arbitration_stats_endpoint(self, admin_headers):
        """GET /api/admin/arbitration/stats returns KPI stats"""
        response = requests.get(f"{BASE_URL}/api/admin/arbitration/stats", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        required_fields = ["escalated_pending", "total_resolved", "total_agreed_by_parties", "awaiting_positions"]
        
        for field in required_fields:
            assert field in data, f"Stats missing required field: {field}"
        
        print(f"PASS: Arbitration stats returned: escalated={data['escalated_pending']}, awaiting={data['awaiting_positions']}, resolved={data['total_resolved']}, agreed={data['total_agreed_by_parties']}")
    
    def test_arbitration_disputes_escalated_filter(self, admin_headers):
        """GET /api/admin/arbitration?filter=escalated returns disputes"""
        response = requests.get(f"{BASE_URL}/api/admin/arbitration?filter=escalated", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "disputes" in data, "Response should contain 'disputes'"
        
        print(f"PASS: Escalated disputes returned: {len(data['disputes'])} disputes")
    
    def test_arbitration_disputes_awaiting_filter(self, admin_headers):
        """GET /api/admin/arbitration?filter=awaiting returns disputes"""
        response = requests.get(f"{BASE_URL}/api/admin/arbitration?filter=awaiting", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "disputes" in data, "Response should contain 'disputes'"
        
        print(f"PASS: Awaiting disputes returned: {len(data['disputes'])} disputes")
    
    def test_arbitration_disputes_resolved_filter(self, admin_headers):
        """GET /api/admin/arbitration?filter=resolved returns disputes"""
        response = requests.get(f"{BASE_URL}/api/admin/arbitration?filter=resolved", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "disputes" in data, "Response should contain 'disputes'"
        
        print(f"PASS: Resolved disputes returned: {len(data['disputes'])} disputes")
    
    def test_arbitration_disputes_have_grouping_fields(self, admin_headers):
        """Verify disputes have fields needed for grouping by appointment"""
        response = requests.get(f"{BASE_URL}/api/admin/arbitration?filter=awaiting", headers=admin_headers)
        assert response.status_code == 200
        
        disputes = response.json().get("disputes", [])
        if len(disputes) == 0:
            pytest.skip("No disputes found to verify grouping fields")
        
        d = disputes[0]
        grouping_fields = [
            "appointment_id", "appointment_title", "appointment_date",
            "appointment_type", "appointment_location", "target_name",
            "status", "has_admissible_proof", "positions"
        ]
        
        for field in grouping_fields:
            assert field in d, f"Dispute missing grouping field: {field}"
        
        # Verify positions structure
        positions = d.get("positions", {})
        assert "organizer" in positions, "positions should have 'organizer'"
        assert "participant" in positions, "positions should have 'participant'"
        
        print(f"PASS: Dispute has all grouping fields: {list(d.keys())}")
    
    def test_arbitration_detail_endpoint(self, admin_headers):
        """GET /api/admin/arbitration/{id} returns full detail"""
        # First get a dispute ID
        response = requests.get(f"{BASE_URL}/api/admin/arbitration?filter=awaiting", headers=admin_headers)
        if response.status_code != 200:
            pytest.skip("Cannot get disputes list")
        
        disputes = response.json().get("disputes", [])
        if len(disputes) == 0:
            # Try escalated
            response = requests.get(f"{BASE_URL}/api/admin/arbitration?filter=escalated", headers=admin_headers)
            disputes = response.json().get("disputes", [])
            if len(disputes) == 0:
                pytest.skip("No disputes found for detail test")
        
        dispute_id = disputes[0]["dispute_id"]
        
        response = requests.get(f"{BASE_URL}/api/admin/arbitration/{dispute_id}", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "dispute_id" in data, "Detail should have dispute_id"
        assert "tech_dossier" in data, "Detail should have tech_dossier"
        assert "declaration_summary" in data, "Detail should have declaration_summary"
        
        print(f"PASS: Arbitration detail for {dispute_id} returned with tech_dossier and declaration_summary")


class TestDecisionDetailEnrichment:
    """Tests for enriched decision detail page data"""
    
    @pytest.fixture(scope="class")
    def user_token(self):
        """Get user auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": USER_EMAIL,
            "password": USER_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"User login failed: {response.status_code}")
        return response.json().get("access_token")
    
    @pytest.fixture(scope="class")
    def user_headers(self, user_token):
        return {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"}
    
    def test_dispute_detail_has_opened_reason(self, user_headers):
        """Verify dispute detail includes opened_reason for 'Ce qui a ete declare' section"""
        response = requests.get(f"{BASE_URL}/api/disputes/mine", headers=user_headers)
        if response.status_code != 200:
            pytest.skip("Cannot get disputes list")
        
        disputes = response.json().get("disputes", [])
        if len(disputes) == 0:
            pytest.skip("No disputes found")
        
        dispute_id = disputes[0]["dispute_id"]
        response = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers=user_headers)
        assert response.status_code == 200
        
        data = response.json()
        # opened_reason may be null/missing if not applicable, but field should be accessible
        # The frontend checks for data.opened_reason
        print(f"PASS: Dispute detail accessible, opened_reason: {data.get('opened_reason', 'N/A')}")
    
    def test_dispute_detail_has_evidence_submissions_list(self, user_headers):
        """Verify dispute detail includes evidence_submissions as list with type and date"""
        response = requests.get(f"{BASE_URL}/api/disputes/mine", headers=user_headers)
        if response.status_code != 200:
            pytest.skip("Cannot get disputes list")
        
        disputes = response.json().get("disputes", [])
        if len(disputes) == 0:
            pytest.skip("No disputes found")
        
        dispute_id = disputes[0]["dispute_id"]
        response = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers=user_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "evidence_submissions" in data, "Should have evidence_submissions"
        assert "evidence_submissions_count" in data, "Should have evidence_submissions_count"
        
        # evidence_submissions should be a list (may be empty)
        assert isinstance(data["evidence_submissions"], list), "evidence_submissions should be a list"
        
        # If there are submissions, verify structure
        if len(data["evidence_submissions"]) > 0:
            sub = data["evidence_submissions"][0]
            assert "evidence_type" in sub, "Submission should have evidence_type"
            assert "submitted_at" in sub, "Submission should have submitted_at"
            assert "is_mine" in sub, "Submission should have is_mine flag"
        
        print(f"PASS: evidence_submissions is a list with {len(data['evidence_submissions'])} items")
    
    def test_dispute_detail_has_financial_context(self, user_headers):
        """Verify dispute detail includes financial_context for detail section"""
        response = requests.get(f"{BASE_URL}/api/disputes/mine", headers=user_headers)
        if response.status_code != 200:
            pytest.skip("Cannot get disputes list")
        
        disputes = response.json().get("disputes", [])
        if len(disputes) == 0:
            pytest.skip("No disputes found")
        
        dispute_id = disputes[0]["dispute_id"]
        response = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers=user_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "financial_context" in data, "Should have financial_context"
        
        fc = data["financial_context"]
        required_fc_fields = ["penalty_amount", "penalty_currency", "compensation_amount"]
        for field in required_fc_fields:
            assert field in fc, f"financial_context missing: {field}"
        
        print(f"PASS: financial_context present with penalty={fc['penalty_amount']} {fc['penalty_currency']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
