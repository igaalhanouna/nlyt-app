"""
ICS Content Tests - Iteration 46
Tests for ICS file content changes:
1. ICS with token includes invitation link in DESCRIPTION
2. ICS without token has NO invitation link in DESCRIPTION
3. ICS DESCRIPTION contains NO direct visio links (zoom/teams/meet/proof URLs)
4. Cancelled appointment ICS shows ANNULE message with no links
5. Email ICS link includes ?token= parameter
6. Frontend ICS download links include ?token= parameter
"""
import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://check-in-flow-1.preview.emergentagent.com').rstrip('/')

# Test data from review_request
ACTIVE_APPOINTMENT_ID = "a860bab5-c885-4787-a73e-3779529d3b8a"
VALID_TOKEN = "17b556f4-876f-44c1-86b9-0203dced05d3"
CANCELLED_APPOINTMENT_ID = "3250f725-9daf-4911-bedc-b001f733c4d7"


class TestHealthEndpoint:
    """Health check test"""
    
    def test_health_returns_200(self):
        """GET /api/health returns 200"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("PASS: Health endpoint returns 200 with status=healthy")


class TestICSWithToken:
    """Tests for ICS endpoint with token parameter"""
    
    def test_ics_with_token_includes_invitation_link(self):
        """GET /api/calendar/export/ics/{apt_id}?token={valid_token} returns ICS with invitation link"""
        response = requests.get(f"{BASE_URL}/api/calendar/export/ics/{ACTIVE_APPOINTMENT_ID}?token={VALID_TOKEN}")
        assert response.status_code == 200
        
        ics_content = response.text
        
        # Check for invitation link in DESCRIPTION
        assert "/invitation/" in ics_content, "ICS should contain /invitation/ link when token provided"
        assert VALID_TOKEN in ics_content, "ICS should contain the participant's token in invitation link"
        print("PASS: ICS with token includes invitation link in DESCRIPTION")
    
    def test_ics_with_token_no_direct_visio_links(self):
        """ICS DESCRIPTION contains NO direct visio links (zoom/teams/meet/proof URLs)"""
        response = requests.get(f"{BASE_URL}/api/calendar/export/ics/{ACTIVE_APPOINTMENT_ID}?token={VALID_TOKEN}")
        assert response.status_code == 200
        
        ics_content = response.text.lower()
        
        # Check for forbidden URLs
        assert "zoom.us" not in ics_content, "ICS should NOT contain zoom.us link"
        assert "teams.microsoft" not in ics_content, "ICS should NOT contain teams.microsoft link"
        assert "meet.google" not in ics_content, "ICS should NOT contain meet.google link"
        assert "/proof/" not in ics_content, "ICS should NOT contain /proof/ link"
        print("PASS: ICS DESCRIPTION contains NO direct visio/proof links")


class TestICSWithoutToken:
    """Tests for ICS endpoint without token parameter"""
    
    def test_ics_without_token_no_invitation_link(self):
        """GET /api/calendar/export/ics/{apt_id} (no token) returns ICS WITHOUT invitation link"""
        response = requests.get(f"{BASE_URL}/api/calendar/export/ics/{ACTIVE_APPOINTMENT_ID}")
        assert response.status_code == 200
        
        ics_content = response.text
        
        # Check that invitation link is NOT present
        assert "/invitation/" not in ics_content, "ICS without token should NOT contain /invitation/ link"
        print("PASS: ICS without token has NO invitation link in DESCRIPTION")
    
    def test_ics_without_token_still_has_basic_info(self):
        """ICS without token still contains basic appointment info"""
        response = requests.get(f"{BASE_URL}/api/calendar/export/ics/{ACTIVE_APPOINTMENT_ID}")
        assert response.status_code == 200
        
        ics_content = response.text
        
        # Check for basic ICS structure
        assert "BEGIN:VCALENDAR" in ics_content
        assert "BEGIN:VEVENT" in ics_content
        assert "SUMMARY:" in ics_content
        assert "DESCRIPTION:" in ics_content
        assert "Genere par NLYT" in ics_content
        print("PASS: ICS without token contains basic appointment info")


class TestICSCancelledAppointment:
    """Tests for ICS of cancelled appointments"""
    
    def test_cancelled_appointment_ics_shows_annule(self):
        """ICS DESCRIPTION for cancelled appointment shows ANNULE message"""
        response = requests.get(f"{BASE_URL}/api/calendar/export/ics/{CANCELLED_APPOINTMENT_ID}")
        assert response.status_code == 200
        
        ics_content = response.text
        
        # Check for ANNULE in title
        assert "[ANNULE]" in ics_content, "Cancelled appointment ICS should have [ANNULE] in title"
        
        # Check for cancellation message in description
        assert "CE RENDEZ-VOUS A ETE ANNULE" in ics_content, "Cancelled appointment should have cancellation message"
        
        # Check status is CANCELLED
        assert "STATUS:CANCELLED" in ics_content, "Cancelled appointment should have STATUS:CANCELLED"
        print("PASS: Cancelled appointment ICS shows ANNULE message")
    
    def test_cancelled_appointment_ics_no_links(self):
        """Cancelled appointment ICS has no invitation/visio/proof links"""
        response = requests.get(f"{BASE_URL}/api/calendar/export/ics/{CANCELLED_APPOINTMENT_ID}")
        assert response.status_code == 200
        
        ics_content = response.text.lower()
        
        # Check for no links
        assert "/invitation/" not in ics_content, "Cancelled ICS should NOT contain /invitation/ link"
        assert "/proof/" not in ics_content, "Cancelled ICS should NOT contain /proof/ link"
        assert "zoom.us" not in ics_content, "Cancelled ICS should NOT contain zoom.us link"
        assert "teams.microsoft" not in ics_content, "Cancelled ICS should NOT contain teams link"
        assert "meet.google" not in ics_content, "Cancelled ICS should NOT contain meet.google link"
        print("PASS: Cancelled appointment ICS has no links")


class TestEmailICSLink:
    """Tests for email ICS link format in code"""
    
    def test_email_ics_link_includes_token(self):
        """Email ICS link (in send_confirmation_email_once helper) includes ?token= parameter"""
        # Read the invitations.py file to verify the code
        invitations_path = "/app/backend/routers/invitations.py"
        
        with open(invitations_path, 'r') as f:
            content = f.read()
        
        # Check for the ics_link format with token
        assert 'ics_link = f"{frontend_url}/api/calendar/export/ics/{apt_id}?token={token}"' in content, \
            "Email ICS link should include ?token= parameter"
        print("PASS: Email ICS link in send_confirmation_email_once includes ?token= parameter")


class TestFrontendICSLinks:
    """Tests for frontend ICS download links"""
    
    def test_frontend_ics_links_include_token(self):
        """Frontend InvitationPage ICS download links include ?token= parameter"""
        # Read the InvitationPage.js file to verify the code
        invitation_page_path = "/app/frontend/src/pages/invitations/InvitationPage.js"
        
        with open(invitation_page_path, 'r') as f:
            content = f.read()
        
        # Check for ICS links with token parameter
        # Pattern: href={`${API_URL}/api/calendar/export/ics/${appointment.appointment_id}?token=${token}`}
        ics_link_pattern = r'\$\{API_URL\}/api/calendar/export/ics/\$\{appointment\.appointment_id\}\?token=\$\{token\}'
        matches = re.findall(ics_link_pattern, content)
        
        assert len(matches) >= 2, f"Expected at least 2 ICS links with token in InvitationPage.js, found {len(matches)}"
        print(f"PASS: Frontend InvitationPage has {len(matches)} ICS download links with ?token= parameter")


class TestICSContentFormat:
    """Tests for ICS content format and structure"""
    
    def test_ics_location_shows_visio_label(self):
        """LOCATION field shows 'Visio - {provider}' for video appointments (label, not link)"""
        # Get a video appointment ICS (the cancelled one was a video appointment)
        response = requests.get(f"{BASE_URL}/api/calendar/export/ics/{CANCELLED_APPOINTMENT_ID}")
        assert response.status_code == 200
        
        ics_content = response.text
        
        # Check LOCATION field format
        assert "LOCATION:Visio - " in ics_content, "Video appointment should have 'Visio - {provider}' in LOCATION"
        print("PASS: LOCATION field shows 'Visio - {provider}' label for video appointments")
    
    def test_ics_uses_escaped_newlines(self):
        """ICS DESCRIPTION uses escaped newlines (\\n in ICS format)"""
        response = requests.get(f"{BASE_URL}/api/calendar/export/ics/{ACTIVE_APPOINTMENT_ID}?token={VALID_TOKEN}")
        assert response.status_code == 200
        
        ics_content = response.text
        
        # ICS format uses \\n for newlines in DESCRIPTION
        assert "\\n" in ics_content, "ICS DESCRIPTION should use escaped newlines"
        print("PASS: ICS DESCRIPTION uses escaped newlines")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
