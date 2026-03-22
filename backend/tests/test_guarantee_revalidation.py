"""
Test Guarantee Revalidation Feature
Tests for:
1. GET /api/invitations/{token} - guarantee_revalidation field
2. POST /api/invitations/{token}/reconfirm-guarantee - new Stripe session
3. GET /api/appointments/ - participants enriched with guarantee_requires_revalidation
"""
import pytest
import requests
import os
from pymongo import MongoClient
from datetime import datetime, timedelta, timezone
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'test_database')

# Test credentials from review request
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"
APPOINTMENT_ID = "e2f69471-af5a-4def-a96b-20c31605e234"
INVITATION_TOKEN = "386b6f65-ce96-4c47-bd97-b0bd4d0e9449"
PARTICIPANT_ID = "3124d763-7daf-46a1-8a99-fff8d1aca8a0"


@pytest.fixture(scope="module")
def db():
    """MongoDB connection"""
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


class TestGuaranteeRevalidationSetup:
    """Setup test data for guarantee revalidation tests"""
    
    def test_setup_participant_with_guarantee(self, db):
        """Setup: Set participant status to accepted_guaranteed and create guarantee with requires_revalidation=true"""
        # Create a test guarantee with requires_revalidation flag
        test_guarantee_id = f"TEST_guarantee_{uuid.uuid4()}"
        
        guarantee_doc = {
            "guarantee_id": test_guarantee_id,
            "participant_id": PARTICIPANT_ID,
            "appointment_id": APPOINTMENT_ID,
            "status": "completed",  # or "dev_pending" for dev mode
            "requires_revalidation": True,
            "revalidation_reason": "date_shift_48h, city_change:Paris->Lyon",
            "revalidation_flagged_at": datetime.now(timezone.utc).isoformat(),
            "capture_deadline": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Insert or update guarantee
        db.payment_guarantees.update_one(
            {"participant_id": PARTICIPANT_ID, "appointment_id": APPOINTMENT_ID},
            {"$set": guarantee_doc},
            upsert=True
        )
        
        # Update participant to accepted_guaranteed with guarantee_id
        db.participants.update_one(
            {"participant_id": PARTICIPANT_ID},
            {"$set": {
                "status": "accepted_guaranteed",
                "guarantee_id": test_guarantee_id,
                "guaranteed_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Verify setup
        participant = db.participants.find_one({"participant_id": PARTICIPANT_ID})
        assert participant is not None, "Participant not found"
        assert participant.get("status") == "accepted_guaranteed", f"Expected accepted_guaranteed, got {participant.get('status')}"
        assert participant.get("guarantee_id") == test_guarantee_id
        
        guarantee = db.payment_guarantees.find_one({"guarantee_id": test_guarantee_id})
        assert guarantee is not None, "Guarantee not found"
        assert guarantee.get("requires_revalidation") == True
        
        print(f"✓ Setup complete: participant {PARTICIPANT_ID} has guarantee {test_guarantee_id} with requires_revalidation=True")


class TestGetInvitationWithRevalidation:
    """Test GET /api/invitations/{token} returns guarantee_revalidation"""
    
    def test_invitation_returns_guarantee_revalidation_when_flagged(self, api_client, db):
        """GET /api/invitations/{token} should return guarantee_revalidation when requires_revalidation=true"""
        response = api_client.get(f"{BASE_URL}/api/invitations/{INVITATION_TOKEN}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Check guarantee_revalidation field exists and is truthy
        guarantee_revalidation = data.get("guarantee_revalidation")
        assert guarantee_revalidation is not None, "guarantee_revalidation should not be None when flagged"
        assert guarantee_revalidation.get("requires_revalidation") == True, "requires_revalidation should be True"
        assert "reason" in guarantee_revalidation, "reason field should be present"
        
        print(f"✓ GET /api/invitations/{INVITATION_TOKEN} returns guarantee_revalidation: {guarantee_revalidation}")
    
    def test_invitation_returns_null_revalidation_when_not_flagged(self, api_client, db):
        """GET /api/invitations/{token} should return guarantee_revalidation=null when no flag"""
        # First, clear the revalidation flag
        db.payment_guarantees.update_many(
            {"participant_id": PARTICIPANT_ID, "appointment_id": APPOINTMENT_ID},
            {"$set": {"requires_revalidation": False}}
        )
        
        response = api_client.get(f"{BASE_URL}/api/invitations/{INVITATION_TOKEN}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # guarantee_revalidation should be null/None when not flagged
        guarantee_revalidation = data.get("guarantee_revalidation")
        assert guarantee_revalidation is None, f"guarantee_revalidation should be None when not flagged, got {guarantee_revalidation}"
        
        print(f"✓ GET /api/invitations/{INVITATION_TOKEN} returns guarantee_revalidation=null when not flagged")
        
        # Restore the flag for subsequent tests
        db.payment_guarantees.update_many(
            {"participant_id": PARTICIPANT_ID, "appointment_id": APPOINTMENT_ID},
            {"$set": {"requires_revalidation": True, "revalidation_reason": "date_shift_48h"}}
        )


class TestReconfirmGuaranteeEndpoint:
    """Test POST /api/invitations/{token}/reconfirm-guarantee"""
    
    def test_reconfirm_guarantee_creates_new_stripe_session(self, api_client, db):
        """POST /api/invitations/{token}/reconfirm-guarantee should create new Stripe session"""
        # Ensure guarantee is flagged for revalidation
        db.payment_guarantees.update_many(
            {"participant_id": PARTICIPANT_ID, "appointment_id": APPOINTMENT_ID},
            {"$set": {"requires_revalidation": True, "revalidation_reason": "date_shift_48h"}}
        )
        
        response = api_client.post(f"{BASE_URL}/api/invitations/{INVITATION_TOKEN}/reconfirm-guarantee")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should return checkout_url and new_guarantee_id
        assert data.get("success") == True, "success should be True"
        assert "checkout_url" in data, "checkout_url should be present"
        assert "new_guarantee_id" in data, "new_guarantee_id should be present"
        assert "session_id" in data, "session_id should be present"
        
        # Verify old guarantee is marked as superseded
        old_guarantee = db.payment_guarantees.find_one({
            "participant_id": PARTICIPANT_ID,
            "appointment_id": APPOINTMENT_ID,
            "status": "superseded"
        })
        assert old_guarantee is not None, "Old guarantee should be marked as superseded"
        assert old_guarantee.get("superseded_by") == data["new_guarantee_id"]
        
        print(f"✓ POST reconfirm-guarantee created new session: {data.get('checkout_url')[:50]}...")
        print(f"✓ Old guarantee marked as superseded, new guarantee: {data.get('new_guarantee_id')}")
    
    def test_reconfirm_guarantee_returns_400_when_not_needed(self, api_client, db):
        """POST /api/invitations/{token}/reconfirm-guarantee should return 400 if no revalidation needed"""
        # Clear the revalidation flag
        db.payment_guarantees.update_many(
            {"participant_id": PARTICIPANT_ID, "appointment_id": APPOINTMENT_ID},
            {"$set": {"requires_revalidation": False}}
        )
        
        response = api_client.post(f"{BASE_URL}/api/invitations/{INVITATION_TOKEN}/reconfirm-guarantee")
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data, "Error detail should be present"
        
        print(f"✓ POST reconfirm-guarantee returns 400 when not needed: {data.get('detail')}")


class TestAppointmentsListEnrichment:
    """Test GET /api/appointments/ enriches participants with guarantee_requires_revalidation"""
    
    def test_appointments_list_includes_revalidation_flag(self, authenticated_client, db):
        """GET /api/appointments/ should include guarantee_requires_revalidation for flagged participants"""
        # Ensure guarantee is flagged
        db.payment_guarantees.update_many(
            {"participant_id": PARTICIPANT_ID, "appointment_id": APPOINTMENT_ID},
            {"$set": {
                "requires_revalidation": True,
                "revalidation_reason": "city_change:Paris->Lyon",
                "status": "completed"
            }}
        )
        
        # Ensure participant status is accepted_guaranteed
        db.participants.update_one(
            {"participant_id": PARTICIPANT_ID},
            {"$set": {"status": "accepted_guaranteed"}}
        )
        
        response = authenticated_client.get(f"{BASE_URL}/api/appointments/")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        appointments = data.get("appointments", [])
        assert len(appointments) > 0, "Should have at least one appointment"
        
        # Find our test appointment
        test_appointment = None
        for apt in appointments:
            if apt.get("appointment_id") == APPOINTMENT_ID:
                test_appointment = apt
                break
        
        assert test_appointment is not None, f"Test appointment {APPOINTMENT_ID} not found in list"
        
        # Find our test participant
        participants = test_appointment.get("participants", [])
        test_participant = None
        for p in participants:
            if p.get("participant_id") == PARTICIPANT_ID:
                test_participant = p
                break
        
        assert test_participant is not None, f"Test participant {PARTICIPANT_ID} not found"
        
        # Check enrichment
        assert test_participant.get("guarantee_requires_revalidation") == True, \
            f"guarantee_requires_revalidation should be True, got {test_participant.get('guarantee_requires_revalidation')}"
        
        print(f"✓ GET /api/appointments/ enriches participant with guarantee_requires_revalidation=True")
        print(f"  Participant: {test_participant.get('first_name')} {test_participant.get('last_name')}")
        print(f"  Revalidation reason: {test_participant.get('guarantee_revalidation_reason')}")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_guarantees(self, db):
        """Cleanup: Remove test guarantees and reset participant status"""
        # Remove test guarantees
        result = db.payment_guarantees.delete_many({
            "guarantee_id": {"$regex": "^TEST_guarantee_"}
        })
        print(f"✓ Cleaned up {result.deleted_count} test guarantees")
        
        # Reset participant status to invited
        db.participants.update_one(
            {"participant_id": PARTICIPANT_ID},
            {"$set": {
                "status": "invited",
                "guarantee_id": None,
                "guaranteed_at": None
            }}
        )
        print(f"✓ Reset participant {PARTICIPANT_ID} status to invited")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
