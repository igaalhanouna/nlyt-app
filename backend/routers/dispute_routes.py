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


def _get_anonymized_summary(appointment_id: str, target_pid: str) -> dict:
    """Build anonymized declaration summary for a dispute target."""
    sheets = list(db.attendance_sheets.find(
        {"appointment_id": appointment_id, "status": "submitted"},
        {"_id": 0}
    ))

    absent_count = 0
    present_count = 0
    unknown_count = 0

    for s in sheets:
        if s.get('submitted_by_participant_id') == target_pid:
            continue
        for d in s.get('declarations', []):
            if d['target_participant_id'] == target_pid:
                status = d.get('declared_status', 'unknown')
                if status == 'absent':
                    absent_count += 1
                elif status in ('present_on_time', 'present_late'):
                    present_count += 1
                else:
                    unknown_count += 1

    has_tech = db.evidence_items.count_documents({
        "participant_id": target_pid,
        "appointment_id": appointment_id
    }) > 0

    return {
        "declared_absent_count": absent_count,
        "declared_present_count": present_count,
        "unknown_count": unknown_count,
        "has_tech_evidence": has_tech,
    }


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

    d['my_role'] = my_role
    d['my_position'] = my_position
    d['other_party_responded'] = other_responded
    d['can_submit_position'] = can_submit_position
    d['can_submit_evidence'] = can_submit_evidence
    d['is_resolved'] = is_resolved

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
            {"_id": 0, "title": 1, "start_datetime": 1}
        )
        if apt:
            d['appointment_title'] = apt.get('title', '')
            d['appointment_date'] = apt.get('start_datetime', '')

        target_p = db.participants.find_one(
            {"participant_id": d['target_participant_id']},
            {"_id": 0, "first_name": 1, "last_name": 1}
        )
        if target_p:
            d['target_name'] = f"{target_p.get('first_name', '')} {target_p.get('last_name', '')}".strip()

        d['declaration_summary'] = _get_anonymized_summary(d['appointment_id'], d['target_participant_id'])
        d['evidence_submissions_count'] = len(d.get('evidence_submissions', []))
        d.pop('evidence_submissions', None)

        _enrich_dispute_for_user(d, user_id)

    return {"disputes": disputes, "count": len(disputes)}


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

    # Enrich with appointment info
    apt = db.appointments.find_one(
        {"appointment_id": dispute['appointment_id']},
        {"_id": 0, "title": 1, "start_datetime": 1}
    )
    if apt:
        dispute['appointment_title'] = apt.get('title', '')
        dispute['appointment_date'] = apt.get('start_datetime', '')

    target_p = db.participants.find_one(
        {"participant_id": dispute['target_participant_id']},
        {"_id": 0, "first_name": 1, "last_name": 1}
    )
    if target_p:
        dispute['target_name'] = f"{target_p.get('first_name', '')} {target_p.get('last_name', '')}".strip()

    dispute['declaration_summary'] = _get_anonymized_summary(
        dispute['appointment_id'], dispute['target_participant_id']
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
    """Resolve a dispute (admin/platform only)."""
    user = await get_current_user(request)

    if user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Seul un administrateur peut arbitrer un litige")

    from services.declarative_service import resolve_dispute
    result = resolve_dispute(dispute_id, body.final_outcome, body.resolution_note, resolved_by="platform")

    if result.get('error'):
        raise HTTPException(status_code=400, detail=result['error'])

    return result
