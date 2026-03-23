"""
Test NLYT Proof integration with attendance decision engine.
5 scenarios as specified by user.
"""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
client = MongoClient(MONGO_URL)
db = client[DB_NAME]

WORKSPACE_ID = "7e219321-18fd-4643-9be6-e4f1de88a2a8"
USER_ID = None  # Will be resolved

# Resolve user
user = db.users.find_one({"email": "testuser_audit@nlyt.app"}, {"_id": 0})
if user:
    USER_ID = user.get("user_id")
    print(f"[SETUP] User: {user.get('first_name')} {user.get('last_name')} (ID: {USER_ID})")
else:
    print("[ERROR] User not found")
    sys.exit(1)

from services.attendance_service import evaluate_participant

def create_test_appointment(title, apt_type="video", start_offset_minutes=-60, duration=60):
    """Create a test appointment that has already ended."""
    apt_id = str(uuid.uuid4())
    start = (datetime.now(timezone.utc) + timedelta(minutes=start_offset_minutes)).isoformat()
    apt = {
        "appointment_id": apt_id,
        "title": title,
        "workspace_id": WORKSPACE_ID,
        "created_by": USER_ID,
        "appointment_type": apt_type,
        "start_datetime": start,
        "duration_minutes": duration,
        "status": "active",
        "tolerated_delay_minutes": 10,
    }
    db.appointments.insert_one(apt)
    return {k: v for k, v in apt.items() if k != "_id"}


def create_test_participant(apt_id, name="Test Participant", status="accepted_guaranteed"):
    """Create a test participant."""
    p_id = str(uuid.uuid4())
    token = str(uuid.uuid4())
    p = {
        "participant_id": p_id,
        "appointment_id": apt_id,
        "email": f"test_{p_id[:8]}@example.com",
        "first_name": name,
        "last_name": "Proof",
        "invitation_token": token,
        "status": status,
        "is_organizer": False,
    }
    db.participants.insert_one(p)
    return {k: v for k, v in p.items() if k != "_id"}


def create_proof_session(apt_id, participant_id, participant_email, score, proof_level,
                         heartbeat_count, active_duration, score_breakdown=None, checked_out=True):
    """Create a proof session in DB."""
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    session = {
        "session_id": session_id,
        "appointment_id": apt_id,
        "participant_id": participant_id,
        "participant_email": participant_email,
        "participant_name": "Test Proof",
        "checked_in_at": (now - timedelta(seconds=active_duration)).isoformat(),
        "checked_out_at": now.isoformat() if checked_out else None,
        "heartbeat_count": heartbeat_count,
        "heartbeat_timestamps": [now.isoformat()],
        "active_duration_seconds": active_duration,
        "score": score,
        "proof_level": proof_level,
        "score_breakdown": score_breakdown or {"checkin_points": 30, "duration_points": score - 30, "video_api_points": 0},
        "suggested_status": "present" if proof_level == "strong" else "partial" if proof_level == "medium" else "absent",
        "final_status": None,
    }
    db.proof_sessions.insert_one(session)
    return session_id


def cleanup(apt_ids):
    """Remove test data."""
    for apt_id in apt_ids:
        db.appointments.delete_many({"appointment_id": apt_id})
        db.participants.delete_many({"appointment_id": apt_id})
        db.proof_sessions.delete_many({"appointment_id": apt_id})
        db.evidence.delete_many({"appointment_id": apt_id})


# ==================== TESTS ====================

apt_ids = []
results = []

# --- SCENARIO 1: Video + strong proof (score 70) → on_time ---
print("\n" + "="*60)
print("SCENARIO 1: RDV vidéo + check-in à l'heure + heartbeat suffisant → PRESENT")
apt = create_test_appointment("Test Proof Strong", "video")
apt_ids.append(apt["appointment_id"])
p = create_test_participant(apt["appointment_id"], "Strong Proof")
create_proof_session(apt["appointment_id"], p["participant_id"], p["email"],
                     score=70, proof_level="strong", heartbeat_count=40,
                     active_duration=3600,
                     score_breakdown={"checkin_points": 30, "duration_points": 40, "video_api_points": 0})

result = evaluate_participant(p, apt)
print(f"  outcome: {result['outcome']}")
print(f"  decision_basis: {result['decision_basis']}")
print(f"  confidence: {result['confidence']}")
print(f"  review_required: {result['review_required']}")
print(f"  proof_context.source: {result.get('proof_context', {}).get('source', 'N/A')}")
print(f"  proof_context.score: {result.get('proof_context', {}).get('score', 'N/A')}")
ok1 = result['outcome'] == 'on_time' and result['confidence'] == 'high' and not result['review_required']
print(f"  ✓ PASS" if ok1 else f"  ✗ FAIL")
results.append(("Scénario 1: Strong proof → on_time", ok1))


# --- SCENARIO 2: Video + weak proof (score 15) → no_show ---
print("\n" + "="*60)
print("SCENARIO 2: RDV vidéo + check-in mais heartbeat insuffisant → NO_SHOW")
apt = create_test_appointment("Test Proof Weak", "video")
apt_ids.append(apt["appointment_id"])
p = create_test_participant(apt["appointment_id"], "Weak Proof")
create_proof_session(apt["appointment_id"], p["participant_id"], p["email"],
                     score=15, proof_level="weak", heartbeat_count=3,
                     active_duration=90,
                     score_breakdown={"checkin_points": 5, "duration_points": 10, "video_api_points": 0})

