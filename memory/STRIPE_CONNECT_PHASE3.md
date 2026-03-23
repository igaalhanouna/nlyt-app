# Phase 3 — Capture + Distribution : Conception détaillée

## A. ARCHITECTURE BACKEND

### Fichiers à créer
```
services/distribution_service.py    → Moteur de calcul + exécution des distributions
```

### Fichiers à modifier
```
services/attendance_service.py      → Hook post-évaluation: déclencher capture/release
scheduler.py                        → Nouveau job: finaliser les distributions en fin de hold
routers/wallet_routes.py            → Endpoints consultation distributions
```

### Collections MongoDB utilisées
```
distributions          (NOUVELLE) — Enregistrement de chaque redistribution
wallets                (existante) — Crédit pending/available
wallet_transactions    (existante) — Ledger append-only
payment_guarantees     (existante) — Statut capture/released
attendance_records     (existante) — Décision d'assiduité source
appointments           (existante) — Paramètres de distribution
participants           (existante) — Rôle organisateur/participant, user_id
```

### Relation entre entités

```
appointment
  ├─ participants[] ─────────┐
  ├─ penalty_amount          │
  ├─ affected_compensation_% │
  ├─ platform_commission_%   │
  ├─ charity_%               │
  └─ charity_association_id  │
                             │
attendance_record ←──────────┘
  ├─ outcome (no_show | on_time | manual_review | waived | late)
  ├─ participant_id
  └─ decided_by
        │
        ▼ (si outcome = no_show)
payment_guarantee (statut: completed → captured)
  ├─ penalty_amount (float, €)
  ├─ stripe_payment_intent_id
  └─ guarantee_id
        │
        ▼
distribution (NOUVELLE)
  ├─ appointment_id
  ├─ guarantee_id
  ├─ no_show_participant_id
  ├─ capture_amount_cents
  ├─ status: pending_hold → distributing → completed | contested | cancelled
  ├─ hold_expires_at (now + 15j)
  └─ beneficiaries[]
        │
        ▼ (pour chaque bénéficiaire)
wallet.pending_balance  (crédit immédiat)
wallet_transaction      (ledger: credit_pending)
        │
        ▼ (après 15j, si pas de contestation bloquante)
wallet.available_balance (pending → available)
wallet_transaction       (ledger: credit_available)
```

---

## B. MODÈLE DE DONNÉES

### B.1 Collection `distributions`

```json
{
  "distribution_id": "uuid",
  "appointment_id": "uuid",
  "guarantee_id": "uuid",

  "no_show_participant_id": "uuid",
  "no_show_user_id": "uuid",
  "no_show_is_organizer": false,

  "capture_amount_cents": 5000,
  "capture_currency": "eur",
  "stripe_payment_intent_id": "pi_xxx | pi_dev_xxx",

  "status": "pending_hold",
  // Statuts: pending_hold → distributing → completed
  //                        → contested → (manual resolution)
  //                        → cancelled (annulation / erreur)

  "distribution_rules": {
    "platform_commission_percent": 20.0,
    "affected_compensation_percent": 50.0,
    "charity_percent": 30.0
  },

  "beneficiaries": [
    {
      "beneficiary_id": "uuid",
      "wallet_id": "uuid",
      "user_id": "uuid",
      "role": "organizer",
      "amount_cents": 2500,
      "status": "credited_pending",
      "transaction_id": "uuid"
    },
    {
      "beneficiary_id": "uuid",
      "wallet_id": "uuid",
      "user_id": "uuid | null",
      "role": "platform",
      "amount_cents": 1000,
      "status": "credited_pending",
      "transaction_id": "uuid"
    },
    {
      "beneficiary_id": "uuid",
      "wallet_id": "uuid",
      "user_id": "uuid | null",
      "role": "charity",
      "amount_cents": 1500,
      "status": "credited_pending",
      "transaction_id": "uuid"
    }
  ],

  "hold_expires_at": "ISO (now + 15 jours)",
  "contested": false,
  "contested_at": null,
  "contested_by": null,
  "contest_reason": null,

  "captured_at": "ISO",
  "distributed_at": null,
  "completed_at": null,
  "cancelled_at": null,
  "cancel_reason": null,

  "created_at": "ISO",
  "updated_at": "ISO"
}
```

### B.2 Statuts de distribution

```
pending_hold        → Capturé, crédits en pending_balance, hold 15j actif
distributing        → Hold expiré, conversion pending→available en cours
completed           → Tous les crédits convertis en available_balance
contested           → Contestation déposée pendant le hold → bloque la distribution
cancelled           → Distribution annulée (erreur, refund, décision admin)
```

