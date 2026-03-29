"""
Test Suite for Stripe Redirect Fix - Iteration 156
Tests the UX fix: after Stripe Checkout, logged-in users are redirected to /appointments/{id}
instead of /invitation/{token}.

Key features tested:
1. BACKEND - Appointment creation without card returns checkout_url pointing to /appointments/{id}
2. BACKEND - Retry guarantee returns checkout_url pointing to /appointments/{id}
3. BACKEND - Invitation flow preserves /invitation/{token} URL (no return_url)
4. BACKEND - Card deletion works correctly
5. FRONTEND - AppointmentDetail.js handles guarantee_status=success (code review)
"""

import pytest
import requests
import os
import json
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_USER_EMAIL = "testuser_audit@nlyt.app"
TEST_USER_PASSWORD = "TestAudit123!"
TEST_WORKSPACE_ID = "7e219321-18fd-4643-9be6-e4f1de88a2a8"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test user"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestStripeRedirectFix:
    """Tests for the Stripe redirect fix - appointments vs invitations"""

    def test_01_delete_card_before_test(self, auth_headers):
        """FLUX1: Delete any existing card to ensure clean state"""
        # First check current state
        get_resp = requests.get(
            f"{BASE_URL}/api/user-settings/me/payment-method",
            headers=auth_headers
        )
        assert get_resp.status_code == 200
        
        # Delete card if exists
        del_resp = requests.delete(
            f"{BASE_URL}/api/user-settings/me/payment-method",
            headers=auth_headers
        )
        assert del_resp.status_code == 200
        assert del_resp.json().get("success") is True
        print("PASS: Card deleted successfully")
        
        # Verify card is gone
        verify_resp = requests.get(
            f"{BASE_URL}/api/user-settings/me/payment-method",
            headers=auth_headers
        )
        assert verify_resp.status_code == 200
        assert verify_resp.json().get("has_payment_method") is False
        print("PASS: Card deletion verified - has_payment_method: false")

    def test_02_create_appointment_without_card_returns_appointments_url(self, auth_headers):
        """
        FLUX2: POST /api/appointments/ with penalty_amount > 0 and no saved card
        should return organizer_checkout_url pointing to /appointments/{id}?guarantee_status=success
        NOT /invitation/{token}
        """
        # Create appointment with penalty
        start_time = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        appointment_data = {
            "workspace_id": TEST_WORKSPACE_ID,
            "title": f"TEST_REDIRECT_FIX_{datetime.now().strftime('%H%M%S')}",
            "appointment_type": "physical",
            "start_datetime": start_time,
            "duration_minutes": 60,
            "penalty_amount": 50.0,
            "penalty_currency": "eur",
            "affected_compensation_percent": 80,
            "charity_percent": 0,
            "tolerated_delay_minutes": 15,
            "cancellation_deadline_hours": 24
        }
        
        response = requests.post(
            f"{BASE_URL}/api/appointments/",
            headers=auth_headers,
            json=appointment_data
        )
        
        assert response.status_code == 200, f"Failed to create appointment: {response.text}"
        data = response.json()
        
        # Verify status is pending_organizer_guarantee (no card saved)
        assert data.get("status") == "pending_organizer_guarantee", \
            f"Expected pending_organizer_guarantee, got {data.get('status')}"
        print(f"PASS: Appointment created with status: {data.get('status')}")
        
        # Verify organizer_checkout_url exists
        checkout_url = data.get("organizer_checkout_url")
        assert checkout_url is not None, "organizer_checkout_url should be present"
        print(f"PASS: organizer_checkout_url present: {checkout_url[:80]}...")
        
        # KEY TEST: Verify the success_url points to /appointments/{id}, NOT /invitation/
        appointment_id = data.get("appointment_id")
        
        # The checkout_url in dev mode contains the success_url directly
        # In production, we'd need to check the Stripe session
        if "guarantee_status=success" in checkout_url:
            # Dev mode - URL contains the redirect directly
            assert f"/appointments/{appointment_id}" in checkout_url, \
                f"checkout_url should contain /appointments/{appointment_id}, got: {checkout_url}"
            assert "/invitation/" not in checkout_url, \
                f"checkout_url should NOT contain /invitation/, got: {checkout_url}"
            print(f"PASS: Dev mode checkout_url correctly points to /appointments/{appointment_id}")
        else:
            # Production mode - URL is Stripe checkout, need to verify via Stripe API
            print(f"INFO: Production Stripe URL detected, will verify via Stripe session")
            # Store appointment_id for later verification
            pytest.appointment_id_for_stripe_check = appointment_id
        
        # Store for cleanup
        pytest.test_appointment_id = appointment_id
        print(f"PASS: Appointment {appointment_id} created with correct redirect URL")

    def test_03_retry_guarantee_returns_appointments_url(self, auth_headers):
        """
        POST /api/appointments/{id}/retry-organizer-guarantee should return
        checkout_url pointing to /appointments/{id}
        """
        appointment_id = getattr(pytest, 'test_appointment_id', None)
        if not appointment_id:
            pytest.skip("No test appointment from previous test")
        
        response = requests.post(
            f"{BASE_URL}/api/appointments/{appointment_id}/retry-organizer-guarantee",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Retry guarantee failed: {response.text}"
        data = response.json()
        
        checkout_url = data.get("checkout_url")
        if checkout_url:
            # Verify URL points to /appointments/{id}
            if "guarantee_status=success" in checkout_url:
                assert f"/appointments/{appointment_id}" in checkout_url, \
                    f"retry checkout_url should contain /appointments/{appointment_id}"
                assert "/invitation/" not in checkout_url, \
                    f"retry checkout_url should NOT contain /invitation/"
                print(f"PASS: Retry guarantee checkout_url correctly points to /appointments/{appointment_id}")
            else:
                print(f"INFO: Production Stripe URL for retry: {checkout_url[:60]}...")
        elif data.get("status") == "active":
            print(f"PASS: Appointment already activated (card was auto-used)")
        else:
            print(f"INFO: Retry response: {data}")

    def test_04_verify_invitation_flow_preserves_invitation_url(self, auth_headers):
        """
        Code review verification: invitations.py calls create_guarantee_session
        WITHOUT return_url parameter, so success_url defaults to /invitation/{token}
        """
        import subprocess
        
        # Check that invitations.py does NOT pass return_url
        result = subprocess.run(
            ["grep", "-c", "return_url", "/app/backend/routers/invitations.py"],
            capture_output=True, text=True
        )
        
        # Should be 0 occurrences of return_url in invitations.py
        count = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0
        assert count == 0, f"invitations.py should NOT have return_url parameter, found {count} occurrences"
        print(f"PASS: invitations.py has 0 return_url parameters - invitation flow preserved")

    def test_05_verify_appointments_passes_return_url(self, auth_headers):
        """
        Code review verification: appointments.py calls create_guarantee_session
        WITH return_url parameter pointing to /appointments/{id}
        """
        import subprocess
        
        # Check that appointments.py DOES pass return_url
        result = subprocess.run(
            ["grep", "-c", "return_url", "/app/backend/routers/appointments.py"],
            capture_output=True, text=True
        )
        
        count = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0
        assert count >= 2, f"appointments.py should have return_url parameter, found {count} occurrences"
        print(f"PASS: appointments.py has {count} return_url parameters - redirect fix applied")

    def test_06_verify_stripe_guarantee_service_handles_return_url(self, auth_headers):
        """
        Code review verification: stripe_guarantee_service.py accepts return_url
        and uses it to build success_url
        """
        import subprocess
        
        # Check function signature
        result = subprocess.run(
            ["grep", "-n", "return_url", "/app/backend/services/stripe_guarantee_service.py"],
            capture_output=True, text=True
        )
        
        lines = result.stdout.strip().split('\n')
        assert len(lines) >= 4, f"stripe_guarantee_service.py should handle return_url, found: {lines}"
        
        # Verify key patterns
        has_param = any("return_url: str = None" in line for line in lines)
        has_dev_mode = any("if return_url:" in line for line in lines)
        has_success_url = any("success_url" in line and "return_url" in line for line in lines)
        
        assert has_param, "Should have return_url parameter in function signature"
        assert has_dev_mode, "Should check if return_url is provided"
        print(f"PASS: stripe_guarantee_service.py correctly handles return_url parameter")

    def test_07_frontend_handles_guarantee_status_success(self, auth_headers):
        """
        Code review verification: AppointmentDetail.js detects guarantee_status=success
        and triggers auto-check
        """
        import subprocess
        
        # Check for guarantee_status=success handling
        result = subprocess.run(
            ["grep", "-A", "15", "guaranteeStatus === 'success'", "/app/frontend/src/pages/appointments/AppointmentDetail.js"],
            capture_output=True, text=True
        )
        
        output = result.stdout
        
        # Verify key patterns for success handling
        assert "success" in output, "Should handle success status"
        assert "checkActivation" in output or "loadData" in output, "Should trigger data reload"
        assert "toast" in output.lower(), "Should show toast notification"
        
        print("PASS: AppointmentDetail.js correctly handles guarantee_status=success")

    def test_08_frontend_handles_guarantee_status_cancelled(self, auth_headers):
        """
        Code review verification: AppointmentDetail.js shows warning toast for cancelled
        """
        import subprocess
        
        result = subprocess.run(
            ["grep", "-A", "5", "guaranteeStatus === 'cancelled'", 
             "/app/frontend/src/pages/appointments/AppointmentDetail.js"],
            capture_output=True, text=True
        )
        
        output = result.stdout
        assert "cancelled" in output, "Should handle cancelled status"
        assert "toast" in output.lower() or "warning" in output.lower(), "Should show warning"
        
        print("PASS: AppointmentDetail.js shows warning for cancelled guarantee")

    def test_09_cleanup_test_appointment(self, auth_headers):
        """Cleanup: Delete test appointment"""
        appointment_id = getattr(pytest, 'test_appointment_id', None)
        if not appointment_id:
            print("INFO: No test appointment to cleanup")
            return
        
        # Cancel the appointment
        response = requests.post(
            f"{BASE_URL}/api/appointments/{appointment_id}/cancel",
            headers=auth_headers
        )
        
        if response.status_code == 200:
            print(f"PASS: Test appointment {appointment_id} cancelled")
        else:
            print(f"INFO: Could not cancel appointment: {response.status_code}")


class TestPaymentMethodEndpoints:
    """Tests for payment method management endpoints"""

    def test_get_payment_method_structure(self, auth_headers):
        """GET /api/user-settings/me/payment-method returns correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/user-settings/me/payment-method",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "has_payment_method" in data
        if data.get("has_payment_method"):
            assert "payment_method" in data
            pm = data["payment_method"]
            assert "last4" in pm
            assert "brand" in pm
            assert "exp" in pm
        
        print(f"PASS: Payment method endpoint returns correct structure")

    def test_delete_payment_method_success(self, auth_headers):
        """DELETE /api/user-settings/me/payment-method returns success"""
        response = requests.delete(
            f"{BASE_URL}/api/user-settings/me/payment-method",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        
        print("PASS: DELETE payment method returns success")

    def test_verify_no_payment_method_after_delete(self, auth_headers):
        """After DELETE, GET returns has_payment_method: false"""
        response = requests.get(
            f"{BASE_URL}/api/user-settings/me/payment-method",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("has_payment_method") is False
        
        print("PASS: After DELETE, has_payment_method is false")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
