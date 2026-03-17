from datetime import datetime, timedelta
from typing import Dict

class ICSGenerator:
    @staticmethod
    def generate_ics(event_data: Dict) -> str:
        start_dt = datetime.fromisoformat(event_data['start_datetime'].replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(event_data['end_datetime'].replace('Z', '+00:00'))
        
        start_str = start_dt.strftime('%Y%m%dT%H%M%SZ')
        end_str = end_dt.strftime('%Y%m%dT%H%M%SZ')
        now_str = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        
        uid = event_data.get('uid', f"{event_data['appointment_id']}@nlyt.app")
        
        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//NLYT//Appointment Commitment//FR
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
DTSTART:{start_str}
DTEND:{end_str}
DTSTAMP:{now_str}
UID:{uid}
SUMMARY:{event_data['title']}
DESCRIPTION:{event_data.get('description', '')}
LOCATION:{event_data.get('location', '')}
STATUS:CONFIRMED
SEQUENCE:0
END:VEVENT
END:VCALENDAR"""
        
        return ics_content
    
    @staticmethod
    def generate_ics_bytes(event_data: Dict) -> bytes:
        return ICSGenerator.generate_ics(event_data).encode('utf-8')