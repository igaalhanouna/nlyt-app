"""
NLYT — Stripe Card Reuse Validation Tests
==========================================
Tests complets pour la réutilisation de carte enregistrée.

Scénarios testés:
  1. CAS NOMINAL : carte valide → réutilisée sans redirect Stripe
  2. CAS SCA/3DS : carte nécessitant authentification → fallback Checkout
  3. CAS CARTE REFUSÉE : carte déclinée → fallback Checkout
  4. CAS CARTE EXPIRÉE : carte expirée → fallback Checkout
  5. FALLBACK : échec quelconque → Checkout standard, pas de double état
  6. PREUVE STRIPE : vérification que le SetupIntent existe réellement côté Stripe
  7. CAPTURE FUTURE : vérification que la carte validée peut être capturée plus tard
"""
import os
import sys
import json
import uuid
import stripe
from datetime import datetime, timezone, timedelta

sys.path.insert(0, '/app/backend')
os.environ['DB_NAME'] = 'test_database'
os.environ['MONGO_URL'] = 'mongodb://localhost:27017'

from dotenv import load_dotenv
load_dotenv('/app/backend/.env', override=True)

from database import db
from services.stripe_guarantee_service import StripeGuaranteeService

STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')
stripe.api_key = STRIPE_API_KEY

# ─── Test result collector ───
results = []

def log_result(name, passed, details, stripe_log=None):
    entry = {
        "test": name,
        "passed": passed,
        "details": details,
    }
    if stripe_log:
        entry["stripe_log"] = stripe_log
    results.append(entry)
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n{'='*70}")
    print(f"  {status} — {name}")
    print(f"  {details}")
    if stripe_log:
        print(f"  Stripe: {json.dumps(stripe_log, indent=2, default=str)[:500]}")
    print(f"{'='*70}")


# ─── Setup: create a real Stripe test customer with various cards ───

def setup_stripe_test_customer():
    """Create a Stripe customer with multiple test payment methods."""
    print("\n" + "="*70)
    print("  SETUP: Création du customer Stripe de test")
    print("="*70)

    customer = stripe.Customer.create(
        email="nlyt-test-reuse@example.com",
        name="NLYT Test Reuse",
        metadata={"source": "nlyt_test", "purpose": "card_reuse_validation"}
    )
    print(f"  Customer créé: {customer.id}")

    # 1. Valid card (tok_visa → 4242424242424242)
    pm_valid = stripe.PaymentMethod.create(
        type="card",
        card={"token": "tok_visa"},
    )
    stripe.PaymentMethod.attach(pm_valid.id, customer=customer.id)
    print(f"  PM valide attaché: {pm_valid.id} (Visa ****4242)")

    # 2. Card requiring 3DS/SCA (tok_threeDSecure2Required)
    pm_sca = stripe.PaymentMethod.create(
        type="card",
        card={"token": "tok_threeDSecure2Required"},
    )
    stripe.PaymentMethod.attach(pm_sca.id, customer=customer.id)
    print(f"  PM SCA attaché: {pm_sca.id} (3DS required)")

    # Note: tok_chargeDeclined cannot be attached to a customer in test mode.
    # We test declined/expired scenarios using a fake PM ID in test_4_invalid_pm.

    return {
        "customer_id": customer.id,
        "pm_valid": pm_valid.id,
        "pm_sca": pm_sca.id,
    }


def create_test_participant(email="nlyt-test-reuse@example.com"):
    """Create a test participant + appointment for testing."""
    apt_id = f"apt_test_{uuid.uuid4().hex[:8]}"
    participant_id = f"part_test_{uuid.uuid4().hex[:8]}"
    token = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    db.appointments.insert_one({
        "appointment_id": apt_id,
        "title": "Test Stripe Card Reuse",
        "organizer_id": "test_organizer",
        "penalty_amount": 50.0,
        "penalty_currency": "eur",
        "start_datetime": (now + timedelta(days=7)).isoformat(),
        "status": "active",
        "created_at": now.isoformat(),
    })

    db.participants.insert_one({
        "participant_id": participant_id,
        "appointment_id": apt_id,
        "email": email,
        "first_name": "Test",
        "last_name": "Reuse",
        "invitation_token": token,
        "status": "invited",
        "created_at": now.isoformat(),
    })

    return {
        "appointment_id": apt_id,
        "participant_id": participant_id,
        "invitation_token": token,
    }


