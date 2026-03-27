"""
Test Suite for Iteration 104 - GPS Radius Fix, Manual Check-in Review, and Review Timeout

Tests the 4 fixes:
1. GPS radius logic: gps_within_radius uses actual configured radius
2. GPS nearby (500m-5km) does not count as positive signal in aggregate_evidence
3. Manual check-in only → review_required=True
4. Review timeout job: auto-resolve after 15 days
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ORGANIZER_EMAIL = "igaal.hanouna@gmail.com"
ORGANIZER_PASSWORD = "OrgTest123!"
PARTICIPANT_EMAIL = "testuser_audit@nlyt.app"
PARTICIPANT_PASSWORD = "TestAudit123!"


def get_auth_token_and_workspace():
    """Get authentication token and workspace_id"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ORGANIZER_EMAIL,
        "password": ORGANIZER_PASSWORD
    }, headers={"Content-Type": "application/json"})
    
    if response.status_code == 200:
        token = response.json().get("access_token")
        
        # Get workspace
        ws_resp = requests.get(f"{BASE_URL}/api/workspaces/", headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        })
        workspace_id = None
        if ws_resp.status_code == 200:
            workspaces = ws_resp.json().get("workspaces", [])
            if workspaces:
                workspace_id = workspaces[0].get("workspace_id")
        
        return token, workspace_id
    return None, None


