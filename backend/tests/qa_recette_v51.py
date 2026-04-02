"""
═══════════════════════════════════════════════════════════════════
RECETTE QA V5.1 — TEST COMPLET DU MOTEUR DÉCLARATIF
═══════════════════════════════════════════════════════════════════
Scénarios couverts:
  A. Cas fondamentaux (configurations de garanties)
  B. Cas comportementaux (déclarations, absences, contradictions)
  C. Cas spécifiques V5.1 (auto-waive des non-garantis)
  D. Cas extrêmes / edge cases (double init, données partielles, etc.)
"""
import sys, os, uuid, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import db
from services.declarative_service import (
    initialize_declarative_phase,
    submit_sheet,
    _run_analysis,
    open_dispute,
)
from utils.date_utils import now_utc
from datetime import timedelta

# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

RESULTS = []
ORG_USER_ID = "qa-org-" + str(uuid.uuid4())[:8]
USER_IDS = ["qa-user-" + str(uuid.uuid4())[:8] for _ in range(6)]

def _uid(i):
    return USER_IDS[i] if i < len(USER_IDS) else "qa-user-" + str(uuid.uuid4())[:8]

def _cleanup():
    """Remove all QA test data."""
    for col in ["appointments", "participants", "attendance_records",
                 "attendance_sheets", "declarative_analyses",
                 "declarative_disputes", "distributions",
                 "payment_guarantees", "user_notifications"]:
        db[col].delete_many({"appointment_id": {"$regex": "^qa-"}})

def _create_scenario(title, participants_config, create_records=True):
    """
    Create a test appointment with participants and attendance_records.
    participants_config: list of dicts with keys:
      - status: 'accepted_guaranteed', 'accepted_pending_guarantee', 'accepted', etc.
      - outcome: 'manual_review', 'on_time', 'no_show', etc. (for attendance_record)
      - user_id: (optional) override user_id
      - is_organizer: (optional) True for organizer participant
    Returns (appointment_id, list of participant_ids)
    """
    apt_id = "qa-" + str(uuid.uuid4())[:12]
    now = now_utc()

    db.appointments.insert_one({
        "appointment_id": apt_id,
        "title": title,
        "organizer_id": ORG_USER_ID,
        "status": "active",
        "start_datetime": (now - timedelta(hours=2)).isoformat(),
        "end_datetime": (now - timedelta(hours=1)).isoformat(),
        "appointment_type": "physical",
        "location": "QA Test Location",
        "duration_minutes": 60,
        "guarantee_amount": 50,
        "penalty_amount": 50,
        "penalty_currency": "EUR",
    })

    pids = []
    for i, cfg in enumerate(participants_config):
        pid = f"qa-p-{apt_id[-8:]}-{i}"
        uid = cfg.get("user_id", _uid(i))
        is_org = cfg.get("is_organizer", False)

        db.participants.insert_one({
            "participant_id": pid,
            "appointment_id": apt_id,
            "user_id": uid,
            "email": f"qa-{i}@test.com",
            "status": cfg["status"],
            "is_organizer": is_org,
        })

        if create_records and cfg.get("outcome"):
            review = cfg["outcome"] == "manual_review"
            db.attendance_records.insert_one({
                "record_id": str(uuid.uuid4()),
                "appointment_id": apt_id,
                "participant_id": pid,
                "outcome": cfg["outcome"],
                "review_required": review,
                "confidence_level": "LOW" if review else "HIGH",
                "decided_by": "tech_engine" if not review else None,
            })

        pids.append(pid)

    return apt_id, pids


def _get_state(apt_id):
    """Get full state for an appointment after engine run."""
    apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
    records = list(db.attendance_records.find({"appointment_id": apt_id}, {"_id": 0}))
    sheets = list(db.attendance_sheets.find({"appointment_id": apt_id}, {"_id": 0}))
    disputes = list(db.declarative_disputes.find({"appointment_id": apt_id}, {"_id": 0}))
    analyses = list(db.declarative_analyses.find({"appointment_id": apt_id}, {"_id": 0}))
    return {
        "phase": apt.get("declarative_phase") if apt else None,
        "records": records,
        "sheets": sheets,
        "disputes": disputes,
        "analyses": analyses,
        "records_by_outcome": {},
    }


def _record_result(scenario_id, title, category, passed, details, severity="N/A"):
    status = "OK" if passed else "KO"
    RESULTS.append({
        "id": scenario_id,
        "title": title,
        "category": category,
        "status": status,
        "details": details,
        "severity": severity if not passed else "N/A",
    })
    icon = "✅" if passed else "❌"
    print(f"  {icon} {scenario_id}: {title} → {status}")
    if not passed:
        print(f"     ⚠️  {details}")


# ═══════════════════════════════════════════════════════════════
# A. CAS FONDAMENTAUX — Configurations de garanties
# ═══════════════════════════════════════════════════════════════

def test_A1_org_guaranteed_participant_guaranteed():
    """A1: 1 org garanti + 1 participant garanti → feuilles créées, phase collecting."""
    apt_id, pids = _create_scenario("A1: Org+Part garantis", [
        {"status": "accepted_guaranteed", "outcome": "manual_review", "is_organizer": True, "user_id": ORG_USER_ID},
        {"status": "accepted_guaranteed", "outcome": "manual_review"},
    ])
    initialize_declarative_phase(apt_id)
    s = _get_state(apt_id)

    checks = []
    checks.append(("phase == collecting", s["phase"] == "collecting"))
    checks.append(("sheets créées", len(s["sheets"]) >= 1))
    checks.append(("tous les records toujours manual_review",
                    all(r["outcome"] == "manual_review" for r in s["records"])))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("A1", "Org garanti + Part garanti", "Fondamental", all_ok, details)
    return apt_id, pids


