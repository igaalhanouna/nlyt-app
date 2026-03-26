import os
from typing import Optional, Dict
import requests
import sys
sys.path.append('/app/backend')

CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid'
]


class GoogleCalendarAdapter:
    @staticmethod
    def get_authorization_url(redirect_uri: str, state: str = None) -> tuple:
        """Build Google OAuth2 authorization URL manually (no Flow dependency)."""
        import urllib.parse

        params = {
            "client_id": CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
        }
        if state:
            params["state"] = state

        auth_url = "https://accounts.google.com/o/oauth2/auth?" + urllib.parse.urlencode(params)
        return auth_url, state

    @staticmethod
    def exchange_code_for_tokens(code: str, redirect_uri: str) -> Optional[Dict]:
        try:
            token_resp = requests.post('https://oauth2.googleapis.com/token', data={
                'code': code,
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code'
            }).json()

            if 'error' in token_resp:
                print(f"[GOOGLE] Token exchange error: {token_resp}")
                return None

            user_info = requests.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {token_resp["access_token"]}'}
            ).json()

            return {
                "access_token": token_resp['access_token'],
                "refresh_token": token_resp.get('refresh_token'),
                "expires_in": token_resp.get('expires_in'),
                "user_email": user_info.get('email'),
                "user_name": user_info.get('name', '')
            }
        except Exception as e:
            print(f"[GOOGLE] Error exchanging code: {e}")
            return None

    @staticmethod
    def refresh_access_token(refresh_token: str) -> Optional[str]:
        """Refresh an expired access token. Returns new access_token or None."""
        try:
            resp = requests.post('https://oauth2.googleapis.com/token', data={
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token'
            }).json()
            if 'error' in resp:
                print(f"[GOOGLE] Refresh error: {resp}")
                return None
            return resp.get('access_token')
        except Exception as e:
            print(f"[GOOGLE] Error refreshing token: {e}")
            return None

    @staticmethod
    def _get_headers(access_token: str, refresh_token: str, connection_update_callback=None) -> Optional[dict]:
        """Get valid auth headers refreshing token if needed.
        Returns None if both token and refresh fail (caller should mark connection expired).
        """
        headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
        # Test current token
        test = requests.get('https://www.googleapis.com/calendar/v3/users/me/calendarList?maxResults=1', headers=headers)
        if test.status_code == 401 and refresh_token:
            new_token = GoogleCalendarAdapter.refresh_access_token(refresh_token)
            if new_token:
                if connection_update_callback:
                    connection_update_callback(new_token)
                headers['Authorization'] = f'Bearer {new_token}'
            else:
                # Refresh failed → token is dead
                if connection_update_callback:
                    connection_update_callback(None)
                return None
        elif test.status_code == 401:
            # No refresh token at all
            return None
        return headers

    @staticmethod
    def get_calendar_timezone(access_token: str, refresh_token: str, connection_update_callback=None) -> str:
        """Get the user's primary Google Calendar timezone."""
        try:
            headers = GoogleCalendarAdapter._get_headers(access_token, refresh_token, connection_update_callback)
            if not headers:
                return 'UTC'
            resp = requests.get(
                'https://www.googleapis.com/calendar/v3/calendars/primary',
                headers=headers
            )
            if resp.status_code == 200:
                return resp.json().get('timeZone', 'UTC')
            return 'UTC'
        except Exception:
            return 'UTC'

    @staticmethod
    def create_event(access_token: str, refresh_token: str, event_data: dict, connection_update_callback=None) -> Optional[Dict]:
        try:
            headers = GoogleCalendarAdapter._get_headers(access_token, refresh_token, connection_update_callback)
            if not headers:
                return None

            # Use the user's calendar timezone for naive datetimes
            calendar_tz = event_data.get('timeZone', 'UTC')

            event = {
                'summary': event_data['title'],
                'description': event_data.get('description', ''),
                'location': event_data.get('location', ''),
                'start': {
                    'dateTime': event_data['start_datetime'],
                    'timeZone': calendar_tz
                },
                'end': {
                    'dateTime': event_data['end_datetime'],
                    'timeZone': calendar_tz
                }
            }

            resp = requests.post(
                'https://www.googleapis.com/calendar/v3/calendars/primary/events',
                headers=headers,
                json=event
            )
            if resp.status_code in (200, 201):
                result = resp.json()
                return {
                    "event_id": result['id'],
                    "html_link": result.get('htmlLink')
                }
            else:
                print(f"[GOOGLE] Create event error {resp.status_code}: {resp.text}")
                return None
        except Exception as e:
            print(f"[GOOGLE] Error creating event: {e}")
            return None

    @staticmethod
    def update_event(access_token: str, refresh_token: str, event_id: str, event_data: dict, connection_update_callback=None) -> Optional[Dict]:
        """Update an existing Google Calendar event."""
        try:
            headers = GoogleCalendarAdapter._get_headers(access_token, refresh_token, connection_update_callback)
            if not headers:
                return None

            calendar_tz = event_data.get('timeZone', 'UTC')

            event = {
                'summary': event_data['title'],
                'description': event_data.get('description', ''),
                'location': event_data.get('location', ''),
                'start': {
                    'dateTime': event_data['start_datetime'],
                    'timeZone': calendar_tz
                },
                'end': {
                    'dateTime': event_data['end_datetime'],
                    'timeZone': calendar_tz
                }
            }

            resp = requests.put(
                f'https://www.googleapis.com/calendar/v3/calendars/primary/events/{event_id}',
                headers=headers,
                json=event
            )
            if resp.status_code in (200,):
                result = resp.json()
                return {"event_id": result['id'], "html_link": result.get('htmlLink')}
            else:
                print(f"[GOOGLE] Update event error {resp.status_code}: {resp.text}")
                return None
        except Exception as e:
            print(f"[GOOGLE] Error updating event: {e}")
            return None

    @staticmethod
    def delete_event(access_token: str, refresh_token: str, event_id: str, connection_update_callback=None) -> bool:
        try:
            headers = GoogleCalendarAdapter._get_headers(access_token, refresh_token, connection_update_callback)
            if not headers:
                return False
            resp = requests.delete(
                f'https://www.googleapis.com/calendar/v3/calendars/primary/events/{event_id}',
                headers=headers
            )
            return resp.status_code in (200, 204)
        except Exception as e:
            print(f"[GOOGLE] Error deleting event: {e}")
            return False

    @staticmethod
    def list_events(access_token: str, refresh_token: str, time_min: str, time_max: str, connection_update_callback=None) -> Optional[list]:
        """List events from the user's primary Google Calendar within a time window.
        Returns a list of dicts with keys: event_id, title, start, end,
        location, description, organizer, attendees, conference_url,
        conference_provider, is_all_day.
        time_min / time_max must be RFC3339 strings (e.g. '2026-03-25T08:00:00Z').
        """
        try:
            headers = GoogleCalendarAdapter._get_headers(access_token, refresh_token, connection_update_callback)
            if not headers:
                return None

            params = {
                'timeMin': time_min,
                'timeMax': time_max,
                'singleEvents': 'true',
                'orderBy': 'startTime',
                'maxResults': 50,
            }
            resp = requests.get(
                'https://www.googleapis.com/calendar/v3/calendars/primary/events',
                headers=headers,
                params=params,
            )
            if resp.status_code != 200:
                print(f"[GOOGLE] list_events error {resp.status_code}: {resp.text[:300]}")
                return None

            events = []
            for item in resp.json().get('items', []):
                if item.get('status') == 'cancelled':
                    continue
                start_raw = item.get('start', {})
                end_raw = item.get('end', {})
                start_dt = start_raw.get('dateTime') or start_raw.get('date')
                end_dt = end_raw.get('dateTime') or end_raw.get('date')
                if not start_dt or not end_dt:
                    continue

                # Detect all-day events (date only, no dateTime)
                is_all_day = 'dateTime' not in start_raw and 'date' in start_raw

                # Extract conference/video link
                conference_url = None
                conference_provider = None
                conf_data = item.get('conferenceData')
                if conf_data:
                    for ep in conf_data.get('entryPoints', []):
                        if ep.get('entryPointType') == 'video':
                            conference_url = ep.get('uri')
                            break
                    conf_type = conf_data.get('conferenceSolution', {}).get('key', {}).get('type', '')
                    if 'hangoutsMeet' in conf_type or conference_url and 'meet.google' in (conference_url or ''):
                        conference_provider = 'meet'
                    elif 'teamsForBusiness' in conf_type:
                        conference_provider = 'teams'

                # Extract organizer
                org_raw = item.get('organizer', {})
                organizer = None
                if org_raw.get('email'):
                    organizer = {'email': org_raw['email'], 'name': org_raw.get('displayName', '')}

                # Extract attendees
                attendees = []
                for att in item.get('attendees', []):
                    if att.get('self'):
                        continue
                    attendees.append({
                        'email': att.get('email', ''),
                        'name': att.get('displayName', ''),
                        'response_status': att.get('responseStatus', ''),
                    })

                events.append({
                    'event_id': item['id'],
                    'title': item.get('summary', '(Sans titre)'),
                    'start': start_dt,
                    'end': end_dt,
                    'location': item.get('location'),
                    'description': item.get('description'),
                    'organizer': organizer,
                    'attendees': attendees,
                    'conference_url': conference_url,
                    'conference_provider': conference_provider,
                    'is_all_day': is_all_day,
                })
            return events
        except Exception as e:
            print(f"[GOOGLE] Error listing events: {e}")
            return None

    @staticmethod
    def revoke_token(access_token: str) -> bool:
        """Revoke Google OAuth token."""
        try:
            resp = requests.post(
                'https://oauth2.googleapis.com/revoke',
                params={'token': access_token},
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            return resp.status_code == 200
        except Exception:
            return False
