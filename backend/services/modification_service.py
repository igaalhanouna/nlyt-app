"""
Modification Proposals Service
Handles business logic for appointment modification proposals.

Flow:
1. Organizer or Participant creates a proposal (changes to date/time/duration/location)
2. All other parties must accept or reject (unanimity required)
3. If all accept → apply changes to the appointment
4. If any reject → proposal rejected, appointment unchanged
5. After 24h without full response → proposal expires

Post-acceptance:
- Capture window is recalculated on every accepted modification
- Major modifications (date shift >24h, city change, type change) flag guarantees for revalidation
"""
import os
import re
import uuid
import logging
import requests
from datetime import datetime, timedelta, timezone
from utils.date_utils import now_utc, now_utc_iso, normalize_to_utc, parse_iso_datetime, format_datetime_fr

from database import db
logger = logging.getLogger(__name__)


PROPOSAL_TIMEOUT_HOURS = 24

CONTRACTUAL_FIELDS = {
    'start_datetime', 'duration_minutes', 'location', 'location_latitude',
    'location_longitude', 'location_place_id', 'meeting_provider', 'appointment_type'
}


def create_proposal(appointment_id: str, changes: dict, proposed_by: dict) -> dict:
    """
    Create a modification proposal for an appointment.

    proposed_by: { user_id?, participant_id?, role: 'organizer'|'participant', name: str }
    changes: dict of fields to change (must be in CONTRACTUAL_FIELDS)
    """
    # Validate appointment
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        raise ValueError("Rendez-vous introuvable")
    if appointment.get('status') == 'cancelled':
        raise ValueError("Impossible de modifier un rendez-vous annulé")

    # Check appointment is in the future
    start_dt = parse_iso_datetime(appointment.get('start_datetime', ''))
    if start_dt and start_dt <= now_utc():
        raise ValueError("Impossible de modifier un rendez-vous passé")

    # Check cancellation deadline — modifications follow the same window as cancellations
    cancellation_hours = appointment.get('cancellation_deadline_hours', 0)
    if start_dt and cancellation_hours > 0:
        cancellation_deadline = start_dt - timedelta(hours=cancellation_hours)
        if now_utc() >= cancellation_deadline:
            raise ValueError("Le délai de modification est dépassé")

    # Check no active proposal exists
    active = db.modification_proposals.find_one({
        "appointment_id": appointment_id,
        "status": "pending"
    }, {"_id": 0})
    if active:
        raise ValueError("Une proposition de modification est déjà en cours pour ce rendez-vous")

    # Filter to contractual fields only
    valid_changes = {k: v for k, v in changes.items() if k in CONTRACTUAL_FIELDS}
    if not valid_changes:
        raise ValueError("Aucun champ contractuel à modifier")

    # Normalize start_datetime if changed
    if 'start_datetime' in valid_changes:
        valid_changes['start_datetime'] = normalize_to_utc(valid_changes['start_datetime'])
        new_start = parse_iso_datetime(valid_changes['start_datetime'])
        if new_start and new_start <= now_utc():
            raise ValueError("La nouvelle date doit être dans le futur")

    # Snapshot original values
    original_values = {}
    for field in valid_changes:
        original_values[field] = appointment.get(field)

    # Build responses list: everyone except the proposer must respond
    # Include all participants who have accepted (regardless of guarantee status)
    accepted_statuses = ["accepted", "guaranteed", "accepted_pending_guarantee", "accepted_guaranteed"]
    participants = list(db.participants.find(
        {"appointment_id": appointment_id, "status": {"$in": accepted_statuses}},
        {"_id": 0}
    ))

    # Exclude organizer participants — only non-org accepted count for vote requirement
    non_org_accepted = [p for p in participants if not p.get('is_organizer')]

    # RULE: If organizer proposes and no non-organizer has accepted yet
    # → Apply modification directly (no vote needed)
    if proposed_by['role'] == 'organizer' and len(non_org_accepted) == 0:
        return _apply_direct_modification(appointment_id, valid_changes, original_values, proposed_by)

    responses = []
    if proposed_by['role'] == 'organizer':
        # Only non-organizer accepted participants vote
        for p in non_org_accepted:
            responses.append({
                "participant_id": p['participant_id'],
                "first_name": p.get('first_name', ''),
                "last_name": p.get('last_name', ''),
                "email": p.get('email', ''),
                "status": "pending",
                "responded_at": None
            })
        organizer_response = {"status": "auto_accepted", "responded_at": now_utc_iso()}
    else:
        # Organizer + all OTHER non-org participants must respond
        for p in non_org_accepted:
            if p['participant_id'] != proposed_by.get('participant_id'):
                responses.append({
                    "participant_id": p['participant_id'],
                    "first_name": p.get('first_name', ''),
                    "last_name": p.get('last_name', ''),
                    "email": p.get('email', ''),
                    "status": "pending",
                    "responded_at": None
                })
        organizer_response = {"status": "pending", "responded_at": None}

    # Safety fallback — should not trigger after the direct modification check above
    if not responses and organizer_response['status'] == 'auto_accepted':
        return _apply_direct_modification(appointment_id, valid_changes, original_values, proposed_by)

    proposal_id = str(uuid.uuid4())
    now_str = now_utc_iso()
    expires_at = (now_utc() + timedelta(hours=PROPOSAL_TIMEOUT_HOURS)).strftime('%Y-%m-%dT%H:%M:%SZ')

    proposal = {
        "proposal_id": proposal_id,
        "appointment_id": appointment_id,
        "proposed_by": proposed_by,
        "changes": valid_changes,
        "original_values": original_values,
        "responses": responses,
        "organizer_response": organizer_response,
        "status": "pending",
        "expires_at": expires_at,
        "created_at": now_str,
        "resolved_at": None
    }

    db.modification_proposals.insert_one(proposal)
    # Remove _id before returning
    proposal.pop('_id', None)

    logger.info(f"[MODIFICATION] Proposal {proposal_id} created for appointment {appointment_id} by {proposed_by['role']}")

    # ── Notification trigger: modification proposée ──
    try:
        _notify_modification_proposed(proposal, appointment)
    except Exception as e:
        logger.warning(f"[NOTIF] Failed to notify modification proposed: {e}")

    return proposal


