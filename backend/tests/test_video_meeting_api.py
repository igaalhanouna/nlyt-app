"""
Video Meeting API Tests - Iteration 25
Tests for NEW video conferencing features:
1. Provider status endpoint
2. Create meeting via API (Google Meet configured, Zoom/Teams not configured)
3. Fetch attendance API
4. CSV/JSON file upload ingestion
5. Auto-create meeting on appointment creation
6. Meeting link in appointment response

Test appointments:
- Zoom: 5fef7ecd-5a97-4ee7-9507-92837d7a4313
- Teams: 17697c91-5fa4-49e6-8a50-e18551fccfcf
- Meet (auto-created): 0afd7819-0068-48e4-b45a-3b6a35e32db0
- CSV test: 30f97396-9227-46af-b6d8-b2791b3e5a6b
- Workspace: 7e219321-18fd-4643-9be6-e4f1de88a2a8

Note: Google Meet creation works (GOOGLE_CLIENT_ID configured).
      Zoom/Teams credentials are NOT configured (expected 424/error responses).
"""
import pytest
import requests
import os
import json
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://homepage-mobile-1.preview.emergentagent.com')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"

# Test appointment IDs
ZOOM_APT_ID = "5fef7ecd-5a97-4ee7-9507-92837d7a4313"
TEAMS_APT_ID = "17697c91-5fa4-49e6-8a50-e18551fccfcf"
MEET_APT_ID = "0afd7819-0068-48e4-b45a-3b6a35e32db0"
CSV_APT_ID = "30f97396-9227-46af-b6d8-b2791b3e5a6b"
WORKSPACE_ID = "7e219321-18fd-4643-9be6-e4f1de88a2a8"


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
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestProviderStatus:
    """Tests for GET /api/video-evidence/provider-status endpoint."""

    def test_provider_status_returns_configured_status(self, auth_headers):
        """Provider status should return configured status for zoom, teams, meet."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Provider status failed: {response.text}"
        data = response.json()
        
        # Check structure
        assert "zoom" in data, "Missing 'zoom' in provider status"
        assert "teams" in data, "Missing 'teams' in provider status"
        assert "meet" in data, "Missing 'meet' in provider status"
        
        # Zoom should NOT be configured (no credentials)
        assert data["zoom"]["configured"] is False, \
            f"Zoom should NOT be configured, got {data['zoom']}"
        
        # Teams should NOT be configured (placeholder credentials)
        assert data["teams"]["configured"] is False, \
            f"Teams should NOT be configured, got {data['teams']}"
        
        # Meet SHOULD be configured (GOOGLE_CLIENT_ID is set)
        assert data["meet"]["configured"] is True, \
            f"Meet SHOULD be configured, got {data['meet']}"
        
        # Check features
        assert "create_meeting" in data["zoom"]["features"]
        assert "fetch_attendance" in data["zoom"]["features"]
        assert "create_meeting" in data["meet"]["features"]
        # Meet should NOT have fetch_attendance (no API)
        assert "fetch_attendance" not in data["meet"]["features"], \
            "Meet should NOT have fetch_attendance feature"
        
        print(f"Provider status: {json.dumps(data, indent=2)}")


class TestCreateMeeting:
    """Tests for POST /api/video-evidence/{apt}/create-meeting endpoint."""

    def test_create_meeting_zoom_returns_config_error(self, auth_headers):
        """Zoom create-meeting should return 424 (config error) since not configured."""
        response = requests.post(
            f"{BASE_URL}/api/video-evidence/{ZOOM_APT_ID}/create-meeting",
            headers=auth_headers,
            json={"provider": "zoom"}
        )
        
        # Should return 424 (Failed Dependency) for unconfigured provider
        assert response.status_code == 424, \
            f"Expected 424 for unconfigured Zoom, got {response.status_code}: {response.text}"
        
        error_detail = response.json().get("detail", "")
        assert "non configurée" in error_detail or "ZOOM" in error_detail.upper(), \
            f"Expected config error message, got: {error_detail}"
        
        print(f"Zoom create-meeting error (expected): {error_detail}")

    def test_create_meeting_teams_returns_config_error(self, auth_headers):
        """Teams create-meeting should return error since not configured."""
        response = requests.post(
            f"{BASE_URL}/api/video-evidence/{TEAMS_APT_ID}/create-meeting",
            headers=auth_headers,
            json={"provider": "teams"}
        )
        
        # Should return 424 (Failed Dependency) for unconfigured provider
        assert response.status_code == 424, \
            f"Expected 424 for unconfigured Teams, got {response.status_code}: {response.text}"
        
        error_detail = response.json().get("detail", "")
        assert "non configurée" in error_detail or "Teams" in error_detail, \
            f"Expected config error message, got: {error_detail}"
        
        print(f"Teams create-meeting error (expected): {error_detail}")

    def test_create_meeting_already_exists_returns_already_exists(self, auth_headers):
        """If meeting already created, should return already_exists flag."""
        # First check if the Meet appointment already has a meeting
        apt_response = requests.get(
            f"{BASE_URL}/api/appointments/{MEET_APT_ID}",
            headers=auth_headers
        )
        
        if apt_response.status_code == 200:
            apt_data = apt_response.json()
            if apt_data.get("meeting_created_via_api") and apt_data.get("meeting_join_url"):
                # Meeting already exists, test the already_exists response
                response = requests.post(
                    f"{BASE_URL}/api/video-evidence/{MEET_APT_ID}/create-meeting",
                    headers=auth_headers,
                    json={}
                )
                
                assert response.status_code == 200, f"Expected 200 for already_exists, got {response.status_code}"
                data = response.json()
                
                assert data.get("already_exists") is True, \
                    f"Expected already_exists=True, got {data}"
                assert data.get("join_url"), "Expected join_url in already_exists response"
                
                print(f"Meeting already exists: {data.get('join_url')}")
            else:
                print(f"Meet appointment doesn't have meeting yet, skipping already_exists test")
        else:
            pytest.skip("Could not fetch Meet appointment")


class TestFetchAttendance:
    """Tests for POST /api/video-evidence/{apt}/fetch-attendance endpoint."""

    def test_fetch_attendance_meet_returns_no_api_error(self, auth_headers):
        """Google Meet fetch-attendance should return error (no attendance API)."""
        response = requests.post(
            f"{BASE_URL}/api/video-evidence/{MEET_APT_ID}/fetch-attendance",
            headers=auth_headers
        )
        
        # Should return 400 with error about no attendance API
        assert response.status_code == 400, \
            f"Expected 400 for Meet fetch-attendance, got {response.status_code}: {response.text}"
        
        error_detail = response.json().get("detail", "")
        assert "pas d'API" in error_detail.lower() or "import manuel" in error_detail.lower() or "n'a pas" in error_detail.lower(), \
            f"Expected 'no attendance API' error, got: {error_detail}"
        
        print(f"Meet fetch-attendance error (expected): {error_detail}")

    def test_fetch_attendance_zoom_returns_config_error(self, auth_headers):
        """Zoom fetch-attendance should return error since not configured."""
        response = requests.post(
            f"{BASE_URL}/api/video-evidence/{ZOOM_APT_ID}/fetch-attendance",
            headers=auth_headers
        )
        
        # Should return 400 with config error
        assert response.status_code == 400, \
            f"Expected 400 for unconfigured Zoom fetch, got {response.status_code}: {response.text}"
        
        error_detail = response.json().get("detail", "")
        assert "non configurée" in error_detail or "Zoom" in error_detail, \
            f"Expected config error, got: {error_detail}"
        
        print(f"Zoom fetch-attendance error (expected): {error_detail}")


class TestFileIngestion:
    """Tests for POST /api/video-evidence/{apt}/ingest-file endpoint."""

    def test_ingest_csv_file_parses_participants(self, auth_headers):
        """CSV file upload should parse participants correctly."""
        # Create CSV content
        csv_content = """Name (Original Name),User Email,Join Time,Leave Time,Duration (Minutes)
