"""
Tests — Retroactive Guard & Migration (Fix orphaned collecting phases)

Scenarios:
  1. Single guaranteed in manual_review → auto-waived, phase = not_needed
  2. Two guaranteed in manual_review → phase stays collecting (valid state)
  3. Zero guaranteed (non-guaranteed only) → auto-waived, phase = not_needed
  4. Mixed: 1 guaranteed + 1 non-guaranteed → auto-waived (< 2 guaranteed)
  5. Already resolved phases are not touched
"""
import sys
import uuid

sys.path.append('/app/backend')
from database import db
from datetime import datetime, timezone, timedelta

PREFIX = "test_retro_"


def _clean():
    db.appointments.delete_many({"appointment_id": {"$regex": f"^{PREFIX}"}})
    db.participants.delete_many({"appointment_id": {"$regex": f"^{PREFIX}"}})
    db.attendance_records.delete_many({"appointment_id": {"$regex": f"^{PREFIX}"}})
    db.attendance_sheets.delete_many({"appointment_id": {"$regex": f"^{PREFIX}"}})


def _create_scenario(apt_suffix, participants_config, phase="collecting"):
    """
    participants_config: list of (status, outcome, review_required)
    Returns apt_id
    """
    apt_id = f"{PREFIX}apt_{apt_suffix}"
    now = datetime.now(timezone.utc)

    db.appointments.insert_one({
        "appointment_id": apt_id,
        "title": f"Test {apt_suffix}",
        "declarative_phase": phase,
        "declarative_deadline": (now + timedelta(hours=48)).isoformat(),
        "attendance_evaluated": True,
        "organizer_id": "org_test",
    })

    for i, (status, outcome, review_req) in enumerate(participants_config):
        pid = f"{PREFIX}part_{apt_suffix}_{i}"
        db.participants.insert_one({
            "participant_id": pid,
            "appointment_id": apt_id,
            "email": f"test{i}@test.com",
            "user_id": f"user_{i}",
            "status": status,
        })
        db.attendance_records.insert_one({
            "appointment_id": apt_id,
            "participant_id": pid,
            "outcome": outcome,
            "review_required": review_req,
            "decided_by": "system",
        })
        if outcome == "manual_review" and review_req:
            db.attendance_sheets.insert_one({
                "sheet_id": f"{PREFIX}sheet_{apt_suffix}_{i}",
                "appointment_id": apt_id,
                "submitted_by_participant_id": pid,
                "status": "pending",
            })

    return apt_id


def _run_guard_on(apt_id):
    """Simulate what the deadline job guard does."""
    from services.declarative_service import run_declarative_deadline_job
    # The guard runs at the top of the job for ALL collecting appointments
    run_declarative_deadline_job()


def test_1_single_guaranteed():
    """1 guaranteed + 1 declined → auto-waive, not_needed."""
    _clean()
    apt_id = _create_scenario("single", [
        ("accepted_guaranteed", "manual_review", True),
        ("declined", "waived", False),
    ])

    _run_guard_on(apt_id)

    apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
    assert apt["declarative_phase"] == "not_needed", \
        f"Phase should be not_needed, got {apt['declarative_phase']}"

    rec = db.attendance_records.find_one(
        {"appointment_id": apt_id, "outcome": "manual_review"}, {"_id": 0}
    )
    assert rec is None, "manual_review record should have been waived"

    waived = db.attendance_records.find_one(
        {"appointment_id": apt_id, "decision_source": "retroactive_guard_insufficient_guaranteed"},
        {"_id": 0}
    )
    assert waived is not None, "Should have a retroactively waived record"
    assert waived["review_required"] is False

    sheets = db.attendance_sheets.count_documents({"appointment_id": apt_id, "status": "pending"})
    assert sheets == 0, "Orphaned sheets should be deleted"

    print("  OK TEST 1 — Single guaranteed → auto-waived, not_needed")


def test_2_two_guaranteed_stays():
    """2 guaranteed in manual_review → phase stays collecting (valid)."""
    _clean()
    apt_id = _create_scenario("two_g", [
        ("accepted_guaranteed", "manual_review", True),
        ("accepted_guaranteed", "manual_review", True),
    ])

    _run_guard_on(apt_id)

    apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
    assert apt["declarative_phase"] == "collecting", \
        f"Phase should stay collecting, got {apt['declarative_phase']}"

    reviews = db.attendance_records.count_documents(
        {"appointment_id": apt_id, "outcome": "manual_review"}
    )
    assert reviews == 2, f"Both review records should remain, got {reviews}"

    print("  OK TEST 2 — Two guaranteed → phase stays collecting")


def test_3_zero_guaranteed():
    """Only non-guaranteed in manual_review → auto-waive, not_needed."""
    _clean()
    apt_id = _create_scenario("zero_g", [
        ("accepted", "manual_review", True),
        ("accepted_pending_guarantee", "manual_review", True),
    ])

    _run_guard_on(apt_id)

    apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
    assert apt["declarative_phase"] == "not_needed", \
        f"Phase should be not_needed, got {apt['declarative_phase']}"

    print("  OK TEST 3 — Zero guaranteed → auto-waived, not_needed")


def test_4_mixed_one_guaranteed():
    """1 guaranteed + 1 non-guaranteed → auto-waive (< 2 guaranteed)."""
    _clean()
    apt_id = _create_scenario("mixed", [
        ("accepted_guaranteed", "manual_review", True),
        ("accepted", "manual_review", True),
    ])

    _run_guard_on(apt_id)

    apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
    assert apt["declarative_phase"] == "not_needed", \
        f"Phase should be not_needed, got {apt['declarative_phase']}"

    reviews = db.attendance_records.count_documents(
        {"appointment_id": apt_id, "outcome": "manual_review"}
    )
    assert reviews == 0, f"All review records should be waived, got {reviews}"

    print("  OK TEST 4 — Mixed (1 guaranteed + 1 non) → auto-waived")


def test_5_resolved_not_touched():
    """Already resolved phases are untouched."""
    _clean()
    apt_id = _create_scenario("resolved", [
        ("accepted_guaranteed", "waived", False),
    ], phase="resolved")

    _run_guard_on(apt_id)

    apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
    assert apt["declarative_phase"] == "resolved", \
        f"Phase should stay resolved, got {apt['declarative_phase']}"

    print("  OK TEST 5 — Resolved phase not touched")


if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("TESTS — Retroactive Guard (orphaned collecting fix)")
    print("=" * 65)

    tests = [
        test_1_single_guaranteed,
        test_2_two_guaranteed_stays,
        test_3_zero_guaranteed,
        test_4_mixed_one_guaranteed,
        test_5_resolved_not_touched,
    ]

    total = len(tests)
    passed = 0
    failed = 0

    for fn in tests:
        try:
            fn()
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {fn.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"  ERROR {fn.__name__}: {e}")

    _clean()

    print(f"\n{'=' * 65}")
    print(f"RESULTAT: {passed}/{total} PASS | {failed} FAIL")
    print("=" * 65)

    if failed > 0:
        sys.exit(1)
    else:
        print("\nTous les tests du guard retroactif sont PASSES.\n")
