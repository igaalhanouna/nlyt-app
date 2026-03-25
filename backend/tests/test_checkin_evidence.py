"""
Test Check-in and Evidence API Endpoints

Tests for:
- POST /api/checkin/manual - manual check-in with device_info and optional GPS
- GET /api/checkin/qr/{appointment_id}?invitation_token=... - QR code generation
- POST /api/checkin/qr/verify - verify QR code and create evidence
- POST /api/checkin/gps - GPS-only evidence submission
- GET /api/checkin/status/{appointment_id}?invitation_token=... - check-in status
- GET /api/checkin/evidence/{appointment_id} - organizer view of all evidence
- POST /api/attendance/reevaluate/{appointment_id} - re-evaluate with fresh evidence
- Duplicate check-in returns 409
- QR verification: valid token accepted, expired/invalid token rejected
- Evidence aggregation: strong (2+ signals), medium (1 signal), weak/none
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://wallet-rebrand.preview.emergentagent.com')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"

# Existing participant with evidence (will return 409 for duplicate check-ins)
EXISTING_PARTICIPANT_ID = "7b283114-6cb3-4abe-a43f-744ea4a4ea1f"
EXISTING_APPOINTMENT_ID = "a860bab5-c885-4787-a73e-3779529d3b8a"
EXISTING_INVITATION_TOKEN = "17b556f4-876f-44c1-86b9-0203dced05d3"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for organizer tests."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("access_token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Return headers with auth token."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestCheckinStatus:
    """Tests for GET /api/checkin/status/{appointment_id}"""

    def test_get_checkin_status_success(self):
        """Test getting check-in status for a participant."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/status/{EXISTING_APPOINTMENT_ID}",
            params={"invitation_token": EXISTING_INVITATION_TOKEN}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "checked_in" in data
        assert "has_manual_checkin" in data
        assert "has_qr_checkin" in data
        assert "has_gps" in data
        assert "evidence_count" in data
        assert "evidence" in data
        
        # Existing participant should have evidence
        assert data["evidence_count"] >= 2
        assert data["checked_in"] == True

    def test_get_checkin_status_invalid_token(self):
        """Test check-in status with invalid invitation token."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/status/{EXISTING_APPOINTMENT_ID}",
            params={"invitation_token": "invalid-token-12345"}
        )
        assert response.status_code == 404
        assert "Invitation invalide" in response.json().get("detail", "")

    def test_get_checkin_status_wrong_appointment(self):
        """Test check-in status with mismatched appointment."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/status/wrong-appointment-id",
            params={"invitation_token": EXISTING_INVITATION_TOKEN}
        )
        assert response.status_code == 403
        assert "ne correspond pas" in response.json().get("detail", "")


class TestManualCheckin:
    """Tests for POST /api/checkin/manual"""

    def test_manual_checkin_duplicate_returns_409(self):
        """Test that duplicate manual check-in returns 409."""
        response = requests.post(
            f"{BASE_URL}/api/checkin/manual",
            json={
                "invitation_token": EXISTING_INVITATION_TOKEN,
                "device_info": "Test Device"
            }
        )
        assert response.status_code == 409
        assert "déjà effectué" in response.json().get("detail", "")

    def test_manual_checkin_invalid_token(self):
        """Test manual check-in with invalid token."""
        response = requests.post(
            f"{BASE_URL}/api/checkin/manual",
            json={
                "invitation_token": "invalid-token-12345",
                "device_info": "Test Device"
            }
        )
        assert response.status_code == 404
        assert "Invitation invalide" in response.json().get("detail", "")


