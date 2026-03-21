from datetime import datetime, timezone
from typing import Optional

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def parse_iso_datetime(iso_string: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
    except:
        return None

def to_iso_string(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


_FRENCH_DAYS = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
_FRENCH_MONTHS = ['', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
                  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']


def format_datetime_fr(dt: datetime) -> str:
    """Format a datetime in French: 'Mercredi 22 avril 2026 à 14:30'"""
    day_name = _FRENCH_DAYS[dt.weekday()]
    month_name = _FRENCH_MONTHS[dt.month]
    return f"{day_name.capitalize()} {dt.day} {month_name} {dt.year} à {dt.strftime('%H:%M')}"