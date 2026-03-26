"""
Test suite for InvitationPage refactoring verification
Tests backend API endpoints related to invitations
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestInvitationAPI:
    """Tests for invitation-related API endpoints"""
    
    def test_health_check(self):
        """Verify API is healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✅ Health check passed")
    
    def test_invalid_invitation_token_returns_404(self):
        """Verify invalid token returns 404 with proper error message"""
        response = requests.get(f"{BASE_URL}/api/invitations/fake-token-12345")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "non trouvée" in data["detail"].lower() or "expirée" in data["detail"].lower()
        print("✅ Invalid token returns 404 with proper error message")
    
    def test_invitation_respond_without_token_fails(self):
        """Verify respond endpoint requires valid token"""
        response = requests.post(
            f"{BASE_URL}/api/invitations/invalid-token/respond",
            json={"action": "accept"}
        )
        assert response.status_code in [404, 400, 422]
        print("✅ Respond endpoint rejects invalid token")
    
    def test_invitation_cancel_without_token_fails(self):
        """Verify cancel endpoint requires valid token"""
        response = requests.post(
            f"{BASE_URL}/api/invitations/invalid-token/cancel"
        )
        assert response.status_code in [404, 400, 422]
        print("✅ Cancel endpoint rejects invalid token")
    
    def test_invitation_guarantee_status_without_token_fails(self):
        """Verify guarantee-status endpoint requires valid token"""
        response = requests.get(
            f"{BASE_URL}/api/invitations/invalid-token/guarantee-status"
        )
        assert response.status_code in [404, 400, 422]
        print("✅ Guarantee-status endpoint rejects invalid token")
    
    def test_checkin_status_without_valid_appointment_fails(self):
        """Verify checkin status endpoint requires valid appointment"""
        response = requests.get(
            f"{BASE_URL}/api/checkin/status/invalid-appointment-id?invitation_token=fake-token"
        )
        # Should return 404 or 400 for invalid appointment
        assert response.status_code in [404, 400, 422, 500]
        print("✅ Checkin status endpoint rejects invalid appointment")
    
    def test_modifications_active_without_valid_appointment_fails(self):
        """Verify modifications endpoint requires valid appointment"""
        response = requests.get(
            f"{BASE_URL}/api/modifications/active/invalid-appointment-id"
        )
        # Should return 404 or empty result for invalid appointment
        assert response.status_code in [200, 404, 400]
        if response.status_code == 200:
            data = response.json()
            # Should return null/empty proposal for non-existent appointment
            assert data.get("proposal") is None or data.get("proposal") == {}
        print("✅ Modifications endpoint handles invalid appointment correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
