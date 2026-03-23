# Phase 2 — Stripe Connect Express : Conception détaillée

## 1. DONNÉES UTILISATEUR

### Champs ajoutés au wallet (collection `wallets`)
Les données Connect vivent dans le wallet existant — pas de nouvelle collection.

```
stripe_connect_account_id:     "acct_xxx" | null       # ID Stripe du compte Express
stripe_connect_status:         enum (voir §1.1)         # Statut normalisé NLYT
stripe_connect_details_submitted: false                  # KYC soumis ?
stripe_connect_charges_enabled:   false                  # Peut recevoir des charges ?
stripe_connect_payouts_enabled:   false                  # Peut recevoir des payouts ?
stripe_connect_requirements:      {}                     # Infos manquantes signalées par Stripe
stripe_connect_created_at:     "ISO" | null
stripe_connect_onboarded_at:   "ISO" | null              # Date de première activation
```

### 1.1 Statuts Connect normalisés

```
not_started       → Aucun compte Stripe créé (défaut)
onboarding        → Compte créé, onboarding en cours (KYC pas terminé)
restricted        → Onboarding terminé mais Stripe exige des infos supplémentaires
active            → Compte pleinement opérationnel (details_submitted + charges + payouts)
disabled          → Compte désactivé par Stripe (fraude, compliance)
```

Transitions :
```
not_started ──→ onboarding        (POST /connect/onboard)
onboarding  ──→ active            (webhook account.updated: all flags true)
onboarding  ──→ restricted        (webhook: details_submitted but requirements pending)
active      ──→ restricted        (webhook: Stripe demande nouvelles infos)
restricted  ──→ active            (webhook: requirements satisfaites)
active      ──→ disabled          (webhook: charges_enabled=false)
disabled    ──→ active            (webhook: ré-activation par Stripe — rare)
```

---

## 2. FLOW D'ONBOARDING EXPRESS

### 2.1 Séquence complète

```
Utilisateur → Page Paramètres → "Recevoir des fonds"
  │
  ├─ 1. Frontend: POST /api/connect/onboard
  │
  ├─ 2. Backend:
  │    ├─ Si wallet.stripe_connect_account_id existe → skip création
  │    ├─ Sinon → stripe.Account.create(type="express")
  │    ├─ Sauvegarder account_id dans wallet
  │    └─ stripe.AccountLink.create(
  │         account=account_id,
  │         type="account_onboarding",
  │         return_url=FRONTEND/settings/wallet?connect=complete,
  │         refresh_url=FRONTEND/settings/wallet?connect=refresh
  │       )
  │
  ├─ 3. Frontend: redirect vers onboarding_url (Stripe hosted)
  │
  ├─ 4. Utilisateur complète KYC sur Stripe
  │
  ├─ 5. Stripe redirige vers return_url ou refresh_url
  │    ├─ ?connect=complete → Frontend affiche "Vérification en cours"
  │    └─ ?connect=refresh → Frontend rappelle POST /api/connect/onboard (nouveau lien)
  │
  ├─ 6. En parallèle: Webhook account.updated arrive
  │    └─ Met à jour stripe_connect_status dans wallet
  │
  └─ 7. Frontend poll GET /api/wallet pour voir le statut final
```

### 2.2 Idempotence

| Scénario | Comportement |
|---|---|
| Premier appel | Crée Account Express + AccountLink |
| Appel avec account_id existant, status=onboarding | Crée nouveau AccountLink (pas de nouveau Account) |
| Appel avec account_id existant, status=active | Retourne statut sans créer de lien |
| Appel avec account_id existant, status=restricted | Crée AccountLink type=account_onboarding pour compléter |

### 2.3 Refresh / Retry

Le `refresh_url` est appelé quand le lien Stripe expire (durée de vie courte).
→ L'utilisateur est redirigé vers `/settings/wallet?connect=refresh`
→ Le frontend appelle automatiquement `POST /api/connect/onboard` pour obtenir un nouveau lien
→ Redirect vers le nouveau lien

---

## 3. WEBHOOKS STRIPE

### 3.1 Événements à écouter

| Événement | Logique métier |
|---|---|
| `account.updated` | Mettre à jour `stripe_connect_status`, `charges_enabled`, `payouts_enabled`, `requirements` dans le wallet. Transition de statut. |
| `account.application.deauthorized` | L'utilisateur a déconnecté NLYT de son Stripe → `status = disabled` |

