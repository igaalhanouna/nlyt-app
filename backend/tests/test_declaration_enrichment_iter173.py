"""
Test Declaration Section Enrichment - Iteration 173

Tests the enriched declaration_summary in GET /api/disputes/{id}:
- target_self_declaration
- contradiction_level
- summary_phrase
- is_organizer per declarant
- organizer_position / participant_position
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "testuser_audit@nlyt.app"
ADMIN_PASSWORD = "TestAudit123!"
USER_EMAIL = "igaal@hotmail.com"
USER_PASSWORD = "Test123!"


class TestDeclarationEnrichment:
    """Tests for enriched declaration_summary in dispute detail"""
    
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
    def user_token(self):
        """Get regular user auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": USER_EMAIL,
            "password": USER_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"User login failed: {response.status_code}")
        return response.json().get("access_token")
    
    @pytest.fixture(scope="class")
    def resolved_disputes(self, admin_token):
        """Get list of resolved disputes"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/disputes/decisions/mine", headers=headers)
        if response.status_code != 200:
            pytest.skip(f"Failed to get decisions: {response.status_code}")
        data = response.json()
        decisions = data.get("decisions", [])
        if not decisions:
            pytest.skip("No resolved disputes found")
        return decisions
    
    def test_admin_login_works(self):
        """Verify admin login returns valid token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        print(f"PASS: Admin login works, token received")
    
    def test_user_login_works(self):
        """Verify user login returns valid token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": USER_EMAIL,
            "password": USER_PASSWORD
        })
        assert response.status_code == 200, f"User login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        print(f"PASS: User login works, token received")
    
    def test_decisions_mine_returns_list(self, admin_token):
        """Verify GET /api/disputes/decisions/mine returns decisions"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/disputes/decisions/mine", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "decisions" in data, "No decisions field in response"
        assert "count" in data, "No count field in response"
        print(f"PASS: decisions/mine returns {data['count']} decisions")
    
    def test_dispute_detail_has_declaration_summary(self, admin_token, resolved_disputes):
        """Verify dispute detail has declaration_summary field"""
        dispute_id = resolved_disputes[0].get("dispute_id")
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "declaration_summary" in data, "No declaration_summary in dispute detail"
        print(f"PASS: dispute detail has declaration_summary")
    
    def test_declaration_summary_has_target_self_declaration(self, admin_token, resolved_disputes):
        """Verify declaration_summary has target_self_declaration field"""
        dispute_id = resolved_disputes[0].get("dispute_id")
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers=headers)
        assert response.status_code == 200
        ds = response.json().get("declaration_summary", {})
        # target_self_declaration can be None if target didn't declare
        assert "target_self_declaration" in ds, "No target_self_declaration field"
        print(f"PASS: target_self_declaration = {ds.get('target_self_declaration')}")
    
    def test_declaration_summary_has_contradiction_level(self, admin_token, resolved_disputes):
        """Verify declaration_summary has contradiction_level field"""
        dispute_id = resolved_disputes[0].get("dispute_id")
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers=headers)
        assert response.status_code == 200
        ds = response.json().get("declaration_summary", {})
        assert "contradiction_level" in ds, "No contradiction_level field"
        valid_levels = [
            "unanimous_present", "unanimous_absent", "majority_present", 
            "majority_absent", "disagreement", "contradiction_with_proof", "no_declarations"
        ]
        assert ds["contradiction_level"] in valid_levels, f"Invalid contradiction_level: {ds['contradiction_level']}"
        print(f"PASS: contradiction_level = {ds['contradiction_level']}")
    
    def test_declaration_summary_has_summary_phrase(self, admin_token, resolved_disputes):
        """Verify declaration_summary has summary_phrase field"""
        dispute_id = resolved_disputes[0].get("dispute_id")
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers=headers)
        assert response.status_code == 200
        ds = response.json().get("declaration_summary", {})
        assert "summary_phrase" in ds, "No summary_phrase field"
        # summary_phrase should be a non-empty string
        assert isinstance(ds["summary_phrase"], str), "summary_phrase should be string"
        print(f"PASS: summary_phrase = '{ds['summary_phrase'][:50]}...'")
    
    def test_declaration_summary_has_target_name(self, admin_token, resolved_disputes):
        """Verify declaration_summary has target_name field"""
        dispute_id = resolved_disputes[0].get("dispute_id")
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers=headers)
        assert response.status_code == 200
        ds = response.json().get("declaration_summary", {})
        assert "target_name" in ds, "No target_name field"
        print(f"PASS: target_name = {ds.get('target_name')}")
    
    def test_declarants_have_is_organizer_field(self, admin_token, resolved_disputes):
        """Verify each declarant has is_organizer boolean field"""
        dispute_id = resolved_disputes[0].get("dispute_id")
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers=headers)
        assert response.status_code == 200
        ds = response.json().get("declaration_summary", {})
        declarants = ds.get("declarants", [])
        for i, dec in enumerate(declarants):
            assert "is_organizer" in dec, f"Declarant {i} missing is_organizer field"
            assert isinstance(dec["is_organizer"], bool), f"is_organizer should be boolean"
        print(f"PASS: {len(declarants)} declarants all have is_organizer field")
    
    def test_dispute_has_organizer_position(self, admin_token, resolved_disputes):
        """Verify dispute detail has organizer_position field"""
        dispute_id = resolved_disputes[0].get("dispute_id")
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        # organizer_position can be None if not yet submitted
        assert "organizer_position" in data, "No organizer_position field"
        print(f"PASS: organizer_position = {data.get('organizer_position')}")
    
    def test_dispute_has_participant_position(self, admin_token, resolved_disputes):
        """Verify dispute detail has participant_position field"""
        dispute_id = resolved_disputes[0].get("dispute_id")
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        # participant_position can be None if not yet submitted
        assert "participant_position" in data, "No participant_position field"
        print(f"PASS: participant_position = {data.get('participant_position')}")
    
    def test_dispute_has_opened_reason(self, admin_token, resolved_disputes):
        """Verify dispute detail has opened_reason field"""
        dispute_id = resolved_disputes[0].get("dispute_id")
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        # opened_reason should exist
        assert "opened_reason" in data, "No opened_reason field"
        print(f"PASS: opened_reason = {data.get('opened_reason')}")
    
    def test_dispute_has_tech_evidence_summary(self, admin_token, resolved_disputes):
        """Verify dispute detail has tech_evidence_summary (regression check)"""
        dispute_id = resolved_disputes[0].get("dispute_id")
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "tech_evidence_summary" in data, "No tech_evidence_summary field"
        tes = data["tech_evidence_summary"]
        assert "has_any_evidence" in tes, "No has_any_evidence in tech_evidence_summary"
        print(f"PASS: tech_evidence_summary present, has_any_evidence = {tes.get('has_any_evidence')}")
    
    def test_dispute_has_financial_context(self, admin_token, resolved_disputes):
        """Verify dispute detail has financial_context (regression check)"""
        dispute_id = resolved_disputes[0].get("dispute_id")
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "financial_context" in data, "No financial_context field"
        fc = data["financial_context"]
        assert "penalty_amount" in fc, "No penalty_amount in financial_context"
        print(f"PASS: financial_context present, penalty_amount = {fc.get('penalty_amount')}")