def _apply_direct_modification(appointment_id: str, valid_changes: dict, original_values: dict, proposed_by: dict) -> dict:
    """
    Apply modification directly when no accepted non-organizer participant exists.
    Stores history as auto_applied proposal. Sends info emails to ALL participants.
    """
    proposal_id = str(uuid.uuid4())
    now_str = now_utc_iso()

    proposal = {
        "proposal_id": proposal_id,
        "appointment_id": appointment_id,
        "proposed_by": proposed_by,
        "changes": valid_changes,
        "original_values": original_values,
        "responses": [],
        "organizer_response": {"status": "auto_accepted", "responded_at": now_str},
        "status": "auto_applied",
        "mode": "direct",
        "expires_at": None,
        "created_at": now_str,
        "resolved_at": now_str
    }

    db.modification_proposals.insert_one(proposal)
    proposal.pop('_id', None)

    # Apply changes (calendar sync, meeting creation, guarantee recalculation)
    _apply_proposal(proposal)

    # Send informational emails to ALL non-organizer participants (including invited)
    try:
        _send_direct_modification_emails(appointment_id, valid_changes, original_values)
    except Exception as e:
        logger.warning(f"[MODIFICATION] Direct modification email failed (non-blocking): {e}")

    logger.info(f"[MODIFICATION] Direct modification {proposal_id} auto-applied for {appointment_id}")

    return proposal


def _send_direct_modification_emails(appointment_id: str, changes: dict, original_values: dict):
    """
    Send informational 'Engagement modifie' emails to ALL non-organizer participants
    when a direct modification is applied (no vote needed).
    Includes participants with status 'invited' who haven't accepted yet.
    """
    import asyncio

    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        return

    frontend_url = os.environ.get('FRONTEND_URL', '').rstrip('/')
    new_type = appointment.get('appointment_type', 'physical')
    type_changed = 'appointment_type' in changes

    # ALL non-organizer participants regardless of status
    all_participants = list(db.participants.find(
        {"appointment_id": appointment_id, "is_organizer": {"$ne": True}},
        {"_id": 0}
    ))

    from services.email_service import EmailService

    for p in all_participants:
        email = p.get('email', '')
        if not email:
            continue

        token = p.get('invitation_token', '')
        name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
        if not name:
            name = email.split('@')[0]

        if type_changed and new_type == 'video':
            access_link = f"{frontend_url}/proof/{appointment_id}?token={token}"
        else:
            access_link = f"{frontend_url}/invitation/{token}"

        invitation_link = f"{frontend_url}/invitation/{token}"

        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(EmailService.send_modification_applied_email(
                to_email=email,
                to_name=name,
                appointment_title=appointment.get('title', 'Rendez-vous'),
                appointment_datetime=appointment.get('start_datetime', ''),
                appointment_timezone=appointment.get('appointment_timezone', 'Europe/Paris'),
                changes=changes,
                original_values=original_values,
                new_appointment_type=new_type,
                type_changed=type_changed,
                access_link=access_link,
                invitation_link=invitation_link,
                meeting_provider=appointment.get('meeting_provider'),
                location=appointment.get('location'),
            ))
            loop.close()
            logger.info(f"[MODIFICATION_EMAIL] Direct mod notification sent to {email}")
        except Exception as e:
            logger.warning(f"[MODIFICATION_EMAIL] Direct mod failed for {email}: {e}")


