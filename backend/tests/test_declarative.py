"""
Tests for Declarative Service — V3 Trustless Collaborative Presence Sheets

Covers:
1. Phase initialization (N>=3, N<3, no manual_review)
2. Sheet submission (validations, trigger analysis)
3. Declaration analysis (unanimity, coherence, contradictions)
4. Dispute creation and resolution
5. Deadline enforcement
6. Reclassification blocking during dispute
"""
import pytest
import os
import sys
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime, timezone, timedelta
import uuid

sys.path.insert(0, '/app/backend')
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
os.environ.setdefault('DB_NAME', 'test_declarative')


# ═══════════════════════════════════════════════════════════════════
# Test helpers
# ═══════════════════════════════════════════════════════════════════

def make_id():
    return str(uuid.uuid4())


def make_appointment(apt_id="apt1", phase=None):
    return {
        "appointment_id": apt_id,
        "organizer_id": "org_user",
        "tolerated_delay_minutes": 5,
        "penalty_amount": 30,
        "declarative_phase": phase,
    }


def make_participants(apt_id="apt1", count=4):
    parts = [
        {"participant_id": "p_org", "user_id": "org_user", "appointment_id": apt_id,
         "is_organizer": True, "status": "accepted_guaranteed"},
    ]
    for i in range(1, count):
        parts.append({
            "participant_id": f"p{i}", "user_id": f"user{i}", "appointment_id": apt_id,
            "is_organizer": False, "status": "accepted_guaranteed",
        })
    return parts


# ═══════════════════════════════════════════════════════════════════
# 1. Unanimity check
# ═══════════════════════════════════════════════════════════════════

class TestCheckUnanimity:
    def test_unanimous_absent(self):
        from services.declarative_service import _check_unanimity
        sheets = [
            {"submitted_by_participant_id": "p_org", "status": "submitted",
             "declarations": [{"target_participant_id": "p1", "declared_status": "absent"}]},
            {"submitted_by_participant_id": "p2", "status": "submitted",
             "declarations": [{"target_participant_id": "p1", "declared_status": "absent"}]},
        ]
        result = _check_unanimity("p1", sheets)
        assert result["unanimous"] is True
        assert result["status"] == "absent"
        assert result["expressed_count"] == 2

    def test_unanimous_present(self):
        from services.declarative_service import _check_unanimity
        sheets = [
            {"submitted_by_participant_id": "p_org", "status": "submitted",
             "declarations": [{"target_participant_id": "p1", "declared_status": "present_on_time"}]},
            {"submitted_by_participant_id": "p2", "status": "submitted",
             "declarations": [{"target_participant_id": "p1", "declared_status": "present_on_time"}]},
        ]
        result = _check_unanimity("p1", sheets)
        assert result["unanimous"] is True
        assert result["status"] == "present_on_time"

    def test_disagreement(self):
        from services.declarative_service import _check_unanimity
        sheets = [
            {"submitted_by_participant_id": "p_org", "status": "submitted",
             "declarations": [{"target_participant_id": "p1", "declared_status": "absent"}]},
            {"submitted_by_participant_id": "p2", "status": "submitted",
             "declarations": [{"target_participant_id": "p1", "declared_status": "present_on_time"}]},
        ]
        result = _check_unanimity("p1", sheets)
        assert result["unanimous"] is False
        assert result["reason"] == "tiers_disagreement"

    def test_fewer_than_2_expressed(self):
        from services.declarative_service import _check_unanimity
        sheets = [
            {"submitted_by_participant_id": "p_org", "status": "submitted",
             "declarations": [{"target_participant_id": "p1", "declared_status": "absent"}]},
            {"submitted_by_participant_id": "p2", "status": "submitted",
             "declarations": [{"target_participant_id": "p1", "declared_status": "unknown"}]},
        ]
        result = _check_unanimity("p1", sheets)
        assert result["unanimous"] is False
        assert result["reason"] == "fewer_than_2_expressed"

    def test_excludes_self(self):
        """Target's own sheet should not count in unanimity."""
        from services.declarative_service import _check_unanimity
        sheets = [
            {"submitted_by_participant_id": "p1", "status": "submitted",
             "declarations": [{"target_participant_id": "p1", "declared_status": "present_on_time"}]},
            {"submitted_by_participant_id": "p_org", "status": "submitted",
             "declarations": [{"target_participant_id": "p1", "declared_status": "absent"}]},
            {"submitted_by_participant_id": "p2", "status": "submitted",
             "declarations": [{"target_participant_id": "p1", "declared_status": "absent"}]},
        ]
        result = _check_unanimity("p1", sheets)
        assert result["unanimous"] is True
        assert result["status"] == "absent"
        assert result["expressed_count"] == 2


