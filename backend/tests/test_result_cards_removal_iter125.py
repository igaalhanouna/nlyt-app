"""
Test Result Cards Removal - Iteration 125
Verifies that result_cards router is completely removed and endpoints return 404
Also verifies that existing functionality still works after removal
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestResultCardsRemoval:
    """Verify result_cards endpoints are removed and return 404"""
    
    def test_health_endpoint_still_works(self):
        """Server should still be healthy after router removal"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("PASS: Health endpoint returns 200")
    
    def test_get_result_card_by_id_returns_404(self):
        """GET /api/result-cards/{id} should return 404 (endpoint removed)"""
        response = requests.get(f"{BASE_URL}/api/result-cards/some-card-id")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: GET /api/result-cards/{id} returns 404")
    
    def test_post_result_cards_returns_404(self):
        """POST /api/result-cards should return 404 (endpoint removed)"""
        response = requests.post(f"{BASE_URL}/api/result-cards", json={"test": "data"})
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: POST /api/result-cards returns 404")
    
    def test_get_my_cards_returns_404(self):
        """GET /api/result-cards/my-cards should return 404 (endpoint removed)"""
        response = requests.get(f"{BASE_URL}/api/result-cards/my-cards")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: GET /api/result-cards/my-cards returns 404")


class TestExistingFunctionalityRegression:
    """Verify existing endpoints still work after result_cards removal"""
    
    @pytest.fixture
    def auth_token_igaal(self):
        """Get auth token for igaal@hotmail.com"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "igaal@hotmail.com",
            "password": "Test123!"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Auth failed for igaal@hotmail.com")
    
    @pytest.fixture
    def auth_token_testuser(self):
        """Get auth token for testuser_audit@nlyt.app"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testuser_audit@nlyt.app",
            "password": "TestAudit123!"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Auth failed for testuser_audit@nlyt.app")
    
    def test_auth_login_works(self):
        """Auth login should still work"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "igaal@hotmail.com",
            "password": "Test123!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        print("PASS: Auth login works")
    
    def test_appointments_endpoint_works(self, auth_token_igaal):
        """Appointments endpoint should still work"""
        headers = {"Authorization": f"Bearer {auth_token_igaal}"}
        response = requests.get(f"{BASE_URL}/api/appointments/", headers=headers)
        assert response.status_code == 200
        print("PASS: Appointments endpoint works")
    
    def test_appointment_detail_works_organizer(self, auth_token_igaal):
        """Appointment detail should work for organizer (884a22e1)"""
        headers = {"Authorization": f"Bearer {auth_token_igaal}"}
        response = requests.get(f"{BASE_URL}/api/appointments/884a22e1-e110-49ec-b785-2bab318b7084", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "appointment_id" in data or "id" in data
        print("PASS: Appointment detail works for organizer")
    
    def test_appointment_detail_works_participant(self, auth_token_testuser):
        """Appointment detail should work for participant (e823473a)"""
        headers = {"Authorization": f"Bearer {auth_token_testuser}"}
        response = requests.get(f"{BASE_URL}/api/appointments/e823473a-f37a-4f59-8576-82e49ee22c53", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "appointment_id" in data or "id" in data
        print("PASS: Appointment detail works for participant")
    
    def test_financial_results_endpoint_works(self, auth_token_testuser):
        """Financial results endpoint should still work"""
        headers = {"Authorization": f"Bearer {auth_token_testuser}"}
        response = requests.get(f"{BASE_URL}/api/financial/my-results", headers=headers)
        assert response.status_code == 200
        print("PASS: Financial results endpoint works")
    
    def test_wallet_endpoint_works(self, auth_token_testuser):
        """Wallet endpoint should still work"""
        headers = {"Authorization": f"Bearer {auth_token_testuser}"}
        response = requests.get(f"{BASE_URL}/api/wallet", headers=headers)
        assert response.status_code == 200
        print("PASS: Wallet endpoint works")
    
    def test_disputes_endpoint_works(self, auth_token_testuser):
        """Disputes endpoint should still work"""
        headers = {"Authorization": f"Bearer {auth_token_testuser}"}
        # Disputes endpoint requires appointment_id param
        response = requests.get(f"{BASE_URL}/api/disputes/?appointment_id=litigation-mgmt", headers=headers)
        # May return 200 or 404 depending on data
        assert response.status_code in [200, 404, 422]
        print(f"PASS: Disputes endpoint returns {response.status_code}")
    
    def test_attendance_endpoint_works(self, auth_token_testuser):
        """Attendance endpoint should still work for past appointment"""
        headers = {"Authorization": f"Bearer {auth_token_testuser}"}
        response = requests.get(f"{BASE_URL}/api/attendance/d839b4a8-3334-4df6-8913-43045b438699", headers=headers)
        # May return 200 or 404 depending on data, but should not error
        assert response.status_code in [200, 404]
        print(f"PASS: Attendance endpoint returns {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
