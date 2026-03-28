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


# ═══════════════════════════════════════════════════════════════════
# Phase initialization
# ═══════════════════════════════════════════════════════════════════

def initialize_declarative_phase(appointment_id: str):
    """
    Called after evaluate_appointment() when manual_review records exist.
    Creates pending attendance sheets for each participant.
    """
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
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

    # RDV with < 3 active participants → escalade directe
    if len(active_participants) < 3:
        logger.info(f"[DECLARATIVE] {appointment_id}: < 3 participants, direct escalation")
        _escalate_all_manual_reviews(appointment_id, active_participants)
        db.appointments.update_one(
            {"appointment_id": appointment_id},
            {"$set": {"declarative_phase": "disputed"}}
        )
        return

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

    deadline = now_utc() + timedelta(hours=SHEET_DEADLINE_HOURS)

    # Create one sheet per active participant
    for p in active_participants:
        existing = db.attendance_sheets.find_one({
            "appointment_id": appointment_id,
            "submitted_by_user_id": p['user_id']
        })
        if existing:
            continue

        # Targets = only participants in manual_review, excluding self
        targets = [
            {"target_participant_id": r['participant_id'], "target_user_id": _get_user_id(r['participant_id']),
             "declared_status": None}
            for r in review_records
            if r['participant_id'] != p.get('participant_id')
        ]

        if not targets:
            continue

        db.attendance_sheets.insert_one({
            "sheet_id": str(uuid.uuid4()),
            "appointment_id": appointment_id,
            "submitted_by_user_id": p['user_id'],
            "submitted_by_participant_id": p.get('participant_id'),
            "status": "pending",
            "submitted_at": None,
            "declarations": targets,
            "created_at": now_utc().isoformat(),
            "deadline": deadline.isoformat(),
        })

    db.appointments.update_one(
        {"appointment_id": appointment_id},
        {"$set": {
            "declarative_phase": "collecting",
            "declarative_deadline": deadline.isoformat(),
        }}
    )
    logger.info(f"[DECLARATIVE] Phase initialized for {appointment_id}. "
                f"{len(review_records)} records in review, {len(active_participants)} sheets created. "
                f"Deadline: {deadline.isoformat()}")


def _get_user_id(participant_id: str) -> str:
    p = db.participants.find_one({"participant_id": participant_id}, {"_id": 0, "user_id": 1})
    return p.get('user_id', '') if p else ''


