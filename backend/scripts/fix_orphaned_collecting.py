"""
Migration Script — Fix orphaned 'collecting' phases with < 2 guaranteed participants.

Finds appointments where:
  - declarative_phase = "collecting"
  - Fewer than 2 accepted_guaranteed participants are in manual_review
  → Auto-waives remaining manual_review records
  → Sets declarative_phase = "not_needed"

Context: Before V5.1 (deployed April 3, 2026), the declarative phase could
open even with a single guaranteed participant, creating an unsolvable state
(no one to cross-declare). This script cleans up those legacy records.
"""
import sys
sys.path.append('/app/backend')

from database import db
from datetime import datetime, timezone

def now_utc():
    return datetime.now(timezone.utc)

def fix_orphaned_collecting():
    # Find all appointments stuck in 'collecting'
    collecting_apts = list(db.appointments.find(
        {"declarative_phase": "collecting"},
        {"_id": 0, "appointment_id": 1, "title": 1, "organizer_id": 1}
    ))

    print(f"Appointments in 'collecting': {len(collecting_apts)}")

    fixed = 0
    for apt in collecting_apts:
        apt_id = apt["appointment_id"]

        # Count guaranteed participants in manual_review
        review_records = list(db.attendance_records.find(
            {"appointment_id": apt_id, "outcome": "manual_review", "review_required": True},
            {"_id": 0, "participant_id": 1}
        ))

        guaranteed_in_review = []
        for r in review_records:
            p = db.participants.find_one(
                {"participant_id": r["participant_id"]},
                {"_id": 0, "status": 1, "email": 1}
            )
            if p and p.get("status") == "accepted_guaranteed":
                guaranteed_in_review.append(r["participant_id"])

        if len(guaranteed_in_review) < 2:
            print(f"\n  [{apt_id}] '{apt.get('title', '?')}'")
            print(f"    manual_review records: {len(review_records)}")
            print(f"    guaranteed in review: {len(guaranteed_in_review)}")
            print(f"    -> Auto-waiving {len(review_records)} records, setting phase to 'not_needed'")

            now = now_utc()
            # Auto-waive ALL manual_review records for this appointment
            for r in review_records:
                db.attendance_records.update_one(
                    {"appointment_id": apt_id, "participant_id": r["participant_id"]},
                    {"$set": {
                        "outcome": "waived",
                        "review_required": False,
                        "decision_source": "migration_insufficient_guaranteed",
                        "confidence_level": "HIGH",
                        "decided_by": "migration_script",
                        "decided_at": now.isoformat(),
                    }}
                )

            # Set phase to not_needed
            db.appointments.update_one(
                {"appointment_id": apt_id},
                {"$set": {
                    "declarative_phase": "not_needed",
                    "updated_at": now.isoformat(),
                }}
            )

            # Clean up orphaned pending sheets
            deleted = db.attendance_sheets.delete_many(
                {"appointment_id": apt_id, "status": "pending"}
            ).deleted_count
            if deleted:
                print(f"    -> Deleted {deleted} orphaned pending sheets")

            fixed += 1
        else:
            print(f"  [{apt_id}] OK — {len(guaranteed_in_review)} guaranteed in review")

    print(f"\nDone. Fixed {fixed} orphaned appointments.")
    return fixed


if __name__ == "__main__":
    fix_orphaned_collecting()
