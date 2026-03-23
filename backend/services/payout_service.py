"""
Payout Service — NLYT Phase 4

Handles real payouts from NLYT platform to user Stripe Connect Express accounts.

Flow:
  1. Verify all conditions (wallet, connect, balance Stripe, no pending payout)
  2. Create payout record (pending) — serves as anti-duplicate lock
  3. Call stripe.Transfer.create()
  4. If Stripe OK → atomically debit wallet → payout: processing
  5. If Stripe KO → payout: failed, wallet untouched
  6. Webhook transfer.paid → payout: completed
  7. Webhook transfer.failed → re-credit wallet, payout: failed

All amounts in CENTIMES (int). Ledger is append-only.
"""
import os
import uuid
import stripe
import logging
from datetime import datetime, timezone
from database import db
from services.wallet_service import MINIMUM_PAYOUT_CENTS

logger = logging.getLogger(__name__)

STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', '')
stripe.api_key = STRIPE_API_KEY


def _is_dev_mode() -> bool:
    return not STRIPE_API_KEY or STRIPE_API_KEY == 'sk_test_emergent'


def _is_connect_unavailable() -> bool:
    """Check if Connect is unavailable (dev account without Connect enabled)."""
    if _is_dev_mode():
        return True
    # Check by looking at wallet connect account IDs
    # If they start with acct_dev_, it's simulated
    return False


# ─── Stripe Balance Check ────────────────────────────────────


def check_stripe_platform_balance(amount_cents: int, currency: str = "eur") -> dict:
    """
    Verify the Stripe platform account has sufficient available balance.
    Returns { sufficient: bool, available_cents: int }
    """
    if _is_dev_mode():
        return {"sufficient": True, "available_cents": amount_cents, "dev_mode": True}

    try:
        balance = stripe.Balance.retrieve()
        available = 0
        for entry in balance.get("available", []):
            if entry.get("currency") == currency:
                available = entry.get("amount", 0)
                break
        return {
            "sufficient": available >= amount_cents,
            "available_cents": available,
        }
    except stripe.error.StripeError as e:
        logger.error(f"[PAYOUT] Stripe balance check failed: {e}")
        return {"sufficient": False, "available_cents": 0, "error": str(e)}


# ─── Payout Request ──────────────────────────────────────────