Transitions :
```
pending_hold ──→ distributing       (hold expiré + pas de contestation bloquante)
pending_hold ──→ contested          (contestation déposée pendant hold)
pending_hold ──→ cancelled          (refund admin, erreur capture)
distributing ──→ completed          (tous les wallets crédités en available)
contested    ──→ pending_hold       (contestation rejetée → reprend le hold)
contested    ──→ cancelled          (contestation acceptée → refund)
```

### B.3 Beneficiary roles

```
organizer       → Part compensation versée à l'organisateur (si participant no_show)
participant     → Part compensation versée au(x) participant(s) (si organisateur no_show)
platform        → Commission NLYT (toujours)
charity         → Part association (si configurée et > 0%)
```

### B.4 Beneficiary status

```
credited_pending    → Montant crédité en pending_balance (hold actif)
credited_available  → Montant converti en available_balance (hold terminé)
refunded            → Montant remboursé (contestation acceptée)
failed              → Échec du crédit (wallet introuvable — ne devrait pas arriver)
```

---

## C. MOTEUR DE CALCUL

### C.1 Entrées

```python
capture_amount_cents: int        # penalty_amount × 100 (ex: 5000 pour 50€)
platform_commission_percent: float   # ex: 20.0
affected_compensation_percent: float # ex: 50.0
charity_percent: float               # ex: 30.0
no_show_is_organizer: bool
present_participants: list[dict]     # participants avec outcome on_time ou late
```

### C.2 Calcul des parts

```python
def compute_distribution(capture_amount_cents, platform_pct, compensation_pct, charity_pct,
                         no_show_is_organizer, present_participants, organizer_user_id):
    """
    Calcul exact des parts en centimes entiers.
    Garantie: sum(parts) == capture_amount_cents (jamais de centime perdu ou créé).
    """

    # 1. Part plateforme (arrondi au centime inférieur)
    platform_cents = int(capture_amount_cents * platform_pct / 100)

    # 2. Part charité (arrondi au centime inférieur)
    charity_cents = int(capture_amount_cents * charity_pct / 100)

    # 3. Part compensation = reste après plateforme + charité
    #    (absorbe les centimes d'arrondi → garantie sum == total)
    compensation_cents = capture_amount_cents - platform_cents - charity_cents

    # 4. Répartition de la compensation
    beneficiaries = []

    if not no_show_is_organizer:
        # CAS NORMAL : participant no_show → compensation à l'organisateur
        beneficiaries.append({
            "user_id": organizer_user_id,
            "role": "organizer",
            "amount_cents": compensation_cents,
        })
    else:
        # CAS SYMÉTRIQUE : organisateur no_show
        # → compensation répartie entre participants présents
        # → l'organisateur NE PEUT PAS se verser à lui-même
        if present_participants:
            base = compensation_cents // len(present_participants)
            remainder = compensation_cents - (base * len(present_participants))
            for i, p in enumerate(present_participants):
                amount = base + (1 if i < remainder else 0)
                beneficiaries.append({
                    "user_id": p["user_id"],
                    "role": "participant",
                    "amount_cents": amount,
                })
        else:
            # Aucun participant présent → compensation reste à la plateforme
            platform_cents += compensation_cents
            compensation_cents = 0

    return platform_cents, charity_cents, compensation_cents, beneficiaries
```

### C.3 Règles d'arrondi

```
1. Platform et charity: arrondi inférieur (int() = floor pour les positifs)
2. Compensation = total - platform - charity (absorbe le reste)
3. Si répartition multi-participants: division euclidienne + reste distribué 1c par 1c
4. Invariant: sum(toutes les parts) == capture_amount_cents TOUJOURS
5. Aucun float dans les calculs de montants. Seuls les pourcentages sont des float.
```

### C.4 Exemples concrets

