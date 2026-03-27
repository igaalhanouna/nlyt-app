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
        "gps_radius_meters": appointment.gps_radius_meters,
        "event_reminders": event_reminders_config,
        "event_reminders_sent": {},
        "appointment_timezone": appointment.appointment_timezone or 'Europe/Paris',
        "status": "pending_organizer_guarantee",
        "created_at": now_utc_iso(),
        "updated_at": now_utc_iso()
    }

    # Store conversion origin if created from an external event
    if appointment.from_external_event_id:
        # Find the external event source for the badge
        ext_ev = db.external_events.find_one(
            {"external_event_id": appointment.from_external_event_id, "imported_by_user_id": user['user_id']},
            {"_id": 0, "source": 1, "status": 1}
        )
        if ext_ev and ext_ev.get("status") == "imported":
            appointment_doc["converted_from"] = {
                "source": ext_ev["source"],
                "external_event_id": appointment.from_external_event_id,
            }
        elif ext_ev and ext_ev.get("status") == "converted":
            raise HTTPException(status_code=409, detail="Cet événement a déjà été converti en engagement NLYT")
    
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

    # ── Mark external event as converted (atomic, anti-double) ──
    if appointment.from_external_event_id:
        from services.external_events_service import mark_as_converted
        conv_result = mark_as_converted(user['user_id'], appointment.from_external_event_id, appointment_id)
        if conv_result.get("error") == "already_converted":
            print(f"[CONVERT] External event {appointment.from_external_event_id} already converted (race condition)")
        elif conv_result.get("success"):
            response["converted_from_external"] = True

            # Create "adopted" sync_log so auto-sync won't re-push to calendar
            ext_ev = db.external_events.find_one(
                {"external_event_id": appointment.from_external_event_id},
                {"_id": 0, "source": 1, "connection_id": 1, "external_event_id": 1}
            )
            if ext_ev and ext_ev.get("connection_id"):
                adopted_log = {
                    "log_id": str(uuid.uuid4()),
                    "appointment_id": appointment_id,
                    "connection_id": ext_ev["connection_id"],
                    "provider": ext_ev["source"],
                    "external_event_id": ext_ev["external_event_id"],
                    "html_link": None,
                    "sync_status": "synced",
                    "sync_source": "adopted",
                    "retry_count": 0,
                    "next_retry_at": None,
                    "max_retries_reached": False,
                    "synced_at": now_utc_iso()
                }
                db.calendar_sync_logs.insert_one(adopted_log)
                print(f"[ADOPT] Created adopted sync_log for appointment {appointment_id} <-> {ext_ev['external_event_id']} ({ext_ev['source']})")

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