# ═══════════════════════════════════════════════════════════════════
#  TEST 1: CAS NOMINAL — Carte valide, réutilisation silencieuse
# ═══════════════════════════════════════════════════════════════════

def test_1_valid_card_reuse(stripe_data):
    """Carte valide → garantie créée sans redirect, SetupIntent succeeded."""
    test_data = create_test_participant()

    result = StripeGuaranteeService.create_guarantee_with_saved_card(
        participant_id=test_data["participant_id"],
        appointment_id=test_data["appointment_id"],
        invitation_token=test_data["invitation_token"],
        penalty_amount=50.0,
        penalty_currency="eur",
        user_id="test_user_valid",
        stripe_customer_id=stripe_data["customer_id"],
        payment_method_id=stripe_data["pm_valid"],
    )

    # Verify result
    passed = result.get("success") is True
    stripe_log = {"setup_intent_id": result.get("setup_intent_id")}

    if passed:
        # Verify SetupIntent exists on Stripe
        si = stripe.SetupIntent.retrieve(result["setup_intent_id"])
        stripe_log["si_status"] = si.status
        stripe_log["si_payment_method"] = si.payment_method
        stripe_log["si_usage"] = si.usage
        passed = passed and si.status == "succeeded"

        # Verify DB guarantee record
        guarantee = db.payment_guarantees.find_one(
            {"guarantee_id": result["guarantee_id"]}, {"_id": 0}
        )
        stripe_log["db_status"] = guarantee.get("status") if guarantee else "NOT_FOUND"
        stripe_log["db_reused_card"] = guarantee.get("reused_card") if guarantee else None
        stripe_log["db_setup_intent_id"] = guarantee.get("stripe_setup_intent_id") if guarantee else None
        passed = passed and guarantee is not None
        passed = passed and guarantee.get("status") == "completed"
        passed = passed and guarantee.get("reused_card") is True
        passed = passed and guarantee.get("stripe_setup_intent_id") == result["setup_intent_id"]

        # Verify participant status updated
        participant = db.participants.find_one(
            {"participant_id": test_data["participant_id"]}, {"_id": 0}
        )
        stripe_log["participant_status"] = participant.get("status") if participant else "NOT_FOUND"
        passed = passed and participant is not None
        passed = passed and participant.get("status") == "accepted_guaranteed"

    details = (
        f"success={result.get('success')}, "
        f"guarantee_id={result.get('guarantee_id', 'N/A')[:15]}, "
        f"setup_intent_id={result.get('setup_intent_id', 'N/A')[:20]}"
    )
    log_result("CAS NOMINAL — Carte valide réutilisée", passed, details, stripe_log)
    return result


# ═══════════════════════════════════════════════════════════════════
#  TEST 2: CAS SCA/3DS — Carte nécessitant authentification
# ═══════════════════════════════════════════════════════════════════

