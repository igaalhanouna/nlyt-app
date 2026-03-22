"""
Google Meet Video Provider Adapter

Normalizes Google Meet attendance data.
Google Meet provides WEAK identity signals in most configurations:
- No authenticated email in many cases
- Display names can be arbitrary
- No official attendance API in standard Workspace editions

Evidence ceiling: ASSISTED — Google Meet alone NEVER triggers auto-penalty.
This adapter always caps identity_confidence at "low" regardless of signals.

Manual ingestion format (organizer uploads CSV or JSON):
{
    "meeting_id": "abc-defg-hij",
    "participants": [
        {
            "name": "John Doe",
            "email": "john@example.com",  (often absent)
            "join_time": "2026-01-01T10:00:00Z",
            "leave_time": "2026-01-01T11:00:00Z",
            "duration": 3600
        }
    ]
}
"""
import hashlib
import json
import logging
from typing import List

from adapters.video_providers.base import (
    VideoProviderAdapter,
    NormalizedAttendanceRecord,
)

logger = logging.getLogger(__name__)


class MeetAdapter(VideoProviderAdapter):
    PROVIDER_NAME = "meet"
    # CRITICAL: Google Meet = assisted evidence ONLY
    EVIDENCE_CEILING = "assisted"

    def validate_payload(self, raw_payload: dict) -> dict:
        if not raw_payload:
            return {"valid": False, "error": "Payload vide"}

        meeting_id = raw_payload.get("meeting_id") or raw_payload.get("id")
        if not meeting_id:
            return {"valid": False, "error": "meeting_id manquant"}

        participants = raw_payload.get("participants", [])
        if not isinstance(participants, list):
            return {"valid": False, "error": "participants doit etre une liste"}

        return {"valid": True, "error": None}

    def normalize_attendance(self, raw_payload: dict) -> List[NormalizedAttendanceRecord]:
        records = []
        meeting_id = str(raw_payload.get("meeting_id") or raw_payload.get("id", ""))
        participants = raw_payload.get("participants", [])
        payload_hash = hashlib.sha256(json.dumps(raw_payload, sort_keys=True, default=str).encode()).hexdigest()[:16]

        for p in participants:
            email = (p.get("email") or "").strip().lower() or None
            name = (p.get("name") or p.get("displayName") or "").strip() or None
            join_time = p.get("join_time") or p.get("joinTime") or ""
            leave_time = p.get("leave_time") or p.get("leaveTime")
            duration = p.get("duration") or p.get("durationSeconds")

            # CRITICAL: Google Meet identity is ALWAYS capped at "low"
            # Even with email, Meet doesn't guarantee authenticated identity
            if email:
                identity_confidence = "low"
                identity_method = "meet_unverified_email"
            elif name:
                identity_confidence = "low"
                identity_method = "meet_display_name_only"
            else:
                identity_confidence = "low"
                identity_method = "meet_anonymous"

            records.append(NormalizedAttendanceRecord(
                provider=self.PROVIDER_NAME,
                external_meeting_id=meeting_id,
                participant_email=email,
                participant_name=name,
                joined_at=join_time,
                left_at=leave_time,
                duration_seconds=duration,
                identity_confidence=identity_confidence,
                identity_match_method=identity_method,
                raw_participant_id=p.get("id"),
                raw_payload_hash=payload_hash,
            ))

        logger.info(f"[MEET] Normalized {len(records)} attendance records for meeting {meeting_id} (all capped at LOW confidence)")
        return records

    def match_participant_identity(
        self,
        normalized_record: NormalizedAttendanceRecord,
        known_email: str,
        known_name: str,
    ) -> dict:
        """
        Google Meet identity matching is ALWAYS low confidence.
        Even a perfect email match stays low because Meet doesn't
        guarantee the email is authenticated.
        """
        known_email_lower = (known_email or "").strip().lower()
        known_name_lower = (known_name or "").strip().lower()
        record_email = (normalized_record.participant_email or "").strip().lower()
        record_name = (normalized_record.participant_name or "").strip().lower()

        # Email match — but still LOW because Meet doesn't verify identity
        if record_email and known_email_lower and record_email == known_email_lower:
            return {
                "matched": True,
                "confidence": "low",
                "method": "meet_email_unverified",
                "detail": f"Email Meet '{record_email}' correspond mais non verifie par Google",
            }

        # Name match — very weak
        if record_name and known_name_lower and _fuzzy_name_match(record_name, known_name_lower):
            return {
                "matched": True,
                "confidence": "low",
                "method": "meet_name_only",
                "detail": f"Nom similaire mais non verifie: '{record_name}'",
            }

        return {
            "matched": False,
            "confidence": "low",
            "method": "no_match",
            "detail": f"Aucune correspondance (Meet: {record_email or record_name})",
        }


def _fuzzy_name_match(name_a: str, name_b: str) -> bool:
    tokens_a = set(name_a.lower().split())
    tokens_b = set(name_b.lower().split())
    if not tokens_a or not tokens_b:
        return False
    overlap = tokens_a & tokens_b
    return len(overlap) >= 1 and any(len(t) > 1 for t in overlap)