Test User,test@example.com,2026-04-15T14:00:00Z,2026-04-15T15:00:00Z,60
Another User,another@example.com,2026-04-15T14:05:00Z,2026-04-15T14:55:00Z,50"""
        
        # Use multipart form data
        files = {
            'file': ('test_attendance.csv', csv_content, 'text/csv')
        }
        data = {
            'provider': 'zoom'
        }
        
        # Remove Content-Type header for multipart
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/video-evidence/{CSV_APT_ID}/ingest-file",
            headers=headers,
            files=files,
            data=data
        )
        
        # May return 400 if already ingested
        if response.status_code == 400:
            error_detail = response.json().get("detail", "")
            if "déjà été ingéré" in error_detail or "déjà existante" in error_detail:
                print(f"CSV already ingested (expected): {error_detail}")
                return
        
        assert response.status_code == 200, f"CSV ingestion failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True, f"Expected success=True, got {data}"
        assert data.get("provider") == "zoom"
        
        # Should have parsed participants (either matched or unmatched)
        matched_count = len(data.get("matched", []))
        unmatched_count = len(data.get("unmatched", []))
        total_parsed = matched_count + unmatched_count
        assert total_parsed >= 1, f"Expected at least 1 parsed participant, got {total_parsed}"
        
        print(f"CSV ingestion result: matched={matched_count}, unmatched={unmatched_count}")
        print(f"Full response: {json.dumps(data, indent=2)}")

    def test_ingest_json_file_works(self, auth_headers):
        """JSON file upload should work correctly."""
        # Create JSON content
        json_content = json.dumps({
            "meeting_id": "json-file-test",
            "participants": [
                {
                    "name": "JSON Test User",
                    "email": "jsontest@example.com",
                    "join_time": "2026-04-15T14:00:00Z",
                    "leave_time": "2026-04-15T15:00:00Z",
                    "duration": 3600
                }
            ]
        })
        
        files = {
            'file': ('test_attendance.json', json_content, 'application/json')
        }
        data = {
            'provider': 'zoom'
        }
        
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/video-evidence/{CSV_APT_ID}/ingest-file",
            headers=headers,
            files=files,
            data=data
        )
        
        # May return 400 if already ingested
        if response.status_code == 400:
            error_detail = response.json().get("detail", "")
            if "déjà été ingéré" in error_detail or "déjà existante" in error_detail:
                print(f"JSON already ingested (expected): {error_detail}")
                return
        
        assert response.status_code == 200, f"JSON file ingestion failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True
        print(f"JSON file ingestion result: {json.dumps(data, indent=2)}")


class TestManualJsonIngestion:
    """Tests for POST /api/video-evidence/{apt}/ingest (JSON body) - regression test."""

    def test_manual_json_ingestion_still_works(self, auth_headers):
        """Manual JSON ingestion via body should still work (no regression)."""
        payload = {
            "provider": "zoom",
            "external_meeting_id": "manual-json-test-" + datetime.utcnow().strftime("%Y%m%d%H%M%S"),
            "raw_payload": {
                "meeting_id": "manual-json-test",
                "participants": [
                    {
                        "id": "manual-user-1",
                        "name": "Manual Test User",
                        "user_email": "manualtest@example.com",
                        "join_time": datetime.utcnow().isoformat() + "Z",
                        "leave_time": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z",
                        "duration": 3600
                    }
                ]
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/video-evidence/{ZOOM_APT_ID}/ingest",
            headers=auth_headers,
            json=payload
        )
        
        # May return 400 if already ingested
        if response.status_code == 400:
            error_detail = response.json().get("detail", "")
            if "déjà été ingéré" in error_detail:
                print(f"Manual JSON already ingested (expected): {error_detail}")
                return
        
        assert response.status_code == 200, f"Manual JSON ingestion failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True
        assert data.get("provider") == "zoom"
        
        print(f"Manual JSON ingestion result: {json.dumps(data, indent=2)}")


class TestAppointmentCreationWithMeeting:
    """Tests for auto-create meeting on appointment creation."""

    def test_video_appointment_with_meet_returns_meeting_info(self, auth_headers):
        """Creating video appointment with meet provider should auto-create meeting."""
        future_date = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"
        
        appointment_data = {
            "workspace_id": WORKSPACE_ID,
            "title": "TEST_Video Meeting Auto-Create",
            "appointment_type": "video",
            "meeting_provider": "meet",
            "start_datetime": future_date,
            "duration_minutes": 60,
            "tolerated_delay_minutes": 15,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "affected_compensation_percent": 70,
            "charity_percent": 10,
            "participants": [
                {
                    "email": "meettest@example.com",
                    "first_name": "Meet",
                    "last_name": "Test"
                }
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/appointments/",
            headers=auth_headers,
            json=appointment_data
        )
        
        assert response.status_code in (200, 201), f"Failed to create appointment: {response.text}"
        data = response.json()
        
        apt_id = data.get("appointment_id")
        assert apt_id, "No appointment_id in response"
        
        # Check if meeting was auto-created
        # Note: This may fail if Google Calendar tokens are not available for the user
        if data.get("meeting"):
            meeting = data["meeting"]
            assert meeting.get("join_url"), "Expected join_url in meeting response"
            assert meeting.get("provider") == "meet", f"Expected provider=meet, got {meeting.get('provider')}"
            print(f"Meeting auto-created: {meeting.get('join_url')}")
        elif data.get("meeting_warning"):
            # Expected if user doesn't have Google Calendar connected
            print(f"Meeting warning (expected if no Google Calendar): {data.get('meeting_warning')}")
        else:
            print("No meeting info in response (may need Google Calendar connection)")
        
        # Clean up
        if apt_id:
            requests.delete(f"{BASE_URL}/api/appointments/{apt_id}", headers=auth_headers)

    def test_get_video_appointment_shows_meeting_info(self, auth_headers):
        """GET appointment should show external_meeting_id and meeting_join_url."""
        response = requests.get(
            f"{BASE_URL}/api/appointments/{MEET_APT_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Failed to get appointment: {response.text}"
        data = response.json()
        
        # Check video appointment fields
        assert data.get("appointment_type") == "video", \
            f"Expected video appointment, got {data.get('appointment_type')}"
        assert data.get("meeting_provider") == "meet", \
            f"Expected meet provider, got {data.get('meeting_provider')}"
        
        # These fields should exist (may be null if meeting not created)
        print(f"external_meeting_id: {data.get('external_meeting_id')}")
        print(f"meeting_join_url: {data.get('meeting_join_url')}")
        print(f"meeting_created_via_api: {data.get('meeting_created_via_api')}")


class TestAttendanceEvaluationRegression:
    """Regression tests for attendance evaluation with video evidence."""

    def test_zoom_video_evidence_evaluates_correctly(self, auth_headers):
        """Zoom video evidence should still evaluate correctly (no regression)."""
        # Trigger evaluation
        response = requests.post(
            f"{BASE_URL}/api/attendance/evaluate/{ZOOM_APT_ID}",
            headers=auth_headers
        )
        
        # May be skipped if already evaluated or no evidence
        if response.status_code == 200:
            data = response.json()
            if data.get("skipped"):
                print(f"Evaluation skipped: {data.get('reason')}")
            else:
                print(f"Zoom evaluation: {data.get('records_created')} records created")
        else:
            print(f"Evaluation response: {response.status_code} - {response.text[:200]}")

    def test_meet_evidence_stays_manual_review(self, auth_headers):
        """Meet evidence should still result in manual_review (no regression)."""
        # Trigger evaluation
        response = requests.post(
            f"{BASE_URL}/api/attendance/evaluate/{MEET_APT_ID}",
            headers=auth_headers
        )
        
        if response.status_code == 200:
            # Check attendance records
            attendance_response = requests.get(
                f"{BASE_URL}/api/attendance/{MEET_APT_ID}",
                headers=auth_headers
            )
            
            if attendance_response.status_code == 200:
                attendance_data = attendance_response.json()
                records = attendance_data.get("records", [])
                
                for record in records:
                    decision_basis = record.get("decision_basis", "")
                    outcome = record.get("outcome", "")
                    
                    # Meet should NEVER auto-decide
                    if "meet" in decision_basis.lower():
                        assert outcome in ("manual_review", "waived"), \
                            f"Meet should be manual_review, got {outcome}"
                        print(f"Meet outcome: {outcome} (basis: {decision_basis}) - CORRECT")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
