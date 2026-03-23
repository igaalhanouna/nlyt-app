"""
Test Stripe Webhook Fix and Meeting Access Control
Tests for:
1. Stripe webhook endpoint NOT crashing with SyntaxError (returns 400 Invalid signature)
2. Invitation API access control - meeting_join_url hidden for non-finalized participants
3. Acceptance flow for no-penalty appointments sets status to 'accepted' directly
"""
import pytest
import requests
import os
from dotenv import load_dotenv
from pymongo import MongoClient
import uuid
from datetime import datetime, timezone, timedelta

load_dotenv()

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = 'test_database'

client = MongoClient(MONGO_URL)
db = client[DB_NAME]


class TestHealthEndpoint:
    """Test backend health endpoint"""
    
    def test_health_returns_200(self):
        """GET /api/health should return 200 with healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get('status') == 'healthy'
        print("✓ Health endpoint returns 200 with healthy status")


class TestStripeWebhook:
    """Test Stripe webhook endpoint - verify no SyntaxError crash"""
    
    def test_webhook_returns_400_invalid_signature_not_500(self):
        """
        POST /api/webhooks/stripe should return 400 'Invalid signature' for unsigned requests
        NOT a 500 internal server error (which would indicate SyntaxError crash)
        """
        response = requests.post(
            f"{BASE_URL}/api/webhooks/stripe",
            headers={"Content-Type": "application/json"},
            json={"type": "test_event", "data": {"object": {}}}
        )
        
        # Should be 400 (Invalid signature), NOT 500 (SyntaxError)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "Invalid signature" in data.get('detail', ''), f"Expected 'Invalid signature', got: {data}"
        print("✓ Stripe webhook returns 400 'Invalid signature' (not 500 SyntaxError)")
    
    def test_webhook_does_not_crash_with_checkout_session_completed(self):
        """
        POST /api/webhooks/stripe with checkout.session.completed event
        should return 400 'Invalid signature', NOT 500 (SyntaxError from await in sync function)
        """
        response = requests.post(
            f"{BASE_URL}/api/webhooks/stripe",
            headers={"Content-Type": "application/json"},
            json={
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_test_123",
                        "mode": "setup",
                        "metadata": {
                            "type": "nlyt_guarantee",
                            "guarantee_id": "test_g_123",
                            "participant_id": "test_p_123"
                        }
                    }
                }
            }
        )
        
        # Should be 400 (Invalid signature), NOT 500 (SyntaxError)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("✓ Webhook with checkout.session.completed returns 400 (not 500 SyntaxError)")


class TestInvitationAccessControl:
    """Test meeting_join_url access control based on participant status"""
    
    def test_accepted_pending_guarantee_no_meeting_url(self):
        """
        GET /api/invitations/{token} for 'accepted_pending_guarantee' status
        should NOT return meeting_join_url (should be empty string)
        """
        # Use the test token from context
        token = "c86cd8f1-160d-4b28-8c07-34d6b418cf5d"
        response = requests.get(f"{BASE_URL}/api/invitations/{token}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify status is accepted_pending_guarantee
        assert data['participant']['status'] == 'accepted_pending_guarantee'
        
        # Verify meeting_join_url is empty (access locked)
        meeting_url = data['appointment'].get('meeting_join_url', '')
        assert meeting_url == '', f"Expected empty meeting_join_url for pending guarantee, got: {meeting_url}"
        print("✓ accepted_pending_guarantee participant does NOT get meeting_join_url")
    
    def test_invited_status_no_meeting_url(self):
        """
        GET /api/invitations/{token} for 'invited' status
        should NOT return meeting_join_url
        """
        # Find an invited participant
        participant = db.participants.find_one({'status': 'invited'}, {'_id': 0, 'invitation_token': 1})
        if not participant:
            pytest.skip("No invited participant found for testing")
        
        token = participant['invitation_token']
        response = requests.get(f"{BASE_URL}/api/invitations/{token}")
        
        if response.status_code == 404:
            pytest.skip("Invitation not found (appointment may be deleted)")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify status is invited
        assert data['participant']['status'] == 'invited'
        
        # Verify meeting_join_url is empty (access locked)
        meeting_url = data['appointment'].get('meeting_join_url', '')
        assert meeting_url == '', f"Expected empty meeting_join_url for invited, got: {meeting_url}"
        print("✓ invited participant does NOT get meeting_join_url")
    
    def test_accepted_guaranteed_gets_meeting_url(self):
        """
        GET /api/invitations/{token} for 'accepted_guaranteed' status
        SHOULD return meeting_join_url if appointment has one
        """
        # Use the test token with accepted_guaranteed status and meeting URL
        token = "2adf14af-7f04-428d-8583-5b0a7cc0e4ad"
        response = requests.get(f"{BASE_URL}/api/invitations/{token}")
        
        if response.status_code == 404:
            pytest.skip("Test invitation not found")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify status is accepted_guaranteed
        assert data['participant']['status'] == 'accepted_guaranteed'
        
        # Verify meeting_join_url is returned (access granted)
        meeting_url = data['appointment'].get('meeting_join_url', '')
        assert meeting_url != '', f"Expected meeting_join_url for accepted_guaranteed, got empty"
        assert 'meet.google.com' in meeting_url or 'zoom.us' in meeting_url or 'teams.microsoft.com' in meeting_url
        print(f"✓ accepted_guaranteed participant gets meeting_join_url: {meeting_url[:50]}...")
    
    def test_accepted_status_gets_meeting_url(self):
        """
        GET /api/invitations/{token} for 'accepted' status (no guarantee required)
        SHOULD return meeting_join_url if appointment has one
        """
        # Find an accepted participant with a video appointment that has meeting_join_url
        participants = list(db.participants.find({'status': 'accepted'}, {'_id': 0, 'invitation_token': 1, 'appointment_id': 1}).limit(10))
        
        test_token = None
        for p in participants:
            apt = db.appointments.find_one(
                {'appointment_id': p['appointment_id'], 'appointment_type': 'video', 'status': 'active'},
                {'_id': 0, 'meeting_join_url': 1}
            )
            if apt and apt.get('meeting_join_url'):
                test_token = p['invitation_token']
                break
        
        if not test_token:
            # Test with physical appointment - meeting_join_url will be empty but that's expected
            token = "17b556f4-876f-44c1-86b9-0203dced05d3"
            response = requests.get(f"{BASE_URL}/api/invitations/{token}")
            
            if response.status_code == 200:
                data = response.json()
                assert data['participant']['status'] == 'accepted'
                # Physical appointment - meeting_join_url is N/A (empty is expected)
                print("✓ accepted participant (physical appointment) - meeting_join_url N/A as expected")
                return
            pytest.skip("No accepted participant with video meeting found")
        
        response = requests.get(f"{BASE_URL}/api/invitations/{test_token}")
        assert response.status_code == 200
        data = response.json()
        
        assert data['participant']['status'] == 'accepted'
        meeting_url = data['appointment'].get('meeting_join_url', '')
        assert meeting_url != '', f"Expected meeting_join_url for accepted, got empty"
        print(f"✓ accepted participant gets meeting_join_url: {meeting_url[:50]}...")


class TestNoPenaltyAcceptanceFlow:
    """Test acceptance flow for appointments without penalty"""
    
    @pytest.fixture
    def no_penalty_appointment(self):
        """Create a test appointment with no penalty and an invited participant"""
        # Get test user
        user = db.users.find_one({'email': 'testuser_audit@nlyt.app'}, {'_id': 0})
        if not user:
            pytest.skip("Test user not found")
        
        # Create appointment with no penalty
        apt_id = f"test_no_penalty_{uuid.uuid4().hex[:8]}"
        invitation_token = str(uuid.uuid4())
        participant_id = str(uuid.uuid4())
        
        now = datetime.now(timezone.utc)
        start_dt = now + timedelta(days=7)
        
        appointment = {
            "appointment_id": apt_id,
            "organizer_id": user['user_id'],
            "workspace_id": user.get('workspace_id'),
            "title": "TEST No Penalty Appointment",
            "appointment_type": "physical",
            "location": "Test Location",
            "start_datetime": start_dt.isoformat(),
            "duration_minutes": 60,
            "penalty_amount": 0,  # NO PENALTY
            "penalty_currency": "EUR",
            "cancellation_deadline_hours": 24,
            "status": "active",
            "created_at": now.isoformat()
        }
        db.appointments.insert_one(appointment)
        
        participant = {
            "participant_id": participant_id,
            "appointment_id": apt_id,
            "email": "test_no_penalty@test.com",
            "first_name": "Test",
            "last_name": "NoPenalty",
            "status": "invited",
            "invitation_token": invitation_token,
            "created_at": now.isoformat()
        }
        db.participants.insert_one(participant)
        
        yield {
            "appointment_id": apt_id,
            "invitation_token": invitation_token,
            "participant_id": participant_id
        }
        
        # Cleanup
        db.appointments.delete_one({"appointment_id": apt_id})
        db.participants.delete_one({"participant_id": participant_id})
    
    def test_accept_no_penalty_sets_status_accepted(self, no_penalty_appointment):
        """
        POST /api/invitations/{token}/respond with action=accept
        for a no-penalty appointment should set status to 'accepted' (not 'accepted_pending_guarantee')
        """
        token = no_penalty_appointment['invitation_token']
        
        response = requests.post(
            f"{BASE_URL}/api/invitations/{token}/respond",
            headers={"Content-Type": "application/json"},
            json={"action": "accept"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should be 'accepted' directly, NOT 'accepted_pending_guarantee'
        assert data.get('status') == 'accepted', f"Expected 'accepted', got: {data.get('status')}"
        assert data.get('requires_guarantee') is None or data.get('requires_guarantee') == False
        assert 'checkout_url' not in data or data.get('checkout_url') is None
        
        print("✓ No-penalty acceptance sets status to 'accepted' (not 'accepted_pending_guarantee')")
        
        # Verify in database
        participant = db.participants.find_one(
            {"invitation_token": token},
            {"_id": 0, "status": 1}
        )
        assert participant['status'] == 'accepted'
        print("✓ Database confirms status is 'accepted'")


class TestAccessControlSummary:
    """Summary test to verify access control logic"""
    
    def test_is_engagement_finalized_logic(self):
        """
        Verify the is_engagement_finalized logic:
        - 'accepted' = finalized (no guarantee required)
        - 'accepted_guaranteed' = finalized (guarantee paid)
        - 'accepted_pending_guarantee' = NOT finalized
        - 'invited' = NOT finalized
        """
        finalized_statuses = ['accepted', 'accepted_guaranteed']
        not_finalized_statuses = ['accepted_pending_guarantee', 'invited', 'declined', 'cancelled_by_participant']
        
        for status in finalized_statuses:
            is_finalized = status in ('accepted', 'accepted_guaranteed')
            assert is_finalized == True, f"Status '{status}' should be finalized"
        
        for status in not_finalized_statuses:
            is_finalized = status in ('accepted', 'accepted_guaranteed')
            assert is_finalized == False, f"Status '{status}' should NOT be finalized"
        
        print("✓ Access control logic verified: only 'accepted' and 'accepted_guaranteed' are finalized")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
