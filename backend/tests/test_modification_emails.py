"""
Tests for modification-applied email notifications.
Covers: recipients, content, type transitions, video params, cleanup.
"""
import os
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
os.environ.setdefault('DB_NAME', 'test_database')
os.environ.setdefault('FRONTEND_URL', 'https://test.nlyt.io')

import uuid
import pytest
from unittest.mock import patch, AsyncMock
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["test_database"]

PREFIX = "tme_"


def _uid():
    return f"{PREFIX}{uuid.uuid4().hex[:8]}"


def _setup_scenario(
    appointment_type="physical",
    meeting_provider=None,
    meeting_join_url=None,
    location="12 rue de Rivoli, Paris",
    num_accepted=2,
    proposer_role="organizer",
):
    apt_id = _uid()
    org_uid = _uid()

    db.users.insert_one({
        "user_id": org_uid, "email": f"{org_uid}@test.nlyt.io",
        "first_name": "Org", "last_name": "Anizer", f"_{PREFIX}test": True,
    })

    db.appointments.insert_one({
        "appointment_id": apt_id,
        "organizer_id": org_uid,
        "title": "RDV Modif Test",
        "start_datetime": "2026-04-15T14:00:00+00:00",
        "duration_minutes": 60,
        "appointment_type": appointment_type,
        "meeting_provider": meeting_provider,
        "meeting_join_url": meeting_join_url,
        "location": location,
        "penalty_amount": 20,
        "penalty_currency": "eur",
        "appointment_timezone": "Europe/Paris",
        f"_{PREFIX}test": True,
    })

    participants = []
    for i in range(num_accepted):
        pid = _uid()
        token = _uid()
        email = f"{pid}@test.nlyt.io"
        db.participants.insert_one({
            "participant_id": pid,
            "appointment_id": apt_id,
            "user_id": _uid(),
            "email": email,
            "first_name": f"Part{i}",
            "last_name": "Test",
            "status": "accepted_guaranteed",
            "invitation_token": token,
            f"_{PREFIX}test": True,
        })
        participants.append({"pid": pid, "email": email, "token": token})

    proposal = {
        "proposal_id": _uid(),
        "appointment_id": apt_id,
        "proposed_by": {"role": proposer_role, "user_id": org_uid if proposer_role == "organizer" else ""},
        "changes": {},
        "original_values": {},
    }

    return {
        "apt_id": apt_id,
        "org_uid": org_uid,
        "participants": participants,
        "proposal": proposal,
    }


def _cleanup():
    for coll in ["users", "appointments", "participants", "modification_proposals"]:
        db[coll].delete_many({f"_{PREFIX}test": True})


@pytest.fixture(autouse=True)
def cleanup():
    _cleanup()
    yield
    _cleanup()