### 3.2 Logique account.updated

```python
account = event.data.object
account_id = account.id

wallet = db.wallets.find_one({"stripe_connect_account_id": account_id})
if not wallet:
    return  # Compte inconnu — ignorer

updates = {
    "stripe_connect_details_submitted": account.details_submitted,
    "stripe_connect_charges_enabled": account.charges_enabled,
    "stripe_connect_payouts_enabled": account.payouts_enabled,
    "stripe_connect_requirements": {
        "currently_due": account.requirements.currently_due,
        "eventually_due": account.requirements.eventually_due,
        "past_due": account.requirements.past_due,
        "disabled_reason": account.requirements.disabled_reason,
    },
    "updated_at": now,
}

# Déterminer le statut normalisé
if account.charges_enabled and account.payouts_enabled and account.details_submitted:
    updates["stripe_connect_status"] = "active"
    if not wallet.get("stripe_connect_onboarded_at"):
        updates["stripe_connect_onboarded_at"] = now
elif account.details_submitted:
    updates["stripe_connect_status"] = "restricted"
elif not account.details_submitted:
    updates["stripe_connect_status"] = "onboarding"

if not account.charges_enabled and wallet.get("stripe_connect_status") == "active":
    updates["stripe_connect_status"] = "disabled"

db.wallets.update_one({"wallet_id": wallet["wallet_id"]}, {"$set": updates})
```

### 3.3 Compte devenu non-éligible après activation

Si Stripe passe `charges_enabled=false` sur un compte précédemment `active` :
- Le wallet passe en `disabled` ou `restricted`
- `can_payout` retourne `false` immédiatement
- Les distributions futures vers ce wallet sont suspendues
- L'utilisateur est notifié (email + banner UI) : "Votre compte de paiement nécessite une mise à jour"
- Il peut relancer l'onboarding via `POST /api/connect/onboard`

---

## 4. RÈGLES MÉTIER NLYT

### 4.1 Trois niveaux d'éligibilité

```
┌─────────────────────────────────────────────────────────────────┐
│  Niveau 1 : A un wallet (tout utilisateur inscrit)              │
│    → Peut voir son solde                                        │
│    → Peut recevoir des crédits internes (pending/available)     │
│    → NE PEUT PAS retirer                                        │
├─────────────────────────────────────────────────────────────────┤
│  Niveau 2 : Éligible distribution (wallet + engagement validé)  │
│    → Ses gains no-show sont crédités sur le wallet              │
│    → Même sans onboarding Stripe (les fonds s'accumulent)       │
├─────────────────────────────────────────────────────────────────┤
│  Niveau 3 : Éligible payout (wallet + Connect active + min 5€)  │
│    → Peut demander un retrait vers son compte bancaire          │
│    → Nécessite stripe_connect_status = "active"                 │
│    → Nécessite available_balance >= 500 centimes                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Blocages et messages

| Condition | Blocage | Message utilisateur |
|---|---|---|
| `connect_status = not_started` | Payout bloqué | "Configurez votre compte de paiement pour retirer vos fonds" |
| `connect_status = onboarding` | Payout bloqué | "Votre compte est en cours de vérification" |
| `connect_status = restricted` | Payout bloqué | "Stripe nécessite des informations complémentaires" |
| `connect_status = disabled` | Payout bloqué | "Votre compte de paiement a été désactivé — contactez le support" |
| `available_balance < 500` | Payout bloqué | "Montant minimum de retrait : 5€" |
| `connect_status = active` + `balance >= 500` | Payout autorisé | Bouton "Retirer" actif |

### 4.3 Impact Phase 3 (Distribution)

Lors de la distribution :
- Les gains sont TOUJOURS crédités sur le wallet interne (credit_pending)
- Même si l'utilisateur n'est PAS onboardé Stripe
- Le payout réel est décorrélé de la distribution
- Un utilisateur peut accumuler des gains et s'onboarder plus tard

---

## 5. API À EXPOSER

### 5.1 Endpoints

```
POST /api/connect/onboard
  → Crée ou reprend l'onboarding Stripe Connect Express
  → Retourne: { onboarding_url, connect_status }
  → Auth: Bearer token requis

GET  /api/connect/status
  → Retourne le statut Connect actuel
  → Retourne: { connect_status, details_submitted, charges_enabled, payouts_enabled, requirements }
  → Auth: Bearer token requis

