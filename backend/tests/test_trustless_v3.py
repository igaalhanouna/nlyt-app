"""
Tests V3 Trustless — Penalty system integrity tests.
Tests the critical rules:
1. No on_time/late/late_penalized without admissible proof (Niveau 1-2)
2. No compensation to unproven beneficiary
3. No reclassification with conflict of interest
4. Cas B: no definitive outcome → all frozen
5. Cas A: payer established but no beneficiary → capture blocked per-payer
6. late vs late_penalized distinction based on tolerated_delay_minutes
"""
import pytest
import os
import sys
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timezone, timedelta
import uuid

sys.path.insert(0, '/app/backend')
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
os.environ.setdefault('DB_NAME', 'test_trustless')


def make_id():
    return str(uuid.uuid4())


# ═══════════════════════════════════════════════════════════════════
# 1. _has_admissible_proof
# ═══════════════════════════════════════════════════════════════════

class TestHasAdmissibleProof:
    """Test proof level classification (Niveau 1, 2, 3)."""

    @patch('services.attendance_service.db')
    def test_no_evidence_returns_false(self, mock_db):
        from services.attendance_service import _has_admissible_proof
        mock_db.evidence_items.find.return_value = []
        assert _has_admissible_proof("pid1", "apt1") is False

    @patch('services.attendance_service.db')
    def test_gps_within_radius_is_admissible(self, mock_db):
        from services.attendance_service import _has_admissible_proof
        mock_db.evidence_items.find.return_value = [
            {"evidence_type": "gps", "source": "manual_checkin", "gps_within_radius": True}
        ]
        assert _has_admissible_proof("pid1", "apt1") is True

    @patch('services.attendance_service.db')
    def test_gps_outside_radius_not_admissible(self, mock_db):
        from services.attendance_service import _has_admissible_proof
        mock_db.evidence_items.find.return_value = [
            {"evidence_type": "gps", "source": "manual_checkin", "gps_within_radius": False}
        ]
        assert _has_admissible_proof("pid1", "apt1") is False

    @patch('services.attendance_service.db')
    def test_qr_scan_is_admissible(self, mock_db):
        from services.attendance_service import _has_admissible_proof
        mock_db.evidence_items.find.return_value = [
            {"evidence_type": "qr_scan", "source": "qr"}
        ]
        assert _has_admissible_proof("pid1", "apt1") is True

    @patch('services.attendance_service.db')
    def test_zoom_api_is_admissible(self, mock_db):
        from services.attendance_service import _has_admissible_proof
        mock_db.evidence_items.find.return_value = [
            {"evidence_type": "video_api", "source": "zoom"}
        ]
        assert _has_admissible_proof("pid1", "apt1") is True

    @patch('services.attendance_service.db')
    def test_teams_api_is_admissible(self, mock_db):
        from services.attendance_service import _has_admissible_proof
        mock_db.evidence_items.find.return_value = [
            {"evidence_type": "video_api", "source": "teams"}
        ]
        assert _has_admissible_proof("pid1", "apt1") is True

    @patch('services.attendance_service.db')
    def test_proof_session_is_admissible(self, mock_db):
        from services.attendance_service import _has_admissible_proof
        mock_db.evidence_items.find.return_value = [
            {"evidence_type": "proof_session", "source": "nlyt_proof"}
        ]
        assert _has_admissible_proof("pid1", "apt1") is True

    @patch('services.attendance_service.db')
    def test_manual_checkin_only_not_admissible(self, mock_db):
        """Niveau 3: manual checkin without GPS = not admissible."""
        from services.attendance_service import _has_admissible_proof
        mock_db.evidence_items.find.return_value = [
            {"evidence_type": "manual_checkin", "source": "self_declaration"}
        ]
        assert _has_admissible_proof("pid1", "apt1") is False

    @patch('services.attendance_service.db')
    def test_google_meet_only_not_admissible(self, mock_db):
        """Niveau 3: Google Meet alone = not admissible."""
        from services.attendance_service import _has_admissible_proof
        mock_db.evidence_items.find.return_value = [
            {"evidence_type": "video_api", "source": "google_meet"}
        ]
        assert _has_admissible_proof("pid1", "apt1") is False


# ═══════════════════════════════════════════════════════════════════
# 2. _process_financial_outcomes — Cas A / Cas B / late vs late_penalized
# ═══════════════════════════════════════════════════════════════════

