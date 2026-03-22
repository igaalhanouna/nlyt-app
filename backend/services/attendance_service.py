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
from pymongo import MongoClient
from utils.date_utils import now_utc

logger = logging.getLogger(__name__)

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
client = MongoClient(MONGO_URL)
db = client[DB_NAME]

# Grace window after appointment end before evaluation (minutes)
GRACE_WINDOW_MINUTES = 30

# Feature flag: no auto-capture in V1
AUTO_CAPTURE_ENABLED = False


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