def respond_to_proposal(proposal_id: str, responder_id: str, action: str, responder_type: str = 'participant') -> dict:
    """
    Accept or reject a modification proposal.

    responder_id: participant_id or user_id (organizer)
    action: 'accept' or 'reject'
    responder_type: 'participant' or 'organizer'
    """
    if action not in ('accept', 'reject'):
        raise ValueError("Action invalide. Utilisez 'accept' ou 'reject'")

    proposal = db.modification_proposals.find_one({"proposal_id": proposal_id}, {"_id": 0})
    if not proposal:
        raise ValueError("Proposition introuvable")
    if proposal['status'] != 'pending':
        raise ValueError(f"Cette proposition n'est plus active (statut: {proposal['status']})")

    # Check expiration
    expires_at = parse_iso_datetime(proposal['expires_at'])
    if expires_at and now_utc() > expires_at:
        db.modification_proposals.update_one(
            {"proposal_id": proposal_id},
            {"$set": {"status": "expired", "resolved_at": now_utc_iso()}}
        )
        raise ValueError("Cette proposition a expiré")

    now_str = now_utc_iso()

    if responder_type == 'organizer':
        if proposal['organizer_response']['status'] != 'pending':
            raise ValueError("L'organisateur a déjà répondu")
        db.modification_proposals.update_one(
            {"proposal_id": proposal_id},
            {"$set": {
                "organizer_response.status": "accepted" if action == 'accept' else "rejected",
                "organizer_response.responded_at": now_str
            }}
        )
    else:
        # Find the participant's response slot
        updated = False
        for i, resp in enumerate(proposal['responses']):
            if resp['participant_id'] == responder_id:
                if resp['status'] != 'pending':
                    raise ValueError("Vous avez déjà répondu à cette proposition")
                db.modification_proposals.update_one(
                    {"proposal_id": proposal_id},
                    {"$set": {
                        f"responses.{i}.status": "accepted" if action == 'accept' else "rejected",
                        f"responses.{i}.responded_at": now_str
                    }}
                )
                updated = True
                break
        if not updated:
            raise ValueError("Vous n'êtes pas concerné par cette proposition")

    # Re-fetch to check unanimity
    updated_proposal = db.modification_proposals.find_one({"proposal_id": proposal_id}, {"_id": 0})

    # Check for immediate rejection
    if action == 'reject':
        db.modification_proposals.update_one(
            {"proposal_id": proposal_id},
            {"$set": {"status": "rejected", "resolved_at": now_str}}
        )
        updated_proposal['status'] = 'rejected'
        updated_proposal['resolved_at'] = now_str
        logger.info(f"[MODIFICATION] Proposal {proposal_id} REJECTED by {responder_type} {responder_id}")
        return updated_proposal

    # Check if all have accepted (unanimity)
    all_participants_accepted = all(r['status'] == 'accepted' for r in updated_proposal['responses'])
    organizer_accepted = updated_proposal['organizer_response']['status'] in ('accepted', 'auto_accepted')

    if all_participants_accepted and organizer_accepted:
        # UNANIMITY → Apply the modification
        _apply_proposal(updated_proposal)
        db.modification_proposals.update_one(
            {"proposal_id": proposal_id},
            {"$set": {"status": "accepted", "resolved_at": now_str}}
        )
        updated_proposal['status'] = 'accepted'
        updated_proposal['resolved_at'] = now_str
        logger.info(f"[MODIFICATION] Proposal {proposal_id} ACCEPTED unanimously — changes applied")
    else:
        logger.info(f"[MODIFICATION] Proposal {proposal_id} — awaiting more responses")

    return updated_proposal



def _auto_create_meeting_on_switch(appointment_id: str, changes: dict, original_values: dict):
    """Auto-create a video meeting when switching to video or changing provider.

    Handles:
    - physical → video (Zoom/Teams/Meet)
    - video → video (provider change, e.g. Zoom → Teams)

    Non-blocking: logs warnings on failure, never raises.
    """
    from services.meeting_provider_service import create_meeting_for_appointment

    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        return

    new_type = appointment.get('appointment_type')
    provider = appointment.get('meeting_provider')

    # Only proceed if the result is a video appointment with a managed provider
    if new_type != 'video' or not provider or provider == 'external':
        if changes.get('appointment_type') == 'physical':
            old_type = original_values.get('appointment_type')
            if old_type == 'video' and original_values.get('meeting_provider'):
                logger.info(f"[MEETING_SWITCH] video→physical for {appointment_id[:8]}: "
                            f"old provider '{original_values.get('meeting_provider')}' meeting becomes obsolete (no API delete in V1)")
        return

    # Determine if we actually need to create a meeting
    type_changed = 'appointment_type' in changes and original_values.get('appointment_type') != 'video'
    provider_changed = 'meeting_provider' in changes and changes['meeting_provider'] != original_values.get('meeting_provider')

    if not type_changed and not provider_changed:
        return  # No relevant change

    # Anti-double-creation: skip if a meeting already exists for the same provider
    if appointment.get('meeting_created_via_api') and appointment.get('meeting_join_url'):
        old_provider = original_values.get('meeting_provider')
        if not old_provider or old_provider == provider:
            # No previous provider (was physical) or same provider — meeting still valid
            logger.info(f"[MEETING_SWITCH] Meeting already exists for {appointment_id[:8]} (provider={provider}), skipping creation")
            return
        # Different provider → old meeting becomes obsolete, create new one
        logger.info(f"[MEETING_SWITCH] Provider changed {old_provider}→{provider} for {appointment_id[:8]}: "
                     f"old meeting becomes obsolete (no API delete in V1)")

    logger.info(f"[MEETING_SWITCH] Auto-creating {provider} meeting for {appointment_id[:8]} "
                f"(type_changed={type_changed}, provider_changed={provider_changed})")

    result = create_meeting_for_appointment(
        appointment_id=appointment_id,
        provider=provider,
        title=appointment.get('title', ''),
        start_datetime=appointment.get('start_datetime', ''),
        duration_minutes=appointment.get('duration_minutes', 60),
        timezone_str=appointment.get('appointment_timezone', 'UTC'),
        organizer_user_id=appointment.get('organizer_id'),
    )

    if result and result.get('success'):
        logger.info(f"[MEETING_SWITCH] Success: {provider} meeting created for {appointment_id[:8]}: {result.get('join_url', '')[:60]}")
    elif result and result.get('error'):
        logger.warning(f"[MEETING_SWITCH] Failed for {appointment_id[:8]}: {result.get('error')} "
                       f"(organizer can use manual creation via UI)")
    else:
        logger.warning(f"[MEETING_SWITCH] Unexpected result for {appointment_id[:8]}: {result}")


