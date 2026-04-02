"""
Migration script: Resolve legacy V4 disputes that should never have been created.

Targets:
- Auto-litiges (target_user_id == organizer_user_id) → waived, auto_no_self_dispute
- Unknown-based disputes (opened_reason = fewer_than_2_expressed | no_declarations_received)
  where no explicit absence was ever declared → waived, declarative_presumption

For each resolved dispute:
1. Mark dispute as resolved
2. Update attendance_record outcome to 'waived'
3. If ALL disputes for an appointment are now resolved → update declarative_phase to 'resolved'
   and trigger financial engine for guarantee release

Run: cd /app/backend && DB_NAME=test_database MONGO_URL=mongodb://localhost:27017 python scripts/fix_v4_legacy_disputes.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import db
from utils.date_utils import now_utc

DRY_RUN = False  # Set to True to preview without modifying

def main():
    timestamp = now_utc().isoformat()

    # Find all non-resolved disputes with legacy reasons
    legacy_reasons = {"fewer_than_2_expressed", "no_declarations_received"}
    disputes = list(db.declarative_disputes.find(
        {"status": {"$ne": "resolved"}, "opened_reason": {"$in": list(legacy_reasons)}},
        {"_id": 0}
    ))

    print(f"[MIGRATION] Found {len(disputes)} legacy V4 disputes to process")
    if not disputes:
        print("[MIGRATION] Nothing to do. Exiting.")
        return

    resolved_count = 0
    auto_litige_count = 0
    unknown_based_count = 0
    appointments_to_check = set()

    for d in disputes:
        dispute_id = d["dispute_id"]
        apt_id = d["appointment_id"]
        target_pid = d["target_participant_id"]
        is_auto_litige = (
            d.get("target_user_id")
            and d.get("organizer_user_id")
            and d["target_user_id"] == d["organizer_user_id"]
        )

        # Determine decision source
        if is_auto_litige:
            decision_source = "auto_no_self_dispute"
            resolution_note = "Migration V5: auto-litige bloque retroactivement (target == organizer)."
            auto_litige_count += 1
        else:
            decision_source = "declarative_presumption"
            resolution_note = "Migration V5: absence d'information (toutes declarations unknown). Presomption de presence appliquee."
            unknown_based_count += 1

        print(f"  [{dispute_id[:12]}] apt={apt_id[:12]} | auto-litige={is_auto_litige} | → waived ({decision_source})")

        if DRY_RUN:
            continue

        # 1. Resolve the dispute
        db.declarative_disputes.update_one(
            {"dispute_id": dispute_id},
            {"$set": {
                "status": "resolved",
                "resolution": {
                    "resolved_at": timestamp,
                    "resolved_by": "migration_v5",
                    "final_outcome": "waived",
                    "resolution_note": resolution_note,
                },
            }}
        )

        # 2. Update attendance record
        db.attendance_records.update_one(
            {"appointment_id": apt_id, "participant_id": target_pid},
            {"$set": {
                "outcome": "waived",
                "review_required": False,
                "decision_source": decision_source,
                "confidence_level": "LOW",
                "decided_by": "migration_v5",
                "decided_at": timestamp,
            }}
        )

        resolved_count += 1
        appointments_to_check.add(apt_id)

    # 3. For each affected appointment, check if ALL disputes are now resolved
    phase_updated = 0
    for apt_id in appointments_to_check:
        open_disputes = db.declarative_disputes.count_documents({
            "appointment_id": apt_id,
            "status": {"$ne": "resolved"}
        })
        if open_disputes == 0:
            db.appointments.update_one(
                {"appointment_id": apt_id},
                {"$set": {"declarative_phase": "resolved"}}
            )
            phase_updated += 1
            print(f"  [PHASE] {apt_id[:12]} → declarative_phase = 'resolved' (all disputes resolved)")

            # Trigger financial engine for guarantee release
            try:
                from services.attendance_service import reset_cas_a_overrides, _process_financial_outcomes
                reset_cas_a_overrides(apt_id)
                appointment = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
                participants = list(db.participants.find({"appointment_id": apt_id}, {"_id": 0}))
                _process_financial_outcomes(
                    apt_id, appointment, participants,
                    immediate_release=True, release_reason="migration_v5_cleanup",
                )
                print(f"  [FINANCIAL] {apt_id[:12]} → financial engine relaunched (immediate release)")
            except Exception as e:
                print(f"  [FINANCIAL][WARN] {apt_id[:12]} → financial engine failed: {e}")

    print(f"\n{'='*60}")
    print(f"[MIGRATION COMPLETE]")
    print(f"  Disputes resolved: {resolved_count}")
    print(f"    - Auto-litiges: {auto_litige_count}")
    print(f"    - Unknown-based: {unknown_based_count}")
    print(f"  Appointments phase updated: {phase_updated}")
    print(f"  DRY_RUN: {DRY_RUN}")


if __name__ == "__main__":
    main()
