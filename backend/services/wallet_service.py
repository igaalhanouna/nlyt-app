"""
Wallet Service — NLYT Internal Ledger

All amounts are stored in CENTIMES (integer) to avoid floating-point issues.
1€ = 100 centimes.

Wallet lifecycle:
  - Auto-created at user registration
  - Credits arrive as pending_balance (during 15-day contestation hold)
  - After hold expires, pending → available
  - Payout transfers available_balance to Stripe Connect Express
"""
import uuid
import logging
from datetime import datetime, timezone
from database import db

logger = logging.getLogger(__name__)

MINIMUM_PAYOUT_CENTS = 500  # 5€


def create_wallet(user_id: str, wallet_type: str = "user", currency: str = "eur") -> dict:
    """Create a wallet for a user. Idempotent — returns existing if already created."""
    existing = db.wallets.find_one({"user_id": user_id, "wallet_type": wallet_type}, {"_id": 0})
    if existing:
        return existing

    now = datetime.now(timezone.utc).isoformat()
    wallet = {
        "wallet_id": str(uuid.uuid4()),
        "user_id": user_id,
        "wallet_type": wallet_type,
        "available_balance": 0,
        "pending_balance": 0,
        "currency": currency,
        "stripe_connect_account_id": None,
        "stripe_connect_status": "not_started",
        "total_received": 0,
        "total_withdrawn": 0,
        "created_at": now,
        "updated_at": now,
    }
    db.wallets.insert_one(wallet)
    logger.info(f"[WALLET] Created wallet {wallet['wallet_id']} for user {user_id} (type={wallet_type})")
    wallet.pop("_id", None)
    return wallet


def get_wallet(user_id: str, wallet_type: str = "user") -> dict | None:
    """Get a user's wallet. Returns None if not found."""
    return db.wallets.find_one(
        {"user_id": user_id, "wallet_type": wallet_type},
        {"_id": 0}
    )


def ensure_wallet(user_id: str) -> dict:
    """Get or create a user wallet. Always returns a wallet."""
    wallet = get_wallet(user_id)
    if not wallet:
        wallet = create_wallet(user_id)
    return wallet


def credit_pending(wallet_id: str, amount_cents: int, currency: str,
                   reference_type: str, reference_id: str, description: str) -> dict:
    """
    Credit pending_balance (funds in contestation hold).
    Creates a ledger transaction.
    """
    if amount_cents <= 0:
        return {"success": False, "error": "Amount must be positive"}

    now = datetime.now(timezone.utc).isoformat()

    result = db.wallets.update_one(
        {"wallet_id": wallet_id},
        {
            "$inc": {"pending_balance": amount_cents, "total_received": amount_cents},
            "$set": {"updated_at": now},
        }
    )
    if result.matched_count == 0:
        return {"success": False, "error": "Wallet not found"}

    tx = _create_transaction(
        wallet_id=wallet_id,
        tx_type="credit_pending",
        amount=amount_cents,
        currency=currency,
        reference_type=reference_type,
        reference_id=reference_id,
        description=description,
    )
    logger.info(f"[WALLET] credit_pending {amount_cents}c to wallet {wallet_id} (ref={reference_id})")
    return {"success": True, "transaction_id": tx["transaction_id"]}


def confirm_pending_to_available(wallet_id: str, amount_cents: int, currency: str,
                                  reference_type: str, reference_id: str, description: str) -> dict:
    """
    Move funds from pending_balance to available_balance.
    Called after the 15-day contestation period expires.
    """
    if amount_cents <= 0:
        return {"success": False, "error": "Amount must be positive"}

    now = datetime.now(timezone.utc).isoformat()

    # Atomic: decrement pending, increment available
    result = db.wallets.update_one(
        {"wallet_id": wallet_id, "pending_balance": {"$gte": amount_cents}},
        {
            "$inc": {"pending_balance": -amount_cents, "available_balance": amount_cents},
            "$set": {"updated_at": now},
        }
    )
    if result.matched_count == 0:
        return {"success": False, "error": "Wallet not found or insufficient pending balance"}

    tx = _create_transaction(
        wallet_id=wallet_id,
        tx_type="credit_available",
        amount=amount_cents,
        currency=currency,
        reference_type=reference_type,
        reference_id=reference_id,
        description=description,
    )
    logger.info(f"[WALLET] confirm_pending {amount_cents}c to available for wallet {wallet_id}")
    return {"success": True, "transaction_id": tx["transaction_id"]}


