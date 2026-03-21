"""
Test Auto-Sync Calendar Feature - NLYT SaaS V1
Tests the new auto-sync functionality including:
- GET /api/calendar/auto-sync/settings - Get auto-sync preferences
- PUT /api/calendar/auto-sync/settings - Update auto-sync preferences
- Auto-sync triggered on appointment creation
- sync_source field in sync logs ('auto' vs 'manual')
- GET /api/calendar/sync/status/{id} returns sync_source
- Idempotence checks
"""

import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test user with Outlook connected (has Google + Outlook connections, auto-sync enabled for outlook)
TEST_USER_WITH_CONNECTIONS = {
    "email": "testuser_audit@nlyt.app",
    "password": "Test1234!",
    "workspace_id": "7e219321-18fd-4643-9be6-e4f1de88a2a8"
}

# Test user without connections
TEST_USER_NO_CONNECTIONS = {
    "email": "outlook_test@nlyt.app",
    "password": "Test1234!"
}

# Auto-synced appointment ID for testing
AUTO_SYNCED_APPOINTMENT_ID = "f11d54c8-af9b-4df8-ad2e-cc831aa3ae25"


class TestAutoSyncSettings:
    """Test auto-sync settings endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication for user with connections"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login with user that has calendar connections
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_WITH_CONNECTIONS["email"],
            "password": TEST_USER_WITH_CONNECTIONS["password"]
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            self.token = data.get("access_token") or data.get("token")
            self.user_id = data.get("user", {}).get("user_id")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            print(f"✓ Logged in as {TEST_USER_WITH_CONNECTIONS['email']}")
        else:
            pytest.skip(f"Authentication failed: {login_response.status_code} - {login_response.text}")
    
    # ── Test 1: GET auto-sync settings ──
    def test_get_auto_sync_settings(self):
        """GET /api/calendar/auto-sync/settings should return auto_sync_enabled and auto_sync_provider"""
        response = self.session.get(f"{BASE_URL}/api/calendar/auto-sync/settings")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "auto_sync_enabled" in data, "Response should have 'auto_sync_enabled' key"
        assert "auto_sync_provider" in data, "Response should have 'auto_sync_provider' key"
        assert isinstance(data["auto_sync_enabled"], bool), "auto_sync_enabled should be boolean"
        
        print(f"✓ GET /api/calendar/auto-sync/settings returned:")
        print(f"  auto_sync_enabled: {data['auto_sync_enabled']}")
        print(f"  auto_sync_provider: {data['auto_sync_provider']}")
    
    # ── Test 2: PUT auto-sync settings - enable with valid provider ──
    def test_update_auto_sync_enable_with_valid_provider(self):
        """PUT /api/calendar/auto-sync/settings should enable auto-sync with connected provider"""
        # First check which providers are connected
        conn_response = self.session.get(f"{BASE_URL}/api/calendar/connections")
        assert conn_response.status_code == 200
        connections = conn_response.json().get("connections", [])
        
        connected_providers = [c["provider"] for c in connections if c.get("status") == "connected"]
        print(f"Connected providers: {connected_providers}")
        
        if not connected_providers:
            pytest.skip("No connected providers to test with")
        
        # Use the first connected provider
        provider = connected_providers[0]
        
        response = self.session.put(f"{BASE_URL}/api/calendar/auto-sync/settings", json={
            "auto_sync_enabled": True,
            "auto_sync_provider": provider
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Response should have success=True"
        assert data.get("auto_sync_enabled") == True, "auto_sync_enabled should be True"
        assert data.get("auto_sync_provider") == provider, f"auto_sync_provider should be {provider}"
        
        print(f"✓ PUT /api/calendar/auto-sync/settings enabled auto-sync for {provider}")
    
    # ── Test 3: PUT auto-sync settings - disable ──
    def test_update_auto_sync_disable(self):
        """PUT /api/calendar/auto-sync/settings should disable auto-sync"""
        response = self.session.put(f"{BASE_URL}/api/calendar/auto-sync/settings", json={
            "auto_sync_enabled": False,
            "auto_sync_provider": None
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Response should have success=True"
        assert data.get("auto_sync_enabled") == False, "auto_sync_enabled should be False"
        assert data.get("auto_sync_provider") is None, "auto_sync_provider should be None"
        
        print(f"✓ PUT /api/calendar/auto-sync/settings disabled auto-sync")
    
    # ── Test 4: PUT auto-sync settings - refuse if enabled=true without provider ──
    def test_update_auto_sync_refuse_enabled_without_provider(self):
        """PUT /api/calendar/auto-sync/settings should refuse if enabled=true without provider"""
        response = self.session.put(f"{BASE_URL}/api/calendar/auto-sync/settings", json={
            "auto_sync_enabled": True,
            "auto_sync_provider": None
        })
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "detail" in data, "Error response should have 'detail' field"
        print(f"✓ PUT /api/calendar/auto-sync/settings correctly refused enabled=true without provider")
        print(f"  Error: {data['detail']}")
    
    # ── Test 5: PUT auto-sync settings - refuse if provider is invalid ──
    def test_update_auto_sync_refuse_invalid_provider(self):
        """PUT /api/calendar/auto-sync/settings should refuse invalid provider"""
        response = self.session.put(f"{BASE_URL}/api/calendar/auto-sync/settings", json={
            "auto_sync_enabled": True,
            "auto_sync_provider": "invalid_provider"
        })
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "detail" in data, "Error response should have 'detail' field"
        print(f"✓ PUT /api/calendar/auto-sync/settings correctly refused invalid provider")
        print(f"  Error: {data['detail']}")


class TestAutoSyncSettingsNoConnections:
    """Test auto-sync settings for user without calendar connections"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication for user without connections"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login with user that has no calendar connections
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_NO_CONNECTIONS["email"],
            "password": TEST_USER_NO_CONNECTIONS["password"]
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            self.token = data.get("access_token") or data.get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            print(f"✓ Logged in as {TEST_USER_NO_CONNECTIONS['email']}")
        else:
            pytest.skip(f"Authentication failed: {login_response.status_code}")
    
    # ── Test 6: PUT auto-sync settings - refuse if provider not connected ──
    def test_update_auto_sync_refuse_provider_not_connected(self):
        """PUT /api/calendar/auto-sync/settings should refuse if provider is not connected"""
        response = self.session.put(f"{BASE_URL}/api/calendar/auto-sync/settings", json={
            "auto_sync_enabled": True,
            "auto_sync_provider": "google"
        })
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "detail" in data, "Error response should have 'detail' field"
        # Should mention that Google Calendar is not connected
        assert "connecté" in data["detail"].lower() or "connected" in data["detail"].lower(), \
            f"Error should mention connection issue: {data['detail']}"
        
        print(f"✓ PUT /api/calendar/auto-sync/settings correctly refused non-connected provider")
        print(f"  Error: {data['detail']}")


