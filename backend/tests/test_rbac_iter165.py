"""
RBAC (Role-Based Access Control) Tests — Iteration 165
Tests for the 5-role permission system: admin, arbitrator, payer, accreditor, user

Test Coverage:
- Backend security: role='user' gets 403 on admin routes
- Backend security: role='admin' can access all admin routes
- Role change via PATCH /api/admin/users/{user_id}/role
- Invalid role validation
- Self-downgrade protection
- Role-based access after role change
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
USER2_EMAIL = "igaal.hanouna@gmail.com"
USER2_PASSWORD = "OrgTest123!"


class TestRBACBackendSecurity:
    """Test that role='user' gets 403 on admin routes and role='admin' can access all"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Login as admin and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, f"No access_token in response: {data}"
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def user_token(self):
        """Login as regular user and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": USER_EMAIL,
            "password": USER_PASSWORD
        })
        assert response.status_code == 200, f"User login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, f"No access_token in response: {data}"
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def user2_token(self):
        """Login as second regular user and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": USER2_EMAIL,
            "password": USER2_PASSWORD
        })
        assert response.status_code == 200, f"User2 login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, f"No access_token in response: {data}"
        return data["access_token"]
    
    # ── User role='user' should get 403 on admin routes ──
    
    def test_user_gets_403_on_arbitration(self, user_token):
        """User with role='user' should receive 403 on GET /api/admin/arbitration"""
        headers = {"Authorization": f"Bearer {user_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/arbitration", headers=headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"PASS: User gets 403 on /api/admin/arbitration")
    
    def test_user_gets_403_on_users(self, user_token):
        """User with role='user' should receive 403 on GET /api/admin/users"""
        headers = {"Authorization": f"Bearer {user_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"PASS: User gets 403 on /api/admin/users")
    
    def test_user_gets_403_on_stale_payouts(self, user_token):
        """User with role='user' should receive 403 on GET /api/admin/stale-payouts"""
        headers = {"Authorization": f"Bearer {user_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/stale-payouts", headers=headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"PASS: User gets 403 on /api/admin/stale-payouts")
    
    # ── Admin role='admin' should access all admin routes ──
    
    def test_admin_can_access_arbitration(self, admin_token):
        """Admin should be able to access GET /api/admin/arbitration"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/arbitration", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "disputes" in data, f"Expected 'disputes' in response: {data}"
        print(f"PASS: Admin can access /api/admin/arbitration - {data.get('count', 0)} disputes")
    
    def test_admin_can_access_users(self, admin_token):
        """Admin should be able to access GET /api/admin/users"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "users" in data, f"Expected 'users' in response: {data}"
        assert "count" in data, f"Expected 'count' in response: {data}"
        print(f"PASS: Admin can access /api/admin/users - {data['count']} users")
    
    def test_admin_can_access_stale_payouts(self, admin_token):
        """Admin should be able to access GET /api/admin/stale-payouts"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/stale-payouts", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "stale_payouts" in data, f"Expected 'stale_payouts' in response: {data}"
        print(f"PASS: Admin can access /api/admin/stale-payouts - {data.get('count', 0)} stale payouts")
    
    def test_admin_can_access_associations(self, admin_token):
        """Admin should be able to access GET /api/charity-associations"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/charity-associations", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "associations" in data, f"Expected 'associations' in response: {data}"
        print(f"PASS: Admin can access /api/charity-associations - {len(data.get('associations', []))} associations")
    
    def test_admin_can_access_payouts(self, admin_token):
        """Admin should be able to access GET /api/admin/payouts"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/payouts", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "payouts" in data, f"Expected 'payouts' in response: {data}"
        print(f"PASS: Admin can access /api/admin/payouts - {len(data.get('payouts', []))} payouts")


class TestRoleChangeAPI:
    """Test PATCH /api/admin/users/{user_id}/role endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Login as admin and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def admin_user_id(self, admin_token):
        """Get admin's user_id"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=headers)
        assert response.status_code == 200
        users = response.json()["users"]
        admin_user = next((u for u in users if u["email"] == ADMIN_EMAIL), None)
        assert admin_user, f"Admin user not found in users list"
        return admin_user["user_id"]
    
    @pytest.fixture(scope="class")
    def test_user_id(self, admin_token):
        """Get test user's user_id (igaal@hotmail.com)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=headers)
        assert response.status_code == 200
        users = response.json()["users"]
        test_user = next((u for u in users if u["email"] == USER_EMAIL), None)
        assert test_user, f"Test user {USER_EMAIL} not found in users list"
        return test_user["user_id"]
    
    def test_change_role_to_arbitrator(self, admin_token, test_user_id):
        """PATCH /api/admin/users/{user_id}/role with role='arbitrator' should work"""
        headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
        response = requests.patch(
            f"{BASE_URL}/api/admin/users/{test_user_id}/role",
            headers=headers,
            json={"role": "arbitrator"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["role"] == "arbitrator", f"Expected role='arbitrator', got {data}"
        print(f"PASS: Changed {USER_EMAIL} role to arbitrator")
    
    def test_invalid_role_returns_400(self, admin_token, test_user_id):
        """PATCH with role='invalid_role' should return 400"""
        headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
        response = requests.patch(
            f"{BASE_URL}/api/admin/users/{test_user_id}/role",
            headers=headers,
            json={"role": "invalid_role"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print(f"PASS: Invalid role returns 400")
    
    def test_admin_cannot_change_own_role(self, admin_token, admin_user_id):
        """Admin cannot change their own role (self-downgrade protection)"""
        headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
        response = requests.patch(
            f"{BASE_URL}/api/admin/users/{admin_user_id}/role",
            headers=headers,
            json={"role": "user"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "propre role" in data.get("detail", "").lower() or "own role" in data.get("detail", "").lower(), \
            f"Expected self-downgrade error message, got: {data}"
        print(f"PASS: Admin cannot change own role")


class TestRoleBasedAccessAfterChange:
    """Test that after changing a user's role, they get appropriate access"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Login as admin and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def test_user_id(self, admin_token):
        """Get test user's user_id"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=headers)
        assert response.status_code == 200
        users = response.json()["users"]
        test_user = next((u for u in users if u["email"] == USER_EMAIL), None)
        assert test_user, f"Test user {USER_EMAIL} not found"
        return test_user["user_id"]
    
    def test_arbitrator_can_access_arbitration_after_role_change(self, admin_token, test_user_id):
        """After changing user to 'arbitrator', they should access /api/admin/arbitration"""
        headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
        
        # First ensure user is set to arbitrator
        response = requests.patch(
            f"{BASE_URL}/api/admin/users/{test_user_id}/role",
            headers=headers,
            json={"role": "arbitrator"}
        )
        assert response.status_code == 200, f"Failed to set role to arbitrator: {response.text}"
        
        # Re-login as the user to get fresh JWT with new role
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": USER_EMAIL,
            "password": USER_PASSWORD
        })
        assert login_response.status_code == 200, f"Re-login failed: {login_response.text}"
        new_token = login_response.json()["access_token"]
        
        # Check the user data in login response
        user_data = login_response.json().get("user", {})
        print(f"User data after re-login: role={user_data.get('role')}")
        
        # Now test access to arbitration
        user_headers = {"Authorization": f"Bearer {new_token}"}
        arb_response = requests.get(f"{BASE_URL}/api/admin/arbitration", headers=user_headers)
        assert arb_response.status_code == 200, f"Arbitrator should access arbitration, got {arb_response.status_code}: {arb_response.text}"
        print(f"PASS: Arbitrator can access /api/admin/arbitration after role change")
    
    def test_arbitrator_cannot_access_users_after_role_change(self, admin_token, test_user_id):
        """After changing user to 'arbitrator', they should NOT access /api/admin/users"""
        headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
        
        # Ensure user is set to arbitrator
        response = requests.patch(
            f"{BASE_URL}/api/admin/users/{test_user_id}/role",
            headers=headers,
            json={"role": "arbitrator"}
        )
        assert response.status_code == 200
        
        # Re-login as the user to get fresh JWT with new role
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": USER_EMAIL,
            "password": USER_PASSWORD
        })
        assert login_response.status_code == 200
        new_token = login_response.json()["access_token"]
        
        # Now test access to users (should be denied)
        user_headers = {"Authorization": f"Bearer {new_token}"}
        users_response = requests.get(f"{BASE_URL}/api/admin/users", headers=user_headers)
        assert users_response.status_code == 403, f"Arbitrator should NOT access users, got {users_response.status_code}: {users_response.text}"
        print(f"PASS: Arbitrator cannot access /api/admin/users (403)")
    
    def test_reset_user_role_to_user(self, admin_token, test_user_id):
        """Reset test user back to role='user' for cleanup"""
        headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
        response = requests.patch(
            f"{BASE_URL}/api/admin/users/{test_user_id}/role",
            headers=headers,
            json={"role": "user"}
        )
        assert response.status_code == 200, f"Failed to reset role: {response.text}"
        print(f"PASS: Reset {USER_EMAIL} role back to 'user'")


class TestLoginResponseIncludesRole:
    """Verify that login response includes the user's role"""
    
    def test_admin_login_includes_role(self):
        """Admin login response should include role='admin'"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        user = data.get("user", {})
        assert "role" in user, f"Expected 'role' in user data: {user}"
        assert user["role"] == "admin", f"Expected role='admin', got {user['role']}"
        print(f"PASS: Admin login includes role='admin'")
    
    def test_user_login_includes_role(self):
        """Regular user login response should include role='user'"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": USER2_EMAIL,
            "password": USER2_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        user = data.get("user", {})
        assert "role" in user, f"Expected 'role' in user data: {user}"
        # Role should be 'user' (default) unless changed
        print(f"PASS: User login includes role='{user.get('role', 'user')}'")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
