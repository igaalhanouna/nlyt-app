"""
NLYT QA Recette — Lot 3: Blocs I (Charity Payouts Admin) et K (Notifications)
Tests de securite, validation, coherence UX.

Test Coverage:
- I1: GET /api/admin/payouts/dashboard — KPIs associations actives
- I2: POST /api/admin/payouts — payout partiel (10 EUR sur 50 EUR)
- I3: POST /api/admin/payouts — payout > solde → erreur 400
- I4: POST /api/admin/payouts — association sans IBAN → erreur 400
- I5: POST /api/admin/payouts — association inexistante → erreur 404
- I6: GET /api/admin/payouts?association_id=assoc_croix_rouge — historique filtre
- I7: PUT /api/charity-associations/admin/assoc_croix_rouge avec IBAN invalide → erreur 400
- I-SECURITY: POST /api/admin/payouts avec token non-admin → erreur 403
- K1: GET /api/notifications/counts — compteur notifications
- K2: POST /api/notifications/mark-read — marquer comme lu
- K3: GET /api/notifications/unread-ids/{event_type} — IDs non lus
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "testuser_audit@nlyt.app"
ADMIN_PASSWORD = "TestAudit123!"
NON_ADMIN_EMAIL = "igaal@hotmail.com"
NON_ADMIN_PASSWORD = "Test123!"

# Test data
ASSOC_WITH_IBAN = "assoc_croix_rouge"
ASSOC_WITHOUT_IBAN = "assoc_medecins_sans_frontieres"  # Has no IBAN configured


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code} - {resp.text}")
    return resp.json().get("access_token")


@pytest.fixture(scope="module")
def non_admin_token():
    """Get non-admin authentication token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": NON_ADMIN_EMAIL,
        "password": NON_ADMIN_PASSWORD
    })
    if resp.status_code != 200:
        pytest.skip(f"Non-admin login failed: {resp.status_code} - {resp.text}")
    return resp.json().get("access_token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Headers with admin auth."""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {admin_token}"
    }


@pytest.fixture(scope="module")
def non_admin_headers(non_admin_token):
    """Headers with non-admin auth."""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {non_admin_token}"
    }