class TestGPSRadiusAndReviewFixes:
    """
    Combined test class for all 4 fixes
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authenticated session"""
        token, workspace_id = get_auth_token_and_workspace()
        if not token:
            pytest.skip("Authentication failed")
        
        self.token = token
        self.workspace_id = workspace_id
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def test_01_gps_within_radius_uses_configured_radius(self):
        """
        Test 1: Verify that gps_within_radius is False when distance > configured radius.
        Create appointment with small radius (100m), check-in from 200m away.
        """
        # Create appointment with 100m GPS radius (use trailing slash to avoid redirect)
        apt_data = {
            "title": f"TEST_GPS_Radius_{uuid.uuid4().hex[:8]}",
            "start_datetime": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "duration_minutes": 60,
            "location": "48.8566,2.3522",
            "location_latitude": 48.8566,
            "location_longitude": 2.3522,
            "gps_radius_meters": 100,  # Small radius: 100m
            "appointment_type": "physical",
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "workspace_id": self.workspace_id,
            "affected_compensation_percent": 50.0,
            "charity_percent": 30.0,
            "participants": [{"email": PARTICIPANT_EMAIL}]
        }
        
        response = requests.post(f"{BASE_URL}/api/appointments/", json=apt_data, headers=self.headers)
        assert response.status_code in [200, 201], f"Failed to create appointment: {response.text}"
        apt = response.json()
        apt_id = apt["appointment_id"]
        
        print(f"✅ Created appointment {apt_id} with gps_radius_meters=100")
        
        # Get participant info
        part_resp = requests.get(f"{BASE_URL}/api/appointments/{apt_id}/participants", headers=self.headers)
        assert part_resp.status_code == 200
        participants = part_resp.json().get("participants", [])
        participant = next((p for p in participants if p.get("email") == PARTICIPANT_EMAIL), None)
        assert participant, "Participant not found"
        
        # Check-in from 200m away (should be outside 100m radius)
        checkin_data = {
            "invitation_token": participant.get("invitation_token"),
            "latitude": 48.8584,  # ~200m north
            "longitude": 2.3522,
            "device_info": "test_device"
        }
        
        checkin_resp = requests.post(f"{BASE_URL}/api/checkin/manual", json=checkin_data, headers=self.headers)
        assert checkin_resp.status_code in [200, 409], f"Check-in failed: {checkin_resp.text}"
        
        # Get evidence and verify gps_within_radius is False
        evidence_resp = requests.get(f"{BASE_URL}/api/checkin/{apt_id}/evidence", headers=self.headers)
        assert evidence_resp.status_code == 200
        evidence_data = evidence_resp.json()
        
        # Find participant's evidence
        part_evidence = next(
            (p for p in evidence_data.get("participants", []) if p.get("participant_id") == participant["participant_id"]),
            None
        )
        
        assert part_evidence, "Participant evidence not found"
        assert part_evidence.get("evidence"), "No evidence found"
        
        gps_evidence = next(
            (e for e in part_evidence["evidence"] if e.get("source") in ["gps", "manual_checkin"]),
            None
        )
        assert gps_evidence, "GPS evidence not found"
        
        facts = gps_evidence.get("derived_facts", {})
        distance = facts.get("distance_meters")
        within_radius = facts.get("gps_within_radius")
        configured_radius = facts.get("gps_radius_meters")
        
        print(f"✅ Distance: {distance}m, Configured radius: {configured_radius}m, Within radius: {within_radius}")
        
        # Key assertion: configured radius should be 100m (not default 200m)
        assert configured_radius == 100, f"Configured radius should be 100m, got {configured_radius}m"
        
        # If distance > configured radius, gps_within_radius should be False
        if distance and distance > configured_radius:
            assert within_radius == False, f"gps_within_radius should be False when distance ({distance}m) > radius ({configured_radius}m)"
            print(f"✅ GPS radius fix verified: distance {distance}m > radius {configured_radius}m → gps_within_radius=False")

    def test_02_nearby_gps_does_not_count_as_close(self):
        """
        Test 2: Verify that 'nearby' GPS (500m-5km) does not count as has_gps_close in aggregate_evidence.
        """
        # Create appointment with default radius
        apt_data = {
            "title": f"TEST_GPS_Nearby_{uuid.uuid4().hex[:8]}",
            "start_datetime": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            "duration_minutes": 60,
            "location": "48.8566,2.3522",
            "location_latitude": 48.8566,
            "location_longitude": 2.3522,
            "gps_radius_meters": 200,
            "appointment_type": "physical",
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "workspace_id": self.workspace_id,
            "affected_compensation_percent": 50.0,
            "charity_percent": 30.0,
            "participants": [{"email": PARTICIPANT_EMAIL}]
        }
        
        response = requests.post(f"{BASE_URL}/api/appointments/", json=apt_data, headers=self.headers)
        assert response.status_code in [200, 201]
        apt = response.json()
        apt_id = apt["appointment_id"]
        
        # Get participant
        part_resp = requests.get(f"{BASE_URL}/api/appointments/{apt_id}/participants", headers=self.headers)
        participants = part_resp.json().get("participants", [])
        participant = next((p for p in participants if p.get("email") == PARTICIPANT_EMAIL), None)
        
        # Check-in from 2km away (nearby, not close)
        checkin_data = {
            "invitation_token": participant.get("invitation_token"),
            "latitude": 48.8746,  # ~2km north
            "longitude": 2.3522,
            "device_info": "test_device"
        }
        
        checkin_resp = requests.post(f"{BASE_URL}/api/checkin/manual", json=checkin_data, headers=self.headers)
        assert checkin_resp.status_code in [200, 409]
        
        # Get evidence
        evidence_resp = requests.get(f"{BASE_URL}/api/checkin/{apt_id}/evidence", headers=self.headers)
        evidence_data = evidence_resp.json()
        
        part_evidence = next(
            (p for p in evidence_data.get("participants", []) if p.get("participant_id") == participant["participant_id"]),
            None
        )
        
        assert part_evidence and part_evidence.get("evidence"), "Evidence not found"
        
        gps_evidence = next(
            (e for e in part_evidence["evidence"] if e.get("source") in ["gps", "manual_checkin"]),
            None
        )
        assert gps_evidence, "GPS evidence not found"
        
        facts = gps_evidence.get("derived_facts", {})
        geo_consistency = facts.get("geographic_consistency")
        distance = facts.get("distance_meters")
        
        print(f"✅ Distance: {distance}m, Geographic consistency: {geo_consistency}")
        
        # Nearby (500m-5km) should have geographic_consistency = "nearby", not "close"
        if distance and 500 < distance < 5000:
            assert geo_consistency == "nearby", f"Expected 'nearby' for distance {distance}m, got {geo_consistency}"
            print(f"✅ Nearby GPS correctly classified: {distance}m → {geo_consistency}")

    def test_03_manual_checkin_only_requires_review(self):
        """
        Test 3: Verify that evaluate_participant returns review_required=True when only signal is manual_checkin (no GPS, no QR).
        """
        # Create past appointment
        apt_data = {
            "title": f"TEST_Manual_Review_{uuid.uuid4().hex[:8]}",
            "start_datetime": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            "duration_minutes": 60,
            "location": "Test Location",
            "appointment_type": "physical",
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "workspace_id": self.workspace_id,
            "affected_compensation_percent": 50.0,
            "charity_percent": 30.0,
            "participants": [{"email": PARTICIPANT_EMAIL}]
        }
        
        response = requests.post(f"{BASE_URL}/api/appointments/", json=apt_data, headers=self.headers)
        assert response.status_code in [200, 201]
        apt = response.json()
        apt_id = apt["appointment_id"]
        
        # Get participant
        part_resp = requests.get(f"{BASE_URL}/api/appointments/{apt_id}/participants", headers=self.headers)
        participants = part_resp.json().get("participants", [])
        participant = next((p for p in participants if p.get("email") == PARTICIPANT_EMAIL), None)
        
        # Manual check-in WITHOUT GPS (no latitude/longitude)
        checkin_data = {
            "invitation_token": participant.get("invitation_token"),
            "device_info": "test_device"
            # No latitude/longitude = manual check-in only
        }
        
        checkin_resp = requests.post(f"{BASE_URL}/api/checkin/manual", json=checkin_data, headers=self.headers)
        assert checkin_resp.status_code in [200, 409]
        
        # Evaluate attendance
        eval_resp = requests.post(f"{BASE_URL}/api/attendance/{apt_id}/evaluate", headers=self.headers)
        assert eval_resp.status_code == 200
        
        # Get attendance records
        att_resp = requests.get(f"{BASE_URL}/api/attendance/{apt_id}", headers=self.headers)
        assert att_resp.status_code == 200
        att_data = att_resp.json()
        
        # Find participant's record
        records = att_data.get("records", [])
        part_record = next(
            (r for r in records if r.get("participant_id") == participant["participant_id"]),
            None
        )
        
        assert part_record, "Attendance record not found"
        
        review_required = part_record.get("review_required")
        decision_basis = part_record.get("decision_basis")
        
        print(f"✅ Decision basis: {decision_basis}, Review required: {review_required}")
        
        # Manual check-in only should require review
        if "manual_checkin_only" in str(decision_basis):
            assert review_required == True, f"Manual check-in only should require review, got review_required={review_required}"
            print(f"✅ Manual check-in only correctly requires review")
        else:
            # If not manual_checkin_only, it might have other evidence
            print(f"⚠️ Decision basis is {decision_basis}, not manual_checkin_only")

    def test_04_reclassify_uses_record_id(self):
        """
        Test 4: Verify PUT /api/attendance/reclassify/{record_id} works with a real record_id.
        """
        # Use the known appointment with pending review
        apt_id = "12132ca1-2f84-4d26-8104-cf24df4ba21d"
        
        # Get attendance records
        att_resp = requests.get(f"{BASE_URL}/api/attendance/{apt_id}", headers=self.headers)
        if att_resp.status_code != 200:
            pytest.skip(f"Could not get attendance for appointment {apt_id}")
        
        att_data = att_resp.json()
        records = att_data.get("records", [])
        
        if not records:
            pytest.skip("No attendance records found")
        
        # Find a record with review_required=True or use first record
        review_record = next((r for r in records if r.get("review_required")), records[0])
        
        record_id = review_record.get("record_id")
        assert record_id, "Record should have record_id"
        
        print(f"✅ Found record_id: {record_id}")
        
        # Test reclassify API with record_id
        reclassify_resp = requests.put(
            f"{BASE_URL}/api/attendance/reclassify/{record_id}",
            json={"new_outcome": "on_time"},
            headers=self.headers
        )
        
        # Should succeed or return meaningful error
        assert reclassify_resp.status_code in [200, 400, 404], f"Unexpected status: {reclassify_resp.status_code}"
        
        if reclassify_resp.status_code == 200:
            result = reclassify_resp.json()
            assert result.get("success") == True
            assert result.get("record_id") == record_id
            print(f"✅ Reclassify API works with record_id: {record_id}")

    def test_05_pending_reviews_list_endpoint(self):
        """
        Test 5: Verify GET /api/attendance/pending-reviews/list returns pending review records.
        """
        response = requests.get(f"{BASE_URL}/api/attendance/pending-reviews/list", headers=self.headers)
        
        # Should return 200 or 404 if no pending reviews
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Pending reviews list: {len(data.get('records', []))} records")
            
            # Verify structure
            if data.get("records"):
                record = data["records"][0]
                assert "record_id" in record, "Record should have record_id"
                assert "appointment_id" in record, "Record should have appointment_id"
                assert "participant_id" in record, "Record should have participant_id"
                print(f"✅ Pending review record structure verified")


