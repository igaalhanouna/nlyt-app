"""
LOCK-DOWN TESTS: Strong proof must NEVER create manual_review, attendance_sheet, or dispute.

These tests explicitly verify the absolute rule:
- Sufficient technological proof = automatic presence confirmation
- No Presences page card, no dispute, no attendance sheet

Covers: GPS valid, QR code, NLYT Proof >= 55, Video API (Zoom/Teams)

DB schema alignment: uses `source` as primary field, `derived_facts` for nested data.
"""
import sys, os
sys.path.insert(0, "/app/backend")
os.environ.setdefault("DB_NAME", "test_database")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")

from database import db
import uuid

# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def create_test_appointment(apt_id, title, apt_type="physical"):
    org_uid = "d13498f9-9c0d-47d4-b48f-9e327e866127"
    par_uid = "239d1bbc-a4ea-47ac-b3c8-2f02f0769ef7"
    org_pid = f"org-{uuid.uuid4().hex[:12]}"
    par_pid = f"par-{uuid.uuid4().hex[:12]}"

    db.appointments.insert_one({
        "appointment_id": apt_id,
        "organizer_id": org_uid,
        "title": title,
        "start_datetime": "2026-03-27T10:00:00Z",
        "duration_minutes": 60,
        "appointment_type": apt_type,
        "status": "completed",
        "declarative_phase": None,
        "location_lat": 48.8566,
        "location_lng": 2.3522,
        "tolerated_delay_minutes": 10,
        "cancellation_deadline_hours": 24,
    })
    db.participants.insert_one({
        "participant_id": org_pid,
        "appointment_id": apt_id,
        "user_id": org_uid,
        "email": "testuser_audit@nlyt.app",
        "first_name": "Test", "last_name": "Audit",
        "status": "accepted_guaranteed",
    })
    db.participants.insert_one({
        "participant_id": par_pid,
        "appointment_id": apt_id,
        "user_id": par_uid,
        "email": "igaal@hotmail.com",
        "first_name": "Igaal", "last_name": "Test",
        "status": "accepted_guaranteed",
    })
    return org_pid, par_pid, org_uid, par_uid


def cleanup(apt_id):
    for coll in ["appointments", "participants", "attendance_records",
                 "evidence_items", "proof_sessions", "attendance_sheets",
                 "declarative_disputes", "declarative_analyses"]:
        db[coll].delete_many({"appointment_id": apt_id})


def verify_no_declarative(apt_id, par_pid, test_name):
    """Verify that no sheet, no dispute, no declarative phase was created."""
    sheets = list(db.attendance_sheets.find({"appointment_id": apt_id}, {"_id": 0}))
    disputes = list(db.declarative_disputes.find({"appointment_id": apt_id}, {"_id": 0}))
    apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0, "declarative_phase": 1})

    assert len(sheets) == 0, f"[{test_name}] FAIL: {len(sheets)} sheets created (expected 0)"
    assert len(disputes) == 0, f"[{test_name}] FAIL: {len(disputes)} disputes created (expected 0)"
    phase = apt.get("declarative_phase")
    assert phase in (None, "not_needed"), f"[{test_name}] FAIL: phase={phase} (expected None or not_needed)"
    print(f"  OK [{test_name}] No sheet, no dispute, phase={phase}")


# ═══════════════════════════════════════════════════════════════════
# TEST A: GPS valid (physical) — real DB schema
# ═══════════════════════════════════════════════════════════════════
print("=== TEST A: GPS valid -> auto confirmation, no Presences, no Litige ===")

apt_id_a = f"lockdown-gps-{uuid.uuid4().hex[:8]}"
cleanup(apt_id_a)
org_pid, par_pid, org_uid, par_uid = create_test_appointment(apt_id_a, "GPS Valid Test")

# Real DB schema: source="gps", gps_within_radius inside derived_facts
for pid in [org_pid, par_pid]:
    db.evidence_items.insert_one({
        "evidence_id": str(uuid.uuid4()),
        "appointment_id": apt_id_a,
        "participant_id": pid,
        "source": "gps",
        "source_timestamp": "2026-03-27T10:01:00+00:00",
        "confidence_score": "high",
        "derived_facts": {
            "geographic_consistency": "close",
            "temporal_consistency": "valid",
            "gps_within_radius": True,
            "gps_radius_meters": 200,
            "distance_meters": 25.0,
        },
    })

from services.attendance_service import evaluate_participant, _has_admissible_proof

