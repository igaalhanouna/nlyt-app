"""
Migration script: Fix orphan participants (user_id=None) and disputes (target_user_id=None).

Run with: cd /app/backend && python3 scripts/fix_orphan_participants.py
Set DRY_RUN=False to apply changes.
"""
import pymongo
import os

DRY_RUN = True

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
client = pymongo.MongoClient(MONGO_URL)
db = client[DB_NAME]


def fix_participants():
    """Link participants with user_id=None to their user accounts via email."""
    orphans = list(db.participants.find({"user_id": None}, {"_id": 0, "participant_id": 1, "email": 1}))
    print(f"[PARTICIPANTS] Found {len(orphans)} with user_id=None")

    fixed = 0
    skipped = 0
    for p in orphans:
        email = p.get("email")
        if not email:
            skipped += 1
            continue
        user = db.users.find_one({"email": email}, {"_id": 0, "user_id": 1})
        if not user:
            skipped += 1
            continue

        real_uid = user["user_id"]
        if DRY_RUN:
            print(f"  [DRY] Would set pid={p['participant_id'][:12]}... ({email}) -> uid={real_uid[:12]}...")
        else:
            db.participants.update_one(
                {"participant_id": p["participant_id"]},
                {"$set": {"user_id": real_uid}}
            )
        fixed += 1

    print(f"  Fixed: {fixed}, Skipped (no account): {skipped}")
    return fixed


def fix_disputes():
    """Fix disputes with target_user_id=None by resolving from participant -> email -> user."""
    orphan_disputes = list(db.declarative_disputes.find(
        {"$or": [{"target_user_id": None}, {"target_user_id": ""}]},
        {"_id": 0, "dispute_id": 1, "target_participant_id": 1}
    ))
    print(f"\n[DISPUTES] Found {len(orphan_disputes)} with target_user_id=None/empty")

    fixed = 0
    for d in orphan_disputes:
        p = db.participants.find_one(
            {"participant_id": d["target_participant_id"]},
            {"_id": 0, "email": 1, "user_id": 1}
        )
        if not p:
            print(f"  [SKIP] Dispute {d['dispute_id'][:12]}... - participant not found")
            continue

        # Try participant.user_id first (may have been fixed by fix_participants)
        uid = p.get("user_id")
        if not uid and p.get("email"):
            user = db.users.find_one({"email": p["email"]}, {"_id": 0, "user_id": 1})
            uid = user.get("user_id") if user else None

        if not uid:
            print(f"  [SKIP] Dispute {d['dispute_id'][:12]}... - no user account for {p.get('email')}")
            continue

        if DRY_RUN:
            print(f"  [DRY] Would set dispute {d['dispute_id'][:12]}... target_user_id={uid[:12]}...")
        else:
            db.declarative_disputes.update_one(
                {"dispute_id": d["dispute_id"]},
                {"$set": {"target_user_id": uid}}
            )
        fixed += 1

    print(f"  Fixed: {fixed}")
    return fixed


if __name__ == "__main__":
    mode = "DRY RUN" if DRY_RUN else "LIVE"
    print(f"=== Fix Orphan Participants & Disputes ({mode}) ===\n")

    p_fixed = fix_participants()
    d_fixed = fix_disputes()

    print(f"\n=== Summary ({mode}) ===")
    print(f"  Participants to fix: {p_fixed}")
    print(f"  Disputes to fix: {d_fixed}")

    if DRY_RUN:
        print("\n  Set DRY_RUN=False to apply changes.")
