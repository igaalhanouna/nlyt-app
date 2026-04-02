"""
Setup des données de recette UI V5.1 — Scénarios réalistes avec vrais utilisateurs.
"""
import sys, os, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import db
from services.declarative_service import initialize_declarative_phase, submit_sheet
from utils.date_utils import now_utc
from datetime import timedelta

# Real user IDs
ORG_UID = "d13498f9-9c0d-47d4-b48f-9e327e866127"     # testuser_audit@nlyt.app
USER1_UID = "239d1bbc-a4ea-47ac-b3c8-2f02f0769ef7"    # igaal@hotmail.com
USER2_UID = "b1d07936-47bf-4855-a0ed-de27c96a01a2"    # audit_fresh@example.com
USER3_UID = "ef067fe8-510f-492b-8367-f751db1250c1"    # outlook_test@nlyt.app

now = now_utc()
SCENARIOS = []

def create_scenario(title, org_status, participants_cfg, scenario_id):
    apt_id = f"ui-recette-{scenario_id}"
    start = now - timedelta(hours=3)
    end = now - timedelta(hours=2)

    db.appointments.insert_one({
        "appointment_id": apt_id,
        "title": title,
        "organizer_id": ORG_UID,
        "status": "active",
        "start_datetime": start.isoformat(),
        "end_datetime": end.isoformat(),
        "appointment_type": "physical",
        "location": "15 Rue de Rivoli, 75001 Paris",
        "location_display_name": "15 Rue de Rivoli, Paris",
        "duration_minutes": 60,
        "guarantee_amount": 50,
        "penalty_amount": 50,
        "penalty_currency": "EUR",
        "tolerated_delay_minutes": 15,
        "cancellation_deadline_hours": 24,
        "created_at": (now - timedelta(days=1)).isoformat(),
    })

    # Organizer participant
    org_pid = f"p-{scenario_id}-org"
    db.participants.insert_one({
        "participant_id": org_pid,
        "appointment_id": apt_id,
        "user_id": ORG_UID,
        "email": "testuser_audit@nlyt.app",
        "first_name": "Test",
        "last_name": "Audit",
        "status": org_status,
        "is_organizer": True,
    })
    db.attendance_records.insert_one({
        "record_id": str(uuid.uuid4()),
        "appointment_id": apt_id,
        "participant_id": org_pid,
        "outcome": "manual_review",
        "review_required": True,
        "confidence_level": "LOW",
    })

    pids = [org_pid]
    for i, cfg in enumerate(participants_cfg):
        pid = f"p-{scenario_id}-{i}"
        db.participants.insert_one({
            "participant_id": pid,
            "appointment_id": apt_id,
            "user_id": cfg["user_id"],
            "email": cfg["email"],
            "first_name": cfg.get("first_name", ""),
            "last_name": cfg.get("last_name", ""),
            "status": cfg["status"],
            "is_organizer": False,
        })
        db.attendance_records.insert_one({
            "record_id": str(uuid.uuid4()),
            "appointment_id": apt_id,
            "participant_id": pid,
            "outcome": "manual_review",
            "review_required": True,
            "confidence_level": "LOW",
        })
        pids.append(pid)

    return apt_id, pids


# ── SCÉNARIO 1: Org garanti + Participant garanti ──
print("Creating Scénario 1: Org garanti + Part garanti")
apt1, pids1 = create_scenario(
    "S1 — Réunion stratégique (2 garantis)",
    "accepted_guaranteed",
    [{"user_id": USER1_UID, "email": "igaal@hotmail.com",
      "first_name": "Igaal", "last_name": "Hanouna",
      "status": "accepted_guaranteed"}],
    "s1"
)
initialize_declarative_phase(apt1)
state1 = db.appointments.find_one({"appointment_id": apt1}, {"_id": 0, "declarative_phase": 1})
sheets1 = db.attendance_sheets.count_documents({"appointment_id": apt1})
print(f"  → Phase: {state1.get('declarative_phase')}, Sheets: {sheets1}")

# ── SCÉNARIO 2: Org garanti + Participant non-garanti ──
print("\nCreating Scénario 2: Org garanti + Part non-garanti")
apt2, pids2 = create_scenario(
    "S2 — Point projet (1 non-garanti)",
    "accepted_guaranteed",
    [{"user_id": USER1_UID, "email": "igaal@hotmail.com",
      "first_name": "Igaal", "last_name": "Hanouna",
      "status": "accepted_pending_guarantee"}],
    "s2"
)
initialize_declarative_phase(apt2)
state2 = db.appointments.find_one({"appointment_id": apt2}, {"_id": 0, "declarative_phase": 1})
sheets2 = db.attendance_sheets.count_documents({"appointment_id": apt2})
rec2 = db.attendance_records.find_one({"appointment_id": apt2, "participant_id": pids2[1]}, {"_id": 0, "outcome": 1})
print(f"  → Phase: {state2.get('declarative_phase')}, Sheets: {sheets2}, Part outcome: {rec2.get('outcome')}")

