"""
Video Webhooks — Real-time Zoom & Teams event processing

Zoom:
  - POST /zoom  — receives Zoom webhook events
  - Verifies HMAC-SHA256 signature using ZOOM_WEBHOOK_SECRET_TOKEN
  - Handles endpoint.url_validation (CRC challenge for initial setup)
  - Handles meeting.ended → triggers immediate attendance fetch

Teams (Microsoft Graph Change Notifications):
  - POST /teams — receives Graph change notifications
  - Handles validationToken on subscription creation
  - Handles callRecords notifications → triggers attendance fetch
  - GET /teams/subscribe — creates/renews Graph subscription (admin)
"""
import os
import hmac
import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
import requests

from database import db

logger = logging.getLogger(__name__)
router = APIRouter()

ZOOM_SECRET_TOKEN = os.environ.get("ZOOM_WEBHOOK_SECRET_TOKEN", "")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "")

MS_CLIENT_ID = os.environ.get("MICROSOFT_CLIENT_ID", "")
MS_CLIENT_SECRET = os.environ.get("MICROSOFT_CLIENT_SECRET", "")
MS_TENANT_ID = os.environ.get("MICROSOFT_TENANT_ID", "common")


# ── Zoom Webhook ─────────────────────────────────────────────

def _verify_zoom_signature(request_body: bytes, timestamp: str, signature: str) -> bool:
    """Verify Zoom webhook signature (HMAC-SHA256)."""
    if not ZOOM_SECRET_TOKEN:
        logger.warning("[ZOOM-WH] No secret token configured — skipping verification")
        return True
    message = f"v0:{timestamp}:{request_body.decode('utf-8')}"
    expected = "v0=" + hmac.new(
        ZOOM_SECRET_TOKEN.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/zoom")
async def zoom_webhook(request: Request):
    """Receive and process Zoom webhook events."""
    body = await request.body()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = payload.get("event", "")

    # ── CRC Challenge (endpoint.url_validation) ──
    if event_type == "endpoint.url_validation":
        plain_token = payload.get("payload", {}).get("plainToken", "")
        if not plain_token:
            raise HTTPException(status_code=400, detail="Missing plainToken")
        encrypted = hmac.new(
            ZOOM_SECRET_TOKEN.encode("utf-8"),
            plain_token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        logger.info("[ZOOM-WH] CRC challenge validated")
        return {"plainToken": plain_token, "encryptedToken": encrypted}

    # ── Signature verification ──
    timestamp = request.headers.get("x-zm-request-timestamp", "")
    signature = request.headers.get("x-zm-signature", "")
    if timestamp and signature:
        if not _verify_zoom_signature(body, timestamp, signature):
            logger.warning("[ZOOM-WH] Invalid signature — rejecting")
            raise HTTPException(status_code=401, detail="Invalid signature")

    # ── Dedup ──
    event_id = payload.get("event_ts", "") or payload.get("payload", {}).get("object", {}).get("uuid", "")
    if event_id:
        existing = db.video_webhook_events.find_one({"event_id": f"zoom_{event_id}"})
        if existing:
            logger.info(f"[ZOOM-WH] Duplicate event {event_type} — skipping")
            return {"status": "duplicate"}

    # Log event
    db.video_webhook_events.insert_one({
        "event_id": f"zoom_{event_id}" if event_id else f"zoom_{datetime.now(timezone.utc).isoformat()}",
        "provider": "zoom",
        "event_type": event_type,
        "payload": payload,
        "processed": False,
        "received_at": datetime.now(timezone.utc).isoformat(),
    })

    logger.info(f"[ZOOM-WH] Received event: {event_type}")

    # ── meeting.ended → trigger attendance fetch ──
    if event_type == "meeting.ended":
        meeting_obj = payload.get("payload", {}).get("object", {})
        zoom_meeting_id = str(meeting_obj.get("id", ""))

        if not zoom_meeting_id:
            logger.warning("[ZOOM-WH] meeting.ended without meeting ID")
            return {"status": "ignored", "reason": "no_meeting_id"}

        # Find matching appointment
        appointment = db.appointments.find_one(
            {"external_meeting_id": zoom_meeting_id, "meeting_provider": "zoom"},
            {"_id": 0, "appointment_id": 1},
        )
        if not appointment:
            # Try with string matching variations
            appointment = db.appointments.find_one(
                {"external_meeting_id": {"$regex": zoom_meeting_id}},
                {"_id": 0, "appointment_id": 1},
            )

        if not appointment:
            logger.info(f"[ZOOM-WH] No matching appointment for Zoom meeting {zoom_meeting_id}")
            return {"status": "ignored", "reason": "no_matching_appointment"}

        apt_id = appointment["appointment_id"]
        logger.info(f"[ZOOM-WH] Meeting ended → triggering attendance fetch for apt {apt_id[:8]}")

        # Delay fetch slightly (Zoom needs ~30s to process attendance data)
        _schedule_attendance_fetch(apt_id, "zoom", delay_seconds=60)

        db.video_webhook_events.update_one(
            {"event_id": f"zoom_{event_id}"},
            {"$set": {"processed": True, "appointment_id": apt_id}},
        )
        return {"status": "success", "appointment_id": apt_id}

    # ── meeting.participant_joined / meeting.participant_left (log only) ──
    if event_type in ("meeting.participant_joined", "meeting.participant_left"):
        meeting_obj = payload.get("payload", {}).get("object", {})
        participant = meeting_obj.get("participant", {})
        logger.info(
            f"[ZOOM-WH] {event_type}: {participant.get('user_name', '?')} "
            f"({participant.get('email', '?')}) meeting={meeting_obj.get('id')}"
        )
        return {"status": "logged"}

    return {"status": "ignored", "event_type": event_type}


# ── Teams / Microsoft Graph Change Notifications ─────────────

@router.post("/teams")
async def teams_webhook(request: Request):
    """Receive Microsoft Graph change notifications for call records."""
    # ── Subscription validation ──
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        logger.info("[TEAMS-WH] Subscription validation — returning token")
        return PlainTextResponse(content=validation_token, status_code=200)

    body = await request.body()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    notifications = payload.get("value", [])
    logger.info(f"[TEAMS-WH] Received {len(notifications)} notification(s)")

    for notif in notifications:
        resource = notif.get("resource", "")
        change_type = notif.get("changeType", "")
        subscription_id = notif.get("subscriptionId", "")

        # ── Lifecycle notifications (subscription renewal) ──
        if notif.get("lifecycleEvent"):
            lifecycle = notif["lifecycleEvent"]
            logger.info(f"[TEAMS-WH] Lifecycle event: {lifecycle} for subscription {subscription_id}")
            if lifecycle in ("reauthorizationRequired", "subscriptionRemoved"):
                _renew_graph_subscription(subscription_id)
            continue

        # Dedup
        event_id = f"teams_{notif.get('id', resource)}"
        existing = db.video_webhook_events.find_one({"event_id": event_id})
        if existing:
            logger.info(f"[TEAMS-WH] Duplicate — skipping")
            continue

        db.video_webhook_events.insert_one({
            "event_id": event_id,
            "provider": "teams",
            "event_type": f"callRecords.{change_type}",
            "resource": resource,
            "payload": notif,
            "processed": False,
            "received_at": datetime.now(timezone.utc).isoformat(),
        })

        # ── callRecords → fetch call record details → match appointment ──
        if "callRecords" in resource and change_type == "created":
            call_record_id = resource.split("/")[-1] if "/" in resource else resource
            logger.info(f"[TEAMS-WH] Call record created: {call_record_id}")
            _process_teams_call_record(call_record_id, event_id)

    return {"status": "success", "processed": len(notifications)}


def _process_teams_call_record(call_record_id: str, event_id: str):
    """Fetch call record details from Graph API and match to an appointment."""
    token = _get_ms_app_token()
    if not token:
        logger.warning("[TEAMS-WH] Cannot fetch call record — no app token")
        return

    try:
        resp = requests.get(
            f"https://graph.microsoft.com/v1.0/communications/callRecords/{call_record_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if resp.status_code == 403:
            logger.warning("[TEAMS-WH] 403 Forbidden — CallRecords.Read.All permission may be missing")
            return
        resp.raise_for_status()
        record = resp.json()
    except Exception as e:
        logger.warning(f"[TEAMS-WH] Failed to fetch call record {call_record_id}: {e}")
        return

    # Extract organizer info to find matching appointment
    organizer = record.get("organizer", {}).get("user", {})
    organizer_email = organizer.get("displayName", "")
    join_url = record.get("joinWebUrl", "")
    start_time = record.get("startDateTime", "")

    logger.info(f"[TEAMS-WH] Call record: organizer={organizer_email} join_url={join_url[:50] if join_url else 'N/A'}")

    # Try to match by join URL
    appointment = None
    if join_url:
        appointment = db.appointments.find_one(
            {"meeting_url": {"$regex": join_url.split("?")[0].split("/0?")[0][:80]}},
            {"_id": 0, "appointment_id": 1},
        )

    # Fallback: match by external_meeting_id
    if not appointment:
        appointment = db.appointments.find_one(
            {"external_meeting_id": call_record_id},
            {"_id": 0, "appointment_id": 1},
        )

    if not appointment:
        logger.info(f"[TEAMS-WH] No matching appointment for call record {call_record_id}")
        return

    apt_id = appointment["appointment_id"]
    logger.info(f"[TEAMS-WH] Matched call record → apt {apt_id[:8]} — scheduling attendance fetch")

    _schedule_attendance_fetch(apt_id, "teams", delay_seconds=30)

    db.video_webhook_events.update_one(
        {"event_id": event_id},
        {"$set": {"processed": True, "appointment_id": apt_id}},
    )


# ── Graph Subscription Management ────────────────────────────

def _get_ms_app_token() -> str:
    """Get an application-level token for Microsoft Graph."""
    if not MS_CLIENT_ID or not MS_CLIENT_SECRET:
        return ""
    try:
        resp = requests.post(
            f"https://login.microsoftonline.com/{MS_TENANT_ID}/oauth2/v2.0/token",
            data={
                "grant_type": "client_credentials",
                "client_id": MS_CLIENT_ID,
                "client_secret": MS_CLIENT_SECRET,
                "scope": "https://graph.microsoft.com/.default",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("access_token", "")
    except Exception as e:
        logger.error(f"[TEAMS-WH] Failed to get app token: {e}")
        return ""


def create_graph_subscription() -> dict:
    """Create a Microsoft Graph subscription for call records."""
    token = _get_ms_app_token()
    if not token:
        return {"error": "Cannot acquire application token"}

    webhook_url = f"{FRONTEND_URL}/api/webhooks/teams"
    expiry = (datetime.now(timezone.utc) + timedelta(hours=71)).isoformat() + "Z"

    try:
        resp = requests.post(
            "https://graph.microsoft.com/v1.0/subscriptions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "changeType": "created",
                "notificationUrl": webhook_url,
                "resource": "communications/callRecords",
                "expirationDateTime": expiry,
                "clientState": "nlyt_teams_webhook",
            },
            timeout=15,
        )
        if resp.status_code in (201, 200):
            sub = resp.json()
            sub_id = sub.get("id", "")
            logger.info(f"[TEAMS-WH] Subscription created: {sub_id} expires={sub.get('expirationDateTime')}")
            db.graph_subscriptions.update_one(
                {"subscription_id": sub_id},
                {"$set": {
                    "subscription_id": sub_id,
                    "resource": "communications/callRecords",
                    "expiration": sub.get("expirationDateTime"),
                    "webhook_url": webhook_url,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }},
                upsert=True,
            )
            return {"success": True, "subscription_id": sub_id, "expiration": sub.get("expirationDateTime")}
        else:
            error = resp.text
            logger.warning(f"[TEAMS-WH] Subscription creation failed ({resp.status_code}): {error}")
            return {"error": f"Graph API returned {resp.status_code}", "detail": error}
    except Exception as e:
        logger.error(f"[TEAMS-WH] Subscription creation error: {e}")
        return {"error": str(e)}


def _renew_graph_subscription(subscription_id: str):
    """Renew an existing Graph subscription."""
    token = _get_ms_app_token()
    if not token:
        return
    expiry = (datetime.now(timezone.utc) + timedelta(hours=71)).isoformat() + "Z"
    try:
        resp = requests.patch(
            f"https://graph.microsoft.com/v1.0/subscriptions/{subscription_id}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"expirationDateTime": expiry},
            timeout=15,
        )
        if resp.status_code == 200:
            logger.info(f"[TEAMS-WH] Subscription {subscription_id} renewed until {expiry}")
            db.graph_subscriptions.update_one(
                {"subscription_id": subscription_id},
                {"$set": {"expiration": expiry, "renewed_at": datetime.now(timezone.utc).isoformat()}},
            )
        else:
            logger.warning(f"[TEAMS-WH] Subscription renewal failed ({resp.status_code}): {resp.text}")
    except Exception as e:
        logger.error(f"[TEAMS-WH] Subscription renewal error: {e}")


def renew_all_graph_subscriptions():
    """Renew all active Graph subscriptions. Called by scheduler."""
    subs = list(db.graph_subscriptions.find({}, {"_id": 0}))
    for sub in subs:
        sub_id = sub.get("subscription_id")
        if sub_id:
            _renew_graph_subscription(sub_id)
    return len(subs)


# ── Shared: Delayed Attendance Fetch ─────────────────────────

def _schedule_attendance_fetch(appointment_id: str, provider: str, delay_seconds: int = 60):
    """
    Schedule an attendance fetch after a short delay.
    Uses a background thread to avoid blocking the webhook response.
    """
    import threading

    def _do_fetch():
        import time
        time.sleep(delay_seconds)
        try:
            # Check if already fetched (idempotent)
            existing = db.evidence_items.find_one({
                "appointment_id": appointment_id,
                "source": "video_conference",
            })
            if existing:
                logger.info(f"[WH-FETCH] Attendance already exists for {appointment_id[:8]} — skipping")
                return

            from services.meeting_provider_service import fetch_attendance_for_appointment
            result = fetch_attendance_for_appointment(appointment_id)

            if result.get("error"):
                logger.warning(f"[WH-FETCH] Failed for {appointment_id[:8]}: {result['error']}")
                # Log for retry by scheduler
                db.auto_fetch_logs.insert_one({
                    "appointment_id": appointment_id,
                    "provider": provider,
                    "attempted_at": datetime.now(timezone.utc).isoformat(),
                    "success": False,
                    "error": result["error"],
                    "trigger": "webhook",
                })
                return

            if result.get("raw_payload"):
                from services.video_evidence_service import ingest_video_attendance
                ingest_result = ingest_video_attendance(
                    appointment_id=appointment_id,
                    provider_name=result["provider"],
                    raw_payload=result["raw_payload"],
                    ingested_by=f"webhook_{provider}",
                    external_meeting_id=db.appointments.find_one(
                        {"appointment_id": appointment_id},
                        {"_id": 0, "external_meeting_id": 1},
                    ).get("external_meeting_id", ""),
                    source_trust="api_verified",
                )
                logger.info(
                    f"[WH-FETCH] Success for {appointment_id[:8]}: "
                    f"{ingest_result.get('records_created', 0)} evidence records created"
                )
                db.auto_fetch_logs.insert_one({
                    "appointment_id": appointment_id,
                    "provider": provider,
                    "attempted_at": datetime.now(timezone.utc).isoformat(),
                    "success": True,
                    "trigger": "webhook",
                    "records_created": ingest_result.get("records_created", 0),
                })
        except Exception as e:
            logger.error(f"[WH-FETCH] Exception for {appointment_id[:8]}: {e}")

    thread = threading.Thread(target=_do_fetch, daemon=True)
    thread.start()
    logger.info(f"[WH-FETCH] Scheduled fetch for {appointment_id[:8]} in {delay_seconds}s (via {provider} webhook)")
