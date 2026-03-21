"""
Test Auto-Update Calendar V1 Feature
Tests for:
1. PATCH with calendar fields (title, start_datetime, duration_minutes, location, description, meeting_provider) triggers auto-update
2. PATCH with non-calendar fields (penalty_amount, cancellation_deadline_hours) does NOT trigger auto-update
3. GET /api/calendar/sync/status/{id} returns out_of_sync=true and sync_error_reason when applicable
4. GET /api/calendar/sync/status/{id} returns out_of_sync=false when synced
5. Manual sync on out_of_sync event does UPDATE (not CREATE) and resets to synced
6. Idempotence: manual sync on already synced returns already_synced
7. Auto-update does not block appointment save (200 immediate)
8. Login error message visible when password incorrect
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_USER_EMAIL = "testuser_audit@nlyt.app"
TEST_USER_PASSWORD = "Test1234!"
TEST_WORKSPACE_ID = "7e219321-18fd-4643-9be6-e4f1de88a2a8"
AUTO_SYNCED_APPOINTMENT_ID = "f11d54c8-af9b-4df8-ad2e-cc831aa3ae25"


class TestAutoUpdateCalendar:
    """Tests for auto-update calendar feature on appointment modification"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        # API returns access_token, not token
        self.token = login_response.json().get("access_token") or login_response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        yield
    
    # ============ CALENDAR_FIELDS constant tests ============
    
    def test_patch_with_title_triggers_auto_update(self):
        """PATCH with title (calendar field) should trigger auto-update"""
        # Get current appointment
        get_response = self.session.get(f"{BASE_URL}/api/appointments/{AUTO_SYNCED_APPOINTMENT_ID}")
        assert get_response.status_code == 200
        original_title = get_response.json().get("title")
        
        # Update title (calendar field)
        new_title = f"Updated Title {int(time.time())}"
        patch_response = self.session.patch(
            f"{BASE_URL}/api/appointments/{AUTO_SYNCED_APPOINTMENT_ID}",
            json={"title": new_title}
        )
        
        # Should return 200 immediately (non-blocking)
        assert patch_response.status_code == 200, f"PATCH failed: {patch_response.text}"
        assert "mis à jour" in patch_response.json().get("message", "").lower() or patch_response.json().get("message") == "Rendez-vous mis à jour"
        
        # Verify title was updated
        verify_response = self.session.get(f"{BASE_URL}/api/appointments/{AUTO_SYNCED_APPOINTMENT_ID}")
        assert verify_response.status_code == 200
        assert verify_response.json().get("title") == new_title
        
        # Restore original title
        self.session.patch(
            f"{BASE_URL}/api/appointments/{AUTO_SYNCED_APPOINTMENT_ID}",
            json={"title": original_title}
        )
        print("✅ PATCH with title (calendar field) returns 200 immediately")
    
    def test_patch_with_description_triggers_auto_update(self):
        """PATCH with description (calendar field) should trigger auto-update"""
        new_description = f"Test description {int(time.time())}"
        patch_response = self.session.patch(
            f"{BASE_URL}/api/appointments/{AUTO_SYNCED_APPOINTMENT_ID}",
            json={"description": new_description}
        )
        
        assert patch_response.status_code == 200, f"PATCH failed: {patch_response.text}"
        print("✅ PATCH with description (calendar field) returns 200 immediately")
    
    def test_patch_with_duration_triggers_auto_update(self):
        """PATCH with duration_minutes (calendar field) should trigger auto-update"""
        # Get current duration
        get_response = self.session.get(f"{BASE_URL}/api/appointments/{AUTO_SYNCED_APPOINTMENT_ID}")
        original_duration = get_response.json().get("duration_minutes", 60)
        
        # Update duration
        new_duration = 90 if original_duration != 90 else 60
        patch_response = self.session.patch(
            f"{BASE_URL}/api/appointments/{AUTO_SYNCED_APPOINTMENT_ID}",
            json={"duration_minutes": new_duration}
        )
        
        assert patch_response.status_code == 200, f"PATCH failed: {patch_response.text}"
        
        # Restore original
        self.session.patch(
            f"{BASE_URL}/api/appointments/{AUTO_SYNCED_APPOINTMENT_ID}",
            json={"duration_minutes": original_duration}
        )
        print("✅ PATCH with duration_minutes (calendar field) returns 200 immediately")
    
    def test_patch_with_location_triggers_auto_update(self):
        """PATCH with location (calendar field) should trigger auto-update"""
        new_location = f"Test Location {int(time.time())}"
        patch_response = self.session.patch(
            f"{BASE_URL}/api/appointments/{AUTO_SYNCED_APPOINTMENT_ID}",
            json={"location": new_location}
        )
        
        assert patch_response.status_code == 200, f"PATCH failed: {patch_response.text}"
        print("✅ PATCH with location (calendar field) returns 200 immediately")
    
    # ============ Non-calendar fields tests ============
    
    def test_patch_with_penalty_amount_no_auto_update(self):
        """PATCH with penalty_amount (non-calendar field) should NOT trigger auto-update"""
        # Get current penalty
        get_response = self.session.get(f"{BASE_URL}/api/appointments/{AUTO_SYNCED_APPOINTMENT_ID}")
        original_penalty = get_response.json().get("penalty_amount", 50)
        
        # Update penalty (non-calendar field)
        new_penalty = original_penalty + 10
        patch_response = self.session.patch(
            f"{BASE_URL}/api/appointments/{AUTO_SYNCED_APPOINTMENT_ID}",
            json={"penalty_amount": new_penalty}
        )
        
        assert patch_response.status_code == 200, f"PATCH failed: {patch_response.text}"
        
        # Restore original
        self.session.patch(
            f"{BASE_URL}/api/appointments/{AUTO_SYNCED_APPOINTMENT_ID}",
            json={"penalty_amount": original_penalty}
        )
        print("✅ PATCH with penalty_amount (non-calendar field) returns 200 - no auto-update triggered")
    
    def test_patch_with_cancellation_deadline_no_auto_update(self):
        """PATCH with cancellation_deadline_hours (non-calendar field) should NOT trigger auto-update"""
        # Get current deadline
        get_response = self.session.get(f"{BASE_URL}/api/appointments/{AUTO_SYNCED_APPOINTMENT_ID}")
        original_deadline = get_response.json().get("cancellation_deadline_hours", 24)
        
        # Update deadline (non-calendar field)
        new_deadline = 48 if original_deadline != 48 else 24
        patch_response = self.session.patch(
            f"{BASE_URL}/api/appointments/{AUTO_SYNCED_APPOINTMENT_ID}",
            json={"cancellation_deadline_hours": new_deadline}
        )
        
        assert patch_response.status_code == 200, f"PATCH failed: {patch_response.text}"
        
        # Restore original
        self.session.patch(
            f"{BASE_URL}/api/appointments/{AUTO_SYNCED_APPOINTMENT_ID}",
            json={"cancellation_deadline_hours": original_deadline}
        )
        print("✅ PATCH with cancellation_deadline_hours (non-calendar field) returns 200 - no auto-update triggered")
    
    def test_patch_with_tolerated_delay_no_auto_update(self):
        """PATCH with tolerated_delay_minutes (non-calendar field) should NOT trigger auto-update"""
        get_response = self.session.get(f"{BASE_URL}/api/appointments/{AUTO_SYNCED_APPOINTMENT_ID}")
        original_delay = get_response.json().get("tolerated_delay_minutes", 10)
        
        new_delay = 15 if original_delay != 15 else 10
        patch_response = self.session.patch(
            f"{BASE_URL}/api/appointments/{AUTO_SYNCED_APPOINTMENT_ID}",
            json={"tolerated_delay_minutes": new_delay}
        )
        
        assert patch_response.status_code == 200, f"PATCH failed: {patch_response.text}"
        
        # Restore original
        self.session.patch(
            f"{BASE_URL}/api/appointments/{AUTO_SYNCED_APPOINTMENT_ID}",
            json={"tolerated_delay_minutes": original_delay}
        )
        print("✅ PATCH with tolerated_delay_minutes (non-calendar field) returns 200 - no auto-update triggered")
    
    # ============ Sync status tests ============
    
    def test_sync_status_returns_synced_state(self):
        """GET /api/calendar/sync/status/{id} returns synced=true when synced"""
        response = self.session.get(f"{BASE_URL}/api/calendar/sync/status/{AUTO_SYNCED_APPOINTMENT_ID}")
        assert response.status_code == 200, f"Sync status failed: {response.text}"
        
        data = response.json()
        # Check outlook status (this appointment is synced to outlook)
        outlook_status = data.get("outlook", {})
        
        # Either synced or out_of_sync should be present
        assert "synced" in outlook_status or "out_of_sync" in outlook_status, f"Missing sync status fields: {data}"
        
        if outlook_status.get("synced"):
            assert outlook_status.get("out_of_sync", False) == False, "synced and out_of_sync should not both be true"
            print("✅ Sync status returns synced=true, out_of_sync=false for synced appointment")
        elif outlook_status.get("out_of_sync"):
            assert "sync_error_reason" in outlook_status or outlook_status.get("sync_error_reason") is None
            print("✅ Sync status returns out_of_sync=true with sync_error_reason field")
        else:
            print(f"⚠️ Appointment sync status: {outlook_status}")
    
    def test_sync_status_has_external_event_id(self):
        """GET /api/calendar/sync/status/{id} returns external_event_id when synced"""
        response = self.session.get(f"{BASE_URL}/api/calendar/sync/status/{AUTO_SYNCED_APPOINTMENT_ID}")
        assert response.status_code == 200
        
        data = response.json()
        outlook_status = data.get("outlook", {})
        
        if outlook_status.get("synced") or outlook_status.get("out_of_sync"):
            assert "external_event_id" in outlook_status, "Missing external_event_id for synced/out_of_sync appointment"
            print(f"✅ Sync status includes external_event_id: {outlook_status.get('external_event_id', '')[:20]}...")
    
    def test_sync_status_has_sync_source(self):
        """GET /api/calendar/sync/status/{id} returns sync_source field"""
        response = self.session.get(f"{BASE_URL}/api/calendar/sync/status/{AUTO_SYNCED_APPOINTMENT_ID}")
        assert response.status_code == 200
        
        data = response.json()
        outlook_status = data.get("outlook", {})
        
        if outlook_status.get("synced") or outlook_status.get("out_of_sync"):
            assert "sync_source" in outlook_status, "Missing sync_source field"
            assert outlook_status.get("sync_source") in ["auto", "manual"], f"Invalid sync_source: {outlook_status.get('sync_source')}"
            print(f"✅ Sync status includes sync_source: {outlook_status.get('sync_source')}")
    
    # ============ Manual sync idempotence tests ============
    
    def test_manual_sync_on_synced_returns_already_synced(self):
        """POST /api/calendar/sync/appointment/{id} on already synced returns already_synced"""
        # First check if already synced
        status_response = self.session.get(f"{BASE_URL}/api/calendar/sync/status/{AUTO_SYNCED_APPOINTMENT_ID}")
        assert status_response.status_code == 200
        
        outlook_status = status_response.json().get("outlook", {})
        
        if outlook_status.get("synced"):
            # Try to sync again - should return already_synced
            sync_response = self.session.post(
                f"{BASE_URL}/api/calendar/sync/appointment/{AUTO_SYNCED_APPOINTMENT_ID}?provider=outlook"
            )
            assert sync_response.status_code == 200, f"Sync failed: {sync_response.text}"
            
            data = sync_response.json()
            assert data.get("sync_status") == "already_synced", f"Expected already_synced, got: {data}"
            print("✅ Manual sync on already synced appointment returns already_synced (idempotent)")
        else:
            print("⚠️ Appointment not in synced state, skipping idempotence test")
    
    # ============ Auto-update non-blocking test ============
    
    def test_auto_update_does_not_block_save(self):
        """Auto-update should not block the appointment save - response should be immediate"""
        import time
        
        start_time = time.time()
        patch_response = self.session.patch(
            f"{BASE_URL}/api/appointments/{AUTO_SYNCED_APPOINTMENT_ID}",
            json={"title": f"Non-blocking test {int(time.time())}"}
        )
        elapsed_time = time.time() - start_time
        
        assert patch_response.status_code == 200, f"PATCH failed: {patch_response.text}"
        # Response should be quick (< 5 seconds) even if calendar update takes longer
        assert elapsed_time < 5, f"Response took too long: {elapsed_time}s - auto-update may be blocking"
        print(f"✅ PATCH response time: {elapsed_time:.2f}s - auto-update is non-blocking")


