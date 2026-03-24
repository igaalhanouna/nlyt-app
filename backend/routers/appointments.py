from fastapi import APIRouter, HTTPException, Request
import os
import uuid
import sys
sys.path.append('/app/backend')
from models.schemas import AppointmentCreate, AppointmentResponse
from middleware.auth_middleware import get_current_user
from utils.date_utils import now_utc, normalize_to_utc, now_utc_iso
from services.contract_service import ContractService

# System constant — platform commission is NOT user-editable
from database import db
PLATFORM_COMMISSION_PERCENT = float(os.environ.get('PLATFORM_COMMISSION_PERCENT', '20'))
VALID_CURRENCIES = {"eur", "usd", "gbp", "chf"}

router = APIRouter()


from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta, timezone

BUFFER_MINUTES = 30  # Warning threshold
MIN_FUTURE_MINUTES = 10  # Never suggest a slot starting less than 10 min from now


class ConflictCheckInput(BaseModel):
    start_datetime: str
    duration_minutes: int = 60


class ConflictItem(BaseModel):
    title: str
    start: str
    end: str
    source: str = "nlyt"  # nlyt | google | outlook


class SuggestionItem(BaseModel):
    datetime_str: str
    label: str  # optimal | comfortable | tight


class ConflictCheckOutput(BaseModel):
    status: str  # conflict | warning | available
    confidence: str  # high | medium
    confidence_detail: str = ""
    conflicts: List[ConflictItem] = []
    warnings: List[ConflictItem] = []
    suggestions: List[SuggestionItem] = []
    sources_checked: List[str] = []


def _parse_dt(s: str) -> Optional[datetime]:
    """Parse ISO datetime string to aware UTC datetime."""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _get_user_engagements(user_id: str) -> list:
    """Return future NLYT engagements for a user (as organizer or participant)."""
    now = now_utc_iso()
    org_apts = list(db.appointments.find(
        {"organizer_id": user_id, "status": {"$nin": ["cancelled", "deleted"]}, "start_datetime": {"$gte": now}},
        {"_id": 0, "appointment_id": 1, "title": 1, "start_datetime": 1, "duration_minutes": 1},
    ))
    participant_apt_ids = [
        p["appointment_id"]
        for p in db.participants.find(
            {"user_id": user_id, "status": {"$nin": ["declined", "cancelled_by_participant"]}},
            {"_id": 0, "appointment_id": 1},
        )
    ]
    if participant_apt_ids:
        part_apts = list(db.appointments.find(
            {"appointment_id": {"$in": participant_apt_ids}, "status": {"$nin": ["cancelled", "deleted"]}, "start_datetime": {"$gte": now}},
            {"_id": 0, "appointment_id": 1, "title": 1, "start_datetime": 1, "duration_minutes": 1},
        ))
        seen = {a["appointment_id"] for a in org_apts}
        for a in part_apts:
            if a["appointment_id"] not in seen:
                org_apts.append(a)
                seen.add(a["appointment_id"])
    return org_apts


def _check_overlap(proposed_start: datetime, proposed_end: datetime, engagements: list):
    """Check for conflicts and warnings against existing engagements.

    Conflict: proposed_start < eng_end AND proposed_end > eng_start (any intersection).
    Warning: no overlap but gap < BUFFER_MINUTES on either side.
    Edge-to-edge (proposed_end == eng_start or eng_end == proposed_start) is NOT a conflict.
    """
    conflicts = []
    warnings = []
    for eng in engagements:
        eng_start = _parse_dt(eng["start_datetime"])
        if not eng_start:
            continue
        eng_dur = eng.get("duration_minutes", 60)
        eng_end = eng_start + timedelta(minutes=eng_dur)
        source = eng.get("source", "nlyt")

        # Strict overlap check (half-open intervals: [start, end))
        if proposed_start < eng_end and proposed_end > eng_start:
            conflicts.append(ConflictItem(
                title=eng.get("title", "Engagement"),
                start=eng["start_datetime"],
                end=eng_end.isoformat(),
                source=source,
            ))
        else:
            # Check buffer proximity
            gap_seconds = None
            if proposed_start >= eng_end:
                gap_seconds = (proposed_start - eng_end).total_seconds()
            elif eng_start >= proposed_end:
                gap_seconds = (eng_start - proposed_end).total_seconds()

            if gap_seconds is not None and gap_seconds < BUFFER_MINUTES * 60:
                warnings.append(ConflictItem(
                    title=eng.get("title", "Engagement"),
                    start=eng["start_datetime"],
                    end=eng_end.isoformat(),
                    source=source,
                ))
    return conflicts, warnings


def _generate_suggestions(
    proposed_start: datetime,
    duration: int,
    engagements: list,
    count: int = 5,
) -> List[SuggestionItem]:
    """Generate slot suggestions that are always in the future and conflict-free."""
    now = datetime.now(timezone.utc)
    earliest_allowed = now + timedelta(minutes=MIN_FUTURE_MINUTES)

    # Build busy intervals within a 3-day window
    busy = []
    for eng in engagements:
        eng_start = _parse_dt(eng["start_datetime"])
        if not eng_start:
            continue
        eng_end = eng_start + timedelta(minutes=eng.get("duration_minutes", 60))
        if abs((eng_start - proposed_start).total_seconds()) < 259200:  # 3 days
            busy.append((eng_start, eng_end))
    busy.sort(key=lambda x: x[0])

    base_date = proposed_start.replace(hour=8, minute=0, second=0, microsecond=0)
    suggestions = []

    for day_offset in range(3):
        day_start = base_date + timedelta(days=day_offset)
        slot = day_start
        while slot.hour < 20:
            slot_end = slot + timedelta(minutes=duration)

            # Rule 1: slot START must be in the future with safety margin
            if slot < earliest_allowed:
                slot += timedelta(minutes=30)
                continue

            # Rule 2: slot must not extend past 20:00
            if slot_end.hour >= 20 and slot_end.minute > 0:
                break

            # Rule 3: skip if this is the same slot the user already selected
            if abs((slot - proposed_start).total_seconds()) < 60:
                slot += timedelta(minutes=30)
                continue

            # Rule 4: check for conflicts (full duration must be clear)
            has_conflict = False
            min_gap_seconds = float("inf")
            for bs, be in busy:
                # Overlap check: [slot, slot_end) vs [bs, be)
                if slot < be and slot_end > bs:
                    has_conflict = True
                    break
                # Gap calculation (only for non-overlapping)
                if slot >= be:
                    gap = (slot - be).total_seconds()
                elif bs >= slot_end:
                    gap = (bs - slot_end).total_seconds()
                else:
                    gap = 0
                min_gap_seconds = min(min_gap_seconds, gap)

            if not has_conflict:
                gap_min = min_gap_seconds / 60 if min_gap_seconds != float("inf") else 999
                if gap_min >= 60:
                    label = "optimal"
                elif gap_min >= BUFFER_MINUTES:
                    label = "comfortable"
                else:
                    label = "tight"
                suggestions.append(SuggestionItem(datetime_str=slot.isoformat(), label=label))
                if len(suggestions) >= count:
                    return suggestions

            slot += timedelta(minutes=30)

    return suggestions


