"""
Wallet API routes — NLYT Internal Ledger

GET  /api/wallet              → Solde du wallet
GET  /api/wallet/transactions → Historique du ledger
"""
import sys
sys.path.append('/app/backend')

from fastapi import APIRouter, HTTPException, Request
from middleware.auth_middleware import get_current_user
from services.wallet_service import (
    ensure_wallet,
    get_transactions,
    get_transaction_count,
    MINIMUM_PAYOUT_CENTS,
)

router = APIRouter()


@router.get("/")
async def get_my_wallet(request: Request):
    """Get current user's wallet with balance summary."""
    user = await get_current_user(request)
    wallet = ensure_wallet(user["user_id"])

    return {
        "wallet_id": wallet["wallet_id"],
        "available_balance": wallet["available_balance"],
        "pending_balance": wallet["pending_balance"],
        "total_balance": wallet["available_balance"] + wallet["pending_balance"],
        "currency": wallet["currency"],
        "total_received": wallet["total_received"],
        "total_withdrawn": wallet["total_withdrawn"],
        "stripe_connect_status": wallet.get("stripe_connect_status", "not_started"),
        "can_payout": (
            wallet["available_balance"] >= MINIMUM_PAYOUT_CENTS
            and wallet.get("stripe_connect_status") == "active"
        ),
        "minimum_payout": MINIMUM_PAYOUT_CENTS,
    }


@router.get("/transactions")
async def get_my_transactions(request: Request, limit: int = 50, skip: int = 0):
    """Get ledger transactions for current user's wallet."""
    user = await get_current_user(request)
    wallet = ensure_wallet(user["user_id"])

    if limit > 100:
        limit = 100

    transactions = get_transactions(wallet["wallet_id"], limit=limit, skip=skip)
    total = get_transaction_count(wallet["wallet_id"])

    return {
        "transactions": transactions,
        "total": total,
        "limit": limit,
        "skip": skip,
    }
