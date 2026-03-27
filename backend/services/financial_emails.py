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


# ─── 6. Post-engagement viral emails ─────────────────────────


# Card accent configs matching the frontend ResultCard component
_CARD_ACCENTS = {
    "engagement_respected": {"color": "#10B981", "bg": "#F0FDF4", "border": "#BBF7D0", "icon": "&#10004;", "icon_color": "#166534"},
    "compensation_received": {"color": "#3B82F6", "bg": "#EFF6FF", "border": "#BFDBFE", "icon": "&#9670;", "icon_color": "#1D4ED8"},
    "charity_donation": {"color": "#F59E0B", "bg": "#FFFBEB", "border": "#FDE68A", "icon": "&#9829;", "icon_color": "#B45309"},
}


def _email_card_html(card_type: str, headline: str, subtitle: str, title: str, date: str) -> str:
    """Render a result card as inline HTML for email embedding."""
    acc = _CARD_ACCENTS.get(card_type, _CARD_ACCENTS["engagement_respected"])
    return f"""
<div style="max-width:380px;margin:0 auto 24px;border-radius:14px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <div style="background:#0A0A0B;padding:14px 20px;display:flex;align-items:center;">
    <span style="font-size:14px;font-weight:700;letter-spacing:0.3em;color:#FFFFFF;">N<span style="color:rgba(255,255,255,0.5);">&middot;</span>L<span style="color:rgba(255,255,255,0.5);">&middot;</span>Y<span style="color:rgba(255,255,255,0.5);">&middot;</span>T</span>
  </div>
  <div style="height:4px;background:{acc['color']};"></div>
  <div style="padding:24px 22px;background:#FFFFFF;">
    <div style="width:44px;height:44px;border-radius:50%;background:{acc['bg']};border:2px solid {acc['border']};text-align:center;line-height:40px;margin-bottom:14px;">
      <span style="font-size:20px;color:{acc['icon_color']};font-weight:700;">{acc['icon']}</span>
    </div>
    <p style="margin:0 0 4px;font-size:22px;font-weight:800;color:#0F172A;line-height:1.2;">{headline}</p>
    <p style="margin:0 0 16px;font-size:14px;color:#64748B;line-height:1.5;">{subtitle}</p>
    <div style="background:#F8FAFC;border-radius:8px;padding:10px 14px;border-left:3px solid {acc['color']};">
      <p style="margin:0;font-size:13px;font-weight:600;color:#0F172A;">{title}</p>
      <p style="margin:3px 0 0;font-size:11px;color:#94A3B8;">{date}</p>
    </div>
    <div style="margin-top:16px;padding-top:14px;border-top:1px solid #E2E8F0;text-align:center;">
      <p style="margin:0;font-size:12px;font-weight:600;color:#475569;font-style:italic;">Le temps ne se perd plus.</p>
    </div>
  </div>
</div>"""


