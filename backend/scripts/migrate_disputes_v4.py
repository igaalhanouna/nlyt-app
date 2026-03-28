"""Migrate existing disputes from Phase 2 (accuser/accused asymmetric)
to V4 (symmetric positions). Run once."""
import sys
sys.path.insert(0, "/app/backend")
import os
os.environ.setdefault("DB_NAME", "test_database")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")

from database import db

disputes = list(db.declarative_disputes.find({}, {"_id": 0}))
print(f"Found {len(disputes)} total disputes")

migrated = 0
for d in disputes:
    update = {}

    # Get organizer_user_id from appointment if not already present
    if "organizer_user_id" not in d:
        apt = db.appointments.find_one(
            {"appointment_id": d["appointment_id"]},
            {"_id": 0, "organizer_id": 1}
        )
        update["organizer_user_id"] = apt.get("organizer_id") if apt else d.get("accuser_user_id")

    # Add symmetric position fields if missing
    if "organizer_position" not in d:
        # Map old decision to new positions
        old_decision = d.get("decision")
        if old_decision == "conceded":
            update["organizer_position"] = "confirmed_present"
            update["organizer_position_at"] = d.get("decision_at")
        elif old_decision == "maintained":
            update["organizer_position"] = "confirmed_absent"
            update["organizer_position_at"] = d.get("decision_at")
        else:
            update["organizer_position"] = None
            update["organizer_position_at"] = None

    if "participant_position" not in d:
        update["participant_position"] = None
        update["participant_position_at"] = None

    # Map old status to new status
    old_status = d.get("status")
    if old_status == "awaiting_evidence":
        update["status"] = "awaiting_positions"
    # Keep escalated/resolved as-is

    if update:
        db.declarative_disputes.update_one(
            {"dispute_id": d["dispute_id"]},
            {"$set": update}
        )
        migrated += 1

print(f"Migrated {migrated} disputes to V4 symmetric schema")
