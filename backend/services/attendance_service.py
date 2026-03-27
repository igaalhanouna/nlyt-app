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


def _has_admissible_proof(participant_id: str, appointment_id: str) -> bool:
    """
    V3 Trustless: Check if a participant has admissible proof of presence (Niveau 1 or 2).
    Returns True if at least one evidence item is NOT purely manual/declarative.
    Niveau 1: GPS in radius, NLYT Proof >= 55
    Niveau 2: QR code, medium GPS, API video (Zoom/Teams)
    Niveau 3 (excluded): manual_checkin alone, Google Meet alone, 0 evidence
    """
    evidence = list(db.evidence_items.find(
        {"appointment_id": appointment_id, "participant_id": participant_id},
        {"_id": 0, "evidence_type": 1, "source": 1, "gps_within_radius": 1}
    ))
    if not evidence:
        return False
    for e in evidence:
        etype = e.get("evidence_type", "")
        source = e.get("source", "")
        # GPS evidence (strong or medium) = Niveau 1-2
        if etype == "gps" and e.get("gps_within_radius"):
            return True
        # QR code = Niveau 2
        if etype == "qr_scan":
            return True
        # Video API (Zoom/Teams) = Niveau 2
        if etype in ("video_api", "video_evidence") and source in ("zoom", "teams", "zoom_api", "teams_api"):
            return True
        # NLYT Proof session with decent score = Niveau 1-2
        if etype == "proof_session":
            return True
    return False


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

        # --- PHYSICAL APPOINTMENT ---
        delay_minutes = aggregation.get('delay_minutes')
        manual_checkin_only = aggregation.get('manual_checkin_only', False)

        if strength == 'strong' and timing == 'on_time':
            return {
                "outcome": "on_time",
                "decision_basis": "strong_evidence_on_time",
                "confidence": "high",
                "review_required": False,
                "delay_minutes": delay_minutes,
                "evidence_summary": aggregation
            }

        if strength == 'strong' and timing == 'late':
            return {
                "outcome": "late",
                "decision_basis": "strong_evidence_late",
                "confidence": "high",
                "review_required": False,
                "delay_minutes": delay_minutes,
                "evidence_summary": aggregation
            }

        if strength == 'medium' and timing == 'on_time':
            # Manual check-in without GPS → always review (no auto-validation on self-declaration alone)
            if manual_checkin_only:
                return {
                    "outcome": "on_time",
                    "decision_basis": "manual_checkin_only_on_time",
                    "confidence": "low",
                    "review_required": True,
                    "delay_minutes": delay_minutes,
                    "evidence_summary": aggregation
                }
            return {
                "outcome": "on_time",
                "decision_basis": "medium_evidence_on_time",
                "confidence": "medium",
                "review_required": False,
                "delay_minutes": delay_minutes,
                "evidence_summary": aggregation
            }

        if strength == 'medium' and timing == 'late':
            # Manual check-in without GPS → always review (no auto-penalty on self-declaration alone)
            if manual_checkin_only:
                return {
                    "outcome": "late",
                    "decision_basis": "manual_checkin_only_late",
                    "confidence": "low",
                    "review_required": True,
                    "delay_minutes": delay_minutes,
                    "evidence_summary": aggregation
                }
            return {
                "outcome": "late",
                "decision_basis": "medium_evidence_late",
                "confidence": "medium",
                "review_required": False,
                "delay_minutes": delay_minutes,
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
            "delay_minutes": evaluation.get('delay_minutes'),
            "tolerated_delay_minutes": appointment.get('tolerated_delay_minutes', 0),
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

    # Post-evaluation: trigger capture/release/distribution
    _process_financial_outcomes(appointment_id, appointment, participants)

    # Post-engagement viral emails (non-blocking)
    try:
        from services.financial_emails import send_post_engagement_emails
        send_post_engagement_emails(appointment_id, appointment)
    except Exception as e:
        logger.warning(f"[ATTENDANCE] Post-engagement email error (non-blocking): {e}")

    # Notify organizer if there are review_required cases (non-blocking)
    review_records = [r for r in records if r.get('review_required')]
    if review_records:
        try:
            _send_review_notification(appointment, review_records)
        except Exception as e:
            logger.warning(f"[ATTENDANCE] Review notification error (non-blocking): {e}")

    return {"evaluated": True, "records_created": len(records), "summary": summary}


def _send_review_notification(appointment: dict, review_records: list):
    """Send email to organizer about pending review cases. Non-blocking."""
    import asyncio

    organizer = db.users.find_one(
        {"user_id": appointment['organizer_id']},
        {"_id": 0, "email": 1, "first_name": 1, "last_name": 1}
    )
    if not organizer:
        return

    # Build participant summaries
    basis_labels = {
        "manual_checkin_only_on_time": "Check-in manuel sans GPS",
        "manual_checkin_only_late": "Check-in manuel sans GPS (retard)",
        "no_proof_of_attendance": "Aucune preuve de presence",
        "weak_evidence": "Preuve insuffisante",
        "nlyt_proof_medium": "NLYT Proof partiel",
        "nlyt_proof_weak": "NLYT Proof insuffisant",
        "no_proof_meet_assisted_only": "Google Meet seul",
        "no_proof_video_fallback_on_time": "API video seule",
        "no_proof_video_fallback_late": "API video en retard",
        "no_proof_no_video": "Aucune preuve video",
        "cancelled_late": "Annulation tardive",
    }

    summaries = []
    for r in review_records:
        participant = db.participants.find_one(
            {"participant_id": r.get('participant_id')},
            {"_id": 0, "first_name": 1, "last_name": 1, "email": 1}
        )
        name = "Participant"
        if participant:
            name = " ".join(filter(None, [participant.get('first_name'), participant.get('last_name')])) or participant.get('email', 'Participant')
        reason = basis_labels.get(r.get('decision_basis'), r.get('decision_basis', 'Preuve insuffisante'))
        summaries.append({"name": name, "reason": reason})

    org_name = " ".join(filter(None, [organizer.get('first_name'), organizer.get('last_name')])) or "Organisateur"

    from services.email_service import EmailService
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(EmailService.send_review_required_notification(
                organizer_email=organizer['email'],
                organizer_name=org_name,
                appointment_title=appointment.get('title', 'Rendez-vous'),
                appointment_id=appointment.get('appointment_id', ''),
                pending_count=len(review_records),
                participant_summaries=summaries,
            ))
        else:
            loop.run_until_complete(EmailService.send_review_required_notification(
                organizer_email=organizer['email'],
                organizer_name=org_name,
                appointment_title=appointment.get('title', 'Rendez-vous'),
                appointment_id=appointment.get('appointment_id', ''),
                pending_count=len(review_records),
                participant_summaries=summaries,
            ))
    except RuntimeError:
        logger.warning("[ATTENDANCE] Could not send review notification email (no event loop)")



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
    Triggers financial hooks on outcome transitions.
    """
    valid_outcomes = ('on_time', 'late', 'no_show', 'manual_review', 'waived')
    if new_outcome not in valid_outcomes:
        return {"error": f"Outcome invalide. Valeurs acceptées: {', '.join(valid_outcomes)}"}

    record = db.attendance_records.find_one({"record_id": record_id}, {"_id": 0})
    if not record:
        return {"error": "Enregistrement introuvable"}

    previous_outcome = record.get('outcome')

    db.attendance_records.update_one(
        {"record_id": record_id},
        {"$set": {
            "outcome": new_outcome,
            "review_required": False,
            "decided_by": reviewer_id or "organizer",
            "decided_at": now_utc().isoformat(),
            "notes": notes,
            "previous_outcome": previous_outcome,
            "previous_decision_basis": record.get('decision_basis')
        }}
    )

    # Update appointment summary
    _refresh_appointment_summary(record['appointment_id'])

    # Post-reclassification financial hooks
    _process_reclassification(record, previous_outcome, new_outcome)

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



# ─── Financial Hooks (Phase 3) ────────────────────────────────────


def _process_financial_outcomes(appointment_id: str, appointment: dict, participants: list):
    """
    Post-evaluation hook: process capture/release for all evaluated participants.
    
    V3 Trustless rules:
    - Beneficiary must have admissible proof (Niveau 1-2) to receive compensation
    - Cas A: payeur absent (established) + beneficiary unproven → capture, compensation to charity/platform
    - Cas B: nobody has Niveau 1-2 proof → all gelé, no capture, no distribution
    """
    from services.stripe_guarantee_service import StripeGuaranteeService
    from services.distribution_service import create_distribution

    penalty_amount = appointment.get('penalty_amount', 0)
    if not penalty_amount or penalty_amount <= 0:
        return  # No penalty → no financial flow

    records = list(db.attendance_records.find(
        {"appointment_id": appointment_id},
        {"_id": 0}
    ))

    # --- V3 Cas B detection: if nobody has Niveau 1-2 proof, everything is gelé ---
    anyone_has_proof = False
    for r in records:
        if r.get('outcome') in ('on_time', 'late') and not r.get('review_required', True):
            pid = r['participant_id']
            if _has_admissible_proof(pid, appointment_id):
                anyone_has_proof = True
                break
        elif r.get('outcome') in ('on_time', 'late') and r.get('review_required', False):
            pid = r['participant_id']
            if _has_admissible_proof(pid, appointment_id):
                anyone_has_proof = True
                break

    if not anyone_has_proof:
        # Cas B: insufficient global proof → force all to manual_review, no financial action
        logger.info(f"[FINANCIAL][CAS_B] No participant has Niveau 1-2 proof for {appointment_id}. All gelé.")
        for r in records:
            if r.get('outcome') in ('no_show', 'late') and not r.get('review_required', True):
                db.attendance_records.update_one(
                    {"record_id": r['record_id']},
                    {"$set": {
                        "review_required": True,
                        "cas_b_override": True,
                        "cas_b_reason": "Aucun participant avec preuve admissible. Situation insuffisamment documentee."
                    }}
                )
                logger.info(f"[FINANCIAL][CAS_B] Forced review_required for {r['record_id']} (was {r['outcome']})")
        return

    # --- Build list of eligible beneficiaries (V3: on_time OR late, WITH admissible proof) ---
    eligible_beneficiaries = []
    for r in records:
        if r.get('outcome') in ('on_time', 'late'):
            p = _find_participant(participants, r['participant_id'])
            if p and p.get('user_id'):
                if _has_admissible_proof(r['participant_id'], appointment_id):
                    eligible_beneficiaries.append({
                        "user_id": p["user_id"],
                        "participant_id": p["participant_id"],
                    })
                else:
                    logger.info(f"[FINANCIAL][GARDE_FOU] {r['participant_id']} has outcome={r['outcome']} but no admissible proof. Excluded from compensation.")

    for record in records:
        if record.get('review_required', True):
            continue  # manual_review → no action until reclassified

        participant = _find_participant(participants, record['participant_id'])
        if not participant:
            continue

        guarantee = db.payment_guarantees.find_one(
            {"participant_id": record['participant_id'], "appointment_id": appointment_id},
            {"_id": 0}
        )
        if not guarantee or guarantee.get('status') not in ('completed', 'dev_pending'):
            continue  # No valid guarantee → no financial action

        outcome = record.get('outcome')

        if outcome in ('no_show', 'late'):
            # Cas A check: capture only if at least 1 other has admissible proof
            no_show_user_id = participant.get('user_id')
            others_with_proof = [b for b in eligible_beneficiaries if b["user_id"] != no_show_user_id]
            if not others_with_proof:
                # No other participant has admissible proof → don't auto-capture, force review
                logger.info(f"[FINANCIAL][CAS_A_BLOCK] No proven beneficiary for {record['participant_id']} capture. Forcing review.")
                db.attendance_records.update_one(
                    {"record_id": record['record_id']},
                    {"$set": {
                        "review_required": True,
                        "cas_a_override": True,
                        "cas_a_reason": "Absence etablie mais aucun beneficiaire avec preuve admissible."
                    }}
                )
                continue

            capture_reason = "no_show" if outcome == "no_show" else "late_beyond_tolerance"
            _execute_capture_and_distribution(
                appointment, participant, guarantee, eligible_beneficiaries, capture_reason
            )
        elif outcome == 'on_time':
            _execute_release(guarantee)
        elif outcome == 'late' and record.get('review_required', True):
            pass  # Already handled above


def _execute_capture_and_distribution(
    appointment: dict, participant: dict, guarantee: dict, present_participants: list,
    capture_reason: str = "no_show"
):
    """Capture guarantee and create distribution."""
    from services.stripe_guarantee_service import StripeGuaranteeService
    from services.distribution_service import create_distribution

    guarantee_id = guarantee['guarantee_id']

    # Check if already captured or has distribution
    if guarantee.get('status') == 'captured':
        logger.info(f"[FINANCIAL] Guarantee {guarantee_id} already captured")
        return
    existing_dist = db.distributions.find_one({"guarantee_id": guarantee_id})
    if existing_dist:
        logger.info(f"[FINANCIAL] Distribution already exists for guarantee {guarantee_id}")
        return

    # Capture
    capture_result = StripeGuaranteeService.capture_guarantee(guarantee_id, capture_reason)
    if not capture_result.get('success'):
        logger.error(f"[FINANCIAL] Capture failed for {guarantee_id}: {capture_result.get('error')}")
        return

    # Determine amounts
    penalty_amount = guarantee.get('penalty_amount', 0)
    capture_amount_cents = int(round(penalty_amount * 100))
    if capture_amount_cents <= 0:
        return

    # Determine if organizer no_show
    is_organizer = participant.get('is_organizer', False)
    organizer_user_id = appointment.get('organizer_id')

    # Filter out the no_show user from present participants
    no_show_user_id = participant.get('user_id')
    filtered_present = [p for p in present_participants if p["user_id"] != no_show_user_id]

    # Get payment intent ID
    refreshed_g = db.payment_guarantees.find_one({"guarantee_id": guarantee_id}, {"_id": 0})
    pi_id = refreshed_g.get('stripe_payment_intent_id', '') if refreshed_g else ''

    create_distribution(
        appointment_id=appointment['appointment_id'],
        guarantee_id=guarantee_id,
        no_show_participant_id=participant['participant_id'],
        no_show_user_id=no_show_user_id or '',
        no_show_is_organizer=is_organizer,
        capture_amount_cents=capture_amount_cents,
        capture_currency=appointment.get('penalty_currency', 'eur'),
        stripe_payment_intent_id=pi_id,
        platform_commission_percent=appointment.get('platform_commission_percent', 20.0),
        affected_compensation_percent=appointment.get('affected_compensation_percent', 50.0),
        charity_percent=appointment.get('charity_percent', 0.0),
        charity_association_id=appointment.get('charity_association_id'),
        organizer_user_id=organizer_user_id or '',
        present_participants=filtered_present,
    )
    logger.info(f"[FINANCIAL] Captured + distributed for guarantee {guarantee_id}")

    # Send capture email to no-show user (non-blocking)
    try:
        from services.financial_emails import send_capture_email
        dist_doc = db.distributions.find_one({"guarantee_id": guarantee_id}, {"_id": 0})
        if dist_doc:
            send_capture_email(
                user_id=participant.get('user_id', ''),
                appointment_title=appointment.get('title', 'RDV'),
                appointment_date=appointment.get('start_datetime', ''),
                capture_amount_cents=dist_doc['capture_amount_cents'],
                distribution_id=dist_doc['distribution_id'],
                beneficiaries=dist_doc.get('beneficiaries', []),
                hold_expires_at=dist_doc.get('hold_expires_at', ''),
            )
    except Exception as e:
        logger.warning(f"[FINANCIAL] Capture email error (non-blocking): {e}")


def _execute_release(guarantee: dict):
    """Release a guarantee (participant was present)."""
    from services.stripe_guarantee_service import StripeGuaranteeService

    guarantee_id = guarantee['guarantee_id']
    if guarantee.get('status') in ('released', 'captured'):
        return

    result = StripeGuaranteeService.release_guarantee(guarantee_id, "present")
    if result.get('success'):
        logger.info(f"[FINANCIAL] Released guarantee {guarantee_id}")
    else:
        logger.warning(f"[FINANCIAL] Release failed for {guarantee_id}: {result.get('error')}")


def _process_reclassification(record: dict, previous_outcome: str, new_outcome: str):
    """
    Post-reclassification hook: handle financial transitions.

    Penalized outcomes: no_show, late (beyond tolerance)
    Non-penalized outcomes: on_time, waived

    Transitions:
    - manual_review → no_show/late : capture + distribution
    - manual_review → on_time : release
    - no_show/late → on_time : cancel distribution + release
    - on_time → no_show/late : capture + distribution (if guarantee exists)
    """
    from services.distribution_service import cancel_distribution as cancel_dist

    PENALIZED = ('no_show', 'late')
    NON_PENALIZED = ('on_time', 'waived')

    appointment_id = record['appointment_id']
    participant_id = record['participant_id']

    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        return

    penalty_amount = appointment.get('penalty_amount', 0)
    if not penalty_amount or penalty_amount <= 0:
        return

    participants = list(db.participants.find({"appointment_id": appointment_id}, {"_id": 0}))
    participant = _find_participant(participants, participant_id)
    if not participant:
        return

    guarantee = db.payment_guarantees.find_one(
        {"participant_id": participant_id, "appointment_id": appointment_id},
        {"_id": 0}
    )
    if not guarantee:
        return  # No guarantee → no financial action

    # Build present participants list (on_time only — late is penalized)
    records = list(db.attendance_records.find({"appointment_id": appointment_id}, {"_id": 0}))
    present_participants = []
    for r in records:
        if r.get('outcome') == 'on_time':
            p = _find_participant(participants, r['participant_id'])
            if p and p.get('user_id'):
                present_participants.append({
                    "user_id": p["user_id"],
                    "participant_id": p["participant_id"],
                })

    # Handle transition: was penalized → now non-penalized → cancel distribution + release
    if previous_outcome in PENALIZED and new_outcome in NON_PENALIZED:
        existing_dist = db.distributions.find_one({"guarantee_id": guarantee['guarantee_id']}, {"_id": 0})
        if existing_dist and existing_dist['status'] not in ('cancelled', 'completed'):
            cancel_dist(existing_dist['distribution_id'], f"Reclassifié: {previous_outcome} → {new_outcome}")

        if guarantee.get('status') in ('completed', 'dev_pending'):
            _execute_release(guarantee)

        logger.info(f"[FINANCIAL] Reclassification {previous_outcome}→{new_outcome}: cancelled distribution + released guarantee")

    # Handle transition: was non-penalized → now penalized → capture + distribution
    elif new_outcome in PENALIZED and previous_outcome not in PENALIZED:
        if guarantee.get('status') in ('completed', 'dev_pending'):
            capture_reason = "no_show" if new_outcome == "no_show" else "late_beyond_tolerance"
            _execute_capture_and_distribution(appointment, participant, guarantee, present_participants, capture_reason)
            logger.info(f"[FINANCIAL] Reclassification {previous_outcome}→{new_outcome}: captured + distributed")


def _find_participant(participants: list, participant_id: str) -> dict | None:
    """Find a participant by ID in a list."""
    for p in participants:
        if p.get('participant_id') == participant_id:
            return p
    return None


# ─── Review Timeout (Phase 4) ────────────────────────────────────

REVIEW_TIMEOUT_DAYS = 15


def run_review_timeout_job():
    """
    Scheduler job: auto-resolve review_required records after REVIEW_TIMEOUT_DAYS.
    
    Rule (decision produit): after 15 days without organizer action,
    the guarantee is RELEASED without penalty (option C — defensive).
    This prevents indefinite financial deadlocks.
    """
    now = now_utc()
    cutoff = now - timedelta(days=REVIEW_TIMEOUT_DAYS)
    cutoff_iso = cutoff.isoformat()

    # Find all unresolved review_required records older than the timeout
    stale_records = list(db.attendance_records.find(
        {
            "review_required": True,
            "decided_by": "system",
            "decided_at": {"$lte": cutoff_iso},
        },
        {"_id": 0}
    ))

    if not stale_records:
        return 0

    resolved_count = 0
    # Group by appointment to batch process
    appointment_ids = list({r['appointment_id'] for r in stale_records})

    for apt_id in appointment_ids:
        apt_records = [r for r in stale_records if r['appointment_id'] == apt_id]

        for record in apt_records:
            # Auto-resolve: release guarantee (no penalty — doubt in favor of participant)
            new_outcome = "waived"

            db.attendance_records.update_one(
                {"record_id": record['record_id']},
                {"$set": {
                    "outcome": new_outcome,
                    "review_required": False,
                    "decided_by": "system_timeout",
                    "decided_at": now.isoformat(),
                    "previous_outcome": record.get('outcome'),
                    "previous_decision_basis": record.get('decision_basis'),
                    "notes": f"Auto-résolu après {REVIEW_TIMEOUT_DAYS} jours sans revue. Garantie libérée (doute en faveur du participant).",
                }}
            )

            # Release the guarantee if one exists
            guarantee = db.payment_guarantees.find_one(
                {
                    "participant_id": record['participant_id'],
                    "appointment_id": apt_id
                },
                {"_id": 0}
            )
            if guarantee and guarantee.get('status') in ('completed', 'dev_pending'):
                _execute_release(guarantee)

            resolved_count += 1

        # Refresh appointment summary
        _refresh_appointment_summary(apt_id)

    logger.info(f"[ATTENDANCE] Review timeout: auto-resolved {resolved_count} records across {len(appointment_ids)} appointments")
    return resolved_count
