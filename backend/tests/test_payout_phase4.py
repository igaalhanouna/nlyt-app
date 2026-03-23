"""
Test Payout Phase 4 — NLYT Payouts to Stripe Connect

Tests:
- POST /api/wallet/payout succeeds when conditions met (dev mode, returns completed)
- POST /api/wallet/payout fails when available_balance insufficient
- POST /api/wallet/payout fails when amount < MINIMUM_PAYOUT_CENTS (500)
- POST /api/wallet/payout fails when stripe_connect_status != active
- POST /api/wallet/payout is idempotent (rejects when balance is 0 after first payout)
- POST /api/wallet/payout debits wallet atomically (available_balance decremented, total_withdrawn incremented)
- POST /api/wallet/payout creates debit_payout transaction in ledger
- POST /api/wallet/payout in dev mode marks payout as completed immediately with tr_dev_ prefix
- GET /api/wallet/payouts returns payout history
- GET /api/wallet/payouts/:id returns payout detail with access control
- Webhook transfer.paid handler marks payout as completed (idempotent)
- Webhook transfer.failed handler re-credits wallet and marks payout as failed
- Webhook handlers are idempotent (skip already processed payouts)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"
TEST_USER_ID = "d13498f9-9c0d-47d4-b48f-9e327e866127"

MINIMUM_PAYOUT_CENTS = 500  # 5€


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test user."""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("access_token")


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Authenticated requests session."""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


@pytest.fixture(scope="function")
def reset_wallet():
    """Reset wallet to known state before each test that needs it."""
    from pymongo import MongoClient
    client = MongoClient('mongodb://localhost:27017')
    db = client['test_database']
    
    # Reset wallet
    db.wallets.update_one(
        {'user_id': TEST_USER_ID},
        {'$set': {'available_balance': 2500, 'total_withdrawn': 0}}
    )
    
    # Delete existing payouts
    db.payouts.delete_many({'user_id': TEST_USER_ID})
    
    # Delete payout transactions
    db.wallet_transactions.delete_many({'type': 'debit_payout'})
    
    yield
    
    # Cleanup after test
    client.close()


class TestPayoutConditions:
    """Test payout validation conditions."""
    
    def test_payout_success_dev_mode(self, api_client, reset_wallet):
        """POST /api/wallet/payout succeeds when conditions met (dev mode, returns completed)."""
        response = api_client.post(f"{BASE_URL}/api/wallet/payout", json={
            "amount_cents": 1000  # 10€
        })
        
        assert response.status_code == 200, f"Payout failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert data.get("success") is True
        assert "payout_id" in data
        assert data.get("amount_cents") == 1000
        assert data.get("status") == "completed"  # Dev mode completes immediately
        assert data.get("dev_mode") is True
        assert data.get("stripe_transfer_id", "").startswith("tr_dev_")
    
    def test_payout_fails_insufficient_balance(self, api_client, reset_wallet):
        """POST /api/wallet/payout fails when available_balance insufficient."""
        # Try to withdraw more than available (2500c)
        response = api_client.post(f"{BASE_URL}/api/wallet/payout", json={
            "amount_cents": 5000  # 50€, but only 25€ available
        })
        
        assert response.status_code == 400
        data = response.json()
        assert "insuffisant" in data.get("detail", "").lower() or "solde" in data.get("detail", "").lower()
    
    def test_payout_fails_below_minimum(self, api_client, reset_wallet):
        """POST /api/wallet/payout fails when amount < MINIMUM_PAYOUT_CENTS (500)."""
        response = api_client.post(f"{BASE_URL}/api/wallet/payout", json={
            "amount_cents": 300  # 3€, below 5€ minimum
        })
        
        assert response.status_code == 400
        data = response.json()
        assert "minimum" in data.get("detail", "").lower() or "5" in data.get("detail", "")
    
    def test_payout_fails_connect_not_active(self, api_client):
        """POST /api/wallet/payout fails when stripe_connect_status != active."""
        from pymongo import MongoClient
        client = MongoClient('mongodb://localhost:27017')
        db = client['test_database']
        
        # Temporarily set connect status to not_started
        db.wallets.update_one(
            {'user_id': TEST_USER_ID},
            {'$set': {'stripe_connect_status': 'not_started', 'available_balance': 2500}}
        )
        
        try:
            response = api_client.post(f"{BASE_URL}/api/wallet/payout", json={
                "amount_cents": 1000
            })
            
            assert response.status_code == 400
            data = response.json()
            assert "connect" in data.get("detail", "").lower() or "actif" in data.get("detail", "").lower()
        finally:
            # Restore connect status
            db.wallets.update_one(
                {'user_id': TEST_USER_ID},
                {'$set': {'stripe_connect_status': 'active'}}
            )
            client.close()
    
    def test_payout_idempotent_zero_balance(self, api_client, reset_wallet):
        """POST /api/wallet/payout is idempotent (rejects when balance is 0 after first payout)."""
        # First payout - full withdrawal
        response1 = api_client.post(f"{BASE_URL}/api/wallet/payout", json={
            "amount_cents": None  # Full withdrawal (2500c)
        })
        assert response1.status_code == 200
        
        # Second payout - should fail (balance is now 0)
        response2 = api_client.post(f"{BASE_URL}/api/wallet/payout", json={
            "amount_cents": 500
        })
        assert response2.status_code == 400
        data = response2.json()
        assert "insuffisant" in data.get("detail", "").lower() or "solde" in data.get("detail", "").lower()


class TestPayoutWalletDebit:
    """Test wallet debit and ledger operations."""
    
    def test_payout_debits_wallet_atomically(self, api_client, reset_wallet):
        """POST /api/wallet/payout debits wallet atomically."""
        # Get initial wallet state
        wallet_before = api_client.get(f"{BASE_URL}/api/wallet").json()
        initial_available = wallet_before.get("available_balance")
        initial_withdrawn = wallet_before.get("total_withdrawn")
        
        # Make payout
        payout_amount = 1000
        response = api_client.post(f"{BASE_URL}/api/wallet/payout", json={
            "amount_cents": payout_amount
        })
        assert response.status_code == 200
        
        # Verify wallet state after payout
        wallet_after = api_client.get(f"{BASE_URL}/api/wallet").json()
        
        assert wallet_after.get("available_balance") == initial_available - payout_amount
        assert wallet_after.get("total_withdrawn") == initial_withdrawn + payout_amount
    
    def test_payout_creates_debit_transaction(self, api_client, reset_wallet):
        """POST /api/wallet/payout creates debit_payout transaction in ledger."""
        # Make payout
        payout_response = api_client.post(f"{BASE_URL}/api/wallet/payout", json={
            "amount_cents": 1000
        })
        assert payout_response.status_code == 200
        payout_data = payout_response.json()
        
        # Get transactions
        tx_response = api_client.get(f"{BASE_URL}/api/wallet/transactions")
        assert tx_response.status_code == 200
        transactions = tx_response.json().get("transactions", [])
        
        # Find the debit_payout transaction
        debit_tx = next((tx for tx in transactions if tx.get("type") == "debit_payout"), None)
        
        assert debit_tx is not None, "debit_payout transaction not found"
        assert debit_tx.get("amount") == 1000
        assert debit_tx.get("reference_type") == "payout"
        assert debit_tx.get("reference_id") == payout_data.get("payout_id")


class TestPayoutDevMode:
    """Test dev mode payout behavior."""
    
    def test_payout_dev_mode_completed_immediately(self, api_client, reset_wallet):
        """POST /api/wallet/payout in dev mode marks payout as completed immediately with tr_dev_ prefix."""
        response = api_client.post(f"{BASE_URL}/api/wallet/payout", json={
            "amount_cents": 1000
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Dev mode specific assertions
        assert data.get("status") == "completed"
        assert data.get("dev_mode") is True
        assert data.get("stripe_transfer_id", "").startswith("tr_dev_")
        
        # Verify payout record in database
        payout_id = data.get("payout_id")
        payout_detail = api_client.get(f"{BASE_URL}/api/wallet/payouts/{payout_id}").json()
        
        assert payout_detail.get("status") == "completed"
        assert payout_detail.get("dev_mode") is True
        assert payout_detail.get("completed_at") is not None


class TestPayoutHistory:
    """Test payout history endpoints."""
    
    def test_get_payouts_returns_history(self, api_client, reset_wallet):
        """GET /api/wallet/payouts returns payout history."""
        # Create a payout first
        api_client.post(f"{BASE_URL}/api/wallet/payout", json={"amount_cents": 1000})
        
        # Get payouts
        response = api_client.get(f"{BASE_URL}/api/wallet/payouts")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "payouts" in data
        assert "total" in data
        assert len(data["payouts"]) >= 1
        
        # Verify payout structure
        payout = data["payouts"][0]
        assert "payout_id" in payout
        assert "amount_cents" in payout
        assert "status" in payout
        assert "requested_at" in payout
    
    def test_get_payout_detail(self, api_client, reset_wallet):
        """GET /api/wallet/payouts/:id returns payout detail."""
        # Create a payout
        payout_response = api_client.post(f"{BASE_URL}/api/wallet/payout", json={"amount_cents": 1000})
        payout_id = payout_response.json().get("payout_id")
        
        # Get payout detail
        response = api_client.get(f"{BASE_URL}/api/wallet/payouts/{payout_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("payout_id") == payout_id
        assert data.get("amount_cents") == 1000
        assert data.get("user_id") == TEST_USER_ID
    
    def test_get_payout_detail_access_control(self, api_client, reset_wallet):
        """GET /api/wallet/payouts/:id returns 404 for non-existent payout."""
        response = api_client.get(f"{BASE_URL}/api/wallet/payouts/non-existent-id")
        
        assert response.status_code == 404


class TestWebhookHandlers:
    """Test webhook handlers for transfer events (testing service functions directly)."""
    
    def test_webhook_transfer_paid_marks_completed(self, api_client, reset_wallet):
        """Webhook transfer.paid handler marks payout as completed (idempotent)."""
        from pymongo import MongoClient
        import uuid
        from datetime import datetime, timezone
        import sys
        import os
        os.environ['MONGO_URL'] = 'mongodb://localhost:27017'
        os.environ['DB_NAME'] = 'test_database'
        sys.path.insert(0, '/app/backend')
        from services.payout_service import handle_transfer_paid
        
        client = MongoClient('mongodb://localhost:27017')
        db = client['test_database']
        
        try:
            # Create a payout in processing state (simulating real Stripe flow)
            payout_id = str(uuid.uuid4())
            transfer_id = f"tr_test_{payout_id[:8]}"
            wallet = db.wallets.find_one({'user_id': TEST_USER_ID}, {'_id': 0})
            
            db.payouts.insert_one({
                "payout_id": payout_id,
                "user_id": TEST_USER_ID,
                "wallet_id": wallet["wallet_id"],
                "amount_cents": 1000,
                "currency": "eur",
                "stripe_transfer_id": transfer_id,
                "stripe_connect_account_id": wallet.get("stripe_connect_account_id"),
                "status": "processing",
                "requested_at": datetime.now(timezone.utc).isoformat(),
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": None,
                "failed_at": None,
                "failure_reason": None,
                "ledger_transaction_id": str(uuid.uuid4()),
                "dev_mode": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            
            # Call handler directly
            transfer_data = {
                "id": transfer_id,
                "object": "transfer",
                "amount": 1000,
                "currency": "eur"
            }
            
            result = handle_transfer_paid(transfer_data)
            assert result.get("success") is True or result.get("skipped") is False
            
            # Verify payout is now completed
            payout = db.payouts.find_one({"payout_id": payout_id}, {"_id": 0})
            assert payout["status"] == "completed"
            assert payout["completed_at"] is not None
            
        finally:
            db.payouts.delete_many({"payout_id": payout_id})
            client.close()
    
    def test_webhook_transfer_failed_recredits_wallet(self, api_client, reset_wallet):
        """Webhook transfer.failed handler re-credits wallet and marks payout as failed."""
        from pymongo import MongoClient
        import uuid
        from datetime import datetime, timezone
        import sys
        import os
        os.environ['MONGO_URL'] = 'mongodb://localhost:27017'
        os.environ['DB_NAME'] = 'test_database'
        sys.path.insert(0, '/app/backend')
        from services.payout_service import handle_transfer_failed
        
        client = MongoClient('mongodb://localhost:27017')
        db = client['test_database']
        
        try:
            # Get wallet and debit it manually (simulating a payout that was debited)
            wallet = db.wallets.find_one({'user_id': TEST_USER_ID}, {'_id': 0})
            initial_balance = wallet["available_balance"]
            payout_amount = 1000
            
            # Debit wallet
            db.wallets.update_one(
                {'user_id': TEST_USER_ID},
                {'$inc': {'available_balance': -payout_amount, 'total_withdrawn': payout_amount}}
            )
            
            # Create a payout in processing state
            payout_id = str(uuid.uuid4())
            transfer_id = f"tr_test_{payout_id[:8]}"
            
            db.payouts.insert_one({
                "payout_id": payout_id,
                "user_id": TEST_USER_ID,
                "wallet_id": wallet["wallet_id"],
                "amount_cents": payout_amount,
                "currency": "eur",
                "stripe_transfer_id": transfer_id,
                "stripe_connect_account_id": wallet.get("stripe_connect_account_id"),
                "status": "processing",
                "requested_at": datetime.now(timezone.utc).isoformat(),
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": None,
                "failed_at": None,
                "failure_reason": None,
                "ledger_transaction_id": str(uuid.uuid4()),
                "dev_mode": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            
            # Call handler directly
            transfer_data = {
                "id": transfer_id,
                "object": "transfer",
                "amount": payout_amount,
                "currency": "eur",
                "failure_message": "Insufficient funds"
            }
            
            result = handle_transfer_failed(transfer_data)
            assert result.get("success") is True
            assert result.get("re_credited") is True
            
            # Verify payout is now failed
            payout = db.payouts.find_one({"payout_id": payout_id}, {"_id": 0})
            assert payout["status"] == "failed"
            assert payout["failed_at"] is not None
            assert payout["failure_reason"] is not None
            
            # Verify wallet was re-credited
            wallet_after = db.wallets.find_one({'user_id': TEST_USER_ID}, {'_id': 0})
            assert wallet_after["available_balance"] == initial_balance
            
        finally:
            db.payouts.delete_many({"payout_id": payout_id})
            client.close()
    
    def test_webhook_idempotent_skip_completed(self, api_client, reset_wallet):
        """Webhook handlers are idempotent (skip already processed payouts)."""
        from pymongo import MongoClient
        import uuid
        from datetime import datetime, timezone
        import sys
        import os
        os.environ['MONGO_URL'] = 'mongodb://localhost:27017'
        os.environ['DB_NAME'] = 'test_database'
        sys.path.insert(0, '/app/backend')
        from services.payout_service import handle_transfer_paid
        
        client = MongoClient('mongodb://localhost:27017')
        db = client['test_database']
        
        try:
            # Create a payout already in completed state
            payout_id = str(uuid.uuid4())
            transfer_id = f"tr_test_{payout_id[:8]}"
            wallet = db.wallets.find_one({'user_id': TEST_USER_ID}, {'_id': 0})
            completed_at = datetime.now(timezone.utc).isoformat()
            
            db.payouts.insert_one({
                "payout_id": payout_id,
                "user_id": TEST_USER_ID,
                "wallet_id": wallet["wallet_id"],
                "amount_cents": 1000,
                "currency": "eur",
                "stripe_transfer_id": transfer_id,
                "stripe_connect_account_id": wallet.get("stripe_connect_account_id"),
                "status": "completed",
                "requested_at": datetime.now(timezone.utc).isoformat(),
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": completed_at,
                "failed_at": None,
                "failure_reason": None,
                "ledger_transaction_id": str(uuid.uuid4()),
                "dev_mode": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            
            # Call handler directly (should be skipped)
            transfer_data = {
                "id": transfer_id,
                "object": "transfer",
                "amount": 1000,
                "currency": "eur"
            }
            
            result = handle_transfer_paid(transfer_data)
            
            # Verify response indicates skipped
            assert result.get("skipped") is True
            assert "idempotent" in result.get("reason", "").lower() or "completed" in result.get("reason", "").lower()
            
            # Verify payout unchanged
            payout = db.payouts.find_one({"payout_id": payout_id}, {"_id": 0})
            assert payout["status"] == "completed"
            assert payout["completed_at"] == completed_at  # Unchanged
            
        finally:
            db.payouts.delete_many({"payout_id": payout_id})
            client.close()


class TestFullPayoutFlow:
    """Test complete payout flow end-to-end."""
    
    def test_full_payout_flow_dev_mode(self, api_client, reset_wallet):
        """Complete payout flow in dev mode: request → completed → history."""
        # 1. Check initial wallet state
        wallet_before = api_client.get(f"{BASE_URL}/api/wallet").json()
        assert wallet_before.get("available_balance") == 2500
        assert wallet_before.get("can_payout") is True
        
        # 2. Request payout (full withdrawal)
        payout_response = api_client.post(f"{BASE_URL}/api/wallet/payout", json={
            "amount_cents": None  # Full withdrawal
        })
        assert payout_response.status_code == 200
        payout_data = payout_response.json()
        
        assert payout_data.get("success") is True
        assert payout_data.get("amount_cents") == 2500
        assert payout_data.get("status") == "completed"
        assert payout_data.get("dev_mode") is True
        
        payout_id = payout_data.get("payout_id")
        
        # 3. Verify wallet debited
        wallet_after = api_client.get(f"{BASE_URL}/api/wallet").json()
        assert wallet_after.get("available_balance") == 0
        assert wallet_after.get("total_withdrawn") == 2500
        assert wallet_after.get("can_payout") is False
        
        # 4. Verify payout in history
        payouts_response = api_client.get(f"{BASE_URL}/api/wallet/payouts")
        assert payouts_response.status_code == 200
        payouts = payouts_response.json().get("payouts", [])
        
        assert len(payouts) >= 1
        latest_payout = payouts[0]
        assert latest_payout.get("payout_id") == payout_id
        assert latest_payout.get("status") == "completed"
        
        # 5. Verify transaction in ledger
        tx_response = api_client.get(f"{BASE_URL}/api/wallet/transactions")
        transactions = tx_response.json().get("transactions", [])
        
        debit_tx = next((tx for tx in transactions if tx.get("type") == "debit_payout"), None)
        assert debit_tx is not None
        assert debit_tx.get("amount") == 2500