# Verify _has_admissible_proof directly
has_proof = _has_admissible_proof(par_pid, apt_id_a)
print(f"  _has_admissible_proof: {has_proof}")
assert has_proof == True, "FAIL: GPS valid should be admissible"

par = db.participants.find_one({"participant_id": par_pid}, {"_id": 0})
apt = db.appointments.find_one({"appointment_id": apt_id_a}, {"_id": 0})
result = evaluate_participant(par, apt)
print(f"  Participant evaluation: outcome={result['outcome']}, review_required={result['review_required']}")
assert result['outcome'] != 'manual_review', f"FAIL: GPS valid should NOT be manual_review, got {result['outcome']}"
assert result['review_required'] == False, f"FAIL: review_required should be False"

# Simulate evaluate_appointment records
db.attendance_records.insert_one({
    "record_id": str(uuid.uuid4()),
    "appointment_id": apt_id_a,
    "participant_id": par_pid,
    "outcome": result['outcome'],
    "review_required": False,
    "decision_basis": result['decision_basis'],
})
db.attendance_records.insert_one({
    "record_id": str(uuid.uuid4()),
    "appointment_id": apt_id_a,
    "participant_id": org_pid,
    "outcome": "on_time",
    "review_required": False,
    "decision_basis": "admissible_proof_on_time",
})

from services.declarative_service import initialize_declarative_phase
initialize_declarative_phase(apt_id_a)
verify_no_declarative(apt_id_a, par_pid, "GPS Valid")
cleanup(apt_id_a)


# ═══════════════════════════════════════════════════════════════════
# TEST B: QR code (physical) — real DB schema
# ═══════════════════════════════════════════════════════════════════
print()
print("=== TEST B: QR code -> auto confirmation ===")

apt_id_b = f"lockdown-qr-{uuid.uuid4().hex[:8]}"
org_pid, par_pid, org_uid, par_uid = create_test_appointment(apt_id_b, "QR Code Test")

# Real DB schema: source="qr"
for pid in [org_pid, par_pid]:
    db.evidence_items.insert_one({
        "evidence_id": str(uuid.uuid4()),
        "appointment_id": apt_id_b,
        "participant_id": pid,
        "source": "qr",
        "source_timestamp": "2026-03-27T10:00:30+00:00",
        "confidence_score": "high",
        "derived_facts": {
            "qr_valid": True,
            "temporal_consistency": "valid",
        },
    })

has_proof = _has_admissible_proof(par_pid, apt_id_b)
assert has_proof == True, "FAIL: QR should be admissible"

par = db.participants.find_one({"participant_id": par_pid}, {"_id": 0})
apt = db.appointments.find_one({"appointment_id": apt_id_b}, {"_id": 0})
result = evaluate_participant(par, apt)
print(f"  Participant evaluation: outcome={result['outcome']}, review_required={result['review_required']}")
assert result['review_required'] == False

for pid, out in [(org_pid, "on_time"), (par_pid, result['outcome'])]:
    db.attendance_records.insert_one({
        "record_id": str(uuid.uuid4()), "appointment_id": apt_id_b,
        "participant_id": pid, "outcome": out,
        "review_required": False, "decision_basis": "admissible",
    })

initialize_declarative_phase(apt_id_b)
verify_no_declarative(apt_id_b, par_pid, "QR Code")
cleanup(apt_id_b)


# ═══════════════════════════════════════════════════════════════════
# TEST C: NLYT Proof score >= 55 (video)
# ═══════════════════════════════════════════════════════════════════
print()
print("=== TEST C: NLYT Proof >= 55 -> auto confirmation ===")

apt_id_c = f"lockdown-nlyt-{uuid.uuid4().hex[:8]}"
org_pid, par_pid, org_uid, par_uid = create_test_appointment(apt_id_c, "NLYT Proof Test", "video")

db.proof_sessions.insert_one({
    "session_id": str(uuid.uuid4()),
    "appointment_id": apt_id_c,
    "participant_id": par_pid,
    "user_id": par_uid,
    "status": "completed",
    "score": 65,
    "proof_level": "strong",
    "score_breakdown": {"checkin_points": 30, "duration_points": 35, "video_api_points": 0},
    "heartbeat_count": 10,
    "active_duration_seconds": 2400,
    "started_at": "2026-03-27T10:01:00Z",
    "checked_out_at": "2026-03-27T10:41:00Z",
    "completed_at": "2026-03-27T10:41:00Z",
})
# NLYT proof also creates an evidence_item with source="nlyt_proof"
db.evidence_items.insert_one({
    "evidence_id": str(uuid.uuid4()),
    "appointment_id": apt_id_c,
    "participant_id": par_pid,
    "source": "nlyt_proof",
    "source_timestamp": "2026-03-27T10:01:00+00:00",
    "confidence_score": "high",
    "derived_facts": {
        "temporal_consistency": "valid",
    },
})

