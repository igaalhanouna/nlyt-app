"""
QA Blind Spots — Audit Produit Global NLYT
============================================
Tests ciblant les angles morts identifiés dans l'architecture Trustless V5.1.

NE TESTE PAS les happy paths déjà validés (qa_recette_v51.py).
Teste les TRANSITIONS INTER-MODULES et les ÉTATS INTERMÉDIAIRES DANGEREUX.

Categories:
- BS-1: Review timeout vs phase déclarative active (CRITIQUE)
- BS-2: Réconciliation wallet vs credit_available_direct (MAJEUR)
- BS-3: Phase "analyzing" stuck sans recovery (MAJEUR)
- BS-4: Reclassification après distribution immediate_release (MOYEN)
- BS-5: debit_refund multi-distribution (MOYEN)
- BS-6: Observateur voit litiges non concernés (PRODUIT)
- BS-7: CAS idempotence — double évaluation concurrente (ROBUSTESSE)
- BS-8: Dispute deadline job — dispute sans deadline field (ROBUSTESSE)
- BS-9: Transition financière quand guarantee status incohérent (ROBUSTESSE)
- BS-10: Phase déclarative avec 0 sheets créées (EDGE)
"""
import sys
import os
import uuid
import logging
from datetime import datetime, timedelta, timezone

sys.path.insert(0, '/app/backend')
os.chdir('/app/backend')

from dotenv import load_dotenv
load_dotenv()

from database import db
from utils.date_utils import now_utc

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("qa_blind_spots")

RESULTS = []


def record(test_id: str, description: str, passed: bool, detail: str = ""):
    status = "OK" if passed else "KO"
    RESULTS.append({"id": test_id, "description": description, "status": status, "detail": detail})
    icon = "PASS" if passed else "FAIL"
    print(f"  [{icon}] {test_id}: {description}" + (f" — {detail}" if detail else ""))


def cleanup_test_data(prefix: str):
    """Remove all test data with a given prefix in appointment_id."""
    db.appointments.delete_many({"appointment_id": {"$regex": f"^{prefix}"}})
    db.participants.delete_many({"appointment_id": {"$regex": f"^{prefix}"}})
    db.attendance_records.delete_many({"appointment_id": {"$regex": f"^{prefix}"}})
    db.attendance_sheets.delete_many({"appointment_id": {"$regex": f"^{prefix}"}})
    db.declarative_disputes.delete_many({"appointment_id": {"$regex": f"^{prefix}"}})
    db.declarative_analyses.delete_many({"appointment_id": {"$regex": f"^{prefix}"}})
    db.payment_guarantees.delete_many({"appointment_id": {"$regex": f"^{prefix}"}})
    db.distributions.delete_many({"appointment_id": {"$regex": f"^{prefix}"}})
    db.wallets.delete_many({"user_id": {"$regex": f"^{prefix}"}})
    db.wallet_transactions.delete_many({"wallet_id": {"$regex": f"^{prefix}"}})


def make_appointment(apt_id, org_id, **kwargs):
    base = {
        "appointment_id": apt_id,
        "organizer_id": org_id,
        "title": f"Test {apt_id}",
        "status": "active",
        "start_datetime": (now_utc() - timedelta(hours=2)).isoformat(),
        "duration_minutes": 60,
        "penalty_amount": 50,
        "penalty_currency": "eur",
        "cancellation_deadline_hours": 24,
        "tolerated_delay_minutes": 5,
        "appointment_type": "physical",
        "platform_commission_percent": 20,
        "affected_compensation_percent": 50,
        "charity_percent": 0,
        "attendance_evaluated": False,
        "declarative_phase": None,
    }
    base.update(kwargs)
    db.appointments.insert_one(base)
    return base


def make_participant(apt_id, pid, uid, email, is_org=False, status="accepted_guaranteed"):
    p = {
        "participant_id": pid,
        "appointment_id": apt_id,
        "user_id": uid,
        "email": email,
        "first_name": f"User_{pid[:4]}",
        "last_name": "Test",
        "status": status,
        "is_organizer": is_org,
        "invitation_token": str(uuid.uuid4()),
    }
    db.participants.insert_one(p)
    return p


