"""
Attendance Evaluation Service V1
Evaluates participant outcomes after an appointment ends.

Rules (V1 - Conservative):
- cancelled_by_participant in time → waived (cancelled_in_time)
- cancelled_by_participant late → no_show (cancelled_late)
- declined → waived (declined)
- invited (never responded) → waived (no_response)
- guarantee_released → waived (guarantee_released)
- accepted / accepted_pending_guarantee / accepted_guaranteed → manual_review
- No auto on_time or late without proof
- auto_capture_enabled = False by default
"""
import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from utils.date_utils import now_utc

from database import db
logger = logging.getLogger(__name__)


# Grace window after appointment end before evaluation (minutes)
GRACE_WINDOW_MINUTES = 30

# Feature flag: no auto-capture in V1
AUTO_CAPTURE_ENABLED = False


def _get_best_proof_session(appointment_id: str, participant_id: str) -> dict | None:
    """
    Get the best (highest score) completed proof session for a participant.
    Returns the session dict or None if no session exists.
    """
    sessions = list(db.proof_sessions.find(
        {
            "appointment_id": appointment_id,
            "participant_id": participant_id,
            "checked_out_at": {"$ne": None},  # Only completed sessions
        },
        {"_id": 0}
    ).sort("score", -1).limit(1))

    if sessions:
        return sessions[0]

    # Also check active sessions (checked in but not checked out yet)
    active = list(db.proof_sessions.find(
        {
            "appointment_id": appointment_id,
            "participant_id": participant_id,
            "checked_out_at": None,
        },
        {"_id": 0}
    ).sort("heartbeat_count", -1).limit(1))

    if active:
        session = active[0]
        # For active sessions, estimate score based on heartbeat count
        session["score"] = min(session.get("heartbeat_count", 0) * 2, 70)
        session["proof_level"] = "strong" if session["score"] >= 60 else "medium" if session["score"] >= 30 else "weak"
        session["score_breakdown"] = session.get("score_breakdown", {"checkin_points": 15, "duration_points": session["score"] - 15, "video_api_points": 0})
        return session

    return None


