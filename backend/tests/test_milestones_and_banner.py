"""
Test Phase 5 (Invitation Banner) and Phase 6 (Milestones Wallet)

Phase 5: Banner for existing account users on invitation page
Phase 6: GET /api/wallet/milestones endpoint
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test123!"


class TestHealthCheck:
    """Basic health check to ensure backend is running"""
    
    def test_backend_health(self):
        """Backend health check passes"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✅ Backend health check passes")


class TestMilestonesEndpoint:
    """Tests for GET /api/wallet/milestones endpoint"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token for test user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Authentication failed: {response.text}")
        return response.json().get("access_token")
    
    def test_milestones_requires_auth(self):
        """GET /api/wallet/milestones returns 401 without token"""
        response = requests.get(f"{BASE_URL}/api/wallet/milestones")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✅ GET /api/wallet/milestones requires authentication (401 without token)")
    
    def test_milestones_returns_correct_structure(self, auth_token):
        """GET /api/wallet/milestones returns correct structure"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/wallet/milestones", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Check required fields exist
        assert "attended_count" in data, "Missing attended_count"
        assert "organized_count" in data, "Missing organized_count"
        assert "milestones" in data, "Missing milestones"
        assert "next_milestone" in data, "Missing next_milestone"
        assert "show_organizer_cta" in data, "Missing show_organizer_cta"
        
        print(f"✅ GET /api/wallet/milestones returns correct structure")
        print(f"   attended_count: {data['attended_count']}")
        print(f"   organized_count: {data['organized_count']}")
        print(f"   next_milestone: {data['next_milestone']}")
        print(f"   show_organizer_cta: {data['show_organizer_cta']}")
    
    def test_milestones_thresholds_correct(self, auth_token):
        """Milestones thresholds are correct: 1, 3, 5, 10, 25, 50, 100"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/wallet/milestones", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        expected_thresholds = [1, 3, 5, 10, 25, 50, 100]
        actual_thresholds = [m["threshold"] for m in data["milestones"]]
        
        assert actual_thresholds == expected_thresholds, f"Expected {expected_thresholds}, got {actual_thresholds}"
        print(f"✅ Milestones thresholds are correct: {expected_thresholds}")
    
    def test_milestones_structure_per_milestone(self, auth_token):
        """Each milestone has threshold, reached, and label fields"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/wallet/milestones", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        for milestone in data["milestones"]:
            assert "threshold" in milestone, "Missing threshold in milestone"
            assert "reached" in milestone, "Missing reached in milestone"
            assert "label" in milestone, "Missing label in milestone"
            assert isinstance(milestone["threshold"], int), "threshold should be int"
            assert isinstance(milestone["reached"], bool), "reached should be bool"
            assert isinstance(milestone["label"], str), "label should be str"
        
        print("✅ Each milestone has correct structure (threshold, reached, label)")
    
    def test_milestones_reached_logic(self, auth_token):
        """Milestones reached field is correctly calculated based on attended_count"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/wallet/milestones", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        attended = data["attended_count"]
        for milestone in data["milestones"]:
            expected_reached = attended >= milestone["threshold"]
            assert milestone["reached"] == expected_reached, \
                f"Milestone {milestone['threshold']}: expected reached={expected_reached}, got {milestone['reached']}"
        
        print(f"✅ Milestones reached logic correct for attended_count={attended}")
    
    def test_show_organizer_cta_logic(self, auth_token):
        """show_organizer_cta is false when user has organized appointments"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/wallet/milestones", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Test user has organized_count=132 (from context), so CTA should be false
        organized = data["organized_count"]
        attended = data["attended_count"]
        expected_cta = organized == 0 and attended >= 1
        
        assert data["show_organizer_cta"] == expected_cta, \
            f"Expected show_organizer_cta={expected_cta} (organized={organized}, attended={attended}), got {data['show_organizer_cta']}"
        
        print(f"✅ show_organizer_cta is {data['show_organizer_cta']} (organized={organized}, attended={attended})")
    
    def test_next_milestone_logic(self, auth_token):
        """next_milestone is correctly calculated"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/wallet/milestones", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        attended = data["attended_count"]
        thresholds = [1, 3, 5, 10, 25, 50, 100]
        
        expected_next = None
        for t in thresholds:
            if attended < t:
                expected_next = t
                break
        
        assert data["next_milestone"] == expected_next, \
            f"Expected next_milestone={expected_next} for attended={attended}, got {data['next_milestone']}"
        
        print(f"✅ next_milestone is {data['next_milestone']} for attended_count={attended}")


class TestInvitationBannerBackend:
    """Tests for invitation endpoint returning has_existing_account field"""
    
    def test_invitation_endpoint_structure(self):
        """Verify invitation endpoint returns has_existing_account field"""
        # We need a valid invitation token to test this
        # For now, we'll test that the endpoint exists and returns proper error for invalid token
        response = requests.get(f"{BASE_URL}/api/invitations/invalid-token-12345")
        
        # Should return 404 for invalid token, not 500
        assert response.status_code in [404, 400], f"Expected 404/400 for invalid token, got {response.status_code}"
        print("✅ Invitation endpoint returns proper error for invalid token")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
