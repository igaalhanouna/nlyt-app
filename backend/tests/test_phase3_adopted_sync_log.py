"""
Phase 3 V2 NLYT: Adopted sync_log + anti-doublons + cohérence auto-sync calendrier

Tests for:
1. Backend starts correctly after Phase 3 changes
2. GET /api/external-events/import-settings still works (no regression)
3. POST /api/external-events/sync still works (no regression)
4. GET /api/external-events/ still works (no regression)
5. GET /api/external-events/{id}/prefill returns 404 for non-existent event
6. POST /api/appointments/ creation still works (no regression from from_external_event_id)
7. Authentication still works at /api/auth/login
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "stripe-test@nlyt.io"
TEST_PASSWORD = "Test123!"


class TestPhase3BackendRegression:
    """Phase 3 regression tests - ensure no breaking changes"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for test user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token") or data.get("token")
        pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_health_endpoint(self):
        """Test backend health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✅ GET /api/health returns healthy status")
    
    def test_auth_login_works(self):
        """Test authentication still works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data or "token" in data
        assert "user" in data
        print("✅ POST /api/auth/login works with test credentials")
    
    def test_external_events_import_settings(self, auth_headers):
        """Test GET /api/external-events/import-settings still works"""
        response = requests.get(
            f"{BASE_URL}/api/external-events/import-settings",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        print("✅ GET /api/external-events/import-settings still works (no regression)")
    
    def test_external_events_sync(self, auth_headers):
        """Test POST /api/external-events/sync still works"""
        response = requests.post(
            f"{BASE_URL}/api/external-events/sync",
            headers=auth_headers,
            json={}
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        print("✅ POST /api/external-events/sync still works (no regression)")
    
    def test_external_events_list(self, auth_headers):
        """Test GET /api/external-events/ still works"""
        response = requests.get(
            f"{BASE_URL}/api/external-events/",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert "providers" in data or "active_providers" in data
        print("✅ GET /api/external-events/ still works (no regression)")
    
    def test_external_events_prefill_404_for_nonexistent(self, auth_headers):
        """Test GET /api/external-events/{id}/prefill returns 404 for non-existent event"""
        fake_id = str(uuid.uuid4())
        response = requests.get(
            f"{BASE_URL}/api/external-events/{fake_id}/prefill",
            headers=auth_headers
        )
        assert response.status_code == 404
        print("✅ GET /api/external-events/{id}/prefill returns 404 for non-existent event")
    
    def test_external_events_prefill_requires_auth(self):
        """Test GET /api/external-events/{id}/prefill requires authentication"""
        fake_id = str(uuid.uuid4())
        response = requests.get(f"{BASE_URL}/api/external-events/{fake_id}/prefill")
        assert response.status_code == 401
        print("✅ GET /api/external-events/{id}/prefill requires auth (401 without token)")
    
    def test_appointments_list(self, auth_headers):
        """Test GET /api/appointments/ still works"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        print("✅ GET /api/appointments/ list works (no regression)")
    
    def test_workspaces_list(self, auth_headers):
        """Test GET /api/workspaces/ still works"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "workspaces" in data
        print("✅ GET /api/workspaces/ works (regression test)")
    
    def test_calendar_connections(self, auth_headers):
        """Test GET /api/calendar/connections still works"""
        response = requests.get(
            f"{BASE_URL}/api/calendar/connections",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "connections" in data
        print("✅ GET /api/calendar/connections works (regression test)")


class TestPhase3AppointmentCreation:
    """Test appointment creation with from_external_event_id field"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for test user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token") or data.get("token")
        pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    @pytest.fixture(scope="class")
    def workspace_id(self, auth_headers):
        """Get first workspace ID for test user"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/",
            headers=auth_headers
        )
        if response.status_code == 200:
            workspaces = response.json().get("workspaces", [])
            if workspaces:
                return workspaces[0]["workspace_id"]
        pytest.skip("No workspace available for test user")
    
    def test_appointment_creation_without_external_event(self, auth_headers, workspace_id):
        """Test POST /api/appointments/ works without from_external_event_id (backward compatibility)"""
        from datetime import datetime, timedelta
        
        # Create appointment in the future
        future_date = datetime.now() + timedelta(days=7)
        start_datetime = future_date.strftime("%Y-%m-%dT10:00:00Z")
        
        payload = {
            "workspace_id": workspace_id,
            "title": f"TEST_Phase3_NoExternal_{uuid.uuid4().hex[:8]}",
            "appointment_type": "physical",
            "location": "123 Test Street, Paris",
            "start_datetime": start_datetime,
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
                    "email": f"test_phase3_{uuid.uuid4().hex[:8]}@example.com"
                }
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/appointments/",
            headers=auth_headers,
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "appointment_id" in data
        assert data.get("status") in ["active", "pending_organizer_guarantee"]
        print("✅ POST /api/appointments/ works without from_external_event_id (backward compatibility)")
        
        # Cleanup: delete the test appointment
        apt_id = data["appointment_id"]
        requests.delete(f"{BASE_URL}/api/appointments/{apt_id}", headers=auth_headers)
    
    def test_appointment_creation_with_nonexistent_external_event(self, auth_headers, workspace_id):
        """Test POST /api/appointments/ with non-existent from_external_event_id (should work, just no conversion)"""
        from datetime import datetime, timedelta
        
        future_date = datetime.now() + timedelta(days=7)
        start_datetime = future_date.strftime("%Y-%m-%dT11:00:00Z")
        
        payload = {
            "workspace_id": workspace_id,
            "title": f"TEST_Phase3_FakeExternal_{uuid.uuid4().hex[:8]}",
            "appointment_type": "physical",
            "location": "456 Test Avenue, Paris",
            "start_datetime": start_datetime,
            "duration_minutes": 60,
            "tolerated_delay_minutes": 15,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "affected_compensation_percent": 80,
            "charity_percent": 0,
            "from_external_event_id": str(uuid.uuid4()),  # Non-existent external event
            "participants": [
                {
                    "first_name": "Test",
                    "last_name": "Participant2",
                    "email": f"test_phase3_ext_{uuid.uuid4().hex[:8]}@example.com"
                }
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/appointments/",
            headers=auth_headers,
            json=payload
        )
        
        # Should succeed - non-existent external event is handled gracefully
        assert response.status_code == 200
        data = response.json()
        assert "appointment_id" in data
        # Should NOT have converted_from_external since event doesn't exist
        assert data.get("converted_from_external") is not True
        print("✅ POST /api/appointments/ with non-existent from_external_event_id works (graceful handling)")
        
        # Cleanup
        apt_id = data["appointment_id"]
        requests.delete(f"{BASE_URL}/api/appointments/{apt_id}", headers=auth_headers)


class TestPhase3CalendarRoutes:
    """Test calendar routes still work after Phase 3 changes"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for test user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token") or data.get("token")
        pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_auto_sync_settings(self, auth_headers):
        """Test GET /api/calendar/auto-sync/settings still works"""
        response = requests.get(
            f"{BASE_URL}/api/calendar/auto-sync/settings",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "auto_sync_enabled" in data
        assert "connected_providers" in data
        print("✅ GET /api/calendar/auto-sync/settings works (no regression)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
