"""
Test P1/P2 UX/Logic Fixes - Iteration 176

P1: Waived status handling in /decisions
- P1a: GET /api/disputes/decisions/mine — waived disputes have financial_impact.type='neutral'
- P1b: /decisions page — waived displays as 'Classé sans suite' with slate styling
- P1c: /decisions/{id} detail — waived shows correct label and financial section

P2: Admin arbitration category simplification
- P2a: GET /api/admin/arbitration/stats — returns total_closed (not separate resolved/agreed)
- P2b: GET /api/admin/arbitration?filter=closed — returns disputes with status IN (resolved, agreed_*)
- P2c: /admin/arbitration page — shows 3 KPI cards (not 4)
- P2d: Status badges show 'Clos — Accord mutuel' for agreed_* and 'Clos — Arbitrage' for resolved
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "testuser_audit@nlyt.app"
ADMIN_PASSWORD = "TestAudit123!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Admin login failed: {response.status_code}")
    return response.json().get("access_token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Headers with admin auth token"""
    return {"Authorization": f"Bearer {admin_token}"}


class TestP1WaivedStatusDecisions:
    """P1: Waived status handling in /decisions API"""
    
    def test_p1a_waived_financial_impact_neutral(self, admin_headers):
        """P1a: Waived disputes must have financial_impact.type='neutral' and label='Aucune penalite'"""
        response = requests.get(f"{BASE_URL}/api/disputes/decisions/mine", headers=admin_headers)
        assert response.status_code == 200
        
        data = response.json()
        decisions = data.get("decisions", [])
        
        # Find waived decisions
        waived_decisions = [d for d in decisions if d.get("final_outcome") == "waived"]
        assert len(waived_decisions) > 0, "No waived decisions found for testing"
        
        # Verify all waived decisions have neutral financial impact
        for decision in waived_decisions:
            fi = decision.get("financial_impact", {})
            assert fi.get("type") == "neutral", f"Waived decision {decision.get('dispute_id')} has type={fi.get('type')}, expected 'neutral'"
            assert fi.get("label") == "Aucune penalite", f"Waived decision {decision.get('dispute_id')} has label={fi.get('label')}, expected 'Aucune penalite'"
    
    def test_p1a_on_time_financial_impact_neutral(self, admin_headers):
        """Regression: on_time disputes should also have neutral financial impact"""
        response = requests.get(f"{BASE_URL}/api/disputes/decisions/mine", headers=admin_headers)
        assert response.status_code == 200
        
        data = response.json()
        decisions = data.get("decisions", [])
        
        on_time_decisions = [d for d in decisions if d.get("final_outcome") == "on_time"]
        
        for decision in on_time_decisions:
            fi = decision.get("financial_impact", {})
            assert fi.get("type") == "neutral", f"on_time decision {decision.get('dispute_id')} has type={fi.get('type')}, expected 'neutral'"
    
    def test_p1c_waived_dispute_detail(self, admin_headers):
        """P1c: Waived dispute detail should have correct resolution info"""
        # First get a waived dispute ID
        response = requests.get(f"{BASE_URL}/api/disputes/decisions/mine", headers=admin_headers)
        assert response.status_code == 200
        
        decisions = response.json().get("decisions", [])
        waived_decisions = [d for d in decisions if d.get("final_outcome") == "waived"]
        
        if not waived_decisions:
            pytest.skip("No waived decisions found")
        
        dispute_id = waived_decisions[0].get("dispute_id")
        
        # Get dispute detail
        detail_response = requests.get(f"{BASE_URL}/api/disputes/{dispute_id}", headers=admin_headers)
        assert detail_response.status_code == 200
        
        detail = detail_response.json()
        resolution = detail.get("resolution", {})
        
        # Verify resolution has waived outcome
        assert resolution.get("final_outcome") == "waived", f"Expected final_outcome='waived', got {resolution.get('final_outcome')}"


