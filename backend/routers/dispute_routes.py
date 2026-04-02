"""
Dispute Routes — V4 Trustless Symmetric Disputes

Replaces asymmetric accuser/accused model with symmetric positions.
Both parties (organizer + participant) submit positions independently.
No penalty without double explicit confirmation.
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import logging

from middleware.auth_middleware import get_current_user
from database import db

logger = logging.getLogger(__name__)
router = APIRouter()


class PositionBody(BaseModel):
    position: str  # confirmed_present | confirmed_absent | confirmed_late_penalized


class EvidenceSubmissionBody(BaseModel):
    evidence_type: str  # screenshot | message | document | text_statement
    content_url: Optional[str] = None
    text_content: Optional[str] = None


class ResolveDisputeBody(BaseModel):
    final_outcome: str
    resolution_note: str


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

RESOLVED_STATUSES = ("resolved", "agreed_present", "agreed_absent", "agreed_late_penalized")

POSITION_LABELS = {
    "confirmed_present": "Presence confirmee",
    "confirmed_absent": "Absence confirmee",
    "confirmed_late_penalized": "Retard penalisable confirme",
}


def _get_anonymized_summary(appointment_id: str, target_pid: str, viewer_user_id: str = None) -> dict:
    """Build enriched declaration summary: per-participant view, self-declaration, roles, contradiction level."""
    sheets = list(db.attendance_sheets.find(
        {"appointment_id": appointment_id, "status": "submitted"},
        {"_id": 0}
    ))

    absent_count = 0
    present_count = 0
    unknown_count = 0
    declarants = []
    target_self_declaration = None

    for s in sheets:
        submitter_pid = s.get('submitted_by_participant_id')
        submitter_uid = s.get('submitted_by_user_id', '')

        submitter_doc = db.participants.find_one(
            {"participant_id": submitter_pid},
            {"_id": 0, "first_name": 1, "is_organizer": 1}
        )
        first_name = (submitter_doc.get('first_name') or '').strip() if submitter_doc else ''
        is_organizer = bool(submitter_doc.get('is_organizer')) if submitter_doc else False

        for d in s.get('declarations', []):
            if d['target_participant_id'] != target_pid:
                continue

            status = d.get('declared_status', 'unknown')

            # Target's own self-declaration
            if submitter_pid == target_pid:
                target_self_declaration = status
                continue

            # Third-party declaration about the target
            if status == 'absent':
                absent_count += 1
            elif status in ('present_on_time', 'present_late'):
                present_count += 1
            else:
                unknown_count += 1

            declarants.append({
                "first_name": first_name or "Un participant",
                "declared_status": status,
                "is_me": (viewer_user_id is not None and submitter_uid == viewer_user_id),
                "is_organizer": is_organizer,
            })

    has_tech = db.evidence_items.count_documents({
        "participant_id": target_pid,
        "appointment_id": appointment_id
    }) > 0

    # Contradiction level
    total_third = absent_count + present_count + unknown_count
    if total_third == 0:
        contradiction_level = "no_declarations"
    elif absent_count == 0 and unknown_count == 0:
        contradiction_level = "unanimous_present"
    elif present_count == 0 and unknown_count == 0:
        if has_tech and target_self_declaration in ('present_on_time', 'present_late'):
            contradiction_level = "contradiction_with_proof"
        else:
            contradiction_level = "unanimous_absent"
    elif absent_count > present_count:
        contradiction_level = "majority_absent"
    elif present_count > absent_count:
        contradiction_level = "majority_present"
    else:
        contradiction_level = "disagreement"

    # Summary phrase
    target_doc = db.participants.find_one(
        {"participant_id": target_pid},
        {"_id": 0, "first_name": 1}
    )
    target_name = (target_doc.get('first_name') or 'Le participant').strip() if target_doc else 'Le participant'

    summary_phrases = {
        "no_declarations": f"Aucune declaration de tiers sur {target_name}.",
        "unanimous_present": f"Tous les participants confirment la presence de {target_name}.",
        "unanimous_absent": f"Tous les participants declarent {target_name} absent.",
        "majority_present": f"Majorite des participants declarent {target_name} present ({present_count} present / {absent_count} absent).",
        "majority_absent": f"Majorite des participants declarent {target_name} absent ({absent_count} absent / {present_count} present).",
        "disagreement": f"Desaccord entre les participants sur la presence de {target_name}.",
        "contradiction_with_proof": f"{target_name} est declare absent mais une trace technique a ete detectee.",
    }

    return {
        "declared_absent_count": absent_count,
        "declared_present_count": present_count,
        "unknown_count": unknown_count,
        "has_tech_evidence": has_tech,
        "declarants": declarants,
        "target_self_declaration": target_self_declaration,
        "target_name": target_name,
        "contradiction_level": contradiction_level,
        "summary_phrase": summary_phrases.get(contradiction_level, ""),
    }


def _is_dispute_counterpart(user_id: str, appointment_id: str, target_participant_id: str) -> bool:
    """Check if user is the true counterpart: submitted a declaration about the target."""
    sheet = db.attendance_sheets.find_one({
        "appointment_id": appointment_id,
        "submitted_by_user_id": user_id,
        "status": "submitted",
    }, {"_id": 0, "declarations": 1})
    if not sheet:
        return False
    return any(
        decl.get("target_participant_id") == target_participant_id
        for decl in sheet.get("declarations", [])
    )


def _get_other_party_name(d: dict, my_role: str) -> str:
    """Get the first name of the party opposite to the current user."""
    deadlock = d.get("organizer_user_id") == d.get("target_user_id")

    if my_role == "organizer":
        if deadlock:
            # Target = organizer → other party is the counterpart, not the target
            p = db.participants.find_one(
                {"appointment_id": d["appointment_id"], "participant_id": {"$ne": d["target_participant_id"]}, "user_id": {"$ne": None}},
                {"_id": 0, "first_name": 1}
            )
        else:
            p = db.participants.find_one(
                {"participant_id": d.get("target_participant_id")},
                {"_id": 0, "first_name": 1}
            )
    else:
        # Participant/counterpart → other party is the organizer
        org_user_id = d.get("organizer_user_id")
        p = db.participants.find_one(
            {"appointment_id": d["appointment_id"], "user_id": org_user_id},
            {"_id": 0, "first_name": 1}
        )

    return (p.get("first_name") or "").strip() if p else ""


def _enrich_dispute_for_user(d: dict, user_id: str) -> dict:
    """Add computed fields for the current user."""
    is_organizer = (d.get('organizer_user_id') == user_id)
    is_target = (d.get('target_user_id') == user_id)

    if is_organizer:
        my_role = "organizer"
        my_position = d.get("organizer_position")
        other_responded = d.get("participant_position") is not None
    elif is_target:
        my_role = "participant"
        my_position = d.get("participant_position")
        other_responded = d.get("organizer_position") is not None
    elif (d.get('organizer_user_id') == d.get('target_user_id')
          and _is_dispute_counterpart(user_id, d['appointment_id'], d['target_participant_id'])):
        # Deadlock fix: target IS the organizer → the true counterpart gets "participant" role
        my_role = "participant"
        my_position = d.get("participant_position")
        other_responded = d.get("organizer_position") is not None
    else:
        my_role = "observer"
        my_position = None
        other_responded = False

    is_resolved = d.get("status") in RESOLVED_STATUSES
    can_submit_position = (
        my_role in ("organizer", "participant")
        and my_position is None
        and d.get("status") == "awaiting_positions"
    )
    can_submit_evidence = d.get("status") in ("awaiting_positions", "awaiting_evidence", "escalated")

    # Compute display state
    org_pos = d.get("organizer_position")
    par_pos = d.get("participant_position")
    status = d.get("status")

    if status in RESOLVED_STATUSES:
        display_state = "resolved"
    elif status == "escalated":
        display_state = "arbitration"
    elif org_pos is not None and par_pos is not None:
        display_state = "arbitration"  # Both responded but disagreed (otherwise would be resolved)
    elif org_pos is not None or par_pos is not None:
        display_state = "waiting_other"
    else:
        display_state = "waiting_both"

    d['my_role'] = my_role
    d['my_position'] = my_position
    d['is_target'] = is_target
    d['other_party_responded'] = other_responded
    d['can_submit_position'] = can_submit_position
    d['can_submit_evidence'] = can_submit_evidence
    d['is_resolved'] = is_resolved
    d['display_state'] = display_state
    d['other_party_name'] = _get_other_party_name(d, my_role) if my_role != "observer" else ""

    return d


# ═══════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════

@router.get("/mine")
async def list_my_disputes(request: Request):
    """List disputes where the current user is involved."""
    user = await get_current_user(request)
    user_id = user['user_id']

    user_participants = list(db.participants.find(
        {"user_id": user_id},
        {"_id": 0, "appointment_id": 1}
    ))
    apt_ids = list({p['appointment_id'] for p in user_participants})

    if not apt_ids:
        return {"disputes": [], "count": 0}

    disputes = list(db.declarative_disputes.find(
        {"appointment_id": {"$in": apt_ids}},
        {"_id": 0}
    ).sort("created_at", -1))

    for d in disputes:
        apt = db.appointments.find_one(
            {"appointment_id": d['appointment_id']},
            {"_id": 0, "title": 1, "start_datetime": 1, "appointment_type": 1,
             "location": 1, "location_display_name": 1, "meeting_provider": 1,
             "duration_minutes": 1}
        )
        if apt:
            d['appointment_title'] = apt.get('title', '')
            d['appointment_date'] = apt.get('start_datetime', '')
            d['appointment_type'] = apt.get('appointment_type', '')
            d['appointment_location'] = apt.get('location_display_name') or apt.get('location', '')
            d['appointment_meeting_provider'] = apt.get('meeting_provider', '')
            d['appointment_duration_minutes'] = apt.get('duration_minutes', 0)

        target_p = db.participants.find_one(
            {"participant_id": d['target_participant_id']},
            {"_id": 0, "first_name": 1, "last_name": 1}
        )
        if target_p:
            d['target_name'] = f"{target_p.get('first_name', '')} {target_p.get('last_name', '')}".strip()

        d['declaration_summary'] = _get_anonymized_summary(d['appointment_id'], d['target_participant_id'], user_id)
        d['evidence_submissions_count'] = len(d.get('evidence_submissions', []))
        d.pop('evidence_submissions', None)

        _enrich_dispute_for_user(d, user_id)

    return {"disputes": disputes, "count": len(disputes)}


@router.get("/decisions/mine")
async def list_my_decisions(request: Request):
    """List resolved/agreed disputes for the current user, enriched with financial context."""
    user = await get_current_user(request)
    user_id = user['user_id']

    user_participants = list(db.participants.find(
        {"user_id": user_id},
        {"_id": 0, "appointment_id": 1, "participant_id": 1, "is_organizer": 1}
    ))
    if not user_participants:
        return {"decisions": [], "count": 0}

    apt_ids = list({p['appointment_id'] for p in user_participants})
    participant_map = {p['appointment_id']: p for p in user_participants}

    resolved_statuses = ["resolved", "agreed_present", "agreed_absent", "agreed_late_penalized"]
    disputes = list(db.declarative_disputes.find(
        {"appointment_id": {"$in": apt_ids}, "status": {"$in": resolved_statuses}},
        {"_id": 0}
    ).sort("created_at", -1))

    decisions = []
    for d in disputes:
        apt_id = d['appointment_id']
        apt = db.appointments.find_one(
            {"appointment_id": apt_id},
            {"_id": 0, "title": 1, "start_datetime": 1, "appointment_type": 1,
             "location": 1, "location_display_name": 1, "meeting_provider": 1,
             "penalty_amount": 1, "penalty_currency": 1,
             "platform_commission_percent": 1, "charity_percent": 1}
        )
        if apt:
            d['appointment_title'] = apt.get('title', '')
            d['appointment_date'] = apt.get('start_datetime', '')
            d['appointment_type'] = apt.get('appointment_type', '')
            d['appointment_location'] = apt.get('location_display_name') or apt.get('location', '')
            d['appointment_meeting_provider'] = apt.get('meeting_provider', '')

        target_p = db.participants.find_one(
            {"participant_id": d['target_participant_id']},
            {"_id": 0, "first_name": 1, "last_name": 1}
        )
        if target_p:
            d['target_name'] = f"{target_p.get('first_name', '')} {target_p.get('last_name', '')}".strip()

        # Resolution info
        resolution = d.get('resolution', {})
        final_outcome = resolution.get('final_outcome', '')
        d['final_outcome'] = final_outcome
        d['resolution_note'] = resolution.get('resolution_note', '')
        d['resolved_at'] = resolution.get('resolved_at', '')

        # User role in this dispute
        my_part = participant_map.get(apt_id, {})
        is_organizer = my_part.get('is_organizer', False)
        is_target = my_part.get('participant_id') == d.get('target_participant_id')
        d['my_role'] = 'organizer' if is_organizer else ('target' if is_target else 'observer')

        # Financial impact from user's perspective
        penalty = apt.get('penalty_amount', 0) if apt else 0
        cur = (apt.get('penalty_currency', 'eur') if apt else 'eur').upper()
        comm_pct = apt.get('platform_commission_percent', 0) if apt else 0
        charity_pct = apt.get('charity_percent', 0) if apt else 0
        penalty_cents = int(penalty * 100)
        comp_cents = penalty_cents - int(penalty_cents * comm_pct / 100) - int(penalty_cents * charity_pct / 100)

        if final_outcome == 'on_time' or d['status'] == 'agreed_present' or final_outcome == 'waived':
            d['financial_impact'] = {'type': 'neutral', 'label': 'Aucune penalite', 'amount': 0}
        elif is_target:
            d['financial_impact'] = {
                'type': 'debit',
                'label': f'Debite de {penalty:.0f}{cur}' if penalty > 0 else 'Penalite appliquee',
                'amount': penalty,
                'currency': cur,
            }
        elif is_organizer:
            d['financial_impact'] = {
                'type': 'credit',
                'label': f'Recu {comp_cents/100:.0f}{cur}' if comp_cents > 0 else 'Compensation versee',
                'amount': comp_cents / 100,
                'currency': cur,
            }
        else:
            d['financial_impact'] = {'type': 'neutral', 'label': 'Non concerne', 'amount': 0}

        # Cleanup
        d.pop('evidence_submissions', None)
        d.pop('resolution', None)

        _enrich_dispute_for_user(d, user_id)
        decisions.append(d)

    return {"decisions": decisions, "count": len(decisions)}



@router.get("/{dispute_id}")
async def get_dispute_detail(dispute_id: str, request: Request):
    """Get dispute detail with symmetric role-based view."""
    user = await get_current_user(request)

    dispute = db.declarative_disputes.find_one({"dispute_id": dispute_id}, {"_id": 0})
    if not dispute:
        raise HTTPException(status_code=404, detail="Litige introuvable")

    participant = db.participants.find_one({
        "appointment_id": dispute['appointment_id'],
        "user_id": user['user_id']
    })
    if not participant:
        raise HTTPException(status_code=403, detail="Acces refuse")

    # Enrich with appointment info + financial context
    apt = db.appointments.find_one(
        {"appointment_id": dispute['appointment_id']},
        {"_id": 0, "title": 1, "start_datetime": 1, "appointment_type": 1,
         "location": 1, "location_display_name": 1, "meeting_provider": 1,
         "duration_minutes": 1, "penalty_amount": 1, "penalty_currency": 1,
         "platform_commission_percent": 1, "charity_percent": 1}
    )
    if apt:
        dispute['appointment_title'] = apt.get('title', '')
        dispute['appointment_date'] = apt.get('start_datetime', '')
        dispute['appointment_type'] = apt.get('appointment_type', '')
        dispute['appointment_location'] = apt.get('location_display_name') or apt.get('location', '')
        dispute['appointment_meeting_provider'] = apt.get('meeting_provider', '')
        dispute['appointment_duration_minutes'] = apt.get('duration_minutes', 0)

        # Financial context for detail view
        penalty = apt.get('penalty_amount', 0)
        cur = apt.get('penalty_currency', 'eur')
        comm_pct = apt.get('platform_commission_percent', 0)
        charity_pct = apt.get('charity_percent', 0)
        p_cents = int(penalty * 100)
        platform_cents = int(p_cents * comm_pct / 100)
        charity_cents = int(p_cents * charity_pct / 100)
        comp_cents = p_cents - platform_cents - charity_cents
        dispute['financial_context'] = {
            'penalty_amount': penalty,
            'penalty_currency': cur,
            'platform_commission_percent': comm_pct,
            'charity_percent': charity_pct,
            'platform_amount': platform_cents / 100,
            'charity_amount': charity_cents / 100,
            'compensation_amount': comp_cents / 100,
        }

    target_p = db.participants.find_one(
        {"participant_id": dispute['target_participant_id']},
        {"_id": 0, "first_name": 1, "last_name": 1}
    )
    if target_p:
        dispute['target_name'] = f"{target_p.get('first_name', '')} {target_p.get('last_name', '')}".strip()

    dispute['declaration_summary'] = _get_anonymized_summary(
        dispute['appointment_id'], dispute['target_participant_id'], user['user_id']
    )

    # Tech evidence summary for transparency (user-facing, no raw payloads)
    from services.admin_arbitration_service import build_evidence_summary_for_target
    dispute['tech_evidence_summary'] = build_evidence_summary_for_target(
        dispute['appointment_id'],
        dispute['target_participant_id'],
        dispute.get('appointment_duration_minutes', 0),
    )

    _enrich_dispute_for_user(dispute, user['user_id'])

    # Get user's own declaration from attendance sheet
    from services.declarative_service import _get_user_declaration_for_target
    dispute['my_declaration'] = _get_user_declaration_for_target(
        dispute['appointment_id'], user['user_id'], dispute['target_participant_id']
    )

    # Sanitize evidence submissions
    dispute['evidence_submissions_count'] = len(dispute.get('evidence_submissions', []))
    sanitized = []
    for sub in dispute.get('evidence_submissions', []):
        sanitized.append({
            "submission_id": sub.get('submission_id'),
            "submitted_at": sub.get('submitted_at'),
            "evidence_type": sub.get('evidence_type'),
            "is_mine": sub.get('submitted_by_user_id') == user['user_id'],
        })
    dispute['evidence_submissions'] = sanitized

    return dispute


@router.post("/{dispute_id}/position")
async def submit_position(dispute_id: str, body: PositionBody, request: Request):
    """Submit a party's position on the dispute. Both organizer and participant use this."""
    user = await get_current_user(request)

    from services.declarative_service import submit_dispute_position
    result = submit_dispute_position(dispute_id, user['user_id'], body.position)

    if result.get('error'):
        raise HTTPException(status_code=400, detail=result['error'])

    return result


@router.post("/{dispute_id}/evidence")
async def submit_evidence(dispute_id: str, body: EvidenceSubmissionBody, request: Request):
    """Submit complementary evidence for a dispute."""
    user = await get_current_user(request)

    from services.declarative_service import submit_dispute_evidence
    result = submit_dispute_evidence(
        dispute_id, user['user_id'],
        body.evidence_type, body.content_url, body.text_content
    )

    if result.get('error'):
        raise HTTPException(status_code=400, detail=result['error'])

    return result


@router.post("/{dispute_id}/resolve")
async def resolve_dispute_endpoint(dispute_id: str, body: ResolveDisputeBody, request: Request):
    """Resolve a dispute (admin/arbitrator only)."""
    from utils.permissions import require_permission
    await require_permission(request, "admin:arbitration")

    from services.declarative_service import resolve_dispute
    result = resolve_dispute(dispute_id, body.final_outcome, body.resolution_note, resolved_by="platform")

    if result.get('error'):
        raise HTTPException(status_code=400, detail=result['error'])

    return result
