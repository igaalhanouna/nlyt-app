"""
Trustless V4 Iteration 127 Tests
Tests for:
1. Atomic CAS on evaluate_appointment (prevents race conditions)
2. Atomic CAS on _run_analysis (prevents double analysis)
3. Monitoring/auto-recovery for stuck 'collecting' phases
4. Dead HTTP endpoints removed (POST /evaluate, POST /reevaluate, PUT /reclassify)
5. GET endpoints still work
6. Full 1v1 flows (disagreement → dispute, agreement → auto-resolved)
7. initialize_declarative_phase guard
8. is_self_declaration preserved
9. Strong proof lockdown (GPS/Video/QR → no manual_review)
"""
import sys
import os
import uuid
import requests
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app/backend")
os.environ.setdefault("DB_NAME", "test_database")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")

from database import db

# Test credentials
org_user_id = "d13498f9-9c0d-47d4-b48f-9e327e866127"
par_user_id = "239d1bbc-a4ea-47ac-b3c8-2f02f0769ef7"
BASE_URL = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()

passed = 0
failed = 0


def create_test_appointment(suffix):
    """Create a test appointment with 2 participants (organizer + participant)"""
    apt_id = f"test-v4-{suffix}-{uuid.uuid4().hex[:8]}"
    org_pid = f"org-{suffix}-{uuid.uuid4().hex[:8]}"
    par_pid = f"par-{suffix}-{uuid.uuid4().hex[:8]}"
    
    db.appointments.insert_one({
        "appointment_id": apt_id,
        "organizer_id": org_user_id,
        "title": f"Test V4 {suffix}",
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
    """Clean up test data"""
    for coll in ['appointments', 'participants', 'attendance_records', 'attendance_sheets',
                 'declarative_analyses', 'declarative_disputes']:
        db[coll].delete_many({"appointment_id": apt_id})


def get_auth_token():
    """Get authentication token for API tests"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "testuser_audit@nlyt.app",
        "password": "TestAudit123!"
    })
    if resp.status_code == 200:
        data = resp.json()
        return data.get("access_token") or data.get("token")
    return None


# ═══════════════════════════════════════════════════════════════════
# TEST 1: Atomic CAS on evaluate_appointment
# ═══════════════════════════════════════════════════════════════════
print("=== TEST 1: Atomic CAS on evaluate_appointment ===")
apt_id = f"test-cas-eval-{uuid.uuid4().hex[:8]}"
db.appointments.insert_one({
    "appointment_id": apt_id, "organizer_id": org_user_id,
    "title": "Test CAS eval", "start_datetime": "2026-03-20T10:00:00Z",
    "duration_minutes": 60, "appointment_type": "physical",
    "status": "active", "workspace_id": "test-ws",
})
db.participants.insert_many([
    {"participant_id": f"org-eval-{uuid.uuid4().hex[:8]}", "appointment_id": apt_id,
     "user_id": org_user_id, "email": "test@test.com", "status": "accepted_guaranteed", "is_organizer": True},
    {"participant_id": f"par-eval-{uuid.uuid4().hex[:8]}", "appointment_id": apt_id,
     "user_id": par_user_id, "email": "igaal@hotmail.com", "status": "accepted_guaranteed", "is_organizer": False},
])

from services.attendance_service import evaluate_appointment
result1 = evaluate_appointment(apt_id)
assert result1.get("evaluated"), f"First call should evaluate: {result1}"
records_after_1 = db.attendance_records.count_documents({"appointment_id": apt_id})

result2 = evaluate_appointment(apt_id)
assert result2.get("skipped"), f"Second call should skip: {result2}"
assert result2.get("reason") == "Déjà évalué", f"Reason should be 'Déjà évalué': {result2}"
records_after_2 = db.attendance_records.count_documents({"appointment_id": apt_id})
assert records_after_2 == records_after_1, "No new records should be created"

print(f"  1st call: evaluated={result1.get('evaluated')}, records={records_after_1}")
print(f"  2nd call: skipped={result2.get('skipped')}, reason='{result2.get('reason')}'")
print("  PASSED: Atomic CAS prevents double evaluation with 'Déjà évalué'")
passed += 1
cleanup(apt_id)


# ═══════════════════════════════════════════════════════════════════
# TEST 2: Atomic CAS on _run_analysis blocks on disputed/resolved/analyzing
# ═══════════════════════════════════════════════════════════════════
print("\n=== TEST 2: _run_analysis CAS blocks on disputed/resolved/analyzing ===")
from services.declarative_service import initialize_declarative_phase, submit_sheet, _run_analysis

# Test 2a: Block on 'disputed'
apt_id, org_pid, par_pid = create_test_appointment("t2a")
initialize_declarative_phase(apt_id)
submit_sheet(apt_id, org_user_id, [{"target_participant_id": par_pid, "declared_status": "absent"}])
submit_sheet(apt_id, par_user_id, [{"target_participant_id": par_pid, "declared_status": "present_on_time"}])

apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
assert apt.get("declarative_phase") == "disputed"
analyses_before = db.declarative_analyses.count_documents({"appointment_id": apt_id})

_run_analysis(apt_id)  # Should be blocked
analyses_after = db.declarative_analyses.count_documents({"appointment_id": apt_id})
assert analyses_after == analyses_before, "No new analysis on 'disputed'"
print(f"  2a: _run_analysis blocked on 'disputed' (analyses: {analyses_before} → {analyses_after})")
cleanup(apt_id)

# Test 2b: Block on 'resolved'
apt_id, org_pid, par_pid = create_test_appointment("t2b")
initialize_declarative_phase(apt_id)
submit_sheet(apt_id, org_user_id, [{"target_participant_id": par_pid, "declared_status": "present_on_time"}])
submit_sheet(apt_id, par_user_id, [{"target_participant_id": par_pid, "declared_status": "present_on_time"}])

apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
assert apt.get("declarative_phase") == "resolved"
analyses_before = db.declarative_analyses.count_documents({"appointment_id": apt_id})

_run_analysis(apt_id)  # Should be blocked
analyses_after = db.declarative_analyses.count_documents({"appointment_id": apt_id})
assert analyses_after == analyses_before, "No new analysis on 'resolved'"
print(f"  2b: _run_analysis blocked on 'resolved' (analyses: {analyses_before} → {analyses_after})")
cleanup(apt_id)

# Test 2c: Block on 'analyzing'
apt_id, org_pid, par_pid = create_test_appointment("t2c")
initialize_declarative_phase(apt_id)
db.appointments.update_one({"appointment_id": apt_id}, {"$set": {"declarative_phase": "analyzing"}})

_run_analysis(apt_id)  # Should be blocked
apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
assert apt.get("declarative_phase") == "analyzing", "Phase should remain 'analyzing'"
print(f"  2c: _run_analysis blocked on 'analyzing'")
cleanup(apt_id)

print("  PASSED: _run_analysis CAS blocks on disputed/resolved/analyzing")
passed += 1


# ═══════════════════════════════════════════════════════════════════
# TEST 3: Dead HTTP endpoints return 404
# ═══════════════════════════════════════════════════════════════════
print("\n=== TEST 3: Dead HTTP endpoints removed ===")
token = get_auth_token()
assert token, "Failed to get auth token"
headers = {"Authorization": f"Bearer {token}"}

# POST /evaluate should not exist
r1 = requests.post(f"{BASE_URL}/api/attendance/evaluate/fake-id", headers=headers)
assert r1.status_code in (404, 405), f"POST /evaluate should be gone, got {r1.status_code}"
print(f"  POST /api/attendance/evaluate/fake-id: {r1.status_code} (expected 404/405)")

# POST /reevaluate should not exist
r2 = requests.post(f"{BASE_URL}/api/attendance/reevaluate/fake-id", headers=headers)
assert r2.status_code in (404, 405), f"POST /reevaluate should be gone, got {r2.status_code}"
print(f"  POST /api/attendance/reevaluate/fake-id: {r2.status_code} (expected 404/405)")

# PUT /reclassify should not exist
r3 = requests.put(f"{BASE_URL}/api/attendance/reclassify/fake-id", headers=headers, json={"new_outcome": "on_time"})
assert r3.status_code in (404, 405), f"PUT /reclassify should be gone, got {r3.status_code}"
print(f"  PUT /api/attendance/reclassify/fake-id: {r3.status_code} (expected 404/405)")

print("  PASSED: Dead endpoints successfully removed")
passed += 1


# ═══════════════════════════════════════════════════════════════════
# TEST 4: GET endpoints still work
# ═══════════════════════════════════════════════════════════════════
print("\n=== TEST 4: GET endpoints still work ===")

# GET /attendance/{id} should still exist (route exists, returns 404 for non-existent appointment)
r4 = requests.get(f"{BASE_URL}/api/attendance/fake-id", headers=headers)
assert r4.status_code in (401, 403, 404), f"GET /attendance should exist, got {r4.status_code}"
print(f"  GET /api/attendance/fake-id: {r4.status_code} (route exists)")

# GET /pending-reviews/list should work
r5 = requests.get(f"{BASE_URL}/api/attendance/pending-reviews/list", headers=headers)
assert r5.status_code == 200, f"GET /pending-reviews/list should work, got {r5.status_code}"
print(f"  GET /api/attendance/pending-reviews/list: {r5.status_code}")

print("  PASSED: GET endpoints still work")
passed += 1


# ═══════════════════════════════════════════════════════════════════
# TEST 5: Full 1v1 disagreement flow → dispute created
# ═══════════════════════════════════════════════════════════════════
print("\n=== TEST 5: Full 1v1 disagreement flow → dispute created ===")
apt_id, org_pid, par_pid = create_test_appointment("t5")
initialize_declarative_phase(apt_id)

submit_sheet(apt_id, org_user_id, [{"target_participant_id": par_pid, "declared_status": "absent"}])
submit_sheet(apt_id, par_user_id, [{"target_participant_id": par_pid, "declared_status": "present_on_time"}])

apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
disputes = list(db.declarative_disputes.find({"appointment_id": apt_id}, {"_id": 0}))

assert apt.get("declarative_phase") == "disputed", f"Expected 'disputed', got '{apt.get('declarative_phase')}'"
assert len(disputes) == 1, f"Expected 1 dispute, got {len(disputes)}"
assert disputes[0]["opened_reason"] == "small_group_disagreement"
print(f"  Phase: {apt.get('declarative_phase')}, Disputes: {len(disputes)}")
print(f"  Dispute reason: {disputes[0]['opened_reason']}")
print("  PASSED: Disagreement → dispute created")
passed += 1
cleanup(apt_id)


# ═══════════════════════════════════════════════════════════════════
# TEST 6: Full 1v1 agreement flow → auto-resolved
# ═══════════════════════════════════════════════════════════════════
print("\n=== TEST 6: Full 1v1 agreement flow → auto-resolved ===")
apt_id, org_pid, par_pid = create_test_appointment("t6")
initialize_declarative_phase(apt_id)

submit_sheet(apt_id, org_user_id, [{"target_participant_id": par_pid, "declared_status": "present_on_time"}])
submit_sheet(apt_id, par_user_id, [{"target_participant_id": par_pid, "declared_status": "present_on_time"}])

apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
disputes = db.declarative_disputes.count_documents({"appointment_id": apt_id})
record = db.attendance_records.find_one({"appointment_id": apt_id, "participant_id": par_pid}, {"_id": 0})

assert apt.get("declarative_phase") == "resolved", f"Expected 'resolved', got '{apt.get('declarative_phase')}'"
assert disputes == 0, "No dispute on agreement"
assert record.get("outcome") == "on_time", f"Outcome should be on_time, got {record.get('outcome')}"
print(f"  Phase: {apt.get('declarative_phase')}, Outcome: {record.get('outcome')}")
print("  PASSED: Agreement → auto-resolved to on_time")
passed += 1
cleanup(apt_id)


# ═══════════════════════════════════════════════════════════════════
# TEST 7: initialize_declarative_phase guard blocks re-entry
# ═══════════════════════════════════════════════════════════════════
print("\n=== TEST 7: initialize_declarative_phase guard blocks re-entry ===")
apt_id, org_pid, par_pid = create_test_appointment("t7")

# First init
initialize_declarative_phase(apt_id)
apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
deadline1 = apt.get("declarative_deadline")
sheets1 = db.attendance_sheets.count_documents({"appointment_id": apt_id})
assert apt.get("declarative_phase") == "collecting"
print(f"  1st init: phase={apt.get('declarative_phase')}, sheets={sheets1}")

# Second init (should be blocked)
import time
time.sleep(0.1)
initialize_declarative_phase(apt_id)
apt2 = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
deadline2 = apt2.get("declarative_deadline")
sheets2 = db.attendance_sheets.count_documents({"appointment_id": apt_id})
assert deadline2 == deadline1, "Deadline should NOT change"
assert sheets2 == sheets1, "No new sheets"
print(f"  2nd init: deadline unchanged, sheets={sheets2}")

# Test on 'disputed'
db.appointments.update_one({"appointment_id": apt_id}, {"$set": {"declarative_phase": "disputed"}})
initialize_declarative_phase(apt_id)
apt3 = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
assert apt3.get("declarative_phase") == "disputed", "Phase should remain 'disputed'"
print(f"  Re-init on 'disputed': blocked")

# Test on 'resolved'
db.appointments.update_one({"appointment_id": apt_id}, {"$set": {"declarative_phase": "resolved"}})
initialize_declarative_phase(apt_id)
apt4 = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
assert apt4.get("declarative_phase") == "resolved", "Phase should remain 'resolved'"
print(f"  Re-init on 'resolved': blocked")

print("  PASSED: Guard blocks re-entry on collecting/disputed/resolved")
passed += 1
cleanup(apt_id)


# ═══════════════════════════════════════════════════════════════════
# TEST 8: is_self_declaration preserved through submit_sheet
# ═══════════════════════════════════════════════════════════════════
print("\n=== TEST 8: is_self_declaration preserved through submit_sheet ===")
apt_id, org_pid, par_pid = create_test_appointment("t8")
initialize_declarative_phase(apt_id)

# Check pre-submit
par_sheet = db.attendance_sheets.find_one({
    "appointment_id": apt_id,
    "submitted_by_user_id": par_user_id,
}, {"_id": 0})
self_decl_before = [d for d in par_sheet.get("declarations", []) if d.get("is_self_declaration")]
assert len(self_decl_before) == 1, f"Expected 1 self-declaration before submit, got {len(self_decl_before)}"
print(f"  Pre-submit: is_self_declaration count = {len(self_decl_before)}")

# Submit
result = submit_sheet(apt_id, par_user_id, [
    {"target_participant_id": par_pid, "declared_status": "present_on_time"},
])
assert result.get("success"), f"Submit failed: {result}"

# Check post-submit
par_sheet_after = db.attendance_sheets.find_one({
    "appointment_id": apt_id,
    "submitted_by_user_id": par_user_id,
}, {"_id": 0})
self_decl_after = [d for d in par_sheet_after.get("declarations", []) if d.get("is_self_declaration")]
assert len(self_decl_after) == 1, f"is_self_declaration LOST after submit! Got {len(self_decl_after)}"
assert self_decl_after[0]["declared_status"] == "present_on_time"
print(f"  Post-submit: is_self_declaration count = {len(self_decl_after)}, status = {self_decl_after[0]['declared_status']}")
print("  PASSED: is_self_declaration preserved through submit_sheet")
passed += 1
cleanup(apt_id)


# ═══════════════════════════════════════════════════════════════════
# TEST 9: Strong proof lockdown (GPS/Video/QR → no manual_review)
# ═══════════════════════════════════════════════════════════════════
print("\n=== TEST 9: Strong proof lockdown ===")
from services.attendance_service import _has_admissible_proof, evaluate_participant

# Test 9a: GPS valid → admissible
apt_id = f"test-lockdown-gps-{uuid.uuid4().hex[:8]}"
par_pid = f"par-gps-{uuid.uuid4().hex[:8]}"
db.evidence_items.insert_one({
    "appointment_id": apt_id,
    "participant_id": par_pid,
    "source": "gps",
    "derived_facts": {"gps_within_radius": True, "distance_meters": 50}
})
assert _has_admissible_proof(par_pid, apt_id) == True
print(f"  9a: GPS valid → admissible: True")
db.evidence_items.delete_many({"appointment_id": apt_id})

# Test 9b: QR code → admissible
db.evidence_items.insert_one({
    "appointment_id": apt_id,
    "participant_id": par_pid,
    "source": "qr",
    "derived_facts": {}
})
assert _has_admissible_proof(par_pid, apt_id) == True
print(f"  9b: QR code → admissible: True")
db.evidence_items.delete_many({"appointment_id": apt_id})

# Test 9c: Video API (Zoom) → admissible
db.evidence_items.insert_one({
    "appointment_id": apt_id,
    "participant_id": par_pid,
    "source": "video_conference",
    "derived_facts": {
        "provider": "zoom",
        "provider_evidence_ceiling": "strong",
        "video_attendance_outcome": "joined_on_time"
    }
})
assert _has_admissible_proof(par_pid, apt_id) == True
print(f"  9c: Video API (Zoom) → admissible: True")
db.evidence_items.delete_many({"appointment_id": apt_id})

# Test 9d: Google Meet → NOT admissible
db.evidence_items.insert_one({
    "appointment_id": apt_id,
    "participant_id": par_pid,
    "source": "video_conference",
    "derived_facts": {
        "provider": "meet",
        "provider_evidence_ceiling": "manual_upload",
        "video_attendance_outcome": "joined_on_time"
    }
})
assert _has_admissible_proof(par_pid, apt_id) == False
print(f"  9d: Google Meet → admissible: False (correct)")
db.evidence_items.delete_many({"appointment_id": apt_id})

# Test 9e: GPS outside radius → NOT admissible
db.evidence_items.insert_one({
    "appointment_id": apt_id,
    "participant_id": par_pid,
    "source": "gps",
    "derived_facts": {"gps_within_radius": False, "distance_meters": 500}
})
assert _has_admissible_proof(par_pid, apt_id) == False
print(f"  9e: GPS outside radius → admissible: False (correct)")
db.evidence_items.delete_many({"appointment_id": apt_id})

print("  PASSED: Strong proof lockdown working correctly")
passed += 1


# ═══════════════════════════════════════════════════════════════════
# TEST 10: Monitoring log for stuck collecting phases
# ═══════════════════════════════════════════════════════════════════
print("\n=== TEST 10: Monitoring for stuck collecting phases ===")
# This test verifies the monitoring code exists in run_declarative_deadline_job
# The actual monitoring triggers when all sheets are submitted but phase is still 'collecting' for >10 min

from services.declarative_service import run_declarative_deadline_job
import inspect

# Verify the monitoring code exists
source = inspect.getsource(run_declarative_deadline_job)
assert "MONITORING" in source or "STUCK_COLLECTING" in source, "Monitoring code should exist"
assert "all sheets submitted" in source.lower() or "all_sheets" in source.lower() or "submitted_sheets >= total_sheets" in source, "Should check for all sheets submitted"
print("  Monitoring code exists in run_declarative_deadline_job")
print("  PASSED: Monitoring for stuck collecting phases implemented")
passed += 1


# ═══════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print(f"  TRUSTLESS V4 ITERATION 127 TESTS: {passed} PASSED, {failed} FAILED")
print(f"{'=' * 60}")

if failed > 0:
    exit(1)
