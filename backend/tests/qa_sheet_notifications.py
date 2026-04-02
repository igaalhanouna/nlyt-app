"""
QA — Notifications Feuilles de Présence (Équité déclarative)
==============================================================
Tests des 4 axes :
1. Email à l'ouverture de la phase (avec/sans compte)
2. Relance 12h avant deadline (avec/sans compte)
3. Participants sans compte ne sont plus exclus
4. Auto-linkage des sheets au login
5. submit_sheet fonctionne après auto-linkage
"""
import sys
import os
import uuid
import time

sys.path.insert(0, '/app/backend')
os.chdir('/app/backend')

from dotenv import load_dotenv
load_dotenv()

from database import db
from datetime import timedelta
from utils.date_utils import now_utc

RESULTS = []
PREFIX = "qa_sheet_"


def record(test_id, desc, passed, detail=""):
    status = "OK" if passed else "KO"
    RESULTS.append({"id": test_id, "status": status, "detail": detail})
    icon = "PASS" if passed else "FAIL"
    print(f"  [{icon}] {test_id}: {desc}" + (f" — {detail}" if detail else ""))


def cleanup():
    for col in ['appointments', 'participants', 'attendance_records',
                 'attendance_sheets', 'declarative_disputes', 'declarative_analyses',
                 'user_notifications', 'email_attempts', 'payment_guarantees']:
        db[col].delete_many({"appointment_id": {"$regex": f"^{PREFIX}"}})
    db.user_notifications.delete_many({"user_id": {"$regex": f"^{PREFIX}"}})
    db.user_notifications.delete_many({"reference_id": {"$regex": f"^{PREFIX}"}})
    db.email_attempts.delete_many({"email": {"$regex": "sheettest"}})


def setup_full_scenario():
    """Create a complete scenario: appointment with 3 guaranteed participants (org + 2 participants).
    One participant has an account, the other does NOT."""
    apt_id = f"{PREFIX}apt_1"
    org_uid = f"{PREFIX}org_uid"
    org_email = "sheettest_org@test.nlyt.io"
    p1_uid = f"{PREFIX}uid_p1"
    p1_email = "sheettest_p1@test.nlyt.io"
    p1_pid = f"{PREFIX}pid_p1"
    p2_email = "sheettest_p2_noaccount@test.nlyt.io"
    p2_pid = f"{PREFIX}pid_p2"

    # Create user accounts
    db.users.update_one(
        {"user_id": org_uid},
        {"$set": {"user_id": org_uid, "email": org_email, "first_name": "Org", "last_name": "Test"}},
        upsert=True
    )
    db.users.update_one(
        {"user_id": p1_uid},
        {"$set": {"user_id": p1_uid, "email": p1_email, "first_name": "Alice", "last_name": "Account"}},
        upsert=True
    )

    # Appointment
    db.appointments.insert_one({
        "appointment_id": apt_id,
        "organizer_id": org_uid,
        "title": "Reunion Test Sheets",
        "status": "active",
        "start_datetime": (now_utc() - timedelta(hours=3)).isoformat(),
        "duration_minutes": 60,
        "penalty_amount": 50,
        "penalty_currency": "eur",
        "location": "Paris 15e",
        "timezone": "Europe/Paris",
        "cancellation_deadline_hours": 24,
        "tolerated_delay_minutes": 5,
        "appointment_type": "physical",
        "platform_commission_percent": 20,
        "affected_compensation_percent": 50,
        "charity_percent": 0,
        "attendance_evaluated": True,
        "declarative_phase": None,
    })

    # Participants
    db.participants.insert_one({
        "participant_id": f"{PREFIX}pid_org",
        "appointment_id": apt_id, "user_id": org_uid, "email": org_email,
        "first_name": "Org", "last_name": "Test",
        "is_organizer": True, "status": "accepted_guaranteed",
        "invitation_token": str(uuid.uuid4()),
    })
    db.participants.insert_one({
        "participant_id": p1_pid,
        "appointment_id": apt_id, "user_id": p1_uid, "email": p1_email,
        "first_name": "Alice", "last_name": "Account",
        "is_organizer": False, "status": "accepted_guaranteed",
        "invitation_token": str(uuid.uuid4()),
    })
    db.participants.insert_one({
        "participant_id": p2_pid,
        "appointment_id": apt_id, "user_id": None, "email": p2_email,
        "first_name": "Bob", "last_name": "NoAccount",
        "is_organizer": False, "status": "accepted_guaranteed",
        "invitation_token": str(uuid.uuid4()),
    })

    # Attendance records (all in manual_review)
    for pid in [f"{PREFIX}pid_org", p1_pid, p2_pid]:
        db.attendance_records.insert_one({
            "record_id": f"{PREFIX}rec_{pid[-4:]}",
            "appointment_id": apt_id,
            "participant_id": pid,
            "outcome": "manual_review",
            "review_required": True,
            "decided_by": "system",
            "decided_at": now_utc().isoformat(),
        })

    return apt_id, org_uid, p1_uid, p1_pid, p1_email, p2_pid, p2_email