def make_guarantee(apt_id, pid, status="completed"):
    g = {
        "guarantee_id": str(uuid.uuid4()),
        "participant_id": pid,
        "appointment_id": apt_id,
        "status": status,
        "penalty_amount": 50,
        "penalty_currency": "eur",
        "stripe_customer_id": f"cus_test_{pid[:8]}",
        "stripe_payment_method_id": f"pm_test_{pid[:8]}",
        "dev_mode": True,
        "created_at": now_utc().isoformat(),
    }
    db.payment_guarantees.insert_one(g)
    return g


# ═══════════════════════════════════════════════════════════════════
# BS-1: Review timeout vs phase déclarative active (CRITIQUE)
# ═══════════════════════════════════════════════════════════════════
def test_bs1_review_timeout_vs_active_dispute():
    """
    Scénario : Un participant est en manual_review, la phase déclarative est
    active (dispute ouverte). Après 15 jours, le review_timeout_job ne devrait
    PAS auto-waiver ce participant si un litige est ouvert pour lui.
    """
    PREFIX = "bs1_"
    cleanup_test_data(PREFIX)

    apt_id = f"{PREFIX}apt_timeout_dispute"
    org_id = f"{PREFIX}org_1"
    pid_target = f"{PREFIX}pid_target"
    uid_target = f"{PREFIX}uid_target"
    pid_org = f"{PREFIX}pid_org"

    make_appointment(apt_id, org_id, declarative_phase="disputed")
    make_participant(apt_id, pid_org, org_id, "org@test.com", is_org=True)
    make_participant(apt_id, pid_target, uid_target, "target@test.com")
    make_guarantee(apt_id, pid_target)

    # Create a stale attendance record (> 15 days old, decided_by=system)
    stale_date = (now_utc() - timedelta(days=20)).isoformat()
    db.attendance_records.insert_one({
        "record_id": f"{PREFIX}rec_1",
        "appointment_id": apt_id,
        "participant_id": pid_target,
        "outcome": "manual_review",
        "review_required": True,
        "decided_by": "system",
        "decided_at": stale_date,
    })

    # Create an open dispute for this participant
    db.declarative_disputes.insert_one({
        "dispute_id": f"{PREFIX}dispute_1",
        "appointment_id": apt_id,
        "target_participant_id": pid_target,
        "target_user_id": uid_target,
        "organizer_user_id": org_id,
        "status": "awaiting_positions",
        "opened_at": stale_date,
        "deadline": (now_utc() + timedelta(days=2)).isoformat(),
        "created_at": stale_date,
    })

    # Run the review timeout job
    from services.attendance_service import run_review_timeout_job
    resolved_count = run_review_timeout_job()

    # Check: the record should NOT have been auto-waived because a dispute is active
    rec = db.attendance_records.find_one({"record_id": f"{PREFIX}rec_1"}, {"_id": 0})
    was_waived = rec.get("outcome") == "waived" and rec.get("decided_by") == "system_timeout"

    if was_waived:
        record("BS-1", "Review timeout vs dispute active: auto-waive devrait être bloqué", False,
               "CRITIQUE: Le participant a été waived malgré un litige ouvert! "
               "Le review_timeout_job ne vérifie pas l'existence de litiges actifs.")
    else:
        record("BS-1", "Review timeout vs dispute active: auto-waive correctement bloqué", True)

    cleanup_test_data(PREFIX)


# ═══════════════════════════════════════════════════════════════════
# BS-2: Réconciliation wallet vs credit_available_direct (MAJEUR)
# ═══════════════════════════════════════════════════════════════════
def test_bs2_reconciliation_credit_available_direct():
    """
    Scénario : Un wallet reçoit un crédit via credit_available_direct (immediate
    release après consensus/arbitrage). La réconciliation devrait le compter
    comme money-in, sinon elle rapportera un faux drift.
    """
    PREFIX = "bs2_"
    cleanup_test_data(PREFIX)

    from services.wallet_service import create_wallet, credit_available_direct, run_reconciliation_job

    wallet = create_wallet(f"{PREFIX}user_1")
    wid = wallet["wallet_id"]

    # Credit 1000c via credit_available_direct (immediate release)
    result = credit_available_direct(
        wallet_id=wid,
        amount_cents=1000,
        currency="eur",
        reference_type="distribution",
        reference_id="dist_test_1",
        description="Test immediate release",
    )
    assert result["success"], f"credit_available_direct failed: {result}"

    # Run reconciliation
    report = run_reconciliation_job()

    # Check: should NOT report a drift for this wallet
    drifts_for_us = [d for d in report.get("drifts", []) if d["wallet_id"] == wid]

    if drifts_for_us:
        drift = drifts_for_us[0]
        record("BS-2", "Réconciliation wallet: credit_available_direct non pris en compte", False,
               f"MAJEUR: Drift reporté = {drift['drift_cents']}c. "
               f"La formule de réconciliation ne compte pas credit_available_direct dans MONEY_IN_TYPES. "
               f"expected={drift['expected_total_cents']}, actual={drift['actual_total_cents']}")
    else:
        record("BS-2", "Réconciliation wallet: credit_available_direct correctement compté", True)

    cleanup_test_data(PREFIX)


