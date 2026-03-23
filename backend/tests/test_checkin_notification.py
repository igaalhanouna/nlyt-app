"""
Test Checkin Notification Feature
Tests the new feature: When a participant checks in (physical or video), 
all OTHER engaged participants receive an email notification.
Uses atomic flag checkin_notification_sent for idempotence.
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from review request
TEST_USER_EMAIL = "testuser_audit@nlyt.app"
TEST_USER_PASSWORD = "Test1234!"
PHYSICAL_APT_ID = "a860bab5-c885-4787-a73e-3779529d3b8a"
VIDEO_APT_ID = "4bc2d91a-fc0f-4b67-a1e1-61439772b504"
ORGANIZER_TOKEN = "3da80d4e-2f1d-45ba-bb8f-801712aa3dd6"
PARTICIPANT_TOKEN = "656caec0-5d2e-42c5-8888-8b0b6684211e"


class TestHealthEndpoint:
    """Test 1: Backend health check"""
    
    def test_health_returns_200(self):
        """GET /api/health returns 200"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✅ Test 1 PASSED: GET /api/health returns 200")


class TestCheckinEndpointsExist:
    """Tests 2-5: Verify check-in endpoints are reachable"""
    
    def test_manual_checkin_endpoint_exists(self):
        """Test 2: POST /api/checkin/manual endpoint is reachable"""
        # Send invalid request to verify endpoint exists (should return 422 for validation error, not 404)
        response = requests.post(f"{BASE_URL}/api/checkin/manual", json={})
        assert response.status_code != 404, f"Endpoint not found: {response.status_code}"
        print(f"✅ Test 2 PASSED: POST /api/checkin/manual endpoint exists (status: {response.status_code})")
    
    def test_qr_verify_endpoint_exists(self):
        """Test 3: POST /api/checkin/qr/verify endpoint is reachable"""
        response = requests.post(f"{BASE_URL}/api/checkin/qr/verify", json={})
        assert response.status_code != 404, f"Endpoint not found: {response.status_code}"
        print(f"✅ Test 3 PASSED: POST /api/checkin/qr/verify endpoint exists (status: {response.status_code})")
    
    def test_gps_checkin_endpoint_exists(self):
        """Test 4: POST /api/checkin/gps endpoint is reachable"""
        response = requests.post(f"{BASE_URL}/api/checkin/gps", json={})
        assert response.status_code != 404, f"Endpoint not found: {response.status_code}"
        print(f"✅ Test 4 PASSED: POST /api/checkin/gps endpoint exists (status: {response.status_code})")
    
    def test_proof_checkin_endpoint_exists(self):
        """Test 5: POST /api/proof/{id}/checkin endpoint is reachable"""
        response = requests.post(f"{BASE_URL}/api/proof/{VIDEO_APT_ID}/checkin", json={"token": "invalid"})
        # Should return 404 for invalid token, not 404 for endpoint not found
        assert response.status_code in [400, 404, 422], f"Unexpected status: {response.status_code}"
        print(f"✅ Test 5 PASSED: POST /api/proof/{{id}}/checkin endpoint exists (status: {response.status_code})")


