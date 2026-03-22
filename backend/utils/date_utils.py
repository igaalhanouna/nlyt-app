from datetime import datetime, timezone, timedelta
from typing import Optional
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)

# Used ONLY for migrating old naive datetimes to UTC.
# New data arrives as UTC from the frontend — no guessing needed.
_LEGACY_TIMEZONE = ZoneInfo('Europe/Paris')


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_utc_iso() -> str:
    """Return current UTC time as ISO string with Z suffix."""
    return now_utc().strftime('%Y-%m-%dT%H:%M:%SZ')


def parse_iso_datetime(iso_string: str) -> Optional[datetime]:
    """Parse any ISO datetime string into a timezone-aware UTC datetime."""
    if not iso_string:
        return None
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            # Legacy naive string — interpret as Europe/Paris, convert to UTC
            dt = dt.replace(tzinfo=_LEGACY_TIMEZONE).astimezone(timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except Exception:
        return None


def to_utc_iso(dt: datetime) -> str:
    """Convert a datetime to UTC ISO string with Z suffix."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    utc_dt = dt.astimezone(timezone.utc)
    return utc_dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def normalize_to_utc(dt_str: str) -> str:
    """
    Normalize a datetime string to UTC ISO format with 'Z' suffix.

    - If already timezone-aware (has Z or +offset), converts to UTC.
    - If naive (no timezone info), interprets as Europe/Paris local time
      then converts to UTC. This handles legacy data only.
    - New data from the frontend should already be UTC.
    """
    if not dt_str:
        return dt_str
    # Already a proper UTC string
    if dt_str.endswith('Z') and 'T' in dt_str:
        return dt_str
    dt = parse_iso_datetime(dt_str)
    if dt is None:
        return dt_str
    return to_utc_iso(dt)


def to_iso_string(dt: datetime) -> str:
    """Legacy helper — prefer to_utc_iso() for new code."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


_FRENCH_DAYS = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
_FRENCH_MONTHS = ['', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
                  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']


def format_datetime_fr(dt: datetime, tz_name: str = 'Europe/Paris') -> str:
    """
    Format a datetime in French for server-side use (emails, etc.).
    Converts to the specified timezone for display.
    Example: 'Mercredi 22 avril 2026 à 14:30'
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local_dt = dt.astimezone(ZoneInfo(tz_name))
    day_name = _FRENCH_DAYS[local_dt.weekday()]
    month_name = _FRENCH_MONTHS[local_dt.month]
    return f"{day_name.capitalize()} {local_dt.day} {month_name} {local_dt.year} à {local_dt.strftime('%H:%M')}"