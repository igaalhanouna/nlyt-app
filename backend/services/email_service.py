import os
import asyncio
import resend
from dotenv import load_dotenv
import logging
from datetime import datetime, timezone
from pymongo import MongoClient
import uuid
from pathlib import Path
from utils.date_utils import format_datetime_fr, parse_iso_datetime


def format_email_datetime(dt_string: str, tz_name: str = 'Europe/Paris') -> str:
    """
    Centralized datetime formatting for all emails.

    Uses the project-standard parse_iso_datetime (handles UTC, offsets, and
    legacy naive strings interpreted as Europe/Paris) then converts to
    the appointment's timezone via format_datetime_fr.

    This is the SINGLE source of truth for email date rendering.
    Every email template MUST use this instead of inline parsing.

    Args:
        dt_string: ISO datetime string (UTC preferred)
        tz_name: IANA timezone name from the appointment (default: Europe/Paris)
    """
    dt = parse_iso_datetime(dt_string)
    if dt:
        return format_datetime_fr(dt, tz_name)
    return dt_string or ''

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
        ics_link: str = None,
        appointment_timezone: str = 'Europe/Paris',
        meeting_join_url: str = None,
        meeting_provider: str = None,
        proof_link: str = None,
    ):
        """Send invitation email with full appointment details and ICS calendar link"""
        formatted_date = format_email_datetime(appointment_datetime, appointment_timezone)
        
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
        
        # Build meeting link section for video appointments
        meeting_section = ""
        if meeting_join_url:
            provider_label = {"zoom": "Zoom", "teams": "Microsoft Teams", "meet": "Google Meet"}.get(
                (meeting_provider or "").lower(), meeting_provider or "Visioconférence"
            )
            if proof_link:
                # Video with NLYT Proof: show provider info only, no direct link (proof link is the entry point)
                meeting_section = f"""
                        <p style="margin: 8px 0; color: #64748B;">
                            <strong>Visioconference :</strong> {provider_label}
                        </p>
                """
            else:
                # Fallback: no proof link (shouldn't happen for video, but safety net)
                meeting_section = f"""
                        <p style="margin: 8px 0; color: #64748B;">
                            <strong>Visioconference :</strong> {provider_label}
                        </p>
                        <div style="text-align: center; margin: 12px 0;">
                            <a href="{meeting_join_url}" style="display: inline-block; padding: 10px 24px; background: #6366F1; color: white; text-decoration: none; border-radius: 6px; font-size: 14px; font-weight: bold;">
                                Rejoindre la reunion {provider_label}
                            </a>
                        </div>
                """
            location_display = f"En ligne ({provider_label})"
        
        # Build ICS calendar link section
        calendar_section = ""
        if ics_link:
            calendar_section = f"""
                    <div style="text-align: center; margin-top: 15px; padding-top: 15px; border-top: 1px solid #E2E8F0;">
                        <a href="{ics_link}" style="display: inline-block; padding: 10px 20px; background: #64748B; color: white; text-decoration: none; border-radius: 6px; font-size: 13px;">
                            Ajouter au calendrier (ICS)
                        </a>
                        <p style="color: #94A3B8; font-size: 11px; margin-top: 8px;">
                            Compatible Google Calendar, Outlook, Apple Calendar
                        </p>
                    </div>
            """

        # Build NLYT Proof section
        proof_section = ""
        if proof_link:
            proof_section = f"""
                    <div style="background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: center;">
                        <p style="margin: 0 0 8px 0; color: #1E40AF; font-weight: bold; font-size: 14px;">
                            Confirmer ma presence le jour J
                        </p>
                        <p style="margin: 0 0 12px 0; color: #3B82F6; font-size: 12px;">
                            Le jour du rendez-vous, utilisez ce lien pour prouver votre presence. La visio s'ouvrira automatiquement.
                        </p>
                        <a href="{proof_link}" style="display: inline-block; padding: 12px 28px; background: #2563EB; color: white; text-decoration: none; border-radius: 8px; font-size: 14px; font-weight: bold;">
                            Mon lien de presence NLYT
                        </a>
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
                        {meeting_section}
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
                    {proof_section}
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
        invitation_link: str = None,
        appointment_timezone: str = 'Europe/Paris',
        proof_link: str = None,
        appointment_type: str = 'physical',
        meeting_provider: str = None,
    ):
        """
        Send the DEFINITIVE confirmation email after engagement is finalized.
        This is the participant's reference email with all actionable links.
        Triggered after:
          - Direct acceptance (no guarantee)
          - Stripe webhook confirmation (with guarantee)
        """
        formatted_date = format_email_datetime(appointment_datetime, appointment_timezone)

        is_video = appointment_type == 'video'
        provider_label = {
            'zoom': 'Zoom', 'teams': 'Microsoft Teams', 'meet': 'Google Meet'
        }.get((meeting_provider or '').lower(), meeting_provider or 'Visioconférence')

        # ── Location display ──
        if is_video:
            location_display = f"En ligne — {provider_label}"
        else:
            location_display = location if location else "Non spécifié"

        # ── Penalty reminder ──
        penalty_reminder = ""
        if penalty_amount and penalty_amount > 0:
            cancel_note = f" Vous pouvez annuler sans pénalité jusqu'à {cancellation_deadline_hours}h avant le rendez-vous." if cancellation_deadline_hours else ""
            penalty_reminder = f"""
                    <div style="background: #FEF3C7; border-left: 4px solid #F59E0B; padding: 15px; margin: 20px 0;">
                        <p style="margin: 0; color: #92400E;">
                            <strong>Rappel d'engagement :</strong> Une pénalité de {penalty_amount} {penalty_currency.upper()}
                            s'appliquera en cas d'absence ou de retard excessif.{cancel_note}
                        </p>
                    </div>
            """

        # ── ICS calendar button ──
        ics_button = ""
        if ics_link:
            ics_button = f"""
                    <div style="text-align: center; margin: 25px 0;">
                        <a href="{ics_link}" style="display: inline-block; padding: 14px 28px; background: #3B82F6; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 15px;">
                            Ajouter a mon calendrier
                        </a>
                        <p style="color: #94A3B8; font-size: 12px; margin-top: 10px;">
                            Telechargez le fichier .ics — compatible Google Calendar, Outlook, Apple Calendar
                        </p>
                    </div>
            """

        # ── View invitation link ──
        view_link = ""
        if invitation_link:
            view_link = f"""
                    <p style="text-align: center; margin-top: 20px;">
                        <a href="{invitation_link}" style="color: #3B82F6; text-decoration: underline; font-size: 13px;">
                            Voir tous les details du rendez-vous
                        </a>
                    </p>
            """

        # ── Timezone note ──
        tz_note = ""
        if appointment_timezone and appointment_timezone != 'UTC':
            tz_display = appointment_timezone.replace('_', ' ').split('/')[-1]
            tz_note = f"""
                        <p style="margin: 4px 0 0 0; color: #94A3B8; font-size: 11px;">
                            Fuseau horaire : {appointment_timezone} ({tz_display})
                        </p>
            """

        # ── MAIN SECTION: different content for video vs physical ──
        access_section = ""
        if is_video and proof_link:
            # VIDEO: NLYT Proof is the unique entry point
            access_section = f"""
                    <div style="background: #EFF6FF; border: 2px solid #BFDBFE; border-radius: 10px; padding: 24px; margin: 24px 0; text-align: center;">
                        <p style="margin: 0 0 6px 0; color: #1E40AF; font-weight: bold; font-size: 16px;">
                            Votre lien de reunion
                        </p>
                        <p style="margin: 0 0 16px 0; color: #3B82F6; font-size: 13px; line-height: 1.5;">
                            Le jour du rendez-vous, cliquez sur ce bouton pour :<br/>
                            1. Confirmer votre presence<br/>
                            2. Ouvrir automatiquement la visio {provider_label}
                        </p>
                        <a href="{proof_link}" style="display: inline-block; padding: 14px 32px; background: #2563EB; color: white; text-decoration: none; border-radius: 10px; font-size: 15px; font-weight: bold;">
                            Confirmer ma presence et rejoindre
                        </a>
                        <p style="margin: 12px 0 0 0; color: #64748B; font-size: 11px;">
                            Ce lien est votre point d'entree unique. Il sera actif 30 minutes avant le debut.
                            <br/>Conservez cet email — c'est votre reference pour le jour J.
                        </p>
                    </div>
            """
        elif not is_video:
            # PHYSICAL: GPS / QR check-in info
            loc_text = f"a l'adresse : <strong>{location_display}</strong>" if location else ""
            access_section = f"""
                    <div style="background: #F0FDF4; border: 2px solid #BBF7D0; border-radius: 10px; padding: 24px; margin: 24px 0;">
                        <p style="margin: 0 0 8px 0; color: #166534; font-weight: bold; font-size: 15px;">
                            Comment confirmer votre presence
                        </p>
                        <p style="margin: 0 0 12px 0; color: #15803D; font-size: 13px; line-height: 1.5;">
                            Le jour du rendez-vous {loc_text}, confirmez votre arrivee via :
                        </p>
                        <ul style="margin: 0; padding-left: 20px; color: #15803D; font-size: 13px; line-height: 1.8;">
                            <li>Le bouton <strong>"Je suis arrive"</strong> sur votre page d'invitation</li>
                            <li>Le <strong>scan du QR code</strong> fourni par l'organisateur</li>
                        </ul>
                        <p style="margin: 12px 0 0 0; color: #64748B; font-size: 11px;">
                            La position GPS sera capturee automatiquement si autorisee. Le check-in est disponible 30 min avant le debut.
                        </p>
                    </div>
            """

        # ── Subject ──
        subject = f"Confirmation d'acces — {appointment_title}"

        # ── Header subtitle ──
        header_subtitle = f"Visioconference {provider_label}" if is_video else "Rendez-vous confirme"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Inter', Arial, sans-serif; line-height: 1.6; color: #334155; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #059669; color: white; padding: 30px; text-align: center; }}
                .content {{ background: #ffffff; padding: 30px; border: 1px solid #E2E8F0; }}
                .info-box {{ background: #F8FAFC; padding: 20px; border-radius: 8px; border: 1px solid #E2E8F0; margin: 20px 0; }}
                .footer {{ text-align: center; color: #64748B; font-size: 14px; padding: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="margin: 0; font-size: 22px;">Votre acces est confirme</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9; font-size: 14px;">{header_subtitle} — NLYT</p>
                </div>
                <div class="content">
                    <h2 style="color: #1E293B; margin-top: 0;">Bonjour {to_name},</h2>
                    <p style="color: #475569;">
                        Votre participation au rendez-vous de <strong>{organizer_name}</strong> est maintenant
                        <strong>entierement confirmee</strong>. Vous trouverez ci-dessous toutes les informations
                        necessaires pour le jour J.
                    </p>

                    <div class="info-box">
                        <h3 style="margin: 0 0 15px 0; color: #1E293B;">{appointment_title}</h3>
                        <p style="margin: 8px 0; color: #334155;">
                            <strong>Date :</strong> {formatted_date}
                        </p>
                        {tz_note}
                        <p style="margin: 8px 0; color: #334155;">
                            <strong>{'Reunion' if is_video else 'Lieu'} :</strong> {location_display}
                        </p>
                    </div>

                    {access_section}

                    {penalty_reminder}

                    {ics_button}

                    {view_link}

                    <div style="background: #F1F5F9; border-radius: 8px; padding: 16px; margin-top: 24px; text-align: center;">
                        <p style="margin: 0; color: #64748B; font-size: 12px;">
                            Cet email est votre <strong>confirmation d'acces definitive</strong>.
                            Conservez-le pour retrouver facilement vos liens le jour du rendez-vous.
                        </p>
                    </div>
                </div>
                <div class="footer">
                    <p>&copy; 2026 NLYT. Tous droits reserves.</p>
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
        appointment_link: str = None,
        appointment_timezone: str = 'Europe/Paris'
    ):
        """Send notification to organizer when a participant cancels their participation"""
        formatted_date = format_email_datetime(appointment_datetime, appointment_timezone)
        
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
        location: str = None,
        appointment_timezone: str = 'Europe/Paris'
    ):
        """Send notification to participant when appointment is cancelled by organizer"""
        formatted_date = format_email_datetime(appointment_datetime, appointment_timezone)
        
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
        location: str = None,
        appointment_timezone: str = 'Europe/Paris'
    ):
        """Send notification to participant when appointment is deleted by organizer"""
        formatted_date = format_email_datetime(appointment_datetime, appointment_timezone)
        
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

    @staticmethod
    async def send_guarantee_revalidation_email(
        participant_email: str,
        participant_name: str,
        appointment_title: str,
        revalidation_reason: str,
        invitation_link: str
    ):
        """Send email when a major modification requires guarantee reconfirmation"""

        reason_labels = {
            "city_change": "Le lieu a changé de ville",
            "date_shift": "La date a été décalée de plus de 24 heures",
            "type_change": "Le type de rendez-vous a changé"
        }

        reason_parts = revalidation_reason.split(", ") if revalidation_reason else []
        reason_html_items = ""
        for r in reason_parts:
            key = r.split(":")[0] if ":" in r else r.split("_")[0] + "_" + r.split("_")[1] if "_" in r else r
            for label_key, label_val in reason_labels.items():
                if label_key in r:
                    detail = r.split(":", 1)[1] if ":" in r else ""
                    reason_html_items += f'<li style="margin:6px 0;color:#92400E;">{label_val}{" (" + detail + ")" if detail else ""}</li>'
                    break

        if not reason_html_items:
            reason_html_items = f'<li style="margin:6px 0;color:#92400E;">{revalidation_reason}</li>'

        subject = f"Action requise — Reconfirmez votre garantie pour \"{appointment_title}\""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Inter', Arial, sans-serif; line-height: 1.6; color: #334155; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #D97706; color: white; padding: 25px; text-align: center; }}
                .content {{ background: #ffffff; padding: 30px; border: 1px solid #E2E8F0; }}
                .alert-box {{ background: #FFFBEB; border-left: 4px solid #D97706; padding: 15px; margin: 20px 0; }}
                .cta-btn {{ display: inline-block; background: #D97706; color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; margin-top: 10px; }}
                .footer {{ text-align: center; color: #64748B; font-size: 14px; padding: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="margin: 0; font-size: 22px;">Garantie à reconfirmer</h1>
                </div>
                <div class="content">
                    <h2 style="color: #1E293B; margin-top: 0;">Bonjour {participant_name},</h2>

                    <p>Les conditions du rendez-vous <strong>"{appointment_title}"</strong> ont changé de manière significative :</p>

                    <div class="alert-box">
                        <ul style="margin:0;padding-left:20px;">
                            {reason_html_items}
                        </ul>
                    </div>

                    <p>Votre garantie actuelle nécessite une reconfirmation pour rester valide.</p>

                    <div style="text-align:center;margin:25px 0;">
                        <a href="{invitation_link}" class="cta-btn">Reconfirmer ma garantie</a>
                    </div>

                    <p style="color:#64748B;font-size:13px;">
                        Tant que vous n'avez pas reconfirmé, votre garantie est considérée comme partiellement invalide.
                    </p>
                </div>
                <div class="footer">
                    <p>© 2026 NLYT. Tous droits réservés.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return await EmailService.send_email(participant_email, subject, html_content, email_type="guarantee_revalidation")
