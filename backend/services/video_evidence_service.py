"""
Video Evidence Service — Ingestion, normalization, and matching of video conference attendance.

This service:
1. Receives raw attendance data from organizer (manual upload) or webhooks
2. Uses the appropriate provider adapter to normalize records
3. Matches normalized records against known NLYT participants
4. Creates evidence_items with source="video_conference"
5. Stores ingestion logs for audit

Rules (V1 — Conservative):
- Zoom/Teams + high identity match → evidence confidence "high"
- Zoom/Teams + medium identity match → evidence confidence "medium"
- Google Meet (any match) → evidence confidence "low" (ALWAYS)
- No match or ambiguous → evidence confidence "low", review required
- Google Meet alone NEVER triggers auto-penalty

Video-specific derived_facts:
{
    "provider": "zoom" | "teams" | "meet",
    "external_meeting_id": str,
    "joined_at": str (ISO UTC),
    "left_at": str (ISO UTC),
    "duration_seconds": int,
    "identity_confidence": "high" | "medium" | "low",
    "identity_match_method": str,
    "identity_match_detail": str,
    "temporal_consistency": str,
    "temporal_detail": str,
    "provider_evidence_ceiling": "strong" | "assisted",
    "video_attendance_outcome": "joined_on_time" | "joined_late" | "no_join_detected" | "manual_review",
}
"""
import os
import uuid
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from adapters.video_providers.base import VideoProviderAdapter, NormalizedAttendanceRecord
from adapters.video_providers.zoom_adapter import ZoomAdapter
from adapters.video_providers.teams_adapter import TeamsAdapter
from adapters.video_providers.meet_adapter import MeetAdapter
from services.evidence_service import create_evidence, assess_temporal_consistency
from utils.date_utils import now_utc, parse_iso_datetime

from database import db
logger = logging.getLogger(__name__)


# Provider registry
PROVIDER_ADAPTERS = {
    "zoom": ZoomAdapter(),
    "teams": TeamsAdapter(),
    "meet": MeetAdapter(),
    "google_meet": MeetAdapter(),
    "google meet": MeetAdapter(),
    "microsoft teams": TeamsAdapter(),
    "microsoft_teams": TeamsAdapter(),
}


def get_adapter(provider_name: str) -> Optional[VideoProviderAdapter]:
    """Get the adapter for a given provider name (case-insensitive)."""
    key = (provider_name or "").strip().lower().replace(" ", "_")
    # Try exact match first, then fuzzy
    adapter = PROVIDER_ADAPTERS.get(key)
    if adapter:
        return adapter
    # Fuzzy: check if key contains provider name
    for pkey, padapter in PROVIDER_ADAPTERS.items():
        if pkey in key or key in pkey:
            return padapter
    return None