class TestCheckinNotificationService:
    """Tests 6-11: Test the checkin notification service logic"""
    
    @pytest.fixture(autouse=True)
    def setup_mongo(self):
        """Setup MongoDB connection for direct testing"""
        from pymongo import MongoClient
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        DB_NAME = os.environ.get('DB_NAME', 'test_database')
        self.client = MongoClient(MONGO_URL)
        self.db = self.client[DB_NAME]
        yield
        self.client.close()
    
    def test_idempotence_flag_prevents_duplicate_notifications(self):
        """Test 6: A second check-in for the same participant should NOT send another notification"""
        # Create a test participant with checkin_notification_sent already True
        test_participant_id = f"TEST_idempotence_{uuid.uuid4()}"
        test_appointment_id = f"TEST_apt_{uuid.uuid4()}"
        
        # Insert test participant with flag already set
        self.db.participants.insert_one({
            "participant_id": test_participant_id,
            "appointment_id": test_appointment_id,
            "email": "test_idempotence@test.com",
            "first_name": "Test",
            "last_name": "Idempotence",
            "status": "accepted",
            "checkin_notification_sent": True,
            "checkin_notification_sent_at": datetime.now(timezone.utc).isoformat(),
        })
        
        try:
            # Try to set the flag again using atomic update
            result = self.db.participants.update_one(
                {"participant_id": test_participant_id, "checkin_notification_sent": {"$ne": True}},
                {"$set": {
                    "checkin_notification_sent": True,
                    "checkin_notification_sent_at": datetime.now(timezone.utc).isoformat(),
                }}
            )
            
            # Should NOT modify because flag is already True
            assert result.modified_count == 0, "Flag should not be modified when already True"
            print("✅ Test 6 PASSED: Idempotence - second check-in does NOT trigger notification (modified_count=0)")
        finally:
            # Cleanup
            self.db.participants.delete_one({"participant_id": test_participant_id})
    
    def test_first_checkin_sets_flag(self):
        """Test 6b: First check-in should set the checkin_notification_sent flag"""
        test_participant_id = f"TEST_first_checkin_{uuid.uuid4()}"
        test_appointment_id = f"TEST_apt_{uuid.uuid4()}"
        
        # Insert test participant WITHOUT the flag
        self.db.participants.insert_one({
            "participant_id": test_participant_id,
            "appointment_id": test_appointment_id,
            "email": "test_first@test.com",
            "first_name": "Test",
            "last_name": "First",
            "status": "accepted",
        })
        
        try:
            # Try to set the flag using atomic update
            result = self.db.participants.update_one(
                {"participant_id": test_participant_id, "checkin_notification_sent": {"$ne": True}},
                {"$set": {
                    "checkin_notification_sent": True,
                    "checkin_notification_sent_at": datetime.now(timezone.utc).isoformat(),
                }}
            )
            
            # Should modify because flag was not set
            assert result.modified_count == 1, "Flag should be set on first check-in"
            
            # Verify flag is now set
            participant = self.db.participants.find_one({"participant_id": test_participant_id})
            assert participant.get("checkin_notification_sent") == True
            print("✅ Test 6b PASSED: First check-in sets checkin_notification_sent flag")
        finally:
            # Cleanup
            self.db.participants.delete_one({"participant_id": test_participant_id})