# ═══════════════════════════════════════════════════════════════
# TEST 1: Participants sans compte ne sont plus exclus
# ═══════════════════════════════════════════════════════════════
def test_1_no_account_not_excluded():
    print("\n=== TEST 1: Participants sans compte ne sont plus exclus ===")
    cleanup()
    apt_id, org_uid, p1_uid, p1_pid, p1_email, p2_pid, p2_email = setup_full_scenario()

    from services.declarative_service import initialize_declarative_phase
    initialize_declarative_phase(apt_id)
    time.sleep(1)

    # Check: sheet created for participant WITH account
    sheet_p1 = db.attendance_sheets.find_one({
        "appointment_id": apt_id,
        "submitted_by_participant_id": p1_pid,
    }, {"_id": 0})
    record("T1-P1", "Sheet creee pour participant AVEC compte", sheet_p1 is not None)

    # Check: sheet created for participant WITHOUT account
    sheet_p2 = db.attendance_sheets.find_one({
        "appointment_id": apt_id,
        "submitted_by_participant_id": p2_pid,
    }, {"_id": 0})
    record("T1-P2", "Sheet creee pour participant SANS compte", sheet_p2 is not None,
           f"submitted_by_user_id={sheet_p2.get('submitted_by_user_id') if sheet_p2 else 'N/A'}")

    # Total sheets
    total = db.attendance_sheets.count_documents({"appointment_id": apt_id})
    record("T1-COUNT", "Nombre total de sheets correct (3: org+p1+p2)", total == 3,
           f"total={total}")


# ═══════════════════════════════════════════════════════════════
# TEST 2: Email envoyé à l'ouverture
# ═══════════════════════════════════════════════════════════════
def test_2_emails_at_phase_start():
    print("\n=== TEST 2: Emails envoyés à l'ouverture de la phase ===")

    # Emails should have been sent during test_1's initialize_declarative_phase
    time.sleep(0.5)

    # P1 (with account): should have email
    e_p1 = db.email_attempts.find_one({"email": "sheettest_p1@test.nlyt.io", "email_type": "sheet_pending"}, {"_id": 0})
    record("T2-P1-EMAIL", "Participant AVEC compte: email envoye", e_p1 is not None,
           e_p1.get("status") if e_p1 else "AUCUN")

    # P1 (with account): should have in-app notification
    n_p1 = db.user_notifications.find_one({
        "user_id": f"{PREFIX}uid_p1", "event_type": "sheet_pending"
    }, {"_id": 0})
    record("T2-P1-NOTIF", "Participant AVEC compte: notification in-app", n_p1 is not None)

    # P2 (without account): should have email
    e_p2 = db.email_attempts.find_one({"email": "sheettest_p2_noaccount@test.nlyt.io", "email_type": "sheet_pending"}, {"_id": 0})
    record("T2-P2-EMAIL", "Participant SANS compte: email envoye", e_p2 is not None,
           e_p2.get("status") if e_p2 else "AUCUN EMAIL — CRITIQUE")

    # Org: should have email too
    e_org = db.email_attempts.find_one({"email": "sheettest_org@test.nlyt.io", "email_type": "sheet_pending"}, {"_id": 0})
    record("T2-ORG-EMAIL", "Organisateur: email envoye", e_org is not None)