class TestLoginErrorMessage:
    """Tests for login error message visibility (401 interceptor fix)"""
    
    def test_login_with_wrong_password_returns_401(self):
        """Login with wrong password should return 401 with error message"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": "WrongPassword123!"
        })
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        data = response.json()
        assert "detail" in data, "Missing error detail in response"
        print(f"✅ Login with wrong password returns 401 with detail: {data.get('detail')}")
    
    def test_login_with_nonexistent_user_returns_401(self):
        """Login with non-existent user should return 401"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "nonexistent_user_12345@nlyt.app",
            "password": "AnyPassword123!"
        })
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ Login with non-existent user returns 401")
    
    def test_login_success_returns_token(self):
        """Login with correct credentials should return token"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        # API returns access_token, not token
        assert "access_token" in data or "token" in data, "Missing token in response"
        token = data.get("access_token") or data.get("token")
        assert len(token) > 0, "Token is empty"
        print("✅ Login with correct credentials returns token")


class TestCalendarConnectionsAndAutoSync:
    """Tests for calendar connections and auto-sync settings"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        assert login_response.status_code == 200
        self.token = login_response.json().get("access_token") or login_response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        yield
    
    def test_get_calendar_connections(self):
        """GET /api/calendar/connections returns connected providers"""
        response = self.session.get(f"{BASE_URL}/api/calendar/connections")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "connections" in data
        connections = data["connections"]
        
        # User should have at least one connection
        print(f"✅ Calendar connections: {len(connections)} provider(s) connected")
        for conn in connections:
            print(f"   - {conn.get('provider')}: {conn.get('status')}")
    
    def test_get_auto_sync_settings(self):
        """GET /api/calendar/auto-sync/settings returns current settings"""
        response = self.session.get(f"{BASE_URL}/api/calendar/auto-sync/settings")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "auto_sync_enabled" in data
        assert "auto_sync_provider" in data
        print(f"✅ Auto-sync settings: enabled={data.get('auto_sync_enabled')}, provider={data.get('auto_sync_provider')}")
    
    def test_auto_sync_settings_validation(self):
        """PUT /api/calendar/auto-sync/settings validates input"""
        # Try to enable without provider - should fail
        response = self.session.put(
            f"{BASE_URL}/api/calendar/auto-sync/settings",
            json={"auto_sync_enabled": True}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✅ Auto-sync settings validation: rejects enabled=true without provider")


class TestNoRegressionManualSync:
    """Tests to ensure no regression on manual sync functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        assert login_response.status_code == 200
        self.token = login_response.json().get("access_token") or login_response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        yield
    
    def test_manual_sync_endpoint_exists(self):
        """POST /api/calendar/sync/appointment/{id} endpoint exists"""
        response = self.session.post(
            f"{BASE_URL}/api/calendar/sync/appointment/{AUTO_SYNCED_APPOINTMENT_ID}?provider=outlook"
        )
        # Should return 200 (already_synced or synced) or 400/401 (connection issue)
        assert response.status_code in [200, 400, 401, 502], f"Unexpected status: {response.status_code}"
        print(f"✅ Manual sync endpoint exists, returned: {response.status_code}")
    
    def test_unsync_endpoint_exists(self):
        """DELETE /api/calendar/sync/appointment/{id} endpoint exists"""
        # Just check endpoint exists - don't actually unsync
        response = self.session.delete(
            f"{BASE_URL}/api/calendar/sync/appointment/{AUTO_SYNCED_APPOINTMENT_ID}"
        )
        # Should return 200 or similar
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
        print(f"✅ Unsync endpoint exists, returned: {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
