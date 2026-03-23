# NLYT Stripe Connect — Architecture Technique

## 1. ÉTAT ACTUEL (Ce qui existe déjà)

### Guarantee Flow existant
```
Participant accepte → Stripe Checkout (setup mode) → payment_method sauvé
  → status: "completed" (prêt à capturer)
```

### Modèle de distribution existant (dans chaque appointment)
```
penalty_amount:                 ex: 50€
platform_commission_percent:    ex: 20% (fixé serveur, non-modifiable)
affected_compensation_percent:  ex: 50% (part "dédommagement")
charity_percent:                ex: 30% (part association)
```
Règle de validation: `affected_compensation_percent + charity_percent = 100 - platform_commission_percent`

### Ce qui manque
- Stripe Connect Express (onboarding organisateurs/participants)
- Wallet interne (ledger)
- Capture + hold + distribution différée
- Symétrie organisateur no-show
- Payouts réels

---

## 2. ARCHITECTURE CIBLE

### 2.1 Vue d'ensemble du flux financier

```
┌──────────────────────────────────────────────────────────────────┐
│  ÉVALUATION ASSIDUITÉ                                            │
│                                                                   │
│  on_time / present ──→ RELEASE (aucun débit)                     │
│  no_show ───────────→ CAPTURE → HOLD 15j → DISTRIBUTION          │
│  manual_review ─────→ FUNDS_ON_HOLD (aucune action)              │
│                        └→ organisateur décide → RELEASE ou CAPTURE│
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 Flux CAPTURE → DISTRIBUTION

```
JOUR J : Évaluation → no_show détecté
  │
  ├─ 1. Stripe PaymentIntent.create (off_session, confirm=true)
  │    → Débite la carte du no-show
  │    → Fonds arrivent sur le compte plateforme NLYT
  │
  ├─ 2. Créer DISTRIBUTION RECORD (status: "pending_contestation")
  │    → Calcul des parts selon paramètres du RDV
  │    → distribution_at = now + 15 jours
  │
  ├─ 3. Créditer les WALLETS INTERNES en "pending_balance"
  │    → Chaque bénéficiaire voit ses gains en attente
  │
JOUR J+15 : Scheduler exécute la distribution
  │
  ├─ 4. Déplacer pending_balance → available_balance (wallet)
  │
  ├─ 5. Marquer distribution comme "completed"
  │
  └─ 6. Les utilisateurs peuvent demander un PAYOUT
         → Stripe Transfer vers leur compte Connect Express
```

### 2.3 Symétrie Organisateur

```
Si ORGANISATEUR = no_show :
  ├─ Sa propre garantie est capturée (même flow)
  ├─ Sa part "affected_compensation" est redistribuée aux PARTICIPANTS présents
  │   (il ne peut pas se verser à lui-même)
  ├─ Part plateforme = identique
  └─ Part charité = identique
```

Exemple concret :
```
RDV: 50€, platform 20%, compensation 50%, charité 30%

CAS 1 - Participant no-show (normal):
  Plateforme NLYT:   10€ (20%)
  Organisateur:      25€ (50%)  → wallet organisateur
  Association:       15€ (30%)  → wallet association

CAS 2 - Organisateur no-show (symétrique):
  Plateforme NLYT:   10€ (20%)
  Participants:      25€ (50%)  → répartis entre participants présents
  Association:       15€ (30%)  → wallet association

CAS 3 - Organisateur no-show, 0% charité, 80% compensation:
  Plateforme NLYT:   10€ (20%)
  Participants:      40€ (80%)  → répartis entre participants présents
```

---

## 3. NOUVELLES ENTITÉS (MongoDB)

### 3.1 `wallets` (Wallet interne NLYT)
```json
{
  "wallet_id": "uuid",
  "user_id": "uuid",              // Lien vers users
  "wallet_type": "user",          // "user" | "charity" | "platform"
  "available_balance": 0,         // Solde disponible (en centimes)
  "pending_balance": 0,           // En attente contestation (en centimes)
  "currency": "eur",
  "stripe_connect_account_id": null, // Rempli après onboarding
  "stripe_connect_status": "not_started", // not_started | onboarding | active | restricted
  "stripe_connect_onboarding_url": null,
  "total_received": 0,            // Historique cumulé
  "total_withdrawn": 0,           // Historique cumulé
  "created_at": "ISO",
  "updated_at": "ISO"
}
```

### 3.2 `distributions` (Enregistrement de chaque redistribution)
```json
{
  "distribution_id": "uuid",
  "appointment_id": "uuid",
  "guarantee_id": "uuid",
  "no_show_participant_id": "uuid",  // Qui est absent (participant OU organisateur)
  "no_show_is_organizer": false,
  "capture_amount": 5000,            // En centimes
  "capture_currency": "eur",
  "stripe_payment_intent_id": "pi_xxx",
  "status": "pending_contestation",  // pending_contestation | distributing | completed | contested | cancelled
  "contestation_deadline": "ISO",    // now + 15 jours
  "distribution_rules": {
    "platform_percent": 20,
    "compensation_percent": 50,
    "charity_percent": 30
  },
  "beneficiaries": [
    {
      "wallet_id": "uuid",
      "user_id": "uuid",
      "role": "organizer",          // "organizer" | "participant" | "charity" | "platform"
      "amount": 2500,               // En centimes
      "status": "pending"           // pending | credited | failed
    }
  ],
  "captured_at": "ISO",
  "distributed_at": null,
  "created_at": "ISO"
}
```

### 3.3 `wallet_transactions` (Ledger)
```json
{
  "transaction_id": "uuid",
  "wallet_id": "uuid",
  "type": "credit_pending",       // credit_pending | credit_available | debit_payout | debit_refund
  "amount": 2500,                 // En centimes (toujours positif)
  "currency": "eur",
  "reference_type": "distribution", // distribution | payout | refund
  "reference_id": "uuid",          // distribution_id ou payout_id
  "description": "Dédommagement — RDV du 15/03/2026",
  "created_at": "ISO"
}
```

### 3.4 `payouts` (Retraits vers Stripe Connect)
```json
{
  "payout_id": "uuid",
  "wallet_id": "uuid",
  "user_id": "uuid",
  "amount": 2500,
  "currency": "eur",
  "stripe_transfer_id": null,     // Rempli après transfert
  "status": "requested",          // requested | processing | completed | failed
  "requested_at": "ISO",
  "completed_at": null
}
```

---

## 4. STRIPE CONNECT EXPRESS — ONBOARDING

### Flow
```
Utilisateur → Page Paramètres → "Recevoir des fonds"
  → Backend crée un Account (type: "express")
  → Backend crée un AccountLink (onboarding URL)
  → Utilisateur redirigé vers Stripe (KYC, IBAN, etc.)
  → Retour vers NLYT → Webhook account.updated
  → stripe_connect_status = "active"