# ═══════════════════════════════════════════════════════════════════
# 2. Global coherence check
# ═══════════════════════════════════════════════════════════════════

class TestCheckGlobalCoherence:
    def test_coherent(self):
        from services.declarative_service import _check_global_coherence
        sheets = [
            {"submitted_by_participant_id": "p_org",
             "declarations": [{"target_participant_id": "p1", "declared_status": "absent"}]},
            {"submitted_by_participant_id": "p2",
             "declarations": [{"target_participant_id": "p1", "declared_status": "absent"}]},
        ]
        result = _check_global_coherence(sheets)
        assert result["coherent"] is True

    def test_cross_accusation_detected(self):
        from services.declarative_service import _check_global_coherence
        sheets = [
            {"submitted_by_participant_id": "p1",
             "declarations": [{"target_participant_id": "p2", "declared_status": "absent"}]},
            {"submitted_by_participant_id": "p2",
             "declarations": [{"target_participant_id": "p1", "declared_status": "absent"}]},
        ]
        result = _check_global_coherence(sheets)
        assert result["coherent"] is False
        assert result["reason"] == "cross_accusation"


# ═══════════════════════════════════════════════════════════════════
# 3. Contradiction signal check
# ═══════════════════════════════════════════════════════════════════

class TestCheckContradictionSignals:
    @patch('services.declarative_service.db')
    def test_no_contradiction_when_not_absent(self, mock_db):
        from services.declarative_service import _check_contradiction_signals
        unanimity = {"unanimous": True, "status": "present_on_time"}
        result = _check_contradiction_signals("p1", unanimity, [], "apt1")
        assert result["contradiction"] is False

    @patch('services.declarative_service.db')
    def test_contestant_contradiction(self, mock_db):
        """Target submitted their sheet = active = contradiction if tiers say absent."""
        from services.declarative_service import _check_contradiction_signals
        mock_db.evidence_items.find.return_value = []
        sheets = [
            {"submitted_by_participant_id": "p1", "submitted_by_user_id": "user1",
             "status": "submitted", "declarations": []},
            {"submitted_by_participant_id": "p_org", "submitted_by_user_id": "org_user",
             "status": "submitted",
             "declarations": [{"target_participant_id": "p1", "declared_status": "absent"}]},
        ]
        unanimity = {"unanimous": True, "status": "absent"}
        result = _check_contradiction_signals("p1", unanimity, sheets, "apt1")
        assert result["contradiction"] is True
        assert result["reason"] == "contestant_contradiction"

    @patch('services.declarative_service.db')
    def test_tech_signal_contradiction(self, mock_db):
        """Weak tech evidence exists but declarative says absent → contradiction."""
        from services.declarative_service import _check_contradiction_signals
        mock_db.evidence_items.find.return_value = [
            {"evidence_type": "manual_checkin"}  # Weak but exists
        ]
        sheets = [
            {"submitted_by_participant_id": "p_org", "submitted_by_user_id": "org_user",
             "status": "submitted",
             "declarations": [{"target_participant_id": "p1", "declared_status": "absent"}]},
        ]
        unanimity = {"unanimous": True, "status": "absent"}
        result = _check_contradiction_signals("p1", unanimity, sheets, "apt1")
        assert result["contradiction"] is True
        assert result["reason"] == "tech_signal_contradiction"

    @patch('services.declarative_service.db')
    def test_collusion_signal(self, mock_db):
        """All accusers are also the only beneficiaries → collusion."""
        from services.declarative_service import _check_contradiction_signals
        mock_db.evidence_items.find.return_value = []
        mock_db.attendance_records.find.return_value = [
            {"participant_id": "p_org", "outcome": "on_time", "review_required": False},
            {"participant_id": "p2", "outcome": "on_time", "review_required": False},
        ]
        mock_db.participants.find_one.side_effect = lambda q, p=None: (
            {"user_id": "org_user"} if q.get("participant_id") == "p_org"
            else {"user_id": "user2"} if q.get("participant_id") == "p2"
            else None
        )
        sheets = [
            {"submitted_by_participant_id": "p_org", "submitted_by_user_id": "org_user",
             "status": "submitted",
             "declarations": [{"target_participant_id": "p1", "declared_status": "absent"}]},
            {"submitted_by_participant_id": "p2", "submitted_by_user_id": "user2",
             "status": "submitted",
             "declarations": [{"target_participant_id": "p1", "declared_status": "absent"}]},
        ]
        unanimity = {"unanimous": True, "status": "absent"}
        result = _check_contradiction_signals("p1", unanimity, sheets, "apt1")
        assert result["contradiction"] is True
        assert result["reason"] == "collusion_signal"

    @patch('services.declarative_service.db')
    def test_no_collusion_when_non_beneficiary_accuses(self, mock_db):
        """A non-beneficiary accuses → not all accusers are beneficiaries → no collusion."""
        from services.declarative_service import _check_contradiction_signals
        mock_db.evidence_items.find.return_value = []
        mock_db.attendance_records.find.return_value = [
            {"participant_id": "p_org", "outcome": "on_time", "review_required": False},
        ]
        mock_db.participants.find_one.side_effect = lambda q, p=None: (
            {"user_id": "org_user"} if q.get("participant_id") == "p_org"
            else None
        )
        sheets = [
            {"submitted_by_participant_id": "p_org", "submitted_by_user_id": "org_user",
             "status": "submitted",
             "declarations": [{"target_participant_id": "p1", "declared_status": "absent"}]},
            {"submitted_by_participant_id": "p3", "submitted_by_user_id": "user3",
             "status": "submitted",
             "declarations": [{"target_participant_id": "p1", "declared_status": "absent"}]},
        ]
        unanimity = {"unanimous": True, "status": "absent"}
        result = _check_contradiction_signals("p1", unanimity, sheets, "apt1")
        # org is beneficiary but user3 is NOT a beneficiary → not all accusers are beneficiaries
        assert result["contradiction"] is False


