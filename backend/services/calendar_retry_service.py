"""
Calendar Retry Service — Auto-update Calendar V2

Periodically retries failed/out_of_sync calendar sync operations with
exponential backoff: 2min → 5min → 15min → 60min (max 4 attempts).

After max retries, marks the sync as permanently_failed and stops retrying.
"""
import logging
from datetime import datetime, timedelta, timezone
from database import db
from utils.date_utils import now_utc

logger = logging.getLogger(__name__)

# Backoff schedule: delay in minutes for each retry attempt
RETRY_BACKOFF_MINUTES = [2, 5, 15, 60]
MAX_RETRIES = len(RETRY_BACKOFF_MINUTES)


def get_next_retry_delay(retry_count: int) -> timedelta:
    """Get the delay before the next retry based on current retry count."""
    if retry_count >= MAX_RETRIES:
        return timedelta(0)
    return timedelta(minutes=RETRY_BACKOFF_MINUTES[retry_count])


def schedule_retry(log_id: str, retry_count: int, error_reason: str):
    """Schedule the next retry for a sync log entry."""
    if retry_count >= MAX_RETRIES:
        db.calendar_sync_logs.update_one(
            {"log_id": log_id},
            {"$set": {
                "sync_status": "permanently_failed",
                "sync_error_reason": f"Max retries ({MAX_RETRIES}) atteint. Dernière erreur : {error_reason[:150]}",
                "retry_count": retry_count,
                "next_retry_at": None,
                "max_retries_reached": True,
                "updated_at": now_utc().isoformat(),
            }}
        )
        logger.warning(f"[CALENDAR-RETRY] log_id={log_id} permanently failed after {MAX_RETRIES} retries")
        return

    next_retry = now_utc() + get_next_retry_delay(retry_count)
    status = "retry_pending"

    db.calendar_sync_logs.update_one(
        {"log_id": log_id},
        {"$set": {
            "sync_status": status,
            "sync_error_reason": error_reason[:200],
            "retry_count": retry_count,
            "next_retry_at": next_retry.isoformat(),
            "max_retries_reached": False,
            "updated_at": now_utc().isoformat(),
        }}
    )
    delay_min = RETRY_BACKOFF_MINUTES[retry_count]
    logger.info(f"[CALENDAR-RETRY] log_id={log_id} retry #{retry_count + 1} scheduled in {delay_min}min")


def run_calendar_retry_job():
    """
    Main retry job: finds all retry_pending sync logs whose next_retry_at has passed,
    and attempts to re-sync or re-update them.
    """
    now = now_utc()
    pending = list(db.calendar_sync_logs.find({
        "sync_status": "retry_pending",
        "next_retry_at": {"$lte": now.isoformat()},
    }))

    if not pending:
        return

    logger.info(f"[CALENDAR-RETRY] Processing {len(pending)} pending retries")

    for sync_log in pending:
        log_id = sync_log.get("log_id")
        appointment_id = sync_log.get("appointment_id")
        provider = sync_log.get("provider")
        connection_id = sync_log.get("connection_id")
        external_event_id = sync_log.get("external_event_id")
        retry_count = sync_log.get("retry_count", 0)
        sync_source = sync_log.get("sync_source", "auto")

        try:
            # Load appointment
            appointment = db.appointments.find_one(
                {"appointment_id": appointment_id},
                {"_id": 0}
            )
            if not appointment:
                logger.warning(f"[CALENDAR-RETRY] Appointment {appointment_id} not found, skipping")
                db.calendar_sync_logs.update_one(
                    {"log_id": log_id},
                    {"$set": {
                        "sync_status": "permanently_failed",
                        "sync_error_reason": "Rendez-vous introuvable",
                        "next_retry_at": None,
                        "updated_at": now.isoformat(),
                    }}
                )
                continue

            # Skip if appointment cancelled
            if appointment.get("status") in ("cancelled", "deleted"):
                db.calendar_sync_logs.update_one(
                    {"log_id": log_id},
                    {"$set": {
                        "sync_status": "cancelled",
                        "sync_error_reason": "Rendez-vous annulé",
                        "next_retry_at": None,
                        "updated_at": now.isoformat(),
                    }}
                )
                continue

            # Load connection
            connection = db.calendar_connections.find_one(
                {"connection_id": connection_id, "status": "connected"},
                {"_id": 0}
            )
            if not connection:
                schedule_retry(log_id, retry_count + 1, "Connexion calendrier déconnectée")
                continue

            # Build event data and attempt sync
            from routers.calendar_routes import _get_adapter, _build_event_data, _make_token_refresh_callback

            adapter = _get_adapter(provider)
            on_refresh = _make_token_refresh_callback(connection_id)
            event_data = _build_event_data(appointment)

            if external_event_id:
                # This was a synced event that went out_of_sync → update
                result = adapter.update_event(
                    connection['access_token'], connection.get('refresh_token'),
                    external_event_id, event_data,
                    connection_update_callback=on_refresh
                )
            else:
                # This was a failed initial sync → create
                result = adapter.create_event(
                    connection['access_token'], connection.get('refresh_token'),
                    event_data, connection_update_callback=on_refresh
                )

            if result:
                update_fields = {
                    "sync_status": "synced",
                    "sync_error_reason": None,
                    "next_retry_at": None,
                    "updated_at": now.isoformat(),
                }
                if not external_event_id and result.get("event_id"):
                    update_fields["external_event_id"] = result["event_id"]
                    update_fields["html_link"] = result.get("html_link")

                db.calendar_sync_logs.update_one(
                    {"log_id": log_id},
                    {"$set": update_fields}
                )
                logger.info(f"[CALENDAR-RETRY] SUCCESS: {appointment_id} on {provider} (attempt #{retry_count + 1})")
            else:
                schedule_retry(log_id, retry_count + 1, f"Échec API {provider}")

        except Exception as e:
            error_msg = str(e)[:200]
            logger.error(f"[CALENDAR-RETRY] ERROR for {appointment_id} on {provider}: {error_msg}")
            schedule_retry(log_id, retry_count + 1, error_msg)
