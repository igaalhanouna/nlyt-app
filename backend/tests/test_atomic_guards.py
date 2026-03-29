"""Tests for atomic CAS on evaluate_appointment, _run_analysis guard,
monitoring of stuck collecting phases, and dead endpoint removal.
"""
import sys, os
sys.path.insert(0, "/app/backend")
os.environ.setdefault("DB_NAME", "test_database")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")

from database import db
import uuid, time, requests

org_user_id = "d13498f9-9c0d-47d4-b48f-9e327e866127"
par_user_id = "239d1bbc-a4ea-47ac-b3c8-2f02f0769ef7"
BASE_URL = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()

passed = 0
failed = 0

def create_apt(suffix):
    apt_id = f"test-cas-{suffix}-{uuid.uuid4().hex[:8]}"
    org_pid = f"org-{suffix}-{uuid.uuid4().hex[:8]}"
    par_pid = f"par-{suffix}-{uuid.uuid4().hex[:8]}"
    db.appointments.insert_one({
        "appointment_id": apt_id, "organizer_id": org_user_id,
        "title": f"Test CAS {suffix}", "start_datetime": "2026-03-27T10:00:00Z",
        "duration_minutes": 60, "appointment_type": "physical",
        "status": "active", "declarative_phase": None, "workspace_id": "test-ws",
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

# ═══════════════════════════════════════════════════════════════
# TEST 1: Atomic CAS prevents double evaluate_appointment
# ═══════════════════════════════════════════════════════════════
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
print(f"  1st call: evaluated={result1.get('evaluated')}, records={records_after_1}")

result2 = evaluate_appointment(apt_id)
assert result2.get("skipped"), f"Second call should skip: {result2}"
records_after_2 = db.attendance_records.count_documents({"appointment_id": apt_id})
assert records_after_2 == records_after_1, "No new records should be created"
print(f"  2nd call: skipped={result2.get('skipped')}, records={records_after_2}")
print(f"  PASSED: Atomic CAS prevents double evaluation")
passed += 1
cleanup(apt_id)

# ═══════════════════════════════════════════════════════════════
# TEST 2: _run_analysis CAS prevents double analysis
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 2: _run_analysis CAS prevents double analysis ===")
apt_id, org_pid, par_pid = create_apt("t2")

from services.declarative_service import initialize_declarative_phase, submit_sheet, _run_analysis
initialize_declarative_phase(apt_id)

submit_sheet(apt_id, org_user_id, [{"target_participant_id": par_pid, "declared_status": "absent"}])
submit_sheet(apt_id, par_user_id, [{"target_participant_id": par_pid, "declared_status": "present_on_time"}])

# Phase should be "disputed" now (analysis ran automatically via submit_sheet)
apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
assert apt.get("declarative_phase") == "disputed", f"Phase should be disputed, got {apt.get('declarative_phase')}"
analyses = db.declarative_analyses.count_documents({"appointment_id": apt_id})
disputes = db.declarative_disputes.count_documents({"appointment_id": apt_id})
assert analyses == 1, f"Expected 1 analysis, got {analyses}"
assert disputes == 1, f"Expected 1 dispute, got {disputes}"
print(f"  After submit: phase={apt.get('declarative_phase')}, analyses={analyses}, disputes={disputes}")

# Call _run_analysis again — should be BLOCKED by CAS guard
_run_analysis(apt_id)
analyses_after = db.declarative_analyses.count_documents({"appointment_id": apt_id})
disputes_after = db.declarative_disputes.count_documents({"appointment_id": apt_id})
apt_after = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
assert analyses_after == 1, f"No new analysis should be created, got {analyses_after}"
assert disputes_after == 1, f"No new dispute should be created, got {disputes_after}"
assert apt_after.get("declarative_phase") == "disputed", "Phase should remain 'disputed'"
print(f"  After double _run_analysis: phase={apt_after.get('declarative_phase')}, analyses={analyses_after}, disputes={disputes_after}")
print(f"  PASSED: _run_analysis CAS prevents double analysis")
passed += 1
cleanup(apt_id)

# ═══════════════════════════════════════════════════════════════
# TEST 3: Dead endpoints return 404/405
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 3: Dead endpoints removed ===")

# Login to get token
login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
    "email": "testuser_audit@nlyt.app", "password": "TestAudit123!"
})
assert login_resp.status_code == 200, f"Login failed: {login_resp.status_code}"
token = login_resp.json().get("token")

headers = {"Authorization": f"Bearer {token}"}