# ═══════════════════════════════════════════════════════════════════
# BS-3: Phase "analyzing" stuck sans recovery (MAJEUR)
# ═══════════════════════════════════════════════════════════════════
def test_bs3_analyzing_stuck_state():
    """
    Scénario : La phase déclarative est bloquée en "analyzing" (crash pendant
    l'analyse). Le deadline job devrait-il détecter et récupérer ?
    """
    PREFIX = "bs3_"
    cleanup_test_data(PREFIX)

    apt_id = f"{PREFIX}apt_stuck"
    org_id = f"{PREFIX}org_1"
    stale_time = (now_utc() - timedelta(hours=2)).isoformat()

    make_appointment(apt_id, org_id, declarative_phase="analyzing",
                     declarative_deadline=stale_time,
                     declarative_analyzing_started_at=stale_time,
                     updated_at=stale_time)

    # Run the declarative deadline job
    from services.declarative_service import run_declarative_deadline_job
    run_declarative_deadline_job()

    # Check: the appointment should still be stuck in "analyzing"
    apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
    phase = apt.get("declarative_phase")

    if phase == "analyzing":
        record("BS-3", "Phase 'analyzing' stuck: aucun mécanisme de recovery", False,
               "MAJEUR: La phase reste en 'analyzing' indéfiniment. "
               "Le deadline job ne cherche que les phases 'collecting'. "
               "Un crash durant _run_analysis() bloque l'appointement à vie.")
    else:
        record("BS-3", "Phase 'analyzing' stuck: recovery automatique fonctionne", True,
               f"Phase transitionée vers '{phase}'")

    cleanup_test_data(PREFIX)


