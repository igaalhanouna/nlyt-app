"""
Test suite for timezone bug fix verification.
Tests that backend returns UTC ISO format and frontend displays consistently.

Bug context: Organizer page showed 01:04 while Invitation page showed 00:04 for same appointment.
Fix: Backend stores/returns ALL dates in UTC ISO format (with 'Z' suffix).
"""
import pytest
import requests
import os
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"

# Sample invitation tokens for testing
INVITATION_TOKEN_1 = "55cebfef-1539-4642-985f-9a9ccb1da110"  # Test chek in 3, UTC: 2026-03-22T00:04:00Z
INVITATION_TOKEN_2 = "4cf4ad07-9f38-41b1-8946-a51f2bd96430"  # Test dates en français, UTC: 2026-04-22T12:30:00Z


class TestBackendUTCFormat:
    """Test that backend APIs return UTC ISO format with Z suffix"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        return data.get("access_token")
    
    @pytest.fixture(scope="class")
    def authenticated_client(self, auth_token):
        """Session with auth header"""
        session = requests.Session()
        session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_token}"
        })
        return session
    
    def test_api_health(self):
        """Verify API is accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("✓ API health check passed")
    
    def test_invitation_api_returns_utc_with_z_suffix(self):
        """Test GET /api/invitations/{token} returns start_datetime in UTC with Z suffix"""
        response = requests.get(f"{BASE_URL}/api/invitations/{INVITATION_TOKEN_1}")
        assert response.status_code == 200, f"Failed to get invitation: {response.text}"
        
        data = response.json()
        start_datetime = data.get("appointment", {}).get("start_datetime", "")
        
        # Verify UTC format with Z suffix
        assert start_datetime.endswith("Z"), f"start_datetime should end with 'Z', got: {start_datetime}"
        assert "T" in start_datetime, f"start_datetime should be ISO format, got: {start_datetime}"
        
        # Verify it's a valid ISO datetime
        try:
            dt = datetime.fromisoformat(start_datetime.replace('Z', '+00:00'))
            assert dt.tzinfo is not None, "Datetime should be timezone-aware"
        except ValueError as e:
            pytest.fail(f"Invalid ISO datetime format: {start_datetime}, error: {e}")
        
        print(f"✓ Invitation API returns UTC format: {start_datetime}")
        return start_datetime
    
    def test_invitation_api_token_2_returns_utc(self):
        """Test second invitation token also returns UTC format"""
        response = requests.get(f"{BASE_URL}/api/invitations/{INVITATION_TOKEN_2}")
        assert response.status_code == 200, f"Failed to get invitation: {response.text}"
        
        data = response.json()
        start_datetime = data.get("appointment", {}).get("start_datetime", "")
        
        assert start_datetime.endswith("Z"), f"start_datetime should end with 'Z', got: {start_datetime}"
        print(f"✓ Invitation 2 API returns UTC format: {start_datetime}")
    
    def test_appointments_list_returns_utc(self, authenticated_client):
        """Test GET /api/appointments/ returns start_datetime in UTC with Z suffix"""
        response = authenticated_client.get(f"{BASE_URL}/api/appointments/")
        assert response.status_code == 200, f"Failed to list appointments: {response.text}"
        
        data = response.json()
        appointments = data.get("appointments", [])
        
        assert len(appointments) > 0, "No appointments found for testing"
        
        utc_count = 0
        non_utc_count = 0
        
        for apt in appointments:
            start_datetime = apt.get("start_datetime", "")
            if start_datetime:
                if start_datetime.endswith("Z"):
                    utc_count += 1
                else:
                    non_utc_count += 1
                    print(f"  WARNING: Non-UTC datetime found: {start_datetime} for appointment {apt.get('title')}")
        
        print(f"✓ Appointments list: {utc_count} UTC format, {non_utc_count} non-UTC")
        assert non_utc_count == 0, f"Found {non_utc_count} appointments with non-UTC datetime format"
    
    def test_single_appointment_returns_utc(self, authenticated_client):
        """Test GET /api/appointments/{id} returns start_datetime in UTC with Z suffix"""
        # First get an appointment ID from the invitation
        response = requests.get(f"{BASE_URL}/api/invitations/{INVITATION_TOKEN_1}")
        assert response.status_code == 200
        
        appointment_id = response.json().get("appointment", {}).get("appointment_id")
        assert appointment_id, "No appointment_id found in invitation"
        
        # Now get the appointment directly
        response = authenticated_client.get(f"{BASE_URL}/api/appointments/{appointment_id}")
        assert response.status_code == 200, f"Failed to get appointment: {response.text}"
        
        data = response.json()
        start_datetime = data.get("start_datetime", "")
        
        assert start_datetime.endswith("Z"), f"start_datetime should end with 'Z', got: {start_datetime}"
        print(f"✓ Single appointment API returns UTC format: {start_datetime}")
        
        return appointment_id, start_datetime


