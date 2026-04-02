"""
Admin Arbitration Service — NLYT V1

Builds the tech dossier and system analysis for escalated disputes.
The admin does not "decide" — they rule within strict system rules:
  - No admissible proof → penalty by default
  - Dispute = last-resort recourse to contest the absence of proof
"""
import logging
from database import db
from services.attendance_service import _has_admissible_proof, _get_best_proof_session
from utils.date_utils import now_utc

logger = logging.getLogger(__name__)


def build_evidence_summary_for_target(appointment_id: str, target_participant_id: str, duration_minutes: int = 0) -> dict:
    """Build a user-facing evidence summary for a single target participant.

    Returns structured, human-readable proof data (no raw payloads).
    Designed for the /decisions detail page — transparency without overload.
    """
    # Evidence items for target
    evidence_items = list(db.evidence_items.find(
        {"appointment_id": appointment_id, "participant_id": target_participant_id},
        {"_id": 0, "source": 1, "source_timestamp": 1, "derived_facts": 1}
    ))

    # Proof sessions for target
    proof_sessions = list(db.proof_sessions.find(
        {"appointment_id": appointment_id, "participant_id": target_participant_id},
        {"_id": 0, "checked_in_at": 1, "checked_out_at": 1,
         "heartbeat_count": 1, "active_duration_seconds": 1, "score": 1,
         "proof_level": 1}
    ))

    # --- Video ---
    video_sessions = []
    for e in evidence_items:
        if e["source"] == "video_conference":
            df = e.get("derived_facts") or {}
            dur = df.get("duration_seconds")
            pct = round((dur / (duration_minutes * 60)) * 100) if dur and duration_minutes else None
            video_sessions.append({
                "joined_at": df.get("joined_at"),
                "left_at": df.get("left_at"),
                "duration_seconds": dur,
                "provider": df.get("provider"),
                "pct_of_rdv": pct,
            })
    total_video_sec = sum(s.get("duration_seconds") or 0 for s in video_sessions)
    video = {
        "has_data": len(video_sessions) > 0,
        "sessions": video_sessions,
        "total_duration_seconds": total_video_sec,
        "total_pct_of_rdv": round((total_video_sec / (duration_minutes * 60)) * 100) if total_video_sec and duration_minutes else None,
    }

    # --- GPS ---
    gps = {"has_data": False}
    for e in evidence_items:
        if e["source"] == "gps":
            df = e.get("derived_facts") or {}
            gps = {
                "has_data": True,
                "distance_meters": df.get("distance_meters"),
                "within_radius": df.get("gps_within_radius", False),
                "geographic_detail": df.get("geographic_detail"),
            }
            break

    # --- Checkin ---
    checkin = {"has_data": False}
    for e in evidence_items:
        if e["source"] == "manual_checkin":
            df = e.get("derived_facts") or {}
            checkin = {
                "has_data": True,
                "timestamp": e.get("source_timestamp"),
                "temporal_detail": df.get("temporal_detail"),
            }
            break

    # --- QR ---
    qr = {"has_data": False}
    for e in evidence_items:
        if e["source"] == "qr":
            qr = {
                "has_data": True,
                "timestamp": e.get("source_timestamp"),
            }
            break

    # --- NLYT Proof Sessions ---
    nlyt = {"has_data": False}
    if proof_sessions:
        best_score = max(ps.get("score") or 0 for ps in proof_sessions)
        total_active = sum(ps.get("active_duration_seconds") or 0 for ps in proof_sessions)
        best_level = None
        for ps in proof_sessions:
            if ps.get("score") == best_score:
                best_level = ps.get("proof_level")
                break
        nlyt = {
            "has_data": True,
            "best_score": best_score,
            "total_active_seconds": total_active,
            "proof_level": best_level,
            "session_count": len(proof_sessions),
        }

    # --- Overall signal ---
    has_any = video["has_data"] or gps["has_data"] or checkin["has_data"] or qr["has_data"] or nlyt["has_data"]

    return {
        "has_any_evidence": has_any,
        "video": video,
        "gps": gps,
        "checkin": checkin,
        "qr": qr,
        "nlyt": nlyt,
    }


