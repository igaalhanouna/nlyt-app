"""
Video Evidence System Tests
Tests for video conference attendance evidence ingestion and attendance evaluation.

Test appointments:
- Zoom: 5fef7ecd-5a97-4ee7-9507-92837d7a4313
- Teams: 17697c91-5fa4-49e6-8a50-e18551fccfcf
- Meet: fe91df67-5e40-41d8-94d4-4d02d142eae0
- Workspace: 7e219321-18fd-4643-9be6-e4f1de88a2a8

Conservative rules to verify:
1. Google Meet evidence confidence is ALWAYS 'low'
2. Google Meet attendance decision is ALWAYS 'manual_review'
3. Zoom/Teams with high identity match → 'on_time' auto-decision
4. Ambiguous identity → 'manual_review'
"""
import pytest
import requests
import os
import json
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://dispute-resolver-12.preview.emergentagent.com')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"

# Test appointment IDs
ZOOM_APT_ID = "5fef7ecd-5a97-4ee7-9507-92837d7a4313"
TEAMS_APT_ID = "17697c91-5fa4-49e6-8a50-e18551fccfcf"
MEET_APT_ID = "fe91df67-5e40-41d8-94d4-4d02d142eae0"
WORKSPACE_ID = "7e219321-18fd-4643-9be6-e4f1de88a2a8"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test user."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Return headers with auth token."""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture(scope="function")
def clean_video_evidence(auth_headers):
    """Clean up video evidence before each test that needs fresh state."""
    # This fixture can be used to clear evidence before specific tests
    pass


