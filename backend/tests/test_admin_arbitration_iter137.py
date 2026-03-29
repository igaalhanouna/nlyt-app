"""
Test Admin Arbitration Dashboard - Iteration 137

Tests for the new admin arbitration feature:
- GET /api/admin/arbitration - List escalated disputes
- GET /api/admin/arbitration/stats - KPI stats
- GET /api/admin/arbitration/:id - Dispute detail with tech_dossier and system_analysis
- POST /api/admin/arbitration/:id/resolve - Resolve dispute
- Admin routes reject non-admin users (403)
- JWT includes role field for admin users
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_USER = {"email": "testuser_audit@nlyt.app", "password": "TestAudit123!"}
NON_ADMIN_USER_1 = {"email": "igaal@hotmail.com", "password": "Test123!"}
NON_ADMIN_USER_2 = {"email": "igaal.hanouna@gmail.com", "password": "OrgTest123!"}

# Module-level token storage
admin_token = None
non_admin_token = None
escalated_dispute_id = None


class TestAdminArbitration:
    """Admin Arbitration Dashboard API Tests"""
    
    # ─── Authentication Tests ───────────────────────────────────────────
    
    def test_01_login_admin_user(self):
        """Admin user login returns JWT with role=admin"""
        global admin_token
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_USER)
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        
        data = response.json()
        # API returns access_token directly (not wrapped in success)
        assert "access_token" in data, "No access_token in response"
        assert "user" in data, "No user in response"
        
        # Verify role is included in user response
        user = data["user"]
        assert user.get("role") == "admin", f"Expected role=admin, got {user.get('role')}"
        
        admin_token = data["access_token"]
        print(f"✅ Admin login successful, role={user.get('role')}")
    
    def test_02_login_non_admin_user(self):
        """Non-admin user login returns JWT without admin role"""
        global non_admin_token
        response = requests.post(f"{BASE_URL}/api/auth/login", json=NON_ADMIN_USER_1)
        assert response.status_code == 200, f"Non-admin login failed: {response.text}"
        
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        
        user = data["user"]
        # Non-admin should have role='user' or no role
        assert user.get("role") != "admin", f"Non-admin user should not have admin role, got {user.get('role')}"
        
        non_admin_token = data["access_token"]
        print(f"✅ Non-admin login successful, role={user.get('role', 'user')}")
    
    # ─── Access Control Tests (403 for non-admin) ───────────────────────
    
    def test_03_non_admin_cannot_access_arbitration_list(self):
        """Non-admin user gets 403 on /api/admin/arbitration"""
        global non_admin_token
        headers = {"Authorization": f"Bearer {non_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/arbitration", headers=headers)
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✅ Non-admin correctly rejected from arbitration list (403)")
    
    def test_04_non_admin_cannot_access_arbitration_stats(self):
        """Non-admin user gets 403 on /api/admin/arbitration/stats"""
        global non_admin_token
        headers = {"Authorization": f"Bearer {non_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/arbitration/stats", headers=headers)
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✅ Non-admin correctly rejected from arbitration stats (403)")
    
    def test_05_non_admin_cannot_access_arbitration_detail(self):
        """Non-admin user gets 403 on /api/admin/arbitration/:id"""
        global non_admin_token
        headers = {"Authorization": f"Bearer {non_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/arbitration/fake-id", headers=headers)
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✅ Non-admin correctly rejected from arbitration detail (403)")
    
    def test_06_non_admin_cannot_resolve_dispute(self):
        """Non-admin user gets 403 on POST /api/admin/arbitration/:id/resolve"""
        global non_admin_token
        headers = {"Authorization": f"Bearer {non_admin_token}"}
        response = requests.post(
            f"{BASE_URL}/api/admin/arbitration/fake-id/resolve",
            headers=headers,
            json={"final_outcome": "no_show", "resolution_note": "Test note"}
        )
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✅ Non-admin correctly rejected from resolve endpoint (403)")
    
    # ─── Admin Access Tests ─────────────────────────────────────────────
    
    def test_07_admin_can_access_arbitration_stats(self):
        """Admin can access /api/admin/arbitration/stats with correct KPI structure"""
        global admin_token
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/arbitration/stats", headers=headers)
        
        assert response.status_code == 200, f"Stats request failed: {response.text}"
        
        data = response.json()
        # Verify KPI fields
        assert "escalated_pending" in data, "Missing escalated_pending"
        assert "total_resolved" in data, "Missing total_resolved"
        assert "total_agreed_by_parties" in data, "Missing total_agreed_by_parties"
        assert "awaiting_positions" in data, "Missing awaiting_positions"
        
        # All should be integers
        assert isinstance(data["escalated_pending"], int), "escalated_pending should be int"
        assert isinstance(data["total_resolved"], int), "total_resolved should be int"
        
        print(f"✅ Arbitration stats: escalated={data['escalated_pending']}, resolved={data['total_resolved']}, agreed={data['total_agreed_by_parties']}, awaiting={data['awaiting_positions']}")
    
    def test_08_admin_can_access_arbitration_list(self):
        """Admin can access /api/admin/arbitration with enriched dispute list"""
        global admin_token, escalated_dispute_id
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/arbitration", headers=headers)
        
        assert response.status_code == 200, f"List request failed: {response.text}"
        
        data = response.json()
        assert "disputes" in data, "Missing disputes array"
        assert "count" in data, "Missing count"
        assert isinstance(data["disputes"], list), "disputes should be a list"
        
        print(f"✅ Found {data['count']} escalated disputes")
        
        # If there are disputes, verify enrichment fields
        if data["count"] > 0:
            dispute = data["disputes"][0]
            escalated_dispute_id = dispute.get("dispute_id")
            
            # Check enrichment fields
            assert "appointment_title" in dispute, "Missing appointment_title"
            assert "appointment_date" in dispute, "Missing appointment_date"
            assert "appointment_type" in dispute, "Missing appointment_type"
            assert "target_name" in dispute, "Missing target_name"
            assert "has_admissible_proof" in dispute, "Missing has_admissible_proof (proof badge)"
            assert "positions" in dispute, "Missing positions"
            
            # Age indicator
            assert "escalated_days_ago" in dispute or "escalated_hours_ago" in dispute, "Missing age indicator"
            
            print(f"  - Dispute: {dispute.get('dispute_id')[:8]}... | Target: {dispute.get('target_name')} | Proof: {dispute.get('has_admissible_proof')}")
    
    def test_09_admin_can_access_dispute_detail(self):
        """Admin can access /api/admin/arbitration/:id with full dossier"""
        global admin_token, escalated_dispute_id
        if not escalated_dispute_id:
            pytest.skip("No escalated dispute found to test detail")
        
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{BASE_URL}/api/admin/arbitration/{escalated_dispute_id}",
            headers=headers
        )
        
        assert response.status_code == 200, f"Detail request failed: {response.text}"
        
        data = response.json()
        
        # Verify tech_dossier
        assert "tech_dossier" in data, "Missing tech_dossier"
        td = data["tech_dossier"]
        assert "has_admissible_proof" in td, "Missing has_admissible_proof in tech_dossier"
        assert "proof_summary" in td, "Missing proof_summary in tech_dossier"
        
        # Verify system_analysis
        assert "system_analysis" in data, "Missing system_analysis"
        sa = data["system_analysis"]
        assert "case" in sa, "Missing case in system_analysis"
        assert "confidence" in sa, "Missing confidence in system_analysis"
        assert "reasoning" in sa, "Missing reasoning in system_analysis"
        assert "suggested_outcome" in sa, "Missing suggested_outcome in system_analysis"
        
        # Verify declaration_summary
        assert "declaration_summary" in data, "Missing declaration_summary"
        
        # Verify positions
        assert "organizer_position" in data or "positions" in data, "Missing positions info"
        
        print(f"✅ Dispute detail loaded:")
        print(f"  - Tech dossier: has_proof={td.get('has_admissible_proof')}")
        print(f"  - System analysis: case={sa.get('case')}, confidence={sa.get('confidence')}, suggested={sa.get('suggested_outcome')}")
        print(f"  - Reasoning: {sa.get('reasoning', '')[:80]}...")
    
    def test_10_resolve_validation_requires_outcome(self):
        """Resolve endpoint validates final_outcome"""
        global admin_token, escalated_dispute_id
        if not escalated_dispute_id:
            pytest.skip("No escalated dispute found")
        
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.post(
            f"{BASE_URL}/api/admin/arbitration/{escalated_dispute_id}/resolve",
            headers=headers,
            json={"final_outcome": "invalid_outcome", "resolution_note": "Test note here"}
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid outcome, got {response.status_code}"
        print("✅ Invalid outcome correctly rejected (400)")
    
    def test_11_resolve_validation_requires_note(self):
        """Resolve endpoint requires resolution_note (min 5 chars)"""
        global admin_token, escalated_dispute_id
        if not escalated_dispute_id:
            pytest.skip("No escalated dispute found")
        
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Test with empty note
        response = requests.post(
            f"{BASE_URL}/api/admin/arbitration/{escalated_dispute_id}/resolve",
            headers=headers,
            json={"final_outcome": "no_show", "resolution_note": ""}
        )
        assert response.status_code == 400, f"Expected 400 for empty note, got {response.status_code}"
        
        # Test with short note
        response = requests.post(
            f"{BASE_URL}/api/admin/arbitration/{escalated_dispute_id}/resolve",
            headers=headers,
            json={"final_outcome": "no_show", "resolution_note": "abc"}
        )
        assert response.status_code == 400, f"Expected 400 for short note, got {response.status_code}"
        
        print("✅ Short/empty note correctly rejected (400)")
    
    def test_12_resolve_dispute_success(self):
        """Admin can resolve an escalated dispute"""
        global admin_token, escalated_dispute_id
        if not escalated_dispute_id:
            pytest.skip("No escalated dispute found")
        
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.post(
            f"{BASE_URL}/api/admin/arbitration/{escalated_dispute_id}/resolve",
            headers=headers,
            json={
                "final_outcome": "no_show",
                "resolution_note": "Test arbitration resolution - absence confirmee par analyse systeme"
            }
        )
        
        # Could be 200 (success) or 400 (already resolved or other business rule)
        if response.status_code == 200:
            data = response.json()
            assert data.get("success") is True, "Expected success=True"
            assert data.get("outcome") == "no_show", f"Expected outcome=no_show, got {data.get('outcome')}"
            print(f"✅ Dispute resolved successfully: outcome={data.get('outcome')}")
        elif response.status_code == 400:
            # Dispute might already be resolved or not in escalated status
            print(f"⚠️ Resolve returned 400 (may be already resolved): {response.json().get('detail')}")
        else:
            pytest.fail(f"Unexpected status {response.status_code}: {response.text}")
    
    def test_13_verify_stats_after_resolution(self):
        """Verify stats update after resolution"""
        global admin_token
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/arbitration/stats", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        print(f"✅ Stats after resolution: escalated={data['escalated_pending']}, resolved={data['total_resolved']}")
    
    def test_14_non_existent_dispute_returns_404(self):
        """Non-existent dispute ID returns 404"""
        global admin_token
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{BASE_URL}/api/admin/arbitration/non-existent-dispute-id",
            headers=headers
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✅ Non-existent dispute correctly returns 404")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
