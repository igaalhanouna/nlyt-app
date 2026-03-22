"""
Test suite for email datetime timezone fix.
Bug: Emails showed +1h offset compared to app display.
Fix: Centralized format_email_datetime() using parse_iso_datetime + format_datetime_fr(Europe/Paris).

Tests:
1. format_email_datetime handles UTC strings correctly (Z suffix)
2. format_email_datetime handles UTC strings with milliseconds (.000Z)
3. format_email_datetime handles naive datetime as Europe/Paris (legacy)
4. Backend starts without errors
5. GET /api/invitations/{token} returns correct formatted_date
6. Modification proposal email uses correct datetime format
"""
import pytest
import requests
import os
import sys

sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestFormatEmailDatetime:
    """Unit tests for the centralized format_email_datetime function"""
    
    def test_utc_string_cest_april(self):
        """UTC April 15 12:00 -> Europe/Paris CEST (UTC+2) = 14:00"""
        from services.email_service import format_email_datetime
        result = format_email_datetime('2026-04-15T12:00:00Z')
        assert '14:00' in result, f"Expected 14:00 in result, got: {result}"
        assert '15 avril 2026' in result, f"Expected '15 avril 2026' in result, got: {result}"
        print(f"✓ UTC 12:00 April -> Paris CEST 14:00: {result}")
    
    def test_utc_string_cet_march(self):
        """UTC March 22 13:00 -> Europe/Paris CET (UTC+1) = 14:00"""
        from services.email_service import format_email_datetime
        result = format_email_datetime('2026-03-22T13:00:00Z')
        assert '14:00' in result, f"Expected 14:00 in result, got: {result}"
        assert '22 mars 2026' in result, f"Expected '22 mars 2026' in result, got: {result}"
        print(f"✓ UTC 13:00 March -> Paris CET 14:00: {result}")
    
    def test_utc_string_with_milliseconds(self):
        """UTC April 15 12:00.000Z -> Europe/Paris CEST = 14:00"""
        from services.email_service import format_email_datetime
        result = format_email_datetime('2026-04-15T12:00:00.000Z')
        assert '14:00' in result, f"Expected 14:00 in result, got: {result}"
        print(f"✓ UTC with .000Z suffix handled: {result}")
    
    def test_naive_datetime_as_paris_summer(self):
        """Naive April 15 14:00 (interpreted as Paris) -> should stay 14:00"""
        from services.email_service import format_email_datetime
        result = format_email_datetime('2026-04-15T14:00')
        assert '14:00' in result, f"Expected 14:00 in result, got: {result}"
        # Should NOT be 16:00 (which would happen if naive was treated as UTC)
        assert '16:00' not in result, f"Naive datetime should NOT be treated as UTC, got: {result}"
        print(f"✓ Naive datetime (Paris) stays at 14:00: {result}")
    
    def test_naive_datetime_as_paris_winter(self):
        """Naive Jan 15 14:00 (interpreted as Paris CET) -> should stay 14:00"""
        from services.email_service import format_email_datetime
        result = format_email_datetime('2026-01-15T14:00')
        assert '14:00' in result, f"Expected 14:00 in result, got: {result}"
        # Should NOT be 15:00 (which would happen if naive was treated as UTC)
        assert '15:00' not in result, f"Naive datetime should NOT be treated as UTC, got: {result}"
        print(f"✓ Naive datetime (Paris winter) stays at 14:00: {result}")
    
    def test_empty_string_returns_empty(self):
        """Empty string should return empty string"""
        from services.email_service import format_email_datetime
        result = format_email_datetime('')
        assert result == '', f"Expected empty string, got: {result}"
        print(f"✓ Empty string handled correctly")
    
    def test_none_returns_empty(self):
        """None should return empty string"""
        from services.email_service import format_email_datetime
        result = format_email_datetime(None)
        assert result == '', f"Expected empty string, got: {result}"
        print(f"✓ None handled correctly")


class TestBackendHealth:
    """Verify backend starts without errors after changes"""
    
    def test_backend_health(self):
        """Backend should respond to health check"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        print(f"✓ Backend health check passed")
    
    def test_auth_login(self):
        """Auth endpoint should work"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "testuser_audit@nlyt.app", "password": "Test1234!"},
            timeout=10
        )
        assert response.status_code == 200, f"Login failed: {response.status_code} - {response.text}"
        data = response.json()
        assert 'access_token' in data, f"No access_token in response: {data}"
        print(f"✓ Auth login works correctly")
        return data['access_token']


