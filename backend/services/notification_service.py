"""
Notification service — unified in-app notification system.
Supports: decisions, dispute_update, modification (future P2).

ARCHITECTURE:
- In-app notification is ALWAYS created first (source of truth)
- Email is sent AFTER notification creation (secondary channel)
- If email fails, the in-app notification remains visible
- Idempotent on (user_id, event_type, reference_id) for both notification AND email
"""
import uuid
import asyncio
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
        return existing.get("notification_id"), False  # already exists

    doc = {
        "notification_id": str(uuid.uuid4()),
        "user_id": user_id,
        "event_type": event_type,
        "reference_id": reference_id,
        "appointment_id": appointment_id,
        "title": title,
        "message": message,
        "is_read": False,
        "email_sent": False,
        "created_at": now_utc().isoformat(),
    }
    db.user_notifications.insert_one(doc)
    logger.info(f"[NOTIF] Created {event_type} notification for {user_id}: {title}")
    return doc["notification_id"], True  # newly created


def mark_email_sent(user_id: str, event_type: str, reference_id: str):
    """Mark that an email was sent for this notification (idempotency guard)."""
    db.user_notifications.update_one(
        {"user_id": user_id, "event_type": event_type, "reference_id": reference_id},
        {"$set": {"email_sent": True, "email_sent_at": now_utc().isoformat()}},
    )


def was_email_sent(user_id: str, event_type: str, reference_id: str) -> bool:
    """Check if email was already sent for this notification."""
    doc = db.user_notifications.find_one(
        {"user_id": user_id, "event_type": event_type, "reference_id": reference_id},
        {"_id": 0, "email_sent": 1},
    )
    return doc.get("email_sent", False) if doc else False


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
# Internal helpers
# ═══════════════════════════════════════════════════════════════

def _get_user_info(user_id: str) -> dict:
    """Fetch user email and name. Returns {} if not found."""
    user = db.users.find_one({"user_id": user_id}, {"_id": 0, "email": 1, "first_name": 1, "last_name": 1})
    if not user:
        return {}
    name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or "Utilisateur"
    return {"email": user.get("email"), "name": name}


def _get_appointment_context(appointment_id: str) -> dict:
    """Fetch appointment details needed for emails."""
    apt = db.appointments.find_one(
        {"appointment_id": appointment_id},
        {"_id": 0, "title": 1, "start_datetime": 1, "location": 1, "meeting_type": 1,
         "meeting_provider": 1, "timezone": 1},
    )
    if not apt:
        return {"title": "Rendez-vous", "start_datetime": "", "location": "Non specifie", "timezone": "Europe/Paris"}
    loc = apt.get("location") or ""
    if not loc and apt.get("meeting_provider"):
        loc = f"En ligne ({apt['meeting_provider'].capitalize()})"
    return {
        "title": apt.get("title", "Rendez-vous"),
        "start_datetime": apt.get("start_datetime", ""),
        "location": loc or "Non specifie",
        "timezone": apt.get("timezone", "Europe/Paris"),
    }


