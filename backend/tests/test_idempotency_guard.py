"""Tests for P0 fixes: idempotency guard on initialize_declarative_phase
and is_self_declaration preservation in submit_sheet.
"""
import sys, os
sys.path.insert(0, "/app/backend")
os.environ.setdefault("DB_NAME", "test_database")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")

from database import db
import uuid

# ─── Helpers ───
org_user_id = "d13498f9-9c0d-47d4-b48f-9e327e866127"
par_user_id = "239d1bbc-a4ea-47ac-b3c8-2f02f0769ef7"

def create_test_appointment(suffix):
    apt_id = f"test-idem-{suffix}-{uuid.uuid4().hex[:8]}"
    org_pid = f"org-{suffix}-{uuid.uuid4().hex[:8]}"
    par_pid = f"par-{suffix}-{uuid.uuid4().hex[:8]}"
    db.appointments.insert_one({
        "appointment_id": apt_id,
        "organizer_id": org_user_id,
        "title": f"Test idempotency {suffix}",
        "start_datetime": "2026-03-27T10:00:00Z",
        "duration_minutes": 60,
        "appointment_type": "physical",
        "status": "active",
        "declarative_phase": None,
        "workspace_id": "test-ws",
    })
    db.participants.insert_many([
        {"participant_id": org_pid, "appointment_id": apt_id, "user_id": org_user_id,
         "email": "testuser_audit@nlyt.app", "status": "accepted_guaranteed", "is_organizer": True},
        {"participant_id": par_pid, "appointment_id": apt_id, "user_id": par_user_id,
         "email": "igaal@hotmail.com", "status": "accepted_guaranteed", "is_organizer": False},
    ])
    db.attendance_records.insert_many([
        {"record_id": str(uuid.uuid4()), "appointment_id": apt_id, "participant_id": org_pid,
         "outcome": "on_time", "review_required": False, "decided_by": "system"},
        {"record_id": str(uuid.uuid4()), "appointment_id": apt_id, "participant_id": par_pid,
         "outcome": "manual_review", "review_required": True, "decided_by": "system"},
    ])
    return apt_id, org_pid, par_pid

def cleanup(apt_id):
    for coll in ['appointments', 'participants', 'attendance_records', 'attendance_sheets',
                 'declarative_analyses', 'declarative_disputes']:
        db[coll].delete_many({"appointment_id": apt_id})

passed = 0
failed = 0

# ═══════════════════════════════════════════════════════════════
# TEST 1: Guard blocks re-entry when phase is already 'collecting'
# ═══════════════════════════════════════════════════════════════
print("=== TEST 1: Guard blocks re-entry on 'collecting' ===")
apt_id, org_pid, par_pid = create_test_appointment("t1")

from services.declarative_service import initialize_declarative_phase
initialize_declarative_phase(apt_id)

apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
deadline1 = apt.get("declarative_deadline")
sheets_before = db.attendance_sheets.count_documents({"appointment_id": apt_id})
assert apt.get("declarative_phase") == "collecting", "Phase should be collecting"
print(f"  Phase after 1st init: {apt.get('declarative_phase')}, deadline: {deadline1[:19]}")

# Call again — should be blocked by guard
import time
time.sleep(0.1)  # Ensure different timestamp
initialize_declarative_phase(apt_id)

apt2 = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
deadline2 = apt2.get("declarative_deadline")
sheets_after = db.attendance_sheets.count_documents({"appointment_id": apt_id})
assert deadline2 == deadline1, f"Deadline should NOT change on re-entry: {deadline2} != {deadline1}"
assert sheets_after == sheets_before, "No new sheets should be created"
print(f"  Phase after 2nd init: {apt2.get('declarative_phase')}, deadline: {deadline2[:19]}")
print(f"  Sheets before/after: {sheets_before}/{sheets_after}")
print("  PASSED: Re-entry blocked, deadline unchanged, no duplicate sheets")
passed += 1
cleanup(apt_id)

# ═══════════════════════════════════════════════════════════════
# TEST 2: Guard blocks re-entry on 'analyzing'
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 2: Guard blocks re-entry on 'analyzing' ===")
apt_id, org_pid, par_pid = create_test_appointment("t2")
initialize_declarative_phase(apt_id)

# Simulate phase advancing to 'analyzing'
db.appointments.update_one({"appointment_id": apt_id}, {"$set": {"declarative_phase": "analyzing"}})
initialize_declarative_phase(apt_id)

apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
assert apt.get("declarative_phase") == "analyzing", "Phase should still be analyzing"
print(f"  Phase: {apt.get('declarative_phase')}")
print("  PASSED: Re-entry blocked on 'analyzing'")
passed += 1
cleanup(apt_id)

# ═══════════════════════════════════════════════════════════════
# TEST 3: Guard blocks re-entry on 'disputed'
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 3: Guard blocks re-entry on 'disputed' ===")
apt_id, org_pid, par_pid = create_test_appointment("t3")
initialize_declarative_phase(apt_id)

db.appointments.update_one({"appointment_id": apt_id}, {"$set": {"declarative_phase": "disputed"}})
initialize_declarative_phase(apt_id)

apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
assert apt.get("declarative_phase") == "disputed", "Phase should still be disputed"
print(f"  Phase: {apt.get('declarative_phase')}")
print("  PASSED: Re-entry blocked on 'disputed'")
passed += 1
cleanup(apt_id)

# ═══════════════════════════════════════════════════════════════
# TEST 4: Guard blocks re-entry on 'resolved'
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 4: Guard blocks re-entry on 'resolved' ===")
apt_id, org_pid, par_pid = create_test_appointment("t4")
initialize_declarative_phase(apt_id)

db.appointments.update_one({"appointment_id": apt_id}, {"$set": {"declarative_phase": "resolved"}})
initialize_declarative_phase(apt_id)

apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
assert apt.get("declarative_phase") == "resolved", "Phase should still be resolved"
print(f"  Phase: {apt.get('declarative_phase')}")
print("  PASSED: Re-entry blocked on 'resolved'")
passed += 1
cleanup(apt_id)

# ═══════════════════════════════════════════════════════════════
# TEST 5: Guard ALLOWS entry from 'not_needed' (legitimate re-init)
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 5: Guard allows entry from 'not_needed' ===")
apt_id, org_pid, par_pid = create_test_appointment("t5")
db.appointments.update_one({"appointment_id": apt_id}, {"$set": {"declarative_phase": "not_needed"}})

initialize_declarative_phase(apt_id)

apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
assert apt.get("declarative_phase") == "collecting", f"Phase should transition to collecting, got: {apt.get('declarative_phase')}"
sheets = db.attendance_sheets.count_documents({"appointment_id": apt_id})
assert sheets > 0, "Sheets should be created"
print(f"  Phase: {apt.get('declarative_phase')}, Sheets: {sheets}")
print("  PASSED: Legitimate initialization from 'not_needed' allowed")
passed += 1
cleanup(apt_id)

# ═══════════════════════════════════════════════════════════════
# TEST 6: Guard ALLOWS first entry (no phase set)
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 6: Guard allows first entry (phase=None) ===")
apt_id, org_pid, par_pid = create_test_appointment("t6")
# Phase is None by default from create_test_appointment

apt_before = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
assert apt_before.get("declarative_phase") is None, "Phase should be None before first init"

initialize_declarative_phase(apt_id)

apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
assert apt.get("declarative_phase") == "collecting", "Phase should be collecting after first init"
sheets = db.attendance_sheets.count_documents({"appointment_id": apt_id})
assert sheets == 2, f"2 sheets expected, got {sheets}"
print(f"  Phase: {apt.get('declarative_phase')}, Sheets: {sheets}")
print("  PASSED: First initialization works correctly")
passed += 1
cleanup(apt_id)

# ═══════════════════════════════════════════════════════════════
# TEST 7: is_self_declaration preserved through submit_sheet
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 7: is_self_declaration preserved in submit_sheet ===")
apt_id, org_pid, par_pid = create_test_appointment("t7")
initialize_declarative_phase(apt_id)

# Check that sheets have is_self_declaration set correctly
par_sheet = db.attendance_sheets.find_one({
    "appointment_id": apt_id,
    "submitted_by_user_id": par_user_id,
}, {"_id": 0})

# Participant's sheet should have self-declaration
self_decl = [d for d in par_sheet.get("declarations", []) if d.get("is_self_declaration")]
non_self = [d for d in par_sheet.get("declarations", []) if not d.get("is_self_declaration")]
print(f"  Pre-submit: self_declarations={len(self_decl)}, non_self={len(non_self)}")
assert len(self_decl) == 1, f"Expected 1 self-declaration, got {len(self_decl)}"

