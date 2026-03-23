"""
Distribution Service — NLYT Phase 3

Handles the capture of guarantees and distribution of funds to wallets
after attendance evaluation determines no-show outcomes.

All amounts in CENTIMES (int). No floats in money calculations.
Ledger is append-only. Idempotent on guarantee_id.
"""
import uuid
import logging
from datetime import datetime, timedelta, timezone
from database import db
from services.wallet_service import (
    ensure_wallet,
    credit_pending,
    confirm_pending_to_available,
    debit_refund,
    create_wallet,
)

logger = logging.getLogger(__name__)

HOLD_DAYS = 15
PLATFORM_WALLET_USER_ID = "__nlyt_platform__"


def _ensure_platform_wallet() -> dict:
    """Get or create the NLYT platform wallet."""
    return ensure_wallet(PLATFORM_WALLET_USER_ID)


def _ensure_charity_wallet(charity_association_id: str) -> dict:
    """Get or create a charity wallet for a given association."""
    existing = db.wallets.find_one(
        {"user_id": charity_association_id, "wallet_type": "charity"},
        {"_id": 0},
    )
    if existing:
        return existing
    return create_wallet(charity_association_id, wallet_type="charity")


# ─── Pure Computation ────────────────────────────────────────────


def compute_distribution(
    capture_amount_cents: int,
    platform_pct: float,
    compensation_pct: float,
    charity_pct: float,
    no_show_is_organizer: bool,
    present_participants: list[dict],
    organizer_user_id: str,
) -> dict:
    """
    Pure calculation of distribution shares.
    Returns dict with platform_cents, charity_cents, and beneficiaries list.

    Invariant: sum of all amounts == capture_amount_cents ALWAYS.

    Rules:
    - platform & charity: floor rounding
    - compensation = total - platform - charity (absorbs rounding remainder)
    - Organizer no_show: same structure (platform/charity/compensation) but
      compensation goes to present participants, never to the organizer.
    - If organizer no_show with 0 present participants: compensation → platform.
    """
    if capture_amount_cents <= 0:
        return {
            "platform_cents": 0,
            "charity_cents": 0,
            "compensation_cents": 0,
            "beneficiaries": [],
        }

    # 1. Platform (floor)
    platform_cents = int(capture_amount_cents * platform_pct / 100)

    # 2. Charity (floor)
    charity_cents = int(capture_amount_cents * charity_pct / 100)

    # 3. Compensation = remainder (absorbs rounding)
    compensation_cents = capture_amount_cents - platform_cents - charity_cents

    beneficiaries = []

    if not no_show_is_organizer:
        # NORMAL CASE: participant no_show → compensation to organizer
        beneficiaries.append({
            "user_id": organizer_user_id,
            "role": "organizer",
            "amount_cents": compensation_cents,
        })
    else:
        # SYMMETRIC CASE: organizer no_show
        # Same structure platform/charity/compensation, but compensation
        # goes to present participants. Organizer NEVER receives his own share.
        if present_participants:
            base = compensation_cents // len(present_participants)
            remainder = compensation_cents - (base * len(present_participants))
            for i, p in enumerate(present_participants):
                amount = base + (1 if i < remainder else 0)
                if amount > 0:
                    beneficiaries.append({
                        "user_id": p["user_id"],
                        "role": "participant",
                        "amount_cents": amount,
                    })
        else:
            # No present participants → compensation absorbed by platform
            platform_cents += compensation_cents
            compensation_cents = 0

    return {
        "platform_cents": platform_cents,
        "charity_cents": charity_cents,
        "compensation_cents": compensation_cents,
        "beneficiaries": beneficiaries,
    }


# ─── Distribution Creation ───────────────────────────────────────


