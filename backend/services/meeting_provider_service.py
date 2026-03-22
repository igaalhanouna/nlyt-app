"""
Meeting Provider Service — Central orchestrator for creating and managing video meetings.

Flow:
1. Organizer creates a video appointment in NLYT
2. NLYT calls the appropriate provider API to create the meeting
3. Stores external_meeting_id, join_url, host_url, provider_metadata
4. Meeting link is displayed in UI, sent in emails, synced to calendars
5. After meeting ends: NLYT fetches attendance data via provider API

Supported providers:
- Zoom: Server-to-Server OAuth (creates meetings, fetches attendance)
- Teams: Microsoft Graph API (creates meetings, fetches attendance)
- Google Meet: Google Calendar API with conferenceData (creates link, no attendance API)
"""
import os
import logging
import base64
import time
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional
from pymongo import MongoClient

logger = logging.getLogger(__name__)

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
mongo_client = MongoClient(MONGO_URL)
db = mongo_client[DB_NAME]

# ============================================================
#  ZOOM — Server-to-Server OAuth
# ============================================================
class ZoomMeetingClient:
    """Creates Zoom meetings and fetches attendance reports."""

    def __init__(self):
        self.account_id = os.environ.get('ZOOM_ACCOUNT_ID')
        self.client_id = os.environ.get('ZOOM_CLIENT_ID')
        self.client_secret = os.environ.get('ZOOM_CLIENT_SECRET')
        self.access_token = None
        self.token_expiry = None
        self.base_url = "https://api.zoom.us/v2"

    def is_configured(self) -> bool:
        return bool(self.account_id and self.client_id and self.client_secret)

    def _get_token(self) -> str:
        if self.access_token and self.token_expiry and datetime.utcnow() < self.token_expiry - timedelta(seconds=60):
            return self.access_token

        creds = f"{self.client_id}:{self.client_secret}"
        encoded = base64.b64encode(creds.encode()).decode()
        resp = requests.post(
            "https://zoom.us/oauth/token",
            headers={"Authorization": f"Basic {encoded}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "account_credentials", "account_id": self.account_id},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        self.access_token = data["access_token"]
        self.token_expiry = datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600))
        return self.access_token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_token()}", "Content-Type": "application/json"}

    def create_meeting(self, topic: str, start_time: str, duration_minutes: int, timezone_str: str = "UTC", user_id: str = "me") -> dict:
        """Create a scheduled Zoom meeting. Returns {meeting_id, join_url, host_url, password, metadata}."""
        payload = {
            "topic": topic,
            "type": 2,  # Scheduled
            "start_time": start_time,
            "duration": duration_minutes,
            "timezone": timezone_str,
            "settings": {
                "host_video": True,
                "participant_video": True,
                "join_before_host": False,
                "mute_upon_entry": False,
                "waiting_room": False,
                "meeting_authentication": False,
            },
        }
        resp = requests.post(f"{self.base_url}/users/{user_id}/meetings", json=payload, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return {
            "external_meeting_id": str(data["id"]),
            "join_url": data.get("join_url"),
            "host_url": data.get("start_url"),
            "password": data.get("password"),
            "metadata": {
                "uuid": data.get("uuid"),
                "host_id": data.get("host_id"),
                "topic": data.get("topic"),
                "created_at": data.get("created_at"),
            },
        }

    def fetch_attendance(self, meeting_id: str) -> Optional[dict]:
        """Fetch past meeting participants (attendance report)."""
        try:
            resp = requests.get(
                f"{self.base_url}/past_meetings/{meeting_id}/participants",
                headers=self._headers(),
                params={"page_size": 300},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "meeting_id": meeting_id,
                "participants": [
                    {
                        "id": p.get("id"),
                        "user_email": p.get("user_email") or p.get("email"),
                        "name": p.get("name"),
                        "join_time": p.get("join_time"),
                        "leave_time": p.get("leave_time"),
                        "duration": p.get("duration"),
                    }
                    for p in data.get("participants", [])
                ],
            }
        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 404:
                return None  # Meeting not ended yet or not found
            raise


# ============================================================
#  MICROSOFT TEAMS — Graph API (Application permissions)
# ============================================================
class TeamsMeetingClient:
    """Creates Teams meetings and fetches attendance reports via Microsoft Graph API."""

    def __init__(self):
        self.tenant_id = os.environ.get('MICROSOFT_TENANT_ID')
        self.client_id = os.environ.get('MICROSOFT_CLIENT_ID')
        self.client_secret = os.environ.get('MICROSOFT_CLIENT_SECRET')
        self.access_token = None
        self.token_expiry = None
        self.graph_url = "https://graph.microsoft.com/v1.0"

    def is_configured(self) -> bool:
        placeholder_values = {"detect-presence", "guarantee-first", "placeholder", "your-tenant-id", "your-client-id"}
        return bool(
            self.tenant_id and self.client_id and self.client_secret
            and self.tenant_id not in placeholder_values
            and self.client_id not in placeholder_values
        )

    def _get_token(self) -> str:
        if self.access_token and self.token_expiry and datetime.utcnow() < self.token_expiry - timedelta(seconds=60):
            return self.access_token

        resp = requests.post(
            f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        self.access_token = data["access_token"]
        self.token_expiry = datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600))
        return self.access_token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_token()}", "Content-Type": "application/json"}

    def create_meeting(self, subject: str, start_time: str, end_time: str, user_id: str) -> dict:
        """Create a Teams online meeting. Requires user_id = Azure AD Object ID of the organizer."""
        payload = {
            "subject": subject,
            "startDateTime": start_time,
            "endDateTime": end_time,
            "lobbyBypassSettings": {
                "scope": "everyone",
            },
            "allowedPresenters": "organizer",
            "isEntryExitAnnounced": False,
        }
        resp = requests.post(
            f"{self.graph_url}/users/{user_id}/onlineMeetings",
            json=payload,
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "external_meeting_id": data.get("id"),
            "join_url": data.get("joinWebUrl") or data.get("joinUrl"),
            "host_url": None,
            "password": None,
            "metadata": {
                "video_teleconference_id": data.get("videoTeleconferenceId"),
                "subject": data.get("subject"),
                "created_at": data.get("creationDateTime"),
                "lobby_bypass_scope": "everyone",
                "allowed_presenters": "organizer",
            },
        }

    def fetch_attendance(self, user_id: str, meeting_id: str) -> Optional[dict]:
        """Fetch attendance reports for a Teams meeting."""
        try:
            # Get attendance reports
            resp = requests.get(
                f"{self.graph_url}/users/{user_id}/onlineMeetings/{meeting_id}/attendanceReports",
                headers=self._headers(),
                timeout=15,
            )
            resp.raise_for_status()
            reports = resp.json().get("value", [])
            if not reports:
                return None

            # Get the most recent report
            report = reports[-1]
            report_id = report.get("id")

            # Get attendance records
            records_resp = requests.get(
                f"{self.graph_url}/users/{user_id}/onlineMeetings/{meeting_id}/attendanceReports/{report_id}/attendanceRecords",
                headers=self._headers(),
                timeout=15,
            )
            records_resp.raise_for_status()
            records = records_resp.json().get("value", [])

            return {
                "meeting_id": meeting_id,
                "attendanceRecords": [
                    {
                        "emailAddress": r.get("emailAddress"),
                        "identity": {"displayName": r.get("identity", {}).get("displayName")},
                        "totalAttendanceInSeconds": r.get("totalAttendanceInSeconds"),
                        "role": r.get("role"),
                        "attendanceIntervals": [
                            {
                                "joinDateTime": i.get("joinDateTime"),
                                "leaveDateTime": i.get("leaveDateTime"),
                                "durationInSeconds": i.get("durationInSeconds"),
                            }
                            for i in r.get("attendanceIntervals", [])
                        ],
                    }
                    for r in records
                ],
            }
        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 404:
                return None
            raise


