"""
Charity Payout Routes — Admin Manual Bank Transfers V1

Allows admin to record manual bank transfers to charity associations,
debiting their internal wallet atomically.

Endpoints:
  GET  /api/admin/payouts              → List all payouts (with filters)
  GET  /api/admin/payouts/dashboard    → Associations with wallet balances
  POST /api/admin/payouts              → Record a completed payout (debit wallet)
"""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional

from database import db
from routers.admin import require_admin
from services.wallet_service import debit_charity_payout, get_wallet, create_wallet

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Models ───────────────────────────────────────────────────

class CreatePayoutBody(BaseModel):
    association_id: str
    amount_cents: int = Field(..., gt=0)
    bank_reference: str = Field(..., min_length=1, max_length=200)
    transfer_date: str = Field(..., min_length=10, max_length=10)


# ── Dashboard: associations + balances ───────────────────────

@router.get("/payouts/dashboard")
async def payouts_dashboard(request: Request):
    """List active associations with their charity wallet balances and last payout."""
    await require_admin(request)

    associations = list(db.charity_associations.find(
        {"is_active": True},
        {"_id": 0}
    ).sort("name", 1))

    result = []
    for assoc in associations:
        aid = assoc["association_id"]

        # Get charity wallet (user_id = association_id, wallet_type = charity)
        wallet = db.wallets.find_one(
            {"user_id": aid, "wallet_type": "charity"},
            {"_id": 0, "wallet_id": 1, "available_balance": 1, "pending_balance": 1}
        )

        # Last payout for this association
        last_payout = db.charity_payouts.find_one(
            {"association_id": aid},
            {"_id": 0, "payout_id": 1, "amount_cents": 1, "transfer_date": 1, "created_at": 1},
            sort=[("created_at", -1)]
        )

        result.append({
            "association_id": aid,
            "name": assoc.get("name"),
            "iban": assoc.get("iban"),
            "bic": assoc.get("bic"),
            "account_holder": assoc.get("account_holder"),
            "available_balance": wallet["available_balance"] if wallet else 0,
            "pending_balance": wallet["pending_balance"] if wallet else 0,
            "has_wallet": wallet is not None,
            "last_payout": last_payout,
        })

    return {"associations": result, "count": len(result)}


# ── List all payouts ─────────────────────────────────────────

@router.get("/payouts")
async def list_payouts(request: Request, association_id: Optional[str] = None, limit: int = 50, skip: int = 0):
    """List payouts, optionally filtered by association."""
    await require_admin(request)

    query = {}
    if association_id:
        query["association_id"] = association_id

    if limit > 100:
        limit = 100

    payouts = list(db.charity_payouts.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit))

    total = db.charity_payouts.count_documents(query)

    # Enrich with admin name
    admin_ids = list({p["created_by"] for p in payouts if p.get("created_by")})
    admin_map = {}
    if admin_ids:
        admins = list(db.users.find(
            {"user_id": {"$in": admin_ids}},
            {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1}
        ))
        admin_map = {a["user_id"]: a for a in admins}

    for p in payouts:
        admin = admin_map.get(p.get("created_by"), {})
        p["admin_name"] = f"{admin.get('first_name', '')} {admin.get('last_name', '')}".strip() or admin.get("email", "—")

    return {"payouts": payouts, "total": total, "limit": limit, "skip": skip}


# ── Create payout (record completed transfer + debit wallet) ─

@router.post("/payouts")
async def create_payout(request: Request, body: CreatePayoutBody):
    """
    Record a completed manual bank transfer and debit the charity wallet.
    
    Strict rules:
    - Association must exist and be active
    - Association must have an IBAN configured
    - Amount must be > 0 and <= available_balance
    - Wallet is debited atomically
    - Payout record created with full audit trail
    """
    admin = await require_admin(request)

    # 1. Validate association
    assoc = db.charity_associations.find_one(
        {"association_id": body.association_id},
        {"_id": 0}
    )
    if not assoc:
        raise HTTPException(status_code=404, detail="Association introuvable")
    if not assoc.get("is_active"):
        raise HTTPException(status_code=400, detail="Cette association est désactivée")
    if not assoc.get("iban"):
        raise HTTPException(status_code=400, detail="Aucun IBAN configuré pour cette association. Veuillez d'abord renseigner les coordonnées bancaires.")

    # 2. Validate wallet exists and has sufficient balance
    wallet = db.wallets.find_one(
        {"user_id": body.association_id, "wallet_type": "charity"},
        {"_id": 0}
    )
    if not wallet:
        raise HTTPException(status_code=400, detail="Aucun wallet trouvé pour cette association (solde = 0)")
    if wallet["available_balance"] < body.amount_cents:
        raise HTTPException(
            status_code=400,
            detail=f"Solde insuffisant. Disponible : {wallet['available_balance'] / 100:.2f} EUR, demandé : {body.amount_cents / 100:.2f} EUR"
        )

    # 3. Validate transfer_date format
    try:
        datetime.strptime(body.transfer_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Date de virement invalide (format attendu : YYYY-MM-DD)")

    # 4. Create payout record FIRST
    now = datetime.now(timezone.utc).isoformat()
    payout_id = str(uuid.uuid4())
    payout_doc = {
        "payout_id": payout_id,
        "association_id": body.association_id,
        "association_name": assoc.get("name"),
        "amount_cents": body.amount_cents,
        "currency": "eur",
        "status": "completed",
        "transfer_method": "manual_bank_transfer",
        "bank_reference": body.bank_reference.strip(),
        "transfer_date": body.transfer_date,
        "iban_snapshot": assoc.get("iban"),
        "bic_snapshot": assoc.get("bic"),
        "account_holder_snapshot": assoc.get("account_holder"),
        "created_by": admin["user_id"],
        "created_at": now,
    }

    try:
        db.charity_payouts.insert_one(payout_doc)
    except Exception as e:
        logger.error(f"[PAYOUT] Failed to create payout record: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de l'enregistrement du reversement")

    # 5. Debit the wallet atomically
    debit_result = debit_charity_payout(
        wallet_id=wallet["wallet_id"],
        amount_cents=body.amount_cents,
        currency="eur",
        payout_id=payout_id,
        description=f"Reversement manuel — {assoc.get('name')} — Ref: {body.bank_reference.strip()}"
    )

    if not debit_result.get("success"):
        # Rollback: delete the payout record
        db.charity_payouts.delete_one({"payout_id": payout_id})
        logger.error(f"[PAYOUT] Wallet debit failed for payout {payout_id}: {debit_result.get('error')}")
        raise HTTPException(status_code=400, detail=debit_result.get("error", "Échec du débit wallet"))

    payout_doc.pop("_id", None)

    logger.info(
        f"[PAYOUT] Charity payout {payout_id}: {body.amount_cents}c to {body.association_id} "
        f"(ref={body.bank_reference}) by admin {admin['email']}"
    )

    return {
        "success": True,
        "payout": payout_doc,
        "new_available_balance": wallet["available_balance"] - body.amount_cents,
    }