def _fetch_external_events(user_id: str, window_start: str, window_end: str):
    """Fetch events from all connected calendars and return normalized engagements.
    Returns (events: list[dict], sources_ok: list[str], sources_failed: list[str]).
    Each event dict has: title, start_datetime, duration_minutes, source.
    """
    from adapters.google_calendar_adapter import GoogleCalendarAdapter
    from adapters.outlook_calendar_adapter import OutlookCalendarAdapter

    events = []
    sources_ok = []
    sources_failed = []

    connections = list(db.calendar_connections.find(
        {"user_id": user_id, "status": "connected"},
        {"_id": 0}
    ))

    # Collect all NLYT-synced external_event_ids for deduplication
    nlyt_external_ids = set()
    if connections:
        connection_ids = [c["connection_id"] for c in connections]
        sync_logs = db.calendar_sync_logs.find(
            {"connection_id": {"$in": connection_ids}, "sync_status": "synced"},
            {"_id": 0, "external_event_id": 1}
        )
        for sl in sync_logs:
            eid = sl.get("external_event_id")
            if eid:
                nlyt_external_ids.add(eid)

    for conn in connections:
        provider = conn.get("provider")
        access_token = conn.get("access_token")
        refresh_token = conn.get("refresh_token")
        connection_id = conn.get("connection_id")

        if not access_token:
            sources_failed.append(provider)
            continue

        def _make_cb(cid):
            def cb(new_token):
                if new_token:
                    db.calendar_connections.update_one(
                        {"connection_id": cid},
                        {"$set": {"access_token": new_token}}
                    )
                else:
                    db.calendar_connections.update_one(
                        {"connection_id": cid},
                        {"$set": {"status": "expired"}}
                    )
            return cb

        on_refresh = _make_cb(connection_id)

        raw_events = None
        if provider == "google":
            raw_events = GoogleCalendarAdapter.list_events(
                access_token, refresh_token, window_start, window_end,
                connection_update_callback=on_refresh
            )
        elif provider == "outlook":
            raw_events = OutlookCalendarAdapter.list_events(
                access_token, refresh_token, window_start, window_end,
                connection_update_callback=on_refresh
            )

        if raw_events is None:
            sources_failed.append(provider)
            continue

        sources_ok.append(provider)

        for ev in raw_events:
            # Deduplication: skip events that originated from NLYT
            if ev.get("event_id") in nlyt_external_ids:
                continue

            start_dt = _parse_dt(ev["start"])
            end_dt = _parse_dt(ev["end"])
            if not start_dt or not end_dt:
                continue
            duration_min = max(int((end_dt - start_dt).total_seconds() / 60), 1)

            events.append({
                "title": ev.get("title", "(Sans titre)"),
                "start_datetime": start_dt.isoformat(),
                "duration_minutes": duration_min,
                "source": provider,
            })

    return events, sources_ok, sources_failed


@router.post("/check-conflicts")
async def check_conflicts(data: ConflictCheckInput, request: Request):
    """Check if a proposed slot conflicts with NLYT engagements + connected calendars."""
    user = await get_current_user(request)

    proposed_start = _parse_dt(data.start_datetime)
    if not proposed_start:
        raise HTTPException(status_code=400, detail="Date invalide")
    proposed_end = proposed_start + timedelta(minutes=data.duration_minutes)

    # ── 1. NLYT engagements (always available) ──
    nlyt_engagements = _get_user_engagements(user["user_id"])
    # Tag each with source
    for eng in nlyt_engagements:
        eng["source"] = "nlyt"

    sources_checked = ["nlyt"]

    # ── 2. External calendar events (smart window: candidate ± buffer) ──
    buffer_td = timedelta(minutes=BUFFER_MINUTES)
    window_start = (proposed_start - buffer_td).isoformat()
    window_end = (proposed_end + buffer_td).isoformat()

    # Also expand for suggestion generation (3-day window)
    suggestion_window_start = proposed_start.replace(hour=0, minute=0, second=0, microsecond=0)
    suggestion_window_end = suggestion_window_start + timedelta(days=3)
    # Use the wider window to cover both conflict check AND suggestion generation
    fetch_start = min(proposed_start - buffer_td, suggestion_window_start).isoformat()
    fetch_end = max(proposed_end + buffer_td, suggestion_window_end).isoformat()

    ext_events, sources_ok, sources_failed = _fetch_external_events(
        user["user_id"], fetch_start, fetch_end
    )
    sources_checked.extend(sources_ok)

    # ── 3. Merge all engagements ──
    all_engagements = nlyt_engagements + ext_events

    # ── 4. Compute conflicts & warnings ──
    conflicts, warnings = _check_overlap(proposed_start, proposed_end, all_engagements)

    if conflicts:
        status = "conflict"
    elif warnings:
        status = "warning"
    else:
        status = "available"

    # ── 5. Confidence: rigorous ──
    # Check how many providers the user has connected
    total_connected = db.calendar_connections.count_documents(
        {"user_id": user["user_id"], "status": "connected"}
    )
    if total_connected == 0:
        # No external calendars → medium (only NLYT data)
        confidence = "medium"
        confidence_detail = "Seuls vos engagements NLYT sont vérifiés"
    elif sources_failed:
        # Some connected sources failed → medium
        confidence = "medium"
        failed_names = ", ".join(s.capitalize() for s in sources_failed)
        confidence_detail = f"Source(s) indisponible(s) : {failed_names}"
    else:
        # All connected sources responded OK → high
        confidence = "high"
        checked_names = ", ".join(s.upper() if s == "nlyt" else s.capitalize() for s in sources_checked)
        confidence_detail = f"Toutes les sources vérifiées : {checked_names}"

    # ── 6. Suggestions (computed locally from the merged set) ──
    suggestions = []
    if status != "available":
        suggestions = _generate_suggestions(proposed_start, data.duration_minutes, all_engagements)

    return ConflictCheckOutput(
        status=status,
        confidence=confidence,
        confidence_detail=confidence_detail,
        conflicts=[c.model_dump() for c in conflicts],
        warnings=[w.model_dump() for w in warnings],
        suggestions=[s.model_dump() for s in suggestions],
        sources_checked=sources_checked,
    )