def _apply_proposal(proposal: dict):
    """Apply accepted proposal changes to the appointment."""
    appointment_id = proposal['appointment_id']
    changes = proposal['changes']

    update_fields = {**changes, "updated_at": now_utc_iso()}

    # When location changes, invalidate cached GPS coordinates
    # so the evidence system re-geocodes on next check
    if 'location' in changes:
        update_fields['location_latitude'] = None
        update_fields['location_longitude'] = None
        update_fields['location_geocoded'] = False
        update_fields['location_display_name'] = None

    # When switching to video, clear physical location fields
    if changes.get('appointment_type') == 'video':
        update_fields.setdefault('location', '')
        update_fields['location_latitude'] = None
        update_fields['location_longitude'] = None
        update_fields['location_geocoded'] = False
        update_fields['location_display_name'] = None

    # When switching to physical, clear all video fields
    if changes.get('appointment_type') == 'physical':
        update_fields.setdefault('meeting_provider', None)
        update_fields['meeting_join_url'] = None
        update_fields['external_meeting_id'] = None
        update_fields['meeting_host_url'] = None
        update_fields['meeting_password'] = None
        update_fields['meeting_provider_metadata'] = None
        update_fields['meeting_created_via_api'] = False
        update_fields['meet_calendar_event_id'] = None

    # When changing video provider (type stays video), clear old meeting data preemptively
    # so a failed create_meeting leaves clean state instead of stale links from old provider
    original_values = proposal.get('original_values', {})
    if ('meeting_provider' in changes
            and changes.get('appointment_type', original_values.get('appointment_type')) == 'video'
            and changes['meeting_provider'] != original_values.get('meeting_provider')):
        update_fields['meeting_join_url'] = None
        update_fields['external_meeting_id'] = None
        update_fields['meeting_host_url'] = None
        update_fields['meeting_password'] = None
        update_fields['meeting_provider_metadata'] = None
        update_fields['meeting_created_via_api'] = False
        update_fields['meet_calendar_event_id'] = None

    db.appointments.update_one(
        {"appointment_id": appointment_id},
        {
            "$set": update_fields,
            "$inc": {"update_count": 1}
        }
    )
    logger.info(f"[MODIFICATION] Applied changes to appointment {appointment_id}: {list(changes.keys())}")

    # Trigger calendar auto-update (non-blocking)
    try:
        appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
        if appointment:
            from routers.calendar_routes import has_calendar_fields_changed, perform_auto_update
            if has_calendar_fields_changed(proposal['original_values'], changes):
                perform_auto_update(appointment['organizer_id'], appointment_id, appointment)
                logger.info(f"[MODIFICATION] Calendar auto-update triggered for {appointment_id}")
    except Exception as e:
        logger.warning(f"[MODIFICATION] Calendar auto-update failed: {e}")

    # Auto-create meeting when switching to video (or changing provider)
    try:
        _auto_create_meeting_on_switch(appointment_id, changes, proposal.get('original_values', {}))
    except Exception as e:
        logger.warning(f"[MODIFICATION] Auto-create meeting failed (non-blocking): {e}")

    # Handle guarantee impact (capture window + major flag)
    try:
        _handle_guarantees_after_modification(appointment_id, proposal)
    except Exception as e:
        logger.warning(f"[MODIFICATION] Guarantee impact assessment failed: {e}")

    # Send "Engagement modifié" email to engaged participants + organizer (non-blocking)
    # STRATEGY: Email only for structural changes (start_datetime, location, appointment_type, meeting_provider)
    structural_fields = {'start_datetime', 'location', 'appointment_type', 'meeting_provider'}
    is_structural = bool(set(changes.keys()) & structural_fields)

    if is_structural:
        try:
            _send_modification_emails(appointment_id, proposal)
        except Exception as e:
            logger.warning(f"[MODIFICATION] Modification email failed (non-blocking): {e}")

    # In-app notification for ALL modifications (structural or not)
    try:
        _notify_modification_applied(proposal, is_structural)
    except Exception as e:
        logger.warning(f"[NOTIF] Failed to notify modification applied: {e}")



