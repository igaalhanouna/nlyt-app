"""
Declarative Attendance Service — V3 Trustless Collaborative Presence Sheets

Handles:
- Initialize declarative phase after evaluation
- Collect attendance sheets from participants
- Analyze declaration matrix (unanimity, coherence, contradictions)
- Auto-resolve or open disputes
- Deadline enforcement
"""
import uuid
import logging
from datetime import timedelta
from database import db
from utils.date_utils import now_utc

logger = logging.getLogger(__name__)

SHEET_DEADLINE_HOURS = 48
SHEET_REMINDER_HOURS = 24
DISPUTE_DEADLINE_DAYS = 7
MIN_TIERS_EXPRESSED = 2

# Statuts de participants considérés comme terminaux / hors-jeu.
# Un participant dans l'un de ces statuts ne constitue plus une cible
# pertinente pour une feuille de présence.
TERMINAL_PARTICIPANT_STATUSES = frozenset({
    'cancelled_by_participant', 'declined', 'guarantee_released',
})

# Statuts de déclaration considérés comme positifs (présence confirmée).
POSITIVE_DECLARATION_STATUSES = frozenset({'present_on_time', 'present_late'})


# ═══════════════════════════════════════════════════════════════════
# Phase initialization
# ═══════════════════════════════════════════════════════════════════

def initialize_declarative_phase(appointment_id: str):
    """
    Called after evaluate_appointment() when manual_review records exist.
    Creates pending attendance sheets for each participant.

    V5.1: Only `accepted_guaranteed` participants enter the declarative phase.
    Non-guaranteed participants in manual_review are auto-resolved to `waived`.
    If fewer than 2 guaranteed participants remain, phase = `not_needed`.
    Targeted participants also get a self-declaration target.
    """
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        return

    # ── Idempotency guard ──────────────────────────────────────────
    current_phase = appointment.get('declarative_phase')
    if current_phase and current_phase not in ('not_needed',):
        logger.warning(
            f"[DECLARATIVE][GUARD] Re-entry blocked for {appointment_id}. "
            f"Phase already '{current_phase}'. Skipping re-initialization."
        )
        return

    participants = list(db.participants.find(
        {"appointment_id": appointment_id},
        {"_id": 0}
    ))
    active_participants = [
        p for p in participants
        if p.get('status') in ('accepted', 'accepted_pending_guarantee', 'accepted_guaranteed')
        or p.get('user_id') == appointment.get('organizer_id')
    ]

    # Get manual_review records (only these need declaration)
    review_records = list(db.attendance_records.find(
        {"appointment_id": appointment_id, "review_required": True, "outcome": "manual_review"},
        {"_id": 0}
    ))
    if not review_records:
        db.appointments.update_one(
            {"appointment_id": appointment_id},
            {"$set": {"declarative_phase": "not_needed"}}
        )
        return

    # ── V5.1: Filter to guaranteed participants only ───────────────
    # Non-guaranteed participants in manual_review are immediately
    # auto-resolved to `waived`. They will NOT generate pending sheets,
    # feed disputes, appear in admin arbitration, or trigger penalties.
    guaranteed_review_records = []
    auto_waived_pids = set()

    for r in review_records:
        pid = r['participant_id']
        p_doc = db.participants.find_one(
            {"participant_id": pid},
            {"_id": 0, "status": 1}
        )
        if p_doc and p_doc.get('status') == 'accepted_guaranteed':
            guaranteed_review_records.append(r)
        else:
            auto_waived_pids.add(pid)
            db.attendance_records.update_one(
                {"appointment_id": appointment_id, "participant_id": pid},
                {"$set": {
                    "outcome": "waived",
                    "review_required": False,
                    "decision_source": "non_guaranteed_auto_waived",
                    "confidence_level": "HIGH",
                    "decided_by": "engine_guard",
                    "decided_at": now_utc().isoformat(),
                }}
            )
            logger.info(
                f"[DECLARATIVE][GUARD] Non-guaranteed participant {pid} "
                f"auto-resolved to waived (status: {p_doc.get('status') if p_doc else 'unknown'})"
            )

    # If fewer than 2 guaranteed participants remain, skip declarative phase
    if len(guaranteed_review_records) < 2:
        # Also waive the remaining guaranteed participants — no sheets will ever
        # be created for them, so leaving them in manual_review would create
        # phantom "review pending" badges in the financial UI.
        for r in guaranteed_review_records:
            pid = r['participant_id']
            db.attendance_records.update_one(
                {"appointment_id": appointment_id, "participant_id": pid},
                {"$set": {
                    "outcome": "waived",
                    "review_required": False,
                    "decision_source": "insufficient_guaranteed_participants",
                    "confidence_level": "HIGH",
                    "decided_by": "engine_guard",
                    "decided_at": now_utc().isoformat(),
                }}
            )
            logger.info(
                f"[DECLARATIVE][GUARD] Remaining guaranteed participant {pid} "
                f"auto-resolved to waived (< 2 guaranteed for declarative phase)"
            )

        db.appointments.update_one(
            {"appointment_id": appointment_id},
            {"$set": {"declarative_phase": "not_needed"}}
        )
        logger.info(
            f"[DECLARATIVE] Only {len(guaranteed_review_records)} guaranteed participant(s) "
            f"in manual_review for {appointment_id}. Phase set to not_needed. "
            f"Auto-waived: {len(auto_waived_pids)}"
        )
        return

    # Replace review_records with guaranteed-only set
    review_records = guaranteed_review_records

    # Exclude auto-waived participants from sheet creators
    active_participants = [
        p for p in active_participants
        if p.get('participant_id') not in auto_waived_pids
    ]

    review_pids = {r['participant_id'] for r in review_records}
    deadline = now_utc() + timedelta(hours=SHEET_DEADLINE_HOURS)
    sheets_created = 0

    # Create one sheet per active participant
    for p in active_participants:
        p_user_id = p.get('user_id')
        p_pid = p.get('participant_id')
        p_email = p.get('email', '')

        # EQUITY FIX: Do NOT skip participants without user_id.
        # They get a sheet linked by participant_id. When they create an account,
        # auto-linkage fills in submitted_by_user_id at login.

        # Use user_id if available, otherwise use email as placeholder identifier
        sheet_owner_id = p_user_id or p_email or p_pid

        existing = db.attendance_sheets.find_one({
            "appointment_id": appointment_id,
            "submitted_by_participant_id": p_pid,
        })
        if existing:
            continue

        # Targets = participants in manual_review, excluding self
        targets = []
        for r in review_records:
            if r['participant_id'] == p_pid:
                continue
            # Skip targets whose participant status is terminal
            tp = db.participants.find_one(
                {"participant_id": r['participant_id']},
                {"_id": 0, "status": 1}
            )
            if tp and tp.get('status') in TERMINAL_PARTICIPANT_STATUSES:
                continue
            targets.append({
                "target_participant_id": r['participant_id'],
                "target_user_id": _get_user_id(r['participant_id']),
                "declared_status": None,
                "is_self_declaration": False,
            })

        # Self-declaration: if THIS participant is in manual_review, add themselves
        # BUT only if there are already relevant non-self targets.
        # Self-declaration alone doesn't resolve a real dispute.
        if p_pid in review_pids and targets:
            targets.append({
                "target_participant_id": p_pid,
                "target_user_id": p_user_id or '',
                "declared_status": None,
                "is_self_declaration": True,
            })

        if not targets:
            continue

        db.attendance_sheets.insert_one({
            "sheet_id": str(uuid.uuid4()),
            "appointment_id": appointment_id,
            "submitted_by_user_id": sheet_owner_id,
            "submitted_by_participant_id": p_pid,
            "status": "pending",
            "submitted_at": None,
            "declarations": targets,
            "created_at": now_utc().isoformat(),
            "deadline": deadline.isoformat(),
        })
        sheets_created += 1

    # If no sheets were created (all targets were terminal), phase is not needed
    if sheets_created == 0:
        db.appointments.update_one(
            {"appointment_id": appointment_id},
            {"$set": {"declarative_phase": "not_needed"}}
        )
        logger.info(f"[DECLARATIVE] No relevant targets for {appointment_id}. "
                     f"All non-self targets are in terminal status. Phase set to not_needed.")
        return

    db.appointments.update_one(
        {"appointment_id": appointment_id},
        {"$set": {
            "declarative_phase": "collecting",
            "declarative_deadline": deadline.isoformat(),
        }}
    )
    logger.info(f"[DECLARATIVE] Phase initialized for {appointment_id}. "
                f"{len(review_records)} records in review, {sheets_created} sheets created, "
                f"{len(active_participants)} active participants. "
                f"Deadline: {deadline.isoformat()}")

    # EQUITY: Notify all participants who have a pending sheet
    try:
        all_sheets = list(db.attendance_sheets.find(
            {"appointment_id": appointment_id, "status": "pending"},
            {"_id": 0}
        ))
        from services.notification_service import notify_sheets_created
        notify_sheets_created(appointment_id, all_sheets)
    except Exception as e:
        logger.warning(f"[DECLARATIVE] Failed to send sheet notifications for {appointment_id}: {e}")