# ═══════════════════════════════════════════════════════════════
# TEST 3: Idempotence
# ═══════════════════════════════════════════════════════════════
def test_3_idempotence():
    print("\n=== TEST 3: Idempotence ===")

    # Re-run notifications (simulate double trigger)
    all_sheets = list(db.attendance_sheets.find(
        {"appointment_id": f"{PREFIX}apt_1", "status": "pending"},
        {"_id": 0}
    ))
    from services.notification_service import notify_sheets_created
    notify_sheets_created(f"{PREFIX}apt_1", all_sheets)
    time.sleep(0.5)

    # Count emails for p1
    count = db.email_attempts.count_documents({"email": "sheettest_p1@test.nlyt.io", "email_type": "sheet_pending"})
    record("T3-IDEMP", "Pas de doublon email apres double appel", count == 1, f"count={count}")


# ═══════════════════════════════════════════════════════════════
# TEST 4: Relance avant deadline
# ═══════════════════════════════════════════════════════════════
def test_4_reminder():
    print("\n=== TEST 4: Relance avant deadline ===")

    # Set the deadline to 6 hours from now (within 12h window)
    short_deadline = (now_utc() + timedelta(hours=6)).isoformat()
    db.appointments.update_one(
        {"appointment_id": f"{PREFIX}apt_1"},
        {"$set": {"declarative_deadline": short_deadline}}
    )
    # Update sheets' deadline too
    db.attendance_sheets.update_many(
        {"appointment_id": f"{PREFIX}apt_1"},
        {"$set": {"deadline": short_deadline}}
    )

    from services.declarative_service import run_sheet_reminder_job
    run_sheet_reminder_job()
    time.sleep(0.5)

    # P1 should have a reminder
    r_p1 = db.email_attempts.find_one({"email": "sheettest_p1@test.nlyt.io", "email_type": "sheet_reminder"}, {"_id": 0})
    record("T4-P1-REMIND", "Relance envoyee au participant AVEC compte", r_p1 is not None,
           r_p1.get("status") if r_p1 else "AUCUN")

    # P2 (no account) should also have a reminder
    r_p2 = db.email_attempts.find_one({"email": "sheettest_p2_noaccount@test.nlyt.io", "email_type": "sheet_reminder"}, {"_id": 0})
    record("T4-P2-REMIND", "Relance envoyee au participant SANS compte", r_p2 is not None,
           r_p2.get("status") if r_p2 else "AUCUN — CRITIQUE")

    # Idempotence: run again
    run_sheet_reminder_job()
    time.sleep(0.3)
    count = db.email_attempts.count_documents({"email": "sheettest_p1@test.nlyt.io", "email_type": "sheet_reminder"})
    record("T4-IDEMP", "Relance: pas de doublon", count == 1, f"count={count}")