POST /api/connect/dashboard
  → Génère un lien vers le dashboard Express Stripe (stripe.Account.create_login_link)
  → Retourne: { dashboard_url }
  → Auth: Bearer token requis
  → Précondition: connect_status = active

POST /api/webhooks/stripe
  → (Existant) Ajouter handler pour account.updated et account.application.deauthorized
```

### 5.2 Pas d'endpoint DELETE

La déconnexion Stripe se fait depuis le dashboard Stripe de l'utilisateur.
NLYT reçoit le webhook `account.application.deauthorized` et met à jour le statut.

---

## 6. IMPACTS FRONTEND / UX

### 6.1 Page Paramètres — Onglet Wallet

```
┌──────────────────────────────────────────────────────────┐
│  Mon Wallet NLYT                                          │
│                                                           │
│  Solde disponible     12,50 €                             │
│  En attente           25,00 €  (contestation en cours)    │
│                                                           │
│  ┌───────────────────────────────────────────────────┐    │
│  │  Compte de paiement                                │    │
│  │                                                     │    │
│  │  [not_started]                                      │    │
│  │  ⚠️ Configurez votre compte pour retirer vos fonds │    │
│  │  [Configurer mon compte →]                          │    │
│  │                                                     │    │
│  │  [active]                                           │    │
│  │  ✅ Compte vérifié — prêt pour les retraits        │    │
│  │  [Accéder à mon dashboard Stripe →]                 │    │
│  │  [Retirer 12,50 € →] (si >= 5€)                    │    │
│  └───────────────────────────────────────────────────┘    │
│                                                           │
│  Historique des transactions                               │
│  ├─ [credit_pending]  +25,00 €  No-show RDV 15/03        │
│  ├─ [credit_available] +12,50 €  Distribution confirmée   │
│  └─ ...                                                    │
└──────────────────────────────────────────────────────────┘
```

### 6.2 Composants à créer

```
pages/settings/WalletPage.js          → Page complète wallet + Connect
components/wallet/ConnectStatusCard.js → Carte statut onboarding
components/wallet/TransactionHistory.js → Historique ledger
```

### 6.3 Emails / Notifications

| Événement | Email |
|---|---|
| Connect activé | "Votre compte de paiement est vérifié" |
| Connect restricted | "Action requise : complétez votre vérification" |
| Connect disabled | "Votre compte de paiement a été désactivé" |

---

## 7. CAS LIMITES

| Cas | Comportement |
|---|---|
| Utilisateur déjà onboardé (active) | `POST /onboard` retourne `{ connect_status: "active" }` sans créer de lien |
| Création multiple | Idempotent : même `stripe_connect_account_id` réutilisé |
| Onboarding interrompu | `refresh_url` rappelle `/onboard` → nouveau lien |
| Compte restricted | Banner UI + bouton "Compléter vérification" → `/onboard` |
| Compte désactivé après activation | Banner rouge + email. Payout bloqué. Wallet intact. |
| Orga sur RDV A, participant sur RDV B | Même wallet, même compte Connect — rôle indépendant du wallet |
| Éligible compensation, pas onboardé | Gains crédités sur wallet (pending → available). Payout bloqué jusqu'à onboarding. |
| Onboarding en dev mode (pas de vraie clé Stripe) | Simulation : `stripe_connect_status` peut être mis à "active" manuellement via debug endpoint |

---

## 8. PLAN D'IMPLÉMENTATION PHASE 2

### Étape 2.1 — Backend Connect routes
- `routers/connect_routes.py` : POST /onboard, GET /status, POST /dashboard
- Logique idempotente de création/reprise
- Tests curl

### Étape 2.2 — Webhook account.updated
- Ajouter handler dans `webhooks.py`
- Mise à jour wallet (statut, flags, requirements)
- Test via Stripe CLI ou simulation

### Étape 2.3 — Frontend WalletPage
- Page `/settings/wallet`
- ConnectStatusCard (statut + actions)
- TransactionHistory (ledger)
- Navigation depuis Paramètres

### Étape 2.4 — Tests
- Testing agent : endpoints Connect + webhook + wallet status
- Cas limites : double onboard, refresh, restricted

### Étape 2.5 — Mode dev
- Si `STRIPE_API_KEY` absent ou `sk_test_emergent` → simulation
- Endpoint dev pour simuler `account.updated`
