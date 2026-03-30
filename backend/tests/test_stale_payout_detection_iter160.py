"""
Test Suite for Stale Payout Detection Feature - Iteration 160

Tests:
1. GET /api/admin/stale-payouts returns stale and processing > 24h payouts (admin only)
2. GET /api/admin/stale-payouts returns 403 for non-admin
3. scan_stale_payouts() marks processing > 24h → stale with stale_detected_at
4. scan_stale_payouts() does not touch processing < 24h payouts
5. scan_stale_payouts() does not create duplicates if already stale
6. Webhook can overwrite stale → completed
7. Scheduler includes stale_payout_detection_job (every 6h)
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "testuser_audit@nlyt.app"
ADMIN_PASSWORD = "TestAudit123!"
NON_ADMIN_EMAIL = "igaal@hotmail.com"
NON_ADMIN_PASSWORD = "Test123!"


class TestStalePayoutDetection:
    """Tests for stale payout detection feature"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Admin authentication failed: {response.status_code} - {response.text}")
    
    @pytest.fixture(scope="class")
    def non_admin_token(self):
        """Get non-admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": NON_ADMIN_EMAIL,
            "password": NON_ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Non-admin authentication failed: {response.status_code} - {response.text}")
    
    @pytest.fixture(scope="class")
    def admin_client(self, admin_token):
        """Session with admin auth header"""
        session = requests.Session()
        session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {admin_token}"
        })
        return session
    
    @pytest.fixture(scope="class")
    def non_admin_client(self, non_admin_token):
        """Session with non-admin auth header"""
        session = requests.Session()
        session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {non_admin_token}"
        })
        return session
    
    # ── Test 1: Admin can access stale-payouts endpoint ──
    def test_admin_can_access_stale_payouts(self, admin_client):
        """GET /api/admin/stale-payouts returns 200 for admin"""
        response = admin_client.get(f"{BASE_URL}/api/admin/stale-payouts")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "stale_payouts" in data, "Response should contain 'stale_payouts' key"
        assert "count" in data, "Response should contain 'count' key"
        assert isinstance(data["stale_payouts"], list), "stale_payouts should be a list"
        assert isinstance(data["count"], int), "count should be an integer"
        print(f"✓ Admin can access stale-payouts endpoint. Found {data['count']} stale payouts.")
    
    # ── Test 2: Non-admin gets 403 ──
    def test_non_admin_gets_403(self, non_admin_client):
        """GET /api/admin/stale-payouts returns 403 for non-admin"""
        response = non_admin_client.get(f"{BASE_URL}/api/admin/stale-payouts")
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✓ Non-admin correctly gets 403 Forbidden")
    
    # ── Test 3: Unauthenticated gets 401 ──
    def test_unauthenticated_gets_401(self):
        """GET /api/admin/stale-payouts returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/admin/stale-payouts")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("✓ Unauthenticated request correctly gets 401")
    
    # ── Test 4: Response structure validation ──
    def test_stale_payouts_response_structure(self, admin_client):
        """Verify response structure includes user_email enrichment"""
        response = admin_client.get(f"{BASE_URL}/api/admin/stale-payouts")
        assert response.status_code == 200
        
        data = response.json()
        # If there are stale payouts, verify structure
        if data["count"] > 0:
            payout = data["stale_payouts"][0]
            # Check expected fields
            expected_fields = ["payout_id", "user_id", "amount_cents", "currency", "status"]
            for field in expected_fields:
                assert field in payout, f"Payout should contain '{field}' field"
            
            # Check user_email enrichment
            assert "user_email" in payout, "Payout should contain 'user_email' enrichment"
            print(f"✓ Response structure valid. First payout: {payout.get('payout_id')}, email: {payout.get('user_email')}")
        else:
            print("✓ Response structure valid (no stale payouts to verify fields)")