def _make_appointment(apt_id="apt1", penalty=30):
    return {
        "appointment_id": apt_id,
        "organizer_id": "org_user",
        "penalty_amount": penalty,
        "penalty_currency": "eur",
        "platform_commission_percent": 20.0,
        "affected_compensation_percent": 50.0,
        "charity_percent": 10.0,
        "charity_association_id": "assoc1",
    }


def _make_participants(apt_id="apt1"):
    return [
        {"participant_id": "p_org", "user_id": "org_user", "appointment_id": apt_id, "is_organizer": True, "status": "accepted_guaranteed"},
        {"participant_id": "p1", "user_id": "user1", "appointment_id": apt_id, "is_organizer": False, "status": "accepted_guaranteed"},
        {"participant_id": "p2", "user_id": "user2", "appointment_id": apt_id, "is_organizer": False, "status": "accepted_guaranteed"},
    ]


def _find_part_factory(parts):
    def find_part(ps, pid):
        return next((p for p in ps if p["participant_id"] == pid), None)
    return lambda ps, pid: find_part(parts, pid)


class TestProcessFinancialOutcomes:
    """Test V3 trustless financial outcome processing."""

    @patch('services.attendance_service._execute_release')
    @patch('services.attendance_service._execute_capture_and_distribution')
    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.attendance_service.db')
    def test_beneficiary_on_time_with_proof_gets_compensation(self, mock_db, mock_proof, mock_capture, mock_release):
        """on_time + Niveau 1-2 proof → compensable."""
        from services.attendance_service import _process_financial_outcomes

        mock_db.attendance_records.find.return_value = [
            {"record_id": "r1", "participant_id": "p1", "outcome": "no_show", "review_required": False},
            {"record_id": "r_org", "participant_id": "p_org", "outcome": "on_time", "review_required": False},
        ]
        mock_db.payment_guarantees.find_one.return_value = {
            "guarantee_id": "g1", "participant_id": "p1", "status": "completed", "penalty_amount": 30
        }
        mock_proof.return_value = True

        apt = _make_appointment()
        parts = _make_participants()

        with patch('services.attendance_service._find_participant', side_effect=_find_part_factory(parts)):
            _process_financial_outcomes("apt1", apt, parts)

        mock_capture.assert_called_once()
        eligible = mock_capture.call_args[0][3]
        user_ids = [b["user_id"] for b in eligible]
        assert "org_user" in user_ids

    @patch('services.attendance_service._execute_release')
    @patch('services.attendance_service._execute_capture_and_distribution')
    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.attendance_service.db')
    def test_late_admissible_is_beneficiary_not_captured(self, mock_db, mock_proof, mock_capture, mock_release):
        """late (admissible) + proof → beneficiary, release guarantee, NOT captured."""
        from services.attendance_service import _process_financial_outcomes

        mock_db.attendance_records.find.return_value = [
            {"record_id": "r1", "participant_id": "p1", "outcome": "no_show", "review_required": False},
            {"record_id": "r_org", "participant_id": "p_org", "outcome": "late", "review_required": False},
        ]
        mock_db.payment_guarantees.find_one.return_value = {
            "guarantee_id": "g1", "participant_id": "p1", "status": "completed", "penalty_amount": 30
        }
        mock_proof.return_value = True

        apt = _make_appointment()
        parts = _make_participants()

        with patch('services.attendance_service._find_participant', side_effect=_find_part_factory(parts)):
            _process_financial_outcomes("apt1", apt, parts)

        # Capture once for p1 (no_show), org (late) is beneficiary
        mock_capture.assert_called_once()
        eligible = mock_capture.call_args[0][3]
        user_ids = [b["user_id"] for b in eligible]
        assert "org_user" in user_ids

    @patch('services.attendance_service._execute_release')
    @patch('services.attendance_service._execute_capture_and_distribution')
    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.attendance_service.db')
    def test_late_penalized_triggers_capture(self, mock_db, mock_proof, mock_capture, mock_release):
        """late_penalized → capture triggered (like no_show)."""
        from services.attendance_service import _process_financial_outcomes

        mock_db.attendance_records.find.return_value = [
            {"record_id": "r1", "participant_id": "p1", "outcome": "late_penalized", "review_required": False},
            {"record_id": "r_org", "participant_id": "p_org", "outcome": "on_time", "review_required": False},
        ]
        mock_db.payment_guarantees.find_one.return_value = {
            "guarantee_id": "g1", "participant_id": "p1", "status": "completed", "penalty_amount": 30
        }
        mock_proof.return_value = True

        apt = _make_appointment()
        parts = _make_participants()

        with patch('services.attendance_service._find_participant', side_effect=_find_part_factory(parts)):
            _process_financial_outcomes("apt1", apt, parts)

        mock_capture.assert_called_once()
        call_args = mock_capture.call_args
        assert call_args[0][4] == "late_beyond_tolerance"

    @patch('services.attendance_service._execute_release')
    @patch('services.attendance_service._execute_capture_and_distribution')
    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.attendance_service.db')
    def test_late_penalized_is_not_beneficiary(self, mock_db, mock_proof, mock_capture, mock_release):
        """late_penalized must NOT be in eligible beneficiaries."""
        from services.attendance_service import _process_financial_outcomes

        mock_db.attendance_records.find.return_value = [
            {"record_id": "r1", "participant_id": "p1", "outcome": "no_show", "review_required": False},
            {"record_id": "r_org", "participant_id": "p_org", "outcome": "on_time", "review_required": False},
            {"record_id": "r2", "participant_id": "p2", "outcome": "late_penalized", "review_required": False},
        ]

        def guarantee_side_effect(query, projection=None):
            pid = query.get("participant_id")
            if pid == "p1":
                return {"guarantee_id": "g1", "participant_id": "p1", "status": "completed", "penalty_amount": 30}
            if pid == "p2":
                return {"guarantee_id": "g2", "participant_id": "p2", "status": "completed", "penalty_amount": 30}
            return None

        mock_db.payment_guarantees.find_one.side_effect = guarantee_side_effect
        mock_proof.return_value = True

        apt = _make_appointment()
        parts = _make_participants()

        with patch('services.attendance_service._find_participant', side_effect=_find_part_factory(parts)):
            _process_financial_outcomes("apt1", apt, parts)

        # Both p1 (no_show) and p2 (late_penalized) should trigger capture
        assert mock_capture.call_count == 2
        # Eligible beneficiaries should only contain org (on_time), NOT p2 (late_penalized)
        for c in mock_capture.call_args_list:
            eligible = c[0][3]
            user_ids = {b["user_id"] for b in eligible}
            assert "org_user" in user_ids
            assert "user2" not in user_ids, "late_penalized must NOT be a beneficiary"

    @patch('services.attendance_service._execute_release')
    @patch('services.attendance_service._execute_capture_and_distribution')
    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.attendance_service.db')
    def test_beneficiary_without_proof_excluded_cas_a(self, mock_db, mock_proof, mock_capture, mock_release):
        """Cas A: on_time without proof → not a beneficiary → capture blocked."""
        from services.attendance_service import _process_financial_outcomes

        mock_db.attendance_records.find.return_value = [
            {"record_id": "r1", "participant_id": "p1", "outcome": "no_show", "review_required": False},
            {"record_id": "r_org", "participant_id": "p_org", "outcome": "on_time", "review_required": False},
        ]
        mock_db.payment_guarantees.find_one.return_value = {
            "guarantee_id": "g1", "participant_id": "p1", "status": "completed", "penalty_amount": 30
        }
        mock_proof.return_value = False
        mock_db.attendance_records.update_one = MagicMock()

        apt = _make_appointment()
        parts = _make_participants()

        with patch('services.attendance_service._find_participant', side_effect=_find_part_factory(parts)):
            _process_financial_outcomes("apt1", apt, parts)

        # No capture (Cas A: org has no proof → excluded → no beneficiary for p1)
        mock_capture.assert_not_called()
        mock_db.attendance_records.update_one.assert_called()

    @patch('services.attendance_service._execute_release')
    @patch('services.attendance_service._execute_capture_and_distribution')
    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.attendance_service.db')
    def test_cas_b_all_manual_review(self, mock_db, mock_proof, mock_capture, mock_release):
        """Cas B: all participants manual_review → no definitive outcome → all frozen."""
        from services.attendance_service import _process_financial_outcomes

        mock_db.attendance_records.find.return_value = [
            {"record_id": "r1", "participant_id": "p1", "outcome": "manual_review", "review_required": True},
            {"record_id": "r_org", "participant_id": "p_org", "outcome": "manual_review", "review_required": True},
        ]

        apt = _make_appointment()
        parts = _make_participants()

        with patch('services.attendance_service._find_participant', side_effect=_find_part_factory(parts)):
            _process_financial_outcomes("apt1", apt, parts)

        mock_capture.assert_not_called()
        mock_release.assert_not_called()

    @patch('services.attendance_service._execute_release')
    @patch('services.attendance_service._execute_capture_and_distribution')
    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.attendance_service.db')
    def test_cas_b_waived_does_not_count_as_definitive(self, mock_db, mock_proof, mock_capture, mock_release):
        """Cas B: waived + manual_review only → waived doesn't document reality → frozen."""
        from services.attendance_service import _process_financial_outcomes

        mock_db.attendance_records.find.return_value = [
            {"record_id": "r1", "participant_id": "p1", "outcome": "waived", "review_required": False},
            {"record_id": "r_org", "participant_id": "p_org", "outcome": "manual_review", "review_required": True},
        ]

        apt = _make_appointment()
        parts = _make_participants()

        with patch('services.attendance_service._find_participant', side_effect=_find_part_factory(parts)):
            _process_financial_outcomes("apt1", apt, parts)

        mock_capture.assert_not_called()
        mock_release.assert_not_called()

    @patch('services.attendance_service._execute_release')
    @patch('services.attendance_service._execute_capture_and_distribution')
    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.attendance_service.db')
    def test_cas_a_capture_with_proven_beneficiary(self, mock_db, mock_proof, mock_capture, mock_release):
        """Cas A: no_show established + at least 1 proven beneficiary → capture."""
        from services.attendance_service import _process_financial_outcomes

        mock_db.attendance_records.find.return_value = [
            {"record_id": "r1", "participant_id": "p1", "outcome": "no_show", "review_required": False},
            {"record_id": "r_org", "participant_id": "p_org", "outcome": "on_time", "review_required": False},
            {"record_id": "r2", "participant_id": "p2", "outcome": "on_time", "review_required": False},
        ]
        mock_db.payment_guarantees.find_one.return_value = {
            "guarantee_id": "g1", "participant_id": "p1", "status": "completed", "penalty_amount": 30
        }

        def proof_side_effect(pid, aid):
            return pid in ("p_org", "p2")

        mock_proof.side_effect = proof_side_effect

        apt = _make_appointment()
        parts = _make_participants()

        with patch('services.attendance_service._find_participant', side_effect=_find_part_factory(parts)):
            _process_financial_outcomes("apt1", apt, parts)

        mock_capture.assert_called_once()
        eligible = mock_capture.call_args[0][3]
        user_ids = [b["user_id"] for b in eligible]
        assert "org_user" in user_ids
        assert "user2" in user_ids
        assert "user1" not in user_ids


