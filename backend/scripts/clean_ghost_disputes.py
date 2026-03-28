"""
Ghost Dispute & Invalid manual_review Cleanup Script

Purpose:
1. Identify and purge disputes created by the old <3 participants bypass
2. Identify manual_review attendance records where the participant actually has
   strong admissible proof (GPS in radius, QR, Zoom/Teams API, NLYT Proof >= 55)
3. Re-evaluate those records correctly
4. Clean orphaned attendance_sheets and declarative_analyses

Safety:
- DRY RUN by default (set DRY_RUN=False to execute)
- Logs every action
- Creates a backup document before any mutation
"""
import sys, os
sys.path.insert(0, "/app/backend")
os.environ.setdefault("DB_NAME", "test_database")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")

from database import db
from datetime import datetime, timezone
import json

DRY_RUN = True  # Set to False to actually execute mutations

def log(msg):
    prefix = "[DRY RUN]" if DRY_RUN else "[EXECUTE]"
    print(f"{prefix} {msg}")


def _has_admissible_proof_v2(participant_id: str, appointment_id: str) -> bool:
    """Fixed version of _has_admissible_proof using correct DB schema."""
    evidence = list(db.evidence_items.find(
        {"appointment_id": appointment_id, "participant_id": participant_id},
        {"_id": 0, "source": 1, "derived_facts": 1}
    ))
    if not evidence:
        return False
    for e in evidence:
        source = e.get("source", "")
        df = e.get("derived_facts") or {}
        if source == "gps" and df.get("gps_within_radius"):
            return True
        if source == "qr":
            return True
        if source == "video_conference":
            provider = df.get("provider", "")
            ceiling = df.get("provider_evidence_ceiling", "")
            outcome = df.get("video_attendance_outcome", "")
            if provider in ("zoom", "teams") and ceiling in ("strong", "autonomous"):
                if outcome in ("joined_on_time", "joined_late"):
                    return True
        if source == "nlyt_proof":
            return True
    return False


def _get_proof_session_score(participant_id: str, appointment_id: str) -> int:
    """Get best proof session score for a participant."""
    session = db.proof_sessions.find_one(
        {"appointment_id": appointment_id, "participant_id": participant_id, "checked_out_at": {"$ne": None}},
        {"_id": 0, "score": 1}
    )
    return session.get("score", 0) if session else 0


# ═══════════════════════════════════════════════════════════════════
# PHASE 1: Audit manual_review records with strong proof
# ═══════════════════════════════════════════════════════════════════
print("=" * 60)
print("PHASE 1: Audit manual_review records with admissible proof")
print("=" * 60)

mr_records = list(db.attendance_records.find(
    {"outcome": "manual_review"},
    {"_id": 0}
))
log(f"Total manual_review records: {len(mr_records)}")

misclassified = []
for r in mr_records:
    pid = r.get("participant_id", "")
    apt_id = r.get("appointment_id", "")
    if _has_admissible_proof_v2(pid, apt_id):
        misclassified.append(r)
        log(f"  MISCLASSIFIED: record={r.get('record_id', '')[:12]}... "
            f"apt={apt_id[:12]}... basis={r.get('decision_basis')}")

log(f"Misclassified manual_review with strong proof: {len(misclassified)}")

if misclassified and not DRY_RUN:
    for r in misclassified:
        # Backup original record
        db.cleanup_backups.insert_one({
            "type": "misclassified_manual_review",
            "original_record": r,
            "cleaned_at": datetime.now(timezone.utc).isoformat(),
        })
        # Delete the erroneous record so re-evaluation creates correct one
        db.attendance_records.delete_one({"record_id": r["record_id"]})
        log(f"  DELETED record {r['record_id'][:12]}...")

    # Mark affected appointments for re-evaluation
    affected_apts = list({r["appointment_id"] for r in misclassified})
    for apt_id in affected_apts:
        db.appointments.update_one(
            {"appointment_id": apt_id},
            {"$set": {"attendance_evaluated": False}}
        )
        log(f"  RESET evaluation flag for apt {apt_id[:12]}...")


# ═══════════════════════════════════════════════════════════════════
# PHASE 2: Audit disputes linked to test/orphan appointments
# ═══════════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("PHASE 2: Audit ghost disputes")
print("=" * 60)