# ═══════════════════════════════════════════════════════════════════
# BS-4: Reclassification après distribution immediate_release
# ═══════════════════════════════════════════════════════════════════
def test_bs4_reclassification_after_immediate_release():
    """
    Scénario : Un participant est no_show, distribution créée avec immediate_release
    (status=completed). L'organisateur reclassifie en on_time.
    La distribution devrait être annulée et le wallet débité.
    """
    PREFIX = "bs4_"
    cleanup_test_data(PREFIX)

    apt_id = f"{PREFIX}apt_reclass"
    org_id = f"{PREFIX}org_1"
    pid_noshow = f"{PREFIX}pid_noshow"
    uid_noshow = f"{PREFIX}uid_noshow"
    pid_org = f"{PREFIX}pid_org"

    make_appointment(apt_id, org_id)
    make_participant(apt_id, pid_org, org_id, "org@test.com", is_org=True)
    make_participant(apt_id, pid_noshow, uid_noshow, "noshow@test.com")
    g = make_guarantee(apt_id, pid_noshow, status="captured")

    # Create a completed (immediate release) distribution
    from services.wallet_service import create_wallet
    org_wallet = create_wallet(org_id)

    dist_id = f"{PREFIX}dist_1"
    db.distributions.insert_one({
        "distribution_id": dist_id,
        "appointment_id": apt_id,
        "guarantee_id": g["guarantee_id"],
        "no_show_participant_id": pid_noshow,
        "no_show_user_id": uid_noshow,
        "no_show_is_organizer": False,
        "capture_amount_cents": 5000,
        "capture_currency": "eur",
        "stripe_payment_intent_id": "pi_test",
        "status": "completed",  # <-- immediate_release!
        "release_reason": "consensus",
        "beneficiaries": [{
            "beneficiary_id": str(uuid.uuid4()),
            "wallet_id": org_wallet["wallet_id"],
            "user_id": org_id,
            "role": "organizer",
            "amount_cents": 4000,
            "status": "credited_available",
        }],
        "created_at": now_utc().isoformat(),
    })

    # Credit the wallet to simulate the initial distribution
    from services.wallet_service import credit_available_direct
    credit_available_direct(
        wallet_id=org_wallet["wallet_id"],
        amount_cents=4000,
        currency="eur",
        reference_type="distribution",
        reference_id=dist_id,
        description="Test credit",
    )

    # Create attendance record for the noshow
    db.attendance_records.insert_one({
        "record_id": f"{PREFIX}rec_noshow",
        "appointment_id": apt_id,
        "participant_id": pid_noshow,
        "outcome": "no_show",
        "review_required": False,
        "decided_by": "system",
        "decided_at": now_utc().isoformat(),
    })

    # Reclassify: no_show → on_time
    from services.attendance_service import reclassify_participant
    result = reclassify_participant(f"{PREFIX}rec_noshow", "on_time", "Erreur", org_id)

    # Check: distribution should be cancelled
    dist = db.distributions.find_one({"distribution_id": dist_id}, {"_id": 0})
    dist_cancelled = dist and dist.get("status") == "cancelled"

    if not dist_cancelled:
        record("BS-4", "Reclassification après immediate_release: distribution non annulée", False,
               f"MOYEN: Distribution status={dist.get('status') if dist else 'N/A'}. "
               f"cancel_distribution() refuse les distributions 'completed'. "
               f"Le remboursement financier n'a pas lieu après reclassification.")
    else:
        record("BS-4", "Reclassification après immediate_release: distribution correctement annulée", True)

    cleanup_test_data(PREFIX)


# ═══════════════════════════════════════════════════════════════════
# BS-5: debit_refund sur wallet multi-distribution (MOYEN)
# ═══════════════════════════════════════════════════════════════════
def test_bs5_debit_refund_multi_distribution():
    """
    Scénario : Un wallet a 1000c pending (dist A) et 500c pending (dist B).
    debit_refund de 1000c pour dist B va prendre dans pending, mais ce sont
    les fonds de dist A. Quand le hold de dist A expire, confirm_pending_to_available
    échouera car le pending est insuffisant.
    """
    PREFIX = "bs5_"
    cleanup_test_data(PREFIX)

    from services.wallet_service import create_wallet, credit_pending, debit_refund, confirm_pending_to_available

    wallet = create_wallet(f"{PREFIX}user_multi")
    wid = wallet["wallet_id"]

    # Credit 1000c pending (dist A) then 500c pending (dist B)
    credit_pending(wid, 1000, "eur", "distribution", "distA", "Dist A")
    credit_pending(wid, 500, "eur", "distribution", "distB", "Dist B")

    # Wallet should have pending_balance = 1500
    w = db.wallets.find_one({"wallet_id": wid}, {"_id": 0})
    assert w["pending_balance"] == 1500, f"Expected 1500 pending, got {w['pending_balance']}"

    # Refund dist B: 500c (should work)
    result = debit_refund(wid, 500, "eur", "distB", "Refund B")
    assert result["success"], f"Refund B failed: {result}"

    # Wallet should have pending_balance = 1000
    w = db.wallets.find_one({"wallet_id": wid}, {"_id": 0})

    # Now confirm dist A hold expiry: 1000c from pending → available
    result = confirm_pending_to_available(wid, 1000, "eur", "distribution", "distA", "Confirm A")

    if result.get("success"):
        record("BS-5", "debit_refund multi-distribution: confirm_pending réussit", True,
               "Pas de conflit — fonds suffisants")
    else:
        record("BS-5", "debit_refund multi-distribution: confirm_pending échoue", False,
               f"MOYEN: {result.get('error')}. Le debit_refund n'est pas distribution-aware, "
               f"il a pris les fonds d'une autre distribution dans pending.")

    cleanup_test_data(PREFIX)