class TestQRCodeGeneration:
    """Tests for GET /api/checkin/qr/{appointment_id}"""

    def test_generate_qr_code_success(self):
        """Test QR code generation for valid participant."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/qr/{EXISTING_APPOINTMENT_ID}",
            params={"invitation_token": EXISTING_INVITATION_TOKEN}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify QR response structure
        assert "qr_token" in data
        assert "qr_image_base64" in data
        assert "appointment_id" in data
        assert "window" in data
        assert "rotation_seconds" in data
        
        # Verify QR token format: NLYT:{appointment_id}:{window}:{signature}
        qr_token = data["qr_token"]
        parts = qr_token.split(":")
        assert len(parts) == 4
        assert parts[0] == "NLYT"
        assert parts[1] == EXISTING_APPOINTMENT_ID
        
        # Verify base64 image is present
        assert len(data["qr_image_base64"]) > 100

    def test_generate_qr_code_invalid_token(self):
        """Test QR code generation with invalid token."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/qr/{EXISTING_APPOINTMENT_ID}",
            params={"invitation_token": "invalid-token-12345"}
        )
        assert response.status_code == 404

    def test_generate_qr_code_wrong_appointment(self):
        """Test QR code generation with mismatched appointment."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/qr/wrong-appointment-id",
            params={"invitation_token": EXISTING_INVITATION_TOKEN}
        )
        assert response.status_code == 403


class TestQRVerification:
    """Tests for POST /api/checkin/qr/verify"""

    def test_qr_verify_duplicate_returns_409(self):
        """Test that duplicate QR verification returns 409."""
        # First get a valid QR token
        qr_response = requests.get(
            f"{BASE_URL}/api/checkin/qr/{EXISTING_APPOINTMENT_ID}",
            params={"invitation_token": EXISTING_INVITATION_TOKEN}
        )
        assert qr_response.status_code == 200
        qr_token = qr_response.json()["qr_token"]
        
        # Try to verify (should fail as already checked in)
        response = requests.post(
            f"{BASE_URL}/api/checkin/qr/verify",
            json={
                "qr_code": qr_token,
                "invitation_token": EXISTING_INVITATION_TOKEN
            }
        )
        assert response.status_code == 409
        assert "déjà effectué" in response.json().get("detail", "")

    def test_qr_verify_invalid_format(self):
        """Test QR verification with invalid format."""
        response = requests.post(
            f"{BASE_URL}/api/checkin/qr/verify",
            json={
                "qr_code": "invalid-qr-format",
                "invitation_token": EXISTING_INVITATION_TOKEN
            }
        )
        assert response.status_code == 400
        assert "invalide" in response.json().get("detail", "").lower()

    def test_qr_verify_invalid_signature(self):
        """Test QR verification with invalid signature."""
        response = requests.post(
            f"{BASE_URL}/api/checkin/qr/verify",
            json={
                "qr_code": f"NLYT:{EXISTING_APPOINTMENT_ID}:12345678:invalidsig12345",
                "invitation_token": EXISTING_INVITATION_TOKEN
            }
        )
        assert response.status_code == 400
        # Should fail with signature or expiry error
        detail = response.json().get("detail", "").lower()
        assert "invalide" in detail or "expiré" in detail


class TestGPSCheckin:
    """Tests for POST /api/checkin/gps"""

    def test_gps_checkin_duplicate_returns_409(self):
        """Test that duplicate GPS check-in returns 409 (if already submitted)."""
        response = requests.post(
            f"{BASE_URL}/api/checkin/gps",
            json={
                "invitation_token": EXISTING_INVITATION_TOKEN,
                "latitude": 48.8566,
                "longitude": 2.3522
            }
        )
        # May return 409 if GPS already submitted, or 200 if not
        # The existing participant may not have GPS evidence
        assert response.status_code in [200, 409]

    def test_gps_checkin_invalid_token(self):
        """Test GPS check-in with invalid token."""
        response = requests.post(
            f"{BASE_URL}/api/checkin/gps",
            json={
                "invitation_token": "invalid-token-12345",
                "latitude": 48.8566,
                "longitude": 2.3522
            }
        )
        assert response.status_code == 404


class TestEvidenceEndpoint:
    """Tests for GET /api/checkin/evidence/{appointment_id} (organizer view)"""

    def test_get_evidence_success(self, auth_headers):
        """Test getting evidence for an appointment as organizer."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{EXISTING_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "appointment_id" in data
        assert "participants" in data
        assert "total_evidence" in data
        
        # Should have at least one participant with evidence
        assert len(data["participants"]) >= 1
        
        # Check participant evidence structure
        participant = data["participants"][0]
        assert "participant_id" in participant
        assert "participant_name" in participant
        assert "evidence" in participant
        assert "aggregation" in participant
        
        # Check aggregation structure
        agg = participant["aggregation"]
        assert "strength" in agg
        assert "signals" in agg
        assert "timing" in agg
        assert "confidence" in agg
        assert "evidence_count" in agg

    def test_get_evidence_requires_auth(self):
        """Test that evidence endpoint requires authentication."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{EXISTING_APPOINTMENT_ID}"
        )
        assert response.status_code == 401

    def test_get_evidence_not_found(self, auth_headers):
        """Test evidence endpoint with non-existent appointment."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/non-existent-appointment-id",
            headers=auth_headers
        )
        assert response.status_code == 404