def evaluate_participant(participant: dict, appointment: dict) -> dict:
    """
    Evaluate a single participant's attendance outcome.
    Returns: {outcome, decision_basis, confidence, review_required}
    """
    status = participant.get('status', 'invited')

    # --- WAIVED cases (no penalty possible) ---
    if status == 'declined':
        return {
            "outcome": "waived",
            "decision_basis": "declined",
            "confidence": "high",
            "review_required": False
        }

    if status == 'guarantee_released':
        return {
            "outcome": "waived",
            "decision_basis": "guarantee_released",
            "confidence": "high",
            "review_required": False
        }

    if status == 'invited':
        return {
            "outcome": "waived",
            "decision_basis": "no_response",
            "confidence": "high",
            "review_required": False
        }

    # --- CANCELLED cases ---
    if status == 'cancelled_by_participant':
        cancelled_at_str = participant.get('cancelled_at')
        deadline_hours = appointment.get('cancellation_deadline_hours', 24)

        try:
            from services.evidence_service import _parse_appointment_start
            start_utc = _parse_appointment_start(appointment)
            deadline_dt = start_utc - timedelta(hours=deadline_hours)

            if cancelled_at_str:
                from utils.date_utils import parse_iso_datetime
                cancelled_at = parse_iso_datetime(cancelled_at_str)
                if cancelled_at is None:
                    cancelled_at = datetime.fromisoformat(cancelled_at_str.replace('Z', '+00:00'))
                    if cancelled_at.tzinfo is None:
                        cancelled_at = cancelled_at.replace(tzinfo=timezone.utc)

                if cancelled_at <= deadline_dt:
                    return {
                        "outcome": "waived",
                        "decision_basis": "cancelled_in_time",
                        "confidence": "high",
                        "review_required": False
                    }
                else:
                    return {
                        "outcome": "no_show",
                        "decision_basis": "cancelled_late",
                        "confidence": "high",
                        "review_required": False
                    }
            else:
                # No cancellation timestamp — assume late cancellation
                return {
                    "outcome": "no_show",
                    "decision_basis": "cancelled_late",
                    "confidence": "medium",
                    "review_required": True
                }
        except Exception:
            return {
                "outcome": "manual_review",
                "decision_basis": "cancellation_date_parse_error",
                "confidence": "low",
                "review_required": True
            }

    # --- ACCEPTED cases: check evidence before defaulting to manual_review ---
    if status in ('accepted', 'accepted_pending_guarantee', 'accepted_guaranteed'):
        # Look for evidence-based decision
        from services.evidence_service import aggregate_evidence
        aggregation = aggregate_evidence(
            participant.get('appointment_id', appointment.get('appointment_id', '')),
            participant.get('participant_id', ''),
            appointment
        )
        strength = aggregation.get('strength', 'none')
        timing = aggregation.get('timing')
        is_video = appointment.get('appointment_type') == 'video'
        video_provider_ceiling = aggregation.get('video_provider_ceiling')
        video_outcome = aggregation.get('video_outcome')

        # --- VIDEO APPOINTMENT: NLYT Proof is the PRIMARY source ---
        if is_video:
            proof_session = _get_best_proof_session(
                appointment.get('appointment_id', participant.get('appointment_id', '')),
                participant.get('participant_id', '')
            )

            # Build video API context (secondary bonus)
            video_bonus = None
            if aggregation.get('video_provider'):
                video_bonus = {
                    "provider": aggregation.get('video_provider'),
                    "video_outcome": video_outcome,
                    "source_trust": aggregation.get('video_source_trust', 'manual_upload'),
                    "provider_ceiling": video_provider_ceiling,
                }

            if proof_session:
                score = proof_session.get('score', 0)
                proof_level = proof_session.get('proof_level', 'weak')
                score_breakdown = proof_session.get('score_breakdown', {})
                checkin_points = score_breakdown.get('checkin_points', 0)

                proof_context = {
                    "source": "nlyt_proof",
                    "session_id": proof_session.get('session_id'),
                    "score": score,
                    "proof_level": proof_level,
                    "score_breakdown": score_breakdown,
                    "heartbeat_count": proof_session.get('heartbeat_count', 0),
                    "active_duration_seconds": proof_session.get('active_duration_seconds', 0),
                    "video_bonus": video_bonus,
                }

                # NLYT PROOF THRESHOLDS (rebalanced Feb 2026)
                # Strong (≥ 55): clear presence proof
                if score >= 55:
                    is_on_time = checkin_points >= 30  # 40=on_time, 20=slightly late
                    confidence = "high"
                    # Video API confirmation elevates confidence
                    if video_bonus and video_outcome in ("joined_on_time", "joined_late"):
                        proof_context["video_confirmed"] = True

                    return {
                        "outcome": "on_time" if is_on_time else "late",
                        "decision_basis": "nlyt_proof_strong_on_time" if is_on_time else "nlyt_proof_strong_late",
                        "confidence": confidence,
                        "review_required": False,
                        "evidence_summary": aggregation,
                        "proof_context": proof_context,
                    }

                # Medium (30-54): presence detected but ambiguous
                if score >= 30:
                    confidence = "medium"
                    if video_bonus and video_outcome in ("joined_on_time", "joined_late"):
                        confidence = "medium_high"
                        proof_context["video_confirmed"] = True

                    return {
                        "outcome": "manual_review",
                        "decision_basis": "nlyt_proof_medium",
                        "confidence": confidence,
                        "review_required": True,
                        "evidence_summary": aggregation,
                        "proof_context": proof_context,
                    }

                # Weak (< 30): very insufficient proof
                return {
                    "outcome": "no_show",
                    "decision_basis": "nlyt_proof_weak",
                    "confidence": "medium",
                    "review_required": True,
                    "evidence_summary": aggregation,
                    "proof_context": proof_context,
                }

            # --- No NLYT Proof session: fall back to video API (secondary) ---
            if aggregation.get('video_provider'):
                video_trust = aggregation.get('video_source_trust', 'manual_upload')

                # Google Meet alone → always manual_review
                if video_provider_ceiling == "assisted" and strength != "strong":
                    return {
                        "outcome": "manual_review",
                        "decision_basis": "no_proof_meet_assisted_only",
                        "confidence": "low",
                        "review_required": True,
                        "evidence_summary": aggregation,
                        "proof_context": {"source": "video_api_fallback", "video_bonus": video_bonus},
                        "video_context": {
                            "provider": aggregation.get('video_provider'),
                            "provider_ceiling": video_provider_ceiling,
                            "video_outcome": video_outcome,
                            "source_trust": video_trust,
                            "rule": "Pas de session NLYT Proof. Google Meet seul = revue manuelle",
                        }
                    }

                # Zoom/Teams with strong evidence
                if strength == "strong" and video_outcome == "joined_on_time":
                    return {
                        "outcome": "on_time",
                        "decision_basis": "no_proof_video_fallback_on_time",
                        "confidence": "medium",
                        "review_required": True,
                        "evidence_summary": aggregation,
                        "proof_context": {"source": "video_api_fallback", "video_bonus": video_bonus, "note": "Pas de session NLYT Proof. Décision basée sur API vidéo (secondaire)."},
                    }

                if strength == "strong" and video_outcome == "joined_late":
                    return {
                        "outcome": "late",
                        "decision_basis": "no_proof_video_fallback_late",
                        "confidence": "medium",
                        "review_required": True,
                        "evidence_summary": aggregation,
                        "proof_context": {"source": "video_api_fallback", "video_bonus": video_bonus, "note": "Pas de session NLYT Proof. Décision basée sur API vidéo (secondaire)."},
                    }

                # Ambiguous video → manual_review
                return {
                    "outcome": "manual_review",
                    "decision_basis": "no_proof_video_ambiguous",
                    "confidence": "low",
                    "review_required": True,
                    "evidence_summary": aggregation,
                    "proof_context": {"source": "video_api_fallback", "video_bonus": video_bonus},
                }

            # --- No NLYT Proof AND no video API → absent ---
            return {
                "outcome": "no_show",
                "decision_basis": "no_proof_no_video",
                "confidence": "medium",
                "review_required": True,
                "proof_context": {"source": "none", "note": "Aucune session NLYT Proof, aucune preuve API vidéo."},
            }

        # --- PHYSICAL APPOINTMENT (original logic, unchanged) ---
        if strength == 'strong' and timing == 'on_time':
            return {
                "outcome": "on_time",
                "decision_basis": "strong_evidence_on_time",
                "confidence": "high",
                "review_required": False,
                "evidence_summary": aggregation
            }

        if strength == 'strong' and timing == 'late':
            return {
                "outcome": "late",
                "decision_basis": "strong_evidence_late",
                "confidence": "high",
                "review_required": False,
                "evidence_summary": aggregation
            }

        if strength == 'medium' and timing == 'on_time':
            return {
                "outcome": "on_time",
                "decision_basis": "medium_evidence_on_time",
                "confidence": "medium",
                "review_required": True,
                "evidence_summary": aggregation
            }

        if strength == 'medium' and timing == 'late':
            return {
                "outcome": "late",
                "decision_basis": "medium_evidence_late",
                "confidence": "medium",
                "review_required": True,
                "evidence_summary": aggregation
            }

        # Weak or no evidence: manual_review
        basis = {
            'accepted': 'accepted_no_guarantee',
            'accepted_pending_guarantee': 'pending_guarantee',
            'accepted_guaranteed': 'no_proof_of_attendance'
        }
        if strength == 'weak':
            basis_val = "weak_evidence"
        elif strength == 'none':
            basis_val = basis.get(status, 'unknown')
        else:
            basis_val = basis.get(status, 'unknown')

        return {
            "outcome": "manual_review",
            "decision_basis": basis_val,
            "confidence": "low",
            "review_required": True,
            "evidence_summary": aggregation if aggregation.get('evidence_count', 0) > 0 else None
        }

    # --- Fallback ---
    return {
        "outcome": "manual_review",
        "decision_basis": f"unknown_status_{status}",
        "confidence": "low",
        "review_required": True
    }


