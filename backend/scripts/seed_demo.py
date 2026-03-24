"""
NLYT Demo Seed Script — Preview Environment Only
==================================================
Generates a realistic, coherent dataset for demonstration purposes.

Creates:
  - 20 users (diverse profiles)
  - Workspaces + memberships
  - Calendar connections (Google, Outlook, Teams)
  - User settings
  - 45 appointments (various statuses, providers, dates)
  - Participants with realistic acceptance flow
  - Payment guarantees
  - Attendance records + distributions + wallets
  - 3 "premium demo" users with showcase scenarios

Usage:
  cd /app/backend
  MONGO_URL="mongodb://localhost:27017" DB_NAME="test_database" python3 scripts/seed_demo.py

Idempotent: cleans demo data (seed_demo=true marker) before inserting.
"""

import uuid
import random
import logging
from datetime import datetime, timezone, timedelta

import sys
sys.path.insert(0, '/app/backend')

from database import db
from utils.password_utils import hash_password

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────

DEMO_MARKER = {"_seed_demo": True}
DEMO_PASSWORD = "Demo2026!"
DEMO_PASSWORD_HASH = hash_password(DEMO_PASSWORD)
NOW = datetime.now(timezone.utc)

PROVIDERS = ["Google Meet", "Microsoft Teams", "Zoom", "external"]
CHARITY_ASSOCIATIONS = [
    ("assoc_croix_rouge", "Croix-Rouge française"),
    ("assoc_restos_coeur", "Les Restos du Cœur"),
    ("assoc_secours_populaire", "Secours populaire français"),
    ("assoc_medecins_sans_frontieres", "Médecins Sans Frontières"),
    ("assoc_unicef", "UNICEF France"),
]

APPOINTMENT_TITLES = [
    "Point hebdomadaire équipe produit",
    "Coaching individuel — session 3",
    "Entretien de recrutement — Data Analyst",
    "Revue de sprint Q1",
    "Réunion partenariat commercial",
    "Atelier design thinking",
    "Formation sécurité informatique",
    "Point mensuel freelance",
    "Consultation juridique",
    "Onboarding nouveau collaborateur",
    "Comité de pilotage projet Alpha",
    "Séance de coaching collectif",
    "Négociation contrat fournisseur",
    "Point avancement refonte site",
    "Workshop OKR trimestriel",
    "Entretien annuel de performance",
    "Démo produit pour investisseur",
    "Réunion copropriété",
    "Atelier créativité brainstorming",
    "Point de suivi mission freelance",
    "Rendez-vous notaire",
    "Consultation stratégie marketing",
    "Stand-up daily ops",
    "Formation management agile",
    "Entretien client grand compte",
    "Bilan semestriel coaching",
    "Réunion lancement campagne",
    "Point budget prévisionnel",
    "Session mentorat startup",
    "Revue architecture technique",
]

LOCATIONS = [
    ("45 rue de Rivoli, Paris", "45 Rue de Rivoli, 75001 Paris, France", 48.8589, 2.3469),
    ("12 avenue Jean Médecin, Nice", "12 Avenue Jean Médecin, 06000 Nice, France", 43.7009, 7.2683),
    ("Place Bellecour, Lyon", "Place Bellecour, 69002 Lyon, France", 45.7578, 4.8320),
    ("Gare Saint-Jean, Bordeaux", "Gare de Bordeaux-Saint-Jean, 33000 Bordeaux, France", 44.8254, -0.5564),
    ("Campus Sophia Antipolis", "2400 Route des Dolines, 06560 Valbonne, France", 43.6163, 7.0553),
]

# ─── User Profiles ──────────────────────────────────────────

