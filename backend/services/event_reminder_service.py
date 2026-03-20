"""
Event Reminder Service
Sends customizable reminders before the appointment time.

IMPORTANT: This is SEPARATE from the cancellation deadline reminder.
- Cancellation deadline reminder: 1h before deadline (reminder_service.py)
- Event reminders: 10min/1h/1day before the appointment itself (this file)
"""
import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from pathlib import Path
from dotenv import load_dotenv

# Load .env
ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')

client = MongoClient(MONGO_URL)
db = client[DB_NAME]


class EventReminderService:
    """
    Service for sending event reminders (10min, 1h, 1day before appointment).
    Completely separate from cancellation deadline reminders.
    """
    
    REMINDER_TYPES = {
        'ten_minutes_before': {'minutes': 10, 'label': '10 minutes'},
        'one_hour_before': {'minutes': 60, 'label': '1 heure'},
        'one_day_before': {'minutes': 1440, 'label': '1 jour'}
    }
    
    @staticmethod
    def get_frontend_url() -> str:
        """Get FRONTEND_URL from env"""
        frontend_url = os.environ.get('FRONTEND_URL', '')
        if frontend_url:
            return frontend_url.rstrip('/')
        # NEVER use a hardcoded fallback - fail explicitly
        raise ValueError("FRONTEND_URL environment variable is required but not set")
    
    @staticmethod
    def parse_datetime(dt_str: str) -> datetime:
        """Parse datetime string to datetime object with UTC timezone"""
        try:
            if '+' in dt_str or 'Z' in dt_str:
                return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M")
            return dt.replace(tzinfo=timezone.utc)
        except:
            return None
    
    @staticmethod
    async def send_event_reminder_email(participant: dict, appointment: dict, reminder_type: str) -> bool:
        """Send event reminder email to a participant"""
        try:
            from services.email_service import EmailService
            
            reminder_info = EventReminderService.REMINDER_TYPES.get(reminder_type, {})
            time_label = reminder_info.get('label', 'bientôt')
            
            # Build participant name
            participant_name = f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip()
            if not participant_name:
                participant_name = participant.get('name', '') or participant.get('email', '').split('@')[0]
            
            # Parse appointment datetime
            start_dt = EventReminderService.parse_datetime(appointment.get('start_datetime', ''))
            if start_dt:
                date_display = start_dt.strftime("%A %d %B %Y à %H:%M")
            else:
                date_display = appointment.get('start_datetime', 'Date non disponible')
            
            # Build email
            base_url = EventReminderService.get_frontend_url()
            appointment_link = f"{base_url}/appointments/{appointment['appointment_id']}"
            
            subject = f"Rappel : votre rendez-vous dans {time_label}"
            
            html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background-color: #DBEAFE; border-left: 4px solid #3B82F6; padding: 16px; margin-bottom: 24px;">
                    <p style="margin: 0; color: #1E40AF; font-weight: bold;">🔔 Rappel : votre rendez-vous approche</p>
                </div>
                
                <p style="color: #475569;">Bonjour {participant_name},</p>
                
                <p style="color: #475569;">Ce message vous est envoyé <strong>{time_label}</strong> avant votre rendez-vous.</p>
                
                <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 20px; margin: 20px 0;">
                    <h3 style="margin: 0 0 12px 0; color: #1E293B;">{appointment.get('title', 'Rendez-vous')}</h3>
                    <p style="margin: 8px 0; color: #64748B;">
                        <strong>📅 Date :</strong> {date_display}
                    </p>
                    <p style="margin: 8px 0; color: #64748B;">
                        <strong>📍 Lieu :</strong> {appointment.get('location', '') or appointment.get('meeting_provider', 'Non spécifié')}
                    </p>
                    <p style="margin: 8px 0; color: #64748B;">
                        <strong>⏱️ Durée :</strong> {appointment.get('duration_minutes', 60)} minutes
                    </p>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{appointment_link}" style="display: inline-block; background-color: #3B82F6; color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold;">
                        Voir le rendez-vous
                    </a>
                </div>
                
                <p style="color: #94A3B8; font-size: 12px; margin-top: 30px;">
                    Ce rappel a été configuré par l'organisateur du rendez-vous.
                </p>
            </div>
            """
            
            result = await EmailService.send_email(
                to_email=participant.get('email'),
                subject=subject,
                html_content=html_content,
                email_type="event_reminder"
            )
            
            if result.get('success'):
                logger.info(f"[EVENT_REMINDER] ✅ Sent {reminder_type} to {participant.get('email')} for {appointment['appointment_id']}")
                return True
            else:
                logger.error(f"[EVENT_REMINDER] ❌ Failed {reminder_type} to {participant.get('email')}: {result.get('error')}")
                return False
                
        except Exception as e:
            logger.error(f"[EVENT_REMINDER] ❌ Exception: {str(e)}")
            return False
    
    @staticmethod
    async def process_event_reminders():
        """
        Process and send event reminders.
        Called periodically by the scheduler.
        
        This is SEPARATE from cancellation deadline reminders.
        """
        now = datetime.now(timezone.utc)
        logger.info(f"[EVENT_REMINDER] Starting check at {now.isoformat()}")
        
        # Find active appointments with event_reminders configured
        appointments = list(db.appointments.find({
            "status": {"$in": ["active", "draft"]},
            "event_reminders": {"$exists": True}
        }, {"_id": 0}))
        
        reminders_sent_count = 0
        
        for apt in appointments:
            start_dt = EventReminderService.parse_datetime(apt.get('start_datetime', ''))
            if not start_dt:
                continue
            
            # Skip if appointment already passed
            if now >= start_dt:
                continue
            
            event_reminders = apt.get('event_reminders', {})
            reminders_sent = apt.get('event_reminders_sent', {})
            
            # Check each reminder type
            for reminder_type, config in EventReminderService.REMINDER_TYPES.items():
                # Check if this reminder is enabled
                if not event_reminders.get(reminder_type, False):
                    continue
                
                # Check if already sent
                sent_key = f"{reminder_type}_sent"
                if reminders_sent.get(sent_key, False):
                    continue
                
                # Calculate when this reminder should be sent
                reminder_time = start_dt - timedelta(minutes=config['minutes'])
                
                # Check if it's time to send
                if now >= reminder_time:
                    # Get participants
                    participants = list(db.participants.find(
                        {"appointment_id": apt['appointment_id']},
                        {"_id": 0}
                    ))
                    
                    # Send to all participants
                    for participant in participants:
                        if participant.get('status') in ['cancelled', 'rejected']:
                            continue
                        await EventReminderService.send_event_reminder_email(participant, apt, reminder_type)
                    
                    # Mark as sent
                    sent_at_key = f"{reminder_type}_sent_at"
                    db.appointments.update_one(
                        {"appointment_id": apt['appointment_id']},
                        {"$set": {
                            f"event_reminders_sent.{sent_key}": True,
                            f"event_reminders_sent.{sent_at_key}": now.isoformat()
                        }}
                    )
                    
                    reminders_sent_count += 1
                    logger.info(f"[EVENT_REMINDER] ✅ {reminder_type} sent for {apt['appointment_id']}")
        
        logger.info(f"[EVENT_REMINDER] Completed - {reminders_sent_count} reminders sent")
        return reminders_sent_count


async def run_event_reminder_job():
    """Entry point for the event reminder job"""
    return await EventReminderService.process_event_reminders()


if __name__ == "__main__":
    asyncio.run(run_event_reminder_job())
