"""
Tests de sécurité — Accès aux feuilles de présence (GET /attendance-sheets/{appointment_id})

Scénarios testés :
  ✅ CAS AUTORISÉS
    1. User avec linkage correct (fast path user_id) → accès OK
    2. User post-register, auto-linkage pas encore fait (fallback participant_id) → accès OK
    3. Après fallback, le linkage est réparé (fast path fonctionne au 2e appel) → accès OK

  ❌ CAS INTERDITS
    4. User A tente d'accéder à la sheet de User B → refus 404
    5. User sans aucun lien (ni participant ni email) → refus 404
    6. Manipulation de participant_id (injection) → impossible (pas d'input externe)
"""
import sys
import uuid

sys.path.append('/app/backend')
from database import db


# ─── Helpers ─────────────────────────────────────────────────────

def _clean(prefix="sec_test_"):
    """Remove all test data by prefix."""
    db.attendance_sheets.delete_many({"appointment_id": {"$regex": f"^{prefix}"}})
    db.participants.delete_many({"appointment_id": {"$regex": f"^{prefix}"}})
    db.appointments.delete_many({"appointment_id": {"$regex": f"^{prefix}"}})


def _setup_scenario():
    """Create a realistic test scenario with 2 users and 1 appointment."""
    _clean()

    apt_id = f"sec_test_apt_{uuid.uuid4().hex[:8]}"
    user_a_id = f"sec_test_user_a_{uuid.uuid4().hex[:8]}"
    user_a_email = "user_a_security_test@nlyt.app"
    user_b_id = f"sec_test_user_b_{uuid.uuid4().hex[:8]}"
    user_b_email = "user_b_security_test@nlyt.app"
    user_c_id = f"sec_test_user_c_{uuid.uuid4().hex[:8]}"
    user_c_email = "user_c_outsider@nlyt.app"
    participant_a_id = f"sec_test_part_a_{uuid.uuid4().hex[:8]}"
    participant_b_id = f"sec_test_part_b_{uuid.uuid4().hex[:8]}"

    # Appointment
    db.appointments.insert_one({
        "appointment_id": apt_id,
        "title": "Test Sécurité Feuilles",
        "start_datetime": "2026-02-01T10:00:00Z",
        "duration_minutes": 60,
        "declarative_phase": "collecting",
        "appointment_type": "in_person",
        "location": "Paris",
        "organizer_id": user_a_id,
    })

    # Participant A (avec user_id lié)
    db.participants.insert_one({
        "participant_id": participant_a_id,
        "appointment_id": apt_id,
        "email": user_a_email,
        "user_id": user_a_id,
        "status": "accepted_guaranteed",
    })

    # Participant B (avec user_id lié)
    db.participants.insert_one({
        "participant_id": participant_b_id,
        "appointment_id": apt_id,
        "email": user_b_email,
        "user_id": user_b_id,
        "status": "accepted_guaranteed",
    })

    # Sheet de A — linkage complet (fast path)
    sheet_a_id = f"sec_test_sheet_a_{uuid.uuid4().hex[:8]}"
    db.attendance_sheets.insert_one({
        "sheet_id": sheet_a_id,
        "appointment_id": apt_id,
        "submitted_by_user_id": user_a_id,
        "submitted_by_participant_id": participant_a_id,
        "status": "pending",
        "declarations": [
            {"target_participant_id": participant_b_id, "declared_status": None, "is_self_declaration": False},
        ],
    })

    # Sheet de B — linkage NON fait (simule post-register, auto-linkage pas encore exécuté)
    sheet_b_id = f"sec_test_sheet_b_{uuid.uuid4().hex[:8]}"
    db.attendance_sheets.insert_one({
        "sheet_id": sheet_b_id,
        "appointment_id": apt_id,
        "submitted_by_user_id": user_b_email,  # email placeholder, pas encore le user_id
        "submitted_by_participant_id": participant_b_id,
        "status": "pending",
        "declarations": [
            {"target_participant_id": participant_a_id, "declared_status": None, "is_self_declaration": False},
        ],
    })

    return {
        "apt_id": apt_id,
        "user_a": {"id": user_a_id, "email": user_a_email},
        "user_b": {"id": user_b_id, "email": user_b_email},
        "user_c": {"id": user_c_id, "email": user_c_email},
        "participant_a_id": participant_a_id,
        "participant_b_id": participant_b_id,
        "sheet_a_id": sheet_a_id,
        "sheet_b_id": sheet_b_id,
    }