def _send_modification_emails(appointment_id: str, proposal: dict):
    """
    Send 'Engagement modifié' email to all engaged participants + organizer.
    Called from _apply_proposal after changes are persisted.
    """
    import asyncio

    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        return

    changes = proposal.get('changes', {})
    original_values = proposal.get('original_values', {})
    proposer = proposal.get('proposed_by', {})
    proposer_role = proposer.get('role', '')
    proposer_user_id = proposer.get('user_id', '')

    frontend_url = os.environ.get('FRONTEND_URL', '').rstrip('/')

    # Determine if type changed for access block
    type_changed = 'appointment_type' in changes
    new_type = appointment.get('appointment_type', 'physical')

    # Build proof_link for video access block
    # (will be personalized per participant below)

    # Collect engaged participants (accepted statuses)
    accepted_statuses = ["accepted", "guaranteed", "accepted_pending_guarantee", "accepted_guaranteed"]
    participants = list(db.participants.find(
        {"appointment_id": appointment_id, "status": {"$in": accepted_statuses}},
        {"_id": 0}
    ))

    from services.email_service import EmailService

    for p in participants:
        token = p.get('invitation_token', '')
        name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
        if not name:
            name = p.get('email', '').split('@')[0]
        email = p.get('email', '')
        if not email:
            continue

        # Access link: proof for video, invitation for physical
        if type_changed and new_type == 'video':
            access_link = f"{frontend_url}/proof/{appointment_id}?token={token}"
        else:
            access_link = f"{frontend_url}/invitation/{token}"

        invitation_link = f"{frontend_url}/invitation/{token}"

        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(EmailService.send_modification_applied_email(
                to_email=email,
                to_name=name,
                appointment_title=appointment.get('title', 'Rendez-vous'),
                appointment_datetime=appointment.get('start_datetime', ''),
                appointment_timezone=appointment.get('appointment_timezone', 'Europe/Paris'),
                changes=changes,
                original_values=original_values,
                new_appointment_type=new_type,
                type_changed=type_changed,
                access_link=access_link,
                invitation_link=invitation_link,
                meeting_provider=appointment.get('meeting_provider'),
                location=appointment.get('location'),
            ))
            loop.close()
            logger.info(f"[MODIFICATION_EMAIL] Sent to participant {email}")
        except Exception as e:
            logger.warning(f"[MODIFICATION_EMAIL] Failed for {email}: {e}")

    # Send to organizer (unless they proposed the change)
    organizer_id = appointment.get('organizer_id', '')
    if organizer_id and (proposer_role != 'organizer' or proposer_user_id != organizer_id):
        org_user = db.users.find_one({"user_id": organizer_id}, {"_id": 0})
        if org_user and org_user.get('email'):
            org_name = f"{org_user.get('first_name', '')} {org_user.get('last_name', '')}".strip() or "Organisateur"
            org_link = f"{frontend_url}/appointments/{appointment_id}"
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(EmailService.send_modification_applied_email(
                    to_email=org_user['email'],
                    to_name=org_name,
                    appointment_title=appointment.get('title', 'Rendez-vous'),
                    appointment_datetime=appointment.get('start_datetime', ''),
                    appointment_timezone=appointment.get('appointment_timezone', 'Europe/Paris'),
                    changes=changes,
                    original_values=original_values,
                    new_appointment_type=new_type,
                    type_changed=type_changed,
                    access_link=org_link,
                    invitation_link=org_link,
                    meeting_provider=appointment.get('meeting_provider'),
                    location=appointment.get('location'),
                ))
                loop.close()
                logger.info(f"[MODIFICATION_EMAIL] Sent to organizer {org_user['email']}")
            except Exception as e:
                logger.warning(f"[MODIFICATION_EMAIL] Failed for organizer {org_user.get('email')}: {e}")



def cancel_proposal(proposal_id: str, canceller_id: str, canceller_role: str) -> dict:
    """Cancel an active proposal. Only the proposer can cancel."""
    proposal = db.modification_proposals.find_one({"proposal_id": proposal_id}, {"_id": 0})
    if not proposal:
        raise ValueError("Proposition introuvable")
    if proposal['status'] != 'pending':
        raise ValueError("Seules les propositions en attente peuvent être annulées")

    # Only proposer can cancel
    proposer = proposal['proposed_by']
    if canceller_role == 'organizer' and proposer['role'] != 'organizer':
        raise ValueError("Seul l'auteur de la proposition peut l'annuler")
    if canceller_role == 'participant' and proposer.get('participant_id') != canceller_id:
        raise ValueError("Seul l'auteur de la proposition peut l'annuler")

    db.modification_proposals.update_one(
        {"proposal_id": proposal_id},
        {"$set": {"status": "cancelled", "resolved_at": now_utc_iso()}}
    )

    proposal['status'] = 'cancelled'
    proposal['resolved_at'] = now_utc_iso()
    return proposal


def get_active_proposal(appointment_id: str) -> dict:
    """Get the active (pending) proposal for an appointment, or None."""
    proposal = db.modification_proposals.find_one(
        {"appointment_id": appointment_id, "status": "pending"},
        {"_id": 0}
    )
    if proposal:
        # Check expiration
        expires_at = parse_iso_datetime(proposal['expires_at'])
        if expires_at and now_utc() > expires_at:
            db.modification_proposals.update_one(
                {"proposal_id": proposal['proposal_id']},
                {"$set": {"status": "expired", "resolved_at": now_utc_iso()}}
            )
            proposal['status'] = 'expired'
    return proposal


def get_proposals_for_appointment(appointment_id: str) -> list:
    """Get all proposals (history) for an appointment."""
    proposals = list(db.modification_proposals.find(
        {"appointment_id": appointment_id},
        {"_id": 0}
    ).sort("created_at", -1))

    # Mark expired proposals
    for p in proposals:
        if p['status'] == 'pending':
            expires_at = parse_iso_datetime(p['expires_at'])
            if expires_at and now_utc() > expires_at:
                db.modification_proposals.update_one(
                    {"proposal_id": p['proposal_id']},
                    {"$set": {"status": "expired", "resolved_at": now_utc_iso()}}
                )
                p['status'] = 'expired'

    return proposals


def expire_stale_proposals():
    """Scheduler job: expire all proposals past their deadline."""
    now_str = now_utc_iso()
    result = db.modification_proposals.update_many(
        {"status": "pending", "expires_at": {"$lte": now_str}},
        {"$set": {"status": "expired", "resolved_at": now_str}}
    )
    if result.modified_count > 0:
        logger.info(f"[MODIFICATION] Expired {result.modified_count} stale proposals")


# ─── Guarantee Impact Assessment ──────────────────────────────────

# Grace period after appointment end before capture window closes
CAPTURE_GRACE_MINUTES = 30

# Threshold for date shift to be considered major (seconds)
MAJOR_DATE_SHIFT_SECONDS = 86400  # 24h


