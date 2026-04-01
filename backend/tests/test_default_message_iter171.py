"""
Test: Default Message for Participants Feature (Iteration 171)
Tests the new default_message field in appointment_defaults:
- GET /api/user-settings/me/appointment-defaults returns default_message (null by default)
- PUT /api/user-settings/me with appointment_defaults.default_message saves correctly
- GET /api/user-settings/me returns default_message in appointment_defaults
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "TestAudit123!"


class TestDefaultMessageFeature:
    """Tests for default_message field in appointment_defaults"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: authenticate and get token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code != 200:
            pytest.skip(f"Authentication failed: {login_response.status_code} - {login_response.text}")
        
        # API returns access_token, not token
        token = login_response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get current defaults to use correct percentages
        defaults_response = self.session.get(f"{BASE_URL}/api/user-settings/me/appointment-defaults")
        if defaults_response.status_code == 200:
            self.current_defaults = defaults_response.json()
        else:
            self.current_defaults = {
                "default_participant_percent": 80.0,
                "default_charity_percent": 0.0
            }
        
        # Store original default_message to restore after tests
        settings_response = self.session.get(f"{BASE_URL}/api/user-settings/me")
        if settings_response.status_code == 200:
            self.original_defaults = settings_response.json().get("appointment_defaults", {})
        else:
            self.original_defaults = {}
        
        yield
        
        # Teardown: restore original default_message
        self._restore_original_message()
    
    def _restore_original_message(self):
        """Restore original default_message after test"""
        try:
            original_message = self.original_defaults.get("default_message")
            self.session.put(f"{BASE_URL}/api/user-settings/me", json={
                "appointment_defaults": {
                    "default_message": original_message,
                    "default_participant_percent": self.current_defaults.get("default_participant_percent", 80.0),
                    "default_charity_percent": self.current_defaults.get("default_charity_percent", 0.0)
                }
            })
        except Exception:
            pass
    
    def test_get_appointment_defaults_returns_default_message_field(self):
        """GET /api/user-settings/me/appointment-defaults should return default_message field"""
        response = self.session.get(f"{BASE_URL}/api/user-settings/me/appointment-defaults")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # default_message should be present in response (can be null)
        assert "default_message" in data, f"default_message field missing from response: {data}"
        print(f"PASS - default_message field present in appointment-defaults: {data.get('default_message')}")
    
    def test_save_default_message_via_put(self):
        """PUT /api/user-settings/me with default_message should save correctly"""
        test_message = "TEST_ITER171_Ceci est un message par défaut pour les participants."
        
        # Use current percentages to avoid validation error
        participant_pct = self.current_defaults.get("default_participant_percent", 80.0)
        charity_pct = self.current_defaults.get("default_charity_percent", 0.0)
        
        # Save the message
        response = self.session.put(f"{BASE_URL}/api/user-settings/me", json={
            "appointment_defaults": {
                "default_message": test_message,
                "default_participant_percent": participant_pct,
                "default_charity_percent": charity_pct
            }
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True: {data}"
        print(f"PASS - default_message saved successfully")
        
        # Verify persistence via GET
        get_response = self.session.get(f"{BASE_URL}/api/user-settings/me")
        assert get_response.status_code == 200
        
        get_data = get_response.json()
        saved_message = get_data.get("appointment_defaults", {}).get("default_message")
        assert saved_message == test_message, f"Expected '{test_message}', got '{saved_message}'"
        print(f"PASS - default_message persisted correctly: {saved_message}")
    
    def test_default_message_returned_in_appointment_defaults_endpoint(self):
        """After saving, GET /api/user-settings/me/appointment-defaults should return the saved message"""
        test_message = "TEST_ITER171_Message pour vérification endpoint appointment-defaults"
        
        # Use current percentages
        participant_pct = self.current_defaults.get("default_participant_percent", 80.0)
        charity_pct = self.current_defaults.get("default_charity_percent", 0.0)
        
        # Save the message
        save_response = self.session.put(f"{BASE_URL}/api/user-settings/me", json={
            "appointment_defaults": {
                "default_message": test_message,
                "default_participant_percent": participant_pct,
                "default_charity_percent": charity_pct
            }
        })
        assert save_response.status_code == 200, f"Save failed: {save_response.text}"
        
        # Verify via appointment-defaults endpoint
        response = self.session.get(f"{BASE_URL}/api/user-settings/me/appointment-defaults")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("default_message") == test_message, f"Expected '{test_message}', got '{data.get('default_message')}'"
        print(f"PASS - default_message returned correctly from appointment-defaults endpoint")
    
    def test_default_message_can_be_cleared(self):
        """default_message can be cleared by setting to empty string"""
        # Use current percentages
        participant_pct = self.current_defaults.get("default_participant_percent", 80.0)
        charity_pct = self.current_defaults.get("default_charity_percent", 0.0)
        
        # First set a message
        set_response = self.session.put(f"{BASE_URL}/api/user-settings/me", json={
            "appointment_defaults": {
                "default_message": "TEST_ITER171_Temporary message",
                "default_participant_percent": participant_pct,
                "default_charity_percent": charity_pct
            }
        })
        assert set_response.status_code == 200
        
        # Clear the message using empty string (since exclude_none=True in backend)
        clear_response = self.session.put(f"{BASE_URL}/api/user-settings/me", json={
            "appointment_defaults": {
                "default_message": "",
                "default_participant_percent": participant_pct,
                "default_charity_percent": charity_pct
            }
        })
        assert clear_response.status_code == 200, f"Clear failed: {clear_response.text}"
        
        # Verify it's empty or null
        response = self.session.get(f"{BASE_URL}/api/user-settings/me/appointment-defaults")
        assert response.status_code == 200
        
        data = response.json()
        # Accept either None or empty string as "cleared"
        cleared_value = data.get("default_message")
        assert cleared_value is None or cleared_value == "", f"Expected None or '', got '{cleared_value}'"
        print(f"PASS - default_message is cleared: '{cleared_value}'")
    
    def test_default_message_max_length_2000(self):
        """default_message should accept up to 2000 characters"""
        # Create a message with exactly 2000 characters
        test_message = "A" * 2000
        
        # Use current percentages
        participant_pct = self.current_defaults.get("default_participant_percent", 80.0)
        charity_pct = self.current_defaults.get("default_charity_percent", 0.0)
        
        response = self.session.put(f"{BASE_URL}/api/user-settings/me", json={
            "appointment_defaults": {
                "default_message": test_message,
                "default_participant_percent": participant_pct,
                "default_charity_percent": charity_pct
            }
        })
        
        assert response.status_code == 200, f"Expected 200 for 2000 char message, got {response.status_code}: {response.text}"
        print(f"PASS - default_message accepts 2000 characters")
        
        # Verify persistence
        get_response = self.session.get(f"{BASE_URL}/api/user-settings/me/appointment-defaults")
        assert get_response.status_code == 200
        saved_message = get_response.json().get("default_message")
        assert len(saved_message) == 2000, f"Expected 2000 chars, got {len(saved_message)}"
        print(f"PASS - 2000 character message persisted correctly")
    
    def test_get_user_settings_returns_default_message_after_save(self):
        """GET /api/user-settings/me should return default_message in appointment_defaults after saving"""
        test_message = "TEST_ITER171_Message for user-settings endpoint"
        
        # Use current percentages
        participant_pct = self.current_defaults.get("default_participant_percent", 80.0)
        charity_pct = self.current_defaults.get("default_charity_percent", 0.0)
        
        # Save a message first
        save_response = self.session.put(f"{BASE_URL}/api/user-settings/me", json={
            "appointment_defaults": {
                "default_message": test_message,
                "default_participant_percent": participant_pct,
                "default_charity_percent": charity_pct
            }
        })
        assert save_response.status_code == 200
        
        # Now verify GET returns it
        response = self.session.get(f"{BASE_URL}/api/user-settings/me")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "appointment_defaults" in data, f"appointment_defaults missing from response: {data}"
        
        defaults = data["appointment_defaults"]
        assert "default_message" in defaults, f"default_message field missing from appointment_defaults: {defaults}"
        assert defaults["default_message"] == test_message, f"Expected '{test_message}', got '{defaults.get('default_message')}'"
        print(f"PASS - default_message in user-settings/me: {defaults.get('default_message')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
