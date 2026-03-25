import os
import asyncio
import resend
from dotenv import load_dotenv
import logging
from datetime import datetime, timezone
import uuid
from pathlib import Path
from utils.date_utils import format_datetime_fr, parse_iso_datetime


from database import db
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

# ─────────────────────────────────────────────────────────────
# EMAIL DESIGN SYSTEM — Single source of truth
# ─────────────────────────────────────────────────────────────

LOGO_URL = "https://static.prod-images.emergentagent.com/jobs/8d993bdc-837f-49f8-85bc-15685d06a6d0/images/50e29436225480c1937c68846acd3259ae9d907f89eceebb9fd6313f99583083.png"
SITE_URL = "https://nlyt.io"

ACCENT_COLORS = {
    "neutral": "#64748B",
    "success": "#10B981",
    "warning": "#F59E0B",
    "danger":  "#EF4444",
    "info":    "#3B82F6",
}

def _base_template(body_html: str, accent: str = "neutral") -> str:
    """Wrap any email body in the NLYT branded template."""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>NLYT</title>
</head>
<body style="margin:0;padding:0;background-color:#F1F5F9;font-family:'Inter',Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#F1F5F9;">
<tr><td align="center" style="padding:32px 16px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);">

<!-- HEADER -->
<tr><td style="background-color:#0A0A0B;padding:28px 32px;text-align:center;">
  <a href="{SITE_URL}" target="_blank" style="text-decoration:none;">
    <span style="font-size:22px;font-weight:700;letter-spacing:0.35em;color:#FFFFFF;">N<span style="color:rgba(255,255,255,0.4);">&middot;</span>L<span style="color:rgba(255,255,255,0.4);">&middot;</span>Y<span style="color:rgba(255,255,255,0.4);">&middot;</span>T</span>
    <br/>
    <span style="font-size:10px;font-weight:500;letter-spacing:0.25em;color:rgba(255,255,255,0.35);text-transform:uppercase;">Never Lose Your Time</span>
  </a>
</td></tr>

<!-- BODY -->
<tr><td style="background-color:#FFFFFF;padding:36px 36px 28px 36px;">
{body_html}
</td></tr>

<!-- FOOTER -->
<tr><td style="background-color:#F8FAFC;padding:24px 36px;border-top:1px solid #E2E8F0;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
    <tr><td style="text-align:center;padding-bottom:12px;">
      <a href="{SITE_URL}" style="text-decoration:none;">
        <span style="font-size:14px;font-weight:700;letter-spacing:0.3em;color:#0F172A;">N<span style="color:#94A3B8;">&middot;</span>L<span style="color:#94A3B8;">&middot;</span>Y<span style="color:#94A3B8;">&middot;</span>T</span>
      </a>
    </td></tr>
    <tr><td style="text-align:center;padding-bottom:8px;">
      <p style="margin:0;font-size:12px;color:#94A3B8;line-height:1.6;">Votre temps a de la valeur. Protégez-le.</p>
    </td></tr>
    <tr><td style="text-align:center;">
      <a href="{SITE_URL}" style="color:#3B82F6;font-size:12px;text-decoration:none;">nlyt.io</a>
      <span style="color:#CBD5E1;font-size:12px;">&nbsp;&middot;&nbsp;</span>
      <span style="font-size:12px;color:#CBD5E1;">&copy; 2026 NLYT</span>
    </td></tr>
  </table>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def _btn(href: str, label: str, bg: str = "#0A0A0B", color: str = "#FFFFFF") -> str:
    """Primary CTA button — action-oriented, high contrast."""
    return f'<div style="text-align:center;margin:28px 0;"><a href="{href}" style="display:inline-block;padding:14px 32px;background-color:{bg};color:{color};text-decoration:none;border-radius:8px;font-size:15px;font-weight:600;line-height:1;letter-spacing:0.01em;">{label}</a></div>'


