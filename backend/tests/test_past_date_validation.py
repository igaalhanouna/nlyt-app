"""
Test Past Date Validation for Appointments
Bug fix: Prevent creating appointments in the past
- Backend: POST /api/appointments/ with past date returns 400
- Backend: POST /api/appointments/ with future date succeeds (201/200)
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://location-proof-1.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"
WORKSPACE_ID = "7e219321-18fd-4643-9be6-e4f1de88a2a8"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    # Auth response uses 'access_token' not 'token'
    token = data.get("access_token") or data.get("token")
    assert token, f"No token in response: {data}"
    return token


@pytest.fixture
def authenticated_client(auth_token):
    """Session with auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


def get_valid_appointment_payload(start_datetime_utc: str):
    """Generate a valid appointment payload with given start_datetime"""
    return {
        "workspace_id": WORKSPACE_ID,
        "title": f"Test Appointment {datetime.utcnow().isoformat()}",
        "appointment_type": "physical",
        "location": "123 Test Street, Paris",
        "start_datetime": start_datetime_utc,
        "duration_minutes": 60,
        "tolerated_delay_minutes": 15,
        "cancellation_deadline_hours": 24,
        "penalty_amount": 50,
        "penalty_currency": "eur",
        "affected_compensation_percent": 80,
        "charity_percent": 0,
        "participants": [
            {
                "first_name": "Test",
                "last_name": "Participant",
                "email": "test_participant@example.com",
                "role": "participant"
            }
        ]
    }


class TestPastDateValidation:
    """Test past date validation for appointment creation"""

    def test_api_health(self):
        """Test API is accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        print("✓ API health check passed")

    def test_create_appointment_with_past_date_returns_400(self, authenticated_client):
        """
        Backend: POST /api/appointments/ with past date returns 400
        with message 'Impossible de créer un rendez-vous dans le passé'
        """
        # Create a date 1 day in the past
        past_date = datetime.utcnow() - timedelta(days=1)
        past_date_utc = past_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        payload = get_valid_appointment_payload(past_date_utc)
        
        response = authenticated_client.post(f"{BASE_URL}/api/appointments/", json=payload)
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        
        data = response.json()
        detail = data.get("detail", "")
        assert "Impossible de créer un rendez-vous dans le passé" in detail, f"Expected error message, got: {detail}"
        
        print(f"✓ Past date (1 day ago) correctly rejected with 400: {detail}")

    def test_create_appointment_with_past_hour_today_returns_400(self, authenticated_client):
        """
        Backend: POST /api/appointments/ with today but past hour returns 400
        """
        # Create a date 2 hours in the past (same day)
        past_hour = datetime.utcnow() - timedelta(hours=2)
        past_hour_utc = past_hour.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        payload = get_valid_appointment_payload(past_hour_utc)
        
        response = authenticated_client.post(f"{BASE_URL}/api/appointments/", json=payload)
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        
        data = response.json()
        detail = data.get("detail", "")
        assert "Impossible de créer un rendez-vous dans le passé" in detail, f"Expected error message, got: {detail}"
        
        print(f"✓ Past hour (2 hours ago) correctly rejected with 400: {detail}")

    def test_create_appointment_with_future_date_succeeds(self, authenticated_client):
        """
        Backend: POST /api/appointments/ with future date succeeds (201/200)
        """
        # Create a date 7 days in the future
        future_date = datetime.utcnow() + timedelta(days=7)
        future_date_utc = future_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        payload = get_valid_appointment_payload(future_date_utc)
        
        response = authenticated_client.post(f"{BASE_URL}/api/appointments/", json=payload)
        
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "appointment_id" in data, f"Expected appointment_id in response: {data}"
        
        print(f"✓ Future date (7 days ahead) correctly accepted: appointment_id={data['appointment_id']}")
        
        # Cleanup: delete the test appointment
        appointment_id = data['appointment_id']
        delete_response = authenticated_client.delete(f"{BASE_URL}/api/appointments/{appointment_id}")
        print(f"  Cleanup: deleted test appointment {appointment_id}")

    def test_create_appointment_with_future_hour_today_succeeds(self, authenticated_client):
        """
        Backend: POST /api/appointments/ with today but future hour succeeds
        """
        # Create a date 3 hours in the future (same day)
        future_hour = datetime.utcnow() + timedelta(hours=3)
        future_hour_utc = future_hour.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        payload = get_valid_appointment_payload(future_hour_utc)
        
        response = authenticated_client.post(f"{BASE_URL}/api/appointments/", json=payload)
        
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "appointment_id" in data, f"Expected appointment_id in response: {data}"
        
        print(f"✓ Future hour (3 hours ahead) correctly accepted: appointment_id={data['appointment_id']}")
        
        # Cleanup: delete the test appointment
        appointment_id = data['appointment_id']
        delete_response = authenticated_client.delete(f"{BASE_URL}/api/appointments/{appointment_id}")
        print(f"  Cleanup: deleted test appointment {appointment_id}")

    def test_create_appointment_with_exact_now_returns_400(self, authenticated_client):
        """
        Backend: POST /api/appointments/ with exact current time returns 400
        (edge case: start_datetime <= now should fail)
        """
        # Use exact current time
        now_utc = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        
        payload = get_valid_appointment_payload(now_utc)
        
        response = authenticated_client.post(f"{BASE_URL}/api/appointments/", json=payload)
        
        # Should be rejected because start_datetime <= now
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        
        data = response.json()
        detail = data.get("detail", "")
        assert "Impossible de créer un rendez-vous dans le passé" in detail, f"Expected error message, got: {detail}"
        
        print(f"✓ Exact current time correctly rejected with 400: {detail}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