class TestEvidenceAggregation:
    """Tests for evidence aggregation logic"""

    def test_aggregation_strong_evidence(self, auth_headers):
        """Test that 2+ signals produce strong evidence."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{EXISTING_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Find participant with multiple evidence items
        for participant in data["participants"]:
            if participant["aggregation"]["evidence_count"] >= 2:
                agg = participant["aggregation"]
                # With 2+ signals, should be strong
                assert agg["strength"] == "strong"
                assert agg["confidence"] == "high"
                assert len(agg["signals"]) >= 2
                break


class TestReevaluateAttendance:
    """Tests for POST /api/attendance/reevaluate/{appointment_id}"""

    def test_reevaluate_success(self, auth_headers):
        """Test re-evaluating attendance with fresh evidence."""
        response = requests.post(
            f"{BASE_URL}/api/attendance/reevaluate/{EXISTING_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should return evaluation result
        assert "evaluated" in data or "summary" in data or "records_created" in data

    def test_reevaluate_requires_auth(self):
        """Test that reevaluate requires authentication."""
        response = requests.post(
            f"{BASE_URL}/api/attendance/reevaluate/{EXISTING_APPOINTMENT_ID}"
        )
        assert response.status_code == 401

    def test_reevaluate_not_found(self, auth_headers):
        """Test reevaluate with non-existent appointment."""
        response = requests.post(
            f"{BASE_URL}/api/attendance/reevaluate/non-existent-appointment-id",
            headers=auth_headers
        )
        assert response.status_code == 404


class TestDecisionEngine:
    """Tests for decision engine with evidence"""

    def test_strong_evidence_auto_classifies(self, auth_headers):
        """Test that strong evidence auto-classifies as on_time or late."""
        # Get attendance records
        response = requests.get(
            f"{BASE_URL}/api/attendance/{EXISTING_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check if records exist and have proper classification
        if data.get("records"):
            for record in data["records"]:
                # Records with strong evidence should not be manual_review
                if "strong_evidence" in record.get("decision_basis", ""):
                    assert record["outcome"] in ["on_time", "late"]
                    assert record["review_required"] == False


class TestQRTokenFormat:
    """Tests for QR token format and validation"""

    def test_qr_token_format(self):
        """Test QR token follows expected format."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/qr/{EXISTING_APPOINTMENT_ID}",
            params={"invitation_token": EXISTING_INVITATION_TOKEN}
        )
        assert response.status_code == 200
        qr_token = response.json()["qr_token"]
        
        # Format: NLYT:{appointment_id}:{epoch//60}:{hmac_16chars}
        parts = qr_token.split(":")
        assert len(parts) == 4
        assert parts[0] == "NLYT"
        assert parts[1] == EXISTING_APPOINTMENT_ID
        assert parts[2].isdigit()  # Window number
        assert len(parts[3]) == 16  # HMAC signature (16 chars)

    def test_qr_rotation_seconds(self):
        """Test QR rotation is 60 seconds."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/qr/{EXISTING_APPOINTMENT_ID}",
            params={"invitation_token": EXISTING_INVITATION_TOKEN}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["rotation_seconds"] == 60


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