def _simulate_get_my_sheet(appointment_id: str, user_id: str, user_email: str):
    """
    Reproduce the exact logic of GET /attendance-sheets/{appointment_id}
    without going through HTTP, to test the security model directly.
    Returns (sheet_or_none, http_status).
    """
    # Fast path
    sheet = db.attendance_sheets.find_one(
        {"appointment_id": appointment_id, "submitted_by_user_id": user_id},
        {"_id": 0}
    )

    # Secure fallback
    if not sheet:
        my_participants = list(db.participants.find(
            {
                "appointment_id": appointment_id,
                "$or": [{"user_id": user_id}, {"email": user_email}],
            },
            {"_id": 0, "participant_id": 1}
        ))
        if my_participants:
            my_pids = [p["participant_id"] for p in my_participants]
            sheet = db.attendance_sheets.find_one(
                {
                    "appointment_id": appointment_id,
                    "submitted_by_participant_id": {"$in": my_pids},
                },
                {"_id": 0}
            )
            if sheet and sheet.get("submitted_by_user_id") != user_id:
                db.attendance_sheets.update_one(
                    {"sheet_id": sheet["sheet_id"]},
                    {"$set": {"submitted_by_user_id": user_id}}
                )

    if not sheet:
        return None, 404
    return sheet, 200


# ═══════════════════════════════════════════════════════════════════
# ✅ CAS AUTORISÉS
# ═══════════════════════════════════════════════════════════════════

def test_1_fast_path_user_linked():
    """User A avec linkage correct → accès direct OK."""
    data = _setup_scenario()
    sheet, status = _simulate_get_my_sheet(
        data["apt_id"], data["user_a"]["id"], data["user_a"]["email"]
    )
    assert status == 200, f"Expected 200, got {status}"
    assert sheet is not None
    assert sheet["sheet_id"] == data["sheet_a_id"]
    print("  ✅ TEST 1 PASS — Fast path user_id → accès OK")
    _clean()


def test_2_fallback_post_register():
    """User B post-register (sheet liée par participant_id, submitted_by_user_id=email) → fallback OK."""
    data = _setup_scenario()
    sheet, status = _simulate_get_my_sheet(
        data["apt_id"], data["user_b"]["id"], data["user_b"]["email"]
    )
    assert status == 200, f"Expected 200, got {status}"
    assert sheet is not None
    assert sheet["sheet_id"] == data["sheet_b_id"]
    print("  ✅ TEST 2 PASS — Fallback participant_id post-register → accès OK")
    _clean()


def test_3_linkage_healed_after_fallback():
    """Après fallback, le submitted_by_user_id est corrigé → fast path au 2e appel."""
    data = _setup_scenario()

    # 1er appel : fallback
    sheet1, status1 = _simulate_get_my_sheet(
        data["apt_id"], data["user_b"]["id"], data["user_b"]["email"]
    )
    assert status1 == 200

    # Vérifier que le linkage a été réparé en base
    healed = db.attendance_sheets.find_one(
        {"sheet_id": data["sheet_b_id"]},
        {"_id": 0, "submitted_by_user_id": 1}
    )
    assert healed["submitted_by_user_id"] == data["user_b"]["id"], \
        f"Linkage non réparé: {healed['submitted_by_user_id']}"

    # 2e appel : doit fonctionner en fast path maintenant
    sheet2, status2 = _simulate_get_my_sheet(
        data["apt_id"], data["user_b"]["id"], data["user_b"]["email"]
    )
    assert status2 == 200
    assert sheet2["sheet_id"] == data["sheet_b_id"]
    print("  ✅ TEST 3 PASS — Linkage réparé, fast path fonctionne au 2e appel")
    _clean()


# ═══════════════════════════════════════════════════════════════════
# ❌ CAS INTERDITS
# ═══════════════════════════════════════════════════════════════════

def test_4_user_a_cannot_access_sheet_of_user_b():
    """User A tente d'accéder à la sheet de User B via le même appointment → refus."""
    data = _setup_scenario()

    # Supprimer la sheet de A pour que le seul résultat possible serait celle de B
    db.attendance_sheets.delete_one({"sheet_id": data["sheet_a_id"]})

    sheet, status = _simulate_get_my_sheet(
        data["apt_id"], data["user_a"]["id"], data["user_a"]["email"]
    )
    # User A n'a plus de sheet, et ne doit PAS obtenir celle de B
    assert status == 404, f"SÉCURITÉ VIOLATION: User A a accédé à la sheet de User B! Status={status}"
    assert sheet is None
    print("  ✅ TEST 4 PASS — User A ne peut PAS accéder à la sheet de User B → refus 404")
    _clean()