```
Exemple 1 — Participant no_show, 50€ (5000c), 20/50/30 :
  platform:     1000c (10€)
  compensation: 2500c (25€) → organisateur
  charity:      1500c (15€)
  total:        5000c ✓

Exemple 2 — Organisateur no_show, 50€, 20/50/30, 2 participants présents :
  platform:     1000c
  compensation: 2500c → 1250c chacun (2 participants)
  charity:      1500c
  total:        5000c ✓

Exemple 3 — Organisateur no_show, 33€ (3300c), 20/80/0, 3 participants :
  platform:     660c
  charity:      0c
  compensation: 2640c → 880c × 3 = 2640c
  total:        3300c ✓

Exemple 4 — Arrondi impair, 51€ (5100c), 20/50/30, 3 participants :
  platform:     1020c (int(5100 × 0.20))
  charity:      1530c (int(5100 × 0.30))
  compensation: 5100 - 1020 - 1530 = 2550c
  → 2550 / 3 = 850 × 3 = 2550c, reste 0
  total:        5100c ✓

Exemple 5 — Arrondi avec reste, 10€ (1000c), 20/50/30, 3 participants :
  platform:     200c
  charity:      300c
  compensation: 500c → 500 / 3 = 166 × 3 = 498, reste 2
  → participant 1: 168c, participant 2: 167c, participant 3: 166c
  → Erreur. Correction: 166 + 166 + 168 = 500c ✓
  total:        1000c ✓
```

---

## D. DÉCLENCHEMENT MÉTIER

### D.1 Séquence complète no_show

```
JOUR J — RDV se termine + grace period (30 min)
  │
  ├─ 1. ÉVALUATION ASSIDUITÉ (scheduler ou manuel)
  │    attendance_service.evaluate_appointment()
  │    → Crée attendance_records pour chaque participant
  │    → outcome = no_show | on_time | late | manual_review | waived
  │
  ├─ 2. POST-ÉVALUATION : hook dans attendance_service
  │    → Pour chaque outcome == "no_show" avec review_required == False :
  │      ├─ Chercher la payment_guarantee du participant (status=completed)
  │      ├─ Appeler capture_guarantee(guarantee_id, reason="no_show")
  │      ├─ Appeler distribution_service.create_distribution(...)
  │      │    ├─ Calcul des parts
  │      │    ├─ Créer le document `distributions`
  │      │    ├─ Créditer chaque bénéficiaire en pending_balance
  │      │    └─ Créer les wallet_transactions (credit_pending)
  │      └─ Marquer la distribution comme "pending_hold"
  │
  │    → Pour chaque outcome == "no_show" avec review_required == True :
  │      └─ Rien. L'organisateur devra reclassifier manuellement.
  │         Quand il confirme no_show via reclassify → même flow (§D.2)
  │
  │    → Pour chaque outcome == "on_time" ou "late" avec review_required == False :
  │      ├─ Chercher la payment_guarantee
  │      └─ Appeler release_guarantee(guarantee_id, reason="present")
  │
  │    → Pour chaque outcome == "manual_review" :
  │      └─ Rien. Garantie reste bloquée (status=completed).
  │
  ├─ 3. RECLASSIFICATION MANUELLE (si manual_review → no_show)
  │    → reclassify_participant(record_id, "no_show")
  │    → Hook post-reclassification déclenche capture + distribution
  │
JOUR J+15 — SCHEDULER HOLD EXPIRY
  │
  ├─ 4. distribution_service.finalize_expired_holds()
  │    → Trouve toutes distributions status=pending_hold, hold_expires_at <= now
  │    → Pour chaque distribution non contestée :
  │      ├─ Passe le status à "distributing"
  │      ├─ Pour chaque bénéficiaire :
  │      │   └─ confirm_pending_to_available(wallet_id, amount)
  │      ├─ Passe le status à "completed"
  │      └─ Crée les wallet_transactions (credit_available)
  │
  │    → Pour chaque distribution contestée :
  │      └─ Skip (attente résolution manuelle)
```

### D.2 Déclenchement post-reclassification

Quand un organisateur reclassifie un `manual_review` en `no_show` :

```python
# Dans attendance_service.reclassify_participant():
# Après mise à jour du record, si new_outcome == "no_show":
#   → Chercher guarantee + déclencher capture/distribution
#   → Même logique que le hook post-évaluation automatique
```

### D.3 Déclenchement release

Quand l'évaluation détermine `on_time` ou `late` avec haute confiance :

```python
# Post-évaluation:
# → Chercher la guarantee du participant
# → release_guarantee(guarantee_id, "present")
# → Aucune distribution créée
```

---

## E. CAS LIMITES

