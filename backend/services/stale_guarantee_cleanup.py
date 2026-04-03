"""
Stale Guarantee Cleanup Service

Cancels payment guarantees that have been stuck in 'pending' status
for more than 1 hour. This covers the case where a user starts the
Stripe Checkout flow but never completes it (abandons the page,
browser crash, etc.).
"""
import logging
from datetime import datetime, timezone, timedelta
from database import db

logger = logging.getLogger(__name__)


def run_stale_guarantee_cleanup():
    """
    Find guarantees in 'pending' status created more than 1 hour ago.
    Mark them as 'expired' and revert participant status.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    now_iso = datetime.now(timezone.utc).isoformat()

    stale = list(db.payment_guarantees.find(
        {
            "status": "pending",
            "created_at": {"$lt": cutoff},
        },
        {"_id": 0, "guarantee_id": 1, "participant_id": 1, "appointment_id": 1}
    ))

    if not stale:
        return

    cleaned = 0
    for g in stale:
        gid = g["guarantee_id"]

        # Mark guarantee as expired
        db.payment_guarantees.update_one(
            {"guarantee_id": gid, "status": "pending"},
            {"$set": {
                "status": "expired",
                "expired_at": now_iso,
                "expiry_reason": "setup_timeout_1h",
                "updated_at": now_iso,
            }}
        )

        # Revert participant to accepted (they can retry)
        if g.get("participant_id"):
            db.participants.update_one(
                {
                    "participant_id": g["participant_id"],
                    "status": "accepted_pending_guarantee",
                },
                {"$set": {
                    "status": "accepted",
                    "updated_at": now_iso,
                }}
            )

        cleaned += 1
        logger.info(
            f"[GUARANTEE-CLEANUP] Expired stale guarantee {gid} "
            f"(appointment={g.get('appointment_id')}, participant={g.get('participant_id')})"
        )

    logger.info(f"[GUARANTEE-CLEANUP] Cleaned {cleaned} stale guarantees")
