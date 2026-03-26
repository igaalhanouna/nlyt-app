"""
Diagnostic script for Check-in Bug P0
Tests 4 scenarios:
1) 1 organizer + 1 participant - both check in
2) 1 organizer + multiple participants - all check in
3) Unauthenticated participant check-in
4) Invited but not yet accepted participant check-in
"""
import os, sys, uuid, json
from datetime import datetime, timedelta, timezone

os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
os.environ.setdefault('DB_NAME', 'test_database')

from database import db

def create_test_appointment(title, apt_type='physical'):
    """Create a test active appointment starting in 10 minutes (within check-in window)"""
    apt_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    start = now + timedelta(minutes=10)  # 10 min from now -> within 30-min pre-window
    
    apt = {
        "appointment_id": apt_id,
        "title": title,
        "appointment_type": apt_type,
        "status": "active",
        "workspace_id": "test-ws-checkin",
        "organizer_user_id": "test-org-user",
        "start_datetime": start.isoformat(),
        "duration_minutes": 60,
        "location": "48.8566, 2.3522",  # Paris
        "latitude": 48.8566,
        "longitude": 2.3522,
        "tolerated_delay_minutes": 15,
        "created_at": now.isoformat(),
    }
    db.appointments.insert_one(apt)
    # Remove _id
    apt.pop('_id', None)
    return apt