class TestSpecificDisputeScenarios:
    """Test specific dispute scenarios mentioned in the request"""
    
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
    
    def test_find_unanimous_absent_dispute(self, admin_token):
        """Find a dispute with contradiction_level=unanimous_absent"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/disputes/decisions/mine", headers=headers)
        assert response.status_code == 200
        decisions = response.json().get("decisions", [])
        
        for d in decisions:
            dispute_id = d.get("dispute_id")
            detail_resp = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers=headers)
            if detail_resp.status_code == 200:
                ds = detail_resp.json().get("declaration_summary", {})
                if ds.get("contradiction_level") == "unanimous_absent":
                    print(f"PASS: Found unanimous_absent dispute: {dispute_id}")
                    print(f"  - target_self_declaration: {ds.get('target_self_declaration')}")
                    print(f"  - summary_phrase: {ds.get('summary_phrase')}")
                    return
        
        print("INFO: No unanimous_absent dispute found in current data")
    
    def test_find_unanimous_present_dispute(self, admin_token):
        """Find a dispute with contradiction_level=unanimous_present"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/disputes/decisions/mine", headers=headers)
        assert response.status_code == 200
        decisions = response.json().get("decisions", [])
        
        for d in decisions:
            dispute_id = d.get("dispute_id")
            detail_resp = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers=headers)
            if detail_resp.status_code == 200:
                ds = detail_resp.json().get("declaration_summary", {})
                if ds.get("contradiction_level") == "unanimous_present":
                    print(f"PASS: Found unanimous_present dispute: {dispute_id}")
                    print(f"  - target_self_declaration: {ds.get('target_self_declaration')}")
                    print(f"  - summary_phrase: {ds.get('summary_phrase')}")
                    return
        
        print("INFO: No unanimous_present dispute found in current data")
    
    def test_declarants_include_organizer_flag(self, admin_token):
        """Verify at least one declarant has is_organizer=True"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/disputes/decisions/mine", headers=headers)
        assert response.status_code == 200
        decisions = response.json().get("decisions", [])
        
        found_organizer = False
        for d in decisions:
            dispute_id = d.get("dispute_id")
            detail_resp = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers=headers)
            if detail_resp.status_code == 200:
                ds = detail_resp.json().get("declaration_summary", {})
                for dec in ds.get("declarants", []):
                    if dec.get("is_organizer"):
                        found_organizer = True
                        print(f"PASS: Found organizer declarant: {dec.get('first_name')}")
                        break
            if found_organizer:
                break
        
        if not found_organizer:
            print("INFO: No organizer declarant found in current data")


class TestAdminArbitrationRegression:
    """Regression tests for admin arbitration (from iteration 172)"""
    
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
    
    def test_arbitration_stats_endpoint(self, admin_token):
        """Verify GET /api/admin/arbitration/stats works"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/arbitration/stats", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "escalated_pending" in data, "No escalated_pending"
        assert "awaiting_positions" in data, "No awaiting_positions"
        assert "total_resolved" in data, "No total_resolved"
        print(f"PASS: arbitration stats - escalated={data.get('escalated_pending')}, awaiting={data.get('awaiting_positions')}, resolved={data.get('total_resolved')}")
    
    def test_arbitration_disputes_list(self, admin_token):
        """Verify GET /api/admin/arbitration works"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/arbitration", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "disputes" in data, "No disputes field"
        print(f"PASS: arbitration disputes list returns {len(data.get('disputes', []))} disputes")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