def _get_user_id(participant_id: str) -> str:
    p = db.participants.find_one({"participant_id": participant_id}, {"_id": 0, "user_id": 1, "email": 1})
    if not p:
        return ''
    if p.get('user_id'):
        return p['user_id']
    # Fallback: resolve from email → user account
    if p.get('email'):
        user = db.users.find_one({"email": p['email']}, {"_id": 0, "user_id": 1})
        if user and user.get('user_id'):
            # Persist the link for future lookups
            db.participants.update_one(
                {"participant_id": participant_id},
                {"$set": {"user_id": user['user_id']}}
            )
            return user['user_id']
    return ''


def _has_negative_tech_evidence(target_pid: str, appointment_id: str) -> bool:
    """Check for explicit negative technical evidence against a participant.

    Principle: 'absence of evidence is NOT evidence of absence'.
    Only returns True if concrete tech signals indicate absence.
    manual_review alone = inconclusive, NOT negative.
    Evidence items (GPS, video, check-in) are POSITIVE presence indicators.
    """
    record = db.attendance_records.find_one(
        {"appointment_id": appointment_id, "participant_id": target_pid},
        {"_id": 0}
    )
    if not record:
        return False
    tech_details = record.get("tech_evaluation") or {}
    if isinstance(tech_details, dict) and tech_details.get("negative_signal"):
        return True
    return False


# ═══════════════════════════════════════════════════════════════════
# Sheet submission
# ═══════════════════════════════════════════════════════════════════

def submit_sheet(appointment_id: str, user_id: str, declarations: list) -> dict:
    """
    Submit a participant's attendance sheet.
    declarations: [{"target_participant_id": "...", "declared_status": "present_on_time"|"present_late"|"absent"|"unknown"}]
    """
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        return {"error": "Rendez-vous introuvable"}

    if appointment.get('declarative_phase') != 'collecting':
        return {"error": "La phase de déclaration n'est pas active pour ce rendez-vous"}

    sheet = db.attendance_sheets.find_one({
        "appointment_id": appointment_id,
        "submitted_by_user_id": user_id,
    })
    # Fallback: look up by participant_id if user was recently auto-linked
    if not sheet:
        participant = db.participants.find_one(
            {"user_id": user_id, "appointment_id": appointment_id},
            {"_id": 0, "participant_id": 1}
        )
        if participant:
            sheet = db.attendance_sheets.find_one({
                "appointment_id": appointment_id,
                "submitted_by_participant_id": participant["participant_id"],
            })
            # Fix the sheet's user_id linkage for future lookups
            if sheet:
                db.attendance_sheets.update_one(
                    {"sheet_id": sheet["sheet_id"]},
                    {"$set": {"submitted_by_user_id": user_id}}
                )
    if not sheet:
        return {"error": "Aucune feuille de présence trouvée pour cet utilisateur"}

    if sheet.get('status') == 'submitted':
        return {"error": "Vous avez déjà soumis votre feuille de présence"}

    valid_statuses = ('present_on_time', 'present_late', 'absent', 'unknown')
    valid_targets = {d['target_participant_id'] for d in sheet['declarations']}

    # Build lookup for preserved fields from original declarations
    original_decl_map = {
        d['target_participant_id']: d for d in sheet['declarations']
    }

    updated_declarations = []
    for decl in declarations:
        tid = decl.get('target_participant_id')
        status = decl.get('declared_status')
        if tid not in valid_targets:
            return {"error": f"Participant cible invalide: {tid}"}
        if status not in valid_statuses:
            return {"error": f"Statut invalide: {status}. Valeurs: {', '.join(valid_statuses)}"}
        original = original_decl_map.get(tid, {})
        updated_declarations.append({
            "target_participant_id": tid,
            "target_user_id": original.get('target_user_id', ''),
            "declared_status": status,
            "is_self_declaration": original.get('is_self_declaration', False),
        })

    # Verify all targets are covered
    submitted_targets = {d['target_participant_id'] for d in updated_declarations}
    if submitted_targets != valid_targets:
        missing = valid_targets - submitted_targets
        return {"error": f"Déclarations manquantes pour: {', '.join(missing)}"}

    db.attendance_sheets.update_one(
        {"sheet_id": sheet['sheet_id']},
        {"$set": {
            "status": "submitted",
            "submitted_at": now_utc().isoformat(),
            "declarations": updated_declarations,
        }}
    )

    logger.info(f"[DECLARATIVE] Sheet submitted by {user_id} for {appointment_id}")

    # Check if all sheets are submitted → trigger analysis
    _check_and_trigger_analysis(appointment_id)

    return {"success": True, "message": "Feuille de présence enregistrée"}


def _check_and_trigger_analysis(appointment_id: str):
    """Check if all sheets submitted or deadline reached, then analyze."""
    total = db.attendance_sheets.count_documents({"appointment_id": appointment_id})
    submitted = db.attendance_sheets.count_documents({"appointment_id": appointment_id, "status": "submitted"})

    if submitted >= total:
        logger.info(f"[DECLARATIVE][TRIGGER] {appointment_id}: all sheets submitted ({submitted}/{total}) → triggering _run_analysis")
        _run_analysis(appointment_id)
    else:
        logger.info(f"[DECLARATIVE][WAITING] {appointment_id}: {submitted}/{total} sheets submitted — waiting for remaining")


# ═══════════════════════════════════════════════════════════════════
# Declaration analysis
# ═══════════════════════════════════════════════════════════════════

