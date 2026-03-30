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
    hold_expires_at: str | None,
    immediate_release: bool = False,
    release_reason: str = "hold",
):
    """Email sent to each beneficiary when a distribution is created."""
    user = _get_user(user_id)
    if not user or not user.get("email"):
        return

    first_name = user.get("first_name", "")
    amount = _fmt_amount(amount_cents)
    date = _fmt_date(appointment_date)

    role_context = {
        "organizer": "en tant qu'organisateur du rendez-vous",
        "participant": "en tant que participant présent au rendez-vous",
    }.get(role, "suite au rendez-vous")

    if immediate_release:
        reason_label = {
            "consensus": "suite à l'accord des participants",
            "admin_arbitration": "suite à l'arbitrage de la plateforme",
        }.get(release_reason, "")
        html = _wrap_html(f"""
<p>Bonjour{' ' + first_name if first_name else ''},</p>
<p>Un <strong>crédit de {amount}</strong> a été enregistré dans votre wallet NLYT, {role_context} <strong>« {appointment_title} »</strong> du {date}.</p>
<p>Ce montant est <strong>immédiatement disponible</strong> pour retrait{' ' + reason_label if reason_label else ''}.</p>
{_button(WALLET_URL, 'Retirer mes fonds')}
{_ref_line(distribution_id)}
""")
        subject = f"Fonds disponibles — {appointment_title}"
    else:
        hold_date = _fmt_date(hold_expires_at) if hold_expires_at else "N/A"
        html = _wrap_html(f"""
<p>Bonjour{' ' + first_name if first_name else ''},</p>
<p>Un <strong>crédit en attente de {amount}</strong> a été enregistré dans votre wallet NLYT, {role_context} <strong>« {appointment_title} »</strong> du {date}.</p>
<p>Ce montant est actuellement <strong>en période de vérification</strong>. Il sera disponible dans votre wallet à partir du <strong>{hold_date}</strong>, sauf contestation en cours.</p>
<p style="font-size:13px;color:#64748b;">Aucune action n'est requise de votre part pour le moment.</p>
{_button(WALLET_URL, 'Voir mon wallet')}
{_ref_line(distribution_id)}
""")
        subject = f"Crédit en attente enregistré — {appointment_title}"

    _send_async(user["email"], subject, html, "distribution_created", distribution_id, user_id)


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


# ─── 6. Post-engagement notification emails ─────────────────────────


