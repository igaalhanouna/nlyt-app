import os
from typing import Optional, Dict
import requests
import urllib.parse

CLIENT_ID = os.environ.get('MICROSOFT_CLIENT_ID')
CLIENT_SECRET = os.environ.get('MICROSOFT_CLIENT_SECRET')

AUTHORITY = 'https://login.microsoftonline.com/common/oauth2/v2.0'
GRAPH_API = 'https://graph.microsoft.com/v1.0'
SCOPES = ['Calendars.ReadWrite', 'User.Read', 'offline_access']


class OutlookCalendarAdapter:

    @staticmethod
    def get_authorization_url(redirect_uri: str, state: str = None) -> tuple:
        params = {
            'client_id': CLIENT_ID,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': ' '.join(SCOPES),
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
        try:
            headers = OutlookCalendarAdapter._get_headers(access_token, refresh_token, connection_update_callback)
            if not headers:
                return 'UTC'
            resp = requests.get(f'{GRAPH_API}/me/mailboxSettings/timeZone', headers=headers)
            if resp.status_code == 200:
                return resp.json().get('value', 'UTC')
            return 'UTC'
        except Exception:
            return 'UTC'

    @staticmethod
    def create_event(access_token: str, refresh_token: str, event_data: dict, connection_update_callback=None) -> Optional[Dict]:
        try:
            headers = OutlookCalendarAdapter._get_headers(access_token, refresh_token, connection_update_callback)
            if not headers:
                return None

            calendar_tz = event_data.get('timeZone', 'UTC')

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

            calendar_tz = event_data.get('timeZone', 'UTC')
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