def send_post_engagement_emails(appointment_id: str, appointment: dict):
    """
    Send viral post-engagement emails to all evaluated participants.
    Auto-creates result cards and embeds them in the email.
    Triggered after evaluate_appointment().
    """
    import uuid as uuid_mod
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

    # Check for no-shows to determine if compensation/charity cards apply
    any_no_show = any(r.get("outcome") == "no_show" for r in records)
    if not any_no_show and not records:
        return

    # Check distributions for amounts
    distributions = list(db.distributions.find(
        {"appointment_id": appointment_id},
        {"_id": 0}
    ))

    # Build per-user compensation map
    compensation_map = {}  # user_id → amount_cents
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
    date_str = _fmt_date(appointment.get("start_datetime", ""))

    for record in records:
        outcome = record.get("outcome")
        if outcome not in ("on_time", "late", "no_show"):
            continue  # skip waived/manual_review

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

        # Determine card type & email content based on outcome
        if outcome in ("on_time", "late"):
            # Check if this user received compensation
            comp_amount = compensation_map.get(user_id, 0)
            if comp_amount > 0:
                card_type = "compensation_received"
                amount_str = _fmt_amount(comp_amount)
                headline = f"Vous avez r\u00e9cup\u00e9r\u00e9 {amount_str}."
                subtitle = "Parce que votre temps compte."
                subject = f"Vous avez r\u00e9cup\u00e9r\u00e9 {amount_str} \u2014 {title}"
            else:
                card_type = "engagement_respected"
                headline = "Engagement respect\u00e9."
                subtitle = "Tout le monde a respect\u00e9 son engagement."
                subject = f"Engagement respect\u00e9 \u2014 {title}"
        else:
            # no_show — send charity card if charity exists, else skip viral email
            if charity_total > 0:
                card_type = "charity_donation"
                c_amount_str = _fmt_amount(charity_total, charity_currency)
                headline = "Vous n\u2019avez pas perdu votre temps. Vous avez aid\u00e9 une association."
                if charity_assoc_name:
                    subtitle = f"{c_amount_str} revers\u00e9s \u00e0 {charity_assoc_name}."
                else:
                    subtitle = f"{c_amount_str} revers\u00e9s \u00e0 une association."
                subject = f"Vous n\u2019avez pas perdu votre temps \u2014 {title}"
            else:
                continue  # no viral email for plain no-show without charity

        # Auto-create result card (idempotent)
        existing_card = db.result_cards.find_one({
            "user_id": user_id,
            "appointment_id": appointment_id,
            "card_type": card_type,
        }, {"_id": 0})

        if existing_card:
            card_id = existing_card["card_id"]
        else:
            card_id = str(uuid_mod.uuid4())
            card_doc = {
                "card_id": card_id,
                "card_type": card_type,
                "user_id": user_id,
                "user_name": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
                "appointment_id": appointment_id,
                "appointment_title": title,
                "appointment_date": appointment.get("start_datetime", ""),
                "appointment_timezone": appointment.get("appointment_timezone", "Europe/Paris"),
                "amount_cents": comp_amount if card_type == "compensation_received" else (charity_total if card_type == "charity_donation" else 0),
                "currency": (charity_currency if card_type == "charity_donation" else appointment.get("penalty_currency", "eur")).upper(),
                "association_name": charity_assoc_name if card_type == "charity_donation" else None,
                "view_count": 0,
                "created_at": dt_cls.now(tz_cls.utc).isoformat(),
            }
            db.result_cards.insert_one(card_doc)

        card_public_url = f"{FRONTEND_URL}/card/{card_id}"
        create_url = f"{FRONTEND_URL}/dashboard"

        # Build email HTML using _base_template from email_service
        from services.email_service import _base_template, _btn

        card_html = _email_card_html(card_type, headline, subtitle, title, date_str)

        share_btn = f"""
<div style="text-align:center;margin:0 0 28px;">
  <a href="{card_public_url}" style="display:inline-block;border:1px solid #CBD5E1;color:#334155;padding:10px 22px;border-radius:8px;text-decoration:none;font-size:13px;font-weight:600;">Partager mon r\u00e9sultat</a>
</div>"""

        primary_cta = _btn(create_url, "Cr\u00e9er un engagement")

        body = f"""
<p style="margin:0 0 6px;font-size:14px;color:#64748B;font-weight:500;">Bonjour{(' ' + first_name) if first_name else ''},</p>
<p style="margin:0 0 24px;font-size:22px;font-weight:800;color:#0F172A;line-height:1.25;">{headline}<br/>
<span style="font-size:15px;font-weight:500;color:#64748B;">{subtitle}</span></p>
{card_html}
{share_btn}
<div style="border-top:1px solid #E2E8F0;padding-top:24px;text-align:center;">
  <p style="margin:0 0 16px;font-size:15px;font-weight:600;color:#0F172A;">Votre temps a de la valeur.<br/>Prot\u00e9gez-le.</p>
  {primary_cta}
</div>"""

        html = _base_template(body, accent="info")

        _send_async(user["email"], subject, html, f"post_engagement_{card_type}", appointment_id, user_id)