USER_PROFILES = [
    # (first, last, email, phone, bio/role context)
    ("Marie", "Dupont", "marie.dupont@demo-nlyt.fr", "+33612345001", "coach"),
    ("Thomas", "Martin", "thomas.martin@demo-nlyt.fr", "+33612345002", "freelance"),
    ("Sophie", "Bernard", "sophie.bernard@demo-nlyt.fr", "+33612345003", "RH"),
    ("Lucas", "Petit", "lucas.petit@demo-nlyt.fr", "+33612345004", "dev"),
    ("Camille", "Robert", "camille.robert@demo-nlyt.fr", "+33612345005", "manager"),
    ("Julien", "Richard", "julien.richard@demo-nlyt.fr", "+33612345006", "consultant"),
    ("Emma", "Moreau", "emma.moreau@demo-nlyt.fr", "+33612345007", "designer"),
    ("Nathan", "Simon", "nathan.simon@demo-nlyt.fr", "+33612345008", "agent-immo"),
    ("Léa", "Laurent", "lea.laurent@demo-nlyt.fr", "+33612345009", "avocat"),
    ("Hugo", "Michel", "hugo.michel@demo-nlyt.fr", "+33612345010", "freelance"),
    ("Chloé", "Garcia", "chloe.garcia@demo-nlyt.fr", "+33612345011", "coach"),
    ("Antoine", "David", "antoine.david@demo-nlyt.fr", "+33612345012", "CTO"),
    ("Manon", "Bertrand", "manon.bertrand@demo-nlyt.fr", "+33612345013", "RH"),
    ("Maxime", "Roux", "maxime.roux@demo-nlyt.fr", "+33612345014", "CEO"),
    ("Sarah", "Vincent", "sarah.vincent@demo-nlyt.fr", "+33612345015", "marketing"),
    ("Paul", "Fournier", "paul.fournier@demo-nlyt.fr", "+33612345016", "notaire"),
    ("Julie", "Morel", "julie.morel@demo-nlyt.fr", "+33612345017", "perso"),
    ("Romain", "Girard", "romain.girard@demo-nlyt.fr", "+33612345018", "freelance"),
    ("Inès", "André", "ines.andre@demo-nlyt.fr", "+33612345019", "startup"),
    ("Alexandre", "Lefèvre", "alex.lefevre@demo-nlyt.fr", "+33612345020", "perso"),
    # ── 3 Premium Demo Users ──
    ("Clara", "Deschamps", "clara.deschamps@demo-nlyt.fr", "+33612345021", "demo-conflit"),
    ("Victor", "Fontaine", "victor.fontaine@demo-nlyt.fr", "+33612345022", "demo-optimal"),
    ("Aurélie", "Marchand", "aurelie.marchand@demo-nlyt.fr", "+33612345023", "demo-penalite"),
]


# ─── Helper functions ───────────────────────────────────────

def uid():
    return str(uuid.uuid4())


def iso(dt):
    return dt.isoformat()


def random_future(min_days=1, max_days=30):
    delta = timedelta(days=random.randint(min_days, max_days),
                      hours=random.choice([9, 10, 11, 14, 15, 16]),
                      minutes=random.choice([0, 15, 30]))
    return NOW + delta


def random_past(min_days=1, max_days=60):
    delta = timedelta(days=random.randint(min_days, max_days),
                      hours=random.choice([9, 10, 11, 14, 15, 16]),
                      minutes=random.choice([0, 15, 30]))
    return NOW - delta


# ─── Cleanup ────────────────────────────────────────────────

def cleanup():
    """Remove all demo-seeded documents."""
    collections = [
        'users', 'workspaces', 'workspace_memberships', 'calendar_connections',
        'user_settings', 'appointments', 'participants', 'payment_guarantees',
        'attendance_records', 'distributions', 'wallets', 'wallet_transactions',
        'policy_snapshots', 'calendar_sync_logs',
    ]
    total = 0
    for coll in collections:
        r = db[coll].delete_many({"_seed_demo": True})
        if r.deleted_count:
            total += r.deleted_count
    if total:
        log.info(f"  Cleanup: {total} documents supprimés")
    else:
        log.info("  Cleanup: rien à supprimer")


# ─── Create Users ───────────────────────────────────────────

def create_users():
    users = []
    for i, (first, last, email, phone, role) in enumerate(USER_PROFILES):
        user_id = uid()
        created = NOW - timedelta(days=random.randint(10, 120))
        user = {
            **DEMO_MARKER,
            "user_id": user_id,
            "email": email,
            "password_hash": DEMO_PASSWORD_HASH,
            "first_name": first,
            "last_name": last,
            "phone": phone,
            "is_verified": True,
            "created_at": iso(created),
            "updated_at": iso(created),
            "_demo_role": role,  # internal tag for seed logic
        }
        users.append(user)

    db.users.insert_many(users)
    log.info(f"  {len(users)} utilisateurs créés")
    return users


# ─── Create Workspaces ──────────────────────────────────────

def create_workspaces(users):
    workspaces = []
    memberships = []
    # Each user gets a default workspace
    for u in users:
        ws_id = uid()
        ws = {
            **DEMO_MARKER,
            "workspace_id": ws_id,
            "name": f"Espace de {u['first_name']} {u['last_name']}",
            "description": "Espace de travail personnel",
            "owner_id": u["user_id"],
            "is_default": True,
            "created_at": u["created_at"],
            "updated_at": u["created_at"],
        }
        workspaces.append(ws)

        mem = {
            **DEMO_MARKER,
            "membership_id": uid(),
            "workspace_id": ws_id,
            "user_id": u["user_id"],
            "role": "admin",
            "joined_at": u["created_at"],
        }
        memberships.append(mem)
        u["_workspace_id"] = ws_id

    db.workspaces.insert_many(workspaces)
    db.workspace_memberships.insert_many(memberships)
    log.info(f"  {len(workspaces)} workspaces + memberships créés")
    return workspaces


