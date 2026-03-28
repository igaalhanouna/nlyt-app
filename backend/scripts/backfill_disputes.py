"""Backfill accuser_user_id on existing disputes created before Phase 2."""
import sys
sys.path.insert(0, "/app/backend")

from database import db

disputes = list(db.declarative_disputes.find(
    {"accuser_user_id": {"$exists": False}},
    {"_id": 0}
))
print(f"Found {len(disputes)} disputes without accuser_user_id")

updated = 0
for d in disputes:
    apt = db.appointments.find_one(
        {"appointment_id": d["appointment_id"]},
        {"_id": 0, "organizer_id": 1}
    )
    if apt and apt.get("organizer_id"):
        db.declarative_disputes.update_one(
            {"dispute_id": d["dispute_id"]},
            {"$set": {
                "accuser_user_id": apt["organizer_id"],
                "accused_participant_id": d.get("target_participant_id"),
                "accused_user_id": d.get("target_user_id"),
                "decision": None,
                "decision_at": None,
                "decision_by": None,
            }}
        )
        updated += 1

print(f"Backfilled {updated} disputes")
