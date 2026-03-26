from database import db

# Get a sample appointment
apt = db.appointments.find_one({}, {'_id': 0, 'appointment_id': 1, 'title': 1, 'status': 1, 'appointment_type': 1})
print('=== Sample Appointment ===')
print(apt)

if apt:
    apt_id = apt['appointment_id']
    parts = list(db.participants.find({'appointment_id': apt_id}, {'_id': 0, 'participant_id': 1, 'first_name': 1, 'email': 1, 'status': 1, 'is_organizer': 1, 'invitation_token': 1}))
    print(f'\n=== Participants for {apt_id[:8]} ===')
    for p in parts:
        tok = p.get('invitation_token', 'N/A')
        print(f"  {p.get('first_name','')} | is_org={p.get('is_organizer')} | status={p.get('status')} | token={tok[:12] if tok else 'N/A'}...")

# Check all distinct participant statuses
statuses = db.participants.distinct('status')
print(f'\n=== All participant statuses in DB: {statuses}')

# Count by is_organizer and status
print('\n=== Organizer participants ===')
org_parts = list(db.participants.find({'is_organizer': True}, {'_id': 0, 'status': 1, 'first_name': 1, 'appointment_id': 1}))
for p in org_parts[:5]:
    print(f"  {p.get('first_name','')} | status={p.get('status')}")

print('\n=== Non-organizer participants ===')
non_org_parts = list(db.participants.find({'is_organizer': {"$ne": True}}, {'_id': 0, 'status': 1, 'first_name': 1, 'email': 1}))
for p in non_org_parts[:10]:
    print(f"  {p.get('first_name','')} ({p.get('email','')}) | status={p.get('status')}")

# Find active appointments with their participants
print('\n=== Active appointments with participants ===')
active_apts = list(db.appointments.find({'status': 'active'}, {'_id': 0, 'appointment_id': 1, 'title': 1}).limit(3))
for a in active_apts:
    print(f"\n  Apt: {a['title']} ({a['appointment_id'][:8]})")
    parts = list(db.participants.find({'appointment_id': a['appointment_id']}, {'_id': 0, 'participant_id': 1, 'first_name': 1, 'status': 1, 'is_organizer': 1, 'invitation_token': 1}))
    for p in parts:
        tok = p.get('invitation_token', 'N/A')
        print(f"    {p.get('first_name','')} | is_org={p.get('is_organizer')} | status={p.get('status')} | token={tok[:16] if tok else 'N/A'}...")