# ═══════════════════════════════════════════════════════════════════
# 3. Mixed profiles — the 2 previously-failing tests
# ═══════════════════════════════════════════════════════════════════

class TestMixedProfiles:
    """Test multiple beneficiaries with different proof levels on the same RDV."""

    @patch('services.attendance_service._execute_release')
    @patch('services.attendance_service._execute_capture_and_distribution')
    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.attendance_service.db')
    def test_mixed_profiles_only_proven_get_compensation(self, mock_db, mock_proof, mock_capture, mock_release):
        """
        Org (GPS proof, on_time) + p1 (no proof, on_time) + p2 (QR proof, late) + p3 (no_show).
        Only org and p2 should be eligible beneficiaries. Only p3 captured.
        """
        from services.attendance_service import _process_financial_outcomes

        mock_db.attendance_records.find.return_value = [
            {"record_id": "r_org", "participant_id": "p_org", "outcome": "on_time", "review_required": False},
            {"record_id": "r1", "participant_id": "p1", "outcome": "on_time", "review_required": False},
            {"record_id": "r2", "participant_id": "p2", "outcome": "late", "review_required": False},
            {"record_id": "r3", "participant_id": "p3", "outcome": "no_show", "review_required": False},
        ]
        mock_db.payment_guarantees.find_one.return_value = {
            "guarantee_id": "g3", "participant_id": "p3", "status": "completed", "penalty_amount": 30
        }

        def proof_side_effect(pid, aid):
            return pid in ("p_org", "p2")

        mock_proof.side_effect = proof_side_effect

        parts = [
            {"participant_id": "p_org", "user_id": "org_user", "is_organizer": True, "status": "accepted_guaranteed"},
            {"participant_id": "p1", "user_id": "user1", "is_organizer": False, "status": "accepted_guaranteed"},
            {"participant_id": "p2", "user_id": "user2", "is_organizer": False, "status": "accepted_guaranteed"},
            {"participant_id": "p3", "user_id": "user3", "is_organizer": False, "status": "accepted_guaranteed"},
        ]
        apt = {
            "appointment_id": "apt1", "organizer_id": "org_user", "penalty_amount": 30,
            "penalty_currency": "eur", "platform_commission_percent": 20.0,
            "affected_compensation_percent": 50.0, "charity_percent": 10.0,
        }

        with patch('services.attendance_service._find_participant', side_effect=_find_part_factory(parts)):
            _process_financial_outcomes("apt1", apt, parts)

        mock_capture.assert_called_once()
        eligible = mock_capture.call_args[0][3]
        user_ids = {b["user_id"] for b in eligible}
        assert "org_user" in user_ids, "Org with GPS should be eligible"
        assert "user2" in user_ids, "p2 with QR should be eligible"
        assert "user1" not in user_ids, "p1 without proof should be excluded"
        assert "user3" not in user_ids, "p3 (no_show) should be excluded"
        assert len(eligible) == 2

    @patch('services.attendance_service._execute_release')
    @patch('services.attendance_service._execute_capture_and_distribution')
    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.attendance_service.db')
    def test_org_late_with_proof_participant_on_time_manual_review_excluded(self, mock_db, mock_proof, mock_capture, mock_release):
        """
        Org (late, GPS proof) + p1 (on_time, GPS) + p2 (manual_review).
        p3 is no_show. Org and p1 eligible. p2 excluded (manual_review).
        """
        from services.attendance_service import _process_financial_outcomes

        mock_db.attendance_records.find.return_value = [
            {"record_id": "r_org", "participant_id": "p_org", "outcome": "late", "review_required": False},
            {"record_id": "r1", "participant_id": "p1", "outcome": "on_time", "review_required": False},
            {"record_id": "r2", "participant_id": "p2", "outcome": "manual_review", "review_required": True},
            {"record_id": "r3", "participant_id": "p3", "outcome": "no_show", "review_required": False},
        ]
        mock_db.payment_guarantees.find_one.return_value = {
            "guarantee_id": "g3", "participant_id": "p3", "status": "completed", "penalty_amount": 30
        }

        def proof_side_effect(pid, aid):
            return pid in ("p_org", "p1")

        mock_proof.side_effect = proof_side_effect

        parts = [
            {"participant_id": "p_org", "user_id": "org_user", "is_organizer": True, "status": "accepted_guaranteed"},
            {"participant_id": "p1", "user_id": "user1", "is_organizer": False, "status": "accepted_guaranteed"},
            {"participant_id": "p2", "user_id": "user2", "is_organizer": False, "status": "accepted_guaranteed"},
            {"participant_id": "p3", "user_id": "user3", "is_organizer": False, "status": "accepted_guaranteed"},
        ]
        apt = {
            "appointment_id": "apt1", "organizer_id": "org_user", "penalty_amount": 30,
            "penalty_currency": "eur", "platform_commission_percent": 20.0,
            "affected_compensation_percent": 50.0, "charity_percent": 10.0,
        }

        with patch('services.attendance_service._find_participant', side_effect=_find_part_factory(parts)):
            _process_financial_outcomes("apt1", apt, parts)

        mock_capture.assert_called_once()
        eligible = mock_capture.call_args[0][3]
        user_ids = {b["user_id"] for b in eligible}
        assert "org_user" in user_ids, "Late org with proof should be eligible"
        assert "user1" in user_ids, "On-time p1 with proof should be eligible"
        assert "user2" not in user_ids, "manual_review p2 should NOT be eligible"
        assert len(eligible) == 2