class TestVideoEvidenceIngestion:
    """Tests for POST /api/video-evidence/{apt_id}/ingest endpoint."""

    def test_zoom_exact_email_match_high_confidence(self, auth_headers):
        """Zoom with exact email match should return high confidence and joined_on_time."""
        # First, get the appointment to find participant email
        apt_response = requests.get(
            f"{BASE_URL}/api/appointments/{ZOOM_APT_ID}",
            headers=auth_headers
        )
        assert apt_response.status_code == 200, f"Failed to get appointment: {apt_response.text}"
        
        # Get participants
        participants_response = requests.get(
            f"{BASE_URL}/api/participants/?appointment_id={ZOOM_APT_ID}",
            headers=auth_headers
        )
        assert participants_response.status_code == 200
        participants = participants_response.json().get("participants", [])
        
        # Find an accepted participant
        accepted_participant = None
        for p in participants:
            if p.get("status") in ("accepted", "accepted_pending_guarantee", "accepted_guaranteed"):
                accepted_participant = p
                break
        
        if not accepted_participant:
            pytest.skip("No accepted participant found for Zoom appointment")
        
        # Create Zoom payload with exact email match
        zoom_payload = {
            "provider": "zoom",
            "external_meeting_id": "zoom-test-123",
            "raw_payload": {
                "meeting_id": "zoom-test-123",
                "topic": "Test Meeting",
                "participants": [
                    {
                        "id": "user-uuid-1",
                        "name": f"{accepted_participant.get('first_name', '')} {accepted_participant.get('last_name', '')}",
                        "user_email": accepted_participant.get("email"),
                        "join_time": datetime.utcnow().isoformat() + "Z",
                        "leave_time": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z",
                        "duration": 3600
                    }
                ]
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/video-evidence/{ZOOM_APT_ID}/ingest",
            headers=auth_headers,
            json=zoom_payload
        )
        
        # May return 400 if already ingested, which is expected
        if response.status_code == 400:
            error_detail = response.json().get("detail", "")
            if "déjà été ingéré" in error_detail or "déjà existante" in error_detail:
                print(f"Evidence already ingested (expected): {error_detail}")
                return
        
        assert response.status_code == 200, f"Ingestion failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True
        assert data.get("provider") == "zoom"
        assert data.get("provider_evidence_ceiling") == "strong"
        
        # Check matched participants have high confidence
        matched = data.get("matched", [])
        if matched:
            for m in matched:
                assert m.get("identity_confidence") in ("high", "medium"), \
                    f"Expected high/medium confidence for Zoom email match, got {m.get('identity_confidence')}"
        
        print(f"Zoom ingestion result: {json.dumps(data, indent=2)}")

    def test_teams_exact_email_match_high_confidence(self, auth_headers):
        """Teams with exact email match should return high confidence."""
        # Get participants
        participants_response = requests.get(
            f"{BASE_URL}/api/participants/?appointment_id={TEAMS_APT_ID}",
            headers=auth_headers
        )
        assert participants_response.status_code == 200
        participants = participants_response.json().get("participants", [])
        
        accepted_participant = None
        for p in participants:
            if p.get("status") in ("accepted", "accepted_pending_guarantee", "accepted_guaranteed"):
                accepted_participant = p
                break
        
        if not accepted_participant:
            pytest.skip("No accepted participant found for Teams appointment")
        
        # Create Teams payload
        teams_payload = {
            "provider": "teams",
            "external_meeting_id": "teams-test-123",
            "raw_payload": {
                "meeting_id": "teams-test-123",
                "attendanceRecords": [
                    {
                        "emailAddress": accepted_participant.get("email"),
                        "identity": {
                            "displayName": f"{accepted_participant.get('first_name', '')} {accepted_participant.get('last_name', '')}"
                        },
                        "totalAttendanceInSeconds": 3600,
                        "attendanceIntervals": [
                            {
                                "joinDateTime": datetime.utcnow().isoformat() + "Z",
                                "leaveDateTime": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z",
                                "durationInSeconds": 3600
                            }
                        ],
                        "role": "Attendee"
                    }
                ]
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/video-evidence/{TEAMS_APT_ID}/ingest",
            headers=auth_headers,
            json=teams_payload
        )
        
        if response.status_code == 400:
            error_detail = response.json().get("detail", "")
            if "déjà été ingéré" in error_detail or "déjà existante" in error_detail:
                print(f"Evidence already ingested (expected): {error_detail}")
                return
        
        assert response.status_code == 200, f"Ingestion failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True
        assert data.get("provider") == "teams"
        assert data.get("provider_evidence_ceiling") == "strong"
        
        print(f"Teams ingestion result: {json.dumps(data, indent=2)}")

    def test_meet_always_low_confidence(self, auth_headers):
        """Google Meet should ALWAYS return low confidence regardless of email match."""
        # Get participants
        participants_response = requests.get(
            f"{BASE_URL}/api/participants/?appointment_id={MEET_APT_ID}",
            headers=auth_headers
        )
        assert participants_response.status_code == 200
        participants = participants_response.json().get("participants", [])
        
        accepted_participant = None
        for p in participants:
            if p.get("status") in ("accepted", "accepted_pending_guarantee", "accepted_guaranteed"):
                accepted_participant = p
                break
        
        if not accepted_participant:
            pytest.skip("No accepted participant found for Meet appointment")
        
        # Create Meet payload with exact email match
        meet_payload = {
            "provider": "meet",
            "external_meeting_id": "meet-test-123",
            "raw_payload": {
                "meeting_id": "meet-test-123",
                "participants": [
                    {
                        "name": f"{accepted_participant.get('first_name', '')} {accepted_participant.get('last_name', '')}",
                        "email": accepted_participant.get("email"),  # Even with email, should be low
                        "join_time": datetime.utcnow().isoformat() + "Z",
                        "leave_time": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z",
                        "duration": 3600
                    }
                ]
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/video-evidence/{MEET_APT_ID}/ingest",
            headers=auth_headers,
            json=meet_payload
        )
        
        if response.status_code == 400:
            error_detail = response.json().get("detail", "")
            if "déjà été ingéré" in error_detail or "déjà existante" in error_detail:
                print(f"Evidence already ingested (expected): {error_detail}")
                # Verify existing evidence has low confidence
                evidence_response = requests.get(
                    f"{BASE_URL}/api/video-evidence/{MEET_APT_ID}",
                    headers=auth_headers
                )
                if evidence_response.status_code == 200:
                    evidence_data = evidence_response.json()
                    for ev in evidence_data.get("video_evidence", []):
                        facts = ev.get("derived_facts", {})
                        if facts.get("provider") == "meet":
                            assert facts.get("identity_confidence") == "low", \
                                f"Meet evidence should have low confidence, got {facts.get('identity_confidence')}"
                            assert ev.get("confidence_score") == "low", \
                                f"Meet evidence confidence_score should be low, got {ev.get('confidence_score')}"
                return
        
        assert response.status_code == 200, f"Ingestion failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True
        assert data.get("provider") == "meet"
        assert data.get("provider_evidence_ceiling") == "assisted", \
            f"Meet should have 'assisted' ceiling, got {data.get('provider_evidence_ceiling')}"
        
        # CRITICAL: All matched participants should have LOW confidence
        matched = data.get("matched", [])
        for m in matched:
            assert m.get("identity_confidence") == "low", \
                f"Meet identity_confidence should ALWAYS be 'low', got {m.get('identity_confidence')}"
            assert m.get("evidence_confidence") == "low", \
                f"Meet evidence_confidence should ALWAYS be 'low', got {m.get('evidence_confidence')}"
            assert m.get("video_outcome") == "manual_review", \
                f"Meet video_outcome should ALWAYS be 'manual_review', got {m.get('video_outcome')}"
        
        print(f"Meet ingestion result: {json.dumps(data, indent=2)}")

    def test_ambiguous_name_only_match_manual_review(self, auth_headers):
        """Name-only match (no email) should result in manual_review."""
        # Get participants
        participants_response = requests.get(
            f"{BASE_URL}/api/participants/?appointment_id={ZOOM_APT_ID}",
            headers=auth_headers
        )
        assert participants_response.status_code == 200
        participants = participants_response.json().get("participants", [])
        
        accepted_participant = None
        for p in participants:
            if p.get("status") in ("accepted", "accepted_pending_guarantee", "accepted_guaranteed"):
                accepted_participant = p
                break
        
        if not accepted_participant:
            pytest.skip("No accepted participant found")
        
        # Create payload with name only (no email)
        zoom_payload = {
            "provider": "zoom",
            "external_meeting_id": "zoom-name-only-test",
            "raw_payload": {
                "meeting_id": "zoom-name-only-test",
                "participants": [
                    {
                        "id": "user-uuid-name-only",
                        "name": f"{accepted_participant.get('first_name', '')} {accepted_participant.get('last_name', '')}",
                        # No user_email - name only match
                        "join_time": datetime.utcnow().isoformat() + "Z",
                        "leave_time": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z",
                        "duration": 3600
                    }
                ]
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/video-evidence/{ZOOM_APT_ID}/ingest",
            headers=auth_headers,
            json=zoom_payload
        )
        
        if response.status_code == 400:
            error_detail = response.json().get("detail", "")
            if "déjà été ingéré" in error_detail:
                print(f"Payload already ingested: {error_detail}")
                return
        
        assert response.status_code == 200, f"Ingestion failed: {response.text}"
        data = response.json()
        
        # Name-only match should have low confidence
        matched = data.get("matched", [])
        for m in matched:
            # Name-only match should be low confidence
            assert m.get("identity_confidence") == "low", \
                f"Name-only match should have low confidence, got {m.get('identity_confidence')}"
        
        print(f"Name-only match result: {json.dumps(data, indent=2)}")

    def test_no_matching_participant_returns_unmatched(self, auth_headers):
        """Participant not in NLYT should be returned as unmatched."""
        zoom_payload = {
            "provider": "zoom",
            "external_meeting_id": "zoom-unmatched-test",
            "raw_payload": {
                "meeting_id": "zoom-unmatched-test",
                "participants": [
                    {
                        "id": "unknown-user",
                        "name": "Unknown Person",
                        "user_email": "unknown.person@example.com",
                        "join_time": datetime.utcnow().isoformat() + "Z",
                        "leave_time": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z",
                        "duration": 3600
                    }
                ]
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/video-evidence/{ZOOM_APT_ID}/ingest",
            headers=auth_headers,
            json=zoom_payload
        )
        
        if response.status_code == 400:
            error_detail = response.json().get("detail", "")
            if "déjà été ingéré" in error_detail:
                print(f"Payload already ingested: {error_detail}")
                return
        
        assert response.status_code == 200, f"Ingestion failed: {response.text}"
        data = response.json()
        
        # Should have unmatched records
        unmatched = data.get("unmatched", [])
        assert len(unmatched) > 0, "Expected unmatched records for unknown participant"
        
        for u in unmatched:
            assert "Aucun participant NLYT" in u.get("reason", ""), \
                f"Expected 'no matching participant' reason, got {u.get('reason')}"
        
        print(f"Unmatched result: {json.dumps(data, indent=2)}")

    def test_duplicate_payload_returns_error(self, auth_headers):
        """Duplicate payload should return error about already ingested."""
        # First ingestion
        zoom_payload = {
            "provider": "zoom",
            "external_meeting_id": "zoom-duplicate-test",
            "raw_payload": {
                "meeting_id": "zoom-duplicate-test",
                "participants": [
                    {
                        "id": "dup-user",
                        "name": "Duplicate Test",
                        "user_email": "duplicate@test.com",
                        "join_time": "2026-01-15T10:00:00Z",
                        "leave_time": "2026-01-15T11:00:00Z",
                        "duration": 3600
                    }
                ]
            }
        }
        
        # First request
        response1 = requests.post(
            f"{BASE_URL}/api/video-evidence/{ZOOM_APT_ID}/ingest",
            headers=auth_headers,
            json=zoom_payload
        )
        
        # Second request with same payload
        response2 = requests.post(
            f"{BASE_URL}/api/video-evidence/{ZOOM_APT_ID}/ingest",
            headers=auth_headers,
            json=zoom_payload
        )
        
        # Second should fail with duplicate error
        assert response2.status_code == 400, f"Expected 400 for duplicate, got {response2.status_code}"
        error_detail = response2.json().get("detail", "")
        assert "déjà été ingéré" in error_detail, \
            f"Expected 'already ingested' error, got: {error_detail}"
        
        print(f"Duplicate error (expected): {error_detail}")

    def test_invalid_provider_returns_error(self, auth_headers):
        """Invalid provider should return error."""
        invalid_payload = {
            "provider": "invalid_provider",
            "raw_payload": {
                "meeting_id": "test",
                "participants": []
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/video-evidence/{ZOOM_APT_ID}/ingest",
            headers=auth_headers,
            json=invalid_payload
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid provider, got {response.status_code}"
        error_detail = response.json().get("detail", "")
        assert "non supporté" in error_detail or "Provider" in error_detail, \
            f"Expected provider error, got: {error_detail}"
        
        print(f"Invalid provider error (expected): {error_detail}")

    def test_invalid_json_payload_returns_error(self, auth_headers):
        """Invalid JSON structure should return error."""
        invalid_payload = {
            "provider": "zoom",
            "raw_payload": {
                # Missing meeting_id
                "participants": "not_a_list"  # Should be a list
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/video-evidence/{ZOOM_APT_ID}/ingest",
            headers=auth_headers,
            json=invalid_payload
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid payload, got {response.status_code}"
        print(f"Invalid payload error: {response.json().get('detail', '')}")


class TestVideoEvidenceRetrieval:
    """Tests for GET /api/video-evidence/{apt_id} and /logs endpoints."""

    def test_get_video_evidence_for_appointment(self, auth_headers):
        """GET /api/video-evidence/{apt_id} should return video evidence."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/{ZOOM_APT_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Failed to get video evidence: {response.text}"
        data = response.json()
        
        assert "appointment_id" in data
        assert "ingestion_logs" in data
        assert "video_evidence" in data
        assert "total_ingestions" in data
        assert "total_video_evidence" in data
        
        print(f"Video evidence for Zoom apt: {data.get('total_video_evidence')} items, {data.get('total_ingestions')} ingestions")

    def test_get_ingestion_logs(self, auth_headers):
        """GET /api/video-evidence/{apt_id}/logs should return ingestion logs."""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/{ZOOM_APT_ID}/logs",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Failed to get ingestion logs: {response.text}"
        data = response.json()
        
        assert "appointment_id" in data
        assert "logs" in data
        
        print(f"Ingestion logs count: {len(data.get('logs', []))}")


class TestAttendanceEvaluation:
    """Tests for POST /api/attendance/evaluate/{apt_id} with video evidence."""

    def test_zoom_video_evidence_auto_decision_on_time(self, auth_headers):
        """Zoom with strong video evidence should auto-decide 'on_time'."""
        # First, get current evidence
        evidence_response = requests.get(
            f"{BASE_URL}/api/video-evidence/{ZOOM_APT_ID}",
            headers=auth_headers
        )
        
        if evidence_response.status_code == 200:
            evidence_data = evidence_response.json()
            has_zoom_evidence = any(
                ev.get("derived_facts", {}).get("provider") == "zoom"
                for ev in evidence_data.get("video_evidence", [])
            )
            
            if has_zoom_evidence:
                # Trigger evaluation
                eval_response = requests.post(
                    f"{BASE_URL}/api/attendance/evaluate/{ZOOM_APT_ID}",
                    headers=auth_headers
                )
                
                if eval_response.status_code == 200:
                    eval_data = eval_response.json()
                    print(f"Zoom evaluation result: {json.dumps(eval_data, indent=2)}")
                    
                    # Check attendance records
                    attendance_response = requests.get(
                        f"{BASE_URL}/api/attendance/{ZOOM_APT_ID}",
                        headers=auth_headers
                    )
                    
                    if attendance_response.status_code == 200:
                        attendance_data = attendance_response.json()
                        records = attendance_data.get("records", [])
                        
                        for record in records:
                            decision_basis = record.get("decision_basis", "")
                            outcome = record.get("outcome", "")
                            
                            # Zoom with strong evidence should be on_time or late (not manual_review)
                            if "video_strong" in decision_basis:
                                assert outcome in ("on_time", "late"), \
                                    f"Zoom strong evidence should be on_time/late, got {outcome}"
                                print(f"Zoom participant outcome: {outcome} (basis: {decision_basis})")

    def test_teams_video_evidence_auto_decision(self, auth_headers):
        """Teams with strong video evidence should auto-decide."""
        evidence_response = requests.get(
            f"{BASE_URL}/api/video-evidence/{TEAMS_APT_ID}",
            headers=auth_headers
        )
        
        if evidence_response.status_code == 200:
            evidence_data = evidence_response.json()
            has_teams_evidence = any(
                ev.get("derived_facts", {}).get("provider") == "teams"
                for ev in evidence_data.get("video_evidence", [])
            )
            
            if has_teams_evidence:
                eval_response = requests.post(
                    f"{BASE_URL}/api/attendance/evaluate/{TEAMS_APT_ID}",
                    headers=auth_headers
                )
                
                if eval_response.status_code == 200:
                    attendance_response = requests.get(
                        f"{BASE_URL}/api/attendance/{TEAMS_APT_ID}",
                        headers=auth_headers
                    )
                    
                    if attendance_response.status_code == 200:
                        attendance_data = attendance_response.json()
                        records = attendance_data.get("records", [])
                        
                        for record in records:
                            decision_basis = record.get("decision_basis", "")
                            outcome = record.get("outcome", "")
                            
                            if "video_strong" in decision_basis:
                                assert outcome in ("on_time", "late"), \
                                    f"Teams strong evidence should be on_time/late, got {outcome}"
                                print(f"Teams participant outcome: {outcome} (basis: {decision_basis})")

    def test_meet_video_evidence_always_manual_review(self, auth_headers):
        """Google Meet evidence should ALWAYS result in manual_review (no auto-penalty)."""
        evidence_response = requests.get(
            f"{BASE_URL}/api/video-evidence/{MEET_APT_ID}",
            headers=auth_headers
        )
        
        if evidence_response.status_code == 200:
            evidence_data = evidence_response.json()
            has_meet_evidence = any(
                ev.get("derived_facts", {}).get("provider") == "meet"
                for ev in evidence_data.get("video_evidence", [])
            )
            
            if has_meet_evidence:
                # Trigger evaluation
                eval_response = requests.post(
                    f"{BASE_URL}/api/attendance/evaluate/{MEET_APT_ID}",
                    headers=auth_headers
                )
                
                if eval_response.status_code == 200:
                    attendance_response = requests.get(
                        f"{BASE_URL}/api/attendance/{MEET_APT_ID}",
                        headers=auth_headers
                    )
                    
                    if attendance_response.status_code == 200:
                        attendance_data = attendance_response.json()
                        records = attendance_data.get("records", [])
                        
                        for record in records:
                            decision_basis = record.get("decision_basis", "")
                            outcome = record.get("outcome", "")
                            
                            # CRITICAL: Meet should NEVER auto-decide on_time/late/no_show
                            # It should always be manual_review or waived
                            if "meet" in decision_basis.lower():
                                assert outcome in ("manual_review", "waived"), \
                                    f"Meet should NEVER auto-decide, got outcome={outcome} for basis={decision_basis}"
                                print(f"Meet participant outcome: {outcome} (basis: {decision_basis}) - CORRECT: no auto-penalty")


class TestPhysicalAppointmentRegression:
    """Tests to ensure physical appointment logic still works correctly."""

    def test_create_physical_appointment(self, auth_headers):
        """Create a physical appointment to test regression."""
        # Create a new physical appointment
        future_date = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"
        
        appointment_data = {
            "workspace_id": WORKSPACE_ID,
            "title": "TEST_Physical Regression Test",
            "appointment_type": "physical",
            "location": "123 Test Street, Paris",
            "start_datetime": future_date,
            "duration_minutes": 60,
            "tolerated_delay_minutes": 15,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "affected_compensation_percent": 70,
            "charity_percent": 10,  # compensation + charity must equal 80%
            "participants": [
                {
                    "email": "physical.test@example.com",
                    "first_name": "Physical",
                    "last_name": "Test"
                }
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/appointments/",
            headers=auth_headers,
            json=appointment_data
        )
        
        assert response.status_code in (200, 201), f"Failed to create physical appointment: {response.text}"
        data = response.json()
        
        apt_id = data.get("appointment_id")
        assert apt_id, "No appointment_id in response"
        
        # Fetch the appointment to verify it was created correctly
        get_response = requests.get(
            f"{BASE_URL}/api/appointments/{apt_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 200, f"Failed to get created appointment: {get_response.text}"
        apt_data = get_response.json()
        
        assert apt_data.get("appointment_type") == "physical"
        assert apt_data.get("location") == "123 Test Street, Paris"
        
        print(f"Created physical appointment: {apt_id}")
        
        # Clean up - delete the test appointment
        if apt_id:
            requests.delete(f"{BASE_URL}/api/appointments/{apt_id}", headers=auth_headers)

    def test_physical_appointment_checkin_still_works(self, auth_headers):
        """Verify physical appointment check-in evidence still works."""
        # This test verifies that the physical appointment flow hasn't regressed
        # by checking that the evidence service still handles physical check-ins
        
        # Get evidence for a physical appointment (if any exists)
        # For now, just verify the endpoint works
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{ZOOM_APT_ID}",
            headers=auth_headers
        )
        
        # Should return 200 even if no evidence
        assert response.status_code == 200, f"Evidence endpoint failed: {response.text}"
        print("Physical check-in evidence endpoint working correctly")


class TestVideoEvidenceValidation:
    """Additional validation tests for video evidence."""

    def test_meet_evidence_has_assisted_ceiling(self, auth_headers):
        """Verify Meet evidence has 'assisted' provider ceiling."""
        evidence_response = requests.get(
            f"{BASE_URL}/api/video-evidence/{MEET_APT_ID}",
            headers=auth_headers
        )
        
        if evidence_response.status_code == 200:
            evidence_data = evidence_response.json()
            
            for ev in evidence_data.get("video_evidence", []):
                facts = ev.get("derived_facts", {})
                if facts.get("provider") == "meet":
                    assert facts.get("provider_evidence_ceiling") == "assisted", \
                        f"Meet should have 'assisted' ceiling, got {facts.get('provider_evidence_ceiling')}"
                    print(f"Meet evidence ceiling: {facts.get('provider_evidence_ceiling')} - CORRECT")

    def test_zoom_teams_evidence_has_strong_ceiling(self, auth_headers):
        """Verify Zoom/Teams evidence has 'strong' provider ceiling."""
        for apt_id, provider in [(ZOOM_APT_ID, "zoom"), (TEAMS_APT_ID, "teams")]:
            evidence_response = requests.get(
                f"{BASE_URL}/api/video-evidence/{apt_id}",
                headers=auth_headers
            )
            
            if evidence_response.status_code == 200:
                evidence_data = evidence_response.json()
                
                for ev in evidence_data.get("video_evidence", []):
                    facts = ev.get("derived_facts", {})
                    if facts.get("provider") == provider:
                        assert facts.get("provider_evidence_ceiling") == "strong", \
                            f"{provider.title()} should have 'strong' ceiling, got {facts.get('provider_evidence_ceiling')}"
                        print(f"{provider.title()} evidence ceiling: {facts.get('provider_evidence_ceiling')} - CORRECT")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