result = evaluate_participant(p, apt)
print(f"  outcome: {result['outcome']}")
print(f"  decision_basis: {result['decision_basis']}")
print(f"  confidence: {result['confidence']}")
print(f"  review_required: {result['review_required']}")
print(f"  proof_context.source: {result.get('proof_context', {}).get('source', 'N/A')}")
print(f"  proof_context.score: {result.get('proof_context', {}).get('score', 'N/A')}")
ok2 = result['outcome'] == 'no_show' and result['review_required'] == True
print(f"  ✓ PASS" if ok2 else f"  ✗ FAIL")
results.append(("Scénario 2: Weak proof → no_show", ok2))


# --- SCENARIO 3: Video + NO proof session → no_show ---
print("\n" + "="*60)
print("SCENARIO 3: RDV vidéo SANS proof_session → NO_SHOW (no_proof_no_video)")
apt = create_test_appointment("Test No Proof", "video")
apt_ids.append(apt["appointment_id"])
p = create_test_participant(apt["appointment_id"], "No Session")
# No proof session created intentionally

result = evaluate_participant(p, apt)
print(f"  outcome: {result['outcome']}")
print(f"  decision_basis: {result['decision_basis']}")
print(f"  confidence: {result['confidence']}")
print(f"  review_required: {result['review_required']}")
print(f"  proof_context.source: {result.get('proof_context', {}).get('source', 'N/A')}")
ok3 = result['outcome'] == 'no_show' and 'no_proof' in result['decision_basis']
print(f"  ✓ PASS" if ok3 else f"  ✗ FAIL")
results.append(("Scénario 3: No proof session → no_show", ok3))


# --- SCENARIO 4: Physical appointment → unchanged logic ---
print("\n" + "="*60)
print("SCENARIO 4: RDV PHYSIQUE → logique inchangée (pas de proof_sessions)")
apt = create_test_appointment("Test Physical", "physical")
apt_ids.append(apt["appointment_id"])
p = create_test_participant(apt["appointment_id"], "Physical")
# No proof session (physical doesn't use them)

result = evaluate_participant(p, apt)
print(f"  outcome: {result['outcome']}")
print(f"  decision_basis: {result['decision_basis']}")
print(f"  review_required: {result['review_required']}")
# Should NOT have proof_context (physical flow)
has_proof_context = 'proof_context' in result
print(f"  has proof_context: {has_proof_context}")
ok4 = result['outcome'] == 'manual_review' and not has_proof_context
print(f"  ✓ PASS" if ok4 else f"  ✗ FAIL")
results.append(("Scénario 4: Physical → unchanged (no proof_context)", ok4))


# --- SCENARIO 5: Video + medium proof (score 45) → manual_review ---
print("\n" + "="*60)
print("SCENARIO 5: RDV vidéo + score moyen (45) → MANUAL_REVIEW")
apt = create_test_appointment("Test Proof Medium", "video")
apt_ids.append(apt["appointment_id"])
p = create_test_participant(apt["appointment_id"], "Medium Proof")
create_proof_session(apt["appointment_id"], p["participant_id"], p["email"],
                     score=45, proof_level="medium", heartbeat_count=20,
                     active_duration=1800,
                     score_breakdown={"checkin_points": 15, "duration_points": 30, "video_api_points": 0})

result = evaluate_participant(p, apt)
print(f"  outcome: {result['outcome']}")
print(f"  decision_basis: {result['decision_basis']}")
print(f"  confidence: {result['confidence']}")
print(f"  review_required: {result['review_required']}")
print(f"  proof_context.source: {result.get('proof_context', {}).get('source', 'N/A')}")
print(f"  proof_context.score: {result.get('proof_context', {}).get('score', 'N/A')}")
ok5 = result['outcome'] == 'manual_review' and result['review_required'] == True and result.get('proof_context', {}).get('source') == 'nlyt_proof'
print(f"  ✓ PASS" if ok5 else f"  ✗ FAIL")
results.append(("Scénario 5: Medium proof → manual_review", ok5))


# --- BONUS SCENARIO 6: Video + strong proof + late check-in → late ---
print("\n" + "="*60)
print("SCENARIO 6 (bonus): RDV vidéo + check-in en retard + heartbeat OK → LATE")
apt = create_test_appointment("Test Proof Late", "video")
apt_ids.append(apt["appointment_id"])
p = create_test_participant(apt["appointment_id"], "Late Proof")
create_proof_session(apt["appointment_id"], p["participant_id"], p["email"],
                     score=60, proof_level="strong", heartbeat_count=35,
                     active_duration=3000,
                     score_breakdown={"checkin_points": 15, "duration_points": 45, "video_api_points": 0})

result = evaluate_participant(p, apt)
print(f"  outcome: {result['outcome']}")
print(f"  decision_basis: {result['decision_basis']}")
print(f"  confidence: {result['confidence']}")
print(f"  review_required: {result['review_required']}")
ok6 = result['outcome'] == 'late' and 'nlyt_proof_strong_late' in result['decision_basis']
print(f"  ✓ PASS" if ok6 else f"  ✗ FAIL")
results.append(("Scénario 6: Strong proof + late → late", ok6))


# --- CLEANUP ---
print("\n" + "="*60)
print("CLEANUP")
cleanup(apt_ids)
print("  Test data cleaned up.")

# --- SUMMARY ---
print("\n" + "="*60)
print("RÉSUMÉ DES TESTS")
print("="*60)
all_pass = True
for name, passed in results:
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  {status} | {name}")
    if not passed:
        all_pass = False

print(f"\n{'='*60}")
if all_pass:
    print("TOUS LES TESTS PASSENT ✓")
else:
    print("CERTAINS TESTS ÉCHOUENT ✗")
    sys.exit(1)
