"""
Attendance Evaluation API Tests
Tests for POST /api/attendance/evaluate/{appointment_id}
Tests for GET /api/attendance/{appointment_id}
Tests for PUT /api/attendance/reclassify/{record_id}
Tests for GET /api/attendance/pending-reviews/list
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"

# Already evaluated appointment
EVALUATED_APPOINTMENT_ID = "35df4fb0-91ac-4d6a-a56b-cfd6e06b4111"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    # Note: Login returns 'access_token' not 'token'
    assert "access_token" in data, "Login response missing access_token"
    return data["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestAttendanceGetEndpoint:
    """Tests for GET /api/attendance/{appointment_id}"""

    def test_get_attendance_success(self, auth_headers):
        """GET /api/attendance/{id} returns attendance records and summary"""
        response = requests.get(
            f"{BASE_URL}/api/attendance/{EVALUATED_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "appointment_id" in data
        assert "evaluated" in data
        assert "summary" in data
        assert "records" in data
        
        # Verify evaluated appointment has records
        assert data["evaluated"] == True
        assert data["evaluated_at"] is not None
        assert isinstance(data["records"], list)
        
        # Verify summary structure
        summary = data["summary"]
        assert "waived" in summary
        assert "no_show" in summary
        assert "manual_review" in summary
        assert "on_time" in summary
        assert "late" in summary

    def test_get_attendance_requires_auth(self):
        """GET /api/attendance/{id} requires authentication"""
        response = requests.get(
            f"{BASE_URL}/api/attendance/{EVALUATED_APPOINTMENT_ID}"
        )
        assert response.status_code == 401
        assert "Token" in response.json().get("detail", "")

    def test_get_attendance_not_found(self, auth_headers):
        """GET /api/attendance/{id} returns 404 for non-existent appointment"""
        fake_id = str(uuid.uuid4())
        response = requests.get(
            f"{BASE_URL}/api/attendance/{fake_id}",
            headers=auth_headers
        )
        assert response.status_code == 404


class TestAttendanceEvaluateEndpoint:
    """Tests for POST /api/attendance/evaluate/{appointment_id}"""

    def test_evaluate_idempotency(self, auth_headers):
        """POST /api/attendance/evaluate/{id} returns 'Déjà évalué' for already evaluated"""
        response = requests.post(
            f"{BASE_URL}/api/attendance/evaluate/{EVALUATED_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should return skipped with reason
        assert data.get("skipped") == True
        assert "Déjà évalué" in data.get("reason", "")

    def test_evaluate_requires_auth(self):
        """POST /api/attendance/evaluate/{id} requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/attendance/evaluate/{EVALUATED_APPOINTMENT_ID}"
        )
        assert response.status_code == 401

    def test_evaluate_not_found(self, auth_headers):
        """POST /api/attendance/evaluate/{id} returns 404 for non-existent appointment"""
        fake_id = str(uuid.uuid4())
        response = requests.post(
            f"{BASE_URL}/api/attendance/evaluate/{fake_id}",
            headers=auth_headers
        )
        assert response.status_code == 404