# ═══════════════════════════════════════════════════════════════════
# 4. Sheet submission
# ═══════════════════════════════════════════════════════════════════

class TestSubmitSheet:
    @patch('services.declarative_service.db')
    def test_reject_if_not_collecting_phase(self, mock_db):
        from services.declarative_service import submit_sheet
        mock_db.appointments.find_one.return_value = {"appointment_id": "apt1", "declarative_phase": "resolved"}
        result = submit_sheet("apt1", "user1", [])
        assert "error" in result

    @patch('services.declarative_service.db')
    def test_reject_if_already_submitted(self, mock_db):
        from services.declarative_service import submit_sheet
        mock_db.appointments.find_one.return_value = {"appointment_id": "apt1", "declarative_phase": "collecting"}
        mock_db.attendance_sheets.find_one.return_value = {
            "sheet_id": "s1", "status": "submitted", "declarations": []
        }
        result = submit_sheet("apt1", "user1", [])
        assert "error" in result

    @patch('services.declarative_service._check_and_trigger_analysis')
    @patch('services.declarative_service.db')
    def test_successful_submission(self, mock_db, mock_trigger):
        from services.declarative_service import submit_sheet
        mock_db.appointments.find_one.return_value = {"appointment_id": "apt1", "declarative_phase": "collecting"}
        mock_db.attendance_sheets.find_one.return_value = {
            "sheet_id": "s1", "status": "pending",
            "declarations": [
                {"target_participant_id": "p1", "target_user_id": "user1", "declared_status": None},
            ]
        }
        mock_db.attendance_sheets.update_one = MagicMock()

        result = submit_sheet("apt1", "org_user", [
            {"target_participant_id": "p1", "declared_status": "absent"}
        ])

        assert result.get("success") is True
        mock_db.attendance_sheets.update_one.assert_called_once()
        mock_trigger.assert_called_once_with("apt1")

    @patch('services.declarative_service.db')
    def test_reject_invalid_status(self, mock_db):
        from services.declarative_service import submit_sheet
        mock_db.appointments.find_one.return_value = {"appointment_id": "apt1", "declarative_phase": "collecting"}
        mock_db.attendance_sheets.find_one.return_value = {
            "sheet_id": "s1", "status": "pending",
            "declarations": [
                {"target_participant_id": "p1", "target_user_id": "user1", "declared_status": None},
            ]
        }
        result = submit_sheet("apt1", "org_user", [
            {"target_participant_id": "p1", "declared_status": "invalid_status"}
        ])
        assert "error" in result


