"""
Financial Email Notifications — NLYT

Non-blocking email notifications for financial events.
Idempotent via sent_emails collection (key: email_type + reference_id + user_id).

Events:
  1. capture_no_show      → sent to no-show user after guarantee capture
  2. distribution_created → sent to each beneficiary after distribution creation
  3. distribution_available → sent to each beneficiary after hold expiry
  4. payout_completed     → sent to user after successful payout
  5. payout_failed        → sent to user after failed payout
"""
import os
import logging
import asyncio
import threading
from datetime import datetime, timezone
from database import db

logger = logging.getLogger(__name__)

FRONTEND_URL = os.environ.get('FRONTEND_URL', '')
WALLET_URL = f"{FRONTEND_URL}/settings/wallet"


# ─── Idempotence ─────────────────────────────────────────────


def _already_sent(email_type: str, reference_id: str, user_id: str) -> bool:
    """Check if this exact email was already sent."""
    return db.sent_emails.find_one({
        "email_type": email_type,
        "reference_id": reference_id,
        "user_id": user_id,
    }) is not None


def _mark_sent(email_type: str, reference_id: str, user_id: str, to_email: str):
    """Record that this email was sent."""
    db.sent_emails.insert_one({
        "email_type": email_type,
        "reference_id": reference_id,
        "user_id": user_id,
        "to_email": to_email,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    })


# ─── Non-blocking send helper ───────────────────────────────


def _send_async(to_email: str, subject: str, html: str, email_type: str,
                reference_id: str, user_id: str):
    """
    Fire-and-forget email send. Never blocks the caller.
    Uses a thread to run the async EmailService.send_email.
    """
    if _already_sent(email_type, reference_id, user_id):
        logger.info(f"[FIN_EMAIL] Skipped (already sent): {email_type} ref={reference_id} user={user_id}")
        return

    def _run():
        try:
            from services.email_service import EmailService
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                EmailService.send_email(to_email, subject, html, email_type)
            )
            loop.close()
            if result.get("success"):
                _mark_sent(email_type, reference_id, user_id, to_email)
                logger.info(f"[FIN_EMAIL] Sent: {email_type} to {to_email} ref={reference_id}")
            else:
                logger.warning(f"[FIN_EMAIL] Failed: {email_type} to {to_email}: {result}")
        except Exception as e:
            logger.error(f"[FIN_EMAIL] Error sending {email_type} to {to_email}: {e}")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


# ─── User lookup ─────────────────────────────────────────────


def _get_user(user_id: str) -> dict | None:
    return db.users.find_one({"user_id": user_id}, {"_id": 0, "email": 1, "first_name": 1, "last_name": 1})


def _fmt_amount(cents: int, currency: str = "eur") -> str:
    return f"{cents / 100:,.2f} €".replace(",", " ").replace(".", ",")