def send_post_engagement_emails(appointment_id: str, appointment: dict):
    """
    Send post-engagement notification emails to all evaluated participants.
    Informs each participant of the outcome (present, compensated, charity).
    """
    from datetime import datetime as dt_cls, timezone as tz_cls

    records = list(db.attendance_records.find(
        {"appointment_id": appointment_id},
        {"_id": 0}
    ))
    if not records:
        return

    participants = list(db.participants.find(
        {"appointment_id": appointment_id},
        {"_id": 0}
    ))
    p_map = {p["participant_id"]: p for p in participants}

    any_no_show = any(r.get("outcome") == "no_show" for r in records)
    if not any_no_show and not records:
        return

    distributions = list(db.distributions.find(
        {"appointment_id": appointment_id},
        {"_id": 0}
    ))

    compensation_map = {}
    charity_total = 0
    charity_currency = "eur"
    charity_assoc_name = None
    for dist in distributions:
        for b in dist.get("beneficiaries", []):
            if b.get("role") == "compensation" and b.get("user_id"):
                compensation_map[b["user_id"]] = compensation_map.get(b["user_id"], 0) + b.get("amount_cents", 0)
            if b.get("role") == "charity":
                charity_total += b.get("amount_cents", 0)
                charity_currency = dist.get("capture_currency", "eur")
                assoc_id = b.get("user_id")
                if assoc_id and not charity_assoc_name:
                    assoc = db.charity_associations.find_one({"association_id": assoc_id}, {"_id": 0, "name": 1})
                    charity_assoc_name = assoc.get("name") if assoc else None

    title = appointment.get("title", "")

    for record in records:
        outcome = record.get("outcome")
        if outcome not in ("on_time", "late", "no_show"):
            continue

        p = p_map.get(record.get("participant_id"))
        if not p:
            continue
        user_id = p.get("user_id")
        if not user_id:
            continue
        user = _get_user(user_id)
        if not user or not user.get("email"):
            continue

        first_name = user.get("first_name", "")

        if outcome in ("on_time", "late"):
            comp_amount = compensation_map.get(user_id, 0)
            if comp_amount > 0:
                amount_str = _fmt_amount(comp_amount)
                headline = f"Vous avez \u00e9t\u00e9 indemnis\u00e9 de {amount_str}."
                subtitle = "Parce que votre temps compte."
                subject = f"Vous avez \u00e9t\u00e9 indemnis\u00e9 de {amount_str} \u2014 {title}"
            else:
                headline = "Engagement respect\u00e9."
                subtitle = "Tout le monde a respect\u00e9 son engagement."
                subject = f"Engagement respect\u00e9 \u2014 {title}"
        else:
            if charity_total > 0:
                c_amount_str = _fmt_amount(charity_total, charity_currency)
                headline = "Vous n\u2019avez pas perdu votre temps. Vous avez aid\u00e9 une association."
                if charity_assoc_name:
                    subtitle = f"{c_amount_str} revers\u00e9s \u00e0 {charity_assoc_name}."
                else:
                    subtitle = f"{c_amount_str} revers\u00e9s \u00e0 une association."
                subject = f"Vous n\u2019avez pas perdu votre temps \u2014 {title}"
            else:
                continue

        from services.email_service import _base_template, _btn

        create_url = f"{FRONTEND_URL}/dashboard"
        primary_cta = _btn(create_url, "Cr\u00e9er un engagement")

        body = f"""
<p style="margin:0 0 6px;font-size:14px;color:#64748B;font-weight:500;">Bonjour{(' ' + first_name) if first_name else ''},</p>
<p style="margin:0 0 24px;font-size:22px;font-weight:800;color:#0F172A;line-height:1.25;">{headline}<br/>
<span style="font-size:15px;font-weight:500;color:#64748B;">{subtitle}</span></p>
<div style="border-top:1px solid #E2E8F0;padding-top:24px;text-align:center;">
  <p style="margin:0 0 16px;font-size:15px;font-weight:600;color:#0F172A;">Votre temps a de la valeur.<br/>Prot\u00e9gez-le.</p>
  {primary_cta}
</div>"""

        html = _base_template(body, accent="info")

        _send_async(user["email"], subject, html, "post_engagement_notification", appointment_id, user_id)


# ─── 7. Dispute resolution emails ────────────────────────────


# Outcome labels (French, non-accusatory, user-facing)
_OUTCOME_LABELS = {
    "on_time": "Présent(e) à l'heure",
    "late": "Présent(e) avec retard toléré",
    "late_penalized": "Retard au-delà de la tolérance",
    "no_show": "Absence constatée",
    "waived": "Aucune pénalité applicable",
}

# Source labels — NEVER expose individual human actors as decision makers
_SOURCE_LABELS = {
    "system": "Évaluation automatique",
    "organizer": "Résolution validée",
    "declarative_consensus": "Consensus déclaratif",
    "platform_arbitration": "Résolution validée",
    "platform": "Résolution validée",
    "system_timeout": "Résolution automatique (délai expiré)",
}


def _fmt_penalty(amount, currency="eur"):
    """Format a penalty amount (in euros, not cents) for display."""
    if not amount:
        return "—"
    currency_symbol = {"eur": "€", "usd": "$", "gbp": "£"}.get(currency.lower(), currency.upper())
    formatted = f"{amount:,.2f}".replace(",", "\u00a0").replace(".", ",")
    return f"{formatted} {currency_symbol}"