def _extract_city_from_address(address: str) -> str:
    """
    Extract city name from a French address string.
    Uses Nominatim with addressdetails for structured data.
    Falls back to regex parsing of common French address formats.
    """
    if not address or not address.strip():
        return ""

    # Try Nominatim with structured address details
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1, "addressdetails": 1},
            headers={"User-Agent": "NLYT-SaaS/1.0 (contact@nlyt.io)"},
            timeout=5
        )
        if resp.status_code == 200 and resp.json():
            addr = resp.json()[0].get('address', {})
            city = addr.get('city') or addr.get('town') or addr.get('village') or addr.get('municipality', '')
            if city:
                return city.strip()
    except Exception as e:
        logger.warning(f"[CITY_EXTRACT] Nominatim failed for '{address[:40]}': {e}")

    # Fallback: parse French address pattern "... XXXXX Ville"
    match = re.search(r'\b\d{5}\s+(.+)', address)
    if match:
        return match.group(1).strip().split(',')[0].strip()

    # Last resort: last comma-separated segment
    parts = [p.strip() for p in address.split(',') if p.strip()]
    if parts:
        return parts[-1]

    return ""


def _assess_modification_impact(proposal: dict) -> dict:
    """
    Determine if a modification is major or minor.

    Major if any of:
    - Date shift > 24h
    - City change
    - Appointment type change (physical ↔ video)

    Returns: {is_major: bool, reasons: list[str]}
    """
    changes = proposal.get('changes', {})
    original = proposal.get('original_values', {})
    reasons = []

    # 1. Date shift > 24h
    if 'start_datetime' in changes:
        old_dt = parse_iso_datetime(original.get('start_datetime', ''))
        new_dt = parse_iso_datetime(changes['start_datetime'])
        if old_dt and new_dt:
            shift = abs((new_dt - old_dt).total_seconds())
            if shift > MAJOR_DATE_SHIFT_SECONDS:
                hours = round(shift / 3600, 1)
                reasons.append(f"date_shift_{hours}h")

    # 2. City change
    if 'location' in changes:
        old_loc = original.get('location', '') or ''
        new_loc = changes['location'] or ''
        if old_loc and new_loc:
            old_city = _extract_city_from_address(old_loc)
            new_city = _extract_city_from_address(new_loc)
            if old_city and new_city and old_city.lower() != new_city.lower():
                reasons.append(f"city_change:{old_city}->{new_city}")

    # 3. Type change
    if 'appointment_type' in changes:
        old_type = original.get('appointment_type', '')
        new_type = changes['appointment_type']
        if old_type and new_type and old_type != new_type:
            reasons.append(f"type_change:{old_type}->{new_type}")

    return {
        "is_major": len(reasons) > 0,
        "reasons": reasons
    }


def _recalculate_capture_window(appointment_id: str, appointment: dict):
    """
    Recalculate and update capture_deadline on all active guarantees
    for this appointment. Called after every accepted modification.

    capture_deadline = appointment end time + grace period
    """
    start_str = appointment.get('start_datetime', '')
    start_dt = parse_iso_datetime(start_str)
    if not start_dt:
        logger.warning(f"[GUARANTEE] Cannot parse start_datetime for {appointment_id}")
        return

    duration = appointment.get('duration_minutes', 60)
    end_dt = start_dt + timedelta(minutes=duration)
    capture_deadline = end_dt + timedelta(minutes=CAPTURE_GRACE_MINUTES)
    capture_deadline_iso = capture_deadline.strftime('%Y-%m-%dT%H:%M:%SZ')

    result = db.payment_guarantees.update_many(
        {
            "appointment_id": appointment_id,
            "status": {"$in": ["completed", "pending", "dev_pending"]}
        },
        {"$set": {
            "capture_deadline": capture_deadline_iso,
            "capture_window_updated_at": now_utc_iso()
        }}
    )
    if result.modified_count > 0:
        logger.info(f"[GUARANTEE] Recalculated capture_deadline={capture_deadline_iso} for {result.modified_count} guarantee(s) on appointment {appointment_id}")


def _flag_guarantees_if_major(appointment_id: str, impact: dict):
    """
    If modification is major, flag all completed guarantees as requiring revalidation.
    Does NOT release or capture — just sets a flag for future business logic.
    Also sends revalidation emails to affected participants (non-blocking).
    """
    if not impact.get('is_major'):
        return

    reason = ", ".join(impact.get('reasons', []))
    result = db.payment_guarantees.update_many(
        {
            "appointment_id": appointment_id,
            "status": {"$in": ["completed", "dev_pending"]},
            "requires_revalidation": {"$ne": True}
        },
        {"$set": {
            "requires_revalidation": True,
            "revalidation_reason": reason,
            "revalidation_flagged_at": now_utc_iso()
        }}
    )
    if result.modified_count > 0:
        logger.info(f"[GUARANTEE] Flagged {result.modified_count} guarantee(s) for revalidation on {appointment_id}: {reason}")
        # Send revalidation emails (non-blocking)
        _send_revalidation_emails(appointment_id, reason)


