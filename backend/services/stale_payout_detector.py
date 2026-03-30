"""
Stale Payout Detector — NLYT V1

Scans the `payouts` collection for records stuck in `processing` for > 24h.
Marks them as `stale` and logs a structured warning.

A late Stripe webhook can still overwrite `stale` → `completed`/`failed` normally.
"""
import logging
from datetime import datetime, timezone, timedelta
from database import db

logger = logging.getLogger(__name__)

STALE_THRESHOLD_HOURS = 24


def scan_stale_payouts() -> int:
    """
    Find payouts in `processing` status older than STALE_THRESHOLD_HOURS.
    Mark them as `stale` with a `stale_detected_at` timestamp.
    Returns the number of payouts marked stale.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=STALE_THRESHOLD_HOURS)
    stale_filter = {
        "status": "processing",
        "updated_at": {"$lt": cutoff.isoformat()},
    }

    stale_payouts = list(db.payouts.find(stale_filter, {"_id": 0}))
    count = len(stale_payouts)

    if count == 0:
        logger.info("[STALE_PAYOUT] Scan complete — no stale payouts detected.")
        return 0

    logger.warning(f"[STALE_PAYOUT] Detected {count} payout(s) stuck in processing > {STALE_THRESHOLD_HOURS}h")

    for p in stale_payouts:
        payout_id = p.get("payout_id", "?")
        user_id = p.get("user_id", "?")
        amount = p.get("amount_cents", 0)
        currency = p.get("currency", "eur")
        updated = p.get("updated_at", "?")

        db.payouts.update_one(
            {"payout_id": payout_id, "status": "processing"},
            {"$set": {
                "status": "stale",
                "stale_detected_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }}
        )

        logger.warning(
            f"[STALE_PAYOUT] Marked stale: payout={payout_id} user={user_id} "
            f"amount={amount}c {currency} last_update={updated}"
        )

    logger.info(f"[STALE_PAYOUT] Scan complete — {count} payout(s) marked stale.")
    return count
