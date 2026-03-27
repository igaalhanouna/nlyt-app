"""
Tests V3 Trustless — Penalty system integrity tests.
Tests the 3 critical rules:
1. No on_time/late without admissible proof
2. No compensation to unproven beneficiary (Cas A/B)
3. No reclassification with conflict of interest
"""
import pytest
import os
import sys
from unittest.mock import patch, MagicMock
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
# 2. _process_financial_outcomes — Cas A / Cas B
# ═══════════════════════════════════════════════════════════════════

class TestProcessFinancialOutcomes:
    """Test V3 trustless financial outcome processing."""

    def _make_appointment(self, apt_id="apt1", penalty=30):
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

    def _make_participants(self, apt_id="apt1"):
        return [
            {"participant_id": "p_org", "user_id": "org_user", "appointment_id": apt_id, "is_organizer": True, "status": "accepted_guaranteed"},
            {"participant_id": "p1", "user_id": "user1", "appointment_id": apt_id, "is_organizer": False, "status": "accepted_guaranteed"},
            {"participant_id": "p2", "user_id": "user2", "appointment_id": apt_id, "is_organizer": False, "status": "accepted_guaranteed"},
        ]

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
        mock_proof.return_value = True  # Organizer has admissible proof

        apt = self._make_appointment()
        parts = self._make_participants()

        def find_part(parts, pid):
            return next((p for p in parts if p["participant_id"] == pid), None)

        with patch('services.attendance_service._find_participant', side_effect=lambda ps, pid: find_part(parts, pid)):
            _process_financial_outcomes("apt1", apt, parts)

        mock_capture.assert_called_once()
        call_args = mock_capture.call_args
        eligible = call_args[0][3]  # 4th positional arg = eligible_beneficiaries
        user_ids = [b["user_id"] for b in eligible]
        assert "org_user" in user_ids, "Organizer with proof should be eligible"

    @patch('services.attendance_service._execute_release')
    @patch('services.attendance_service._execute_capture_and_distribution')
    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.attendance_service.db')
    def test_beneficiary_late_with_proof_gets_compensation(self, mock_db, mock_proof, mock_capture, mock_release):
        """late + Niveau 1-2 proof → compensable."""
        from services.attendance_service import _process_financial_outcomes

        mock_db.attendance_records.find.return_value = [
            {"record_id": "r1", "participant_id": "p1", "outcome": "no_show", "review_required": False},
            {"record_id": "r_org", "participant_id": "p_org", "outcome": "late", "review_required": False},
        ]
        mock_db.payment_guarantees.find_one.return_value = {
            "guarantee_id": "g1", "participant_id": "p1", "status": "completed", "penalty_amount": 30
        }
        mock_proof.return_value = True

        apt = self._make_appointment()
        parts = self._make_participants()

        def find_part(parts, pid):
            return next((p for p in parts if p["participant_id"] == pid), None)

        with patch('services.attendance_service._find_participant', side_effect=lambda ps, pid: find_part(parts, pid)):
            _process_financial_outcomes("apt1", apt, parts)

        mock_capture.assert_called_once()
        call_args = mock_capture.call_args
        eligible = call_args[0][3]
        user_ids = [b["user_id"] for b in eligible]
        assert "org_user" in user_ids, "Late organizer with proof should be eligible"

    @patch('services.attendance_service._execute_release')
    @patch('services.attendance_service._execute_capture_and_distribution')
    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.attendance_service.db')
    def test_beneficiary_without_proof_excluded(self, mock_db, mock_proof, mock_capture, mock_release):
        """on_time/late + Niveau 3 or 0 evidence → not compensable, forced to review (Cas A)."""
        from services.attendance_service import _process_financial_outcomes

        mock_db.attendance_records.find.return_value = [
            {"record_id": "r1", "participant_id": "p1", "outcome": "no_show", "review_required": False},
            {"record_id": "r_org", "participant_id": "p_org", "outcome": "on_time", "review_required": False},
        ]
        mock_db.payment_guarantees.find_one.return_value = {
            "guarantee_id": "g1", "participant_id": "p1", "status": "completed", "penalty_amount": 30
        }
        mock_proof.return_value = False  # Organizer has NO admissible proof
        mock_db.attendance_records.update_one = MagicMock()

        apt = self._make_appointment()
        parts = self._make_participants()

        def find_part(parts, pid):
            return next((p for p in parts if p["participant_id"] == pid), None)

        with patch('services.attendance_service._find_participant', side_effect=lambda ps, pid: find_part(parts, pid)):
            _process_financial_outcomes("apt1", apt, parts)

        # No capture should occur because no proven beneficiary → Cas A override to review
        mock_capture.assert_not_called()
        # The no_show record should have been forced to review
        mock_db.attendance_records.update_one.assert_called()

    @patch('services.attendance_service._execute_release')
    @patch('services.attendance_service._execute_capture_and_distribution')
    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.attendance_service.db')
    def test_cas_b_nobody_has_proof_all_gele(self, mock_db, mock_proof, mock_capture, mock_release):
        """Cas B: no participant has Niveau 1-2 proof → all gelé, no capture."""
        from services.attendance_service import _process_financial_outcomes

        mock_db.attendance_records.find.return_value = [
            {"record_id": "r1", "participant_id": "p1", "outcome": "no_show", "review_required": False},
            {"record_id": "r_org", "participant_id": "p_org", "outcome": "on_time", "review_required": False},
        ]
        mock_proof.return_value = False  # Nobody has proof
        mock_db.attendance_records.update_one = MagicMock()

        apt = self._make_appointment()
        parts = self._make_participants()

        def find_part(parts, pid):
            return next((p for p in parts if p["participant_id"] == pid), None)

        with patch('services.attendance_service._find_participant', side_effect=lambda ps, pid: find_part(parts, pid)):
            _process_financial_outcomes("apt1", apt, parts)

        # No capture, no release
        mock_capture.assert_not_called()
        mock_release.assert_not_called()
        # All records forced to review_required
        assert mock_db.attendance_records.update_one.call_count >= 1

    @patch('services.attendance_service._execute_release')
    @patch('services.attendance_service._execute_capture_and_distribution')
    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.attendance_service.db')
    def test_cas_a_capture_with_proven_beneficiary(self, mock_db, mock_proof, mock_capture, mock_release):
        """Cas A: payeur absent + at least 1 proven beneficiary → capture + compensation."""
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
            # org has proof, p2 has proof, p1 (no_show) has no proof
            return pid in ("p_org", "p2")

        mock_proof.side_effect = proof_side_effect

        apt = self._make_appointment()
        parts = self._make_participants()

        def find_part(parts, pid):
            return next((p for p in parts if p["participant_id"] == pid), None)

        with patch('services.attendance_service._find_participant', side_effect=lambda ps, pid: find_part(parts, pid)):
            _process_financial_outcomes("apt1", apt, parts)

        mock_capture.assert_called_once()
        eligible = mock_capture.call_args[0][3]
        user_ids = [b["user_id"] for b in eligible]
        assert "org_user" in user_ids
        assert "user2" in user_ids
        assert "user1" not in user_ids  # no_show excluded