def _btn_secondary(href: str, label: str) -> str:
    """Secondary / outline-style button."""
    return f'<div style="text-align:center;margin:16px 0;"><a href="{href}" style="display:inline-block;padding:12px 24px;background-color:#F8FAFC;color:#334155;text-decoration:none;border-radius:8px;font-size:14px;font-weight:500;border:1px solid #E2E8F0;line-height:1;">{label}</a></div>'


def _info_box(inner_html: str) -> str:
    """Neutral info card."""
    return f'<div style="background:#F8FAFC;padding:20px;border-radius:10px;border:1px solid #E2E8F0;margin:20px 0;">{inner_html}</div>'


def _alert_box(inner_html: str, border_color: str = "#F59E0B", bg: str = "#FFFBEB") -> str:
    """Alert / warning box."""
    return f'<div style="background:{bg};border-left:4px solid {border_color};padding:16px 20px;margin:20px 0;border-radius:0 8px 8px 0;">{inner_html}</div>'


def _detail_row(label: str, value: str) -> str:
    """Single label:value row for info boxes."""
    return f'<p style="margin:6px 0;color:#475569;font-size:14px;"><strong style="color:#1E293B;">{label}</strong> {value}</p>'


def _section_title(text: str) -> str:
    return f'<h2 style="margin:0 0 12px 0;font-size:22px;font-weight:700;color:#0F172A;line-height:1.3;">{text}</h2>'


def _greeting(name: str) -> str:
    return f'<p style="margin:0 0 16px 0;font-size:16px;color:#1E293B;">Bonjour {name},</p>'


def _paragraph(text: str) -> str:
    return f'<p style="margin:0 0 16px 0;font-size:15px;color:#475569;line-height:1.65;">{text}</p>'


def _small(text: str) -> str:
    return f'<p style="margin:12px 0 0 0;font-size:12px;color:#94A3B8;line-height:1.5;">{text}</p>'


def _fallback_link(url: str) -> str:
    return f'<p style="margin:12px 0 0 0;font-size:12px;color:#94A3B8;word-break:break-all;">Ou copiez ce lien : <a href="{url}" style="color:#3B82F6;">{url}</a></p>'


def _brand_note(text: str) -> str:
    """Subtle brand reinforcement line — grey, small, centered."""
    return f'<p style="margin:24px 0 0 0;font-size:12px;color:#94A3B8;text-align:center;font-style:italic;">{text}</p>'


# ─────────────────────────────────────────────────────────────
# MongoDB for tracking email attempts
# ─────────────────────────────────────────────────────────────