class TestDateConsistency:
    """Test that invitation and appointment detail show IDENTICAL dates"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json().get("access_token")
    
    @pytest.fixture(scope="class")
    def authenticated_client(self, auth_token):
        """Session with auth header"""
        session = requests.Session()
        session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_token}"
        })
        return session
    
    def test_invitation_and_appointment_have_same_datetime(self, authenticated_client):
        """
        CRITICAL TEST: Verify invitation page and appointment detail page 
        receive the SAME start_datetime value from backend.
        
        This was the root cause of the bug: inconsistent date handling.
        """
        # Get datetime from invitation API (public endpoint)
        inv_response = requests.get(f"{BASE_URL}/api/invitations/{INVITATION_TOKEN_1}")
        assert inv_response.status_code == 200
        
        inv_data = inv_response.json()
        inv_start_datetime = inv_data.get("appointment", {}).get("start_datetime", "")
        appointment_id = inv_data.get("appointment", {}).get("appointment_id")
        
        # Get datetime from appointment API (authenticated endpoint)
        apt_response = authenticated_client.get(f"{BASE_URL}/api/appointments/{appointment_id}")
        assert apt_response.status_code == 200
        
        apt_data = apt_response.json()
        apt_start_datetime = apt_data.get("start_datetime", "")
        
        # CRITICAL: Both should be IDENTICAL
        assert inv_start_datetime == apt_start_datetime, (
            f"TIMEZONE BUG DETECTED!\n"
            f"Invitation API returned: {inv_start_datetime}\n"
            f"Appointment API returned: {apt_start_datetime}\n"
            f"These should be IDENTICAL!"
        )
        
        print(f"✓ CRITICAL: Invitation and Appointment APIs return IDENTICAL datetime: {inv_start_datetime}")
    
    def test_second_invitation_consistency(self, authenticated_client):
        """Test second invitation token for consistency"""
        # Get datetime from invitation API
        inv_response = requests.get(f"{BASE_URL}/api/invitations/{INVITATION_TOKEN_2}")
        assert inv_response.status_code == 200
        
        inv_data = inv_response.json()
        inv_start_datetime = inv_data.get("appointment", {}).get("start_datetime", "")
        appointment_id = inv_data.get("appointment", {}).get("appointment_id")
        
        # Get datetime from appointment API
        apt_response = authenticated_client.get(f"{BASE_URL}/api/appointments/{appointment_id}")
        assert apt_response.status_code == 200
        
        apt_data = apt_response.json()
        apt_start_datetime = apt_data.get("start_datetime", "")
        
        assert inv_start_datetime == apt_start_datetime, (
            f"TIMEZONE BUG DETECTED for invitation 2!\n"
            f"Invitation API: {inv_start_datetime}\n"
            f"Appointment API: {apt_start_datetime}"
        )
        
        print(f"✓ Invitation 2 consistency verified: {inv_start_datetime}")


class TestLegacyDateNormalization:
    """Test that legacy naive datetime strings are normalized correctly"""
    
    def test_normalize_to_utc_function(self):
        """Test the normalize_to_utc function handles various formats"""
        import sys
        sys.path.insert(0, '/app/backend')
        from utils.date_utils import normalize_to_utc, parse_iso_datetime
        
        # Test 1: Already UTC string (should pass through)
        utc_str = "2026-03-22T00:04:00Z"
        result = normalize_to_utc(utc_str)
        assert result == utc_str, f"UTC string should pass through unchanged, got: {result}"
        print(f"✓ UTC string passes through: {utc_str}")
        
        # Test 2: Naive datetime (should be interpreted as Europe/Paris and converted to UTC)
        # Europe/Paris is UTC+1 in winter, so 01:04 Paris = 00:04 UTC
        naive_str = "2026-03-22T01:04:00"
        result = normalize_to_utc(naive_str)
        assert result.endswith("Z"), f"Result should end with Z, got: {result}"
        # In March 2026, Paris is in CET (UTC+1), so 01:04 Paris = 00:04 UTC
        # But after March 29, 2026 it's CEST (UTC+2)
        # March 22 is before DST change, so UTC+1
        expected = "2026-03-22T00:04:00Z"
        assert result == expected, f"Expected {expected}, got: {result}"
        print(f"✓ Naive datetime normalized: {naive_str} -> {result}")
        
        # Test 3: Datetime with offset (should convert to UTC)
        offset_str = "2026-04-22T14:30:00+02:00"
        result = normalize_to_utc(offset_str)
        assert result.endswith("Z"), f"Result should end with Z, got: {result}"
        expected = "2026-04-22T12:30:00Z"
        assert result == expected, f"Expected {expected}, got: {result}"
        print(f"✓ Offset datetime normalized: {offset_str} -> {result}")
    
    def test_parse_iso_datetime_function(self):
        """Test parse_iso_datetime handles various formats"""
        import sys
        sys.path.insert(0, '/app/backend')
        from utils.date_utils import parse_iso_datetime
        
        # Test UTC string
        dt = parse_iso_datetime("2026-03-22T00:04:00Z")
        assert dt is not None
        assert dt.tzinfo is not None
        assert dt.hour == 0
        assert dt.minute == 4
        print(f"✓ Parsed UTC string: {dt}")
        
        # Test naive string (interpreted as Europe/Paris)
        dt = parse_iso_datetime("2026-03-22T01:04:00")
        assert dt is not None
        assert dt.tzinfo is not None
        # After conversion to UTC, should be 00:04
        assert dt.hour == 0
        assert dt.minute == 4
        print(f"✓ Parsed naive string (as Paris): {dt}")


class TestFrontendDateFormatUtility:
    """Test that frontend dateFormat.js utility is correctly implemented"""
    
    def test_dateformat_js_exists(self):
        """Verify dateFormat.js exists and has required functions"""
        import os
        path = "/app/frontend/src/utils/dateFormat.js"
        assert os.path.exists(path), f"dateFormat.js not found at {path}"
        
        with open(path, 'r') as f:
            content = f.read()
        
        # Check for required functions
        required_functions = [
            "formatDateTimeFr",
            "formatDateTimeCompactFr",
            "formatTimeFr",
            "localInputToUTC",
            "utcToLocalInput",
            "parseUTC",
            "getUserTimezone"
        ]
        
        for func in required_functions:
            assert f"export function {func}" in content, f"Missing function: {func}"
            print(f"✓ Found function: {func}")
        
        # Check that it uses USER_TIMEZONE
        assert "USER_TIMEZONE" in content, "Should use USER_TIMEZONE constant"
        assert "Intl.DateTimeFormat" in content, "Should use Intl.DateTimeFormat for timezone"
        print("✓ dateFormat.js uses Intl.DateTimeFormat for timezone handling")
    
    def test_invitation_page_uses_formatDateTimeFr(self):
        """Verify InvitationPage.js uses formatDateTimeFr for date display"""
        path = "/app/frontend/src/pages/invitations/InvitationPage.js"
        with open(path, 'r') as f:
            content = f.read()
        
        # Check import
        assert "formatDateTimeFr" in content, "Should import formatDateTimeFr"
        
        # Check usage for appointment date display
        assert "formatDateTimeFr(appointment.start_datetime)" in content, (
            "Should use formatDateTimeFr(appointment.start_datetime) for date display"
        )
        
        # Check that old hack is removed (appending 'Z' to naive strings)
        assert "start_datetime + 'Z'" not in content, "Old 'Z' append hack should be removed"
        assert "start_datetime+'Z'" not in content, "Old 'Z' append hack should be removed"
        
        print("✓ InvitationPage.js uses formatDateTimeFr correctly")
    
    def test_appointment_detail_uses_formatDateTimeFr(self):
        """Verify AppointmentDetail.js uses formatDateTimeFr for date display"""
        path = "/app/frontend/src/pages/appointments/AppointmentDetail.js"
        with open(path, 'r') as f:
            content = f.read()
        
        # Check import
        assert "formatDateTimeFr" in content, "Should import formatDateTimeFr"
        
        # Check usage
        assert "formatDateTimeFr(appointment.start_datetime)" in content, (
            "Should use formatDateTimeFr(appointment.start_datetime) for date display"
        )
        
        print("✓ AppointmentDetail.js uses formatDateTimeFr correctly")
    
    def test_organizer_dashboard_uses_formatDateTimeCompactFr(self):
        """Verify OrganizerDashboard.js uses formatDateTimeCompactFr"""
        path = "/app/frontend/src/pages/dashboard/OrganizerDashboard.js"
        with open(path, 'r') as f:
            content = f.read()
        
        # Check import
        assert "formatDateTimeCompactFr" in content, "Should import formatDateTimeCompactFr"
        assert "parseUTC" in content, "Should import parseUTC"
        
        # Check usage
        assert "formatDateTimeCompactFr(appointment.start_datetime)" in content, (
            "Should use formatDateTimeCompactFr for appointment cards"
        )
        
        print("✓ OrganizerDashboard.js uses formatDateTimeCompactFr correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
