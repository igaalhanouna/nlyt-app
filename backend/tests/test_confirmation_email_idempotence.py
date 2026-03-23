"""
Test: Confirmation Email Idempotence Fix (Iteration 45)

Tests the critical fix where confirmation email is now sent from BOTH:
- Webhook path (webhooks.py)
- Polling fallback path (check_guarantee_status in invitations.py)

Key features tested:
1. send_confirmation_email_once helper exists and is importable
2. Idempotence: calling twice sends email only once (confirmation_email_sent flag)
3. MongoDB atomic update with $ne True condition for concurrency safety
4. Video email content: proof_link, "Confirmer ma presence et rejoindre" button
5. Physical email content: "Je suis arrive" button, NO proof_link
6. ICS button present in both email types
7. Webhook path imports and calls send_confirmation_email_once
8. Polling path calls send_confirmation_email_once
9. Direct accept path calls send_confirmation_email_once
10. Polling endpoint returns correct status and is_guaranteed fields
"""

import pytest
import requests
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.append('/app/backend')

# Load frontend .env to get REACT_APP_BACKEND_URL
from dotenv import load_dotenv
load_dotenv('/app/frontend/.env')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://stripe-connect-hub-6.preview.emergentagent.com').rstrip('/')


class TestHealthEndpoint:
    """Basic health check"""
    
    def test_health_returns_200(self):
        """GET /api/health returns 200"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get('status') == 'healthy'
        print("✅ Health endpoint returns 200")


class TestHelperImportability:
    """Test that send_confirmation_email_once is importable"""
    
    def test_helper_exists_and_importable(self):
        """send_confirmation_email_once exists and is importable from routers.invitations"""
        try:
            from routers.invitations import send_confirmation_email_once
            assert callable(send_confirmation_email_once)
            print("✅ send_confirmation_email_once is importable and callable")
        except ImportError as e:
            pytest.fail(f"Failed to import send_confirmation_email_once: {e}")
    
    def test_webhook_imports_helper(self):
        """webhooks.py can import send_confirmation_email_once"""
        # Verify the import statement exists in webhooks.py
        webhooks_path = '/app/backend/routers/webhooks.py'
        with open(webhooks_path, 'r') as f:
            content = f.read()
        
        assert 'from routers.invitations import send_confirmation_email_once' in content
        print("✅ webhooks.py imports send_confirmation_email_once")


class TestIdempotence:
    """Test idempotent email sending"""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock MongoDB database"""
        from pymongo import MongoClient
        MONGO_URL = os.environ.get('MONGO_URL')
        DB_NAME = os.environ.get('DB_NAME')
        client = MongoClient(MONGO_URL)
        return client[DB_NAME]
    
    @pytest.fixture
    def test_participant(self, mock_db):
        """Create a test participant for idempotence testing"""
        participant_id = f"TEST_IDEM_{uuid.uuid4().hex[:8]}"
        appointment_id = f"TEST_APT_{uuid.uuid4().hex[:8]}"
        
        # Create test appointment
        mock_db.appointments.insert_one({
            "appointment_id": appointment_id,
            "title": "Test Idempotence Appointment",
            "organizer_id": "test_organizer_id",
            "start_datetime": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "appointment_type": "video",
            "penalty_amount": 50,
            "penalty_currency": "EUR",
            "status": "active"
        })
        
        # Create test participant WITHOUT confirmation_email_sent flag
        mock_db.participants.insert_one({
            "participant_id": participant_id,
            "appointment_id": appointment_id,
            "email": "test_idempotence@example.com",
            "first_name": "Test",
            "last_name": "Idempotence",
            "status": "accepted_guaranteed",
            "invitation_token": f"TEST_TOKEN_{uuid.uuid4().hex[:8]}"
        })
        
        yield {
            "participant_id": participant_id,
            "appointment_id": appointment_id
        }
        
        # Cleanup
        mock_db.participants.delete_many({"participant_id": participant_id})
        mock_db.appointments.delete_many({"appointment_id": appointment_id})
    
    @pytest.mark.asyncio
    async def test_idempotence_sends_email_only_once(self, mock_db, test_participant):
        """Calling send_confirmation_email_once twice sends email only once"""
        from routers.invitations import send_confirmation_email_once
        
        participant = mock_db.participants.find_one(
            {"participant_id": test_participant["participant_id"]},
            {"_id": 0}
        )
        appointment = mock_db.appointments.find_one(
            {"appointment_id": test_participant["appointment_id"]},
            {"_id": 0}
        )
        
        email_send_count = 0
        
        async def mock_send_email(*args, **kwargs):
            nonlocal email_send_count
            email_send_count += 1
            return {"success": True, "email_id": "mock_id"}
        
        # Patch EmailService.send_email
        with patch('services.email_service.EmailService.send_email', new=mock_send_email):
            # First call should send email
            result1 = await send_confirmation_email_once(participant, appointment)
            
            # Refresh participant from DB
            participant_after_first = mock_db.participants.find_one(
                {"participant_id": test_participant["participant_id"]},
                {"_id": 0}
            )
            
            # Second call should NOT send email (idempotent)
            result2 = await send_confirmation_email_once(participant_after_first, appointment)
        
        assert result1 == True, "First call should return True (email sent)"
        assert result2 == False, "Second call should return False (already sent)"
        assert email_send_count == 1, f"Email should be sent exactly once, but was sent {email_send_count} times"
        
        # Verify flag is set in DB
        final_participant = mock_db.participants.find_one(
            {"participant_id": test_participant["participant_id"]},
            {"_id": 0}
        )
        assert final_participant.get('confirmation_email_sent') == True
        assert 'confirmation_email_sent_at' in final_participant
        
        print("✅ Idempotence: Email sent exactly once, second call returns False")
    
    @pytest.mark.asyncio
    async def test_atomic_update_prevents_duplicates(self, mock_db, test_participant):
        """MongoDB atomic update with $ne True prevents race condition duplicates"""
        # Manually set the flag to simulate another process already claimed it
        mock_db.participants.update_one(
            {"participant_id": test_participant["participant_id"]},
            {"$set": {"confirmation_email_sent": True, "confirmation_email_sent_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        from routers.invitations import send_confirmation_email_once
        
        participant = mock_db.participants.find_one(
            {"participant_id": test_participant["participant_id"]},
            {"_id": 0}
        )
        appointment = mock_db.appointments.find_one(
            {"appointment_id": test_participant["appointment_id"]},
            {"_id": 0}
        )
        
        email_send_count = 0
        
        async def mock_send_email(*args, **kwargs):
            nonlocal email_send_count
            email_send_count += 1
            return {"success": True}
        
        with patch('services.email_service.EmailService.send_email', new=mock_send_email):
            result = await send_confirmation_email_once(participant, appointment)
        
        assert result == False, "Should return False when flag already set"
        assert email_send_count == 0, "Email should NOT be sent when flag already set"
        
        print("✅ Atomic update: Prevents duplicate email when flag already set")


class TestEmailContent:
    """Test email content for video and physical appointments"""
    
    def test_video_email_has_proof_link_and_button(self):
        """Video email content: proof_link is set, 'Confirmer ma presence et rejoindre' button present"""
        from services.email_service import EmailService
        import asyncio
        
        captured_html = None
        
        async def capture_email(*args, **kwargs):
            nonlocal captured_html
            # args: to_email, subject, html_content, email_type
            if len(args) >= 3:
                captured_html = args[2]
            return {"success": True}
        
        with patch.object(EmailService, 'send_email', new=capture_email):
            asyncio.get_event_loop().run_until_complete(
                EmailService.send_acceptance_confirmation_email(
                    to_email="test@example.com",
                    to_name="Test User",
                    organizer_name="Organizer",
                    appointment_title="Video Meeting",
                    appointment_datetime=datetime.now(timezone.utc).isoformat(),
                    location=None,
                    penalty_amount=50,
                    penalty_currency="EUR",
                    cancellation_deadline_hours=24,
                    ics_link="https://example.com/ics",
                    invitation_link="https://example.com/invitation",
                    appointment_timezone="Europe/Paris",
                    proof_link="https://example.com/proof/123?token=abc",  # VIDEO has proof_link
                    appointment_type="video",
                    meeting_provider="zoom"
                )
            )
        
        assert captured_html is not None, "Email HTML should be captured"
        
        # Check for proof_link button text
        assert "Confirmer ma presence et rejoindre" in captured_html, \
            "Video email should have 'Confirmer ma presence et rejoindre' button"
        
        # Check proof_link is in the HTML
        assert "https://example.com/proof/123?token=abc" in captured_html, \
            "Video email should contain the proof_link URL"
        
        # Check ICS button is present
        assert "Ajouter a mon calendrier" in captured_html, \
            "Video email should have ICS calendar button"
        
        print("✅ Video email: proof_link present, 'Confirmer ma presence et rejoindre' button present, ICS button present")
    
    def test_physical_email_has_je_suis_arrive_button_no_proof_link(self):
        """Physical email content: 'Je suis arrive' button present, NO proof_link"""
        from services.email_service import EmailService
        import asyncio
        
        captured_html = None
        
        async def capture_email(*args, **kwargs):
            nonlocal captured_html
            if len(args) >= 3:
                captured_html = args[2]
            return {"success": True}
        
        with patch.object(EmailService, 'send_email', new=capture_email):
            asyncio.get_event_loop().run_until_complete(
                EmailService.send_acceptance_confirmation_email(
                    to_email="test@example.com",
                    to_name="Test User",
                    organizer_name="Organizer",
                    appointment_title="Physical Meeting",
                    appointment_datetime=datetime.now(timezone.utc).isoformat(),
                    location="123 Main Street, Paris",
                    penalty_amount=50,
                    penalty_currency="EUR",
                    cancellation_deadline_hours=24,
                    ics_link="https://example.com/ics",
                    invitation_link="https://example.com/invitation/token123",
                    appointment_timezone="Europe/Paris",
                    proof_link=None,  # PHYSICAL has NO proof_link
                    appointment_type="physical",
                    meeting_provider=None
                )
            )
        
        assert captured_html is not None, "Email HTML should be captured"
        
        # Check for "Je suis arrive" button text
        assert "Je suis arrive" in captured_html, \
            "Physical email should have 'Je suis arrive' button"
        
        # Check that proof_link section is NOT present (no "Confirmer ma presence et rejoindre")
        assert "Confirmer ma presence et rejoindre" not in captured_html, \
            "Physical email should NOT have video proof button"
        
        # Check ICS button is present
        assert "Ajouter a mon calendrier" in captured_html, \
            "Physical email should have ICS calendar button"
        
        # Check invitation link is used for check-in
        assert "https://example.com/invitation/token123" in captured_html, \
            "Physical email should contain invitation link for check-in"
        
        print("✅ Physical email: 'Je suis arrive' button present, NO proof_link, ICS button present")


class TestPollingEndpoint:
    """Test the guarantee-status polling endpoint"""
    
    def test_guarantee_status_endpoint_returns_correct_fields(self):
        """GET /api/invitations/{token}/guarantee-status returns correct status and is_guaranteed fields"""
        # Use the provided test token
        token = "c86cd8f1-160d-4b28-8c07-34d6b418cf5d"
        
        response = requests.get(f"{BASE_URL}/api/invitations/{token}/guarantee-status")
        
        # Should return 200 or 404 (if token doesn't exist)
        if response.status_code == 404:
            print("⚠️ Test token not found - creating test participant")
            # This is expected if the test participant doesn't exist
            pytest.skip("Test participant token not found in database")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify required fields
        assert 'status' in data, "Response should have 'status' field"
        assert 'is_guaranteed' in data, "Response should have 'is_guaranteed' field"
        assert 'participant_id' in data, "Response should have 'participant_id' field"
        
        # Verify is_guaranteed logic
        if data['status'] == 'accepted_guaranteed':
            assert data['is_guaranteed'] == True
        else:
            assert data['is_guaranteed'] == False
        
        print(f"✅ Polling endpoint returns correct fields: status={data['status']}, is_guaranteed={data['is_guaranteed']}")


class TestRespondEndpoint:
    """Test the respond endpoint still works (no regression)"""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock MongoDB database"""
        from pymongo import MongoClient
        MONGO_URL = os.environ.get('MONGO_URL')
        DB_NAME = os.environ.get('DB_NAME')
        client = MongoClient(MONGO_URL)
        return client[DB_NAME]
    
    @pytest.fixture
    def test_invitation(self, mock_db):
        """Create a test invitation for respond testing"""
        participant_id = f"TEST_RESP_{uuid.uuid4().hex[:8]}"
        appointment_id = f"TEST_APT_{uuid.uuid4().hex[:8]}"
        token = f"TEST_TOKEN_{uuid.uuid4().hex[:8]}"
        
        # Create test appointment with NO penalty (direct accept)
        mock_db.appointments.insert_one({
            "appointment_id": appointment_id,
            "title": "Test Respond Appointment",
            "organizer_id": "test_organizer_id",
            "start_datetime": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "appointment_type": "physical",
            "penalty_amount": 0,  # No penalty = direct accept
            "penalty_currency": "EUR",
            "status": "active"
        })
        
        # Create test participant with status 'invited'
        mock_db.participants.insert_one({
            "participant_id": participant_id,
            "appointment_id": appointment_id,
            "email": "test_respond@example.com",
            "first_name": "Test",
            "last_name": "Respond",
            "status": "invited",
            "invitation_token": token
        })
        
        yield {
            "participant_id": participant_id,
            "appointment_id": appointment_id,
            "token": token
        }
        
        # Cleanup
        mock_db.participants.delete_many({"participant_id": participant_id})
        mock_db.appointments.delete_many({"appointment_id": appointment_id})
    
    def test_respond_endpoint_works(self, mock_db, test_invitation):
        """POST /api/invitations/{token}/respond still works (no regression)"""
        token = test_invitation["token"]
        
        # Accept the invitation
        response = requests.post(
            f"{BASE_URL}/api/invitations/{token}/respond",
            json={"action": "accept"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('success') == True
        assert data.get('status') == 'accepted'  # Direct accept (no penalty)
        
        # Verify participant status in DB
        participant = mock_db.participants.find_one(
            {"participant_id": test_invitation["participant_id"]},
            {"_id": 0}
        )
        assert participant['status'] == 'accepted'
        
        print("✅ Respond endpoint works correctly for direct accept")


class TestCodePaths:
    """Test that all code paths call send_confirmation_email_once"""
    
    def test_webhook_path_calls_helper(self):
        """webhooks.py calls send_confirmation_email_once (line 119-121)"""
        webhooks_path = '/app/backend/routers/webhooks.py'
        with open(webhooks_path, 'r') as f:
            content = f.read()
        
        # Check import
        assert 'from routers.invitations import send_confirmation_email_once' in content, \
            "webhooks.py should import send_confirmation_email_once"
        
        # Check call
        assert 'await send_confirmation_email_once(participant, appointment)' in content, \
            "webhooks.py should call send_confirmation_email_once"
        
        print("✅ Webhook path imports and calls send_confirmation_email_once")
    
    def test_polling_path_calls_helper(self):
        """check_guarantee_status calls send_confirmation_email_once (line 490-500)"""
        invitations_path = '/app/backend/routers/invitations.py'
        with open(invitations_path, 'r') as f:
            content = f.read()
        
        # Find the check_guarantee_status function and verify it calls the helper
        # The function should call send_confirmation_email_once when status becomes accepted_guaranteed
        assert 'async def check_guarantee_status' in content, \
            "invitations.py should have check_guarantee_status function"
        
        # Check that the function calls send_confirmation_email_once
        # Look for the call within the function context
        assert 'await send_confirmation_email_once(fresh_participant, appointment)' in content, \
            "check_guarantee_status should call send_confirmation_email_once"
        
        print("✅ Polling path (check_guarantee_status) calls send_confirmation_email_once")
    
    def test_direct_accept_path_calls_helper(self):
        """respond_to_invitation calls send_confirmation_email_once for direct accept (line 410-413)"""
        invitations_path = '/app/backend/routers/invitations.py'
        with open(invitations_path, 'r') as f:
            content = f.read()
        
        # Check that respond_to_invitation calls the helper for direct accept
        assert 'await send_confirmation_email_once(updated_participant, appointment)' in content, \
            "respond_to_invitation should call send_confirmation_email_once for direct accept"
        
        print("✅ Direct accept path (respond_to_invitation) calls send_confirmation_email_once")


class TestHelperLogic:
    """Test the helper function logic in detail"""
    
    def test_helper_returns_false_if_already_sent(self):
        """Helper returns False if confirmation_email_sent is already True"""
        from routers.invitations import send_confirmation_email_once
        import asyncio
        
        # Participant with flag already set
        participant = {
            "participant_id": "test_id",
            "email": "test@example.com",
            "confirmation_email_sent": True  # Already sent
        }
        appointment = {
            "appointment_id": "apt_id",
            "title": "Test"
        }
        
        result = asyncio.get_event_loop().run_until_complete(
            send_confirmation_email_once(participant, appointment)
        )
        
        assert result == False, "Should return False when confirmation_email_sent is already True"
        print("✅ Helper returns False when confirmation_email_sent is already True")
    
    def test_helper_rollback_on_email_failure(self):
        """Helper rolls back flag on email failure so other path can retry"""
        from pymongo import MongoClient
        import asyncio
        
        MONGO_URL = os.environ.get('MONGO_URL')
        DB_NAME = os.environ.get('DB_NAME')
        client = MongoClient(MONGO_URL)
        db = client[DB_NAME]
        
        # Create test participant
        participant_id = f"TEST_ROLLBACK_{uuid.uuid4().hex[:8]}"
        appointment_id = f"TEST_APT_{uuid.uuid4().hex[:8]}"
        
        db.appointments.insert_one({
            "appointment_id": appointment_id,
            "title": "Test Rollback",
            "organizer_id": "test_org",
            "start_datetime": datetime.now(timezone.utc).isoformat(),
            "appointment_type": "video"
        })
        
        db.participants.insert_one({
            "participant_id": participant_id,
            "appointment_id": appointment_id,
            "email": "test_rollback@example.com",
            "first_name": "Test",
            "last_name": "Rollback",
            "status": "accepted_guaranteed",
            "invitation_token": f"TOKEN_{uuid.uuid4().hex[:8]}"
        })
        
        try:
            from routers.invitations import send_confirmation_email_once
            
            participant = db.participants.find_one({"participant_id": participant_id}, {"_id": 0})
            appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
            
            async def failing_send_email(*args, **kwargs):
                raise Exception("Simulated email failure")
            
            with patch('services.email_service.EmailService.send_acceptance_confirmation_email', new=failing_send_email):
                result = asyncio.get_event_loop().run_until_complete(
                    send_confirmation_email_once(participant, appointment)
                )
            
            assert result == False, "Should return False on email failure"
            
            # Check that flag was rolled back
            final_participant = db.participants.find_one({"participant_id": participant_id}, {"_id": 0})
            assert final_participant.get('confirmation_email_sent') is None or final_participant.get('confirmation_email_sent') == False, \
                "Flag should be rolled back on email failure"
            
            print("✅ Helper rolls back flag on email failure")
        
        finally:
            # Cleanup
            db.participants.delete_many({"participant_id": participant_id})
            db.appointments.delete_many({"appointment_id": appointment_id})


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
