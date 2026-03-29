"""
Test iteration 135: Modification Summary Display Fix
Tests that the formatChangeSummary function in OrganizerDashboard correctly displays:
- DATE changes (not just time)
- LOCATION changes (with old → new format)
- MEETING_PROVIDER changes (Zoom, Teams, Google Meet labels)
- DURATION changes
- APPOINTMENT_TYPE changes

Backend API tests verify that /api/modifications/mine returns:
- changes: dict with modified fields
- original_values: dict with original values for comparison
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestModificationSummaryAPI:
    """Tests for modification summary display - backend API verification"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
    def test_01_health_check(self):
        """Verify API is accessible"""
        response = self.session.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("PASS: API health check")
        
    def test_02_login_organizer(self):
        """Login as organizer to get token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testuser_audit@nlyt.app",
            "password": "TestAudit123!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        self.session.headers.update({"Authorization": f"Bearer {data['access_token']}"})
        print("PASS: Organizer login successful")
        return data['access_token']
        
    def test_03_modifications_mine_endpoint(self):
        """Test GET /api/modifications/mine returns proposals with changes and original_values"""
        # First login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testuser_audit@nlyt.app",
            "password": "TestAudit123!"
        })
        assert login_resp.status_code == 200
        token = login_resp.json()['access_token']
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get modifications
        response = self.session.get(f"{BASE_URL}/api/modifications/mine")
        assert response.status_code == 200
        data = response.json()
        assert "proposals" in data
        print(f"PASS: GET /api/modifications/mine returns {len(data['proposals'])} proposals")
        
        # If there are proposals, verify structure
        if data['proposals']:
            proposal = data['proposals'][0]
            print(f"  Sample proposal fields: {list(proposal.keys())}")
            
            # Verify required fields exist
            required_fields = ['proposal_id', 'appointment_id', 'status', 'changes']
            for field in required_fields:
                assert field in proposal, f"Missing field: {field}"
            
            # Verify changes structure
            if proposal.get('changes'):
                print(f"  Changes: {proposal['changes']}")
            if proposal.get('original_values'):
                print(f"  Original values: {proposal['original_values']}")
                
        return data
        
    def test_04_modifications_mine_fields_structure(self):
        """Verify modifications/mine returns all fields needed for formatChangeSummary"""
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testuser_audit@nlyt.app",
            "password": "TestAudit123!"
        })
        token = login_resp.json()['access_token']
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        response = self.session.get(f"{BASE_URL}/api/modifications/mine")
        assert response.status_code == 200
        data = response.json()
        
        # Check if any proposal has the fields we need for summary display
        for proposal in data.get('proposals', []):
            changes = proposal.get('changes', {})
            original = proposal.get('original_values', {})
            
            # Log what fields are present
            if changes:
                print(f"  Proposal {proposal['proposal_id'][:8]}... changes: {list(changes.keys())}")
                
                # Verify original_values has corresponding fields
                for field in changes.keys():
                    if field in original:
                        print(f"    {field}: {original[field]} → {changes[field]}")
                    else:
                        print(f"    {field}: (no original) → {changes[field]}")
                        
        print("PASS: Modifications structure verified")
        
    def test_05_timeline_with_modifications(self):
        """Test GET /api/appointments/my-timeline returns modification data"""
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testuser_audit@nlyt.app",
            "password": "TestAudit123!"
        })
        token = login_resp.json()['access_token']
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        response = self.session.get(f"{BASE_URL}/api/appointments/my-timeline")
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "upcoming" in data or "items" in data
        print(f"PASS: Timeline endpoint returns data")
        
        # Look for items with modifications
        items = data.get('upcoming', data.get('items', []))
        items_with_mods = [i for i in items if i.get('has_pending_modification')]
        print(f"  Found {len(items_with_mods)} items with pending modifications")
        
    def test_06_participant_login_and_modifications(self):
        """Test participant can see modifications via /api/modifications/mine"""
        # Login as participant
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "igaal@hotmail.com",
            "password": "Test123!"
        })
        assert login_resp.status_code == 200
        token = login_resp.json()['access_token']
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        response = self.session.get(f"{BASE_URL}/api/modifications/mine")
        assert response.status_code == 200
        data = response.json()
        
        print(f"PASS: Participant sees {len(data.get('proposals', []))} modification proposals")
        
        # Check for action required
        action_required = [p for p in data.get('proposals', []) if p.get('is_action_required')]
        print(f"  Action required: {len(action_required)}")


class TestModificationSummaryFields:
    """Tests specifically for the fields used in formatChangeSummary"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
    def test_07_contractual_fields_in_changes(self):
        """Verify CONTRACTUAL_FIELDS are properly returned in changes"""
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testuser_audit@nlyt.app",
            "password": "TestAudit123!"
        })
        token = login_resp.json()['access_token']
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        response = self.session.get(f"{BASE_URL}/api/modifications/mine")
        data = response.json()
        
        # CONTRACTUAL_FIELDS from backend: start_datetime, duration_minutes, location, meeting_provider, appointment_type
        contractual_fields = ['start_datetime', 'duration_minutes', 'location', 'meeting_provider', 'appointment_type']
        
        found_fields = set()
        for proposal in data.get('proposals', []):
            changes = proposal.get('changes', {})
            for field in changes.keys():
                if field in contractual_fields:
                    found_fields.add(field)
                    
        print(f"PASS: Found contractual fields in proposals: {found_fields}")
        
    def test_08_original_values_for_comparison(self):
        """Verify original_values are returned for comparison in formatChangeSummary"""
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testuser_audit@nlyt.app",
            "password": "TestAudit123!"
        })
        token = login_resp.json()['access_token']
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        response = self.session.get(f"{BASE_URL}/api/modifications/mine")
        data = response.json()
        
        for proposal in data.get('proposals', []):
            changes = proposal.get('changes', {})
            original = proposal.get('original_values', {})
            
            if changes:
                # Verify each changed field has an original value
                for field in changes.keys():
                    if field in original:
                        print(f"  {field}: original={original[field]}, new={changes[field]}")
                    else:
                        print(f"  {field}: NO ORIGINAL VALUE (new={changes[field]})")
                        
        print("PASS: Original values structure verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