```

### API Stripe utilisées
```
stripe.Account.create(type="express", country="FR", email=...)
stripe.AccountLink.create(account=..., type="account_onboarding", ...)
stripe.Transfer.create(amount=..., currency=..., destination=account_id)
```

### Contrainte
- Aucun transfert possible tant que `stripe_connect_status != "active"`
- Le payout est bloqué si l'utilisateur n'est pas onboardé

---

## 5. IMPACTS SUR L'EXISTANT

### 5.1 Backend — Nouveaux fichiers
```
services/wallet_service.py          → CRUD wallet + transactions
services/distribution_service.py    → Calcul + exécution des distributions
routers/wallet_routes.py            → GET /wallet, POST /wallet/payout
routers/connect_routes.py           → Onboarding Stripe Connect Express
```

### 5.2 Backend — Fichiers modifiés
```
services/attendance_service.py      → Après évaluation, déclenche capture/release
services/stripe_guarantee_service.py → Ajout logique hold + distribution record
routers/webhooks.py                 → Gérer account.updated (Connect)
scheduler.py                        → Job: exécuter distributions après 15j
```

### 5.3 Frontend — Nouvelles pages/composants
```
pages/settings/WalletSettings.js     → Solde, historique, payout, onboarding Connect
pages/appointments/DistributionPanel.js → Détail distribution sur AppointmentDetail
```

### 5.4 Schémas existants — impact minimal
Le modèle `CreateAppointment` contient déjà :
- `penalty_amount`, `penalty_currency`
- `affected_compensation_percent`, `platform_commission_percent`, `charity_percent`
- `charity_association_id`

→ Pas de changement de schéma pour la création de RDV.

---

## 6. RISQUES ET EDGE CASES

### 6.1 Compliance
| Risque | Mitigation |
|---|---|
| Transfert vers non-onboardé | Blocage systématique : payout impossible sans `stripe_connect_status = active` |
| Double capture | Flag `distribution_id` sur guarantee + check idempotent |
| Contestation pendant hold | Status `contested` bloque la distribution, passe en revue manuelle |

### 6.2 Edge Cases
| Cas | Comportement |
|---|---|
| Organisateur no-show, aucun participant présent | Pas de part "compensation" distribuée (reste sur plateforme) |
| Organisateur no-show, 1 seul participant | 100% de la part compensation va au participant |
| `manual_review` → organisateur classe `on_time` | Garantie libérée, aucune distribution |
| `manual_review` → organisateur classe `no_show` | Déclenche capture + distribution avec hold 15j |
| Participant conteste pendant les 15j | Distribution marquée `contested`, revue admin NLYT |
| Charity non onboardée Stripe Connect | Gains crédités sur wallet interne, payout bloqué jusqu'à onboarding |
| Dev mode (pas de clé Stripe) | Simulation complète comme l'existant (flag `dev_mode`) |

### 6.3 Symétrie — vérification anti-abus
| Règle | Implémentation |
|---|---|
| Organisateur ne peut pas se verser à lui-même en cas de no-show | `if no_show_is_organizer: skip beneficiary where role=organizer` |
| Part non-distribuable → répartie entre participants | Redistribution proportionnelle au nombre de participants présents |
| Pas de transfert externe | Seuls les `user_id` existants dans NLYT peuvent être bénéficiaires |

---

## 7. PLAN D'IMPLÉMENTATION (Ordre suggéré)

### Phase 1 — Fondations (wallet + ledger)
1. `database` → collections `wallets`, `wallet_transactions`
2. `wallet_service.py` → create, get, credit, debit
3. `wallet_routes.py` → GET /api/wallet (solde)
4. Auto-création wallet à l'inscription

### Phase 2 — Stripe Connect Express
5. `connect_routes.py` → onboarding flow
6. Frontend → page paramètres "Recevoir des fonds"
7. Webhook `account.updated` → mise à jour statut

### Phase 3 — Capture + Distribution
8. `distribution_service.py` → calcul parts, création records
9. Intégration dans `attendance_service` → post-évaluation
10. Scheduler → job distribution différée (15j)

### Phase 4 — Payouts
11. `wallet_routes.py` → POST /api/wallet/payout
12. Frontend → bouton retrait + historique

### Phase 5 — UI complète
13. `DistributionPanel.js` → sur AppointmentDetail
14. `WalletSettings.js` → page wallet complète
15. Emails de notification (capture, distribution, payout)