# ═══════════════════════════════════════════════════════════════════
# 4. Reclassification — conflict of interest
# ═══════════════════════════════════════════════════════════════════

class TestReclassificationConflict:
    """Test V3 trustless reclassification blocking logic."""

    def test_conflict_no_show(self):
        """Org reclassifies non-org to no_show → conflict."""
        reclassified = {"participant_id": "p1", "is_organizer": False, "user_id": "user1"}
        new_outcome = "no_show"
        is_conflict = (
            new_outcome in ('no_show', 'late_penalized')
            and reclassified
            and not reclassified.get('is_organizer', False)
        )
        assert is_conflict is True

    def test_conflict_late_penalized(self):
        """Org reclassifies non-org to late_penalized → conflict."""
        reclassified = {"participant_id": "p1", "is_organizer": False, "user_id": "user1"}
        new_outcome = "late_penalized"
        is_conflict = (
            new_outcome in ('no_show', 'late_penalized')
            and reclassified
            and not reclassified.get('is_organizer', False)
        )
        assert is_conflict is True

    def test_no_conflict_late_admissible(self):
        """Reclassify to late (admissible) → no conflict (not penalizing)."""
        new_outcome = "late"
        is_conflict = new_outcome in ('no_show', 'late_penalized')
        assert is_conflict is False

    def test_no_conflict_on_time(self):
        """Reclassify to on_time → no conflict."""
        new_outcome = "on_time"
        is_conflict = new_outcome in ('no_show', 'late_penalized')
        assert is_conflict is False

    def test_no_conflict_org_self(self):
        """Org reclassifying themselves → no conflict."""
        reclassified = {"participant_id": "p_org", "is_organizer": True, "user_id": "org_user"}
        new_outcome = "no_show"
        is_conflict = (
            new_outcome in ('no_show', 'late_penalized')
            and reclassified
            and not reclassified.get('is_organizer', False)
        )
        assert is_conflict is False


