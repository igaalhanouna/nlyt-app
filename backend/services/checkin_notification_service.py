"""
Checkin Notification Helper
Sends a one-time email to all other participants when someone checks in.
Uses atomic flag `checkin_notification_sent` on participant doc for idempotence.
"""
from datetime import datetime, timezone
import os



async def notify_checkin(
    participant_id: str,
    appointment_id: str,
    checkin_time: str = None,
    evidence_details: dict = None,
):
    """
    Send check-in notification to all OTHER participants (+ organizer if the checker is not the organizer).
    Idempotent: uses checkin_notification_sent flag on the participant who checked in.
    """
    # 1. Load the participant who checked in
    checker = db.participants.find_one({"participant_id": participant_id}, {"_id": 0})
    if not checker:
        return

    # 2. Idempotence: atomic flag
    result = db.participants.update_one(
        {"participant_id": participant_id, "checkin_notification_sent": {"$ne": True}},
        {"$set": {
            "checkin_notification_sent": True,
            "checkin_notification_sent_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    if result.modified_count == 0:
        return  # Already sent

    # 3. Load the appointment
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        return

    # Skip if cancelled
    if appointment.get("status") in ("cancelled", "deleted"):
        return

    # 4. Build checker name
    checker_name = f"{checker.get('first_name', '')} {checker.get('last_name', '')}".strip()
    if not checker_name:
        checker_name = checker.get('email', '').split('@')[0]
    checker_is_organizer = checker.get('is_organizer', False)

    # 5. Get all OTHER participants who have accepted (engaged)
    recipients = list(db.participants.find(
        {
            "appointment_id": appointment_id,
            "participant_id": {"$ne": participant_id},
            "status": {"$in": ["accepted", "accepted_guaranteed"]},
        },
        {"_id": 0}
    ))

    if not recipients:
        return

    # 6. Send emails
    try:
        from services.email_service import EmailService

from database import db
        frontend_url = os.environ.get('FRONTEND_URL', '').rstrip('/')

        for recipient in recipients:
            r_name = f"{recipient.get('first_name', '')} {recipient.get('last_name', '')}".strip()
            if not r_name:
                r_name = recipient.get('email', '').split('@')[0]

            r_token = recipient.get('invitation_token', '')
            appointment_link = f"{frontend_url}/invitation/{r_token}" if r_token else None

            try:
                await EmailService.send_checkin_notification_email(
                    to_email=recipient.get('email', ''),
                    to_name=r_name,
                    checkin_person_name=checker_name,
                    checkin_is_organizer=checker_is_organizer,
                    appointment_title=appointment.get('title', ''),
                    appointment_datetime=appointment.get('start_datetime', ''),
                    appointment_type=appointment.get('appointment_type', 'physical'),
                    meeting_provider=appointment.get('meeting_provider'),
                    checkin_time=checkin_time or datetime.now(timezone.utc).isoformat(),
                    appointment_link=appointment_link,
                    appointment_timezone=appointment.get('appointment_timezone', 'Europe/Paris'),
                    evidence_details=evidence_details,
                )
            except Exception as e:
                print(f"[CHECKIN_NOTIFY] Failed to send to {recipient.get('email')}: {e}")

        print(f"[CHECKIN_NOTIFY] Sent {len(recipients)} notification(s) for {checker_name} on apt {appointment_id[:8]}")

    except Exception as e:
        print(f"[CHECKIN_NOTIFY] Global failure: {e}")
        # Roll back flag so it can be retried
        db.participants.update_one(
            {"participant_id": participant_id},
            {"$unset": {"checkin_notification_sent": "", "checkin_notification_sent_at": ""}}
        )
