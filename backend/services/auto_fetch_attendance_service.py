"""
Auto-Fetch Attendance Service

Automatically fetches attendance reports from Zoom/Teams after meetings end.
Called by the scheduler every 5 minutes.

Logic:
1. Find active video appointments where meeting has ended (start + duration < now)
2. Only Zoom and Teams (Meet has no attendance API)
3. Skip if attendance was already fetched (idempotent)
4. Attempt fetch, log results
5. Auto-ingest if successful
"""
import logging
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
import os

logger = logging.getLogger(__name__)

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
client = MongoClient(MONGO_URL)
db = client[DB_NAME]

# Providers that support auto-fetch
AUTO_FETCH_PROVIDERS = {"zoom", "teams", "microsoft teams"}

# How long after meeting end to keep trying (hours)
MAX_FETCH_WINDOW_HOURS = 2

# Grace period after meeting end before first attempt (minutes)
GRACE_PERIOD_MINUTES = 5


def run_auto_fetch_attendance_job():
    """
    Main job entry point. Finds eligible appointments and attempts auto-fetch.
    Idempotent: skips appointments that already have video evidence.
    """
    now = datetime.now(timezone.utc)
    fetched_count = 0
    skipped_count = 0
    error_count = 0

    # Find video appointments that:
    # - Are active
    # - Have a meeting created via API
    # - Use Zoom or Teams (not Meet)
    # - Meeting should have ended by now (start + duration + grace < now)
    eligible_appointments = list(db.appointments.find(
        {
            "status": "active",
            "appointment_type": "video",
            "meeting_created_via_api": True,
            "external_meeting_id": {"$exists": True, "$ne": None, "$ne": ""},
        },
        {"_id": 0}
    ))

    for apt in eligible_appointments:
        apt_id = apt.get("appointment_id", "")
        provider = (apt.get("meeting_provider") or "").lower()

        # Skip unsupported providers (Meet, external)
        if provider not in AUTO_FETCH_PROVIDERS:
            continue

        # Skip legacy (application_fallback) meetings — attendance not accessible via delegated token
        metadata = apt.get("meeting_provider_metadata") or {}
        if provider == "teams" and metadata.get("creation_mode") == "application_fallback":
            continue

        # Calculate meeting end time
        start_str = apt.get("start_datetime")
        duration_min = apt.get("duration_minutes", 60)
        if not start_str:
            continue

        try:
            from utils.date_utils import parse_iso_datetime
            start_dt = parse_iso_datetime(start_str)
            if not start_dt:
                continue
            meeting_end = start_dt + timedelta(minutes=duration_min)
            fetch_eligible_at = meeting_end + timedelta(minutes=GRACE_PERIOD_MINUTES)
            fetch_deadline = meeting_end + timedelta(hours=MAX_FETCH_WINDOW_HOURS)
        except Exception:
            continue

        # Skip if meeting hasn't ended yet (with grace period)
        if now < fetch_eligible_at:
            continue

        # Skip if past the fetch window
        if now > fetch_deadline:
            continue

        # Skip if already has video evidence (idempotent)
        existing_evidence = db.evidence_items.find_one({
            "appointment_id": apt_id,
            "source": "video_conference",
        })
        if existing_evidence:
            skipped_count += 1
            continue

        # Skip if already attempted and failed recently (avoid spam)
        recent_attempt = db.auto_fetch_logs.find_one({
            "appointment_id": apt_id,
            "attempted_at": {"$gte": (now - timedelta(minutes=10)).isoformat()},
        })
        if recent_attempt:
            skipped_count += 1
            continue

        # Attempt fetch
        try:
            logger.info(f"[AUTO-FETCH] Attempting {provider} attendance for apt {apt_id[:8]}")

            from services.meeting_provider_service import fetch_attendance_for_appointment
            result = fetch_attendance_for_appointment(apt_id)

            # Log the attempt
            log_entry = {
                "appointment_id": apt_id,
                "provider": provider,
                "attempted_at": now.isoformat(),
                "success": False,
                "error": None,
                "ingestion_result": None,
            }

            if result.get("error"):
                log_entry["error"] = result["error"]
                logger.warning(f"[AUTO-FETCH] Failed for apt {apt_id[:8]}: {result['error']}")
                error_count += 1
            elif result.get("raw_payload"):
                # Auto-ingest the fetched data
                from services.video_evidence_service import ingest_video_attendance
                ingest_result = ingest_video_attendance(
                    appointment_id=apt_id,
                    provider_name=result["provider"],
                    raw_payload=result["raw_payload"],
                    ingested_by="auto_fetch_scheduler",
                    external_meeting_id=apt.get("external_meeting_id"),
                    source_trust="api_verified",
                )
                log_entry["success"] = not ingest_result.get("error")
                log_entry["ingestion_result"] = {
                    "records_created": ingest_result.get("records_created", 0),
                    "matched_count": len(ingest_result.get("matched", [])),
                    "unmatched_count": len(ingest_result.get("unmatched", [])),
                }
                if ingest_result.get("error"):
                    log_entry["error"] = ingest_result["error"]
                    error_count += 1
                else:
                    fetched_count += 1
                    logger.info(
                        f"[AUTO-FETCH] Success for apt {apt_id[:8]}: "
                        f"{ingest_result.get('records_created', 0)} evidence created"
                    )

            db.auto_fetch_logs.insert_one(log_entry)

        except Exception as e:
            logger.error(f"[AUTO-FETCH] Exception for apt {apt_id[:8]}: {e}")
            error_count += 1
            db.auto_fetch_logs.insert_one({
                "appointment_id": apt_id,
                "provider": provider,
                "attempted_at": now.isoformat(),
                "success": False,
                "error": str(e),
            })

    if fetched_count or error_count:
        logger.info(
            f"[AUTO-FETCH] Job complete: {fetched_count} fetched, "
            f"{skipped_count} skipped, {error_count} errors"
        )