# ─── Calendar Connections ───────────────────────────────────

def create_calendar_connections(users):
    connections = []
    settings = []

    for u in users:
        role = u["_demo_role"]
        user_id = u["user_id"]
        conns_for_user = []

        # Google: 60% of users
        if random.random() < 0.6 or role in ("coach", "manager", "demo-conflit", "demo-optimal"):
            conn = {
                **DEMO_MARKER,
                "connection_id": uid(),
                "provider": "google",
                "user_id": user_id,
                "status": "connected",
                "google_email": u["email"],
                "google_name": f"{u['first_name']} {u['last_name']}",
                "access_token": f"demo_google_at_{user_id[:8]}",
                "refresh_token": f"demo_google_rt_{user_id[:8]}",
                "connected_at": iso(NOW - timedelta(days=random.randint(5, 60))),
                "updated_at": iso(NOW - timedelta(days=random.randint(0, 5))),
                "calendar_timezone": "Europe/Paris",
            }
            connections.append(conn)
            conns_for_user.append("google")

        # Outlook: 40% of users
        if random.random() < 0.4 or role in ("CTO", "RH", "manager", "demo-conflit", "demo-penalite"):
            has_teams = role in ("CTO", "RH", "manager", "demo-conflit")
            conn = {
                **DEMO_MARKER,
                "connection_id": uid(),
                "provider": "outlook",
                "user_id": user_id,
                "status": "connected",
                "outlook_email": u["email"],
                "outlook_name": f"{u['first_name']} {u['last_name']}",
                "access_token": f"demo_outlook_at_{user_id[:8]}",
                "refresh_token": f"demo_outlook_rt_{user_id[:8]}",
                "connected_at": iso(NOW - timedelta(days=random.randint(5, 60))),
                "updated_at": iso(NOW - timedelta(days=random.randint(0, 5))),
                "calendar_timezone": "Europe/Paris",
                "has_online_meetings_scope": has_teams,
                "scope_level": "teams_advanced" if has_teams else "calendar_base",
            }
            connections.append(conn)
            conns_for_user.append("outlook")

        # User settings
        setting = {
            **DEMO_MARKER,
            "user_id": user_id,
        }
        if "google" in conns_for_user:
            setting["google_connected"] = True
        if "outlook" in conns_for_user:
            setting["teams_connected"] = True
            setting["teams_connected_at"] = iso(NOW - timedelta(days=random.randint(1, 30)))
        if role in ("freelance", "consultant"):
            setting["zoom_connected"] = True
            setting["zoom_connected_at"] = iso(NOW - timedelta(days=random.randint(1, 30)))
            setting["zoom_email"] = u["email"]

        settings.append(setting)
        u["_conns"] = conns_for_user

    if connections:
        db.calendar_connections.insert_many(connections)
    if settings:
        db.user_settings.insert_many(settings)
    log.info(f"  {len(connections)} connexions calendrier + {len(settings)} user_settings créés")


# ─── Create Appointments ────────────────────────────────────

