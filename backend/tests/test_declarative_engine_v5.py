"""
Tests for Declarative Engine V5 / V5.1

V5 — Presumption of Presence & Auto-Litige Guard (Tests 1-11)
V5.1 — Guaranteed-Only Declarative Phase (Tests 12-17)

V5.1 Rule:
  - Only `accepted_guaranteed` participants in manual_review enter the declarative phase.
  - Non-guaranteed participants are auto-resolved to `waived` immediately.
  - If < 2 guaranteed participants remain, declarative_phase = `not_needed`.
  - Auto-waived participants: no pending sheet, no dispute, no penalty, no admin noise.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import uuid
import pytest
from unittest.mock import patch, MagicMock, call
from services.declarative_service import (
    _run_small_group_analysis,
    _run_large_group_analysis,
    _has_negative_tech_evidence,
    open_dispute,
    _apply_declarative_outcome,
    _check_unanimity,
    initialize_declarative_phase,
)


def make_pid():
    return str(uuid.uuid4())


def make_review_records(pids):
    return [{"participant_id": pid} for pid in pids]


def make_sheet(submitter_pid, submitter_uid, declarations, status="submitted"):
    return {
        "sheet_id": str(uuid.uuid4()),
        "submitted_by_participant_id": submitter_pid,
        "submitted_by_user_id": submitter_uid,
        "status": status,
        "declarations": declarations,
    }


def make_decl(target_pid, declared_status, is_self=False):
    return {
        "target_participant_id": target_pid,
        "target_user_id": "",
        "declared_status": declared_status,
        "is_self_declaration": is_self,
    }


# ═══════════════════════════════════════════════════════════════════
# SMALL GROUP TESTS (< 3 participants)
# ═══════════════════════════════════════════════════════════════════

class TestSmallGroupAnalysis:
    """Tests 1-4: Small group (< 3 participants)."""

    def test_1_all_unknown_no_neg_tech_waived(self):
        """Test 1: All unknown + no negative tech → waived."""
        apt_id = str(uuid.uuid4())
        target = make_pid()
        submitter = make_pid()

        review_records = make_review_records([target])
        sheets = [
            make_sheet(submitter, "uid_sub", [make_decl(target, "unknown")]),
        ]

        with patch('services.declarative_service._has_negative_tech_evidence', return_value=False):
            results = _run_small_group_analysis(apt_id, review_records, sheets)

        assert len(results) == 1
        r = results[0]
        assert r["auto_resolvable"] is True
        assert r["unanimous_status"] == "waived"
        assert r["tiers_expressed_count"] == 0
        print("TEST 1 PASS: All unknown + no neg tech → waived")

    def test_2_all_unknown_with_neg_tech_dispute(self):
        """Test 2: All unknown + negative tech evidence → dispute."""
        apt_id = str(uuid.uuid4())
        target = make_pid()
        submitter = make_pid()

        review_records = make_review_records([target])
        sheets = [
            make_sheet(submitter, "uid_sub", [make_decl(target, "unknown")]),
        ]

        with patch('services.declarative_service._has_negative_tech_evidence', return_value=True):
            results = _run_small_group_analysis(apt_id, review_records, sheets)

        assert len(results) == 1
        r = results[0]
        assert r["auto_resolvable"] is False
        assert r["reason_if_not"] == "negative_tech_with_no_declarations"
        print("TEST 2 PASS: All unknown + neg tech → dispute")

    def test_3_unanimous_present_on_time(self):
        """Test 3: Unanimous present_on_time → on_time."""
        apt_id = str(uuid.uuid4())
        target = make_pid()
        sub1 = make_pid()
        sub2 = make_pid()

        review_records = make_review_records([target])
        sheets = [
            make_sheet(sub1, "uid1", [make_decl(target, "present_on_time")]),
            make_sheet(sub2, "uid2", [make_decl(target, "present_on_time")]),
        ]

        with patch('services.declarative_service._has_negative_tech_evidence', return_value=False):
            results = _run_small_group_analysis(apt_id, review_records, sheets)

        assert len(results) == 1
        r = results[0]
        assert r["auto_resolvable"] is True
        assert r["unanimous_status"] == "present_on_time"
        assert r["confidence_level"] == "MEDIUM"
        print("TEST 3 PASS: Unanimous present → on_time")

    def test_4_contradictory_declarations_dispute(self):
        """Test 4: One says present, one says absent → dispute."""
        apt_id = str(uuid.uuid4())
        target = make_pid()
        sub1 = make_pid()
        sub2 = make_pid()

        review_records = make_review_records([target])
        sheets = [
            make_sheet(sub1, "uid1", [make_decl(target, "present_on_time")]),
            make_sheet(sub2, "uid2", [make_decl(target, "absent")]),
        ]

        with patch('services.declarative_service._has_negative_tech_evidence', return_value=False):
            results = _run_small_group_analysis(apt_id, review_records, sheets)

        assert len(results) == 1
        r = results[0]
        assert r["auto_resolvable"] is False
        assert "disagreement" in r["reason_if_not"]
        print("TEST 4 PASS: Contradictory declarations → dispute")

    def test_4b_unanimous_absent_dispute(self):
        """Test 4b: All say absent in small group → dispute (not auto-resolve)."""
        apt_id = str(uuid.uuid4())
        target = make_pid()
        sub1 = make_pid()

        review_records = make_review_records([target])
        sheets = [
            make_sheet(sub1, "uid1", [make_decl(target, "absent")]),
        ]

        with patch('services.declarative_service._has_negative_tech_evidence', return_value=False):
            results = _run_small_group_analysis(apt_id, review_records, sheets)

        assert len(results) == 1
        r = results[0]
        assert r["auto_resolvable"] is False
        assert r["reason_if_not"] == "unanimous_absence"
        print("TEST 4b PASS: Unanimous absent in small group → dispute")


# ═══════════════════════════════════════════════════════════════════
# LARGE GROUP TESTS (>= 3 participants)
# ═══════════════════════════════════════════════════════════════════

class TestLargeGroupAnalysis:
    """Tests 5-10: Large group (>= 3 participants)."""

    def test_5_zero_expressed_no_neg_tech_waived(self):
        """Test 5: 0 expressed + no neg tech → waived."""
        apt_id = str(uuid.uuid4())
        target = make_pid()
        sub1, sub2, sub3 = make_pid(), make_pid(), make_pid()

        review_records = make_review_records([target])
        sheets = [
            make_sheet(sub1, "uid1", [make_decl(target, "unknown")]),
            make_sheet(sub2, "uid2", [make_decl(target, "unknown")]),
            make_sheet(sub3, "uid3", [make_decl(target, "unknown")]),
        ]

        with patch('services.declarative_service._has_negative_tech_evidence', return_value=False):
            results = _run_large_group_analysis(apt_id, review_records, sheets)

        assert len(results) == 1
        r = results[0]
        assert r["auto_resolvable"] is True
        assert r["unanimous_status"] == "waived"
        print("TEST 5 PASS: 0 expressed + no neg tech → waived")

    def test_6_single_positive_no_neg_tech_waived(self):
        """Test 6: 1 positive + no neg tech → waived (not on_time)."""
        apt_id = str(uuid.uuid4())
        target = make_pid()
        sub1, sub2, sub3 = make_pid(), make_pid(), make_pid()

        review_records = make_review_records([target])
        sheets = [
            make_sheet(sub1, "uid1", [make_decl(target, "present_on_time")]),
            make_sheet(sub2, "uid2", [make_decl(target, "unknown")]),
            make_sheet(sub3, "uid3", [make_decl(target, "unknown")]),
        ]

        with patch('services.declarative_service._has_negative_tech_evidence', return_value=False):
            results = _run_large_group_analysis(apt_id, review_records, sheets)

        assert len(results) == 1
        r = results[0]
        assert r["auto_resolvable"] is True
        assert r["unanimous_status"] == "waived"  # NOT on_time
        print("TEST 6 PASS: 1 positive + no neg tech → waived (not on_time)")

    def test_7_single_absent_dispute(self):
        """Test 7: 1 absent → dispute."""
        apt_id = str(uuid.uuid4())
        target = make_pid()
        sub1, sub2, sub3 = make_pid(), make_pid(), make_pid()

        review_records = make_review_records([target])
        sheets = [
            make_sheet(sub1, "uid1", [make_decl(target, "absent")]),
            make_sheet(sub2, "uid2", [make_decl(target, "unknown")]),
            make_sheet(sub3, "uid3", [make_decl(target, "unknown")]),
        ]

        with patch('services.declarative_service._has_negative_tech_evidence', return_value=False):
            results = _run_large_group_analysis(apt_id, review_records, sheets)

        assert len(results) == 1
        r = results[0]
        assert r["auto_resolvable"] is False
        assert r["reason_if_not"] == "single_negative_signal"
        print("TEST 7 PASS: 1 absent → dispute")

    def test_8_two_unanimous_present_on_time(self):
        """Test 8: >=2 unanimous present → on_time."""
        apt_id = str(uuid.uuid4())
        target = make_pid()
        sub1, sub2, sub3 = make_pid(), make_pid(), make_pid()

        review_records = make_review_records([target])
        sheets = [
            make_sheet(sub1, "uid1", [make_decl(target, "present_on_time")]),
            make_sheet(sub2, "uid2", [make_decl(target, "present_on_time")]),
            make_sheet(sub3, "uid3", [make_decl(target, "unknown")]),
        ]

        with patch('services.declarative_service._has_negative_tech_evidence', return_value=False):
            results = _run_large_group_analysis(apt_id, review_records, sheets)

        assert len(results) == 1
        r = results[0]
        assert r["auto_resolvable"] is True
        assert r["unanimous_status"] == "present_on_time"
        assert r["confidence_level"] == "MEDIUM"
        print("TEST 8 PASS: >=2 unanimous present → on_time")

    def test_9_two_unanimous_absent_existing_logic(self):
        """Test 9: >=2 unanimous absent → existing contradiction checks."""
        apt_id = str(uuid.uuid4())
        target = make_pid()
        sub1, sub2, sub3 = make_pid(), make_pid(), make_pid()

        review_records = make_review_records([target])
        sheets = [
            make_sheet(sub1, "uid1", [make_decl(target, "absent")]),
            make_sheet(sub2, "uid2", [make_decl(target, "absent")]),
            make_sheet(sub3, "uid3", [make_decl(target, "unknown")]),
        ]

        # Mock coherence as coherent and no contradiction → should auto-resolve as absent/no_show
        with patch('services.declarative_service._has_negative_tech_evidence', return_value=False), \
             patch('services.declarative_service._check_global_coherence', return_value={"coherent": True}), \
             patch('services.declarative_service._check_contradiction_signals', return_value={"contradiction": False}):
            results = _run_large_group_analysis(apt_id, review_records, sheets)

        assert len(results) == 1
        r = results[0]
        assert r["auto_resolvable"] is True
        assert r["unanimous_status"] == "absent"
        print("TEST 9 PASS: >=2 unanimous absent → existing logic (auto-resolve when no contradiction)")

    def test_9b_two_unanimous_absent_with_contradiction(self):
        """Test 9b: >=2 unanimous absent + contradiction → dispute."""
        apt_id = str(uuid.uuid4())
        target = make_pid()
        sub1, sub2, sub3 = make_pid(), make_pid(), make_pid()

        review_records = make_review_records([target])
        sheets = [
            make_sheet(sub1, "uid1", [make_decl(target, "absent")]),
            make_sheet(sub2, "uid2", [make_decl(target, "absent")]),
            make_sheet(sub3, "uid3", [make_decl(target, "unknown")]),
        ]

        with patch('services.declarative_service._has_negative_tech_evidence', return_value=False), \
             patch('services.declarative_service._check_global_coherence', return_value={"coherent": True}), \
             patch('services.declarative_service._check_contradiction_signals',
                   return_value={"contradiction": True, "reason": "contestant_contradiction"}):
            results = _run_large_group_analysis(apt_id, review_records, sheets)

        assert len(results) == 1
        r = results[0]
        assert r["auto_resolvable"] is False
        assert "contestant_contradiction" in r.get("reason_if_not", "")
        print("TEST 9b PASS: >=2 unanimous absent + contradiction → dispute")

    def test_10_disagreement_dispute(self):
        """Test 10: Disagreement → dispute."""
        apt_id = str(uuid.uuid4())
        target = make_pid()
        sub1, sub2, sub3 = make_pid(), make_pid(), make_pid()

        review_records = make_review_records([target])
        sheets = [
            make_sheet(sub1, "uid1", [make_decl(target, "present_on_time")]),
            make_sheet(sub2, "uid2", [make_decl(target, "absent")]),
            make_sheet(sub3, "uid3", [make_decl(target, "present_on_time")]),
        ]

        with patch('services.declarative_service._has_negative_tech_evidence', return_value=False):
            results = _run_large_group_analysis(apt_id, review_records, sheets)

        assert len(results) == 1
        r = results[0]
        assert r["auto_resolvable"] is False
        assert "disagreement" in r.get("reason_if_not", "")
        print("TEST 10 PASS: Disagreement → dispute")


# ═══════════════════════════════════════════════════════════════════
# AUTO-LITIGE TEST
# ═══════════════════════════════════════════════════════════════════

class TestAutoLitigeGuard:
    """Test 11: Auto-litige guard."""

    def test_11_auto_litige_blocked(self):
        """Test 11: target_user_id == organizer_user_id → no dispute, waived."""
        apt_id = str(uuid.uuid4())
        target_pid = make_pid()
        user_id = str(uuid.uuid4())

        # Mock DB calls
        with patch('services.declarative_service.db') as mock_db:
            # Existing dispute check
            mock_db.declarative_disputes.find_one.return_value = None

            # _get_user_id → returns user_id
            mock_db.participants.find_one.return_value = {"user_id": user_id, "email": "test@test.com"}

            # appointment → organizer_id == same user_id
            mock_db.appointments.find_one.return_value = {"organizer_id": user_id}

            # Mock update_one for attendance_records
            mock_db.attendance_records.update_one.return_value = None

            result = open_dispute(apt_id, target_pid, "test_reason")

        # Should return None (no dispute created)
        assert result is None

        # Should NOT have created a dispute
        mock_db.declarative_disputes.insert_one.assert_not_called()

        # Should have updated attendance record to waived
        update_call = mock_db.attendance_records.update_one.call_args
        assert update_call is not None
        update_set = update_call[0][1]["$set"]
        assert update_set["outcome"] == "waived"
        assert update_set["decision_source"] == "auto_no_self_dispute"
        assert update_set["decided_by"] == "engine_guard"
        print("TEST 11 PASS: Auto-litige blocked → waived, no dispute created")


# ═══════════════════════════════════════════════════════════════════
# _check_unanimity unit tests
# ═══════════════════════════════════════════════════════════════════

class TestCheckUnanimity:
    """Verify the updated _check_unanimity returns correct granular info."""

    def test_zero_expressed(self):
        target = make_pid()
        sheets = [
            make_sheet("sub1", "uid1", [make_decl(target, "unknown")]),
            make_sheet("sub2", "uid2", [make_decl(target, "unknown")]),
        ]
        result = _check_unanimity(target, sheets)
        assert result["reason"] == "no_expressed"
        assert result["expressed_count"] == 0
        print("UNANIMITY TEST: 0 expressed → no_expressed")

    def test_single_expressed(self):
        target = make_pid()
        sheets = [
            make_sheet("sub1", "uid1", [make_decl(target, "present_on_time")]),
            make_sheet("sub2", "uid2", [make_decl(target, "unknown")]),
        ]
        result = _check_unanimity(target, sheets)
        assert result["reason"] == "single_expressed"
        assert result["expressed_count"] == 1
        assert result["status"] == "present_on_time"
        print("UNANIMITY TEST: 1 expressed → single_expressed")

    def test_two_unanimous(self):
        target = make_pid()
        sheets = [
            make_sheet("sub1", "uid1", [make_decl(target, "present_on_time")]),
            make_sheet("sub2", "uid2", [make_decl(target, "present_on_time")]),
        ]
        result = _check_unanimity(target, sheets)
        assert result["unanimous"] is True
        assert result["status"] == "present_on_time"
        assert result["expressed_count"] == 2
        print("UNANIMITY TEST: 2 unanimous → unanimous=True")

    def test_two_disagreement(self):
        target = make_pid()
        sheets = [
            make_sheet("sub1", "uid1", [make_decl(target, "present_on_time")]),
            make_sheet("sub2", "uid2", [make_decl(target, "absent")]),
        ]
        result = _check_unanimity(target, sheets)
        assert result["unanimous"] is False
        assert result["reason"] == "tiers_disagreement"
        assert result["expressed_count"] == 2
        print("UNANIMITY TEST: 2 disagreement → tiers_disagreement")

    def test_excludes_self_declaration(self):
        """Tiers who submitted about themselves should be excluded."""
        target = make_pid()
        sheets = [
            # Target's own sheet (should be excluded)
            make_sheet(target, "uid_target", [make_decl(target, "present_on_time", is_self=True)]),
            make_sheet("sub1", "uid1", [make_decl(target, "unknown")]),
        ]
        result = _check_unanimity(target, sheets)
        assert result["reason"] == "no_expressed"
        assert result["expressed_count"] == 0
        print("UNANIMITY TEST: Self-declaration excluded from tiers count")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


# ═══════════════════════════════════════════════════════════════════
# V5.1 TESTS: GUARANTEED-ONLY DECLARATIVE PHASE (Tests 12-17)
# ═══════════════════════════════════════════════════════════════════

class TestGuaranteedOnlyPhase:
    """Tests 12-17: Only accepted_guaranteed participants enter declarative phase."""

    def _build_mock_db(self, appointment, participants_list, review_records):
        """Helper to build a mock DB for initialize_declarative_phase tests."""
        mock_db = MagicMock()

        # appointments.find_one returns appointment
        mock_db.appointments.find_one.return_value = appointment

        # participants.find returns all participants
        mock_db.participants.find.return_value = iter(participants_list)

        # attendance_records.find returns review records
        mock_db.attendance_records.find.return_value = iter(review_records)

        # participants.find_one: return participant by participant_id
        def find_one_participant(query, projection=None):
            pid = query.get("participant_id")
            for p in participants_list:
                if p.get("participant_id") == pid:
                    return p
            return None
        mock_db.participants.find_one.side_effect = find_one_participant

        # attendance_sheets.find_one returns None (no existing sheet)
        mock_db.attendance_sheets.find_one.return_value = None

        # Mock update_one and insert_one
        mock_db.appointments.update_one.return_value = MagicMock(modified_count=1)
        mock_db.attendance_records.update_one.return_value = MagicMock(modified_count=1)
        mock_db.attendance_sheets.insert_one.return_value = None

        return mock_db

    def test_12_all_guaranteed_normal_flow(self):
        """Test 12: All participants are accepted_guaranteed → normal flow, sheets created."""
        apt_id = str(uuid.uuid4())
        org_id = str(uuid.uuid4())
        pid1, pid2 = str(uuid.uuid4()), str(uuid.uuid4())
        uid1, uid2 = str(uuid.uuid4()), str(uuid.uuid4())

        appointment = {"appointment_id": apt_id, "organizer_id": org_id}
        participants = [
            {"participant_id": pid1, "user_id": uid1, "status": "accepted_guaranteed"},
            {"participant_id": pid2, "user_id": uid2, "status": "accepted_guaranteed"},
        ]
        review_records = [
            {"participant_id": pid1, "appointment_id": apt_id, "review_required": True, "outcome": "manual_review"},
            {"participant_id": pid2, "appointment_id": apt_id, "review_required": True, "outcome": "manual_review"},
        ]

        mock_db = self._build_mock_db(appointment, participants, review_records)

        with patch('services.declarative_service.db', mock_db):
            initialize_declarative_phase(apt_id)

        # Phase should be set to "collecting"
        phase_update_calls = mock_db.appointments.update_one.call_args_list
        phase_set = phase_update_calls[-1][0][1]["$set"]
        assert phase_set.get("declarative_phase") == "collecting"

        # No attendance_records should be auto-waived
        waive_calls = [
            c for c in mock_db.attendance_records.update_one.call_args_list
            if c[0][1].get("$set", {}).get("decision_source") == "non_guaranteed_auto_waived"
        ]
        assert len(waive_calls) == 0

        # Sheets should be created
        assert mock_db.attendance_sheets.insert_one.call_count >= 1
        print("TEST 12 PASS: All guaranteed → normal flow, sheets created")

    def test_13_mix_guaranteed_and_non_guaranteed(self):
        """Test 13: 2 guaranteed + 1 non-guaranteed → non-guaranteed waived, sheets for guaranteed only."""
        apt_id = str(uuid.uuid4())
        org_id = str(uuid.uuid4())
        pid1, pid2, pid3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        uid1, uid2, uid3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())

        appointment = {"appointment_id": apt_id, "organizer_id": org_id}
        participants = [
            {"participant_id": pid1, "user_id": uid1, "status": "accepted_guaranteed"},
            {"participant_id": pid2, "user_id": uid2, "status": "accepted_guaranteed"},
            {"participant_id": pid3, "user_id": uid3, "status": "accepted_pending_guarantee"},
        ]
        review_records = [
            {"participant_id": pid1, "appointment_id": apt_id, "review_required": True, "outcome": "manual_review"},
            {"participant_id": pid2, "appointment_id": apt_id, "review_required": True, "outcome": "manual_review"},
            {"participant_id": pid3, "appointment_id": apt_id, "review_required": True, "outcome": "manual_review"},
        ]

        mock_db = self._build_mock_db(appointment, participants, review_records)

        with patch('services.declarative_service.db', mock_db):
            initialize_declarative_phase(apt_id)

        # pid3 (non-guaranteed) should be auto-waived
        waive_calls = [
            c for c in mock_db.attendance_records.update_one.call_args_list
            if c[0][1].get("$set", {}).get("decision_source") == "non_guaranteed_auto_waived"
        ]
        assert len(waive_calls) == 1
        waived_filter = waive_calls[0][0][0]
        assert waived_filter["participant_id"] == pid3

        # Phase should be collecting (2 guaranteed remain)
        phase_update_calls = mock_db.appointments.update_one.call_args_list
        phase_set = phase_update_calls[-1][0][1]["$set"]
        assert phase_set.get("declarative_phase") == "collecting"

        # Sheets should be created (for guaranteed participants only)
        assert mock_db.attendance_sheets.insert_one.call_count >= 1
        print("TEST 13 PASS: Mix guaranteed/non-guaranteed → non-guaranteed waived, sheets for guaranteed")

    def test_14_one_guaranteed_rest_non_guaranteed_not_needed(self):
        """Test 14: 1 guaranteed + 2 non-guaranteed → all non-guaranteed waived, phase = not_needed."""
        apt_id = str(uuid.uuid4())
        org_id = str(uuid.uuid4())
        pid1, pid2, pid3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        uid1, uid2, uid3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())

        appointment = {"appointment_id": apt_id, "organizer_id": org_id}
        participants = [
            {"participant_id": pid1, "user_id": uid1, "status": "accepted_guaranteed"},
            {"participant_id": pid2, "user_id": uid2, "status": "accepted_pending_guarantee"},
            {"participant_id": pid3, "user_id": uid3, "status": "accepted"},
        ]
        review_records = [
            {"participant_id": pid1, "appointment_id": apt_id, "review_required": True, "outcome": "manual_review"},
            {"participant_id": pid2, "appointment_id": apt_id, "review_required": True, "outcome": "manual_review"},
            {"participant_id": pid3, "appointment_id": apt_id, "review_required": True, "outcome": "manual_review"},
        ]

        mock_db = self._build_mock_db(appointment, participants, review_records)

        with patch('services.declarative_service.db', mock_db):
            initialize_declarative_phase(apt_id)

        # pid2 and pid3 should be auto-waived
        waive_calls = [
            c for c in mock_db.attendance_records.update_one.call_args_list
            if c[0][1].get("$set", {}).get("decision_source") == "non_guaranteed_auto_waived"
        ]
        assert len(waive_calls) == 2

        # Phase should be not_needed (only 1 guaranteed)
        phase_update_calls = mock_db.appointments.update_one.call_args_list
        phase_set = phase_update_calls[-1][0][1]["$set"]
        assert phase_set.get("declarative_phase") == "not_needed"

        # No sheets should be created
        assert mock_db.attendance_sheets.insert_one.call_count == 0
        print("TEST 14 PASS: 1 guaranteed + 2 non-guaranteed → not_needed, no sheets")

    def test_15_zero_guaranteed_all_waived_not_needed(self):
        """Test 15: 0 guaranteed (all non-guaranteed) → all waived, phase = not_needed."""
        apt_id = str(uuid.uuid4())
        org_id = str(uuid.uuid4())
        pid1, pid2 = str(uuid.uuid4()), str(uuid.uuid4())
        uid1, uid2 = str(uuid.uuid4()), str(uuid.uuid4())

        appointment = {"appointment_id": apt_id, "organizer_id": org_id}
        participants = [
            {"participant_id": pid1, "user_id": uid1, "status": "accepted"},
            {"participant_id": pid2, "user_id": uid2, "status": "accepted_pending_guarantee"},
        ]
        review_records = [
            {"participant_id": pid1, "appointment_id": apt_id, "review_required": True, "outcome": "manual_review"},
            {"participant_id": pid2, "appointment_id": apt_id, "review_required": True, "outcome": "manual_review"},
        ]

        mock_db = self._build_mock_db(appointment, participants, review_records)

        with patch('services.declarative_service.db', mock_db):
            initialize_declarative_phase(apt_id)

        # Both should be auto-waived
        waive_calls = [
            c for c in mock_db.attendance_records.update_one.call_args_list
            if c[0][1].get("$set", {}).get("decision_source") == "non_guaranteed_auto_waived"
        ]
        assert len(waive_calls) == 2

        # Phase should be not_needed
        phase_update_calls = mock_db.appointments.update_one.call_args_list
        phase_set = phase_update_calls[-1][0][1]["$set"]
        assert phase_set.get("declarative_phase") == "not_needed"

        # No sheets created
        assert mock_db.attendance_sheets.insert_one.call_count == 0
        print("TEST 15 PASS: 0 guaranteed → all waived, not_needed, no sheets")

    def test_16_waived_outcome_fields_correct(self):
        """Test 16: Verify the exact fields set on auto-waived attendance records."""
        apt_id = str(uuid.uuid4())
        org_id = str(uuid.uuid4())
        pid1, pid2 = str(uuid.uuid4()), str(uuid.uuid4())
        uid1, uid2 = str(uuid.uuid4()), str(uuid.uuid4())

        appointment = {"appointment_id": apt_id, "organizer_id": org_id}
        participants = [
            {"participant_id": pid1, "user_id": uid1, "status": "accepted_guaranteed"},
            {"participant_id": pid2, "user_id": uid2, "status": "accepted_pending_guarantee"},
        ]
        review_records = [
            {"participant_id": pid1, "appointment_id": apt_id, "review_required": True, "outcome": "manual_review"},
            {"participant_id": pid2, "appointment_id": apt_id, "review_required": True, "outcome": "manual_review"},
        ]

        mock_db = self._build_mock_db(appointment, participants, review_records)

        with patch('services.declarative_service.db', mock_db):
            initialize_declarative_phase(apt_id)

        # Find the waive call for pid2
        waive_calls = [
            c for c in mock_db.attendance_records.update_one.call_args_list
            if c[0][1].get("$set", {}).get("decision_source") == "non_guaranteed_auto_waived"
        ]
        assert len(waive_calls) == 1
        waived_set = waive_calls[0][0][1]["$set"]

        # Verify all required fields
        assert waived_set["outcome"] == "waived"
        assert waived_set["review_required"] is False
        assert waived_set["decision_source"] == "non_guaranteed_auto_waived"
        assert waived_set["confidence_level"] == "HIGH"
        assert waived_set["decided_by"] == "engine_guard"
        assert "decided_at" in waived_set
        print("TEST 16 PASS: Auto-waived fields correct (outcome, review_required, decision_source, etc.)")

    def test_17_non_guaranteed_excluded_from_sheet_creators(self):
        """Test 17: Auto-waived participant should NOT have a sheet created for them."""
        apt_id = str(uuid.uuid4())
        org_id = str(uuid.uuid4())
        pid1, pid2, pid3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        uid1, uid2, uid3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())

        appointment = {"appointment_id": apt_id, "organizer_id": org_id}
        participants = [
            {"participant_id": pid1, "user_id": uid1, "status": "accepted_guaranteed"},
            {"participant_id": pid2, "user_id": uid2, "status": "accepted_guaranteed"},
            {"participant_id": pid3, "user_id": uid3, "status": "accepted_pending_guarantee"},
        ]
        review_records = [
            {"participant_id": pid1, "appointment_id": apt_id, "review_required": True, "outcome": "manual_review"},
            {"participant_id": pid2, "appointment_id": apt_id, "review_required": True, "outcome": "manual_review"},
            {"participant_id": pid3, "appointment_id": apt_id, "review_required": True, "outcome": "manual_review"},
        ]

        mock_db = self._build_mock_db(appointment, participants, review_records)

        with patch('services.declarative_service.db', mock_db):
            initialize_declarative_phase(apt_id)

        # Check that sheets were created only for uid1 and uid2, NOT uid3
        created_sheets = mock_db.attendance_sheets.insert_one.call_args_list
        for sheet_call in created_sheets:
            sheet_data = sheet_call[0][0]
            assert sheet_data["submitted_by_user_id"] != uid3, \
                f"Sheet was created for non-guaranteed user {uid3}"
            # Also verify that pid3 is NOT a target in any sheet
            for decl in sheet_data.get("declarations", []):
                assert decl["target_participant_id"] != pid3, \
                    f"Non-guaranteed participant {pid3} appears as target in sheet"

        print("TEST 17 PASS: Non-guaranteed participant excluded from sheets (both as creator and target)")
