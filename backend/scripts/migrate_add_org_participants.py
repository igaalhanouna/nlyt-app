"""
Migration: Add missing organizer participants.

Adds an organizer participant record for every appointment that doesn't have one.
Idempotent — safe to run multiple times.

Usage:
    cd /app/backend && python scripts/migrate_add_org_participants.py
    cd /app/backend && python scripts/migrate_add_org_participants.py --dry-run
"""
import os
import sys
import uuid
import logging
import argparse
from datetime import datetime, timezone

import pymongo

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("migrate_org_participants")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


def run(dry_run: bool = False):
    client = pymongo.MongoClient(MONGO_URL)
    db = client[DB_NAME]
    now = datetime.now(timezone.utc).isoformat()

    # 1. Collect appointment_ids that already have an organizer participant
    existing = set()
    for p in db.participants.find({"is_organizer": True}, {"_id": 0, "appointment_id": 1}):
        existing.add(p["appointment_id"])

    # 2. Find all appointments missing an organizer participant
    all_apts = list(db.appointments.find(
        {"status": {"$ne": "deleted"}},
        {"_id": 0, "appointment_id": 1, "organizer_id": 1, "created_at": 1, "title": 1}
    ))
    missing = [a for a in all_apts if a["appointment_id"] not in existing]

    log.info(f"Total appointments: {len(all_apts)}")
    log.info(f"Already have org-participant: {len(existing)}")
    log.info(f"Missing org-participant: {len(missing)}")

    if not missing:
        log.info("Nothing to migrate.")
        return

    # 3. Pre-load all users by user_id for fast lookup
    user_ids = set(a.get("organizer_id") for a in missing if a.get("organizer_id"))
    users_by_id = {}
    for u in db.users.find({"user_id": {"$in": list(user_ids)}}, {"_id": 0, "user_id": 1, "email": 1, "first_name": 1, "last_name": 1}):
        users_by_id[u["user_id"]] = u

    # 4. Pre-load existing participant emails per appointment (avoid duplicates)
    existing_emails = {}
    for p in db.participants.find(
        {"appointment_id": {"$in": [a["appointment_id"] for a in missing]}},
        {"_id": 0, "appointment_id": 1, "email": 1}
    ):
        existing_emails.setdefault(p["appointment_id"], set()).add(
            (p.get("email") or "").strip().lower()
        )

    # 5. Build org-participant documents
    to_insert = []
    skipped_no_user = 0
    skipped_duplicate_email = 0

    for apt in missing:
        organizer_id = apt.get("organizer_id")
        if not organizer_id or organizer_id not in users_by_id:
            skipped_no_user += 1
            log.warning(f"  SKIP {apt['appointment_id'][:12]}... — organizer_id={organizer_id} not found in users")
            continue

        user = users_by_id[organizer_id]
        org_email = (user.get("email") or "").strip().lower()

        # Guard: if this email already exists as a participant, skip
        apt_emails = existing_emails.get(apt["appointment_id"], set())
        if org_email in apt_emails:
            skipped_duplicate_email += 1
            log.info(f"  SKIP {apt['appointment_id'][:12]}... — {org_email} already in participants")
            continue

        doc = {
            "participant_id": str(uuid.uuid4()),
            "appointment_id": apt["appointment_id"],
            "email": user.get("email", ""),
            "first_name": user.get("first_name", ""),
            "last_name": user.get("last_name", ""),
            "name": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
            "role": "organizer",
            "is_organizer": True,
            "status": "accepted_pending_guarantee",
            "invitation_token": str(uuid.uuid4()),
            "user_id": organizer_id,
            "accepted_at": apt.get("created_at", now),
            "invited_at": apt.get("created_at", now),
            "created_at": now,
            "updated_at": now,
            "migrated_at": now,
        }
        to_insert.append(doc)

    log.info(f"To insert: {len(to_insert)}")
    log.info(f"Skipped (no user): {skipped_no_user}")
    log.info(f"Skipped (duplicate email): {skipped_duplicate_email}")

    if dry_run:
        log.info("DRY RUN — no changes applied.")
        for doc in to_insert[:5]:
            log.info(f"  Would insert: apt={doc['appointment_id'][:12]}... email={doc['email']}")
        if len(to_insert) > 5:
            log.info(f"  ... and {len(to_insert) - 5} more")
        return

    # 6. Insert
    if to_insert:
        result = db.participants.insert_many(to_insert)
        log.info(f"Inserted {len(result.inserted_ids)} org-participant records.")
    else:
        log.info("Nothing to insert.")

    # 7. Verify
    post_existing = db.participants.count_documents({"is_organizer": True})
    log.info(f"Verification: {post_existing} org-participant records total (was {len(existing)})")

    log.info("Migration complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