def _escalate_all_manual_reviews(appointment_id: str, participants: list):
    """For RDV < 3 participants: create a dispute for each manual_review record."""
    review_records = list(db.attendance_records.find(
        {"appointment_id": appointment_id, "review_required": True, "outcome": "manual_review"},
        {"_id": 0}
    ))
    for r in review_records:
        open_dispute(appointment_id, r['participant_id'], "small_group_escalation")


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
    if not sheet:
        return {"error": "Aucune feuille de présence trouvée pour cet utilisateur"}

    if sheet.get('status') == 'submitted':
        return {"error": "Vous avez déjà soumis votre feuille de présence"}

    valid_statuses = ('present_on_time', 'present_late', 'absent', 'unknown')
    valid_targets = {d['target_participant_id'] for d in sheet['declarations']}

    updated_declarations = []
    for decl in declarations:
        tid = decl.get('target_participant_id')
        status = decl.get('declared_status')
        if tid not in valid_targets:
            return {"error": f"Participant cible invalide: {tid}"}
        if status not in valid_statuses:
            return {"error": f"Statut invalide: {status}. Valeurs: {', '.join(valid_statuses)}"}
        target_uid = next((d['target_user_id'] for d in sheet['declarations'] if d['target_participant_id'] == tid), '')
        updated_declarations.append({
            "target_participant_id": tid,
            "target_user_id": target_uid,
            "declared_status": status,
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
        _run_analysis(appointment_id)


# ═══════════════════════════════════════════════════════════════════
# Declaration analysis
# ═══════════════════════════════════════════════════════════════════

def _run_analysis(appointment_id: str):
    """Analyze all sheets and resolve or open disputes."""
    db.appointments.update_one(
        {"appointment_id": appointment_id},
        {"$set": {"declarative_phase": "analyzing"}}
    )

    sheets = list(db.attendance_sheets.find({"appointment_id": appointment_id}, {"_id": 0}))
    submitted_sheets = [s for s in sheets if s['status'] == 'submitted']

    # Build the declaration matrix
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

    # Global coherence check (cross-accusations)
    global_coherence = _check_global_coherence(submitted_sheets)

    per_participant_results = []

    for record in review_records:
        target_pid = record['participant_id']

        unanimity = _check_unanimity(target_pid, submitted_sheets)
        contradiction = _check_contradiction_signals(
            target_pid, unanimity, submitted_sheets, appointment_id
        )

        auto_resolvable = (
            unanimity.get('unanimous', False)
            and global_coherence.get('coherent', False)
            and not contradiction.get('contradiction', False)
        )

        confidence = "MEDIUM" if auto_resolvable else "LOW"
        reason = None
        if not auto_resolvable:
            reasons = []
            if not unanimity.get('unanimous'):
                reasons.append(unanimity.get('reason', 'no_unanimity'))
            if not global_coherence.get('coherent'):
                reasons.append(global_coherence.get('reason', 'incoherent'))
            if contradiction.get('contradiction'):
                reasons.append(contradiction.get('reason', 'contradiction'))
            reason = "; ".join(reasons)

        per_participant_results.append({
            "target_participant_id": target_pid,
            "tiers_expressed_count": unanimity.get('expressed_count', 0),
            "tiers_unanimous": unanimity.get('unanimous', False),
            "unanimous_status": unanimity.get('status'),
            "contestant_contradiction": contradiction.get('reason') == 'contestant_contradiction',
            "collusion_detected": contradiction.get('reason') == 'collusion_signal',
            "tech_signal_contradiction": contradiction.get('reason') == 'tech_signal_contradiction',
            "confidence_level": confidence,
            "auto_resolvable": auto_resolvable,
            "reason_if_not": reason,
        })

    # Store analysis
    db.declarative_analyses.insert_one({
        "analysis_id": str(uuid.uuid4()),
        "appointment_id": appointment_id,
        "analyzed_at": now_utc().isoformat(),
        "global_coherent": global_coherence.get('coherent', False),
        "per_participant": per_participant_results,
    })

    # Apply results
    any_dispute = False
    for result in per_participant_results:
        if result['auto_resolvable']:
            _apply_declarative_outcome(appointment_id, result)
        else:
            open_dispute(appointment_id, result['target_participant_id'], result.get('reason_if_not', 'unknown'))
            any_dispute = True

    new_phase = "disputed" if any_dispute else "resolved"
    db.appointments.update_one(
        {"appointment_id": appointment_id},
        {"$set": {"declarative_phase": new_phase}}
    )

    if new_phase == "resolved":
        # Reset Cas A overrides before re-triggering financial engine
        from services.attendance_service import reset_cas_a_overrides, _process_financial_outcomes
        reset_cas_a_overrides(appointment_id)
        appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
        participants = list(db.participants.find({"appointment_id": appointment_id}, {"_id": 0}))
        _process_financial_outcomes(appointment_id, appointment, participants)
        logger.info(f"[DECLARATIVE] All manual_reviews resolved for {appointment_id}. Financial engine relaunched.")


def _check_unanimity(target_pid: str, sheets: list) -> dict:
    """Check if all tiers agree on target_pid's status."""
    declarations = []
    for s in sheets:
        if s.get('submitted_by_participant_id') == target_pid:
            continue
        for d in s.get('declarations', []):
            if d['target_participant_id'] == target_pid:
                declarations.append(d)

    expressed = [d for d in declarations if d.get('declared_status') != 'unknown']

    if len(expressed) < MIN_TIERS_EXPRESSED:
        return {"unanimous": False, "reason": "fewer_than_2_expressed", "expressed_count": len(expressed)}

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
    """Apply a MEDIUM confidence declarative outcome to an attendance record."""
    target_pid = result['target_participant_id']
    declared = result.get('unanimous_status')

    outcome_map = {
        'present_on_time': 'on_time',
        'present_late': 'late',
        'absent': 'no_show',
    }
    outcome = outcome_map.get(declared, 'manual_review')

    if outcome == 'manual_review':
        return

    db.attendance_records.update_one(
        {"appointment_id": appointment_id, "participant_id": target_pid},
        {"$set": {
            "outcome": outcome,
            "review_required": False,
            "decision_source": "declarative",
            "confidence_level": "MEDIUM",
            "decided_by": "declarative_consensus",
            "decided_at": now_utc().isoformat(),
            "declarative_details": {
                "tiers_expressed": result.get('tiers_expressed_count', 0),
                "unanimous_status": declared,
            }
        }}
    )
    logger.info(f"[DECLARATIVE] Applied {outcome} to {target_pid} (declarative, MEDIUM confidence)")


def open_dispute(appointment_id: str, target_participant_id: str, reason: str):
    """Create a dispute for a participant whose status cannot be auto-resolved.
    The organizer is ALWAYS assigned as the sole accuser_user_id.
    """
    existing = db.declarative_disputes.find_one({
        "appointment_id": appointment_id,
        "target_participant_id": target_participant_id,
    })
    if existing:
        return existing.get('dispute_id')

    target_user_id = _get_user_id(target_participant_id)
    deadline = now_utc() + timedelta(days=DISPUTE_DEADLINE_DAYS)

    # The organizer is the sole accuser — if organizer doesn't support the
    # absence claim, there is no financial dispute to arbitrate.
    appointment = db.appointments.find_one(
        {"appointment_id": appointment_id},
        {"_id": 0, "organizer_id": 1}
    )
    accuser_user_id = appointment.get("organizer_id") if appointment else None

    dispute = {
        "dispute_id": str(uuid.uuid4()),
        "appointment_id": appointment_id,
        "target_participant_id": target_participant_id,
        "target_user_id": target_user_id,
        # Phase 2: accuser/accused explicit fields
        "accuser_user_id": accuser_user_id,
        "accused_participant_id": target_participant_id,
        "accused_user_id": target_user_id,
        # Organizer decision (concede / maintain / null)
        "decision": None,
        "decision_at": None,
        "decision_by": None,
        "status": "awaiting_evidence",
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
    logger.info(f"[DISPUTE] Opened for {target_participant_id} in {appointment_id}: {reason}. Accuser (organizer): {accuser_user_id}")
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

    # Apply to attendance record
    previous_outcome = None
    existing_record = db.attendance_records.find_one(
        {"appointment_id": dispute['appointment_id'], "participant_id": dispute['target_participant_id']},
        {"_id": 0, "outcome": 1}
    )
    if existing_record:
        previous_outcome = existing_record.get("outcome")

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
        _process_financial_outcomes(appointment_id, appointment, participants)
        logger.info(f"[DISPUTE] All disputes resolved for {appointment_id}. Financial engine relaunched.")

    # Non-blocking: send dispute resolution emails
    try:
        from services.financial_emails import send_dispute_resolution_emails
        send_dispute_resolution_emails(dispute_id)
    except Exception as e:
        logger.warning(f"[DISPUTE] Email notification error (non-blocking): {e}")

    return {"success": True}


def concede_dispute(dispute_id: str, user_id: str) -> dict:
    """Organizer concedes the dispute — releases the participant's guarantee.
    This resolves the dispute with outcome 'waived' (no penalty).
    """
    dispute = db.declarative_disputes.find_one({"dispute_id": dispute_id}, {"_id": 0})
    if not dispute:
        return {"error": "Litige introuvable"}
    if dispute.get("accuser_user_id") != user_id:
        return {"error": "Seul l'organisateur (accusateur) peut prendre cette décision"}
    if dispute.get("decision") is not None:
        return {"error": "Une décision a déjà été prise pour ce litige"}
    if dispute.get("status") == "resolved":
        return {"error": "Ce litige est déjà résolu"}

    db.declarative_disputes.update_one(
        {"dispute_id": dispute_id},
        {"$set": {
            "decision": "conceded",
            "decision_at": now_utc().isoformat(),
            "decision_by": user_id,
        }}
    )
    logger.info(f"[DISPUTE] Organizer {user_id} conceded dispute {dispute_id}")

    # Auto-resolve: release guarantee → outcome = waived
    return resolve_dispute(
        dispute_id,
        final_outcome="waived",
        resolution_note="L'organisateur a libéré la garantie du participant.",
        resolved_by="organizer_concession",
    )


def maintain_dispute(dispute_id: str, user_id: str) -> dict:
    """Organizer maintains position — escalates to platform arbitration."""
    dispute = db.declarative_disputes.find_one({"dispute_id": dispute_id}, {"_id": 0})
    if not dispute:
        return {"error": "Litige introuvable"}
    if dispute.get("accuser_user_id") != user_id:
        return {"error": "Seul l'organisateur (accusateur) peut prendre cette décision"}
    if dispute.get("decision") is not None:
        return {"error": "Une décision a déjà été prise pour ce litige"}
    if dispute.get("status") == "resolved":
        return {"error": "Ce litige est déjà résolu"}

    db.declarative_disputes.update_one(
        {"dispute_id": dispute_id},
        {"$set": {
            "decision": "maintained",
            "decision_at": now_utc().isoformat(),
            "decision_by": user_id,
            "status": "escalated",
            "escalated_at": now_utc().isoformat(),
        }}
    )
    logger.info(f"[DISPUTE] Organizer {user_id} maintained dispute {dispute_id} — escalated to platform")
    return {"success": True, "message": "Litige escaladé à la plateforme pour arbitrage."}


def submit_dispute_evidence(dispute_id: str, user_id: str, evidence_type: str, content_url: str = None, text_content: str = None):
    """Submit complementary evidence for a dispute."""
    dispute = db.declarative_disputes.find_one({"dispute_id": dispute_id}, {"_id": 0})
    if not dispute:
        return {"error": "Litige introuvable"}
    if dispute['status'] not in ('awaiting_evidence', 'opened'):
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
    """Force-close sheets that passed the 48h deadline and trigger analysis."""
    from datetime import datetime

    appointments = list(db.appointments.find(
        {"declarative_phase": "collecting"},
        {"_id": 0}
    ))

    now = now_utc()
    processed = 0
    for apt in appointments:
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
    """Escalate disputes that passed the 7-day deadline."""
    from datetime import datetime

    disputes = list(db.declarative_disputes.find(
        {"status": "awaiting_evidence"},
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
