"""
Test Teams Level Feature — Tests for the new 'level' field in provider-status API.

The 'level' field replaces the old 'connection_mode' field and indicates:
- 'advanced': Outlook connected with has_online_meetings_scope=True (Microsoft 365 Pro)
- 'standard': Outlook connected without OnlineMeetings scope
- 'application': Legacy Azure AD form configuration (no Outlook)
- null: No Outlook connection and no Azure AD configuration

Test users:
- Clara (advanced): clara.deschamps@demo-nlyt.fr - Outlook + has_online_meetings_scope=True
- Sandrine (standard): sandrine.bonnet@demo-nlyt.fr - Outlook connected, no OnlineMeetings scope
- Marie (none): marie.morel@demo-nlyt.fr - No Outlook connection
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PASSWORD = "Demo2026!"


class TestTeamsLevelFeature:
    """Tests for Teams 'level' field in provider-status API"""

    @pytest.fixture(scope="class")
    def clara_token(self):
        """Login as Clara (advanced level - Outlook + has_online_meetings_scope)"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clara.deschamps@demo-nlyt.fr",
            "password": PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Clara login failed: {response.status_code}")
        return response.json().get("access_token")

    @pytest.fixture(scope="class")
    def sandrine_token(self):
        """Login as Sandrine (standard level - Outlook without OnlineMeetings scope)"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "sandrine.bonnet@demo-nlyt.fr",
            "password": PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Sandrine login failed: {response.status_code}")
        return response.json().get("access_token")

    @pytest.fixture(scope="class")
    def marie_token(self):
        """Login as Marie (no level - no Outlook connection)"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "marie.morel@demo-nlyt.fr",
            "password": PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Marie login failed: {response.status_code}")
        return response.json().get("access_token")

    # ========== Clara (Advanced Level) Tests ==========

    def test_clara_teams_level_is_advanced(self, clara_token):
        """Clara should have Teams level='advanced' (Outlook + has_online_meetings_scope)"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {clara_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["teams"]["level"] == "advanced", f"Expected 'advanced', got {data['teams']['level']}"

    def test_clara_teams_has_attendance_true(self, clara_token):
        """Clara (advanced) should have has_attendance=True"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {clara_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["teams"]["has_attendance"] is True, f"Expected has_attendance=True, got {data['teams']['has_attendance']}"

    def test_clara_teams_can_auto_generate_true(self, clara_token):
        """Clara (advanced) should have can_auto_generate=True"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {clara_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["teams"]["can_auto_generate"] is True, f"Expected can_auto_generate=True, got {data['teams']['can_auto_generate']}"

    def test_clara_teams_connected_true(self, clara_token):
        """Clara (advanced) should have connected=True"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {clara_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["teams"]["connected"] is True, f"Expected connected=True, got {data['teams']['connected']}"

    def test_clara_teams_email_from_outlook(self, clara_token):
        """Clara's Teams email should come from Outlook connection"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {clara_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["teams"]["email"] == "clara.deschamps@demo-nlyt.fr"

    def test_clara_teams_no_unavailable_reason(self, clara_token):
        """Clara (advanced) should have no unavailable_reason"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {clara_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["teams"]["unavailable_reason"] is None, f"Expected None, got {data['teams']['unavailable_reason']}"

    # ========== Sandrine (Standard Level) Tests ==========

    def test_sandrine_teams_level_is_standard(self, sandrine_token):
        """Sandrine should have Teams level='standard' (Outlook without OnlineMeetings scope)"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {sandrine_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["teams"]["level"] == "standard", f"Expected 'standard', got {data['teams']['level']}"

    def test_sandrine_teams_has_attendance_false(self, sandrine_token):
        """Sandrine (standard) should have has_attendance=False"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {sandrine_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["teams"]["has_attendance"] is False, f"Expected has_attendance=False, got {data['teams']['has_attendance']}"

    def test_sandrine_teams_can_auto_generate_true(self, sandrine_token):
        """Sandrine (standard) should have can_auto_generate=True (via calendar mode)"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {sandrine_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["teams"]["can_auto_generate"] is True, f"Expected can_auto_generate=True, got {data['teams']['can_auto_generate']}"

    def test_sandrine_teams_connected_true(self, sandrine_token):
        """Sandrine (standard) should have connected=True"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {sandrine_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["teams"]["connected"] is True, f"Expected connected=True, got {data['teams']['connected']}"

    def test_sandrine_teams_email_from_outlook(self, sandrine_token):
        """Sandrine's Teams email should come from Outlook connection"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {sandrine_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["teams"]["email"] == "sandrine.bonnet@demo-nlyt.fr"

    def test_sandrine_teams_no_unavailable_reason(self, sandrine_token):
        """Sandrine (standard) should have no unavailable_reason"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {sandrine_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["teams"]["unavailable_reason"] is None, f"Expected None, got {data['teams']['unavailable_reason']}"

    # ========== Marie (No Level / Null) Tests ==========

    def test_marie_teams_level_is_null(self, marie_token):
        """Marie should have Teams level=null (no Outlook connection)"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {marie_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["teams"]["level"] is None, f"Expected None, got {data['teams']['level']}"

    def test_marie_teams_has_attendance_false(self, marie_token):
        """Marie (no level) should have has_attendance=False"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {marie_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["teams"]["has_attendance"] is False, f"Expected has_attendance=False, got {data['teams']['has_attendance']}"

    def test_marie_teams_can_auto_generate_false(self, marie_token):
        """Marie (no level) should have can_auto_generate=False"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {marie_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["teams"]["can_auto_generate"] is False, f"Expected can_auto_generate=False, got {data['teams']['can_auto_generate']}"

    def test_marie_teams_connected_false(self, marie_token):
        """Marie (no level) should have connected=False"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {marie_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["teams"]["connected"] is False, f"Expected connected=False, got {data['teams']['connected']}"

    def test_marie_teams_has_unavailable_reason(self, marie_token):
        """Marie (no level) should have unavailable_reason about Outlook"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {marie_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        reason = data["teams"]["unavailable_reason"]
        assert reason is not None, "Expected unavailable_reason to be set"
        assert "Outlook" in reason, f"Expected 'Outlook' in unavailable_reason, got: {reason}"

    def test_marie_teams_email_is_none(self, marie_token):
        """Marie (no level) should have no Teams email"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {marie_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["teams"]["email"] is None, f"Expected None, got {data['teams']['email']}"