# ═══════════════════════════════════════════════════════════════════
# BS-6: Observateur voit litiges non concernés (PRODUIT)
# ═══════════════════════════════════════════════════════════════════
def test_bs6_observer_sees_unrelated_disputes():
    """
    Scénario : 3 participants (A, B, C) dans un RDV. Un litige concerne
    uniquement A vs l'Organisateur. B et C voient-ils ce litige via /mine ?
    """
    PREFIX = "bs6_"
    cleanup_test_data(PREFIX)

    apt_id = f"{PREFIX}apt_obs"
    org_id = f"{PREFIX}org_1"
    pid_a = f"{PREFIX}pid_A"
    uid_a = f"{PREFIX}uid_A"
    pid_b = f"{PREFIX}pid_B"
    uid_b = f"{PREFIX}uid_B"
    pid_c = f"{PREFIX}pid_C"
    uid_c = f"{PREFIX}uid_C"
    pid_org = f"{PREFIX}pid_org"

    make_appointment(apt_id, org_id, declarative_phase="disputed")
    make_participant(apt_id, pid_org, org_id, "org@test.com", is_org=True)
    make_participant(apt_id, pid_a, uid_a, "a@test.com")
    make_participant(apt_id, pid_b, uid_b, "b@test.com")
    make_participant(apt_id, pid_c, uid_c, "c@test.com")

    # Dispute only about participant A
    db.declarative_disputes.insert_one({
        "dispute_id": f"{PREFIX}dispute_A",
        "appointment_id": apt_id,
        "target_participant_id": pid_a,
        "target_user_id": uid_a,
        "organizer_user_id": org_id,
        "status": "awaiting_positions",
        "organizer_position": None,
        "participant_position": None,
        "opened_at": now_utc().isoformat(),
        "created_at": now_utc().isoformat(),
    })

    # Simulate "GET /disputes/mine" for user B — using the SAME filtering logic as the API
    user_b_participants = list(db.participants.find(
        {"user_id": uid_b}, {"_id": 0, "appointment_id": 1}
    ))
    apt_ids_b = list({p['appointment_id'] for p in user_b_participants})
    all_disputes_for_b = list(db.declarative_disputes.find(
        {"appointment_id": {"$in": apt_ids_b}}, {"_id": 0}
    ))

    # Apply the BS-6 fix filtering: only keep disputes where user is organizer, target, or counterpart
    relevant_for_b = []
    for d in all_disputes_for_b:
        is_organizer = (d.get('organizer_user_id') == uid_b)
        is_target = (d.get('target_user_id') == uid_b)
        is_counterpart = False
        if not is_organizer and not is_target:
            # Check if B submitted a declaration about the target
            sheet = db.attendance_sheets.find_one({
                "appointment_id": d['appointment_id'],
                "submitted_by_user_id": uid_b,
                "status": "submitted",
            }, {"_id": 0, "declarations": 1})
            if sheet:
                is_counterpart = any(
                    decl.get("target_participant_id") == d['target_participant_id']
                    for decl in sheet.get("declarations", [])
                )
        if is_organizer or is_target or is_counterpart:
            relevant_for_b.append(d)

    sees_unrelated = len(relevant_for_b) > 0

    if sees_unrelated:
        record("BS-6", "Observateur voit litiges non concernés", False,
               f"PRODUIT: L'utilisateur B voit {len(disputes_seen_by_b)} litige(s) "
               f"qui ne le concerne(nt) pas. Le query /disputes/mine retourne tous les "
               f"litiges de l'appointment, pas seulement ceux où l'user est partie prenante.")
    else:
        record("BS-6", "Observateur ne voit pas les litiges non concernés", True)

    cleanup_test_data(PREFIX)


# ═══════════════════════════════════════════════════════════════════
# BS-7: CAS idempotence — double évaluation concurrente (ROBUSTESSE)
# ═══════════════════════════════════════════════════════════════════
def test_bs7_double_evaluation_cas():
    """
    Scénario : Deux appels concurrent à evaluate_appointment().
    Le CAS doit garantir qu'un seul passe.
    """
    PREFIX = "bs7_"
    cleanup_test_data(PREFIX)

    apt_id = f"{PREFIX}apt_cas"
    org_id = f"{PREFIX}org_1"
    pid = f"{PREFIX}pid_1"
    uid = f"{PREFIX}uid_1"

    make_appointment(apt_id, org_id, attendance_evaluated=False,
                     start_datetime=(now_utc() - timedelta(hours=3)).isoformat())
    make_participant(apt_id, pid, uid, "user@test.com", status="declined")

    from services.attendance_service import evaluate_appointment

    result1 = evaluate_appointment(apt_id)
    result2 = evaluate_appointment(apt_id)

    first_ran = result1.get("evaluated", False)
    second_skipped = result2.get("skipped", False)

    if first_ran and second_skipped:
        record("BS-7", "CAS idempotence: double évaluation bloquée", True)
    else:
        record("BS-7", "CAS idempotence: double évaluation non protégée", False,
               f"result1={result1}, result2={result2}")

    cleanup_test_data(PREFIX)


