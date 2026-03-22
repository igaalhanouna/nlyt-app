"""
Microsoft Teams Video Provider Adapter

Normalizes Teams attendance reports from Graph API.
Teams provides strong identity signals via AAD-authenticated user emails.

Teams attendance report format (Graph API /onlineMeetings/{id}/attendanceReports):
{
    "meeting_id": "AAMkAG...",
    "attendanceRecords": [
        {
            "emailAddress": "john@example.com",
            "identity": {"displayName": "John Doe"},
            "totalAttendanceInSeconds": 3600,
            "attendanceIntervals": [
                {"joinDateTime": "2026-01-01T10:00:00Z", "leaveDateTime": "2026-01-01T11:00:00Z", "durationInSeconds": 3600}
            ],
            "role": "Attendee"
        }
    ]
}

Evidence ceiling: STRONG — Teams authenticates users via Azure AD.
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


class TeamsAdapter(VideoProviderAdapter):
    PROVIDER_NAME = "teams"
    EVIDENCE_CEILING = "strong"

    def validate_payload(self, raw_payload: dict) -> dict:
        if not raw_payload:
            return {"valid": False, "error": "Payload vide"}

        meeting_id = raw_payload.get("meeting_id") or raw_payload.get("id")
        if not meeting_id:
            return {"valid": False, "error": "meeting_id manquant"}

        records = raw_payload.get("attendanceRecords") or raw_payload.get("participants", [])
        if not isinstance(records, list):
            return {"valid": False, "error": "attendanceRecords doit etre une liste"}

        return {"valid": True, "error": None}

    def normalize_attendance(self, raw_payload: dict) -> List[NormalizedAttendanceRecord]:
        results = []
        meeting_id = str(raw_payload.get("meeting_id") or raw_payload.get("id", ""))
        records = raw_payload.get("attendanceRecords") or raw_payload.get("participants", [])
        payload_hash = hashlib.sha256(json.dumps(raw_payload, sort_keys=True, default=str).encode()).hexdigest()[:16]

        for r in records:
            email = (r.get("emailAddress") or "").strip().lower() or None
            identity = r.get("identity", {})
            name = (identity.get("displayName") or r.get("name") or "").strip() or None
            total_seconds = r.get("totalAttendanceInSeconds") or r.get("duration")

            # Use first attendance interval for join/leave times
            intervals = r.get("attendanceIntervals", [])
            join_time = None
            leave_time = None
            if intervals:
                join_time = intervals[0].get("joinDateTime")
                leave_time = intervals[-1].get("leaveDateTime")
            else:
                join_time = r.get("join_time") or r.get("joinDateTime")
                leave_time = r.get("leave_time") or r.get("leaveDateTime")

            # Identity confidence
            if email:
                identity_confidence = "high"
                identity_method = "teams_aad_email"
            elif name:
                identity_confidence = "medium"
                identity_method = "teams_display_name_only"
            else:
                identity_confidence = "low"
                identity_method = "teams_anonymous"

            results.append(NormalizedAttendanceRecord(
                provider=self.PROVIDER_NAME,
                external_meeting_id=meeting_id,
                participant_email=email,
                participant_name=name,
                joined_at=join_time or "",
                left_at=leave_time,
                duration_seconds=total_seconds,
                identity_confidence=identity_confidence,
                identity_match_method=identity_method,
                raw_participant_id=r.get("id"),
                raw_payload_hash=payload_hash,
            ))

        logger.info(f"[TEAMS] Normalized {len(results)} attendance records for meeting {meeting_id}")
        return results

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

        # AAD email = high confidence
        if record_email and known_email_lower and record_email == known_email_lower:
            return {
                "matched": True,
                "confidence": "high",
                "method": "exact_email_match",
                "detail": f"Email Teams AAD '{record_email}' = email NLYT",
            }

        # Same domain + name match
        if record_email and known_email_lower:
            record_domain = record_email.split("@")[-1] if "@" in record_email else ""
            known_domain = known_email_lower.split("@")[-1] if "@" in known_email_lower else ""
            if record_domain and record_domain == known_domain and record_name and known_name_lower:
                if _fuzzy_name_match(record_name, known_name_lower):
                    return {
                        "matched": True,
                        "confidence": "medium",
                        "method": "domain_and_name_match",
                        "detail": f"Meme domaine AAD '{record_domain}' + nom similaire",
                    }

        # Name only
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
            "detail": f"Aucune correspondance (Teams: {record_email or record_name})",
        }


def _fuzzy_name_match(name_a: str, name_b: str) -> bool:
    tokens_a = set(name_a.lower().split())
    tokens_b = set(name_b.lower().split())
    if not tokens_a or not tokens_b:
        return False
    overlap = tokens_a & tokens_b
    return len(overlap) >= 1 and any(len(t) > 1 for t in overlap)