# ═══════════════════════════════════════════════════════════════
# TEST 5: Auto-linkage des sheets au login
# ═══════════════════════════════════════════════════════════════
def test_5_auto_linkage_sheets():
    print("\n=== TEST 5: Auto-linkage des sheets au login ===")

    p2_pid = f"{PREFIX}pid_p2"
    p2_email = "sheettest_p2_noaccount@test.nlyt.io"
    new_uid = f"{PREFIX}uid_p2_new"

    # Before linkage: sheet should have email as submitted_by_user_id
    sheet_before = db.attendance_sheets.find_one({
        "appointment_id": f"{PREFIX}apt_1",
        "submitted_by_participant_id": p2_pid,
    }, {"_id": 0})
    record("T5-BEFORE", "Sheet avant linkage: user_id = email placeholder",
           sheet_before is not None and sheet_before.get("submitted_by_user_id") == p2_email,
           f"submitted_by_user_id={sheet_before.get('submitted_by_user_id') if sheet_before else 'N/A'}")

    # Simulate login: user creates account and auto-linkage runs
    from services.auth_service import _auto_link_user_to_participants
    _auto_link_user_to_participants(new_uid, p2_email)

    # After linkage: sheet should have the real user_id
    sheet_after = db.attendance_sheets.find_one({
        "appointment_id": f"{PREFIX}apt_1",
        "submitted_by_participant_id": p2_pid,
    }, {"_id": 0})
    record("T5-AFTER", "Sheet apres linkage: user_id = vrai user_id",
           sheet_after is not None and sheet_after.get("submitted_by_user_id") == new_uid,
           f"submitted_by_user_id={sheet_after.get('submitted_by_user_id') if sheet_after else 'N/A'}")

    # Participant should also be linked
    part = db.participants.find_one({"participant_id": p2_pid}, {"_id": 0})
    record("T5-PART", "Participant lie au user_id",
           part is not None and part.get("user_id") == new_uid)


# ═══════════════════════════════════════════════════════════════
# TEST 6: submit_sheet fonctionne après auto-linkage
# ═══════════════════════════════════════════════════════════════
def test_6_submit_after_linkage():
    print("\n=== TEST 6: submit_sheet après auto-linkage ===")

    new_uid = f"{PREFIX}uid_p2_new"
    apt_id = f"{PREFIX}apt_1"

    # Make sure phase is still collecting
    db.appointments.update_one(
        {"appointment_id": apt_id},
        {"$set": {"declarative_phase": "collecting"}}
    )

    # Find the sheet to get targets
    sheet = db.attendance_sheets.find_one({
        "appointment_id": apt_id,
        "submitted_by_user_id": new_uid,
    }, {"_id": 0})

    if not sheet:
        record("T6-FIND", "Sheet trouvee par user_id apres linkage", False, "Sheet non trouvee")
        return

    record("T6-FIND", "Sheet trouvee par user_id apres linkage", True)

    # Submit declarations (including self-declaration — required by submit_sheet)
    decls = []
    for d in sheet["declarations"]:
        decls.append({
            "target_participant_id": d["target_participant_id"],
            "declared_status": "present_on_time",
        })

    from services.declarative_service import submit_sheet
    result = submit_sheet(apt_id, new_uid, decls)

    if result.get("error"):
        record("T6-SUBMIT", "submit_sheet reussit apres auto-linkage", False, result["error"])
    else:
        record("T6-SUBMIT", "submit_sheet reussit apres auto-linkage", True)

    # Verify sheet is submitted
    updated = db.attendance_sheets.find_one({"sheet_id": sheet["sheet_id"]}, {"_id": 0})
    record("T6-STATUS", "Sheet status = submitted",
           updated and updated.get("status") == "submitted",
           f"status={updated.get('status') if updated else 'N/A'}")


