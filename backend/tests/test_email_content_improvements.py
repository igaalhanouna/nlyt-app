"""
Test Email Content Improvements - Confirmation Email Cases
Tests the send_acceptance_confirmation_email method for all 4 cases:
1. Video + Guarantee (penalty > 0)
2. Video + No Guarantee (penalty = 0)
3. Physical + Guarantee (penalty > 0)
4. Physical + No Guarantee (penalty = 0)

Verifies:
- Method signature accepts appointment_type and meeting_provider params
- Email subject uses "Confirmation d'acces — {title}" format
- Video emails contain proof link, provider label, ICS button, timezone note
- Physical emails contain GPS/QR check-in section, location, ICS button, NO proof link
- Location display: "En ligne — Zoom" / "En ligne — Microsoft Teams" for video
- All emails contain "confirmation d'acces definitive" note
"""
import pytest
import pytest_asyncio
import os
import asyncio
from unittest.mock import patch, MagicMock

# Configure pytest-asyncio
pytestmark = pytest.mark.asyncio(loop_scope="function")

# Set up environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://teams-ux-fix.preview.emergentagent.com').rstrip('/')


class TestEmailMethodSignature:
    """Test that send_acceptance_confirmation_email accepts new params"""
    
    def test_method_accepts_appointment_type_param(self):
        """Verify method signature includes appointment_type parameter"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.email_service import EmailService
        import inspect
        
        sig = inspect.signature(EmailService.send_acceptance_confirmation_email)
        params = list(sig.parameters.keys())
        
        assert 'appointment_type' in params, "appointment_type param missing from method signature"
        print("✓ appointment_type param found in method signature")
    
    def test_method_accepts_meeting_provider_param(self):
        """Verify method signature includes meeting_provider parameter"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.email_service import EmailService
        import inspect
        
        sig = inspect.signature(EmailService.send_acceptance_confirmation_email)
        params = list(sig.parameters.keys())
        
        assert 'meeting_provider' in params, "meeting_provider param missing from method signature"
        print("✓ meeting_provider param found in method signature")
    
    def test_method_default_values(self):
        """Verify default values for new params"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.email_service import EmailService
        import inspect
        
        sig = inspect.signature(EmailService.send_acceptance_confirmation_email)
        
        # appointment_type should default to 'physical'
        apt_type_default = sig.parameters['appointment_type'].default
        assert apt_type_default == 'physical', f"appointment_type default should be 'physical', got {apt_type_default}"
        print(f"✓ appointment_type default is 'physical'")
        
        # meeting_provider should default to None
        provider_default = sig.parameters['meeting_provider'].default
        assert provider_default is None, f"meeting_provider default should be None, got {provider_default}"
        print(f"✓ meeting_provider default is None")


class TestEmailContentGeneration:
    """Test email HTML content for all 4 cases by capturing send_email calls"""
    
    @pytest.fixture
    def captured_emails(self):
        """Fixture to capture email content"""
        return []
    
    @pytest.mark.asyncio
    async def test_video_with_guarantee_email_content(self):
        """Case 1: Video + Guarantee - verify proof link, provider label, ICS, timezone"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.email_service import EmailService
        
        captured = []
        
        # Monkey-patch send_email to capture HTML
        original_send_email = EmailService.send_email
        
        @staticmethod
        async def mock_send_email(to_email, subject, html_content, email_type="generic"):
            captured.append({
                'to_email': to_email,
                'subject': subject,
                'html_content': html_content,
                'email_type': email_type
            })
            return {"success": True, "email_id": "test_id"}
        
        EmailService.send_email = mock_send_email
        
        try:
            await EmailService.send_acceptance_confirmation_email(
                to_email="participant@test.com",
                to_name="Jean Dupont",
                organizer_name="Marie Martin",
                appointment_title="Réunion Stratégique",
                appointment_datetime="2026-02-15T14:00:00Z",
                location=None,
                penalty_amount=50.0,
                penalty_currency="EUR",
                cancellation_deadline_hours=24,
                ics_link="https://example.com/api/calendar/export/ics/apt123",
                invitation_link="https://example.com/invitation/token123",
                appointment_timezone="Europe/Paris",
                proof_link="https://example.com/proof/apt123?token=token123",
                appointment_type="video",
                meeting_provider="zoom"
            )
            
            assert len(captured) == 1, "Expected 1 email to be sent"
            email = captured[0]
            
            # Check subject format
            assert "Confirmation d'acces —" in email['subject'], f"Subject should use new format, got: {email['subject']}"
            assert "Réunion Stratégique" in email['subject'], "Subject should contain appointment title"
            print(f"✓ Subject format correct: {email['subject']}")
            
            html = email['html_content']
            
            # Check proof link section
            assert "Confirmer ma presence et rejoindre" in html, "Video email should contain proof link button text"
            assert "proof/apt123?token=token123" in html, "Video email should contain proof link URL"
            print("✓ Proof link section present")
            
            # Check provider label
            assert "Zoom" in html, "Video email should mention Zoom provider"
            assert "En ligne — Zoom" in html, "Location should show 'En ligne — Zoom'"
            print("✓ Provider label (Zoom) present")
            
            # Check ICS button
            assert "Ajouter a mon calendrier" in html, "Email should contain ICS button"
            assert "calendar/export/ics" in html, "Email should contain ICS link"
            print("✓ ICS button present")
            
            # Check timezone note
            assert "Europe/Paris" in html, "Email should contain timezone"
            assert "Fuseau horaire" in html, "Email should contain timezone label"
            print("✓ Timezone note present")
            
            # Check confirmation definitive note
            assert "confirmation d'acces definitive" in html, "Email should contain 'confirmation d'acces definitive' note"
            print("✓ 'confirmation d'acces definitive' note present")
            
            # Check penalty reminder (since penalty > 0)
            assert "50" in html and "EUR" in html, "Email should show penalty amount"
            assert "Rappel d'engagement" in html, "Email should contain penalty reminder"
            print("✓ Penalty reminder present")
            
        finally:
            EmailService.send_email = original_send_email
    
    @pytest.mark.asyncio
    async def test_video_without_guarantee_email_content(self):
        """Case 2: Video + No Guarantee - verify proof link, provider, NO penalty reminder"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.email_service import EmailService
        
        captured = []
        original_send_email = EmailService.send_email
        
        @staticmethod
        async def mock_send_email(to_email, subject, html_content, email_type="generic"):
            captured.append({
                'to_email': to_email,
                'subject': subject,
                'html_content': html_content,
                'email_type': email_type
            })
            return {"success": True, "email_id": "test_id"}
        
        EmailService.send_email = mock_send_email
        
        try:
            await EmailService.send_acceptance_confirmation_email(
                to_email="participant@test.com",
                to_name="Jean Dupont",
                organizer_name="Marie Martin",
                appointment_title="Call Teams",
                appointment_datetime="2026-02-15T14:00:00Z",
                location=None,
                penalty_amount=0,  # No penalty
                penalty_currency="EUR",
                cancellation_deadline_hours=None,
                ics_link="https://example.com/api/calendar/export/ics/apt456",
                invitation_link="https://example.com/invitation/token456",
                appointment_timezone="Europe/Paris",
                proof_link="https://example.com/proof/apt456?token=token456",
                appointment_type="video",
                meeting_provider="teams"
            )
            
            assert len(captured) == 1
            email = captured[0]
            html = email['html_content']
            
            # Check subject format
            assert "Confirmation d'acces —" in email['subject']
            print(f"✓ Subject format correct: {email['subject']}")
            
            # Check proof link section
            assert "Confirmer ma presence et rejoindre" in html
            print("✓ Proof link section present")
            
            # Check provider label - Microsoft Teams
            assert "Microsoft Teams" in html, "Video email should mention Microsoft Teams"
            assert "En ligne — Microsoft Teams" in html, "Location should show 'En ligne — Microsoft Teams'"
            print("✓ Provider label (Microsoft Teams) present")
            
            # Check NO penalty reminder (since penalty = 0)
            assert "Rappel d'engagement" not in html, "Email should NOT contain penalty reminder when penalty=0"
            print("✓ No penalty reminder (correct for no-guarantee)")
            
            # Check confirmation definitive note
            assert "confirmation d'acces definitive" in html
            print("✓ 'confirmation d'acces definitive' note present")
            
        finally:
            EmailService.send_email = original_send_email
    
    @pytest.mark.asyncio
    async def test_physical_with_guarantee_email_content(self):
        """Case 3: Physical + Guarantee - verify GPS/QR section, location, NO proof link"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.email_service import EmailService
        
        captured = []
        original_send_email = EmailService.send_email
        
        @staticmethod
        async def mock_send_email(to_email, subject, html_content, email_type="generic"):
            captured.append({
                'to_email': to_email,
                'subject': subject,
                'html_content': html_content,
                'email_type': email_type
            })
            return {"success": True, "email_id": "test_id"}
        
        EmailService.send_email = mock_send_email
        
        try:
            await EmailService.send_acceptance_confirmation_email(
                to_email="participant@test.com",
                to_name="Jean Dupont",
                organizer_name="Marie Martin",
                appointment_title="Réunion Bureau",
                appointment_datetime="2026-02-15T14:00:00Z",
                location="123 Rue de Paris, 75001 Paris",
                penalty_amount=100.0,
                penalty_currency="EUR",
                cancellation_deadline_hours=48,
                ics_link="https://example.com/api/calendar/export/ics/apt789",
                invitation_link="https://example.com/invitation/token789",
                appointment_timezone="Europe/Paris",
                proof_link=None,  # No proof link for physical
                appointment_type="physical",
                meeting_provider=None
            )
            
            assert len(captured) == 1
            email = captured[0]
            html = email['html_content']
            
            # Check subject format
            assert "Confirmation d'acces —" in email['subject']
            print(f"✓ Subject format correct: {email['subject']}")
            
            # Check GPS/QR check-in section
            assert "Je suis arrive" in html, "Physical email should contain 'Je suis arrive' button text"
            assert "scan du QR code" in html, "Physical email should mention QR code"
            assert "GPS" in html, "Physical email should mention GPS"
            print("✓ GPS/QR check-in section present")
            
            # Check location
            assert "123 Rue de Paris" in html, "Physical email should contain location"
            print("✓ Location present")
            
            # Check NO proof link button
            assert "Confirmer ma presence et rejoindre" not in html, "Physical email should NOT contain video proof link button"
            print("✓ No video proof link (correct for physical)")
            
            # Check ICS button
            assert "Ajouter a mon calendrier" in html
            print("✓ ICS button present")
            
            # Check penalty reminder
            assert "100" in html and "EUR" in html
            assert "Rappel d'engagement" in html
            print("✓ Penalty reminder present")
            
            # Check confirmation definitive note
            assert "confirmation d'acces definitive" in html
            print("✓ 'confirmation d'acces definitive' note present")
            
        finally:
            EmailService.send_email = original_send_email
    
    @pytest.mark.asyncio
    async def test_physical_without_guarantee_email_content(self):
        """Case 4: Physical + No Guarantee - verify GPS/QR section, NO penalty reminder"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.email_service import EmailService
        
        captured = []
        original_send_email = EmailService.send_email
        
        @staticmethod
        async def mock_send_email(to_email, subject, html_content, email_type="generic"):
            captured.append({
                'to_email': to_email,
                'subject': subject,
                'html_content': html_content,
                'email_type': email_type
            })
            return {"success": True, "email_id": "test_id"}
        
        EmailService.send_email = mock_send_email
        
        try:
            await EmailService.send_acceptance_confirmation_email(
                to_email="participant@test.com",
                to_name="Jean Dupont",
                organizer_name="Marie Martin",
                appointment_title="Café Networking",
                appointment_datetime="2026-02-15T14:00:00Z",
                location="Café de Flore, Paris",
                penalty_amount=0,  # No penalty
                penalty_currency="EUR",
                cancellation_deadline_hours=None,
                ics_link="https://example.com/api/calendar/export/ics/apt000",
                invitation_link="https://example.com/invitation/token000",
                appointment_timezone="America/New_York",
                proof_link=None,
                appointment_type="physical",
                meeting_provider=None
            )
            
            assert len(captured) == 1
            email = captured[0]
            html = email['html_content']
            
            # Check subject format
            assert "Confirmation d'acces —" in email['subject']
            print(f"✓ Subject format correct: {email['subject']}")
            
            # Check GPS/QR check-in section
            assert "Je suis arrive" in html
            assert "scan du QR code" in html
            print("✓ GPS/QR check-in section present")
            
            # Check location
            assert "Café de Flore" in html
            print("✓ Location present")
            
            # Check NO penalty reminder
            assert "Rappel d'engagement" not in html
            print("✓ No penalty reminder (correct for no-guarantee)")
            
            # Check timezone (different timezone)
            assert "America/New_York" in html
            print("✓ Timezone note present (America/New_York)")
            
            # Check confirmation definitive note
            assert "confirmation d'acces definitive" in html
            print("✓ 'confirmation d'acces definitive' note present")
            
        finally:
            EmailService.send_email = original_send_email


class TestProviderLabelMapping:
    """Test that provider labels are correctly mapped"""
    
    @pytest.mark.asyncio
    async def test_zoom_provider_label(self):
        """Verify 'zoom' maps to 'Zoom'"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.email_service import EmailService
        
        captured = []
        original_send_email = EmailService.send_email
        
        @staticmethod
        async def mock_send_email(to_email, subject, html_content, email_type="generic"):
            captured.append({'html_content': html_content})
            return {"success": True}
        
        EmailService.send_email = mock_send_email
        
        try:
            await EmailService.send_acceptance_confirmation_email(
                to_email="test@test.com", to_name="Test", organizer_name="Org",
                appointment_title="Test", appointment_datetime="2026-02-15T14:00:00Z",
                appointment_type="video", meeting_provider="zoom",
                proof_link="https://example.com/proof/test"
            )
            
            html = captured[0]['html_content']
            assert "En ligne — Zoom" in html
            print("✓ 'zoom' correctly maps to 'En ligne — Zoom'")
        finally:
            EmailService.send_email = original_send_email
    
    @pytest.mark.asyncio
    async def test_teams_provider_label(self):
        """Verify 'teams' maps to 'Microsoft Teams'"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.email_service import EmailService
        
        captured = []
        original_send_email = EmailService.send_email
        
        @staticmethod
        async def mock_send_email(to_email, subject, html_content, email_type="generic"):
            captured.append({'html_content': html_content})
            return {"success": True}
        
        EmailService.send_email = mock_send_email
        
        try:
            await EmailService.send_acceptance_confirmation_email(
                to_email="test@test.com", to_name="Test", organizer_name="Org",
                appointment_title="Test", appointment_datetime="2026-02-15T14:00:00Z",
                appointment_type="video", meeting_provider="teams",
                proof_link="https://example.com/proof/test"
            )
            
            html = captured[0]['html_content']
            assert "En ligne — Microsoft Teams" in html
            print("✓ 'teams' correctly maps to 'En ligne — Microsoft Teams'")
        finally:
            EmailService.send_email = original_send_email
    
    @pytest.mark.asyncio
    async def test_meet_provider_label(self):
        """Verify 'meet' maps to 'Google Meet'"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.email_service import EmailService
        
        captured = []
        original_send_email = EmailService.send_email
        
        @staticmethod
        async def mock_send_email(to_email, subject, html_content, email_type="generic"):
            captured.append({'html_content': html_content})
            return {"success": True}
        
        EmailService.send_email = mock_send_email
        
        try:
            await EmailService.send_acceptance_confirmation_email(
                to_email="test@test.com", to_name="Test", organizer_name="Org",
                appointment_title="Test", appointment_datetime="2026-02-15T14:00:00Z",
                appointment_type="video", meeting_provider="meet",
                proof_link="https://example.com/proof/test"
            )
            
            html = captured[0]['html_content']
            assert "En ligne — Google Meet" in html
            print("✓ 'meet' correctly maps to 'En ligne — Google Meet'")
        finally:
            EmailService.send_email = original_send_email