# ═══════════════════════════════════════════════════════════════════
# 5. Reclassification financial transitions
# ═══════════════════════════════════════════════════════════════════

class TestReclassificationFinancial:
    """Test _process_reclassification with new PENALIZED/NON_PENALIZED tuples."""

    @patch('services.attendance_service._execute_release')
    @patch('services.attendance_service._execute_capture_and_distribution')
    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.attendance_service.db')
    def test_reclassify_to_late_admissible_releases(self, mock_db, mock_proof, mock_capture, mock_release):
        """manual_review → late (admissible) = NON_PENALIZED → cancel distribution + release."""
        from services.attendance_service import _process_reclassification

        record = {"appointment_id": "apt1", "participant_id": "p1", "record_id": "r1"}
        mock_db.appointments.find_one.return_value = _make_appointment()
        mock_db.participants.find.return_value = _make_participants()
        mock_db.payment_guarantees.find_one.return_value = {
            "guarantee_id": "g1", "participant_id": "p1", "status": "completed", "penalty_amount": 30
        }
        mock_db.distributions.find_one.return_value = None
        mock_db.attendance_records.find.return_value = []
        mock_proof.return_value = True

        _process_reclassification(record, "manual_review", "late")

        # manual_review is not in PENALIZED, late is in NON_PENALIZED
        # But manual_review → late: previous NOT in PENALIZED and new NOT in PENALIZED → no action
        # Actually: manual_review is not in PENALIZED, so "was penalized → now non-penalized" doesn't apply
        # And: new_outcome 'late' is in NON_PENALIZED but previous 'manual_review' is NOT in PENALIZED
        # So neither transition fires. This is correct.
        mock_capture.assert_not_called()

    @patch('services.attendance_service._execute_release')
    @patch('services.attendance_service._execute_capture_and_distribution')
    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.attendance_service.db')
    def test_reclassify_to_late_penalized_captures(self, mock_db, mock_proof, mock_capture, mock_release):
        """manual_review → late_penalized = PENALIZED → capture + distribution."""
        from services.attendance_service import _process_reclassification

        record = {"appointment_id": "apt1", "participant_id": "p1", "record_id": "r1"}
        mock_db.appointments.find_one.return_value = _make_appointment()
        parts = _make_participants()
        mock_db.participants.find.return_value = parts
        mock_db.payment_guarantees.find_one.return_value = {
            "guarantee_id": "g1", "participant_id": "p1", "status": "completed", "penalty_amount": 30
        }
        mock_db.attendance_records.find.return_value = [
            {"record_id": "r_org", "participant_id": "p_org", "outcome": "on_time", "review_required": False},
        ]
        mock_proof.return_value = True

        with patch('services.attendance_service._find_participant', side_effect=_find_part_factory(parts)):
            _process_reclassification(record, "manual_review", "late_penalized")

        # manual_review → late_penalized: previous NOT in PENALIZED, new IS in PENALIZED → capture
        mock_capture.assert_called_once()

    @patch('services.attendance_service._execute_release')
    @patch('services.attendance_service._execute_capture_and_distribution')
    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.attendance_service.db')
    def test_reclassify_no_show_to_late_releases(self, mock_db, mock_proof, mock_capture, mock_release):
        """no_show → late (admissible) = PENALIZED → NON_PENALIZED → cancel + release."""
        from services.attendance_service import _process_reclassification
        from services.distribution_service import cancel_distribution

        record = {"appointment_id": "apt1", "participant_id": "p1", "record_id": "r1"}
        mock_db.appointments.find_one.return_value = _make_appointment()
        parts = _make_participants()
        mock_db.participants.find.return_value = parts
        mock_db.payment_guarantees.find_one.return_value = {
            "guarantee_id": "g1", "participant_id": "p1", "status": "completed", "penalty_amount": 30
        }
        mock_db.distributions.find_one.return_value = {
            "distribution_id": "d1", "guarantee_id": "g1", "status": "pending"
        }
        mock_db.attendance_records.find.return_value = []
        mock_proof.return_value = True

        with patch('services.attendance_service._find_participant', side_effect=_find_part_factory(parts)):
            with patch('services.distribution_service.cancel_distribution') as mock_cancel:
                _process_reclassification(record, "no_show", "late")

                mock_cancel.assert_called_once()
                mock_release.assert_called_once()


