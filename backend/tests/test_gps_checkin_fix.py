"""
Test GPS Check-in Fix - Backend API Tests
Tests for proper HTTP error codes and messages for check-in endpoints:
- 409 for already checked-in participant
- 400 for non-accepted participant
- 404 for invalid token
- Success cases with/without GPS coordinates
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"


class TestGPSCheckinFix:
    """Test suite for GPS check-in error handling improvements"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get auth token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        yield
        
        # Cleanup
        self.session.close()

    def test_health_endpoint(self):
        """Test 1: Verify API is healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✓ Test 1: Health endpoint returns 200")

    def test_manual_checkin_invalid_token_returns_404(self):
        """Test 2: POST /api/checkin/manual with invalid token returns 404"""
        response = requests.post(f"{BASE_URL}/api/checkin/manual", json={
            "invitation_token": "invalid-token-12345",
            "device_info": "pytest-test-agent"
        })
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        print(f"✓ Test 2: Invalid token returns 404 with detail: {data['detail']}")

    def test_manual_checkin_non_accepted_returns_400(self):
        """Test 3: POST /api/checkin/manual with non-accepted participant returns 400"""
        # Get user's workspaces
        ws_response = self.session.get(f"{BASE_URL}/api/workspaces/")
        if ws_response.status_code != 200:
            pytest.skip(f"Cannot get workspaces - status {ws_response.status_code}")
        
        ws_data = ws_response.json()
        workspaces = ws_data.get("workspaces", [])
        if not workspaces:
            pytest.skip("No workspaces available")
        
        workspace_id = workspaces[0].get("workspace_id")
        
        # Create a test appointment
        future_date = (datetime.utcnow() + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        apt_response = self.session.post(f"{BASE_URL}/api/appointments/", json={
            "workspace_id": workspace_id,
            "title": f"TEST_GPS_FIX_{uuid.uuid4().hex[:8]}",
            "start_datetime": future_date,
            "duration_minutes": 30,
            "appointment_type": "physical",
            "location": "Test Location",
            "penalty_amount": 1,
            "cancellation_deadline_hours": 1,
            "tolerated_delay_minutes": 5,
            "affected_compensation_percent": 80,
            "charity_percent": 0
        })
        
        if apt_response.status_code not in (200, 201):
            pytest.skip(f"Cannot create appointment: {apt_response.text}")
        
        apt_data = apt_response.json()
        appointment_id = apt_data.get("appointment_id")
        
        # Add a participant (will be in 'invited' status)
        part_response = self.session.post(f"{BASE_URL}/api/participants/?appointment_id={appointment_id}", json={
            "email": f"test_invited_{uuid.uuid4().hex[:8]}@test.com",
            "first_name": "Test",
            "last_name": "Invited"
        })
        
        if part_response.status_code not in (200, 201):
            self.session.delete(f"{BASE_URL}/api/appointments/{appointment_id}")
            pytest.skip(f"Cannot create participant: {part_response.text}")
        
        part_data = part_response.json()
        invitation_token = part_data.get("invitation_token")
        
        # Try to check in with non-accepted participant
        checkin_response = requests.post(f"{BASE_URL}/api/checkin/manual", json={
            "invitation_token": invitation_token,
            "device_info": "pytest-test-agent"
        })
        
        assert checkin_response.status_code == 400
        data = checkin_response.json()
        assert "detail" in data
        print(f"✓ Test 3: Non-accepted participant returns 400 with detail: {data['detail']}")
        
        # Cleanup - delete the appointment
        self.session.delete(f"{BASE_URL}/api/appointments/{appointment_id}")

    def test_manual_checkin_success_without_gps(self):
        """Test 4: POST /api/checkin/manual accepts valid check-in without GPS"""
        # Get an existing accepted participant from the database
        # We'll use the test appointment from previous iterations
        
        # First try to find an existing accepted participant
        ws_response = self.session.get(f"{BASE_URL}/api/workspaces/")
        if ws_response.status_code != 200:
            pytest.skip("Cannot get workspaces")
        
        ws_data = ws_response.json()
        workspaces = ws_data.get("workspaces", [])
        if not workspaces:
            pytest.skip("No workspaces available")
        
        workspace_id = workspaces[0].get("workspace_id")
        
        # Create a test appointment with accepted participant
        future_date = (datetime.utcnow() + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        apt_response = self.session.post(f"{BASE_URL}/api/appointments/", json={
            "workspace_id": workspace_id,
            "title": f"TEST_CHECKIN_SUCCESS_{uuid.uuid4().hex[:8]}",
            "start_datetime": future_date,
            "duration_minutes": 60,
            "appointment_type": "physical",
            "location": "Test Location Paris",
            "penalty_amount": 1,
            "cancellation_deadline_hours": 1,
            "tolerated_delay_minutes": 15,
            "affected_compensation_percent": 80,
            "charity_percent": 0
        })
        
        if apt_response.status_code not in (200, 201):
            pytest.skip(f"Cannot create appointment: {apt_response.text}")
        
        apt_data = apt_response.json()
        appointment_id = apt_data.get("appointment_id")
        
        # Add a participant
        part_response = self.session.post(f"{BASE_URL}/api/participants/?appointment_id={appointment_id}", json={
            "email": f"test_accept_{uuid.uuid4().hex[:8]}@test.com",
            "first_name": "Test",
            "last_name": "Accept"
        })
        
        if part_response.status_code not in (200, 201):
            self.session.delete(f"{BASE_URL}/api/appointments/{appointment_id}")
            pytest.skip(f"Cannot create participant: {part_response.text}")
        
        part_data = part_response.json()
        invitation_token = part_data.get("invitation_token")
        
        # Accept the invitation
        accept_response = requests.post(f"{BASE_URL}/api/invitations/{invitation_token}/respond", json={
            "action": "accept"
        })
        
        if accept_response.status_code != 200:
            self.session.delete(f"{BASE_URL}/api/appointments/{appointment_id}")
            pytest.skip(f"Cannot accept invitation: {accept_response.text}")
        
        # Now try to check in without GPS
        checkin_response = requests.post(f"{BASE_URL}/api/checkin/manual", json={
            "invitation_token": invitation_token,
            "device_info": "pytest-test-agent-no-gps"
        })
        
        # Should succeed (200) or already checked in (409)
        assert checkin_response.status_code in (200, 409)
        data = checkin_response.json()
        
        if checkin_response.status_code == 200:
            assert "evidence" in data or "success" in str(data).lower() or "evidence_id" in data
            print(f"✓ Test 4: Check-in without GPS succeeded")
        else:
            assert "detail" in data
            print(f"✓ Test 4: Check-in returned 409 (already checked in): {data['detail']}")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/appointments/{appointment_id}")

    def test_manual_checkin_success_with_gps(self):
        """Test 5: POST /api/checkin/manual accepts valid check-in with GPS coordinates"""
        ws_response = self.session.get(f"{BASE_URL}/api/workspaces/")
        if ws_response.status_code != 200:
            pytest.skip("Cannot get workspaces")
        
        ws_data = ws_response.json()
        workspaces = ws_data.get("workspaces", [])
        if not workspaces:
            pytest.skip("No workspaces available")
        
        workspace_id = workspaces[0].get("workspace_id")
        
        # Create a test appointment
        future_date = (datetime.utcnow() + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        apt_response = self.session.post(f"{BASE_URL}/api/appointments/", json={
            "workspace_id": workspace_id,
            "title": f"TEST_CHECKIN_GPS_{uuid.uuid4().hex[:8]}",
            "start_datetime": future_date,
            "duration_minutes": 60,
            "appointment_type": "physical",
            "location": "48.8566, 2.3522",  # Paris coordinates
            "penalty_amount": 1,
            "cancellation_deadline_hours": 1,
            "tolerated_delay_minutes": 15,
            "affected_compensation_percent": 80,
            "charity_percent": 0
        })
        
        if apt_response.status_code not in (200, 201):
            pytest.skip(f"Cannot create appointment: {apt_response.text}")
        
        apt_data = apt_response.json()
        appointment_id = apt_data.get("appointment_id")
        
        # Add a participant
        part_response = self.session.post(f"{BASE_URL}/api/participants/?appointment_id={appointment_id}", json={
            "email": f"test_gps_{uuid.uuid4().hex[:8]}@test.com",
            "first_name": "Test",
            "last_name": "GPS"
        })
        
        if part_response.status_code not in (200, 201):
            self.session.delete(f"{BASE_URL}/api/appointments/{appointment_id}")
            pytest.skip(f"Cannot create participant: {part_response.text}")
        
        part_data = part_response.json()
        invitation_token = part_data.get("invitation_token")
        
        # Accept the invitation
        accept_response = requests.post(f"{BASE_URL}/api/invitations/{invitation_token}/respond", json={
            "action": "accept"
        })
        
        if accept_response.status_code != 200:
            self.session.delete(f"{BASE_URL}/api/appointments/{appointment_id}")
            pytest.skip(f"Cannot accept invitation: {accept_response.text}")
        
        # Check in with GPS coordinates
        checkin_response = requests.post(f"{BASE_URL}/api/checkin/manual", json={
            "invitation_token": invitation_token,
            "device_info": "pytest-test-agent-with-gps",
            "latitude": 48.8566,
            "longitude": 2.3522,
            "gps_consent": True
        })
        
        assert checkin_response.status_code in (200, 409)
        data = checkin_response.json()
        
        if checkin_response.status_code == 200:
            print(f"✓ Test 5: Check-in with GPS succeeded")
        else:
            print(f"✓ Test 5: Check-in returned 409 (already checked in): {data.get('detail')}")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/appointments/{appointment_id}")

    def test_manual_checkin_duplicate_returns_409(self):
        """Test 6: POST /api/checkin/manual returns 409 for duplicate check-in"""
        ws_response = self.session.get(f"{BASE_URL}/api/workspaces/")
        if ws_response.status_code != 200:
            pytest.skip("Cannot get workspaces")
        
        ws_data = ws_response.json()
        workspaces = ws_data.get("workspaces", [])
        if not workspaces:
            pytest.skip("No workspaces available")
        
        workspace_id = workspaces[0].get("workspace_id")
        
        # Create a test appointment
        future_date = (datetime.utcnow() + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        apt_response = self.session.post(f"{BASE_URL}/api/appointments/", json={
            "workspace_id": workspace_id,
            "title": f"TEST_DUPLICATE_{uuid.uuid4().hex[:8]}",
            "start_datetime": future_date,
            "duration_minutes": 60,
            "appointment_type": "physical",
            "location": "Test Location",
            "penalty_amount": 1,
            "cancellation_deadline_hours": 1,
            "tolerated_delay_minutes": 15,
            "affected_compensation_percent": 80,
            "charity_percent": 0
        })
        
        if apt_response.status_code not in (200, 201):
            pytest.skip(f"Cannot create appointment: {apt_response.text}")
        
        apt_data = apt_response.json()
        appointment_id = apt_data.get("appointment_id")
        
        # Add a participant
        part_response = self.session.post(f"{BASE_URL}/api/participants/?appointment_id={appointment_id}", json={
            "email": f"test_dup_{uuid.uuid4().hex[:8]}@test.com",
            "first_name": "Test",
            "last_name": "Duplicate"
        })
        
        if part_response.status_code not in (200, 201):
            self.session.delete(f"{BASE_URL}/api/appointments/{appointment_id}")
            pytest.skip(f"Cannot create participant: {part_response.text}")
        
        part_data = part_response.json()
        invitation_token = part_data.get("invitation_token")
        
        # Accept the invitation
        accept_response = requests.post(f"{BASE_URL}/api/invitations/{invitation_token}/respond", json={
            "action": "accept"
        })
        
        if accept_response.status_code != 200:
            self.session.delete(f"{BASE_URL}/api/appointments/{appointment_id}")
            pytest.skip(f"Cannot accept invitation: {accept_response.text}")
        
        # First check-in
        first_checkin = requests.post(f"{BASE_URL}/api/checkin/manual", json={
            "invitation_token": invitation_token,
            "device_info": "pytest-first-checkin"
        })
        
        # Second check-in should return 409
        second_checkin = requests.post(f"{BASE_URL}/api/checkin/manual", json={
            "invitation_token": invitation_token,
            "device_info": "pytest-second-checkin"
        })
        
        assert second_checkin.status_code == 409
        data = second_checkin.json()
        assert "detail" in data
        print(f"✓ Test 6: Duplicate check-in returns 409 with detail: {data['detail']}")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/appointments/{appointment_id}")

    def test_gps_checkin_invalid_token_returns_404(self):
        """Test 7: POST /api/checkin/gps with invalid token returns 404"""
        response = requests.post(f"{BASE_URL}/api/checkin/gps", json={
            "invitation_token": "invalid-gps-token-12345",
            "latitude": 48.8566,
            "longitude": 2.3522
        })
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        print(f"✓ Test 7: GPS check-in with invalid token returns 404 with detail: {data['detail']}")

    def test_gps_checkin_duplicate_returns_409(self):
        """Test 8: POST /api/checkin/gps returns 409 for duplicate GPS evidence"""
        ws_response = self.session.get(f"{BASE_URL}/api/workspaces/")
        if ws_response.status_code != 200:
            pytest.skip("Cannot get workspaces")
        
        ws_data = ws_response.json()
        workspaces = ws_data.get("workspaces", [])
        if not workspaces:
            pytest.skip("No workspaces available")
        
        workspace_id = workspaces[0].get("workspace_id")
        
        # Create a test appointment
        future_date = (datetime.utcnow() + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        apt_response = self.session.post(f"{BASE_URL}/api/appointments/", json={
            "workspace_id": workspace_id,
            "title": f"TEST_GPS_DUP_{uuid.uuid4().hex[:8]}",
            "start_datetime": future_date,
            "duration_minutes": 60,
            "appointment_type": "physical",
            "location": "48.8566, 2.3522",
            "penalty_amount": 1,
            "cancellation_deadline_hours": 1,
            "tolerated_delay_minutes": 15,
            "affected_compensation_percent": 80,
            "charity_percent": 0
        })
        
        if apt_response.status_code not in (200, 201):
            pytest.skip(f"Cannot create appointment: {apt_response.text}")
        
        apt_data = apt_response.json()
        appointment_id = apt_data.get("appointment_id")
        
        # Add a participant
        part_response = self.session.post(f"{BASE_URL}/api/participants/?appointment_id={appointment_id}", json={
            "email": f"test_gps_dup_{uuid.uuid4().hex[:8]}@test.com",
            "first_name": "Test",
            "last_name": "GPSDup"
        })
        
        if part_response.status_code not in (200, 201):
            self.session.delete(f"{BASE_URL}/api/appointments/{appointment_id}")
            pytest.skip(f"Cannot create participant: {part_response.text}")
        
        part_data = part_response.json()
        invitation_token = part_data.get("invitation_token")
        
        # Accept the invitation
        accept_response = requests.post(f"{BASE_URL}/api/invitations/{invitation_token}/respond", json={
            "action": "accept"
        })
        
        if accept_response.status_code != 200:
            self.session.delete(f"{BASE_URL}/api/appointments/{appointment_id}")
            pytest.skip(f"Cannot accept invitation: {accept_response.text}")
        
        # First GPS check-in
        first_gps = requests.post(f"{BASE_URL}/api/checkin/gps", json={
            "invitation_token": invitation_token,
            "latitude": 48.8566,
            "longitude": 2.3522
        })
        
        # Second GPS check-in should return 409
        second_gps = requests.post(f"{BASE_URL}/api/checkin/gps", json={
            "invitation_token": invitation_token,
            "latitude": 48.8567,
            "longitude": 2.3523
        })
        
        assert second_gps.status_code == 409
        data = second_gps.json()
        assert "detail" in data
        print(f"✓ Test 8: Duplicate GPS check-in returns 409 with detail: {data['detail']}")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/appointments/{appointment_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
