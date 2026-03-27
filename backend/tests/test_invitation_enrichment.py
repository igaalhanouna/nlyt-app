"""
Test Invitation Page Enrichment - Iteration 95
Tests the enriched participant invitation view with:
- EngagementSummary fields (penalty_amount, tolerance, cancellation_deadline)
- FinancialBreakdown fields (compensation %, commission %, charity %)
- Trust signal (confirmed_count, total_participants)
- Meeting join link security (only for finalized participants)
- Full location address (location_display_name)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test tokens provided by main agent
TOKEN_WITH_CONFIRMED = "ff28e36a-1e66-4be5-ae29-8bc8d129840b"  # confirmed_count > 0
TOKEN_NO_CONFIRMED = "2c24eb23-934d-4a88-908e-a1355a62272b"    # confirmed_count = 0
TOKEN_FINALIZED = "2adf14af-7f04-428d-8583-5b0a7cc0e4ad"       # accepted_guaranteed with meeting URL


class TestInvitationAPIEnrichment:
    """Test GET /api/invitations/{token} returns all new enrichment fields"""
    
    def test_invitation_returns_200(self):
        """Basic API health check"""
        response = requests.get(f"{BASE_URL}/api/invitations/{TOKEN_WITH_CONFIRMED}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ GET /api/invitations/{token} returns 200")
    
    def test_appointment_has_cancellation_deadline_hours(self):
        """Verify appointment.cancellation_deadline_hours is present"""
        response = requests.get(f"{BASE_URL}/api/invitations/{TOKEN_WITH_CONFIRMED}")
        data = response.json()
        assert "appointment" in data
        assert "cancellation_deadline_hours" in data["appointment"]
        assert isinstance(data["appointment"]["cancellation_deadline_hours"], (int, float))
        print(f"✅ cancellation_deadline_hours: {data['appointment']['cancellation_deadline_hours']}")
    
    def test_appointment_has_penalty_amount(self):
        """Verify appointment.penalty_amount is present"""
        response = requests.get(f"{BASE_URL}/api/invitations/{TOKEN_WITH_CONFIRMED}")
        data = response.json()
        assert "penalty_amount" in data["appointment"]
        assert isinstance(data["appointment"]["penalty_amount"], (int, float))
        print(f"✅ penalty_amount: {data['appointment']['penalty_amount']}")
    
    def test_appointment_has_penalty_currency(self):
        """Verify appointment.penalty_currency is present"""
        response = requests.get(f"{BASE_URL}/api/invitations/{TOKEN_WITH_CONFIRMED}")
        data = response.json()
        assert "penalty_currency" in data["appointment"]
        assert data["appointment"]["penalty_currency"] in ["EUR", "USD", "GBP"]
        print(f"✅ penalty_currency: {data['appointment']['penalty_currency']}")
    
    def test_appointment_has_location_display_name(self):
        """Verify appointment.location_display_name is present"""
        response = requests.get(f"{BASE_URL}/api/invitations/{TOKEN_WITH_CONFIRMED}")
        data = response.json()
        assert "location_display_name" in data["appointment"]
        print(f"✅ location_display_name present (value: '{data['appointment']['location_display_name']}')")
    
    def test_appointment_has_affected_compensation_percent(self):
        """Verify appointment.affected_compensation_percent is present"""
        response = requests.get(f"{BASE_URL}/api/invitations/{TOKEN_WITH_CONFIRMED}")
        data = response.json()
        assert "affected_compensation_percent" in data["appointment"]
        assert isinstance(data["appointment"]["affected_compensation_percent"], (int, float))
        print(f"✅ affected_compensation_percent: {data['appointment']['affected_compensation_percent']}%")
    
    def test_appointment_has_platform_commission_percent(self):
        """Verify appointment.platform_commission_percent is present"""
        response = requests.get(f"{BASE_URL}/api/invitations/{TOKEN_WITH_CONFIRMED}")
        data = response.json()
        assert "platform_commission_percent" in data["appointment"]
        assert isinstance(data["appointment"]["platform_commission_percent"], (int, float))
        print(f"✅ platform_commission_percent: {data['appointment']['platform_commission_percent']}%")
    
    def test_appointment_has_charity_percent(self):
        """Verify appointment.charity_percent is present"""
        response = requests.get(f"{BASE_URL}/api/invitations/{TOKEN_WITH_CONFIRMED}")
        data = response.json()
        assert "charity_percent" in data["appointment"]
        assert isinstance(data["appointment"]["charity_percent"], (int, float))
        print(f"✅ charity_percent: {data['appointment']['charity_percent']}%")
    
    def test_response_has_confirmed_count(self):
        """Verify confirmed_count is present in response"""
        response = requests.get(f"{BASE_URL}/api/invitations/{TOKEN_WITH_CONFIRMED}")
        data = response.json()
        assert "confirmed_count" in data
        assert isinstance(data["confirmed_count"], int)
        print(f"✅ confirmed_count: {data['confirmed_count']}")
    
    def test_response_has_total_participants(self):
        """Verify total_participants is present in response"""
        response = requests.get(f"{BASE_URL}/api/invitations/{TOKEN_WITH_CONFIRMED}")
        data = response.json()
        assert "total_participants" in data
        assert isinstance(data["total_participants"], int)
        print(f"✅ total_participants: {data['total_participants']}")


class TestTrustSignal:
    """Test trust signal visibility based on confirmed_count"""
    
    def test_trust_signal_visible_when_confirmed_count_gt_0(self):
        """Trust signal should be visible when confirmed_count > 0"""
        response = requests.get(f"{BASE_URL}/api/invitations/{TOKEN_WITH_CONFIRMED}")
        data = response.json()
        assert data["confirmed_count"] > 0, "Expected confirmed_count > 0 for this token"
        print(f"✅ Trust signal visible: {data['confirmed_count']} participant(s) confirmed")
    
    def test_trust_signal_hidden_when_confirmed_count_eq_0(self):
        """Trust signal should be hidden when confirmed_count = 0"""
        response = requests.get(f"{BASE_URL}/api/invitations/{TOKEN_NO_CONFIRMED}")
        data = response.json()
        assert data["confirmed_count"] == 0, f"Expected confirmed_count = 0, got {data['confirmed_count']}"
        print("✅ Trust signal hidden: confirmed_count = 0")


class TestMeetingLinkSecurity:
    """Test meeting_join_url access control based on participant status"""
    
    def test_meeting_url_hidden_for_invited_participant(self):
        """Meeting URL should be empty for non-finalized participant (status=invited)"""
        response = requests.get(f"{BASE_URL}/api/invitations/{TOKEN_WITH_CONFIRMED}")
        data = response.json()
        
        # Verify participant is not finalized
        assert data["participant"]["status"] == "invited", f"Expected status=invited, got {data['participant']['status']}"
        
        # Meeting URL should be empty
        assert data["appointment"]["meeting_join_url"] == "", \
            f"Meeting URL should be empty for invited participant, got: {data['appointment']['meeting_join_url']}"
        print("✅ Meeting URL correctly hidden for non-finalized participant (status=invited)")
    
    def test_meeting_url_visible_for_finalized_participant(self):
        """Meeting URL should be visible for finalized participant (accepted/accepted_guaranteed)"""
        response = requests.get(f"{BASE_URL}/api/invitations/{TOKEN_FINALIZED}")
        data = response.json()
        
        # Verify participant is finalized
        assert data["participant"]["status"] in ["accepted", "accepted_guaranteed"], \
            f"Expected finalized status, got {data['participant']['status']}"
        
        # Meeting URL should be present
        assert data["appointment"]["meeting_join_url"] != "", \
            "Meeting URL should be visible for finalized participant"
        print(f"✅ Meeting URL visible for finalized participant: {data['appointment']['meeting_join_url']}")


class TestParticipantBadges:
    """Test participant status badges are returned correctly"""
    
    def test_other_participants_have_status(self):
        """Other participants should have status field for badge coloring"""
        response = requests.get(f"{BASE_URL}/api/invitations/{TOKEN_WITH_CONFIRMED}")
        data = response.json()
        
        assert "other_participants" in data
        for p in data["other_participants"]:
            assert "status" in p, f"Participant missing status: {p}"
            assert p["status"] in ["invited", "accepted", "accepted_guaranteed", "accepted_pending_guarantee", "declined", "cancelled_by_participant"]
        
        print(f"✅ {len(data['other_participants'])} other participants with valid status badges")


class TestEngagementRulesCard:
    """Test engagement_rules object is still present and correct"""
    
    def test_engagement_rules_present(self):
        """Verify engagement_rules object is present"""
        response = requests.get(f"{BASE_URL}/api/invitations/{TOKEN_WITH_CONFIRMED}")
        data = response.json()
        
        assert "engagement_rules" in data
        rules = data["engagement_rules"]
        
        # Check all required fields
        required_fields = [
            "cancellation_deadline_hours",
            "cancellation_deadline_formatted",
            "cancellation_deadline_passed",
            "can_cancel",
            "tolerated_delay_minutes",
            "penalty_amount",
            "penalty_currency",
            "affected_compensation_percent",
            "platform_commission_percent",
            "charity_percent"
        ]
        
        for field in required_fields:
            assert field in rules, f"Missing field in engagement_rules: {field}"
        
        print("✅ engagement_rules has all required fields")


class TestPhysicalAppointmentLocation:
    """Test location display for physical appointments"""
    
    def test_physical_appointment_shows_location(self):
        """Physical appointment should show location address"""
        response = requests.get(f"{BASE_URL}/api/invitations/{TOKEN_NO_CONFIRMED}")
        data = response.json()
        
        # This is a physical appointment
        assert data["appointment"]["appointment_type"] == "physical"
        assert data["appointment"]["location"] != "", "Physical appointment should have location"
        print(f"✅ Physical appointment location: {data['appointment']['location']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
