"""
Test Phase 2 V2 External Events: Prefill endpoint, from_external_event_id, conversion flow
Tests:
- GET /api/external-events/{id}/prefill returns 404 for non-existent event
- GET /api/external-events/{id}/prefill requires authentication (401 without token)
- POST /api/appointments/ still works (no regression)
- Phase 1 endpoints still work (GET /import-settings, POST /sync, GET /)
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "stripe-test@nlyt.io"
TEST_PASSWORD = "Test123!"


class TestPhase2ExternalEventsPrefill:
    """Tests for the new /prefill endpoint in Phase 2"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for test user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json().get("access_token")
    
    def test_prefill_requires_authentication(self):
        """GET /api/external-events/{id}/prefill returns 401 without token"""
        response = requests.get(f"{BASE_URL}/api/external-events/fake-event-id/prefill")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ GET /api/external-events/{id}/prefill requires auth (401 without token)")
    
    def test_prefill_returns_404_for_nonexistent_event(self, auth_token):
        """GET /api/external-events/{id}/prefill returns 404 for non-existent event"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(
            f"{BASE_URL}/api/external-events/nonexistent-event-12345/prefill",
            headers=headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data
        print(f"✅ GET /api/external-events/{{id}}/prefill returns 404 for non-existent event: {data['detail']}")
    
    def test_prefill_returns_404_for_random_uuid(self, auth_token):
        """GET /api/external-events/{id}/prefill returns 404 for random UUID"""
        import uuid
        headers = {"Authorization": f"Bearer {auth_token}"}
        random_id = str(uuid.uuid4())
        response = requests.get(
            f"{BASE_URL}/api/external-events/{random_id}/prefill",
            headers=headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"✅ GET /api/external-events/{{id}}/prefill returns 404 for random UUID")


class TestPhase1EndpointsRegression:
    """Regression tests for Phase 1 endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for test user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json().get("access_token")
    
    def test_import_settings_still_works(self, auth_token):
        """GET /api/external-events/import-settings still works"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/external-events/import-settings", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "providers" in data
        print(f"✅ GET /api/external-events/import-settings works: {data}")
    
    def test_sync_still_works(self, auth_token):
        """POST /api/external-events/sync still works"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(f"{BASE_URL}/api/external-events/sync", headers=headers, json={})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "results" in data
        print(f"✅ POST /api/external-events/sync works: {data}")
    
    def test_list_external_events_still_works(self, auth_token):
        """GET /api/external-events/ still works"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/external-events/", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "events" in data
        assert "providers" in data
        print(f"✅ GET /api/external-events/ works: events={len(data['events'])}, providers={data['providers']}")


class TestAppointmentsNoRegression:
    """Regression tests for appointments API"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for test user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json().get("access_token")
    
    @pytest.fixture(scope="class")
    def workspace_id(self, auth_token):
        """Get workspace ID for test user"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/workspaces/", headers=headers)
        assert response.status_code == 200
        data = response.json()
        workspaces = data.get("workspaces", data) if isinstance(data, dict) else data
        assert len(workspaces) > 0, "No workspaces found"
        return workspaces[0]["workspace_id"]
    
    def test_appointments_list_works(self, auth_token, workspace_id):
        """GET /api/appointments/ still works"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(
            f"{BASE_URL}/api/appointments/",
            headers=headers,
            params={"workspace_id": workspace_id}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "items" in data
        assert "total" in data
        print(f"✅ GET /api/appointments/ works: total={data['total']}")
    
    def test_appointments_create_with_from_external_event_id_field(self, auth_token, workspace_id):
        """POST /api/appointments/ accepts from_external_event_id field (optional)"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Create appointment with from_external_event_id (should be ignored if event doesn't exist)
        future_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%dT14:00")
        payload = {
            "workspace_id": workspace_id,
            "title": "TEST_Phase2_Appointment",
            "appointment_type": "physical",
            "location": "123 Test Street, Paris",
            "start_datetime": future_date,
            "duration_minutes": 60,
            "tolerated_delay_minutes": 15,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 10,
            "penalty_currency": "eur",
            "affected_compensation_percent": 80,
            "charity_percent": 0,
            "participants": [
                {"first_name": "Test", "last_name": "User", "email": "test-phase2@example.com"}
            ],
            "from_external_event_id": "nonexistent-external-event-id"  # Should be handled gracefully
        }
        
        response = requests.post(f"{BASE_URL}/api/appointments/", headers=headers, json=payload)
        # Should succeed - from_external_event_id is optional and non-existent event is handled gracefully
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "appointment_id" in data
        appointment_id = data["appointment_id"]
        print(f"✅ POST /api/appointments/ works with from_external_event_id field: {appointment_id}")
        
        # Cleanup: delete the test appointment
        delete_response = requests.delete(f"{BASE_URL}/api/appointments/{appointment_id}", headers=headers)
        assert delete_response.status_code == 200, f"Cleanup failed: {delete_response.text}"
        print(f"✅ Cleanup: deleted test appointment {appointment_id}")
    
    def test_appointments_create_without_from_external_event_id(self, auth_token, workspace_id):
        """POST /api/appointments/ works without from_external_event_id (backward compatibility)"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        future_date = (datetime.now() + timedelta(days=8)).strftime("%Y-%m-%dT15:00")
        payload = {
            "workspace_id": workspace_id,
            "title": "TEST_Phase2_NoExternal",
            "appointment_type": "physical",
            "location": "456 Test Avenue, Paris",
            "start_datetime": future_date,
            "duration_minutes": 45,
            "tolerated_delay_minutes": 10,
            "cancellation_deadline_hours": 12,
            "penalty_amount": 15,
            "penalty_currency": "eur",
            "affected_compensation_percent": 80,
            "charity_percent": 0,
            "participants": [
                {"first_name": "Backward", "last_name": "Compat", "email": "backward-compat@example.com"}
            ]
            # No from_external_event_id - backward compatibility
        }
        
        response = requests.post(f"{BASE_URL}/api/appointments/", headers=headers, json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "appointment_id" in data
        appointment_id = data["appointment_id"]
        print(f"✅ POST /api/appointments/ works without from_external_event_id: {appointment_id}")
        
        # Cleanup
        delete_response = requests.delete(f"{BASE_URL}/api/appointments/{appointment_id}", headers=headers)
        assert delete_response.status_code == 200
        print(f"✅ Cleanup: deleted test appointment {appointment_id}")


class TestHealthAndAuth:
    """Basic health and auth tests"""
    
    def test_health_endpoint(self):
        """GET /api/health returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("✅ GET /api/health returns healthy status")
    
    def test_login_works(self):
        """POST /api/auth/login works with test credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        print(f"✅ POST /api/auth/login works: user={data['user']['email']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