has_proof = _has_admissible_proof(par_pid, apt_id_c)
assert has_proof == True, "FAIL: NLYT proof should be admissible"

par = db.participants.find_one({"participant_id": par_pid}, {"_id": 0})
apt = db.appointments.find_one({"appointment_id": apt_id_c}, {"_id": 0})
result = evaluate_participant(par, apt)
print(f"  Participant evaluation: outcome={result['outcome']}, review_required={result['review_required']}")
assert result['outcome'] != 'manual_review', f"FAIL: NLYT Proof >= 55 should NOT be manual_review"
assert result['review_required'] == False

for pid, out, rr in [(org_pid, "on_time", False), (par_pid, result['outcome'], False)]:
    db.attendance_records.insert_one({
        "record_id": str(uuid.uuid4()), "appointment_id": apt_id_c,
        "participant_id": pid, "outcome": out,
        "review_required": rr, "decision_basis": "strong_proof",
    })

initialize_declarative_phase(apt_id_c)
verify_no_declarative(apt_id_c, par_pid, "NLYT Proof >= 55")
db.proof_sessions.delete_many({"appointment_id": apt_id_c})
cleanup(apt_id_c)


# ═══════════════════════════════════════════════════════════════════
# TEST D: Video API (Zoom) — real DB schema (source="video_conference")
# ═══════════════════════════════════════════════════════════════════
print()
print("=== TEST D: Video API (Zoom) -> auto confirmation ===")

apt_id_d = f"lockdown-zoom-{uuid.uuid4().hex[:8]}"
org_pid, par_pid, org_uid, par_uid = create_test_appointment(apt_id_d, "Zoom API Test", "video")

# Real DB schema: source="video_conference", provider in derived_facts
db.evidence_items.insert_one({
    "evidence_id": str(uuid.uuid4()),
    "appointment_id": apt_id_d,
    "participant_id": par_pid,
    "source": "video_conference",
    "source_timestamp": "2026-03-27T10:02:00+00:00",
    "confidence_score": "high",
    "derived_facts": {
        "provider": "zoom",
        "provider_evidence_ceiling": "strong",
        "identity_confidence": "high",
        "video_attendance_outcome": "joined_on_time",
        "temporal_consistency": "valid",
    },
})

has_proof = _has_admissible_proof(par_pid, apt_id_d)
print(f"  _has_admissible_proof: {has_proof}")
assert has_proof == True, "FAIL: Zoom API should be admissible"

for pid, out in [(org_pid, "on_time"), (par_pid, "on_time")]:
    db.attendance_records.insert_one({
        "record_id": str(uuid.uuid4()), "appointment_id": apt_id_d,
        "participant_id": pid, "outcome": out,
        "review_required": False, "decision_basis": "video_api",
    })

initialize_declarative_phase(apt_id_d)
verify_no_declarative(apt_id_d, par_pid, "Video API Zoom")
cleanup(apt_id_d)


# ═══════════════════════════════════════════════════════════════════
# TEST D2: Video API (Teams) — real DB schema
# ═══════════════════════════════════════════════════════════════════
print()
print("=== TEST D2: Video API (Teams) -> auto confirmation ===")

apt_id_d2 = f"lockdown-teams-{uuid.uuid4().hex[:8]}"
org_pid, par_pid, org_uid, par_uid = create_test_appointment(apt_id_d2, "Teams API Test", "video")

db.evidence_items.insert_one({
    "evidence_id": str(uuid.uuid4()),
    "appointment_id": apt_id_d2,
    "participant_id": par_pid,
    "source": "video_conference",
    "source_timestamp": "2026-03-27T10:01:00+00:00",
    "confidence_score": "high",
    "derived_facts": {
        "provider": "teams",
        "provider_evidence_ceiling": "strong",
        "identity_confidence": "high",
        "video_attendance_outcome": "joined_late",
        "temporal_consistency": "valid",
    },
})

has_proof = _has_admissible_proof(par_pid, apt_id_d2)
assert has_proof == True, "FAIL: Teams API should be admissible"
print(f"  OK [Teams] _has_admissible_proof: True")
cleanup(apt_id_d2)


