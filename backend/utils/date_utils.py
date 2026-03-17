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