# ═══════════════════════════════════════════════════════════════════
# 5. Dispute creation and resolution
# ═══════════════════════════════════════════════════════════════════

class TestDisputes:
    @patch('services.declarative_service.db')
    def test_open_dispute_creates_document(self, mock_db):
        from services.declarative_service import open_dispute
        mock_db.declarative_disputes.find_one.return_value = None
        mock_db.participants.find_one.return_value = {"user_id": "user1"}
        mock_db.declarative_disputes.insert_one = MagicMock()

        result = open_dispute("apt1", "p1", "tiers_disagreement")
        assert result is not None
        mock_db.declarative_disputes.insert_one.assert_called_once()

    @patch('services.declarative_service.db')
    def test_open_dispute_idempotent(self, mock_db):
        from services.declarative_service import open_dispute
        mock_db.declarative_disputes.find_one.return_value = {"dispute_id": "existing"}
        result = open_dispute("apt1", "p1", "tiers_disagreement")
        assert result == "existing"

    @patch('services.declarative_service.db')
    def test_resolve_dispute_updates_record(self, mock_db):
        from services.declarative_service import resolve_dispute
        mock_db.declarative_disputes.find_one.return_value = {
            "dispute_id": "d1", "status": "awaiting_evidence",
            "appointment_id": "apt1", "target_participant_id": "p1"
        }
        mock_db.declarative_disputes.update_one = MagicMock()
        mock_db.attendance_records.update_one = MagicMock()
        mock_db.declarative_disputes.count_documents.return_value = 0
        mock_db.appointments.update_one = MagicMock()
        mock_db.appointments.find_one.return_value = make_appointment()
        mock_db.participants.find.return_value = make_participants()
        mock_db.attendance_records.find.return_value = []
        mock_db.payment_guarantees.find_one.return_value = None

        with patch('services.attendance_service._process_financial_outcomes'):
            result = resolve_dispute("d1", "no_show", "Preuve insuffisante", "platform")

        assert result.get("success") is True
        mock_db.attendance_records.update_one.assert_called_once()

    @patch('services.declarative_service.db')
    def test_submit_dispute_evidence(self, mock_db):
        from services.declarative_service import submit_dispute_evidence
        mock_db.declarative_disputes.find_one.return_value = {
            "dispute_id": "d1", "status": "awaiting_evidence",
            "appointment_id": "apt1"
        }
        mock_db.participants.find_one.return_value = {"participant_id": "p1", "user_id": "user1"}
        mock_db.declarative_disputes.update_one = MagicMock()

        result = submit_dispute_evidence("d1", "user1", "text_statement", text_content="I was there")
        assert result.get("success") is True