# ============================================================
#  GOOGLE MEET — via Google Calendar API (conferenceData)
# ============================================================
class GoogleMeetClient:
    """Creates Google Meet links via Calendar API. No attendance API in standard Workspace."""

    def __init__(self):
        self.client_id = os.environ.get('GOOGLE_CLIENT_ID')
        self.client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def create_meeting(self, access_token: str, refresh_token: str, title: str, start_time: str, end_time: str, timezone_str: str = "UTC") -> dict:
        """Create a Google Calendar event with a Meet conference link."""
        from adapters.google_calendar_adapter import GoogleCalendarAdapter

        headers = GoogleCalendarAdapter._get_headers(access_token, refresh_token)
        if not headers:
            return {"error": "Google Calendar tokens expired or invalid"}

        import uuid as uuid_mod
        event_body = {
            "summary": title,
            "start": {"dateTime": start_time, "timeZone": timezone_str},
            "end": {"dateTime": end_time, "timeZone": timezone_str},
            "conferenceData": {
                "createRequest": {
                    "requestId": str(uuid_mod.uuid4()),
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                },
            },
        }
        resp = requests.post(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers=headers,
            params={"conferenceDataVersion": 1},
            json=event_body,
            timeout=15,
        )
        if resp.status_code not in (200, 201):
            logger.error(f"[MEET] Create event error {resp.status_code}: {resp.text[:300]}")
            return {"error": f"Google Calendar API error: {resp.status_code}"}

        data = resp.json()
        conf = data.get("conferenceData", {})
        entry_points = conf.get("entryPoints", [])
        join_url = None
        for ep in entry_points:
            if ep.get("entryPointType") == "video":
                join_url = ep.get("uri")
                break

        return {
            "external_meeting_id": conf.get("conferenceId") or data.get("id"),
            "join_url": join_url,
            "host_url": None,
            "password": None,
            "calendar_event_id": data.get("id"),
            "metadata": {
                "conference_solution": conf.get("conferenceSolution", {}).get("name"),
                "html_link": data.get("htmlLink"),
            },
        }

    def fetch_attendance(self, **kwargs) -> Optional[dict]:
        """Google Meet has no standard attendance API — returns None."""
        return None