def test_A2_org_guaranteed_participant_not_guaranteed():
    """A2: 1 org garanti + 1 participant non-garanti → non-garanti waived, phase not_needed."""
    apt_id, pids = _create_scenario("A2: Org garanti + Part non-garanti", [
        {"status": "accepted_guaranteed", "outcome": "manual_review", "is_organizer": True, "user_id": ORG_USER_ID},
        {"status": "accepted_pending_guarantee", "outcome": "manual_review"},
    ])
    initialize_declarative_phase(apt_id)
    s = _get_state(apt_id)

    non_g_record = next((r for r in s["records"] if r["participant_id"] == pids[1]), None)
    checks = []
    checks.append(("phase == not_needed", s["phase"] == "not_needed"))
    checks.append(("0 sheets", len(s["sheets"]) == 0))
    checks.append(("non-garanti waived", non_g_record and non_g_record["outcome"] == "waived"))
    checks.append(("decision_source correct",
                    non_g_record and non_g_record.get("decision_source") == "non_guaranteed_auto_waived"))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("A2", "Org garanti + Part non-garanti", "Fondamental", all_ok, details)


def test_A3_org_not_guaranteed_participant_guaranteed():
    """A3: 1 org non-garanti + 1 participant garanti → 1 garanti seul, not_needed."""
    apt_id, pids = _create_scenario("A3: Org non-garanti + Part garanti", [
        {"status": "accepted", "outcome": "manual_review", "is_organizer": True, "user_id": ORG_USER_ID},
        {"status": "accepted_guaranteed", "outcome": "manual_review"},
    ])
    initialize_declarative_phase(apt_id)
    s = _get_state(apt_id)

    org_record = next((r for r in s["records"] if r["participant_id"] == pids[0]), None)
    checks = []
    checks.append(("phase == not_needed", s["phase"] == "not_needed"))
    checks.append(("0 sheets", len(s["sheets"]) == 0))
    checks.append(("org waived", org_record and org_record["outcome"] == "waived"))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("A3", "Org non-garanti + Part garanti", "Fondamental", all_ok, details)


def test_A4_zero_guaranteed():
    """A4: 0 garanti (tous accepted ou pending) → tous waived, not_needed."""
    apt_id, pids = _create_scenario("A4: 0 garanti", [
        {"status": "accepted", "outcome": "manual_review", "is_organizer": True, "user_id": ORG_USER_ID},
        {"status": "accepted_pending_guarantee", "outcome": "manual_review"},
        {"status": "accepted", "outcome": "manual_review"},
    ])
    initialize_declarative_phase(apt_id)
    s = _get_state(apt_id)

    waived_count = sum(1 for r in s["records"] if r["outcome"] == "waived")
    checks = []
    checks.append(("phase == not_needed", s["phase"] == "not_needed"))
    checks.append(("0 sheets", len(s["sheets"]) == 0))
    checks.append(("tous waived", waived_count == 3))
    checks.append(("0 disputes", len(s["disputes"]) == 0))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("A4", "0 garanti", "Fondamental", all_ok, details)


def test_A5_3_participants_2_guaranteed():
    """A5: 3 participants dont 2 garantis → feuilles pour 2, 1 waived."""
    apt_id, pids = _create_scenario("A5: 3 part, 2 garantis", [
        {"status": "accepted_guaranteed", "outcome": "manual_review", "is_organizer": True, "user_id": ORG_USER_ID},
        {"status": "accepted_guaranteed", "outcome": "manual_review"},
        {"status": "accepted_pending_guarantee", "outcome": "manual_review"},
    ])
    initialize_declarative_phase(apt_id)
    s = _get_state(apt_id)

    non_g_record = next((r for r in s["records"] if r["participant_id"] == pids[2]), None)
    checks = []
    checks.append(("phase == collecting", s["phase"] == "collecting"))
    checks.append(("sheets >= 1", len(s["sheets"]) >= 1))
    checks.append(("non-garanti waived", non_g_record and non_g_record["outcome"] == "waived"))
    # Check non-garanti is NOT a target in any sheet
    is_target = False
    for sheet in s["sheets"]:
        for d in sheet.get("declarations", []):
            if d["target_participant_id"] == pids[2]:
                is_target = True
    checks.append(("non-garanti PAS cible", not is_target))
    # Check non-garanti has no own sheet
    has_own = any(sh["submitted_by_participant_id"] == pids[2] for sh in s["sheets"]
                  if "submitted_by_participant_id" in sh)
    checks.append(("non-garanti PAS auteur", not has_own))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("A5", "3 part, 2 garantis", "Fondamental", all_ok, details)


