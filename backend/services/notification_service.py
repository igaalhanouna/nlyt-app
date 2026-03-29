"""
Notification service — unified in-app notification system.
Supports: decisions, dispute_update, modification (future P2).
"""
import uuid
import logging
from datetime import datetime, timezone
from database import db

logger = logging.getLogger(__name__)


def now_utc():
    return datetime.now(timezone.utc)


def create_notification(
    user_id: str,
    event_type: str,
    reference_id: str,
    appointment_id: str,
    title: str,
    message: str,
):
    """Insert a notification for a user. Idempotent on (user_id, event_type, reference_id)."""
    existing = db.user_notifications.find_one({
        "user_id": user_id,
        "event_type": event_type,
        "reference_id": reference_id,
    })
    if existing:
        return existing.get("notification_id")

    doc = {
        "notification_id": str(uuid.uuid4()),
        "user_id": user_id,
        "event_type": event_type,
        "reference_id": reference_id,
        "appointment_id": appointment_id,
        "title": title,
        "message": message,
        "is_read": False,
        "created_at": now_utc().isoformat(),
    }
    db.user_notifications.insert_one(doc)
    logger.info(f"[NOTIF] Created {event_type} notification for {user_id}: {title}")
    return doc["notification_id"]


def get_unread_counts(user_id: str) -> dict:
    """Return unread notification counts grouped by event_type."""
    pipeline = [
        {"$match": {"user_id": user_id, "is_read": False}},
        {"$group": {"_id": "$event_type", "count": {"$sum": 1}}},
    ]
    results = list(db.user_notifications.aggregate(pipeline))
    counts = {}
    for r in results:
        counts[r["_id"]] = r["count"]
    return {
        "decisions": counts.get("decision", 0),
        "disputes": counts.get("dispute_update", 0),
    }


def mark_as_read(notification_id: str, user_id: str) -> bool:
    """Mark a single notification as read."""
    result = db.user_notifications.update_one(
        {"notification_id": notification_id, "user_id": user_id},
        {"$set": {"is_read": True, "read_at": now_utc().isoformat()}},
    )
    return result.modified_count > 0


def mark_read_by_reference(user_id: str, event_type: str, reference_id: str) -> int:
    """Mark all notifications matching (user, type, reference) as read."""
    result = db.user_notifications.update_many(
        {"user_id": user_id, "event_type": event_type, "reference_id": reference_id, "is_read": False},
        {"$set": {"is_read": True, "read_at": now_utc().isoformat()}},
    )
    return result.modified_count


def get_unread_reference_ids(user_id: str, event_type: str) -> list:
    """Return list of reference_ids that are unread for a given type."""
    docs = db.user_notifications.find(
        {"user_id": user_id, "event_type": event_type, "is_read": False},
        {"_id": 0, "reference_id": 1},
    )
    return [d["reference_id"] for d in docs]


# ═══════════════════════════════════════════════════════════════
# Trigger helpers — called from other services
# ═══════════════════════════════════════════════════════════════

def notify_decision_rendered(dispute: dict, appointment_title: str = ""):
    """Notify both parties when a dispute is resolved (decision rendered)."""
    org_id = dispute.get("organizer_user_id")
    target_id = dispute.get("target_user_id")
    dispute_id = dispute.get("dispute_id")
    apt_id = dispute.get("appointment_id")

    resolution = dispute.get("resolution", {})
    outcome = resolution.get("final_outcome", "")
    resolved_by = resolution.get("resolved_by", "")

    outcome_labels = {
        "on_time": "Presence validee",
        "no_show": "Absence confirmee",
        "late_penalized": "Retard penalise",
        "waived": "Penalite annulee",
    }
    outcome_label = outcome_labels.get(outcome, outcome)

    source_labels = {
        "mutual_agreement": "Accord mutuel",
        "admin_arbitration": "Arbitrage administrateur",
        "platform": "Decision plateforme",
    }
    source_label = source_labels.get(resolved_by, resolved_by)

    title_text = appointment_title or "Rendez-vous"
    message = f"{outcome_label} — {source_label}"

    for uid in [org_id, target_id]:
        if uid:
            create_notification(
                user_id=uid,
                event_type="decision",
                reference_id=dispute_id,
                appointment_id=apt_id,
                title=title_text,
                message=message,
            )


def notify_dispute_opened(dispute: dict, appointment_title: str = ""):
    """Notify both parties when a dispute is opened."""
    org_id = dispute.get("organizer_user_id")
    target_id = dispute.get("target_user_id")
    dispute_id = dispute.get("dispute_id")
    apt_id = dispute.get("appointment_id")

    title_text = appointment_title or "Rendez-vous"
    message = "Un litige a ete ouvert — votre position est attendue."

    for uid in [org_id, target_id]:
        if uid:
            create_notification(
                user_id=uid,
                event_type="dispute_update",
                reference_id=dispute_id,
                appointment_id=apt_id,
                title=title_text,
                message=message,
            )


def notify_dispute_position_submitted(dispute: dict, submitter_user_id: str, appointment_title: str = ""):
    """Notify the OTHER party when one party submits their position."""
    org_id = dispute.get("organizer_user_id")
    target_id = dispute.get("target_user_id")
    dispute_id = dispute.get("dispute_id")
    apt_id = dispute.get("appointment_id")

    other_id = target_id if submitter_user_id == org_id else org_id
    if not other_id:
        return

    title_text = appointment_title or "Rendez-vous"
    message = "L'autre partie a soumis sa position sur le litige."

    create_notification(
        user_id=other_id,
        event_type="dispute_update",
        reference_id=dispute_id,
        appointment_id=apt_id,
        title=title_text,
        message=message,
    )


def notify_dispute_escalated(dispute: dict, appointment_title: str = ""):
    """Notify both parties when a dispute is escalated to arbitration."""
    org_id = dispute.get("organizer_user_id")
    target_id = dispute.get("target_user_id")
    dispute_id = dispute.get("dispute_id")
    apt_id = dispute.get("appointment_id")

    title_text = appointment_title or "Rendez-vous"
    message = "Les positions divergent — le dossier est transmis a un arbitre."

    for uid in [org_id, target_id]:
        if uid:
            create_notification(
                user_id=uid,
                event_type="dispute_update",
                reference_id=dispute_id,
                appointment_id=apt_id,
                title=title_text,
                message=message,
            )