# Submit the participant's sheet
from services.declarative_service import submit_sheet
result = submit_sheet(apt_id, par_user_id, [
    {"target_participant_id": par_pid, "declared_status": "present_on_time"},
])
assert result.get("success"), f"Submit failed: {result}"

# Verify is_self_declaration is preserved
par_sheet_after = db.attendance_sheets.find_one({
    "appointment_id": apt_id,
    "submitted_by_user_id": par_user_id,
}, {"_id": 0})
self_decl_after = [d for d in par_sheet_after.get("declarations", []) if d.get("is_self_declaration")]
print(f"  Post-submit: self_declarations={len(self_decl_after)}")
assert len(self_decl_after) == 1, f"is_self_declaration LOST after submit! Got {len(self_decl_after)}"
assert self_decl_after[0]["declared_status"] == "present_on_time"
print("  PASSED: is_self_declaration preserved through submit_sheet")
passed += 1
cleanup(apt_id)

# ═══════════════════════════════════════════════════════════════
# TEST 8: Full flow — 1v1 disagreement triggers dispute (not blocked)
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 8: Full 1v1 flow with guard active ===")
apt_id, org_pid, par_pid = create_test_appointment("t8")
initialize_declarative_phase(apt_id)

# Submit organizer: declares participant absent
result_org = submit_sheet(apt_id, org_user_id, [
    {"target_participant_id": par_pid, "declared_status": "absent"},
])
assert result_org.get("success"), f"Org submit failed: {result_org}"

# Submit participant: declares self present
result_par = submit_sheet(apt_id, par_user_id, [
    {"target_participant_id": par_pid, "declared_status": "present_on_time"},
])
assert result_par.get("success"), f"Par submit failed: {result_par}"

# Check results
apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
disputes = list(db.declarative_disputes.find({"appointment_id": apt_id}, {"_id": 0}))
analysis = db.declarative_analyses.find_one({"appointment_id": apt_id}, {"_id": 0})

assert apt.get("declarative_phase") == "disputed", f"Expected 'disputed', got '{apt.get('declarative_phase')}'"
assert len(disputes) == 1, f"Expected 1 dispute, got {len(disputes)}"
assert disputes[0]["opened_reason"] == "small_group_disagreement"
assert analysis is not None
print(f"  Phase: {apt.get('declarative_phase')}, Disputes: {len(disputes)}")
print(f"  Dispute reason: {disputes[0]['opened_reason']}")

# Now try to re-initialize — guard should block
initialize_declarative_phase(apt_id)
apt_after = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
assert apt_after.get("declarative_phase") == "disputed", "Guard should prevent overwriting 'disputed'"
print("  Guard correctly blocked re-init after dispute creation")
print("  PASSED: Full flow works correctly with guard active")
passed += 1
cleanup(apt_id)

# ═══════════════════════════════════════════════════════════════
# TEST 9: Full flow — 1v1 agreement auto-resolves
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 9: Full 1v1 agreement auto-resolves ===")
apt_id, org_pid, par_pid = create_test_appointment("t9")
initialize_declarative_phase(apt_id)

# Both declare present
submit_sheet(apt_id, org_user_id, [
    {"target_participant_id": par_pid, "declared_status": "present_on_time"},
])
submit_sheet(apt_id, par_user_id, [
    {"target_participant_id": par_pid, "declared_status": "present_on_time"},
])

apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
disputes = db.declarative_disputes.count_documents({"appointment_id": apt_id})
record = db.attendance_records.find_one({
    "appointment_id": apt_id, "participant_id": par_pid}, {"_id": 0})

assert apt.get("declarative_phase") == "resolved", f"Expected 'resolved', got '{apt.get('declarative_phase')}'"
assert disputes == 0, "No dispute on agreement"
assert record.get("outcome") == "on_time", f"Outcome should be on_time, got {record.get('outcome')}"
assert record.get("decision_source") == "declarative"
print(f"  Phase: {apt.get('declarative_phase')}, Outcome: {record.get('outcome')}")
print("  PASSED: Agreement auto-resolves to on_time")
passed += 1
cleanup(apt_id)

# ═══════════════════════════════════════════════════════════════
print(f"\n{'=' * 50}")
print(f"  {passed} PASSED, {failed} FAILED")
print(f"{'=' * 50}")
if failed > 0:
    exit(1)