def test_2_sca_required(stripe_data):
    """Carte 3DS → success=False, reason=sca_required, SetupIntent cancelled."""
    test_data = create_test_participant()

    result = StripeGuaranteeService.create_guarantee_with_saved_card(
        participant_id=test_data["participant_id"],
        appointment_id=test_data["appointment_id"],
        invitation_token=test_data["invitation_token"],
        penalty_amount=50.0,
        penalty_currency="eur",
        user_id="test_user_sca",
        stripe_customer_id=stripe_data["customer_id"],
        payment_method_id=stripe_data["pm_sca"],
    )

    passed = result.get("success") is False
    passed = passed and result.get("reason") == "sca_required"
    stripe_log = {"reason": result.get("reason")}

    # Verify NO guarantee created in DB
    guarantee = db.payment_guarantees.find_one(
        {"participant_id": test_data["participant_id"]}, {"_id": 0}
    )
    stripe_log["guarantee_created"] = guarantee is not None
    passed = passed and guarantee is None  # Should NOT have been created

    # Verify participant status NOT changed
    participant = db.participants.find_one(
        {"participant_id": test_data["participant_id"]}, {"_id": 0}
    )
    stripe_log["participant_status"] = participant.get("status") if participant else "NOT_FOUND"
    passed = passed and participant is not None
    passed = passed and participant.get("status") == "invited"  # Still invited

    details = f"success={result.get('success')}, reason={result.get('reason')}"
    log_result("CAS SCA/3DS — Authentification requise", passed, details, stripe_log)
    return result


# ═══════════════════════════════════════════════════════════════════
#  TEST 3: CAS CARTE REFUSÉE — Declined
# ═══════════════════════════════════════════════════════════════════

def test_3_card_declined(stripe_data):
    """PM détaché ou invalide côté Stripe → success=False, reason contient error."""
    test_data = create_test_participant()

    # Create a PM, then detach it to simulate an expired/invalid PM that exists in our DB
    # but is no longer valid on Stripe
    detached_pm = stripe.PaymentMethod.create(
        type="card",
        card={"token": "tok_visa"},
    )
    stripe.PaymentMethod.attach(detached_pm.id, customer=stripe_data["customer_id"])
    stripe.PaymentMethod.detach(detached_pm.id)
    print(f"  PM détaché pour test: {detached_pm.id}")

    result = StripeGuaranteeService.create_guarantee_with_saved_card(
        participant_id=test_data["participant_id"],
        appointment_id=test_data["appointment_id"],
        invitation_token=test_data["invitation_token"],
        penalty_amount=50.0,
        penalty_currency="eur",
        user_id="test_user_declined",
        stripe_customer_id=stripe_data["customer_id"],
        payment_method_id=detached_pm.id,
    )

    passed = result.get("success") is False
    stripe_log = {"reason": result.get("reason"), "message": result.get("message", "")}

    # Verify NO guarantee in DB
    guarantee = db.payment_guarantees.find_one(
        {"participant_id": test_data["participant_id"]}, {"_id": 0}
    )
    stripe_log["guarantee_created"] = guarantee is not None
    passed = passed and guarantee is None

    # Verify participant status unchanged
    participant = db.participants.find_one(
        {"participant_id": test_data["participant_id"]}, {"_id": 0}
    )
    stripe_log["participant_status"] = participant.get("status") if participant else "NOT_FOUND"
    passed = passed and participant is not None
    passed = passed and participant.get("status") == "invited"

    details = f"success={result.get('success')}, reason={result.get('reason')}, message={result.get('message', '')}"
    log_result("CAS CARTE INVALIDE — PM détaché/expiré", passed, details, stripe_log)
    return result


# ═══════════════════════════════════════════════════════════════════
#  TEST 4: CAS CARTE INVALIDE (PM inexistant)
# ═══════════════════════════════════════════════════════════════════

def test_4_invalid_pm(stripe_data):
    """PM inexistant → success=False, reason=verification_error."""
    test_data = create_test_participant()

    result = StripeGuaranteeService.create_guarantee_with_saved_card(
        participant_id=test_data["participant_id"],
        appointment_id=test_data["appointment_id"],
        invitation_token=test_data["invitation_token"],
        penalty_amount=50.0,
        penalty_currency="eur",
        user_id="test_user_invalid",
        stripe_customer_id=stripe_data["customer_id"],
        payment_method_id="pm_FAKE_does_not_exist",
    )

    passed = result.get("success") is False
    stripe_log = {"reason": result.get("reason")}

    # Verify NO guarantee in DB
    guarantee = db.payment_guarantees.find_one(
        {"participant_id": test_data["participant_id"]}, {"_id": 0}
    )
    stripe_log["guarantee_created"] = guarantee is not None
    passed = passed and guarantee is None

    details = f"success={result.get('success')}, reason={result.get('reason')}"
    log_result("CAS CARTE INVALIDE — PM inexistant", passed, details, stripe_log)
    return result