def test_A6_3_participants_1_guaranteed():
    """A6: 3 participants dont 1 seul garanti → not_needed, 2 waived."""
    apt_id, pids = _create_scenario("A6: 3 part, 1 garanti", [
        {"status": "accepted_guaranteed", "outcome": "manual_review", "is_organizer": True, "user_id": ORG_USER_ID},
        {"status": "accepted_pending_guarantee", "outcome": "manual_review"},
        {"status": "accepted", "outcome": "manual_review"},
    ])
    initialize_declarative_phase(apt_id)
    s = _get_state(apt_id)

    waived_count = sum(1 for r in s["records"]
                       if r["outcome"] == "waived" and r.get("decision_source") == "non_guaranteed_auto_waived")
    checks = []
    checks.append(("phase == not_needed", s["phase"] == "not_needed"))
    checks.append(("0 sheets", len(s["sheets"]) == 0))
    checks.append(("2 non-garantis waived", waived_count == 2))
    checks.append(("0 disputes", len(s["disputes"]) == 0))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("A6", "3 part, 1 seul garanti", "Fondamental", all_ok, details)


def test_A7_all_guaranteed():
    """A7: Tous garantis (4 participants) → feuilles pour tous."""
    apt_id, pids = _create_scenario("A7: Tous garantis", [
        {"status": "accepted_guaranteed", "outcome": "manual_review", "is_organizer": True, "user_id": ORG_USER_ID},
        {"status": "accepted_guaranteed", "outcome": "manual_review"},
        {"status": "accepted_guaranteed", "outcome": "manual_review"},
        {"status": "accepted_guaranteed", "outcome": "manual_review"},
    ])
    initialize_declarative_phase(apt_id)
    s = _get_state(apt_id)

    checks = []
    checks.append(("phase == collecting", s["phase"] == "collecting"))
    checks.append(("sheets == 4", len(s["sheets"]) == 4))
    checks.append(("0 waived", sum(1 for r in s["records"] if r["outcome"] == "waived") == 0))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("A7", "Tous garantis (4)", "Fondamental", all_ok, details)
    return apt_id, pids


def test_A8_none_guaranteed():
    """A8: Aucun garanti (3 participants) → tous waived, not_needed."""
    apt_id, pids = _create_scenario("A8: Aucun garanti", [
        {"status": "accepted", "outcome": "manual_review", "is_organizer": True, "user_id": ORG_USER_ID},
        {"status": "accepted_pending_guarantee", "outcome": "manual_review"},
        {"status": "accepted_pending_guarantee", "outcome": "manual_review"},
    ])
    initialize_declarative_phase(apt_id)
    s = _get_state(apt_id)

    waived = sum(1 for r in s["records"] if r["outcome"] == "waived")
    checks = []
    checks.append(("phase == not_needed", s["phase"] == "not_needed"))
    checks.append(("tous waived (3)", waived == 3))
    checks.append(("0 sheets", len(s["sheets"]) == 0))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("A8", "Aucun garanti (3)", "Fondamental", all_ok, details)


# ═══════════════════════════════════════════════════════════════
# B. CAS COMPORTEMENTAUX — Déclarations et analyse
# ═══════════════════════════════════════════════════════════════

def _create_and_init_guaranteed_scenario(title, n_participants):
    """Helper: create N guaranteed participants + org, init phase, return (apt_id, pids, sheets)."""
    configs = [{"status": "accepted_guaranteed", "outcome": "manual_review",
                "is_organizer": True, "user_id": ORG_USER_ID}]
    for i in range(n_participants - 1):
        configs.append({"status": "accepted_guaranteed", "outcome": "manual_review"})
    apt_id, pids = _create_scenario(title, configs)
    initialize_declarative_phase(apt_id)
    sheets = list(db.attendance_sheets.find({"appointment_id": apt_id}, {"_id": 0}))
    return apt_id, pids, sheets


def _submit_all_sheets(apt_id, sheets, status_map):
    """Submit all sheets. status_map: {target_pid: declared_status} (applied to all sheets)."""
    for sheet in sheets:
        decls = []
        for d in sheet["declarations"]:
            tid = d["target_participant_id"]
            decls.append({
                "target_participant_id": tid,
                "declared_status": status_map.get(tid, "unknown"),
            })
        submit_sheet(apt_id, sheet["submitted_by_user_id"], decls)


def test_B1_everyone_present():
    """B1: Tout le monde déclare tout le monde présent → auto-resolve on_time."""
    apt_id, pids, sheets = _create_and_init_guaranteed_scenario("B1: Tous présents", 2)
    status_map = {pid: "present_on_time" for pid in pids}
    _submit_all_sheets(apt_id, sheets, status_map)
    s = _get_state(apt_id)

    on_time = sum(1 for r in s["records"] if r["outcome"] == "on_time")
    checks = []
    checks.append(("phase == resolved", s["phase"] == "resolved"))
    checks.append(("records on_time", on_time == 2))
    checks.append(("0 disputes", len(s["disputes"]) == 0))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("B1", "Tous présents → on_time", "Comportemental", all_ok, details)


def test_B2_one_absent():
    """B2: 1 absent signalé (petit groupe) → dispute."""
    apt_id, pids, sheets = _create_and_init_guaranteed_scenario("B2: 1 absent", 2)
    status_map = {pids[0]: "present_on_time", pids[1]: "absent"}
    _submit_all_sheets(apt_id, sheets, status_map)
    s = _get_state(apt_id)

    checks = []
    checks.append(("phase == disputed", s["phase"] == "disputed"))
    checks.append(("disputes >= 1", len(s["disputes"]) >= 1))
    # The dispute should target pids[1] (the one declared absent)
    dispute_targets = [d.get("target_participant_id") for d in s["disputes"]]
    checks.append(("dispute cible le bon PID", pids[1] in dispute_targets))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("B2", "1 absent → dispute", "Comportemental", all_ok, details)


