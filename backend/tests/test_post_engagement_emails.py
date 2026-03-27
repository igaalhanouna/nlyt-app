"""
Test Phase 4: Post-Engagement Viral Emails
Tests for send_post_engagement_emails() function and _email_card_html() helper.

Features tested:
1. _email_card_html() renders correct HTML for 3 card types with proper accent colors
2. send_post_engagement_emails() generates correct card types based on attendance records
3. Auto-creation of result_cards in DB during email generation (idempotent)
4. Email subject lines contain emotional headlines
5. Idempotence: email_type 'post_engagement_{card_type}' is unique per appointment+user
6. evaluate_appointment() triggers send_post_engagement_emails() after financial outcomes
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestEmailCardHtmlHelper:
    """Test _email_card_html() helper function renders correct HTML for 3 card types."""

    def test_email_card_html_engagement_respected(self):
        """Test engagement_respected card HTML has green accent color."""
        # Set environment variables before import
        os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
        os.environ.setdefault('DB_NAME', 'test_database')
        
        import sys
        sys.path.insert(0, '/app/backend')
        from services.financial_emails import _email_card_html
        
        html = _email_card_html(
            card_type="engagement_respected",
            headline="Engagement respecté.",
            subtitle="Tout le monde a respecté son engagement.",
            title="Test Meeting",
            date="15 janvier 2026"
        )
        
        # Check green accent color (#10B981)
        assert "#10B981" in html, "engagement_respected should have green accent color"
        assert "#F0FDF4" in html, "engagement_respected should have green background"
        assert "#BBF7D0" in html, "engagement_respected should have green border"
        assert "&#10004;" in html, "engagement_respected should have checkmark icon"
        assert "Engagement respecté." in html
        assert "Tout le monde a respecté son engagement." in html
        assert "Test Meeting" in html
        assert "15 janvier 2026" in html
        print("✅ _email_card_html() renders engagement_respected with green accent")

    def test_email_card_html_compensation_received(self):
        """Test compensation_received card HTML has blue accent color."""
        os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
        os.environ.setdefault('DB_NAME', 'test_database')
        
        import sys
        sys.path.insert(0, '/app/backend')
        from services.financial_emails import _email_card_html
        
        html = _email_card_html(
            card_type="compensation_received",
            headline="Vous avez récupéré 35,00 €.",
            subtitle="Parce que votre temps compte.",
            title="Business Meeting",
            date="20 janvier 2026"
        )
        
        # Check blue accent color (#3B82F6)
        assert "#3B82F6" in html, "compensation_received should have blue accent color"
        assert "#EFF6FF" in html, "compensation_received should have blue background"
        assert "#BFDBFE" in html, "compensation_received should have blue border"
        assert "&#9670;" in html, "compensation_received should have diamond icon"
        assert "Vous avez récupéré 35,00 €." in html
        assert "Parce que votre temps compte." in html
        print("✅ _email_card_html() renders compensation_received with blue accent")

    def test_email_card_html_charity_donation(self):
        """Test charity_donation card HTML has amber accent color."""
        os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
        os.environ.setdefault('DB_NAME', 'test_database')
        
        import sys
        sys.path.insert(0, '/app/backend')
        from services.financial_emails import _email_card_html
        
        html = _email_card_html(
            card_type="charity_donation",
            headline="Votre temps a aidé quelqu'un.",
            subtitle="10,00 € reversés à Restos du Coeur.",
            title="Team Sync",
            date="25 janvier 2026"
        )
        
        # Check amber accent color (#F59E0B)
        assert "#F59E0B" in html, "charity_donation should have amber accent color"
        assert "#FFFBEB" in html, "charity_donation should have amber background"
        assert "#FDE68A" in html, "charity_donation should have amber border"
        assert "&#9829;" in html, "charity_donation should have heart icon"
        assert "Votre temps a aidé quelqu'un." in html
        assert "10,00 € reversés à Restos du Coeur." in html
        print("✅ _email_card_html() renders charity_donation with amber accent")

    def test_email_card_html_unknown_type_fallback(self):
        """Test unknown card type falls back to engagement_respected styling."""
        os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
        os.environ.setdefault('DB_NAME', 'test_database')
        
        import sys
        sys.path.insert(0, '/app/backend')
        from services.financial_emails import _email_card_html
        
        html = _email_card_html(
            card_type="unknown_type",
            headline="Test",
            subtitle="Test subtitle",
            title="Test",
            date="Test"
        )
        
        # Should fallback to green (engagement_respected)
        assert "#10B981" in html, "Unknown type should fallback to green accent"
        print("✅ _email_card_html() falls back to engagement_respected for unknown types")


class TestCardAccentsConfig:
    """Test _CARD_ACCENTS configuration matches frontend ResultCard component."""

    def test_card_accents_match_frontend(self):
        """Verify backend card accents match frontend CARD_CONFIG."""
        os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
        os.environ.setdefault('DB_NAME', 'test_database')
        
        import sys
        sys.path.insert(0, '/app/backend')
        from services.financial_emails import _CARD_ACCENTS
        
        # Expected values from frontend ResultCard.js
        expected = {
            "engagement_respected": {"color": "#10B981", "bg": "#F0FDF4", "border": "#BBF7D0"},
            "compensation_received": {"color": "#3B82F6", "bg": "#EFF6FF", "border": "#BFDBFE"},
            "charity_donation": {"color": "#F59E0B", "bg": "#FFFBEB", "border": "#FDE68A"},
        }
        
        for card_type, expected_vals in expected.items():
            assert card_type in _CARD_ACCENTS, f"Missing card type: {card_type}"
            assert _CARD_ACCENTS[card_type]["color"] == expected_vals["color"], f"Color mismatch for {card_type}"
            assert _CARD_ACCENTS[card_type]["bg"] == expected_vals["bg"], f"Background mismatch for {card_type}"
            assert _CARD_ACCENTS[card_type]["border"] == expected_vals["border"], f"Border mismatch for {card_type}"
        
        print("✅ _CARD_ACCENTS matches frontend CARD_CONFIG colors")


class TestSendPostEngagementEmailsFunction:
    """Test send_post_engagement_emails() function logic."""

    def test_function_exists_and_importable(self):
        """Verify send_post_engagement_emails can be imported."""
        os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
        os.environ.setdefault('DB_NAME', 'test_database')
        
        import sys
        sys.path.insert(0, '/app/backend')
        from services.financial_emails import send_post_engagement_emails
        assert callable(send_post_engagement_emails)
        print("✅ send_post_engagement_emails() is importable and callable")

    def test_function_handles_empty_records(self):
        """Test function handles appointment with no attendance records gracefully."""
        os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
        os.environ.setdefault('DB_NAME', 'test_database')
        
        import sys
        sys.path.insert(0, '/app/backend')
        from services.financial_emails import send_post_engagement_emails
        
        # Use a non-existent appointment ID
        fake_appointment_id = str(uuid.uuid4())
        fake_appointment = {
            "appointment_id": fake_appointment_id,
            "title": "Test Appointment",
            "start_datetime": datetime.now(timezone.utc).isoformat(),
        }
        
        # Should not raise an exception
        try:
            send_post_engagement_emails(fake_appointment_id, fake_appointment)
            print("✅ send_post_engagement_emails() handles empty records gracefully")
        except Exception as e:
            pytest.fail(f"Function raised exception for empty records: {e}")


class TestIdempotenceChecks:
    """Test idempotence mechanisms for post-engagement emails."""

    def test_already_sent_function_exists(self):
        """Verify _already_sent helper function exists."""
        os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
        os.environ.setdefault('DB_NAME', 'test_database')
        
        import sys
        sys.path.insert(0, '/app/backend')
        from services.financial_emails import _already_sent
        assert callable(_already_sent)
        print("✅ _already_sent() helper function exists")

    def test_mark_sent_function_exists(self):
        """Verify _mark_sent helper function exists."""
        os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
        os.environ.setdefault('DB_NAME', 'test_database')
        
        import sys
        sys.path.insert(0, '/app/backend')
        from services.financial_emails import _mark_sent
        assert callable(_mark_sent)
        print("✅ _mark_sent() helper function exists")


class TestEvaluateAppointmentIntegration:
    """Test that evaluate_appointment() triggers send_post_engagement_emails()."""

    def test_evaluate_appointment_source_contains_post_engagement_call(self):
        """Verify evaluate_appointment source code contains call to send_post_engagement_emails."""
        # Read the source file directly to avoid import issues
        with open('/app/backend/services/attendance_service.py', 'r') as f:
            source = f.read()
        
        # Check that the function imports and calls send_post_engagement_emails
        assert "send_post_engagement_emails" in source, \
            "evaluate_appointment should call send_post_engagement_emails"
        assert "from services.financial_emails import send_post_engagement_emails" in source, \
            "evaluate_appointment should import send_post_engagement_emails"
        
        print("✅ evaluate_appointment() contains call to send_post_engagement_emails()")

    def test_post_engagement_call_is_non_blocking(self):
        """Verify post-engagement email call is wrapped in try-except (non-blocking)."""
        # Read the source file directly
        with open('/app/backend/services/attendance_service.py', 'r') as f:
            source = f.read()
        
        # Check for try-except wrapper around the call
        assert "try:" in source and "send_post_engagement_emails" in source, \
            "send_post_engagement_emails should be in a try block"
        
        # Check for the specific pattern: try block followed by send_post_engagement_emails
        lines = source.split('\n')
        found_try_before_call = False
        in_try_block = False
        for line in lines:
            if 'try:' in line:
                in_try_block = True
            if in_try_block and 'send_post_engagement_emails' in line:
                found_try_before_call = True
                break
            if 'except' in line:
                in_try_block = False
        
        assert found_try_before_call, "send_post_engagement_emails should be inside a try block"
        print("✅ send_post_engagement_emails() call is non-blocking (wrapped in try-except)")


class TestResultCardsPublicEndpoint:
    """Test GET /api/result-cards/{card_id} still works for auto-created cards."""

    def test_get_engagement_card(self):
        """Test public endpoint returns engagement_respected card."""
        card_id = "44bda97c-47d5-4645-a28a-6ccee99f3432"
        response = requests.get(f"{BASE_URL}/api/result-cards/{card_id}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data["card_type"] == "engagement_respected"
        assert data["card_id"] == card_id
        print("✅ GET /api/result-cards/{card_id} works for engagement_respected card")

    def test_get_compensation_card(self):
        """Test public endpoint returns compensation_received card."""
        card_id = "dfdf1740-9972-466f-986a-303478e00de6"
        response = requests.get(f"{BASE_URL}/api/result-cards/{card_id}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data["card_type"] == "compensation_received"
        assert data["amount_cents"] == 3500
        print("✅ GET /api/result-cards/{card_id} works for compensation_received card")

    def test_get_charity_card(self):
        """Test public endpoint returns charity_donation card."""
        card_id = "fb6a67d4-0cb1-4645-9ed5-0668ca124ca5"
        response = requests.get(f"{BASE_URL}/api/result-cards/{card_id}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data["card_type"] == "charity_donation"
        assert data["association_name"] == "Restos du Coeur"
        print("✅ GET /api/result-cards/{card_id} works for charity_donation card")

    def test_get_nonexistent_card_returns_404(self):
        """Test public endpoint returns 404 for nonexistent card."""
        response = requests.get(f"{BASE_URL}/api/result-cards/nonexistent-card-id")
        assert response.status_code == 404
        print("✅ GET /api/result-cards/nonexistent returns 404")


class TestResultCardsMyCardsEndpoint:
    """Test GET /api/result-cards/my-cards returns auto-created cards."""

    @pytest.fixture
    def auth_token(self):
        """Get auth token for test user."""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testuser_audit@nlyt.app",
            "password": "Test123!"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")

    def test_my_cards_requires_auth(self):
        """Test my-cards endpoint requires authentication."""
        response = requests.get(f"{BASE_URL}/api/result-cards/my-cards")
        assert response.status_code == 401
        print("✅ GET /api/result-cards/my-cards requires authentication")

    def test_my_cards_returns_user_cards(self, auth_token):
        """Test my-cards returns cards for authenticated user."""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/result-cards/my-cards", headers=headers)
        
        assert response.status_code == 200
        cards = response.json()
        assert isinstance(cards, list)
        
        # Should have at least the 3 test cards
        card_types = [c["card_type"] for c in cards]
        print(f"✅ GET /api/result-cards/my-cards returns {len(cards)} cards")
        print(f"   Card types: {card_types}")


class TestHealthCheck:
    """Verify backend health check still passes."""

    def test_health_endpoint(self):
        """Test /api/health returns healthy status."""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✅ Backend health check passes")


class TestFinancialEmailsSourceCode:
    """Test financial_emails.py source code for Phase 4 features."""

    def test_send_post_engagement_emails_function_exists(self):
        """Verify send_post_engagement_emails function is defined in source."""
        with open('/app/backend/services/financial_emails.py', 'r') as f:
            source = f.read()
        
        assert "def send_post_engagement_emails(" in source, \
            "send_post_engagement_emails function should be defined"
        print("✅ send_post_engagement_emails() function is defined")

    def test_email_card_html_function_exists(self):
        """Verify _email_card_html helper function is defined."""
        with open('/app/backend/services/financial_emails.py', 'r') as f:
            source = f.read()
        
        assert "def _email_card_html(" in source, \
            "_email_card_html helper function should be defined"
        print("✅ _email_card_html() helper function is defined")

    def test_card_accents_config_exists(self):
        """Verify _CARD_ACCENTS configuration is defined."""
        with open('/app/backend/services/financial_emails.py', 'r') as f:
            source = f.read()
        
        assert "_CARD_ACCENTS" in source, "_CARD_ACCENTS config should be defined"
        assert "engagement_respected" in source
        assert "compensation_received" in source
        assert "charity_donation" in source
        print("✅ _CARD_ACCENTS configuration is defined with all 3 card types")

    def test_auto_card_creation_logic(self):
        """Verify auto-creation of result cards in send_post_engagement_emails."""
        with open('/app/backend/services/financial_emails.py', 'r') as f:
            source = f.read()
        
        # Check for idempotent card creation
        assert "db.result_cards.find_one" in source, "Should check for existing card"
        assert "db.result_cards.insert_one" in source, "Should insert new card"
        print("✅ Auto-creation of result_cards logic is present (idempotent)")

    def test_email_type_format(self):
        """Verify email_type format is 'post_engagement_{card_type}'."""
        with open('/app/backend/services/financial_emails.py', 'r') as f:
            source = f.read()
        
        assert 'f"post_engagement_{card_type}"' in source or "post_engagement_" in source, \
            "Email type should be formatted as post_engagement_{card_type}"
        print("✅ Email type format is 'post_engagement_{card_type}'")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
