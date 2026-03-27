"""
Test suite for Financial Results Page (Résultats financiers) - Iteration 107
Tests the GET /api/financial/my-results endpoint for the new dedicated page.

Features tested:
- Synthesis cards: total_received_cents, total_paid_cents, net_balance_cents
- Engagements list with user-centric financial wording
- Solidarity impact section with charity donations
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ORGANIZER_EMAIL = "igaal.hanouna@gmail.com"
ORGANIZER_PASSWORD = "OrgTest123!"
PARTICIPANT_EMAIL = "testuser_audit@nlyt.app"
PARTICIPANT_PASSWORD = "TestAudit123!"


@pytest.fixture(scope="module")
def organizer_token():
    """Get authentication token for organizer"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ORGANIZER_EMAIL,
        "password": ORGANIZER_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Authentication failed for organizer: {response.status_code}")


@pytest.fixture(scope="module")
def participant_token():
    """Get authentication token for participant"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": PARTICIPANT_EMAIL,
        "password": PARTICIPANT_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Authentication failed for participant: {response.status_code}")


class TestFinancialResultsEndpoint:
    """Tests for GET /api/financial/my-results endpoint"""

    def test_01_endpoint_returns_200(self, organizer_token):
        """Endpoint should return 200 for authenticated user"""
        response = requests.get(
            f"{BASE_URL}/api/financial/my-results",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_02_synthesis_structure(self, organizer_token):
        """Response should have synthesis with correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/financial/my-results",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check synthesis exists
        assert "synthesis" in data, "Response should have 'synthesis' field"
        synthesis = data["synthesis"]
        
        # Check required fields
        assert "total_received_cents" in synthesis, "synthesis should have total_received_cents"
        assert "total_paid_cents" in synthesis, "synthesis should have total_paid_cents"
        assert "net_balance_cents" in synthesis, "synthesis should have net_balance_cents"
        assert "currency" in synthesis, "synthesis should have currency"
        assert "engagement_count" in synthesis, "synthesis should have engagement_count"
        
        # Check types
        assert isinstance(synthesis["total_received_cents"], int), "total_received_cents should be int"
        assert isinstance(synthesis["total_paid_cents"], int), "total_paid_cents should be int"
        assert isinstance(synthesis["net_balance_cents"], int), "net_balance_cents should be int"

    def test_03_synthesis_values_correct(self, organizer_token):
        """Synthesis values should be mathematically correct"""
        response = requests.get(
            f"{BASE_URL}/api/financial/my-results",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        assert response.status_code == 200
        synthesis = response.json()["synthesis"]
        
        # Net balance = received - paid
        expected_net = synthesis["total_received_cents"] - synthesis["total_paid_cents"]
        assert synthesis["net_balance_cents"] == expected_net, \
            f"Net balance should be {expected_net}, got {synthesis['net_balance_cents']}"

    def test_04_engagements_structure(self, organizer_token):
        """Response should have engagements list with correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/financial/my-results",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check engagements exists
        assert "engagements" in data, "Response should have 'engagements' field"
        engagements = data["engagements"]
        assert isinstance(engagements, list), "engagements should be a list"
        
        # If there are engagements, check structure
        if len(engagements) > 0:
            eng = engagements[0]
            assert "appointment_id" in eng, "engagement should have appointment_id"
            assert "title" in eng, "engagement should have title"
            assert "date" in eng, "engagement should have date"
            assert "currency" in eng, "engagement should have currency"
            assert "received_cents" in eng, "engagement should have received_cents"
            assert "paid_cents" in eng, "engagement should have paid_cents"
            assert "type" in eng, "engagement should have type"
            
            # Type should be one of: paid, received, both, neutral
            assert eng["type"] in ["paid", "received", "both", "neutral"], \
                f"engagement type should be valid, got {eng['type']}"

    def test_05_engagements_have_charity_info(self, organizer_token):
        """Engagements should include charity information"""
        response = requests.get(
            f"{BASE_URL}/api/financial/my-results",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        assert response.status_code == 200
        engagements = response.json()["engagements"]
        
        # Check charity fields exist
        if len(engagements) > 0:
            eng = engagements[0]
            assert "charity_cents" in eng, "engagement should have charity_cents"
            assert "charity_association_name" in eng, "engagement should have charity_association_name"

    def test_06_solidarity_structure(self, organizer_token):
        """Response should have solidarity section with correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/financial/my-results",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check solidarity exists
        assert "solidarity" in data, "Response should have 'solidarity' field"
        solidarity = data["solidarity"]
        
        # Check required fields
        assert "total_charity_cents" in solidarity, "solidarity should have total_charity_cents"
        assert "associations" in solidarity, "solidarity should have associations"
        assert isinstance(solidarity["associations"], list), "associations should be a list"

    def test_07_solidarity_associations_structure(self, organizer_token):
        """Solidarity associations should have correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/financial/my-results",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        assert response.status_code == 200
        associations = response.json()["solidarity"]["associations"]
        
        # If there are associations, check structure
        if len(associations) > 0:
            assoc = associations[0]
            assert "association_id" in assoc, "association should have association_id"
            assert "name" in assoc, "association should have name"
            assert "total_cents" in assoc, "association should have total_cents"
            assert "count" in assoc, "association should have count"

    def test_08_unauthenticated_returns_401(self):
        """Endpoint should return 401 for unauthenticated request"""
        response = requests.get(f"{BASE_URL}/api/financial/my-results")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    def test_09_engagement_count_matches_list(self, organizer_token):
        """Engagement count in synthesis should match engagements list length"""
        response = requests.get(
            f"{BASE_URL}/api/financial/my-results",
            headers={"Authorization": f"Bearer {organizer_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        synthesis_count = data["synthesis"]["engagement_count"]
        actual_count = len(data["engagements"])
        assert synthesis_count == actual_count, \
            f"engagement_count ({synthesis_count}) should match engagements list length ({actual_count})"


class TestFinancialResultsParticipant:
    """Tests for participant user financial results"""

    def test_01_participant_can_access_endpoint(self, participant_token):
        """Participant should be able to access their financial results"""
        response = requests.get(
            f"{BASE_URL}/api/financial/my-results",
            headers={"Authorization": f"Bearer {participant_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_02_participant_has_valid_structure(self, participant_token):
        """Participant response should have valid structure"""
        response = requests.get(
            f"{BASE_URL}/api/financial/my-results",
            headers={"Authorization": f"Bearer {participant_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check all main sections exist
        assert "synthesis" in data
        assert "engagements" in data
        assert "solidarity" in data
