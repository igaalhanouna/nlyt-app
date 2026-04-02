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


RESOLVED_DISPUTE_STATUSES = frozenset({
    "resolved", "agreed_present", "agreed_absent", "agreed_late_penalized",
})


def _cleanup_resolved_dispute_notifications(user_id: str):
    """Auto-mark dispute notifications as read when their dispute is resolved or missing.
    Self-healing: runs on each count fetch, only queries DB when there ARE unread dispute notifs.
    """
    unread = list(db.user_notifications.find(
        {"user_id": user_id, "event_type": "dispute_update", "is_read": False},
        {"_id": 0, "reference_id": 1}
    ))
    if not unread:
        return

    ref_ids = list({n["reference_id"] for n in unread})

    # Find which disputes are still active (not resolved)
    active = set()
    for d in db.declarative_disputes.find(
        {"dispute_id": {"$in": ref_ids},
         "status": {"$nin": list(RESOLVED_DISPUTE_STATUSES)}},
        {"_id": 0, "dispute_id": 1}
    ):
        active.add(d["dispute_id"])

    # All ref_ids NOT in active set → stale (resolved or missing)
    stale_ids = [rid for rid in ref_ids if rid not in active]

    if stale_ids:
        result = db.user_notifications.update_many(
            {"user_id": user_id, "event_type": "dispute_update",
             "reference_id": {"$in": stale_ids}, "is_read": False},
            {"$set": {"is_read": True, "read_at": now_utc().isoformat()}}
        )
        if result.modified_count > 0:
            logger.info(
                f"[NOTIF][CLEANUP] Auto-marked {result.modified_count} stale dispute "
                f"notifications as read for {user_id}"
            )


