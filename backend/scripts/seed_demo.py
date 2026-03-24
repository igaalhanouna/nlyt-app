"""
NLYT Demo Seed Script — Preview Environment Only (V2 — 100+ users)
===================================================================
Usage:
  cd /app/backend
  MONGO_URL="mongodb://localhost:27017" DB_NAME="test_database" python3 scripts/seed_demo.py
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

DEMO_MARKER = {"_seed_demo": True}
DEMO_PASSWORD = "Demo2026!"
DEMO_PASSWORD_HASH = hash_password(DEMO_PASSWORD)
NOW = datetime.now(timezone.utc)

CHARITY_ASSOCIATIONS = [
    ("assoc_croix_rouge", "Croix-Rouge française"),
    ("assoc_restos_coeur", "Les Restos du Cœur"),
    ("assoc_secours_populaire", "Secours populaire français"),
    ("assoc_medecins_sans_frontieres", "Médecins Sans Frontières"),
    ("assoc_unicef", "UNICEF France"),
    ("assoc_emmaus", "Emmaüs France"),
    ("assoc_fondation_abbe_pierre", "Fondation Abbé Pierre"),
    ("assoc_action_contre_faim", "Action contre la Faim"),
]

APPOINTMENT_TITLES = [
    "Point hebdomadaire équipe produit", "Coaching individuel — session 3",
    "Entretien de recrutement — Data Analyst", "Revue de sprint Q1",
    "Réunion partenariat commercial", "Atelier design thinking",
    "Formation sécurité informatique", "Point mensuel freelance",
    "Consultation juridique", "Onboarding nouveau collaborateur",
    "Comité de pilotage projet Alpha", "Séance de coaching collectif",
    "Négociation contrat fournisseur", "Point avancement refonte site",
    "Workshop OKR trimestriel", "Entretien annuel de performance",
    "Démo produit pour investisseur", "Réunion copropriété",
    "Atelier créativité brainstorming", "Point de suivi mission freelance",
    "Rendez-vous notaire", "Consultation stratégie marketing",
    "Stand-up daily ops", "Formation management agile",
    "Entretien client grand compte", "Bilan semestriel coaching",
    "Réunion lancement campagne", "Point budget prévisionnel",
    "Session mentorat startup", "Revue architecture technique",
    "Comité éditorial newsletter", "Entretien fournisseur logistique",
    "Réunion de cadrage projet Beta", "Point commercial trimestriel",
    "Atelier retour d'expérience", "Session brainstorm roadmap",
    "Débrief post-mortem incident", "Comité RSE mensuel",
    "Point de suivi alternant", "Préparation salon professionnel",
    "Réunion coordination inter-équipes", "Entretien bilan de compétences",
    "Formation cybersécurité avancée", "Pitch deck review",
    "Point conformité RGPD", "Réunion association de quartier",
]

LOCATIONS = [
    ("45 rue de Rivoli, Paris", "45 Rue de Rivoli, 75001 Paris", 48.8589, 2.3469),
    ("12 avenue Jean Médecin, Nice", "12 Avenue Jean Médecin, 06000 Nice", 43.7009, 7.2683),
    ("Place Bellecour, Lyon", "Place Bellecour, 69002 Lyon", 45.7578, 4.8320),
    ("Gare Saint-Jean, Bordeaux", "Gare de Bordeaux-Saint-Jean, 33000 Bordeaux", 44.8254, -0.5564),
    ("Campus Sophia Antipolis", "2400 Route des Dolines, 06560 Valbonne", 43.6163, 7.0553),
    ("La Défense, Paris", "1 Parvis de la Défense, 92800 Puteaux", 48.8920, 2.2360),
    ("Vieux-Port, Marseille", "Quai du Port, 13002 Marseille", 43.2951, 5.3699),
    ("Place du Capitole, Toulouse", "Place du Capitole, 31000 Toulouse", 43.6047, 1.4442),
    ("Euralille, Lille", "100 Centre Commercial, 59777 Lille", 50.6365, 3.0700),
    ("Presqu'île, Strasbourg", "Place de la Cathédrale, 67000 Strasbourg", 48.5818, 7.7510),
]

# ─── 100+ User Profiles ────────────────────────────────────

FIRST_NAMES_M = [
    "Thomas", "Lucas", "Julien", "Nathan", "Hugo", "Antoine", "Maxime", "Paul",
    "Romain", "Alexandre", "Pierre", "Nicolas", "Mathieu", "Vincent", "Sébastien",
    "Olivier", "François", "Guillaume", "Raphaël", "Louis", "Gabriel", "Arthur",
    "Léo", "Adam", "Jules", "Théo", "Noah", "Ethan", "Liam", "Samuel",
    "Clément", "Adrien", "Benjamin", "David", "Éric", "Fabien", "Grégoire",
    "Hervé", "Ibrahim", "Jean", "Karim", "Laurent", "Marc", "Noé", "Oscar",
    "Philippe", "Quentin", "Rémi", "Stéphane", "Tristan",
]

FIRST_NAMES_F = [
    "Marie", "Sophie", "Camille", "Emma", "Léa", "Chloé", "Manon", "Sarah",
    "Julie", "Inès", "Clara", "Aurélie", "Élodie", "Charlotte", "Anaïs",
    "Margaux", "Pauline", "Marine", "Céline", "Nathalie", "Isabelle", "Valérie",
    "Caroline", "Stéphanie", "Laure", "Hélène", "Diane", "Agathe", "Alice",
    "Béatrice", "Delphine", "Émilie", "Fanny", "Gaëlle", "Juliette", "Lucie",
    "Mélanie", "Nina", "Ophélie", "Patricia", "Rachel", "Sandrine", "Tatiana",
    "Virginie", "Yasmine", "Zoé", "Amandine", "Clémence", "Florence", "Justine",
]

LAST_NAMES = [
    "Dupont", "Martin", "Bernard", "Petit", "Robert", "Richard", "Moreau",
    "Simon", "Laurent", "Michel", "Garcia", "David", "Bertrand", "Roux",
    "Vincent", "Fournier", "Morel", "Girard", "André", "Lefèvre", "Mercier",
    "Duval", "Denis", "Bonnet", "Lemaire", "Renard", "Mathieu", "Chevalier",
    "Robin", "Gauthier", "Perrot", "Blanc", "Guérin", "Muller", "Henry",
    "Rousseau", "Thomas", "Faure", "Brunet", "Blanchard", "Leroux", "Rivière",
    "Collet", "Legrand", "Garnier", "Dubois", "Lambert", "Fontaine", "Roussel",
    "Boyer", "Masson", "Marchand", "Dumont", "Picard", "Gérard", "Arnaud",
    "Barbier", "Lecomte", "Brun", "Rey", "Noel", "Hubert", "Perrin", "Maillard",
]

ROLES = [
    "coach", "freelance", "RH", "dev", "manager", "consultant", "designer",
    "agent-immo", "avocat", "CTO", "CEO", "marketing", "notaire", "perso",
    "startup", "comptable", "architecte", "medecin", "formateur", "commercial",
    "data-analyst", "product-manager", "ops", "recruteur", "chercheur",
]


def uid():
    return str(uuid.uuid4())


def iso(dt):
    return dt.isoformat()


def random_future(min_d=1, max_d=45):
    return NOW + timedelta(
        days=random.randint(min_d, max_d),
        hours=random.choice([8, 9, 10, 11, 14, 15, 16, 17]),
        minutes=random.choice([0, 15, 30, 45]),
    )


def random_past(min_d=1, max_d=90):
    return NOW - timedelta(
        days=random.randint(min_d, max_d),
        hours=random.choice([8, 9, 10, 11, 14, 15, 16, 17]),
        minutes=random.choice([0, 15, 30, 45]),
    )


# ─── Cleanup ────────────────────────────────────────────────

def cleanup():
    total = 0
    for coll in db.list_collection_names():
        r = db[coll].delete_many({"_seed_demo": True})
        if r.deleted_count:
            total += r.deleted_count
    log.info(f"  Nettoyage : {total} documents supprimés" if total else "  Rien à nettoyer")


# ─── Generate 100+ unique user profiles ─────────────────────

def generate_user_profiles(count=105):
    """Generate unique user profiles with realistic French names."""
    used_emails = set()
    profiles = []

    # 3 premium demo users first (fixed)
    premiums = [
        ("Clara", "Deschamps", "clara.deschamps@demo-nlyt.fr", "+33612900001", "demo-conflit"),
        ("Victor", "Fontaine", "victor.fontaine@demo-nlyt.fr", "+33612900002", "demo-optimal"),
        ("Aurélie", "Marchand", "aurelie.marchand@demo-nlyt.fr", "+33612900003", "demo-penalite"),
    ]
    for p in premiums:
        profiles.append(p)
        used_emails.add(p[2])

    # Generate remaining users
    i = 0
    while len(profiles) < count:
        is_female = random.random() < 0.5
        first = random.choice(FIRST_NAMES_F if is_female else FIRST_NAMES_M)
        last = random.choice(LAST_NAMES)

        # Build unique email
        email_base = f"{first.lower().replace('é','e').replace('è','e').replace('ë','e').replace('ê','e').replace('ï','i').replace('î','i').replace('ô','o').replace('ü','u').replace('û','u').replace('ç','c').replace('à','a').replace('â','a')}.{last.lower().replace('è','e').replace('é','e').replace('ê','e').replace('ë','e').replace('ï','i').replace('î','i').replace('ô','o').replace('ü','u').replace('û','u').replace('ç','c').replace('à','a').replace('â','a')}"
        email = f"{email_base}@demo-nlyt.fr"
        if email in used_emails:
            email = f"{email_base}{random.randint(2,99)}@demo-nlyt.fr"
            if email in used_emails:
                continue
        used_emails.add(email)

        phone = f"+336{random.randint(10000000, 99999999)}"
        role = random.choice(ROLES)
        profiles.append((first, last, email, phone, role))
        i += 1

    return profiles


# ─── Create Users ───────────────────────────────────────────

def create_users(profiles):
    users = []
    for first, last, email, phone, role in profiles:
        user_id = uid()
        created = NOW - timedelta(days=random.randint(7, 180))
        users.append({
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
            "_demo_role": role,
        })
    db.users.insert_many(users)
    log.info(f"  {len(users)} utilisateurs créés")
    return users


# ─── Create Workspaces ──────────────────────────────────────

def create_workspaces(users):
    workspaces = []
    memberships = []
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
        memberships.append({
            **DEMO_MARKER,
            "membership_id": uid(),
            "workspace_id": ws_id,
            "user_id": u["user_id"],
            "role": "admin",
            "joined_at": u["created_at"],
        })
        u["_workspace_id"] = ws_id
    db.workspaces.insert_many(workspaces)
    db.workspace_memberships.insert_many(memberships)
    log.info(f"  {len(workspaces)} workspaces créés")


# ─── Calendar Connections ───────────────────────────────────

def create_calendar_connections(users):
    connections = []
    settings_list = []

    for u in users:
        role = u["_demo_role"]
        user_id = u["user_id"]
        conns = []

        force_google = role in ("coach", "manager", "demo-conflit", "demo-optimal", "formateur", "startup")
        force_outlook = role in ("CTO", "RH", "manager", "demo-conflit", "demo-penalite", "avocat", "notaire")

        if force_google or random.random() < 0.55:
            connections.append({
                **DEMO_MARKER,
                "connection_id": uid(),
                "provider": "google",
                "user_id": user_id,
                "status": "connected",
                "google_email": u["email"],
                "google_name": f"{u['first_name']} {u['last_name']}",
                "access_token": f"demo_gat_{user_id[:8]}",
                "refresh_token": f"demo_grt_{user_id[:8]}",
                "connected_at": iso(NOW - timedelta(days=random.randint(3, 90))),
                "updated_at": iso(NOW - timedelta(days=random.randint(0, 5))),
                "calendar_timezone": "Europe/Paris",
            })
            conns.append("google")

        if force_outlook or random.random() < 0.35:
            has_teams = role in ("CTO", "RH", "manager", "demo-conflit", "ops", "CEO")
            connections.append({
                **DEMO_MARKER,
                "connection_id": uid(),
                "provider": "outlook",
                "user_id": user_id,
                "status": "connected",
                "outlook_email": u["email"],
                "outlook_name": f"{u['first_name']} {u['last_name']}",
                "access_token": f"demo_oat_{user_id[:8]}",
                "refresh_token": f"demo_ort_{user_id[:8]}",
                "connected_at": iso(NOW - timedelta(days=random.randint(3, 90))),
                "updated_at": iso(NOW - timedelta(days=random.randint(0, 5))),
                "calendar_timezone": "Europe/Paris",
                "has_online_meetings_scope": has_teams,
                "scope_level": "teams_advanced" if has_teams else "calendar_base",
            })
            conns.append("outlook")

        setting = {**DEMO_MARKER, "user_id": user_id}
        if "google" in conns:
            setting["google_connected"] = True
        if "outlook" in conns:
            setting["teams_connected"] = True
            setting["teams_connected_at"] = iso(NOW - timedelta(days=random.randint(1, 30)))
        if role in ("freelance", "consultant", "commercial"):
            setting["zoom_connected"] = True
            setting["zoom_connected_at"] = iso(NOW - timedelta(days=random.randint(1, 30)))
            setting["zoom_email"] = u["email"]
        settings_list.append(setting)
        u["_conns"] = conns

    if connections:
        db.calendar_connections.insert_many(connections)
    if settings_list:
        db.user_settings.insert_many(settings_list)

    google_c = sum(1 for c in connections if c["provider"] == "google")
    outlook_c = sum(1 for c in connections if c["provider"] == "outlook")
    teams_c = sum(1 for c in connections if c.get("has_online_meetings_scope"))
    no_cal = sum(1 for u in users if not u.get("_conns"))
    log.info(f"  {len(connections)} connexions (Google:{google_c}, Outlook:{outlook_c}, Teams avancé:{teams_c}, sans calendrier:{no_cal})")


# ─── Appointments + Participants ────────────────────────────

def create_appointments(users):
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

    def pick_provider(org):
        conns = org.get("_conns", [])
        opts = []
        if "outlook" in conns:
            opts.append("Microsoft Teams")
        if "google" in conns:
            opts.append("Google Meet")
        opts += ["Zoom", "external"]
        return random.choice(opts)

    def pick_participants(org, count=None):
        if count is None:
            count = random.choices([1, 2, 3, 4, 5], weights=[25, 35, 25, 10, 5])[0]
        eligible = [u for u in users if u["user_id"] != org["user_id"]]
        return random.sample(eligible, min(count, len(eligible)))

    def make_snapshot(apt):
        snap_id = uid()
        all_snapshots.append({
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
                "penalty_currency": "eur",
            },
            "consent_language": {"fr": "En acceptant, je m'engage à respecter les conditions."},
            "created_at": apt["created_at"],
        })
        return snap_id

    def create_distribution_for_noshow(apt, participant, guarantee):
        dist_id = uid()
        capture = int(apt["penalty_amount"] * 100)
        plat_pct = apt["platform_commission_percent"]
        charity_pct = apt["charity_percent"]
        platform_cents = int(capture * plat_pct / 100)
        charity_cents = int(capture * charity_pct / 100)
        comp_cents = capture - platform_cents - charity_cents

        beneficiaries = []
        if platform_cents > 0:
            beneficiaries.append({
                "beneficiary_id": uid(), "wallet_id": "wallet_platform_demo",
                "user_id": "__nlyt_platform__", "role": "platform",
                "amount_cents": platform_cents, "status": "credited_available",
            })
            all_wallets_to_create.add("__nlyt_platform__")

        assoc_id = apt.get("charity_association_id")
        if charity_cents > 0 and assoc_id:
            beneficiaries.append({
                "beneficiary_id": uid(), "wallet_id": f"wallet_{assoc_id}",
                "user_id": assoc_id, "role": "charity",
                "amount_cents": charity_cents, "status": "credited_available",
            })

        if comp_cents > 0:
            beneficiaries.append({
                "beneficiary_id": uid(), "wallet_id": f"wallet_{apt['organizer_id'][:8]}",
                "user_id": apt["organizer_id"], "role": "organizer",
                "amount_cents": comp_cents, "status": "credited_available",
            })
            all_wallets_to_create.add(apt["organizer_id"])

        eval_at = apt.get("_eval_at", iso(NOW - timedelta(days=5)))
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
                "platform_commission_percent": plat_pct,
                "affected_compensation_percent": apt["affected_compensation_percent"],
                "charity_percent": charity_pct,
            },
            "beneficiaries": beneficiaries,
            "hold_expires_at": iso(NOW - timedelta(days=1)),
            "contested": False, "contested_at": None, "contested_by": None,
            "contest_reason": None, "captured_at": eval_at, "distributed_at": eval_at,
            "completed_at": eval_at, "cancelled_at": None, "cancel_reason": None,
            "created_at": eval_at, "updated_at": eval_at,
        }
        all_distributions.append(dist)
        for b in beneficiaries:
            all_wallet_txns.append({
                **DEMO_MARKER,
                "transaction_id": uid(), "wallet_id": b["wallet_id"],
                "type": "credit_available", "amount": b["amount_cents"],
                "currency": "eur", "reference_type": "distribution",
                "reference_id": dist_id,
                "description": f"Distribution — {apt['title']}",
                "created_at": eval_at,
            })

    def make_apt(org, title, start_dt, status, apt_type, provider, penalty,
                 charity_pct=0, assoc_id=None, assoc_name=None,
                 part_users=None, extra=None):
        apt_id = uid()
        loc = loc_disp = lat = lng = None
        if apt_type == "physical":
            l = random.choice(LOCATIONS)
            loc, loc_disp, lat, lng = l

        created = start_dt - timedelta(days=random.randint(2, 14))
        comp_pct = round(100 - 20 - charity_pct, 1)
        duration = random.choice([30, 45, 60, 90, 120])

        apt = {
            **DEMO_MARKER,
            "appointment_id": apt_id,
            "workspace_id": org["_workspace_id"],
            "organizer_id": org["user_id"],
            "title": title,
            "appointment_type": apt_type,
            "location": loc, "location_display_name": loc_disp,
            "location_geocoded": loc is not None,
            "location_latitude": lat, "location_longitude": lng,
            "meeting_provider": provider if apt_type == "video" else "",
            "start_datetime": iso(start_dt),
            "appointment_timezone": "Europe/Paris",
            "duration_minutes": duration,
            "tolerated_delay_minutes": random.choice([5, 10, 15, 20]),
            "cancellation_deadline_hours": random.choice([6, 12, 24, 48]),
            "penalty_amount": penalty,
            "penalty_currency": "eur",
            "affected_compensation_percent": comp_pct,
            "platform_commission_percent": 20.0,
            "charity_percent": charity_pct,
            "charity_association_id": assoc_id,
            "charity_association_name": assoc_name,
            "policy_template_id": None,
            "event_reminders": {"ten_minutes_before": True, "one_hour_before": True, "one_day_before": True},
            "event_reminders_sent": {},
            "status": status,
            "created_at": iso(created), "updated_at": iso(created),
        }
        if extra:
            apt.update(extra)
        apt["policy_snapshot_id"] = make_snapshot(apt)
        appointments.append(apt)

        # Participants
        p_users = part_users or pick_participants(org)
        for pu in p_users:
            p_id = uid()
            token = uid()
            if status == "active" and start_dt < NOW:
                p_status = random.choices(
                    ["accepted_guaranteed", "accepted_pending_guarantee", "cancelled_by_participant"],
                    weights=[55, 25, 20])[0]
            elif status == "active":
                p_status = random.choices(
                    ["accepted_guaranteed", "accepted_pending_guarantee", "invited"],
                    weights=[45, 30, 25])[0]
            elif status == "cancelled":
                p_status = random.choice(["invited", "accepted_pending_guarantee", "cancelled_by_participant"])
            else:
                p_status = "invited"

            part = {
                **DEMO_MARKER,
                "participant_id": p_id, "appointment_id": apt_id,
                "email": pu["email"], "first_name": pu["first_name"],
                "last_name": pu["last_name"], "name": "", "role": "participant",
                "status": p_status, "invitation_token": token,
                "user_id": pu.get("user_id"),
                "invited_at": iso(created), "created_at": iso(created),
                "updated_at": iso(created),
            }

            if p_status in ("accepted_guaranteed", "accepted_pending_guarantee"):
                part["accept_initiated_at"] = iso(created + timedelta(hours=random.randint(1, 48)))

            if p_status == "accepted_guaranteed":
                g_id = uid()
                part["guarantee_id"] = g_id
                part["guaranteed_at"] = iso(created + timedelta(hours=random.randint(2, 72)))
                g = {
                    **DEMO_MARKER,
                    "guarantee_id": g_id, "participant_id": p_id,
                    "appointment_id": apt_id, "invitation_token": token,
                    "stripe_customer_id": f"cus_demo_{p_id[:8]}",
                    "stripe_session_id": f"cs_demo_{g_id[:8]}",
                    "stripe_setup_intent_id": None,
                    "stripe_payment_method_id": f"pm_demo_{g_id[:8]}",
                    "penalty_amount": penalty, "penalty_currency": "eur",
                    "status": "completed", "dev_mode": True,
                    "created_at": part["accept_initiated_at"],
                    "updated_at": part["guaranteed_at"],
                    "completed_at": part["guaranteed_at"],
                }
                all_guarantees.append(g)
                part["_guarantee_doc"] = g

            all_participants.append(part)

        return apt

    # ─── CATEGORY 1: Future active (50) ───────────────────
    log.info("    Futurs actifs (50)...")
    for _ in range(50):
        org = random.choice(organizers)
        t = random.choice(APPOINTMENT_TITLES)
        s = random_future(1, 40)
        at = random.choices(["video", "physical"], weights=[70, 30])[0]
        prov = pick_provider(org) if at == "video" else ""
        pen = random.choice([10, 15, 20, 25, 30, 40, 50, 75, 100])
        cp = random.choices([0, 0, 0, 5, 10, 15, 20, 25, 30], weights=[30, 10, 5, 5, 15, 15, 10, 5, 5])[0]
        a = random.choice(CHARITY_ASSOCIATIONS) if cp > 0 else (None, None)
        make_apt(org, t, s, "active", at, prov, pen, cp, a[0], a[1])

    # ─── CATEGORY 2: Past evaluated (60) ──────────────────
    log.info("    Passés évalués (60)...")
    for _ in range(60):
        org = random.choice(organizers)
        t = random.choice(APPOINTMENT_TITLES)
        s = random_past(2, 75)
        at = random.choices(["video", "physical"], weights=[70, 30])[0]
        prov = pick_provider(org) if at == "video" else ""
        pen = random.choice([15, 20, 25, 30, 50, 75, 100])
        cp = random.choices([0, 0, 10, 15, 20, 25], weights=[35, 20, 15, 15, 10, 5])[0]
        a = random.choice(CHARITY_ASSOCIATIONS) if cp > 0 else (None, None)

        apt = make_apt(org, t, s, "active", at, prov, pen, cp, a[0], a[1],
                       extra={"attendance_evaluated": True,
                              "attendance_evaluated_at": iso(s + timedelta(hours=2))})
        apt["_eval_at"] = iso(s + timedelta(hours=2))

        # Attendance
        parts = [p for p in all_participants
                 if p["appointment_id"] == apt["appointment_id"]
                 and p["status"] == "accepted_guaranteed"]
        summary = {"on_time": 0, "late": 0, "no_show": 0, "waived": 0, "manual_review": 0}
        for p in parts:
            outcome = random.choices(["on_time", "late", "no_show"], weights=[60, 25, 15])[0]
            summary[outcome] += 1
            all_attendance.append({
                **DEMO_MARKER,
                "record_id": uid(), "appointment_id": apt["appointment_id"],
                "participant_id": p["participant_id"],
                "participant_email": p["email"],
                "participant_name": f"{p['first_name']} {p['last_name']}",
                "outcome": outcome, "confidence": "high",
                "decided_at": iso(s + timedelta(hours=1, minutes=30)),
                "decided_by": org["user_id"],
                "decision_basis": random.choice(["organizer_manual", "auto_video", "auto_checkin"]),
                "auto_capture_enabled": outcome == "no_show",
                "review_required": False,
            })
            if outcome == "no_show" and p.get("_guarantee_doc"):
                create_distribution_for_noshow(apt, p, p["_guarantee_doc"])

        apt["attendance_summary"] = summary

    # ─── CATEGORY 3: Cancelled (15) ──────────────────────
    log.info("    Annulés (15)...")
    for _ in range(15):
        org = random.choice(organizers)
        t = random.choice(APPOINTMENT_TITLES)
        s = random_future(2, 25)
        cancel_dt = NOW - timedelta(days=random.randint(0, 7))
        at = random.choices(["video", "physical"], weights=[70, 30])[0]
        prov = pick_provider(org) if at == "video" else ""
        pen = random.choice([20, 30, 50])
        make_apt(org, t, s, "cancelled", at, prov, pen,
                 extra={"cancelled_at": iso(cancel_dt),
                        "cancelled_by": random.choice([org["user_id"], "participant"])})

    # ─── CATEGORY 4: Pending organizer guarantee (8) ─────
    log.info("    En attente de garantie organisateur (8)...")
    for _ in range(8):
        org = random.choice(organizers)
        t = random.choice(APPOINTMENT_TITLES)
        s = random_future(5, 25)
        at = "video"
        prov = pick_provider(org)
        pen = random.choice([25, 50, 75, 100])
        make_apt(org, t, s, "pending_organizer_guarantee", at, prov, pen)

    # ─── PREMIUM 1: Clara — Conflit clair ────────────────
    log.info("    Premium: Clara (conflit)...")
    clara = next(u for u in users if u["_demo_role"] == "demo-conflit")
    ct = random_future(3, 7).replace(hour=14, minute=0)
    make_apt(clara, "Coaching client VIP — session mensuelle", ct,
             "active", "video", "Microsoft Teams", 75, 15,
             "assoc_croix_rouge", "Croix-Rouge française")
    make_apt(clara, "Point hebdomadaire équipe projet", ct + timedelta(minutes=15),
             "active", "video", "Google Meet", 50, 10,
             "assoc_restos_coeur", "Les Restos du Cœur")

    # ─── PREMIUM 2: Victor — Créneau optimal ────────────
    log.info("    Premium: Victor (suggestion optimale)...")
    victor = next(u for u in users if u["_demo_role"] == "demo-optimal")
    vt = random_future(4, 8).replace(hour=10, minute=0)
    make_apt(victor, "Stand-up daily engineering", vt,
             "active", "video", "Google Meet", 30)
    make_apt(victor, "Démo produit pour investisseur", vt.replace(hour=14),
             "active", "video", "Zoom", 100, 20,
             "assoc_unicef", "UNICEF France")

    # ─── PREMIUM 3: Aurélie — Pénalité appliquée ────────
    log.info("    Premium: Aurélie (pénalité)...")
    aurelie = next(u for u in users if u["_demo_role"] == "demo-penalite")
    pt = random_past(5, 15)
    apt_p = make_apt(aurelie, "Consultation stratégique — client premium", pt,
                     "active", "video", "Microsoft Teams", 100, 25,
                     "assoc_medecins_sans_frontieres", "Médecins Sans Frontières",
                     extra={"attendance_evaluated": True,
                            "attendance_evaluated_at": iso(pt + timedelta(hours=2))})
    apt_p["_eval_at"] = iso(pt + timedelta(hours=2))
    ns_parts = [p for p in all_participants
                if p["appointment_id"] == apt_p["appointment_id"]
                and p["status"] == "accepted_guaranteed"]
    if ns_parts:
        ns = ns_parts[0]
        all_attendance.append({
            **DEMO_MARKER,
            "record_id": uid(), "appointment_id": apt_p["appointment_id"],
            "participant_id": ns["participant_id"],
            "participant_email": ns["email"],
            "participant_name": f"{ns['first_name']} {ns['last_name']}",
            "outcome": "no_show", "confidence": "high",
            "decided_at": iso(pt + timedelta(hours=1, minutes=30)),
            "decided_by": aurelie["user_id"],
            "decision_basis": "organizer_manual",
            "auto_capture_enabled": True, "review_required": False,
        })
        if ns.get("_guarantee_doc"):
            create_distribution_for_noshow(apt_p, ns, ns["_guarantee_doc"])
        apt_p["attendance_summary"] = {"on_time": max(0, len(ns_parts) - 1), "late": 0, "no_show": 1, "waived": 0, "manual_review": 0}

    # ─── CATEGORY 5: Buffer warning (4) ─────────────────
    log.info("    Buffer warning (4)...")
    for _ in range(2):
        borg = random.choice(organizers)
        bt = random_future(4, 12).replace(hour=15, minute=0)
        make_apt(borg, "Formation continue — module avancé", bt,
                 "active", "video", pick_provider(borg), 50)
        make_apt(borg, "Débrief formation avec RH", bt + timedelta(minutes=50),
                 "active", "video", pick_provider(borg), 30)

    # ─── INSERT ──────────────────────────────────────────
    for p in all_participants:
        p.pop("_guarantee_doc", None)

    if appointments:
        db.appointments.insert_many(appointments)
    if all_participants:
        db.participants.insert_many(all_participants)
    if all_guarantees:
        db.payment_guarantees.insert_many(all_guarantees)
    if all_snapshots:
        db.policy_snapshots.insert_many(all_snapshots)
    if all_attendance:
        db.attendance_records.insert_many(all_attendance)
    if all_distributions:
        db.distributions.insert_many(all_distributions)

    log.info(f"  {len(appointments)} rendez-vous")
    log.info(f"  {len(all_participants)} participants")
    log.info(f"  {len(all_guarantees)} garanties")
    log.info(f"  {len(all_attendance)} records de présence")
    log.info(f"  {len(all_distributions)} distributions")

    return appointments, all_wallets_to_create, all_wallet_txns


# ─── Wallets ────────────────────────────────────────────────

def create_wallets(users, wallets_needed, wallet_txns):
    wallets = []
    txn_by_wallet = {}
    for tx in wallet_txns:
        txn_by_wallet.setdefault(tx["wallet_id"], []).append(tx)

    if "__nlyt_platform__" in wallets_needed:
        total = sum(tx["amount"] for tx in txn_by_wallet.get("wallet_platform_demo", []))
        wallets.append({
            **DEMO_MARKER,
            "wallet_id": "wallet_platform_demo", "user_id": "__nlyt_platform__",
            "wallet_type": "platform", "available_balance": total, "pending_balance": 0,
            "currency": "eur", "total_received": total, "total_withdrawn": 0,
            "created_at": iso(NOW - timedelta(days=90)), "updated_at": iso(NOW),
        })

    for u in users:
        w_id = f"wallet_{u['user_id'][:8]}"
        total = sum(tx["amount"] for tx in txn_by_wallet.get(w_id, []))
        connect_active = random.random() < 0.65
        wallets.append({
            **DEMO_MARKER,
            "wallet_id": w_id, "user_id": u["user_id"],
            "wallet_type": "user", "available_balance": total, "pending_balance": 0,
            "currency": "eur",
            "stripe_connect_account_id": f"acct_demo_{u['user_id'][:8]}",
            "stripe_connect_status": "active" if connect_active else "not_started",
            "total_received": total, "total_withdrawn": 0,
            "created_at": u["created_at"], "updated_at": iso(NOW),
        })

    if wallets:
        db.wallets.insert_many(wallets)
    if wallet_txns:
        db.wallet_transactions.insert_many(wallet_txns)
    log.info(f"  {len(wallets)} wallets, {len(wallet_txns)} transactions")


# ─── Main ───────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("NLYT Demo Seed V2 — 100+ utilisateurs")
    log.info("=" * 60)

    log.info("\n[1/7] Nettoyage...")
    cleanup()

    log.info("\n[2/7] Utilisateurs...")
    profiles = generate_user_profiles(105)
    users = create_users(profiles)

    log.info("\n[3/7] Workspaces...")
    create_workspaces(users)

    log.info("\n[4/7] Connexions calendrier...")
    create_calendar_connections(users)

    log.info("\n[5/7] Rendez-vous + participants + présence + distributions...")
    apts, wallets_needed, wallet_txns = create_appointments(users)

    log.info("\n[6/7] Wallets...")
    create_wallets(users, wallets_needed, wallet_txns)

    log.info("\n[7/7] Refresh stats impact...")
    from services.distribution_service import refresh_impact_stats
    stats = refresh_impact_stats()
    log.info(f"  Impact: {stats['total_charity_cents']/100:.0f}€ fléchés, "
             f"{len(stats['associations'])} associations, "
             f"{stats['distributions_count']} distributions")

    log.info("\n" + "=" * 60)
    log.info("SEED TERMINÉ")
    log.info(f"  Mot de passe : {DEMO_PASSWORD}")
    log.info(f"  Utilisateurs : {len(users)}")
    log.info(f"  Premium :")
    log.info(f"    clara.deschamps@demo-nlyt.fr   (conflit)")
    log.info(f"    victor.fontaine@demo-nlyt.fr    (suggestion)")
    log.info(f"    aurelie.marchand@demo-nlyt.fr   (pénalité)")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