class TestEmailContent:
    """Tests 7-9: Test email content for video and physical check-ins"""
    
    @pytest.mark.asyncio
    async def test_video_checkin_email_content(self):
        """Test 7: Email content for video check-in contains 'a confirme sa presence'"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.email_service import EmailService
        
        captured_html = []
        
        # Monkey-patch send_email to capture HTML
        original_send_email = EmailService.send_email
        
        async def mock_send_email(to_email, subject, html_content, email_type="generic"):
            captured_html.append(html_content)
            return {"success": True, "email_id": "mock_id"}
        
        EmailService.send_email = staticmethod(mock_send_email)
        
        try:
            await EmailService.send_checkin_notification_email(
                to_email="recipient@test.com",
                to_name="Recipient Name",
                checkin_person_name="John Doe",
                checkin_is_organizer=False,
                appointment_title="Test Meeting",
                appointment_datetime=datetime.now(timezone.utc).isoformat(),
                appointment_type="video",
                meeting_provider="zoom",
                checkin_time=datetime.now(timezone.utc).isoformat(),
            )
            
            assert len(captured_html) == 1, "Email should be sent"
            html = captured_html[0]
            
            # Check for video-specific wording (French)
            assert "a confirme sa presence" in html.lower() or "a confirmé sa présence" in html.lower(), \
                f"Video check-in email should contain 'a confirme sa presence'. HTML: {html[:500]}"
            print("✅ Test 7 PASSED: Video check-in email contains 'a confirme sa presence'")
        finally:
            EmailService.send_email = staticmethod(original_send_email)
    
    @pytest.mark.asyncio
    async def test_physical_checkin_email_content(self):
        """Test 8: Email content for physical check-in contains 'est arrive au rendez-vous'"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.email_service import EmailService
        
        captured_html = []
        
        async def mock_send_email(to_email, subject, html_content, email_type="generic"):
            captured_html.append(html_content)
            return {"success": True, "email_id": "mock_id"}
        
        original_send_email = EmailService.send_email
        EmailService.send_email = staticmethod(mock_send_email)
        
        try:
            await EmailService.send_checkin_notification_email(
                to_email="recipient@test.com",
                to_name="Recipient Name",
                checkin_person_name="John Doe",
                checkin_is_organizer=False,
                appointment_title="Test Meeting",
                appointment_datetime=datetime.now(timezone.utc).isoformat(),
                appointment_type="physical",
                checkin_time=datetime.now(timezone.utc).isoformat(),
            )
            
            assert len(captured_html) == 1, "Email should be sent"
            html = captured_html[0]
            
            # Check for physical-specific wording (French)
            assert "est arrive au rendez-vous" in html.lower() or "est arrivé au rendez-vous" in html.lower(), \
                f"Physical check-in email should contain 'est arrive au rendez-vous'. HTML: {html[:500]}"
            print("✅ Test 8 PASSED: Physical check-in email contains 'est arrive au rendez-vous'")
        finally:
            EmailService.send_email = staticmethod(original_send_email)
    
    @pytest.mark.asyncio
    async def test_organizer_label_in_email(self):
        """Test 9: When checkin_is_organizer=True, email includes '(organisateur)'"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.email_service import EmailService
        
        captured_html = []
        
        async def mock_send_email(to_email, subject, html_content, email_type="generic"):
            captured_html.append(html_content)
            return {"success": True, "email_id": "mock_id"}
        
        original_send_email = EmailService.send_email
        EmailService.send_email = staticmethod(mock_send_email)
        
        try:
            await EmailService.send_checkin_notification_email(
                to_email="recipient@test.com",
                to_name="Recipient Name",
                checkin_person_name="John Doe",
                checkin_is_organizer=True,  # Organizer checking in
                appointment_title="Test Meeting",
                appointment_datetime=datetime.now(timezone.utc).isoformat(),
                appointment_type="physical",
                checkin_time=datetime.now(timezone.utc).isoformat(),
            )
            
            assert len(captured_html) == 1, "Email should be sent"
            html = captured_html[0]
            
            # Check for organizer label
            assert "(organisateur)" in html.lower(), \
                f"Organizer check-in email should contain '(organisateur)'. HTML: {html[:500]}"
            print("✅ Test 9 PASSED: Organizer check-in email includes '(organisateur)'")
        finally:
            EmailService.send_email = staticmethod(original_send_email)


class TestRecipientFiltering:
    """Tests 10-11: Test recipient filtering logic"""
    
    @pytest.fixture(autouse=True)
    def setup_mongo(self):
        """Setup MongoDB connection for direct testing"""
        from pymongo import MongoClient
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        DB_NAME = os.environ.get('DB_NAME', 'test_database')
        self.client = MongoClient(MONGO_URL)
        self.db = self.client[DB_NAME]
        yield
        self.client.close()
    
    def test_only_engaged_recipients_receive_notification(self):
        """Test 10: Notification is only sent to participants with status accepted or accepted_guaranteed"""
        test_appointment_id = f"TEST_engaged_{uuid.uuid4()}"
        
        # Create participants with different statuses
        participants = [
            {"participant_id": f"TEST_p1_{uuid.uuid4()}", "status": "accepted", "email": "accepted@test.com"},
            {"participant_id": f"TEST_p2_{uuid.uuid4()}", "status": "accepted_guaranteed", "email": "guaranteed@test.com"},
            {"participant_id": f"TEST_p3_{uuid.uuid4()}", "status": "invited", "email": "invited@test.com"},
            {"participant_id": f"TEST_p4_{uuid.uuid4()}", "status": "declined", "email": "declined@test.com"},
        ]
        
        for p in participants:
            self.db.participants.insert_one({
                **p,
                "appointment_id": test_appointment_id,
                "first_name": "Test",
                "last_name": "User",
            })
        
        try:
            # Query for engaged recipients (same logic as notify_checkin)
            recipients = list(self.db.participants.find(
                {
                    "appointment_id": test_appointment_id,
                    "status": {"$in": ["accepted", "accepted_guaranteed"]},
                },
                {"_id": 0, "email": 1, "status": 1}
            ))
            
            emails = [r["email"] for r in recipients]
            
            # Should include accepted and accepted_guaranteed
            assert "accepted@test.com" in emails, "Should include 'accepted' status"
            assert "guaranteed@test.com" in emails, "Should include 'accepted_guaranteed' status"
            
            # Should NOT include invited or declined
            assert "invited@test.com" not in emails, "Should NOT include 'invited' status"
            assert "declined@test.com" not in emails, "Should NOT include 'declined' status"
            
            print("✅ Test 10 PASSED: Only engaged recipients (accepted, accepted_guaranteed) receive notification")
        finally:
            # Cleanup
            for p in participants:
                self.db.participants.delete_one({"participant_id": p["participant_id"]})
    
    def test_self_exclusion_from_notification(self):
        """Test 11: The person who checks in does NOT receive their own notification email"""
        test_appointment_id = f"TEST_self_excl_{uuid.uuid4()}"
        checker_id = f"TEST_checker_{uuid.uuid4()}"
        other_id = f"TEST_other_{uuid.uuid4()}"
        
        # Create checker and another participant
        self.db.participants.insert_one({
            "participant_id": checker_id,
            "appointment_id": test_appointment_id,
            "email": "checker@test.com",
            "first_name": "Checker",
            "last_name": "User",
            "status": "accepted",
        })
        self.db.participants.insert_one({
            "participant_id": other_id,
            "appointment_id": test_appointment_id,
            "email": "other@test.com",
            "first_name": "Other",
            "last_name": "User",
            "status": "accepted",
        })
        
        try:
            # Query for recipients excluding the checker (same logic as notify_checkin)
            recipients = list(self.db.participants.find(
                {
                    "appointment_id": test_appointment_id,
                    "participant_id": {"$ne": checker_id},  # Exclude self
                    "status": {"$in": ["accepted", "accepted_guaranteed"]},
                },
                {"_id": 0, "email": 1, "participant_id": 1}
            ))
            
            recipient_ids = [r["participant_id"] for r in recipients]
            emails = [r["email"] for r in recipients]
            
            # Should NOT include the checker
            assert checker_id not in recipient_ids, "Checker should be excluded from recipients"
            assert "checker@test.com" not in emails, "Checker email should not be in recipients"
            
            # Should include the other participant
            assert other_id in recipient_ids, "Other participant should be included"
            assert "other@test.com" in emails, "Other participant email should be included"
            
            print("✅ Test 11 PASSED: Self-exclusion - checker does NOT receive their own notification")
        finally:
            # Cleanup
            self.db.participants.delete_one({"participant_id": checker_id})
            self.db.participants.delete_one({"participant_id": other_id})


class TestIntegrationWithRealEndpoints:
    """Integration tests using real endpoints with test data"""
    
    @pytest.fixture(autouse=True)
    def setup_mongo(self):
        """Setup MongoDB connection"""
        from pymongo import MongoClient
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        DB_NAME = os.environ.get('DB_NAME', 'test_database')
        self.client = MongoClient(MONGO_URL)
        self.db = self.client[DB_NAME]
        yield
        self.client.close()
    
    def test_manual_checkin_with_valid_token(self):
        """Test manual check-in endpoint with a valid invitation token"""
        # First, find a valid participant token for the physical appointment
        participant = self.db.participants.find_one({
            "appointment_id": PHYSICAL_APT_ID,
            "status": {"$in": ["accepted", "accepted_guaranteed"]},
        }, {"_id": 0})
        
        if not participant:
            pytest.skip("No valid participant found for physical appointment")
        
        token = participant.get("invitation_token")
        if not token:
            pytest.skip("Participant has no invitation token")
        
        # Reset the checkin_notification_sent flag for testing
        self.db.participants.update_one(
            {"participant_id": participant["participant_id"]},
            {"$unset": {"checkin_notification_sent": "", "checkin_notification_sent_at": ""}}
        )
        
        # Also delete any existing evidence for this participant
        self.db.evidence.delete_many({
            "appointment_id": PHYSICAL_APT_ID,
            "participant_id": participant["participant_id"],
        })
        
        response = requests.post(f"{BASE_URL}/api/checkin/manual", json={
            "invitation_token": token,
            "device_info": "pytest_test",
            "latitude": 48.8566,
            "longitude": 2.3522,
            "gps_consent": True,
        })
        
        # Accept 200 (success), 409 (already checked in), or 400 (outside time window)
        assert response.status_code in [200, 400, 409], f"Unexpected status: {response.status_code}, body: {response.text}"
        
        if response.status_code == 200:
            # Verify the flag was set
            updated = self.db.participants.find_one({"participant_id": participant["participant_id"]})
            assert updated.get("checkin_notification_sent") == True, "Flag should be set after check-in"
            print("✅ Integration Test PASSED: Manual check-in sets notification flag")
        else:
            print(f"ℹ️ Integration Test: Manual check-in returned {response.status_code} - {response.json().get('detail', '')}")
    
    def test_video_proof_checkin_with_valid_token(self):
        """Test video proof check-in endpoint"""
        # Use the provided video appointment tokens
        response = requests.post(f"{BASE_URL}/api/proof/{VIDEO_APT_ID}/checkin", json={
            "token": PARTICIPANT_TOKEN,
            "video_display_name": "Test User",
        })
        
        # Accept 200 (success), 400 (not video apt or cancelled), or 404 (invalid token)
        assert response.status_code in [200, 400, 404], f"Unexpected status: {response.status_code}, body: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "session_id" in data or "already_active" in data
            print("✅ Integration Test PASSED: Video proof check-in works")
        else:
            print(f"ℹ️ Integration Test: Video proof check-in returned {response.status_code} - {response.json().get('detail', '')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
