"""
Wallet API routes — NLYT Internal Ledger

GET  /api/wallet                             → Solde du wallet
GET  /api/wallet/transactions                → Historique du ledger
GET  /api/wallet/distributions               → Distributions de l'utilisateur
GET  /api/wallet/distributions/:id           → Détail d'une distribution
POST /api/wallet/distributions/:id/contest   → Contester une distribution
GET  /api/wallet/impact                      → Impact solidaire
POST /api/wallet/payout                      → Demander un retrait
GET  /api/wallet/payouts                     → Historique des retraits
"""
import sys
sys.path.append('/app/backend')

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from middleware.auth_middleware import get_current_user
from database import db
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
    resolve_contestation,
    get_charity_impact,
)
from services.payout_service import (
    request_payout,
    get_payouts_for_user,
    get_payout,
    get_payout_count,
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


@router.get("/impact")
async def get_my_impact(request: Request):
    """Get charity impact summary for the current user."""
    user = await get_current_user(request)
    return get_charity_impact(user["user_id"])


@router.get("/milestones")
async def get_my_milestones(request: Request):
    """Get engagement milestones for the current user + CTA organiser."""
    user = await get_current_user(request)
    uid = user["user_id"]

    # Count engagements where user was present (on_time or late)
    attended = db.attendance_records.count_documents({
        "participant_email": user.get("email"),
        "outcome": {"$in": ["on_time", "late"]},
    })

    # Count engagements organized
    organized = db.appointments.count_documents({
        "organizer_id": uid,
        "status": {"$nin": ["deleted", "draft"]},
    })

    # Milestone thresholds
    thresholds = [1, 3, 5, 10, 25, 50, 100]
    milestones = []
    for t in thresholds:
        milestones.append({
            "threshold": t,
            "reached": attended >= t,
            "label": f"{t} engagement{'s' if t > 1 else ''} tenu{'s' if t > 1 else ''}",
        })

    # Next milestone
    next_milestone = None
    for t in thresholds:
        if attended < t:
            next_milestone = t
            break

    return {
        "attended_count": attended,
        "organized_count": organized,
        "milestones": milestones,
        "next_milestone": next_milestone,
        "show_organizer_cta": organized == 0 and attended >= 1,
    }


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


class ResolveContestationRequest(BaseModel):
    resolution: str  # "upheld" or "rejected"
    note: str = ""


@router.post("/distributions/{distribution_id}/resolve-contestation")
async def resolve_contest(distribution_id: str, body: ResolveContestationRequest, request: Request):
    """
    Resolve a contested distribution (organizer, with conflict-of-interest guard).
    resolution: "upheld" (cancel distribution, refund) or "rejected" (resume hold).

    Trustless guards:
    - Organizer is BLOCKED if they are a beneficiary of this distribution (judge-and-party)
    - Organizer is BLOCKED if the distribution includes a charity split (platform-only)
    """
    user = await get_current_user(request)
    dist = get_distribution(distribution_id)
    if not dist:
        raise HTTPException(status_code=404, detail="Distribution introuvable")
    apt = db.appointments.find_one({"appointment_id": dist["appointment_id"]}, {"_id": 0})
    if not apt or apt.get("organizer_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="Seul l'organisateur peut résoudre une contestation")

    user_id = user["user_id"]
    beneficiaries = dist.get("beneficiaries", [])

    # Guard 1: Conflict of interest — organizer is a beneficiary
    if any(b.get("user_id") == user_id for b in beneficiaries):
        raise HTTPException(
            status_code=403,
            detail="Conflit d'intérêt : vous êtes bénéficiaire de cette distribution. La résolution est réservée à la plateforme."
        )

    # Guard 2: Charity split — reserved to platform/admin
    if any(b.get("role") == "charity" for b in beneficiaries):
        raise HTTPException(
            status_code=403,
            detail="Cette distribution implique un flux charité. La résolution est réservée à la plateforme."
        )

    result = resolve_contestation(distribution_id, body.resolution, resolved_by=user_id, note=body.note)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Erreur résolution"))
    return result



class PayoutRequest(BaseModel):
    amount_cents: Optional[int] = None


@router.post("/payout")
async def create_payout(body: PayoutRequest, request: Request):
    """Request a payout from NLYT wallet to Stripe Connect account."""
    user = await get_current_user(request)
    result = request_payout(user["user_id"], body.amount_cents)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Erreur retrait"))
    return result


@router.get("/payouts")
async def get_my_payouts(request: Request, limit: int = 50, skip: int = 0):
    """Get payout history for the current user."""
    user = await get_current_user(request)
    if limit > 100:
        limit = 100
    payouts = get_payouts_for_user(user["user_id"], limit=limit, skip=skip)
    total = get_payout_count(user["user_id"])
    return {"payouts": payouts, "total": total, "limit": limit, "skip": skip}


@router.get("/payouts/{payout_id}")
async def get_payout_detail(payout_id: str, request: Request):
    """Get details of a specific payout."""
    user = await get_current_user(request)
    p = get_payout(payout_id)
    if not p:
        raise HTTPException(status_code=404, detail="Retrait introuvable")
    if p["user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    return p