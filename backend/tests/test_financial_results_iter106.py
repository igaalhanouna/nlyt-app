"""
Test Financial Results Section - Iteration 106
Tests the financial_summary API response for past appointments with attendance_evaluated=True
Verifies compensation_received_cents, compensation_role, beneficiaries, and status fields
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "igaal.hanouna@gmail.com"
TEST_PASSWORD = "OrgTest123!"

# Test appointments
APPOINTMENT_WITH_PENALTIES = "23970d2e-985c-4eda-a1cd-953ca117d783"  # E2E Stripe Real Penalty - 2 penalized participants
APPOINTMENT_WITH_CLEAN_RESULTS = "12132ca1-2f84-4d26-8104-cf24df4ba21d"  # test invitation - on_time + waived


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test organizer"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def authenticated_client(auth_token):
    """Session with auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestFinancialSummaryAPI:
    """Tests for GET /api/appointments/{id} financial_summary field"""

    def test_01_appointment_with_penalties_has_financial_summary(self, authenticated_client):
        """Verify appointment with penalties returns financial_summary"""
        response = authenticated_client.get(f"{BASE_URL}/api/appointments/{APPOINTMENT_WITH_PENALTIES}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('attendance_evaluated') is True, "attendance_evaluated should be True"
        assert 'financial_summary' in data, "financial_summary field should be present"
        assert isinstance(data['financial_summary'], list), "financial_summary should be a list"
        assert len(data['financial_summary']) > 0, "financial_summary should not be empty"
        print(f"✅ Appointment has financial_summary with {len(data['financial_summary'])} entries")

    def test_02_penalized_participant_has_correct_fields(self, authenticated_client):
        """Verify penalized participant has outcome, delay_minutes, capture_amount_cents, beneficiaries"""
        response = authenticated_client.get(f"{BASE_URL}/api/appointments/{APPOINTMENT_WITH_PENALTIES}")
        assert response.status_code == 200
        
        data = response.json()
        fin_summary = data.get('financial_summary', [])
        
        # Find a penalized participant (late or no_show)
        penalized = [f for f in fin_summary if f.get('outcome') in ('late', 'no_show')]
        assert len(penalized) > 0, "Should have at least one penalized participant"
        
        p = penalized[0]
        assert 'participant_id' in p, "participant_id should be present"
        assert p.get('outcome') in ('late', 'no_show'), f"outcome should be late or no_show, got {p.get('outcome')}"
        assert 'delay_minutes' in p, "delay_minutes should be present"
        assert 'capture_amount_cents' in p, "capture_amount_cents should be present"
        assert 'beneficiaries' in p, "beneficiaries should be present"
        assert 'guarantee_status' in p, "guarantee_status should be present"
        assert 'captured' in p, "captured field should be present"
        print(f"✅ Penalized participant has all required fields: outcome={p['outcome']}, delay={p.get('delay_minutes')}, capture={p.get('capture_amount_cents')}")

    def test_03_beneficiaries_structure(self, authenticated_client):
        """Verify beneficiaries array has correct structure (role, amount_cents)"""
        response = authenticated_client.get(f"{BASE_URL}/api/appointments/{APPOINTMENT_WITH_PENALTIES}")
        assert response.status_code == 200
        
        data = response.json()
        fin_summary = data.get('financial_summary', [])
        
        # Find participant with beneficiaries
        with_beneficiaries = [f for f in fin_summary if f.get('beneficiaries')]
        assert len(with_beneficiaries) > 0, "Should have at least one participant with beneficiaries"
        
        beneficiaries = with_beneficiaries[0]['beneficiaries']
        assert isinstance(beneficiaries, list), "beneficiaries should be a list"
        
        for b in beneficiaries:
            assert 'role' in b, "beneficiary should have role"
            assert 'amount_cents' in b, "beneficiary should have amount_cents"
            assert b['role'] in ('platform', 'organizer', 'affected', 'charity'), f"Invalid role: {b['role']}"
            assert isinstance(b['amount_cents'], int), "amount_cents should be int"
        
        print(f"✅ Beneficiaries structure correct: {len(beneficiaries)} beneficiaries")
        for b in beneficiaries:
            print(f"   - {b['role']}: {b['amount_cents']} cents")

    def test_04_compensation_received_cents_for_organizer(self, authenticated_client):
        """Verify organizer who received compensation has compensation_received_cents > 0"""
        response = authenticated_client.get(f"{BASE_URL}/api/appointments/{APPOINTMENT_WITH_PENALTIES}")
        assert response.status_code == 200
        
        data = response.json()
        fin_summary = data.get('financial_summary', [])
        
        # The organizer (participant_id starting with 8547230f) should have received compensation
        # from the other participant's penalty (2000 cents to organizer)
        organizer_entry = None
        for f in fin_summary:
            if f.get('participant_id', '').startswith('8547230f'):
                organizer_entry = f
                break
        
        if organizer_entry:
            comp_received = organizer_entry.get('compensation_received_cents', 0)
            comp_role = organizer_entry.get('compensation_role')
            print(f"✅ Organizer entry found: compensation_received_cents={comp_received}, compensation_role={comp_role}")
            # The organizer was penalized 25€ (all to platform) AND received 20€ from other participant
            assert comp_received == 2000, f"Expected 2000 cents compensation, got {comp_received}"
            assert comp_role == 'organizer', f"Expected role 'organizer', got {comp_role}"
        else:
            # If organizer entry not found by ID, check if any entry has compensation
            with_compensation = [f for f in fin_summary if f.get('compensation_received_cents', 0) > 0]
            assert len(with_compensation) > 0, "At least one participant should have compensation_received_cents > 0"
            print(f"✅ Found {len(with_compensation)} participant(s) with compensation received")

    def test_05_clean_results_appointment(self, authenticated_client):
        """Verify appointment with on_time and waived outcomes has correct financial_summary"""
        response = authenticated_client.get(f"{BASE_URL}/api/appointments/{APPOINTMENT_WITH_CLEAN_RESULTS}")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('attendance_evaluated') is True, "attendance_evaluated should be True"
        
        fin_summary = data.get('financial_summary', [])
        assert len(fin_summary) > 0, "financial_summary should not be empty"
        
        # Check outcomes
        outcomes = [f.get('outcome') for f in fin_summary]
        assert 'on_time' in outcomes, "Should have on_time outcome"
        assert 'waived' in outcomes, "Should have waived outcome"
        
        # on_time and waived should not have penalties
        for f in fin_summary:
            if f.get('outcome') in ('on_time', 'waived'):
                assert f.get('captured') is False or f.get('captured') is None, f"on_time/waived should not be captured"
        
        print(f"✅ Clean results appointment has correct outcomes: {outcomes}")

    def test_06_review_required_field(self, authenticated_client):
        """Verify review_required field is present in financial_summary"""
        response = authenticated_client.get(f"{BASE_URL}/api/appointments/{APPOINTMENT_WITH_PENALTIES}")
        assert response.status_code == 200
        
        data = response.json()
        fin_summary = data.get('financial_summary', [])
        
        for f in fin_summary:
            assert 'review_required' in f, "review_required field should be present"
            assert isinstance(f['review_required'], bool), "review_required should be boolean"
        
        print(f"✅ All entries have review_required field")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