def _send_revalidation_emails(appointment_id: str, reason: str):
    """Send revalidation notification emails to all affected participants."""
    import asyncio

    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        return

    frontend_url = os.environ.get('FRONTEND_URL', '').rstrip('/')

    # Find all participants with flagged guarantees
    flagged = list(db.payment_guarantees.find(
        {"appointment_id": appointment_id, "requires_revalidation": True},
        {"_id": 0, "participant_id": 1}
    ))

    for g in flagged:
        participant = db.participants.find_one(
            {"participant_id": g['participant_id']},
            {"_id": 0, "email": 1, "first_name": 1, "last_name": 1, "invitation_token": 1}
        )
        if not participant or not participant.get('email'):
            continue

        name = f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip() or "Participant"
        invitation_link = f"{frontend_url}/invitation/{participant['invitation_token']}" if frontend_url else ""

        try:
            from services.email_service import EmailService
            loop = asyncio.new_event_loop()
            loop.run_until_complete(EmailService.send_guarantee_revalidation_email(
                participant_email=participant['email'],
                participant_name=name,
                appointment_title=appointment.get('title', 'Rendez-vous'),
                revalidation_reason=reason,
                invitation_link=invitation_link
            ))
            loop.close()
            logger.info(f"[EMAIL] Revalidation email sent to {participant['email']}")
        except Exception as e:
            logger.warning(f"[EMAIL] Failed to send revalidation email to {participant.get('email')}: {e}")


def _handle_guarantees_after_modification(appointment_id: str, proposal: dict):
    """
    Post-acceptance hook: recalculate capture window and flag if major.
    Called from _apply_proposal after changes are persisted.
    """
    # Re-read appointment with updated values
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        return

    # Always recalculate capture window
    _recalculate_capture_window(appointment_id, appointment)

    # Assess impact and flag if major
    impact = _assess_modification_impact(proposal)
    _flag_guarantees_if_major(appointment_id, impact)

    if impact['is_major']:
        logger.info(f"[MODIFICATION] MAJOR modification detected for {appointment_id}: {impact['reasons']}")
    else:
        logger.info(f"[MODIFICATION] Minor modification for {appointment_id} — guarantees preserved")


# ═══════════════════════════════════════════════════════════════
# Notification triggers for modifications
# ═══════════════════════════════════════════════════════════════

def _notify_modification_proposed(proposal: dict, appointment: dict):
    """
    Trigger: after create_proposal() DB insert.
    In-app notification + email to all voters.
    """
    import asyncio
    from services.notification_service import create_notification, was_email_sent, mark_email_sent
    from services.email_service import EmailService

    proposal_id = proposal['proposal_id']
    apt_id = proposal['appointment_id']
    apt_title = appointment.get('title', 'Rendez-vous')
    apt_datetime = appointment.get('start_datetime', '')
    apt_tz = appointment.get('appointment_timezone', 'Europe/Paris')
    proposer = proposal.get('proposed_by', {})
    proposer_name = proposer.get('name', 'Un participant')
    changes = proposal.get('changes', {})
    original_values = proposal.get('original_values', {})
    expires_at = proposal.get('expires_at', '')

    # Build summary of changes for notification message
    field_labels = {'start_datetime': 'date', 'duration_minutes': 'duree', 'location': 'lieu',
                    'appointment_type': 'format', 'meeting_provider': 'plateforme'}
    changed_labels = [field_labels.get(f, f) for f in changes.keys() if f in field_labels]
    summary = ', '.join(changed_labels) if changed_labels else 'details'

    # Collect voters: participants with pending responses + organizer if pending
    voter_emails = []
    for resp in proposal.get('responses', []):
        if resp.get('status') == 'pending':
            # Resolve user_id from participant_id
            pid = resp.get('participant_id')
            p = db.participants.find_one({'participant_id': pid}, {'_id': 0, 'user_id': 1, 'email': 1, 'first_name': 1, 'last_name': 1})
            if p:
                uid = p.get('user_id')
                name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or p.get('email', '').split('@')[0]
                email = p.get('email', '')
                if uid:
                    voter_emails.append({'user_id': uid, 'email': email, 'name': name})

    org_resp = proposal.get('organizer_response', {})
    if org_resp.get('status') == 'pending':
        org_id = appointment.get('organizer_id')
        if org_id:
            org = db.users.find_one({'user_id': org_id}, {'_id': 0, 'email': 1, 'first_name': 1, 'last_name': 1})
            if org:
                org_name = f"{org.get('first_name', '')} {org.get('last_name', '')}".strip() or 'Organisateur'
                voter_emails.append({'user_id': org_id, 'email': org.get('email', ''), 'name': org_name})

    message = f"Modification proposee ({summary}) — votre vote est requis."

    for voter in voter_emails:
        uid = voter['user_id']
        # 1. In-app notification
        create_notification(
            user_id=uid,
            event_type="modification",
            reference_id=proposal_id,
            appointment_id=apt_id,
            title=apt_title,
            message=message,
        )
        # 2. Email
        if voter['email'] and not was_email_sent(uid, "modification", proposal_id):
            try:
                from services.notification_service import _fire_email
                _fire_email(EmailService.send_modification_proposed_email(
                    to_email=voter['email'],
                    to_name=voter['name'],
                    proposer_name=proposer_name,
                    appointment_title=apt_title,
                    appointment_datetime=apt_datetime,
                    appointment_timezone=apt_tz,
                    changes=changes,
                    original_values=original_values,
                    appointment_id=apt_id,
                    expires_at=expires_at,
                ))
                mark_email_sent(uid, "modification", proposal_id)
                logger.info(f"[NOTIF-EMAIL] Sent modification proposed email to {voter['email']}")
            except Exception as e:
                logger.warning(f"[NOTIF-EMAIL] Failed to send modification proposed email to {voter['email']}: {e}")


