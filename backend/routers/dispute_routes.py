"""
Dispute Routes — V3 Trustless Declarative Disputes
Replaces old violation-based disputes with attendance-based disputes.
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import logging

from middleware.auth_middleware import get_current_user
from database import db

logger = logging.getLogger(__name__)
router = APIRouter()


class EvidenceSubmissionBody(BaseModel):
    evidence_type: str  # screenshot | message | document | text_statement
    content_url: Optional[str] = None
    text_content: Optional[str] = None


class ResolveDisputeBody(BaseModel):
    final_outcome: str
    resolution_note: str


@router.get("/mine")
async def list_my_disputes(request: Request):
    """List disputes where the current user is involved."""
    user = await get_current_user(request)
    user_id = user['user_id']

    # Find appointments where user is a participant
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

    # Enrich with appointment info
    for d in disputes:
        apt = db.appointments.find_one(
            {"appointment_id": d['appointment_id']},
            {"_id": 0, "title": 1, "start_datetime": 1}
        )
        if apt:
            d['appointment_title'] = apt.get('title', '')
            d['appointment_date'] = apt.get('start_datetime', '')

        # Target name
        target_p = db.participants.find_one(
            {"participant_id": d['target_participant_id']},
            {"_id": 0, "first_name": 1, "last_name": 1}
        )
        if target_p:
            d['target_name'] = f"{target_p.get('first_name', '')} {target_p.get('last_name', '')}".strip()

        # Anonymized declaration summary
        d['declaration_summary'] = _get_anonymized_summary(d['appointment_id'], d['target_participant_id'])
        d['evidence_submissions_count'] = len(d.get('evidence_submissions', []))
        d.pop('evidence_submissions', None)

    return {"disputes": disputes, "count": len(disputes)}


@router.get("/{dispute_id}")
async def get_dispute_detail(dispute_id: str, request: Request):
    """Get dispute detail (anonymized view for participants)."""
    user = await get_current_user(request)

    dispute = db.declarative_disputes.find_one({"dispute_id": dispute_id}, {"_id": 0})
    if not dispute:
        raise HTTPException(status_code=404, detail="Litige introuvable")

    # Verify user is participant of this appointment
    participant = db.participants.find_one({
        "appointment_id": dispute['appointment_id'],
        "user_id": user['user_id']
    })
    if not participant:
        raise HTTPException(status_code=403, detail="Acces refuse")

    # Enrich
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

    dispute['declaration_summary'] = _get_anonymized_summary(dispute['appointment_id'], dispute['target_participant_id'])

    # Check if user can submit evidence
    dispute['can_submit_evidence'] = dispute['status'] in ('awaiting_evidence', 'opened')
    dispute['evidence_submissions_count'] = len(dispute.get('evidence_submissions', []))

    # Remove individual submission details (keep count only for non-admin)
    sanitized_submissions = []
    for sub in dispute.get('evidence_submissions', []):
        sanitized_submissions.append({
            "submission_id": sub.get('submission_id'),
            "submitted_at": sub.get('submitted_at'),
            "evidence_type": sub.get('evidence_type'),
            "is_mine": sub.get('submitted_by_user_id') == user['user_id'],
        })
    dispute['evidence_submissions'] = sanitized_submissions

    return dispute


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

    # Only admin can resolve
    if user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Seul un administrateur peut arbitrer un litige")

    from services.declarative_service import resolve_dispute
    result = resolve_dispute(dispute_id, body.final_outcome, body.resolution_note, resolved_by="platform")

    if result.get('error'):
        raise HTTPException(status_code=400, detail=result['error'])

    return result


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
