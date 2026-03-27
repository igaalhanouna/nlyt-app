"""
Tests for dispute resolution email notifications.
10 tests covering: trigger, recipients, idempotence, financial blocs, edge cases.
"""
import os
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
os.environ.setdefault('DB_NAME', 'test_database')
os.environ.setdefault('FRONTEND_URL', 'https://test.nlyt.io')

import uuid
import pytest
from unittest.mock import patch, MagicMock
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["test_database"]

PREFIX = "tde_"  # test dispute email prefix


def _uid():
    return f"{PREFIX}{uuid.uuid4().hex[:8]}"


def _setup_dispute_scenario(
    final_outcome="on_time",
    resolved_by="platform",
    guarantee_status=None,
    distribution_status=None,
    distribution_beneficiaries=None,
    organizer_is_target=False,
):
    """Create a complete dispute scenario in DB. Returns IDs dict."""
    apt_id = _uid()
    dispute_id = _uid()
    target_pid = _uid()
    target_uid = _uid()
    org_uid = target_uid if organizer_is_target else _uid()

    # Users
    db.users.insert_many([
        {"user_id": target_uid, "email": f"{target_uid}@test.nlyt.io",
         "first_name": "Alice", "last_name": "Dupont", f"_{PREFIX}test": True},
        *([{"user_id": org_uid, "email": f"{org_uid}@test.nlyt.io",
            "first_name": "Bob", "last_name": "Martin", f"_{PREFIX}test": True}]
          if not organizer_is_target else []),
    ])

    # Appointment
    db.appointments.insert_one({
        "appointment_id": apt_id,
        "organizer_id": org_uid,
        "title": "RDV Test Litige",
        "start_datetime": "2026-03-15T10:00:00+00:00",
        "penalty_amount": 25,
        "penalty_currency": "eur",
        "appointment_timezone": "Europe/Paris",
        f"_{PREFIX}test": True,
    })

    # Participant
    db.participants.insert_one({
        "participant_id": target_pid,
        "appointment_id": apt_id,
        "user_id": target_uid,
        "first_name": "Alice",
        "last_name": "Dupont",
        "email": f"{target_uid}@test.nlyt.io",
        f"_{PREFIX}test": True,
    })

    # Attendance record
    db.attendance_records.insert_one({
        "record_id": _uid(),
        "appointment_id": apt_id,
        "participant_id": target_pid,
        "outcome": final_outcome,
        "review_required": False,
        "decided_by": resolved_by,
        f"_{PREFIX}test": True,
    })

    # Dispute (resolved)
    db.declarative_disputes.insert_one({
        "dispute_id": dispute_id,
        "appointment_id": apt_id,
        "target_participant_id": target_pid,
        "target_user_id": target_uid,
        "status": "resolved",
        "resolution": {
            "resolved_at": "2026-03-16T12:00:00+00:00",
            "resolved_by": resolved_by,
            "final_outcome": final_outcome,
            "resolution_note": "Test resolution",
        },
        f"_{PREFIX}test": True,
    })

    # Guarantee (optional)
    if guarantee_status:
        db.payment_guarantees.insert_one({
            "guarantee_id": _uid(),
            "participant_id": target_pid,
            "appointment_id": apt_id,
            "penalty_amount": 25,
            "status": guarantee_status,
            f"_{PREFIX}test": True,
        })

    # Distribution (optional)
    dist_id = None
    if distribution_status:
        dist_id = _uid()
        db.distributions.insert_one({
            "distribution_id": dist_id,
            "appointment_id": apt_id,
            "guarantee_id": _uid(),
            "no_show_participant_id": target_pid,
            "status": distribution_status,
            "beneficiaries": distribution_beneficiaries or [],
            f"_{PREFIX}test": True,
        })

    return {
        "dispute_id": dispute_id,
        "apt_id": apt_id,
        "target_pid": target_pid,
        "target_uid": target_uid,
        "org_uid": org_uid,
        "dist_id": dist_id,
    }


def _cleanup():
    for coll in ["users", "appointments", "participants", "attendance_records",
                 "declarative_disputes", "payment_guarantees", "distributions", "sent_emails"]:
        db[coll].delete_many({f"_{PREFIX}test": True})
    # Also clean sent_emails by reference_id prefix
    db.sent_emails.delete_many({"reference_id": {"$regex": f"^{PREFIX}"}})


@pytest.fixture(autouse=True)
def cleanup():
    _cleanup()
    yield
    _cleanup()