def get_frontend_url(request: Request) -> str:
    """Get FRONTEND_URL from env, fallback to request.base_url"""
    frontend_url = os.environ.get('FRONTEND_URL', '')
    if frontend_url:
        return frontend_url.rstrip('/')
    return str(request.base_url).rstrip('/')

@router.post("/")
async def create_appointment(appointment: AppointmentCreate, request: Request):
    user = await get_current_user(request)
    
    membership = db.workspace_memberships.find_one({
        "workspace_id": appointment.workspace_id,
        "user_id": user['user_id']
    }, {"_id": 0})
    
    if not membership:
        raise HTTPException(status_code=403, detail="Accès refusé au workspace")
    
    # --- Server-side validations ---
    # Currency validation
    if appointment.penalty_currency.lower() not in VALID_CURRENCIES:
        raise HTTPException(status_code=400, detail=f"Devise invalide. Devises acceptées : {', '.join(VALID_CURRENCIES)}")
    
    # Platform commission is a SYSTEM value — override any client-sent value
    platform_pct = PLATFORM_COMMISSION_PERCENT
    
    # Validate distribution: participant + charity must equal (100 - platform) for total = 100%
    max_distributable = 100 - platform_pct
    total_distributed = round(appointment.affected_compensation_percent + appointment.charity_percent, 2)
    if total_distributed != max_distributable:
        raise HTTPException(
            status_code=400,
            detail=f"La somme compensation ({appointment.affected_compensation_percent}%) + charité ({appointment.charity_percent}%) doit être exactement {max_distributable}%. Commission plateforme fixée à {platform_pct}%."
        )
    
    # Validate charity association if charity > 0
    if appointment.charity_percent > 0 and appointment.charity_association_id:
        from routers.charity_associations import is_valid_association
        if not is_valid_association(appointment.charity_association_id):
            raise HTTPException(status_code=400, detail="Association caritative non valide")
    
    # Resolve charity association name for snapshot
    charity_association_name = None
    if appointment.charity_association_id:
        from routers.charity_associations import get_association_name
        charity_association_name = get_association_name(appointment.charity_association_id)
    
    appointment_id = str(uuid.uuid4())
    
    # Prepare event_reminders config (default: all enabled for better UX)
    event_reminders_config = None
    if appointment.event_reminders:
        event_reminders_config = {
            "ten_minutes_before": appointment.event_reminders.ten_minutes_before,
            "one_hour_before": appointment.event_reminders.one_hour_before,
            "one_day_before": appointment.event_reminders.one_day_before
        }
    else:
        # Default: enable all reminders (zéro friction - automatic)
        event_reminders_config = {
            "ten_minutes_before": True,
            "one_hour_before": True,
            "one_day_before": True
        }
    
    # Normalize start_datetime to UTC ISO format
    utc_start = normalize_to_utc(appointment.start_datetime)

    # Reject past dates — compare in UTC
    from utils.date_utils import parse_iso_datetime
    start_dt = parse_iso_datetime(utc_start)
    if start_dt and start_dt <= now_utc():
        raise HTTPException(status_code=400, detail="Impossible de créer un rendez-vous dans le passé")

    # SHORT NOTICE: Cap cancellation_deadline_hours to actual time until appointment
    hours_until_start = (start_dt - now_utc()).total_seconds() / 3600 if start_dt else None
    effective_cancellation_hours = appointment.cancellation_deadline_hours
    if hours_until_start is not None and effective_cancellation_hours > hours_until_start:
        effective_cancellation_hours = max(0, int(hours_until_start))

    # ── Validate meeting provider availability before creation ──
    if appointment.appointment_type == "video" and appointment.meeting_provider:
        mp = appointment.meeting_provider
        if mp == "teams":
            outlook_conn = db.calendar_connections.find_one(
                {"user_id": user['user_id'], "provider": "outlook", "status": "connected"},
                {"_id": 0, "has_online_meetings_scope": 1}
            )
            if not (outlook_conn and outlook_conn.get("has_online_meetings_scope") is True):
                raise HTTPException(status_code=400, detail="Microsoft Teams nécessite l'activation de Teams avancé sur un compte Microsoft 365 professionnel.")
        elif mp == "meet":
            google_conn = db.calendar_connections.find_one(
                {"user_id": user['user_id'], "provider": "google", "status": "connected"},
                {"_id": 0}
            )
            if not google_conn:
                raise HTTPException(status_code=400, detail="Google Meet nécessite la connexion d'un compte Google dans les paramètres.")
        elif mp == "zoom":
            from routers.video_evidence_routes import get_provider_status
            zoom_platform = get_provider_status()["zoom"]["configured"]
            zoom_user = db.user_settings.find_one(
                {"user_id": user['user_id']}, {"_id": 0, "zoom_connected": 1}
            )
            if not (zoom_platform and zoom_user and zoom_user.get("zoom_connected") is True):
                raise HTTPException(status_code=400, detail="Zoom nécessite une connexion Zoom active dans les paramètres.")
        elif mp == "external":
            if not appointment.meeting_join_url or not appointment.meeting_join_url.strip():
                raise HTTPException(status_code=400, detail="L'URL de la réunion est requise pour Autre plateforme.")

    appointment_doc = {
        "appointment_id": appointment_id,
        "workspace_id": appointment.workspace_id,
        "organizer_id": user['user_id'],
        "title": appointment.title,
        "appointment_type": appointment.appointment_type,
        "location": appointment.location,
        "location_latitude": appointment.location_latitude,
        "location_longitude": appointment.location_longitude,
        "location_place_id": appointment.location_place_id,
        "meeting_provider": appointment.meeting_provider,
        "external_meeting_id": appointment.external_meeting_id,
        "meeting_join_url": appointment.meeting_join_url,
        "start_datetime": utc_start,
        "duration_minutes": appointment.duration_minutes,
        "tolerated_delay_minutes": appointment.tolerated_delay_minutes,
        "cancellation_deadline_hours": effective_cancellation_hours,
        "cancellation_deadline_hours_original": appointment.cancellation_deadline_hours,
        "penalty_amount": appointment.penalty_amount,
        "penalty_currency": appointment.penalty_currency.lower(),
        "affected_compensation_percent": appointment.affected_compensation_percent,
        "platform_commission_percent": platform_pct,  # SYSTEM value — never from client
        "charity_percent": appointment.charity_percent,
        "charity_association_id": appointment.charity_association_id,
        "charity_association_name": charity_association_name,
        "policy_template_id": appointment.policy_template_id,
        "policy_snapshot_id": None,
        "event_reminders": event_reminders_config,
        "event_reminders_sent": {},
        "appointment_timezone": appointment.appointment_timezone or 'Europe/Paris',
        "status": "pending_organizer_guarantee",
        "created_at": now_utc_iso(),
        "updated_at": now_utc_iso()
    }
    
    db.appointments.insert_one(appointment_doc)

    # --- Inject organizer as participant (same rules, with guarantee) ---
    organizer_user = db.users.find_one({"user_id": user['user_id']}, {"_id": 0})
    organizer_invitation_token = str(uuid.uuid4())
    organizer_participant_id = str(uuid.uuid4())
    organizer_participant_doc = {
        "participant_id": organizer_participant_id,
        "appointment_id": appointment_id,
        "email": organizer_user.get('email', ''),
        "first_name": organizer_user.get('first_name', ''),
        "last_name": organizer_user.get('last_name', ''),
        "name": f"{organizer_user.get('first_name', '')} {organizer_user.get('last_name', '')}".strip(),
        "role": "organizer",
        "is_organizer": True,
        "status": "accepted_pending_guarantee",
        "invitation_token": organizer_invitation_token,
        "user_id": user['user_id'],
        "accepted_at": now_utc().isoformat(),
        "invited_at": now_utc().isoformat(),
        "created_at": now_utc().isoformat()
    }
    db.participants.insert_one(organizer_participant_doc)

    # --- Save other participants (DB records only — NO emails yet) ---
    if appointment.participants:
        for p in appointment.participants:
            if p.email and p.email.strip():
                if p.email.strip().lower() == organizer_user.get('email', '').lower():
                    continue
                invitation_token = str(uuid.uuid4())
                participant_doc = {
                    "participant_id": str(uuid.uuid4()),
                    "appointment_id": appointment_id,
                    "email": p.email.strip(),
                    "first_name": p.first_name or "",
                    "last_name": p.last_name or "",
                    "name": p.name or "",
                    "role": p.role or "participant",
                    "status": "invited",
                    "invitation_token": invitation_token,
                    "user_id": None,
                    "invited_at": now_utc().isoformat(),
                    "created_at": now_utc().isoformat()
                }
                db.participants.insert_one(participant_doc)

    # --- Generate policy snapshot (independent of guarantee) ---
    organizer = db.users.find_one({"user_id": user['user_id']}, {"_id": 0})
    snapshot = ContractService.generate_policy_snapshot(appointment_id, appointment_doc, organizer)
    db.appointments.update_one(
        {"appointment_id": appointment_id},
        {"$set": {"policy_snapshot_id": snapshot['snapshot_id']}}
    )

    # ──────────────────────────────────────────────────────────────
    # ORGANIZER GUARANTEE LOGIC
    # Rule: invitations are NEVER sent before organizer is guaranteed
    # ──────────────────────────────────────────────────────────────
    organizer_checkout_url = None
    organizer_auto_guaranteed = False

    if appointment.penalty_amount and appointment.penalty_amount > 0:
        # Check if organizer has a saved default payment method + consent
        has_default_pm = (
            organizer_user.get('default_payment_method_id')
            and organizer_user.get('payment_method_consent')
            and organizer_user.get('stripe_customer_id')
        )

        if has_default_pm:
            # ── OPTION A: Auto-guarantee with saved card (no Stripe redirect) ──
            guarantee_id = str(uuid.uuid4())
            guarantee_record = {
                "guarantee_id": guarantee_id,
                "participant_id": organizer_participant_id,
                "appointment_id": appointment_id,
                "stripe_customer_id": organizer_user['stripe_customer_id'],
                "stripe_payment_method_id": organizer_user['default_payment_method_id'],
                "penalty_amount": float(appointment.penalty_amount),
                "penalty_currency": appointment.penalty_currency.lower(),
                "status": "completed",
                "source": "default_payment_method",
                "created_at": now_utc_iso(),
                "completed_at": now_utc_iso(),
                "updated_at": now_utc_iso()
            }
            db.payment_guarantees.insert_one(guarantee_record)

            db.participants.update_one(
                {"participant_id": organizer_participant_id},
                {"$set": {
                    "status": "accepted_guaranteed",
                    "guarantee_id": guarantee_id,
                    "stripe_customer_id": organizer_user['stripe_customer_id'],
                    "stripe_payment_method_id": organizer_user['default_payment_method_id'],
                    "guaranteed_at": now_utc_iso(),
                    "updated_at": now_utc_iso()
                }}
            )
            organizer_auto_guaranteed = True
        else:
            # ── OPTION B: Stripe Checkout redirect (fallback) ──
            try:
                from services.stripe_guarantee_service import StripeGuaranteeService
                frontend_url = os.environ.get('FRONTEND_URL', '').rstrip('/') or str(request.base_url).rstrip('/')
                org_name = f"{organizer_user.get('first_name', '')} {organizer_user.get('last_name', '')}".strip()
                result = StripeGuaranteeService.create_guarantee_session(
                    participant_id=organizer_participant_id,
                    appointment_id=appointment_id,
                    participant_email=organizer_user.get('email', ''),
                    participant_name=org_name or 'Organisateur',
                    appointment_title=appointment.title,
                    penalty_amount=float(appointment.penalty_amount),
                    penalty_currency=appointment.penalty_currency.lower(),
                    frontend_url=frontend_url,
                    invitation_token=organizer_invitation_token
                )
                if result.get('success'):
                    organizer_checkout_url = result['checkout_url']
                    db.participants.update_one(
                        {"participant_id": organizer_participant_id},
                        {"$set": {
                            "guarantee_id": result['guarantee_id'],
                            "stripe_session_id": result['session_id']
                        }}
                    )
                else:
                    print(f"[ORGANIZER] Stripe session failed: {result.get('error')}")
            except Exception as e:
                print(f"[ORGANIZER] Non-blocking Stripe error: {e}")
    else:
        # No penalty → organizer directly guaranteed
        db.participants.update_one(
            {"participant_id": organizer_participant_id},
            {"$set": {"status": "accepted_guaranteed"}}
        )
        organizer_auto_guaranteed = True

    # ──────────────────────────────────────────────────────────────
    # ACTIVATION: only if organizer is already guaranteed
    # If not, RDV stays "pending_organizer_guarantee" — no emails,
    # no calendar sync, no meeting creation.
    # ──────────────────────────────────────────────────────────────
    meeting_result = None
    if organizer_auto_guaranteed:
        from services.appointment_lifecycle import activate_appointment
        activation = await activate_appointment(appointment_id, user['user_id'])
        meeting_result = activation.get("meeting_result")

    # Build response
    final_status = "active" if organizer_auto_guaranteed else "pending_organizer_guarantee"
    response = {
        "appointment_id": appointment_id,
        "policy_snapshot_id": snapshot['snapshot_id'],
        "organizer_participant_id": organizer_participant_id,
        "organizer_invitation_token": organizer_invitation_token,
        "status": final_status,
    }

    if organizer_auto_guaranteed:
        response["message"] = "Rendez-vous créé et invitations envoyées"
    else:
        response["message"] = "Rendez-vous créé. Complétez votre garantie pour envoyer les invitations."

    if organizer_checkout_url:
        response["organizer_checkout_url"] = organizer_checkout_url

    if meeting_result and meeting_result.get("success"):
        response["meeting"] = {
            "join_url": meeting_result.get("join_url"),
            "external_meeting_id": meeting_result.get("external_meeting_id"),
            "host_url": meeting_result.get("host_url"),
            "provider": meeting_result.get("provider"),
        }
    elif meeting_result and meeting_result.get("error"):
        response["meeting_warning"] = meeting_result["error"]

    return response


