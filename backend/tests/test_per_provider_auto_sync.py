"""
Test Per-Provider Auto-Sync Calendar Feature - NLYT SaaS V1
Tests the new per-provider auto-sync functionality:
- GET /api/calendar/auto-sync/settings returns auto_sync_providers (array) and connected_providers (array)
- PUT /api/calendar/auto-sync/settings with {auto_sync_providers: ['google']} enables only Google
- PUT /api/calendar/auto-sync/settings with {auto_sync_providers: ['google','outlook']} enables both
- PUT /api/calendar/auto-sync/settings with {auto_sync_providers: []} disables all
- Legacy format PUT with {auto_sync_enabled: true} still works (enables all connected)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test user with Google + Outlook connected
TEST_USER_CLARA = {
    "email": "clara.deschamps@demo-nlyt.fr",
    "password": "Demo2026!"
}


class TestPerProviderAutoSyncSettings:
    """Test per-provider auto-sync settings endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication for Clara (has Google + Outlook)"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_CLARA["email"],
            "password": TEST_USER_CLARA["password"]
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            self.token = data.get("access_token") or data.get("token")
            self.user_id = data.get("user", {}).get("user_id")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            print(f"✓ Logged in as {TEST_USER_CLARA['email']}")
        else:
            pytest.skip(f"Authentication failed: {login_response.status_code} - {login_response.text}")
    
    # ── Test 1: GET auto-sync settings returns auto_sync_providers and connected_providers ──
    def test_get_auto_sync_settings_returns_arrays(self):
        """GET /api/calendar/auto-sync/settings should return auto_sync_providers (array) and connected_providers (array)"""
        response = self.session.get(f"{BASE_URL}/api/calendar/auto-sync/settings")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Check for new per-provider fields
        assert "auto_sync_providers" in data, "Response should have 'auto_sync_providers' key"
        assert "connected_providers" in data, "Response should have 'connected_providers' key"
        assert isinstance(data["auto_sync_providers"], list), "auto_sync_providers should be a list"
        assert isinstance(data["connected_providers"], list), "connected_providers should be a list"
        
        # Legacy field should still exist
        assert "auto_sync_enabled" in data, "Response should have 'auto_sync_enabled' key (legacy)"
        assert isinstance(data["auto_sync_enabled"], bool), "auto_sync_enabled should be boolean"
        
        print(f"✓ GET /api/calendar/auto-sync/settings returned:")
        print(f"  auto_sync_enabled: {data['auto_sync_enabled']}")
        print(f"  auto_sync_providers: {data['auto_sync_providers']}")
        print(f"  connected_providers: {data['connected_providers']}")
    
    # ── Test 2: PUT with auto_sync_providers: ['google'] enables only Google ──
    def test_enable_only_google_sync(self):
        """PUT /api/calendar/auto-sync/settings with {auto_sync_providers: ['google']} should enable only Google"""
        response = self.session.put(f"{BASE_URL}/api/calendar/auto-sync/settings", json={
            "auto_sync_providers": ["google"]
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Response should have success=True"
        assert data.get("auto_sync_enabled") == True, "auto_sync_enabled should be True"
        assert "auto_sync_providers" in data, "Response should have auto_sync_providers"
        assert data["auto_sync_providers"] == ["google"], f"auto_sync_providers should be ['google'], got {data['auto_sync_providers']}"
        
        print(f"✓ PUT with auto_sync_providers: ['google'] - enabled only Google")
        print(f"  Response: {data}")
    
    # ── Test 3: PUT with auto_sync_providers: ['google', 'outlook'] enables both ──
    def test_enable_both_google_and_outlook_sync(self):
        """PUT /api/calendar/auto-sync/settings with {auto_sync_providers: ['google','outlook']} should enable both"""
        response = self.session.put(f"{BASE_URL}/api/calendar/auto-sync/settings", json={
            "auto_sync_providers": ["google", "outlook"]
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Response should have success=True"
        assert data.get("auto_sync_enabled") == True, "auto_sync_enabled should be True"
        assert "auto_sync_providers" in data, "Response should have auto_sync_providers"
        
        # Check both providers are enabled (order may vary)
        providers = set(data["auto_sync_providers"])
        assert providers == {"google", "outlook"}, f"auto_sync_providers should be ['google', 'outlook'], got {data['auto_sync_providers']}"
        
        print(f"✓ PUT with auto_sync_providers: ['google', 'outlook'] - enabled both")
        print(f"  Response: {data}")
    
    # ── Test 4: PUT with auto_sync_providers: [] disables all ──
    def test_disable_all_sync(self):
        """PUT /api/calendar/auto-sync/settings with {auto_sync_providers: []} should disable all"""
        response = self.session.put(f"{BASE_URL}/api/calendar/auto-sync/settings", json={
            "auto_sync_providers": []
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Response should have success=True"
        assert data.get("auto_sync_enabled") == False, "auto_sync_enabled should be False when providers list is empty"
        assert data.get("auto_sync_providers") == [], f"auto_sync_providers should be [], got {data['auto_sync_providers']}"
        
        print(f"✓ PUT with auto_sync_providers: [] - disabled all")
        print(f"  Response: {data}")
    
    # ── Test 5: Legacy format PUT with {auto_sync_enabled: true} still works ──
    def test_legacy_format_enable_all_connected(self):
        """PUT /api/calendar/auto-sync/settings with {auto_sync_enabled: true} should enable all connected providers"""
        response = self.session.put(f"{BASE_URL}/api/calendar/auto-sync/settings", json={
            "auto_sync_enabled": True
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Response should have success=True"
        assert data.get("auto_sync_enabled") == True, "auto_sync_enabled should be True"
        
        # Should enable all connected providers
        connected = data.get("connected_providers", [])
        enabled = data.get("auto_sync_providers", [])
        
        # All connected providers should be enabled
        for provider in connected:
            assert provider in enabled, f"Connected provider {provider} should be enabled"
        
        print(f"✓ Legacy format PUT with auto_sync_enabled: true - enabled all connected")
        print(f"  connected_providers: {connected}")
        print(f"  auto_sync_providers: {enabled}")
    
    # ── Test 6: Legacy format PUT with {auto_sync_enabled: false} disables all ──
    def test_legacy_format_disable_all(self):
        """PUT /api/calendar/auto-sync/settings with {auto_sync_enabled: false} should disable all"""
        response = self.session.put(f"{BASE_URL}/api/calendar/auto-sync/settings", json={
            "auto_sync_enabled": False
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Response should have success=True"
        assert data.get("auto_sync_enabled") == False, "auto_sync_enabled should be False"
        assert data.get("auto_sync_providers") == [], f"auto_sync_providers should be [], got {data['auto_sync_providers']}"
        
        print(f"✓ Legacy format PUT with auto_sync_enabled: false - disabled all")
        print(f"  Response: {data}")
    
    # ── Test 7: PUT with only outlook enabled ──
    def test_enable_only_outlook_sync(self):
        """PUT /api/calendar/auto-sync/settings with {auto_sync_providers: ['outlook']} should enable only Outlook"""
        response = self.session.put(f"{BASE_URL}/api/calendar/auto-sync/settings", json={
            "auto_sync_providers": ["outlook"]
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Response should have success=True"
        assert data.get("auto_sync_enabled") == True, "auto_sync_enabled should be True"
        assert data["auto_sync_providers"] == ["outlook"], f"auto_sync_providers should be ['outlook'], got {data['auto_sync_providers']}"
        
        print(f"✓ PUT with auto_sync_providers: ['outlook'] - enabled only Outlook")
        print(f"  Response: {data}")
    
    # ── Test 8: Verify GET reflects changes after PUT ──
    def test_get_reflects_put_changes(self):
        """GET should reflect changes made by PUT"""
        # First enable only Google
        put_response = self.session.put(f"{BASE_URL}/api/calendar/auto-sync/settings", json={
            "auto_sync_providers": ["google"]
        })
        assert put_response.status_code == 200
        
        # Then GET and verify
        get_response = self.session.get(f"{BASE_URL}/api/calendar/auto-sync/settings")
        assert get_response.status_code == 200
        
        data = get_response.json()
        assert data["auto_sync_providers"] == ["google"], f"GET should return ['google'], got {data['auto_sync_providers']}"
        assert data["auto_sync_enabled"] == True, "auto_sync_enabled should be True"
        
        print(f"✓ GET reflects PUT changes correctly")
        print(f"  auto_sync_providers: {data['auto_sync_providers']}")
    
    # ── Test 9: Invalid provider is filtered out ──
    def test_invalid_provider_filtered(self):
        """PUT with invalid provider should filter it out (only keep connected providers)"""
        response = self.session.put(f"{BASE_URL}/api/calendar/auto-sync/settings", json={
            "auto_sync_providers": ["google", "invalid_provider", "outlook"]
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Invalid provider should be filtered out
        assert "invalid_provider" not in data.get("auto_sync_providers", []), "Invalid provider should be filtered out"
        
        print(f"✓ Invalid provider filtered out")
        print(f"  auto_sync_providers: {data['auto_sync_providers']}")


class TestAutoSyncSettingsNoConnections:
    """Test auto-sync settings for user without calendar connections"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication for user without connections"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Try to login with a user that might not have connections
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "marie.morel@demo-nlyt.fr",
            "password": "Demo2026!"
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            self.token = data.get("access_token") or data.get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            print(f"✓ Logged in as marie.morel@demo-nlyt.fr")
        else:
            pytest.skip(f"Authentication failed: {login_response.status_code}")
    
    def test_legacy_enable_without_connections_fails(self):
        """PUT with auto_sync_enabled: true should fail if no calendars connected"""
        # First check if user has connections
        conn_response = self.session.get(f"{BASE_URL}/api/calendar/connections")
        if conn_response.status_code == 200:
            connections = conn_response.json().get("connections", [])
            connected = [c for c in connections if c.get("status") == "connected"]
            if connected:
                pytest.skip("User has calendar connections, skipping this test")
        
        response = self.session.put(f"{BASE_URL}/api/calendar/auto-sync/settings", json={
            "auto_sync_enabled": True
        })
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "detail" in data, "Error response should have 'detail' field"
        print(f"✓ Legacy enable without connections correctly rejected")
        print(f"  Error: {data['detail']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
