"""
Migration script: Fix participants with status 'guarantee_released' that were actually cancelled.
The bug: StripeGuaranteeService.release_guarantee() was overwriting the business status
'cancelled_by_participant' with the financial status 'guarantee_released'.

This script restores the correct business status for historical data.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from database import db

def fix_guarantee_released_participants():
    # Case 1: Participants with guarantee_released AND cancelled_at → were cancelled
    result_cancelled = db.participants.update_many(
        {"status": "guarantee_released", "cancelled_at": {"$ne": None}},
        {"$set": {"status": "cancelled_by_participant"}}
    )
    print(f"[FIX] {result_cancelled.modified_count} participant(s) restored to 'cancelled_by_participant' (had cancelled_at)")

    # Case 2: Participants with guarantee_released AND declined_at → were declined
    result_declined = db.participants.update_many(
        {"status": "guarantee_released", "declined_at": {"$ne": None}},
        {"$set": {"status": "declined"}}
    )
    print(f"[FIX] {result_declined.modified_count} participant(s) restored to 'declined' (had declined_at)")

    # Report remaining guarantee_released (legitimate cases: appointment ended normally)
    remaining = db.participants.count_documents({"status": "guarantee_released"})
    print(f"[INFO] {remaining} participant(s) still have 'guarantee_released' (legitimate post-appointment releases)")

if __name__ == "__main__":
    fix_guarantee_released_participants()
