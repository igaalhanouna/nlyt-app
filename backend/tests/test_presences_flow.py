"""Integration test: 1-vs-1 scenario — manual_review → Presences → Litiges.
Verifies that no dispute can be created without going through Presences first.
"""
import sys, os
sys.path.insert(0, "/app/backend")
os.environ.setdefault("DB_NAME", "test_database")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")

from database import db
import uuid
from datetime import datetime, timezone

# ─── Setup: create a test appointment (1-vs-1) ───
apt_id = f"test-1v1-{uuid.uuid4().hex[:8]}"
org_user_id = "d13498f9-9c0d-47d4-b48f-9e327e866127"  # testuser_audit
par_user_id = "239d1bbc-a4ea-47ac-b3c8-2f02f0769ef7"  # igaal@hotmail.com
org_pid = f"org-pid-{uuid.uuid4().hex[:8]}"
par_pid = f"par-pid-{uuid.uuid4().hex[:8]}"

# Create appointment
db.appointments.insert_one({
    "appointment_id": apt_id,
    "organizer_id": org_user_id,
    "title": "Test 1-vs-1 Presences",
    "start_datetime": "2026-03-27T10:00:00Z",
    "duration_minutes": 60,
    "appointment_type": "physical",
    "status": "completed",
    "declarative_phase": None,
})

# Create participants (organizer + 1 participant)
db.participants.insert_one({
    "participant_id": org_pid,
    "appointment_id": apt_id,
    "user_id": org_user_id,
    "email": "testuser_audit@nlyt.app",
    "first_name": "Test",
    "last_name": "Audit",
    "status": "accepted_guaranteed",
    "role": "organizer",
})
db.participants.insert_one({
    "participant_id": par_pid,
    "appointment_id": apt_id,
    "user_id": par_user_id,
    "email": "igaal@hotmail.com",
    "first_name": "Igaal",
    "last_name": "Hotmail",
    "status": "accepted_guaranteed",
    "role": "participant",
})

# Create attendance record: ONLY participant is manual_review (organizer had GPS)
db.attendance_records.insert_one({
    "record_id": str(uuid.uuid4()),
    "appointment_id": apt_id,
    "participant_id": par_pid,
    "outcome": "manual_review",
    "review_required": True,
    "decision_basis": "no_proof_of_attendance",
})
# Organizer has strong proof (won't be in manual_review)
db.attendance_records.insert_one({
    "record_id": str(uuid.uuid4()),
    "appointment_id": apt_id,
    "participant_id": org_pid,
    "outcome": "on_time",
    "review_required": False,
    "decision_basis": "admissible_proof_on_time",
})

print(f"Setup complete: apt={apt_id}")
print(f"  org_pid={org_pid}, par_pid={par_pid}")
print()

# ─── Test 1: Initialize declarative phase ───
print("═══ TEST 1: Initialize declarative phase (1-vs-1) ═══")
from services.declarative_service import initialize_declarative_phase
initialize_declarative_phase(apt_id)

apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0, "declarative_phase": 1})
print(f"  Phase: {apt.get('declarative_phase')}")
assert apt.get('declarative_phase') == 'collecting', f"FAIL: Expected 'collecting', got '{apt.get('declarative_phase')}'"
print("  ✅ Phase is 'collecting' (not 'disputed' — bypass removed)")

# ─── Test 2: Check sheets created ───
print()
print("═══ TEST 2: Verify sheets created ═══")
sheets = list(db.attendance_sheets.find({"appointment_id": apt_id}, {"_id": 0}))
print(f"  Sheets created: {len(sheets)}")
assert len(sheets) == 2, f"FAIL: Expected 2 sheets, got {len(sheets)}"

for s in sheets:
    user = s.get('submitted_by_user_id')
    targets = s.get('declarations', [])
    is_org = user == org_user_id
    role = "organizer" if is_org else "participant"
    print(f"  Sheet for {role} ({user[:8]}): {len(targets)} target(s)")
    for t in targets:
        self_flag = t.get('is_self_declaration', False)
        print(f"    target={t['target_participant_id'][:8]}... is_self={self_flag}")

# Verify: organizer sheet has 1 target (participant, not self since org isn't in review)
org_sheet = next(s for s in sheets if s['submitted_by_user_id'] == org_user_id)
assert len(org_sheet['declarations']) == 1
assert org_sheet['declarations'][0]['target_participant_id'] == par_pid
assert not org_sheet['declarations'][0].get('is_self_declaration', False)

# Verify: participant sheet has 1 target (SELF — since participant IS in manual_review)
par_sheet = next(s for s in sheets if s['submitted_by_user_id'] == par_user_id)
assert len(par_sheet['declarations']) == 1
assert par_sheet['declarations'][0]['target_participant_id'] == par_pid
assert par_sheet['declarations'][0].get('is_self_declaration') == True
print("  ✅ Sheets correct: organizer declares on participant, participant self-declares")

# ─── Test 3: No disputes exist yet ───
print()
print("═══ TEST 3: No disputes before Presences submission ═══")
disputes_before = list(db.declarative_disputes.find({"appointment_id": apt_id}, {"_id": 0}))
print(f"  Disputes: {len(disputes_before)}")
assert len(disputes_before) == 0, f"FAIL: Expected 0 disputes, got {len(disputes_before)}"
print("  ✅ No dispute created before going through Presences")