class EmailService:
    @staticmethod
    def _log_email_attempt(email: str, email_type: str, status: str, resend_response: dict = None, error: str = None):
        """Log every email attempt to database for debugging"""
        attempt = {
            "attempt_id": str(uuid.uuid4()),
            "email": email,
            "email_type": email_type,
            "status": status,
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
            logger.info(f"[EMAIL_SERVICE] Resend API call successful for {to_email}")
            logger.info(f"[EMAIL_SERVICE] Resend response: {email}")
            EmailService._log_email_attempt(
                email=to_email, email_type=email_type,
                status="success", resend_response=email
            )
            return {"success": True, "email_id": email.get('id'), "resend_response": email}
        except Exception as e:
            logger.error(f"[EMAIL_SERVICE] Failed to send email to {to_email}: {str(e)}")
            EmailService._log_email_attempt(
                email=to_email, email_type=email_type,
                status="failed", error=str(e)
            )
            return {"success": False, "error": str(e)}

    # ─────────────────────────────────────────────────────────
    # 1. VERIFICATION EMAIL
    # ─────────────────────────────────────────────────────────
    @staticmethod
    async def send_verification_email(to_email: str, verification_token: str, base_url: str):
        logger.info(f"[VERIFICATION_EMAIL] Starting for {to_email}")
        logger.info(f"[VERIFICATION_EMAIL] Token length: {len(verification_token)}")
        logger.info(f"[VERIFICATION_EMAIL] Base URL: {base_url}")

        verification_link = f"{base_url}/verify-email?token={verification_token}"
        subject = "Confirmez votre adresse email — NLYT"

        body = (
            _section_title("Bienvenue sur NLYT")
            + _paragraph("Vous y êtes presque. Confirmez votre adresse email pour activer votre compte et commencer à protéger votre temps.")
            + _btn(verification_link, "Activer mon compte")
            + _fallback_link(verification_link)
            + _small("Ce lien expirera dans 24 heures.")
            + _brand_note("NLYT — Ne perdez plus jamais votre temps.")
        )
        html_content = _base_template(body, accent="info")

        result = await EmailService.send_email(to_email, subject, html_content, email_type="verification")
        logger.info(f"[VERIFICATION_EMAIL] Result for {to_email}: {result}")
        return result

    # ─────────────────────────────────────────────────────────
    # 2. PASSWORD RESET
    # ─────────────────────────────────────────────────────────
    @staticmethod
    async def send_password_reset_email(to_email: str, reset_token: str, base_url: str):
        reset_link = f"{base_url}/reset-password?token={reset_token}"
        subject = "Réinitialisez votre mot de passe — NLYT"

        body = (
            _section_title("Réinitialisation de mot de passe")
            + _paragraph("Vous avez demandé la réinitialisation de votre mot de passe. Cliquez ci-dessous pour en créer un nouveau et retrouver l'accès à votre compte.")
            + _btn(reset_link, "Créer un nouveau mot de passe")
            + _fallback_link(reset_link)
            + _small("Ce lien expirera dans 1 heure. Si vous n'avez pas fait cette demande, ignorez cet email.")
        )
        html_content = _base_template(body, accent="neutral")
        return await EmailService.send_email(to_email, subject, html_content, email_type="password_reset")

    # ─────────────────────────────────────────────────────────
    # 3. INVITATION
    # ─────────────────────────────────────────────────────────
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
        formatted_date = format_email_datetime(appointment_datetime, appointment_timezone)
        location_display = location if location else "Non spécifié"

        # Meeting info
        meeting_section = ""
        if meeting_join_url:
            provider_label = {"zoom": "Zoom", "teams": "Microsoft Teams", "meet": "Google Meet"}.get(
                (meeting_provider or "").lower(), meeting_provider or "Visioconférence"
            )
            meeting_section = _detail_row("Visioconférence :", provider_label)
            location_display = f"En ligne ({provider_label})"

        # Guarantee info
        guarantee_info = ""
        if penalty_amount and penalty_amount > 0:
            guarantee_info = _detail_row("Garantie d'engagement :", f"{penalty_amount} {penalty_currency.upper()}")

        # Deadline info
        deadline_info = ""
        if cancellation_deadline_hours:
            deadline_info = _detail_row("Délai d'annulation :", f"{cancellation_deadline_hours}h avant l'engagement")

        # ICS section
        calendar_section = _btn_secondary(ics_link, "Ajouter au calendrier (ICS)") if ics_link else ""

        # Proof section
        proof_section = ""
        if proof_link:
            proof_section = (
                '<div style="background:#F0F9FF;border:1px solid #BAE6FD;border-radius:8px;padding:20px;margin:20px 0;text-align:center;">'
                '<p style="margin:0 0 8px 0;color:#0369A1;font-weight:600;font-size:14px;">Confirmer ma présence le jour J</p>'
                '<p style="margin:0 0 12px 0;color:#0284C7;font-size:13px;">Ce lien vous permettra de prouver votre présence. La visio s\'ouvrira automatiquement.</p>'
                + _btn(proof_link, "Mon lien de présence NLYT", bg="#0369A1")
                + '</div>'
            )

        subject = f"Vous êtes invité — {appointment_title}"

        details = (
            _detail_row("Date :", formatted_date)
            + _detail_row("Lieu :", location_display)
            + meeting_section
            + guarantee_info
            + deadline_info
        )

        body = (
            _greeting(to_name)
            + _paragraph(f"<strong>{organizer_name}</strong> vous invite à un engagement solidaire.")
            + _info_box(f'<p style="margin:0 0 12px 0;font-size:16px;font-weight:700;color:#0F172A;">{appointment_title}</p>{details}')
            + _alert_box('<p style="margin:0;color:#92400E;font-size:14px;">En acceptant, vous vous engagez à respecter les conditions définies par l\'organisateur. Une garantie peut être requise.</p>')
            + _btn(invitation_link, "Consulter l'invitation")
            + _small("Vous pourrez consulter toutes les conditions avant d'accepter ou de refuser.")
            + calendar_section
            + proof_section
        )
        html_content = _base_template(body, accent="info")
        return await EmailService.send_email(to_email, subject, html_content, email_type="invitation")

    # ─────────────────────────────────────────────────────────
    # 4. ACCEPTANCE CONFIRMATION
    # ─────────────────────────────────────────────────────────
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
        formatted_date = format_email_datetime(appointment_datetime, appointment_timezone)
        is_video = appointment_type == 'video'
        provider_label = {
            'zoom': 'Zoom', 'teams': 'Microsoft Teams', 'meet': 'Google Meet'
        }.get((meeting_provider or '').lower(), meeting_provider or 'Visioconférence')

        if is_video:
            location_display = f"En ligne — {provider_label}"
        else:
            location_display = location if location else "Non spécifié"

        # Timezone note
        tz_note = ""
        if appointment_timezone and appointment_timezone != 'UTC':
            tz_display = appointment_timezone.replace('_', ' ').split('/')[-1]
            tz_note = f'<p style="margin:2px 0 0 0;color:#94A3B8;font-size:11px;">Fuseau horaire : {appointment_timezone} ({tz_display})</p>'

        details = (
            _detail_row("Date :", formatted_date)
            + tz_note
            + _detail_row("Réunion :" if is_video else "Lieu :", location_display)
        )

        # Guarantee reminder
        guarantee_reminder = ""
        if penalty_amount and penalty_amount > 0:
            cancel_note = f" Vous pouvez annuler sans frais jusqu'à {cancellation_deadline_hours}h avant." if cancellation_deadline_hours else ""
            guarantee_reminder = _alert_box(
                f'<p style="margin:0;color:#92400E;font-size:14px;"><strong>Rappel :</strong> Une garantie de {penalty_amount} {penalty_currency.upper()} s\'appliquera en cas d\'absence.{cancel_note}</p>'
            )

        # Access section
        access_section = ""
        if is_video and proof_link:
            access_section = (
                '<div style="background:#F0F9FF;border:2px solid #BAE6FD;border-radius:10px;padding:24px;margin:24px 0;text-align:center;">'
                '<p style="margin:0 0 6px 0;color:#0369A1;font-weight:700;font-size:16px;">Votre lien de réunion</p>'
                f'<p style="margin:0 0 16px 0;color:#0284C7;font-size:13px;line-height:1.5;">Le jour de l\'engagement, cliquez pour confirmer votre présence et ouvrir la visio {provider_label}.</p>'
                + _btn(proof_link, "Confirmer ma présence et rejoindre", bg="#0369A1")
                + '<p style="margin:12px 0 0 0;color:#64748B;font-size:11px;">Ce lien sera actif 30 minutes avant le début. Conservez cet email.</p>'
                + '</div>'
            )
        elif not is_video:
            loc_text = f"à l'adresse : <strong>{location_display}</strong>" if location else ""
            checkin_button = _btn(invitation_link, "Je suis arrivé — confirmer ma présence", bg="#059669") if invitation_link else ""
            access_section = (
                '<div style="background:#F0FDF4;border:2px solid #BBF7D0;border-radius:10px;padding:24px;margin:24px 0;">'
                '<p style="margin:0 0 8px 0;color:#166534;font-weight:700;font-size:15px;">Comment confirmer votre présence</p>'
                f'<p style="margin:0 0 12px 0;color:#15803D;font-size:13px;line-height:1.5;">Le jour de l\'engagement {loc_text}, confirmez votre arrivée via le bouton ci-dessous ou le scan du QR code.</p>'
                + checkin_button
                + '<p style="margin:12px 0 0 0;color:#64748B;font-size:11px;">Le check-in est disponible 30 min avant le début. Conservez cet email.</p>'
                + '</div>'
            )

        # ICS button
        ics_button = _btn_secondary(ics_link, "Ajouter à mon calendrier") if ics_link else ""

        # View link
        view_link = ""
        if invitation_link:
            view_link = f'<p style="text-align:center;margin-top:16px;"><a href="{invitation_link}" style="color:#3B82F6;text-decoration:underline;font-size:13px;">Voir tous les détails de l\'engagement</a></p>'

        subject = f"Votre accès est confirmé — {appointment_title}"

        body = (
            _greeting(to_name)
            + _paragraph(f'Votre participation à l\'engagement de <strong>{organizer_name}</strong> est <strong>confirmée</strong>. Votre temps est maintenant protégé. Voici tout ce qu\'il faut savoir pour le jour J.')
            + _info_box(f'<p style="margin:0 0 12px 0;font-size:16px;font-weight:700;color:#0F172A;">{appointment_title}</p>{details}')
            + access_section
            + guarantee_reminder
            + ics_button
            + view_link
            + '<div style="background:#F8FAFC;border-radius:8px;padding:14px;margin-top:20px;text-align:center;">'
            + '<p style="margin:0;color:#64748B;font-size:12px;">Cet email est votre <strong>confirmation d\'accès définitive</strong>. Conservez-le.</p>'
            + '</div>'
        )
        html_content = _base_template(body, accent="success")
        return await EmailService.send_email(to_email, subject, html_content, email_type="acceptance_confirmation")

    # ─────────────────────────────────────────────────────────
    # 5. CHECK-IN NOTIFICATION
    # ─────────────────────────────────────────────────────────
    @staticmethod
    async def send_checkin_notification_email(
        to_email: str,
        to_name: str,
        checkin_person_name: str,
        checkin_is_organizer: bool,
        appointment_title: str,
        appointment_datetime: str,
        appointment_type: str = 'physical',
        meeting_provider: str = None,
        checkin_time: str = None,
        appointment_link: str = None,
        appointment_timezone: str = 'Europe/Paris',
        evidence_details: dict = None,
    ):
        formatted_date = format_email_datetime(appointment_datetime, appointment_timezone)
        is_video = appointment_type == 'video'
        details = evidence_details or {}

        provider_label = {
            'zoom': 'Zoom', 'teams': 'Microsoft Teams', 'meet': 'Google Meet'
        }.get((meeting_provider or '').lower(), meeting_provider or 'visioconférence')

        role = " (organisateur)" if checkin_is_organizer else ""
        if is_video:
            action_text = f"<strong>{checkin_person_name}</strong>{role} a confirmé sa présence pour la réunion."
        else:
            action_text = f"<strong>{checkin_person_name}</strong>{role} est arrivé à l'engagement."

        # Checkin time
        checkin_display = ""
        if checkin_time:
            try:
                from datetime import datetime as dt
                import pytz
                ct = dt.fromisoformat(checkin_time.replace('Z', '+00:00'))
                local_tz = pytz.timezone(appointment_timezone)
                ct_local = ct.astimezone(local_tz)
                checkin_display = ct_local.strftime("%H:%M")
            except Exception:
                checkin_display = ""

        # Evidence details
        evidence_rows = ""
        if is_video:
            display_name = details.get('video_display_name')
            items = []
            if display_name:
                items.append(_detail_row("Nom de connexion :", display_name))
            if checkin_display:
                items.append(_detail_row("Heure :", checkin_display))
            items.append(_detail_row("Plateforme :", provider_label))
            if items:
                evidence_rows = '<div style="background:#F0F9FF;border:1px solid #BAE6FD;border-radius:8px;padding:16px;margin:16px 0;">' + '<p style="margin:0 0 8px 0;color:#0369A1;font-weight:700;font-size:12px;text-transform:uppercase;letter-spacing:0.5px;">Détails de connexion</p>' + ''.join(items) + '</div>'
        else:
            items = []
            source_label = {'gps': 'GPS', 'qr': 'QR Code', 'manual_checkin': 'Check-in manuel'}.get(details.get('source', ''), details.get('source', ''))
            if source_label:
                items.append(_detail_row("Méthode :", source_label))
            if checkin_display:
                items.append(_detail_row("Heure d'arrivée :", checkin_display))
            addr = details.get('address_label')
            if addr:
                items.append(_detail_row("Localisation :", addr))
            lat = details.get('latitude')
            lon = details.get('longitude')
            if lat is not None and lon is not None:
                maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                items.append(f'<p style="margin:6px 0;color:#475569;font-size:14px;"><strong style="color:#1E293B;">Coordonnées :</strong> <a href="{maps_url}" style="color:#3B82F6;">{lat:.5f}, {lon:.5f}</a></p>')
            dist = details.get('distance_km')
            if dist is not None:
                items.append(_detail_row("Distance au lieu :", f"{dist:.1f} km"))
            if items:
                evidence_rows = '<div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:8px;padding:16px;margin:16px 0;">' + '<p style="margin:0 0 8px 0;color:#166534;font-weight:700;font-size:12px;text-transform:uppercase;letter-spacing:0.5px;">Preuves de présence</p>' + ''.join(items) + '</div>'

        link_section = ""
        if appointment_link:
            link_section = _btn(appointment_link, "Accéder à l'engagement")

        accent = "info" if is_video else "success"
        subject = f"{checkin_person_name} a confirmé sa présence — {appointment_title}"

        body = (
            _greeting(to_name)
            + _alert_box(f'<p style="margin:0;color:#1E293B;font-size:15px;">{action_text}</p>', border_color=ACCENT_COLORS[accent], bg="#F0FDF4" if not is_video else "#F0F9FF")
            + evidence_rows
            + _info_box(f'<p style="margin:0 0 6px 0;color:#0F172A;font-weight:700;">{appointment_title}</p><p style="margin:0;color:#64748B;font-size:13px;">{formatted_date}</p>')
            + link_section
        )
        html_content = _base_template(body, accent=accent)
        return await EmailService.send_email(to_email, subject, html_content, email_type="checkin_notification")

    # ─────────────────────────────────────────────────────────
    # 6. PARTICIPANT CANCELLATION (notif to organizer)
    # ─────────────────────────────────────────────────────────
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
        formatted_date = format_email_datetime(appointment_datetime, appointment_timezone)
        location_display = location if location else "Non spécifié"

        link_button = _btn(appointment_link, "Voir les détails de l'engagement") if appointment_link else ""

        subject = f"Un participant a annulé — {appointment_title}"
        body = (
            _greeting(organizer_name)
            + _alert_box(f'<p style="margin:0;color:#92400E;font-size:14px;"><strong>{participant_name}</strong> ({participant_email}) a annulé sa participation à votre engagement.</p>')
            + _info_box(
                f'<p style="margin:0 0 12px 0;font-size:16px;font-weight:700;color:#0F172A;">{appointment_title}</p>'
                + _detail_row("Date :", formatted_date)
                + _detail_row("Lieu :", location_display)
            )
            + _paragraph("Le participant a annulé dans les délais prévus. Aucune garantie ne sera capturée.")
            + link_button
            + _brand_note("Les engagements pris sur NLYT sont protégés.")
        )
        html_content = _base_template(body, accent="warning")
        return await EmailService.send_email(organizer_email, subject, html_content, email_type="participant_cancellation")

    # ─────────────────────────────────────────────────────────
    # 7. APPOINTMENT CANCELLED BY ORGANIZER
    # ─────────────────────────────────────────────────────────
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
        formatted_date = format_email_datetime(appointment_datetime, appointment_timezone)
        location_display = location if location else "Non spécifié"

        subject = f"Engagement annulé — {appointment_title}"
        body = (
            _greeting(participant_name)
            + _alert_box(
                f'<p style="margin:0;color:#991B1B;font-size:14px;">L\'engagement suivant a été <strong>annulé</strong> par l\'organisateur ({organizer_name}).</p>',
                border_color="#EF4444", bg="#FEF2F2"
            )
            + _info_box(
                f'<p style="margin:0 0 12px 0;font-size:16px;font-weight:700;color:#94A3B8;text-decoration:line-through;">{appointment_title}</p>'
                + _detail_row("Date :", formatted_date)
                + _detail_row("Lieu :", location_display)
            )
            + _paragraph("<strong>Vous n'avez plus besoin de vous présenter.</strong> Si vous avez des questions, contactez directement l'organisateur.")
            + _brand_note("Votre temps reste protégé avec NLYT.")
        )
        html_content = _base_template(body, accent="danger")
        return await EmailService.send_email(participant_email, subject, html_content, email_type="appointment_cancelled")

    # ─────────────────────────────────────────────────────────
    # 8. APPOINTMENT DELETED
    # ─────────────────────────────────────────────────────────
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
        formatted_date = format_email_datetime(appointment_datetime, appointment_timezone)
        location_display = location if location else "Non spécifié"

        subject = f"Engagement supprimé — {appointment_title}"
        body = (
            _greeting(participant_name)
            + _alert_box(
                '<p style="margin:0;color:#475569;font-size:14px;">L\'engagement suivant a été <strong>supprimé</strong> par l\'organisateur.</p>',
                border_color="#64748B", bg="#F1F5F9"
            )
            + _info_box(
                f'<p style="margin:0 0 12px 0;font-size:16px;font-weight:700;color:#94A3B8;text-decoration:line-through;">{appointment_title}</p>'
                + _detail_row("Date :", formatted_date)
                + _detail_row("Lieu :", location_display)
            )
            + _paragraph("<strong>Cet engagement n'aura pas lieu.</strong>")
        )
        html_content = _base_template(body, accent="neutral")
        return await EmailService.send_email(participant_email, subject, html_content, email_type="appointment_deleted")

    # ─────────────────────────────────────────────────────────
    # 9. GUARANTEE REVALIDATION
    # ─────────────────────────────────────────────────────────
    @staticmethod
    async def send_guarantee_revalidation_email(
        participant_email: str,
        participant_name: str,
        appointment_title: str,
        revalidation_reason: str,
        invitation_link: str
    ):
        reason_labels = {
            "city_change": "Le lieu a changé de ville",
            "date_shift": "La date a été décalée de plus de 24 heures",
            "type_change": "Le type d'engagement a changé"
        }

        reason_parts = revalidation_reason.split(", ") if revalidation_reason else []
        reason_html_items = ""
        for r in reason_parts:
            for label_key, label_val in reason_labels.items():
                if label_key in r:
                    detail = r.split(":", 1)[1] if ":" in r else ""
                    reason_html_items += f'<li style="margin:6px 0;color:#92400E;font-size:14px;">{label_val}{" (" + detail + ")" if detail else ""}</li>'
                    break

        if not reason_html_items:
            reason_html_items = f'<li style="margin:6px 0;color:#92400E;font-size:14px;">{revalidation_reason}</li>'

        subject = f"Action requise — Reconfirmez votre garantie pour \"{appointment_title}\""
        body = (
            _greeting(participant_name)
            + _paragraph(f'Les conditions de l\'engagement <strong>"{appointment_title}"</strong> ont changé de manière significative :')
            + _alert_box(f'<ul style="margin:0;padding-left:20px;">{reason_html_items}</ul>')
            + _paragraph("Votre garantie actuelle nécessite une reconfirmation pour rester valide.")
            + _btn(invitation_link, "Reconfirmer ma participation", bg="#D97706")
            + _small("Tant que vous n'avez pas reconfirmé, votre garantie est considérée comme partiellement invalide.")
        )
        html_content = _base_template(body, accent="warning")
        return await EmailService.send_email(participant_email, subject, html_content, email_type="guarantee_revalidation")
