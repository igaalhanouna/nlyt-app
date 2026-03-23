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
        status = event_data.get('status', 'CONFIRMED')
        
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
            f"STATUS:{status}",
            "TRANSP:OPAQUE",
            "SEQUENCE:0",
        ])
        
        # Only add alarm for confirmed events
        if status == "CONFIRMED":
            lines.extend([
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                "DESCRIPTION:Rappel NLYT",
                "TRIGGER:-PT1H",
                "END:VALARM",
            ])
        
        lines.extend([
            "END:VEVENT",
            "END:VCALENDAR"
        ])
        
        # Join with CRLF as per RFC 5545
        return '\r\n'.join(lines)
    
    @staticmethod
    def generate_ics_bytes(event_data: Dict) -> bytes:
        """Generate ICS content as UTF-8 bytes"""
        return ICSGenerator.generate_ics(event_data).encode('utf-8')
    
    @staticmethod
    def generate_feed(appointments: list, calendar_name: str = "NLYT") -> str:
        """
        Generate an ICS feed containing multiple appointments.
        Suitable for calendar subscription (webcal://).
        
        Args:
            appointments: List of appointment dicts from MongoDB
            calendar_name: Name for the calendar feed
        
        Returns:
            Complete ICS feed as string
        """
        from datetime import timedelta
        
        now_utc_dt = datetime.now(timezone.utc)
        now_ics = now_utc_dt.strftime('%Y%m%dT%H%M%SZ')
        
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//NLYT//Appointment Commitment System//FR",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            f"X-WR-CALNAME:NLYT - {ICSGenerator.escape_ics_text(calendar_name)}",
            "X-WR-TIMEZONE:UTC",
        ]
        
        for apt in appointments:
            try:
                # Parse datetime
                start_str = apt.get('start_datetime', '')
                if '+' in start_str or 'Z' in start_str:
                    start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                else:
                    start_dt = datetime.fromisoformat(start_str).replace(tzinfo=timezone.utc)
                
                duration = apt.get('duration_minutes', 60)
                end_dt = start_dt + timedelta(minutes=duration)
                
                start_utc = start_dt.astimezone(timezone.utc)
                end_utc = end_dt.astimezone(timezone.utc)
                
                start_ics = start_utc.strftime('%Y%m%dT%H%M%SZ')
                end_ics = end_utc.strftime('%Y%m%dT%H%M%SZ')
                
                uid = f"{apt.get('appointment_id', 'event')}@nlyt.app"
                
                # Determine status
                is_cancelled = apt.get('status') in ['cancelled', 'deleted']
                status = "CANCELLED" if is_cancelled else "CONFIRMED"
                
                # Build title
                title = apt.get('title', 'Rendez-vous NLYT')
                if is_cancelled:
                    title = f"[ANNULÉ] {title}"
                title = ICSGenerator.escape_ics_text(title)
                
                # Location
                location = apt.get('location', '')
                if not location and apt.get('meeting_provider'):
                    location = f"Visio - {apt.get('meeting_provider')}"
                location = ICSGenerator.escape_ics_text(location)
                
                # Description
                if is_cancelled:
                    desc = "Ce rendez-vous a ete annule."
                else:
                    desc = f"Rendez-vous NLYT organise via nlyt.app. Penalite: {apt.get('penalty_amount', 0)} {apt.get('penalty_currency', 'EUR').upper()}"
                desc = ICSGenerator.escape_ics_text(desc)
                
                lines.append("BEGIN:VEVENT")
                lines.append(f"DTSTART:{start_ics}")
                lines.append(f"DTEND:{end_ics}")
                lines.append(f"DTSTAMP:{now_ics}")
                lines.append(f"UID:{uid}")
                lines.append(ICSGenerator.fold_line(f"SUMMARY:{title}"))
                lines.append(ICSGenerator.fold_line(f"DESCRIPTION:{desc}"))
                if location:
                    lines.append(ICSGenerator.fold_line(f"LOCATION:{location}"))
                lines.append(f"STATUS:{status}")
                lines.append("TRANSP:OPAQUE")
                lines.append("SEQUENCE:0")
                
                # Alarm only for confirmed events
                if status == "CONFIRMED":
                    lines.append("BEGIN:VALARM")
                    lines.append("ACTION:DISPLAY")
                    lines.append("DESCRIPTION:Rappel NLYT")
                    lines.append("TRIGGER:-PT1H")
                    lines.append("END:VALARM")
                
                lines.append("END:VEVENT")
            
            except Exception as e:
                # Skip malformed appointments
                continue
        
        lines.append("END:VCALENDAR")
        
        return '\r\n'.join(lines)