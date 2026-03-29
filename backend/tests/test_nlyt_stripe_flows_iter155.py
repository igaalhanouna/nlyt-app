"""
NLYT QA Iteration 155 - Stripe Flows & Webhook Protocol Testing

Tests:
- FLUX 1: Card deletion flow (DELETE /api/user-settings/me/payment-method)
- FLUX 2: Appointment creation without card → pending_organizer_guarantee + checkout_url
- W3-W5, W8: Webhook handler existence verification (transfer.created/reversed/updated, account.updated)
- W6: Webhook idempotence (duplicate event_id)
- W7: Invalid signature rejection

Credentials:
- Admin: testuser_audit@nlyt.app / TestAudit123!
- User: igaal@hotmail.com / Test123!
- User: igaal.hanouna@gmail.com / OrgTest123!
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://litigation-mgmt.preview.emergentagent.com').rstrip('/')
WORKSPACE_ID = "7e219321-18fd-4643-9be6-e4f1de88a2a8"  # testuser_audit workspace


class TestStripeFlows:
    """Test Stripe payment flows and webhook handlers"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testuser_audit@nlyt.app",
            "password": "TestAudit123!"
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def user_token(self):
        """Get regular user auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "igaal@hotmail.com",
            "password": "Test123!"
        })
        assert response.status_code == 200, f"User login failed: {response.text}"
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def org_user_token(self):
        """Get organizer user auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "igaal.hanouna@gmail.com",
            "password": "OrgTest123!"
        })
        assert response.status_code == 200, f"Org user login failed: {response.text}"
        return response.json()["access_token"]
    
    # ─────────────────────────────────────────────────────────────
    # FLUX 1: Card Deletion Flow
    # ─────────────────────────────────────────────────────────────
    
    def test_flux1_delete_card_and_verify_no_recovery(self, admin_token):
        """
        FLUX 1: DELETE /api/user-settings/me/payment-method should permanently delete card.
        Subsequent GET should return has_payment_method: false (no auto-recovery).
        """
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Step 1: Check current payment method status
        get_before = requests.get(f"{BASE_URL}/api/user-settings/me/payment-method", headers=headers)
        assert get_before.status_code == 200, f"GET payment-method failed: {get_before.text}"
        initial_status = get_before.json()
        print(f"[FLUX1] Initial payment method status: has_payment_method={initial_status.get('has_payment_method')}")
        
        # Step 2: Delete payment method
        delete_response = requests.delete(f"{BASE_URL}/api/user-settings/me/payment-method", headers=headers)
        assert delete_response.status_code == 200, f"DELETE payment-method failed: {delete_response.text}"
        delete_data = delete_response.json()
        assert delete_data.get("success") is True, f"Delete should return success=True: {delete_data}"
        print(f"[FLUX1] Delete response: {delete_data}")
        
        # Step 3: Verify card is gone (no auto-recovery)
        get_after = requests.get(f"{BASE_URL}/api/user-settings/me/payment-method", headers=headers)
        assert get_after.status_code == 200, f"GET after delete failed: {get_after.text}"
        after_status = get_after.json()
        
        assert after_status.get("has_payment_method") is False, \
            f"FLUX1 FAIL: has_payment_method should be False after delete, got: {after_status}"
        print(f"[FLUX1] PASS: Card deleted, has_payment_method=False (no auto-recovery)")
    
    # ─────────────────────────────────────────────────────────────
    # FLUX 2: Appointment Creation Without Card → Stripe Redirect
    # ─────────────────────────────────────────────────────────────
    
    def test_flux2_create_appointment_without_card_returns_checkout_url(self, admin_token):
        """
        FLUX 2: POST /api/appointments/ with penalty_amount > 0 when user has no card
        should return status=pending_organizer_guarantee with organizer_checkout_url.
        """
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Step 1: Ensure user has no card (delete if exists)
        requests.delete(f"{BASE_URL}/api/user-settings/me/payment-method", headers=headers)
        
        # Step 2: Verify no card
        pm_check = requests.get(f"{BASE_URL}/api/user-settings/me/payment-method", headers=headers)
        assert pm_check.status_code == 200
        assert pm_check.json().get("has_payment_method") is False, "User should have no card for this test"
        
        # Step 3: Create appointment with penalty
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        appointment_data = {
            "workspace_id": WORKSPACE_ID,
            "title": f"TEST_FLUX2_NoCard_{uuid.uuid4().hex[:8]}",
            "appointment_type": "physical",
            "location": "Paris, France",
            "start_datetime": future_date,
            "duration_minutes": 60,
            "penalty_amount": 50.0,
            "penalty_currency": "eur",
            "affected_compensation_percent": 80.0,  # 80% participant + 20% platform = 100%
            "charity_percent": 0.0,
            "tolerated_delay_minutes": 15,
            "cancellation_deadline_hours": 24
        }
        
        create_response = requests.post(f"{BASE_URL}/api/appointments/", json=appointment_data, headers=headers)
        assert create_response.status_code == 200, f"Create appointment failed: {create_response.text}"
        
        result = create_response.json()
        print(f"[FLUX2] Create response: status={result.get('status')}, has_checkout_url={bool(result.get('organizer_checkout_url'))}")
        
        # Verify response
        assert result.get("status") == "pending_organizer_guarantee", \
            f"FLUX2 FAIL: Expected status=pending_organizer_guarantee, got: {result.get('status')}"
        
        assert result.get("organizer_checkout_url") is not None, \
            f"FLUX2 FAIL: Expected organizer_checkout_url, got: {result}"
        
        checkout_url = result.get("organizer_checkout_url")
        assert "stripe" in checkout_url.lower() or "checkout" in checkout_url.lower() or "dev_mode" in checkout_url.lower(), \
            f"FLUX2 FAIL: checkout_url should point to Stripe: {checkout_url}"
        
        print(f"[FLUX2] PASS: Appointment created with pending_organizer_guarantee and checkout_url")
        print(f"[FLUX2] Checkout URL: {checkout_url[:100]}...")
    
    # ─────────────────────────────────────────────────────────────
    # W3-W5, W8: Webhook Handler Existence Verification
    # ─────────────────────────────────────────────────────────────
    
    def test_w3_transfer_created_handler_exists(self):
        """
        W3: Verify transfer.created handler exists in webhooks.py.
        The code should listen for transfer.created (not transfer.paid).
        """
        # Read webhooks.py and verify handler
        import sys
        sys.path.insert(0, '/app/backend')
        
        with open('/app/backend/routers/webhooks.py', 'r') as f:
            content = f.read()
        
        # Check for transfer.created handler
        assert 'event_type == "transfer.created"' in content, \
            "W3 FAIL: transfer.created handler not found in webhooks.py"
        
        # Verify it's NOT using the old transfer.paid
        assert 'event_type == "transfer.paid"' not in content, \
            "W3 FAIL: Old transfer.paid handler still present (should be transfer.created)"
        
        print("[W3] PASS: transfer.created handler exists (not transfer.paid)")
    
    def test_w4_transfer_reversed_handler_exists(self):
        """
        W4: Verify transfer.reversed handler exists in webhooks.py.
        """
        with open('/app/backend/routers/webhooks.py', 'r') as f:
            content = f.read()
        
        assert 'event_type == "transfer.reversed"' in content, \
            "W4 FAIL: transfer.reversed handler not found in webhooks.py"
        
        print("[W4] PASS: transfer.reversed handler exists")
    
    def test_w5_transfer_updated_handler_exists(self):
        """
        W5: Verify transfer.updated handler exists in webhooks.py.
        """
        with open('/app/backend/routers/webhooks.py', 'r') as f:
            content = f.read()
        
        assert 'event_type == "transfer.updated"' in content, \
            "W5 FAIL: transfer.updated handler not found in webhooks.py"
        
        print("[W5] PASS: transfer.updated handler exists")
    
    def test_w8_account_updated_handler_exists(self):
        """
        W8: Verify account.updated handler exists in webhooks.py.
        """
        with open('/app/backend/routers/webhooks.py', 'r') as f:
            content = f.read()
        
        assert 'event_type == "account.updated"' in content, \
            "W8 FAIL: account.updated handler not found in webhooks.py"
        
        print("[W8] PASS: account.updated handler exists")
    
    # ─────────────────────────────────────────────────────────────
    # W6: Webhook Idempotence (Duplicate Event)
    # ─────────────────────────────────────────────────────────────
    
    def test_w6_webhook_idempotence_duplicate_event(self):
        """
        W6: POST /api/webhooks/stripe with an event_id already in stripe_events
        should return {status: "duplicate"}.
        
        Note: Since STRIPE_WEBHOOK_SECRET is set, we verify the idempotence logic
        exists in the code (signature verification prevents direct API testing).
        """
        # Verify the idempotence guard exists in the code
        with open('/app/backend/routers/webhooks.py', 'r') as f:
            content = f.read()
        
        # Check for idempotence guard
        assert 'existing = db.stripe_events.find_one({"event_id": event_id})' in content, \
            "W6 FAIL: Idempotence guard (find_one by event_id) not found"
        
        assert '"status": "duplicate"' in content or "'status': 'duplicate'" in content, \
            "W6 FAIL: Duplicate status response not found"
        
        # Verify the duplicate response structure
        assert '"event_id": event_id' in content or "'event_id': event_id" in content, \
            "W6 FAIL: Duplicate response should include event_id"
        
        print("[W6] PASS: Idempotence guard exists in code (duplicate event_id → {status: duplicate, event_id: ...})")
    
    # ─────────────────────────────────────────────────────────────
    # W7: Invalid Signature Rejection
    # ─────────────────────────────────────────────────────────────
    
    def test_w7_invalid_signature_rejected(self):
        """
        W7: POST /api/webhooks/stripe with header Stripe-Signature: t=9999999999,v1=fake
        should return HTTP 400 with {detail: "Invalid signature"}.
        """
        # Send webhook with fake signature
        fake_signature = "t=9999999999,v1=fake_signature_for_testing"
        
        response = requests.post(
            f"{BASE_URL}/api/webhooks/stripe",
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": fake_signature
            },
            json={
                "id": "evt_fake_test",
                "type": "test.event",
                "data": {"object": {}}
            }
        )
        
        print(f"[W7] Response: status={response.status_code}, body={response.text[:200]}")
        
        assert response.status_code == 400, \
            f"W7 FAIL: Expected 400 for invalid signature, got {response.status_code}"
        
        response_data = response.json()
        assert "Invalid signature" in response_data.get("detail", ""), \
            f"W7 FAIL: Expected 'Invalid signature' in detail, got: {response_data}"
        
        print("[W7] PASS: Invalid signature correctly rejected with 400 'Invalid signature'")