@router.post("/{appointment_id}/check-activation")
async def check_and_activate(appointment_id: str, request: Request):
    """
    Comfort polling endpoint — called by frontend after Stripe redirect.
    If the organizer guarantee is completed (via webhook or direct check),
    this activates the appointment (sends invitations, syncs calendar, etc.).
    Webhook is the primary source of truth; this is the fallback.
    """
    user = await get_current_user(request)

    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

    if appointment['organizer_id'] != user['user_id']:
        raise HTTPException(status_code=403, detail="Accès refusé")

    if appointment.get('status') == 'active':
        return {"status": "active", "already_active": True}

    if appointment.get('status') != 'pending_organizer_guarantee':
        return {"status": appointment.get('status')}

    # Check if organizer participant is already guaranteed
    org_p = db.participants.find_one(
        {"appointment_id": appointment_id, "is_organizer": True},
        {"_id": 0}
    )
    if not org_p:
        return {"status": "pending_organizer_guarantee", "guaranteed": False}

    if org_p.get('status') == 'accepted_guaranteed':
        from services.appointment_lifecycle import activate_appointment
        result = await activate_appointment(appointment_id, user['user_id'])
        return {
            "status": "active" if result.get("success") else "pending_organizer_guarantee",
            "activated": result.get("success", False),
            "meeting": result.get("meeting_result")
        }

    # Guarantee might be completed but webhook hasn't arrived yet — poll Stripe
    if org_p.get('stripe_session_id'):
        from services.stripe_guarantee_service import StripeGuaranteeService
        g_result = StripeGuaranteeService.get_guarantee_status(org_p['stripe_session_id'])

        if g_result.get('status') == 'completed':
            from services.appointment_lifecycle import activate_appointment
            result = await activate_appointment(appointment_id, user['user_id'])
            return {
                "status": "active" if result.get("success") else "pending_organizer_guarantee",
                "activated": result.get("success", False),
                "meeting": result.get("meeting_result")
            }

    return {"status": "pending_organizer_guarantee", "guaranteed": False}