# ============================================================
#  ORCHESTRATOR — create_meeting_for_appointment
# ============================================================
_zoom_client = ZoomMeetingClient()
_teams_client = TeamsMeetingClient()
_meet_client = GoogleMeetClient()


def get_provider_status() -> dict:
    """Returns which providers are configured and ready."""
    return {
        "zoom": {"configured": _zoom_client.is_configured(), "features": ["create_meeting", "fetch_attendance"]},
        "teams": {"configured": _teams_client.is_configured(), "features": ["create_meeting", "fetch_attendance"]},
        "meet": {"configured": _meet_client.is_configured(), "features": ["create_meeting"]},
    }


def create_meeting_for_appointment(
    appointment_id: str,
    provider: str,
    title: str,
    start_datetime: str,
    duration_minutes: int,
    timezone_str: str = "UTC",
    organizer_user_id: str = None,
) -> dict:
    """
    Create a meeting via the provider API and update the appointment document.

    Returns: {success, external_meeting_id, join_url, host_url, ...} or {error}
    """
    provider_lower = (provider or "").strip().lower()

    try:
        if provider_lower == "zoom":
            if not _zoom_client.is_configured():
                return {"error": "Zoom API non configurée. Ajoutez ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET dans les variables d'environnement.", "needs_config": True}
            result = _zoom_client.create_meeting(
                topic=title,
                start_time=start_datetime,
                duration_minutes=duration_minutes,
                timezone_str=timezone_str,
            )

        elif provider_lower in ("teams", "microsoft teams", "microsoft_teams"):
            if not _teams_client.is_configured():
                return {"error": "Teams API non configurée. Ajoutez MICROSOFT_TENANT_ID, MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET.", "needs_config": True}
            # Compute end time
            from utils.date_utils import parse_iso_datetime
            start_dt = parse_iso_datetime(start_datetime)
            end_dt = start_dt + timedelta(minutes=duration_minutes) if start_dt else None
            end_time = end_dt.isoformat() if end_dt else start_datetime

            # For Teams app permissions, we need the user's Azure AD object ID
            # Try to find it from user settings or use organizer_user_id
            azure_user_id = _resolve_teams_user_id(organizer_user_id)
            if not azure_user_id:
                return {"error": "Azure AD User ID introuvable. Configurez votre ID utilisateur Teams dans les paramètres.", "needs_config": True}

            result = _teams_client.create_meeting(
                subject=title,
                start_time=start_datetime,
                end_time=end_time,
                user_id=azure_user_id,
            )

        elif provider_lower in ("meet", "google meet", "google_meet"):
            if not _meet_client.is_configured():
                return {"error": "Google API non configurée.", "needs_config": True}
            # Google Meet requires user OAuth tokens (delegated)
            google_tokens = _resolve_google_tokens(organizer_user_id)
            if not google_tokens:
                return {"error": "Connexion Google Calendar requise pour créer un lien Meet. Connectez votre calendrier Google dans les paramètres.", "needs_config": True}

            from utils.date_utils import parse_iso_datetime
            start_dt = parse_iso_datetime(start_datetime)
            end_dt = start_dt + timedelta(minutes=duration_minutes) if start_dt else None
            end_time = end_dt.isoformat() if end_dt else start_datetime

            result = _meet_client.create_meeting(
                access_token=google_tokens["access_token"],
                refresh_token=google_tokens.get("refresh_token"),
                title=title,
                start_time=start_datetime,
                end_time=end_time,
                timezone_str=timezone_str,
            )

            # Enrich Meet metadata with the creator's Google email
            google_conn = db.calendar_connections.find_one(
                {"user_id": organizer_user_id, "provider": "google", "status": "connected"},
                {"_id": 0, "google_email": 1, "google_name": 1},
            )
            if google_conn and result.get("metadata"):
                result["metadata"]["creator_email"] = google_conn.get("google_email")
                result["metadata"]["creator_name"] = google_conn.get("google_name")
        else:
            return {"error": f"Provider '{provider}' non supporté. Utilisez 'zoom', 'teams' ou 'meet'."}

        if result.get("error"):
            return result

        # Update appointment document
        update = {
            "external_meeting_id": result.get("external_meeting_id"),
            "meeting_join_url": result.get("join_url"),
            "meeting_host_url": result.get("host_url"),
            "meeting_password": result.get("password"),
            "meeting_provider_metadata": result.get("metadata"),
            "meeting_created_via_api": True,
        }
        if result.get("calendar_event_id"):
            update["meet_calendar_event_id"] = result["calendar_event_id"]

        db.appointments.update_one(
            {"appointment_id": appointment_id},
            {"$set": update},
        )

        logger.info(f"[MEETING] Created {provider_lower} meeting for apt {appointment_id[:8]}: {result.get('join_url')}")

        return {
            "success": True,
            "provider": provider_lower,
            "external_meeting_id": result.get("external_meeting_id"),
            "join_url": result.get("join_url"),
            "host_url": result.get("host_url"),
            "password": result.get("password"),
            "metadata": result.get("metadata"),
        }

    except requests.exceptions.HTTPError as e:
        logger.error(f"[MEETING] API error creating {provider_lower} meeting: {e}")
        error_detail = ""
        if e.response is not None:
            try:
                error_detail = e.response.json().get("message", e.response.text[:200])
            except Exception:
                error_detail = e.response.text[:200]
        return {"error": f"Erreur API {provider}: {error_detail or str(e)}"}
    except Exception as e:
        logger.error(f"[MEETING] Unexpected error creating {provider_lower} meeting: {e}")
        return {"error": f"Erreur inattendue: {str(e)}"}