# ═══════════════════════════════════════════════════════════════════
# 6. Reclassification blocking during dispute
# ═══════════════════════════════════════════════════════════════════

class TestReclassifyBlockedDuringDispute:
    @patch('services.attendance_service.db')
    def test_reclassify_blocked_when_dispute_open(self, mock_db):
        from services.attendance_service import reclassify_participant
        mock_db.attendance_records.find_one.return_value = {
            "record_id": "r1", "appointment_id": "apt1",
            "participant_id": "p1", "outcome": "manual_review"
        }
        mock_db.declarative_disputes.find_one.return_value = {
            "dispute_id": "d1", "status": "awaiting_evidence"
        }

        result = reclassify_participant("r1", "no_show", "org_user")
        assert "error" in result
        assert "litige" in result["error"].lower()

    @patch('services.attendance_service.db')
    def test_reclassify_allowed_when_no_dispute(self, mock_db):
        from services.attendance_service import reclassify_participant
        mock_db.attendance_records.find_one.return_value = {
            "record_id": "r1", "appointment_id": "apt1",
            "participant_id": "p1", "outcome": "manual_review"
        }
        mock_db.declarative_disputes.find_one.return_value = None
        mock_db.appointments.find_one.return_value = make_appointment()
        mock_db.participants.find.return_value = make_participants()
        mock_db.participants.find_one.return_value = {"participant_id": "p1", "user_id": "user1", "is_organizer": False}
        mock_db.attendance_records.update_one = MagicMock()
        mock_db.attendance_records.find.return_value = []
        mock_db.payment_guarantees.find_one.return_value = None
        mock_db.distributions.find_one.return_value = None

        result = reclassify_participant("r1", "on_time", "org_user")
        assert "error" not in result


# ═══════════════════════════════════════════════════════════════════
# 7. Apply declarative outcome
# ═══════════════════════════════════════════════════════════════════

class TestApplyDeclarativeOutcome:
    @patch('services.declarative_service.db')
    def test_apply_absent_as_no_show(self, mock_db):
        from services.declarative_service import _apply_declarative_outcome
        mock_db.attendance_records.update_one = MagicMock()

        result = {
            "target_participant_id": "p1",
            "unanimous_status": "absent",
            "tiers_expressed_count": 3,
        }
        _apply_declarative_outcome("apt1", result)

        call_args = mock_db.attendance_records.update_one.call_args
        update_set = call_args[0][1]["$set"]
        assert update_set["outcome"] == "no_show"
        assert update_set["decision_source"] == "declarative"
        assert update_set["confidence_level"] == "MEDIUM"
        assert update_set["review_required"] is False

    @patch('services.declarative_service.db')
    def test_apply_present_on_time(self, mock_db):
        from services.declarative_service import _apply_declarative_outcome
        mock_db.attendance_records.update_one = MagicMock()

        result = {
            "target_participant_id": "p1",
            "unanimous_status": "present_on_time",
            "tiers_expressed_count": 2,
        }
        _apply_declarative_outcome("apt1", result)

        update_set = mock_db.attendance_records.update_one.call_args[0][1]["$set"]
        assert update_set["outcome"] == "on_time"

    @patch('services.declarative_service.db')
    def test_apply_present_late(self, mock_db):
        from services.declarative_service import _apply_declarative_outcome
        mock_db.attendance_records.update_one = MagicMock()

        result = {
            "target_participant_id": "p1",
            "unanimous_status": "present_late",
            "tiers_expressed_count": 2,
        }
        _apply_declarative_outcome("apt1", result)

        update_set = mock_db.attendance_records.update_one.call_args[0][1]["$set"]
        assert update_set["outcome"] == "late"