| # | Cas | Comportement | Guard |
|---|-----|-------------|-------|
| 1 | **Double exécution du moteur** | Idempotent. `distribution_service.create_distribution()` vérifie si une distribution existe déjà pour ce `guarantee_id`. Si oui, skip. | `db.distributions.find_one({"guarantee_id": gid})` |
| 2 | **Double capture Stripe** | `capture_guarantee()` vérifie que `status == "completed"` avant de capturer. Si déjà `captured`, retourne erreur. | Guard dans `stripe_guarantee_service.py` (existe déjà) |
| 3 | **Contestation pendant hold** | L'utilisateur conteste → `distribution.contested = True`, status → `contested`. Le scheduler skip cette distribution au J+15. Résolution manuelle par admin. | Champ `contested` sur la distribution |
| 4 | **Organisateur no_show, plusieurs participants présents** | Compensation répartie équitablement (division euclidienne + reste 1c). L'organisateur est exclu des bénéficiaires. | `no_show_is_organizer` check + `present_participants` list |
| 5 | **Organisateur no_show, 0 participants présents** | La part compensation est absorbée par la plateforme. Pas de bénéficiaire "participant". | `if not present_participants: platform += compensation` |
| 6 | **Bénéficiaire sans wallet** | Impossible normalement (wallet auto-créé à l'inscription). Fallback: `ensure_wallet()` avant crédit. | `wallet_service.ensure_wallet()` |
| 7 | **Bénéficiaire non onboardé Connect** | Gains crédités sur wallet interne normalement. Le payout réel sera bloqué en Phase 4 tant que Connect != active. Les fonds s'accumulent. | Pas de check Connect en Phase 3 |
| 8 | **Charité configurée mais pas de wallet** | Créer un wallet type="charity" pour l'association_id. Crédit en pending. | `ensure_wallet(charity_association_id, wallet_type="charity")` |
| 9 | **Échec partiel de distribution** | Si le crédit d'un bénéficiaire échoue, son `status` passe à `failed`. Les autres bénéficiaires restent `credited_pending`. Le système retente au prochain passage du scheduler. Distribution status reste `pending_hold`. | Bénéficiaire-level status tracking |
| 10 | **Refund / annulation post-capture** | Admin déclenche `cancel_distribution(distribution_id, reason)`. Appelle `debit_refund()` sur chaque wallet crédité. Distribution passe à `cancelled`. Le refund Stripe réel est hors scope Phase 3. | `distribution_service.cancel_distribution()` |
| 11 | **Incohérence assiduité ↔ financier** | Reclassification d'un `no_show` en `on_time` après capture → déclenche annulation de la distribution + release de la garantie. Log d'audit complet. | Hook dans `reclassify_participant()` |
| 12 | **Participant sans guarantee (accepted, pas accepted_guaranteed)** | Pas de capture possible. Outcome `no_show` enregistré mais aucun flux financier. Distribution non créée. | Guard: `guarantee.status == "completed"` requis |
| 13 | **penalty_amount = 0** | Pas de capture. Pas de distribution. L'évaluation d'assiduité se fait normalement. | Guard: `capture_amount_cents > 0` |

---

## F. API / INTÉGRATION

### F.1 Endpoints à créer

```
GET  /api/wallet/distributions
  → Liste les distributions touchant le wallet de l'utilisateur courant
  → (en tant que bénéficiaire OU en tant que no_show)
  → Auth: Bearer token
  → Réponse: { distributions: [...], total: int }

GET  /api/wallet/distributions/:distribution_id
  → Détail d'une distribution
  → Auth: Bearer token
  → Inclut: bénéficiaires, montants, statut, hold

GET  /api/appointments/:id/distributions
  → Distributions liées à un RDV (vue organisateur)
  → Auth: Bearer token (organisateur ou admin)
  → Réponse: { distributions: [...] }
```

### F.2 Endpoint de contestation (futur, préparé mais pas implémenté complètement)

```
POST /api/wallet/distributions/:distribution_id/contest
  → Body: { reason: "string" }
  → Passe distribution.contested = true
  → Auth: Bearer token (seul le no_show peut contester)
  → Précondition: status == pending_hold
```

### F.3 Hooks internes (pas d'API, appels internes)

```python
# Post-évaluation automatique:
attendance_service.evaluate_appointment()
  → distribution_service.process_attendance_outcomes(appointment_id)

# Post-reclassification manuelle:
attendance_service.reclassify_participant()
  → distribution_service.process_reclassification(record_id, new_outcome, previous_outcome)

# Scheduler hold expiry:
scheduler.distribution_hold_expiry_job()
  → distribution_service.finalize_expired_holds()
```

---

## G. FRONTEND / UX (Spécification pour implémentation future)

### G.1 WalletPage (déjà créée Phase 2) — À enrichir

```
Solde disponible     12,50 €     ← available_balance
En attente           25,00 €     ← pending_balance

Historique :
├─ +25,00 € en attente    "Dédommagement — No-show RDV du 15/03"     (credit_pending)
├─ +12,50 € disponible    "Distribution confirmée — RDV du 01/03"    (credit_available)
└─ ...
```

### G.2 Ce que voit un bénéficiaire

```
Crédit en attente :
  Montant : 25,00 €
  Source : Absence de [Nom] au RDV "[Titre]"
  En attente de : Fin du délai de contestation (15j)
  Date d'expiration du hold : 30/03/2026
  Statut : En attente
```

### G.3 Ce que voit le no_show

```
Pénalité capturée :
  Montant : 50,00 €
  RDV : "[Titre]" du 15/03/2026
  Motif : Absence détectée (no_show)
  Distribution :
    - Organisateur : 25,00 €
    - NLYT : 10,00 €
    - Association X : 15,00 €
  Statut : En attente de distribution (contestation possible jusqu'au 30/03)
  [Contester] (si status == pending_hold)
```

### G.4 Vue organisateur sur AppointmentDetail

```
Distribution des pénalités :
  ├─ [Participant A] — No-show — 50€ capturés
  │   ├─ Votre part : 25,00 € (en attente)
  │   ├─ NLYT : 10,00 €
  │   └─ Association : 15,00 €
  │   Statut : Pending hold (expire le 30/03)
  └─ [Participant B] — Présent — Garantie libérée
```

---

## H. PLAN D'IMPLÉMENTATION

### Étape 3.1 — Modèle de données + distribution_service.py (calcul pur)
- Créer `distribution_service.py`
- Implémenter `compute_distribution()` — logique de calcul pure (pas d'IO)
- Tester avec des cas unitaires (arrondi, symétrie, etc.)
- **Test** : `pytest tests/test_distribution_compute.py`

### Étape 3.2 — create_distribution() + intégration wallet
- Implémenter `create_distribution()` — crée le document + crédite les wallets
- Gère la création de wallet charity si nécessaire
- Idempotence sur `guarantee_id`
- **Test** : curl create_distribution avec données simulées, vérifier wallets et ledger

### Étape 3.3 — Hook post-évaluation (capture + release)
- Modifier `attendance_service.evaluate_appointment()` pour appeler le moteur
- Pour `no_show` (haute confiance) : capture_guarantee + create_distribution
- Pour `on_time`/`late` (haute confiance) : release_guarantee
- Pour `manual_review` : rien
- **Test** : simuler une évaluation avec no_show, vérifier guarantee captured + distribution créée

### Étape 3.4 — Hook post-reclassification
- Modifier `reclassify_participant()` pour déclencher capture/release/annulation
- Reclassification no_show → on_time = annuler distribution + release guarantee
- Reclassification manual_review → no_show = capture + distribution
- **Test** : reclassifier un participant, vérifier flux financier

### Étape 3.5 — Scheduler hold expiry
- Implémenter `finalize_expired_holds()`
- Ajouter job dans `scheduler.py` (toutes les 15 minutes)
- Convertit `pending_balance` → `available_balance` pour chaque bénéficiaire
- **Test** : créer distribution avec hold expiré, lancer job, vérifier conversion

### Étape 3.6 — Endpoints API (consultation + contestation)
- GET /api/wallet/distributions
- GET /api/wallet/distributions/:id
- GET /api/appointments/:id/distributions
- POST /api/wallet/distributions/:id/contest (structure seulement)
- **Test** : testing agent complet backend + frontend

### Étape 3.7 — Mode dev / simulation
- Si capture Stripe échoue (dev mode → `pi_dev_*`), le reste du flux fonctionne normalement
- Le capture_guarantee() existant gère déjà le dev mode
- La distribution fonctionne identiquement en dev et prod (seul le PI est simulé)
- Endpoint debug pour simuler une distribution complète (admin only)
- **Test** : flux complet en dev mode

---

## RÉSUMÉ DES INVARIANTS

```
1. sum(beneficiaries.amount_cents) == capture_amount_cents        TOUJOURS
2. Un guarantee_id ne peut avoir qu'une seule distribution        IDEMPOTENT
3. Un organisateur no_show ne reçoit jamais de compensation       SYMÉTRIE
4. Le ledger est append-only, jamais modifié                      AUDIT
5. Les montants sont toujours en centimes (int), jamais en float  PRÉCISION
6. La distribution crédite les wallets, pas Stripe                PHASE 3
7. Le payout Stripe réel est reporté à Phase 4                    SCOPE
8. La contestation bloque la finalisation, jamais la capture      SÉCURITÉ
```