def request_payout(user_id: str, amount_cents: int | None = None) -> dict:
    """
    Request a payout from NLYT wallet to user's Stripe Connect account.

    If amount_cents is None, withdraws the full available_balance.
    """
    # 1. Get wallet
    wallet = db.wallets.find_one(
        {"user_id": user_id, "wallet_type": "user"},
        {"_id": 0},
    )
    if not wallet:
        return {"success": False, "error": "Wallet introuvable"}

    # Default to full withdrawal
    if amount_cents is None:
        amount_cents = wallet["available_balance"]

    # 2. Validate conditions
    if amount_cents <= 0:
        return {"success": False, "error": "Le montant doit être positif"}

    if wallet["available_balance"] < amount_cents:
        return {"success": False, "error": "Solde disponible insuffisant"}

    if amount_cents < MINIMUM_PAYOUT_CENTS:
        return {"success": False, "error": f"Montant minimum de retrait : {MINIMUM_PAYOUT_CENTS / 100:.2f} €"}

    if wallet.get("stripe_connect_status") != "active":
        return {"success": False, "error": "Votre compte Stripe Connect doit être actif pour retirer"}

    connect_account_id = wallet.get("stripe_connect_account_id")
    if not connect_account_id:
        return {"success": False, "error": "Aucun compte Stripe Connect associé"}

    # 3. Check no pending/processing payout for this user
    existing = db.payouts.find_one(
        {"user_id": user_id, "status": {"$in": ["pending", "processing"]}},
        {"_id": 0},
    )
    if existing:
        return {"success": False, "error": "Un retrait est déjà en cours"}

    # 4. Check Stripe platform balance (skip for dev accounts)
    currency = wallet.get("currency", "eur")
    is_dev = _is_dev_mode() or connect_account_id.startswith("acct_dev_")
    if not is_dev:
        balance_check = check_stripe_platform_balance(amount_cents, currency)
        if not balance_check.get("sufficient"):
            logger.warning(
                f"[PAYOUT] Stripe balance insufficient for {amount_cents}c "
                f"(available: {balance_check.get('available_cents')}c)"
            )
            return {"success": False, "error": "Fonds plateforme temporairement insuffisants. Réessayez plus tard."}

    # 5. Create payout record (pending — serves as lock)
    now_iso = datetime.now(timezone.utc).isoformat()
    payout_id = str(uuid.uuid4())
    payout = {
        "payout_id": payout_id,
        "user_id": user_id,
        "wallet_id": wallet["wallet_id"],
        "amount_cents": amount_cents,
        "currency": currency,
        "stripe_transfer_id": None,
        "stripe_connect_account_id": connect_account_id,
        "status": "pending",
        "requested_at": now_iso,
        "processed_at": None,
        "completed_at": None,
        "failed_at": None,
        "failure_reason": None,
        "ledger_transaction_id": None,
        "dev_mode": False,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    db.payouts.insert_one(payout)
    payout.pop("_id", None)

    # 6. Dev mode: simulate
    if is_dev:
        return _execute_dev_payout(payout)

    # 7. Call Stripe Transfer
    return _execute_stripe_transfer(payout)


def _execute_stripe_transfer(payout: dict) -> dict:
    """Execute real Stripe Transfer and debit wallet on success."""
    payout_id = payout["payout_id"]

    try:
        transfer = stripe.Transfer.create(
            amount=payout["amount_cents"],
            currency=payout["currency"],
            destination=payout["stripe_connect_account_id"],
            metadata={
                "payout_id": payout_id,
                "user_id": payout["user_id"],
                "source": "nlyt_payout",
            },
        )

        # Stripe call succeeded → atomically debit wallet
        debit_result = _atomic_debit_wallet(payout)
        if not debit_result["success"]:
            # Critical: Stripe succeeded but wallet debit failed
            # Attempt to reverse the transfer
            logger.error(
                f"[PAYOUT] CRITICAL: Stripe transfer succeeded but wallet debit failed "
                f"for payout {payout_id}. Attempting reversal."
            )
            try:
                stripe.Transfer.create_reversal(transfer.id)
            except Exception as rev_err:
                logger.error(f"[PAYOUT] CRITICAL: Reversal also failed: {rev_err}")

            _fail_payout(payout_id, f"Débit wallet échoué après transfert Stripe: {debit_result['error']}")
            return {"success": False, "error": "Erreur interne — le retrait a été annulé"}

        # Update payout to processing
        db.payouts.update_one(
            {"payout_id": payout_id},
            {"$set": {
                "status": "processing",
                "stripe_transfer_id": transfer.id,
                "ledger_transaction_id": debit_result["transaction_id"],
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )

        logger.info(f"[PAYOUT] Transfer created: {transfer.id} for payout {payout_id}")
        return {
            "success": True,
            "payout_id": payout_id,
            "amount_cents": payout["amount_cents"],
            "status": "processing",
            "stripe_transfer_id": transfer.id,
        }

    except stripe.error.StripeError as e:
        error_msg = str(e)
        # Check if Connect unavailable → fallback to dev mode
        if "signed up for Connect" in error_msg or "not a valid" in error_msg:
            logger.warning("[PAYOUT] Stripe Connect unavailable — falling back to dev mode")
            return _execute_dev_payout(payout)

        _fail_payout(payout_id, error_msg)
        logger.error(f"[PAYOUT] Stripe Transfer failed for {payout_id}: {e}")
        return {"success": False, "error": f"Erreur Stripe: {error_msg}"}


def _execute_dev_payout(payout: dict) -> dict:
    """Dev mode: simulate a successful payout without real Stripe transfer."""
    payout_id = payout["payout_id"]
    now_iso = datetime.now(timezone.utc).isoformat()

    # Debit wallet
    debit_result = _atomic_debit_wallet(payout)
    if not debit_result["success"]:
        _fail_payout(payout_id, debit_result["error"])
        return {"success": False, "error": debit_result["error"]}

    # Mark as completed immediately in dev mode
    db.payouts.update_one(
        {"payout_id": payout_id},
        {"$set": {
            "status": "completed",
            "stripe_transfer_id": f"tr_dev_{payout_id[:8]}",
            "ledger_transaction_id": debit_result["transaction_id"],
            "dev_mode": True,
            "processed_at": now_iso,
            "completed_at": now_iso,
            "updated_at": now_iso,
        }},
    )

    logger.info(f"[PAYOUT] [DEV MODE] Payout {payout_id} completed: {payout['amount_cents']}c")
    return {
        "success": True,
        "payout_id": payout_id,
        "amount_cents": payout["amount_cents"],
        "status": "completed",
        "stripe_transfer_id": f"tr_dev_{payout_id[:8]}",
        "dev_mode": True,
        "message": "[DEV MODE] Retrait simulé avec succès",
    }


def _atomic_debit_wallet(payout: dict) -> dict:
    """Atomically debit available_balance with guard. Creates ledger entry."""
    now_iso = datetime.now(timezone.utc).isoformat()
    amount = payout["amount_cents"]

    result = db.wallets.update_one(
        {
            "wallet_id": payout["wallet_id"],
            "available_balance": {"$gte": amount},
        },
        {
            "$inc": {
                "available_balance": -amount,
                "total_withdrawn": amount,
            },
            "$set": {"updated_at": now_iso},
        },
    )
    if result.matched_count == 0:
        return {"success": False, "error": "Solde insuffisant (vérification atomique)"}

    # Create ledger transaction
    tx_id = str(uuid.uuid4())
    tx = {
        "transaction_id": tx_id,
        "wallet_id": payout["wallet_id"],
        "type": "debit_payout",
        "amount": amount,
        "currency": payout["currency"],
        "reference_type": "payout",
        "reference_id": payout["payout_id"],
        "description": f"Retrait vers Stripe Connect{' [DEV MODE]' if payout.get('dev_mode') else ''}",
        "created_at": now_iso,
    }
    db.wallet_transactions.insert_one(tx)
    tx.pop("_id", None)

    return {"success": True, "transaction_id": tx_id}


def _fail_payout(payout_id: str, reason: str):
    """Mark a payout as failed."""
    db.payouts.update_one(
        {"payout_id": payout_id},
        {"$set": {
            "status": "failed",
            "failure_reason": reason,
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )


# ─── Webhook Handlers ────────────────────────────────────────


def handle_transfer_paid(transfer_data: dict) -> dict:
    """
    Handle Stripe webhook: transfer.paid
    Marks the payout as completed. Idempotent.
    """
    transfer_id = transfer_data.get("id")
    if not transfer_id:
        return {"skipped": True, "reason": "No transfer ID"}

    payout = db.payouts.find_one(
        {"stripe_transfer_id": transfer_id},
        {"_id": 0},
    )
    if not payout:
        return {"skipped": True, "reason": f"No payout for transfer {transfer_id}"}

    if payout["status"] == "completed":
        return {"skipped": True, "reason": "Already completed (idempotent)"}

    now_iso = datetime.now(timezone.utc).isoformat()
    db.payouts.update_one(
        {"payout_id": payout["payout_id"]},
        {"$set": {
            "status": "completed",
            "completed_at": now_iso,
            "updated_at": now_iso,
        }},
    )

    logger.info(f"[PAYOUT] Webhook: transfer.paid → payout {payout['payout_id']} completed")
    return {"success": True, "payout_id": payout["payout_id"]}


def handle_transfer_failed(transfer_data: dict) -> dict:
    """
    Handle Stripe webhook: transfer.failed or transfer.reversed
    Re-credits the wallet and marks payout as failed. Idempotent.
    """
    transfer_id = transfer_data.get("id")
    if not transfer_id:
        return {"skipped": True, "reason": "No transfer ID"}

    payout = db.payouts.find_one(
        {"stripe_transfer_id": transfer_id},
        {"_id": 0},
    )
    if not payout:
        return {"skipped": True, "reason": f"No payout for transfer {transfer_id}"}

    if payout["status"] in ("failed", "completed"):
        return {"skipped": True, "reason": f"Payout already {payout['status']} (idempotent)"}

    now_iso = datetime.now(timezone.utc).isoformat()

    # Re-credit the wallet
    db.wallets.update_one(
        {"wallet_id": payout["wallet_id"]},
        {
            "$inc": {
                "available_balance": payout["amount_cents"],
                "total_withdrawn": -payout["amount_cents"],
            },
            "$set": {"updated_at": now_iso},
        },
    )

    # Create reversal ledger entry
    tx_id = str(uuid.uuid4())
    db.wallet_transactions.insert_one({
        "transaction_id": tx_id,
        "wallet_id": payout["wallet_id"],
        "type": "credit_available",
        "amount": payout["amount_cents"],
        "currency": payout["currency"],
        "reference_type": "payout_reversal",
        "reference_id": payout["payout_id"],
        "description": "Retrait échoué — fonds re-crédités",
        "created_at": now_iso,
    })

    # Mark payout as failed
    failure_reason = transfer_data.get("failure_message", "Transfer failed")
    db.payouts.update_one(
        {"payout_id": payout["payout_id"]},
        {"$set": {
            "status": "failed",
            "failure_reason": failure_reason,
            "failed_at": now_iso,
            "updated_at": now_iso,
        }},
    )

    logger.info(f"[PAYOUT] Webhook: transfer failed → payout {payout['payout_id']} failed, wallet re-credited")
    return {"success": True, "payout_id": payout["payout_id"], "re_credited": True}


# ─── Query Helpers ────────────────────────────────────────────


def get_payouts_for_user(user_id: str, limit: int = 50, skip: int = 0) -> list:
    """Get all payouts for a user."""
    return list(db.payouts.find(
        {"user_id": user_id},
        {"_id": 0},
    ).sort("created_at", -1).skip(skip).limit(limit))


def get_payout(payout_id: str) -> dict | None:
    """Get a single payout."""
    return db.payouts.find_one({"payout_id": payout_id}, {"_id": 0})


def get_payout_count(user_id: str) -> int:
    """Count payouts for a user."""
    return db.payouts.count_documents({"user_id": user_id})