def _build_target_financial_html(guarantee_status, penalty_amount, penalty_currency):
    """Build financial impact HTML for the target participant."""
    amount_str = _fmt_penalty(penalty_amount, penalty_currency)
    if guarantee_status == "captured":
        return (
            '<div style="background:#FEF2F2;border-left:4px solid #EF4444;padding:16px 20px;margin:20px 0;border-radius:0 8px 8px 0;">'
            '<p style="margin:0 0 6px;font-weight:600;color:#991B1B;font-size:14px;">Impact financier</p>'
            f'<p style="margin:0;color:#7F1D1D;font-size:14px;">Votre garantie de <strong>{amount_str}</strong> a été appliquée en tant que pénalité. Ce montant sera redistribué aux participants présents sous forme de dédommagement.</p>'
            '</div>'
        )
    elif guarantee_status == "released":
        return (
            '<div style="background:#F0FDF4;border-left:4px solid #10B981;padding:16px 20px;margin:20px 0;border-radius:0 8px 8px 0;">'
            '<p style="margin:0 0 6px;font-weight:600;color:#166534;font-size:14px;">Impact financier</p>'
            f'<p style="margin:0;color:#15803D;font-size:14px;">Votre garantie de <strong>{amount_str}</strong> a été libérée. Aucune pénalité ne vous est appliquée.</p>'
            '</div>'
        )
    else:
        return (
            '<div style="background:#F8FAFC;border-left:4px solid #94A3B8;padding:16px 20px;margin:20px 0;border-radius:0 8px 8px 0;">'
            '<p style="margin:0 0 6px;font-weight:600;color:#1E293B;font-size:14px;">Impact financier</p>'
            '<p style="margin:0;color:#475569;font-size:14px;">Cette résolution n\'a aucun impact financier sur votre compte.</p>'
            '</div>'
        )


def _build_organizer_financial_text(guarantee_status, penalty_amount, penalty_currency, target_name):
    """Build financial summary text for the organizer."""
    amount_str = _fmt_penalty(penalty_amount, penalty_currency)
    if guarantee_status == "captured":
        return f"La garantie de {target_name} ({amount_str}) a été capturée et redistribuée."
    elif guarantee_status == "released":
        return f"La garantie de {target_name} ({amount_str}) a été libérée."
    return "Aucun impact financier."