# ═══════════════════════════════════════════════════════════════
# TEST 7: submit_sheet fallback par participant_id
# ═══════════════════════════════════════════════════════════════
def test_7_submit_fallback():
    print("\n=== TEST 7: submit_sheet fallback par participant_id ===")
    # Create a new scenario where user just registered but sheet not yet linked
    cleanup()
    apt_id = f"{PREFIX}apt_fb"
    org_uid = f"{PREFIX}org_fb"
    p_uid = f"{PREFIX}uid_fb"
    p_pid = f"{PREFIX}pid_fb"
    p_email = "sheettest_fb@test.nlyt.io"

    db.users.update_one(
        {"user_id": org_uid},
        {"$set": {"user_id": org_uid, "email": "sheettest_orgfb@test.nlyt.io", "first_name": "Org", "last_name": "FB"}},
        upsert=True
    )

    db.appointments.insert_one({
        "appointment_id": apt_id, "organizer_id": org_uid,
        "title": "Test Fallback", "status": "active",
        "start_datetime": (now_utc() - timedelta(hours=2)).isoformat(),
        "duration_minutes": 60, "penalty_amount": 30, "penalty_currency": "eur",
        "location": "Lyon", "timezone": "Europe/Paris",
        "declarative_phase": "collecting",
        "declarative_deadline": (now_utc() + timedelta(hours=40)).isoformat(),
    })

    # Participant linked to user_id
    db.participants.insert_one({
        "participant_id": p_pid, "appointment_id": apt_id,
        "user_id": p_uid, "email": p_email,
        "first_name": "Test", "last_name": "Fallback",
        "is_organizer": False, "status": "accepted_guaranteed",
    })

    # Sheet still has email as owner (auto-linkage not yet run for sheets)
    org_pid = f"{PREFIX}pid_org_fb"
    db.participants.insert_one({
        "participant_id": org_pid, "appointment_id": apt_id,
        "user_id": org_uid, "email": "sheettest_orgfb@test.nlyt.io",
        "first_name": "Org", "last_name": "FB",
        "is_organizer": True, "status": "accepted_guaranteed",
    })

    db.attendance_sheets.insert_one({
        "sheet_id": f"{PREFIX}sheet_fb",
        "appointment_id": apt_id,
        "submitted_by_user_id": p_email,  # email placeholder, not real user_id
        "submitted_by_participant_id": p_pid,
        "status": "pending",
        "submitted_at": None,
        "declarations": [
            {"target_participant_id": org_pid, "target_user_id": org_uid,
             "declared_status": None, "is_self_declaration": False}
        ],
        "created_at": now_utc().isoformat(),
        "deadline": (now_utc() + timedelta(hours=40)).isoformat(),
    })

    # submit_sheet with the real user_id (should fallback to participant_id lookup)
    from services.declarative_service import submit_sheet
    result = submit_sheet(apt_id, p_uid, [
        {"target_participant_id": org_pid, "declared_status": "present_on_time"}
    ])

    if result.get("error"):
        record("T7-FALLBACK", "submit_sheet fallback par participant_id", False, result["error"])
    else:
        record("T7-FALLBACK", "submit_sheet fallback par participant_id", True)

    # Check sheet user_id was auto-fixed
    fixed = db.attendance_sheets.find_one({"sheet_id": f"{PREFIX}sheet_fb"}, {"_id": 0})
    record("T7-FIX", "Sheet user_id corrige apres submit",
           fixed and fixed.get("submitted_by_user_id") == p_uid,
           f"user_id={fixed.get('submitted_by_user_id') if fixed else 'N/A'}")


if __name__ == "__main__":
    print("=" * 70)
    print("QA NOTIFICATIONS FEUILLES DE PRESENCE — Equite declarative")
    print("=" * 70)

    tests = [
        ("T1", test_1_no_account_not_excluded),
        ("T2", test_2_emails_at_phase_start),
        ("T3", test_3_idempotence),
        ("T4", test_4_reminder),
        ("T5", test_5_auto_linkage_sheets),
        ("T6", test_6_submit_after_linkage),
        ("T7", test_7_submit_fallback),
    ]

    for name, fn in tests:
        try:
            fn()
        except Exception as e:
            record(name, f"CRASH: {str(e)[:150]}", False, str(e))
            import traceback
            traceback.print_exc()

    cleanup()
    db.users.delete_many({"user_id": {"$regex": f"^{PREFIX}"}})

    print("\n" + "=" * 70)
    print("RESULTATS")
    print("=" * 70)
    passed = sum(1 for r in RESULTS if r["status"] == "OK")
    failed = sum(1 for r in RESULTS if r["status"] == "KO")
    total = len(RESULTS)
    print(f"\n  {passed}/{total} OK — {failed}/{total} KO\n")
    if failed > 0:
        print("  ECHECS:")
        for r in RESULTS:
            if r["status"] == "KO":
                print(f"    [{r['id']}] {r['description'] if 'description' in r else ''}")
                if r.get("detail"):
                    print(f"           {r['detail']}")
    print()
