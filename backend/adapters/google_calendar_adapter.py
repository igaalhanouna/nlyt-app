import os
from typing import Optional, Dict
import requests
import sys
sys.path.append('/app/backend')

CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
SCOPES = ['https://www.googleapis.com/auth/calendar', 'email', 'profile']


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