@router.post("/{appointment_id}/retry-organizer-guarantee")
async def retry_organizer_guarantee(appointment_id: str, request: Request):
    """
    Re-generate a Stripe Checkout session for an organizer whose appointment
    is stuck in pending_organizer_guarantee.
    If the user now has a default payment method, auto-guarantee + activate instead.
    """
    user = await get_current_user(request)

    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

    if appointment['organizer_id'] != user['user_id']:
        raise HTTPException(status_code=403, detail="Accès refusé")

    if appointment.get('status') != 'pending_organizer_guarantee':
        return {"status": appointment.get('status'), "message": "Ce rendez-vous n'est pas en attente de garantie"}

    # Find organizer participant
    org_p = db.participants.find_one(
        {"appointment_id": appointment_id, "is_organizer": True},
        {"_id": 0}
    )
    if not org_p:
        raise HTTPException(status_code=500, detail="Participant organisateur introuvable")

    # Check if user NOW has a default payment method
    user_doc = db.users.find_one({"user_id": user['user_id']}, {"_id": 0})
    has_default_pm = (
        user_doc.get('default_payment_method_id')
        and user_doc.get('payment_method_consent')
        and user_doc.get('stripe_customer_id')
    )

    if has_default_pm:
        # Auto-guarantee with saved card
        guarantee_id = str(uuid.uuid4())
        guarantee_record = {
            "guarantee_id": guarantee_id,
            "participant_id": org_p['participant_id'],
            "appointment_id": appointment_id,
            "stripe_customer_id": user_doc['stripe_customer_id'],
            "stripe_payment_method_id": user_doc['default_payment_method_id'],
            "penalty_amount": float(appointment.get('penalty_amount', 0)),
            "penalty_currency": appointment.get('penalty_currency', 'eur').lower(),
            "status": "completed",
            "source": "default_payment_method",
            "created_at": now_utc_iso(),
            "completed_at": now_utc_iso(),
            "updated_at": now_utc_iso()
        }
        db.payment_guarantees.insert_one(guarantee_record)

        db.participants.update_one(
            {"participant_id": org_p['participant_id']},
            {"$set": {
                "status": "accepted_guaranteed",
                "guarantee_id": guarantee_id,
                "stripe_customer_id": user_doc['stripe_customer_id'],
                "stripe_payment_method_id": user_doc['default_payment_method_id'],
                "guaranteed_at": now_utc_iso(),
                "updated_at": now_utc_iso()
            }}
        )

        from services.appointment_lifecycle import activate_appointment
        activation = await activate_appointment(appointment_id, user['user_id'])

        return {
            "status": "active",
            "activated": True,
            "message": "Garantie validée avec votre carte par défaut. Invitations envoyées.",
            "meeting": activation.get("meeting_result")
        }
    else:
        # Create a new Stripe Checkout session
        from services.stripe_guarantee_service import StripeGuaranteeService
        frontend_url = os.environ.get('FRONTEND_URL', '').rstrip('/') or str(request.base_url).rstrip('/')
        org_name = f"{user_doc.get('first_name', '')} {user_doc.get('last_name', '')}".strip()

        result = StripeGuaranteeService.create_guarantee_session(
            participant_id=org_p['participant_id'],
            appointment_id=appointment_id,
            participant_email=user_doc.get('email', ''),
            participant_name=org_name or 'Organisateur',
            appointment_title=appointment.get('title', ''),
            penalty_amount=float(appointment.get('penalty_amount', 0)),
            penalty_currency=appointment.get('penalty_currency', 'eur').lower(),
            frontend_url=frontend_url,
            invitation_token=org_p.get('invitation_token', '')
        )

        if result.get('success'):
            db.participants.update_one(
                {"participant_id": org_p['participant_id']},
                {"$set": {
                    "guarantee_id": result['guarantee_id'],
                    "stripe_session_id": result['session_id']
                }}
            )
            return {
                "status": "pending_organizer_guarantee",
                "checkout_url": result['checkout_url'],
                "message": "Redirigez vers Stripe pour valider votre garantie."
            }
        else:
            raise HTTPException(status_code=500, detail=result.get('error', 'Erreur Stripe'))