def build_tech_dossier(appointment_id: str, target_participant_id: str) -> dict:
    """Aggregate all technical evidence for the admin dossier.

    Returns the legacy proof_summary for backward compat AND a new
    `participant_dossiers` list with per-participant raw evidence.
    No business logic — pure aggregation and structuring.
    """
    # 1. Admissible proof check (existing)
    has_proof = _has_admissible_proof(target_participant_id, appointment_id)

    # 2. NLYT Proof session for target (existing)
    proof_session = _get_best_proof_session(appointment_id, target_participant_id)
    nlyt_score = None
    nlyt_level = None
    nlyt_details = None
    if proof_session:
        nlyt_score = proof_session.get("score")
        nlyt_level = proof_session.get("proof_level")
        nlyt_details = {
            "session_id": proof_session.get("session_id"),
            "score": nlyt_score,
            "proof_level": nlyt_level,
            "heartbeat_count": proof_session.get("heartbeat_count", 0),
            "active_duration_seconds": proof_session.get("active_duration_seconds", 0),
            "score_breakdown": proof_session.get("score_breakdown"),
        }

    # 3. Raw evidence items for target (existing — kept for backward compat)
    evidence_items = list(db.evidence_items.find(
        {"appointment_id": appointment_id, "participant_id": target_participant_id},
        {"_id": 0, "source": 1, "derived_facts": 1, "collected_at": 1}
    ))

    video_api_outcome = None
    video_provider = None
    gps_evidence = False
    qr_evidence = False
    for e in evidence_items:
        src = e.get("source", "")
        df = e.get("derived_facts") or {}
        if src == "video_conference":
            video_api_outcome = df.get("video_attendance_outcome")
            video_provider = df.get("provider")
        elif src == "gps" and df.get("gps_within_radius"):
            gps_evidence = True
        elif src == "qr":
            qr_evidence = True

    # 4. Attendance record (existing)
    attendance_record = db.attendance_records.find_one(
        {"appointment_id": appointment_id, "participant_id": target_participant_id},
        {"_id": 0, "outcome": 1, "decision_basis": 1, "confidence_level": 1, "delay_minutes": 1}
    )

    # ──────────────────────────────────────────────────────
    # 5. NEW: Per-participant dossiers (all participants)
    # ──────────────────────────────────────────────────────
    participants = list(db.participants.find(
        {"appointment_id": appointment_id,
         "status": {"$in": ["accepted", "accepted_pending_guarantee", "accepted_guaranteed"]}},
        {"_id": 0, "participant_id": 1, "first_name": 1, "last_name": 1,
         "email": 1, "is_organizer": 1, "role": 1}
    ))

    # All evidence items for this appointment (all participants)
    all_evidence = list(db.evidence_items.find(
        {"appointment_id": appointment_id},
        {"_id": 0, "evidence_id": 1, "participant_id": 1, "source": 1,
         "source_timestamp": 1, "collected_at": 1, "derived_facts": 1,
         "confidence_score": 1}
    ))

    # All proof sessions for this appointment
    all_proof_sessions = list(db.proof_sessions.find(
        {"appointment_id": appointment_id},
        {"_id": 0, "participant_id": 1, "checked_in_at": 1, "checked_out_at": 1,
         "heartbeat_count": 1, "active_duration_seconds": 1, "score": 1,
         "proof_level": 1, "score_breakdown": 1}
    ))

    # All attendance records
    all_records = list(db.attendance_records.find(
        {"appointment_id": appointment_id},
        {"_id": 0, "participant_id": 1, "outcome": 1, "decision_basis": 1,
         "delay_minutes": 1, "review_required": 1}
    ))

    # All attendance sheets (declarations)
    all_sheets = list(db.attendance_sheets.find(
        {"appointment_id": appointment_id, "status": "submitted"},
        {"_id": 0, "submitted_by_participant_id": 1, "declarations": 1}
    ))

    # Index by participant
    ev_by_pid = {}
    for e in all_evidence:
        ev_by_pid.setdefault(e["participant_id"], []).append(e)

    ps_by_pid = {}
    for ps in all_proof_sessions:
        ps_by_pid.setdefault(ps["participant_id"], []).append(ps)

    rec_by_pid = {}
    for r in all_records:
        rec_by_pid[r["participant_id"]] = r

    # Build declarations index: what did others declare about each participant?
    decl_about_pid = {}
    for sheet in all_sheets:
        submitter = sheet["submitted_by_participant_id"]
        for decl in sheet.get("declarations", []):
            target = decl.get("target_participant_id") or decl.get("participant_id")
            if target and not decl.get("is_self_declaration"):
                decl_about_pid.setdefault(target, []).append({
                    "declared_by": submitter,
                    "declared_status": decl.get("declared_status") or decl.get("status"),
                })

    participant_dossiers = []
    for p in participants:
        pid = p["participant_id"]
        p_evidence = ev_by_pid.get(pid, [])
        p_sessions = ps_by_pid.get(pid, [])
        p_record = rec_by_pid.get(pid)
        p_declarations = decl_about_pid.get(pid, [])

        # Structure video sessions
        video_sessions = []
        for e in p_evidence:
            if e["source"] == "video_conference":
                df = e.get("derived_facts") or {}
                video_sessions.append({
                    "joined_at": df.get("joined_at"),
                    "left_at": df.get("left_at"),
                    "duration_seconds": df.get("duration_seconds"),
                    "provider": df.get("provider"),
                    "identity_confidence": df.get("identity_confidence"),
                    "identity_match_method": df.get("identity_match_method"),
                    "temporal_detail": df.get("temporal_detail"),
                    "video_outcome": df.get("video_attendance_outcome"),
                    "name_from_provider": df.get("participant_name_from_provider"),
                })

        # Structure checkin data
        checkin_data = None
        for e in p_evidence:
            if e["source"] == "manual_checkin":
                df = e.get("derived_facts") or {}
                checkin_data = {
                    "timestamp": e.get("source_timestamp"),
                    "temporal_detail": df.get("temporal_detail"),
                }
                break

        # Structure GPS data
        gps_data = None
        for e in p_evidence:
            if e["source"] == "gps":
                df = e.get("derived_facts") or {}
                gps_data = {
                    "timestamp": e.get("source_timestamp") or e.get("collected_at"),
                    "distance_meters": df.get("distance_meters"),
                    "geographic_detail": df.get("geographic_detail"),
                    "geographic_consistency": df.get("geographic_consistency"),
                    "within_radius": df.get("gps_within_radius", False),
                }
                break

        # Structure QR data
        qr_data = None
        for e in p_evidence:
            if e["source"] == "qr":
                qr_data = {
                    "timestamp": e.get("source_timestamp") or e.get("collected_at"),
                }
                break

        # All proof sessions (not just best — arbitrator needs the full picture)
        proof_sessions_list = []
        for ps in p_sessions:
            proof_sessions_list.append({
                "checked_in_at": ps.get("checked_in_at"),
                "checked_out_at": ps.get("checked_out_at"),
                "heartbeat_count": ps.get("heartbeat_count", 0),
                "active_duration_seconds": ps.get("active_duration_seconds", 0),
                "score": ps.get("score"),
                "proof_level": ps.get("proof_level"),
                "suggested_status": ps.get("suggested_status"),
            })

        # Declared position about this participant (by others)
        declared_present = sum(1 for d in p_declarations if d["declared_status"] in ("present", "late", "present_on_time", "present_late"))
        declared_absent = sum(1 for d in p_declarations if d["declared_status"] in ("absent", "no_show"))

        participant_dossiers.append({
            "participant_id": pid,
            "first_name": p.get("first_name", ""),
            "last_name": p.get("last_name", ""),
            "email": p.get("email", ""),
            "is_organizer": p.get("is_organizer", False),
            "is_target": pid == target_participant_id,
            "video_sessions": video_sessions,
            "checkin": checkin_data,
            "gps": gps_data,
            "qr": qr_data,
            "proof_sessions": proof_sessions_list,
            "attendance_record": {
                "outcome": p_record.get("outcome") if p_record else None,
                "decision_basis": p_record.get("decision_basis") if p_record else None,
                "delay_minutes": p_record.get("delay_minutes") if p_record else None,
            },
            "declarations_about": {
                "declared_present": declared_present,
                "declared_absent": declared_absent,
            },
            "evidence_count": len(p_evidence),
        })

    return {
        "has_admissible_proof": has_proof,
        "proof_summary": {
            "nlyt_proof_score": nlyt_score,
            "nlyt_proof_level": nlyt_level,
            "nlyt_proof_details": nlyt_details,
            "video_api_outcome": video_api_outcome,
            "video_provider": video_provider,
            "gps_evidence": gps_evidence,
            "qr_evidence": qr_evidence,
            "evidence_count": len(evidence_items),
        },
        "attendance_record": attendance_record,
        "participant_dossiers": participant_dossiers,
    }