class TestTeamsLevelResponseStructure:
    """Tests for Teams response structure in provider-status API"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login as any user to test response structure"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clara.deschamps@demo-nlyt.fr",
            "password": PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Login failed: {response.status_code}")
        return response.json().get("access_token")

    def test_teams_has_level_field(self, auth_token):
        """Teams response should have 'level' field"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "level" in data["teams"], "Teams should have 'level' field"

    def test_teams_has_has_attendance_field(self, auth_token):
        """Teams response should have 'has_attendance' field"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "has_attendance" in data["teams"], "Teams should have 'has_attendance' field"

    def test_teams_has_can_auto_generate_field(self, auth_token):
        """Teams response should have 'can_auto_generate' field"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "can_auto_generate" in data["teams"], "Teams should have 'can_auto_generate' field"

    def test_teams_has_connected_field(self, auth_token):
        """Teams response should have 'connected' field"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "connected" in data["teams"], "Teams should have 'connected' field"

    def test_teams_has_unavailable_reason_field(self, auth_token):
        """Teams response should have 'unavailable_reason' field"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "unavailable_reason" in data["teams"], "Teams should have 'unavailable_reason' field"

    def test_teams_has_email_field(self, auth_token):
        """Teams response should have 'email' field"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "email" in data["teams"], "Teams should have 'email' field"

    def test_teams_has_label_field(self, auth_token):
        """Teams response should have 'label' field"""
        response = requests.get(
            f"{BASE_URL}/api/video-evidence/provider-status",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["teams"]["label"] == "Microsoft Teams"
