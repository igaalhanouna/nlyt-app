"""
Test suite for Organizer as Participant feature
Tests:
1. POST /api/appointments/ → response contains organizer_participant_id and organizer_invitation_token
2. POST /api/appointments/ → response contains organizer_checkout_url when penalty_amount > 0
3. GET /api/participants/?appointment_id={id} → returns organizer with is_organizer=true and role='organizer'
4. Organizer should NOT receive duplicate invitation email (same email as organizer)
5. POST /api/checkin/manual with organizer's invitation_token → creates evidence_item
6. Physical appointment without meeting_provider → should work (non-regression)
7. Video appointment with meeting_provider='meet' → should work with organizer auto-injected
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"
WORKSPACE_ID = "7e219321-18fd-4643-9be6-e4f1de88a2a8"
EXISTING_APPOINTMENT_ID = "8f3572cb-11b9-4b51-a659-f187cbd633ee"


class TestOrganizerParticipant:
    """Tests for organizer as participant feature"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code != 200:
            pytest.skip(f"Login failed: {login_response.status_code} - {login_response.text}")
        
        self.token = login_response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.user_email = TEST_EMAIL
        yield
    
    def test_01_create_appointment_returns_organizer_fields(self):
        """TEST 1: POST /api/appointments/ returns organizer_participant_id and organizer_invitation_token"""
        # Create a future datetime
        from datetime import datetime, timedelta
        future_dt = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
        
        payload = {
            "workspace_id": WORKSPACE_ID,
            "title": f"TEST_Organizer_Participant_{int(time.time())}",
            "appointment_type": "physical",
            "location": "123 Test Street, Paris",
            "start_datetime": future_dt,
            "duration_minutes": 60,
            "tolerated_delay_minutes": 15,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "affected_compensation_percent": 80,
            "charity_percent": 0,
            "participants": [
                {"first_name": "Test", "last_name": "Participant", "email": "test_participant@example.com", "role": "participant"}
            ]
        }
        
        response = self.session.post(f"{BASE_URL}/api/appointments/", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify organizer fields are present
        assert "organizer_participant_id" in data, "Response should contain organizer_participant_id"
        assert "organizer_invitation_token" in data, "Response should contain organizer_invitation_token"
        assert data["organizer_participant_id"] is not None, "organizer_participant_id should not be None"
        assert data["organizer_invitation_token"] is not None, "organizer_invitation_token should not be None"
        
        # Store for cleanup
        self.created_appointment_id = data["appointment_id"]
        print(f"✓ TEST 1 PASSED: Appointment created with organizer_participant_id={data['organizer_participant_id']}")
    
    def test_02_create_appointment_returns_organizer_checkout_url(self):
        """TEST 2: POST /api/appointments/ returns organizer_checkout_url when penalty_amount > 0"""
        from datetime import datetime, timedelta
        future_dt = (datetime.utcnow() + timedelta(days=8)).strftime("%Y-%m-%dT%H:%M:%S")
        
        payload = {
            "workspace_id": WORKSPACE_ID,
            "title": f"TEST_Organizer_Stripe_{int(time.time())}",
            "appointment_type": "physical",
            "location": "456 Test Avenue, Paris",
            "start_datetime": future_dt,
            "duration_minutes": 60,
            "tolerated_delay_minutes": 15,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 100,  # > 0 to trigger Stripe
            "penalty_currency": "eur",
            "affected_compensation_percent": 80,
            "charity_percent": 0,
            "participants": []
        }
        
        response = self.session.post(f"{BASE_URL}/api/appointments/", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify organizer_checkout_url is present when penalty > 0
        assert "organizer_checkout_url" in data, "Response should contain organizer_checkout_url when penalty_amount > 0"
        assert data["organizer_checkout_url"] is not None, "organizer_checkout_url should not be None"
        assert "stripe.com" in data["organizer_checkout_url"] or "checkout" in data["organizer_checkout_url"], \
            f"organizer_checkout_url should be a Stripe URL, got: {data['organizer_checkout_url']}"
        
        print(f"✓ TEST 2 PASSED: organizer_checkout_url present: {data['organizer_checkout_url'][:50]}...")
    
    def test_03_get_participants_returns_organizer(self):
        """TEST 3: GET /api/participants/?appointment_id={id} returns organizer with is_organizer=true and role='organizer'"""
        # Use existing test appointment
        response = self.session.get(f"{BASE_URL}/api/participants/?appointment_id={EXISTING_APPOINTMENT_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        participants = data.get("participants", [])
        assert len(participants) > 0, "Should have at least one participant"
        
        # Find organizer participant
        organizer = next((p for p in participants if p.get("is_organizer") == True), None)
        
        assert organizer is not None, "Should have an organizer participant with is_organizer=true"
        assert organizer.get("role") == "organizer", f"Organizer should have role='organizer', got: {organizer.get('role')}"
        assert organizer.get("is_organizer") == True, "Organizer should have is_organizer=true"
        
        print(f"✓ TEST 3 PASSED: Organizer found with is_organizer=true, role='organizer', email={organizer.get('email')}")
    
    def test_04_organizer_not_duplicated_as_participant(self):
        """TEST 4: Organizer should NOT be duplicated when added as participant with same email"""
        from datetime import datetime, timedelta
        future_dt = (datetime.utcnow() + timedelta(days=9)).strftime("%Y-%m-%dT%H:%M:%S")
        
        # Create appointment with organizer's own email in participants list
        payload = {
            "workspace_id": WORKSPACE_ID,
            "title": f"TEST_No_Duplicate_{int(time.time())}",
            "appointment_type": "physical",
            "location": "789 Test Boulevard, Paris",
            "start_datetime": future_dt,
            "duration_minutes": 60,
            "tolerated_delay_minutes": 15,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "affected_compensation_percent": 80,
            "charity_percent": 0,
            "participants": [
                # Add organizer's own email - should be skipped
                {"first_name": "Test", "last_name": "User", "email": TEST_EMAIL, "role": "participant"},
                {"first_name": "Other", "last_name": "Person", "email": "other@example.com", "role": "participant"}
            ]
        }
        
        response = self.session.post(f"{BASE_URL}/api/appointments/", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        appointment_id = data["appointment_id"]
        
        # Get participants
        participants_response = self.session.get(f"{BASE_URL}/api/participants/?appointment_id={appointment_id}")
        assert participants_response.status_code == 200
        
        participants = participants_response.json().get("participants", [])
        
        # Count how many times organizer's email appears
        organizer_email_count = sum(1 for p in participants if p.get("email", "").lower() == TEST_EMAIL.lower())
        
        assert organizer_email_count == 1, f"Organizer email should appear exactly once, found {organizer_email_count} times"
        
        # Verify the one with organizer email has is_organizer=true
        organizer_participant = next((p for p in participants if p.get("email", "").lower() == TEST_EMAIL.lower()), None)
        assert organizer_participant.get("is_organizer") == True, "The organizer email participant should have is_organizer=true"
        
        print(f"✓ TEST 4 PASSED: Organizer email appears exactly once with is_organizer=true")
    
    def test_05_organizer_checkin_creates_evidence(self):
        """TEST 5: POST /api/checkin/manual with organizer's invitation_token creates evidence_item"""
        # Get organizer's invitation token from existing appointment
        participants_response = self.session.get(f"{BASE_URL}/api/participants/?appointment_id={EXISTING_APPOINTMENT_ID}")
        assert participants_response.status_code == 200
        
        participants = participants_response.json().get("participants", [])
        organizer = next((p for p in participants if p.get("is_organizer") == True), None)
        
        assert organizer is not None, "Should have an organizer participant"
        invitation_token = organizer.get("invitation_token")
        assert invitation_token is not None, "Organizer should have an invitation_token"
        
        # Check organizer status - must be accepted_guaranteed for check-in
        if organizer.get("status") != "accepted_guaranteed":
            pytest.skip(f"Organizer status is {organizer.get('status')}, needs to be accepted_guaranteed for check-in test")
        
        # Perform manual check-in
        checkin_payload = {
            "appointment_id": EXISTING_APPOINTMENT_ID,
            "invitation_token": invitation_token
        }
        
        checkin_response = self.session.post(f"{BASE_URL}/api/checkin/manual", json=checkin_payload)
        
        # Accept both 200 (success) and 409 (already checked in)
        assert checkin_response.status_code in [200, 409], \
            f"Expected 200 or 409, got {checkin_response.status_code}: {checkin_response.text}"
        
        if checkin_response.status_code == 200:
            data = checkin_response.json()
            assert "evidence_id" in data, "Check-in response should contain evidence_id"
            print(f"✓ TEST 5 PASSED: Organizer check-in created evidence_id={data.get('evidence_id')}")
        else:
            # Already checked in - verify evidence exists
            status_response = self.session.get(
                f"{BASE_URL}/api/checkin/status/{EXISTING_APPOINTMENT_ID}?invitation_token={invitation_token}"
            )
            assert status_response.status_code == 200
            status_data = status_response.json()
            assert status_data.get("evidence_count", 0) > 0, "Should have evidence after check-in"
            print(f"✓ TEST 5 PASSED: Organizer already checked in, evidence_count={status_data.get('evidence_count')}")
    
    def test_06_physical_appointment_without_meeting_provider(self):
        """TEST 6: Physical appointment without meeting_provider should work (non-regression)"""
        from datetime import datetime, timedelta
        future_dt = (datetime.utcnow() + timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S")
        
        payload = {
            "workspace_id": WORKSPACE_ID,
            "title": f"TEST_Physical_No_Provider_{int(time.time())}",
            "appointment_type": "physical",
            "location": "Physical Location Test, Paris",
            "start_datetime": future_dt,
            "duration_minutes": 60,
            "tolerated_delay_minutes": 15,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "affected_compensation_percent": 80,
            "charity_percent": 0,
            "participants": []
            # Note: No meeting_provider field for physical appointment
        }
        
        response = self.session.post(f"{BASE_URL}/api/appointments/", json=payload)
        
        assert response.status_code == 200, f"Physical appointment should succeed, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "appointment_id" in data, "Response should contain appointment_id"
        assert "organizer_participant_id" in data, "Response should contain organizer_participant_id"
        
        print(f"✓ TEST 6 PASSED: Physical appointment created without meeting_provider")
    
    def test_07_video_appointment_with_meet_provider(self):
        """TEST 7: Video appointment with meeting_provider='meet' should work with organizer auto-injected"""
        from datetime import datetime, timedelta
        future_dt = (datetime.utcnow() + timedelta(days=11)).strftime("%Y-%m-%dT%H:%M:%S")
        
        payload = {
            "workspace_id": WORKSPACE_ID,
            "title": f"TEST_Video_Meet_{int(time.time())}",
            "appointment_type": "video",
            "meeting_provider": "meet",
            "start_datetime": future_dt,
            "duration_minutes": 60,
            "tolerated_delay_minutes": 15,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "affected_compensation_percent": 80,
            "charity_percent": 0,
            "participants": []
        }
        
        response = self.session.post(f"{BASE_URL}/api/appointments/", json=payload)
        
        assert response.status_code == 200, f"Video appointment with meet should succeed, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "appointment_id" in data, "Response should contain appointment_id"
        assert "organizer_participant_id" in data, "Response should contain organizer_participant_id"
        assert "organizer_invitation_token" in data, "Response should contain organizer_invitation_token"
        
        # Verify organizer was injected
        appointment_id = data["appointment_id"]
        participants_response = self.session.get(f"{BASE_URL}/api/participants/?appointment_id={appointment_id}")
        assert participants_response.status_code == 200
        
        participants = participants_response.json().get("participants", [])
        organizer = next((p for p in participants if p.get("is_organizer") == True), None)
        
        assert organizer is not None, "Organizer should be auto-injected as participant"
        assert organizer.get("role") == "organizer", "Organizer should have role='organizer'"
        
        print(f"✓ TEST 7 PASSED: Video appointment with meet provider created, organizer auto-injected")


class TestMeetingProviderValidation:
    """Tests for meeting_provider validation (non-regression from previous bug)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code != 200:
            pytest.skip(f"Login failed: {login_response.status_code}")
        
        self.token = login_response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        yield
    
    def test_08_video_without_provider_fails(self):
        """TEST 8: Video appointment without meeting_provider should fail validation"""
        from datetime import datetime, timedelta
        future_dt = (datetime.utcnow() + timedelta(days=12)).strftime("%Y-%m-%dT%H:%M:%S")
        
        payload = {
            "workspace_id": WORKSPACE_ID,
            "title": f"TEST_Video_No_Provider_{int(time.time())}",
            "appointment_type": "video",
            # No meeting_provider - should fail
            "start_datetime": future_dt,
            "duration_minutes": 60,
            "tolerated_delay_minutes": 15,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "affected_compensation_percent": 80,
            "charity_percent": 0,
            "participants": []
        }
        
        response = self.session.post(f"{BASE_URL}/api/appointments/", json=payload)
        
        # Should fail with 422 validation error
        assert response.status_code == 422, f"Video without provider should fail with 422, got {response.status_code}: {response.text}"
        
        print(f"✓ TEST 8 PASSED: Video appointment without meeting_provider correctly rejected with 422")
    
    def test_09_physical_with_empty_provider_succeeds(self):
        """TEST 9: Physical appointment with empty meeting_provider string should succeed"""
        from datetime import datetime, timedelta
        future_dt = (datetime.utcnow() + timedelta(days=13)).strftime("%Y-%m-%dT%H:%M:%S")
        
        payload = {
            "workspace_id": WORKSPACE_ID,
            "title": f"TEST_Physical_Empty_Provider_{int(time.time())}",
            "appointment_type": "physical",
            "location": "Test Location",
            "meeting_provider": "",  # Empty string - should be converted to None
            "start_datetime": future_dt,
            "duration_minutes": 60,
            "tolerated_delay_minutes": 15,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "affected_compensation_percent": 80,
            "charity_percent": 0,
            "participants": []
        }
        
        response = self.session.post(f"{BASE_URL}/api/appointments/", json=payload)
        
        assert response.status_code == 200, f"Physical with empty provider should succeed, got {response.status_code}: {response.text}"
        
        print(f"✓ TEST 9 PASSED: Physical appointment with empty meeting_provider succeeded")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