def create_appointments(users):
    """Create 45 appointments with realistic distribution."""
    user_map = {u["user_id"]: u for u in users}
    organizers = [u for u in users if u["_demo_role"] not in ("perso",)]

    appointments = []
    all_participants = []
    all_guarantees = []
    all_snapshots = []
    all_attendance = []
    all_distributions = []
    all_wallets_to_create = set()
    all_wallet_txns = []

    def pick_provider(organizer):
        conns = organizer.get("_conns", [])
        options = []
        if "outlook" in conns:
            options.append("Microsoft Teams")
        if "google" in conns:
            options.append("Google Meet")
        options.append("Zoom")
        options.append("external")
        return random.choice(options)

    def pick_participants(organizer, count=None):
        if count is None:
            count = random.choices([1, 2, 3, 4], weights=[40, 30, 20, 10])[0]
        eligible = [u for u in users if u["user_id"] != organizer["user_id"]]
        return random.sample(eligible, min(count, len(eligible)))

    def make_snapshot(apt):
        snap_id = uid()
        snap = {
            **DEMO_MARKER,
            "snapshot_id": snap_id,
            "appointment_id": apt["appointment_id"],
            "contract_version": "1.0",
            "is_immutable": True,
            "terms": {
                "appointment_title": apt["title"],
                "appointment_type": apt["appointment_type"],
                "start_datetime": apt["start_datetime"],
                "duration_minutes": apt["duration_minutes"],
                "tolerated_delay_minutes": apt["tolerated_delay_minutes"],
                "cancellation_deadline_hours": apt["cancellation_deadline_hours"],
                "penalty_amount": apt["penalty_amount"],
                "penalty_currency": apt["penalty_currency"],
            },
            "consent_language": {"fr": "En acceptant ce rendez-vous, je m'engage à respecter les conditions."},
            "created_at": apt["created_at"],
        }
        all_snapshots.append(snap)
        return snap_id

    # ── Distribution helper ──
    def create_distribution_for_noshow(apt, participant, guarantee):
        dist_id = uid()
        capture = int(apt["penalty_amount"] * 100)
        platform_pct = apt["platform_commission_percent"]
        comp_pct = apt["affected_compensation_percent"]
        charity_pct = apt["charity_percent"]

        platform_cents = int(capture * platform_pct / 100)
        charity_cents = int(capture * charity_pct / 100)
        comp_cents = capture - platform_cents - charity_cents

        beneficiaries = []

        # Platform
        if platform_cents > 0:
            beneficiaries.append({
                "beneficiary_id": uid(),
                "wallet_id": f"wallet_platform_demo",
                "user_id": "__nlyt_platform__",
                "role": "platform",
                "amount_cents": platform_cents,
                "status": "credited_available",
            })
            all_wallets_to_create.add("__nlyt_platform__")

        # Charity
        assoc_id = apt.get("charity_association_id")
        if charity_cents > 0 and assoc_id:
            beneficiaries.append({
                "beneficiary_id": uid(),
                "wallet_id": f"wallet_{assoc_id}",
                "user_id": assoc_id,
                "role": "charity",
                "amount_cents": charity_cents,
                "status": "credited_available",
            })

        # Compensation to organizer
        if comp_cents > 0:
            beneficiaries.append({
                "beneficiary_id": uid(),
                "wallet_id": f"wallet_{apt['organizer_id'][:8]}",
                "user_id": apt["organizer_id"],
                "role": "organizer",
                "amount_cents": comp_cents,
                "status": "credited_available",
            })
            all_wallets_to_create.add(apt["organizer_id"])

        dist = {
            **DEMO_MARKER,
            "distribution_id": dist_id,
            "appointment_id": apt["appointment_id"],
            "guarantee_id": guarantee["guarantee_id"],
            "no_show_participant_id": participant["participant_id"],
            "no_show_user_id": participant.get("user_id") or participant["participant_id"],
            "no_show_is_organizer": False,
            "capture_amount_cents": capture,
            "capture_currency": "eur",
            "stripe_payment_intent_id": f"pi_demo_{dist_id[:8]}",
            "status": "completed",
            "distribution_rules": {
                "platform_commission_percent": platform_pct,
                "affected_compensation_percent": comp_pct,
                "charity_percent": charity_pct,
            },
            "beneficiaries": beneficiaries,
            "hold_expires_at": iso(NOW - timedelta(days=1)),
            "contested": False,
            "contested_at": None,
            "contested_by": None,
            "contest_reason": None,
            "captured_at": apt.get("_eval_at", iso(NOW - timedelta(days=5))),
            "distributed_at": apt.get("_eval_at", iso(NOW - timedelta(days=5))),
            "completed_at": apt.get("_eval_at", iso(NOW - timedelta(days=5))),
            "cancelled_at": None,
            "cancel_reason": None,
            "created_at": apt.get("_eval_at", iso(NOW - timedelta(days=5))),
            "updated_at": apt.get("_eval_at", iso(NOW - timedelta(days=5))),
        }
        all_distributions.append(dist)

        # Track wallet transactions
        for b in beneficiaries:
            all_wallet_txns.append({
                **DEMO_MARKER,
                "transaction_id": uid(),
                "wallet_id": b["wallet_id"],
                "type": "credit_available",
                "amount": b["amount_cents"],
                "currency": "eur",
                "reference_type": "distribution",
                "reference_id": dist_id,
                "description": f"Distribution — {apt['title']}",
                "created_at": dist["created_at"],
            })

    # ───────────────────────────────────────────────────────
    # Generate appointments in categories
    # ───────────────────────────────────────────────────────

    def make_appointment(organizer, title, start_dt, status, apt_type, provider,
                         penalty, charity_pct=0, assoc_id=None, assoc_name=None,
                         participants_data=None, extra_fields=None):
        apt_id = uid()
        loc = None
        loc_display = None
        lat = lng = None

        if apt_type == "physical":
            loc_data = random.choice(LOCATIONS)
            loc, loc_display, lat, lng = loc_data

        created = start_dt - timedelta(days=random.randint(3, 14))
        tolerated = random.choice([5, 10, 15, 20])
        cancel_deadline = random.choice([6, 12, 24, 48])
        comp_pct = round(100 - 20 - charity_pct, 1)  # platform=20% fixed
        duration = random.choice([30, 45, 60, 90])

        apt = {
            **DEMO_MARKER,
            "appointment_id": apt_id,
            "workspace_id": organizer["_workspace_id"],
            "organizer_id": organizer["user_id"],
            "title": title,
            "appointment_type": apt_type,
            "location": loc,
            "location_display_name": loc_display,
            "location_geocoded": loc is not None,
            "location_latitude": lat,
            "location_longitude": lng,
            "meeting_provider": provider if apt_type == "video" else "",
            "start_datetime": iso(start_dt),
            "appointment_timezone": "Europe/Paris",
            "duration_minutes": duration,
            "tolerated_delay_minutes": tolerated,
            "cancellation_deadline_hours": cancel_deadline,
            "penalty_amount": penalty,
            "penalty_currency": "eur",
            "affected_compensation_percent": comp_pct,
            "platform_commission_percent": 20.0,
            "charity_percent": charity_pct,
            "charity_association_id": assoc_id,
            "charity_association_name": assoc_name,
            "policy_template_id": None,
            "event_reminders": {
                "ten_minutes_before": True,
                "one_hour_before": True,
                "one_day_before": True,
            },
            "event_reminders_sent": {},
            "status": status,
            "created_at": iso(created),
            "updated_at": iso(created),
        }
        if extra_fields:
            apt.update(extra_fields)

        snap_id = make_snapshot(apt)
        apt["policy_snapshot_id"] = snap_id
        appointments.append(apt)

        # Create participants
        parts_list = participants_data or pick_participants(organizer)
        for p_user in parts_list:
            p_id = uid()
            token = uid()
            p_status = "invited"
            p_extra = {}

            if status == "active":
                if isinstance(p_user, dict) and p_user.get("_force_status"):
                    p_status = p_user["_force_status"]
                elif start_dt < NOW:
                    # Past appointment
                    p_status = random.choices(
                        ["accepted_guaranteed", "accepted_pending_guarantee", "cancelled_by_participant"],
                        weights=[60, 20, 20]
                    )[0]
                else:
                    # Future appointment
                    p_status = random.choices(
                        ["accepted_guaranteed", "accepted_pending_guarantee", "invited"],
                        weights=[50, 25, 25]
                    )[0]
            elif status == "cancelled":
                p_status = random.choice(["invited", "accepted_pending_guarantee", "cancelled_by_participant"])

            p_email = p_user["email"] if isinstance(p_user, dict) else p_user.get("email", "unknown@demo.fr")
            p_first = p_user.get("first_name", "Unknown") if isinstance(p_user, dict) else "Unknown"
            p_last = p_user.get("last_name", "") if isinstance(p_user, dict) else ""
            p_user_id = p_user.get("user_id") if isinstance(p_user, dict) else None

            part = {
                **DEMO_MARKER,
                "participant_id": p_id,
                "appointment_id": apt_id,
                "email": p_email,
                "first_name": p_first,
                "last_name": p_last,
                "name": "",
                "role": "participant",
                "status": p_status,
                "invitation_token": token,
                "user_id": p_user_id,
                "invited_at": iso(created),
                "created_at": iso(created),
                "updated_at": iso(created),
                **p_extra,
            }

            if p_status in ("accepted_guaranteed", "accepted_pending_guarantee"):
                part["accept_initiated_at"] = iso(created + timedelta(hours=random.randint(1, 24)))

            if p_status == "accepted_guaranteed":
                g_id = uid()
                part["guarantee_id"] = g_id
                part["guaranteed_at"] = iso(created + timedelta(hours=random.randint(2, 48)))
                guarantee = {
                    **DEMO_MARKER,
                    "guarantee_id": g_id,
                    "participant_id": p_id,
                    "appointment_id": apt_id,
                    "invitation_token": token,
                    "stripe_customer_id": f"cus_demo_{p_id[:8]}",
                    "stripe_session_id": f"cs_demo_{g_id[:8]}",
                    "stripe_setup_intent_id": None,
                    "stripe_payment_method_id": f"pm_demo_{g_id[:8]}",
                    "penalty_amount": penalty,
                    "penalty_currency": "eur",
                    "status": "completed",
                    "dev_mode": True,
                    "created_at": part["accept_initiated_at"],
                    "updated_at": part["guaranteed_at"],
                    "completed_at": part["guaranteed_at"],
                }
                all_guarantees.append(guarantee)
                part["_guarantee_doc"] = guarantee

            all_participants.append(part)

        return apt

    # ───────────────────────────────────────────────────────
    # CATEGORY 1: Future active appointments (15)
    # ───────────────────────────────────────────────────────
    log.info("  Generating future active appointments...")
    for i in range(15):
        org = random.choice(organizers)
        title = random.choice(APPOINTMENT_TITLES)
        start = random_future(1, 28)
        apt_type = random.choices(["video", "physical"], weights=[70, 30])[0]
        provider = pick_provider(org) if apt_type == "video" else ""
        penalty = random.choice([10, 20, 30, 50, 75, 100])
        charity_pct = random.choices([0, 0, 0, 10, 15, 20, 30], weights=[40, 10, 10, 15, 10, 10, 5])[0]
        assoc = random.choice(CHARITY_ASSOCIATIONS) if charity_pct > 0 else (None, None)
        make_appointment(org, title, start, "active", apt_type, provider, penalty,
                         charity_pct, assoc[0], assoc[1])

    # ───────────────────────────────────────────────────────
    # CATEGORY 2: Past completed (attendance evaluated) (15)
    # ───────────────────────────────────────────────────────
    log.info("  Generating past completed appointments...")
    for i in range(15):
        org = random.choice(organizers)
        title = random.choice(APPOINTMENT_TITLES)
        start = random_past(2, 45)
        apt_type = random.choices(["video", "physical"], weights=[70, 30])[0]
        provider = pick_provider(org) if apt_type == "video" else ""
        penalty = random.choice([20, 30, 50, 75, 100])
        charity_pct = random.choices([0, 0, 10, 15, 20], weights=[40, 20, 15, 15, 10])[0]
        assoc = random.choice(CHARITY_ASSOCIATIONS) if charity_pct > 0 else (None, None)

        apt = make_appointment(org, title, start, "active", apt_type, provider, penalty,
                               charity_pct, assoc[0], assoc[1],
                               extra_fields={
                                   "attendance_evaluated": True,
                                   "attendance_evaluated_at": iso(start + timedelta(hours=2)),
                               })
        apt["_eval_at"] = iso(start + timedelta(hours=2))

        # Generate attendance records for participants
        apt_parts = [p for p in all_participants if p["appointment_id"] == apt["appointment_id"]]
        summary = {"on_time": 0, "late": 0, "no_show": 0, "waived": 0, "manual_review": 0}

        for p in apt_parts:
            if p["status"] != "accepted_guaranteed":
                continue
            outcome = random.choices(
                ["on_time", "late", "no_show"],
                weights=[60, 25, 15]
            )[0]
            summary[outcome] += 1

            record = {
                **DEMO_MARKER,
                "record_id": uid(),
                "appointment_id": apt["appointment_id"],
                "participant_id": p["participant_id"],
                "participant_email": p["email"],
                "participant_name": f"{p['first_name']} {p['last_name']}",
                "outcome": outcome,
                "confidence": "high",
                "decided_at": iso(start + timedelta(hours=1, minutes=30)),
                "decided_by": org["user_id"],
                "decision_basis": "organizer_manual",
                "auto_capture_enabled": outcome == "no_show",
                "review_required": False,
            }
            all_attendance.append(record)

            # Create distribution for no-shows
            if outcome == "no_show" and p.get("_guarantee_doc"):
                create_distribution_for_noshow(apt, p, p["_guarantee_doc"])

        apt["attendance_summary"] = summary

    # ───────────────────────────────────────────────────────
    # CATEGORY 3: Cancelled appointments (5)
    # ───────────────────────────────────────────────────────
    log.info("  Generating cancelled appointments...")
    for i in range(5):
        org = random.choice(organizers)
        title = random.choice(APPOINTMENT_TITLES)
        start = random_future(3, 20)
        cancel_time = NOW - timedelta(days=random.randint(1, 5))
        apt_type = random.choices(["video", "physical"], weights=[70, 30])[0]
        provider = pick_provider(org) if apt_type == "video" else ""
        penalty = random.choice([20, 50])

        make_appointment(org, title, start, "cancelled", apt_type, provider, penalty,
                         extra_fields={
                             "cancelled_at": iso(cancel_time),
                             "cancelled_by": random.choice([org["user_id"], "participant"]),
                         })

    # ───────────────────────────────────────────────────────
    # CATEGORY 4: Pending organizer guarantee (3)
    # ───────────────────────────────────────────────────────
    log.info("  Generating pending organizer guarantee appointments...")
    for i in range(3):
        org = random.choice(organizers)
        title = random.choice(APPOINTMENT_TITLES)
        start = random_future(5, 20)
        apt_type = "video"
        provider = pick_provider(org)
        penalty = random.choice([30, 50, 100])

        make_appointment(org, title, start, "pending_organizer_guarantee",
                         apt_type, provider, penalty)

    # ───────────────────────────────────────────────────────
    # PREMIUM DEMO 1: Clara — Conflit clair
    # ───────────────────────────────────────────────────────
    log.info("  Generating premium demo: Clara (conflit)...")
    clara = next(u for u in users if u["_demo_role"] == "demo-conflit")
    # Two overlapping appointments
    conflict_time = random_future(3, 7)
    conflict_time = conflict_time.replace(hour=14, minute=0)

    make_appointment(clara, "Coaching client VIP — session mensuelle", conflict_time,
                     "active", "video", "Microsoft Teams", 75, 15,
                     "assoc_croix_rouge", "Croix-Rouge française")

    make_appointment(clara, "Point hebdomadaire équipe projet", conflict_time + timedelta(minutes=15),
                     "active", "video", "Google Meet", 50, 10,
                     "assoc_restos_coeur", "Les Restos du Cœur")

    # ───────────────────────────────────────────────────────
    # PREMIUM DEMO 2: Victor — Suggestion optimale
    # ───────────────────────────────────────────────────────
    log.info("  Generating premium demo: Victor (suggestion optimale)...")
    victor = next(u for u in users if u["_demo_role"] == "demo-optimal")
    # One appointment at 10h, one at 14h → clear slot at 11h-13h
    opt_day = random_future(4, 8)
    opt_day = opt_day.replace(hour=10, minute=0)

    make_appointment(victor, "Stand-up daily engineering", opt_day,
                     "active", "video", "Google Meet", 30)

    make_appointment(victor, "Démo produit pour investisseur", opt_day.replace(hour=14),
                     "active", "video", "Zoom", 100, 20,
                     "assoc_unicef", "UNICEF France")

    # ───────────────────────────────────────────────────────
    # PREMIUM DEMO 3: Aurélie — Pénalité appliquée
    # ───────────────────────────────────────────────────────
    log.info("  Generating premium demo: Aurélie (pénalité)...")
    aurelie = next(u for u in users if u["_demo_role"] == "demo-penalite")
    penalty_time = random_past(5, 12)

    apt_penalite = make_appointment(
        aurelie,
        "Consultation stratégique — client premium",
        penalty_time,
        "active",
        "video",
        "Microsoft Teams",
        100,
        25,
        "assoc_medecins_sans_frontieres",
        "Médecins Sans Frontières",
        extra_fields={
            "attendance_evaluated": True,
            "attendance_evaluated_at": iso(penalty_time + timedelta(hours=2)),
        },
    )
    apt_penalite["_eval_at"] = iso(penalty_time + timedelta(hours=2))

    # Force one no-show participant
    noshow_parts = [p for p in all_participants
                    if p["appointment_id"] == apt_penalite["appointment_id"]
                    and p["status"] == "accepted_guaranteed"]

    if noshow_parts:
        ns_part = noshow_parts[0]
        record = {
            **DEMO_MARKER,
            "record_id": uid(),
            "appointment_id": apt_penalite["appointment_id"],
            "participant_id": ns_part["participant_id"],
            "participant_email": ns_part["email"],
            "participant_name": f"{ns_part['first_name']} {ns_part['last_name']}",
            "outcome": "no_show",
            "confidence": "high",
            "decided_at": iso(penalty_time + timedelta(hours=1, minutes=30)),
            "decided_by": aurelie["user_id"],
            "decision_basis": "organizer_manual",
            "auto_capture_enabled": True,
            "review_required": False,
        }
        all_attendance.append(record)
        if ns_part.get("_guarantee_doc"):
            create_distribution_for_noshow(apt_penalite, ns_part, ns_part["_guarantee_doc"])

        apt_penalite["attendance_summary"] = {"on_time": max(0, len(noshow_parts) - 1), "late": 0, "no_show": 1, "waived": 0, "manual_review": 0}

    # ───────────────────────────────────────────────────────
    # CATEGORY 5: Buffer warning appointments (2)
    # ───────────────────────────────────────────────────────
    log.info("  Generating buffer warning appointments...")
    buffer_org = random.choice(organizers)
    buffer_time = random_future(5, 10).replace(hour=15, minute=0)

    make_appointment(buffer_org, "Formation continue — module 3", buffer_time,
                     "active", "video", pick_provider(buffer_org), 50)
    # Second one starts 20 min after the first ends (tight buffer)
    make_appointment(buffer_org, "Débrief formation avec RH",
                     buffer_time + timedelta(minutes=50),  # 50 min after start of 45-min meeting = 5 min gap
                     "active", "video", pick_provider(buffer_org), 30)

    # ───────────────────────────────────────────────────────
    # INSERT EVERYTHING
    # ───────────────────────────────────────────────────────
    if appointments:
        db.appointments.insert_many(appointments)
    if all_participants:
        # Clean internal helper fields
        for p in all_participants:
            p.pop("_guarantee_doc", None)
            p.pop("_force_status", None)
        db.participants.insert_many(all_participants)
    if all_guarantees:
        db.payment_guarantees.insert_many(all_guarantees)
    if all_snapshots:
        db.policy_snapshots.insert_many(all_snapshots)
    if all_attendance:
        db.attendance_records.insert_many(all_attendance)
    if all_distributions:
        db.distributions.insert_many(all_distributions)

    log.info(f"  {len(appointments)} rendez-vous créés")
    log.info(f"  {len(all_participants)} participants créés")
    log.info(f"  {len(all_guarantees)} garanties créées")
    log.info(f"  {len(all_attendance)} records de présence créés")
    log.info(f"  {len(all_distributions)} distributions créées")

    return appointments, all_wallets_to_create, all_wallet_txns