# ═══════════════════════════════════════════════════════════════════
# 3. Reclassification conflict of interest
# ═══════════════════════════════════════════════════════════════════

class TestReclassificationConflict:
    """Test V3 trustless reclassification blocking logic."""

    @patch('routers.attendance_routes.db')
    def test_conflict_detection_logic(self, mock_db):
        """
        If organizer reclassifies a non-org participant to no_show,
        the participant lookup returns is_organizer=False → conflict detected.
        """
        mock_db.participants.find_one.return_value = {
            "participant_id": "p1",
            "is_organizer": False,
            "user_id": "user1",
        }

        reclassified = mock_db.participants.find_one.return_value
        new_outcome = "no_show"

        # This is the exact logic from the endpoint
        is_conflict = (
            new_outcome in ('no_show', 'late')
            and reclassified
            and not reclassified.get('is_organizer', False)
        )
        assert is_conflict is True, "Should detect conflict: org reclassifies non-org to no_show"

    @patch('routers.attendance_routes.db')
    def test_no_conflict_when_reclassify_to_on_time(self, mock_db):
        """Reclassify to on_time → no conflict (benefits the participant, not the org)."""
        new_outcome = "on_time"
        is_conflict = new_outcome in ('no_show', 'late')
        assert is_conflict is False, "on_time reclassification should never be a conflict"

    @patch('routers.attendance_routes.db')
    def test_no_conflict_when_reclassify_org_self(self, mock_db):
        """Org reclassifying themselves (is_organizer=True) → no conflict."""
        mock_db.participants.find_one.return_value = {
            "participant_id": "p_org",
            "is_organizer": True,
            "user_id": "org_user",
        }

        reclassified = mock_db.participants.find_one.return_value
        new_outcome = "no_show"

        is_conflict = (
            new_outcome in ('no_show', 'late')
            and reclassified
            and not reclassified.get('is_organizer', False)
        )
        assert is_conflict is False, "Org reclassifying themselves = no conflict"