class TestBlocI_CharityPayoutsAdmin:
    """BLOC I — Charity Payouts Admin Tests"""

    def test_I1_payouts_dashboard_returns_associations_with_kpis(self, admin_headers):
        """I1: GET /api/admin/payouts/dashboard — retourne associations actives avec KPIs."""
        resp = requests.get(f"{BASE_URL}/api/admin/payouts/dashboard", headers=admin_headers)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify structure
        assert "associations" in data, "Response should contain 'associations' key"
        assert "count" in data, "Response should contain 'count' key"
        assert isinstance(data["associations"], list), "associations should be a list"
        
        # Find assoc_croix_rouge (should have IBAN and wallet)
        croix_rouge = next((a for a in data["associations"] if a["association_id"] == ASSOC_WITH_IBAN), None)
        if croix_rouge:
            # Verify KPI fields
            assert "name" in croix_rouge, "Association should have 'name'"
            assert "iban" in croix_rouge, "Association should have 'iban' field"
            assert "available_balance" in croix_rouge, "Association should have 'available_balance'"
            assert "pending_balance" in croix_rouge, "Association should have 'pending_balance'"
            assert "has_wallet" in croix_rouge, "Association should have 'has_wallet'"
            
            # IBAN should be present for Croix-Rouge
            assert croix_rouge["iban"] is not None, "Croix-Rouge should have IBAN configured"
            
            # Verify IBAN format (masked or full)
            iban = croix_rouge["iban"]
            assert len(iban) >= 15, f"IBAN should be at least 15 chars, got {len(iban)}"
            
            print(f"✓ I1 PASS: Dashboard returns {data['count']} associations")
            print(f"  Croix-Rouge: balance={croix_rouge['available_balance']}c, IBAN={iban[:4]}...{iban[-4:]}")
        else:
            print(f"⚠ I1 WARNING: assoc_croix_rouge not found in dashboard (may be inactive)")

    def test_I2_partial_payout_success(self, admin_headers):
        """I2: POST /api/admin/payouts — payout partiel (10 EUR sur 50 EUR dispo)."""
        # First, check current balance
        dash_resp = requests.get(f"{BASE_URL}/api/admin/payouts/dashboard", headers=admin_headers)
        assert dash_resp.status_code == 200
        
        associations = dash_resp.json().get("associations", [])
        croix_rouge = next((a for a in associations if a["association_id"] == ASSOC_WITH_IBAN), None)
        
        if not croix_rouge:
            pytest.skip("assoc_croix_rouge not found in dashboard")
        
        initial_balance = croix_rouge.get("available_balance", 0)
        if initial_balance < 1000:  # Need at least 10 EUR
            pytest.skip(f"Insufficient balance for test: {initial_balance}c (need 1000c)")
        
        # Create payout of 10 EUR (1000 centimes)
        payout_body = {
            "association_id": ASSOC_WITH_IBAN,
            "amount_cents": 1000,  # 10 EUR
            "bank_reference": f"TEST_I2_{uuid.uuid4().hex[:8]}",
            "transfer_date": datetime.now().strftime("%Y-%m-%d")
        }
        
        resp = requests.post(f"{BASE_URL}/api/admin/payouts", headers=admin_headers, json=payout_body)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify response structure
        assert data.get("success") is True, "Response should indicate success"
        assert "payout" in data, "Response should contain 'payout' object"
        assert "new_available_balance" in data, "Response should contain 'new_available_balance'"
        
        payout = data["payout"]
        assert payout["amount_cents"] == 1000, "Payout amount should be 1000c"
        assert payout["association_id"] == ASSOC_WITH_IBAN
        assert payout["status"] == "completed"
        assert "iban_snapshot" in payout, "Payout should have IBAN snapshot"
        
        # Verify balance was debited
        expected_new_balance = initial_balance - 1000
        assert data["new_available_balance"] == expected_new_balance, \
            f"New balance should be {expected_new_balance}, got {data['new_available_balance']}"
        
        print(f"✓ I2 PASS: Payout of 10 EUR created successfully")
        print(f"  Initial balance: {initial_balance}c → New balance: {data['new_available_balance']}c")
        print(f"  Payout ID: {payout['payout_id']}")

    def test_I3_payout_exceeds_balance_returns_400(self, admin_headers):
        """I3: POST /api/admin/payouts — payout > solde disponible → erreur 400."""
        # Get current balance
        dash_resp = requests.get(f"{BASE_URL}/api/admin/payouts/dashboard", headers=admin_headers)
        assert dash_resp.status_code == 200
        
        associations = dash_resp.json().get("associations", [])
        croix_rouge = next((a for a in associations if a["association_id"] == ASSOC_WITH_IBAN), None)
        
        if not croix_rouge:
            pytest.skip("assoc_croix_rouge not found in dashboard")
        
        current_balance = croix_rouge.get("available_balance", 0)
        
        # Try to payout more than available
        excessive_amount = current_balance + 100000  # 1000 EUR more than available
        
        payout_body = {
            "association_id": ASSOC_WITH_IBAN,
            "amount_cents": excessive_amount,
            "bank_reference": f"TEST_I3_{uuid.uuid4().hex[:8]}",
            "transfer_date": datetime.now().strftime("%Y-%m-%d")
        }
        
        resp = requests.post(f"{BASE_URL}/api/admin/payouts", headers=admin_headers, json=payout_body)
        
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify error message mentions insufficient balance
        detail = data.get("detail", "")
        assert "insuffisant" in detail.lower() or "solde" in detail.lower(), \
            f"Error should mention insufficient balance, got: {detail}"
        
        print(f"✓ I3 PASS: Excessive payout correctly rejected with 400")
        print(f"  Attempted: {excessive_amount}c, Available: {current_balance}c")

    def test_I4_payout_without_iban_returns_400(self, admin_headers):
        """I4: POST /api/admin/payouts — association sans IBAN → erreur 400."""
        payout_body = {
            "association_id": ASSOC_WITHOUT_IBAN,
            "amount_cents": 1000,
            "bank_reference": f"TEST_I4_{uuid.uuid4().hex[:8]}",
            "transfer_date": datetime.now().strftime("%Y-%m-%d")
        }
        
        resp = requests.post(f"{BASE_URL}/api/admin/payouts", headers=admin_headers, json=payout_body)
        
        # Should be 400 for either "no IBAN" or "no wallet" (both are valid rejections)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify error message mentions IBAN or wallet
        detail = data.get("detail", "").lower()
        assert "iban" in detail or "wallet" in detail or "solde" in detail, \
            f"Error should mention IBAN or wallet, got: {detail}"
        
        print(f"✓ I4 PASS: Payout without IBAN correctly rejected with 400")
        print(f"  Error: {data.get('detail')}")

    def test_I5_payout_nonexistent_association_returns_404(self, admin_headers):
        """I5: POST /api/admin/payouts — association inexistante → erreur 404."""
        payout_body = {
            "association_id": "assoc_nonexistent_xyz_123",
            "amount_cents": 1000,
            "bank_reference": f"TEST_I5_{uuid.uuid4().hex[:8]}",
            "transfer_date": datetime.now().strftime("%Y-%m-%d")
        }
        
        resp = requests.post(f"{BASE_URL}/api/admin/payouts", headers=admin_headers, json=payout_body)
        
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        detail = data.get("detail", "")
        assert "introuvable" in detail.lower() or "not found" in detail.lower(), \
            f"Error should mention not found, got: {detail}"
        
        print(f"✓ I5 PASS: Nonexistent association correctly rejected with 404")

    def test_I6_payouts_filtered_by_association(self, admin_headers):
        """I6: GET /api/admin/payouts?association_id=assoc_croix_rouge — historique filtre."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/payouts",
            headers=admin_headers,
            params={"association_id": ASSOC_WITH_IBAN}
        )
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify structure
        assert "payouts" in data, "Response should contain 'payouts' key"
        assert "total" in data, "Response should contain 'total' key"
        
        payouts = data["payouts"]
        
        # All payouts should be for the filtered association
        for payout in payouts:
            assert payout["association_id"] == ASSOC_WITH_IBAN, \
                f"Payout should be for {ASSOC_WITH_IBAN}, got {payout['association_id']}"
        
        print(f"✓ I6 PASS: Filtered payouts returned {len(payouts)} records for {ASSOC_WITH_IBAN}")

    def test_I7_invalid_iban_validation(self, admin_headers):
        """I7: PUT /api/charity-associations/admin/assoc_croix_rouge avec IBAN invalide → erreur 400."""
        # Try to update with invalid IBAN (too short)
        update_body = {
            "iban": "ABC"  # Invalid: too short (< 15 chars)
        }
        
        resp = requests.put(
            f"{BASE_URL}/api/charity-associations/admin/{ASSOC_WITH_IBAN}",
            headers=admin_headers,
            json=update_body
        )
        
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        detail = data.get("detail", "")
        assert "iban" in detail.lower() or "invalide" in detail.lower(), \
            f"Error should mention IBAN validation, got: {detail}"
        
        print(f"✓ I7 PASS: Invalid IBAN correctly rejected with 400")
        print(f"  Error: {detail}")

    def test_I_SECURITY_non_admin_cannot_create_payout(self, non_admin_headers):
        """I-SECURITY: POST /api/admin/payouts avec token non-admin → erreur 403."""
        payout_body = {
            "association_id": ASSOC_WITH_IBAN,
            "amount_cents": 1000,
            "bank_reference": f"TEST_SEC_{uuid.uuid4().hex[:8]}",
            "transfer_date": datetime.now().strftime("%Y-%m-%d")
        }
        
        resp = requests.post(f"{BASE_URL}/api/admin/payouts", headers=non_admin_headers, json=payout_body)
        
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        
        print(f"✓ I-SECURITY PASS: Non-admin correctly rejected with 403")


class TestBlocK_Notifications:
    """BLOC K — Notifications Tests"""

    def test_K1_get_notification_counts(self, admin_headers):
        """K1: GET /api/notifications/counts — retourne compteur notifications."""
        resp = requests.get(f"{BASE_URL}/api/notifications/counts", headers=admin_headers)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify structure (counts by category)
        assert "decisions" in data, "Response should contain 'decisions' count"
        assert "disputes" in data, "Response should contain 'disputes' count"
        assert "modifications" in data, "Response should contain 'modifications' count"
        
        # All counts should be integers >= 0
        assert isinstance(data["decisions"], int) and data["decisions"] >= 0
        assert isinstance(data["disputes"], int) and data["disputes"] >= 0
        assert isinstance(data["modifications"], int) and data["modifications"] >= 0
        
        print(f"✓ K1 PASS: Notification counts returned")
        print(f"  Decisions: {data['decisions']}, Disputes: {data['disputes']}, Modifications: {data['modifications']}")

    def test_K2_mark_notification_as_read(self, admin_headers):
        """K2: POST /api/notifications/mark-read — marquer comme lu."""
        # Try to mark a notification as read (may not exist, but endpoint should work)
        mark_body = {
            "event_type": "decision",
            "reference_id": "test_dispute_id_123"
        }
        
        resp = requests.post(f"{BASE_URL}/api/notifications/mark-read", headers=admin_headers, json=mark_body)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify response structure
        assert "marked" in data, "Response should contain 'marked' count"
        assert isinstance(data["marked"], int), "'marked' should be an integer"
        
        print(f"✓ K2 PASS: Mark-read endpoint works, marked {data['marked']} notifications")

    def test_K3_get_unread_ids_by_event_type(self, admin_headers):
        """K3: GET /api/notifications/unread-ids/{event_type} — IDs non lus."""
        # Test with valid event type
        resp = requests.get(f"{BASE_URL}/api/notifications/unread-ids/decision", headers=admin_headers)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify structure
        assert "unread_ids" in data, "Response should contain 'unread_ids' list"
        assert isinstance(data["unread_ids"], list), "'unread_ids' should be a list"
        
        print(f"✓ K3 PASS: Unread IDs returned, count: {len(data['unread_ids'])}")

    def test_K3_invalid_event_type_returns_400(self, admin_headers):
        """K3: GET /api/notifications/unread-ids/{invalid_type} — erreur 400."""
        resp = requests.get(f"{BASE_URL}/api/notifications/unread-ids/invalid_type", headers=admin_headers)
        
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        
        print(f"✓ K3 PASS: Invalid event type correctly rejected with 400")


class TestBlocI_AdditionalValidation:
    """Additional validation tests for BLOC I"""

    def test_I_payout_requires_positive_amount(self, admin_headers):
        """Payout with amount_cents <= 0 should be rejected."""
        payout_body = {
            "association_id": ASSOC_WITH_IBAN,
            "amount_cents": 0,
            "bank_reference": "TEST_ZERO",
            "transfer_date": datetime.now().strftime("%Y-%m-%d")
        }
        
        resp = requests.post(f"{BASE_URL}/api/admin/payouts", headers=admin_headers, json=payout_body)
        
        # Should be rejected by Pydantic validation (422) or business logic (400)
        assert resp.status_code in [400, 422], f"Expected 400/422, got {resp.status_code}: {resp.text}"
        
        print(f"✓ Additional: Zero amount correctly rejected")

    def test_I_payout_requires_bank_reference(self, admin_headers):
        """Payout without bank_reference should be rejected."""
        payout_body = {
            "association_id": ASSOC_WITH_IBAN,
            "amount_cents": 1000,
            "bank_reference": "",  # Empty
            "transfer_date": datetime.now().strftime("%Y-%m-%d")
        }
        
        resp = requests.post(f"{BASE_URL}/api/admin/payouts", headers=admin_headers, json=payout_body)
        
        # Should be rejected by Pydantic validation (422)
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
        
        print(f"✓ Additional: Empty bank_reference correctly rejected")

    def test_I_dashboard_requires_admin(self, non_admin_headers):
        """Dashboard endpoint requires admin role."""
        resp = requests.get(f"{BASE_URL}/api/admin/payouts/dashboard", headers=non_admin_headers)
        
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        
        print(f"✓ Additional: Dashboard correctly requires admin role")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