# ═══════════════════════════════════════════════════════════════════
# TEST D3: Google Meet (assisted) — NOT admissible
# ═══════════════════════════════════════════════════════════════════
print()
print("=== TEST D3: Google Meet (assisted) -> NOT admissible ===")

apt_id_d3 = f"lockdown-meet-{uuid.uuid4().hex[:8]}"
org_pid, par_pid, org_uid, par_uid = create_test_appointment(apt_id_d3, "Meet Test", "video")

db.evidence_items.insert_one({
    "evidence_id": str(uuid.uuid4()),
    "appointment_id": apt_id_d3,
    "participant_id": par_pid,
    "source": "video_conference",
    "source_timestamp": "2026-03-27T10:00:00+00:00",
    "confidence_score": "low",
    "derived_facts": {
        "provider": "meet",
        "provider_evidence_ceiling": "assisted",
        "identity_confidence": "low",
        "video_attendance_outcome": "manual_review",
        "temporal_consistency": "valid",
    },
})

has_proof = _has_admissible_proof(par_pid, apt_id_d3)
assert has_proof == False, "FAIL: Google Meet (assisted) should NOT be admissible"
print(f"  OK [Meet] _has_admissible_proof: False (correct)")
cleanup(apt_id_d3)


# ═══════════════════════════════════════════════════════════════════
# TEST E: Manual only -> MUST go to manual_review
# ═══════════════════════════════════════════════════════════════════
print()
print("=== TEST E: Manual only -> manual_review -> Presences sheet created ===")

apt_id_e = f"lockdown-manual-{uuid.uuid4().hex[:8]}"
org_pid, par_pid, org_uid, par_uid = create_test_appointment(apt_id_e, "Manual Only Test")

db.evidence_items.insert_one({
    "evidence_id": str(uuid.uuid4()),
    "appointment_id": apt_id_e,
    "participant_id": par_pid,
    "source": "manual_checkin",
    "source_timestamp": "2026-03-27T10:05:00+00:00",
    "confidence_score": "low",
    "derived_facts": {
        "temporal_consistency": "valid",
    },
})

has_proof = _has_admissible_proof(par_pid, apt_id_e)
print(f"  _has_admissible_proof (manual only): {has_proof}")
assert has_proof == False, "FAIL: Manual checkin should NOT be admissible"

# Organizer has GPS (strong), participant has manual only
db.evidence_items.insert_one({
    "evidence_id": str(uuid.uuid4()),
    "appointment_id": apt_id_e,
    "participant_id": org_pid,
    "source": "gps",
    "source_timestamp": "2026-03-27T10:00:00+00:00",
    "confidence_score": "high",
    "derived_facts": {
        "gps_within_radius": True,
        "geographic_consistency": "close",
        "temporal_consistency": "valid",
    },
})

db.attendance_records.insert_one({
    "record_id": str(uuid.uuid4()), "appointment_id": apt_id_e,
    "participant_id": org_pid, "outcome": "on_time",
    "review_required": False, "decision_basis": "admissible_proof_on_time",
})
db.attendance_records.insert_one({
    "record_id": str(uuid.uuid4()), "appointment_id": apt_id_e,
    "participant_id": par_pid, "outcome": "manual_review",
    "review_required": True, "decision_basis": "no_proof_of_attendance",
})

initialize_declarative_phase(apt_id_e)

sheets = list(db.attendance_sheets.find({"appointment_id": apt_id_e}, {"_id": 0}))
apt = db.appointments.find_one({"appointment_id": apt_id_e}, {"_id": 0, "declarative_phase": 1})
print(f"  Phase: {apt.get('declarative_phase')}")
print(f"  Sheets created: {len(sheets)}")
assert apt.get('declarative_phase') == 'collecting', f"FAIL: Manual should go to collecting"
assert len(sheets) >= 1, f"FAIL: Sheets should be created for manual_review"
print(f"  OK [Manual Only] Correctly goes to Presences (collecting), {len(sheets)} sheets created")

disputes = list(db.declarative_disputes.find({"appointment_id": apt_id_e}, {"_id": 0}))
assert len(disputes) == 0, f"FAIL: No dispute should exist before sheet submission"
print(f"  OK [Manual Only] No dispute before Presences submission")
cleanup(apt_id_e)


# ═══════════════════════════════════════════════════════════════════
# TEST F: NLYT Proof score < 30 (weak) -> manual_review
# ═══════════════════════════════════════════════════════════════════
print()
print("=== TEST F: NLYT Proof < 30 (weak) -> manual_review -> Presences ===")