def ingest_video_attendance(
    appointment_id: str,
    provider_name: str,
    raw_payload: dict,
    ingested_by: str = "organizer",
    external_meeting_id: Optional[str] = None,
    source_trust: str = "manual_upload",
) -> dict:
    """
    Main ingestion entry point.
    1. Validates the provider and payload
    2. Normalizes attendance records
    3. Matches against NLYT participants
    4. Creates evidence_items
    5. Logs the ingestion

    Returns: {success, records_created, matched, unmatched, errors, ingestion_log_id}
    """
    # 1. Resolve adapter
    adapter = get_adapter(provider_name)
    if not adapter:
        return {"error": f"Provider '{provider_name}' non supporté. Providers valides: zoom, teams, meet"}

    # 2. Validate payload
    validation = adapter.validate_payload(raw_payload)
    if not validation["valid"]:
        return {"error": f"Payload invalide: {validation['error']}"}

    # 3. Get appointment
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        return {"error": "Rendez-vous introuvable"}

    # 4. Get participants
    participants = list(db.participants.find(
        {"appointment_id": appointment_id},
        {"_id": 0}
    ))
    accepted_participants = [
        p for p in participants
        if p.get("status") in ("accepted", "accepted_pending_guarantee", "accepted_guaranteed")
    ]

    # 5. Normalize attendance records
    normalized_records = adapter.normalize_attendance(raw_payload)
    if not normalized_records:
        return {"error": "Aucun enregistrement de présence trouvé dans le payload"}

    # Override external_meeting_id if provided explicitly
    if external_meeting_id:
        for rec in normalized_records:
            rec.external_meeting_id = external_meeting_id

    # 6. Store raw payload as ingestion log
    ingestion_log_id = str(uuid.uuid4())
    payload_hash = hashlib.sha256(json.dumps(raw_payload, sort_keys=True, default=str).encode()).hexdigest()[:32]

    # Check for duplicate ingestion
    existing_log = db.video_ingestion_logs.find_one({
        "appointment_id": appointment_id,
        "payload_hash": payload_hash,
    })
    if existing_log:
        return {
            "error": "Ce payload a déjà été ingéré pour ce rendez-vous",
            "existing_ingestion_log_id": existing_log.get("ingestion_log_id"),
        }

    ingestion_log = {
        "ingestion_log_id": ingestion_log_id,
        "appointment_id": appointment_id,
        "provider": adapter.PROVIDER_NAME,
        "provider_evidence_ceiling": adapter.EVIDENCE_CEILING,
        "external_meeting_id": external_meeting_id or (normalized_records[0].external_meeting_id if normalized_records else None),
        "raw_payload": raw_payload,
        "payload_hash": payload_hash,
        "normalized_record_count": len(normalized_records),
        "ingested_by": ingested_by,
        "ingested_at": now_utc().isoformat(),
        "source_trust": source_trust,
    }
    db.video_ingestion_logs.insert_one(ingestion_log)

    # 7. Match and create evidence
    records_created = 0
    matched_participants = []
    unmatched_records = []
    errors = []

    for norm_rec in normalized_records:
        best_match = None
        best_confidence_rank = -1
        confidence_ranks = {"high": 3, "medium": 2, "low": 1}

        for participant in accepted_participants:
            p_email = participant.get("email", "")
            p_name = f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip()

            match_result = adapter.match_participant_identity(norm_rec, p_email, p_name)
            if match_result["matched"]:
                rank = confidence_ranks.get(match_result["confidence"], 0)
                if rank > best_confidence_rank:
                    best_confidence_rank = rank
                    best_match = {
                        "participant": participant,
                        "match_result": match_result,
                    }

        if best_match:
            participant = best_match["participant"]
            match_result = best_match["match_result"]

            # Check if evidence already exists for this participant from this provider
            existing = db.evidence_items.find_one({
                "appointment_id": appointment_id,
                "participant_id": participant["participant_id"],
                "source": "video_conference",
                "derived_facts.provider": adapter.PROVIDER_NAME,
            })
            if existing:
                errors.append(f"Preuve vidéo déjà existante pour {participant.get('email')} (provider: {adapter.PROVIDER_NAME})")
                continue

            # Compute temporal consistency
            join_dt = parse_iso_datetime(norm_rec.joined_at) if norm_rec.joined_at else None
            temporal = {"consistency": "unknown", "detail": "Pas de timestamp de connexion"}
            if join_dt:
                temporal = assess_temporal_consistency(join_dt, appointment)

            # Compute video attendance outcome
            video_outcome = _compute_video_outcome(
                temporal=temporal,
                duration_seconds=norm_rec.duration_seconds,
                appointment=appointment,
                identity_confidence=match_result["confidence"],
                provider_ceiling=adapter.EVIDENCE_CEILING,
            )

            # Determine final evidence confidence
            evidence_confidence = _compute_video_evidence_confidence(
                identity_confidence=match_result["confidence"],
                temporal=temporal,
                provider_ceiling=adapter.EVIDENCE_CEILING,
                video_outcome=video_outcome,
            )

            # Build derived facts
            derived_facts = {
                "provider": adapter.PROVIDER_NAME,
                "external_meeting_id": norm_rec.external_meeting_id,
                "joined_at": norm_rec.joined_at,
                "left_at": norm_rec.left_at,
                "duration_seconds": norm_rec.duration_seconds,
                "identity_confidence": match_result["confidence"],
                "identity_match_method": match_result["method"],
                "identity_match_detail": match_result["detail"],
                "temporal_consistency": temporal.get("consistency", "unknown"),
                "temporal_detail": temporal.get("detail", ""),
                "provider_evidence_ceiling": adapter.EVIDENCE_CEILING,
                "video_attendance_outcome": video_outcome,
                "participant_email_from_provider": norm_rec.participant_email,
                "participant_name_from_provider": norm_rec.participant_name,
                "source_trust": source_trust,
            }

            # Create evidence item
            create_evidence(
                appointment_id=appointment_id,
                participant_id=participant["participant_id"],
                source="video_conference",
                created_by=ingested_by,
                source_timestamp=norm_rec.joined_at or now_utc().isoformat(),
                derived_facts=derived_facts,
                confidence_score=evidence_confidence,
                raw_payload_reference=ingestion_log_id,
            )

            records_created += 1
            matched_participants.append({
                "participant_id": participant["participant_id"],
                "participant_email": participant.get("email"),
                "identity_confidence": match_result["confidence"],
                "video_outcome": video_outcome,
                "evidence_confidence": evidence_confidence,
                "source_trust": source_trust,
            })
        else:
            unmatched_records.append({
                "provider_email": norm_rec.participant_email,
                "provider_name": norm_rec.participant_name,
                "reason": "Aucun participant NLYT correspondant",
            })

    # Update ingestion log with results
    db.video_ingestion_logs.update_one(
        {"ingestion_log_id": ingestion_log_id},
        {"$set": {
            "records_created": records_created,
            "matched_count": len(matched_participants),
            "unmatched_count": len(unmatched_records),
            "matched_participants": matched_participants,
            "unmatched_records": unmatched_records,
            "processing_errors": errors,
        }}
    )

    # Update appointment with video meeting info if not already set
    update_fields = {}
    if external_meeting_id and not appointment.get("external_meeting_id"):
        update_fields["external_meeting_id"] = external_meeting_id
    if normalized_records and not appointment.get("meeting_join_url"):
        # No URL in attendance reports typically, but track the meeting ID
        pass
    if update_fields:
        db.appointments.update_one(
            {"appointment_id": appointment_id},
            {"$set": update_fields}
        )

    logger.info(
        f"[VIDEO] Ingested {adapter.PROVIDER_NAME} for apt {appointment_id[:8]}: "
        f"{records_created} evidence created, {len(matched_participants)} matched, "
        f"{len(unmatched_records)} unmatched"
    )

    return {
        "success": True,
        "ingestion_log_id": ingestion_log_id,
        "provider": adapter.PROVIDER_NAME,
        "provider_evidence_ceiling": adapter.EVIDENCE_CEILING,
        "records_created": records_created,
        "matched": matched_participants,
        "unmatched": unmatched_records,
        "errors": errors,
    }


