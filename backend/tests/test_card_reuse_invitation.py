"""
Test Card Reuse During Invitation Acceptance
Tests the NEW feature: when a user has a saved card (default_payment_method_id),
they should NOT be redirected to Stripe Checkout for each new invitation.
The system must reuse the existing card.

Endpoints tested:
- POST /api/invitations/{token}/respond (authenticated users)
- POST /api/invitations/{token}/login-accept (login + accept)
- create_guarantee_with_saved_card() method

Test user WITH saved card: testuser_audit@nlyt.app / Test123!
  - default_payment_method_id: pm_dev_5400be0a
  - stripe_customer_id: cus_UCDTE42s6v8l37
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://check-in-flow-1.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_USER_WITH_CARD = {
    "email": "testuser_audit@nlyt.app",
    "password": "Test123!",
    "user_id": "d13498f9-9c0d-47d4-b48f-9e327e866127",
    "default_payment_method_id": "pm_dev_5400be0a",
    "stripe_customer_id": "cus_UCDTE42s6v8l37"
}


class TestHealthAndRegression:
    """Basic health checks and regression tests"""
    
    def test_health_check(self):
        """Backend health check passes"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✅ Health check passes")
    
    def test_login_test_user_with_card(self):
        """Login with test user that has saved card"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_WITH_CARD["email"],
            "password": TEST_USER_WITH_CARD["password"]
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data.get("user", {}).get("email") == TEST_USER_WITH_CARD["email"]
        print(f"✅ Login successful for {TEST_USER_WITH_CARD['email']}")
    
    def test_get_payment_method_regression(self):
        """GET /api/user-settings/me/payment-method still returns card correctly (regression)"""
        # Login first
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_WITH_CARD["email"],
            "password": TEST_USER_WITH_CARD["password"]
        })
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        
        # Get payment method
        response = requests.get(
            f"{BASE_URL}/api/user-settings/me/payment-method",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("has_payment_method") == True
        assert "payment_method" in data
        pm = data["payment_method"]
        # API returns last4, brand, exp, consent - not payment_method_id
        assert pm.get("last4") is not None
        assert pm.get("brand") is not None
        print(f"✅ GET /me/payment-method returns card: {pm.get('brand')} ****{pm.get('last4')}")
    
    def test_wallet_milestones_regression(self):
        """GET /api/wallet/milestones still works (regression)"""
        # Login first
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_WITH_CARD["email"],
            "password": TEST_USER_WITH_CARD["password"]
        })
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        
        response = requests.get(
            f"{BASE_URL}/api/wallet/milestones",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "attended_count" in data
        assert "organized_count" in data
        print(f"✅ GET /wallet/milestones works: attended={data.get('attended_count')}, organized={data.get('organized_count')}")


class TestCardReuseLoginAcceptEndpoint:
    """Test POST /api/invitations/{token}/login-accept with card reuse"""
    
    @pytest.fixture
    def organizer_token(self):
        """Get auth token for test user (will be organizer)"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_WITH_CARD["email"],
            "password": TEST_USER_WITH_CARD["password"]
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Login failed")
    
    @pytest.fixture
    def create_appointment_for_test_user(self, organizer_token):
        """Create appointment where test user with card is participant"""
        future_date = (datetime.now(timezone.utc) + timedelta(days=8)).isoformat()
        
        # Get workspace
        ws_resp = requests.get(
            f"{BASE_URL}/api/workspaces/",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        if ws_resp.status_code != 200:
            pytest.skip("No workspace found")
        ws_data = ws_resp.json()
        workspaces = ws_data.get("workspaces", []) if isinstance(ws_data, dict) else ws_data
        if not workspaces:
            pytest.skip("No workspace found")
        workspace_id = workspaces[0]["workspace_id"]
        
        # Create appointment with a different email as participant
        # (organizer can't be participant in their own appointment for this test)
        test_participant_email = f"test_cardreuse_{uuid.uuid4().hex[:8]}@example.com"
        apt_data = {
            "title": f"TEST_LoginAccept_{uuid.uuid4().hex[:8]}",
            "appointment_type": "physical",
            "location": "Test Location",
            "start_datetime": future_date,
            "duration_minutes": 60,
            "penalty_amount": 30.0,
            "penalty_currency": "EUR",
            "cancellation_deadline_hours": 24,
            "workspace_id": workspace_id,
            "affected_compensation_percent": 80.0,
            "charity_percent": 0.0,
            "platform_commission_percent": 20.0,
            "participants": [{
                "email": test_participant_email,
                "first_name": "Card",
                "last_name": "Test"
            }]
        }
        
        apt_resp = requests.post(
            f"{BASE_URL}/api/appointments/",
            headers={"Authorization": f"Bearer {organizer_token}", "Content-Type": "application/json"},
            json=apt_data
        )
        
        if apt_resp.status_code not in [200, 201]:
            print(f"Failed to create appointment: {apt_resp.text}")
            pytest.skip("Failed to create test appointment")
        
        apt = apt_resp.json()
        appointment_id = apt["appointment_id"]
        
        # Get participant's invitation token from appointments list
        apt_list = requests.get(
            f"{BASE_URL}/api/appointments/?workspace_id={workspace_id}&time_filter=upcoming",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        apt_list_data = apt_list.json()
        
        invitation_token = None
        for a in apt_list_data.get("items", []):
            if a.get("appointment_id") == appointment_id:
                for p in a.get("participants", []):
                    if p.get("email") == test_participant_email:
                        invitation_token = p.get("invitation_token")
                        break
                break
        
        if not invitation_token:
            pytest.skip("No invitation token found")
        
        yield {
            "appointment_id": appointment_id,
            "invitation_token": invitation_token,
            "participant_email": test_participant_email
        }
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/appointments/{appointment_id}",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
    
    def test_user_without_card_gets_stripe_redirect(self, create_appointment_for_test_user):
        """
        User WITHOUT saved card gets requires_guarantee=true, checkout_url (normal Stripe flow)
        """
        test_data = create_appointment_for_test_user
        token = test_data["invitation_token"]
        
        # Call respond endpoint (no auth - guest user without card)
        response = requests.post(
            f"{BASE_URL}/api/invitations/{token}/respond",
            headers={"Content-Type": "application/json"},
            json={"action": "accept"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify Stripe redirect is required (no saved card)
        assert data.get("success") == True
        assert data.get("requires_guarantee") == True, f"Expected requires_guarantee=True, got {data}"
        assert "checkout_url" in data, "Should have checkout_url for user without saved card"
        assert data.get("status") == "accepted_pending_guarantee"
        
        print(f"✅ User without card correctly gets Stripe redirect")
        print(f"   requires_guarantee={data.get('requires_guarantee')}, has checkout_url={bool(data.get('checkout_url'))}")


class TestCardReuseWithExistingInvitation:
    """Test card reuse with existing invitation for user with saved card"""
    
    def test_login_accept_with_saved_card_reuses_card(self):
        """
        POST /api/invitations/{token}/login-accept: user WITH saved card gets reused_card=true
        
        This test uses an existing invitation in the database for testuser_audit@nlyt.app
        """
        # First, find an existing invitation for the test user in 'invited' status
        # We'll create one if needed
        
        # Login as organizer to create appointment
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_WITH_CARD["email"],
            "password": TEST_USER_WITH_CARD["password"]
        })
        if login_resp.status_code != 200:
            pytest.skip("Login failed")
        organizer_token = login_resp.json()["access_token"]
        
        # Get workspace
        ws_resp = requests.get(
            f"{BASE_URL}/api/workspaces/",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        ws_data = ws_resp.json()
        workspaces = ws_data.get("workspaces", [])
        if not workspaces:
            pytest.skip("No workspace found")
        workspace_id = workspaces[0]["workspace_id"]
        
        # Create appointment with test user as participant (different from organizer)
        # We need to use a different organizer, but since we only have one test user,
        # we'll create an appointment and use the organizer's own invitation token
        # Actually, let's create an appointment where the test user is invited
        
        future_date = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        apt_data = {
            "title": f"TEST_CardReuse_LoginAccept_{uuid.uuid4().hex[:8]}",
            "appointment_type": "physical",
            "location": "Test Location",
            "start_datetime": future_date,
            "duration_minutes": 60,
            "penalty_amount": 25.0,
            "penalty_currency": "EUR",
            "cancellation_deadline_hours": 24,
            "workspace_id": workspace_id,
            "affected_compensation_percent": 80.0,
            "charity_percent": 0.0,
            "platform_commission_percent": 20.0,
            "participants": [{
                "email": TEST_USER_WITH_CARD["email"],
                "first_name": "Test",
                "last_name": "Audit"
            }]
        }
        
        apt_resp = requests.post(
            f"{BASE_URL}/api/appointments/",
            headers={"Authorization": f"Bearer {organizer_token}", "Content-Type": "application/json"},
            json=apt_data
        )
        
        if apt_resp.status_code not in [200, 201]:
            pytest.skip(f"Failed to create appointment: {apt_resp.text}")
        
        apt = apt_resp.json()
        appointment_id = apt["appointment_id"]
        
        try:
            # Get participant's invitation token
            apt_list = requests.get(
                f"{BASE_URL}/api/appointments/?workspace_id={workspace_id}&time_filter=upcoming",
                headers={"Authorization": f"Bearer {organizer_token}"}
            )
            apt_list_data = apt_list.json()
            
            invitation_token = None
            for a in apt_list_data.get("items", []):
                if a.get("appointment_id") == appointment_id:
                    for p in a.get("participants", []):
                        if p.get("email") == TEST_USER_WITH_CARD["email"] and p.get("role") != "organizer":
                            invitation_token = p.get("invitation_token")
                            break
                    break
            
            if not invitation_token:
                # The test user is the organizer, so they're auto-accepted
                # Let's check if there's an existing invitation we can use
                pytest.skip("Test user is organizer - cannot test card reuse in this scenario")
            
            # Call login-and-accept endpoint
            response = requests.post(
                f"{BASE_URL}/api/invitations/{invitation_token}/login-and-accept",
                headers={"Content-Type": "application/json"},
                json={
                    "password": TEST_USER_WITH_CARD["password"],
                    "action": "accept"
                }
            )
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            data = response.json()
            
            # Verify login succeeded
            assert data.get("success") == True
            assert "access_token" in data
            
            # Verify card was reused (no Stripe redirect)
            assert data.get("reused_card") == True, f"Expected reused_card=True, got {data}"
            assert data.get("requires_guarantee") == False, f"Expected requires_guarantee=False, got {data}"
            assert data.get("status") == "accepted_guaranteed"
            assert "checkout_url" not in data, "Should NOT have checkout_url when card is reused"
            
            print(f"✅ Login-accept with card reuse successful!")
            print(f"   reused_card={data.get('reused_card')}, status={data.get('status')}")
            
        finally:
            # Cleanup
            requests.delete(
                f"{BASE_URL}/api/appointments/{appointment_id}",
                headers={"Authorization": f"Bearer {organizer_token}"}
            )


class TestGuaranteeCreationVerification:
    """Verify guarantee is created correctly when card is reused"""
    
    def test_guarantee_has_correct_fields_when_card_reused(self):
        """
        Verify guarantee created via card reuse has:
        - status=completed
        - reused_card=true
        - stripe_payment_method_id set correctly
        """
        # This test verifies the database state after a card reuse
        # We'll use the login-accept endpoint and then check the guarantee
        
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_WITH_CARD["email"],
            "password": TEST_USER_WITH_CARD["password"]
        })
        if login_resp.status_code != 200:
            pytest.skip("Login failed")
        organizer_token = login_resp.json()["access_token"]
        
        # Get workspace
        ws_resp = requests.get(
            f"{BASE_URL}/api/workspaces/",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        ws_data = ws_resp.json()
        workspaces = ws_data.get("workspaces", [])
        if not workspaces:
            pytest.skip("No workspace found")
        workspace_id = workspaces[0]["workspace_id"]
        
        # Create appointment
        future_date = (datetime.now(timezone.utc) + timedelta(days=11)).isoformat()
        apt_data = {
            "title": f"TEST_GuaranteeVerify_{uuid.uuid4().hex[:8]}",
            "appointment_type": "physical",
            "location": "Test Location",
            "start_datetime": future_date,
            "duration_minutes": 60,
            "penalty_amount": 25.0,
            "penalty_currency": "EUR",
            "cancellation_deadline_hours": 24,
            "workspace_id": workspace_id,
            "affected_compensation_percent": 80.0,
            "charity_percent": 0.0,
            "platform_commission_percent": 20.0,
            "participants": [{
                "email": TEST_USER_WITH_CARD["email"],
                "first_name": "Test",
                "last_name": "Audit"
            }]
        }
        
        apt_resp = requests.post(
            f"{BASE_URL}/api/appointments/",
            headers={"Authorization": f"Bearer {organizer_token}", "Content-Type": "application/json"},
            json=apt_data
        )
        
        if apt_resp.status_code not in [200, 201]:
            pytest.skip(f"Failed to create appointment: {apt_resp.text}")
        
        apt = apt_resp.json()
        appointment_id = apt["appointment_id"]
        
        try:
            # Get participant's invitation token
            apt_list = requests.get(
                f"{BASE_URL}/api/appointments/?workspace_id={workspace_id}&time_filter=upcoming",
                headers={"Authorization": f"Bearer {organizer_token}"}
            )
            apt_list_data = apt_list.json()
            
            invitation_token = None
            for a in apt_list_data.get("items", []):
                if a.get("appointment_id") == appointment_id:
                    for p in a.get("participants", []):
                        if p.get("email") == TEST_USER_WITH_CARD["email"] and p.get("role") != "organizer":
                            invitation_token = p.get("invitation_token")
                            break
                    break
            
            if not invitation_token:
                pytest.skip("Test user is organizer - cannot test card reuse")
            
            # Accept invitation
            response = requests.post(
                f"{BASE_URL}/api/invitations/{invitation_token}/login-and-accept",
                headers={"Content-Type": "application/json"},
                json={
                    "password": TEST_USER_WITH_CARD["password"],
                    "action": "accept"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify card was reused
            assert data.get("reused_card") == True
            guarantee_id = data.get("guarantee_id")
            assert guarantee_id is not None
            
            # Check guarantee status via API
            status_resp = requests.get(
                f"{BASE_URL}/api/invitations/{invitation_token}/guarantee-status"
            )
            assert status_resp.status_code == 200
            status_data = status_resp.json()
            
            assert status_data.get("status") == "accepted_guaranteed"
            assert status_data.get("is_guaranteed") == True
            assert status_data.get("guarantee_id") == guarantee_id
            
            print(f"✅ Guarantee created with correct status")
            print(f"   guarantee_id={guarantee_id}")
            print(f"   status=accepted_guaranteed")
            print(f"   is_guaranteed=True")
            
        finally:
            # Cleanup
            requests.delete(
                f"{BASE_URL}/api/appointments/{appointment_id}",
                headers={"Authorization": f"Bearer {organizer_token}"}
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
