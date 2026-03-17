from datetime import datetime, timedelta, timezone
from typing import Dict
import re

class ICSGenerator:
    """
    ICS file generator compatible with:
    - Google Calendar
    - Microsoft Outlook
    - Apple Calendar
    - Other iCalendar-compliant applications
    """
    
    @staticmethod
    def escape_ics_text(text: str) -> str:
        """Escape special characters for ICS format"""
        if not text:
            return ""
        # ICS requires escaping of backslashes, semicolons, commas, and newlines
        text = text.replace('\\', '\\\\')
        text = text.replace(';', '\\;')
        text = text.replace(',', '\\,')
        text = text.replace('\n', '\\n')
        text = text.replace('\r', '')
        return text
    
    @staticmethod
    def fold_line(line: str) -> str:
        """Fold long lines per RFC 5545 (max 75 chars per line)"""
        if len(line) <= 75:
            return line
        
        result = []
        while len(line) > 75:
            result.append(line[:75])
            line = ' ' + line[75:]  # Continuation lines start with space
        result.append(line)
        return '\r\n'.join(result)
    
    @staticmethod
    def generate_ics(event_data: Dict) -> str:
        """
        Generate ICS content from event data.
        
        Args:
            event_data: Dict containing:
                - appointment_id: str
                - title: str
                - description: str (optional)
                - location: str (optional)
                - start_datetime: ISO format string
                - end_datetime: ISO format string
        
        Returns:
            ICS file content as string
        """
        # Parse datetimes
        start_str = event_data['start_datetime']
        end_str = event_data['end_datetime']
        
        # Handle various datetime formats
        try:
            if '+' in start_str or 'Z' in start_str:
                start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            else:
                start_dt = datetime.fromisoformat(start_str).replace(tzinfo=timezone.utc)
        except:
            start_dt = datetime.now(timezone.utc)
        
        try:
            if '+' in end_str or 'Z' in end_str:
                end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
            else:
                end_dt = datetime.fromisoformat(end_str).replace(tzinfo=timezone.utc)
        except:
            end_dt = start_dt + timedelta(hours=1)
        
        # Convert to UTC for ICS format
        start_utc = start_dt.astimezone(timezone.utc)
        end_utc = end_dt.astimezone(timezone.utc)
        now_utc = datetime.now(timezone.utc)
        
        # Format dates for ICS (YYYYMMDDTHHMMSSZ)
        start_ics = start_utc.strftime('%Y%m%dT%H%M%SZ')
        end_ics = end_utc.strftime('%Y%m%dT%H%M%SZ')
        now_ics = now_utc.strftime('%Y%m%dT%H%M%SZ')
        
        # Generate unique ID
        uid = event_data.get('uid', f"{event_data.get('appointment_id', 'event')}@nlyt.app")
        
        # Escape text fields
        title = ICSGenerator.escape_ics_text(event_data.get('title', 'Rendez-vous NLYT'))
        description = ICSGenerator.escape_ics_text(event_data.get('description', ''))
        location = ICSGenerator.escape_ics_text(event_data.get('location', ''))
        
        # Build ICS content with proper line folding
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//NLYT//Appointment Commitment System//FR",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "X-WR-CALNAME:NLYT Rendez-vous",
            "BEGIN:VEVENT",
            f"DTSTART:{start_ics}",
            f"DTEND:{end_ics}",
            f"DTSTAMP:{now_ics}",
            f"UID:{uid}",
            f"CREATED:{now_ics}",
            f"LAST-MODIFIED:{now_ics}",
            ICSGenerator.fold_line(f"SUMMARY:{title}"),
        ]
        
        if description:
            lines.append(ICSGenerator.fold_line(f"DESCRIPTION:{description}"))
        
        if location:
            lines.append(ICSGenerator.fold_line(f"LOCATION:{location}"))
        
        lines.extend([
            "STATUS:CONFIRMED",
            "TRANSP:OPAQUE",
            "SEQUENCE:0",
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            "DESCRIPTION:Rappel NLYT",
            "TRIGGER:-PT1H",
            "END:VALARM",
            "END:VEVENT",
            "END:VCALENDAR"
        ])
        
        # Join with CRLF as per RFC 5545
        return '\r\n'.join(lines)
    
    @staticmethod
    def generate_ics_bytes(event_data: Dict) -> bytes:
        """Generate ICS content as UTF-8 bytes"""
        return ICSGenerator.generate_ics(event_data).encode('utf-8')