def create_participant(apt_id, first_name, email, status, is_organizer=False):
    """Create a participant with specific status"""
    p_id = str(uuid.uuid4())
    token = str(uuid.uuid4())
    p = {
        "participant_id": p_id,
        "appointment_id": apt_id,
        "first_name": first_name,
        "last_name": "Test",
        "email": email,
        "status": status,
        "is_organizer": is_organizer,
        "invitation_token": token,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.participants.insert_one(p)
    p.pop('_id', None)
    return p

def test_checkin(invitation_token, label, expected_success=True):
    """Test manual check-in by directly calling the service"""
    from services.evidence_service import process_manual_checkin
    
    # Step 1: Resolve participant
    participant = db.participants.find_one({"invitation_token": invitation_token}, {"_id": 0})
    if not participant:
        print(f"  [{label}] FAIL: Participant not found for token")
        return False
    
    print(f"  [{label}] Participant found: {participant['first_name']} | status={participant['status']} | is_org={participant.get('is_organizer')}")
    
    # Step 2: Check status validation (replicating _resolve_participant logic)
    if participant.get('status') not in ('accepted', 'accepted_pending_guarantee', 'accepted_guaranteed'):
        print(f"  [{label}] BLOCKED by _resolve_participant: status '{participant['status']}' not in accepted statuses")
        if expected_success:
            print(f"  [{label}] >>> ROOT CAUSE: Participant status prevents check-in!")
        else:
            print(f"  [{label}] Expected block - OK")
        return False
    
    # Step 3: Check appointment
    appointment = db.appointments.find_one({"appointment_id": participant['appointment_id']}, {"_id": 0})
    if not appointment:
        print(f"  [{label}] FAIL: Appointment not found")
        return False
    
    if appointment.get('status') != 'active':
        print(f"  [{label}] BLOCKED: Appointment status is '{appointment['status']}', not 'active'")
        return False
    
    # Step 4: Attempt actual check-in
    try:
        result = process_manual_checkin(
            appointment_id=appointment['appointment_id'],
            participant_id=participant['participant_id'],
            device_info="diagnostic_test",
            latitude=48.8566,
            longitude=2.3522,
        )
        if result.get('error'):
            print(f"  [{label}] CHECK-IN ERROR: {result['error']}")
            if result.get('already_checked_in'):
                print(f"  [{label}] Already checked in (expected for repeat test)")
            return False
        else:
            print(f"  [{label}] CHECK-IN SUCCESS! Evidence: {result.get('evidence', {}).get('source', 'unknown')}")
            return True
    except Exception as e:
        print(f"  [{label}] CHECK-IN EXCEPTION: {e}")
        return False

# ======= SETUP =======
print("=" * 70)
print("DIAGNOSTIC: Check-in Bug P0")
print("=" * 70)

# Clean up previous test data
db.appointments.delete_many({"workspace_id": "test-ws-checkin"})
db.participants.delete_many({"email": {"$regex": "checkin-test"}})
db.evidence.delete_many({"device_info": "diagnostic_test"})

# ======= SCENARIO 1: 1 org + 1 participant =======
print("\n--- SCENARIO 1: 1 organizer + 1 participant, both check-in ---")
apt1 = create_test_appointment("Scenario 1: 1+1 Check-in")
org1 = create_participant(apt1['appointment_id'], "Org1", "org1-checkin-test@test.com", "accepted_guaranteed", is_organizer=True)
part1 = create_participant(apt1['appointment_id'], "Part1", "part1-checkin-test@test.com", "accepted")

print(f"  Appointment: {apt1['title']} ({apt1['appointment_id'][:8]})")
test_checkin(org1['invitation_token'], "ORG1", expected_success=True)
test_checkin(part1['invitation_token'], "PART1", expected_success=True)

# ======= SCENARIO 2: 1 org + multiple participants =======
print("\n--- SCENARIO 2: 1 organizer + 3 participants, all check-in ---")
apt2 = create_test_appointment("Scenario 2: 1+3 Check-in")
org2 = create_participant(apt2['appointment_id'], "Org2", "org2-checkin-test@test.com", "accepted_guaranteed", is_organizer=True)
part2a = create_participant(apt2['appointment_id'], "PartA", "partA-checkin-test@test.com", "accepted")
part2b = create_participant(apt2['appointment_id'], "PartB", "partB-checkin-test@test.com", "accepted_guaranteed")
part2c = create_participant(apt2['appointment_id'], "PartC", "partC-checkin-test@test.com", "accepted_pending_guarantee")

print(f"  Appointment: {apt2['title']} ({apt2['appointment_id'][:8]})")
test_checkin(org2['invitation_token'], "ORG2", expected_success=True)
test_checkin(part2a['invitation_token'], "PART_A (accepted)", expected_success=True)
test_checkin(part2b['invitation_token'], "PART_B (accepted_guaranteed)", expected_success=True)
test_checkin(part2c['invitation_token'], "PART_C (accepted_pending_guarantee)", expected_success=True)

# ======= SCENARIO 3: Unauthenticated participant check-in =======
print("\n--- SCENARIO 3: Unauthenticated participant (no JWT, just token) ---")
apt3 = create_test_appointment("Scenario 3: Unauth Check-in")
part3 = create_participant(apt3['appointment_id'], "UnauthPart", "unauth-checkin-test@test.com", "accepted")

print(f"  Appointment: {apt3['title']} ({apt3['appointment_id'][:8]})")
print(f"  (No JWT, just invitation_token)")
test_checkin(part3['invitation_token'], "UNAUTH_PART", expected_success=True)

# ======= SCENARIO 4: Invited but NOT accepted participant =======
print("\n--- SCENARIO 4: Invited but NOT accepted participant ---")
apt4 = create_test_appointment("Scenario 4: Invited-only Check-in")
org4 = create_participant(apt4['appointment_id'], "Org4", "org4-checkin-test@test.com", "accepted_guaranteed", is_organizer=True)
part4 = create_participant(apt4['appointment_id'], "InvitedPart", "invited-checkin-test@test.com", "invited")

print(f"  Appointment: {apt4['title']} ({apt4['appointment_id'][:8]})")
test_checkin(org4['invitation_token'], "ORG4", expected_success=True)
test_checkin(part4['invitation_token'], "INVITED_PART (should be blocked)", expected_success=False)

# ======= SUMMARY =======
print("\n" + "=" * 70)
print("DIAGNOSTIC SUMMARY")
print("=" * 70)

# Now test via HTTP to simulate the actual API call
print("\nNow testing via HTTP (simulating actual frontend calls)...")
print("Use the tokens above with curl to test the actual API endpoint.")

# Print tokens for curl testing
print(f"\n  Scenario 1 org token: {org1['invitation_token']}")
print(f"  Scenario 1 part token: {part1['invitation_token']}")
print(f"  Scenario 3 unauth token: {part3['invitation_token']}")
print(f"  Scenario 4 invited token: {part4['invitation_token']}")
print(f"  Scenario 4 apt_id: {apt4['appointment_id']}")