def _run_analysis(appointment_id: str):
    """Analyze all sheets and resolve or open disputes.

    V4: Two analysis paths:
    - Large groups (>= 3 participants): cross-declaration unanimity check
    - Small groups (< 3 participants): direct comparison including self-declarations

    Idempotent: uses atomic CAS to transition collecting → analyzing.
    Any phase other than 'collecting' is blocked (already analyzed or in progress).
    """
    # ── Atomic CAS: collecting → analyzing ──────────────────────
    # Only ONE caller can transition. Prevents double-analysis from
    # concurrent _check_and_trigger_analysis calls or deadline job.
    cas_result = db.appointments.update_one(
        {"appointment_id": appointment_id, "declarative_phase": "collecting"},
        {"$set": {
            "declarative_phase": "analyzing",
            "declarative_analyzing_started_at": now_utc().isoformat(),
        }}
    )
    if cas_result.modified_count == 0:
        current = db.appointments.find_one(
            {"appointment_id": appointment_id},
            {"_id": 0, "declarative_phase": 1}
        )
        current_phase = current.get("declarative_phase") if current else "N/A"
        logger.warning(
            f"[DECLARATIVE][GUARD] _run_analysis blocked for {appointment_id}. "
            f"Phase is '{current_phase}', expected 'collecting'. Skipping double-analysis."
        )
        return

    logger.info(f"[DECLARATIVE][ANALYSIS_START] {appointment_id}: CAS collecting→analyzing acquired")

    sheets = list(db.attendance_sheets.find({"appointment_id": appointment_id}, {"_id": 0}))
    submitted_sheets = [s for s in sheets if s['status'] == 'submitted']

    review_records = list(db.attendance_records.find(
        {"appointment_id": appointment_id, "review_required": True, "outcome": "manual_review"},
        {"_id": 0}
    ))

    if not review_records:
        db.appointments.update_one(
            {"appointment_id": appointment_id},
            {"$set": {"declarative_phase": "resolved"}}
        )
        return

    # Determine group size
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    participants = list(db.participants.find({"appointment_id": appointment_id}, {"_id": 0}))
    active_count = len([
        p for p in participants
        if p.get('status') in ('accepted', 'accepted_pending_guarantee', 'accepted_guaranteed')
        or p.get('user_id') == (appointment or {}).get('organizer_id')
    ])

    if active_count < 3:
        per_participant_results = _run_small_group_analysis(appointment_id, review_records, submitted_sheets)
    else:
        per_participant_results = _run_large_group_analysis(appointment_id, review_records, submitted_sheets)

    # Store analysis
    db.declarative_analyses.insert_one({
        "analysis_id": str(uuid.uuid4()),
        "appointment_id": appointment_id,
        "analyzed_at": now_utc().isoformat(),
        "group_size": active_count,
        "per_participant": per_participant_results,
    })

    # Apply results
    any_dispute = False
    for result in per_participant_results:
        if result['auto_resolvable']:
            _apply_declarative_outcome(appointment_id, result)
        else:
            dispute_id = open_dispute(appointment_id, result['target_participant_id'], result.get('reason_if_not', 'unknown'))
            if dispute_id is not None:
                any_dispute = True

    new_phase = "disputed" if any_dispute else "resolved"
    db.appointments.update_one(
        {"appointment_id": appointment_id},
        {"$set": {"declarative_phase": new_phase}}
    )
    logger.info(
        f"[DECLARATIVE][PHASE_TRANSITION] {appointment_id}: analyzing→{new_phase} "
        f"(disputes={sum(1 for r in per_participant_results if not r['auto_resolvable'])}, "
        f"auto_resolved={sum(1 for r in per_participant_results if r['auto_resolvable'])}, "
        f"group_size={active_count})"
    )

    if new_phase == "resolved":
        from services.attendance_service import reset_cas_a_overrides, _process_financial_outcomes
        reset_cas_a_overrides(appointment_id)
        appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
        participants = list(db.participants.find({"appointment_id": appointment_id}, {"_id": 0}))
        _process_financial_outcomes(
            appointment_id, appointment, participants,
            immediate_release=True, release_reason="consensus",
        )
        logger.info(f"[DECLARATIVE] All manual_reviews resolved for {appointment_id}. Financial engine relaunched (immediate release: consensus).")


def _run_small_group_analysis(appointment_id: str, review_records: list, submitted_sheets: list) -> list:
    """For < 3 participants: direct comparison of ALL declarations including self-declarations.

    V5 Rules:
    - 0 expressed (all unknown) + no negative tech evidence -> waived (presumption)
    - 0 expressed + negative tech evidence -> dispute
    - All expressed positive (present_on_time/present_late) -> auto-resolve
    - Any 'absent' signal -> dispute
    - Mix present/absent -> dispute
    """
    results = []
    for record in review_records:
        target_pid = record['participant_id']

        all_declarations = []
        for s in submitted_sheets:
            for d in s.get('declarations', []):
                if d['target_participant_id'] == target_pid and d.get('declared_status') not in (None, 'unknown'):
                    all_declarations.append({
                        'declared_status': d['declared_status'],
                        'is_self': d.get('is_self_declaration', False),
                        'submitted_by': s.get('submitted_by_participant_id'),
                    })

        if not all_declarations:
            # 0 expressed — apply presumption rule
            has_neg_tech = _has_negative_tech_evidence(target_pid, appointment_id)
            if has_neg_tech:
                results.append({
                    "target_participant_id": target_pid,
                    "tiers_expressed_count": 0,
                    "auto_resolvable": False,
                    "reason_if_not": "negative_tech_with_no_declarations",
                    "confidence_level": "LOW",
                })
            else:
                logger.info(
                    f"[DECLARATIVE][PRESUMPTION] {target_pid}: 0 expressed, no negative tech "
                    f"-> waived (small group, appointment {appointment_id})"
                )
                results.append({
                    "target_participant_id": target_pid,
                    "tiers_expressed_count": 0,
                    "auto_resolvable": True,
                    "unanimous_status": "waived",
                    "confidence_level": "LOW",
                })
            continue

        statuses = set(d['declared_status'] for d in all_declarations)
        has_negative = 'absent' in statuses

        if has_negative:
            # Any absent signal -> dispute (whether unanimous absent or mixed)
            reason = "unanimous_absence" if len(statuses) == 1 else "small_group_disagreement"
            results.append({
                "target_participant_id": target_pid,
                "tiers_expressed_count": len(all_declarations),
                "tiers_unanimous": len(statuses) == 1,
                "auto_resolvable": False,
                "reason_if_not": reason,
                "confidence_level": "LOW",
            })
        elif statuses <= POSITIVE_DECLARATION_STATUSES:
            # All expressed are positive — auto-resolve
            if len(statuses) == 1:
                agreed_status = statuses.pop()
            else:
                # Mixed positive (on_time + late): default to on_time (presence confirmed)
                agreed_status = 'present_on_time'
            results.append({
                "target_participant_id": target_pid,
                "tiers_expressed_count": len(all_declarations),
                "tiers_unanimous": True,
                "unanimous_status": agreed_status,
                "auto_resolvable": True,
                "confidence_level": "MEDIUM",
            })
        else:
            # Unknown status value — dispute (safety)
            results.append({
                "target_participant_id": target_pid,
                "tiers_expressed_count": len(all_declarations),
                "tiers_unanimous": False,
                "auto_resolvable": False,
                "reason_if_not": "small_group_disagreement",
                "confidence_level": "LOW",
            })

    return results


