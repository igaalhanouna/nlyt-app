"""
Modification Proposals Router
Endpoints for creating, responding to, and managing appointment modification proposals.
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import os
import sys
sys.path.append('/app/backend')
from middleware.auth_middleware import get_current_user
from database import db
from services.modification_service import (
    create_proposal, respond_to_proposal, cancel_proposal,
    get_active_proposal, get_proposals_for_appointment
)
from utils.date_utils import now_utc_iso, format_datetime_fr, parse_iso_datetime
from services.email_service import format_email_datetime

router = APIRouter()



class CreateProposalRequest(BaseModel):
    appointment_id: str
    changes: dict
    invitation_token: Optional[str] = None


class RespondProposalRequest(BaseModel):
    action: str  # 'accept' or 'reject'
    invitation_token: Optional[str] = None


# --- Organizer endpoints (JWT auth) ---

@router.post("/")
async def create_modification_proposal(body: CreateProposalRequest, request: Request):
    """
    Create a modification proposal.
    - Organizer: authenticated via JWT
    - Participant: authenticated via invitation_token in body
    """
    proposed_by = None

    if body.invitation_token:
        # Participant proposing via invitation token
        participant = db.participants.find_one(
            {"invitation_token": body.invitation_token},
            {"_id": 0}
        )
        if not participant:
            raise HTTPException(status_code=404, detail="Token d'invitation invalide")
        if participant['appointment_id'] != body.appointment_id:
            raise HTTPException(status_code=403, detail="Ce token ne correspond pas à ce rendez-vous")
        if participant.get('status') not in ('accepted', 'guaranteed', 'accepted_pending_guarantee', 'accepted_guaranteed'):
            raise HTTPException(status_code=400, detail="Seuls les participants ayant accepté peuvent proposer une modification")

        proposed_by = {
            "participant_id": participant['participant_id'],
            "role": "participant",
            "name": f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip()
        }
    else:
        # JWT-authenticated user — determine role (organizer or participant)
        user = await get_current_user(request)
        appointment = db.appointments.find_one(
            {"appointment_id": body.appointment_id},
            {"_id": 0}
        )
        if not appointment:
            raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

        if appointment['organizer_id'] == user['user_id']:
            # Organizer proposing
            proposed_by = {
                "user_id": user['user_id'],
                "role": "organizer",
                "name": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get('email', '')
            }
        else:
            # Participant proposing via JWT (P1.2 — bidirectional)
            participant = db.participants.find_one(
                {"appointment_id": body.appointment_id, "user_id": user['user_id'], "is_organizer": {"$ne": True}},
                {"_id": 0}
            )
            if not participant:
                raise HTTPException(status_code=403, detail="Vous n'êtes pas participant de ce rendez-vous")
            if participant.get('status') not in ('accepted', 'guaranteed', 'accepted_pending_guarantee', 'accepted_guaranteed'):
                raise HTTPException(status_code=400, detail="Seuls les participants ayant accepté peuvent proposer une modification")
            proposed_by = {
                "participant_id": participant['participant_id'],
                "role": "participant",
                "name": f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip()
            }

    try:
        result = create_proposal(body.appointment_id, body.changes, proposed_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Only send proposal notification emails for real proposals (not direct modifications)
    if result.get('mode') != 'direct':
        try:
            await _send_proposal_emails(result)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[MODIFICATION] Failed to send proposal emails: {e}")

    return result


@router.get("/appointment/{appointment_id}")
async def get_appointment_proposals(appointment_id: str, request: Request):
    """Get all proposals for an appointment. Auth: organizer via JWT."""
    user = await get_current_user(request)
    appointment = db.appointments.find_one(
        {"appointment_id": appointment_id},
        {"_id": 0}
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

    membership = db.workspace_memberships.find_one({
        "workspace_id": appointment['workspace_id'],
        "user_id": user['user_id']
    }, {"_id": 0})
    participant = db.participants.find_one({
        "appointment_id": appointment_id,
        "user_id": user['user_id']
    }, {"_id": 0})
    if not membership and not participant:
        raise HTTPException(status_code=403, detail="Accès refusé")

    proposals = get_proposals_for_appointment(appointment_id)
    return {"proposals": proposals}


@router.get("/mine")
async def get_my_modifications(request: Request):
    """Get all modification proposals involving the current user (as organizer or participant)."""
    user = await get_current_user(request)
    user_id = user['user_id']

    # Appointments where user is organizer
    org_apt_ids = set()
    for apt in db.appointments.find({"organizer_id": user_id, "status": {"$ne": "deleted"}}, {"_id": 0, "appointment_id": 1}):
        org_apt_ids.add(apt["appointment_id"])

    # Appointments where user is participant
    part_map = {}
    for p in db.participants.find({"user_id": user_id, "is_organizer": {"$ne": True}}, {"_id": 0, "appointment_id": 1, "participant_id": 1}):
        part_map[p["appointment_id"]] = p["participant_id"]

    all_apt_ids = org_apt_ids | set(part_map.keys())
    if not all_apt_ids:
        return {"proposals": []}

    proposals = list(db.modification_proposals.find(
        {"appointment_id": {"$in": list(all_apt_ids)}},
        {"_id": 0}
    ).sort("created_at", -1))

    # Cache appointments for enrichment
    apt_cache = {}
    for apt in db.appointments.find(
        {"appointment_id": {"$in": list(all_apt_ids)}},
        {"_id": 0, "appointment_id": 1, "title": 1, "start_datetime": 1}
    ):
        apt_cache[apt["appointment_id"]] = apt

    result = []
    for prop in proposals:
        apt_id = prop["appointment_id"]
        apt = apt_cache.get(apt_id, {})
        is_org = apt_id in org_apt_ids
        my_role = "organizer" if is_org else "participant"

        # My response status
        my_response_status = None
        if is_org:
            my_response_status = prop.get("organizer_response", {}).get("status")
        else:
            pid = part_map.get(apt_id)
            for r in prop.get("responses", []):
                if r.get("participant_id") == pid:
                    my_response_status = r.get("status")
                    break

        is_action_required = prop.get("status") == "pending" and my_response_status == "pending"

        # Participants summary
        responses = prop.get("responses", [])
        accepted_count = sum(1 for r in responses if r["status"] == "accepted")
        total_voters = len(responses)
        org_resp = prop.get("organizer_response", {}).get("status")
        if org_resp == "auto_accepted":
            total_voters += 1
            accepted_count += 1
        elif org_resp in ("pending", "accepted", "rejected"):
            total_voters += 1
            if org_resp == "accepted":
                accepted_count += 1

        result.append({
            "proposal_id": prop["proposal_id"],
            "appointment_id": apt_id,
            "appointment_title": apt.get("title", ""),
            "start_datetime": apt.get("start_datetime", ""),
            "proposed_by": prop.get("proposed_by", {}),
            "changes": prop.get("changes", {}),
            "original_values": prop.get("original_values", {}),
            "status": prop.get("status"),
            "mode": prop.get("mode", "proposal"),
            "expires_at": prop.get("expires_at"),
            "created_at": prop.get("created_at"),
            "my_role": my_role,
            "my_response_status": my_response_status,
            "is_action_required": is_action_required,
            "participants_summary": f"{accepted_count}/{total_voters}"
        })

    return {"proposals": result}


@router.get("/active/{appointment_id}")
async def get_active_proposal_endpoint(appointment_id: str):
    """Get the active (pending) proposal for an appointment. Public endpoint."""
    proposal = get_active_proposal(appointment_id)
    return {"proposal": proposal}


@router.post("/{proposal_id}/respond")
async def respond_to_modification(proposal_id: str, body: RespondProposalRequest, request: Request):
    """
    Accept or reject a modification proposal.
    - Organizer: via JWT
    - Participant: via invitation_token
    """
    if body.action not in ('accept', 'reject'):
        raise HTTPException(status_code=400, detail="Action invalide. Utilisez 'accept' ou 'reject'")

    proposal = db.modification_proposals.find_one({"proposal_id": proposal_id}, {"_id": 0})
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposition introuvable")

    responder_id = None
    responder_type = 'participant'

    if body.invitation_token:
        # Participant responding
        participant = db.participants.find_one(
            {"invitation_token": body.invitation_token},
            {"_id": 0}
        )
        if not participant:
            raise HTTPException(status_code=404, detail="Token d'invitation invalide")
        responder_id = participant['participant_id']
        responder_type = 'participant'
    else:
        # JWT-authenticated user — determine role
        user = await get_current_user(request)
        appointment = db.appointments.find_one(
            {"appointment_id": proposal['appointment_id']},
            {"_id": 0}
        )
        if not appointment:
            raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

        if appointment['organizer_id'] == user['user_id']:
            # Organizer responding
            responder_id = user['user_id']
            responder_type = 'organizer'
        else:
            # Participant responding via JWT (P1.2 — bidirectional)
            participant = db.participants.find_one(
                {"appointment_id": proposal['appointment_id'], "user_id": user['user_id'], "is_organizer": {"$ne": True}},
                {"_id": 0}
            )
            if not participant:
                raise HTTPException(status_code=403, detail="Vous n'êtes pas participant de ce rendez-vous")
            responder_id = participant['participant_id']
            responder_type = 'participant'

    try:
        updated = respond_to_proposal(proposal_id, responder_id, body.action, responder_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # If proposal was just accepted unanimously, send confirmation emails
    if updated['status'] == 'accepted':
        try:
            await _send_acceptance_emails(updated)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[MODIFICATION] Failed to send acceptance emails: {e}")

    return updated


@router.post("/{proposal_id}/cancel")
async def cancel_modification_proposal(proposal_id: str, request: Request):
    """Cancel an active proposal. Only the proposer can cancel."""
    user = await get_current_user(request)

    proposal = db.modification_proposals.find_one({"proposal_id": proposal_id}, {"_id": 0})
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposition introuvable")

    # Determine canceller identity
    appointment = db.appointments.find_one({"appointment_id": proposal['appointment_id']}, {"_id": 0})
    if appointment and appointment.get('organizer_id') == user['user_id']:
        canceller_id = user['user_id']
        canceller_type = 'organizer'
    else:
        participant = db.participants.find_one(
            {"appointment_id": proposal['appointment_id'], "user_id": user['user_id'], "is_organizer": {"$ne": True}},
            {"_id": 0}
        )
        if participant:
            canceller_id = participant['participant_id']
            canceller_type = 'participant'
        else:
            raise HTTPException(status_code=403, detail="Vous n'êtes pas impliqué dans ce rendez-vous")

    try:
        result = cancel_proposal(proposal_id, canceller_id, canceller_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


# --- Email helpers ---

async def _send_proposal_emails(proposal: dict):
    """Send notification emails to all respondents about a new modification proposal."""
    from services.email_service import EmailService

    appointment = db.appointments.find_one(
        {"appointment_id": proposal['appointment_id']},
        {"_id": 0}
    )
    if not appointment:
        return

    proposer_name = proposal['proposed_by'].get('name', 'Un participant')
    base_url = os.environ.get('FRONTEND_URL', '').rstrip('/')

    # Build changes description
    appt_tz = appointment.get('appointment_timezone', 'Europe/Paris')
    changes_html = _build_changes_html(proposal, appt_tz)

    # Notify participants who need to respond
    for resp in proposal.get('responses', []):
        participant = db.participants.find_one(
            {"participant_id": resp['participant_id']},
            {"_id": 0}
        )
        if not participant or not participant.get('email'):
            continue

        invitation_link = f"{base_url}/invitation/{participant.get('invitation_token', '')}"
        to_name = f"{resp.get('first_name', '')} {resp.get('last_name', '')}".strip() or resp.get('email', '')

        subject = f"Modification proposée - {appointment.get('title', 'Rendez-vous')}"
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Inter', Arial, sans-serif; line-height: 1.6; color: #334155; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #2563EB; color: white; padding: 25px; text-align: center; }}
                .content {{ background: #ffffff; padding: 30px; border: 1px solid #E2E8F0; }}
                .changes-box {{ background: #F0F9FF; padding: 20px; border-radius: 8px; border: 1px solid #BAE6FD; margin: 20px 0; }}
                .button {{ display: inline-block; padding: 14px 28px; background: #2563EB; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; }}
                .footer {{ text-align: center; color: #64748B; font-size: 14px; padding: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="margin: 0; font-size: 22px;">Modification proposée</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">NLYT</p>
                </div>
                <div class="content">
                    <h2 style="color: #1E293B;">Bonjour {to_name},</h2>
                    <p><strong>{proposer_name}</strong> propose une modification pour le rendez-vous <strong>{appointment.get('title', '')}</strong>.</p>

                    <div class="changes-box">
                        {changes_html}
                    </div>

                    <p>Votre accord est requis. Veuillez accepter ou refuser cette modification.</p>

                    <div style="text-align: center; margin: 25px 0;">
                        <a href="{invitation_link}" class="button">Voir et répondre</a>
                    </div>

                    <p style="color: #94A3B8; font-size: 13px;">Cette proposition expire dans 24 heures.</p>
                </div>
                <div class="footer"><p>&copy; 2026 NLYT</p></div>
            </div>
        </body>
        </html>
        """
        await EmailService.send_email(participant['email'], subject, html_content, email_type="modification_proposal")

    # Notify organizer if a participant proposed
    if proposal['proposed_by']['role'] == 'participant' and proposal['organizer_response']['status'] == 'pending':
        organizer = db.users.find_one(
            {"user_id": appointment['organizer_id']},
            {"_id": 0}
        )
        if organizer and organizer.get('email'):
            org_link = f"{base_url}/appointments/{appointment['appointment_id']}"
            org_name = f"{organizer.get('first_name', '')} {organizer.get('last_name', '')}".strip() or organizer.get('email', '')

            subject = f"Modification proposée par un participant - {appointment.get('title', '')}"
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head><style>
                body {{ font-family: 'Inter', Arial, sans-serif; line-height: 1.6; color: #334155; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #2563EB; color: white; padding: 25px; text-align: center; }}
                .content {{ background: #ffffff; padding: 30px; border: 1px solid #E2E8F0; }}
                .changes-box {{ background: #F0F9FF; padding: 20px; border-radius: 8px; border: 1px solid #BAE6FD; margin: 20px 0; }}
                .button {{ display: inline-block; padding: 14px 28px; background: #2563EB; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; }}
                .footer {{ text-align: center; color: #64748B; font-size: 14px; padding: 20px; }}
            </style></head>
            <body>
            <div class="container">
                <div class="header"><h1 style="margin:0;font-size:22px;">Modification proposée</h1></div>
                <div class="content">
                    <h2>Bonjour {org_name},</h2>
                    <p><strong>{proposer_name}</strong> propose une modification.</p>
                    <div class="changes-box">{changes_html}</div>
                    <div style="text-align:center;margin:25px 0;">
                        <a href="{org_link}" class="button">Voir et répondre</a>
                    </div>
                    <p style="color:#94A3B8;font-size:13px;">Cette proposition expire dans 24 heures.</p>
                </div>
                <div class="footer"><p>&copy; 2026 NLYT</p></div>
            </div>
            </body></html>
            """
            await EmailService.send_email(organizer['email'], subject, html_content, email_type="modification_proposal_organizer")


async def _send_acceptance_emails(proposal: dict):
    """Send confirmation emails when a proposal is unanimously accepted."""
    from services.email_service import EmailService

    appointment = db.appointments.find_one(
        {"appointment_id": proposal['appointment_id']},
        {"_id": 0}
    )
    if not appointment:
        return

    appt_tz = appointment.get('appointment_timezone', 'Europe/Paris')
    changes_html = _build_changes_html(proposal, appt_tz)
    base_url = os.environ.get('FRONTEND_URL', '').rstrip('/')

    # Notify all participants
    accepted_statuses = ["accepted", "guaranteed", "accepted_pending_guarantee", "accepted_guaranteed"]
    all_participants = list(db.participants.find(
        {"appointment_id": proposal['appointment_id'], "status": {"$in": accepted_statuses}},
        {"_id": 0}
    ))
    for p in all_participants:
        if not p.get('email'):
            continue
        to_name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
        invitation_link = f"{base_url}/invitation/{p.get('invitation_token', '')}"

        subject = f"Modification confirmée - {appointment.get('title', '')}"
        html_content = f"""
        <!DOCTYPE html><html><head><style>
        body {{ font-family: 'Inter', Arial, sans-serif; line-height: 1.6; color: #334155; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #059669; color: white; padding: 25px; text-align: center; }}
        .content {{ background: #fff; padding: 30px; border: 1px solid #E2E8F0; }}
        .changes-box {{ background: #F0FDF4; padding: 20px; border-radius: 8px; border: 1px solid #BBF7D0; margin: 20px 0; }}
        .footer {{ text-align: center; color: #64748B; font-size: 14px; padding: 20px; }}
        </style></head><body>
        <div class="container">
            <div class="header"><h1 style="margin:0;font-size:22px;">Modification confirmée</h1></div>
            <div class="content">
                <h2>Bonjour {to_name},</h2>
                <p>La modification du rendez-vous <strong>{appointment.get('title','')}</strong> a été acceptée par tous les participants.</p>
                <div class="changes-box">{changes_html}</div>
                <p>Le rendez-vous a été mis à jour.</p>
                <div style="text-align:center;margin:25px 0;">
                    <a href="{invitation_link}" style="padding:14px 28px;background:#059669;color:white;text-decoration:none;border-radius:8px;font-weight:bold;">Voir le rendez-vous</a>
                </div>
            </div>
            <div class="footer"><p>&copy; 2026 NLYT</p></div>
        </div></body></html>
        """
        await EmailService.send_email(p['email'], subject, html_content, email_type="modification_accepted")


def _build_changes_html(proposal: dict, tz_name: str = 'Europe/Paris') -> str:
    """Build HTML showing old vs new values."""
    original = proposal.get('original_values', {})
    changes = proposal.get('changes', {})

    labels = {
        'start_datetime': 'Date et heure',
        'duration_minutes': 'Durée',
        'location': 'Lieu',
        'meeting_provider': 'Plateforme visio',
        'appointment_type': 'Type de rendez-vous',
    }

    rows = []
    for field, new_val in changes.items():
        old_val = original.get(field, '—')
        label = labels.get(field, field)

        if field == 'start_datetime':
            old_display = format_email_datetime(str(old_val), tz_name) if old_val else str(old_val)
            new_display = format_email_datetime(str(new_val), tz_name) if new_val else str(new_val)
        elif field == 'duration_minutes':
            old_display = f"{old_val} min" if old_val else '—'
            new_display = f"{new_val} min"
        elif field == 'appointment_type':
            type_labels = {'physical': 'En personne', 'video': 'Visioconférence'}
            old_display = type_labels.get(str(old_val), str(old_val))
            new_display = type_labels.get(str(new_val), str(new_val))
        else:
            old_display = str(old_val) if old_val else '—'
            new_display = str(new_val)

        rows.append(f"""
        <div style="margin-bottom: 12px;">
            <p style="margin: 0; font-weight: 600; color: #1E293B;">{label}</p>
            <p style="margin: 2px 0; color: #DC2626; text-decoration: line-through;">{old_display}</p>
            <p style="margin: 2px 0; color: #059669; font-weight: 600;">{new_display}</p>
        </div>
        """)

    return "\n".join(rows) if rows else "<p>Aucun changement détaillé.</p>"