def fetch_attendance_for_appointment(appointment_id: str) -> dict:
    """Fetch attendance data from the provider API for a completed meeting."""
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        return {"error": "Rendez-vous introuvable"}

    provider = (appointment.get("meeting_provider") or "").lower()
    meeting_id = appointment.get("external_meeting_id")
    if not meeting_id:
        return {"error": "Pas d'identifiant de meeting externe"}

    try:
        if provider == "zoom":
            if not _zoom_client.is_configured():
                return {"error": "Zoom API non configurée"}
            data = _zoom_client.fetch_attendance(meeting_id)
            if data:
                return {"success": True, "provider": "zoom", "raw_payload": data}
            return {"error": "Rapport de présence Zoom non disponible (réunion pas encore terminée ?)"}

        elif provider in ("teams", "microsoft teams"):
            if not _teams_client.is_configured():
                return {"error": "Teams API non configurée"}
            azure_user_id = _resolve_teams_user_id(appointment.get("organizer_id"))
            if not azure_user_id:
                return {"error": "Azure AD User ID introuvable"}
            data = _teams_client.fetch_attendance(azure_user_id, meeting_id)
            if data:
                return {"success": True, "provider": "teams", "raw_payload": data}
            return {"error": "Rapport de présence Teams non disponible"}

        elif provider in ("meet", "google meet"):
            return {"error": "Google Meet n'a pas d'API de présence standard. Utilisez l'import manuel."}

        return {"error": f"Provider '{provider}' non supporté pour le fetch automatique"}

    except Exception as e:
        logger.error(f"[MEETING] Error fetching attendance for {appointment_id[:8]}: {e}")
        return {"error": str(e)}


def _resolve_teams_user_id(nlyt_user_id: str) -> Optional[str]:
    """Resolve NLYT user_id to Azure AD user ID for Teams app permissions."""
    if not nlyt_user_id:
        return None
    # Check user_settings for azure_user_id
    settings = db.user_settings.find_one({"user_id": nlyt_user_id}, {"_id": 0})
    if settings and settings.get("azure_user_id"):
        return settings["azure_user_id"]
    # Check calendar connections for Outlook (might have user email as ID)
    connection = db.calendar_connections.find_one(
        {"user_id": nlyt_user_id, "provider": "outlook", "status": "connected"},
        {"_id": 0},
    )
    if connection and connection.get("user_email"):
        return connection["user_email"]
    return None


def _resolve_google_tokens(nlyt_user_id: str) -> Optional[dict]:
    """Resolve NLYT user_id to Google Calendar OAuth tokens."""
    if not nlyt_user_id:
        return None
    connection = db.calendar_connections.find_one(
        {"user_id": nlyt_user_id, "provider": "google", "status": "connected"},
        {"_id": 0},
    )
    if connection and connection.get("access_token"):
        return {
            "access_token": connection["access_token"],
            "refresh_token": connection.get("refresh_token"),
        }
    return None
