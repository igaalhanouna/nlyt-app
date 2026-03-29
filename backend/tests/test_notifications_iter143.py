"""
Test suite for in-app notification system (iteration 143)
Tests: notification counts, unread IDs, mark-as-read, auth requirements
Uses session-scoped fixtures to avoid rate limiting
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
ADMIN_EMAIL = "testuser_audit@nlyt.app"
ADMIN_PASSWORD = "TestAudit123!"
PARTICIPANT_EMAIL = "igaal@hotmail.com"
PARTICIPANT_PASSWORD = "Test123!"


# ═══════════════════════════════════════════════════════════════
# Session-scoped fixtures to avoid rate limiting
# ═══════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def admin_session():
    """Login as admin once per session"""
    time.sleep(2)  # Small delay to avoid rate limiting
    login_res = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if login_res.status_code != 200:
        pytest.skip(f"Admin login failed: {login_res.status_code} - {login_res.text}")
    data = login_res.json()
    token = data.get("access_token")
    user = data.get("user", {})
    print(f"\n[SESSION] Logged in as admin: {user.get('email')}")
    return {
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
        "user": user
    }


@pytest.fixture(scope="session")
def participant_session():
    """Login as participant once per session"""
    time.sleep(2)  # Small delay to avoid rate limiting
    login_res = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": PARTICIPANT_EMAIL, "password": PARTICIPANT_PASSWORD}
    )
    if login_res.status_code != 200:
        pytest.skip(f"Participant login failed: {login_res.status_code} - {login_res.text}")
    data = login_res.json()
    token = data.get("access_token")
    user = data.get("user", {})
    print(f"\n[SESSION] Logged in as participant: {user.get('email')}")
    return {
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
        "user": user
    }


# ═══════════════════════════════════════════════════════════════
# Auth requirement tests (no login needed)
# ═══════════════════════════════════════════════════════════════

class TestNotificationAuth:
    """Test authentication requirements for notification endpoints"""

    def test_counts_requires_auth(self):
        """GET /api/notifications/counts returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/notifications/counts")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: /api/notifications/counts returns 401 without auth")

    def test_unread_ids_requires_auth(self):
        """GET /api/notifications/unread-ids/decision returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/notifications/unread-ids/decision")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: /api/notifications/unread-ids/decision returns 401 without auth")

    def test_mark_read_requires_auth(self):
        """POST /api/notifications/mark-read returns 401 without auth"""
        response = requests.post(
            f"{BASE_URL}/api/notifications/mark-read",
            json={"event_type": "decision", "reference_id": "test-id"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: /api/notifications/mark-read returns 401 without auth")


# ═══════════════════════════════════════════════════════════════
# Admin user tests
# ═══════════════════════════════════════════════════════════════

class TestNotificationCountsAdmin:
    """Test notification counts for admin user"""

    def test_counts_returns_correct_structure(self, admin_session):
        """GET /api/notifications/counts returns {decisions: N, disputes: N}"""
        response = requests.get(
            f"{BASE_URL}/api/notifications/counts",
            headers=admin_session["headers"]
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "decisions" in data, "Expected 'decisions' key in response"
        assert "disputes" in data, "Expected 'disputes' key in response"
        assert isinstance(data["decisions"], int), "decisions should be an integer"
        assert isinstance(data["disputes"], int), "disputes should be an integer"
        print(f"PASS: Counts structure correct - decisions: {data['decisions']}, disputes: {data['disputes']}")

    def test_admin_notification_counts(self, admin_session):
        """Admin user notification counts are valid"""
        response = requests.get(
            f"{BASE_URL}/api/notifications/counts",
            headers=admin_session["headers"]
        )
        assert response.status_code == 200
        data = response.json()
        print(f"Admin unread decisions: {data['decisions']}, disputes: {data['disputes']}")
        assert data["decisions"] >= 0, "decisions count should be >= 0"
        assert data["disputes"] >= 0, "disputes count should be >= 0"


class TestNotificationValidation:
    """Test input validation for notification endpoints"""

    def test_invalid_event_type_returns_400(self, admin_session):
        """GET /api/notifications/unread-ids/{invalid} returns 400"""
        response = requests.get(
            f"{BASE_URL}/api/notifications/unread-ids/invalid_type",
            headers=admin_session["headers"]
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "detail" in data, "Expected error detail in response"
        print(f"PASS: Invalid event_type returns 400 with detail: {data.get('detail')}")


class TestNotificationUnreadIds:
    """Test unread IDs endpoint"""

    def test_unread_ids_decision_returns_list(self, admin_session):
        """GET /api/notifications/unread-ids/decision returns {unread_ids: [...]}"""
        response = requests.get(
            f"{BASE_URL}/api/notifications/unread-ids/decision",
            headers=admin_session["headers"]
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "unread_ids" in data, "Expected 'unread_ids' key in response"
        assert isinstance(data["unread_ids"], list), "unread_ids should be a list"
        print(f"PASS: Decision unread_ids: {data['unread_ids']}")

    def test_unread_ids_dispute_update_returns_list(self, admin_session):
        """GET /api/notifications/unread-ids/dispute_update returns {unread_ids: [...]}"""
        response = requests.get(
            f"{BASE_URL}/api/notifications/unread-ids/dispute_update",
            headers=admin_session["headers"]
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "unread_ids" in data, "Expected 'unread_ids' key in response"
        assert isinstance(data["unread_ids"], list), "unread_ids should be a list"
        print(f"PASS: Dispute update unread_ids: {data['unread_ids']}")


class TestNotificationMarkRead:
    """Test mark-as-read functionality"""

    def test_mark_read_returns_marked_count(self, admin_session):
        """POST /api/notifications/mark-read returns {marked: N}"""
        response = requests.post(
            f"{BASE_URL}/api/notifications/mark-read",
            headers=admin_session["headers"],
            json={"event_type": "decision", "reference_id": "nonexistent-id"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "marked" in data, "Expected 'marked' key in response"
        assert isinstance(data["marked"], int), "marked should be an integer"
        print(f"PASS: mark-read returns marked count: {data['marked']}")


# ═══════════════════════════════════════════════════════════════
# Participant user tests
# ═══════════════════════════════════════════════════════════════

class TestNotificationCountsParticipant:
    """Test notification counts for participant user"""

    def test_participant_counts_structure(self, participant_session):
        """Participant can access notification counts"""
        response = requests.get(
            f"{BASE_URL}/api/notifications/counts",
            headers=participant_session["headers"]
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "decisions" in data
        assert "disputes" in data
        print(f"PASS: Participant counts - decisions: {data['decisions']}, disputes: {data['disputes']}")

    def test_participant_unread_ids(self, participant_session):
        """Participant can access unread IDs"""
        response = requests.get(
            f"{BASE_URL}/api/notifications/unread-ids/decision",
            headers=participant_session["headers"]
        )
        assert response.status_code == 200
        data = response.json()
        assert "unread_ids" in data
        print(f"PASS: Participant decision unread_ids: {data['unread_ids']}")


# ═══════════════════════════════════════════════════════════════
# Related endpoints tests
# ═══════════════════════════════════════════════════════════════

class TestDecisionsEndpoint:
    """Test the decisions endpoint that uses notifications"""

    def test_decisions_mine_endpoint(self, admin_session):
        """GET /api/disputes/decisions/mine returns decisions list"""
        response = requests.get(
            f"{BASE_URL}/api/disputes/decisions/mine",
            headers=admin_session["headers"]
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "decisions" in data, "Expected 'decisions' key in response"
        assert isinstance(data["decisions"], list), "decisions should be a list"
        print(f"PASS: /api/disputes/decisions/mine returns {len(data['decisions'])} decisions")


class TestDisputesMineEndpoint:
    """Test the disputes/mine endpoint"""

    def test_disputes_mine_endpoint(self, admin_session):
        """GET /api/disputes/mine returns disputes list"""
        response = requests.get(
            f"{BASE_URL}/api/disputes/mine",
            headers=admin_session["headers"]
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "disputes" in data, "Expected 'disputes' key in response"
        assert isinstance(data["disputes"], list), "disputes should be a list"
        print(f"PASS: /api/disputes/mine returns {len(data['disputes'])} disputes")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
