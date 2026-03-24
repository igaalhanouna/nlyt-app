"""
Centralized MongoDB connection — single MongoClient for the entire application.

Usage in any router or service:
    from database import db
"""
import os
from pymongo import MongoClient, ASCENDING, DESCENDING

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')

client = MongoClient(MONGO_URL)
db = client[DB_NAME]


def ensure_indexes():
    """Create indexes for performance. Safe to call multiple times (idempotent)."""

    # appointments — dashboard listing, time filters, conflict detection
    db.appointments.create_index([("workspace_id", ASCENDING), ("status", ASCENDING)])
    db.appointments.create_index([("start_datetime", ASCENDING)])
    db.appointments.create_index("appointment_id", unique=True)

    # participants — lookup by appointment, by token, by status
    db.participants.create_index("appointment_id")
    db.participants.create_index("invitation_token", unique=True, sparse=True)
    db.participants.create_index("participant_id", unique=True)

    # calendar_sync_logs — retry job, sync status lookup
    db.calendar_sync_logs.create_index([("appointment_id", ASCENDING), ("connection_id", ASCENDING)])
    db.calendar_sync_logs.create_index([("sync_status", ASCENDING), ("next_retry_at", ASCENDING)])
    db.calendar_sync_logs.create_index("log_id", unique=True)

    # calendar_connections — user calendar listing
    db.calendar_connections.create_index([("user_id", ASCENDING), ("provider", ASCENDING)])
    db.calendar_connections.create_index("connection_id", unique=True)

    # payment_guarantees — participant guarantee lookup
    db.payment_guarantees.create_index([("participant_id", ASCENDING), ("appointment_id", ASCENDING)])
    db.payment_guarantees.create_index("guarantee_id", unique=True)

    # users — login, lookup
    db.users.create_index("email", unique=True)
    db.users.create_index("user_id", unique=True)

    # workspaces & memberships
    db.workspaces.create_index("workspace_id", unique=True)
    db.workspace_memberships.create_index("user_id")

    # wallets — user wallet lookup
    db.wallets.create_index("user_id")

    # stripe
    db.stripe_customers.create_index("email", unique=True, sparse=True)
    db.stripe_events.create_index("event_id", unique=True)

    # disputes, distributions, violation_cases
    db.disputes.create_index("dispute_id", unique=True)
    db.distributions.create_index("guarantee_id")
    db.violation_cases.create_index("appointment_id")

    # email idempotency
    db.sent_emails.create_index(
        [("email_type", ASCENDING), ("reference_id", ASCENDING), ("user_id", ASCENDING)],
        unique=True, name="unique_email_idempotency"
    )

    print("[DB] Indexes ensured")
