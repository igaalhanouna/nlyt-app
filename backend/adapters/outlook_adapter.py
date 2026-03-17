import os
import msal
import requests
from typing import Optional, Dict

CLIENT_ID = os.environ.get('MICROSOFT_CLIENT_ID')
CLIENT_SECRET = os.environ.get('MICROSOFT_CLIENT_SECRET')
TENANT_ID = os.environ.get('MICROSOFT_TENANT_ID')
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ['Calendars.ReadWrite', 'User.Read']

class OutlookAdapter:
    @staticmethod
    def get_authorization_url(redirect_uri: str) -> str:
        app = msal.ConfidentialClientApplication(
            CLIENT_ID,
            authority=AUTHORITY,
            client_credential=CLIENT_SECRET
        )
        
        auth_url = app.get_authorization_request_url(
            scopes=[f"https://graph.microsoft.com/{scope}" for scope in SCOPES],
            redirect_uri=redirect_uri
        )
        
        return auth_url
    
    @staticmethod
    def exchange_code_for_tokens(code: str, redirect_uri: str) -> Optional[Dict]:
        try:
            app = msal.ConfidentialClientApplication(
                CLIENT_ID,
                authority=AUTHORITY,
                client_credential=CLIENT_SECRET
            )
            
            result = app.acquire_token_by_authorization_code(
                code,
                scopes=[f"https://graph.microsoft.com/{scope}" for scope in SCOPES],
                redirect_uri=redirect_uri
            )
            
            if 'error' in result:
                print(f"Error: {result.get('error_description')}")
                return None
            
            user_info = requests.get(
                'https://graph.microsoft.com/v1.0/me',
                headers={'Authorization': f'Bearer {result["access_token"]}'}
            ).json()
            
            return {
                "access_token": result['access_token'],
                "refresh_token": result.get('refresh_token'),
                "token_expiry": result.get('expires_in'),
                "user_email": user_info.get('mail') or user_info.get('userPrincipalName')
            }
        except Exception as e:
            print(f"Error exchanging code: {e}")
            return None
    
    @staticmethod
    def refresh_access_token(refresh_token: str) -> Optional[str]:
        try:
            app = msal.ConfidentialClientApplication(
                CLIENT_ID,
                authority=AUTHORITY,
                client_credential=CLIENT_SECRET
            )
            
            result = app.acquire_token_by_refresh_token(
                refresh_token,
                scopes=[f"https://graph.microsoft.com/{scope}" for scope in SCOPES]
            )
            
            if 'error' in result:
                return None
            
            return result['access_token']
        except Exception as e:
            print(f"Error refreshing token: {e}")
            return None
    
    @staticmethod
    def create_event(access_token: str, event_data: dict) -> Optional[Dict]:
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            event_body = {
                "subject": event_data['title'],
                "body": {
                    "contentType": "HTML",
                    "content": event_data.get('description', '')
                },
                "start": {
                    "dateTime": event_data['start_datetime'],
                    "timeZone": "UTC"
                },
                "end": {
                    "dateTime": event_data['end_datetime'],
                    "timeZone": "UTC"
                },
                "location": {
                    "displayName": event_data.get('location', '')
                }
            }
            
            response = requests.post(
                'https://graph.microsoft.com/v1.0/me/events',
                headers=headers,
                json=event_body
            )
            
            if response.status_code == 201:
                result = response.json()
                return {
                    "event_id": result['id'],
                    "web_link": result.get('webLink')
                }
            return None
        except Exception as e:
            print(f"Error creating event: {e}")
            return None
    
    @staticmethod
    def update_event(access_token: str, event_id: str, event_data: dict) -> bool:
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            update_body = {}
            if 'title' in event_data:
                update_body['subject'] = event_data['title']
            if 'description' in event_data:
                update_body['body'] = {
                    "contentType": "HTML",
                    "content": event_data['description']
                }
            if 'start_datetime' in event_data:
                update_body['start'] = {
                    "dateTime": event_data['start_datetime'],
                    "timeZone": "UTC"
                }
            if 'end_datetime' in event_data:
                update_body['end'] = {
                    "dateTime": event_data['end_datetime'],
                    "timeZone": "UTC"
                }
            if 'location' in event_data:
                update_body['location'] = {
                    "displayName": event_data['location']
                }
            
            response = requests.patch(
                f'https://graph.microsoft.com/v1.0/me/events/{event_id}',
                headers=headers,
                json=update_body
            )
            
            return response.status_code == 200
        except Exception as e:
            print(f"Error updating event: {e}")
            return False
    
    @staticmethod
    def delete_event(access_token: str, event_id: str) -> bool:
        try:
            headers = {'Authorization': f'Bearer {access_token}'}
            
            response = requests.delete(
                f'https://graph.microsoft.com/v1.0/me/events/{event_id}',
                headers=headers
            )
            
            return response.status_code == 204
        except Exception as e:
            print(f"Error deleting event: {e}")
            return False