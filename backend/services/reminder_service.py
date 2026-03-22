"""
Reminder Scheduler Service
Sends automatic reminders 1 hour before the cancellation deadline
"""
import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from pathlib import Path
from dotenv import load_dotenv
from utils.date_utils import format_datetime_fr, parse_iso_datetime as _parse_dt

# Load .env
ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
FRONTEND_URL = os.environ.get('FRONTEND_URL', '')

client = MongoClient(MONGO_URL)
db = client[DB_NAME]


class ReminderService:
    
    @staticmethod
    def get_frontend_url() -> str:
        """Get FRONTEND_URL from env - read at runtime, not at import"""
        frontend_url = os.environ.get('FRONTEND_URL', '')
        if frontend_url:
            return frontend_url.rstrip('/')
        # NEVER use a hardcoded fallback - fail explicitly
        raise ValueError("FRONTEND_URL environment variable is required but not set")
    
    @staticmethod
    def parse_datetime(dt_str: str) -> datetime:
        """Parse datetime string to datetime object with UTC timezone"""
        return _parse_dt(dt_str)
    
    @staticmethod
    def calculate_reminder_time(appointment: dict) -> datetime:
        """
        Calculate when the reminder should be sent.
        Reminder = cancellation_deadline - 1 hour
        Cancellation deadline = start_datetime - cancellation_deadline_hours
        """
        start_dt = ReminderService.parse_datetime(appointment.get('start_datetime', ''))
        if not start_dt:
            return None
        
        cancellation_hours = appointment.get('cancellation_deadline_hours', 24)
        
        # Cancellation deadline = start - cancellation_deadline_hours
        cancellation_deadline = start_dt - timedelta(hours=cancellation_hours)
        
        # Reminder time = cancellation_deadline - 1 hour
        reminder_time = cancellation_deadline - timedelta(hours=1)
        
        return reminder_time
    
    @staticmethod
    async def send_reminder_email(participant: dict, appointment: dict) -> bool:
        """Send reminder email to a participant"""
        try:
            from services.email_service import EmailService
            
            # Build participant name
            participant_name = f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip()
            if not participant_name:
                participant_name = participant.get('name', '') or participant.get('email', '').split('@')[0]
            
            # Parse appointment datetime for display
            start_dt = ReminderService.parse_datetime(appointment.get('start_datetime', ''))
            if start_dt:
                date_display = format_datetime_fr(start_dt)
            else:
                date_display = appointment.get('start_datetime', 'Date non disponible')
            
            # Build email content
            base_url = ReminderService.get_frontend_url()
            appointment_link = f"{base_url}/appointments/{appointment['appointment_id']}"
            
            subject = "Rappel : délai d'annulation bientôt atteint"
            
            html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background-color: #FEF3C7; border-left: 4px solid #F59E0B; padding: 16px; margin-bottom: 24px;">
                    <p style="margin: 0; color: #92400E; font-weight: bold;">⚠️ Attention : il vous reste 1 heure pour annuler sans pénalité</p>
                </div>
                
                <h2 style="color: #1E293B;">Rappel de rendez-vous</h2>
                
                <p style="color: #475569;">Bonjour {participant_name},</p>
                
                <p style="color: #475569;">Vous avez un rendez-vous prévu :</p>
                
                <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 20px; margin: 20px 0;">
                    <h3 style="margin: 0 0 12px 0; color: #1E293B;">{appointment.get('title', 'Rendez-vous')}</h3>
                    <p style="margin: 8px 0; color: #64748B;">
                        <strong>Date :</strong> {date_display}
                    </p>
                    <p style="margin: 8px 0; color: #64748B;">
                        <strong>Lieu :</strong> {appointment.get('location', '') or appointment.get('meeting_provider', 'Non spécifié')}
                    </p>
                    <p style="margin: 8px 0; color: #64748B;">
                        <strong>Pénalité en cas d'absence :</strong> {appointment.get('penalty_amount', 0)} {appointment.get('penalty_currency', 'EUR').upper()}
                    </p>
                </div>
                
                <p style="color: #DC2626; font-weight: bold;">
                    ⏰ Passé ce délai d'1 heure, les conditions d'engagement s'appliqueront et vous ne pourrez plus annuler sans pénalité.
                </p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{appointment_link}" style="display: inline-block; background-color: #1E293B; color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold;">
                        Voir le rendez-vous
                    </a>
                </div>
                
                <p style="color: #94A3B8; font-size: 12px; margin-top: 30px;">
                    Cet email a été envoyé automatiquement par NLYT.
                </p>
            </div>
            """
            
            result = await EmailService.send_email(
                to_email=participant.get('email'),
                subject=subject,
                html_content=html_content,
                email_type="reminder"
            )
            
            if result.get('success'):
                logger.info(f"[REMINDER] ✅ Sent to {participant.get('email')} for appointment {appointment['appointment_id']}")
                return True
            else:
                logger.error(f"[REMINDER] ❌ Failed to send to {participant.get('email')}: {result.get('error')}")
                return False
                
        except Exception as e:
            logger.error(f"[REMINDER] ❌ Exception sending to {participant.get('email')}: {str(e)}")
            return False
    
    @staticmethod
    async def process_reminders():
        """
        Main function to process and send reminders.
        Called periodically by the scheduler.
        """
        now = datetime.now(timezone.utc)
        logger.info(f"[REMINDER] Starting reminder check at {now.isoformat()}")
        
        # Find appointments that need reminders (exclude cancelled/deleted)
        appointments = list(db.appointments.find({
            "status": {"$in": ["active", "draft"]},
            "reminder_sent": {"$ne": True}
        }, {"_id": 0}))
        
        reminders_sent = 0
        
        for apt in appointments:
            reminder_time = ReminderService.calculate_reminder_time(apt)
            
            if not reminder_time:
                continue
            
            # Check if it's time to send the reminder
            if now >= reminder_time:
                # Check if the appointment hasn't already started
                start_dt = ReminderService.parse_datetime(apt.get('start_datetime', ''))
                if start_dt and now >= start_dt:
                    # Appointment already started, don't send reminder
                    logger.info(f"[REMINDER] Skipping {apt['appointment_id']} - already started")
                    continue
                
                # Get all participants
                participants = list(db.participants.find(
                    {"appointment_id": apt['appointment_id']},
                    {"_id": 0}
                ))
                
                if not participants:
                    logger.info(f"[REMINDER] No participants for {apt['appointment_id']}")
                    continue
                
                # Send reminders to all participants
                all_sent = True
                for participant in participants:
                    if participant.get('status') in ['cancelled', 'rejected']:
                        continue
                    
                    success = await ReminderService.send_reminder_email(participant, apt)
                    if not success:
                        all_sent = False
                
                # Mark reminder as sent
                db.appointments.update_one(
                    {"appointment_id": apt['appointment_id']},
                    {"$set": {
                        "reminder_sent": True,
                        "reminder_sent_at": now.isoformat()
                    }}
                )
                
                reminders_sent += 1
                logger.info(f"[REMINDER] ✅ Processed {apt['appointment_id']} ({apt['title']})")
        
        logger.info(f"[REMINDER] Completed - {reminders_sent} appointments processed")
        return reminders_sent


async def run_reminder_job():
    """Entry point for the reminder job"""
    return await ReminderService.process_reminders()


if __name__ == "__main__":
    # For testing
    asyncio.run(run_reminder_job())