def _run_large_group_analysis(appointment_id: str, review_records: list, submitted_sheets: list) -> list:
    """For >= 3 participants: cross-declaration analysis with unanimity and coherence checks.
    Self-declarations are EXCLUDED (tiers only).

    V5 Rules:
    - 0 expressed + no neg tech -> waived
    - 1 expressed positive + no neg tech -> waived (insufficient for on_time)
    - 1 expressed negative -> dispute
    - >=2 unanimous positive -> on_time/late (auto-resolve)
    - >=2 unanimous absent -> existing contradiction checks -> no_show or dispute
    - >=2 disagreement -> dispute
    """
    global_coherence = _check_global_coherence(submitted_sheets)

    results = []
    for record in review_records:
        target_pid = record['participant_id']
        unanimity = _check_unanimity(target_pid, submitted_sheets)
        expressed_count = unanimity.get('expressed_count', 0)

        # -- Case 1: 0 expressed (all unknown) --
        if expressed_count == 0:
            has_neg_tech = _has_negative_tech_evidence(target_pid, appointment_id)
            if has_neg_tech:
                results.append({
                    "target_participant_id": target_pid,
                    "tiers_expressed_count": 0,
                    "tiers_unanimous": False,
                    "auto_resolvable": False,
                    "reason_if_not": "negative_tech_with_no_declarations",
                    "confidence_level": "LOW",
                })
            else:
                logger.info(
                    f"[DECLARATIVE][PRESUMPTION] {target_pid}: 0 tiers expressed, no negative tech "
                    f"-> waived (large group, appointment {appointment_id})"
                )
                results.append({
                    "target_participant_id": target_pid,
                    "tiers_expressed_count": 0,
                    "tiers_unanimous": False,
                    "unanimous_status": "waived",
                    "auto_resolvable": True,
                    "confidence_level": "LOW",
                })
            continue

        # -- Case 2: 1 single expressed --
        if unanimity.get('reason') == 'single_expressed':
            single_status = unanimity.get('status')
            if single_status == 'absent':
                # 1 negative signal -> dispute
                results.append({
                    "target_participant_id": target_pid,
                    "tiers_expressed_count": 1,
                    "tiers_unanimous": False,
                    "auto_resolvable": False,
                    "reason_if_not": "single_negative_signal",
                    "confidence_level": "LOW",
                })
            else:
                # 1 positive signal -> waived (not enough for on_time in large group)
                has_neg_tech = _has_negative_tech_evidence(target_pid, appointment_id)
                if has_neg_tech:
                    results.append({
                        "target_participant_id": target_pid,
                        "tiers_expressed_count": 1,
                        "tiers_unanimous": False,
                        "auto_resolvable": False,
                        "reason_if_not": "tech_contradicts_single_positive",
                        "confidence_level": "LOW",
                    })
                else:
                    logger.info(
                        f"[DECLARATIVE][PRESUMPTION] {target_pid}: 1 tiers says '{single_status}', "
                        f"no negative tech -> waived (large group, appointment {appointment_id})"
                    )
                    results.append({
                        "target_participant_id": target_pid,
                        "tiers_expressed_count": 1,
                        "tiers_unanimous": False,
                        "unanimous_status": "waived",
                        "auto_resolvable": True,
                        "confidence_level": "LOW",
                    })
            continue

        # -- Case 3: >=2 unanimous --
        if unanimity.get('unanimous'):
            status = unanimity.get('status')
            if status in POSITIVE_DECLARATION_STATUSES:
                # >=2 unanimous positive -> auto-resolve
                results.append({
                    "target_participant_id": target_pid,
                    "tiers_expressed_count": expressed_count,
                    "tiers_unanimous": True,
                    "unanimous_status": status,
                    "auto_resolvable": True,
                    "confidence_level": "MEDIUM",
                })
            elif status == 'absent':
                # >=2 unanimous absent -> existing contradiction checks
                contradiction = _check_contradiction_signals(
                    target_pid, unanimity, submitted_sheets, appointment_id
                )
                auto_ok = (
                    global_coherence.get('coherent', False)
                    and not contradiction.get('contradiction', False)
                )
                if auto_ok:
                    results.append({
                        "target_participant_id": target_pid,
                        "tiers_expressed_count": expressed_count,
                        "tiers_unanimous": True,
                        "unanimous_status": status,
                        "contestant_contradiction": False,
                        "collusion_detected": False,
                        "tech_signal_contradiction": False,
                        "auto_resolvable": True,
                        "confidence_level": "MEDIUM",
                    })
                else:
                    reasons = []
                    if not global_coherence.get('coherent'):
                        reasons.append(global_coherence.get('reason', 'incoherent'))
                    if contradiction.get('contradiction'):
                        reasons.append(contradiction.get('reason', 'contradiction'))
                    results.append({
                        "target_participant_id": target_pid,
                        "tiers_expressed_count": expressed_count,
                        "tiers_unanimous": True,
                        "unanimous_status": status,
                        "contestant_contradiction": contradiction.get('reason') == 'contestant_contradiction',
                        "collusion_detected": contradiction.get('reason') == 'collusion_signal',
                        "tech_signal_contradiction": contradiction.get('reason') == 'tech_signal_contradiction',
                        "auto_resolvable": False,
                        "reason_if_not": "; ".join(reasons),
                        "confidence_level": "LOW",
                    })
            else:
                # Other unanimous status -> auto-resolve
                results.append({
                    "target_participant_id": target_pid,
                    "tiers_expressed_count": expressed_count,
                    "tiers_unanimous": True,
                    "unanimous_status": status,
                    "auto_resolvable": True,
                    "confidence_level": "MEDIUM",
                })
            continue

        # -- Case 4: >=2 disagreement --
        results.append({
            "target_participant_id": target_pid,
            "tiers_expressed_count": expressed_count,
            "tiers_unanimous": False,
            "auto_resolvable": False,
            "reason_if_not": unanimity.get('reason', 'tiers_disagreement'),
            "confidence_level": "LOW",
        })

    return results


def _check_unanimity(target_pid: str, sheets: list) -> dict:
    """Check tiers declarations for target_pid.

    V5: Returns granular info for 0, 1, and >=2 expressed cases.
    """
    declarations = []
    for s in sheets:
        if s.get('submitted_by_participant_id') == target_pid:
            continue
        for d in s.get('declarations', []):
            if d['target_participant_id'] == target_pid:
                declarations.append(d)

    expressed = [d for d in declarations if d.get('declared_status') not in (None, 'unknown')]

    if len(expressed) == 0:
        return {"unanimous": False, "reason": "no_expressed", "expressed_count": 0}

    if len(expressed) == 1:
        return {
            "unanimous": False,
            "reason": "single_expressed",
            "expressed_count": 1,
            "status": expressed[0]['declared_status'],
        }

    statuses = set(d['declared_status'] for d in expressed)

    if len(statuses) == 1:
        return {"unanimous": True, "status": statuses.pop(), "expressed_count": len(expressed)}
    else:
        return {"unanimous": False, "reason": "tiers_disagreement", "expressed_count": len(expressed)}