def compute_system_analysis(dispute: dict, tech_dossier: dict, declaration_summary: dict) -> dict:
    """Compute the system analysis (not a 'recommendation' — a factual assessment).

    Rules:
    - No admissible proof + no strong declarative convergence → no_show (default)
    - Contradiction signal detected → requires human examination
    - Weak proof with positive declarative signals → ambiguous, needs examination
    """
    has_proof = tech_dossier.get("has_admissible_proof", False)
    nlyt_level = tech_dossier.get("proof_summary", {}).get("nlyt_proof_level")
    declared_present = declaration_summary.get("declared_present_count", 0)
    declared_absent = declaration_summary.get("declared_absent_count", 0)
    opened_reason = dispute.get("opened_reason", "")

    # Contradiction signals from dispute opening
    has_contradiction = any(sig in opened_reason for sig in
        ("contestant_contradiction", "tech_signal_contradiction", "collusion_signal"))

    # Case A: No admissible proof → penalty by default
    if not has_proof:
        if declared_present == 0:
            return {
                "suggested_outcome": "no_show",
                "confidence": "high",
                "case": "A",
                "reasoning": "Absence de preuve technologique. Aucun tiers ne confirme la presence. Charge de la preuve non remplie.",
            }
        if has_contradiction:
            return {
                "suggested_outcome": None,
                "confidence": "low",
                "case": "B",
                "reasoning": f"Absence de preuve technologique, mais signal de contradiction detecte ({opened_reason}). Examen des elements soumis requis.",
            }
        return {
            "suggested_outcome": "no_show",
            "confidence": "medium",
            "case": "A",
            "reasoning": f"Absence de preuve technologique. {declared_present} tiers declarent present vs {declared_absent} absent. Preuve insuffisante — charge de la preuve sur le participant.",
        }

    # Case C: Weak/medium proof exists
    if nlyt_level in ("weak", "medium"):
        if declared_present > declared_absent and declared_present >= 2:
            return {
                "suggested_outcome": None,
                "confidence": "low",
                "case": "C",
                "reasoning": f"Preuve partielle ({nlyt_level}, score {tech_dossier['proof_summary'].get('nlyt_proof_score')}). Convergence declarative positive ({declared_present} present vs {declared_absent} absent). A examiner.",
            }
        return {
            "suggested_outcome": "no_show",
            "confidence": "medium",
            "case": "C",
            "reasoning": f"Preuve partielle ({nlyt_level}) mais pas de convergence declarative suffisante. Charge de la preuve non remplie.",
        }

    # Rare case: Strong proof but still escalated
    return {
        "suggested_outcome": "on_time",
        "confidence": "medium",
        "case": "rare",
        "reasoning": "Preuve technologique admissible detectee. Le systeme aurait du resoudre automatiquement — a verifier.",
    }