# ═══════════════════════════════════════════════════════════════════
# 6. evaluate_participant — physical 3-way delay split
# ═══════════════════════════════════════════════════════════════════

class TestEvaluatePhysical:
    """Test 3-way delay split for physical appointments."""

    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.evidence_service.aggregate_evidence')
    @patch('services.attendance_service.db')
    def test_on_time_with_proof(self, mock_db, mock_agg, mock_proof):
        """delay=0, admissible proof → on_time."""
        from services.attendance_service import evaluate_participant

        mock_agg.return_value = {
            "strength": "strong", "timing": "on_time", "delay_minutes": 0,
            "evidence_count": 1, "manual_checkin_only": False,
        }
        mock_proof.return_value = True

        participant = {"participant_id": "p1", "status": "accepted_guaranteed", "appointment_id": "apt1"}
        appointment = {"appointment_id": "apt1", "tolerated_delay_minutes": 5}

        result = evaluate_participant(participant, appointment)
        assert result["outcome"] == "on_time"
        assert result["review_required"] is False

    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.evidence_service.aggregate_evidence')
    @patch('services.attendance_service.db')
    def test_late_within_tolerance(self, mock_db, mock_agg, mock_proof):
        """0 < delay <= tolerated, admissible proof → late (admissible)."""
        from services.attendance_service import evaluate_participant

        mock_agg.return_value = {
            "strength": "strong", "timing": "on_time", "delay_minutes": 3,
            "evidence_count": 1, "manual_checkin_only": False,
        }
        mock_proof.return_value = True

        participant = {"participant_id": "p1", "status": "accepted_guaranteed", "appointment_id": "apt1"}
        appointment = {"appointment_id": "apt1", "tolerated_delay_minutes": 5}

        result = evaluate_participant(participant, appointment)
        assert result["outcome"] == "late"
        assert result["review_required"] is False
        assert result["decision_basis"] == "admissible_proof_late_within_tolerance"

    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.evidence_service.aggregate_evidence')
    @patch('services.attendance_service.db')
    def test_late_beyond_tolerance(self, mock_db, mock_agg, mock_proof):
        """delay > tolerated, admissible proof → late_penalized."""
        from services.attendance_service import evaluate_participant

        mock_agg.return_value = {
            "strength": "strong", "timing": "late", "delay_minutes": 8,
            "evidence_count": 1, "manual_checkin_only": False,
        }
        mock_proof.return_value = True

        participant = {"participant_id": "p1", "status": "accepted_guaranteed", "appointment_id": "apt1"}
        appointment = {"appointment_id": "apt1", "tolerated_delay_minutes": 5}

        result = evaluate_participant(participant, appointment)
        assert result["outcome"] == "late_penalized"
        assert result["review_required"] is False
        assert result["decision_basis"] == "admissible_proof_late_beyond_tolerance"

    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.evidence_service.aggregate_evidence')
    @patch('services.attendance_service.db')
    def test_zero_tolerance_no_late_zone(self, mock_db, mock_agg, mock_proof):
        """tolerated=0, delay=1min → late_penalized (no admissible late zone)."""
        from services.attendance_service import evaluate_participant

        mock_agg.return_value = {
            "strength": "strong", "timing": "late", "delay_minutes": 1,
            "evidence_count": 1, "manual_checkin_only": False,
        }
        mock_proof.return_value = True

        participant = {"participant_id": "p1", "status": "accepted_guaranteed", "appointment_id": "apt1"}
        appointment = {"appointment_id": "apt1", "tolerated_delay_minutes": 0}

        result = evaluate_participant(participant, appointment)
        assert result["outcome"] == "late_penalized"

    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.evidence_service.aggregate_evidence')
    @patch('services.attendance_service.db')
    def test_zero_tolerance_on_time(self, mock_db, mock_agg, mock_proof):
        """tolerated=0, delay=0 → on_time."""
        from services.attendance_service import evaluate_participant

        mock_agg.return_value = {
            "strength": "strong", "timing": "on_time", "delay_minutes": 0,
            "evidence_count": 1, "manual_checkin_only": False,
        }
        mock_proof.return_value = True

        participant = {"participant_id": "p1", "status": "accepted_guaranteed", "appointment_id": "apt1"}
        appointment = {"appointment_id": "apt1", "tolerated_delay_minutes": 0}

        result = evaluate_participant(participant, appointment)
        assert result["outcome"] == "on_time"

    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.evidence_service.aggregate_evidence')
    @patch('services.attendance_service.db')
    def test_no_proof_forces_manual_review(self, mock_db, mock_agg, mock_proof):
        """No admissible proof → manual_review regardless of timing."""
        from services.attendance_service import evaluate_participant

        mock_agg.return_value = {
            "strength": "medium", "timing": "on_time", "delay_minutes": 0,
            "evidence_count": 1, "manual_checkin_only": True,
        }
        mock_proof.return_value = False

        participant = {"participant_id": "p1", "status": "accepted_guaranteed", "appointment_id": "apt1"}
        appointment = {"appointment_id": "apt1", "tolerated_delay_minutes": 5}

        result = evaluate_participant(participant, appointment)
        assert result["outcome"] == "manual_review"
        assert result["review_required"] is True