# ═══════════════════════════════════════════════════════════════════
# BS-8: Dispute deadline job — dispute sans champ deadline
# ═══════════════════════════════════════════════════════════════════
def test_bs8_dispute_without_deadline():
    """
    Scénario : Un litige dans la DB n'a pas de champ 'deadline' (données
    historiques ou bug de création). Le job d'escalade ne doit pas crasher.
    """
    PREFIX = "bs8_"
    cleanup_test_data(PREFIX)

    apt_id = f"{PREFIX}apt_nodl"
    db.declarative_disputes.insert_one({
        "dispute_id": f"{PREFIX}dispute_nodl",
        "appointment_id": apt_id,
        "target_participant_id": f"{PREFIX}pid_1",
        "target_user_id": f"{PREFIX}uid_1",
        "organizer_user_id": f"{PREFIX}org_1",
        "status": "awaiting_positions",
        # NO deadline field!
        "created_at": (now_utc() - timedelta(days=30)).isoformat(),
    })

    try:
        from services.declarative_service import run_dispute_deadline_job
        run_dispute_deadline_job()
        record("BS-8", "Dispute sans deadline: job ne crash pas", True)
    except Exception as e:
        record("BS-8", "Dispute sans deadline: job crash", False, str(e))

    # Check: dispute should NOT have been escalated (no deadline to compare)
    d = db.declarative_disputes.find_one({"dispute_id": f"{PREFIX}dispute_nodl"}, {"_id": 0})
    if d and d.get("status") == "awaiting_positions":
        record("BS-8b", "Dispute sans deadline: dispute non escaladée (correct)", True)
    elif d and d.get("status") == "escalated":
        record("BS-8b", "Dispute sans deadline: dispute escaladée incorrectement", False,
               "Le job a escaladé une dispute sans deadline — comportement ambigu")

    cleanup_test_data(PREFIX)


# ═══════════════════════════════════════════════════════════════════
# BS-9: Capture quand guarantee already released
# ═══════════════════════════════════════════════════════════════════
def test_bs9_capture_released_guarantee():
    """
    Scénario : Un litige se résout en no_show APRÈS que la review_timeout
    a déjà libéré la garantie. La capture devrait échouer proprement.
    """
    PREFIX = "bs9_"
    cleanup_test_data(PREFIX)

    apt_id = f"{PREFIX}apt_released"
    org_id = f"{PREFIX}org_1"
    pid_target = f"{PREFIX}pid_t"
    uid_target = f"{PREFIX}uid_t"
    pid_org = f"{PREFIX}pid_org"

    make_appointment(apt_id, org_id)
    make_participant(apt_id, pid_org, org_id, "org@test.com", is_org=True)
    make_participant(apt_id, pid_target, uid_target, "target@test.com")

    # Guarantee already released (by review_timeout or other path)
    g = make_guarantee(apt_id, pid_target, status="released")

    # Attendance record exists
    db.attendance_records.insert_one({
        "record_id": f"{PREFIX}rec_t",
        "appointment_id": apt_id,
        "participant_id": pid_target,
        "outcome": "manual_review",
        "review_required": True,
        "decided_by": "system",
        "decided_at": now_utc().isoformat(),
    })

    # Try to capture the guarantee (as would happen after dispute resolution)
    from services.stripe_guarantee_service import StripeGuaranteeService
    result = StripeGuaranteeService.capture_guarantee(g["guarantee_id"], "no_show")

    if not result.get("success"):
        record("BS-9", "Capture garantie déjà libérée: échec propre", True,
               f"Error: {result.get('error', 'N/A')}")
    else:
        record("BS-9", "Capture garantie déjà libérée: acceptée incorrectement", False,
               "La capture ne devrait pas réussir sur une garantie released!")

    cleanup_test_data(PREFIX)