apt_id_f = f"lockdown-weak-{uuid.uuid4().hex[:8]}"
org_pid, par_pid, org_uid, par_uid = create_test_appointment(apt_id_f, "Weak Proof Test", "video")

db.proof_sessions.insert_one({
    "session_id": str(uuid.uuid4()),
    "appointment_id": apt_id_f,
    "participant_id": par_pid,
    "user_id": par_uid,
    "status": "completed",
    "score": 20,
    "proof_level": "weak",
    "score_breakdown": {"checkin_points": 10, "duration_points": 10, "video_api_points": 0},
    "heartbeat_count": 2,
    "active_duration_seconds": 600,
    "started_at": "2026-03-27T10:01:00Z",
    "checked_out_at": "2026-03-27T10:11:00Z",
    "completed_at": "2026-03-27T10:11:00Z",
})
db.evidence_items.insert_one({
    "evidence_id": str(uuid.uuid4()),
    "appointment_id": apt_id_f,
    "participant_id": par_pid,
    "source": "nlyt_proof",
    "source_timestamp": "2026-03-27T10:01:00+00:00",
    "confidence_score": "low",
    "derived_facts": {
        "temporal_consistency": "valid",
    },
})

par = db.participants.find_one({"participant_id": par_pid}, {"_id": 0})
apt = db.appointments.find_one({"appointment_id": apt_id_f}, {"_id": 0})
result = evaluate_participant(par, apt)
print(f"  Participant evaluation: outcome={result['outcome']}, review_required={result['review_required']}")
assert result['outcome'] == 'manual_review', f"FAIL: Weak proof should be manual_review"
assert result['review_required'] == True

db.attendance_records.insert_one({
    "record_id": str(uuid.uuid4()), "appointment_id": apt_id_f,
    "participant_id": org_pid, "outcome": "on_time",
    "review_required": False, "decision_basis": "strong_proof",
})
db.attendance_records.insert_one({
    "record_id": str(uuid.uuid4()), "appointment_id": apt_id_f,
    "participant_id": par_pid, "outcome": "manual_review",
    "review_required": True, "decision_basis": "nlyt_proof_weak",
})

initialize_declarative_phase(apt_id_f)
sheets = list(db.attendance_sheets.find({"appointment_id": apt_id_f}, {"_id": 0}))
apt_after = db.appointments.find_one({"appointment_id": apt_id_f}, {"_id": 0, "declarative_phase": 1})
print(f"  Phase: {apt_after.get('declarative_phase')}, Sheets: {len(sheets)}")
assert apt_after.get('declarative_phase') == 'collecting'
assert len(sheets) >= 1
print(f"  OK [Weak Proof] Correctly goes to Presences")
db.proof_sessions.delete_many({"appointment_id": apt_id_f})
cleanup(apt_id_f)


# ═══════════════════════════════════════════════════════════════════
# TEST G: GPS valid but outside radius -> NOT admissible
# ═══════════════════════════════════════════════════════════════════
print()
print("=== TEST G: GPS outside radius -> NOT admissible ===")

apt_id_g = f"lockdown-gps-far-{uuid.uuid4().hex[:8]}"
org_pid, par_pid, org_uid, par_uid = create_test_appointment(apt_id_g, "GPS Far Test")

db.evidence_items.insert_one({
    "evidence_id": str(uuid.uuid4()),
    "appointment_id": apt_id_g,
    "participant_id": par_pid,
    "source": "gps",
    "source_timestamp": "2026-03-27T10:05:00+00:00",
    "confidence_score": "low",
    "derived_facts": {
        "gps_within_radius": False,
        "geographic_consistency": "far",
        "distance_meters": 12000.0,
        "temporal_consistency": "valid",
    },
})

has_proof = _has_admissible_proof(par_pid, apt_id_g)
assert has_proof == False, "FAIL: GPS outside radius should NOT be admissible"
print(f"  OK [GPS Far] _has_admissible_proof: False (correct)")
cleanup(apt_id_g)


# ═══════════════════════════════════════════════════════════════════
print()
print("===================================================")
print("  ALL LOCK-DOWN TESTS PASSED (9 tests)")
print("  Strong proof -> NEVER manual_review, sheet, or dispute")
print("  Weak/no proof -> ALWAYS manual_review -> Presences")
print("  Google Meet -> NOT admissible (Niveau 3)")
print("  GPS outside radius -> NOT admissible")
print("===================================================")