def test_B3_multiple_absent():
    """B3: Plusieurs absents signalés (large group) → disputes multiples."""
    apt_id, pids, sheets = _create_and_init_guaranteed_scenario("B3: Plusieurs absents", 4)
    # Declare pids[1] and pids[2] absent by everyone
    status_map = {pids[0]: "present_on_time", pids[1]: "absent",
                  pids[2]: "absent", pids[3]: "present_on_time"}
    _submit_all_sheets(apt_id, sheets, status_map)
    s = _get_state(apt_id)

    checks = []
    checks.append(("phase == disputed ou resolved", s["phase"] in ("disputed", "resolved")))
    dispute_targets = {d.get("target_participant_id") for d in s["disputes"]}
    # At least pids[1] and pids[2] should have disputes or be resolved
    checks.append(("disputes ou résolutions pour absents", len(s["disputes"]) >= 1 or s["phase"] == "resolved"))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("B3", "Plusieurs absents", "Comportemental", all_ok, details)


def test_B4_all_absent():
    """B4: Tout le monde déclaré absent → disputes pour tous."""
    apt_id, pids, sheets = _create_and_init_guaranteed_scenario("B4: Tous absents", 2)
    status_map = {pid: "absent" for pid in pids}
    _submit_all_sheets(apt_id, sheets, status_map)
    s = _get_state(apt_id)

    checks = []
    checks.append(("phase == disputed", s["phase"] == "disputed"))
    checks.append(("disputes créées", len(s["disputes"]) >= 1))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("B4", "Tous absents → disputes", "Comportemental", all_ok, details)


def test_B5_coherent_declarations():
    """B5: Déclarations 100% cohérentes (large group) → auto-resolve."""
    apt_id, pids, sheets = _create_and_init_guaranteed_scenario("B5: Déclarations cohérentes", 4)
    status_map = {pid: "present_on_time" for pid in pids}
    _submit_all_sheets(apt_id, sheets, status_map)
    s = _get_state(apt_id)

    on_time = sum(1 for r in s["records"] if r["outcome"] == "on_time")
    checks = []
    checks.append(("phase == resolved", s["phase"] == "resolved"))
    checks.append(("tous on_time (4)", on_time == 4))
    checks.append(("0 disputes", len(s["disputes"]) == 0))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("B5", "Déclarations cohérentes (4) → resolved", "Comportemental", all_ok, details)


def test_B6_contradictory_declarations():
    """B6: Déclarations 100% contradictoires entre garantis → disputes."""
    apt_id, pids, sheets = _create_and_init_guaranteed_scenario("B6: Contradictions", 2)
    # Each person says the other is absent (but self is present)
    for sheet in sheets:
        decls = []
        for d in sheet["declarations"]:
            tid = d["target_participant_id"]
            if d.get("is_self_declaration"):
                decls.append({"target_participant_id": tid, "declared_status": "present_on_time"})
            else:
                decls.append({"target_participant_id": tid, "declared_status": "absent"})
        submit_sheet(apt_id, sheet["submitted_by_user_id"], decls)

    s = _get_state(apt_id)
    checks = []
    checks.append(("phase == disputed", s["phase"] == "disputed"))
    checks.append(("disputes >= 1", len(s["disputes"]) >= 1))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("B6", "Contradictions → disputes", "Comportemental", all_ok, details)


def test_B7_nobody_fills_sheet():
    """B7: Personne ne remplit la feuille → sheets restent pending, phase collecting."""
    apt_id, pids, sheets = _create_and_init_guaranteed_scenario("B7: Aucune soumission", 2)
    # Don't submit anything
    s = _get_state(apt_id)

    pending = sum(1 for sh in s["sheets"] if sh["status"] == "pending")
    checks = []
    checks.append(("phase == collecting", s["phase"] == "collecting"))
    checks.append(("sheets toutes pending", pending == len(s["sheets"])))
    checks.append(("0 disputes", len(s["disputes"]) == 0))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("B7", "Personne ne remplit → collecting", "Comportemental", all_ok, details)


def test_B8_all_unknown():
    """B8: Tous déclarent 'unknown' → waived (présomption V5)."""
    apt_id, pids, sheets = _create_and_init_guaranteed_scenario("B8: Tous unknown", 2)
    status_map = {pid: "unknown" for pid in pids}
    _submit_all_sheets(apt_id, sheets, status_map)
    s = _get_state(apt_id)

    waived = sum(1 for r in s["records"] if r["outcome"] == "waived")
    checks = []
    checks.append(("phase == resolved", s["phase"] == "resolved"))
    checks.append(("tous waived", waived == 2))
    checks.append(("0 disputes", len(s["disputes"]) == 0))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("B8", "Tous unknown → waived (V5 presumption)", "Comportemental", all_ok, details)


# ═══════════════════════════════════════════════════════════════
# C. CAS SPÉCIFIQUES V5.1 — Auto-waive des non-garantis
# ═══════════════════════════════════════════════════════════════