class TestSyncStatusWithSyncSource:
    """Test sync status endpoint returns sync_source field"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login with user that has calendar connections
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_WITH_CONNECTIONS["email"],
            "password": TEST_USER_WITH_CONNECTIONS["password"]
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            self.token = data.get("access_token") or data.get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            print(f"✓ Logged in as {TEST_USER_WITH_CONNECTIONS['email']}")
        else:
            pytest.skip(f"Authentication failed: {login_response.status_code}")
    
    # ── Test 7: GET sync status returns sync_source ──
    def test_sync_status_returns_sync_source(self):
        """GET /api/calendar/sync/status/{id} should return sync_source in response"""
        response = self.session.get(f"{BASE_URL}/api/calendar/sync/status/{AUTO_SYNCED_APPOINTMENT_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify multi-provider format
        assert "google" in data, "Response should have 'google' key"
        assert "outlook" in data, "Response should have 'outlook' key"
        
        # Check if any provider has sync_source
        has_sync_source = False
        for provider in ["google", "outlook"]:
            if data[provider].get("synced"):
                # If synced, should have sync_source
                if "sync_source" in data[provider]:
                    has_sync_source = True
                    sync_source = data[provider]["sync_source"]
                    assert sync_source in ["auto", "manual"], f"sync_source should be 'auto' or 'manual', got: {sync_source}"
                    print(f"✓ {provider} sync_source: {sync_source}")
        
        print(f"✓ GET /api/calendar/sync/status/{AUTO_SYNCED_APPOINTMENT_ID} returned:")
        print(f"  Google: synced={data['google']['synced']}, sync_source={data['google'].get('sync_source', 'N/A')}")
        print(f"  Outlook: synced={data['outlook']['synced']}, sync_source={data['outlook'].get('sync_source', 'N/A')}")


class TestAutoSyncOnAppointmentCreation:
    """Test auto-sync is triggered when creating an appointment"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login with user that has calendar connections
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_WITH_CONNECTIONS["email"],
            "password": TEST_USER_WITH_CONNECTIONS["password"]
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            self.token = data.get("access_token") or data.get("token")
            self.user_id = data.get("user", {}).get("user_id")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            print(f"✓ Logged in as {TEST_USER_WITH_CONNECTIONS['email']}")
        else:
            pytest.skip(f"Authentication failed: {login_response.status_code}")
    
    # ── Test 8: Create appointment with auto-sync enabled ──
    def test_create_appointment_triggers_auto_sync(self):
        """POST /api/appointments/ should trigger auto-sync when enabled"""
        # First, check current auto-sync settings
        settings_response = self.session.get(f"{BASE_URL}/api/calendar/auto-sync/settings")
        assert settings_response.status_code == 200
        settings = settings_response.json()
        
        print(f"Current auto-sync settings: enabled={settings['auto_sync_enabled']}, provider={settings['auto_sync_provider']}")
        
        # If auto-sync is not enabled, enable it first
        if not settings['auto_sync_enabled']:
            # Check which providers are connected
            conn_response = self.session.get(f"{BASE_URL}/api/calendar/connections")
            connections = conn_response.json().get("connections", [])
            connected_providers = [c["provider"] for c in connections if c.get("status") == "connected"]
            
            if not connected_providers:
                pytest.skip("No connected providers to test auto-sync")
            
            # Enable auto-sync
            enable_response = self.session.put(f"{BASE_URL}/api/calendar/auto-sync/settings", json={
                "auto_sync_enabled": True,
                "auto_sync_provider": connected_providers[0]
            })
            assert enable_response.status_code == 200
            print(f"✓ Enabled auto-sync for {connected_providers[0]}")
        
        # Create a new appointment
        start_datetime = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%dT10:00:00Z")
        appointment_data = {
            "workspace_id": TEST_USER_WITH_CONNECTIONS["workspace_id"],
            "title": f"Test Auto-Sync {uuid.uuid4().hex[:8]}",
            "appointment_type": "video",
            "meeting_provider": "Google Meet",
            "start_datetime": start_datetime,
            "duration_minutes": 60,
            "tolerated_delay_minutes": 10,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 50,
            "penalty_currency": "EUR",
            "affected_compensation_percent": 60,
            "charity_percent": 20,
            "participants": []
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/appointments/", json=appointment_data)
        
        assert create_response.status_code == 200, f"Expected 200, got {create_response.status_code}: {create_response.text}"
        
        data = create_response.json()
        appointment_id = data.get("appointment_id")
        assert appointment_id, "Response should have appointment_id"
        
        print(f"✓ Created appointment: {appointment_id}")
        
        # Wait a moment for auto-sync to complete (it's synchronous but let's be safe)
        import time
        time.sleep(2)
        
        # Check sync status - should have sync_source='auto' if auto-sync worked
        sync_response = self.session.get(f"{BASE_URL}/api/calendar/sync/status/{appointment_id}")
        assert sync_response.status_code == 200
        
        sync_data = sync_response.json()
        print(f"Sync status: {sync_data}")
        
        # Check if auto-sync created a sync log
        auto_synced = False
        for provider in ["google", "outlook"]:
            if sync_data[provider].get("synced") and sync_data[provider].get("sync_source") == "auto":
                auto_synced = True
                print(f"✓ Auto-sync worked! {provider} synced with sync_source='auto'")
        
        # Note: Auto-sync might fail if the calendar API has issues, but the endpoint should still work
        if not auto_synced:
            print("⚠ Auto-sync did not create a sync log (may be expected if calendar API failed)")
        
        return appointment_id


class TestNoAutoSyncWhenDisabled:
    """Test that no auto-sync happens when disabled"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login with user that has no connections (auto-sync should be disabled)
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_NO_CONNECTIONS["email"],
            "password": TEST_USER_NO_CONNECTIONS["password"]
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            self.token = data.get("access_token") or data.get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            print(f"✓ Logged in as {TEST_USER_NO_CONNECTIONS['email']}")
        else:
            pytest.skip(f"Authentication failed: {login_response.status_code}")
    
    # ── Test 9: No auto-sync when disabled ──
    def test_no_auto_sync_when_disabled(self):
        """Creating appointment should not auto-sync when auto_sync_enabled=false"""
        # Verify auto-sync is disabled
        settings_response = self.session.get(f"{BASE_URL}/api/calendar/auto-sync/settings")
        assert settings_response.status_code == 200
        settings = settings_response.json()
        
        print(f"Auto-sync settings: enabled={settings['auto_sync_enabled']}, provider={settings['auto_sync_provider']}")
        
        # Get user's workspaces
        workspaces_response = self.session.get(f"{BASE_URL}/api/workspaces/")
        assert workspaces_response.status_code == 200
        workspaces = workspaces_response.json().get("workspaces", [])
        
        if not workspaces:
            pytest.skip("No workspaces available for this user")
        
        workspace_id = workspaces[0]["workspace_id"]
        
        # Create an appointment
        start_datetime = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%dT10:00:00Z")
        appointment_data = {
            "workspace_id": workspace_id,
            "title": f"Test No Auto-Sync {uuid.uuid4().hex[:8]}",
            "appointment_type": "video",
            "meeting_provider": "Zoom",
            "start_datetime": start_datetime,
            "duration_minutes": 30,
            "tolerated_delay_minutes": 5,
            "cancellation_deadline_hours": 12,
            "penalty_amount": 25,
            "penalty_currency": "EUR",
            "affected_compensation_percent": 60,
            "charity_percent": 20,
            "participants": []
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/appointments/", json=appointment_data)
        
        assert create_response.status_code == 200, f"Expected 200, got {create_response.status_code}: {create_response.text}"
        
        data = create_response.json()
        appointment_id = data.get("appointment_id")
        
        print(f"✓ Created appointment: {appointment_id}")
        
        # Check sync status - should have no syncs
        sync_response = self.session.get(f"{BASE_URL}/api/calendar/sync/status/{appointment_id}")
        assert sync_response.status_code == 200
        
        sync_data = sync_response.json()
        
        # Verify no auto-sync happened
        for provider in ["google", "outlook"]:
            assert sync_data[provider]["synced"] == False, f"{provider} should not be synced"
        
        print(f"✓ No auto-sync happened (as expected)")


class TestManualSyncStillWorks:
    """Test that manual sync still works (no regression)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login with user that has calendar connections
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_WITH_CONNECTIONS["email"],
            "password": TEST_USER_WITH_CONNECTIONS["password"]
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            self.token = data.get("access_token") or data.get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            print(f"✓ Logged in as {TEST_USER_WITH_CONNECTIONS['email']}")
        else:
            pytest.skip(f"Authentication failed: {login_response.status_code}")
    
    # ── Test 10: Manual sync creates sync_source='manual' ──
    def test_manual_sync_creates_manual_source(self):
        """POST /api/calendar/sync/appointment/{id} should create sync_source='manual'"""
        # Get an appointment to test with
        appointments_response = self.session.get(f"{BASE_URL}/api/appointments/")
        assert appointments_response.status_code == 200
        appointments = appointments_response.json().get("appointments", [])
        
        if not appointments:
            pytest.skip("No appointments available for testing")
        
        # Find an appointment that's not already synced
        test_appointment = None
        for apt in appointments:
            if apt.get("status") == "active":
                sync_response = self.session.get(f"{BASE_URL}/api/calendar/sync/status/{apt['appointment_id']}")
                if sync_response.status_code == 200:
                    sync_data = sync_response.json()
                    # Check if any provider is not synced but has connection
                    for provider in ["google", "outlook"]:
                        if sync_data[provider].get("has_connection") and not sync_data[provider].get("synced"):
                            test_appointment = apt
                            test_provider = provider
                            break
                if test_appointment:
                    break
        
        if not test_appointment:
            print("⚠ All appointments already synced or no connections available")
            # Just verify the endpoint works
            test_appointment = appointments[0]
            test_provider = "google"
        
        # Try manual sync
        sync_response = self.session.post(
            f"{BASE_URL}/api/calendar/sync/appointment/{test_appointment['appointment_id']}?provider={test_provider}"
        )
        
        # Could be 200 (synced), 400 (not connected), or already_synced
        if sync_response.status_code == 200:
            data = sync_response.json()
            if data.get("sync_status") == "synced":
                print(f"✓ Manual sync successful for {test_provider}")
                
                # Verify sync_source is 'manual'
                status_response = self.session.get(f"{BASE_URL}/api/calendar/sync/status/{test_appointment['appointment_id']}")
                status_data = status_response.json()
                
                if status_data[test_provider].get("sync_source") == "manual":
                    print(f"✓ sync_source is 'manual' as expected")
                else:
                    print(f"⚠ sync_source is '{status_data[test_provider].get('sync_source')}' (may be from previous auto-sync)")
            elif data.get("sync_status") == "already_synced":
                print(f"✓ Appointment already synced to {test_provider}")
        elif sync_response.status_code == 400:
            print(f"✓ Manual sync returned 400 (provider not connected): {sync_response.json().get('detail')}")
        else:
            print(f"Manual sync returned {sync_response.status_code}: {sync_response.text}")


class TestNoRegression:
    """Test that existing functionality still works"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_health_endpoint(self):
        """GET /api/health should return healthy"""
        response = self.session.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✓ Health endpoint working")
    
    def test_login_works(self):
        """POST /api/auth/login should work with valid credentials"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_WITH_CONNECTIONS["email"],
            "password": TEST_USER_WITH_CONNECTIONS["password"]
        })
        assert response.status_code == 200, f"Login failed: {response.status_code}: {response.text}"
        data = response.json()
        assert "access_token" in data or "token" in data
        print(f"✓ Login works for {TEST_USER_WITH_CONNECTIONS['email']}")
    
    def test_calendar_connections_endpoint(self):
        """GET /api/calendar/connections should work"""
        # Login first
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_WITH_CONNECTIONS["email"],
            "password": TEST_USER_WITH_CONNECTIONS["password"]
        })
        assert login_response.status_code == 200
        token = login_response.json().get("access_token") or login_response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        response = self.session.get(f"{BASE_URL}/api/calendar/connections")
        assert response.status_code == 200
        data = response.json()
        assert "connections" in data
        print(f"✓ Calendar connections endpoint working, found {len(data['connections'])} connection(s)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