class TestSubjectFormat:
    """Test email subject format"""
    
    @pytest.mark.asyncio
    async def test_subject_uses_new_format(self):
        """Verify subject uses 'Confirmation d'acces — {title}' format"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.email_service import EmailService
        
        captured = []
        original_send_email = EmailService.send_email
        
        @staticmethod
        async def mock_send_email(to_email, subject, html_content, email_type="generic"):
            captured.append({'subject': subject})
            return {"success": True}
        
        EmailService.send_email = mock_send_email
        
        try:
            await EmailService.send_acceptance_confirmation_email(
                to_email="test@test.com", to_name="Test", organizer_name="Org",
                appointment_title="Ma Réunion Importante",
                appointment_datetime="2026-02-15T14:00:00Z",
                appointment_type="physical"
            )
            
            subject = captured[0]['subject']
            assert subject == "Confirmation d'acces — Ma Réunion Importante", f"Unexpected subject: {subject}"
            print(f"✓ Subject format correct: {subject}")
            
            # Verify old format is NOT used
            assert "✅" not in subject, "Subject should NOT contain emoji"
            assert "Confirmation -" not in subject, "Subject should NOT use old format with hyphen"
        finally:
            EmailService.send_email = original_send_email


class TestCallerIntegration:
    """Test that webhooks.py and invitations.py pass correct params"""
    
    def test_webhooks_passes_appointment_type_and_meeting_provider(self):
        """Verify webhooks.py passes appointment_type and meeting_provider to email method"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        # Read webhooks.py and check the call
        with open('/app/backend/routers/webhooks.py', 'r') as f:
            content = f.read()
        
        # Check that send_acceptance_confirmation_email call includes new params
        assert "appointment_type=appointment.get('appointment_type'" in content, \
            "webhooks.py should pass appointment_type param"
        assert "meeting_provider=appointment.get('meeting_provider')" in content, \
            "webhooks.py should pass meeting_provider param"
        
        print("✓ webhooks.py passes appointment_type and meeting_provider to email method")
    
    def test_invitations_passes_appointment_type_and_meeting_provider(self):
        """Verify invitations.py passes appointment_type and meeting_provider to email method"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        # Read invitations.py and check the call
        with open('/app/backend/routers/invitations.py', 'r') as f:
            content = f.read()
        
        # Check that send_acceptance_confirmation_email call includes new params
        assert "appointment_type=appointment.get('appointment_type'" in content, \
            "invitations.py should pass appointment_type param"
        assert "meeting_provider=appointment.get('meeting_provider')" in content, \
            "invitations.py should pass meeting_provider param"
        
        print("✓ invitations.py passes appointment_type and meeting_provider to email method")


class TestHealthAndInvitationFlow:
    """Test basic API health and invitation flow still works"""
    
    def test_health_endpoint(self):
        """GET /api/health returns 200"""
        import requests
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get('status') == 'healthy'
        print(f"✓ Health endpoint returns 200: {data}")
    
    def test_invitation_respond_endpoint_exists(self):
        """POST /api/invitations/{token}/respond endpoint exists"""
        import requests
        
        # Use a fake token - we just want to verify the endpoint exists and returns proper error
        response = requests.post(
            f"{BASE_URL}/api/invitations/fake-token-12345/respond",
            json={"action": "accept"}
        )
        
        # Should return 404 (invitation not found), not 405 (method not allowed) or 500
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        data = response.json()
        assert "non trouvée" in data.get('detail', '').lower() or "not found" in data.get('detail', '').lower()
        print(f"✓ Invitation respond endpoint exists and returns 404 for invalid token")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
