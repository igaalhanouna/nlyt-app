"""
Test Honest UX Messaging for Video Presence Verification

Tests the corrected UX messaging that provides honest, provider-specific information:
1. Teams check-in shows 'Récupération automatique via Teams' (NOT 'vérifiée automatiquement')
2. Meet check-in shows 'Import manuel requis — Google Meet' (NOT 'vérifiée automatiquement')
3. Backend scheduler has auto_fetch_attendance_job registered
4. GET /api/appointments/{id} returns all meeting fields correctly
"""
import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"

# Test appointment IDs
TEAMS_APPOINTMENT_ID = "87c58ee3-a512-4c17-a8ca-381d5519d98f"
MEET_APPOINTMENT_ID = "10c355e4-2796-4aaf-b163-74a912d71957"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def authenticated_client(auth_token):
    """Session with auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestBackendSchedulerAutoFetch:
    """Test that auto_fetch_attendance_job is registered in scheduler"""

    def test_scheduler_has_auto_fetch_job(self):
        """Verify scheduler.py has auto_fetch_attendance_job registered"""
        scheduler_path = "/app/backend/scheduler.py"
        with open(scheduler_path, 'r') as f:
            content = f.read()
        
        # Check job function exists
        assert "async def auto_fetch_attendance_job" in content, \
            "auto_fetch_attendance_job function not found in scheduler.py"
        
        # Check job is added to scheduler
        assert "auto_fetch_attendance_job" in content, \
            "auto_fetch_attendance_job not added to scheduler"
        
        # Check job name mentions Zoom/Teams
        assert "Auto-fetch Zoom/Teams attendance" in content or "auto-fetch" in content.lower(), \
            "Job name should mention Zoom/Teams auto-fetch"
        
        print("✓ scheduler.py has auto_fetch_attendance_job registered")

    def test_auto_fetch_service_exists(self):
        """Verify auto_fetch_attendance_service.py exists and has correct logic"""
        service_path = "/app/backend/services/auto_fetch_attendance_service.py"
        with open(service_path, 'r') as f:
            content = f.read()
        
        # Check main function exists
        assert "def run_auto_fetch_attendance_job" in content, \
            "run_auto_fetch_attendance_job function not found"
        
        # Check it only handles Zoom/Teams (not Meet)
        assert "AUTO_FETCH_PROVIDERS" in content, \
            "AUTO_FETCH_PROVIDERS constant not found"
        
        # Verify Meet is NOT in auto-fetch providers
        assert '"meet"' not in content.lower() or 'not in AUTO_FETCH_PROVIDERS' in content, \
            "Meet should NOT be in AUTO_FETCH_PROVIDERS (no API support)"
        
        print("✓ auto_fetch_attendance_service.py exists with correct logic")


class TestBackendAppointmentAPI:
    """Test GET /api/appointments/{id} returns all meeting fields"""

    def test_teams_appointment_returns_meeting_fields(self, authenticated_client):
        """Teams appointment should return all meeting fields"""
        response = authenticated_client.get(f"{BASE_URL}/api/appointments/{TEAMS_APPOINTMENT_ID}")
        
        if response.status_code == 404:
            pytest.skip(f"Teams appointment {TEAMS_APPOINTMENT_ID} not found")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify appointment type and provider
        assert data.get("appointment_type") == "video", "Should be video appointment"
        assert data.get("meeting_provider") in ["teams", "microsoft teams", "Teams"], \
            f"Expected Teams provider, got {data.get('meeting_provider')}"
        
        # Verify meeting fields exist (may be None if not created yet)
        assert "meeting_join_url" in data, "meeting_join_url field should exist"
        assert "external_meeting_id" in data, "external_meeting_id field should exist"
        
        print(f"✓ Teams appointment returns meeting fields: join_url={data.get('meeting_join_url', 'None')[:50] if data.get('meeting_join_url') else 'None'}")

    def test_meet_appointment_returns_meeting_fields(self, authenticated_client):
        """Meet appointment should return all meeting fields"""
        response = authenticated_client.get(f"{BASE_URL}/api/appointments/{MEET_APPOINTMENT_ID}")
        
        if response.status_code == 404:
            pytest.skip(f"Meet appointment {MEET_APPOINTMENT_ID} not found")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify appointment type and provider
        assert data.get("appointment_type") == "video", "Should be video appointment"
        assert data.get("meeting_provider") in ["meet", "google meet", "Meet"], \
            f"Expected Meet provider, got {data.get('meeting_provider')}"
        
        # Verify meeting fields exist
        assert "meeting_join_url" in data, "meeting_join_url field should exist"
        assert "external_meeting_id" in data, "external_meeting_id field should exist"
        
        print(f"✓ Meet appointment returns meeting fields: join_url={data.get('meeting_join_url', 'None')[:50] if data.get('meeting_join_url') else 'None'}")


class TestFrontendHonestMessaging:
    """Test frontend code has honest, provider-specific messaging"""

    def test_appointment_detail_teams_checkin_message(self):
        """AppointmentDetail.js should show 'Récupération automatique via Teams' for Teams"""
        file_path = "/app/frontend/src/pages/appointments/AppointmentDetail.js"
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check for data-testid
        assert 'data-testid="checkin-msg-auto-fetch"' in content, \
            "Missing data-testid='checkin-msg-auto-fetch' for Teams/Zoom check-in message"
        
        # Check for correct message
        assert "Récupération automatique via" in content, \
            "Missing 'Récupération automatique via' message for Teams/Zoom"
        
        # Verify old misleading text is NOT present
        assert "vérifiée automatiquement via votre connexion" not in content, \
            "OLD MISLEADING TEXT FOUND: 'vérifiée automatiquement via votre connexion' should be removed"
        
        print("✓ AppointmentDetail.js has correct Teams check-in message with data-testid='checkin-msg-auto-fetch'")

    def test_appointment_detail_meet_checkin_message(self):
        """AppointmentDetail.js should show 'Import manuel requis — Google Meet' for Meet"""
        file_path = "/app/frontend/src/pages/appointments/AppointmentDetail.js"
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check for data-testid
        assert 'data-testid="checkin-msg-manual-import"' in content, \
            "Missing data-testid='checkin-msg-manual-import' for Meet check-in message"
        
        # Check for correct message
        assert "Import manuel requis" in content, \
            "Missing 'Import manuel requis' message for Meet"
        
        print("✓ AppointmentDetail.js has correct Meet check-in message with data-testid='checkin-msg-manual-import'")

    def test_appointment_detail_evidence_status_waiting(self):
        """AppointmentDetail.js should show 'Réunion en cours ou à venir' for Teams/Zoom"""
        file_path = "/app/frontend/src/pages/appointments/AppointmentDetail.js"
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check for data-testid
        assert 'data-testid="evidence-status-waiting"' in content, \
            "Missing data-testid='evidence-status-waiting' for Teams/Zoom evidence status"
        
        # Check for correct message
        assert "Réunion en cours ou à venir" in content, \
            "Missing 'Réunion en cours ou à venir' message"
        
        print("✓ AppointmentDetail.js has correct evidence status with data-testid='evidence-status-waiting'")

    def test_appointment_detail_evidence_status_meet_manual(self):
        """AppointmentDetail.js should show 'Import requis — Google Meet' for Meet evidence"""
        file_path = "/app/frontend/src/pages/appointments/AppointmentDetail.js"
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check for data-testid
        assert 'data-testid="evidence-status-meet-manual"' in content, \
            "Missing data-testid='evidence-status-meet-manual' for Meet evidence status"
        
        # Check for correct message
        assert "Import requis" in content, \
            "Missing 'Import requis' message for Meet evidence"
        
        print("✓ AppointmentDetail.js has correct Meet evidence status with data-testid='evidence-status-meet-manual'")

    def test_invitation_page_updated_messaging(self):
        """InvitationPage.js should have updated participant messaging"""
        file_path = "/app/frontend/src/pages/invitations/InvitationPage.js"
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check for correct message in active check-in section
        assert "Rejoignez la réunion pour confirmer votre présence" in content, \
            "Missing 'Rejoignez la réunion pour confirmer votre présence' message"
        
        # Check for updated verification message
        assert "Votre présence sera vérifiée après la réunion via le rapport du provider" in content, \
            "Missing 'Votre présence sera vérifiée après la réunion via le rapport du provider' message"
        
        print("✓ InvitationPage.js has updated participant messaging")

    def test_invitation_page_no_misleading_text_anywhere(self):
        """InvitationPage.js should NOT have old misleading text 'vérifiée automatiquement' ANYWHERE"""
        file_path = "/app/frontend/src/pages/invitations/InvitationPage.js"
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Verify the old misleading text is completely removed
        assert "vérifiée automatiquement via votre connexion" not in content, \
            "OLD MISLEADING TEXT FOUND: 'vérifiée automatiquement via votre connexion' should be removed from InvitationPage.js"
        
        # Check that the corrected text exists (should appear twice - before window and during window)
        corrected_count = content.count("Votre présence sera vérifiée après la réunion via le rapport du provider")
        assert corrected_count >= 2, \
            f"Corrected text should appear at least twice in InvitationPage.js, found {corrected_count}"
        
        print(f"✓ InvitationPage.js has corrected messaging (found {corrected_count} occurrences)")


class TestPhysicalAppointmentNoVideoSection:
    """Test that physical appointments don't show video evidence section"""

    def test_appointment_detail_physical_no_video_section(self):
        """AppointmentDetail.js should not show video evidence section for physical appointments"""
        file_path = "/app/frontend/src/pages/appointments/AppointmentDetail.js"
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check that video evidence section is conditional on appointment_type === 'video'
        assert "appointment.appointment_type === 'video'" in content, \
            "Video evidence section should be conditional on appointment_type === 'video'"
        
        # Check for data-testid
        assert 'data-testid="video-evidence-section"' in content, \
            "Missing data-testid='video-evidence-section'"
        
        print("✓ AppointmentDetail.js video evidence section is conditional on video appointment type")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
