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


def build_tech_dossier(appointment_id: str, target_participant_id: str) -> dict:
    """Aggregate all technical evidence for the admin dossier."""
    # 1. Admissible proof check
    has_proof = _has_admissible_proof(target_participant_id, appointment_id)

    # 2. NLYT Proof session
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

    # 3. Raw evidence items
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

    # 4. Attendance record (initial evaluation result)
    attendance_record = db.attendance_records.find_one(
        {"appointment_id": appointment_id, "participant_id": target_participant_id},
        {"_id": 0, "outcome": 1, "decision_basis": 1, "confidence_level": 1, "delay_minutes": 1}
    )

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


def get_escalated_disputes_for_admin() -> list:
    """Get all escalated disputes with enrichment for the admin list."""
    disputes = list(db.declarative_disputes.find(
        {"status": "escalated"},
        {"_id": 0}
    ).sort("escalated_at", 1))  # Oldest first (FIFO)

    enriched = []
    for d in disputes:
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

        # Target name
        target_p = db.participants.find_one(
            {"participant_id": d["target_participant_id"]},
            {"_id": 0, "first_name": 1, "last_name": 1, "email": 1}
        )
        if target_p:
            d["target_name"] = f"{target_p.get('first_name', '')} {target_p.get('last_name', '')}".strip()
            d["target_email"] = target_p.get("email", "")

        # Organizer name
        org_p = db.participants.find_one(
            {"appointment_id": d["appointment_id"], "is_organizer": True},
            {"_id": 0, "first_name": 1, "last_name": 1}
        )
        if org_p:
            d["organizer_name"] = f"{org_p.get('first_name', '')} {org_p.get('last_name', '')}".strip()

        # Quick tech check
        d["has_admissible_proof"] = _has_admissible_proof(
            d["target_participant_id"], d["appointment_id"]
        )

        # Age indicator
        escalated_at = d.get("escalated_at")
        if escalated_at:
            from utils.date_utils import parse_iso_datetime
            esc_dt = parse_iso_datetime(escalated_at)
            if esc_dt:
                delta = now_utc() - esc_dt
                d["escalated_days_ago"] = delta.days
                d["escalated_hours_ago"] = int(delta.total_seconds() / 3600)

        # Positions summary
        d["positions"] = {
            "organizer": d.get("organizer_position"),
            "participant": d.get("participant_position"),
        }

        # Remove heavy fields from list
        d.pop("evidence_submissions", None)
        d.pop("resolution", None)

        enriched.append(d)

    return enriched


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
         "duration_minutes": 1, "tolerated_delay_minutes": 1}
    )
    if apt:
        dispute["appointment_title"] = apt.get("title", "")
        dispute["appointment_date"] = apt.get("start_datetime", "")
        dispute["appointment_type"] = apt.get("appointment_type", "")
        dispute["appointment_location"] = apt.get("location_display_name") or apt.get("location", "")
        dispute["appointment_meeting_provider"] = apt.get("meeting_provider", "")
        dispute["appointment_duration_minutes"] = apt.get("duration_minutes", 0)
        dispute["tolerated_delay_minutes"] = apt.get("tolerated_delay_minutes", 0)

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
        {"_id": 0, "first_name": 1, "last_name": 1, "email": 1}
    )
    if org_p:
        dispute["organizer_name"] = f"{org_p.get('first_name', '')} {org_p.get('last_name', '')}".strip()

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