def _check_global_coherence(sheets: list) -> dict:
    """Check for cross-accusations between participants."""
    # Build participant_id → {target_pid: declared_status} map
    decl_map = {}
    for s in sheets:
        submitter = s.get('submitted_by_participant_id')
        if not submitter:
            continue
        decl_map[submitter] = {}
        for d in s.get('declarations', []):
            decl_map[submitter][d['target_participant_id']] = d.get('declared_status')

    # Cross-accusation check: A says B absent AND B says A absent
    pids = list(decl_map.keys())
    for i, a in enumerate(pids):
        for b in pids[i + 1:]:
            a_says_b = decl_map.get(a, {}).get(b)
            b_says_a = decl_map.get(b, {}).get(a)
            if a_says_b == 'absent' and b_says_a == 'absent':
                return {"coherent": False, "reason": "cross_accusation", "pair": [a, b]}

    return {"coherent": True}


def _check_contradiction_signals(target_pid: str, unanimity: dict, sheets: list, appointment_id: str) -> dict:
    """Check for strong contradiction signals against the unanimity result."""
    if not unanimity.get('unanimous') or unanimity.get('status') != 'absent':
        return {"contradiction": False}

    # Signal A: contestant contradiction
    # Target submitted their sheet (they're active/aware) but tiers say absent
    target_sheet = next(
        (s for s in sheets if s.get('submitted_by_participant_id') == target_pid and s.get('status') == 'submitted'),
        None
    )
    if target_sheet:
        return {"contradiction": True, "reason": "contestant_contradiction"}

    # Signal B: tech signal contradiction
    # Any evidence exists for target (even weak) but declarative says absent
    evidence = list(db.evidence_items.find(
        {"participant_id": target_pid, "appointment_id": appointment_id},
        {"_id": 0}
    ))
    if evidence and len(evidence) > 0:
        return {"contradiction": True, "reason": "tech_signal_contradiction"}

    # Signal C: collusion pattern V1
    # All declarants who say "absent" are ALSO the only potential beneficiaries
    declarants_against = set()
    for s in sheets:
        if s.get('submitted_by_participant_id') == target_pid:
            continue
        for d in s.get('declarations', []):
            if d['target_participant_id'] == target_pid and d.get('declared_status') == 'absent':
                declarants_against.add(s['submitted_by_user_id'])

    # Beneficiaries = participants with on_time/late outcome (tech proven)
    # OR participants declared present by unanimity in this same analysis
    beneficiary_records = list(db.attendance_records.find(
        {"appointment_id": appointment_id, "outcome": {"$in": ["on_time", "late"]}, "review_required": False},
        {"_id": 0}
    ))
    beneficiary_user_ids = set()
    for r in beneficiary_records:
        p = db.participants.find_one({"participant_id": r['participant_id']}, {"_id": 0, "user_id": 1})
        if p:
            beneficiary_user_ids.add(p['user_id'])

    if declarants_against and declarants_against <= beneficiary_user_ids and len(declarants_against) == len(beneficiary_user_ids):
        return {"contradiction": True, "reason": "collusion_signal"}

    return {"contradiction": False}


# ═══════════════════════════════════════════════════════════════════
# Outcome application & dispute creation
# ═══════════════════════════════════════════════════════════════════

def _apply_declarative_outcome(appointment_id: str, result: dict):
    """Apply a declarative outcome to an attendance record."""
    target_pid = result['target_participant_id']
    declared = result.get('unanimous_status')

    outcome_map = {
        'present_on_time': 'on_time',
        'present_late': 'late',
        'absent': 'no_show',
        'waived': 'waived',
    }
    outcome = outcome_map.get(declared, 'manual_review')

    if outcome == 'manual_review':
        return

    decision_source = "declarative_presumption" if outcome == "waived" else "declarative"
    confidence = "LOW" if outcome == "waived" else result.get('confidence_level', 'MEDIUM')

    db.attendance_records.update_one(
        {"appointment_id": appointment_id, "participant_id": target_pid},
        {"$set": {
            "outcome": outcome,
            "review_required": False,
            "decision_source": decision_source,
            "confidence_level": confidence,
            "decided_by": "declarative_presumption" if outcome == "waived" else "declarative_consensus",
            "decided_at": now_utc().isoformat(),
            "declarative_details": {
                "tiers_expressed": result.get('tiers_expressed_count', 0),
                "unanimous_status": declared,
            }
        }}
    )
    logger.info(f"[DECLARATIVE] Applied {outcome} to {target_pid} ({decision_source}, {confidence} confidence)")


def open_dispute(appointment_id: str, target_participant_id: str, reason: str):
    """Create a symmetric dispute for a participant whose status cannot be auto-resolved.

    Trustless V4: both organizer and participant have equal power.
    Neither party can unilaterally impose a financial penalty.
    """
    existing = db.declarative_disputes.find_one({
        "appointment_id": appointment_id,
        "target_participant_id": target_participant_id,
    })
    if existing:
        return existing.get('dispute_id')

    target_user_id = _get_user_id(target_participant_id)
    appointment = db.appointments.find_one(
        {"appointment_id": appointment_id},
        {"_id": 0, "organizer_id": 1}
    )
    organizer_user_id = appointment.get("organizer_id") if appointment else None

    # ── GUARD: Auto-litige interdit ─────────────────────────────
    if target_user_id and organizer_user_id and target_user_id == organizer_user_id:
        logger.warning(
            f"[DISPUTE][GUARD] Auto-litige bloque pour {target_participant_id} "
            f"dans {appointment_id}: target_user_id == organizer_user_id ({target_user_id}). "
            f"Auto-resolution en 'waived'."
        )
        db.attendance_records.update_one(
            {"appointment_id": appointment_id, "participant_id": target_participant_id},
            {"$set": {
                "outcome": "waived",
                "review_required": False,
                "decision_source": "auto_no_self_dispute",
                "confidence_level": "LOW",
                "decided_by": "engine_guard",
                "decided_at": now_utc().isoformat(),
            }}
        )
        return None

    deadline = now_utc() + timedelta(days=DISPUTE_DEADLINE_DAYS)

    dispute = {
        "dispute_id": str(uuid.uuid4()),
        "appointment_id": appointment_id,
        "target_participant_id": target_participant_id,
        "target_user_id": target_user_id,
        "organizer_user_id": organizer_user_id,
        # Symmetric positions: null = not yet responded
        # Values: "confirmed_present" | "confirmed_absent" | "confirmed_late_penalized"
        "organizer_position": None,
        "organizer_position_at": None,
        "participant_position": None,
        "participant_position_at": None,
        "status": "awaiting_positions",
        "opened_at": now_utc().isoformat(),
        "opened_reason": reason,
        "resolution": {
            "resolved_at": None,
            "resolved_by": None,
            "final_outcome": None,
            "resolution_note": None,
        },
        "evidence_submissions": [],
        "escalated_at": None,
        "deadline": deadline.isoformat(),
        "created_at": now_utc().isoformat(),
    }
    db.declarative_disputes.insert_one(dispute)
    logger.info(f"[DISPUTE] Opened for {target_participant_id} in {appointment_id}: {reason}. Organizer: {organizer_user_id}")

    # Notification trigger: litige ouvert
    try:
        from services.notification_service import notify_dispute_opened
        apt = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0, "title": 1})
        notify_dispute_opened(dispute, apt.get("title", "") if apt else "")
    except Exception as e:
        logger.warning(f"[NOTIF] Failed to notify dispute opened: {e}")

    return dispute['dispute_id']


# ═══════════════════════════════════════════════════════════════════
# Dispute resolution
# ═══════════════════════════════════════════════════════════════════