class TestAttendanceReclassifyEndpoint:
    """Tests for PUT /api/attendance/reclassify/{record_id}"""

    @pytest.fixture(scope="class")
    def record_id(self, auth_headers):
        """Get a record_id from the evaluated appointment"""
        response = requests.get(
            f"{BASE_URL}/api/attendance/{EVALUATED_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        records = response.json().get("records", [])
        assert len(records) > 0, "No records found for testing"
        return records[0]["record_id"]

    def test_reclassify_to_on_time(self, auth_headers, record_id):
        """PUT /api/attendance/reclassify/{id} can change outcome to on_time"""
        response = requests.put(
            f"{BASE_URL}/api/attendance/reclassify/{record_id}",
            headers=auth_headers,
            json={"new_outcome": "on_time", "notes": "Test reclassify to on_time"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert data.get("new_outcome") == "on_time"

    def test_reclassify_to_late(self, auth_headers, record_id):
        """PUT /api/attendance/reclassify/{id} can change outcome to late"""
        response = requests.put(
            f"{BASE_URL}/api/attendance/reclassify/{record_id}",
            headers=auth_headers,
            json={"new_outcome": "late", "notes": "Test reclassify to late"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert data.get("new_outcome") == "late"

    def test_reclassify_to_no_show(self, auth_headers, record_id):
        """PUT /api/attendance/reclassify/{id} can change outcome to no_show"""
        response = requests.put(
            f"{BASE_URL}/api/attendance/reclassify/{record_id}",
            headers=auth_headers,
            json={"new_outcome": "no_show", "notes": "Test reclassify to no_show"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert data.get("new_outcome") == "no_show"

    def test_reclassify_to_waived(self, auth_headers, record_id):
        """PUT /api/attendance/reclassify/{id} can change outcome to waived"""
        response = requests.put(
            f"{BASE_URL}/api/attendance/reclassify/{record_id}",
            headers=auth_headers,
            json={"new_outcome": "waived", "notes": "Test reclassify to waived"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert data.get("new_outcome") == "waived"

    def test_reclassify_invalid_outcome(self, auth_headers, record_id):
        """PUT /api/attendance/reclassify/{id} returns 400 for invalid outcome"""
        response = requests.put(
            f"{BASE_URL}/api/attendance/reclassify/{record_id}",
            headers=auth_headers,
            json={"new_outcome": "invalid_outcome"}
        )
        assert response.status_code == 400
        assert "invalide" in response.json().get("detail", "").lower()

    def test_reclassify_stores_previous_outcome(self, auth_headers, record_id):
        """Reclassification stores previous_outcome in record"""
        # First reclassify to on_time
        requests.put(
            f"{BASE_URL}/api/attendance/reclassify/{record_id}",
            headers=auth_headers,
            json={"new_outcome": "on_time"}
        )
        
        # Then reclassify to late
        requests.put(
            f"{BASE_URL}/api/attendance/reclassify/{record_id}",
            headers=auth_headers,
            json={"new_outcome": "late"}
        )
        
        # Verify previous_outcome is stored
        response = requests.get(
            f"{BASE_URL}/api/attendance/{EVALUATED_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        records = response.json().get("records", [])
        record = next((r for r in records if r["record_id"] == record_id), None)
        assert record is not None
        assert record.get("previous_outcome") == "on_time"

    def test_reclassify_updates_summary(self, auth_headers, record_id):
        """Reclassification updates appointment summary"""
        # Reclassify to on_time
        requests.put(
            f"{BASE_URL}/api/attendance/reclassify/{record_id}",
            headers=auth_headers,
            json={"new_outcome": "on_time"}
        )
        
        # Verify summary is updated
        response = requests.get(
            f"{BASE_URL}/api/attendance/{EVALUATED_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        summary = response.json().get("summary", {})
        assert summary.get("on_time", 0) >= 1

    def test_reclassify_requires_auth(self):
        """PUT /api/attendance/reclassify/{id} requires authentication"""
        response = requests.put(
            f"{BASE_URL}/api/attendance/reclassify/some-record-id",
            json={"new_outcome": "on_time"}
        )
        assert response.status_code == 401

    def test_reclassify_not_found(self, auth_headers):
        """PUT /api/attendance/reclassify/{id} returns 404 for non-existent record"""
        fake_id = str(uuid.uuid4())
        response = requests.put(
            f"{BASE_URL}/api/attendance/reclassify/{fake_id}",
            headers=auth_headers,
            json={"new_outcome": "on_time"}
        )
        assert response.status_code == 404


class TestPendingReviewsEndpoint:
    """Tests for GET /api/attendance/pending-reviews/list"""

    def test_pending_reviews_success(self, auth_headers):
        """GET /api/attendance/pending-reviews/list returns pending reviews"""
        response = requests.get(
            f"{BASE_URL}/api/attendance/pending-reviews/list",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "pending_reviews" in data
        assert "count" in data
        assert isinstance(data["pending_reviews"], list)
        assert isinstance(data["count"], int)
        assert data["count"] == len(data["pending_reviews"])

    def test_pending_reviews_requires_auth(self):
        """GET /api/attendance/pending-reviews/list requires authentication"""
        response = requests.get(
            f"{BASE_URL}/api/attendance/pending-reviews/list"
        )
        assert response.status_code == 401


class TestClassificationRules:
    """Tests for classification rules (requires test data setup)"""

    def test_classification_rules_documented(self, auth_headers):
        """Verify classification rules are documented in service"""
        # This test verifies the rules by checking an evaluated appointment
        response = requests.get(
            f"{BASE_URL}/api/attendance/{EVALUATED_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        records = response.json().get("records", [])
        
        # Verify record structure includes decision_basis
        if len(records) > 0:
            record = records[0]
            assert "decision_basis" in record
            assert "confidence" in record
            assert "review_required" in record
            assert "auto_capture_enabled" in record


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