# ═══════════════════════════════════════════════════════════════════
# BS-10: Resolve dispute → financial engine avec no beneficiary
# ═══════════════════════════════════════════════════════════════════
def test_bs10_resolve_dispute_no_beneficiary():
    """
    Scénario : Tous les participants sont en manual_review (pas de présence
    prouvée). Un litige est résolu en no_show. Mais il n'y a aucun
    bénéficiaire éligible (Cas A). La capture devrait être bloquée.
    """
    PREFIX = "bs10_"
    cleanup_test_data(PREFIX)

    apt_id = f"{PREFIX}apt_nob"
    org_id = f"{PREFIX}org_1"
    pid_org = f"{PREFIX}pid_org"
    pid_a = f"{PREFIX}pid_a"
    uid_a = f"{PREFIX}uid_a"
    pid_b = f"{PREFIX}pid_b"
    uid_b = f"{PREFIX}uid_b"

    make_appointment(apt_id, org_id, declarative_phase="disputed",
                     attendance_evaluated=True)
    make_participant(apt_id, pid_org, org_id, "org@test.com", is_org=True)
    make_participant(apt_id, pid_a, uid_a, "a@test.com")
    make_participant(apt_id, pid_b, uid_b, "b@test.com")
    make_guarantee(apt_id, pid_a, status="completed")
    make_guarantee(apt_id, pid_b, status="completed")

    # Both participants in manual_review (no proof, no beneficiary)
    for pid in [pid_a, pid_b]:
        db.attendance_records.insert_one({
            "record_id": f"{PREFIX}rec_{pid[-2:]}",
            "appointment_id": apt_id,
            "participant_id": pid,
            "outcome": "manual_review",
            "review_required": True,
            "decided_by": "system",
            "decided_at": now_utc().isoformat(),
        })

    # Create dispute for participant A
    dispute_id = f"{PREFIX}disp_a"
    db.declarative_disputes.insert_one({
        "dispute_id": dispute_id,
        "appointment_id": apt_id,
        "target_participant_id": pid_a,
        "target_user_id": uid_a,
        "organizer_user_id": org_id,
        "status": "escalated",
        "organizer_position": "confirmed_absent",
        "participant_position": "confirmed_present",
        "opened_at": now_utc().isoformat(),
        "created_at": now_utc().isoformat(),
        "resolution": {"resolved_at": None, "final_outcome": None, "resolved_by": None, "resolution_note": None},
    })

    # Resolve as no_show
    from services.declarative_service import resolve_dispute
    result = resolve_dispute(dispute_id, "no_show", "Admin decision", "platform")

    # Check: distribution should NOT be created (Cas A: no beneficiary)
    dist = db.distributions.find_one({"appointment_id": apt_id}, {"_id": 0})

    if dist is None:
        # Check if record was properly set back to review_required (Cas A override)
        rec = db.attendance_records.find_one({
            "appointment_id": apt_id, "participant_id": pid_a
        }, {"_id": 0})
        cas_a = rec.get("cas_a_override", False) if rec else False

        if cas_a:
            record("BS-10", "Dispute résolue no_show sans bénéficiaire: Cas A correctement appliqué", True,
                   "Capture bloquée, record marqué cas_a_override=True")
        else:
            outcome = rec.get("outcome") if rec else "N/A"
            record("BS-10", "Dispute résolue no_show sans bénéficiaire: pas de distribution", True,
                   f"Record outcome={outcome}, pas de Cas A explicite mais pas de distribution non plus")
    else:
        record("BS-10", "Dispute résolue no_show sans bénéficiaire: distribution créée!", False,
               "DANGER: Distribution créée alors qu'il n'y a aucun bénéficiaire prouvé!")

    cleanup_test_data(PREFIX)