def resolve_dispute(dispute_id: str, final_outcome: str, resolution_note: str, resolved_by: str = "platform"):
    """Resolve a dispute (by platform arbitration or new evidence)."""
    dispute = db.declarative_disputes.find_one({"dispute_id": dispute_id}, {"_id": 0})
    if not dispute:
        return {"error": "Litige introuvable"}

    if dispute['status'] == 'resolved':
        return {"error": "Ce litige est déjà résolu"}

    valid = ('on_time', 'late', 'late_penalized', 'no_show', 'waived')
    if final_outcome not in valid:
        return {"error": f"Outcome invalide: {final_outcome}"}

    db.declarative_disputes.update_one(
        {"dispute_id": dispute_id},
        {"$set": {
            "status": "resolved",
            "resolution": {
                "resolved_at": now_utc().isoformat(),
                "resolved_by": resolved_by,
                "final_outcome": final_outcome,
                "resolution_note": resolution_note,
            }
        }}
    )

    # Notification trigger: décision rendue
    try:
        from services.notification_service import notify_decision_rendered
        resolved_dispute = db.declarative_disputes.find_one({"dispute_id": dispute_id}, {"_id": 0})
        apt = db.appointments.find_one({"appointment_id": dispute['appointment_id']}, {"_id": 0, "title": 1})
        notify_decision_rendered(resolved_dispute, apt.get("title", "") if apt else "")
    except Exception as e:
        logger.warning(f"[NOTIF] Failed to notify decision rendered: {e}")

    # Apply to attendance record
    existing_record = db.attendance_records.find_one(
        {"appointment_id": dispute['appointment_id'], "participant_id": dispute['target_participant_id']},
        {"_id": 0, "outcome": 1}
    )

    db.attendance_records.update_one(
        {"appointment_id": dispute['appointment_id'], "participant_id": dispute['target_participant_id']},
        {"$set": {
            "outcome": final_outcome,
            "review_required": False,
            "decision_source": "dispute_resolved",
            "confidence_level": "MEDIUM",
            "decided_by": resolved_by,
            "decided_at": now_utc().isoformat(),
        }}
    )

    # Check if all disputes for this appointment are resolved
    appointment_id = dispute['appointment_id']
    open_disputes = db.declarative_disputes.count_documents({
        "appointment_id": appointment_id,
        "status": {"$ne": "resolved"}
    })

    if open_disputes == 0:
        db.appointments.update_one(
            {"appointment_id": appointment_id},
            {"$set": {"declarative_phase": "resolved"}}
        )
        # Reset Cas A overrides before re-triggering financial engine
        from services.attendance_service import reset_cas_a_overrides, _process_financial_outcomes
        reset_cas_a_overrides(appointment_id)
        appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
        participants = list(db.participants.find({"appointment_id": appointment_id}, {"_id": 0}))
        _process_financial_outcomes(
            appointment_id, appointment, participants,
            immediate_release=True, release_reason="admin_arbitration",
        )
        logger.info(f"[DISPUTE] All disputes resolved for {appointment_id}. Financial engine relaunched (immediate release: admin_arbitration).")

    # Non-blocking: send dispute resolution emails
    try:
        from services.financial_emails import send_dispute_resolution_emails
        send_dispute_resolution_emails(dispute_id)
    except Exception as e:
        logger.warning(f"[DISPUTE] Email notification error (non-blocking): {e}")

    return {"success": True}


def submit_dispute_position(dispute_id: str, user_id: str, position: str) -> dict:
    """Submit a party's position on a dispute. Both organizer and participant use this.

    Trustless V4: No penalty without double explicit confirmation.
    Positions: confirmed_present | confirmed_absent | confirmed_late_penalized
    """
    valid_positions = ("confirmed_present", "confirmed_absent", "confirmed_late_penalized")
    if position not in valid_positions:
        return {"error": f"Position invalide. Valeurs: {', '.join(valid_positions)}"}

    dispute = db.declarative_disputes.find_one({"dispute_id": dispute_id}, {"_id": 0})
    if not dispute:
        return {"error": "Litige introuvable"}

    if dispute.get("status") not in ("awaiting_positions",):
        return {"error": "Ce litige n'accepte plus de positions"}

    # Determine role
    is_organizer = (dispute.get("organizer_user_id") == user_id)
    is_participant = (dispute.get("target_user_id") == user_id)

    # Deadlock fix: when target = organizer, the counterpart gets participant role
    if not is_organizer and not is_participant:
        if (dispute.get("organizer_user_id") == dispute.get("target_user_id")):
            # Check if user is the true counterpart (submitted a declaration about the target)
            sheet = db.attendance_sheets.find_one({
                "appointment_id": dispute["appointment_id"],
                "submitted_by_user_id": user_id,
                "status": "submitted",
            }, {"_id": 0, "declarations": 1})
            if sheet and any(
                decl.get("target_participant_id") == dispute["target_participant_id"]
                for decl in sheet.get("declarations", [])
            ):
                is_participant = True

    if not is_organizer and not is_participant:
        return {"error": "Vous n'êtes pas partie prenante de ce litige"}

    if is_organizer:
        if dispute.get("organizer_position") is not None:
            return {"error": "Vous avez déjà soumis votre position"}
        db.declarative_disputes.update_one(
            {"dispute_id": dispute_id},
            {"$set": {
                "organizer_position": position,
                "organizer_position_at": now_utc().isoformat(),
            }}
        )
        logger.info(f"[DISPUTE] Organizer {user_id} submitted position '{position}' on {dispute_id}")
    else:
        if dispute.get("participant_position") is not None:
            return {"error": "Vous avez déjà soumis votre position"}
        db.declarative_disputes.update_one(
            {"dispute_id": dispute_id},
            {"$set": {
                "participant_position": position,
                "participant_position_at": now_utc().isoformat(),
            }}
        )
        logger.info(f"[DISPUTE] Participant {user_id} submitted position '{position}' on {dispute_id}")

    # Notification trigger: position soumise -> notifier l'autre partie
    try:
        from services.notification_service import notify_dispute_position_submitted
        updated = db.declarative_disputes.find_one({"dispute_id": dispute_id}, {"_id": 0})
        apt = db.appointments.find_one({"appointment_id": updated["appointment_id"]}, {"_id": 0, "title": 1})
        notify_dispute_position_submitted(updated, user_id, apt.get("title", "") if apt else "")
    except Exception as e:
        logger.warning(f"[NOTIF] Failed to notify position submitted: {e}")

    # Re-fetch and check if both positions are in → auto-resolve
    return _check_positions_and_resolve(dispute_id)


