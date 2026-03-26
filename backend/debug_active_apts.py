from database import db
from datetime import datetime, timezone
import re

# Find active appointments
apts = list(db.appointments.find({"status": "active"}, {"_id": 0}).limit(5))
print(f"Active appointments: {len(apts)}")

for apt in apts:
    print(f"\nTitle: {apt.get('title')}")
    print(f"  ID: {apt['appointment_id']}")
    print(f"  Type: {apt.get('appointment_type')}")
    print(f"  Start: {apt.get('start_datetime')}")
    print(f"  Location: {apt.get('location')}")
    
    start_str = apt.get('start_datetime', '')
    if start_str:
        try:
            start = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            diff_min = (start - now).total_seconds() / 60
            print(f"  Time diff: {diff_min:.0f} min (neg=past)")
            
            window_open = start.timestamp() - 30 * 60
            window_close = start.timestamp() + (apt.get('duration_minutes', 60) + apt.get('tolerated_delay_minutes', 0)) * 60
            now_ts = now.timestamp()
            
            if now_ts < window_open:
                print(f"  Window: NOT YET OPEN (opens in {(window_open - now_ts)/60:.0f} min)")
            elif now_ts <= window_close:
                print(f"  Window: OPEN (closes in {(window_close - now_ts)/60:.0f} min)")
            else:
                print(f"  Window: CLOSED (closed {(now_ts - window_close)/60:.0f} min ago)")
        except Exception as e:
            print(f"  Date parse error: {e}")
    
    parts = list(db.participants.find({"appointment_id": apt["appointment_id"]}, {"_id": 0}))
    for p in parts:
        print(f"  -> {p.get('first_name', 'N/A')} | org={p.get('is_organizer')} | status={p.get('status')} | token={p.get('invitation_token', 'N/A')}")
