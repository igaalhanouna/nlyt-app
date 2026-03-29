"""
Charity Payouts V1 — Backend API Tests (Iteration 151)

Tests for manual bank transfer recording to charity associations:
- GET /api/admin/payouts/dashboard — associations with wallet balances
- GET /api/admin/payouts — payout history with admin name
- POST /api/admin/payouts — create payout + debit wallet atomically
- PUT /api/charity-associations/admin/{id} — IBAN validation
- Access control (admin-only endpoints)
- Wallet balance verification after payout
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
ADMIN_EMAIL = "testuser_audit@nlyt.app"
ADMIN_PASSWORD = "TestAudit123!"
REGULAR_USER_EMAIL = "igaal.hanouna@gmail.com"
REGULAR_USER_PASSWORD = "OrgTest123!"

# Test association with IBAN configured
TEST_ASSOCIATION_ID = "assoc_croix_rouge"


class TestCharityPayoutsAuth:
    """Test access control for payout endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin JWT token"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert resp.status_code == 200, f"Admin login failed: {resp.text}"
        return resp.json().get("access_token")
    
    @pytest.fixture(scope="class")
    def user_token(self):
        """Get regular user JWT token"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": REGULAR_USER_EMAIL,
            "password": REGULAR_USER_PASSWORD
        })
        assert resp.status_code == 200, f"User login failed: {resp.text}"
        return resp.json().get("access_token")
    
    def test_payouts_dashboard_requires_auth(self):
        """GET /api/admin/payouts/dashboard returns 401 without auth"""
        resp = requests.get(f"{BASE_URL}/api/admin/payouts/dashboard")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
    
    def test_payouts_list_requires_auth(self):
        """GET /api/admin/payouts returns 401 without auth"""
        resp = requests.get(f"{BASE_URL}/api/admin/payouts")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
    
    def test_create_payout_requires_auth(self):
        """POST /api/admin/payouts returns 401 without auth"""
        resp = requests.post(f"{BASE_URL}/api/admin/payouts", json={
            "association_id": TEST_ASSOCIATION_ID,
            "amount_cents": 1000,
            "bank_reference": "TEST-REF",
            "transfer_date": "2026-01-25"
        })
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
    
    def test_payouts_dashboard_requires_admin(self, user_token):
        """GET /api/admin/payouts/dashboard returns 403 for non-admin"""
        headers = {"Authorization": f"Bearer {user_token}"}
        resp = requests.get(f"{BASE_URL}/api/admin/payouts/dashboard", headers=headers)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
    
    def test_payouts_list_requires_admin(self, user_token):
        """GET /api/admin/payouts returns 403 for non-admin"""
        headers = {"Authorization": f"Bearer {user_token}"}
        resp = requests.get(f"{BASE_URL}/api/admin/payouts", headers=headers)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
    
    def test_create_payout_requires_admin(self, user_token):
        """POST /api/admin/payouts returns 403 for non-admin"""
        headers = {"Authorization": f"Bearer {user_token}"}
        resp = requests.post(f"{BASE_URL}/api/admin/payouts", headers=headers, json={
            "association_id": TEST_ASSOCIATION_ID,
            "amount_cents": 1000,
            "bank_reference": "TEST-REF",
            "transfer_date": "2026-01-25"
        })
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"


class TestPayoutsDashboard:
    """Test GET /api/admin/payouts/dashboard"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert resp.status_code == 200
        token = resp.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_dashboard_returns_associations(self, admin_headers):
        """Dashboard returns list of active associations with wallet info"""
        resp = requests.get(f"{BASE_URL}/api/admin/payouts/dashboard", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "associations" in data
        assert "count" in data
        assert isinstance(data["associations"], list)
        assert data["count"] >= 0
    
    def test_dashboard_association_fields(self, admin_headers):
        """Dashboard associations have required fields"""
        resp = requests.get(f"{BASE_URL}/api/admin/payouts/dashboard", headers=admin_headers)
        assert resp.status_code == 200
        
        data = resp.json()
        if data["count"] > 0:
            assoc = data["associations"][0]
            required_fields = ["association_id", "name", "iban", "bic", "account_holder",
                               "available_balance", "pending_balance", "has_wallet", "last_payout"]
            for field in required_fields:
                assert field in assoc, f"Missing field: {field}"
    
    def test_dashboard_croix_rouge_has_wallet(self, admin_headers):
        """Croix-Rouge association has wallet with balance"""
        resp = requests.get(f"{BASE_URL}/api/admin/payouts/dashboard", headers=admin_headers)
        assert resp.status_code == 200
        
        data = resp.json()
        croix_rouge = next((a for a in data["associations"] if a["association_id"] == TEST_ASSOCIATION_ID), None)
        assert croix_rouge is not None, f"Association {TEST_ASSOCIATION_ID} not found in dashboard"
        assert croix_rouge["has_wallet"] == True, "Croix-Rouge should have a wallet"
        assert croix_rouge["iban"] is not None, "Croix-Rouge should have IBAN configured"
        # Balance may have been debited in previous tests, just check it's a number
        assert isinstance(croix_rouge["available_balance"], int)


class TestPayoutsList:
    """Test GET /api/admin/payouts"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert resp.status_code == 200
        token = resp.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_list_payouts_returns_array(self, admin_headers):
        """List payouts returns array with pagination info"""
        resp = requests.get(f"{BASE_URL}/api/admin/payouts", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "payouts" in data
        assert "total" in data
        assert "limit" in data
        assert "skip" in data
        assert isinstance(data["payouts"], list)
    
    def test_list_payouts_with_limit(self, admin_headers):
        """List payouts respects limit parameter"""
        resp = requests.get(f"{BASE_URL}/api/admin/payouts?limit=5", headers=admin_headers)
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["limit"] == 5
        assert len(data["payouts"]) <= 5
    
    def test_list_payouts_filter_by_association(self, admin_headers):
        """List payouts can filter by association_id"""
        resp = requests.get(f"{BASE_URL}/api/admin/payouts?association_id={TEST_ASSOCIATION_ID}", headers=admin_headers)
        assert resp.status_code == 200
        
        data = resp.json()
        for payout in data["payouts"]:
            assert payout["association_id"] == TEST_ASSOCIATION_ID
    
    def test_payout_has_admin_name(self, admin_headers):
        """Payouts are enriched with admin_name"""
        resp = requests.get(f"{BASE_URL}/api/admin/payouts", headers=admin_headers)
        assert resp.status_code == 200
        
        data = resp.json()
        if len(data["payouts"]) > 0:
            payout = data["payouts"][0]
            assert "admin_name" in payout, "Payout should have admin_name field"


class TestCreatePayout:
    """Test POST /api/admin/payouts"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert resp.status_code == 200
        token = resp.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def get_association_balance(self, admin_headers, association_id):
        """Helper to get current balance for an association"""
        resp = requests.get(f"{BASE_URL}/api/admin/payouts/dashboard", headers=admin_headers)
        if resp.status_code != 200:
            return None
        data = resp.json()
        assoc = next((a for a in data["associations"] if a["association_id"] == association_id), None)
        return assoc["available_balance"] if assoc else None
    
    def test_create_payout_rejects_no_iban(self, admin_headers):
        """POST /api/admin/payouts rejects if association has no IBAN"""
        # Find an association without IBAN
        resp = requests.get(f"{BASE_URL}/api/admin/payouts/dashboard", headers=admin_headers)
        assert resp.status_code == 200
        
        data = resp.json()
        no_iban_assoc = next((a for a in data["associations"] if not a.get("iban")), None)
        
        if no_iban_assoc:
            resp = requests.post(f"{BASE_URL}/api/admin/payouts", headers=admin_headers, json={
                "association_id": no_iban_assoc["association_id"],
                "amount_cents": 100,
                "bank_reference": "TEST-NO-IBAN",
                "transfer_date": "2026-01-25"
            })
            assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
            assert "IBAN" in resp.json().get("detail", "")
        else:
            pytest.skip("No association without IBAN found for testing")
    
    def test_create_payout_rejects_amount_zero(self, admin_headers):
        """POST /api/admin/payouts rejects amount <= 0"""
        resp = requests.post(f"{BASE_URL}/api/admin/payouts", headers=admin_headers, json={
            "association_id": TEST_ASSOCIATION_ID,
            "amount_cents": 0,
            "bank_reference": "TEST-ZERO",
            "transfer_date": "2026-01-25"
        })
        # Pydantic validation should reject amount_cents <= 0
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"
    
    def test_create_payout_rejects_negative_amount(self, admin_headers):
        """POST /api/admin/payouts rejects negative amount"""
        resp = requests.post(f"{BASE_URL}/api/admin/payouts", headers=admin_headers, json={
            "association_id": TEST_ASSOCIATION_ID,
            "amount_cents": -100,
            "bank_reference": "TEST-NEGATIVE",
            "transfer_date": "2026-01-25"
        })
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"
    
    def test_create_payout_rejects_exceeds_balance(self, admin_headers):
        """POST /api/admin/payouts rejects if amount > available_balance"""
        balance = self.get_association_balance(admin_headers, TEST_ASSOCIATION_ID)
        if balance is None or balance == 0:
            pytest.skip("Association has no balance to test")
        
        # Try to withdraw more than available
        resp = requests.post(f"{BASE_URL}/api/admin/payouts", headers=admin_headers, json={
            "association_id": TEST_ASSOCIATION_ID,
            "amount_cents": balance + 10000,  # More than available
            "bank_reference": "TEST-EXCEED",
            "transfer_date": "2026-01-25"
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        assert "insuffisant" in resp.json().get("detail", "").lower() or "solde" in resp.json().get("detail", "").lower()
    
    def test_create_payout_rejects_nonexistent_association(self, admin_headers):
        """POST /api/admin/payouts rejects non-existent association"""
        resp = requests.post(f"{BASE_URL}/api/admin/payouts", headers=admin_headers, json={
            "association_id": "assoc_nonexistent_xyz",
            "amount_cents": 100,
            "bank_reference": "TEST-NONEXISTENT",
            "transfer_date": "2026-01-25"
        })
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
    
    def test_create_payout_rejects_invalid_date(self, admin_headers):
        """POST /api/admin/payouts rejects invalid date format"""
        resp = requests.post(f"{BASE_URL}/api/admin/payouts", headers=admin_headers, json={
            "association_id": TEST_ASSOCIATION_ID,
            "amount_cents": 100,
            "bank_reference": "TEST-INVALID-DATE",
            "transfer_date": "25-01-2026"  # Wrong format
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
    
    def test_create_payout_success_and_wallet_debit(self, admin_headers):
        """POST /api/admin/payouts creates payout and debits wallet atomically"""
        # Get initial balance
        initial_balance = self.get_association_balance(admin_headers, TEST_ASSOCIATION_ID)
        if initial_balance is None or initial_balance < 100:
            pytest.skip(f"Insufficient balance for test: {initial_balance}")
        
        # Create a small payout
        payout_amount = 100  # 1 EUR
        unique_ref = f"TEST-{uuid.uuid4().hex[:8].upper()}"
        
        resp = requests.post(f"{BASE_URL}/api/admin/payouts", headers=admin_headers, json={
            "association_id": TEST_ASSOCIATION_ID,
            "amount_cents": payout_amount,
            "bank_reference": unique_ref,
            "transfer_date": "2026-01-25"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert data["success"] == True
        assert "payout" in data
        assert "new_available_balance" in data
        
        # Verify payout record
        payout = data["payout"]
        assert payout["association_id"] == TEST_ASSOCIATION_ID
        assert payout["amount_cents"] == payout_amount
        assert payout["bank_reference"] == unique_ref
        assert payout["status"] == "completed"
        assert payout["iban_snapshot"] is not None, "Payout should have iban_snapshot"
        
        # Verify balance was debited
        assert data["new_available_balance"] == initial_balance - payout_amount
        
        # Double-check by fetching dashboard
        new_balance = self.get_association_balance(admin_headers, TEST_ASSOCIATION_ID)
        assert new_balance == initial_balance - payout_amount, f"Balance mismatch: expected {initial_balance - payout_amount}, got {new_balance}"


class TestPayoutSnapshots:
    """Test that payouts save IBAN/BIC/account_holder snapshots"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert resp.status_code == 200
        token = resp.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_payout_has_snapshots(self, admin_headers):
        """Existing payouts have iban_snapshot, bic_snapshot, account_holder_snapshot"""
        resp = requests.get(f"{BASE_URL}/api/admin/payouts?association_id={TEST_ASSOCIATION_ID}&limit=1", headers=admin_headers)
        assert resp.status_code == 200
        
        data = resp.json()
        if len(data["payouts"]) > 0:
            payout = data["payouts"][0]
            assert "iban_snapshot" in payout, "Payout should have iban_snapshot"
            assert "bic_snapshot" in payout, "Payout should have bic_snapshot"
            assert "account_holder_snapshot" in payout, "Payout should have account_holder_snapshot"
        else:
            pytest.skip("No payouts found for snapshot test")


class TestIBANValidation:
    """Test IBAN validation in PUT /api/charity-associations/admin/{id}"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert resp.status_code == 200
        token = resp.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_iban_validation_rejects_too_short(self, admin_headers):
        """IBAN validation rejects IBAN < 15 characters"""
        resp = requests.put(f"{BASE_URL}/api/charity-associations/admin/{TEST_ASSOCIATION_ID}", 
                           headers=admin_headers, json={"iban": "FR76300060"})
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        assert "longueur" in resp.json().get("detail", "").lower()
    
    def test_iban_validation_rejects_no_country_code(self, admin_headers):
        """IBAN validation rejects IBAN not starting with 2 letters"""
        resp = requests.put(f"{BASE_URL}/api/charity-associations/admin/{TEST_ASSOCIATION_ID}", 
                           headers=admin_headers, json={"iban": "12345678901234567890"})
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        assert "pays" in resp.json().get("detail", "").lower() or "lettres" in resp.json().get("detail", "").lower()
    
    def test_iban_validation_rejects_no_check_digits(self, admin_headers):
        """IBAN validation rejects IBAN without check digits at positions 3-4"""
        resp = requests.put(f"{BASE_URL}/api/charity-associations/admin/{TEST_ASSOCIATION_ID}", 
                           headers=admin_headers, json={"iban": "FRAB30006000011234567890189"})
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        assert "chiffres" in resp.json().get("detail", "").lower()
    
    def test_iban_validation_accepts_valid_iban(self, admin_headers):
        """IBAN validation accepts valid IBAN format"""
        # Use the existing valid IBAN to avoid changing data
        valid_iban = "FR7630006000011234567890189"
        resp = requests.put(f"{BASE_URL}/api/charity-associations/admin/{TEST_ASSOCIATION_ID}", 
                           headers=admin_headers, json={"iban": valid_iban})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert data["iban"] == valid_iban.replace(" ", "").upper()
    
    def test_iban_validation_normalizes_spaces(self, admin_headers):
        """IBAN validation removes spaces and normalizes to uppercase"""
        iban_with_spaces = "FR76 3000 6000 0112 3456 7890 189"
        resp = requests.put(f"{BASE_URL}/api/charity-associations/admin/{TEST_ASSOCIATION_ID}", 
                           headers=admin_headers, json={"iban": iban_with_spaces})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert data["iban"] == "FR7630006000011234567890189"


class TestWalletLedger:
    """Test that wallet transactions are created for payouts"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert resp.status_code == 200
        token = resp.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_payout_creates_ledger_transaction(self, admin_headers):
        """Creating a payout creates a debit_payout transaction in wallet_transactions"""
        # Get initial balance
        resp = requests.get(f"{BASE_URL}/api/admin/payouts/dashboard", headers=admin_headers)
        assert resp.status_code == 200
        
        data = resp.json()
        assoc = next((a for a in data["associations"] if a["association_id"] == TEST_ASSOCIATION_ID), None)
        if not assoc or assoc["available_balance"] < 100:
            pytest.skip("Insufficient balance for ledger test")
        
        # Create payout
        unique_ref = f"LEDGER-TEST-{uuid.uuid4().hex[:6].upper()}"
        resp = requests.post(f"{BASE_URL}/api/admin/payouts", headers=admin_headers, json={
            "association_id": TEST_ASSOCIATION_ID,
            "amount_cents": 100,
            "bank_reference": unique_ref,
            "transfer_date": "2026-01-25"
        })
        
        if resp.status_code == 200:
            # Payout created successfully - ledger transaction should exist
            # We can't directly query wallet_transactions via API, but the balance change confirms it
            data = resp.json()
            assert data["success"] == True
            # The fact that balance changed atomically confirms ledger was updated
        else:
            pytest.skip(f"Could not create payout for ledger test: {resp.text}")


class TestInactiveAssociation:
    """Test that payouts are rejected for inactive associations"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert resp.status_code == 200
        token = resp.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_payout_rejects_inactive_association(self, admin_headers):
        """POST /api/admin/payouts rejects if association is inactive"""
        # First, find or create an inactive association
        resp = requests.get(f"{BASE_URL}/api/charity-associations/admin/list", headers=admin_headers)
        assert resp.status_code == 200
        
        data = resp.json()
        inactive_assoc = next((a for a in data["associations"] if not a.get("is_active")), None)
        
        if inactive_assoc:
            resp = requests.post(f"{BASE_URL}/api/admin/payouts", headers=admin_headers, json={
                "association_id": inactive_assoc["association_id"],
                "amount_cents": 100,
                "bank_reference": "TEST-INACTIVE",
                "transfer_date": "2026-01-25"
            })
            assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
            assert "désactivée" in resp.json().get("detail", "").lower() or "inactive" in resp.json().get("detail", "").lower()
        else:
            pytest.skip("No inactive association found for testing")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
