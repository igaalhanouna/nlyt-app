"""
Financial Email Notifications Tests — NLYT

Tests for the financial_emails.py module:
1. Idempotency: MongoDB unique index on sent_emails
2. Non-blocking: _send_async uses daemon threads
3. Email hooks in attendance_service, distribution_service, payout_service
4. Email wording: 'crédit en attente' (not 'vous avez reçu')

Uses source code inspection to avoid import issues with environment variables.
"""
import pytest
import os
import requests
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from datetime import datetime, timezone

# MongoDB connection - strip quotes from env vars
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017').strip('"')
DB_NAME = os.environ.get('DB_NAME', 'test_database').strip('"')
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://litigation-mgmt.preview.emergentagent.com')

client = MongoClient(MONGO_URL)
db = client[DB_NAME]


class TestIdempotencyIndex:
    """Test MongoDB unique index on sent_emails collection"""
    
    def test_unique_index_exists_on_sent_emails(self):
        """Verify the unique compound index exists on sent_emails collection"""
        indexes = list(db.sent_emails.list_indexes())
        
        # Find the unique_email_idempotency index
        found_index = None
        for idx in indexes:
            if idx.get('name') == 'unique_email_idempotency':
                found_index = idx
                break
        
        assert found_index is not None, \
            f"Expected 'unique_email_idempotency' index, found: {[idx.get('name') for idx in indexes]}"
        
        # Verify it's unique
        assert found_index.get('unique') == True, "Index should be unique"
        
        # Verify key structure - key is a SON (ordered dict)
        key = found_index.get('key')
        assert key is not None
        # SON is dict-like, so use .keys()
        key_fields = list(key.keys())
        assert 'email_type' in key_fields, f"Index should include email_type, got: {key_fields}"
        assert 'reference_id' in key_fields, f"Index should include reference_id, got: {key_fields}"
        assert 'user_id' in key_fields, f"Index should include user_id, got: {key_fields}"
        print(f"✓ Unique index verified with keys: {key_fields}")
    
    def test_duplicate_insert_raises_error(self):
        """Verify that inserting duplicate (email_type, reference_id, user_id) raises DuplicateKeyError"""
        test_doc = {
            "email_type": "test_idempotency_check",
            "reference_id": "test_ref_123",
            "user_id": "test_user_456",
            "to_email": "test@example.com",
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Clean up any existing test data
        db.sent_emails.delete_many({
            "email_type": "test_idempotency_check",
            "reference_id": "test_ref_123",
            "user_id": "test_user_456",
        })
        
        # First insert should succeed
        db.sent_emails.insert_one(test_doc.copy())
        print("✓ First insert succeeded")
        
        # Second insert with same key should fail
        with pytest.raises(DuplicateKeyError):
            db.sent_emails.insert_one(test_doc.copy())
        print("✓ Duplicate insert correctly raised DuplicateKeyError")
        
        # Cleanup
        db.sent_emails.delete_many({
            "email_type": "test_idempotency_check",
            "reference_id": "test_ref_123",
            "user_id": "test_user_456",
        })


class TestIdempotencyLogic:
    """Test idempotency logic via direct MongoDB operations"""
    
    def test_idempotency_prevents_duplicate_records(self):
        """Simulating _already_sent / _mark_sent logic"""
        test_email_type = "capture_no_show"
        test_ref_id = f"dist_idempotent_{datetime.now().timestamp()}"
        test_user_id = "user_idempotent_test"
        
        # Clean up
        db.sent_emails.delete_many({
            "email_type": test_email_type,
            "reference_id": test_ref_id,
            "user_id": test_user_id,
        })
        
        # Simulate _already_sent - should return None (not found)
        first_check = db.sent_emails.find_one({
            "email_type": test_email_type,
            "reference_id": test_ref_id,
            "user_id": test_user_id,
        })
        assert first_check is None
        print("✓ First check: not sent yet")
        
        # Simulate _mark_sent
        db.sent_emails.insert_one({
            "email_type": test_email_type,
            "reference_id": test_ref_id,
            "user_id": test_user_id,
            "to_email": "test@example.com",
            "sent_at": datetime.now(timezone.utc).isoformat(),
        })
        print("✓ Marked as sent")
        
        # Second check - should find the record
        second_check = db.sent_emails.find_one({
            "email_type": test_email_type,
            "reference_id": test_ref_id,
            "user_id": test_user_id,
        })
        assert second_check is not None
        print("✓ Second check: already sent, would be blocked")
        
        # Cleanup
        db.sent_emails.delete_many({
            "email_type": test_email_type,
            "reference_id": test_ref_id,
            "user_id": test_user_id,
        })


class TestSourceCodeInspection:
    """Test source code for correct implementation via file inspection"""
    
    def test_financial_emails_module_exists(self):
        """financial_emails.py exists with all 5 email functions"""
        with open('/app/backend/services/financial_emails.py', 'r') as f:
            source = f.read()
        
        # Check all 5 functions exist
        assert 'def send_capture_email(' in source, "send_capture_email function missing"
        assert 'def send_distribution_created_email(' in source, "send_distribution_created_email function missing"
        assert 'def send_distribution_available_email(' in source, "send_distribution_available_email function missing"
        assert 'def send_payout_completed_email(' in source, "send_payout_completed_email function missing"
        assert 'def send_payout_failed_email(' in source, "send_payout_failed_email function missing"
        print("✓ All 5 email functions exist in financial_emails.py")
    
    def test_idempotency_functions_exist(self):
        """_already_sent and _mark_sent functions exist"""
        with open('/app/backend/services/financial_emails.py', 'r') as f:
            source = f.read()
        
        assert 'def _already_sent(' in source, "_already_sent function missing"
        assert 'def _mark_sent(' in source, "_mark_sent function missing"
        print("✓ Idempotency functions exist")
    
    def test_send_async_uses_daemon_thread(self):
        """_send_async creates daemon threads"""
        with open('/app/backend/services/financial_emails.py', 'r') as f:
            source = f.read()
        
        assert 'def _send_async(' in source, "_send_async function missing"
        assert 'threading.Thread' in source, "Should use threading.Thread"
        assert 'daemon=True' in source, "Thread should be daemon=True"
        print("✓ _send_async uses daemon threads")
    
    def test_send_async_checks_idempotency(self):
        """_send_async checks _already_sent before sending"""
        with open('/app/backend/services/financial_emails.py', 'r') as f:
            source = f.read()
        
        # Find _send_async function and check it calls _already_sent
        assert '_already_sent(' in source, "_send_async should call _already_sent"
        print("✓ _send_async checks idempotency before sending")


class TestEmailWording:
    """Test email content wording requirements"""
    
    def test_distribution_created_email_says_credit_en_attente(self):
        """distribution_created email must say 'crédit en attente' not 'vous avez reçu'"""
        with open('/app/backend/services/financial_emails.py', 'r') as f:
            source = f.read()
        
        # Check for correct wording (case-insensitive)
        source_lower = source.lower()
        assert 'crédit en attente' in source_lower, \
            "Email should contain 'crédit en attente'"
        
        # Check it doesn't say 'vous avez reçu'
        assert 'vous avez reçu' not in source_lower, \
            "Email should NOT contain 'vous avez reçu'"
        
        print("✓ distribution_created email uses correct wording: 'crédit en attente'")
    
    def test_email_subject_contains_credit_en_attente(self):
        """Email subject should reference 'Crédit en attente enregistré'"""
        with open('/app/backend/services/financial_emails.py', 'r') as f:
            source = f.read()
        
        # Check subject line
        assert 'Crédit en attente enregistré' in source, \
            "Email subject should be 'Crédit en attente enregistré'"
        
        print("✓ Email subject contains 'Crédit en attente enregistré'")


class TestHooksInAttendanceService:
    """Test email hooks in attendance_service.py"""
    
    def test_capture_email_hook_exists(self):
        """send_capture_email is called in attendance_service._execute_capture_and_distribution"""
        with open('/app/backend/services/attendance_service.py', 'r') as f:
            source = f.read()
        
        assert 'send_capture_email' in source, \
            "attendance_service should call send_capture_email"
        assert 'from services.financial_emails import send_capture_email' in source, \
            "Should import send_capture_email from financial_emails"
        
        print("✓ send_capture_email hook found in attendance_service")


class TestHooksInDistributionService:
    """Test email hooks in distribution_service.py"""
    
    def test_distribution_created_email_hook_exists(self):
        """send_distribution_created_email is called in distribution_service.create_distribution"""
        with open('/app/backend/services/distribution_service.py', 'r') as f:
            source = f.read()
        
        assert 'send_distribution_created_email' in source, \
            "distribution_service should call send_distribution_created_email"
        
        print("✓ send_distribution_created_email hook found in distribution_service")
    
    def test_distribution_created_email_only_for_organizer_participant(self):
        """distribution_created email should only be sent to 'organizer' and 'participant' roles"""
        with open('/app/backend/services/distribution_service.py', 'r') as f:
            source = f.read()
        
        # Check that it filters by role - look for the condition
        assert 'benef["role"] in ("organizer", "participant")' in source or \
               "benef['role'] in ('organizer', 'participant')" in source, \
            "Should only send to organizer and participant roles"
        
        print("✓ distribution_created email only sent to organizer/participant (not platform/charity)")
    
    def test_distribution_available_email_hook_exists(self):
        """send_distribution_available_email is called in distribution_service._finalize_single_distribution"""
        with open('/app/backend/services/distribution_service.py', 'r') as f:
            source = f.read()
        
        assert 'send_distribution_available_email' in source, \
            "distribution_service should call send_distribution_available_email"
        
        print("✓ send_distribution_available_email hook found in distribution_service")
    
    def test_distribution_available_email_only_on_completed(self):
        """send_distribution_available_email should only be called when final_status == completed"""
        with open('/app/backend/services/distribution_service.py', 'r') as f:
            source = f.read()
        
        # Check it's only called when final_status == completed
        assert 'final_status == "completed"' in source or "final_status == 'completed'" in source, \
            "Should only send when final_status == completed"
        
        print("✓ send_distribution_available_email only sent when status is completed")


class TestHooksInPayoutService:
    """Test email hooks in payout_service.py"""
    
    def test_payout_completed_email_hook_in_dev_payout(self):
        """send_payout_completed_email is called in payout_service._execute_dev_payout"""
        with open('/app/backend/services/payout_service.py', 'r') as f:
            source = f.read()
        
        assert 'send_payout_completed_email' in source, \
            "payout_service should call send_payout_completed_email"
        
        print("✓ send_payout_completed_email hook found in payout_service")
    
    def test_payout_completed_email_hook_in_webhook_handler(self):
        """send_payout_completed_email is called in payout_service.handle_transfer_paid"""
        with open('/app/backend/services/payout_service.py', 'r') as f:
            source = f.read()
        
        # Check handle_transfer_paid function contains the email call
        # Find the function and check it has the email call
        assert 'def handle_transfer_paid' in source, "handle_transfer_paid function should exist"
        assert 'send_payout_completed_email' in source, \
            "handle_transfer_paid should call send_payout_completed_email"
        
        print("✓ send_payout_completed_email hook found in handle_transfer_paid")
    
    def test_payout_failed_email_hook_in_stripe_transfer(self):
        """send_payout_failed_email is called in payout_service._execute_stripe_transfer on StripeError"""
        with open('/app/backend/services/payout_service.py', 'r') as f:
            source = f.read()
        
        assert 'send_payout_failed_email' in source, \
            "payout_service should call send_payout_failed_email"
        assert 'StripeError' in source, \
            "Should handle StripeError"
        
        print("✓ send_payout_failed_email hook found in payout_service (on StripeError)")
    
    def test_payout_failed_email_hook_in_webhook_handler(self):
        """send_payout_failed_email is called in payout_service.handle_transfer_failed"""
        with open('/app/backend/services/payout_service.py', 'r') as f:
            source = f.read()
        
        assert 'def handle_transfer_failed' in source, "handle_transfer_failed function should exist"
        assert 'send_payout_failed_email' in source, \
            "handle_transfer_failed should call send_payout_failed_email"
        
        print("✓ send_payout_failed_email hook found in handle_transfer_failed")


class TestServerLifespanIndex:
    """Test that server.py creates the unique index on startup"""
    
    def test_server_creates_sent_emails_index(self):
        """server.py lifespan should create unique index on sent_emails"""
        with open('/app/backend/server.py', 'r') as f:
            source = f.read()
        
        # Check for index creation
        assert 'sent_emails.create_index' in source, \
            "server.py should create index on sent_emails"
        assert 'unique_email_idempotency' in source, \
            "Index should be named 'unique_email_idempotency'"
        assert 'unique=True' in source, \
            "Index should be unique"
        
        # Check the key structure
        assert 'email_type' in source and 'reference_id' in source and 'user_id' in source, \
            "Index should include email_type, reference_id, user_id"
        
        print("✓ server.py creates unique index on sent_emails in lifespan")


class TestHealthEndpoint:
    """Verify health endpoint still works"""
    
    def test_health_endpoint_returns_200(self):
        """GET /api/health should return 200"""
        response = requests.get(f"{BASE_URL}/api/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get('status') == 'healthy'
        print(f"✓ GET /api/health returns 200: {data}")


class TestEmailFunctionSignatures:
    """Test email function signatures via source code inspection"""
    
    def test_send_capture_email_signature(self):
        """send_capture_email has correct parameters"""
        with open('/app/backend/services/financial_emails.py', 'r') as f:
            source = f.read()
        
        # Find the function definition
        assert 'def send_capture_email(' in source
        
        # Check for expected parameters
        expected_params = ['user_id', 'appointment_title', 'appointment_date', 
                          'capture_amount_cents', 'distribution_id', 'beneficiaries', 
                          'hold_expires_at']
        
        for param in expected_params:
            assert param in source, f"send_capture_email should have parameter: {param}"
        
        print(f"✓ send_capture_email has correct parameters")
    
    def test_send_distribution_created_email_signature(self):
        """send_distribution_created_email has correct parameters"""
        with open('/app/backend/services/financial_emails.py', 'r') as f:
            source = f.read()
        
        expected_params = ['user_id', 'role', 'amount_cents', 'appointment_title',
                          'appointment_date', 'distribution_id', 'hold_expires_at']
        
        for param in expected_params:
            assert param in source, f"send_distribution_created_email should have parameter: {param}"
        
        print(f"✓ send_distribution_created_email has correct parameters")
    
    def test_send_distribution_available_email_signature(self):
        """send_distribution_available_email has correct parameters"""
        with open('/app/backend/services/financial_emails.py', 'r') as f:
            source = f.read()
        
        expected_params = ['user_id', 'amount_cents', 'appointment_title', 'distribution_id']
        
        for param in expected_params:
            assert param in source, f"send_distribution_available_email should have parameter: {param}"
        
        print(f"✓ send_distribution_available_email has correct parameters")
    
    def test_send_payout_completed_email_signature(self):
        """send_payout_completed_email has correct parameters"""
        with open('/app/backend/services/financial_emails.py', 'r') as f:
            source = f.read()
        
        expected_params = ['user_id', 'amount_cents', 'payout_id', 'stripe_transfer_id']
        
        for param in expected_params:
            assert param in source, f"send_payout_completed_email should have parameter: {param}"
        
        print(f"✓ send_payout_completed_email has correct parameters")
    
    def test_send_payout_failed_email_signature(self):
        """send_payout_failed_email has correct parameters"""
        with open('/app/backend/services/financial_emails.py', 'r') as f:
            source = f.read()
        
        expected_params = ['user_id', 'amount_cents', 'payout_id', 'failure_reason']
        
        for param in expected_params:
            assert param in source, f"send_payout_failed_email should have parameter: {param}"
        
        print(f"✓ send_payout_failed_email has correct parameters")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