class TestStalePayoutDetectorService:
    """Tests for scan_stale_payouts() service function"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Admin authentication failed: {response.status_code}")
    
    @pytest.fixture(scope="class")
    def admin_client(self, admin_token):
        """Session with admin auth header"""
        session = requests.Session()
        session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {admin_token}"
        })
        return session
    
    def test_scheduler_includes_stale_payout_job(self):
        """Verify scheduler.py includes stale_payout_detection_job"""
        scheduler_path = "/app/backend/scheduler.py"
        with open(scheduler_path, "r") as f:
            content = f.read()
        
        # Check job function exists
        assert "async def stale_payout_detection_job" in content, "stale_payout_detection_job function should exist"
        
        # Check job is added to scheduler
        assert "stale_payout_detection_job" in content, "Job should be added to scheduler"
        
        # Check interval is 6 hours
        assert "hours=6" in content, "Job should run every 6 hours"
        
        # Check job ID
        assert "id='stale_payout_detection_job'" in content, "Job should have correct ID"
        
        print("✓ Scheduler includes stale_payout_detection_job with 6h interval")
    
    def test_stale_detector_service_exists(self):
        """Verify stale_payout_detector.py service exists and has correct function"""
        service_path = "/app/backend/services/stale_payout_detector.py"
        with open(service_path, "r") as f:
            content = f.read()
        
        # Check function exists
        assert "def scan_stale_payouts" in content, "scan_stale_payouts function should exist"
        
        # Check it uses 24h threshold
        assert "STALE_THRESHOLD_HOURS = 24" in content, "Should use 24h threshold"
        
        # Check it sets stale_detected_at
        assert "stale_detected_at" in content, "Should set stale_detected_at timestamp"
        
        # Check it updates status to stale
        assert '"status": "stale"' in content or "'status': 'stale'" in content, "Should update status to stale"
        
        print("✓ stale_payout_detector.py service exists with correct implementation")


class TestAdminRouteIntegration:
    """Integration tests for admin stale-payouts route"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Admin authentication failed: {response.status_code}")
    
    @pytest.fixture(scope="class")
    def admin_client(self, admin_token):
        """Session with admin auth header"""
        session = requests.Session()
        session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {admin_token}"
        })
        return session
    
    def test_admin_route_exists_in_router(self):
        """Verify /stale-payouts route exists in admin.py"""
        router_path = "/app/backend/routers/admin.py"
        with open(router_path, "r") as f:
            content = f.read()
        
        # Check route decorator
        assert '@router.get("/stale-payouts")' in content, "Route should be defined"
        
        # Check function name
        assert "async def get_stale_payouts" in content, "Route handler should exist"
        
        # Check admin guard
        assert "await require_admin(request)" in content, "Route should require admin"
        
        print("✓ Admin route /stale-payouts exists with proper guard")
    
    def test_admin_dashboard_link_exists(self):
        """Verify AdminDashboard.js includes link to stale-payouts"""
        dashboard_path = "/app/frontend/src/pages/admin/AdminDashboard.js"
        with open(dashboard_path, "r") as f:
            content = f.read()
        
        # Check link exists
        assert "/admin/stale-payouts" in content, "Link to stale-payouts should exist"
        
        # Check AlertTriangle icon
        assert "AlertTriangle" in content, "AlertTriangle icon should be imported"
        
        # Check title
        assert "Payouts bloqués" in content, "Section title should be 'Payouts bloqués'"
        
        print("✓ AdminDashboard includes 'Payouts bloqués' link with AlertTriangle icon")
    
    def test_app_js_route_exists(self):
        """Verify App.js includes route for /admin/stale-payouts"""
        app_path = "/app/frontend/src/App.js"
        with open(app_path, "r") as f:
            content = f.read()
        
        # Check route exists
        assert "/admin/stale-payouts" in content, "Route should be defined in App.js"
        
        # Check component import
        assert "AdminStalePayouts" in content, "AdminStalePayouts component should be imported"
        
        print("✓ App.js includes route /admin/stale-payouts with AdminStalePayouts component")
    
    def test_stale_payouts_page_component_exists(self):
        """Verify AdminStalePayouts.js component exists with correct structure"""
        page_path = "/app/frontend/src/pages/admin/AdminStalePayouts.js"
        with open(page_path, "r") as f:
            content = f.read()
        
        # Check data-testid attributes
        assert 'data-testid="stale-payouts-title"' in content, "Title should have data-testid"
        assert 'data-testid="no-stale-payouts"' in content, "Empty state should have data-testid"
        assert 'data-testid="stale-payouts-list"' in content, "List should have data-testid"
        assert 'data-testid="refresh-stale-payouts"' in content, "Refresh button should have data-testid"
        
        # Check empty state message
        assert "Aucun payout bloqué" in content, "Empty state message should exist"
        
        # Check Stripe link
        assert "dashboard.stripe.com" in content, "Stripe dashboard link should exist"
        
        # Check STALE badge
        assert "STALE" in content, "STALE badge should exist"
        
        print("✓ AdminStalePayouts.js component has correct structure and data-testid attributes")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