def _compute_video_outcome(
    temporal: dict,
    duration_seconds: Optional[int],
    appointment: dict,
    identity_confidence: str,
    provider_ceiling: str,
) -> str:
    """
    Determine video attendance outcome.
    Returns: "joined_on_time" | "joined_late" | "partial_attendance" | "no_join_detected" | "manual_review"
    """
    tc = temporal.get("consistency", "unknown")

    # If Google Meet (assisted) → always manual_review
    if provider_ceiling == "assisted":
        return "manual_review"

    # If identity is low confidence → manual_review
    if identity_confidence == "low":
        return "manual_review"

    # If no temporal data → manual_review
    if tc == "unknown":
        return "manual_review"

    # If way too early or too late → manual_review
    if tc in ("too_early", "too_late"):
        return "manual_review"

    # Valid timing
    if tc == "valid":
        # Check if they stayed long enough (at least 50% of meeting duration)
        meeting_duration = appointment.get("duration_minutes", 60) * 60
        if duration_seconds is not None and meeting_duration > 0:
            attendance_ratio = duration_seconds / meeting_duration
            if attendance_ratio < 0.5:
                return "manual_review"  # Less than 50% attendance
        return "joined_on_time"

    if tc == "valid_late":
        return "joined_late"

    return "manual_review"


def _compute_video_evidence_confidence(
    identity_confidence: str,
    temporal: dict,
    provider_ceiling: str,
    video_outcome: str,
) -> str:
    """
    Compute final evidence confidence for a video attendance record.
    Combines identity confidence, temporal consistency, and provider ceiling.
    """
    # Google Meet = ALWAYS low
    if provider_ceiling == "assisted":
        return "low"

    # If outcome is manual_review → confidence is at most medium
    if video_outcome == "manual_review":
        return "low"

    # Identity drives the base
    tc = temporal.get("consistency", "unknown")

    if identity_confidence == "high" and tc in ("valid", "valid_late"):
        return "high"
    elif identity_confidence == "high" and tc in ("too_early", "too_late"):
        return "medium"
    elif identity_confidence == "medium" and tc in ("valid", "valid_late"):
        return "medium"
    else:
        return "low"


def get_video_evidence_for_appointment(appointment_id: str) -> dict:
    """Get all video evidence and ingestion logs for an appointment."""
    ingestion_logs = list(db.video_ingestion_logs.find(
        {"appointment_id": appointment_id},
        {"_id": 0, "raw_payload": 0}  # Exclude large raw payloads
    ))

    video_evidence = list(db.evidence_items.find(
        {"appointment_id": appointment_id, "source": "video_conference"},
        {"_id": 0}
    ))

    return {
        "appointment_id": appointment_id,
        "ingestion_logs": ingestion_logs,
        "video_evidence": video_evidence,
        "total_ingestions": len(ingestion_logs),
        "total_video_evidence": len(video_evidence),
    }


def get_ingestion_log(ingestion_log_id: str) -> Optional[dict]:
    """Get a specific ingestion log with full details."""
    log = db.video_ingestion_logs.find_one(
        {"ingestion_log_id": ingestion_log_id},
        {"_id": 0}
    )
    return log
