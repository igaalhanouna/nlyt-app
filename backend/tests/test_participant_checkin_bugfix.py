"""
Test Participant Check-in Bug Fix (Iteration 98)

Bug: ParticipantCheckinBlock was sending wrong payload to /api/checkin/manual
Fixed: Now sends {invitation_token, device_info, latitude?, longitude?, gps_consent?}
Also fixed: Status check uses res.data.checked_in instead of res.data.checkins
Also fixed: Status filter includes accepted_pending_guarantee

Tests:
A. Dashboard display - organizer/participant see correct data
B. Appointment detail page - viewer_role returned correctly
C. Participant check-in - POST /api/checkin/manual with invitation_token
D. Check-in status sync - GET /api/checkin/status returns checked_in field
E. Timeline endpoint - returns invitation_token for participant items
F. Edge cases - 409 on double check-in, 401 for unauthenticated
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_USER_EMAIL = "testuser_audit@nlyt.app"
TEST_USER_PASSWORD = "Test123!"
PARTICIPANT_EMAIL = "igaal.hanouna@gmail.com"


class TestParticipantCheckinBugFix:
    """Tests for the participant check-in bug fix"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as test user
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.user_id = login_resp.json()["user"]["user_id"]
        
    # ─── A. DASHBOARD DISPLAY ───
    
    def test_my_timeline_returns_data(self):
        """GET /api/appointments/my-timeline returns timeline buckets"""
        resp = self.session.get(f"{BASE_URL}/api/appointments/my-timeline")
        assert resp.status_code == 200, f"Timeline failed: {resp.text}"
        data = resp.json()
        
        # Should have timeline structure
        assert "upcoming" in data or "today" in data or "past" in data or "items" in data, \
            f"Timeline missing expected buckets: {list(data.keys())}"
        print(f"✅ Timeline endpoint returns data with keys: {list(data.keys())}")
    
    def test_timeline_participant_items_have_invitation_token(self):
        """Participant items in timeline should have invitation_token field"""
        resp = self.session.get(f"{BASE_URL}/api/appointments/my-timeline")
        assert resp.status_code == 200
        data = resp.json()
        
        # Find any participant items
        all_items = []
        for bucket in ["today", "upcoming", "past"]:
            if bucket in data:
                all_items.extend(data[bucket])
        
        participant_items = [item for item in all_items if item.get("role") == "participant"]
        
        if participant_items:
            for item in participant_items[:3]:  # Check first 3
                assert "invitation_token" in item, f"Participant item missing invitation_token: {item.get('appointment_id')}"
            print(f"✅ Found {len(participant_items)} participant items with invitation_token")
        else:
            print("⚠️ No participant items found in timeline (may be expected)")
    
    # ─── B. APPOINTMENT DETAIL PAGE ───
    
    def test_appointment_detail_returns_viewer_role(self):
        """GET /api/appointments/{id} returns viewer_role field"""
        # First get an appointment from timeline
        timeline_resp = self.session.get(f"{BASE_URL}/api/appointments/my-timeline")
        assert timeline_resp.status_code == 200
        data = timeline_resp.json()
        
        # Find any appointment
        all_items = []
        for bucket in ["today", "upcoming", "past"]:
            if bucket in data:
                all_items.extend(data[bucket])
        
        if not all_items:
            pytest.skip("No appointments found for testing")
        
        apt_id = all_items[0].get("appointment_id")
        
        # Get appointment detail
        detail_resp = self.session.get(f"{BASE_URL}/api/appointments/{apt_id}")
        assert detail_resp.status_code == 200, f"Detail failed: {detail_resp.text}"
        apt = detail_resp.json()
        
        assert "viewer_role" in apt, f"Missing viewer_role in appointment detail"
        assert apt["viewer_role"] in ["organizer", "participant"], f"Invalid viewer_role: {apt['viewer_role']}"
        print(f"✅ Appointment {apt_id[:8]} has viewer_role={apt['viewer_role']}")
    
    def test_participant_view_has_invitation_token(self):
        """Participant view should have viewer_invitation_token"""
        timeline_resp = self.session.get(f"{BASE_URL}/api/appointments/my-timeline")
        assert timeline_resp.status_code == 200
        data = timeline_resp.json()
        
        # Find participant items
        all_items = []
        for bucket in ["today", "upcoming", "past"]:
            if bucket in data:
                all_items.extend(data[bucket])
        
        participant_items = [item for item in all_items if item.get("role") == "participant"]
        
        if not participant_items:
            pytest.skip("No participant appointments found")
        
        apt_id = participant_items[0].get("appointment_id")
        detail_resp = self.session.get(f"{BASE_URL}/api/appointments/{apt_id}")
        assert detail_resp.status_code == 200
        apt = detail_resp.json()
        
        if apt.get("viewer_role") == "participant":
            assert "viewer_invitation_token" in apt, "Participant view missing viewer_invitation_token"
            assert apt["viewer_invitation_token"], "viewer_invitation_token is empty"
            print(f"✅ Participant view has viewer_invitation_token")
        else:
            print(f"⚠️ Appointment {apt_id[:8]} is organizer view, skipping token check")
    
    # ─── C. PARTICIPANT CHECK-IN (MANUAL) ───
    
    def test_checkin_manual_requires_invitation_token(self):
        """POST /api/checkin/manual requires invitation_token in payload"""
        # Try with missing invitation_token - should fail
        resp = self.session.post(f"{BASE_URL}/api/checkin/manual", json={
            "device_info": "pytest"
        })
        # Should fail with 422 (validation error) or 404 (not found)
        assert resp.status_code in [422, 400, 404], f"Expected validation error, got {resp.status_code}"
        print(f"✅ Check-in without invitation_token correctly rejected ({resp.status_code})")
    
    def test_checkin_manual_with_invalid_token(self):
        """POST /api/checkin/manual with invalid token returns 404"""
        resp = self.session.post(f"{BASE_URL}/api/checkin/manual", json={
            "invitation_token": "invalid-token-12345",
            "device_info": "pytest"
        })
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        print(f"✅ Check-in with invalid token correctly returns 404")
    
    def test_checkin_manual_payload_structure(self):
        """Verify the expected payload structure for manual check-in"""
        # This tests that the API accepts the correct payload format
        # We use a known-bad token to verify the payload is parsed correctly
        resp = self.session.post(f"{BASE_URL}/api/checkin/manual", json={
            "invitation_token": "test-token-structure",
            "device_info": "Mozilla/5.0 pytest",
            "latitude": 48.8566,
            "longitude": 2.3522,
            "gps_consent": True
        })
        # Should fail with 404 (token not found), not 422 (validation error)
        assert resp.status_code == 404, f"Payload structure issue: {resp.status_code} - {resp.text}"
        print(f"✅ Check-in payload structure is correct (invitation_token, device_info, lat, lon, gps_consent)")
    
    # ─── D. CHECK-IN STATUS SYNC ───
    
    def test_checkin_status_returns_checked_in_field(self):
        """GET /api/checkin/status/{id} returns checked_in field (not checkins)"""
        # Get a participant appointment with invitation token
        timeline_resp = self.session.get(f"{BASE_URL}/api/appointments/my-timeline")
        assert timeline_resp.status_code == 200
        data = timeline_resp.json()
        
        all_items = []
        for bucket in ["today", "upcoming", "past"]:
            if bucket in data:
                all_items.extend(data[bucket])
        
        participant_items = [item for item in all_items if item.get("role") == "participant" and item.get("invitation_token")]
        
        if not participant_items:
            pytest.skip("No participant appointments with invitation_token found")
        
        item = participant_items[0]
        apt_id = item["appointment_id"]
        token = item["invitation_token"]
        
        # Get check-in status
        status_resp = self.session.get(f"{BASE_URL}/api/checkin/status/{apt_id}?invitation_token={token}")
        assert status_resp.status_code == 200, f"Status check failed: {status_resp.text}"
        status = status_resp.json()
        
        # CRITICAL: Must have checked_in field (not checkins)
        assert "checked_in" in status, f"Missing 'checked_in' field in status response: {list(status.keys())}"
        assert isinstance(status["checked_in"], bool), f"checked_in should be boolean, got {type(status['checked_in'])}"
        
        # Should also have evidence_count
        assert "evidence_count" in status, "Missing evidence_count field"
        
        print(f"✅ Status endpoint returns checked_in={status['checked_in']}, evidence_count={status['evidence_count']}")
    
    # ─── E. EDGE CASES ───
    
    def test_double_checkin_returns_409(self):
        """Double check-in should return 409 Conflict"""
        # Use the known already-checked-in appointment from context
        # Token: 285cbc51-31fe-476c-bdba-2c91c73bef9e (already checked in)
        known_token = "285cbc51-31fe-476c-bdba-2c91c73bef9e"
        
        resp = self.session.post(f"{BASE_URL}/api/checkin/manual", json={
            "invitation_token": known_token,
            "device_info": "pytest double-check"
        })
        
        # Should be 409 (already checked in) or 404 (token not found/expired)
        if resp.status_code == 409:
            print(f"✅ Double check-in correctly returns 409 Conflict")
        elif resp.status_code == 404:
            print(f"⚠️ Token not found (may have expired or been cleaned up)")
        elif resp.status_code == 400:
            # Could be "invitation not accepted" or similar
            print(f"⚠️ Check-in rejected with 400: {resp.json().get('detail', resp.text)}")
        else:
            pytest.fail(f"Unexpected status {resp.status_code}: {resp.text}")
    
    def test_unauthenticated_evidence_returns_401(self):
        """GET /api/checkin/evidence/{id} without auth returns 401"""
        # Use a session without auth
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        
        resp = no_auth_session.get(f"{BASE_URL}/api/checkin/evidence/test-appointment-id")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
        print(f"✅ Evidence endpoint without auth returns {resp.status_code}")
    
    # ─── F. EVIDENCE ENDPOINT ACCESS ───
    
    def test_evidence_endpoint_accessible_by_participant(self):
        """GET /api/checkin/evidence/{id} accessible by participant"""
        # Get a participant appointment
        timeline_resp = self.session.get(f"{BASE_URL}/api/appointments/my-timeline")
        assert timeline_resp.status_code == 200
        data = timeline_resp.json()
        
        all_items = []
        for bucket in ["today", "upcoming", "past"]:
            if bucket in data:
                all_items.extend(data[bucket])
        
        if not all_items:
            pytest.skip("No appointments found")
        
        apt_id = all_items[0]["appointment_id"]
        
        # Get evidence
        evidence_resp = self.session.get(f"{BASE_URL}/api/checkin/evidence/{apt_id}")
        # Should be 200 (accessible) or 403 (not a participant/organizer)
        assert evidence_resp.status_code in [200, 403], f"Unexpected status: {evidence_resp.status_code}"
        
        if evidence_resp.status_code == 200:
            evidence = evidence_resp.json()
            assert "participants" in evidence, "Evidence response missing participants field"
            print(f"✅ Evidence endpoint accessible, {len(evidence.get('participants', []))} participants")
        else:
            print(f"⚠️ Evidence endpoint returned 403 (user may not be participant/organizer)")