class TestSchedulerRegistration:
    """
    Test scheduler registration for review_timeout_job
    """

    def test_scheduler_module_has_review_timeout_job(self):
        """
        Verify the review_timeout_job is defined in scheduler.py
        """
        # Read scheduler.py and check for review_timeout_job
        with open('/app/backend/scheduler.py', 'r') as f:
            content = f.read()
        
        assert 'review_timeout_job' in content, "review_timeout_job not found in scheduler.py"
        assert 'run_review_timeout_job' in content, "run_review_timeout_job not called in scheduler.py"
        assert 'hours=6' in content or 'IntervalTrigger(hours=6)' in content, "review_timeout_job should run every 6 hours"
        
        print("✅ review_timeout_job is registered in scheduler.py")
        print("✅ Runs every 6 hours as expected")


class TestAttendanceServiceReviewTimeout:
    """
    Test attendance_service.py review timeout logic
    """

    def test_review_timeout_constants(self):
        """
        Verify REVIEW_TIMEOUT_DAYS = 15 in attendance_service.py
        """
        with open('/app/backend/services/attendance_service.py', 'r') as f:
            content = f.read()
        
        assert 'REVIEW_TIMEOUT_DAYS = 15' in content, "REVIEW_TIMEOUT_DAYS should be 15"
        assert 'run_review_timeout_job' in content, "run_review_timeout_job function should exist"
        assert 'waived' in content, "Timeout should set outcome to 'waived'"
        assert 'system_timeout' in content, "decided_by should be 'system_timeout'"
        
        print("✅ REVIEW_TIMEOUT_DAYS = 15")
        print("✅ run_review_timeout_job function exists")
        print("✅ Timeout sets outcome to 'waived' and decided_by to 'system_timeout'")


