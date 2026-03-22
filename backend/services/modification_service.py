"""
Modification Proposals Service
Handles business logic for appointment modification proposals.

Flow:
1. Organizer or Participant creates a proposal (changes to date/time/duration/location)
2. All other parties must accept or reject (unanimity required)
3. If all accept → apply changes to the appointment
4. If any reject → proposal rejected, appointment unchanged
5. After 24h without full response → proposal expires
"""
import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from utils.date_utils import now_utc, now_utc_iso, normalize_to_utc, parse_iso_datetime, format_datetime_fr

logger = logging.getLogger(__name__)

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
client = MongoClient(MONGO_URL)
db = client[DB_NAME]

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

    responses = []
    if proposed_by['role'] == 'organizer':
        # All accepted participants must respond
        for p in participants:
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
        # Organizer + all OTHER participants must respond
        for p in participants:
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

    if not responses and organizer_response['status'] == 'auto_accepted':
        raise ValueError("Aucun participant accepté à notifier")

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

    return proposal


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


def _apply_proposal(proposal: dict):
    """Apply accepted proposal changes to the appointment."""
    appointment_id = proposal['appointment_id']
    changes = proposal['changes']

    update_fields = {**changes, "updated_at": now_utc_iso()}
    db.appointments.update_one(
        {"appointment_id": appointment_id},
        {"$set": update_fields}
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
