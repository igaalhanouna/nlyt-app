import os
from typing import Optional, Dict
import requests
import urllib.parse

CLIENT_ID = os.environ.get('MICROSOFT_CLIENT_ID')
CLIENT_SECRET = os.environ.get('MICROSOFT_CLIENT_SECRET')

AUTHORITY = 'https://login.microsoftonline.com/common/oauth2/v2.0'
GRAPH_API = 'https://graph.microsoft.com/v1.0'

# Level 1: Universal scopes (personal + pro accounts) — Calendar sync
BASE_SCOPES = ['Calendars.ReadWrite', 'User.Read', 'offline_access']

# Level 2: Teams advanced scopes (pro accounts only) — OnlineMeetings + Attendance
TEAMS_SCOPES = ['Calendars.ReadWrite', 'User.Read', 'offline_access',
                'OnlineMeetings.ReadWrite', 'OnlineMeetingArtifact.Read.All']

# Default: base scopes for initial connection
SCOPES = BASE_SCOPES

# IANA → Windows timezone mapping (Microsoft Graph requires Windows IDs for personal accounts)
IANA_TO_WINDOWS_TZ = {
    'Europe/Paris': 'Romance Standard Time',
    'Europe/Brussels': 'Romance Standard Time',
    'Europe/Madrid': 'Romance Standard Time',
    'Europe/Amsterdam': 'W. Europe Standard Time',
    'Europe/Berlin': 'W. Europe Standard Time',
    'Europe/Rome': 'W. Europe Standard Time',
    'Europe/Zurich': 'W. Europe Standard Time',
    'Europe/Vienna': 'W. Europe Standard Time',
    'Europe/Stockholm': 'W. Europe Standard Time',
    'Europe/Oslo': 'W. Europe Standard Time',
    'Europe/Copenhagen': 'Romance Standard Time',
    'Europe/London': 'GMT Standard Time',
    'Europe/Dublin': 'GMT Standard Time',
    'Europe/Lisbon': 'GMT Standard Time',
    'Europe/Athens': 'GTB Standard Time',
    'Europe/Bucharest': 'GTB Standard Time',
    'Europe/Helsinki': 'FLE Standard Time',
    'Europe/Warsaw': 'Central European Standard Time',
    'Europe/Prague': 'Central European Standard Time',
    'Europe/Budapest': 'Central European Standard Time',
    'Europe/Moscow': 'Russian Standard Time',
    'Europe/Istanbul': 'Turkey Standard Time',
    'America/New_York': 'Eastern Standard Time',
    'America/Chicago': 'Central Standard Time',
    'America/Denver': 'Mountain Standard Time',
    'America/Los_Angeles': 'Pacific Standard Time',
    'America/Toronto': 'Eastern Standard Time',
    'America/Vancouver': 'Pacific Standard Time',
    'America/Montreal': 'Eastern Standard Time',
    'America/Sao_Paulo': 'E. South America Standard Time',
    'America/Argentina/Buenos_Aires': 'Argentina Standard Time',
    'America/Mexico_City': 'Central Standard Time (Mexico)',
    'Asia/Tokyo': 'Tokyo Standard Time',
    'Asia/Shanghai': 'China Standard Time',
    'Asia/Hong_Kong': 'China Standard Time',
    'Asia/Singapore': 'Singapore Standard Time',
    'Asia/Kolkata': 'India Standard Time',
    'Asia/Dubai': 'Arabian Standard Time',
    'Asia/Seoul': 'Korea Standard Time',
    'Asia/Bangkok': 'SE Asia Standard Time',
    'Asia/Taipei': 'Taipei Standard Time',
    'Australia/Sydney': 'AUS Eastern Standard Time',
    'Australia/Melbourne': 'AUS Eastern Standard Time',
    'Australia/Perth': 'W. Australia Standard Time',
    'Pacific/Auckland': 'New Zealand Standard Time',
    'Africa/Johannesburg': 'South Africa Standard Time',
    'Africa/Cairo': 'Egypt Standard Time',
    'Africa/Casablanca': 'Morocco Standard Time',
    'UTC': 'UTC',
}