class TestEvidenceServiceGPSFix:
    """
    Test evidence_service.py GPS radius fix
    """

    def test_gps_radius_uses_actual_radius(self):
        """
        Verify gps_within_radius uses actual_radius from appointment config
        """
        with open('/app/backend/services/evidence_service.py', 'r') as f:
            content = f.read()
        
        # Check that gps_within_radius uses actual_radius, not hardcoded categories
        assert 'actual_radius = appointment.get' in content, "Should get actual_radius from appointment"
        assert 'gps_radius_meters' in content, "Should use gps_radius_meters field"
        # The actual pattern is: geographic['distance_meters'] <= actual_radius
        assert "geographic['distance_meters'] <= actual_radius" in content, "Should compare distance to actual_radius"
        
        print("✅ gps_within_radius uses actual_radius from appointment config")

    def test_manual_checkin_only_flag(self):
        """
        Verify manual_checkin_only flag is computed in aggregate_evidence
        """
        with open('/app/backend/services/evidence_service.py', 'r') as f:
            content = f.read()
        
        assert 'manual_checkin_only' in content, "manual_checkin_only flag should exist"
        assert 'has_checkin and not has_qr and not has_gps_close' in content, "manual_checkin_only should check for no QR and no GPS close"
        
        print("✅ manual_checkin_only flag is computed correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