class TestDisputeResolutionEmails:

    @patch("services.financial_emails._send_async")
    def test_1_target_receives_email(self, mock_send):
        """Target participant receives an email when dispute is resolved."""
        ids = _setup_dispute_scenario()
        from services.financial_emails import send_dispute_resolution_emails
        send_dispute_resolution_emails(ids["dispute_id"])

        calls = [c for c in mock_send.call_args_list if c[0][3] == "dispute_resolved_target"]
        assert len(calls) == 1
        assert ids["target_uid"] in calls[0][0][0]  # email contains target uid

    @patch("services.financial_emails._send_async")
    def test_2_organizer_receives_email(self, mock_send):
        """Organizer receives an email when dispute is resolved."""
        ids = _setup_dispute_scenario()
        from services.financial_emails import send_dispute_resolution_emails
        send_dispute_resolution_emails(ids["dispute_id"])

        calls = [c for c in mock_send.call_args_list if c[0][3] == "dispute_resolved_organizer"]
        assert len(calls) == 1
        assert ids["org_uid"] in calls[0][0][0]

    @patch("services.financial_emails._send_async")
    def test_3_organizer_is_target_single_email(self, mock_send):
        """When organizer = target participant, only 1 email (target variant) is sent."""
        ids = _setup_dispute_scenario(organizer_is_target=True)
        from services.financial_emails import send_dispute_resolution_emails
        send_dispute_resolution_emails(ids["dispute_id"])

        target_calls = [c for c in mock_send.call_args_list if c[0][3] == "dispute_resolved_target"]
        org_calls = [c for c in mock_send.call_args_list if c[0][3] == "dispute_resolved_organizer"]
        assert len(target_calls) == 1
        assert len(org_calls) == 0

    @patch("services.financial_emails._send_async")
    def test_4_idempotence(self, mock_send):
        """Calling twice with same dispute_id: _send_async checks idempotence internally."""
        ids = _setup_dispute_scenario()
        from services.financial_emails import send_dispute_resolution_emails
        send_dispute_resolution_emails(ids["dispute_id"])
        first_count = mock_send.call_count
        send_dispute_resolution_emails(ids["dispute_id"])
        # _send_async is called again but its internal _already_sent will block actual send
        # Here we just verify the function doesn't crash on second call
        assert mock_send.call_count == first_count * 2  # called again, idempotence is inside _send_async

    @patch("services.financial_emails._send_async")
    def test_5_no_email_if_not_resolved(self, mock_send):
        """No email sent if dispute status is not 'resolved'."""
        ids = _setup_dispute_scenario()
        # Change dispute status back to awaiting_evidence
        db.declarative_disputes.update_one(
            {"dispute_id": ids["dispute_id"]},
            {"$set": {"status": "awaiting_evidence"}}
        )
        from services.financial_emails import send_dispute_resolution_emails
        send_dispute_resolution_emails(ids["dispute_id"])
        assert mock_send.call_count == 0

    @patch("services.financial_emails._send_async")
    def test_6_financial_bloc_captured(self, mock_send):
        """When guarantee is captured, email contains penalty wording."""
        ids = _setup_dispute_scenario(final_outcome="no_show", guarantee_status="captured")
        from services.financial_emails import send_dispute_resolution_emails
        send_dispute_resolution_emails(ids["dispute_id"])

        target_calls = [c for c in mock_send.call_args_list if c[0][3] == "dispute_resolved_target"]
        assert len(target_calls) == 1
        html = target_calls[0][0][2]  # 3rd positional arg = html
        assert "pénalité" in html.lower()
        assert "25" in html

    @patch("services.financial_emails._send_async")
    def test_7_financial_bloc_released(self, mock_send):
        """When guarantee is released, email contains liberation wording."""
        ids = _setup_dispute_scenario(final_outcome="on_time", guarantee_status="released")
        from services.financial_emails import send_dispute_resolution_emails
        send_dispute_resolution_emails(ids["dispute_id"])

        target_calls = [c for c in mock_send.call_args_list if c[0][3] == "dispute_resolved_target"]
        html = target_calls[0][0][2]
        assert "libérée" in html

    @patch("services.financial_emails._send_async")
    def test_8_financial_bloc_no_impact(self, mock_send):
        """When no guarantee exists, email says no financial impact."""
        ids = _setup_dispute_scenario(final_outcome="waived", guarantee_status=None)
        from services.financial_emails import send_dispute_resolution_emails
        send_dispute_resolution_emails(ids["dispute_id"])

        target_calls = [c for c in mock_send.call_args_list if c[0][3] == "dispute_resolved_target"]
        html = target_calls[0][0][2]
        assert "aucun impact financier" in html.lower()

    @patch("services.financial_emails._send_async")
    def test_9_beneficiary_cancelled_distribution(self, mock_send):
        """Beneficiary receives 'dédommagement annulé' when distribution is cancelled."""
        bene_uid = _uid()
        db.users.insert_one({
            "user_id": bene_uid, "email": f"{bene_uid}@test.nlyt.io",
            "first_name": "Charlie", "last_name": "Bene", f"_{PREFIX}test": True,
        })
        ids = _setup_dispute_scenario(
            final_outcome="on_time",
            guarantee_status="released",
            distribution_status="cancelled",
            distribution_beneficiaries=[
                {"role": "participant", "user_id": bene_uid, "amount_cents": 1000},
                {"role": "platform", "user_id": "platform", "amount_cents": 500},
            ],
        )
        from services.financial_emails import send_dispute_resolution_emails
        send_dispute_resolution_emails(ids["dispute_id"])

        bene_calls = [c for c in mock_send.call_args_list if c[0][3] == "dispute_resolved_beneficiary"]
        assert len(bene_calls) == 1  # only participant role, not platform
        html = bene_calls[0][0][2]
        assert "annulé" in html.lower()
        assert "10,00" in html  # 1000 cents = 10,00 €

    @patch("services.financial_emails._send_async")
    def test_10_source_never_shows_organizer(self, mock_send):
        """Source label never exposes 'organisateur' as decision maker."""
        ids = _setup_dispute_scenario(resolved_by="organizer")
        from services.financial_emails import send_dispute_resolution_emails
        send_dispute_resolution_emails(ids["dispute_id"])

        for call in mock_send.call_args_list:
            html = call[0][2]
            # The word "organisateur" should only appear in context labels, never as decision source
            # Check that "Décision de l'organisateur" is absent
            assert "décision de l'organisateur" not in html.lower()
            assert "décision de l&#x27;organisateur" not in html.lower()
            # Instead, it should show "Résolution validée"
            assert "Résolution validée" in html
