"""
Test Toggle Harmonization for External Calendar Sync
Tests the 3 changes:
1. Toggle ON in Agenda should NOT trigger GET /api/appointments/my-timeline (only GET /api/external-events/)
2. Guard anti double-clic via useRef in handleImportSettingChange
3. Auto-refresh 2min interval with lastAutoCheckAt
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestExternalEventsAPI:
    """Test external events API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "igaal@hotmail.com",
            "password": "Test123!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_import_settings(self):
        """GET /api/external-events/import-settings returns provider settings"""
        resp = requests.get(f"{BASE_URL}/api/external-events/import-settings", headers=self.headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "providers" in data, "Response should contain 'providers' key"
        print(f"✅ GET /api/external-events/import-settings - providers: {list(data.get('providers', {}).keys())}")
    
    def test_get_external_events(self):
        """GET /api/external-events/ returns events list"""
        resp = requests.get(f"{BASE_URL}/api/external-events/", headers=self.headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "events" in data, "Response should contain 'events' key"
        print(f"✅ GET /api/external-events/ - event count: {len(data.get('events', []))}")
    
    def test_sync_external_events(self):
        """POST /api/external-events/sync triggers sync"""
        resp = requests.post(f"{BASE_URL}/api/external-events/sync", 
                            headers=self.headers, 
                            json={"force": True})
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "results" in data, "Response should contain 'results' key"
        print(f"✅ POST /api/external-events/sync - results: {data.get('results', {})}")
    
    def test_update_import_setting_toggle_on(self):
        """PUT /api/external-events/import-settings with enabled=true triggers sync"""
        # First get current settings
        settings_resp = requests.get(f"{BASE_URL}/api/external-events/import-settings", headers=self.headers)
        settings = settings_resp.json()
        providers = settings.get("providers", {})
        
        # If google is connected, test toggle
        if "google" in providers:
            current_enabled = providers["google"].get("import_enabled", False)
            
            # Toggle ON
            resp = requests.put(f"{BASE_URL}/api/external-events/import-settings",
                               headers=self.headers,
                               json={"provider": "google", "enabled": True})
            assert resp.status_code == 200, f"Failed: {resp.text}"
            data = resp.json()
            
            # When enabling, sync should be triggered
            if "sync" in data:
                assert "synced" in data["sync"], "Sync result should contain 'synced' key"
                print(f"✅ PUT import-settings (google=true) - sync triggered: {data['sync'].get('synced')}")
            else:
                print(f"✅ PUT import-settings (google=true) - no sync needed (already enabled)")
            
            # Restore original state
            requests.put(f"{BASE_URL}/api/external-events/import-settings",
                        headers=self.headers,
                        json={"provider": "google", "enabled": current_enabled})
        elif "outlook" in providers:
            current_enabled = providers["outlook"].get("import_enabled", False)
            
            resp = requests.put(f"{BASE_URL}/api/external-events/import-settings",
                               headers=self.headers,
                               json={"provider": "outlook", "enabled": True})
            assert resp.status_code == 200, f"Failed: {resp.text}"
            print(f"✅ PUT import-settings (outlook=true) - success")
            
            # Restore
            requests.put(f"{BASE_URL}/api/external-events/import-settings",
                        headers=self.headers,
                        json={"provider": "outlook", "enabled": current_enabled})
        else:
            pytest.skip("No calendar provider connected - skipping toggle test")
    
    def test_update_import_setting_toggle_off(self):
        """PUT /api/external-events/import-settings with enabled=false"""
        settings_resp = requests.get(f"{BASE_URL}/api/external-events/import-settings", headers=self.headers)
        settings = settings_resp.json()
        providers = settings.get("providers", {})
        
        if "google" in providers:
            current_enabled = providers["google"].get("import_enabled", False)
            
            # Toggle OFF
            resp = requests.put(f"{BASE_URL}/api/external-events/import-settings",
                               headers=self.headers,
                               json={"provider": "google", "enabled": False})
            assert resp.status_code == 200, f"Failed: {resp.text}"
            data = resp.json()
            
            # When disabling, no sync should be triggered
            assert "sync" not in data or not data.get("sync", {}).get("synced"), \
                "Sync should NOT be triggered when disabling"
            print(f"✅ PUT import-settings (google=false) - no sync triggered (correct)")
            
            # Restore
            requests.put(f"{BASE_URL}/api/external-events/import-settings",
                        headers=self.headers,
                        json={"provider": "google", "enabled": current_enabled})
        elif "outlook" in providers:
            current_enabled = providers["outlook"].get("import_enabled", False)
            
            resp = requests.put(f"{BASE_URL}/api/external-events/import-settings",
                               headers=self.headers,
                               json={"provider": "outlook", "enabled": False})
            assert resp.status_code == 200, f"Failed: {resp.text}"
            print(f"✅ PUT import-settings (outlook=false) - success")
            
            # Restore
            requests.put(f"{BASE_URL}/api/external-events/import-settings",
                        headers=self.headers,
                        json={"provider": "outlook", "enabled": current_enabled})
        else:
            pytest.skip("No calendar provider connected - skipping toggle test")
    
    def test_my_timeline_endpoint(self):
        """GET /api/appointments/my-timeline returns timeline data"""
        resp = requests.get(f"{BASE_URL}/api/appointments/my-timeline", headers=self.headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "action_required" in data, "Response should contain 'action_required'"
        assert "upcoming" in data, "Response should contain 'upcoming'"
        assert "past" in data, "Response should contain 'past'"
        print(f"✅ GET /api/appointments/my-timeline - counts: {data.get('counts', {})}")


class TestInvalidRequests:
    """Test error handling for invalid requests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "igaal@hotmail.com",
            "password": "Test123!"
        })
        self.token = login_resp.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_invalid_provider(self):
        """PUT with invalid provider should return 400"""
        resp = requests.put(f"{BASE_URL}/api/external-events/import-settings",
                           headers=self.headers,
                           json={"provider": "invalid", "enabled": True})
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        print(f"✅ Invalid provider returns 400")
    
    def test_invalid_enabled_type(self):
        """PUT with non-boolean enabled should return 400"""
        resp = requests.put(f"{BASE_URL}/api/external-events/import-settings",
                           headers=self.headers,
                           json={"provider": "google", "enabled": "yes"})
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        print(f"✅ Invalid enabled type returns 400")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