def _fire_email(coro):
    """Run an async email coroutine from sync context. Fire-and-forget safe."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(coro)
        else:
            loop.run_until_complete(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(coro)


# ═══════════════════════════════════════════════════════════════
# Trigger helpers — called from other services
# ═══════════════════════════════════════════════════════════════

def notify_decision_rendered(dispute: dict, appointment_title: str = ""):
    """Notify both parties when a dispute is resolved (decision rendered).
    Trigger point: resolve_dispute() after status set to 'resolved'.
    """
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

    apt = _get_appointment_context(apt_id)
    title_text = appointment_title or apt["title"]
    message = f"{outcome_label} — {source_label}"

    for uid in [org_id, target_id]:
        if not uid:
            continue
        # 1. In-app notification (always first)
        create_notification(
            user_id=uid,
            event_type="decision",
            reference_id=dispute_id,
            appointment_id=apt_id,
            title=title_text,
            message=message,
        )
        # 2. Email (idempotent, fire-and-forget)
        if not was_email_sent(uid, "decision", dispute_id):
            user_info = _get_user_info(uid)
            if user_info.get("email"):
                try:
                    from services.email_service import EmailService
                    _fire_email(EmailService.send_decision_rendered_email(
                        to_email=user_info["email"],
                        to_name=user_info["name"],
                        appointment_title=title_text,
                        appointment_date=apt["start_datetime"],
                        dispute_id=dispute_id,
                        final_outcome=outcome,
                        resolved_by=resolved_by,
                        appointment_timezone=apt["timezone"],
                    ))
                    mark_email_sent(uid, "decision", dispute_id)
                except Exception as e:
                    logger.warning(f"[NOTIF-EMAIL] Failed to send decision email to {uid}: {e}")


def notify_dispute_opened(dispute: dict, appointment_title: str = ""):
    """Notify both parties when a dispute is opened.
    Trigger point: open_dispute() after DB insert.
    """
    org_id = dispute.get("organizer_user_id")
    target_id = dispute.get("target_user_id")
    dispute_id = dispute.get("dispute_id")
    apt_id = dispute.get("appointment_id")

    apt = _get_appointment_context(apt_id)
    title_text = appointment_title or apt["title"]
    message = "Un litige a ete ouvert — votre position est attendue."

    for uid in [org_id, target_id]:
        if not uid:
            continue
        # 1. In-app notification
        create_notification(
            user_id=uid,
            event_type="dispute_update",
            reference_id=dispute_id,
            appointment_id=apt_id,
            title=title_text,
            message=message,
        )
        # 2. Email
        if not was_email_sent(uid, "dispute_update", dispute_id):
            user_info = _get_user_info(uid)
            if user_info.get("email"):
                try:
                    from services.email_service import EmailService
                    _fire_email(EmailService.send_dispute_opened_email(
                        to_email=user_info["email"],
                        to_name=user_info["name"],
                        appointment_title=title_text,
                        appointment_date=apt["start_datetime"],
                        appointment_location=apt["location"],
                        dispute_id=dispute_id,
                        reason=dispute.get("opened_reason", ""),
                        appointment_timezone=apt["timezone"],
                    ))
                    mark_email_sent(uid, "dispute_update", dispute_id)
                except Exception as e:
                    logger.warning(f"[NOTIF-EMAIL] Failed to send dispute opened email to {uid}: {e}")


def notify_dispute_position_submitted(dispute: dict, submitter_user_id: str, appointment_title: str = ""):
    """Notify the OTHER party when one party submits their position.
    Trigger point: submit_dispute_position() after position saved.
    In-app only — no email (per strategy matrix).
    """
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
    # No email for position submission (strategy: in-app only)


def notify_dispute_escalated(dispute: dict, appointment_title: str = ""):
    """Notify both parties when a dispute is escalated to arbitration.
    Trigger point: _check_positions_and_resolve() on disagreement.
    Email + In-app (validated by user).
    """
    org_id = dispute.get("organizer_user_id")
    target_id = dispute.get("target_user_id")
    dispute_id = dispute.get("dispute_id")
    apt_id = dispute.get("appointment_id")

    apt = _get_appointment_context(apt_id)
    title_text = appointment_title or apt["title"]
    message = "Les positions divergent — le dossier est transmis a un arbitre."

    for uid in [org_id, target_id]:
        if not uid:
            continue
        # 1. In-app notification
        create_notification(
            user_id=uid,
            event_type="dispute_update",
            reference_id=dispute_id,
            appointment_id=apt_id,
            title=title_text,
            message=message,
        )
        # 2. Email for escalation
        # Note: escalation uses a DIFFERENT email_type key to avoid clash with dispute_opened email
        if not was_email_sent(uid, "dispute_escalated", dispute_id):
            user_info = _get_user_info(uid)
            if user_info.get("email"):
                try:
                    from services.email_service import EmailService
                    _fire_email(EmailService.send_dispute_escalated_email(
                        to_email=user_info["email"],
                        to_name=user_info["name"],
                        appointment_title=title_text,
                        appointment_date=apt["start_datetime"],
                        dispute_id=dispute_id,
                        appointment_timezone=apt["timezone"],
                    ))
                    mark_email_sent(uid, "dispute_escalated", dispute_id)
                except Exception as e:
                    logger.warning(f"[NOTIF-EMAIL] Failed to send escalation email to {uid}: {e}")