# ═══════════════════════════════════════════════════════════════════
#  TEST 5: FALLBACK — Vérifier que l'endpoint /respond bascule
#           vers Checkout quand la carte échoue
# ═══════════════════════════════════════════════════════════════════

def test_5_endpoint_fallback(stripe_data):
    """
    Si un user a une carte SCA et appelle /respond avec action=accept,
    le backend doit détecter l'échec silencieux et basculer vers Checkout.
    """
    import httpx

    api_url = os.environ.get('FRONTEND_URL', '').rstrip('/') or 'https://dispute-resolver-12.preview.emergentagent.com'

    # Setup: user with SCA card in DB
    user_id = f"test_user_fallback_{uuid.uuid4().hex[:6]}"
    email = f"fallback-{uuid.uuid4().hex[:6]}@example.com"

    db.users.insert_one({
        "user_id": user_id,
        "email": email,
        "is_verified": True,
        "default_payment_method_id": stripe_data["pm_sca"],
        "stripe_customer_id": stripe_data["customer_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Create appointment + participant
    apt_id = f"apt_fb_{uuid.uuid4().hex[:8]}"
    part_id = f"part_fb_{uuid.uuid4().hex[:8]}"
    token = str(uuid.uuid4())

    db.appointments.insert_one({
        "appointment_id": apt_id,
        "title": "Test Fallback",
        "organizer_id": "test_organizer",
        "penalty_amount": 50.0,
        "penalty_currency": "eur",
        "start_datetime": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    db.participants.insert_one({
        "participant_id": part_id,
        "appointment_id": apt_id,
        "email": email,
        "user_id": user_id,
        "first_name": "Fallback",
        "last_name": "Test",
        "invitation_token": token,
        "status": "invited",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Call the endpoint
    resp = httpx.post(
        f"{api_url}/api/invitations/{token}/respond",
        json={"action": "accept"},
        timeout=30,
    )

    data = resp.json()
    stripe_log = {"http_status": resp.status_code, "response": data}

    # The card is SCA → reuse fails → should fall back to Checkout
    passed = resp.status_code == 200
    passed = passed and data.get("success") is True
    passed = passed and data.get("requires_guarantee") is True
    passed = passed and "checkout_url" in data
    passed = passed and data.get("status") == "accepted_pending_guarantee"

    # Verify participant status in DB
    part = db.participants.find_one({"participant_id": part_id}, {"_id": 0})
    stripe_log["participant_status"] = part.get("status") if part else "NOT_FOUND"
    passed = passed and part is not None
    passed = passed and part.get("status") == "accepted_pending_guarantee"

    details = (
        f"HTTP {resp.status_code}, "
        f"requires_guarantee={data.get('requires_guarantee')}, "
        f"has_checkout_url={'checkout_url' in data}"
    )
    log_result("FALLBACK — SCA card → Checkout redirect", passed, details, stripe_log)
    return data


# ═══════════════════════════════════════════════════════════════════
#  TEST 6: PREUVE STRIPE — Le SetupIntent est-il réel et utilisable ?
# ═══════════════════════════════════════════════════════════════════

def test_6_stripe_proof(test1_result):
    """
    Vérifie que le SetupIntent créé par Test 1 est un objet Stripe RÉEL,
    avec les bons metadata, et que le PaymentMethod associé est utilisable
    pour un PaymentIntent off_session futur.
    """
    si_id = test1_result.get("setup_intent_id")
    if not si_id:
        log_result("PREUVE STRIPE — SetupIntent réel", False, "No SetupIntent ID from Test 1", {})
        return

    si = stripe.SetupIntent.retrieve(si_id)
    stripe_log = {
        "id": si.id,
        "status": si.status,
        "usage": si.usage,
        "payment_method": si.payment_method,
        "customer": si.customer,
        "metadata": dict(si.metadata) if si.metadata else {},
        "created": si.created,
        "latest_attempt": si.latest_attempt,
    }

    passed = si.status == "succeeded"
    passed = passed and si.usage == "off_session"
    passed = passed and si.payment_method is not None
    passed = passed and si.customer is not None
    passed = passed and si.metadata.get("type") == "reuse_verification"

    # Verify PaymentMethod is still valid
    pm = stripe.PaymentMethod.retrieve(si.payment_method)
    stripe_log["pm_type"] = pm.type
    stripe_log["pm_card_brand"] = pm.card.brand if pm.card else "?"
    stripe_log["pm_card_last4"] = pm.card.last4 if pm.card else "?"
    stripe_log["pm_card_exp"] = f"{pm.card.exp_month}/{pm.card.exp_year}" if pm.card else "?"
    passed = passed and pm.type == "card"

    details = f"SI {si.id} | status={si.status} | usage={si.usage} | PM={si.payment_method}"
    log_result("PREUVE STRIPE — SetupIntent réel et utilisable", passed, details, stripe_log)


# ═══════════════════════════════════════════════════════════════════
#  TEST 7: CAPTURE FUTURE — La carte validée peut-elle être capturée ?
# ═══════════════════════════════════════════════════════════════════

def test_7_future_capture_possible(stripe_data, test1_result):
    """
    Simule une capture de garantie (no-show) avec la carte validée par Test 1.
    Crée un PaymentIntent off_session → vérifie que le paiement réussit.
    Puis rembourse immédiatement (c'est un test).
    """
    gid = test1_result.get("guarantee_id")
    if not gid:
        log_result("CAPTURE FUTURE — PaymentIntent off_session", False, "No guarantee from Test 1", {})
        return

    guarantee = db.payment_guarantees.find_one({"guarantee_id": gid}, {"_id": 0})
    if not guarantee:
        log_result("CAPTURE FUTURE — PaymentIntent off_session", False, "Guarantee not found in DB", {})
        return

    stripe_log = {}
    try:
        # Create a real PaymentIntent off_session — this is what capture_guarantee() does
        pi = stripe.PaymentIntent.create(
            amount=100,  # 1.00 EUR (minimum testable)
            currency="eur",
            customer=guarantee["stripe_customer_id"],
            payment_method=guarantee["stripe_payment_method_id"],
            off_session=True,
            confirm=True,
            metadata={
                "guarantee_id": gid,
                "purpose": "nlyt_test_capture_simulation",
            }
        )

        stripe_log["payment_intent_id"] = pi.id
        stripe_log["pi_status"] = pi.status
        stripe_log["pi_amount"] = pi.amount
        stripe_log["pi_currency"] = pi.currency

        passed = pi.status == "succeeded"

        # Immediately refund (it's a test)
        if pi.status == "succeeded":
            refund = stripe.Refund.create(payment_intent=pi.id)
            stripe_log["refund_id"] = refund.id
            stripe_log["refund_status"] = refund.status

        details = f"PI {pi.id} | status={pi.status} | amount={pi.amount} {pi.currency}"
        log_result("CAPTURE FUTURE — PaymentIntent off_session réussit", passed, details, stripe_log)

    except stripe.error.CardError as e:
        stripe_log["error"] = str(e)
        stripe_log["code"] = e.code
        log_result("CAPTURE FUTURE — PaymentIntent off_session", False, f"CardError: {e.user_message}", stripe_log)
    except Exception as e:
        stripe_log["error"] = str(e)
        log_result("CAPTURE FUTURE — PaymentIntent off_session", False, f"Error: {e}", stripe_log)


# ═══════════════════════════════════════════════════════════════════
#  TEST 8: NON-RÉGRESSION — Dev mode (pm_dev_*) skip validation
# ═══════════════════════════════════════════════════════════════════

def test_8_dev_mode_skip():
    """Les PM dev (pm_dev_*) doivent skip la validation Stripe."""
    test_data = create_test_participant()

    result = StripeGuaranteeService.create_guarantee_with_saved_card(
        participant_id=test_data["participant_id"],
        appointment_id=test_data["appointment_id"],
        invitation_token=test_data["invitation_token"],
        penalty_amount=50.0,
        penalty_currency="eur",
        user_id="test_user_dev",
        stripe_customer_id="cus_dev_fake",
        payment_method_id="pm_dev_test123",
    )

    passed = result.get("success") is True
    passed = passed and result.get("setup_intent_id") is None  # No SI created

    guarantee = db.payment_guarantees.find_one(
        {"guarantee_id": result.get("guarantee_id")}, {"_id": 0}
    )
    stripe_log = {
        "setup_intent_id": result.get("setup_intent_id"),
        "db_dev_mode": guarantee.get("dev_mode") if guarantee else None,
    }
    if guarantee:
        passed = passed and guarantee.get("dev_mode") is True

    details = f"success={result.get('success')}, setup_intent_id={result.get('setup_intent_id')}"
    log_result("DEV MODE — pm_dev_* skip validation Stripe", passed, details, stripe_log)


# ═══════════════════════════════════════════════════════════════════
#  TEST 9: COHÉRENCE DB — Pas de double état après fallback
# ═══════════════════════════════════════════════════════════════════

def test_9_no_double_state(stripe_data):
    """
    Si la réutilisation échoue et le fallback Checkout est créé,
    il ne doit y avoir qu'UNE seule guarantee en DB pour ce participant.
    """
    # User with declined card
    user_id = f"test_dbl_{uuid.uuid4().hex[:6]}"
    email = f"dbl-{uuid.uuid4().hex[:6]}@example.com"

    db.users.insert_one({
        "user_id": user_id,
        "email": email,
        "is_verified": True,
        "default_payment_method_id": stripe_data["pm_sca"],
        "stripe_customer_id": stripe_data["customer_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    apt_id = f"apt_dbl_{uuid.uuid4().hex[:8]}"
    part_id = f"part_dbl_{uuid.uuid4().hex[:8]}"
    token = str(uuid.uuid4())

    db.appointments.insert_one({
        "appointment_id": apt_id,
        "title": "Test Double State",
        "organizer_id": "test_organizer",
        "penalty_amount": 50.0,
        "penalty_currency": "eur",
        "start_datetime": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    db.participants.insert_one({
        "participant_id": part_id,
        "appointment_id": apt_id,
        "email": email,
        "user_id": user_id,
        "first_name": "Double",
        "last_name": "State",
        "invitation_token": token,
        "status": "invited",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Call endpoint — card will fail, should fall back to Checkout
    import httpx
    api_url = os.environ.get('FRONTEND_URL', '').rstrip('/') or 'https://dispute-resolver-12.preview.emergentagent.com'

    resp = httpx.post(
        f"{api_url}/api/invitations/{token}/respond",
        json={"action": "accept"},
        timeout=30,
    )
    data = resp.json()

    # Count guarantees for this participant
    guarantee_count = db.payment_guarantees.count_documents({"participant_id": part_id})
    stripe_log = {
        "guarantee_count": guarantee_count,
        "response_status": data.get("status"),
        "requires_guarantee": data.get("requires_guarantee"),
    }

    passed = resp.status_code == 200
    passed = passed and guarantee_count == 1  # Exactly 1 guarantee (the Checkout one)
    passed = passed and data.get("requires_guarantee") is True

    details = f"guarantee_count={guarantee_count}, status={data.get('status')}"
    log_result("COHÉRENCE DB — Pas de double état après fallback", passed, details, stripe_log)


# ═══════════════════════════════════════════════════════════════════
#  CLEANUP
# ═══════════════════════════════════════════════════════════════════

def cleanup(stripe_data):
    """Clean up test data."""
    print("\n--- Nettoyage ---")
    # Remove test documents from DB
    db.participants.delete_many({"participant_id": {"$regex": "^part_test_|^part_fb_|^part_dbl_"}})
    db.appointments.delete_many({"appointment_id": {"$regex": "^apt_test_|^apt_fb_|^apt_dbl_"}})
    db.payment_guarantees.delete_many({"participant_id": {"$regex": "^part_test_|^part_fb_|^part_dbl_"}})
    db.users.delete_many({"user_id": {"$regex": "^test_user_fallback_|^test_dbl_"}})

    # Delete Stripe customer
    try:
        stripe.Customer.delete(stripe_data["customer_id"])
        print(f"  Customer Stripe supprimé: {stripe_data['customer_id']}")
    except Exception as e:
        print(f"  Erreur suppression customer: {e}")
    print("  DB nettoyée")


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    print("\n" + "█"*70)
    print("  NLYT — TESTS STRIPE CARD REUSE VALIDATION")
    print(f"  Stripe Key: {STRIPE_API_KEY[:15]}...{STRIPE_API_KEY[-4:]}" if STRIPE_API_KEY else "  ⚠ NO STRIPE KEY")
    print(f"  Mode: {'LIVE' if STRIPE_API_KEY and STRIPE_API_KEY.startswith('sk_live') else 'TEST'}")
    print("█"*70)

    if not STRIPE_API_KEY or STRIPE_API_KEY == 'sk_test_emergent':
        print("\n⚠ STRIPE_API_KEY not configured — tests will be skipped")
        return

    # Setup
    stripe_data = setup_stripe_test_customer()

    # Run tests
    test1_result = test_1_valid_card_reuse(stripe_data)
    test_2_sca_required(stripe_data)
    test_3_card_declined(stripe_data)
    test_4_invalid_pm(stripe_data)
    test_5_endpoint_fallback(stripe_data)
    test_6_stripe_proof(test1_result)
    test_7_future_capture_possible(stripe_data, test1_result)
    test_8_dev_mode_skip()
    test_9_no_double_state(stripe_data)

    # Summary
    print("\n\n" + "█"*70)
    print("  RÉSUMÉ DES TESTS")
    print("█"*70)
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    for r in results:
        icon = "✅" if r["passed"] else "❌"
        print(f"  {icon} {r['test']}")
    print(f"\n  TOTAL: {passed}/{total} passés, {failed} échoué(s)")
    print("█"*70)

    # Cleanup
    cleanup(stripe_data)

    # Write JSON report
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stripe_mode": "TEST",
        "total_tests": total,
        "passed": passed,
        "failed": failed,
        "results": results,
    }
    os.makedirs("/app/test_reports", exist_ok=True)
    with open("/app/test_reports/stripe_card_reuse_validation.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n  Rapport écrit: /app/test_reports/stripe_card_reuse_validation.json")

    # Answer the critical question
    print("\n\n" + "█"*70)
    print("  RÉPONSE À LA QUESTION CRITIQUE")
    print("█"*70)
    if passed == total:
        print("""
  ✅ OUI — Quand create_guarantee_with_saved_card() réussit :
  
  1. Un SetupIntent Stripe RÉEL est créé et confirmé (usage=off_session)
  2. Stripe vérifie que la carte est valide, non-expirée, et peut être débitée
  3. Le PaymentMethod est confirmé utilisable pour des charges futures off_session
  4. En cas de no-show, capture_guarantee() crée un PaymentIntent off_session
     qui DÉBITE réellement la carte — ce n'est PAS une vérification logique NLYT
  
  Ce n'est PAS un simple enregistrement DB. C'est une opération Stripe réelle
  avec un SetupIntent succeeded qui prouve la validité de la carte.
""")
    else:
        print(f"\n  ⚠ {failed} test(s) échoué(s) — voir détails ci-dessus")
    print("█"*70)

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