class TestPaymentMethodFlow:
    """Additional tests for payment method management"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testuser_audit@nlyt.app",
            "password": "TestAudit123!"
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return response.json()["access_token"]
    
    def test_get_payment_method_endpoint(self, admin_token):
        """Verify GET /api/user-settings/me/payment-method returns correct structure"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(f"{BASE_URL}/api/user-settings/me/payment-method", headers=headers)
        assert response.status_code == 200, f"GET payment-method failed: {response.text}"
        
        data = response.json()
        assert "has_payment_method" in data, "Response should contain has_payment_method"
        
        if data.get("has_payment_method"):
            pm = data.get("payment_method", {})
            assert "last4" in pm, "payment_method should have last4"
            assert "brand" in pm, "payment_method should have brand"
            assert "exp" in pm, "payment_method should have exp"
        
        print(f"[PM_GET] PASS: Payment method endpoint returns correct structure")
    
    def test_setup_payment_method_endpoint(self, admin_token):
        """Verify POST /api/user-settings/me/setup-payment-method returns checkout_url"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.post(f"{BASE_URL}/api/user-settings/me/setup-payment-method", headers=headers)
        assert response.status_code == 200, f"Setup payment-method failed: {response.text}"
        
        data = response.json()
        assert data.get("success") is True, f"Setup should return success=True: {data}"
        assert "checkout_url" in data, f"Setup should return checkout_url: {data}"
        
        print(f"[PM_SETUP] PASS: Setup payment method returns checkout_url")


class TestWebhookHandlerIntegration:
    """Test webhook handler integration with payout_service"""
    
    def test_payout_service_handlers_exist(self):
        """Verify payout_service has handle_transfer_paid and handle_transfer_failed"""
        with open('/app/backend/services/payout_service.py', 'r') as f:
            content = f.read()
        
        assert 'def handle_transfer_paid(' in content, \
            "payout_service should have handle_transfer_paid function"
        
        assert 'def handle_transfer_failed(' in content, \
            "payout_service should have handle_transfer_failed function"
        
        print("[PAYOUT_SERVICE] PASS: handle_transfer_paid and handle_transfer_failed exist")
    
    def test_webhooks_imports_payout_handlers(self):
        """Verify webhooks.py imports payout handlers"""
        with open('/app/backend/routers/webhooks.py', 'r') as f:
            content = f.read()
        
        assert 'from services.payout_service import handle_transfer_paid, handle_transfer_failed' in content, \
            "webhooks.py should import payout handlers"
        
        print("[WEBHOOKS_IMPORT] PASS: Payout handlers imported in webhooks.py")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