def _check_positions_and_resolve(dispute_id: str) -> dict:
    """Check if both positions are submitted and resolve accordingly.

    Decision matrix (Trustless V4):
    - Both confirm_present → resolved as on_time (guarantee released)
    - Both confirm_absent → resolved as no_show (penalty applied)
    - Both confirm_late_penalized → resolved as late_penalized (penalty applied)
    - Any disagreement → escalated to platform arbitration
    - Any silence (position = null) → wait (deadline job will escalate)

    CRITICAL: No penalty is EVER applied without double explicit confirmation.
    """
    dispute = db.declarative_disputes.find_one({"dispute_id": dispute_id}, {"_id": 0})
    if not dispute:
        return {"error": "Litige introuvable"}

    org_pos = dispute.get("organizer_position")
    par_pos = dispute.get("participant_position")

    # If one party hasn't responded yet, just acknowledge
    if org_pos is None or par_pos is None:
        return {"success": True, "message": "Position enregistrée. En attente de l'autre partie."}

    # Both have responded — apply decision matrix
    if org_pos == par_pos:
        # AGREEMENT
        outcome_map = {
            "confirmed_present": ("on_time", "agreed_present", "Accord mutuel : présence confirmée."),
            "confirmed_absent": ("no_show", "agreed_absent", "Accord mutuel : absence confirmée."),
            "confirmed_late_penalized": ("late_penalized", "agreed_late_penalized", "Accord mutuel : retard pénalisable confirmé."),
        }
        final_outcome, new_status, note = outcome_map[org_pos]

        db.declarative_disputes.update_one(
            {"dispute_id": dispute_id},
            {"$set": {"status": new_status}}
        )
        resolve_dispute(dispute_id, final_outcome, note, resolved_by="mutual_agreement")
        logger.info(f"[DISPUTE] {dispute_id} resolved by mutual agreement: {final_outcome}")
        return {"success": True, "message": note, "resolved": True, "outcome": final_outcome}
    else:
        # DISAGREEMENT → escalade automatique
        db.declarative_disputes.update_one(
            {"dispute_id": dispute_id},
            {"$set": {
                "status": "escalated",
                "escalated_at": now_utc().isoformat(),
            }}
        )
        logger.info(f"[DISPUTE] {dispute_id} escalated: organizer={org_pos}, participant={par_pos}")
        # Notification trigger: escalade
        try:
            from services.notification_service import notify_dispute_escalated
            escalated = db.declarative_disputes.find_one({"dispute_id": dispute_id}, {"_id": 0})
            apt = db.appointments.find_one({"appointment_id": escalated["appointment_id"]}, {"_id": 0, "title": 1})
            notify_dispute_escalated(escalated, apt.get("title", "") if apt else "")
        except Exception as e:
            logger.warning(f"[NOTIF] Failed to notify escalation: {e}")
        return {"success": True, "message": "Les positions divergent. Le dossier est transmis à un arbitre neutre.", "escalated": True}


def _get_user_declaration_for_target(appointment_id: str, user_id: str, target_pid: str) -> str:
    """Get what a user declared about a target in their attendance sheet."""
    sheet = db.attendance_sheets.find_one({
        "appointment_id": appointment_id,
        "submitted_by_user_id": user_id,
        "status": "submitted"
    }, {"_id": 0})
    if not sheet:
        return None
    for d in sheet.get('declarations', []):
        if d.get('target_participant_id') == target_pid:
            return d.get('declared_status')
    return None


def submit_dispute_evidence(dispute_id: str, user_id: str, evidence_type: str, content_url: str = None, text_content: str = None):
    """Submit complementary evidence for a dispute."""
    dispute = db.declarative_disputes.find_one({"dispute_id": dispute_id}, {"_id": 0})
    if not dispute:
        return {"error": "Litige introuvable"}
    if dispute['status'] not in ('awaiting_positions', 'awaiting_evidence', 'escalated'):
        return {"error": "Ce litige n'accepte plus de preuves complémentaires"}

    # Verify user is participant of this appointment
    participant = db.participants.find_one({
        "appointment_id": dispute['appointment_id'],
        "user_id": user_id
    })
    if not participant:
        return {"error": "Vous n'êtes pas participant de ce rendez-vous"}

    submission = {
        "submission_id": str(uuid.uuid4()),
        "submitted_by_user_id": user_id,
        "submitted_at": now_utc().isoformat(),
        "evidence_type": evidence_type,
        "content_url": content_url,
        "text_content": text_content,
    }

    db.declarative_disputes.update_one(
        {"dispute_id": dispute_id},
        {"$push": {"evidence_submissions": submission}}
    )
    return {"success": True, "submission_id": submission['submission_id']}


# ═══════════════════════════════════════════════════════════════════
# Scheduled jobs
# ═══════════════════════════════════════════════════════════════════