def to_windows_timezone(iana_tz: str) -> str:
    """Convert IANA timezone to Windows timezone ID for Microsoft Graph API."""
    if not iana_tz:
        return 'UTC'
    return IANA_TO_WINDOWS_TZ.get(iana_tz, iana_tz)


class OutlookCalendarAdapter:

    @staticmethod
    def get_authorization_url(redirect_uri: str, state: str = None, scopes: list = None) -> tuple:
        """Build the Microsoft OAuth authorization URL.
        scopes: override the default BASE_SCOPES (used for Teams upgrade flow).
        """
        scope_list = scopes or SCOPES
        params = {
            'client_id': CLIENT_ID,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': ' '.join(scope_list),
            'response_mode': 'query',
            'prompt': 'consent',
        }
        if state:
            params['state'] = state
        auth_url = f'{AUTHORITY}/authorize?' + urllib.parse.urlencode(params)
        return auth_url, state

    @staticmethod
    def exchange_code_for_tokens(code: str, redirect_uri: str) -> Optional[Dict]:
        try:
            resp = requests.post(f'{AUTHORITY}/token', data={
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'code': code,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code',
                'scope': ' '.join(SCOPES),
            }).json()

            if 'error' in resp:
                print(f'[OUTLOOK] Token exchange error: {resp}')
                return None

            # Get user profile
            headers = {'Authorization': f'Bearer {resp["access_token"]}'}
            profile = requests.get(f'{GRAPH_API}/me', headers=headers).json()

            return {
                'access_token': resp['access_token'],
                'refresh_token': resp.get('refresh_token'),
                'expires_in': resp.get('expires_in'),
                'user_email': profile.get('mail') or profile.get('userPrincipalName', ''),
                'user_name': profile.get('displayName', ''),
                'granted_scopes': resp.get('scope', '').split(' '),
            }
        except Exception as e:
            print(f'[OUTLOOK] Error exchanging code: {e}')
            return None

    @staticmethod
    def refresh_access_token(refresh_token: str) -> Optional[str]:
        try:
            resp = requests.post(f'{AUTHORITY}/token', data={
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token',
                'scope': ' '.join(SCOPES),
            }).json()
            if 'error' in resp:
                print(f'[OUTLOOK] Refresh error: {resp}')
                return None
            return resp.get('access_token')
        except Exception as e:
            print(f'[OUTLOOK] Error refreshing token: {e}')
            return None

    @staticmethod
    def _get_headers(access_token: str, refresh_token: str, connection_update_callback=None) -> Optional[dict]:
        headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
        test = requests.get(f'{GRAPH_API}/me/calendars?$top=1', headers=headers)
        if test.status_code == 401 and refresh_token:
            new_token = OutlookCalendarAdapter.refresh_access_token(refresh_token)
            if new_token:
                if connection_update_callback:
                    connection_update_callback(new_token)
                headers['Authorization'] = f'Bearer {new_token}'
            else:
                if connection_update_callback:
                    connection_update_callback(None)
                return None
        elif test.status_code == 401:
            return None
        return headers

    @staticmethod
    def get_calendar_timezone(access_token: str, refresh_token: str, connection_update_callback=None) -> str:
        """Get the user's Outlook calendar timezone.
        Tries mailboxSettings first (works for pro accounts), falls back gracefully for personal accounts.
        """
        try:
            headers = OutlookCalendarAdapter._get_headers(access_token, refresh_token, connection_update_callback)
            if not headers:
                return 'UTC'
            resp = requests.get(f'{GRAPH_API}/me/mailboxSettings/timeZone', headers=headers)
            if resp.status_code == 200:
                return resp.json().get('value', 'UTC')
            # Personal accounts may not support mailboxSettings — graceful fallback
            return 'UTC'
        except Exception:
            return 'UTC'

    @staticmethod
    def create_event(access_token: str, refresh_token: str, event_data: dict, connection_update_callback=None) -> Optional[Dict]:
        try:
            headers = OutlookCalendarAdapter._get_headers(access_token, refresh_token, connection_update_callback)
            if not headers:
                return None

            calendar_tz = to_windows_timezone(event_data.get('timeZone', 'UTC'))

            event = {
                'subject': event_data['title'],
                'body': {
                    'contentType': 'text',
                    'content': event_data.get('description', '')
                },
                'start': {
                    'dateTime': event_data['start_datetime'],
                    'timeZone': calendar_tz
                },
                'end': {
                    'dateTime': event_data['end_datetime'],
                    'timeZone': calendar_tz
                },
            }
            if event_data.get('location'):
                event['location'] = {'displayName': event_data['location']}

            resp = requests.post(f'{GRAPH_API}/me/events', headers=headers, json=event)
            if resp.status_code in (200, 201):
                result = resp.json()
                return {
                    'event_id': result['id'],
                    'html_link': result.get('webLink')
                }
            else:
                print(f'[OUTLOOK] Create event error {resp.status_code}: {resp.text[:300]}')
                return None
        except Exception as e:
            print(f'[OUTLOOK] Error creating event: {e}')
            return None

    @staticmethod
    def update_event(access_token: str, refresh_token: str, event_id: str, event_data: dict, connection_update_callback=None) -> Optional[Dict]:
        try:
            headers = OutlookCalendarAdapter._get_headers(access_token, refresh_token, connection_update_callback)
            if not headers:
                return None

            calendar_tz = to_windows_timezone(event_data.get('timeZone', 'UTC'))
            event = {
                'subject': event_data['title'],
                'body': {'contentType': 'text', 'content': event_data.get('description', '')},
                'start': {'dateTime': event_data['start_datetime'], 'timeZone': calendar_tz},
                'end': {'dateTime': event_data['end_datetime'], 'timeZone': calendar_tz},
            }
            if event_data.get('location'):
                event['location'] = {'displayName': event_data['location']}

            resp = requests.patch(f'{GRAPH_API}/me/events/{event_id}', headers=headers, json=event)
            if resp.status_code == 200:
                result = resp.json()
                return {'event_id': result['id'], 'html_link': result.get('webLink')}
            return None
        except Exception as e:
            print(f'[OUTLOOK] Error updating event: {e}')
            return None

    @staticmethod
    def list_events(access_token: str, refresh_token: str, time_min: str, time_max: str, connection_update_callback=None) -> Optional[list]:
        """List events from the user's Outlook calendar within a time window.
        Returns a list of dicts with keys: event_id, title, start, end, or None on failure.
        time_min / time_max must be ISO 8601 strings.
        """
        try:
            headers = OutlookCalendarAdapter._get_headers(access_token, refresh_token, connection_update_callback)
            if not headers:
                return None

            params = {
                '$filter': f"start/dateTime ge '{time_min}' and end/dateTime le '{time_max}'",
                '$orderby': 'start/dateTime',
                '$top': 50,
                '$select': 'id,subject,start,end,isCancelled',
            }
            resp = requests.get(
                f'{GRAPH_API}/me/events',
                headers=headers,
                params=params,
            )
            if resp.status_code != 200:
                print(f"[OUTLOOK] list_events error {resp.status_code}: {resp.text[:300]}")
                return None

            events = []
            for item in resp.json().get('value', []):
                if item.get('isCancelled'):
                    continue
                start_dt = item.get('start', {}).get('dateTime')
                end_dt = item.get('end', {}).get('dateTime')
                if not start_dt or not end_dt:
                    continue
                # Graph API returns naive datetimes in UTC by default for calendarView
                # Ensure timezone suffix for consistency
                if not start_dt.endswith('Z') and '+' not in start_dt:
                    start_dt += 'Z'
                if not end_dt.endswith('Z') and '+' not in end_dt:
                    end_dt += 'Z'
                events.append({
                    'event_id': item['id'],
                    'title': item.get('subject', '(Sans titre)'),
                    'start': start_dt,
                    'end': end_dt,
                })
            return events
        except Exception as e:
            print(f"[OUTLOOK] Error listing events: {e}")
            return None

    @staticmethod
    def delete_event(access_token: str, refresh_token: str, event_id: str, connection_update_callback=None) -> bool:
        try:
            headers = OutlookCalendarAdapter._get_headers(access_token, refresh_token, connection_update_callback)
            if not headers:
                return False
            resp = requests.delete(f'{GRAPH_API}/me/events/{event_id}', headers=headers)
            return resp.status_code in (200, 204)
        except Exception as e:
            print(f'[OUTLOOK] Error deleting event: {e}')
            return False
