"""
Seed script for Declarative Phase testing (Iteration 108)
Creates test data for:
- AttendanceSheetPage
- DisputesListPage
- DisputeDetailPage
- AppointmentDetail CTA banners
"""
import uuid
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
import os

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'test_database')

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

# Test user IDs from credentials
ORGANIZER_USER_ID = "7a074c87-ac40-4d2f-861d-4f5e630d5aa8"
ORGANIZER_EMAIL = "igaal.hanouna@gmail.com"

def now_utc():
    return datetime.now(timezone.utc)

def seed_declarative_test_data():
    """Seed test data for declarative phase testing."""
    
    # Find an existing active appointment for the organizer
    existing_apt = db.appointments.find_one({
        "organizer_id": ORGANIZER_USER_ID,
        "status": "active"
    }, {"_id": 0})
    
    if not existing_apt:
        print("No active appointment found for organizer. Creating one...")
        # Create a test appointment
        appointment_id = f"test-declarative-apt-{uuid.uuid4().hex[:8]}"
        start_time = now_utc() - timedelta(hours=2)  # Past appointment
        
        db.appointments.insert_one({
            "appointment_id": appointment_id,
            "organizer_id": ORGANIZER_USER_ID,
            "title": "Test Declarative Phase RDV",
            "start_datetime": start_time.isoformat(),
            "duration_minutes": 60,
            "status": "active",
            "appointment_type": "physical",
            "location": "Paris, France",
            "penalty_amount": 10,
            "penalty_currency": "eur",
            "created_at": now_utc().isoformat(),
            "declarative_phase": None,
            "attendance_evaluated": True,
        })
        print(f"Created appointment: {appointment_id}")
    else:
        appointment_id = existing_apt['appointment_id']
        print(f"Using existing appointment: {appointment_id}")
    
    # Get participants for this appointment
    participants = list(db.participants.find(
        {"appointment_id": appointment_id},
        {"_id": 0}
    ))
    
    if len(participants) < 2:
        print("Not enough participants. Creating test participants...")
        # Create organizer participant
        org_participant_id = f"part-org-{uuid.uuid4().hex[:8]}"
        db.participants.update_one(
            {"appointment_id": appointment_id, "user_id": ORGANIZER_USER_ID},
            {"$setOnInsert": {
                "participant_id": org_participant_id,
                "appointment_id": appointment_id,
                "user_id": ORGANIZER_USER_ID,
                "email": ORGANIZER_EMAIL,
                "first_name": "Igaal",
                "last_name": "Hanouna",
                "status": "accepted_guaranteed",
                "is_organizer": True,
                "invitation_token": f"inv-{uuid.uuid4().hex[:8]}",
                "created_at": now_utc().isoformat(),
            }},
            upsert=True
        )
        
        # Create test participant 1
        part1_id = f"part-test1-{uuid.uuid4().hex[:8]}"
        part1_user_id = f"user-test1-{uuid.uuid4().hex[:8]}"
        db.participants.update_one(
            {"appointment_id": appointment_id, "email": "test1@example.com"},
            {"$setOnInsert": {
                "participant_id": part1_id,
                "appointment_id": appointment_id,
                "user_id": part1_user_id,
                "email": "test1@example.com",
                "first_name": "Jean",
                "last_name": "Dupont",
                "status": "accepted_guaranteed",
                "is_organizer": False,
                "invitation_token": f"inv-{uuid.uuid4().hex[:8]}",
                "created_at": now_utc().isoformat(),
            }},
            upsert=True
        )
        
        # Create test participant 2
        part2_id = f"part-test2-{uuid.uuid4().hex[:8]}"
        part2_user_id = f"user-test2-{uuid.uuid4().hex[:8]}"
        db.participants.update_one(
            {"appointment_id": appointment_id, "email": "test2@example.com"},
            {"$setOnInsert": {
                "participant_id": part2_id,
                "appointment_id": appointment_id,
                "user_id": part2_user_id,
                "email": "test2@example.com",
                "first_name": "Marie",
                "last_name": "Martin",
                "status": "accepted_guaranteed",
                "is_organizer": False,
                "invitation_token": f"inv-{uuid.uuid4().hex[:8]}",
                "created_at": now_utc().isoformat(),
            }},
            upsert=True
        )
        
        participants = list(db.participants.find(
            {"appointment_id": appointment_id},
            {"_id": 0}
        ))
    
    print(f"Found {len(participants)} participants")
    
    # Get participant IDs
    org_participant = next((p for p in participants if p.get('is_organizer')), participants[0])
    other_participants = [p for p in participants if p['participant_id'] != org_participant['participant_id']]
    
    if not other_participants:
        print("ERROR: Need at least 2 participants for declarative phase testing")
        return None, None
    
    target_participant = other_participants[0]
    
    print(f"Organizer participant: {org_participant['participant_id']}")
    print(f"Target participant for review: {target_participant['participant_id']}")
    
    # ═══════════════════════════════════════════════════════════════════
    # SCENARIO 1: Attendance Sheet (collecting phase)
    # ═══════════════════════════════════════════════════════════════════
    
    # Create attendance_sheet for the organizer
    sheet_id = f"sheet-{uuid.uuid4().hex[:8]}"
    deadline = now_utc() + timedelta(hours=48)
    
    # Delete existing sheets for this appointment
    db.attendance_sheets.delete_many({"appointment_id": appointment_id})
    
    # Create sheet for organizer to fill
    db.attendance_sheets.insert_one({
        "sheet_id": sheet_id,
        "appointment_id": appointment_id,
        "submitted_by_user_id": ORGANIZER_USER_ID,
        "submitted_by_participant_id": org_participant['participant_id'],
        "status": "pending",
        "submitted_at": None,
        "declarations": [
            {
                "target_participant_id": target_participant['participant_id'],
                "target_user_id": target_participant.get('user_id', ''),
                "target_name": f"{target_participant.get('first_name', '')} {target_participant.get('last_name', '')}".strip() or target_participant.get('email', 'Participant'),
                "declared_status": None,
            }
        ],
        "created_at": now_utc().isoformat(),
        "deadline": deadline.isoformat(),
    })
    print(f"Created attendance sheet: {sheet_id}")
    
    # Set appointment to collecting phase
    db.appointments.update_one(
        {"appointment_id": appointment_id},
        {"$set": {
            "declarative_phase": "collecting",
            "declarative_deadline": deadline.isoformat(),
        }}
    )
    print(f"Set appointment {appointment_id} to declarative_phase='collecting'")
    
    # ═══════════════════════════════════════════════════════════════════
    # SCENARIO 2: Dispute (for DisputesListPage and DisputeDetailPage)
    # ═══════════════════════════════════════════════════════════════════
    
    # Create a second appointment for dispute testing
    dispute_apt_id = f"test-dispute-apt-{uuid.uuid4().hex[:8]}"
    dispute_start = now_utc() - timedelta(days=1)
    
    db.appointments.update_one(
        {"appointment_id": dispute_apt_id},
        {"$setOnInsert": {
            "appointment_id": dispute_apt_id,
            "organizer_id": ORGANIZER_USER_ID,
            "title": "Test Dispute RDV",
            "start_datetime": dispute_start.isoformat(),
            "duration_minutes": 60,
            "status": "active",
            "appointment_type": "physical",
            "location": "Lyon, France",
            "penalty_amount": 15,
            "penalty_currency": "eur",
            "created_at": now_utc().isoformat(),
            "declarative_phase": "disputed",
            "attendance_evaluated": True,
        }},
        upsert=True
    )
    
    # Create participants for dispute appointment
    dispute_org_pid = f"part-dispute-org-{uuid.uuid4().hex[:8]}"
    db.participants.update_one(
        {"appointment_id": dispute_apt_id, "user_id": ORGANIZER_USER_ID},
        {"$setOnInsert": {
            "participant_id": dispute_org_pid,
            "appointment_id": dispute_apt_id,
            "user_id": ORGANIZER_USER_ID,
            "email": ORGANIZER_EMAIL,
            "first_name": "Igaal",
            "last_name": "Hanouna",
            "status": "accepted_guaranteed",
            "is_organizer": True,
            "invitation_token": f"inv-{uuid.uuid4().hex[:8]}",
            "created_at": now_utc().isoformat(),
        }},
        upsert=True
    )
    
    dispute_target_pid = f"part-dispute-target-{uuid.uuid4().hex[:8]}"
    dispute_target_uid = f"user-dispute-target-{uuid.uuid4().hex[:8]}"
    db.participants.update_one(
        {"appointment_id": dispute_apt_id, "email": "dispute-target@example.com"},
        {"$setOnInsert": {
            "participant_id": dispute_target_pid,
            "appointment_id": dispute_apt_id,
            "user_id": dispute_target_uid,
            "email": "dispute-target@example.com",
            "first_name": "Pierre",
            "last_name": "Durand",
            "status": "accepted_guaranteed",
            "is_organizer": False,
            "invitation_token": f"inv-{uuid.uuid4().hex[:8]}",
            "created_at": now_utc().isoformat(),
        }},
        upsert=True
    )
    
    # Get actual participant IDs
    dispute_org = db.participants.find_one({"appointment_id": dispute_apt_id, "user_id": ORGANIZER_USER_ID}, {"_id": 0})
    dispute_target = db.participants.find_one({"appointment_id": dispute_apt_id, "email": "dispute-target@example.com"}, {"_id": 0})
    
    # Create dispute
    dispute_id = f"dispute-{uuid.uuid4().hex[:8]}"
    dispute_deadline = now_utc() + timedelta(days=7)
    
    # Delete existing disputes for this appointment
    db.declarative_disputes.delete_many({"appointment_id": dispute_apt_id})
    
    db.declarative_disputes.insert_one({
        "dispute_id": dispute_id,
        "appointment_id": dispute_apt_id,
        "target_participant_id": dispute_target['participant_id'],
        "target_user_id": dispute_target.get('user_id', ''),
        "status": "awaiting_evidence",
        "opened_at": now_utc().isoformat(),
        "opened_reason": "tiers_disagreement",
        "resolution": {
            "resolved_at": None,
            "resolved_by": None,
            "final_outcome": None,
            "resolution_note": None,
        },
        "evidence_submissions": [],
        "escalated_at": None,
        "deadline": dispute_deadline.isoformat(),
        "created_at": now_utc().isoformat(),
    })
    print(f"Created dispute: {dispute_id}")
    
    # ═══════════════════════════════════════════════════════════════════
    # SCENARIO 3: Resolved dispute (for testing resolution display)
    # ═══════════════════════════════════════════════════════════════════
    
    resolved_dispute_id = f"dispute-resolved-{uuid.uuid4().hex[:8]}"
    db.declarative_disputes.insert_one({
        "dispute_id": resolved_dispute_id,
        "appointment_id": dispute_apt_id,
        "target_participant_id": dispute_org['participant_id'],
        "target_user_id": ORGANIZER_USER_ID,
        "status": "resolved",
        "opened_at": (now_utc() - timedelta(days=5)).isoformat(),
        "opened_reason": "contestant_contradiction",
        "resolution": {
            "resolved_at": (now_utc() - timedelta(days=2)).isoformat(),
            "resolved_by": "platform",
            "final_outcome": "on_time",
            "resolution_note": "Preuves complémentaires validées - présence confirmée",
        },
        "evidence_submissions": [
            {
                "submission_id": f"sub-{uuid.uuid4().hex[:8]}",
                "submitted_by_user_id": ORGANIZER_USER_ID,
                "submitted_at": (now_utc() - timedelta(days=3)).isoformat(),
                "evidence_type": "text_statement",
                "content_url": None,
                "text_content": "J'étais bien présent, voici ma déclaration.",
            }
        ],
        "escalated_at": None,
        "deadline": (now_utc() - timedelta(days=1)).isoformat(),
        "created_at": (now_utc() - timedelta(days=5)).isoformat(),
    })
    print(f"Created resolved dispute: {resolved_dispute_id}")
    
    print("\n" + "="*60)
    print("SEED DATA SUMMARY")
    print("="*60)
    print(f"Appointment for AttendanceSheet (collecting): {appointment_id}")
    print(f"Appointment for Disputes (disputed): {dispute_apt_id}")
    print(f"Open dispute ID: {dispute_id}")
    print(f"Resolved dispute ID: {resolved_dispute_id}")
    print("="*60)
    
    return {
        "collecting_appointment_id": appointment_id,
        "disputed_appointment_id": dispute_apt_id,
        "open_dispute_id": dispute_id,
        "resolved_dispute_id": resolved_dispute_id,
        "sheet_id": sheet_id,
    }


def cleanup_test_data():
    """Clean up test data created by this script."""
    # Delete test appointments
    db.appointments.delete_many({"appointment_id": {"$regex": "^test-"}})
    db.participants.delete_many({"appointment_id": {"$regex": "^test-"}})
    db.attendance_sheets.delete_many({"appointment_id": {"$regex": "^test-"}})
    db.declarative_disputes.delete_many({"appointment_id": {"$regex": "^test-"}})
    print("Cleaned up test data")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        cleanup_test_data()
    else:
        result = seed_declarative_test_data()
        if result:
            print("\nTest data seeded successfully!")
            print(f"Use these IDs for testing:")
            for key, value in result.items():
                print(f"  {key}: {value}")