# ── SCÉNARIO 3: Mix 3 participants, 2 garantis ──
print("\nCreating Scénario 3: 3 participants, 2 garantis")
apt3, pids3 = create_scenario(
    "S3 — Comité de pilotage (mix garantis)",
    "accepted_guaranteed",
    [
        {"user_id": USER1_UID, "email": "igaal@hotmail.com",
         "first_name": "Igaal", "last_name": "Hanouna",
         "status": "accepted_guaranteed"},
        {"user_id": USER2_UID, "email": "audit_fresh@example.com",
         "first_name": "Fresh", "last_name": "User",
         "status": "accepted_pending_guarantee"},
    ],
    "s3"
)
initialize_declarative_phase(apt3)
state3 = db.appointments.find_one({"appointment_id": apt3}, {"_id": 0, "declarative_phase": 1})
sheets3 = db.attendance_sheets.count_documents({"appointment_id": apt3})
rec3 = db.attendance_records.find_one({"appointment_id": apt3, "participant_id": pids3[2]}, {"_id": 0, "outcome": 1})
print(f"  → Phase: {state3.get('declarative_phase')}, Sheets: {sheets3}, Non-garanti outcome: {rec3.get('outcome')}")

# ── SCÉNARIO 4: Org garanti + 2 non-garantis = not_needed ──
print("\nCreating Scénario 4: 1 garanti + 2 non-garantis")
apt4, pids4 = create_scenario(
    "S4 — Formation (< 2 garantis)",
    "accepted_guaranteed",
    [
        {"user_id": USER1_UID, "email": "igaal@hotmail.com",
         "first_name": "Igaal", "last_name": "Hanouna",
         "status": "accepted_pending_guarantee"},
        {"user_id": USER3_UID, "email": "outlook_test@nlyt.app",
         "first_name": "Outlook", "last_name": "Test",
         "status": "accepted"},
    ],
    "s4"
)
initialize_declarative_phase(apt4)
state4 = db.appointments.find_one({"appointment_id": apt4}, {"_id": 0, "declarative_phase": 1})
sheets4 = db.attendance_sheets.count_documents({"appointment_id": apt4})
print(f"  → Phase: {state4.get('declarative_phase')}, Sheets: {sheets4}")

# ── SCÉNARIO 5: Org + Part garantis, tout le monde présent → resolved ──
print("\nCreating Scénario 5: 2 garantis + déclarations + resolved")
apt5, pids5 = create_scenario(
    "S5 — Revue technique (résolu)",
    "accepted_guaranteed",
    [{"user_id": USER1_UID, "email": "igaal@hotmail.com",
      "first_name": "Igaal", "last_name": "Hanouna",
      "status": "accepted_guaranteed"}],
    "s5"
)
initialize_declarative_phase(apt5)
# Submit sheets declaring everyone present
sheets5 = list(db.attendance_sheets.find({"appointment_id": apt5}, {"_id": 0}))
for sh in sheets5:
    decls = [{"target_participant_id": d["target_participant_id"],
              "declared_status": "present_on_time"} for d in sh["declarations"]]
    submit_sheet(apt5, sh["submitted_by_user_id"], decls)

state5 = db.appointments.find_one({"appointment_id": apt5}, {"_id": 0, "declarative_phase": 1})
disputes5 = db.declarative_disputes.count_documents({"appointment_id": apt5})
print(f"  → Phase: {state5.get('declarative_phase')}, Disputes: {disputes5}")

# ── Summary ──
print("\n" + "=" * 60)
print("RÉSUMÉ DES SCÉNARIOS CRÉÉS")
print("=" * 60)
print(f"S1 (2 garantis)     → Phase: {state1.get('declarative_phase')}, Sheets: {sheets1}")
print(f"S2 (1 non-garanti)  → Phase: {state2.get('declarative_phase')}, Sheets: {sheets2}")
print(f"S3 (mix 3 parts)    → Phase: {state3.get('declarative_phase')}, Sheets: {sheets3}")
print(f"S4 (< 2 garantis)   → Phase: {state4.get('declarative_phase')}, Sheets: {sheets4}")
print(f"S5 (résolu)         → Phase: {state5.get('declarative_phase')}, Disputes: {disputes5}")