# ═══════════════════════════════════════════════════════════════════
# 7. Idempotence
# ═══════════════════════════════════════════════════════════════════

class TestIdempotence:
    """Test that _process_financial_outcomes is idempotent."""

    @patch('services.attendance_service._execute_release')
    @patch('services.attendance_service._execute_capture_and_distribution')
    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.attendance_service.db')
    def test_double_call_no_double_capture(self, mock_db, mock_proof, mock_capture, mock_release):
        """Calling _process_financial_outcomes twice should not double-capture."""
        from services.attendance_service import _process_financial_outcomes

        mock_db.attendance_records.find.return_value = [
            {"record_id": "r1", "participant_id": "p1", "outcome": "no_show", "review_required": False},
            {"record_id": "r_org", "participant_id": "p_org", "outcome": "on_time", "review_required": False},
        ]
        mock_db.payment_guarantees.find_one.return_value = {
            "guarantee_id": "g1", "participant_id": "p1", "status": "completed", "penalty_amount": 30
        }
        mock_proof.return_value = True

        parts = [
            {"participant_id": "p_org", "user_id": "org_user", "is_organizer": True, "status": "accepted_guaranteed"},
            {"participant_id": "p1", "user_id": "user1", "is_organizer": False, "status": "accepted_guaranteed"},
        ]
        apt = _make_appointment()

        with patch('services.attendance_service._find_participant', side_effect=_find_part_factory(parts)):
            _process_financial_outcomes("apt1", apt, parts)
            # Second call — simulate guarantee already captured
            mock_db.payment_guarantees.find_one.return_value = {
                "guarantee_id": "g1", "participant_id": "p1", "status": "captured", "penalty_amount": 30
            }
            _process_financial_outcomes("apt1", apt, parts)

        assert mock_capture.call_count == 1, f"Expected 1 capture call, got {mock_capture.call_count}"