# ─── Test 4: Submit sheets — AGREEMENT ───
print()
print("═══ TEST 4a: Submit sheets with AGREEMENT (both say present) ═══")
from services.declarative_service import submit_sheet

# Organizer declares participant as present_on_time
result_org = submit_sheet(apt_id, org_user_id, [
    {"target_participant_id": par_pid, "declared_status": "present_on_time"}
])
print(f"  Organizer submit: {result_org}")

# Participant self-declares as present_on_time
result_par = submit_sheet(apt_id, par_user_id, [
    {"target_participant_id": par_pid, "declared_status": "present_on_time"}
])
print(f"  Participant submit: {result_par}")

# Check: should be resolved (agreement), NO dispute
apt_after = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0, "declarative_phase": 1})
disputes_after = list(db.declarative_disputes.find({"appointment_id": apt_id}, {"_id": 0}))
print(f"  Phase: {apt_after.get('declarative_phase')}")
print(f"  Disputes: {len(disputes_after)}")
assert apt_after.get('declarative_phase') == 'resolved', f"FAIL: Expected 'resolved', got {apt_after.get('declarative_phase')}"
assert len(disputes_after) == 0, f"FAIL: Expected 0 disputes after agreement"
print("  ✅ Agreement → resolved, no dispute created")

# ─── Test 5: Create another 1-vs-1 with DISAGREEMENT ───
print()
print("═══ TEST 5: 1-vs-1 with DISAGREEMENT ═══")
apt_id2 = f"test-1v1-disagree-{uuid.uuid4().hex[:8]}"
par_pid2 = f"par2-pid-{uuid.uuid4().hex[:8]}"
org_pid2 = f"org2-pid-{uuid.uuid4().hex[:8]}"

db.appointments.insert_one({
    "appointment_id": apt_id2,
    "organizer_id": org_user_id,
    "title": "Test 1-vs-1 Disagreement",
    "start_datetime": "2026-03-27T14:00:00Z",
    "duration_minutes": 30,
    "appointment_type": "physical",
    "status": "completed",
    "declarative_phase": None,
})
db.participants.insert_one({
    "participant_id": org_pid2,
    "appointment_id": apt_id2,
    "user_id": org_user_id,
    "email": "testuser_audit@nlyt.app",
    "first_name": "Test",
    "last_name": "Audit",
    "status": "accepted_guaranteed",
})
db.participants.insert_one({
    "participant_id": par_pid2,
    "appointment_id": apt_id2,
    "user_id": par_user_id,
    "email": "igaal@hotmail.com",
    "first_name": "Igaal",
    "last_name": "Hotmail",
    "status": "accepted_guaranteed",
})
db.attendance_records.insert_one({
    "record_id": str(uuid.uuid4()),
    "appointment_id": apt_id2,
    "participant_id": par_pid2,
    "outcome": "manual_review",
    "review_required": True,
    "decision_basis": "no_proof_of_attendance",
})
db.attendance_records.insert_one({
    "record_id": str(uuid.uuid4()),
    "appointment_id": apt_id2,
    "participant_id": org_pid2,
    "outcome": "on_time",
    "review_required": False,
    "decision_basis": "admissible_proof_on_time",
})

initialize_declarative_phase(apt_id2)

# Organizer says: ABSENT
submit_sheet(apt_id2, org_user_id, [
    {"target_participant_id": par_pid2, "declared_status": "absent"}
])

# Participant says: PRESENT (self-declaration)
submit_sheet(apt_id2, par_user_id, [
    {"target_participant_id": par_pid2, "declared_status": "present_on_time"}
])

apt_after2 = db.appointments.find_one({"appointment_id": apt_id2}, {"_id": 0, "declarative_phase": 1})
disputes_after2 = list(db.declarative_disputes.find({"appointment_id": apt_id2}, {"_id": 0}))
print(f"  Phase: {apt_after2.get('declarative_phase')}")
print(f"  Disputes: {len(disputes_after2)}")
assert apt_after2.get('declarative_phase') == 'disputed'
assert len(disputes_after2) == 1
d = disputes_after2[0]
print(f"  Dispute reason: {d.get('opened_reason')}")
print(f"  Dispute target: {d.get('target_participant_id')[:8]}")
assert d['opened_reason'] == 'small_group_disagreement'
print("  ✅ Disagreement → dispute created AFTER Presences phase")

# ─── Cleanup test data ───
print()
print("═══ CLEANUP ═══")
for aid in [apt_id, apt_id2]:
    db.appointments.delete_many({"appointment_id": aid})
    db.participants.delete_many({"appointment_id": aid})
    db.attendance_records.delete_many({"appointment_id": aid})
    db.attendance_sheets.delete_many({"appointment_id": aid})
    db.declarative_disputes.delete_many({"appointment_id": aid})
    db.declarative_analyses.delete_many({"appointment_id": aid})
print("  Cleaned up test data")

print()
print("═══════════════════════════════════════")
print("  ALL TESTS PASSED ✅")
print("═══════════════════════════════════════")
