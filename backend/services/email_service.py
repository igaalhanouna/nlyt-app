import os
import asyncio
import resend
from dotenv import load_dotenv
import logging
from datetime import datetime, timezone
from pymongo import MongoClient
import uuid
from pathlib import Path

# Load .env from backend directory
ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')

resend.api_key = RESEND_API_KEY

# MongoDB for tracking email attempts
MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
client = MongoClient(MONGO_URL)
db = client[DB_NAME]

class EmailService:
    @staticmethod
    def _log_email_attempt(email: str, email_type: str, status: str, resend_response: dict = None, error: str = None):
        """Log every email attempt to database for debugging"""
        attempt = {
            "attempt_id": str(uuid.uuid4()),
            "email": email,
            "email_type": email_type,
            "status": status,  # 'success', 'failed', 'error'
            "resend_response": resend_response,
            "error_message": error,
            "attempted_at": datetime.now(timezone.utc).isoformat(),
            "sender_email": SENDER_EMAIL,
            "resend_api_key_present": bool(RESEND_API_KEY)
        }
        
        try:
            db.email_attempts.insert_one(attempt)
            logger.info(f"[EMAIL_ATTEMPT] Logged: {email_type} to {email} - Status: {status}")
        except Exception as e:
            logger.error(f"[EMAIL_ATTEMPT] Failed to log attempt: {str(e)}")
        
        return attempt
    
    @staticmethod
    async def send_email(to_email: str, subject: str, html_content: str, email_type: str = "generic"):
        logger.info(f"[EMAIL_SERVICE] Starting send_email for {to_email}")
        logger.info(f"[EMAIL_SERVICE] Email type: {email_type}")
        logger.info(f"[EMAIL_SERVICE] Resend API key present: {bool(RESEND_API_KEY)}")
        logger.info(f"[EMAIL_SERVICE] Sender email: {SENDER_EMAIL}")
        
        params = {
            "from": SENDER_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html_content
        }
        
        try:
            logger.info(f"[EMAIL_SERVICE] Calling Resend API for {to_email}...")
            email = await asyncio.to_thread(resend.Emails.send, params)
            logger.info(f"[EMAIL_SERVICE] ✅ Resend API call successful for {to_email}")
            logger.info(f"[EMAIL_SERVICE] Resend response: {email}")
            
            # Log success
            EmailService._log_email_attempt(
                email=to_email,
                email_type=email_type,
                status="success",
                resend_response=email
            )
            
            return {"success": True, "email_id": email.get('id'), "resend_response": email}
        except Exception as e:
            logger.error(f"[EMAIL_SERVICE] ❌ Failed to send email to {to_email}: {str(e)}")
            logger.error(f"[EMAIL_SERVICE] Error type: {type(e).__name__}")
            logger.error(f"[EMAIL_SERVICE] Error details: {repr(e)}")
            
            # Log failure
            EmailService._log_email_attempt(
                email=to_email,
                email_type=email_type,
                status="failed",
                error=str(e)
            )
            
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def send_verification_email(to_email: str, verification_token: str, base_url: str):
        logger.info(f"[VERIFICATION_EMAIL] Starting for {to_email}")
        logger.info(f"[VERIFICATION_EMAIL] Token length: {len(verification_token)}")
        logger.info(f"[VERIFICATION_EMAIL] Base URL: {base_url}")
        
        verification_link = f"{base_url}/verify-email?token={verification_token}"
        subject = "Vérifiez votre adresse email - NLYT"
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Inter', Arial, sans-serif; line-height: 1.6; color: #334155; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #0F172A; color: white; padding: 30px; text-align: center; }}
                .content {{ background: #ffffff; padding: 30px; border: 1px solid #E2E8F0; }}
                .button {{ display: inline-block; padding: 12px 24px; background: #0F172A; color: white; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
                .footer {{ text-align: center; color: #64748B; font-size: 14px; padding: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>NLYT</h1>
                </div>
                <div class="content">
                    <h2>Bienvenue sur NLYT !</h2>
                    <p>Merci de vous être inscrit. Veuillez vérifier votre adresse email en cliquant sur le bouton ci-dessous :</p>
                    <a href="{verification_link}" class="button">Vérifier mon email</a>
                    <p>Ou copiez ce lien dans votre navigateur :</p>
                    <p style="word-break: break-all; color: #6366F1;">{verification_link}</p>
                    <p>Ce lien expirera dans 24 heures.</p>
                </div>
                <div class="footer">
                    <p>© 2026 NLYT. Tous droits réservés.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        result = await EmailService.send_email(to_email, subject, html_content, email_type="verification")
        
        logger.info(f"[VERIFICATION_EMAIL] Result for {to_email}: {result}")
        return result
    
    @staticmethod
    async def send_password_reset_email(to_email: str, reset_token: str, base_url: str):
        reset_link = f"{base_url}/reset-password?token={reset_token}"
        subject = "Réinitialisation de votre mot de passe - NLYT"
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Inter', Arial, sans-serif; line-height: 1.6; color: #334155; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #0F172A; color: white; padding: 30px; text-align: center; }}
                .content {{ background: #ffffff; padding: 30px; border: 1px solid #E2E8F0; }}
                .button {{ display: inline-block; padding: 12px 24px; background: #0F172A; color: white; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
                .footer {{ text-align: center; color: #64748B; font-size: 14px; padding: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>NLYT</h1>
                </div>
                <div class="content">
                    <h2>Réinitialisation de mot de passe</h2>
                    <p>Vous avez demandé la réinitialisation de votre mot de passe. Cliquez sur le bouton ci-dessous pour continuer :</p>
                    <a href="{reset_link}" class="button">Réinitialiser mon mot de passe</a>
                    <p>Ou copiez ce lien dans votre navigateur :</p>
                    <p style="word-break: break-all; color: #6366F1;">{reset_link}</p>
                    <p>Ce lien expirera dans 1 heure.</p>
                    <p>Si vous n'avez pas demandé cette réinitialisation, ignorez cet email.</p>
                </div>
                <div class="footer">
                    <p>© 2026 NLYT. Tous droits réservés.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return await EmailService.send_email(to_email, subject, html_content, email_type="password_reset")
    
    @staticmethod
    async def send_invitation_email(
        to_email: str, 
        to_name: str, 
        organizer_name: str, 
        appointment_title: str, 
        appointment_datetime: str, 
        invitation_link: str,
        location: str = None,
        penalty_amount: float = None,
        penalty_currency: str = "EUR",
        cancellation_deadline_hours: int = None,
        appointment_id: str = None,
        ics_link: str = None
    ):
        """Send invitation email with full appointment details and ICS calendar link"""
        # Parse datetime for display
        try:
            from datetime import datetime, timezone
            if '+' in appointment_datetime or 'Z' in appointment_datetime:
                dt = datetime.fromisoformat(appointment_datetime.replace('Z', '+00:00'))
            else:
                dt = datetime.strptime(appointment_datetime, "%Y-%m-%dT%H:%M")
            formatted_date = dt.strftime("%A %d %B %Y à %H:%M")
        except:
            formatted_date = appointment_datetime
        
        # Build penalty info
        penalty_info = ""
        if penalty_amount and penalty_amount > 0:
            penalty_info = f"""
            <p style="margin: 8px 0; color: #64748B;">
                <strong>Pénalité en cas d'absence :</strong> {penalty_amount} {penalty_currency.upper()}
            </p>
            """
        
        # Build deadline info
        deadline_info = ""
        if cancellation_deadline_hours:
            deadline_info = f"""
            <p style="margin: 8px 0; color: #64748B;">
                <strong>Délai d'annulation :</strong> {cancellation_deadline_hours}h avant le rendez-vous
            </p>
            """
        
        # Build location info
        location_display = location if location else "Non spécifié"
        
        # Build ICS calendar link section
        calendar_section = ""
        if ics_link:
            calendar_section = f"""
                    <div style="text-align: center; margin-top: 15px; padding-top: 15px; border-top: 1px solid #E2E8F0;">
                        <a href="{ics_link}" style="display: inline-block; padding: 10px 20px; background: #64748B; color: white; text-decoration: none; border-radius: 6px; font-size: 13px;">
                            📅 Ajouter au calendrier (ICS)
                        </a>
                        <p style="color: #94A3B8; font-size: 11px; margin-top: 8px;">
                            Compatible Google Calendar, Outlook, Apple Calendar
                        </p>
                    </div>
            """
        
        subject = f"Invitation à un rendez-vous - {appointment_title}"
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Inter', Arial, sans-serif; line-height: 1.6; color: #334155; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #0F172A; color: white; padding: 30px; text-align: center; }}
                .content {{ background: #ffffff; padding: 30px; border: 1px solid #E2E8F0; }}
                .button {{ display: inline-block; padding: 14px 28px; background: #10B981; color: white; text-decoration: none; border-radius: 8px; margin: 20px 0; font-weight: bold; }}
                .info-box {{ background: #F8FAFC; padding: 20px; border-radius: 8px; border: 1px solid #E2E8F0; margin: 20px 0; }}
                .warning-box {{ background: #FEF3C7; border-left: 4px solid #F59E0B; padding: 15px; margin: 20px 0; }}
                .footer {{ text-align: center; color: #64748B; font-size: 14px; padding: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="margin: 0;">NLYT</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">Rendez-vous avec engagement</p>
                </div>
                <div class="content">
                    <h2 style="color: #1E293B;">Bonjour {to_name},</h2>
                    <p style="color: #475569;">{organizer_name} vous invite à un rendez-vous avec contrat d'engagement.</p>
                    
                    <div class="info-box">
                        <h3 style="margin: 0 0 15px 0; color: #1E293B;">{appointment_title}</h3>
                        <p style="margin: 8px 0; color: #64748B;">
                            <strong>📅 Date :</strong> {formatted_date}
                        </p>
                        <p style="margin: 8px 0; color: #64748B;">
                            <strong>📍 Lieu :</strong> {location_display}
                        </p>
                        {penalty_info}
                        {deadline_info}
                    </div>
                    
                    <div class="warning-box">
                        <p style="margin: 0; color: #92400E;">
                            <strong>⚠️ Attention :</strong> Ce rendez-vous inclut un contrat d'engagement. 
                            En acceptant, vous vous engagez à respecter les conditions définies par l'organisateur.
                        </p>
                    </div>
                    
                    <div style="text-align: center;">
                        <a href="{invitation_link}" class="button">Voir et répondre à l'invitation</a>
                    </div>
                    
                    <p style="color: #94A3B8; font-size: 13px; text-align: center;">
                        Vous pourrez consulter toutes les conditions avant d'accepter ou de refuser.
                    </p>
                    
                    {calendar_section}
                </div>
                <div class="footer">
                    <p>© 2026 NLYT. Tous droits réservés.</p>
                    <p style="font-size: 12px;">Si vous n'êtes pas concerné par cette invitation, ignorez cet email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return await EmailService.send_email(to_email, subject, html_content, email_type="invitation")


    @staticmethod
    async def send_acceptance_confirmation_email(
        to_email: str,
        to_name: str,
        organizer_name: str,
        appointment_title: str,
        appointment_datetime: str,
        location: str = None,
        penalty_amount: float = None,
        penalty_currency: str = "EUR",
        cancellation_deadline_hours: int = None,
        ics_link: str = None,
        invitation_link: str = None
    ):
        """Send confirmation email after participant accepts invitation, with ICS download link"""
        # Parse datetime for display
        try:
            from datetime import datetime, timezone
            if '+' in appointment_datetime or 'Z' in appointment_datetime:
                dt = datetime.fromisoformat(appointment_datetime.replace('Z', '+00:00'))
            else:
                dt = datetime.strptime(appointment_datetime, "%Y-%m-%dT%H:%M")
            formatted_date = dt.strftime("%A %d %B %Y à %H:%M")
        except:
            formatted_date = appointment_datetime
        
        location_display = location if location else "Non spécifié"
        
        # Build penalty reminder
        penalty_reminder = ""
        if penalty_amount and penalty_amount > 0:
            penalty_reminder = f"""
            <div style="background: #FEF3C7; border-left: 4px solid #F59E0B; padding: 15px; margin: 20px 0;">
                <p style="margin: 0; color: #92400E;">
                    <strong>Rappel d'engagement :</strong> Une pénalité de {penalty_amount} {penalty_currency.upper()} 
                    s'appliquera en cas d'absence ou de retard excessif.
                    {f"Vous pouvez annuler sans pénalité jusqu'à {cancellation_deadline_hours}h avant le rendez-vous." if cancellation_deadline_hours else ""}
                </p>
            </div>
            """
        
        # ICS button
        ics_button = ""
        if ics_link:
            ics_button = f"""
                    <div style="text-align: center; margin: 25px 0;">
                        <a href="{ics_link}" style="display: inline-block; padding: 14px 28px; background: #3B82F6; color: white; text-decoration: none; border-radius: 8px; font-weight: bold;">
                            📅 Ajouter à mon calendrier
                        </a>
                        <p style="color: #94A3B8; font-size: 12px; margin-top: 10px;">
                            Téléchargez le fichier .ics pour l'ajouter à Google Calendar, Outlook ou Apple Calendar
                        </p>
                    </div>
            """
        
        # View invitation link
        view_link = ""
        if invitation_link:
            view_link = f"""
                    <p style="text-align: center; margin-top: 20px;">
                        <a href="{invitation_link}" style="color: #3B82F6; text-decoration: underline;">
                            Voir les détails du rendez-vous
                        </a>
                    </p>
            """
        
        subject = f"✅ Confirmation - {appointment_title}"
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Inter', Arial, sans-serif; line-height: 1.6; color: #334155; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #059669; color: white; padding: 30px; text-align: center; }}
                .content {{ background: #ffffff; padding: 30px; border: 1px solid #E2E8F0; }}
                .info-box {{ background: #F0FDF4; padding: 20px; border-radius: 8px; border: 1px solid #BBF7D0; margin: 20px 0; }}
                .footer {{ text-align: center; color: #64748B; font-size: 14px; padding: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="margin: 0;">✅ Rendez-vous confirmé</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">NLYT</p>
                </div>
                <div class="content">
                    <h2 style="color: #1E293B;">Bonjour {to_name},</h2>
                    <p style="color: #475569;">
                        Vous avez accepté l'invitation de <strong>{organizer_name}</strong>. 
                        Le rendez-vous est maintenant confirmé.
                    </p>
                    
                    <div class="info-box">
                        <h3 style="margin: 0 0 15px 0; color: #1E293B;">📋 {appointment_title}</h3>
                        <p style="margin: 8px 0; color: #64748B;">
                            <strong>📅 Date :</strong> {formatted_date}
                        </p>
                        <p style="margin: 8px 0; color: #64748B;">
                            <strong>📍 Lieu :</strong> {location_display}
                        </p>
                    </div>
                    
                    {penalty_reminder}
                    
                    {ics_button}
                    
                    {view_link}
                </div>
                <div class="footer">
                    <p>© 2026 NLYT. Tous droits réservés.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return await EmailService.send_email(to_email, subject, html_content, email_type="acceptance_confirmation")


    @staticmethod
    async def send_participant_cancellation_notification(
        organizer_email: str,
        organizer_name: str,
        participant_name: str,
        participant_email: str,
        appointment_title: str,
        appointment_datetime: str,
        location: str = None,
        appointment_link: str = None
    ):
        """Send notification to organizer when a participant cancels their participation"""
        # Parse datetime for display
        try:
            from datetime import datetime, timezone
            if '+' in appointment_datetime or 'Z' in appointment_datetime:
                dt = datetime.fromisoformat(appointment_datetime.replace('Z', '+00:00'))
            else:
                dt = datetime.strptime(appointment_datetime, "%Y-%m-%dT%H:%M")
            formatted_date = dt.strftime("%A %d %B %Y à %H:%M")
        except:
            formatted_date = appointment_datetime
        
        location_display = location if location else "Non spécifié"
        
        # Build link button if provided
        link_button = ""
        if appointment_link:
            link_button = f"""
            <div style="text-align: center; margin-top: 25px;">
                <a href="{appointment_link}" style="display: inline-block; padding: 12px 24px; background: #0F172A; color: white; text-decoration: none; border-radius: 6px; font-weight: 500;">
                    Voir les détails du rendez-vous
                </a>
            </div>
            """
        
        subject = f"Un participant a annulé sa participation - {appointment_title}"
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Inter', Arial, sans-serif; line-height: 1.6; color: #334155; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #F97316; color: white; padding: 25px; text-align: center; }}
                .content {{ background: #ffffff; padding: 30px; border: 1px solid #E2E8F0; }}
                .alert-box {{ background: #FEF3C7; border-left: 4px solid #F97316; padding: 15px; margin: 20px 0; }}
                .info-box {{ background: #F8FAFC; padding: 20px; border-radius: 8px; border: 1px solid #E2E8F0; margin: 20px 0; }}
                .footer {{ text-align: center; color: #64748B; font-size: 14px; padding: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="margin: 0; font-size: 22px;">Annulation de participation</h1>
                </div>
                <div class="content">
                    <h2 style="color: #1E293B; margin-top: 0;">Bonjour {organizer_name},</h2>
                    
                    <div class="alert-box">
                        <p style="margin: 0; color: #92400E;">
                            <strong>Le participant {participant_name}</strong> ({participant_email}) a annulé sa participation à votre rendez-vous.
                        </p>
                    </div>
                    
                    <div class="info-box">
                        <h3 style="margin: 0 0 15px 0; color: #1E293B;">{appointment_title}</h3>
                        <p style="margin: 8px 0; color: #64748B;">
                            <strong>📅 Date :</strong> {formatted_date}
                        </p>
                        <p style="margin: 8px 0; color: #64748B;">
                            <strong>📍 Lieu :</strong> {location_display}
                        </p>
                    </div>
                    
                    <p style="color: #475569;">
                        Le participant a annulé dans les délais prévus. Aucune pénalité ne sera appliquée.
                    </p>
                    
                    {link_button}
                </div>
                <div class="footer">
                    <p>© 2026 NLYT. Tous droits réservés.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return await EmailService.send_email(organizer_email, subject, html_content, email_type="participant_cancellation")

    @staticmethod
    async def send_appointment_cancelled_notification(
        participant_email: str,
        participant_name: str,
        organizer_name: str,
        appointment_title: str,
        appointment_datetime: str,
        location: str = None
    ):
        """Send notification to participant when appointment is cancelled by organizer"""
        # Parse datetime for display
        try:
            from datetime import datetime, timezone
            if '+' in appointment_datetime or 'Z' in appointment_datetime:
                dt = datetime.fromisoformat(appointment_datetime.replace('Z', '+00:00'))
            else:
                dt = datetime.strptime(appointment_datetime, "%Y-%m-%dT%H:%M")
            formatted_date = dt.strftime("%A %d %B %Y à %H:%M")
        except:
            formatted_date = appointment_datetime
        
        location_display = location if location else "Non spécifié"
        
        subject = f"Le rendez-vous a été annulé - {appointment_title}"
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Inter', Arial, sans-serif; line-height: 1.6; color: #334155; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #DC2626; color: white; padding: 25px; text-align: center; }}
                .content {{ background: #ffffff; padding: 30px; border: 1px solid #E2E8F0; }}
                .alert-box {{ background: #FEE2E2; border-left: 4px solid #DC2626; padding: 15px; margin: 20px 0; }}
                .info-box {{ background: #F8FAFC; padding: 20px; border-radius: 8px; border: 1px solid #E2E8F0; margin: 20px 0; }}
                .footer {{ text-align: center; color: #64748B; font-size: 14px; padding: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="margin: 0; font-size: 22px;">Rendez-vous annulé</h1>
                </div>
                <div class="content">
                    <h2 style="color: #1E293B; margin-top: 0;">Bonjour {participant_name},</h2>
                    
                    <div class="alert-box">
                        <p style="margin: 0; color: #991B1B;">
                            <strong>Le rendez-vous suivant a été annulé par l'organisateur ({organizer_name}).</strong>
                        </p>
                    </div>
                    
                    <div class="info-box">
                        <h3 style="margin: 0 0 15px 0; color: #1E293B; text-decoration: line-through;">{appointment_title}</h3>
                        <p style="margin: 8px 0; color: #64748B;">
                            <strong>📅 Date :</strong> {formatted_date}
                        </p>
                        <p style="margin: 8px 0; color: #64748B;">
                            <strong>📍 Lieu :</strong> {location_display}
                        </p>
                    </div>
                    
                    <p style="color: #475569;">
                        <strong>Vous n'avez plus besoin de vous présenter à ce rendez-vous.</strong>
                    </p>
                    
                    <p style="color: #64748B; font-size: 14px;">
                        Si vous avez des questions, veuillez contacter directement l'organisateur.
                    </p>
                </div>
                <div class="footer">
                    <p>© 2026 NLYT. Tous droits réservés.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return await EmailService.send_email(participant_email, subject, html_content, email_type="appointment_cancelled")

    @staticmethod
    async def send_appointment_deleted_notification(
        participant_email: str,
        participant_name: str,
        organizer_name: str,
        appointment_title: str,
        appointment_datetime: str,
        location: str = None
    ):
        """Send notification to participant when appointment is deleted by organizer"""
        # Parse datetime for display
        try:
            from datetime import datetime, timezone
            if '+' in appointment_datetime or 'Z' in appointment_datetime:
                dt = datetime.fromisoformat(appointment_datetime.replace('Z', '+00:00'))
            else:
                dt = datetime.strptime(appointment_datetime, "%Y-%m-%dT%H:%M")
            formatted_date = dt.strftime("%A %d %B %Y à %H:%M")
        except:
            formatted_date = appointment_datetime
        
        location_display = location if location else "Non spécifié"
        
        subject = f"Le rendez-vous a été supprimé - {appointment_title}"
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Inter', Arial, sans-serif; line-height: 1.6; color: #334155; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #64748B; color: white; padding: 25px; text-align: center; }}
                .content {{ background: #ffffff; padding: 30px; border: 1px solid #E2E8F0; }}
                .alert-box {{ background: #F1F5F9; border-left: 4px solid #64748B; padding: 15px; margin: 20px 0; }}
                .info-box {{ background: #F8FAFC; padding: 20px; border-radius: 8px; border: 1px solid #E2E8F0; margin: 20px 0; }}
                .footer {{ text-align: center; color: #64748B; font-size: 14px; padding: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="margin: 0; font-size: 22px;">Rendez-vous supprimé</h1>
                </div>
                <div class="content">
                    <h2 style="color: #1E293B; margin-top: 0;">Bonjour {participant_name},</h2>
                    
                    <div class="alert-box">
                        <p style="margin: 0; color: #475569;">
                            <strong>Le rendez-vous suivant a été supprimé par l'organisateur.</strong>
                        </p>
                    </div>
                    
                    <div class="info-box">
                        <h3 style="margin: 0 0 15px 0; color: #94A3B8; text-decoration: line-through;">{appointment_title}</h3>
                        <p style="margin: 8px 0; color: #94A3B8;">
                            <strong>📅 Date :</strong> {formatted_date}
                        </p>
                        <p style="margin: 8px 0; color: #94A3B8;">
                            <strong>📍 Lieu :</strong> {location_display}
                        </p>
                    </div>
                    
                    <p style="color: #475569;">
                        <strong>Ce rendez-vous n'aura pas lieu.</strong>
                    </p>
                </div>
                <div class="footer">
                    <p>© 2026 NLYT. Tous droits réservés.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return await EmailService.send_email(participant_email, subject, html_content, email_type="appointment_deleted")