def debit_payout(wallet_id: str, amount_cents: int, currency: str,
                 payout_id: str, description: str) -> dict:
    """
    Debit available_balance for a payout to Stripe Connect.
    """
    if amount_cents < MINIMUM_PAYOUT_CENTS:
        return {"success": False, "error": f"Montant minimum de retrait : {MINIMUM_PAYOUT_CENTS / 100:.2f}€"}

    now = datetime.now(timezone.utc).isoformat()

    result = db.wallets.update_one(
        {"wallet_id": wallet_id, "available_balance": {"$gte": amount_cents}},
        {
            "$inc": {"available_balance": -amount_cents, "total_withdrawn": amount_cents},
            "$set": {"updated_at": now},
        }
    )
    if result.matched_count == 0:
        return {"success": False, "error": "Solde insuffisant"}

    tx = _create_transaction(
        wallet_id=wallet_id,
        tx_type="debit_payout",
        amount=amount_cents,
        currency=currency,
        reference_type="payout",
        reference_id=payout_id,
        description=description,
    )
    logger.info(f"[WALLET] debit_payout {amount_cents}c from wallet {wallet_id} (payout={payout_id})")
    return {"success": True, "transaction_id": tx["transaction_id"]}


def debit_refund(wallet_id: str, amount_cents: int, currency: str,
                 reference_id: str, description: str) -> dict:
    """
    Debit for a refund (e.g., contestation upheld).
    Tries pending first, then available.
    """
    if amount_cents <= 0:
        return {"success": False, "error": "Amount must be positive"}

    now = datetime.now(timezone.utc).isoformat()

    # Try pending first
    result = db.wallets.update_one(
        {"wallet_id": wallet_id, "pending_balance": {"$gte": amount_cents}},
        {
            "$inc": {"pending_balance": -amount_cents, "total_received": -amount_cents},
            "$set": {"updated_at": now},
        }
    )
    source = "pending"
    if result.matched_count == 0:
        # Fall back to available
        result = db.wallets.update_one(
            {"wallet_id": wallet_id, "available_balance": {"$gte": amount_cents}},
            {
                "$inc": {"available_balance": -amount_cents, "total_received": -amount_cents},
                "$set": {"updated_at": now},
            }
        )
        source = "available"
        if result.matched_count == 0:
            return {"success": False, "error": "Solde insuffisant pour remboursement"}

    tx = _create_transaction(
        wallet_id=wallet_id,
        tx_type="debit_refund",
        amount=amount_cents,
        currency=currency,
        reference_type="refund",
        reference_id=reference_id,
        description=description,
    )
    logger.info(f"[WALLET] debit_refund {amount_cents}c from {source} wallet {wallet_id}")
    return {"success": True, "transaction_id": tx["transaction_id"], "source": source}


def get_transactions(wallet_id: str, limit: int = 50, skip: int = 0) -> list:
    """Get ledger transactions for a wallet, newest first."""
    cursor = db.wallet_transactions.find(
        {"wallet_id": wallet_id},
        {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit)
    return list(cursor)


def get_transaction_count(wallet_id: str) -> int:
    """Count total transactions for pagination."""
    return db.wallet_transactions.count_documents({"wallet_id": wallet_id})


# ─── Internal ────────────────────────────────────────────

def _create_transaction(wallet_id: str, tx_type: str, amount: int,
                        currency: str, reference_type: str,
                        reference_id: str, description: str) -> dict:
    """Create a ledger entry. All amounts stored as positive integers (centimes)."""
    tx = {
        "transaction_id": str(uuid.uuid4()),
        "wallet_id": wallet_id,
        "type": tx_type,
        "amount": amount,
        "currency": currency,
        "reference_type": reference_type,
        "reference_id": reference_id,
        "description": description,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.wallet_transactions.insert_one(tx)
    tx.pop("_id", None)
    return tx