def evaluate_appointment(appointment_id: str) -> dict:
    """
    Evaluate all participants for a given appointment.
    Idempotent: skips if already evaluated (unless force=True via re-evaluate).
    Returns summary of outcomes.
    """
    appointment = db.appointments.find_one(
        {"appointment_id": appointment_id},
        {"_id": 0}
    )
    if not appointment:
        return {"error": "Rendez-vous introuvable"}

    if appointment.get('status') in ('cancelled', 'deleted'):
        return {"skipped": True, "reason": "Rendez-vous annulé ou supprimé"}

    # Idempotency: skip if already evaluated
    if appointment.get('attendance_evaluated'):
        return {"skipped": True, "reason": "Déjà évalué"}

    participants = list(db.participants.find(
        {"appointment_id": appointment_id},
        {"_id": 0}
    ))

    if not participants:
        db.appointments.update_one(
            {"appointment_id": appointment_id},
            {"$set": {"attendance_evaluated": True, "attendance_evaluated_at": now_utc().isoformat()}}
        )
        return {"skipped": True, "reason": "Aucun participant"}

    records = []
    summary = {"waived": 0, "no_show": 0, "manual_review": 0, "on_time": 0, "late": 0}

    for participant in participants:
        # Skip if already has a record
        existing = db.attendance_records.find_one({
            "appointment_id": appointment_id,
            "participant_id": participant['participant_id']
        })
        if existing:
            summary[existing.get('outcome', 'manual_review')] = summary.get(existing.get('outcome', 'manual_review'), 0) + 1
            continue

        evaluation = evaluate_participant(participant, appointment)

        record = {
            "record_id": str(uuid.uuid4()),
            "appointment_id": appointment_id,
            "participant_id": participant['participant_id'],
            "participant_email": participant.get('email'),
            "participant_name": f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip(),
            "outcome": evaluation['outcome'],
            "decision_basis": evaluation['decision_basis'],
            "confidence": evaluation['confidence'],
            "review_required": evaluation['review_required'],
            "decided_by": "system",
            "decided_at": now_utc().isoformat(),
            "notes": None,
            "auto_capture_enabled": AUTO_CAPTURE_ENABLED
        }
        db.attendance_records.insert_one(record)
        records.append(record)
        summary[evaluation['outcome']] = summary.get(evaluation['outcome'], 0) + 1

    # Mark appointment as evaluated
    db.appointments.update_one(
        {"appointment_id": appointment_id},
        {"$set": {
            "attendance_evaluated": True,
            "attendance_evaluated_at": now_utc().isoformat(),
            "attendance_summary": summary
        }}
    )

    logger.info(f"[ATTENDANCE] Evaluated {appointment_id}: {summary}")
    return {"evaluated": True, "records_created": len(records), "summary": summary}


