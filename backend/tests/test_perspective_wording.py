"""
Tests for P0 Perspective Wording Fix:
- is_target correctly returned by _enrich_dispute_for_user
- is_me correctly returned by _get_anonymized_summary
- Covers: 1v1, organizer-as-target (deadlock), N>2 participants
"""
import pytest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class FakeCollection:
    """Minimal mock for MongoDB collection."""
    def __init__(self, docs=None):
        self._docs = docs or []

    def find(self, query=None, projection=None):
        return FakeCursor(self._docs)

    def find_one(self, query=None, projection=None):
        return self._docs[0] if self._docs else None

    def count_documents(self, query=None):
        return len(self._docs)


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def __iter__(self):
        return iter(self._docs)

    def __next__(self):
        return next(iter(self._docs))

    def sort(self, *args, **kwargs):
        return self


# ─── Test _enrich_dispute_for_user ───

def test_is_target_normal_participant():
    """When user IS the target (target_user_id matches), is_target should be True."""
    from routers.dispute_routes import _enrich_dispute_for_user

    dispute = {
        "dispute_id": "d1",
        "appointment_id": "a1",
        "target_participant_id": "p2",
        "target_user_id": "user_bob",
        "organizer_user_id": "user_alice",
        "organizer_position": None,
        "participant_position": None,
        "status": "awaiting_positions",
        "resolution": {},
        "evidence_submissions": [],
    }

    with patch('routers.dispute_routes._get_other_party_name', return_value="Alice"):
        result = _enrich_dispute_for_user(dispute, "user_bob")

    assert result['is_target'] is True
    assert result['my_role'] == 'participant'


def test_is_target_organizer_not_target():
    """When user is the organizer but NOT the target, is_target should be False."""
    from routers.dispute_routes import _enrich_dispute_for_user

    dispute = {
        "dispute_id": "d2",
        "appointment_id": "a1",
        "target_participant_id": "p2",
        "target_user_id": "user_bob",
        "organizer_user_id": "user_alice",
        "organizer_position": None,
        "participant_position": None,
        "status": "awaiting_positions",
        "resolution": {},
        "evidence_submissions": [],
    }

    with patch('routers.dispute_routes._get_other_party_name', return_value="Bob"):
        result = _enrich_dispute_for_user(dispute, "user_alice")

    assert result['is_target'] is False
    assert result['my_role'] == 'organizer'


def test_is_target_deadlock_organizer_is_target():
    """Deadlock: organizer IS the target. is_target should be True, my_role should be organizer."""
    from routers.dispute_routes import _enrich_dispute_for_user

    dispute = {
        "dispute_id": "d3",
        "appointment_id": "a1",
        "target_participant_id": "p_org",
        "target_user_id": "user_alice",
        "organizer_user_id": "user_alice",
        "organizer_position": None,
        "participant_position": None,
        "status": "awaiting_positions",
        "resolution": {},
        "evidence_submissions": [],
    }

    with patch('routers.dispute_routes._get_other_party_name', return_value="Bob"):
        result = _enrich_dispute_for_user(dispute, "user_alice")

    # Key: is_target is True even though my_role is "organizer" (first branch wins)
    assert result['is_target'] is True
    assert result['my_role'] == 'organizer'


def test_is_target_deadlock_counterpart():
    """Deadlock: counterpart of a deadlock dispute. is_target should be False."""
    from routers.dispute_routes import _enrich_dispute_for_user, _is_dispute_counterpart

    dispute = {
        "dispute_id": "d4",
        "appointment_id": "a1",
        "target_participant_id": "p_org",
        "target_user_id": "user_alice",
        "organizer_user_id": "user_alice",
        "organizer_position": None,
        "participant_position": None,
        "status": "awaiting_positions",
        "resolution": {},
        "evidence_submissions": [],
    }

    with patch('routers.dispute_routes._is_dispute_counterpart', return_value=True), \
         patch('routers.dispute_routes._get_other_party_name', return_value="Alice"):
        result = _enrich_dispute_for_user(dispute, "user_bob")

    assert result['is_target'] is False
    assert result['my_role'] == 'participant'


def test_is_target_observer():
    """Observer (unrelated user) — is_target should be False."""
    from routers.dispute_routes import _enrich_dispute_for_user

    dispute = {
        "dispute_id": "d5",
        "appointment_id": "a1",
        "target_participant_id": "p2",
        "target_user_id": "user_bob",
        "organizer_user_id": "user_alice",
        "organizer_position": None,
        "participant_position": None,
        "status": "awaiting_positions",
        "resolution": {},
        "evidence_submissions": [],
    }

    with patch('routers.dispute_routes._is_dispute_counterpart', return_value=False):
        result = _enrich_dispute_for_user(dispute, "user_charlie")

    assert result['is_target'] is False
    assert result['my_role'] == 'observer'


# ─── Test _get_anonymized_summary with is_me ───

