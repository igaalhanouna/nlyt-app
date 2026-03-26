"""
Zoom Video Provider Adapter

Normalizes Zoom attendance reports / webhook payloads.
Zoom provides strong identity signals via authenticated user emails.

Zoom attendance report format (from Reports API):
{
    "meeting_id": "123456789",
    "topic": "My Meeting",
    "participants": [
        {
            "id": "user-uuid",
            "name": "John Doe",
            "user_email": "john@example.com",
            "join_time": "2026-01-01T10:00:00Z",
            "leave_time": "2026-01-01T11:00:00Z",
            "duration": 3600
        }
    ]
}

Evidence ceiling: STRONG — Zoom authenticates users via SSO/email login.
"""
import hashlib
import json
import logging
from typing import List
from datetime import datetime, timezone

from adapters.video_providers.base import (
    VideoProviderAdapter,
    NormalizedAttendanceRecord,
)

logger = logging.getLogger(__name__)


class ZoomAdapter(VideoProviderAdapter):
    PROVIDER_NAME = "zoom"
    EVIDENCE_CEILING = "strong"

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
            email = (p.get("user_email") or p.get("email") or "").strip().lower() or None
            name = (p.get("name") or "").strip() or None
            join_time = p.get("join_time", "")
            leave_time = p.get("leave_time")
            duration = p.get("duration")
            role = (p.get("role") or "").strip().lower() or None

            # Determine identity confidence based on available signals
            if email:
                identity_confidence = "high"
                identity_method = "zoom_authenticated_email"
            elif name:
                identity_confidence = "medium"
                identity_method = "zoom_display_name_only"
            else:
                identity_confidence = "low"
                identity_method = "zoom_anonymous"

            rec = NormalizedAttendanceRecord(
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
            )
            rec.provider_role = role  # "host" | "attendee" | None
            records.append(rec)

        logger.info(f"[ZOOM] Normalized {len(records)} attendance records for meeting {meeting_id}")
        return records

    def match_participant_identity(
        self,
        normalized_record: NormalizedAttendanceRecord,
        known_email: str,
        known_name: str,
    ) -> dict:
        known_email_lower = (known_email or "").strip().lower()
        known_name_lower = (known_name or "").strip().lower()
        record_email = (normalized_record.participant_email or "").strip().lower()
        record_name = (normalized_record.participant_name or "").strip().lower()

        # Best: exact email match
        if record_email and known_email_lower and record_email == known_email_lower:
            return {
                "matched": True,
                "confidence": "high",
                "method": "exact_email_match",
                "detail": f"Email Zoom '{record_email}' = email NLYT",
            }

        # Medium: email domain match + partial name
        if record_email and known_email_lower:
            record_domain = record_email.split("@")[-1] if "@" in record_email else ""
            known_domain = known_email_lower.split("@")[-1] if "@" in known_email_lower else ""
            if record_domain and record_domain == known_domain and record_name and known_name_lower:
                if _fuzzy_name_match(record_name, known_name_lower):
                    return {
                        "matched": True,
                        "confidence": "medium",
                        "method": "domain_and_name_match",
                        "detail": f"Meme domaine '{record_domain}' + nom similaire",
                    }

        # Low: name-only match
        if record_name and known_name_lower and _fuzzy_name_match(record_name, known_name_lower):
            return {
                "matched": True,
                "confidence": "low",
                "method": "name_only_match",
                "detail": f"Nom similaire: '{record_name}' ≈ '{known_name_lower}'",
            }

        return {
            "matched": False,
            "confidence": "low",
            "method": "no_match",
            "detail": f"Aucune correspondance (Zoom: {record_email or record_name})",
        }


def _fuzzy_name_match(name_a: str, name_b: str) -> bool:
    """Simple fuzzy name matching: check if first/last name tokens overlap."""
    tokens_a = set(name_a.lower().split())
    tokens_b = set(name_b.lower().split())
    if not tokens_a or not tokens_b:
        return False
    overlap = tokens_a & tokens_b
    # At least one meaningful token must match
    return len(overlap) >= 1 and any(len(t) > 1 for t in overlap)
