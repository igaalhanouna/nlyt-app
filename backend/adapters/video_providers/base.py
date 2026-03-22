"""
Base interface for video conference provider adapters.

Each adapter normalizes raw attendance data from its provider
into a standard format consumable by the evidence engine.

Standard normalized attendance record:
{
    "provider": "zoom" | "teams" | "meet",
    "external_meeting_id": str,
    "participant_email": str | None,
    "participant_name": str | None,
    "joined_at": str (ISO UTC),
    "left_at": str | None (ISO UTC),
    "duration_seconds": int | None,
    "identity_confidence": "high" | "medium" | "low",
    "identity_match_method": str,
    "raw_participant_id": str | None,
    "raw_payload_hash": str | None,
}
"""
from abc import ABC, abstractmethod
from typing import List, Optional


class NormalizedAttendanceRecord:
    """Standard attendance record after normalization."""

    def __init__(
        self,
        provider: str,
        external_meeting_id: str,
        participant_email: Optional[str],
        participant_name: Optional[str],
        joined_at: str,
        left_at: Optional[str],
        duration_seconds: Optional[int],
        identity_confidence: str,
        identity_match_method: str,
        raw_participant_id: Optional[str] = None,
        raw_payload_hash: Optional[str] = None,
    ):
        self.provider = provider
        self.external_meeting_id = external_meeting_id
        self.participant_email = participant_email
        self.participant_name = participant_name
        self.joined_at = joined_at
        self.left_at = left_at
        self.duration_seconds = duration_seconds
        self.identity_confidence = identity_confidence
        self.identity_match_method = identity_match_method
        self.raw_participant_id = raw_participant_id
        self.raw_payload_hash = raw_payload_hash

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "external_meeting_id": self.external_meeting_id,
            "participant_email": self.participant_email,
            "participant_name": self.participant_name,
            "joined_at": self.joined_at,
            "left_at": self.left_at,
            "duration_seconds": self.duration_seconds,
            "identity_confidence": self.identity_confidence,
            "identity_match_method": self.identity_match_method,
            "raw_participant_id": self.raw_participant_id,
            "raw_payload_hash": self.raw_payload_hash,
        }


class VideoProviderAdapter(ABC):
    """Abstract base class for video provider adapters."""

    PROVIDER_NAME: str = ""

    # Provider-level evidence strength ceiling
    # "strong" = can auto-decide if identity matches
    # "assisted" = can only assist, never auto-decide alone
    EVIDENCE_CEILING: str = "strong"

    @abstractmethod
    def normalize_attendance(self, raw_payload: dict) -> List[NormalizedAttendanceRecord]:
        """
        Normalize raw provider payload into standard attendance records.
        Returns a list of NormalizedAttendanceRecord.
        """
        pass

    @abstractmethod
    def match_participant_identity(
        self,
        normalized_record: NormalizedAttendanceRecord,
        known_email: str,
        known_name: str,
    ) -> dict:
        """
        Match a normalized attendance record against a known NLYT participant.
        Returns: {"matched": bool, "confidence": "high"|"medium"|"low", "method": str, "detail": str}
        """
        pass

    @abstractmethod
    def validate_payload(self, raw_payload: dict) -> dict:
        """
        Validate the raw payload structure.
        Returns: {"valid": bool, "error": str | None}
        """
        pass