def test_C1_non_guaranteed_no_sheet():
    """C1: Vérifier qu'un non-garanti waived n'a PAS de pending sheet."""
    apt_id, pids = _create_scenario("C1: Non-garanti sans sheet", [
        {"status": "accepted_guaranteed", "outcome": "manual_review", "is_organizer": True, "user_id": ORG_USER_ID},
        {"status": "accepted_guaranteed", "outcome": "manual_review"},
        {"status": "accepted_pending_guarantee", "outcome": "manual_review"},
    ])
    initialize_declarative_phase(apt_id)
    s = _get_state(apt_id)

    non_g_pid = pids[2]
    has_sheet = any(sh.get("submitted_by_participant_id") == non_g_pid for sh in s["sheets"])
    checks = []
    checks.append(("non-garanti n'a PAS de sheet", not has_sheet))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("C1", "Non-garanti PAS de pending sheet", "V5.1", all_ok, details)


def test_C2_non_guaranteed_not_target():
    """C2: Vérifier qu'un non-garanti waived n'est PAS cible dans les feuilles."""
    apt_id, pids = _create_scenario("C2: Non-garanti pas cible", [
        {"status": "accepted_guaranteed", "outcome": "manual_review", "is_organizer": True, "user_id": ORG_USER_ID},
        {"status": "accepted_guaranteed", "outcome": "manual_review"},
        {"status": "accepted", "outcome": "manual_review"},
    ])
    initialize_declarative_phase(apt_id)
    s = _get_state(apt_id)

    non_g_pid = pids[2]
    is_target = False
    for sh in s["sheets"]:
        for d in sh.get("declarations", []):
            if d["target_participant_id"] == non_g_pid:
                is_target = True

    checks = []
    checks.append(("non-garanti PAS cible", not is_target))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("C2", "Non-garanti PAS cible dans sheets", "V5.1", all_ok, details)


def test_C3_non_guaranteed_no_dispute():
    """C3: Vérifier qu'un non-garanti waived ne génère PAS de dispute même après analyse."""
    apt_id, pids = _create_scenario("C3: Non-garanti pas de dispute", [
        {"status": "accepted_guaranteed", "outcome": "manual_review", "is_organizer": True, "user_id": ORG_USER_ID},
        {"status": "accepted_guaranteed", "outcome": "manual_review"},
        {"status": "accepted_pending_guarantee", "outcome": "manual_review"},
    ])
    initialize_declarative_phase(apt_id)

    # Submit sheets with everyone present
    sheets = list(db.attendance_sheets.find({"appointment_id": apt_id}, {"_id": 0}))
    for sh in sheets:
        decls = [{"target_participant_id": d["target_participant_id"],
                  "declared_status": "present_on_time"} for d in sh["declarations"]]
        submit_sheet(apt_id, sh["submitted_by_user_id"], decls)

    s = _get_state(apt_id)
    non_g_pid = pids[2]
    dispute_targets = [d.get("target_participant_id") for d in s["disputes"]]

    checks = []
    checks.append(("non-garanti PAS dans disputes", non_g_pid not in dispute_targets))
    checks.append(("non-garanti toujours waived",
                    any(r["participant_id"] == non_g_pid and r["outcome"] == "waived" for r in s["records"])))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("C3", "Non-garanti PAS de dispute après analyse", "V5.1", all_ok, details)


def test_C4_non_guaranteed_waived_fields():
    """C4: Vérifier les champs exacts du record auto-waived."""
    apt_id, pids = _create_scenario("C4: Champs waived", [
        {"status": "accepted_guaranteed", "outcome": "manual_review", "is_organizer": True, "user_id": ORG_USER_ID},
        {"status": "accepted_guaranteed", "outcome": "manual_review"},
        {"status": "accepted", "outcome": "manual_review"},
    ])
    initialize_declarative_phase(apt_id)

    rec = db.attendance_records.find_one(
        {"appointment_id": apt_id, "participant_id": pids[2]}, {"_id": 0}
    )
    checks = []
    checks.append(("outcome == waived", rec and rec["outcome"] == "waived"))
    checks.append(("review_required == False", rec and rec.get("review_required") is False))
    checks.append(("decision_source == non_guaranteed_auto_waived",
                    rec and rec.get("decision_source") == "non_guaranteed_auto_waived"))
    checks.append(("confidence_level == HIGH", rec and rec.get("confidence_level") == "HIGH"))
    checks.append(("decided_by == engine_guard", rec and rec.get("decided_by") == "engine_guard"))
    checks.append(("decided_at present", rec and rec.get("decided_at") is not None))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("C4", "Champs exacts du record auto-waived", "V5.1", all_ok, details)


def test_C5_non_guaranteed_not_in_admin():
    """C5: Vérifier qu'un non-garanti waived ne remonte PAS en arbitrage admin."""
    apt_id, pids = _create_scenario("C5: Pas d'arbitrage admin", [
        {"status": "accepted_guaranteed", "outcome": "manual_review", "is_organizer": True, "user_id": ORG_USER_ID},
        {"status": "accepted_guaranteed", "outcome": "manual_review"},
        {"status": "accepted_pending_guarantee", "outcome": "manual_review"},
    ])
    initialize_declarative_phase(apt_id)

    # Check admin dispute queries
    non_g_pid = pids[2]
    admin_disputes = list(db.declarative_disputes.find(
        {"target_participant_id": non_g_pid}, {"_id": 0}
    ))
    manual_review_records = list(db.attendance_records.find(
        {"appointment_id": apt_id, "participant_id": non_g_pid,
         "review_required": True, "outcome": "manual_review"}, {"_id": 0}
    ))

    checks = []
    checks.append(("0 disputes admin", len(admin_disputes) == 0))
    checks.append(("plus en manual_review", len(manual_review_records) == 0))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("C5", "Non-garanti PAS en arbitrage admin", "V5.1", all_ok, details)


