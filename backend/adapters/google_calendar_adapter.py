import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request as GoogleRequest
from google_auth_oauthlib.flow import Flow
import requests
from typing import Optional, Dict
import sys
sys.path.append('/app/backend')

CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
SCOPES = ['https://www.googleapis.com/auth/calendar']

class GoogleCalendarAdapter:
    @staticmethod
    def get_authorization_url(redirect_uri: str) -> tuple:
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            },
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            prompt='consent'
        )
        
        return authorization_url, state
    
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
                return None
            
            user_info = requests.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {token_resp["access_token"]}'}
            ).json()
            
            return {
                "access_token": token_resp['access_token'],
                "refresh_token": token_resp.get('refresh_token'),
                "token_expiry": token_resp.get('expires_in'),
                "user_email": user_info.get('email')
            }
        except Exception as e:
            print(f"Error exchanging code: {e}")
            return None
    
    @staticmethod
    def refresh_credentials(refresh_token: str) -> Optional[Credentials]:
        try:
            creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET
            )
            creds.refresh(GoogleRequest())
            return creds
        except Exception as e:
            print(f"Error refreshing credentials: {e}")
            return None
    
    @staticmethod
    def get_service(access_token: str, refresh_token: str):
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET
        )
        
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
        
        return build('calendar', 'v3', credentials=creds), creds.token
    
    @staticmethod
    def create_event(access_token: str, refresh_token: str, event_data: dict) -> Optional[Dict]:
        try:
            service, new_token = GoogleCalendarAdapter.get_service(access_token, refresh_token)
            
            event = {
                'summary': event_data['title'],
                'description': event_data.get('description', ''),
                'location': event_data.get('location', ''),
                'start': {
                    'dateTime': event_data['start_datetime'],
                    'timeZone': 'UTC'
                },
                'end': {
                    'dateTime': event_data['end_datetime'],
                    'timeZone': 'UTC'
                }
            }
            
            result = service.events().insert(calendarId='primary', body=event).execute()
            return {
                "event_id": result['id'],
                "html_link": result.get('htmlLink'),
                "new_access_token": new_token
            }
        except Exception as e:
            print(f"Error creating event: {e}")
            return None
    
    @staticmethod
    def update_event(access_token: str, refresh_token: str, event_id: str, event_data: dict) -> bool:
        try:
            service, _ = GoogleCalendarAdapter.get_service(access_token, refresh_token)
            
            event = service.events().get(calendarId='primary', eventId=event_id).execute()
            
            event['summary'] = event_data.get('title', event['summary'])
            event['description'] = event_data.get('description', event.get('description', ''))
            event['location'] = event_data.get('location', event.get('location', ''))
            
            if 'start_datetime' in event_data:
                event['start'] = {'dateTime': event_data['start_datetime'], 'timeZone': 'UTC'}
            if 'end_datetime' in event_data:
                event['end'] = {'dateTime': event_data['end_datetime'], 'timeZone': 'UTC'}
            
            service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
            return True
        except Exception as e:
            print(f"Error updating event: {e}")
            return False
    
    @staticmethod
    def delete_event(access_token: str, refresh_token: str, event_id: str) -> bool:
        try:
            service, _ = GoogleCalendarAdapter.get_service(access_token, refresh_token)
            service.events().delete(calendarId='primary', eventId=event_id).execute()
            return True
        except Exception as e:
            print(f"Error deleting event: {e}")
            return False