def _fmt_date(iso: str) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso)
        months = ["janvier", "février", "mars", "avril", "mai", "juin",
                   "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        return f"{dt.day} {months[dt.month - 1]} {dt.year}"
    except Exception:
        return iso[:10]


# ─── Email Template Shell ────────────────────────────────────


def _wrap_html(content: str) -> str:
    return f"""
<div style="max-width:600px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1e293b;">
  <div style="background:#1e293b;padding:24px;text-align:center;">
    <span style="color:white;font-size:20px;font-weight:700;letter-spacing:1px;">NLYT</span>
  </div>
  <div style="padding:32px 24px;line-height:1.6;">
    {content}
  </div>
  <div style="padding:16px 24px;background:#f8fafc;text-align:center;font-size:11px;color:#94a3b8;">
    NLYT — Garantie de présence · Cet email est envoyé automatiquement
  </div>
</div>
"""


def _button(url: str, label: str) -> str:
    return f"""
<div style="text-align:center;margin:24px 0;">
  <a href="{url}" style="display:inline-block;background:#1e293b;color:white;padding:12px 28px;border-radius:6px;text-decoration:none;font-size:14px;font-weight:600;">{label}</a>
</div>
"""


def _ref_line(ref_id: str) -> str:
    return f'<p style="font-size:11px;color:#94a3b8;margin-top:24px;">Réf. : {ref_id}</p>'


# ─── 1. Garantie capturée (no-show) ─────────────────────────


def send_capture_email(
    user_id: str,
    appointment_title: str,
    appointment_date: str,
    capture_amount_cents: int,
    distribution_id: str,
    beneficiaries: list[dict],
    hold_expires_at: str,
):
    """Email sent to the no-show user when their guarantee is captured."""
    user = _get_user(user_id)
    if not user or not user.get("email"):
        return

    first_name = user.get("first_name", "")
    amount = _fmt_amount(capture_amount_cents)
    date = _fmt_date(appointment_date)
    hold_date = _fmt_date(hold_expires_at)

    # Build breakdown
    breakdown_lines = ""
    for b in beneficiaries:
        role_label = {
            "platform": "Commission NLYT",
            "charity": "Association",
            "organizer": "Dédommagement organisateur",
            "participant": "Compensation participant",
        }.get(b.get("role"), b.get("role", ""))
        breakdown_lines += f"<li>{role_label} : {_fmt_amount(b['amount_cents'])}</li>"

    html = _wrap_html(f"""
<p>Bonjour{' ' + first_name if first_name else ''},</p>
<p>Votre présence au rendez-vous <strong>« {appointment_title} »</strong> du {date} n'a pas pu être confirmée.</p>
<p>Conformément aux conditions acceptées lors de votre inscription, votre garantie de <strong>{amount}</strong> a été capturée.</p>
<p style="font-size:14px;font-weight:600;margin-top:16px;">Répartition :</p>
<ul style="padding-left:20px;font-size:14px;">{breakdown_lines}</ul>
<p>Une <strong>période de vérification de 15 jours</strong> est en cours. Vous avez jusqu'au <strong>{hold_date}</strong> pour signaler toute erreur depuis votre wallet.</p>
{_button(WALLET_URL, 'Accéder à mon wallet')}
{_ref_line(distribution_id)}
""")

    _send_async(user["email"], f"Votre garantie a été capturée — {appointment_title}",
                html, "capture_no_show", distribution_id, user_id)


# ─── 2. Distribution créditée (bénéficiaires) ───────────────


def send_distribution_created_email(
    user_id: str,
    role: str,
    amount_cents: int,
    appointment_title: str,
    appointment_date: str,
    distribution_id: str,
    hold_expires_at: str,
):
    """Email sent to each beneficiary when a distribution is created."""
    user = _get_user(user_id)
    if not user or not user.get("email"):
        return

    first_name = user.get("first_name", "")
    amount = _fmt_amount(amount_cents)
    date = _fmt_date(appointment_date)
    hold_date = _fmt_date(hold_expires_at)

    role_context = {
        "organizer": "en tant qu'organisateur du rendez-vous",
        "participant": "en tant que participant présent au rendez-vous",
    }.get(role, "suite au rendez-vous")

    html = _wrap_html(f"""
<p>Bonjour{' ' + first_name if first_name else ''},</p>
<p>Un <strong>crédit en attente de {amount}</strong> a été enregistré dans votre wallet NLYT, {role_context} <strong>« {appointment_title} »</strong> du {date}.</p>
<p>Ce montant est actuellement <strong>en période de vérification</strong>. Il sera disponible dans votre wallet à partir du <strong>{hold_date}</strong>, sauf contestation en cours.</p>
<p style="font-size:13px;color:#64748b;">Aucune action n'est requise de votre part pour le moment.</p>
{_button(WALLET_URL, 'Voir mon wallet')}
{_ref_line(distribution_id)}
""")

    _send_async(user["email"], f"Crédit en attente enregistré — {appointment_title}",
                html, "distribution_created", distribution_id, user_id)


# ─── 3. Fonds disponibles (après hold) ──────────────────────


def send_distribution_available_email(
    user_id: str,
    amount_cents: int,
    appointment_title: str,
    distribution_id: str,
):
    """Email sent to each beneficiary when funds move from pending to available."""
    user = _get_user(user_id)
    if not user or not user.get("email"):
        return

    first_name = user.get("first_name", "")
    amount = _fmt_amount(amount_cents)

    html = _wrap_html(f"""
<p>Bonjour{' ' + first_name if first_name else ''},</p>
<p>Le crédit de <strong>{amount}</strong> lié au rendez-vous <strong>« {appointment_title} »</strong> est désormais <strong>disponible</strong> dans votre wallet NLYT.</p>
<p>Vous pouvez retirer ce montant vers votre compte bancaire depuis votre wallet.</p>
{_button(WALLET_URL, 'Retirer mes fonds')}
{_ref_line(distribution_id)}
""")

    _send_async(user["email"], f"Vos fonds sont disponibles — {amount}",
                html, "distribution_available", distribution_id, user_id)


# ─── 4. Payout effectué ─────────────────────────────────────


def send_payout_completed_email(
    user_id: str,
    amount_cents: int,
    payout_id: str,
    stripe_transfer_id: str,
):
    """Email sent when a payout is successfully completed."""
    user = _get_user(user_id)
    if not user or not user.get("email"):
        return

    first_name = user.get("first_name", "")
    amount = _fmt_amount(amount_cents)

    html = _wrap_html(f"""
<p>Bonjour{' ' + first_name if first_name else ''},</p>
<p>Votre retrait de <strong>{amount}</strong> a été effectué avec succès vers votre compte Stripe Connect.</p>
<p>Les fonds seront disponibles sur votre compte bancaire selon les délais habituels de votre établissement.</p>
<p style="font-size:13px;color:#64748b;">Référence transfert : {stripe_transfer_id}</p>
{_button(WALLET_URL, 'Voir mes retraits')}
{_ref_line(payout_id)}
""")

    _send_async(user["email"], f"Retrait effectué — {amount}",
                html, "payout_completed", payout_id, user_id)


# ─── 5. Payout échoué ───────────────────────────────────────


def send_payout_failed_email(
    user_id: str,
    amount_cents: int,
    payout_id: str,
    failure_reason: str,
):
    """Email sent when a payout fails (funds re-credited to wallet)."""
    user = _get_user(user_id)
    if not user or not user.get("email"):
        return

    first_name = user.get("first_name", "")
    amount = _fmt_amount(amount_cents)

    html = _wrap_html(f"""
<p>Bonjour{' ' + first_name if first_name else ''},</p>
<p>Le retrait de <strong>{amount}</strong> depuis votre wallet NLYT n'a pas pu aboutir.</p>
<p><strong>Les fonds ont été automatiquement re-crédités</strong> sur votre wallet. Aucune perte.</p>
<p style="font-size:13px;color:#64748b;">Motif : {failure_reason or 'Erreur technique'}</p>
<p>Nous vous invitons à vérifier votre compte Stripe Connect et à réessayer.</p>
{_button(WALLET_URL, 'Vérifier mon compte')}
{_ref_line(payout_id)}
""")

    _send_async(user["email"], f"Échec du retrait — {amount}",
                html, "payout_failed", payout_id, user_id)