# ─── Create Wallets ─────────────────────────────────────────

def create_wallets(users, wallets_needed, wallet_txns):
    wallets = []
    # Platform wallet
    if "__nlyt_platform__" in wallets_needed:
        wallets.append({
            **DEMO_MARKER,
            "wallet_id": "wallet_platform_demo",
            "user_id": "__nlyt_platform__",
            "wallet_type": "platform",
            "available_balance": 0,
            "pending_balance": 0,
            "currency": "eur",
            "total_received": 0,
            "total_withdrawn": 0,
            "created_at": iso(NOW - timedelta(days=60)),
            "updated_at": iso(NOW),
        })

    # User wallets
    for u in users:
        w_id = f"wallet_{u['user_id'][:8]}"
        total_received = 0
        # Check if this user has any distributions as beneficiary
        if u["user_id"] in wallets_needed:
            for tx in wallet_txns:
                if tx["wallet_id"] == w_id:
                    total_received += tx["amount"]

        wallets.append({
            **DEMO_MARKER,
            "wallet_id": w_id,
            "user_id": u["user_id"],
            "wallet_type": "user",
            "available_balance": total_received,
            "pending_balance": 0,
            "currency": "eur",
            "stripe_connect_account_id": f"acct_demo_{u['user_id'][:8]}",
            "stripe_connect_status": random.choices(["active", "not_started"], weights=[70, 30])[0],
            "total_received": total_received,
            "total_withdrawn": 0,
            "created_at": u["created_at"],
            "updated_at": iso(NOW),
        })

    # Compute platform wallet balance
    platform_total = sum(tx["amount"] for tx in wallet_txns if tx["wallet_id"] == "wallet_platform_demo")
    for w in wallets:
        if w["user_id"] == "__nlyt_platform__":
            w["available_balance"] = platform_total
            w["total_received"] = platform_total

    if wallets:
        db.wallets.insert_many(wallets)
    if wallet_txns:
        db.wallet_transactions.insert_many(wallet_txns)
    log.info(f"  {len(wallets)} wallets + {len(wallet_txns)} transactions créés")