@router.get("/")
async def list_appointments(workspace_id: str = None, skip: int = 0, limit: int = 20, time_filter: str = None, request: Request = None):
    user = await get_current_user(request)
    
    query = {}
    if workspace_id:
        membership = db.workspace_memberships.find_one({
            "workspace_id": workspace_id,
            "user_id": user['user_id']
        }, {"_id": 0})
        
        if not membership:
            raise HTTPException(status_code=403, detail="Accès refusé")
        
        query["workspace_id"] = workspace_id
    else:
        memberships = list(db.workspace_memberships.find({"user_id": user['user_id']}, {"_id": 0}))
        workspace_ids = [m['workspace_id'] for m in memberships]
        query["workspace_id"] = {"$in": workspace_ids}
    
    # Exclude deleted appointments from listing
    query["status"] = {"$ne": "deleted"}

    # Time filter: upcoming (future) or past
    now_str = now_utc().isoformat()
    sort_order = 1  # ascending by default
    if time_filter == "upcoming":
        query["start_datetime"] = {"$gte": now_str}
        sort_order = 1  # nearest first
    elif time_filter == "past":
        query["start_datetime"] = {"$lt": now_str}
        sort_order = -1  # most recent past first

    total = db.appointments.count_documents(query)
    appointments = list(
        db.appointments.find(query, {"_id": 0})
        .sort("start_datetime", sort_order)
        .skip(skip)
        .limit(limit)
    )
    
    # Add participants with status to each appointment
    for apt in appointments:
        # Normalize legacy naive datetimes to UTC
        if apt.get('start_datetime'):
            apt['start_datetime'] = normalize_to_utc(apt['start_datetime'])
        
        participants = list(db.participants.find(
            {"appointment_id": apt['appointment_id']}, 
            {"_id": 0, "participant_id": 1, "email": 1, "name": 1, "first_name": 1, "last_name": 1, "role": 1, "status": 1, "accepted_at": 1, "declined_at": 1, "cancelled_at": 1, "invitation_token": 1}
        ))
        apt['participants'] = participants
        apt['participants_count'] = len(participants)

        # Enrich participants with guarantee revalidation status
        for p in participants:
            if p.get('status') in ('accepted_guaranteed', 'accepted_pending_guarantee'):
                g = db.payment_guarantees.find_one(
                    {"participant_id": p['participant_id'], "appointment_id": apt['appointment_id'],
                     "status": {"$in": ["completed", "dev_pending"]}},
                    {"_id": 0, "requires_revalidation": 1, "revalidation_reason": 1}
                )
                if g and g.get('requires_revalidation'):
                    p['guarantee_requires_revalidation'] = True
                    p['guarantee_revalidation_reason'] = g.get('revalidation_reason', '')
        
        # Add summary of participant statuses
        status_summary = {"invited": 0, "accepted": 0, "declined": 0, "cancelled_by_participant": 0}
        for p in participants:
            status = p.get('status', 'invited')
            if status in ('accepted', 'accepted_pending_guarantee', 'accepted_guaranteed'):
                status_summary['accepted'] += 1
            elif status in status_summary:
                status_summary[status] += 1
            else:
                status_summary['invited'] += 1
        apt['participants_status_summary'] = status_summary
    
    return {
        "items": appointments,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": skip + limit < total,
    }