def _notify_modification_applied(proposal: dict, is_structural: bool):
    """
    Trigger: after _apply_proposal() changes are persisted.
    In-app notification for ALL modifications.
    Email already handled by _send_modification_emails if structural.
    """
    from services.notification_service import create_notification

    apt_id = proposal['appointment_id']
    proposal_id = proposal['proposal_id']
    changes = proposal.get('changes', {})

    apt = db.appointments.find_one({'appointment_id': apt_id}, {'_id': 0, 'title': 1, 'organizer_id': 1})
    apt_title = apt.get('title', 'Rendez-vous') if apt else 'Rendez-vous'

    field_labels = {'start_datetime': 'date', 'duration_minutes': 'duree', 'location': 'lieu',
                    'appointment_type': 'format', 'meeting_provider': 'plateforme'}
    changed_labels = [field_labels.get(f, f) for f in changes.keys() if f in field_labels]
    summary = ', '.join(changed_labels) if changed_labels else 'details'
    message = f"Modification confirmee ({summary})."

    # Notify all engaged participants + organizer
    accepted_statuses = ["accepted", "guaranteed", "accepted_pending_guarantee", "accepted_guaranteed"]
    participants = list(db.participants.find(
        {"appointment_id": apt_id, "status": {"$in": accepted_statuses}},
        {"_id": 0, "user_id": 1}
    ))
    notified_uids = set()

    for p in participants:
        uid = p.get('user_id')
        if uid and uid not in notified_uids:
            create_notification(
                user_id=uid,
                event_type="modification",
                reference_id=f"{proposal_id}_applied",
                appointment_id=apt_id,
                title=apt_title,
                message=message,
            )
            notified_uids.add(uid)

    # Also notify organizer
    org_id = apt.get('organizer_id') if apt else None
    if org_id and org_id not in notified_uids:
        create_notification(
            user_id=org_id,
            event_type="modification",
            reference_id=f"{proposal_id}_applied",
            appointment_id=apt_id,
            title=apt_title,
            message=message,
        )


def send_modification_vote_reminders():
    """
    Scheduler job: send J-1 reminder emails to voters who haven't responded.
    Called every 15 minutes. Sends reminder when < 1h remains before expiration.
    Only sends between 9h-20h Europe/Paris. Each voter gets max 1 reminder per proposal.
    """
    import asyncio
    from services.notification_service import was_email_sent, mark_email_sent
    from services.email_service import EmailService

    # Check if within sending hours (9h-20h Europe/Paris)
    from utils.date_utils import parse_iso_datetime
    import pytz
    paris = pytz.timezone('Europe/Paris')
    now_paris = now_utc().astimezone(paris)
    if now_paris.hour < 9 or now_paris.hour >= 20:
        return 0

    # Find proposals pending with expiration in < 1h
    threshold = (now_utc() + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
    proposals = list(db.modification_proposals.find(
        {"status": "pending", "expires_at": {"$lte": threshold}},
        {"_id": 0}
    ))

    reminders_sent = 0

    for proposal in proposals:
        proposal_id = proposal['proposal_id']
        apt_id = proposal['appointment_id']
        changes = proposal.get('changes', {})
        original_values = proposal.get('original_values', {})
        proposer = proposal.get('proposed_by', {})
        proposer_name = proposer.get('name', 'Un participant')
        expires_at = proposal.get('expires_at', '')

        apt = db.appointments.find_one({'appointment_id': apt_id}, {'_id': 0, 'title': 1, 'appointment_timezone': 1, 'organizer_id': 1})
        if not apt:
            continue
        apt_title = apt.get('title', 'Rendez-vous')
        apt_tz = apt.get('appointment_timezone', 'Europe/Paris')

        # Find voters who haven't responded
        pending_voters = []
        for resp in proposal.get('responses', []):
            if resp.get('status') == 'pending':
                pid = resp.get('participant_id')
                p = db.participants.find_one({'participant_id': pid}, {'_id': 0, 'user_id': 1, 'email': 1, 'first_name': 1, 'last_name': 1})
                if p and p.get('user_id') and p.get('email'):
                    name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or p.get('email').split('@')[0]
                    pending_voters.append({'user_id': p['user_id'], 'email': p['email'], 'name': name})

        org_resp = proposal.get('organizer_response', {})
        if org_resp.get('status') == 'pending':
            org_id = apt.get('organizer_id')
            if org_id:
                org = db.users.find_one({'user_id': org_id}, {'_id': 0, 'email': 1, 'first_name': 1, 'last_name': 1})
                if org and org.get('email'):
                    org_name = f"{org.get('first_name', '')} {org.get('last_name', '')}".strip() or 'Organisateur'
                    pending_voters.append({'user_id': org_id, 'email': org['email'], 'name': org_name})

        # Send reminder to each pending voter (idempotent via 'modification_reminder' key)
        reminder_key = f"{proposal_id}_reminder"
        for voter in pending_voters:
            uid = voter['user_id']
            if was_email_sent(uid, "modification_reminder", reminder_key):
                continue
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(EmailService.send_modification_reminder_email(
                    to_email=voter['email'],
                    to_name=voter['name'],
                    proposer_name=proposer_name,
                    appointment_title=apt_title,
                    appointment_timezone=apt_tz,
                    changes=changes,
                    original_values=original_values,
                    appointment_id=apt_id,
                    expires_at=expires_at,
                ))
                loop.close()
                mark_email_sent(uid, "modification_reminder", reminder_key)
                reminders_sent += 1
                logger.info(f"[REMINDER] Vote reminder sent to {voter['email']} for proposal {proposal_id}")
            except Exception as e:
                logger.warning(f"[REMINDER] Failed to send reminder to {voter['email']}: {e}")

    if reminders_sent > 0:
        logger.info(f"[REMINDER] Sent {reminders_sent} vote reminders")
    return reminders_sent