def run_declarative_deadline_job():
    """Force-close sheets that passed the 48h deadline and trigger analysis.
    Also monitors for stuck 'collecting' phases where all sheets are submitted
    but no analysis was triggered (safety net).
    """
    from datetime import datetime

    appointments = list(db.appointments.find(
        {"declarative_phase": "collecting"},
        {"_id": 0}
    ))

    now = now_utc()
    # BS-3 FIX: Detect and recover from stuck "analyzing" phases.
    # If an appointment has been in "analyzing" for > 30 minutes, it's considered stuck.
    # Reset to "collecting" so the normal analysis flow can retry.
    stuck_analyzing = list(db.appointments.find(
        {"declarative_phase": "analyzing"},
        {"_id": 0, "appointment_id": 1, "declarative_analyzing_started_at": 1, "updated_at": 1}
    ))
    for stuck in stuck_analyzing:
        stuck_apt_id = stuck["appointment_id"]
        # Use analyzing_started_at if available, otherwise updated_at
        started_str = stuck.get("declarative_analyzing_started_at") or stuck.get("updated_at", "")
        if not started_str:
            continue
        try:
            started_dt = datetime.fromisoformat(started_str.replace('Z', '+00:00'))
            if hasattr(started_dt, 'tzinfo') and started_dt.tzinfo is None:
                from datetime import timezone as tz
                started_dt = started_dt.replace(tzinfo=tz.utc)
            stuck_minutes = (now - started_dt).total_seconds() / 60
            if stuck_minutes > 30:
                logger.warning(
                    f"[AUTO-RECOVERY][ANALYZING] Appointment {stuck_apt_id}: "
                    f"stuck in 'analyzing' for {stuck_minutes:.0f} min. "
                    f"Resetting to 'collecting' for retry."
                )
                db.appointments.update_one(
                    {"appointment_id": stuck_apt_id, "declarative_phase": "analyzing"},
                    {"$set": {
                        "declarative_phase": "collecting",
                        "updated_at": now.isoformat(),
                    }}
                )
                # Immediately retry analysis
                _run_analysis(stuck_apt_id)
        except (ValueError, TypeError):
            continue

    # ── V5.1 Retroactive Guard ─────────────────────────────────────
    # Clean up collecting phases that should never have opened:
    # if < 2 accepted_guaranteed participants are in manual_review,
    # the declarative phase is unsolvable → auto-waive + not_needed.
    for apt in appointments:
        apt_id = apt['appointment_id']
        review_recs = list(db.attendance_records.find(
            {"appointment_id": apt_id, "outcome": "manual_review", "review_required": True},
            {"_id": 0, "participant_id": 1}
        ))
        guaranteed_count = 0
        for rr in review_recs:
            p_doc = db.participants.find_one(
                {"participant_id": rr["participant_id"]},
                {"_id": 0, "status": 1}
            )
            if p_doc and p_doc.get("status") == "accepted_guaranteed":
                guaranteed_count += 1
        if guaranteed_count < 2:
            for rr in review_recs:
                db.attendance_records.update_one(
                    {"appointment_id": apt_id, "participant_id": rr["participant_id"]},
                    {"$set": {
                        "outcome": "waived",
                        "review_required": False,
                        "decision_source": "retroactive_guard_insufficient_guaranteed",
                        "confidence_level": "HIGH",
                        "decided_by": "engine_guard",
                        "decided_at": now.isoformat(),
                    }}
                )
            db.appointments.update_one(
                {"appointment_id": apt_id},
                {"$set": {"declarative_phase": "not_needed", "updated_at": now.isoformat()}}
            )
            db.attendance_sheets.delete_many(
                {"appointment_id": apt_id, "status": "pending"}
            )
            logger.info(
                f"[DECLARATIVE][RETROACTIVE-GUARD] {apt_id}: "
                f"only {guaranteed_count} guaranteed in review → auto-waived, phase=not_needed"
            )

    # Re-fetch after guard cleanup (some may have been set to not_needed)
    appointments = list(db.appointments.find(
        {"declarative_phase": "collecting"},
        {"_id": 0}
    ))

    processed = 0
    for apt in appointments:
        apt_id = apt['appointment_id']
        deadline_str = apt.get('declarative_deadline')
        if not deadline_str:
            continue
        try:
            deadline = datetime.fromisoformat(deadline_str.replace('Z', '+00:00'))
            if hasattr(deadline, 'tzinfo') and deadline.tzinfo is None:
                from datetime import timezone
                deadline = deadline.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue

        # ── Monitoring: detect stuck collecting phases ──────────────
        # If ALL sheets are submitted but phase is still 'collecting',
        # this means _run_analysis was never triggered or crashed.
        # Log a warning with actionable details and auto-trigger analysis.
        total_sheets = db.attendance_sheets.count_documents({"appointment_id": apt_id})
        submitted_sheets = db.attendance_sheets.count_documents(
            {"appointment_id": apt_id, "status": "submitted"}
        )
        if total_sheets > 0 and submitted_sheets >= total_sheets and now < deadline:
            # All sheets submitted, deadline NOT yet reached, but still collecting
            # → this is a stuck state. Find last submission time.
            last_sheet = db.attendance_sheets.find_one(
                {"appointment_id": apt_id, "status": "submitted"},
                {"_id": 0, "submitted_at": 1},
                sort=[("submitted_at", -1)]
            )
            last_submit = last_sheet.get("submitted_at", "") if last_sheet else ""
            if last_submit:
                try:
                    submit_dt = datetime.fromisoformat(last_submit.replace('Z', '+00:00'))
                    if hasattr(submit_dt, 'tzinfo') and submit_dt.tzinfo is None:
                        from datetime import timezone as tz
                        submit_dt = submit_dt.replace(tzinfo=tz.utc)
                    delay_minutes = (now - submit_dt).total_seconds() / 60
                    if delay_minutes > 10:
                        logger.warning(
                            f"[AUTO-RECOVERY][TRIGGERED] Appointment {apt_id}: "
                            f"all {submitted_sheets}/{total_sheets} sheets submitted "
                            f"but phase still 'collecting' after {delay_minutes:.0f} min since last submit. "
                            f"Last submit: {last_submit}. Triggering _run_analysis as safety net."
                        )
                        _run_analysis(apt_id)
                        processed += 1
                        continue
                except (ValueError, TypeError):
                    pass

        if now >= deadline:
            # Force all pending sheets to "submitted" with unknown declarations
            pending = list(db.attendance_sheets.find({
                "appointment_id": apt['appointment_id'],
                "status": "pending"
            }, {"_id": 0}))

            for sheet in pending:
                default_decls = [
                    {**d, "declared_status": "unknown"} for d in sheet.get('declarations', [])
                ]
                db.attendance_sheets.update_one(
                    {"sheet_id": sheet['sheet_id']},
                    {"$set": {
                        "status": "submitted",
                        "submitted_at": now.isoformat(),
                        "declarations": default_decls,
                        "auto_closed": True,
                    }}
                )

            _run_analysis(apt['appointment_id'])
            processed += 1

    if processed:
        logger.info(f"[DECLARATIVE_JOB] Deadline enforced for {processed} appointments")


def run_dispute_deadline_job():
    """Escalate disputes that passed the 7-day deadline.
    Trustless V4: silence = uncertainty = arbitrage. Never a penalty.
    """
    from datetime import datetime

    disputes = list(db.declarative_disputes.find(
        {"status": {"$in": ["awaiting_positions", "awaiting_evidence"]}},
        {"_id": 0}
    ))

    now = now_utc()
    escalated = 0
    for d in disputes:
        deadline_str = d.get('deadline')
        if not deadline_str:
            continue
        try:
            deadline = datetime.fromisoformat(deadline_str.replace('Z', '+00:00'))
            if hasattr(deadline, 'tzinfo') and deadline.tzinfo is None:
                from datetime import timezone
                deadline = deadline.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue

        if now >= deadline:
            db.declarative_disputes.update_one(
                {"dispute_id": d['dispute_id']},
                {"$set": {
                    "status": "escalated",
                    "escalated_at": now.isoformat(),
                }}
            )
            escalated += 1

    if escalated:
        logger.info(f"[DISPUTE_JOB] Escalated {escalated} disputes past deadline")


def get_sheet_status(appointment_id: str) -> dict:
    """Get global status of attendance sheets for an appointment."""
    total = db.attendance_sheets.count_documents({"appointment_id": appointment_id})
    submitted = db.attendance_sheets.count_documents({"appointment_id": appointment_id, "status": "submitted"})
    apt = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0, "declarative_phase": 1, "declarative_deadline": 1})

    return {
        "appointment_id": appointment_id,
        "phase": apt.get('declarative_phase', 'not_needed') if apt else 'not_needed',
        "total_sheets": total,
        "submitted_sheets": submitted,
        "deadline": apt.get('declarative_deadline') if apt else None,
    }


def run_sheet_reminder_job():
    """Send reminders for pending sheets approaching deadline (< 12h remaining).
    Only targets sheets that are still 'pending' (not yet submitted).
    Idempotent: uses notification_service tracking to avoid duplicates.
    """
    from datetime import datetime, timezone as tz

    now = now_utc()
    reminder_window_hours = 12

    # Find all appointments in "collecting" phase
    collecting_apts = list(db.appointments.find(
        {"declarative_phase": "collecting"},
        {"_id": 0, "appointment_id": 1, "declarative_deadline": 1}
    ))

    reminded = 0
    for apt in collecting_apts:
        deadline_str = apt.get("declarative_deadline")
        if not deadline_str:
            continue

        try:
            deadline = datetime.fromisoformat(deadline_str.replace('Z', '+00:00'))
            if hasattr(deadline, 'tzinfo') and deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=tz.utc)
        except (ValueError, TypeError):
            continue

        hours_left = (deadline - now).total_seconds() / 3600

        # Only remind if between 0 and 12 hours remaining
        if hours_left <= 0 or hours_left > reminder_window_hours:
            continue

        # Find pending sheets for this appointment
        pending_sheets = list(db.attendance_sheets.find(
            {"appointment_id": apt["appointment_id"], "status": "pending"},
            {"_id": 0}
        ))

        for sheet in pending_sheets:
            try:
                from services.notification_service import notify_sheet_reminder
                notify_sheet_reminder(sheet, apt["appointment_id"], int(hours_left))
                reminded += 1
            except Exception as e:
                logger.warning(f"[SHEET_REMINDER] Failed for sheet {sheet.get('sheet_id')}: {e}")

    if reminded:
        logger.info(f"[SHEET_REMINDER] Sent {reminded} reminder(s)")
