"""
Appointment Lifecycle Service
Handles appointment activation after organizer guarantee is validated.

BUSINESS RULE: A RDV never becomes "active" until:
  1. The organizer's guarantee is validated
  2. Invitation emails have been sent to participants

pending_organizer_guarantee → active (only transition allowed here)

This service is shared between:
  - appointments router (auto-guarantee with saved payment method)
  - webhooks router (after Stripe Checkout completion)
  - check-activation endpoint (frontend polling fallback)
"""
import os
from pymongo import MongoClient
from utils.date_utils import now_utc_iso

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
client = MongoClient(MONGO_URL)
db = client[DB_NAME]


def _get_frontend_url():
    return os.environ.get('FRONTEND_URL', '').rstrip('/')


async def activate_appointment(appointment_id: str, organizer_user_id: str) -> dict:
    """
    Activate an appointment after organizer guarantee is validated.
    Sets status to active, sends invitation emails, syncs calendar, creates meeting.

    IDEMPOTENT: calling on an already active appointment returns immediately.
    """
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        return {"success": False, "error": "Appointment not found"}

    if appointment.get("status") == "active":
        return {"success": True, "already_active": True}

    if appointment.get("status") != "pending_organizer_guarantee":
        return {"success": False, "error": f"Cannot activate from status: {appointment.get('status')}"}

    # 1. Set appointment status to active
    db.appointments.update_one(
        {"appointment_id": appointment_id},
        {"$set": {
            "status": "active",
            "activated_at": now_utc_iso(),
            "updated_at": now_utc_iso()
        }}
    )

    # 2. Send invitation emails to all NON-organizer participants
    participants = list(db.participants.find(
        {"appointment_id": appointment_id, "is_organizer": {"$ne": True}},
        {"_id": 0}
    ))

    frontend_url = _get_frontend_url()
    organizer_user = db.users.find_one({"user_id": organizer_user_id}, {"_id": 0})
    organizer_name = (
        f"{organizer_user.get('first_name', '')} {organizer_user.get('last_name', '')}".strip()
        if organizer_user else "L'organisateur"
    )

    for p in participants:
        try:
            from services.email_service import EmailService
            invitation_link = f"{frontend_url}/invitation/{p['invitation_token']}"
            ics_link = f"{frontend_url}/api/calendar/export/ics/{appointment_id}"

            p_name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
            if not p_name:
                p_name = p.get('name') or p.get('email', '').split('@')[0]

            proof_link = f"{frontend_url}/proof/{appointment_id}?token={p['invitation_token']}"

            await EmailService.send_invitation_email(
                to_email=p['email'],
                to_name=p_name,
                organizer_name=organizer_name,
                appointment_title=appointment.get('title', ''),
                appointment_datetime=appointment.get('start_datetime', ''),
                invitation_link=invitation_link,
                location=appointment.get('location') or appointment.get('meeting_provider'),
                penalty_amount=appointment.get('penalty_amount'),
                penalty_currency=appointment.get('penalty_currency', 'eur'),
                cancellation_deadline_hours=appointment.get('cancellation_deadline_hours'),
                appointment_id=appointment_id,
                ics_link=ics_link,
                appointment_timezone=appointment.get('appointment_timezone', 'Europe/Paris'),
                meeting_join_url=appointment.get('meeting_join_url'),
                meeting_provider=appointment.get('meeting_provider'),
                proof_link=proof_link,
            )
        except Exception as e:
            print(f"[ACTIVATE] Failed to send invitation to {p.get('email')}: {e}")

    # 3. Auto-sync to calendar (non-blocking)
    try:
        from routers.calendar_routes import perform_auto_sync
        appointment["status"] = "active"
        perform_auto_sync(organizer_user_id, appointment_id, appointment)
    except Exception as e:
        print(f"[ACTIVATE] Calendar sync error: {e}")

    # 4. Auto-create meeting if video appointment with managed provider
    meeting_result = None
    if (appointment.get('appointment_type') == 'video'
            and appointment.get('meeting_provider')
            and appointment.get('meeting_provider') != 'external'):
        try:
            from services.meeting_provider_service import create_meeting_for_appointment
            meeting_result = create_meeting_for_appointment(
                appointment_id=appointment_id,
                provider=appointment['meeting_provider'],
                title=appointment.get('title', ''),
                start_datetime=appointment.get('start_datetime', ''),
                duration_minutes=appointment.get('duration_minutes', 60),
                timezone_str=appointment.get('appointment_timezone', 'UTC'),
                organizer_user_id=organizer_user_id,
            )
            if meeting_result and meeting_result.get("success"):
                print(f"[ACTIVATE] Auto-created meeting: {meeting_result.get('join_url')}")
            elif meeting_result and meeting_result.get("error"):
                print(f"[ACTIVATE] Meeting creation FAILED for {appointment['meeting_provider']}: {meeting_result.get('error')}")
        except Exception as e:
            print(f"[ACTIVATE] Meeting creation error: {e}")
            meeting_result = {"error": str(e)}

    return {"success": True, "meeting_result": meeting_result}