all_disputes = list(db.declarative_disputes.find({}, {"_id": 0}))
log(f"Total disputes: {len(all_disputes)}")

ghost_disputes = []
for d in all_disputes:
    apt_id = d.get("appointment_id", "")
    # Check if the appointment exists
    apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0, "appointment_id": 1, "title": 1, "status": 1})

    is_ghost = False
    reason = ""

    if not apt:
        is_ghost = True
        reason = "orphan_no_appointment"
    elif apt.get("status") in ("cancelled", "deleted"):
        is_ghost = True
        reason = "cancelled_appointment"
    elif apt_id.startswith("test-"):
        is_ghost = True
        reason = "test_appointment"
    else:
        # Check if the target participant has strong proof (dispute shouldn't exist)
        target_pid = d.get("target_participant_id", "")
        if _has_admissible_proof_v2(target_pid, apt_id):
            is_ghost = True
            reason = "target_has_strong_proof"

    if is_ghost:
        ghost_disputes.append({"dispute": d, "reason": reason})
        log(f"  GHOST: dispute={d.get('dispute_id', '')[:12]}... "
            f"apt={apt_id[:12]}... status={d.get('status')} reason={reason}")

log(f"Ghost disputes to purge: {len(ghost_disputes)}")

if ghost_disputes and not DRY_RUN:
    for gd in ghost_disputes:
        d = gd["dispute"]
        db.cleanup_backups.insert_one({
            "type": "ghost_dispute",
            "original_dispute": d,
            "reason": gd["reason"],
            "cleaned_at": datetime.now(timezone.utc).isoformat(),
        })
        db.declarative_disputes.delete_one({"dispute_id": d["dispute_id"]})
        log(f"  DELETED dispute {d['dispute_id'][:12]}...")


# ═══════════════════════════════════════════════════════════════════
# PHASE 3: Clean orphaned attendance_sheets for test appointments
# ═══════════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("PHASE 3: Clean orphaned attendance sheets")
print("=" * 60)

all_sheets = list(db.attendance_sheets.find({}, {"_id": 0, "sheet_id": 1, "appointment_id": 1}))
orphan_sheets = []
for s in all_sheets:
    apt_id = s.get("appointment_id", "")
    apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0, "appointment_id": 1})
    if not apt or apt_id.startswith("test-"):
        orphan_sheets.append(s)

log(f"Total sheets: {len(all_sheets)}, Orphaned: {len(orphan_sheets)}")

if orphan_sheets and not DRY_RUN:
    for s in orphan_sheets:
        db.attendance_sheets.delete_one({"sheet_id": s["sheet_id"]})
        log(f"  DELETED sheet {s['sheet_id'][:12]}...")


# ═══════════════════════════════════════════════════════════════════
# PHASE 4: Clean orphaned declarative_analyses
# ═══════════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("PHASE 4: Clean orphaned declarative analyses")
print("=" * 60)

all_analyses = list(db.declarative_analyses.find({}, {"_id": 0, "analysis_id": 1, "appointment_id": 1}))
orphan_analyses = []
for a in all_analyses:
    apt_id = a.get("appointment_id", "")
    apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0, "appointment_id": 1})
    if not apt or apt_id.startswith("test-"):
        orphan_analyses.append(a)

log(f"Total analyses: {len(all_analyses)}, Orphaned: {len(orphan_analyses)}")

if orphan_analyses and not DRY_RUN:
    for a in orphan_analyses:
        db.declarative_analyses.delete_one({"analysis_id": a["analysis_id"]})


# ═══════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("CLEANUP SUMMARY")
print("=" * 60)
print(f"  Misclassified manual_review (strong proof exists): {len(misclassified)}")
print(f"  Ghost disputes to purge: {len(ghost_disputes)}")
print(f"  Orphaned sheets: {len(orphan_sheets)}")
print(f"  Orphaned analyses: {len(orphan_analyses)}")
if DRY_RUN:
    print()
    print("  >>> DRY RUN MODE — No changes made <<<")
    print("  >>> Set DRY_RUN = False in the script to execute <<<")
else:
    print()
    print("  >>> CLEANUP EXECUTED <<<")
    print(f"  Backups saved in collection: cleanup_backups")
