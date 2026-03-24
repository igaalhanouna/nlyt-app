"""
Test Video Provider Selection Feature (Option A Enriched)
Tests for:
- GET /api/video-evidence/provider-status returns can_auto_generate and unavailable_reason
- Teams can_auto_generate=false when has_online_meetings_scope is not true
- Meet can_auto_generate=true when Google Calendar connected
- Zoom can_auto_generate=true when platform configured AND user connected
- External can_auto_generate=true always
- Backend validation: POST /api/appointments/ rejects invalid provider choices
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test user."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Return headers with auth token."""
    return {"Authorization": f"Bearer {auth_token}"}


class TestProviderStatusEndpoint:
    """Tests for GET /api/video-evidence/provider-status endpoint."""

    def test_provider_status_returns_all_providers(self, auth_headers):
        """Provider status endpoint returns all 4 providers."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # All 4 providers must be present
        assert "teams" in data, "teams provider missing"
        assert "meet" in data, "meet provider missing"
        assert "zoom" in data, "zoom provider missing"
        assert "external" in data, "external provider missing"

    def test_provider_status_has_can_auto_generate(self, auth_headers):
        """Each provider has can_auto_generate field."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for provider in ["teams", "meet", "zoom", "external"]:
            assert "can_auto_generate" in data[provider], f"{provider} missing can_auto_generate"
            assert isinstance(data[provider]["can_auto_generate"], bool), f"{provider} can_auto_generate not boolean"

    def test_provider_status_has_unavailable_reason(self, auth_headers):
        """Each provider has unavailable_reason field."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for provider in ["teams", "meet", "zoom", "external"]:
            assert "unavailable_reason" in data[provider], f"{provider} missing unavailable_reason"

    def test_teams_unavailable_without_advanced_scope(self, auth_headers):
        """Teams can_auto_generate=false when has_online_meetings_scope is not true."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Test user has Outlook connected but NO Teams advanced scope
        teams = data["teams"]
        assert teams["can_auto_generate"] is False, "Teams should be unavailable without advanced scope"
        assert teams["unavailable_reason"] is not None, "Teams should have unavailable_reason"
        assert "Teams avancé" in teams["unavailable_reason"] or "Microsoft 365" in teams["unavailable_reason"], \
            f"Teams unavailable_reason should mention Teams avancé or M365: {teams['unavailable_reason']}"

    def test_meet_available_with_google_connected(self, auth_headers):
        """Meet can_auto_generate=true when Google Calendar connected."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Test user has Google connected
        meet = data["meet"]
        assert meet["can_auto_generate"] is True, "Meet should be available with Google connected"
        assert meet["unavailable_reason"] is None, "Meet should have no unavailable_reason"
        assert meet["email"] is not None, "Meet should show connected email"

    def test_zoom_available_when_configured_and_connected(self, auth_headers):
        """Zoom can_auto_generate=true when platform configured AND user connected."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Test user has Zoom connected
        zoom = data["zoom"]
        assert zoom["can_auto_generate"] is True, "Zoom should be available when configured and connected"
        assert zoom["unavailable_reason"] is None, "Zoom should have no unavailable_reason"
        assert zoom["email"] is not None, "Zoom should show connected email"

    def test_external_always_available(self, auth_headers):
        """External can_auto_generate=true always."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        external = data["external"]
        assert external["can_auto_generate"] is True, "External should always be available"
        assert external["unavailable_reason"] is None, "External should have no unavailable_reason"
        assert external["label"] == "Autre plateforme", f"External label should be 'Autre plateforme', got: {external['label']}"


class TestAppointmentProviderValidation:
    """Tests for backend validation of meeting_provider in POST /api/appointments/."""

    @pytest.fixture
    def workspace_id(self, auth_headers):
        """Get a workspace ID for the test user."""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/",
            headers=auth_headers
        )
        assert response.status_code == 200
        workspaces = response.json().get("workspaces", [])
        assert len(workspaces) > 0, "Test user has no workspaces"
        return workspaces[0]["workspace_id"]

    def test_reject_teams_without_advanced_scope(self, auth_headers, workspace_id):
        """POST /api/appointments/ rejects meeting_provider=teams when Teams advanced not active."""
        from datetime import datetime, timedelta
        
        future_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT10:00:00")
        
        payload = {
            "workspace_id": workspace_id,
            "title": "TEST_Teams_Validation",
            "appointment_type": "video",
            "meeting_provider": "teams",
            "start_datetime": future_date,
            "duration_minutes": 60,
            "tolerated_delay_minutes": 15,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "affected_compensation_percent": 80,
            "charity_percent": 0,
            "participants": [
                {"first_name": "Test", "last_name": "User", "email": "test@example.com"}
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/appointments/",
            json=payload,
            headers=auth_headers
        )
        
        # Should be rejected with 400
        assert response.status_code == 400, f"Expected 400 for Teams without advanced scope, got {response.status_code}: {response.text}"
        error_detail = response.json().get("detail", "")
        assert "Teams" in error_detail or "Microsoft" in error_detail, \
            f"Error should mention Teams/Microsoft: {error_detail}"

    def test_accept_meet_with_google_connected(self, auth_headers, workspace_id):
        """POST /api/appointments/ accepts meeting_provider=meet when Google connected."""
        from datetime import datetime, timedelta
        
        future_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT11:00:00")
        
        payload = {
            "workspace_id": workspace_id,
            "title": "TEST_Meet_Validation",
            "appointment_type": "video",
            "meeting_provider": "meet",
            "start_datetime": future_date,
            "duration_minutes": 60,
            "tolerated_delay_minutes": 15,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "affected_compensation_percent": 80,
            "charity_percent": 0,
            "participants": [
                {"first_name": "Test", "last_name": "User", "email": "test@example.com"}
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/appointments/",
            json=payload,
            headers=auth_headers
        )
        
        # Should be accepted (200 or 201)
        assert response.status_code in [200, 201], f"Expected success for Meet with Google connected, got {response.status_code}: {response.text}"
        
        # Cleanup: cancel the appointment
        appointment_id = response.json().get("appointment_id")
        if appointment_id:
            requests.post(
                f"{BASE_URL}/api/appointments/{appointment_id}/cancel",
                headers=auth_headers
            )

    def test_accept_zoom_when_connected(self, auth_headers, workspace_id):
        """POST /api/appointments/ accepts meeting_provider=zoom when Zoom connected."""
        from datetime import datetime, timedelta
        
        future_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT12:00:00")
        
        payload = {
            "workspace_id": workspace_id,
            "title": "TEST_Zoom_Validation",
            "appointment_type": "video",
            "meeting_provider": "zoom",
            "start_datetime": future_date,
            "duration_minutes": 60,
            "tolerated_delay_minutes": 15,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "affected_compensation_percent": 80,
            "charity_percent": 0,
            "participants": [
                {"first_name": "Test", "last_name": "User", "email": "test@example.com"}
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/appointments/",
            json=payload,
            headers=auth_headers
        )
        
        # Should be accepted (200 or 201)
        assert response.status_code in [200, 201], f"Expected success for Zoom when connected, got {response.status_code}: {response.text}"
        
        # Cleanup: cancel the appointment
        appointment_id = response.json().get("appointment_id")
        if appointment_id:
            requests.post(
                f"{BASE_URL}/api/appointments/{appointment_id}/cancel",
                headers=auth_headers
            )

    def test_reject_external_without_url(self, auth_headers, workspace_id):
        """POST /api/appointments/ rejects meeting_provider=external without meeting_join_url."""
        from datetime import datetime, timedelta
        
        future_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT13:00:00")
        
        payload = {
            "workspace_id": workspace_id,
            "title": "TEST_External_No_URL",
            "appointment_type": "video",
            "meeting_provider": "external",
            "start_datetime": future_date,
            "duration_minutes": 60,
            "tolerated_delay_minutes": 15,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "affected_compensation_percent": 80,
            "charity_percent": 0,
            "participants": [
                {"first_name": "Test", "last_name": "User", "email": "test@example.com"}
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/appointments/",
            json=payload,
            headers=auth_headers
        )
        
        # Should be rejected with 400
        assert response.status_code == 400, f"Expected 400 for external without URL, got {response.status_code}: {response.text}"
        error_detail = response.json().get("detail", "")
        assert "URL" in error_detail or "url" in error_detail.lower(), \
            f"Error should mention URL: {error_detail}"

    def test_accept_external_with_url(self, auth_headers, workspace_id):
        """POST /api/appointments/ accepts meeting_provider=external with meeting_join_url."""
        from datetime import datetime, timedelta
        
        future_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT14:00:00")
        
        payload = {
            "workspace_id": workspace_id,
            "title": "TEST_External_With_URL",
            "appointment_type": "video",
            "meeting_provider": "external",
            "meeting_join_url": "https://zoom.us/j/123456789",
            "start_datetime": future_date,
            "duration_minutes": 60,
            "tolerated_delay_minutes": 15,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "affected_compensation_percent": 80,
            "charity_percent": 0,
            "participants": [
                {"first_name": "Test", "last_name": "User", "email": "test@example.com"}
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/appointments/",
            json=payload,
            headers=auth_headers
        )
        
        # Should be accepted (200 or 201)
        assert response.status_code in [200, 201], f"Expected success for external with URL, got {response.status_code}: {response.text}"
        
        # Cleanup: cancel the appointment
        appointment_id = response.json().get("appointment_id")
        if appointment_id:
            requests.post(
                f"{BASE_URL}/api/appointments/{appointment_id}/cancel",
                headers=auth_headers
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