def create_distribution(
    appointment_id: str,
    guarantee_id: str,
    no_show_participant_id: str,
    no_show_user_id: str,
    no_show_is_organizer: bool,
    capture_amount_cents: int,
    capture_currency: str,
    stripe_payment_intent_id: str,
    platform_commission_percent: float,
    affected_compensation_percent: float,
    charity_percent: float,
    charity_association_id: str | None,
    organizer_user_id: str,
    present_participants: list[dict],
) -> dict:
    """
    Create a distribution record and credit beneficiary wallets (pending).

    Idempotent on guarantee_id: if a distribution already exists, returns it.
    """
    # Idempotence guard
    existing = db.distributions.find_one(
        {"guarantee_id": guarantee_id}, {"_id": 0}
    )
    if existing:
        logger.info(f"[DISTRIBUTION] Already exists for guarantee {guarantee_id}")
        return {"success": True, "distribution_id": existing["distribution_id"], "already_existed": True}

    if capture_amount_cents <= 0:
        return {"success": False, "error": "Capture amount must be positive"}

    # Compute shares
    calc = compute_distribution(
        capture_amount_cents=capture_amount_cents,
        platform_pct=platform_commission_percent,
        compensation_pct=affected_compensation_percent,
        charity_pct=charity_percent,
        no_show_is_organizer=no_show_is_organizer,
        present_participants=present_participants,
        organizer_user_id=organizer_user_id,
    )

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    hold_expires = (now + timedelta(days=HOLD_DAYS)).isoformat()
    distribution_id = str(uuid.uuid4())

    # Build beneficiary list and credit wallets
    beneficiaries = []
    appointment = db.appointments.find_one(
        {"appointment_id": appointment_id},
        {"_id": 0, "title": 1, "start_datetime": 1},
    )
    apt_title = appointment.get("title", "RDV") if appointment else "RDV"

    # --- Platform beneficiary ---
    if calc["platform_cents"] > 0:
        platform_wallet = _ensure_platform_wallet()
        tx_result = credit_pending(
            wallet_id=platform_wallet["wallet_id"],
            amount_cents=calc["platform_cents"],
            currency=capture_currency,
            reference_type="distribution",
            reference_id=distribution_id,
            description=f"Commission plateforme — {apt_title}",
        )
        beneficiaries.append({
            "beneficiary_id": str(uuid.uuid4()),
            "wallet_id": platform_wallet["wallet_id"],
            "user_id": PLATFORM_WALLET_USER_ID,
            "role": "platform",
            "amount_cents": calc["platform_cents"],
            "status": "credited_pending" if tx_result.get("success") else "failed",
            "transaction_id": tx_result.get("transaction_id"),
        })

    # --- Charity beneficiary ---
    if calc["charity_cents"] > 0 and charity_association_id:
        charity_wallet = _ensure_charity_wallet(charity_association_id)
        tx_result = credit_pending(
            wallet_id=charity_wallet["wallet_id"],
            amount_cents=calc["charity_cents"],
            currency=capture_currency,
            reference_type="distribution",
            reference_id=distribution_id,
            description=f"Don association — {apt_title}",
        )
        beneficiaries.append({
            "beneficiary_id": str(uuid.uuid4()),
            "wallet_id": charity_wallet["wallet_id"],
            "user_id": charity_association_id,
            "role": "charity",
            "amount_cents": calc["charity_cents"],
            "status": "credited_pending" if tx_result.get("success") else "failed",
            "transaction_id": tx_result.get("transaction_id"),
        })
    elif calc["charity_cents"] > 0 and not charity_association_id:
        # Charity configured but no association → absorb into platform
        platform_wallet = _ensure_platform_wallet()
        tx_result = credit_pending(
            wallet_id=platform_wallet["wallet_id"],
            amount_cents=calc["charity_cents"],
            currency=capture_currency,
            reference_type="distribution",
            reference_id=distribution_id,
            description=f"Part charité (pas d'association) — {apt_title}",
        )
        # Update platform beneficiary if exists, otherwise add
        found = False
        for b in beneficiaries:
            if b["role"] == "platform":
                b["amount_cents"] += calc["charity_cents"]
                found = True
                break
        if not found:
            beneficiaries.append({
                "beneficiary_id": str(uuid.uuid4()),
                "wallet_id": platform_wallet["wallet_id"],
                "user_id": PLATFORM_WALLET_USER_ID,
                "role": "platform",
                "amount_cents": calc["charity_cents"],
                "status": "credited_pending" if tx_result.get("success") else "failed",
                "transaction_id": tx_result.get("transaction_id"),
            })

    # --- Compensation beneficiaries (organizer or participants) ---
    for comp_benef in calc["beneficiaries"]:
        user_wallet = ensure_wallet(comp_benef["user_id"])
        role_label = "Dédommagement" if comp_benef["role"] == "organizer" else "Compensation"
        tx_result = credit_pending(
            wallet_id=user_wallet["wallet_id"],
            amount_cents=comp_benef["amount_cents"],
            currency=capture_currency,
            reference_type="distribution",
            reference_id=distribution_id,
            description=f"{role_label} — {apt_title}",
        )
        beneficiaries.append({
            "beneficiary_id": str(uuid.uuid4()),
            "wallet_id": user_wallet["wallet_id"],
            "user_id": comp_benef["user_id"],
            "role": comp_benef["role"],
            "amount_cents": comp_benef["amount_cents"],
            "status": "credited_pending" if tx_result.get("success") else "failed",
            "transaction_id": tx_result.get("transaction_id"),
        })

    # Create distribution document
    distribution = {
        "distribution_id": distribution_id,
        "appointment_id": appointment_id,
        "guarantee_id": guarantee_id,
        "no_show_participant_id": no_show_participant_id,
        "no_show_user_id": no_show_user_id,
        "no_show_is_organizer": no_show_is_organizer,
        "capture_amount_cents": capture_amount_cents,
        "capture_currency": capture_currency,
        "stripe_payment_intent_id": stripe_payment_intent_id,
        "status": "pending_hold",
        "distribution_rules": {
            "platform_commission_percent": platform_commission_percent,
            "affected_compensation_percent": affected_compensation_percent,
            "charity_percent": charity_percent,
        },
        "beneficiaries": beneficiaries,
        "hold_expires_at": hold_expires,
        "contested": False,
        "contested_at": None,
        "contested_by": None,
        "contest_reason": None,
        "captured_at": now_iso,
        "distributed_at": None,
        "completed_at": None,
        "cancelled_at": None,
        "cancel_reason": None,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    db.distributions.insert_one(distribution)
    distribution.pop("_id", None)

    logger.info(
        f"[DISTRIBUTION] Created {distribution_id} for guarantee {guarantee_id} "
        f"— {capture_amount_cents}c, {len(beneficiaries)} beneficiaries"
    )
    return {"success": True, "distribution_id": distribution_id, "beneficiaries_count": len(beneficiaries)}


# ─── Hold Finalization ───────────────────────────────────────────


def finalize_expired_holds() -> dict:
    """
    Scheduler job: find all distributions in pending_hold where hold has expired.
    Convert pending_balance → available_balance for each beneficiary.
    """
    now = datetime.now(timezone.utc).isoformat()

    distributions = list(db.distributions.find(
        {
            "status": "pending_hold",
            "contested": False,
            "hold_expires_at": {"$lte": now},
        },
        {"_id": 0},
    ))

    finalized = 0
    for dist in distributions:
        try:
            _finalize_single_distribution(dist)
            finalized += 1
        except Exception as e:
            logger.error(f"[DISTRIBUTION] Failed to finalize {dist['distribution_id']}: {e}")

    if finalized > 0:
        logger.info(f"[DISTRIBUTION] Finalized {finalized}/{len(distributions)} distributions")
    return {"finalized": finalized, "total_candidates": len(distributions)}


def _finalize_single_distribution(dist: dict):
    """Finalize a single distribution: pending → available for all beneficiaries."""
    dist_id = dist["distribution_id"]
    now_iso = datetime.now(timezone.utc).isoformat()

    # Mark as distributing
    db.distributions.update_one(
        {"distribution_id": dist_id, "status": "pending_hold"},
        {"$set": {"status": "distributing", "updated_at": now_iso}},
    )

    appointment = db.appointments.find_one(
        {"appointment_id": dist["appointment_id"]},
        {"_id": 0, "title": 1},
    )
    apt_title = appointment.get("title", "RDV") if appointment else "RDV"

    all_ok = True
    for benef in dist.get("beneficiaries", []):
        if benef["status"] != "credited_pending":
            continue
        if benef["amount_cents"] <= 0:
            continue

        result = confirm_pending_to_available(
            wallet_id=benef["wallet_id"],
            amount_cents=benef["amount_cents"],
            currency=dist["capture_currency"],
            reference_type="distribution",
            reference_id=dist_id,
            description=f"Distribution confirmée — {apt_title}",
        )
        if result.get("success"):
            benef["status"] = "credited_available"
        else:
            all_ok = False
            logger.error(
                f"[DISTRIBUTION] Failed to confirm {benef['amount_cents']}c "
                f"for wallet {benef['wallet_id']}: {result.get('error')}"
            )

    # Update distribution
    final_status = "completed" if all_ok else "distributing"
    update = {
        "beneficiaries": dist["beneficiaries"],
        "status": final_status,
        "updated_at": now_iso,
    }
    if final_status == "completed":
        update["completed_at"] = now_iso
        update["distributed_at"] = now_iso

    db.distributions.update_one(
        {"distribution_id": dist_id},
        {"$set": update},
    )
    logger.info(f"[DISTRIBUTION] {dist_id} → {final_status}")


# ─── Cancel / Contest ────────────────────────────────────────────


def cancel_distribution(distribution_id: str, reason: str) -> dict:
    """
    Cancel a distribution and refund all credited wallets.
    Used when a reclassification reverses a no_show, or admin action.
    """
    dist = db.distributions.find_one({"distribution_id": distribution_id}, {"_id": 0})
    if not dist:
        return {"success": False, "error": "Distribution introuvable"}

    if dist["status"] in ("cancelled", "completed"):
        return {"success": False, "error": f"Distribution déjà {dist['status']}"}

    now_iso = datetime.now(timezone.utc).isoformat()
    refund_errors = []

    for benef in dist.get("beneficiaries", []):
        if benef["status"] not in ("credited_pending", "credited_available"):
            continue
        if benef["amount_cents"] <= 0:
            continue

        result = debit_refund(
            wallet_id=benef["wallet_id"],
            amount_cents=benef["amount_cents"],
            currency=dist["capture_currency"],
            reference_id=distribution_id,
            description=f"Annulation distribution — {reason}",
        )
        if result.get("success"):
            benef["status"] = "refunded"
        else:
            refund_errors.append(benef["wallet_id"])

    db.distributions.update_one(
        {"distribution_id": distribution_id},
        {"$set": {
            "status": "cancelled",
            "cancel_reason": reason,
            "cancelled_at": now_iso,
            "beneficiaries": dist["beneficiaries"],
            "updated_at": now_iso,
        }},
    )

    logger.info(f"[DISTRIBUTION] Cancelled {distribution_id}: {reason}")
    if refund_errors:
        logger.warning(f"[DISTRIBUTION] Refund errors for wallets: {refund_errors}")

    return {"success": True, "refund_errors": refund_errors}


def contest_distribution(distribution_id: str, user_id: str, reason: str) -> dict:
    """
    Contest a distribution during hold period.
    Only the no_show user can contest. Blocks finalization.
    """
    dist = db.distributions.find_one({"distribution_id": distribution_id}, {"_id": 0})
    if not dist:
        return {"success": False, "error": "Distribution introuvable"}

    if dist["status"] != "pending_hold":
        return {"success": False, "error": "La contestation n'est possible que pendant le délai de hold"}

    if dist["no_show_user_id"] != user_id:
        return {"success": False, "error": "Seul l'utilisateur concerné peut contester"}

    now_iso = datetime.now(timezone.utc).isoformat()
    db.distributions.update_one(
        {"distribution_id": distribution_id},
        {"$set": {
            "contested": True,
            "contested_at": now_iso,
            "contested_by": user_id,
            "contest_reason": reason,
            "status": "contested",
            "updated_at": now_iso,
        }},
    )

    logger.info(f"[DISTRIBUTION] Contested {distribution_id} by user {user_id}")
    return {"success": True}


# ─── Query Helpers ───────────────────────────────────────────────


def get_distributions_for_user(user_id: str, limit: int = 50, skip: int = 0) -> list:
    """Get distributions where user is a beneficiary OR the no_show."""
    cursor = db.distributions.find(
        {
            "$or": [
                {"no_show_user_id": user_id},
                {"beneficiaries.user_id": user_id},
            ]
        },
        {"_id": 0},
    ).sort("created_at", -1).skip(skip).limit(limit)
    distributions = list(cursor)

    # Enrich with appointment title
    apt_ids = list({d["appointment_id"] for d in distributions if d.get("appointment_id")})
    if apt_ids:
        apts = {
            a["appointment_id"]: a
            for a in db.appointments.find(
                {"appointment_id": {"$in": apt_ids}},
                {"_id": 0, "appointment_id": 1, "title": 1, "start_datetime": 1},
            )
        }
        for d in distributions:
            apt = apts.get(d.get("appointment_id"))
            if apt:
                d["appointment_title"] = apt.get("title", "RDV")
                d["appointment_date"] = apt.get("start_datetime")

    return distributions


def get_distributions_for_appointment(appointment_id: str) -> list:
    """Get all distributions for an appointment."""
    return list(db.distributions.find(
        {"appointment_id": appointment_id},
        {"_id": 0},
    ).sort("created_at", -1))


def get_distribution(distribution_id: str) -> dict | None:
    """Get a single distribution by ID."""
    return db.distributions.find_one(
        {"distribution_id": distribution_id},
        {"_id": 0},
    )