FILTER_QUERIES = {
    "escalated": {"status": "escalated"},
    "awaiting": {"status": "awaiting_positions"},
    "resolved": {"status": "resolved"},
    "agreed": {"status": {"$in": ["agreed_present", "agreed_absent", "agreed_late_penalized"]}},
}


def get_disputes_for_admin(filter_key: str = "escalated") -> list:
    """Get disputes filtered by category, with enrichment for the admin list."""
    query = FILTER_QUERIES.get(filter_key, FILTER_QUERIES["escalated"])
    sort_field = "escalated_at" if filter_key == "escalated" else "created_at"
    sort_dir = 1 if filter_key == "escalated" else -1  # FIFO for escalated, newest first otherwise

    disputes = list(db.declarative_disputes.find(
        query, {"_id": 0}
    ).sort(sort_field, sort_dir).limit(100))

    return [_enrich_dispute_for_list(d) for d in disputes]


def get_escalated_disputes_for_admin() -> list:
    """Legacy wrapper — returns only escalated disputes."""
    return get_disputes_for_admin("escalated")


def _enrich_dispute_for_list(d: dict) -> dict:
    """Enrich a single dispute document for the admin list view."""
    apt = db.appointments.find_one(
        {"appointment_id": d["appointment_id"]},
        {"_id": 0, "title": 1, "start_datetime": 1, "appointment_type": 1,
         "location": 1, "location_display_name": 1, "meeting_provider": 1,
         "duration_minutes": 1}
    )
    if apt:
        d["appointment_title"] = apt.get("title", "")
        d["appointment_date"] = apt.get("start_datetime", "")
        d["appointment_type"] = apt.get("appointment_type", "")
        d["appointment_location"] = apt.get("location_display_name") or apt.get("location", "")
        d["appointment_meeting_provider"] = apt.get("meeting_provider", "")

    target_p = db.participants.find_one(
        {"participant_id": d["target_participant_id"]},
        {"_id": 0, "first_name": 1, "last_name": 1, "email": 1}
    )
    if target_p:
        d["target_name"] = f"{target_p.get('first_name', '')} {target_p.get('last_name', '')}".strip()
        d["target_email"] = target_p.get("email", "")

    org_p = db.participants.find_one(
        {"appointment_id": d["appointment_id"], "is_organizer": True},
        {"_id": 0, "first_name": 1, "last_name": 1}
    )
    if org_p:
        d["organizer_name"] = f"{org_p.get('first_name', '')} {org_p.get('last_name', '')}".strip()

    d["has_admissible_proof"] = _has_admissible_proof(
        d["target_participant_id"], d["appointment_id"]
    )

    escalated_at = d.get("escalated_at")
    if escalated_at:
        from utils.date_utils import parse_iso_datetime
        esc_dt = parse_iso_datetime(escalated_at)
        if esc_dt:
            delta = now_utc() - esc_dt
            d["escalated_days_ago"] = delta.days
            d["escalated_hours_ago"] = int(delta.total_seconds() / 3600)

    d["positions"] = {
        "organizer": d.get("organizer_position"),
        "participant": d.get("participant_position"),
    }

    # Status label for non-escalated views
    status = d.get("status", "")
    STATUS_LABELS = {
        "escalated": "Escalade",
        "awaiting_positions": "Positions en cours",
        "resolved": "Resolu",
        "agreed_present": "Accord: Present",
        "agreed_absent": "Accord: Absent",
        "agreed_late_penalized": "Accord: Retard",
    }
    d["status_label"] = STATUS_LABELS.get(status, status)

    # Financial summary for resolved disputes
    resolution = d.get("resolution") or {}
    final_outcome = resolution.get("final_outcome", "")
    if status in ("resolved", "agreed_present", "agreed_absent", "agreed_late_penalized"):
        if final_outcome == "on_time" or status == "agreed_present":
            d["financial_summary"] = "Aucune penalite"
        else:
            # Look up appointment penalty
            apt_fin = db.appointments.find_one(
                {"appointment_id": d["appointment_id"]},
                {"_id": 0, "penalty_amount": 1, "penalty_currency": 1,
                 "platform_commission_percent": 1, "charity_percent": 1}
            )
            if apt_fin and apt_fin.get("penalty_amount"):
                p = apt_fin["penalty_amount"]
                cur = (apt_fin.get("penalty_currency") or "eur").upper()
                comm_pct = apt_fin.get("platform_commission_percent", 0)
                charity_pct = apt_fin.get("charity_percent", 0)
                p_cents = int(p * 100)
                comp_cents = p_cents - int(p_cents * comm_pct / 100) - int(p_cents * charity_pct / 100)
                d["financial_summary"] = f"{p:.0f}{cur} preleves — {comp_cents/100:.0f}{cur} verses a l'organisateur"
            else:
                d["financial_summary"] = "Penalite appliquee"

    d.pop("evidence_submissions", None)
    d.pop("resolution", None)

    return d