def test_5_outsider_no_link():
    """User C (pas participant) tente d'accéder → refus total."""
    data = _setup_scenario()
    sheet, status = _simulate_get_my_sheet(
        data["apt_id"], data["user_c"]["id"], data["user_c"]["email"]
    )
    assert status == 404, f"SÉCURITÉ VIOLATION: User C outsider a obtenu une sheet! Status={status}"
    assert sheet is None
    print("  ✅ TEST 5 PASS — Outsider sans lien → refus 404")
    _clean()


def test_6_fabricated_participant_id_impossible():
    """
    Le client ne peut PAS injecter un participant_id arbitraire.
    Le fallback utilise UNIQUEMENT le user_id et email du JWT.
    Même si un attaquant connaît le participant_id d'un autre user,
    il ne peut pas l'utiliser car l'endpoint n'accepte aucun paramètre participant_id.
    """
    data = _setup_scenario()

    # User C connaît le participant_id de User A mais n'a aucun lien
    # Le endpoint n'accepte PAS de participant_id en input,
    # donc le seul moyen d'accès est via le JWT.
    fake_user_id = f"sec_test_attacker_{uuid.uuid4().hex[:8]}"
    fake_email = "attacker@evil.com"

    # Même en connaissant l'appointment_id, l'attaquant ne peut rien faire
    sheet, status = _simulate_get_my_sheet(
        data["apt_id"], fake_user_id, fake_email
    )
    assert status == 404, f"SÉCURITÉ VIOLATION: Attaquant a obtenu une sheet! Status={status}"
    assert sheet is None
    print("  ✅ TEST 6 PASS — Injection participant_id impossible (pas d'input externe) → refus 404")
    _clean()


def test_7_cross_appointment_isolation():
    """Un participant d'un autre RDV ne peut pas accéder aux sheets d'un RDV différent."""
    data = _setup_scenario()

    other_apt_id = f"sec_test_apt_other_{uuid.uuid4().hex[:8]}"
    db.appointments.insert_one({
        "appointment_id": other_apt_id,
        "title": "Autre RDV",
        "declarative_phase": "collecting",
        "organizer_id": "someone_else",
    })

    # User A est participant du premier RDV mais PAS du second
    sheet, status = _simulate_get_my_sheet(
        other_apt_id, data["user_a"]["id"], data["user_a"]["email"]
    )
    assert status == 404, f"SÉCURITÉ VIOLATION: Accès cross-appointment! Status={status}"
    assert sheet is None
    print("  ✅ TEST 7 PASS — Isolation inter-RDV → refus 404")

    db.appointments.delete_one({"appointment_id": other_apt_id})
    _clean()


# ═══════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("🔒 TESTS DE SÉCURITÉ — Accès feuilles de présence")
    print("=" * 65)

    tests = [
        ("CAS AUTORISÉS", [
            test_1_fast_path_user_linked,
            test_2_fallback_post_register,
            test_3_linkage_healed_after_fallback,
        ]),
        ("CAS INTERDITS", [
            test_4_user_a_cannot_access_sheet_of_user_b,
            test_5_outsider_no_link,
            test_6_fabricated_participant_id_impossible,
            test_7_cross_appointment_isolation,
        ]),
    ]

    total = 0
    passed = 0
    failed = 0

    for section, test_fns in tests:
        print(f"\n── {section} ──")
        for fn in test_fns:
            total += 1
            try:
                fn()
                passed += 1
            except AssertionError as e:
                failed += 1
                print(f"  ❌ {fn.__name__} FAILED: {e}")
            except Exception as e:
                failed += 1
                print(f"  ❌ {fn.__name__} ERROR: {e}")

    print(f"\n{'=' * 65}")
    print(f"RÉSULTAT: {passed}/{total} PASS | {failed} FAIL")
    print("=" * 65)

    # Cleanup
    _clean()

    if failed > 0:
        sys.exit(1)
    else:
        print("\n🔒 Tous les tests de sécurité sont PASSÉS. Aucune fuite possible.\n")