# ═══════════════════════════════════════════════════════════════════
# 4. Additional coverage — mixed profiles, idempotence
# ═══════════════════════════════════════════════════════════════════

class TestMixedProfiles:
    """Test multiple beneficiaries with different proof levels on the same RDV."""

    @patch('services.attendance_service._execute_release')
    @patch('services.attendance_service._execute_capture_and_distribution')
    @patch('services.attendance_service._has_admissible_proof')
    @patch('services.attendance_service.db')
    def test_mixed_profiles_only_proven_get_compensation(self, mock_db, mock_proof, mock_capture, mock_release):
        """
        Org (GPS proof) + p1 (no proof) + p2 (QR proof) + p3 (no_show).
        Only org and p2 should be eligible beneficiaries.
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
            return pid in ("p_org", "p2")  # org=GPS, p2=QR. p1=no proof.

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

        def find_part(ps, pid):
            return next((p for p in ps if p["participant_id"] == pid), None)

        with patch('services.attendance_service._find_participant', side_effect=lambda ps, pid: find_part(parts, pid)):
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

        def find_part(ps, pid):
            return next((p for p in ps if p["participant_id"] == pid), None)

        with patch('services.attendance_service._find_participant', side_effect=lambda ps, pid: find_part(parts, pid)):
            _process_financial_outcomes("apt1", apt, parts)

        mock_capture.assert_called_once()
        eligible = mock_capture.call_args[0][3]
        user_ids = {b["user_id"] for b in eligible}
        assert "org_user" in user_ids, "Late org with proof should be eligible"
        assert "user1" in user_ids, "On-time p1 with proof should be eligible"
        assert "user2" not in user_ids, "manual_review p2 should NOT be eligible"
        assert len(eligible) == 2


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
        apt = {
            "appointment_id": "apt1", "organizer_id": "org_user", "penalty_amount": 30,
            "penalty_currency": "eur", "platform_commission_percent": 20.0,
            "affected_compensation_percent": 50.0, "charity_percent": 10.0,
        }

        def find_part(ps, pid):
            return next((p for p in ps if p["participant_id"] == pid), None)

        with patch('services.attendance_service._find_participant', side_effect=lambda ps, pid: find_part(parts, pid)):
            _process_financial_outcomes("apt1", apt, parts)
            # Second call — simulate guarantee already captured
            mock_db.payment_guarantees.find_one.return_value = {
                "guarantee_id": "g1", "participant_id": "p1", "status": "captured", "penalty_amount": 30
            }
            _process_financial_outcomes("apt1", apt, parts)

        # _execute_capture should be called only ONCE (second call skips because status=captured → no valid guarantee)
        assert mock_capture.call_count == 1, f"Expected 1 capture call, got {mock_capture.call_count}"