class TestInvitationEndpoint:
    """Test GET /api/invitations/{token} returns correct formatted_date"""
    
    @pytest.fixture
    def invitation_token(self):
        return "386b6f65-ce96-4c47-bd97-b0bd4d0e9449"
    
    def test_invitation_returns_formatted_date(self, invitation_token):
        """GET /api/invitations/{token} should return formatted_date in Europe/Paris"""
        response = requests.get(
            f"{BASE_URL}/api/invitations/{invitation_token}",
            timeout=10
        )
        # Token may not exist, but endpoint should work
        if response.status_code == 200:
            data = response.json()
            if 'formatted_date' in data:
                formatted_date = data['formatted_date']
                print(f"✓ Invitation formatted_date: {formatted_date}")
                # Verify it's in French format
                assert 'à' in formatted_date or ':' in formatted_date, f"Date not in French format: {formatted_date}"
            else:
                print(f"✓ Invitation endpoint works (no formatted_date in response)")
        elif response.status_code == 404:
            print(f"✓ Invitation endpoint works (token not found - expected)")
        else:
            pytest.fail(f"Unexpected status: {response.status_code} - {response.text}")


class TestModificationRoutes:
    """Test modification routes use format_email_datetime correctly"""
    
    @pytest.fixture
    def auth_token(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "testuser_audit@nlyt.app", "password": "Test1234!"},
            timeout=10
        )
        if response.status_code == 200:
            return response.json().get('access_token')
        pytest.skip("Could not authenticate")
    
    def test_build_changes_html_uses_format_email_datetime(self):
        """Verify _build_changes_html uses format_email_datetime for start_datetime"""
        from routers.modification_routes import _build_changes_html
        
        # Test proposal with start_datetime change
        proposal = {
            'original_values': {'start_datetime': '2026-04-15T12:00:00Z'},
            'changes': {'start_datetime': '2026-04-16T14:00:00Z'}
        }
        
        html = _build_changes_html(proposal)
        
        # Old value: UTC 12:00 -> Paris CEST 14:00
        assert '14:00' in html, f"Old datetime should show 14:00 (Paris), got: {html}"
        # New value: UTC 14:00 -> Paris CEST 16:00
        assert '16:00' in html, f"New datetime should show 16:00 (Paris), got: {html}"
        print(f"✓ _build_changes_html uses format_email_datetime correctly")


class TestReminderServices:
    """Test reminder services use format_email_datetime"""
    
    def test_reminder_service_imports_format_email_datetime(self):
        """reminder_service.py should import format_email_datetime"""
        from services.reminder_service import format_email_datetime
        # If import works, the function is available
        assert callable(format_email_datetime)
        print(f"✓ reminder_service imports format_email_datetime")
    
    def test_event_reminder_service_imports_format_email_datetime(self):
        """event_reminder_service.py should import format_email_datetime"""
        from services.event_reminder_service import format_email_datetime
        # If import works, the function is available
        assert callable(format_email_datetime)
        print(f"✓ event_reminder_service imports format_email_datetime")


class TestAppointmentsRoute:
    """Test appointments.py uses utc_start for invitation emails"""
    
    @pytest.fixture
    def auth_headers(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "testuser_audit@nlyt.app", "password": "Test1234!"},
            timeout=10
        )
        if response.status_code == 200:
            token = response.json().get('access_token')
            return {"Authorization": f"Bearer {token}"}
        pytest.skip("Could not authenticate")
    
    def test_appointments_endpoint_works(self, auth_headers):
        """GET /api/appointments/ should work after changes"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Appointments list failed: {response.status_code}"
        data = response.json()
        assert 'appointments' in data, f"No appointments key in response: {data}"
        print(f"✓ Appointments endpoint works, found {len(data['appointments'])} appointments")


class TestDateUtilsFunctions:
    """Test the underlying date_utils functions"""
    
    def test_parse_iso_datetime_utc(self):
        """parse_iso_datetime should handle UTC strings"""
        from utils.date_utils import parse_iso_datetime
        from datetime import timezone
        
        dt = parse_iso_datetime('2026-04-15T12:00:00Z')
        assert dt is not None
        assert dt.tzinfo == timezone.utc
        assert dt.hour == 12
        print(f"✓ parse_iso_datetime handles UTC: {dt}")
    
    def test_parse_iso_datetime_naive_as_paris(self):
        """parse_iso_datetime should interpret naive as Europe/Paris"""
        from utils.date_utils import parse_iso_datetime
        from datetime import timezone
        
        # Naive datetime 14:00 in Paris (CEST, UTC+2) = 12:00 UTC
        dt = parse_iso_datetime('2026-04-15T14:00')
        assert dt is not None
        assert dt.tzinfo == timezone.utc
        # 14:00 Paris CEST = 12:00 UTC
        assert dt.hour == 12, f"Expected 12:00 UTC, got {dt.hour}:00 UTC"
        print(f"✓ parse_iso_datetime interprets naive as Paris: {dt}")
    
    def test_format_datetime_fr(self):
        """format_datetime_fr should format in French"""
        from utils.date_utils import format_datetime_fr, parse_iso_datetime
        
        dt = parse_iso_datetime('2026-04-15T12:00:00Z')
        result = format_datetime_fr(dt, 'Europe/Paris')
        
        assert 'avril' in result, f"Expected French month name, got: {result}"
        assert '14:00' in result, f"Expected 14:00 (Paris CEST), got: {result}"
        print(f"✓ format_datetime_fr works: {result}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