# ═══════════════════════════════════════════════════════════════
# D. CAS EXTRÊMES / EDGE CASES
# ═══════════════════════════════════════════════════════════════

def test_D1_single_guaranteed_in_manual_review():
    """D1: 1 seul garanti en manual_review → not_needed."""
    apt_id, pids = _create_scenario("D1: 1 seul garanti MR", [
        {"status": "accepted_guaranteed", "outcome": "manual_review"},
    ])
    initialize_declarative_phase(apt_id)
    s = _get_state(apt_id)

    checks = []
    checks.append(("phase == not_needed", s["phase"] == "not_needed"))
    checks.append(("0 sheets", len(s["sheets"]) == 0))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("D1", "1 seul garanti MR → not_needed", "Edge case", all_ok, details)


def test_D2_zero_guaranteed_multiple_mr():
    """D2: 0 garanti mais 5 manual_review → tous waived, not_needed."""
    apt_id, pids = _create_scenario("D2: 0 garanti, 5 MR", [
        {"status": "accepted", "outcome": "manual_review", "is_organizer": True, "user_id": ORG_USER_ID},
        {"status": "accepted_pending_guarantee", "outcome": "manual_review"},
        {"status": "accepted_pending_guarantee", "outcome": "manual_review"},
        {"status": "accepted", "outcome": "manual_review"},
        {"status": "accepted", "outcome": "manual_review"},
    ])
    initialize_declarative_phase(apt_id)
    s = _get_state(apt_id)

    waived = sum(1 for r in s["records"]
                 if r["outcome"] == "waived" and r.get("decision_source") == "non_guaranteed_auto_waived")
    checks = []
    checks.append(("phase == not_needed", s["phase"] == "not_needed"))
    checks.append(("5 waived", waived == 5))
    checks.append(("0 sheets", len(s["sheets"]) == 0))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("D2", "0 garanti, 5 MR → all waived", "Edge case", all_ok, details)


def test_D3_organizer_only_guaranteed():
    """D3: Organisateur seul garanti, 2 non-garantis → not_needed."""
    apt_id, pids = _create_scenario("D3: Org seul garanti", [
        {"status": "accepted_guaranteed", "outcome": "manual_review", "is_organizer": True, "user_id": ORG_USER_ID},
        {"status": "accepted_pending_guarantee", "outcome": "manual_review"},
        {"status": "accepted", "outcome": "manual_review"},
    ])
    initialize_declarative_phase(apt_id)
    s = _get_state(apt_id)

    checks = []
    checks.append(("phase == not_needed", s["phase"] == "not_needed"))
    non_g_waived = sum(1 for r in s["records"]
                       if r["outcome"] == "waived" and r.get("decision_source") == "non_guaranteed_auto_waived")
    checks.append(("2 non-garantis waived", non_g_waived == 2))
    # Remaining guaranteed org should ALSO be waived (insufficient participants)
    org_rec = next((r for r in s["records"] if r["participant_id"] == pids[0]), None)
    checks.append(("org waived (insufficient participants)",
                    org_rec and org_rec.get("outcome") == "waived" and
                    org_rec.get("decision_source") == "insufficient_guaranteed_participants"))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("D3", "Org seul garanti → not_needed", "Edge case", all_ok, details)


def test_D4_double_initialization():
    """D4: Double appel à initialize_declarative_phase → idempotent, pas de duplication."""
    apt_id, pids = _create_scenario("D4: Double init", [
        {"status": "accepted_guaranteed", "outcome": "manual_review", "is_organizer": True, "user_id": ORG_USER_ID},
        {"status": "accepted_guaranteed", "outcome": "manual_review"},
    ])
    initialize_declarative_phase(apt_id)
    sheets_before = db.attendance_sheets.count_documents({"appointment_id": apt_id})

    # Second call — should be blocked by idempotency guard
    initialize_declarative_phase(apt_id)
    sheets_after = db.attendance_sheets.count_documents({"appointment_id": apt_id})

    checks = []
    checks.append(("sheets pas dupliquées", sheets_before == sheets_after))
    checks.append(("sheets_before > 0", sheets_before > 0))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("D4", "Double init → idempotent", "Edge case", all_ok, details)


def test_D5_rerun_on_same_rdv():
    """D5: Rerun after resolved phase → blocked."""
    apt_id, pids, sheets = _create_and_init_guaranteed_scenario("D5: Rerun après resolved", 2)
    status_map = {pid: "present_on_time" for pid in pids}
    _submit_all_sheets(apt_id, sheets, status_map)

    s = _get_state(apt_id)
    assert s["phase"] == "resolved"

    # Try to re-initialize → should be blocked
    initialize_declarative_phase(apt_id)
    s2 = _get_state(apt_id)

    checks = []
    checks.append(("phase toujours resolved", s2["phase"] == "resolved"))
    sheets_count = db.attendance_sheets.count_documents({"appointment_id": apt_id})
    checks.append(("sheets pas recréées", sheets_count == len(sheets)))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("D5", "Rerun après resolved → bloqué", "Edge case", all_ok, details)


