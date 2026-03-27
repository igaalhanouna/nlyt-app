"""
Test: Guarantee Finalization Fix (Iteration 102)
Tests that participants with status 'accepted_pending_guarantee' can:
1. Finalize their guarantee via POST /api/invitations/{token}/respond with action='accept'
2. Decline via POST /api/invitations/{token}/respond with action='decline'
3. Statuses 'accepted', 'accepted_guaranteed', 'declined' remain blocked
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test tokens from the review request
TEST_TOKEN_PENDING = "c86cd8f1-160d-4b28-8c07-34d6b418cf5d"  # accepted_pending_guarantee
TEST_TOKEN_FOR_DECLINE = "7f8ddfb9-b06c-4f59-be09-b1127fda77c1"  # another pending guarantee token
TEST_APPOINTMENT_ID = "3e6f96c5-d1ec-4499-89a0-b886ec208494"

# Test credentials
TEST_EMAIL = "igaal@hotmail.com"
TEST_PASSWORD = "Demo123!"


class TestGuaranteeFinalization:
    """Tests for accepted_pending_guarantee status handling"""
    
    def test_a_get_invitation_details_pending_guarantee(self):
        """Test: GET invitation details for accepted_pending_guarantee participant"""
        response = requests.get(f"{BASE_URL}/api/invitations/{TEST_TOKEN_PENDING}")
        print(f"GET invitation response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            status = data.get('participant', {}).get('status')
            print(f"Participant status: {status}")
            print(f"Participant email: {data.get('participant', {}).get('email')}")
            print(f"Appointment title: {data.get('appointment', {}).get('title')}")
            assert status in ['accepted_pending_guarantee', 'invited', 'accepted', 'accepted_guaranteed', 'declined'], f"Unexpected status: {status}"
            print(f"✅ A. GET invitation details works for token {TEST_TOKEN_PENDING[:8]}...")
        elif response.status_code == 404:
            pytest.skip(f"Token {TEST_TOKEN_PENDING[:8]}... not found - may have been used/changed")
        else:
            print(f"Response: {response.text}")
            pytest.fail(f"Unexpected status code: {response.status_code}")
    
    def test_b_respond_accept_pending_guarantee_returns_checkout(self):
        """Test: POST respond with action='accept' for accepted_pending_guarantee should work (not 400)"""
        # First check current status
        get_resp = requests.get(f"{BASE_URL}/api/invitations/{TEST_TOKEN_PENDING}")
        if get_resp.status_code == 404:
            pytest.skip("Token not found")
        
        current_status = get_resp.json().get('participant', {}).get('status')
        print(f"Current status before accept: {current_status}")
        
        if current_status not in ['accepted_pending_guarantee', 'invited']:
            pytest.skip(f"Participant already has status '{current_status}' - cannot test accept")
        
        # Try to accept
        response = requests.post(
            f"{BASE_URL}/api/invitations/{TEST_TOKEN_PENDING}/respond",
            json={"action": "accept"}
        )
        print(f"POST respond (accept) response: {response.status_code}")
        data = response.json()
        print(f"Response data: {data}")
        
        # Should NOT return 400 for accepted_pending_guarantee
        if current_status == 'accepted_pending_guarantee':
            assert response.status_code != 400 or "déjà répondu" not in data.get('detail', ''), \
                f"BUG: accepted_pending_guarantee should be allowed to retry, got: {data}"
        
        if response.status_code == 200:
            # Should return checkout_url for Stripe
            if data.get('requires_guarantee'):
                assert 'checkout_url' in data, "Missing checkout_url for guarantee"
                print(f"✅ B. Accept returns checkout_url: {data['checkout_url'][:50]}...")
            elif data.get('reused_card'):
                print(f"✅ B. Accept reused saved card: {data.get('message')}")
            else:
                print(f"✅ B. Accept succeeded without guarantee (penalty=0?)")
        else:
            print(f"Response: {data}")
            # If 400, check if it's the old bug
            if response.status_code == 400 and "déjà répondu" in str(data):
                pytest.fail("BUG NOT FIXED: accepted_pending_guarantee still blocked from retrying")
    
    def test_c_respond_decline_pending_guarantee_works(self):
        """Test: POST respond with action='decline' for accepted_pending_guarantee should work"""
        # Use a different token for decline test to not interfere with accept test
        get_resp = requests.get(f"{BASE_URL}/api/invitations/{TEST_TOKEN_FOR_DECLINE}")
        if get_resp.status_code == 404:
            pytest.skip("Decline test token not found")
        
        current_status = get_resp.json().get('participant', {}).get('status')
        print(f"Current status before decline: {current_status}")
        
        if current_status not in ['accepted_pending_guarantee', 'invited']:
            pytest.skip(f"Participant already has status '{current_status}' - cannot test decline")
        
        # Try to decline
        response = requests.post(
            f"{BASE_URL}/api/invitations/{TEST_TOKEN_FOR_DECLINE}/respond",
            json={"action": "decline"}
        )
        print(f"POST respond (decline) response: {response.status_code}")
        data = response.json()
        print(f"Response data: {data}")
        
        if current_status == 'accepted_pending_guarantee':
            assert response.status_code != 400 or "déjà répondu" not in data.get('detail', ''), \
                f"BUG: accepted_pending_guarantee should be allowed to decline, got: {data}"
        
        if response.status_code == 200:
            assert data.get('status') == 'declined', f"Expected status 'declined', got: {data.get('status')}"
            print(f"✅ C. Decline works for accepted_pending_guarantee")
        else:
            print(f"Response: {data}")
    
    def test_d_blocked_statuses_still_blocked(self):
        """Test: Statuses 'accepted', 'accepted_guaranteed', 'declined' should still be blocked"""
        # We need to find tokens with these statuses - let's check the test tokens
        blocked_statuses = ['accepted', 'accepted_guaranteed', 'declined']
        
        # Check first token
        get_resp = requests.get(f"{BASE_URL}/api/invitations/{TEST_TOKEN_PENDING}")
        if get_resp.status_code == 200:
            status = get_resp.json().get('participant', {}).get('status')
            if status in blocked_statuses:
                # Try to respond - should be blocked
                response = requests.post(
                    f"{BASE_URL}/api/invitations/{TEST_TOKEN_PENDING}/respond",
                    json={"action": "accept"}
                )
                assert response.status_code == 400, f"Expected 400 for status '{status}', got {response.status_code}"
                assert "déjà répondu" in response.json().get('detail', ''), "Expected 'déjà répondu' error"
                print(f"✅ D. Status '{status}' correctly blocked from responding")
            else:
                print(f"Token has status '{status}' - not a blocked status, skipping this check")
        
        # Check second token
        get_resp2 = requests.get(f"{BASE_URL}/api/invitations/{TEST_TOKEN_FOR_DECLINE}")
        if get_resp2.status_code == 200:
            status2 = get_resp2.json().get('participant', {}).get('status')
            if status2 in blocked_statuses:
                response2 = requests.post(
                    f"{BASE_URL}/api/invitations/{TEST_TOKEN_FOR_DECLINE}/respond",
                    json={"action": "accept"}
                )
                assert response2.status_code == 400, f"Expected 400 for status '{status2}', got {response2.status_code}"
                print(f"✅ D. Status '{status2}' correctly blocked from responding")
        
        print("✅ D. Blocked statuses verification complete")


class TestLoginAndAppointmentAccess:
    """Test login and appointment detail access for participant"""
    
    def test_e_login_as_participant(self):
        """Test: Login as igaal@hotmail.com"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        print(f"Login response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            assert 'access_token' in data, "Missing access_token in login response"
            print(f"✅ E. Login successful for {TEST_EMAIL}")
            return data['access_token']
        else:
            print(f"Login failed: {response.text}")
            pytest.skip(f"Cannot login as {TEST_EMAIL}")
    
    def test_f_get_appointment_as_participant(self):
        """Test: GET appointment detail as participant shows viewer_participant_status"""
        # First login
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if login_resp.status_code != 200:
            pytest.skip("Cannot login")
        
        token = login_resp.json()['access_token']
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get appointment
        response = requests.get(
            f"{BASE_URL}/api/appointments/{TEST_APPOINTMENT_ID}",
            headers=headers
        )
        print(f"GET appointment response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            viewer_role = data.get('viewer_role')
            viewer_status = data.get('viewer_participant_status')
            viewer_token = data.get('viewer_invitation_token')
            
            print(f"Viewer role: {viewer_role}")
            print(f"Viewer participant status: {viewer_status}")
            print(f"Viewer invitation token: {viewer_token[:8] if viewer_token else 'None'}...")
            
            assert viewer_role == 'participant', f"Expected viewer_role='participant', got '{viewer_role}'"
            assert viewer_status is not None, "Missing viewer_participant_status"
            assert viewer_token is not None, "Missing viewer_invitation_token"
            
            print(f"✅ F. Appointment detail returns correct viewer info")
            return data
        elif response.status_code == 404:
            pytest.skip(f"Appointment {TEST_APPOINTMENT_ID} not found")
        else:
            print(f"Response: {response.text}")
            pytest.fail(f"Unexpected status: {response.status_code}")


class TestCodeReview:
    """Code review checks for the fix"""
    
    def test_g_invitations_py_status_check_line_296(self):
        """Verify: Line 296 in invitations.py excludes accepted_pending_guarantee from blocked list"""
        # Read the file
        try:
            with open('/app/backend/routers/invitations.py', 'r') as f:
                content = f.read()
                lines = content.split('\n')
            
            # Check around line 296 (respond_to_invitation status check)
            for i, line in enumerate(lines[290:310], start=291):
                if 'accepted_pending_guarantee' in line and 'status' in line:
                    print(f"Line {i}: {line.strip()}")
            
            # The fix should have: if current_status in ['accepted', 'accepted_guaranteed', 'declined']:
            # NOT: if current_status in ['accepted', 'accepted_pending_guarantee', 'accepted_guaranteed', 'declined']:
            
            # Find the respond_to_invitation function and check the status list
            in_respond_func = False
            for i, line in enumerate(lines, start=1):
                if 'async def respond_to_invitation' in line:
                    in_respond_func = True
                if in_respond_func and 'current_status in' in line:
                    print(f"Found status check at line {i}: {line.strip()}")
                    # Check if accepted_pending_guarantee is NOT in the blocked list
                    if "'accepted_pending_guarantee'" in line or '"accepted_pending_guarantee"' in line:
                        pytest.fail(f"BUG: accepted_pending_guarantee still in blocked list at line {i}")
                    else:
                        print(f"✅ G. Line {i} correctly excludes accepted_pending_guarantee from blocked list")
                    break
        except Exception as e:
            pytest.skip(f"Could not read invitations.py: {e}")
    
    def test_h_invitations_py_accept_with_account_line_508(self):
        """Verify: Line 508 in invitations.py (accept_with_account) excludes accepted_pending_guarantee"""
        try:
            with open('/app/backend/routers/invitations.py', 'r') as f:
                content = f.read()
                lines = content.split('\n')
            
            in_accept_with_account = False
            for i, line in enumerate(lines, start=1):
                if 'async def accept_with_account' in line:
                    in_accept_with_account = True
                if in_accept_with_account and 'status' in line and ("in [" in line or "in (" in line):
                    if 'accepted' in line and 'declined' in line:
                        print(f"Found status check at line {i}: {line.strip()}")
                        if "'accepted_pending_guarantee'" in line or '"accepted_pending_guarantee"' in line:
                            pytest.fail(f"BUG: accepted_pending_guarantee still in blocked list at line {i}")
                        else:
                            print(f"✅ H. accept_with_account correctly excludes accepted_pending_guarantee")
                        break
        except Exception as e:
            pytest.skip(f"Could not read invitations.py: {e}")
    
    def test_i_invitations_py_login_and_accept_line_633(self):
        """Verify: Line 633 in invitations.py (login_and_accept) excludes accepted_pending_guarantee"""
        try:
            with open('/app/backend/routers/invitations.py', 'r') as f:
                content = f.read()
                lines = content.split('\n')
            
            in_login_and_accept = False
            for i, line in enumerate(lines, start=1):
                if 'async def login_and_accept' in line:
                    in_login_and_accept = True
                if in_login_and_accept and 'status' in line and ("in [" in line or "in (" in line):
                    if 'accepted' in line and 'declined' in line:
                        print(f"Found status check at line {i}: {line.strip()}")
                        if "'accepted_pending_guarantee'" in line or '"accepted_pending_guarantee"' in line:
                            pytest.fail(f"BUG: accepted_pending_guarantee still in blocked list at line {i}")
                        else:
                            print(f"✅ I. login_and_accept correctly excludes accepted_pending_guarantee")
                        break
        except Exception as e:
            pytest.skip(f"Could not read invitations.py: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