def get_dispute_detail_for_admin(dispute_id: str) -> dict:
    """Full detail for admin arbitration view."""
    dispute = db.declarative_disputes.find_one({"dispute_id": dispute_id}, {"_id": 0})
    if not dispute:
        return None

    apt_id = dispute["appointment_id"]
    target_pid = dispute["target_participant_id"]

    # Appointment context
    apt = db.appointments.find_one(
        {"appointment_id": apt_id},
        {"_id": 0, "title": 1, "start_datetime": 1, "appointment_type": 1,
         "location": 1, "location_display_name": 1, "meeting_provider": 1,
         "duration_minutes": 1, "tolerated_delay_minutes": 1,
         "penalty_amount": 1, "penalty_currency": 1,
         "platform_commission_percent": 1, "charity_percent": 1, "compensation_percent": 1}
    )
    if apt:
        dispute["appointment_title"] = apt.get("title", "")
        dispute["appointment_date"] = apt.get("start_datetime", "")
        dispute["appointment_type"] = apt.get("appointment_type", "")
        dispute["appointment_location"] = apt.get("location_display_name") or apt.get("location", "")
        dispute["appointment_meeting_provider"] = apt.get("meeting_provider", "")
        dispute["appointment_duration_minutes"] = apt.get("duration_minutes", 0)
        dispute["tolerated_delay_minutes"] = apt.get("tolerated_delay_minutes", 0)

        # Financial context for preview
        penalty = apt.get("penalty_amount", 0)
        currency = apt.get("penalty_currency", "eur")
        commission_pct = apt.get("platform_commission_percent", 0)
        charity_pct = apt.get("charity_percent", 0)
        penalty_cents = int(penalty * 100)
        platform_cents = int(penalty_cents * commission_pct / 100)
        charity_cents = int(penalty_cents * charity_pct / 100)
        compensation_cents = penalty_cents - platform_cents - charity_cents

        dispute["financial_context"] = {
            "penalty_amount": penalty,
            "penalty_currency": currency,
            "platform_commission_percent": commission_pct,
            "charity_percent": charity_pct,
            "platform_amount": platform_cents / 100,
            "charity_amount": charity_cents / 100,
            "compensation_amount": compensation_cents / 100,
        }

    # Names
    target_p = db.participants.find_one(
        {"participant_id": target_pid},
        {"_id": 0, "first_name": 1, "last_name": 1, "email": 1}
    )
    if target_p:
        dispute["target_name"] = f"{target_p.get('first_name', '')} {target_p.get('last_name', '')}".strip()
        dispute["target_email"] = target_p.get("email", "")

    org_p = db.participants.find_one(
        {"appointment_id": apt_id, "is_organizer": True},
        {"_id": 0, "participant_id": 1, "first_name": 1, "last_name": 1, "email": 1}
    )
    if org_p:
        dispute["organizer_name"] = f"{org_p.get('first_name', '')} {org_p.get('last_name', '')}".strip()

    # Counterpart name: the person facing the organizer in the dispute.
    # Rule:
    #   - If target IS a participant → counterpart = target (they face the organizer)
    #   - If target IS the organizer → NO counterpart (the org is judging themselves,
    #     the dispute was opened by declarative disagreement among other participants,
    #     not by a specific opposing party)
    if target_p and org_p:
        target_is_org = (dispute.get("target_participant_id") == org_p.get("participant_id")) if org_p.get("participant_id") else False
    else:
        target_is_org = False

    dispute["target_is_organizer"] = target_is_org

    if target_is_org:
        # Target is the organizer → no counterpart party
        dispute["counterpart_name"] = None
    else:
        # Target is a participant → counterpart = target (the person facing the org)
        dispute["counterpart_name"] = dispute.get("target_name", "")

    # Tech dossier
    tech_dossier = build_tech_dossier(apt_id, target_pid)
    dispute["tech_dossier"] = tech_dossier

    # Declaration summary (full, not anonymized for admin)
    from routers.dispute_routes import _get_anonymized_summary
    dispute["declaration_summary"] = _get_anonymized_summary(apt_id, target_pid)

    # Analyse systeme
    dispute["system_analysis"] = compute_system_analysis(
        dispute, tech_dossier, dispute["declaration_summary"]
    )

    # Age indicator
    escalated_at = dispute.get("escalated_at")
    if escalated_at:
        from utils.date_utils import parse_iso_datetime
        esc_dt = parse_iso_datetime(escalated_at)
        if esc_dt:
            delta = now_utc() - esc_dt
            dispute["escalated_days_ago"] = delta.days

    # Declarative analysis (if available)
    analysis = db.declarative_analyses.find_one(
        {"appointment_id": apt_id},
        {"_id": 0}
    )
    if analysis:
        for pr in analysis.get("per_participant", []):
            if pr.get("target_participant_id") == target_pid:
                dispute["declarative_analysis"] = pr
                break

    return dispute


def get_arbitration_stats() -> dict:
    """KPI stats for the admin dashboard."""
    escalated = db.declarative_disputes.count_documents({"status": "escalated"})
    total_resolved = db.declarative_disputes.count_documents({"status": "resolved"})
    total_agreed = db.declarative_disputes.count_documents(
        {"status": {"$in": ["agreed_present", "agreed_absent", "agreed_late_penalized"]}}
    )
    awaiting = db.declarative_disputes.count_documents({"status": "awaiting_positions"})

    return {
        "escalated_pending": escalated,
        "total_resolved": total_resolved,
        "total_agreed_by_parties": total_agreed,
        "awaiting_positions": awaiting,
    }