def send_dispute_resolution_emails(dispute_id: str):
    """
    Send notification emails when a dispute is resolved.

    Recipients:
      A. Target participant (always)
      B. Organizer (always, unless same user as target)
      C. Beneficiaries who lost a distribution (only if cancelled)

    Idempotent via sent_emails (dispute_resolved_{role} + dispute_id + user_id).
    Non-blocking via _send_async threads.
    """
    from services.email_service import (
        _base_template, _btn, _info_box, _alert_box,
        _detail_row, _greeting, _paragraph,
        format_email_datetime, SITE_URL,
    )

    dispute = db.declarative_disputes.find_one({"dispute_id": dispute_id}, {"_id": 0})
    if not dispute or dispute.get("status") != "resolved":
        logger.warning(f"[DISPUTE_EMAIL] Skipped: dispute {dispute_id} not resolved")
        return

    appointment_id = dispute["appointment_id"]
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        logger.warning(f"[DISPUTE_EMAIL] Skipped: appointment {appointment_id} not found")
        return

    target_pid = dispute["target_participant_id"]
    target_participant = db.participants.find_one({"participant_id": target_pid}, {"_id": 0})
    target_user_id = target_participant.get("user_id", "") if target_participant else ""

    record = db.attendance_records.find_one(
        {"appointment_id": appointment_id, "participant_id": target_pid},
        {"_id": 0}
    )

    resolution = dispute.get("resolution", {})
    final_outcome = resolution.get("final_outcome", record.get("outcome", "") if record else "")
    resolved_by = resolution.get("resolved_by", "platform")

    guarantee = db.payment_guarantees.find_one(
        {"participant_id": target_pid, "appointment_id": appointment_id},
        {"_id": 0}
    )
    guarantee_status = guarantee.get("status") if guarantee else None

    distribution = db.distributions.find_one(
        {"appointment_id": appointment_id, "no_show_participant_id": target_pid},
        {"_id": 0}
    )
    distribution_status = distribution.get("status") if distribution else None

    # Shared context
    title = appointment.get("title", "Rendez-vous")
    tz = appointment.get("appointment_timezone", "Europe/Paris")
    date_display = format_email_datetime(appointment.get("start_datetime", ""), tz)
    outcome_label = _OUTCOME_LABELS.get(final_outcome, final_outcome or "—")
    source_label = _SOURCE_LABELS.get(resolved_by, "Résolution validée")
    penalty_amount = (guarantee.get("penalty_amount") if guarantee else None) or appointment.get("penalty_amount", 0)
    penalty_currency = appointment.get("penalty_currency", "eur")
    organizer_user_id = appointment.get("organizer_id", "")
    has_financial_impact = guarantee_status in ("captured", "released")

    appointment_url = f"{SITE_URL}/appointments/{appointment_id}"
    wallet_url = f"{SITE_URL}/wallet"

    # ─── A. Target participant ───
    if target_user_id:
        target_user = _get_user(target_user_id)
        if target_user and target_user.get("email"):
            cta_url = wallet_url if has_financial_impact else appointment_url
            cta_label = "Voir mon wallet" if has_financial_impact else "Voir le rendez-vous"

            body = (
                _greeting(target_user.get("first_name", ""))
                + _paragraph(
                    f"Le litige concernant votre présence au rendez-vous "
                    f"<strong>{title}</strong> du <strong>{date_display}</strong> a été résolu."
                )
                + _info_box(
                    _detail_row("Statut de présence :", f"<strong>{outcome_label}</strong>")
                    + _detail_row("Base de décision :", source_label)
                )
                + _build_target_financial_html(guarantee_status, penalty_amount, penalty_currency)
                + _btn(cta_url, cta_label)
            )
            _send_async(
                target_user["email"],
                f"Litige résolu — {title}",
                _base_template(body, accent="neutral"),
                "dispute_resolved_target", dispute_id, target_user_id,
            )

    # ─── B. Organizer ───
    if organizer_user_id and organizer_user_id != target_user_id:
        org_user = _get_user(organizer_user_id)
        if org_user and org_user.get("email"):
            target_name = "Participant"
            if target_participant:
                target_name = " ".join(filter(None, [
                    target_participant.get("first_name"),
                    target_participant.get("last_name"),
                ])) or target_participant.get("email", "Participant")

            org_fin_text = _build_organizer_financial_text(
                guarantee_status, penalty_amount, penalty_currency, target_name
            )

            body = (
                _greeting(org_user.get("first_name", ""))
                + _paragraph(
                    f"Un litige a été résolu pour votre rendez-vous "
                    f"<strong>{title}</strong> du <strong>{date_display}</strong>."
                )
                + _info_box(
                    _detail_row("Participant concerné :", f"<strong>{target_name}</strong>")
                    + _detail_row("Décision finale :", f"<strong>{outcome_label}</strong>")
                    + _detail_row("Base de décision :", source_label)
                )
                + _paragraph(org_fin_text)
                + _btn(appointment_url, "Voir le rendez-vous")
            )
            _send_async(
                org_user["email"],
                f"Litige résolu — {title}",
                _base_template(body, accent="neutral"),
                "dispute_resolved_organizer", dispute_id, organizer_user_id,
            )

    # ─── C. Beneficiaries: dédommagement annulé ───
    if distribution and distribution_status == "cancelled":
        for beneficiary in distribution.get("beneficiaries", []):
            b_role = beneficiary.get("role", "")
            if b_role not in ("organizer", "participant"):
                continue
            b_user_id = beneficiary.get("user_id", "")
            if not b_user_id or b_user_id == target_user_id:
                continue

            b_user = _get_user(b_user_id)
            if not b_user or not b_user.get("email"):
                continue

            b_amount = _fmt_amount(beneficiary.get("amount_cents", 0))

            body = (
                _greeting(b_user.get("first_name", ""))
                + _paragraph(
                    f"Suite à la résolution d'un litige pour le rendez-vous "
                    f"<strong>{title}</strong> du <strong>{date_display}</strong>, "
                    f"votre dédommagement a été mis à jour."
                )
                + _alert_box(
                    f'<p style="margin:0;color:#92400E;font-size:14px;">'
                    f'Le dédommagement de <strong>{b_amount}</strong> précédemment attribué '
                    f'a été annulé suite à la résolution du litige.</p>'
                )
                + _btn(wallet_url, "Voir mon wallet")
            )
            _send_async(
                b_user["email"],
                f"Mise à jour de votre dédommagement — {title}",
                _base_template(body, accent="warning"),
                "dispute_resolved_beneficiary", dispute_id, b_user_id,
            )

    logger.info(f"[DISPUTE_EMAIL] Emails queued for dispute {dispute_id}")