@router.get("/{appointment_id}")
async def get_appointment(appointment_id: str, request: Request):
    user = await get_current_user(request)
    
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    
    membership = db.workspace_memberships.find_one({
        "workspace_id": appointment['workspace_id'],
        "user_id": user['user_id']
    }, {"_id": 0})
    
    if not membership:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    # Normalize legacy naive datetimes to UTC on read
    if appointment.get('start_datetime'):
        appointment['start_datetime'] = normalize_to_utc(appointment['start_datetime'])
    
    return appointment

@router.patch("/{appointment_id}")
async def update_appointment(appointment_id: str, update_data: dict, request: Request):
    user = await get_current_user(request)
    
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    
    if appointment['organizer_id'] != user['user_id']:
        raise HTTPException(status_code=403, detail="Seul l'organisateur peut modifier ce rendez-vous")
    
    has_acceptances = db.acceptances.find_one({"appointment_id": appointment_id})
    if has_acceptances:
        raise HTTPException(status_code=400, detail="Impossible de modifier un rendez-vous déjà accepté")
    
    # Whitelist: only these fields can be updated
    ALLOWED_FIELDS = {
        "title", "description", "appointment_type", "location", "location_latitude",
        "location_longitude", "location_place_id", "meeting_provider",
        "external_meeting_id", "meeting_join_url",
        "start_datetime", "duration_minutes", "tolerated_delay_minutes",
        "cancellation_deadline_hours", "penalty_amount", "penalty_currency",
        "affected_compensation_percent", "charity_percent",
        "charity_association_id", "event_reminders"
    }
    
    safe_data = {k: v for k, v in update_data.items() if k in ALLOWED_FIELDS}
    
    if not safe_data:
        raise HTTPException(status_code=400, detail="Aucun champ modifiable fourni")
    
    # Normalize start_datetime to UTC if being updated
    if 'start_datetime' in safe_data:
        safe_data['start_datetime'] = normalize_to_utc(safe_data['start_datetime'])
        # Reject past dates
        from utils.date_utils import parse_iso_datetime
        new_start = parse_iso_datetime(safe_data['start_datetime'])
        if new_start and new_start <= now_utc():
            raise HTTPException(status_code=400, detail="Impossible de modifier un rendez-vous vers une date dans le passé")
    
    # platform_commission_percent is NEVER user-editable
    safe_data.pop("platform_commission_percent", None)
    safe_data['updated_at'] = now_utc_iso()
    
    db.appointments.update_one(
        {"appointment_id": appointment_id},
        {"$set": safe_data}
    )
    
    # Auto-update calendar events if calendar-visible fields changed (non-blocking)
    try:
        from routers.calendar_routes import has_calendar_fields_changed, perform_auto_update
        if has_calendar_fields_changed(appointment, safe_data):
            updated_doc = {**appointment, **safe_data}
            perform_auto_update(user['user_id'], appointment_id, updated_doc)
    except Exception as e:
        print(f"[AUTO-UPDATE] Error during auto-update: {e}")
    
    return {"message": "Rendez-vous mis à jour"}


@router.post("/{appointment_id}/cancel")
async def cancel_appointment(appointment_id: str, request: Request):
    """
    Cancel an appointment (soft cancel - keeps history).
    Notifies all participants via email.
    """
    user = await get_current_user(request)
    
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    
    if appointment['organizer_id'] != user['user_id']:
        raise HTTPException(status_code=403, detail="Seul l'organisateur peut annuler ce rendez-vous")
    
    # Check if already cancelled
    if appointment.get('status') == 'cancelled':
        raise HTTPException(status_code=400, detail="Ce rendez-vous est déjà annulé")
    
    # Allow cancellation from both active and pending_organizer_guarantee statuses
    is_pending = appointment.get('status') == 'pending_organizer_guarantee'
    
    # Update appointment status to cancelled
    now = now_utc().isoformat()
    db.appointments.update_one(
        {"appointment_id": appointment_id},
        {"$set": {
            "status": "cancelled",
            "cancelled_at": now,
            "cancelled_by": user['user_id'],
            "updated_at": now
        }}
    )
    
    # Get organizer info for email
    organizer = db.users.find_one({"user_id": user['user_id']}, {"_id": 0})
    organizer_name = f"{organizer.get('first_name', '')} {organizer.get('last_name', '')}".strip() or "L'organisateur"
    
    # Release all active guarantees for this appointment
    guaranteed_participants = list(db.participants.find(
        {"appointment_id": appointment_id, "status": "accepted_guaranteed"},
        {"_id": 0, "guarantee_id": 1}
    ))
    for gp in guaranteed_participants:
        if gp.get('guarantee_id'):
            try:
                from services.stripe_guarantee_service import StripeGuaranteeService
                StripeGuaranteeService.release_guarantee(
                    gp['guarantee_id'],
                    "appointment_cancelled_by_organizer"
                )
            except Exception as e:
                import logging
                logging.error(f"Failed to release guarantee {gp['guarantee_id']}: {e}")
    
    # Notify participants ONLY if appointment was active (invitations were sent)
    notifications_sent = 0
    if not is_pending:
        participants = list(db.participants.find({"appointment_id": appointment_id}, {"_id": 0}))
        from services.email_service import EmailService
        for participant in participants:
            try:
                participant_name = f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip()
                if not participant_name:
                    participant_name = participant.get('email', '').split('@')[0]
                
                await EmailService.send_appointment_cancelled_notification(
                    participant_email=participant['email'],
                    participant_name=participant_name,
                    organizer_name=organizer_name,
                    appointment_title=appointment.get('title', 'Rendez-vous'),
                    appointment_datetime=appointment.get('start_datetime', ''),
                    location=appointment.get('location') or appointment.get('meeting_provider'),
                    appointment_timezone=appointment.get('appointment_timezone', 'Europe/Paris')
                )
                notifications_sent += 1
            except Exception as e:
                import logging
                logging.error(f"Failed to send cancellation notification to {participant.get('email')}: {e}")
    
    participants = list(db.participants.find({"appointment_id": appointment_id}, {"_id": 0}))
    
    # Delete calendar events across all connected providers (best-effort, only if was active)
    try:
        from adapters.google_calendar_adapter import GoogleCalendarAdapter
        from adapters.outlook_calendar_adapter import OutlookCalendarAdapter
        adapters = {"google": GoogleCalendarAdapter, "outlook": OutlookCalendarAdapter}

        for provider, adapter in adapters.items():
            connection = db.calendar_connections.find_one(
                {"user_id": user['user_id'], "provider": provider, "status": "connected"}
            )
            if not connection:
                continue
            sync_log = db.calendar_sync_logs.find_one({
                "appointment_id": appointment_id,
                "connection_id": connection['connection_id'],
                "sync_status": "synced"
            })
            if sync_log and sync_log.get('external_event_id'):
                deleted = adapter.delete_event(
                    connection['access_token'],
                    connection.get('refresh_token'),
                    sync_log['external_event_id']
                )
                if deleted:
                    db.calendar_sync_logs.update_one(
                        {"log_id": sync_log['log_id']},
                        {"$set": {"sync_status": "deleted", "deleted_at": now}}
                    )
    except Exception as e:
        import logging
        logging.error(f"Failed to delete calendar events: {e}")

    return {
        "success": True,
        "message": "Rendez-vous annulé avec succès",
        "participants_notified": notifications_sent,
        "total_participants": len(participants)
    }