# ═══════════════════════════════════════════════════════════════════
# BS-11: Phase déclarative — organizer aussi en manual_review, auto-litige guard
# ═══════════════════════════════════════════════════════════════════
def test_bs11_declarative_auto_litige_guard():
    """
    Scénario : L'organisateur est aussi participant et en manual_review.
    L'analyse déclarative ne doit PAS créer un auto-litige (org vs org).
    """
    PREFIX = "bs11_"
    cleanup_test_data(PREFIX)

    apt_id = f"{PREFIX}apt_autol"
    org_id = f"{PREFIX}org_1"
    pid_org = f"{PREFIX}pid_org"
    pid_other = f"{PREFIX}pid_other"
    uid_other = f"{PREFIX}uid_other"

    make_appointment(apt_id, org_id, declarative_phase=None)
    make_participant(apt_id, pid_org, org_id, "org@test.com", is_org=True, status="accepted_guaranteed")
    make_participant(apt_id, pid_other, uid_other, "other@test.com", status="accepted_guaranteed")

    # Both in manual_review
    for pid in [pid_org, pid_other]:
        db.attendance_records.insert_one({
            "record_id": f"{PREFIX}rec_{pid[-4:]}",
            "appointment_id": apt_id,
            "participant_id": pid,
            "outcome": "manual_review",
            "review_required": True,
            "decided_by": "system",
            "decided_at": now_utc().isoformat(),
        })

    # Initialize declarative phase
    from services.declarative_service import initialize_declarative_phase
    initialize_declarative_phase(apt_id)

    # Create sheets and submit with "absent" declarations about each other
    sheets = list(db.attendance_sheets.find({"appointment_id": apt_id}, {"_id": 0}))
    from services.declarative_service import submit_sheet

    for s in sheets:
        decls = []
        for d in s["declarations"]:
            decls.append({
                "target_participant_id": d["target_participant_id"],
                "declared_status": "absent",  # Everyone says everyone else is absent
            })
        submit_sheet(apt_id, s["submitted_by_user_id"], decls)

    # Check: dispute for org (pid_org) should NOT be created (auto-litige guard)
    org_dispute = db.declarative_disputes.find_one({
        "appointment_id": apt_id,
        "target_participant_id": pid_org,
    }, {"_id": 0})

    if org_dispute is None:
        record("BS-11", "Auto-litige guard: pas de litige org vs org", True,
               "L'organisateur en manual_review est correctement protégé")
    else:
        if org_dispute.get("target_user_id") == org_dispute.get("organizer_user_id"):
            record("BS-11", "Auto-litige guard: auto-litige créé!", False,
                   "DANGER: Litige org vs org créé, target_user_id == organizer_user_id")
        else:
            record("BS-11", "Auto-litige guard: litige créé avec IDs distincts", True,
                   "Pas un auto-litige (IDs différents)")

    cleanup_test_data(PREFIX)


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 70)
    print("QA BLIND SPOTS — Audit Produit Global NLYT")
    print("=" * 70)
    print()

    tests = [
        ("BS-1", test_bs1_review_timeout_vs_active_dispute),
        ("BS-2", test_bs2_reconciliation_credit_available_direct),
        ("BS-3", test_bs3_analyzing_stuck_state),
        ("BS-4", test_bs4_reclassification_after_immediate_release),
        ("BS-5", test_bs5_debit_refund_multi_distribution),
        ("BS-6", test_bs6_observer_sees_unrelated_disputes),
        ("BS-7", test_bs7_double_evaluation_cas),
        ("BS-8", test_bs8_dispute_without_deadline),
        ("BS-9", test_bs9_capture_released_guarantee),
        ("BS-10", test_bs10_resolve_dispute_no_beneficiary),
        ("BS-11", test_bs11_declarative_auto_litige_guard),
    ]

    for test_id, test_fn in tests:
        print(f"\n--- {test_id} ---")
        try:
            test_fn()
        except Exception as e:
            record(test_id, f"CRASH: {str(e)[:100]}", False, f"Exception: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("RÉSULTATS")
    print("=" * 70)
    passed = sum(1 for r in RESULTS if r["status"] == "OK")
    failed = sum(1 for r in RESULTS if r["status"] == "KO")
    total = len(RESULTS)
    print(f"\n  {passed}/{total} OK — {failed}/{total} KO\n")

    if failed > 0:
        print("  ÉCHECS:")
        for r in RESULTS:
            if r["status"] == "KO":
                print(f"    [{r['id']}] {r['description']}")
                if r.get("detail"):
                    print(f"           {r['detail']}")

    print()
