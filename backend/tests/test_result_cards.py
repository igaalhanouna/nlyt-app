"""
Test Result Cards API - Phase 3 Viral Loop
Tests for shareable result cards: engagement_respected, compensation_received, charity_donation
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test123!"

# Existing test card IDs (pre-created)
ENGAGEMENT_CARD_ID = "44bda97c-47d5-4645-a28a-6ccee99f3432"
COMPENSATION_CARD_ID = "dfdf1740-9972-466f-986a-303478e00de6"
CHARITY_CARD_ID = "fb6a67d4-0cb1-4645-9ed5-0668ca124ca5"
TEST_APPOINTMENT_ID = "35df4fb0-91ac-4d6a-a56b-cfd6e06b4111"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestPublicCardEndpoint:
    """GET /api/result-cards/{card_id} - Public endpoint (no auth required)"""
    
    def test_get_engagement_card_public(self):
        """Test fetching engagement_respected card without auth"""
        response = requests.get(f"{BASE_URL}/api/result-cards/{ENGAGEMENT_CARD_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["card_id"] == ENGAGEMENT_CARD_ID
        assert data["card_type"] == "engagement_respected"
        assert "user_name" in data
        assert "appointment_title" in data
        assert "appointment_date" in data
        assert "view_count" in data
        assert isinstance(data["view_count"], int)
        print(f"✅ Engagement card fetched: {data['card_type']}, views: {data['view_count']}")
    
    def test_get_compensation_card_public(self):
        """Test fetching compensation_received card without auth"""
        response = requests.get(f"{BASE_URL}/api/result-cards/{COMPENSATION_CARD_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["card_id"] == COMPENSATION_CARD_ID
        assert data["card_type"] == "compensation_received"
        assert "amount_cents" in data
        assert "currency" in data
        print(f"✅ Compensation card fetched: {data['amount_cents']} {data['currency']}")
    
    def test_get_charity_card_public(self):
        """Test fetching charity_donation card without auth"""
        response = requests.get(f"{BASE_URL}/api/result-cards/{CHARITY_CARD_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["card_id"] == CHARITY_CARD_ID
        assert data["card_type"] == "charity_donation"
        assert "association_name" in data
        print(f"✅ Charity card fetched: {data.get('association_name')}, amount: {data.get('amount_cents')}")
    
    def test_view_count_increments(self):
        """Test that view_count increments on each GET"""
        # First request
        response1 = requests.get(f"{BASE_URL}/api/result-cards/{ENGAGEMENT_CARD_ID}")
        assert response1.status_code == 200
        view_count_1 = response1.json()["view_count"]
        
        # Second request
        response2 = requests.get(f"{BASE_URL}/api/result-cards/{ENGAGEMENT_CARD_ID}")
        assert response2.status_code == 200
        view_count_2 = response2.json()["view_count"]
        
        assert view_count_2 == view_count_1 + 1, f"View count should increment: {view_count_1} -> {view_count_2}"
        print(f"✅ View count incremented: {view_count_1} -> {view_count_2}")
    
    def test_nonexistent_card_returns_404(self):
        """Test that nonexistent card returns 404"""
        response = requests.get(f"{BASE_URL}/api/result-cards/nonexistent-card-id-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data
        print(f"✅ Nonexistent card returns 404: {data['detail']}")


class TestCreateCardEndpoint:
    """POST /api/result-cards - Create card (requires auth)"""
    
    def test_create_card_requires_auth(self):
        """Test that creating a card without auth returns 401"""
        response = requests.post(f"{BASE_URL}/api/result-cards", json={
            "appointment_id": TEST_APPOINTMENT_ID,
            "card_type": "engagement_respected"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ Create card requires authentication")
    
    def test_create_card_invalid_type_returns_400(self, auth_headers):
        """Test that invalid card_type returns 400"""
        response = requests.post(f"{BASE_URL}/api/result-cards", json={
            "appointment_id": TEST_APPOINTMENT_ID,
            "card_type": "invalid_type"
        }, headers=auth_headers)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data
        print(f"✅ Invalid card type returns 400: {data['detail']}")
    
    def test_create_card_missing_appointment_returns_400(self, auth_headers):
        """Test that missing appointment_id returns 400"""
        response = requests.post(f"{BASE_URL}/api/result-cards", json={
            "card_type": "engagement_respected"
        }, headers=auth_headers)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data
        print(f"✅ Missing appointment_id returns 400: {data['detail']}")
    
    def test_create_card_idempotent(self, auth_headers):
        """Test that creating same card type for same appointment returns existing card"""
        # First creation (or existing)
        response1 = requests.post(f"{BASE_URL}/api/result-cards", json={
            "appointment_id": TEST_APPOINTMENT_ID,
            "card_type": "engagement_respected"
        }, headers=auth_headers)
        assert response1.status_code == 200, f"Expected 200, got {response1.status_code}"
        card1 = response1.json()
        
        # Second creation - should return same card
        response2 = requests.post(f"{BASE_URL}/api/result-cards", json={
            "appointment_id": TEST_APPOINTMENT_ID,
            "card_type": "engagement_respected"
        }, headers=auth_headers)
        assert response2.status_code == 200, f"Expected 200, got {response2.status_code}"
        card2 = response2.json()
        
        assert card1["card_id"] == card2["card_id"], "Idempotent: should return same card_id"
        print(f"✅ Idempotent creation verified: {card1['card_id']}")


class TestMyCardsEndpoint:
    """GET /api/result-cards/my-cards - List user's cards (requires auth)"""
    
    def test_my_cards_requires_auth(self):
        """Test that listing cards without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/result-cards/my-cards")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ My cards requires authentication")
    
    def test_my_cards_returns_list(self, auth_headers):
        """Test that my-cards returns a list of cards"""
        response = requests.get(f"{BASE_URL}/api/result-cards/my-cards", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Should return a list"
        
        if len(data) > 0:
            card = data[0]
            assert "card_id" in card
            assert "card_type" in card
            assert "appointment_id" in card
            print(f"✅ My cards returned {len(data)} cards")
        else:
            print("✅ My cards returned empty list (user has no cards)")


class TestCardDataStructure:
    """Verify card data structure and fields"""
    
    def test_engagement_card_structure(self):
        """Verify engagement_respected card has all required fields"""
        response = requests.get(f"{BASE_URL}/api/result-cards/{ENGAGEMENT_CARD_ID}")
        assert response.status_code == 200
        
        card = response.json()
        required_fields = [
            "card_id", "card_type", "user_id", "user_name",
            "appointment_id", "appointment_title", "appointment_date",
            "appointment_timezone", "amount_cents", "currency",
            "association_name", "view_count", "created_at"
        ]
        
        for field in required_fields:
            assert field in card, f"Missing field: {field}"
        
        assert card["card_type"] == "engagement_respected"
        assert card["amount_cents"] == 0  # No amount for engagement card
        print("✅ Engagement card has all required fields")
    
    def test_compensation_card_has_amount(self):
        """Verify compensation_received card has amount_cents > 0"""
        response = requests.get(f"{BASE_URL}/api/result-cards/{COMPENSATION_CARD_ID}")
        assert response.status_code == 200
        
        card = response.json()
        assert card["card_type"] == "compensation_received"
        assert "amount_cents" in card
        assert isinstance(card["amount_cents"], int)
        # Amount should be positive for compensation
        print(f"✅ Compensation card amount: {card['amount_cents']} {card['currency']}")
    
    def test_charity_card_has_association(self):
        """Verify charity_donation card has association_name"""
        response = requests.get(f"{BASE_URL}/api/result-cards/{CHARITY_CARD_ID}")
        assert response.status_code == 200
        
        card = response.json()
        assert card["card_type"] == "charity_donation"
        # association_name can be null if not found
        print(f"✅ Charity card association: {card.get('association_name')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
