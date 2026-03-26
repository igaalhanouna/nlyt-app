"""Create a test appointment with proper time window for E2E testing"""
import os, uuid
from datetime import datetime, timedelta, timezone

os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
os.environ.setdefault('DB_NAME', 'test_database')

from database import db

# Clean previous E2E test data
db.appointments.delete_many({"title": "E2E Check-in Test"})
db.participants.delete_many({"email": {"$regex": "e2e-checkin"}})
db.evidence.delete_many({"device_info": {"$regex": "e2e"}})

now = datetime.now(timezone.utc)
# Start 10 minutes from now — this puts us within the 30-min pre-window
start = now + timedelta(minutes=10)

apt_id = str(uuid.uuid4())
apt = {
    "appointment_id": apt_id,
    "title": "E2E Check-in Test",
    "appointment_type": "physical",
    "status": "active",
    "workspace_id": "test-ws-e2e",
    "organizer_user_id": "test-org-user-e2e",
    "start_datetime": start.strftime("%Y-%m-%dT%H:%M:%S"),
    "duration_minutes": 60,
    "location": "48.8566, 2.3522",
    "latitude": 48.8566,
    "longitude": 2.3522,
    "tolerated_delay_minutes": 15,
    "stake_per_person": 10,
    "charity_percentage": 50,
    "created_at": now.isoformat(),
}
db.appointments.insert_one(apt)

# Create organizer participant
org_token = str(uuid.uuid4())
org = {
    "participant_id": str(uuid.uuid4()),
    "appointment_id": apt_id,
    "first_name": "Organisateur",
    "last_name": "Test",
    "email": "org-e2e-checkin@test.com",
    "status": "accepted_guaranteed",
    "is_organizer": True,
    "invitation_token": org_token,
    "created_at": now.isoformat(),
}
db.participants.insert_one(org)

# Create accepted participant (standard)
part1_token = str(uuid.uuid4())
part1 = {
    "participant_id": str(uuid.uuid4()),
    "appointment_id": apt_id,
    "first_name": "Participant",
    "last_name": "Accepté",
    "email": "part1-e2e-checkin@test.com",
    "status": "accepted",
    "is_organizer": False,
    "invitation_token": part1_token,
    "created_at": now.isoformat(),
    "accepted_at": now.isoformat(),
}
db.participants.insert_one(part1)

# Create accepted_pending_guarantee participant
part2_token = str(uuid.uuid4())
part2 = {
    "participant_id": str(uuid.uuid4()),
    "appointment_id": apt_id,
    "first_name": "Participant",
    "last_name": "PendingGuarantee",
    "email": "part2-e2e-checkin@test.com",
    "status": "accepted_pending_guarantee",
    "is_organizer": False,
    "invitation_token": part2_token,
    "created_at": now.isoformat(),
    "accepted_at": now.isoformat(),
}
db.participants.insert_one(part2)

# Create invited (not accepted) participant
part3_token = str(uuid.uuid4())
part3 = {
    "participant_id": str(uuid.uuid4()),
    "appointment_id": apt_id,
    "first_name": "Participant",
    "last_name": "Invité",
    "email": "part3-e2e-checkin@test.com",
    "status": "invited",
    "is_organizer": False,
    "invitation_token": part3_token,
    "created_at": now.isoformat(),
}
db.participants.insert_one(part3)

print("=== E2E Test Data Created ===")
print(f"Appointment: {apt_id}")
print(f"Start: {start.isoformat()} (in ~10 min)")
print(f"Window opens: {(start - timedelta(minutes=30)).isoformat()} (already open)")
print(f"Now: {now.isoformat()}")
print()
print(f"Organizer token:    {org_token}")
print(f"Accepted token:     {part1_token}")
print(f"Pending guar token: {part2_token}")
print(f"Invited token:      {part3_token}")
print()
print(f"Invitation URLs:")
base = os.environ.get('FRONTEND_URL', 'https://checkin-bug-fix.preview.emergentagent.com')
print(f"  Organizer:        {base}/invitation/{org_token}")
print(f"  Accepted:         {base}/invitation/{part1_token}")
print(f"  Pending Guarantee:{base}/invitation/{part2_token}")
print(f"  Invited:          {base}/invitation/{part3_token}")