# ─── Refresh Impact Stats ──────────────────────────────────

def refresh_stats():
    from services.distribution_service import refresh_impact_stats
    stats = refresh_impact_stats()
    log.info(f"  Impact stats: {stats['total_charity_cents']}c fléchés, "
             f"{len(stats['associations'])} associations, "
             f"{stats['distributions_count']} distributions")


# ─── Main ───────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("NLYT Demo Seed — Preview Environment")
    log.info("=" * 60)

    log.info("\n[1/8] Nettoyage des données de démo existantes...")
    cleanup()

    log.info("\n[2/8] Création des utilisateurs...")
    users = create_users()

    log.info("\n[3/8] Création des workspaces...")
    create_workspaces(users)

    log.info("\n[4/8] Connexions calendrier...")
    create_calendar_connections(users)

    log.info("\n[5/8] Création des rendez-vous + participants...")
    appointments, wallets_needed, wallet_txns = create_appointments(users)

    log.info("\n[6/8] Wallets et transactions...")
    create_wallets(users, wallets_needed, wallet_txns)

    log.info("\n[7/8] Refresh des stats d'impact...")
    refresh_stats()

    log.info("\n[8/8] Résumé")
    log.info("─" * 60)
    log.info(f"  Mot de passe commun : {DEMO_PASSWORD}")
    log.info(f"  Utilisateurs premium :")
    log.info(f"    Clara Deschamps  → clara.deschamps@demo-nlyt.fr  (conflit)")
    log.info(f"    Victor Fontaine  → victor.fontaine@demo-nlyt.fr  (suggestion)")
    log.info(f"    Aurélie Marchand → aurelie.marchand@demo-nlyt.fr (pénalité)")
    log.info("─" * 60)
    log.info("Seed terminé avec succès.")


if __name__ == "__main__":
    main()