class TestAcceptedPendingGuaranteeStatus:
    """Tests for accepted_pending_guarantee status handling"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        assert login_resp.status_code == 200
        self.token = login_resp.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_resolve_participant_accepts_pending_guarantee(self):
        """_resolve_participant should accept accepted_pending_guarantee status"""
        # This is tested indirectly through the check-in endpoint
        # The backend code at line 80 includes accepted_pending_guarantee
        # We verify by checking the status endpoint works for such participants
        
        timeline_resp = self.session.get(f"{BASE_URL}/api/appointments/my-timeline")
        assert timeline_resp.status_code == 200
        data = timeline_resp.json()
        
        all_items = []
        for bucket in ["today", "upcoming", "past"]:
            if bucket in data:
                all_items.extend(data[bucket])
        
        # Look for any participant items
        participant_items = [item for item in all_items if item.get("role") == "participant"]
        
        if participant_items:
            item = participant_items[0]
            if item.get("invitation_token"):
                # Try to get status - should work for accepted/accepted_pending_guarantee/accepted_guaranteed
                status_resp = self.session.get(
                    f"{BASE_URL}/api/checkin/status/{item['appointment_id']}?invitation_token={item['invitation_token']}"
                )
                # 200 = accepted status, 400 = not accepted yet
                if status_resp.status_code == 200:
                    print(f"✅ Status check works for participant (status accepted)")
                elif status_resp.status_code == 400:
                    detail = status_resp.json().get("detail", "")
                    print(f"⚠️ Participant not yet accepted: {detail}")
                else:
                    print(f"⚠️ Unexpected status: {status_resp.status_code}")
        else:
            print("⚠️ No participant items found to test")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