@router.get("/my-timeline")
async def get_my_timeline(request: Request):
    """
    Unified dashboard timeline merging organizer + participant items.
    Returns 3 buckets: action_required, upcoming, past.
    Each item has a stable, explicit structure for frontend rendering.
    """
    user = await get_current_user(request)
    user_id = user["user_id"]
    user_email = user.get("email", "")
    now_str = now_utc().isoformat()
    items = []

    # ── 1. Fetch organizer appointments ──
    memberships = list(db.workspace_memberships.find(
        {"user_id": user_id}, {"_id": 0, "workspace_id": 1}
    ))
    ws_ids = [m["workspace_id"] for m in memberships]

    if ws_ids:
        org_appointments = list(db.appointments.find(
            {"workspace_id": {"$in": ws_ids}, "status": {"$ne": "deleted"}},
            {"_id": 0}
        ).sort("start_datetime", 1))

        for apt in org_appointments:
            if apt.get("start_datetime"):
                apt["start_datetime"] = normalize_to_utc(apt["start_datetime"])

            participants = list(db.participants.find(
                {"appointment_id": apt["appointment_id"]},
                {"_id": 0, "participant_id": 1, "email": 1, "first_name": 1,
                 "last_name": 1, "status": 1, "invitation_token": 1, "is_organizer": 1}
            ))
            non_org_parts = [p for p in participants if not p.get("is_organizer")]
            accepted = sum(1 for p in participants if p.get("status") in ("accepted", "accepted_guaranteed"))
            guaranteed = sum(1 for p in non_org_parts if p.get("status") == "accepted_guaranteed")
            pending = sum(1 for p in participants if p.get("status") in ("invited", "accepted_pending_guarantee"))
            total = len(participants)
            non_org_count = len(non_org_parts)

            # Counterparty: list participant names (max 2 + "et X autres")
            names = []
            for p in participants:
                n = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
                if n:
                    names.append(n)
            if len(names) <= 2:
                counterparty = ", ".join(names) if names else "Aucun participant"
            else:
                counterparty = f"{names[0]}, {names[1]} et {len(names) - 2} autre{'s' if len(names) - 2 > 1 else ''}"

            is_past = apt.get("start_datetime", "") < now_str
            is_cancelled = apt.get("status") == "cancelled"

            # Use end_time (start + duration) to determine if truly finished
            _start_dt = _parse_dt(apt.get("start_datetime", ""))
            _end_dt = _start_dt + timedelta(minutes=apt.get("duration_minutes", 60)) if _start_dt else None
            _now_dt = datetime.now(timezone.utc)
            is_ended = (_end_dt <= _now_dt) if _end_dt else is_past

            action_required = False
            org_alert_label = None

            # Organizer action_required: < 50% guaranteed AND within 24h of cancellation deadline
            if not is_ended and not is_cancelled and non_org_count > 0:
                cancel_h = apt.get("cancellation_deadline_hours", 0)
                start_dt = _parse_dt(apt.get("start_datetime", ""))
                if start_dt:
                    now_dt = datetime.now(timezone.utc)
                    hours_to_start = (start_dt - now_dt).total_seconds() / 3600
                    hours_to_deadline = hours_to_start - cancel_h
                    if guaranteed < non_org_count / 2 and hours_to_deadline < 24:
                        action_required = True
                        if guaranteed == 0:
                            org_alert_label = "Personne n'a encore sécurisé sa présence"
                        else:
                            org_alert_label = f"Seulement {guaranteed}/{non_org_count} présence{'s' if guaranteed > 1 else ''} sécurisée{'s' if guaranteed > 1 else ''}"

            # Determine available actions
            if action_required:
                actions = ["remind", "cancel", "view_details"]
            else:
                actions = ["view_details"]
                if not is_ended and pending > 0:
                    actions.insert(0, "remind")
                if not is_ended:
                    actions.append("delete")

            # Pending wording for organizer
            pending_label = org_alert_label
            if not pending_label and pending > 0 and not is_ended:
                pending_label = f"En attente de réponse ({pending})"

            items.append({
                "appointment_id": apt["appointment_id"],
                "role": "organizer",
                "status": apt.get("status", "active"),
                "action_required": action_required,
                "starts_at": apt.get("start_datetime", ""),
                "sort_date": apt.get("start_datetime", ""),
                "counterparty_name": counterparty,
                "is_user_organizer": True,
                "is_user_participant": False,
                "title": apt.get("title", ""),
                "appointment_type": apt.get("appointment_type", "physical"),
                "location": apt.get("location", ""),
                "location_display_name": apt.get("location_display_name", ""),
                "meeting_provider": apt.get("meeting_provider", ""),
                "duration_minutes": apt.get("duration_minutes", 60),
                "penalty_amount": apt.get("penalty_amount", 0),
                "penalty_currency": apt.get("penalty_currency", "EUR"),
                "tolerated_delay_minutes": apt.get("tolerated_delay_minutes", 0),
                "cancellation_deadline_hours": apt.get("cancellation_deadline_hours", 0),
                "participants_count": total,
                "accepted_count": accepted,
                "guaranteed_count": guaranteed,
                "pending_count": pending,
                "actions": actions,
                "pending_label": pending_label,
                "converted_from": apt.get("converted_from"),
                "appointment_status": apt.get("status", "active"),
            })

    # ── 2. Fetch participant invitations ──
    my_participations = list(db.participants.find(
        {"$or": [{"user_id": user_id}, {"email": user_email}]},
        {"_id": 0}
    ))

    # Deduplicate: exclude participations where user is also organizer
    org_apt_ids = {item["appointment_id"] for item in items}

    for part in my_participations:
        apt_id = part.get("appointment_id")
        if apt_id in org_apt_ids:
            continue  # skip — already shown as organizer

        apt = db.appointments.find_one(
            {"appointment_id": apt_id, "status": {"$ne": "deleted"}},
            {"_id": 0}
        )
        if not apt:
            continue

        if apt.get("start_datetime"):
            apt["start_datetime"] = normalize_to_utc(apt["start_datetime"])

        # Get organizer name as counterparty
        organizer = db.users.find_one(
            {"user_id": apt.get("organizer_id")},
            {"_id": 0, "first_name": 1, "last_name": 1}
        )
        organizer_name = "Organisateur"
        if organizer:
            organizer_name = f"{organizer.get('first_name', '')} {organizer.get('last_name', '')}".strip() or "Organisateur"

        p_status = part.get("status", "invited")
        is_cancelled = apt.get("status") == "cancelled"

        # Use end_time (start + duration) to determine if truly finished
        _p_start_dt = _parse_dt(apt.get("start_datetime", ""))
        _p_end_dt = _p_start_dt + timedelta(minutes=apt.get("duration_minutes", 60)) if _p_start_dt else None
        _p_now_dt = datetime.now(timezone.utc)
        is_ended = (_p_end_dt <= _p_now_dt) if _p_end_dt else (apt.get("start_datetime", "") < now_str)

        # Action required: participant must act (respond OR finalize guarantee)
        # Never for cancelled or ended appointments
        action_required = p_status in ("invited", "accepted_pending_guarantee") and not is_ended and not is_cancelled

        # Available actions
        actions = ["view_details"]
        if p_status == "invited" and not is_ended:
            actions = ["accept", "decline", "view_details"]
        elif p_status == "accepted_pending_guarantee" and not is_ended:
            actions = ["finalize_guarantee", "view_details"]
        elif p_status in ("accepted", "accepted_guaranteed") and not is_ended:
            actions = ["view_details"]

        # Pending wording for participant
        pending_label = None
        if p_status == "invited" and not is_ended:
            pending_label = "Votre réponse est attendue"
        elif p_status == "accepted_pending_guarantee" and not is_ended:
            pending_label = "Garantie en attente"

        items.append({
            "appointment_id": apt_id,
            "role": "participant",
            "status": p_status,
            "action_required": action_required,
            "starts_at": apt.get("start_datetime", ""),
            "sort_date": apt.get("start_datetime", ""),
            "counterparty_name": organizer_name,
            "is_user_organizer": False,
            "is_user_participant": True,
            "title": apt.get("title", ""),
            "appointment_type": apt.get("appointment_type", "physical"),
            "location": apt.get("location", ""),
            "location_display_name": apt.get("location_display_name", ""),
            "meeting_provider": apt.get("meeting_provider", ""),
            "duration_minutes": apt.get("duration_minutes", 60),
            "penalty_amount": apt.get("penalty_amount", 0),
            "penalty_currency": apt.get("penalty_currency", "EUR"),
            "tolerated_delay_minutes": apt.get("tolerated_delay_minutes", 0),
            "cancellation_deadline_hours": apt.get("cancellation_deadline_hours", 0),
            "participant_status": p_status,
            "participant_id": part.get("participant_id"),
            "invitation_token": part.get("invitation_token"),
            "participants_count": 0,
            "accepted_count": 0,
            "pending_count": 0,
            "actions": actions,
            "pending_label": pending_label,
            "converted_from": apt.get("converted_from"),
            "appointment_status": apt.get("status", "active"),
        })

    # ── 3. Bucket into action_required / upcoming / past ──
    now_dt = datetime.now(timezone.utc)

    def _is_past_item(i):
        # Cancelled → always historique
        if i["appointment_status"] == "cancelled":
            return True
        # Declined/cancelled participations → historique
        if i.get("participant_status") in ("declined", "cancelled_by_participant"):
            return True
        # Use end_time (start + duration) as the real boundary
        start_dt = _parse_dt(i.get("sort_date", ""))
        if start_dt:
            end_dt = start_dt + timedelta(minutes=i.get("duration_minutes", 60))
            return end_dt <= now_dt
        return i["sort_date"] < now_str

    action_required = sorted(
        [i for i in items if i["action_required"]],
        key=lambda x: x["sort_date"]
    )
    upcoming = sorted(
        [i for i in items if not i["action_required"] and not _is_past_item(i)],
        key=lambda x: x["sort_date"]
    )
    past = sorted(
        [i for i in items if _is_past_item(i) and not i["action_required"]],
        key=lambda x: x["sort_date"],
        reverse=True
    )

    return {
        "action_required": action_required,
        "upcoming": upcoming,
        "past": past,
        "counts": {
            "action_required": len(action_required),
            "upcoming": len(upcoming),
            "past": len(past),
            "total": len(items),
        }
    }



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