def test_is_me_viewer_is_declarant():
    """When the viewer submitted a declaration, their entry should have is_me=True."""
    from routers.dispute_routes import _get_anonymized_summary

    sheets = [
        {
            "submitted_by_participant_id": "p_alice",
            "submitted_by_user_id": "user_alice",
            "status": "submitted",
            "declarations": [
                {"target_participant_id": "p_bob", "declared_status": "absent"}
            ],
        },
        {
            "submitted_by_participant_id": "p_charlie",
            "submitted_by_user_id": "user_charlie",
            "status": "submitted",
            "declarations": [
                {"target_participant_id": "p_bob", "declared_status": "present_on_time"}
            ],
        },
    ]

    mock_db = MagicMock()
    mock_db.attendance_sheets.find.return_value = FakeCursor(sheets)
    mock_db.participants.find_one.side_effect = lambda q, p=None: (
        {"first_name": "Alice"} if q.get("participant_id") == "p_alice"
        else {"first_name": "Charlie"} if q.get("participant_id") == "p_charlie"
        else None
    )
    mock_db.evidence_items.count_documents.return_value = 0

    with patch('routers.dispute_routes.db', mock_db):
        result = _get_anonymized_summary("a1", "p_bob", viewer_user_id="user_alice")

    assert len(result['declarants']) == 2
    alice_decl = next(d for d in result['declarants'] if d['first_name'] == 'Alice')
    charlie_decl = next(d for d in result['declarants'] if d['first_name'] == 'Charlie')
    assert alice_decl['is_me'] is True
    assert charlie_decl['is_me'] is False


def test_is_me_viewer_not_declarant():
    """When the viewer didn't submit any declaration, all entries should have is_me=False."""
    from routers.dispute_routes import _get_anonymized_summary

    sheets = [
        {
            "submitted_by_participant_id": "p_alice",
            "submitted_by_user_id": "user_alice",
            "status": "submitted",
            "declarations": [
                {"target_participant_id": "p_bob", "declared_status": "absent"}
            ],
        },
    ]

    mock_db = MagicMock()
    mock_db.attendance_sheets.find.return_value = FakeCursor(sheets)
    mock_db.participants.find_one.return_value = {"first_name": "Alice"}
    mock_db.evidence_items.count_documents.return_value = 0

    with patch('routers.dispute_routes.db', mock_db):
        result = _get_anonymized_summary("a1", "p_bob", viewer_user_id="user_bob")

    assert len(result['declarants']) == 1
    assert result['declarants'][0]['is_me'] is False


def test_is_me_no_viewer():
    """When no viewer_user_id is passed, all is_me should be False."""
    from routers.dispute_routes import _get_anonymized_summary

    sheets = [
        {
            "submitted_by_participant_id": "p_alice",
            "submitted_by_user_id": "user_alice",
            "status": "submitted",
            "declarations": [
                {"target_participant_id": "p_bob", "declared_status": "absent"}
            ],
        },
    ]

    mock_db = MagicMock()
    mock_db.attendance_sheets.find.return_value = FakeCursor(sheets)
    mock_db.participants.find_one.return_value = {"first_name": "Alice"}
    mock_db.evidence_items.count_documents.return_value = 0

    with patch('routers.dispute_routes.db', mock_db):
        result = _get_anonymized_summary("a1", "p_bob")

    assert result['declarants'][0]['is_me'] is False


def test_is_me_multiple_declarants_n3():
    """3 participants (N=3): 2 tiers declare on target. Viewer is one of them."""
    from routers.dispute_routes import _get_anonymized_summary

    sheets = [
        {
            "submitted_by_participant_id": "p_alice",
            "submitted_by_user_id": "user_alice",
            "status": "submitted",
            "declarations": [
                {"target_participant_id": "p_bob", "declared_status": "absent"}
            ],
        },
        {
            "submitted_by_participant_id": "p_charlie",
            "submitted_by_user_id": "user_charlie",
            "status": "submitted",
            "declarations": [
                {"target_participant_id": "p_bob", "declared_status": "absent"}
            ],
        },
        {
            "submitted_by_participant_id": "p_bob",
            "submitted_by_user_id": "user_bob",
            "status": "submitted",
            "declarations": [
                {"target_participant_id": "p_bob", "declared_status": "present_on_time"}
            ],
        },
    ]

    mock_db = MagicMock()
    mock_db.attendance_sheets.find.return_value = FakeCursor(sheets)
    mock_db.participants.find_one.side_effect = lambda q, p=None: (
        {"first_name": "Alice"} if q.get("participant_id") == "p_alice"
        else {"first_name": "Charlie"} if q.get("participant_id") == "p_charlie"
        else {"first_name": "Bob"} if q.get("participant_id") == "p_bob"
        else None
    )
    mock_db.evidence_items.count_documents.return_value = 0

    with patch('routers.dispute_routes.db', mock_db):
        # Viewer = Alice (one of the tiers)
        result = _get_anonymized_summary("a1", "p_bob", viewer_user_id="user_alice")

    # p_bob's self-declaration is excluded (submitter_pid == target_pid)
    assert len(result['declarants']) == 2
    alice_decl = next(d for d in result['declarants'] if d['first_name'] == 'Alice')
    charlie_decl = next(d for d in result['declarants'] if d['first_name'] == 'Charlie')
    assert alice_decl['is_me'] is True
    assert charlie_decl['is_me'] is False
    assert result['declared_absent_count'] == 2