def test_D6_less_than_2_guaranteed_after_filter():
    """D6: Tentative de déclencher une feuille avec < 2 garantis → impossible."""
    apt_id, pids = _create_scenario("D6: < 2 garantis post-filtre", [
        {"status": "accepted_guaranteed", "outcome": "manual_review", "is_organizer": True, "user_id": ORG_USER_ID},
        {"status": "accepted_pending_guarantee", "outcome": "manual_review"},
        {"status": "accepted", "outcome": "manual_review"},
        {"status": "accepted_pending_guarantee", "outcome": "manual_review"},
    ])
    initialize_declarative_phase(apt_id)
    s = _get_state(apt_id)

    checks = []
    checks.append(("phase == not_needed", s["phase"] == "not_needed"))
    checks.append(("0 sheets", len(s["sheets"]) == 0))
    waived = sum(1 for r in s["records"]
                 if r.get("decision_source") == "non_guaranteed_auto_waived")
    checks.append(("3 non-garantis waived", waived == 3))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("D6", "< 2 garantis post-filtre → rien", "Edge case", all_ok, details)


def test_D7_100pct_contradictions_between_guaranteed():
    """D7: Déclarations 100% contradictoires entre garantis (large group)."""
    apt_id, pids, sheets = _create_and_init_guaranteed_scenario("D7: Contradictions totales", 4)
    # Half say present, half say absent for each target
    for i, sheet in enumerate(sheets):
        decls = []
        for d in sheet["declarations"]:
            if d.get("is_self_declaration"):
                decls.append({"target_participant_id": d["target_participant_id"],
                              "declared_status": "present_on_time"})
            else:
                # Alternate: even sheets say present, odd say absent
                status = "present_on_time" if i % 2 == 0 else "absent"
                decls.append({"target_participant_id": d["target_participant_id"],
                              "declared_status": status})
        submit_sheet(apt_id, sheet["submitted_by_user_id"], decls)

    s = _get_state(apt_id)
    checks = []
    checks.append(("phase == disputed ou resolved", s["phase"] in ("disputed", "resolved")))
    # With disagreements, we expect disputes
    checks.append(("disputes ou analyses créées", len(s["disputes"]) >= 1 or len(s["analyses"]) >= 1))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("D7", "Contradictions totales (large group)", "Edge case", all_ok, details)


def test_D8_mix_manual_review_and_resolved():
    """D8: Mix de participants en manual_review et déjà résolus → seuls les MR entrent."""
    apt_id, pids = _create_scenario("D8: Mix MR + on_time", [
        {"status": "accepted_guaranteed", "outcome": "manual_review", "is_organizer": True, "user_id": ORG_USER_ID},
        {"status": "accepted_guaranteed", "outcome": "manual_review"},
        {"status": "accepted_guaranteed", "outcome": "on_time"},  # Already resolved
    ])
    initialize_declarative_phase(apt_id)
    s = _get_state(apt_id)

    # pids[2] is on_time, should not be in sheets
    is_target = False
    for sh in s["sheets"]:
        for d in sh.get("declarations", []):
            if d["target_participant_id"] == pids[2]:
                is_target = True

    checks = []
    checks.append(("phase == collecting", s["phase"] == "collecting"))
    checks.append(("on_time participant PAS cible", not is_target))
    checks.append(("sheets créées pour MR", len(s["sheets"]) >= 1))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("D8", "Mix MR + on_time → seuls MR en sheets", "Edge case", all_ok, details)


def test_D9_participant_with_no_record():
    """D9: Participant garanti sans attendance_record → pas de crash, pas de sheet."""
    apt_id, pids = _create_scenario("D9: Part sans record", [
        {"status": "accepted_guaranteed", "outcome": "manual_review", "is_organizer": True, "user_id": ORG_USER_ID},
        {"status": "accepted_guaranteed", "outcome": None},  # No record created
    ], create_records=True)
    # Remove record for pids[1] to simulate missing data
    db.attendance_records.delete_many({"participant_id": pids[1]})

    initialize_declarative_phase(apt_id)
    s = _get_state(apt_id)

    checks = []
    # With only 1 MR record, should be not_needed (< 2 guaranteed in MR)
    checks.append(("phase == not_needed", s["phase"] == "not_needed"))
    checks.append(("pas de crash", True))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("D9", "Participant sans record → safe", "Edge case", all_ok, details)


def test_D10_cancelled_participant_guaranteed():
    """D10: Participant garanti annulé tardivement → terminal status, pas cible."""
    apt_id, pids = _create_scenario("D10: Part garanti annulé", [
        {"status": "accepted_guaranteed", "outcome": "manual_review", "is_organizer": True, "user_id": ORG_USER_ID},
        {"status": "accepted_guaranteed", "outcome": "manual_review"},
        {"status": "cancelled_by_participant", "outcome": "manual_review"},  # Cancelled but has MR record
    ])
    initialize_declarative_phase(apt_id)
    s = _get_state(apt_id)

    # pids[2] is cancelled (terminal status) — should not be in sheets
    # But also not guaranteed, so gets waived first
    cancelled_pid = pids[2]
    is_target = False
    for sh in s["sheets"]:
        for d in sh.get("declarations", []):
            if d["target_participant_id"] == cancelled_pid:
                is_target = True

    checks = []
    checks.append(("phase == collecting", s["phase"] == "collecting"))
    checks.append(("cancelled participant PAS cible", not is_target))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("D10", "Part garanti annulé → pas cible", "Edge case", all_ok, details)