def get_unread_counts(user_id: str) -> dict:
    """Return unread notification counts grouped by event_type.
    Auto-cleans stale dispute notifications before counting.
    """
    _cleanup_resolved_dispute_notifications(user_id)

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
        "modifications": counts.get("modification", 0),
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

    EQUITY: Target MUST be notified even without an account.
    """
    org_id = dispute.get("organizer_user_id")
    target_id = dispute.get("target_user_id")
    target_pid = dispute.get("target_participant_id")
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

    # ── 1. Notify ORGANIZER ──
    if org_id:
        create_notification(
            user_id=org_id,
            event_type="decision",
            reference_id=dispute_id,
            appointment_id=apt_id,
            title=title_text,
            message=message,
        )
        if not was_email_sent(org_id, "decision", dispute_id):
            user_info = _get_user_info(org_id)
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
                        needs_account=False,
                    ))
                    mark_email_sent(org_id, "decision", dispute_id)
                except Exception as e:
                    logger.warning(f"[NOTIF-EMAIL] Failed to send decision email to organizer {org_id}: {e}")

    # ── 2. Notify TARGET ──
    target_email, target_name, has_account = _resolve_target_contact(target_id, target_pid)
    if target_email:
        idempotency_uid = target_id if has_account else f"no_account_{target_email}"
        if has_account:
            create_notification(
                user_id=target_id,
                event_type="decision",
                reference_id=dispute_id,
                appointment_id=apt_id,
                title=title_text,
                message=message,
            )
        if not was_email_sent(idempotency_uid, "decision", dispute_id):
            if not has_account:
                create_notification(
                    user_id=idempotency_uid,
                    event_type="decision",
                    reference_id=dispute_id,
                    appointment_id=apt_id,
                    title=title_text,
                    message=f"[email-only] {message}",
                )
            try:
                from services.email_service import EmailService
                _fire_email(EmailService.send_decision_rendered_email(
                    to_email=target_email,
                    to_name=target_name,
                    appointment_title=title_text,
                    appointment_date=apt["start_datetime"],
                    dispute_id=dispute_id,
                    final_outcome=outcome,
                    resolved_by=resolved_by,
                    appointment_timezone=apt["timezone"],
                    needs_account=not has_account,
                ))
                mark_email_sent(idempotency_uid, "decision", dispute_id)
                if not has_account:
                    logger.info(f"[NOTIF-EMAIL] Decision email sent to non-account user {target_email} for dispute {dispute_id}")
            except Exception as e:
                logger.warning(f"[NOTIF-EMAIL] Failed to send decision email to target {target_email}: {e}")
    elif not target_id:
        logger.error(
            f"[NOTIF-EMAIL][EQUITY] Cannot notify target for decision on dispute {dispute_id}: "
            f"no user_id AND no email found for participant {target_pid}."
        )


def notify_dispute_opened(dispute: dict, appointment_title: str = ""):
    """Notify both parties when a dispute is opened.
    Trigger point: open_dispute() after DB insert.

    EQUITY REQUIREMENT: The target MUST be notified even if they have no NLYT account.
    Three cases:
      1. User with account (target_user_id exists) → in-app + email
      2. User with account but inactive → in-app + email (they'll see it when they log in)
      3. User without account (target_user_id is None) → email only, with "create account" CTA
    """
    org_id = dispute.get("organizer_user_id")
    target_id = dispute.get("target_user_id")
    dispute_id = dispute.get("dispute_id")
    apt_id = dispute.get("appointment_id")
    target_pid = dispute.get("target_participant_id")

    apt = _get_appointment_context(apt_id)
    title_text = appointment_title or apt["title"]
    message = "Un litige a ete ouvert — votre position est attendue."

    # Fetch penalty info for the email
    appointment_doc = db.appointments.find_one(
        {"appointment_id": apt_id},
        {"_id": 0, "penalty_amount": 1, "penalty_currency": 1}
    )
    penalty_amount = appointment_doc.get("penalty_amount") if appointment_doc else None
    penalty_currency = appointment_doc.get("penalty_currency", "EUR") if appointment_doc else "EUR"

    # ── 1. Notify ORGANIZER (always has an account) ──
    if org_id:
        create_notification(
            user_id=org_id,
            event_type="dispute_update",
            reference_id=dispute_id,
            appointment_id=apt_id,
            title=title_text,
            message=message,
        )
        if not was_email_sent(org_id, "dispute_update", dispute_id):
            user_info = _get_user_info(org_id)
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
                        penalty_amount=penalty_amount,
                        penalty_currency=penalty_currency,
                        is_target=False,
                    ))
                    mark_email_sent(org_id, "dispute_update", dispute_id)
                except Exception as e:
                    logger.warning(f"[NOTIF-EMAIL] Failed to send dispute opened email to organizer {org_id}: {e}")

    # ── 2. Notify TARGET ──
    if target_id:
        # Case 1 & 2: User has an account → in-app notification + email
        create_notification(
            user_id=target_id,
            event_type="dispute_update",
            reference_id=dispute_id,
            appointment_id=apt_id,
            title=title_text,
            message=message,
        )
        if not was_email_sent(target_id, "dispute_update", dispute_id):
            user_info = _get_user_info(target_id)
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
                        penalty_amount=penalty_amount,
                        penalty_currency=penalty_currency,
                        is_target=True,
                        needs_account=False,
                    ))
                    mark_email_sent(target_id, "dispute_update", dispute_id)
                except Exception as e:
                    logger.warning(f"[NOTIF-EMAIL] Failed to send dispute opened email to target {target_id}: {e}")
    else:
        # Case 3: User has NO account → email-only notification with "create account" CTA
        # Resolve email from the participants collection using target_participant_id
        target_email = None
        target_name = "Participant"
        if target_pid:
            participant = db.participants.find_one(
                {"participant_id": target_pid},
                {"_id": 0, "email": 1, "first_name": 1, "last_name": 1}
            )
            if participant:
                target_email = participant.get("email")
                fn = participant.get("first_name", "")
                ln = participant.get("last_name", "")
                target_name = f"{fn} {ln}".strip() or target_email or "Participant"

        if target_email:
            # Use email as idempotency key (no user_id available)
            # Create a tracking notification record for idempotency
            idempotency_key = f"no_account_{target_email}"
            if not was_email_sent(idempotency_key, "dispute_update", dispute_id):
                # Create a tracking record (no in-app notification, email-only)
                create_notification(
                    user_id=idempotency_key,
                    event_type="dispute_update",
                    reference_id=dispute_id,
                    appointment_id=apt_id,
                    title=title_text,
                    message=f"[email-only] {message}",
                )
                try:
                    from services.email_service import EmailService
                    _fire_email(EmailService.send_dispute_opened_email(
                        to_email=target_email,
                        to_name=target_name,
                        appointment_title=title_text,
                        appointment_date=apt["start_datetime"],
                        appointment_location=apt["location"],
                        dispute_id=dispute_id,
                        reason=dispute.get("opened_reason", ""),
                        appointment_timezone=apt["timezone"],
                        penalty_amount=penalty_amount,
                        penalty_currency=penalty_currency,
                        is_target=True,
                        needs_account=True,
                    ))
                    mark_email_sent(idempotency_key, "dispute_update", dispute_id)
                    logger.info(
                        f"[NOTIF-EMAIL] Dispute notification sent to non-account user "
                        f"{target_email} for dispute {dispute_id}"
                    )
                except Exception as e:
                    logger.warning(
                        f"[NOTIF-EMAIL] Failed to send dispute opened email to "
                        f"non-account user {target_email}: {e}"
                    )
        else:
            logger.error(
                f"[NOTIF-EMAIL][EQUITY] Cannot notify target for dispute {dispute_id}: "
                f"no user_id AND no email found for participant {target_pid}. "
                f"The target has {DISPUTE_DEADLINE_DAYS} days to respond but no way to know."
            )


DISPUTE_DEADLINE_DAYS = 7  # Duplicated from declarative_service for reference


def _resolve_target_contact(target_user_id, target_participant_id):
    """Resolve the target's contact info.
    Returns (email, name, has_account).
    - If user has an account: returns their user info.
    - If no account: falls back to the participants collection.
    """
    if target_user_id:
        user_info = _get_user_info(target_user_id)
        if user_info.get("email"):
            return user_info["email"], user_info["name"], True

    # Fallback: resolve from participants collection
    if target_participant_id:
        participant = db.participants.find_one(
            {"participant_id": target_participant_id},
            {"_id": 0, "email": 1, "first_name": 1, "last_name": 1}
        )
        if participant and participant.get("email"):
            fn = participant.get("first_name", "")
            ln = participant.get("last_name", "")
            name = f"{fn} {ln}".strip() or participant["email"] or "Participant"
            return participant["email"], name, False

    return None, "Participant", False


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

    EQUITY: Target MUST be notified even without an account (same pattern as dispute_opened).
    """
    org_id = dispute.get("organizer_user_id")
    target_id = dispute.get("target_user_id")
    target_pid = dispute.get("target_participant_id")
    dispute_id = dispute.get("dispute_id")
    apt_id = dispute.get("appointment_id")

    apt = _get_appointment_context(apt_id)
    title_text = appointment_title or apt["title"]
    message = "Les positions divergent — le dossier est transmis a un arbitre."

    # ── 1. Notify ORGANIZER ──
    if org_id:
        create_notification(
            user_id=org_id,
            event_type="dispute_update",
            reference_id=dispute_id,
            appointment_id=apt_id,
            title=title_text,
            message=message,
        )
        if not was_email_sent(org_id, "dispute_escalated", dispute_id):
            # Create tracking record for escalation email idempotency
            create_notification(
                user_id=org_id,
                event_type="dispute_escalated",
                reference_id=dispute_id,
                appointment_id=apt_id,
                title=title_text,
                message=f"[email-tracking] {message}",
            )
            user_info = _get_user_info(org_id)
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
                        needs_account=False,
                    ))
                    mark_email_sent(org_id, "dispute_escalated", dispute_id)
                except Exception as e:
                    logger.warning(f"[NOTIF-EMAIL] Failed to send escalation email to organizer {org_id}: {e}")

    # ── 2. Notify TARGET ──
    target_email, target_name, has_account = _resolve_target_contact(target_id, target_pid)
    if target_email:
        idempotency_uid = target_id if has_account else f"no_account_{target_email}"
        if has_account:
            create_notification(
                user_id=target_id,
                event_type="dispute_update",
                reference_id=dispute_id,
                appointment_id=apt_id,
                title=title_text,
                message=message,
            )
        if not was_email_sent(idempotency_uid, "dispute_escalated", dispute_id):
            # Create tracking record for idempotency
            create_notification(
                user_id=idempotency_uid,
                event_type="dispute_escalated",
                reference_id=dispute_id,
                appointment_id=apt_id,
                title=title_text,
                message=f"[email-tracking] {message}" if has_account else f"[email-only] {message}",
            )
            try:
                from services.email_service import EmailService
                _fire_email(EmailService.send_dispute_escalated_email(
                    to_email=target_email,
                    to_name=target_name,
                    appointment_title=title_text,
                    appointment_date=apt["start_datetime"],
                    dispute_id=dispute_id,
                    appointment_timezone=apt["timezone"],
                    needs_account=not has_account,
                ))
                mark_email_sent(idempotency_uid, "dispute_escalated", dispute_id)
                if not has_account:
                    logger.info(f"[NOTIF-EMAIL] Escalation email sent to non-account user {target_email} for dispute {dispute_id}")
            except Exception as e:
                logger.warning(f"[NOTIF-EMAIL] Failed to send escalation email to target {target_email}: {e}")
    elif not target_id:
        logger.error(
            f"[NOTIF-EMAIL][EQUITY] Cannot notify target for escalated dispute {dispute_id}: "
            f"no user_id AND no email found for participant {target_pid}."
        )