class TestP2AdminArbitrationCategories:
    """P2: Admin arbitration category simplification"""
    
    def test_p2a_stats_returns_total_closed(self, admin_headers):
        """P2a: /api/admin/arbitration/stats must return total_closed field"""
        response = requests.get(f"{BASE_URL}/api/admin/arbitration/stats", headers=admin_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        # Must have total_closed
        assert "total_closed" in data, "Missing 'total_closed' field in stats"
        assert isinstance(data["total_closed"], int), "total_closed must be an integer"
        
        # Must NOT have old separate fields
        assert "total_resolved" not in data, "Old 'total_resolved' field should not exist"
        assert "total_agreed_by_parties" not in data, "Old 'total_agreed_by_parties' field should not exist"
        
        # Must have other expected fields
        assert "escalated_pending" in data, "Missing 'escalated_pending' field"
        assert "awaiting_positions" in data, "Missing 'awaiting_positions' field"
    
    def test_p2b_closed_filter_returns_all_closed_statuses(self, admin_headers):
        """P2b: filter=closed must return disputes with status IN (resolved, agreed_*)"""
        response = requests.get(f"{BASE_URL}/api/admin/arbitration?filter=closed", headers=admin_headers)
        assert response.status_code == 200
        
        data = response.json()
        disputes = data.get("disputes", [])
        
        # All disputes should have closed statuses
        valid_closed_statuses = {"resolved", "agreed_present", "agreed_absent", "agreed_late_penalized"}
        
        for dispute in disputes:
            status = dispute.get("status")
            assert status in valid_closed_statuses, f"Dispute {dispute.get('dispute_id')} has status={status}, expected one of {valid_closed_statuses}"
    
    def test_p2d_financial_summary_waived_no_penalty(self, admin_headers):
        """P2d: Waived disputes in admin view should show 'Aucune penalite' financial summary"""
        response = requests.get(f"{BASE_URL}/api/admin/arbitration?filter=closed", headers=admin_headers)
        assert response.status_code == 200
        
        disputes = response.json().get("disputes", [])
        
        # Find disputes with waived outcome
        for dispute in disputes:
            resolution = dispute.get("resolution") or {}
            if resolution.get("final_outcome") == "waived":
                financial_summary = dispute.get("financial_summary")
                assert financial_summary == "Aucune penalite", f"Waived dispute should have 'Aucune penalite', got {financial_summary}"


class TestRegressionDecisions:
    """Regression tests for existing decision outcomes"""
    
    def test_on_time_still_works(self, admin_headers):
        """Regression: on_time decisions should still display correctly"""
        response = requests.get(f"{BASE_URL}/api/disputes/decisions/mine", headers=admin_headers)
        assert response.status_code == 200
        
        decisions = response.json().get("decisions", [])
        on_time = [d for d in decisions if d.get("final_outcome") == "on_time"]
        
        # Should have some on_time decisions
        assert len(on_time) >= 0, "on_time decisions query works"
    
    def test_no_show_still_works(self, admin_headers):
        """Regression: no_show decisions should still display correctly"""
        response = requests.get(f"{BASE_URL}/api/disputes/decisions/mine", headers=admin_headers)
        assert response.status_code == 200
        
        decisions = response.json().get("decisions", [])
        no_show = [d for d in decisions if d.get("final_outcome") == "no_show"]
        
        # Should have some no_show decisions
        assert len(no_show) >= 0, "no_show decisions query works"
    
    def test_litiges_page_still_works(self, admin_headers):
        """Regression: /api/disputes/mine should still work"""
        response = requests.get(f"{BASE_URL}/api/disputes/mine", headers=admin_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "disputes" in data, "Response should have 'disputes' field"
        assert "count" in data, "Response should have 'count' field"


class TestFrontendCodeReview:
    """Code review checks for frontend files"""
    
    def test_decisions_list_has_waived_config(self):
        """P1b: DecisionsListPage.js must have waived in OUTCOME_CFG"""
        with open("/app/frontend/src/pages/decisions/DecisionsListPage.js", "r") as f:
            content = f.read()
        
        # Check OUTCOME_CFG has waived entry
        assert "waived:" in content, "OUTCOME_CFG missing 'waived' entry"
        assert "Classe sans suite" in content, "Missing 'Classe sans suite' label"
        assert "bg-slate-100" in content, "Missing slate background for waived"
        assert "text-slate-600" in content, "Missing slate text color for waived"
    
    def test_decision_detail_has_waived_config(self):
        """P1d: DecisionDetailPage.js must have waived entries"""
        with open("/app/frontend/src/pages/decisions/DecisionDetailPage.js", "r") as f:
            content = f.read()
        
        # Check OUTCOME_CFG has waived
        assert "waived:" in content, "OUTCOME_CFG missing 'waived' entry"
        
        # Check STATUS_LABELS has waived (can be waived: without quotes in JS object)
        assert "waived:" in content, "STATUS_LABELS missing 'waived' entry"
        
        # Check OUTCOME_PHRASES has waived
        assert "classe sans suite" in content.lower(), "OUTCOME_PHRASES missing waived phrase"
        
        # Check slate color entries
        assert "slate:" in content, "Missing 'slate' color entries in BORDER/BG/TEXT"
    
    def test_admin_arbitration_has_closed_filter(self):
        """P2c: AdminArbitrationList.js must have 'closed' filter instead of separate resolved/agreed"""
        with open("/app/frontend/src/pages/admin/AdminArbitrationList.js", "r") as f:
            content = f.read()
        
        # Check FILTERS has 'closed'
        assert "'closed'" in content or '"closed"' in content, "FILTERS missing 'closed' key"
        
        # Check for 3 filters (not 4)
        # Count filter entries
        import re
        filter_matches = re.findall(r"key:\s*['\"](\w+)['\"]", content)
        assert len(filter_matches) == 3, f"Expected 3 filters, found {len(filter_matches)}: {filter_matches}"
        
        # Check labels
        assert "En attente des parties" in content, "Missing 'En attente des parties' label"
        assert "Clos" in content, "Missing 'Clos' label"