def test_D11_auto_litige_guard():
    """D11: Anti auto-litige — target_user_id == organizer_user_id → waived, pas de dispute."""
    apt_id, pids = _create_scenario("D11: Auto-litige", [
        {"status": "accepted_guaranteed", "outcome": "manual_review", "is_organizer": True, "user_id": ORG_USER_ID},
        {"status": "accepted_guaranteed", "outcome": "manual_review"},
    ])
    initialize_declarative_phase(apt_id)
    sheets = list(db.attendance_sheets.find({"appointment_id": apt_id}, {"_id": 0}))

    # Submit: declare organizer absent
    for sh in sheets:
        decls = []
        for d in sh["declarations"]:
            if d["target_participant_id"] == pids[0]:  # organizer
                decls.append({"target_participant_id": d["target_participant_id"],
                              "declared_status": "absent"})
            else:
                decls.append({"target_participant_id": d["target_participant_id"],
                              "declared_status": "present_on_time"})
        submit_sheet(apt_id, sh["submitted_by_user_id"], decls)

    s = _get_state(apt_id)

    # Check that organizer dispute is auto-waived (V5 guard)
    org_disputes = [d for d in s["disputes"] if d.get("target_user_id") == ORG_USER_ID]
    org_record = next((r for r in s["records"] if r["participant_id"] == pids[0]), None)

    checks = []
    checks.append(("0 auto-litiges org", len(org_disputes) == 0))
    checks.append(("org waived (auto-litige guard)",
                    org_record and org_record.get("outcome") == "waived"))

    all_ok = all(c[1] for c in checks)
    details = "; ".join(f"{c[0]}={'OK' if c[1] else 'FAIL'}" for c in checks)
    _record_result("D11", "Anti auto-litige → waived", "Edge case", all_ok, details)


# ═══════════════════════════════════════════════════════════════
# EXÉCUTION
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  RECETTE QA V5.1 — MOTEUR DÉCLARATIF TRUSTLESS")
    print("=" * 70)

    # Clean any previous QA data
    _cleanup()

    # Run all tests
    print("\n── A. CAS FONDAMENTAUX ──")
    test_A1_org_guaranteed_participant_guaranteed()
    test_A2_org_guaranteed_participant_not_guaranteed()
    test_A3_org_not_guaranteed_participant_guaranteed()
    test_A4_zero_guaranteed()
    test_A5_3_participants_2_guaranteed()
    test_A6_3_participants_1_guaranteed()
    test_A7_all_guaranteed()
    test_A8_none_guaranteed()

    print("\n── B. CAS COMPORTEMENTAUX ──")
    test_B1_everyone_present()
    test_B2_one_absent()
    test_B3_multiple_absent()
    test_B4_all_absent()
    test_B5_coherent_declarations()
    test_B6_contradictory_declarations()
    test_B7_nobody_fills_sheet()
    test_B8_all_unknown()

    print("\n── C. CAS SPÉCIFIQUES V5.1 ──")
    test_C1_non_guaranteed_no_sheet()
    test_C2_non_guaranteed_not_target()
    test_C3_non_guaranteed_no_dispute()
    test_C4_non_guaranteed_waived_fields()
    test_C5_non_guaranteed_not_in_admin()

    print("\n── D. CAS EXTRÊMES / EDGE CASES ──")
    test_D1_single_guaranteed_in_manual_review()
    test_D2_zero_guaranteed_multiple_mr()
    test_D3_organizer_only_guaranteed()
    test_D4_double_initialization()
    test_D5_rerun_on_same_rdv()
    test_D6_less_than_2_guaranteed_after_filter()
    test_D7_100pct_contradictions_between_guaranteed()
    test_D8_mix_manual_review_and_resolved()
    test_D9_participant_with_no_record()
    test_D10_cancelled_participant_guaranteed()
    test_D11_auto_litige_guard()

    # Clean up
    _cleanup()

    # ── RAPPORT ──
    print("\n" + "=" * 70)
    print("  RAPPORT DE RECETTE")
    print("=" * 70)

    ok_count = sum(1 for r in RESULTS if r["status"] == "OK")
    ko_count = sum(1 for r in RESULTS if r["status"] == "KO")
    total = len(RESULTS)

    print(f"\n  Total: {total} scénarios")
    print(f"  ✅ OK: {ok_count}")
    print(f"  ❌ KO: {ko_count}")
    print(f"  Taux de réussite: {ok_count/total*100:.1f}%")

    if ko_count > 0:
        print(f"\n  ── ANOMALIES DÉTECTÉES ──")
        for r in RESULTS:
            if r["status"] == "KO":
                print(f"  ❌ [{r['severity']}] {r['id']}: {r['title']}")
                print(f"     {r['details']}")

    # Write JSON report
    report = {
        "summary": f"{ok_count}/{total} scénarios OK ({ok_count/total*100:.1f}%)",
        "total": total,
        "ok": ok_count,
        "ko": ko_count,
        "results": RESULTS,
    }
    report_path = "/app/test_reports/qa_recette_v51.json"
    os.makedirs("/app/test_reports", exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n  Rapport JSON: {report_path}")
    print("=" * 70)