class TestModificationEmails:

    @patch("services.email_service.EmailService.send_modification_applied_email", new_callable=AsyncMock)
    def test_1_participants_receive_email(self, mock_send):
        """Engaged participants receive modification email."""
        s = _setup_scenario(num_accepted=3)
        s["proposal"]["changes"] = {"duration_minutes": 90}
        s["proposal"]["original_values"] = {"duration_minutes": 60}

        from services.modification_service import _send_modification_emails
        _send_modification_emails(s["apt_id"], s["proposal"])

        # 3 participants (organizer is proposer, excluded)
        assert mock_send.call_count == 3
        emails_sent = [c.kwargs.get("to_email") or c[0][0] for c in mock_send.call_args_list]
        for p in s["participants"]:
            assert p["email"] in emails_sent

    @patch("services.email_service.EmailService.send_modification_applied_email", new_callable=AsyncMock)
    def test_2_organizer_receives_if_not_proposer(self, mock_send):
        """Organizer receives email if they did not propose the change."""
        s = _setup_scenario(num_accepted=1, proposer_role="participant")
        s["proposal"]["changes"] = {"duration_minutes": 90}
        s["proposal"]["original_values"] = {"duration_minutes": 60}

        from services.modification_service import _send_modification_emails
        _send_modification_emails(s["apt_id"], s["proposal"])

        # 1 participant + 1 organizer = 2
        assert mock_send.call_count == 2

    @patch("services.email_service.EmailService.send_modification_applied_email", new_callable=AsyncMock)
    def test_3_organizer_excluded_if_proposer(self, mock_send):
        """Organizer does NOT receive email if they proposed the change."""
        s = _setup_scenario(num_accepted=1, proposer_role="organizer")
        s["proposal"]["changes"] = {"location": "Nouveau lieu"}
        s["proposal"]["original_values"] = {"location": "Ancien lieu"}

        from services.modification_service import _send_modification_emails
        _send_modification_emails(s["apt_id"], s["proposal"])

        # Only the 1 participant
        assert mock_send.call_count == 1

    @patch("services.email_service.EmailService.send_modification_applied_email", new_callable=AsyncMock)
    def test_4_physical_to_video_sends_type_changed(self, mock_send):
        """Physical→Video: type_changed=True, new_appointment_type=video."""
        s = _setup_scenario(appointment_type="video", meeting_provider="zoom", num_accepted=1)
        s["proposal"]["changes"] = {"appointment_type": "video", "meeting_provider": "zoom"}
        s["proposal"]["original_values"] = {"appointment_type": "physical", "meeting_provider": None}

        from services.modification_service import _send_modification_emails
        _send_modification_emails(s["apt_id"], s["proposal"])

        call_kwargs = mock_send.call_args_list[0].kwargs
        assert call_kwargs["type_changed"] is True
        assert call_kwargs["new_appointment_type"] == "video"
        assert call_kwargs["meeting_provider"] == "zoom"
        assert "/proof/" in call_kwargs["access_link"]

    @patch("services.email_service.EmailService.send_modification_applied_email", new_callable=AsyncMock)
    def test_5_video_to_physical_sends_type_changed(self, mock_send):
        """Video→Physical: type_changed=True, new_appointment_type=physical."""
        s = _setup_scenario(appointment_type="physical", location="5 rue de la Paix", num_accepted=1)
        s["proposal"]["changes"] = {"appointment_type": "physical"}
        s["proposal"]["original_values"] = {"appointment_type": "video"}

        from services.modification_service import _send_modification_emails
        _send_modification_emails(s["apt_id"], s["proposal"])

        call_kwargs = mock_send.call_args_list[0].kwargs
        assert call_kwargs["type_changed"] is True
        assert call_kwargs["new_appointment_type"] == "physical"
        assert call_kwargs["location"] == "5 rue de la Paix"
        assert "/invitation/" in call_kwargs["access_link"]

    @patch("services.email_service.EmailService.send_modification_applied_email", new_callable=AsyncMock)
    def test_6_no_type_change_no_access_block(self, mock_send):
        """When type doesn't change, type_changed=False."""
        s = _setup_scenario(num_accepted=1)
        s["proposal"]["changes"] = {"duration_minutes": 120}
        s["proposal"]["original_values"] = {"duration_minutes": 60}

        from services.modification_service import _send_modification_emails
        _send_modification_emails(s["apt_id"], s["proposal"])

        call_kwargs = mock_send.call_args_list[0].kwargs
        assert call_kwargs["type_changed"] is False

    def test_7_cleanup_video_to_physical(self):
        """Switching video→physical clears meeting_join_url and external_meeting_id."""
        s = _setup_scenario(
            appointment_type="video", meeting_provider="zoom",
            meeting_join_url="https://zoom.us/j/123", num_accepted=0
        )

        # Simulate _apply_proposal with type change
        from services.modification_service import _apply_proposal
        proposal = {
            "appointment_id": s["apt_id"],
            "changes": {"appointment_type": "physical"},
            "original_values": {"appointment_type": "video"},
            "proposed_by": {"role": "organizer", "user_id": s["org_uid"]},
        }

        with patch("services.modification_service._handle_guarantees_after_modification"), \
             patch("services.modification_service._send_modification_emails"):
            _apply_proposal(proposal)

        apt = db.appointments.find_one({"appointment_id": s["apt_id"]}, {"_id": 0})
        assert apt["appointment_type"] == "physical"
        assert apt.get("meeting_provider") is None
        assert apt.get("meeting_join_url") is None
        assert apt.get("external_meeting_id") is None

    def test_8_template_contains_before_after(self):
        """Email HTML contains before/after table with correct labels."""
        import asyncio
        from services.email_service import EmailService

        html = None
        original_send = EmailService.send_email

        async def capture_html(to, subject, html_content, **kwargs):
            nonlocal html
            html = html_content
            return {"success": True, "id": "test"}

        with patch.object(EmailService, 'send_email', side_effect=capture_html):
            loop = asyncio.new_event_loop()
            loop.run_until_complete(EmailService.send_modification_applied_email(
                to_email="test@test.io",
                to_name="Alice",
                appointment_title="RDV Test",
                appointment_datetime="2026-04-15T14:00:00+00:00",
                changes={"appointment_type": "video", "duration_minutes": 90},
                original_values={"appointment_type": "physical", "duration_minutes": 60},
                new_appointment_type="video",
                type_changed=True,
                access_link="https://test.nlyt.io/proof/123",
                invitation_link="https://test.nlyt.io/invitation/abc",
                meeting_provider="zoom",
            ))
            loop.close()

        assert html is not None
        # Check before/after labels
        assert "En personne" in html  # old type
        assert "Visioconférence" in html  # new type
        assert "60 min" in html  # old duration
        assert "90 min" in html  # new duration
        assert "Format" in html  # field label
        assert "Durée" in html  # field label
        # Check access block for video
        assert "Confirmer ma présence et rejoindre" in html
        assert "Zoom" in html
        # Check CTA
        assert "Voir le rendez-vous" in html

    def test_9_template_physical_access_block(self):
        """When switching to physical, access block shows location and GPS check-in."""
        import asyncio
        from services.email_service import EmailService

        html = None

        async def capture_html(to, subject, html_content, **kwargs):
            nonlocal html
            html = html_content
            return {"success": True, "id": "test"}

        with patch.object(EmailService, 'send_email', side_effect=capture_html):
            loop = asyncio.new_event_loop()
            loop.run_until_complete(EmailService.send_modification_applied_email(
                to_email="test@test.io",
                to_name="Bob",
                appointment_title="RDV Physique",
                appointment_datetime="2026-04-15T14:00:00+00:00",
                changes={"appointment_type": "physical"},
                original_values={"appointment_type": "video"},
                new_appointment_type="physical",
                type_changed=True,
                access_link="https://test.nlyt.io/invitation/abc",
                invitation_link="https://test.nlyt.io/invitation/abc",
                location="5 avenue des Champs-Élysées, Paris",
            ))
            loop.close()

        assert html is not None
        assert "5 avenue des Champs-Élysées, Paris" in html
        assert "Je suis arrivé" in html
        assert "confirmer ma présence" in html.lower()

    def test_10_source_label_never_exposes_organizer_decision(self):
        """Email modification never contains accusatory language."""
        import asyncio
        from services.email_service import EmailService

        html = None

        async def capture_html(to, subject, html_content, **kwargs):
            nonlocal html
            html = html_content
            return {"success": True, "id": "test"}

        with patch.object(EmailService, 'send_email', side_effect=capture_html):
            loop = asyncio.new_event_loop()
            loop.run_until_complete(EmailService.send_modification_applied_email(
                to_email="test@test.io",
                to_name="Charlie",
                appointment_title="RDV Neutral",
                appointment_datetime="2026-04-15T14:00:00+00:00",
                changes={"location": "Nouveau lieu"},
                original_values={"location": "Ancien lieu"},
                new_appointment_type="physical",
                type_changed=False,
                access_link="https://test.nlyt.io/invitation/abc",
                invitation_link="https://test.nlyt.io/invitation/abc",
            ))
            loop.close()

        assert html is not None
        low = html.lower()
        assert "sanction" not in low
        assert "faute" not in low
        assert "violation" not in low
        assert "punition" not in low