@router.delete("/{appointment_id}")
async def delete_appointment(appointment_id: str, request: Request):
    """
    Delete an appointment (soft delete).
    Notifies all participants via email.
    """
    user = await get_current_user(request)
    
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    
    # Check if user is organizer OR has admin role in workspace
    membership = db.workspace_memberships.find_one({
        "workspace_id": appointment['workspace_id'],
        "user_id": user['user_id']
    }, {"_id": 0})
    
    if not membership:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    if appointment['organizer_id'] != user['user_id'] and membership.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Seul l'organisateur peut supprimer ce rendez-vous")
    
    # Get organizer info for email
    organizer = db.users.find_one({"user_id": appointment['organizer_id']}, {"_id": 0})
    organizer_name = f"{organizer.get('first_name', '')} {organizer.get('last_name', '')}".strip() or "L'organisateur"
    
    # Notify all participants before deletion
    participants = list(db.participants.find({"appointment_id": appointment_id}, {"_id": 0}))
    
    from services.email_service import EmailService
    
    for participant in participants:
        try:
            participant_name = f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip()
            if not participant_name:
                participant_name = participant.get('email', '').split('@')[0]
            
            await EmailService.send_appointment_deleted_notification(
                participant_email=participant['email'],
                participant_name=participant_name,
                organizer_name=organizer_name,
                appointment_title=appointment.get('title', 'Rendez-vous'),
                appointment_datetime=appointment.get('start_datetime', ''),
                location=appointment.get('location') or appointment.get('meeting_provider'),
                appointment_timezone=appointment.get('appointment_timezone', 'Europe/Paris')
            )
        except Exception as e:
            import logging
            logging.error(f"Failed to send deletion notification to {participant.get('email')}: {e}")
    
    # Soft delete: mark as deleted instead of hard delete
    now = now_utc().isoformat()
    db.appointments.update_one(
        {"appointment_id": appointment_id},
        {"$set": {
            "status": "deleted",
            "deleted_at": now,
            "deleted_by": user['user_id'],
            "updated_at": now
        }}
    )
    
    # Also mark participants as belonging to deleted appointment
    db.participants.update_many(
        {"appointment_id": appointment_id},
        {"$set": {"appointment_deleted": True, "updated_at": now}}
    )
    
    return {"message": "Rendez-vous supprimé avec succès"}


@router.get("/{appointment_id}/distributions")
async def get_appointment_distributions(appointment_id: str, request: Request):
    """Get all distributions for a specific appointment."""
    user = await get_current_user(request)
    appointment = db.appointments.find_one(
        {"appointment_id": appointment_id},
        {"_id": 0, "organizer_id": 1, "workspace_id": 1}
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

    # Only organizer can see all distributions
    if appointment.get("organizer_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="Accès réservé à l'organisateur")

    from services.distribution_service import get_distributions_for_appointment
    distributions = get_distributions_for_appointment(appointment_id)
    return {"distributions": distributions}


@router.post("/{appointment_id}/remind")
async def remind_participants(appointment_id: str, request: Request):
    """Send reminder to pending participants."""
    user = await get_current_user(request)

    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        raise HTTPException(status_code=404, detail="Engagement introuvable")
    if appointment.get("organizer_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="Seul l'organisateur peut relancer")

    # Fetch participants from separate collection (not embedded in appointment doc)
    participants = list(db.participants.find(
        {"appointment_id": appointment_id},
        {"_id": 0, "participant_id": 1, "email": 1, "first_name": 1, "last_name": 1, 
         "status": 1, "invitation_token": 1, "is_organizer": 1}
    ))
    
    pending_statuses = {"invited", "accepted_pending_guarantee"}
    # Exclude organizer from reminders
    pending = [p for p in participants if p.get("status") in pending_statuses and not p.get("is_organizer")]

    if not pending:
        raise HTTPException(status_code=400, detail="Aucun participant en attente")

    frontend_url = get_frontend_url(request)
    from services.email_service import EmailService
    organizer = db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    organizer_name = f"{organizer.get('first_name', '')} {organizer.get('last_name', '')}".strip() if organizer else "L'organisateur"
    sent = 0

    for p in pending:
        try:
            invitation_link = f"{frontend_url}/invitation/{p.get('invitation_token', '')}"
            name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or p.get("email", "").split("@")[0]
            await EmailService.send_invitation_email(
                to_email=p["email"],
                to_name=name,
                organizer_name=organizer_name,
                appointment_title=appointment.get("title", ""),
                appointment_datetime=appointment.get("start_datetime", ""),
                invitation_link=invitation_link,
                location=appointment.get("location"),
                penalty_amount=appointment.get("penalty_amount"),
                penalty_currency=appointment.get("penalty_currency", "EUR"),
                cancellation_deadline_hours=appointment.get("cancellation_deadline_hours"),
                appointment_id=appointment_id,
            )
            sent += 1
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Remind email failed for {p.get('email')}: {e}")

    return {"success": True, "reminded": sent, "total_pending": len(pending)}