def reevaluate_appointment(appointment_id: str) -> dict:
    """
    Re-evaluate all participants with fresh evidence.
    Deletes existing auto-classified records and re-runs evaluation.
    Preserves manually reclassified records.
    """
    appointment = db.appointments.find_one(
        {"appointment_id": appointment_id}, {"_id": 0}
    )
    if not appointment:
        return {"error": "Rendez-vous introuvable"}

    # Delete only system-decided records (preserve manual reclassifications)
    db.attendance_records.delete_many({
        "appointment_id": appointment_id,
        "decided_by": "system"
    })

    # Reset evaluation flag
    db.appointments.update_one(
        {"appointment_id": appointment_id},
        {"$set": {"attendance_evaluated": False}}
    )

    # Re-run evaluation
    result = evaluate_appointment(appointment_id)
    logger.info(f"[ATTENDANCE] Re-evaluated {appointment_id}: {result}")
    return result


def run_attendance_evaluation_job():
    """
    Scheduled job: find all ended appointments not yet evaluated and evaluate them.
    An appointment is "ended" when now > start_datetime + duration_minutes + GRACE_WINDOW_MINUTES.
    """
    now = now_utc()
    logger.info(f"[ATTENDANCE] Running evaluation job at {now.isoformat()}")

    # Find active appointments not yet evaluated
    appointments = list(db.appointments.find(
        {
            "status": "active",
            "attendance_evaluated": {"$ne": True},
            "start_datetime": {"$exists": True}
        },
        {"_id": 0, "appointment_id": 1, "start_datetime": 1, "duration_minutes": 1}
    ))

    evaluated_count = 0
    for apt in appointments:
        try:
            from utils.date_utils import parse_iso_datetime
            start_dt = parse_iso_datetime(apt.get('start_datetime', ''))
            if start_dt is None:
                continue

            duration = apt.get('duration_minutes', 60)
            end_dt = start_dt + timedelta(minutes=duration) + timedelta(minutes=GRACE_WINDOW_MINUTES)

            if now >= end_dt:
                result = evaluate_appointment(apt['appointment_id'])
                if result.get('evaluated'):
                    evaluated_count += 1
        except Exception as e:
            logger.error(f"[ATTENDANCE] Error evaluating {apt.get('appointment_id')}: {e}")

    logger.info(f"[ATTENDANCE] Job complete: {evaluated_count} appointments evaluated out of {len(appointments)} candidates")
    return evaluated_count


def reclassify_participant(record_id: str, new_outcome: str, notes: str = None, reviewer_id: str = None) -> dict:
    """
    Manually reclassify a participant's attendance outcome.
    Used by organizer/reviewer to override system decisions.
    """
    valid_outcomes = ('on_time', 'late', 'no_show', 'manual_review', 'waived')
    if new_outcome not in valid_outcomes:
        return {"error": f"Outcome invalide. Valeurs acceptées: {', '.join(valid_outcomes)}"}

    record = db.attendance_records.find_one({"record_id": record_id}, {"_id": 0})
    if not record:
        return {"error": "Enregistrement introuvable"}

    db.attendance_records.update_one(
        {"record_id": record_id},
        {"$set": {
            "outcome": new_outcome,
            "review_required": False,
            "decided_by": reviewer_id or "organizer",
            "decided_at": now_utc().isoformat(),
            "notes": notes,
            "previous_outcome": record.get('outcome'),
            "previous_decision_basis": record.get('decision_basis')
        }}
    )

    # Update appointment summary
    _refresh_appointment_summary(record['appointment_id'])

    return {"success": True, "record_id": record_id, "new_outcome": new_outcome}


def _refresh_appointment_summary(appointment_id: str):
    """Recalculate attendance summary for an appointment."""
    records = list(db.attendance_records.find(
        {"appointment_id": appointment_id},
        {"_id": 0, "outcome": 1}
    ))
    summary = {"waived": 0, "no_show": 0, "manual_review": 0, "on_time": 0, "late": 0}
    for r in records:
        outcome = r.get('outcome', 'manual_review')
        summary[outcome] = summary.get(outcome, 0) + 1

    db.appointments.update_one(
        {"appointment_id": appointment_id},
        {"$set": {"attendance_summary": summary}}
    )