@router.get("/analytics/stats")
async def get_analytics_stats(workspace_id: str = None, request: Request = None):
    """Return KPI stats for the organizer analytics dashboard."""
    user = await get_current_user(request)

    # Resolve workspace IDs
    if workspace_id:
        membership = db.workspace_memberships.find_one(
            {"workspace_id": workspace_id, "user_id": user['user_id']}, {"_id": 0}
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Accès refusé")
        ws_ids = [workspace_id]
    else:
        memberships = list(db.workspace_memberships.find({"user_id": user['user_id']}, {"_id": 0}))
        ws_ids = [m['workspace_id'] for m in memberships]

    base_query = {"workspace_id": {"$in": ws_ids}, "status": {"$ne": "deleted"}}

    # --- KPI 1: Engagements créés ---
    total_engagements = db.appointments.count_documents(base_query)

    # Get all appointment IDs for participant queries
    apt_ids = [a['appointment_id'] for a in db.appointments.find(base_query, {"_id": 0, "appointment_id": 1})]

    # --- KPI 2: Taux de présence ---
    # Based on attendance evaluation outcomes: on_time/late = present, no_show = absent
    # Only count appointments where evaluation happened (past appointments with results)
    attendance_records = list(db.attendance_evaluations.find(
        {"appointment_id": {"$in": apt_ids}},
        {"_id": 0, "outcome": 1}
    ))
    present_count = sum(1 for r in attendance_records if r.get('outcome') in ('on_time', 'late', 'waived'))
    absent_count = sum(1 for r in attendance_records if r.get('outcome') == 'no_show')
    attendance_total = present_count + absent_count
    presence_rate = round((present_count / attendance_total * 100), 1) if attendance_total > 0 else None

    # --- KPI 3: Taux d'acceptation ---
    # accepted_* / total invited (exclude participants in cancelled/deleted appointments)
    all_participants = list(db.participants.find(
        {"appointment_id": {"$in": apt_ids}},
        {"_id": 0, "status": 1}
    ))
    accepted_statuses = {'accepted', 'accepted_pending_guarantee', 'accepted_guaranteed', 'guarantee_released'}
    total_invited = len(all_participants)
    total_accepted = sum(1 for p in all_participants if p.get('status') in accepted_statuses)
    acceptance_rate = round((total_accepted / total_invited * 100), 1) if total_invited > 0 else None

    # --- KPI 4: Dédommagement personnel (compensation to organizer from captured guarantees) ---
    distributions = list(db.distributions.find(
        {"appointment_id": {"$in": apt_ids}},
        {"_id": 0, "capture_amount_cents": 1, "affected_compensation_percent": 1,
         "platform_commission_percent": 1, "charity_percent": 1,
         "no_show_is_organizer": 1, "status": 1}
    ))
    personal_compensation_cents = 0
    charity_total_cents = 0
    organizer_penalties_cents = 0

    for dist in distributions:
        amount = dist.get('capture_amount_cents', 0)
        commission = dist.get('platform_commission_percent', 20)
        compensation_pct = dist.get('affected_compensation_percent', 50)
        charity_pct = dist.get('charity_percent', 0)

        net_after_commission = amount * (1 - commission / 100)

        if dist.get('no_show_is_organizer'):
            # Organizer was the no-show → this is an organizer penalty
            organizer_penalties_cents += amount
        else:
            # Participant was the no-show → organizer gets compensation
            personal_compensation_cents += int(net_after_commission * compensation_pct / 100)

        charity_total_cents += int(net_after_commission * charity_pct / 100)

    # --- KPI 5: Impact caritatif ---
    # Already computed above

    # --- KPI 6: Engagements non honorés par l'organisateur ---
    # Cancelled by organizer + organizer no-shows
    cancelled_by_org = db.appointments.count_documents({
        **base_query,
        "status": "cancelled",
        "cancelled_by": "organizer"
    })
    organizer_no_shows = sum(1 for d in distributions if d.get('no_show_is_organizer'))
    organizer_defaults = cancelled_by_org + organizer_no_shows

    # --- Global message ---
    if presence_rate is not None:
        if presence_rate >= 85:
            global_message = "Vos engagements fonctionnent très bien"
            global_tone = "positive"
        elif presence_rate >= 65:
            global_message = "Vos engagements fonctionnent correctement"
            global_tone = "neutral"
        else:
            global_message = "Certains engagements nécessitent votre attention"
            global_tone = "warning"
    elif total_engagements > 0:
        global_message = "En attente des premiers résultats de présence"
        global_tone = "neutral"
    else:
        global_message = "Créez votre premier engagement pour commencer"
        global_tone = "neutral"

    return {
        "total_engagements": total_engagements,
        "presence_rate": presence_rate,
        "acceptance_rate": acceptance_rate,
        "personal_compensation_cents": personal_compensation_cents,
        "charity_total_cents": charity_total_cents,
        "organizer_defaults": organizer_defaults,
        "organizer_penalties_cents": organizer_penalties_cents,
        "currency": "eur",
        "global_message": global_message,
        "global_tone": global_tone,
    }


@router.get("/{appointment_id}")
async def get_appointment(appointment_id: str, request: Request):
    user = await get_current_user(request)
    
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    
    # Check access: workspace member OR participant of this appointment
    viewer_role = None
    membership = db.workspace_memberships.find_one({
        "workspace_id": appointment['workspace_id'],
        "user_id": user['user_id']
    }, {"_id": 0})
    
    if membership:
        viewer_role = "organizer"
    else:
        # Check if user is a participant (by user_id or email)
        participant_match = db.participants.find_one({
            "appointment_id": appointment_id,
            "$or": [
                {"user_id": user["user_id"]},
                {"email": user.get("email", "")}
            ]
        }, {"_id": 0, "participant_id": 1, "invitation_token": 1, "status": 1})
        
        if participant_match:
            viewer_role = "participant"
    
    if not viewer_role:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    # Normalize legacy naive datetimes to UTC on read
    if appointment.get('start_datetime'):
        appointment['start_datetime'] = normalize_to_utc(appointment['start_datetime'])
    
    appointment['viewer_role'] = viewer_role
    if viewer_role == "participant" and participant_match:
        appointment['viewer_participant_id'] = participant_match.get('participant_id')
        appointment['viewer_invitation_token'] = participant_match.get('invitation_token')
        appointment['viewer_participant_status'] = participant_match.get('status')
    
    # Include financial data if attendance has been evaluated
    if appointment.get('attendance_evaluated'):
        att_records = list(db.attendance_records.find(
            {"appointment_id": appointment_id},
            {"_id": 0}
        ))
        appointment['attendance_records'] = att_records

        distributions = list(db.distributions.find(
            {"appointment_id": appointment_id},
            {"_id": 0}
        ))
        appointment['distributions'] = distributions

        # Build compensation received map: user_id → total cents received
        compensation_map = {}  # user_id → { amount_cents, role, from_participant_id }
        for dist in distributions:
            for b in dist.get('beneficiaries', []):
                uid = b.get('user_id')
                if uid and uid not in ('__nlyt_platform__',) and b.get('role') != 'platform':
                    if uid not in compensation_map:
                        compensation_map[uid] = {
                            'total_cents': 0,
                            'role': b.get('role'),
                            'from_participant_id': dist.get('no_show_participant_id'),
                        }
                    compensation_map[uid]['total_cents'] += b.get('amount_cents', 0)

        # Build per-participant financial summary
        fin_summary = []
        for rec in att_records:
            pid = rec.get('participant_id')
            # Get participant's user_id for compensation lookup
            p_doc = db.participants.find_one(
                {"participant_id": pid},
                {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1}
            )
            p_user_id = p_doc.get('user_id') if p_doc else None

            guarantee = db.payment_guarantees.find_one(
                {"participant_id": pid, "appointment_id": appointment_id},
                {"_id": 0, "guarantee_id": 1, "status": 1, "penalty_amount": 1}
            )
            dist = None
            if guarantee:
                dist = db.distributions.find_one(
                    {"guarantee_id": guarantee['guarantee_id']},
                    {"_id": 0}
                )

            # Compensation received from OTHER participants' penalties
            comp = compensation_map.get(p_user_id)
            compensation_received_cents = comp['total_cents'] if comp else 0
            compensation_role = comp['role'] if comp else None

            fin_summary.append({
                "participant_id": pid,
                "outcome": rec.get('outcome'),
                "review_required": rec.get('review_required', False),
                "decision_basis": rec.get('decision_basis'),
                "delay_minutes": rec.get('delay_minutes'),
                "tolerated_delay_minutes": rec.get('tolerated_delay_minutes'),
                "guarantee_status": guarantee.get('status') if guarantee else None,
                "penalty_amount": guarantee.get('penalty_amount') if guarantee else None,
                "captured": guarantee.get('status') == 'captured' if guarantee else False,
                "distribution_id": dist.get('distribution_id') if dist else None,
                "distribution_status": dist.get('status') if dist else None,
                "capture_amount_cents": dist.get('capture_amount_cents') if dist else None,
                "beneficiaries": dist.get('beneficiaries', []) if dist else [],
                "compensation_received_cents": compensation_received_cents,
                "compensation_role": compensation_role,
            })
        appointment['financial_summary'] = fin_summary
    
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
        "charity_association_id", "event_reminders", "gps_radius_meters"
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

    # If appointment was converted from an external event, revert to "imported"
    converted_from = appointment.get("converted_from")
    if converted_from and converted_from.get("external_event_id"):
        db.external_events.update_one(
            {
                "external_event_id": converted_from["external_event_id"],
                "status": "converted",
            },
            {"$set": {
                "status": "imported",
                "nlyt_appointment_id": None,
                "converted_at": None,
            }}
        )
        # Remove the adopted sync_log
        db.calendar_sync_logs.delete_many({
            "appointment_id": appointment_id,
            "sync_source": "adopted",
        })
        print(f"[DELETE] Reverted external event {converted_from['external_event_id']} to imported")

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
            has_account = db.users.count_documents({"email": p["email"], "is_verified": True}) > 0
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
                has_existing_account=has_account,
            )
            sent += 1
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Remind email failed for {p.get('email')}: {e}")

    return {"success": True, "reminded": sent, "total_pending": len(pending)}
