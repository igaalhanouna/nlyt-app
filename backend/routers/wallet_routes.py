"""
Wallet API routes — NLYT Internal Ledger

GET  /api/wallet                             → Solde du wallet
GET  /api/wallet/transactions                → Historique du ledger
GET  /api/wallet/distributions               → Distributions de l'utilisateur
GET  /api/wallet/distributions/:id           → Détail d'une distribution
POST /api/wallet/distributions/:id/contest   → Contester une distribution
"""
import sys
sys.path.append('/app/backend')

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from middleware.auth_middleware import get_current_user
from services.wallet_service import (
    ensure_wallet,
    get_transactions,
    get_transaction_count,
    MINIMUM_PAYOUT_CENTS,
)
from services.distribution_service import (
    get_distributions_for_user,
    get_distribution,
    contest_distribution,
)

router = APIRouter()


@router.get("")
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


@router.get("/distributions")
async def get_my_distributions(request: Request, limit: int = 50, skip: int = 0):
    """Get distributions involving the current user (as beneficiary or no_show)."""
    user = await get_current_user(request)
    if limit > 100:
        limit = 100
    distributions = get_distributions_for_user(user["user_id"], limit=limit, skip=skip)
    return {"distributions": distributions, "total": len(distributions)}


@router.get("/distributions/{distribution_id}")
async def get_distribution_detail(distribution_id: str, request: Request):
    """Get details of a specific distribution."""
    user = await get_current_user(request)
    dist = get_distribution(distribution_id)
    if not dist:
        raise HTTPException(status_code=404, detail="Distribution introuvable")

    # Check access: user must be beneficiary or the no_show
    user_id = user["user_id"]
    is_involved = (
        dist.get("no_show_user_id") == user_id
        or any(b.get("user_id") == user_id for b in dist.get("beneficiaries", []))
    )
    if not is_involved:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    return dist


class ContestRequest(BaseModel):
    reason: str


@router.post("/distributions/{distribution_id}/contest")
async def contest_dist(distribution_id: str, body: ContestRequest, request: Request):
    """Contest a distribution during the hold period."""
    user = await get_current_user(request)
    result = contest_distribution(distribution_id, user["user_id"], body.reason)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Erreur contestation"))
    return result