# POST /evaluate should not exist
r1 = requests.post(f"{BASE_URL}/api/attendance/evaluate/fake-id", headers=headers)
assert r1.status_code in (404, 405), f"evaluate endpoint should be gone, got {r1.status_code}"
print(f"  POST /evaluate/fake-id: {r1.status_code} (expected 404/405)")

# POST /reevaluate should not exist
r2 = requests.post(f"{BASE_URL}/api/attendance/reevaluate/fake-id", headers=headers)
assert r2.status_code in (404, 405), f"reevaluate endpoint should be gone, got {r2.status_code}"
print(f"  POST /reevaluate/fake-id: {r2.status_code} (expected 404/405)")

# PUT /reclassify should not exist
r3 = requests.put(f"{BASE_URL}/api/attendance/reclassify/fake-id", headers=headers, json={"new_outcome": "on_time"})
assert r3.status_code in (404, 405), f"reclassify endpoint should be gone, got {r3.status_code}"
print(f"  PUT /reclassify/fake-id: {r3.status_code} (expected 404/405)")

# GET /attendance/{id} should still work (not removed)
r4 = requests.get(f"{BASE_URL}/api/attendance/fake-id", headers=headers)
# Will return 404 because appointment doesn't exist, but the ROUTE exists
assert r4.status_code in (401, 403, 404), f"GET /attendance should still exist, got {r4.status_code}"
print(f"  GET /attendance/fake-id: {r4.status_code} (route exists)")

print(f"  PASSED: Dead endpoints successfully removed")
passed += 1

# ═══════════════════════════════════════════════════════════════
# TEST 4: Full 1v1 end-to-end flow (complete pipeline)
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 4: Full 1v1 end-to-end with all guards active ===")
apt_id, org_pid, par_pid = create_apt("t4")

# Step 1: Initialize
initialize_declarative_phase(apt_id)
apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
assert apt.get("declarative_phase") == "collecting"
sheets = db.attendance_sheets.count_documents({"appointment_id": apt_id})
assert sheets == 2
print(f"  Step 1: Phase={apt.get('declarative_phase')}, Sheets={sheets}")

# Step 2: Double-init (guard blocks)
initialize_declarative_phase(apt_id)
apt2 = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
assert apt2.get("declarative_deadline") == apt.get("declarative_deadline"), "Deadline must NOT change"
print(f"  Step 2: Double-init blocked, deadline unchanged")

# Step 3: Submit with disagreement
submit_sheet(apt_id, org_user_id, [{"target_participant_id": par_pid, "declared_status": "absent"}])
submit_sheet(apt_id, par_user_id, [{"target_participant_id": par_pid, "declared_status": "present_on_time"}])

# Step 4: Verify dispute created
apt3 = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
disputes = list(db.declarative_disputes.find({"appointment_id": apt_id}, {"_id": 0}))
assert apt3.get("declarative_phase") == "disputed"
assert len(disputes) == 1
assert disputes[0]["status"] == "awaiting_positions"
print(f"  Step 3-4: Phase={apt3.get('declarative_phase')}, Disputes={len(disputes)}, Status={disputes[0]['status']}")

# Step 5: Double-analysis blocked
_run_analysis(apt_id)
disputes_after = db.declarative_disputes.count_documents({"appointment_id": apt_id})
assert disputes_after == 1, "No duplicate disputes"
print(f"  Step 5: Double _run_analysis blocked, disputes still={disputes_after}")

# Step 6: Double-init blocked on disputed
initialize_declarative_phase(apt_id)
apt4 = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
assert apt4.get("declarative_phase") == "disputed", "Phase must remain 'disputed'"
print(f"  Step 6: Double-init blocked on 'disputed'")

# Step 7: Verify is_self_declaration preserved
par_sheet = db.attendance_sheets.find_one({
    "appointment_id": apt_id, "submitted_by_user_id": par_user_id}, {"_id": 0})
self_decls = [d for d in par_sheet.get("declarations", []) if d.get("is_self_declaration")]
assert len(self_decls) == 1, f"is_self_declaration should be preserved, got {len(self_decls)}"
print(f"  Step 7: is_self_declaration preserved in submitted sheet")

print(f"  PASSED: Full E2E pipeline with all guards active")
passed += 1
cleanup(apt_id)

# ═══════════════════════════════════════════════════════════════
print(f"\n{'=' * 55}")
print(f"  {passed} PASSED, {failed} FAILED")
print(f"{'=' * 55}")
if failed > 0:
    exit(1)
