# Protocole de Test Webhooks Stripe — NLYT

---

## PARTIE A — CHECKLIST UTILISATEUR (Votre cote)

### A1. Configuration Webhook dans le Stripe Dashboard

**Ou :** https://dashboard.stripe.com/test/webhooks (mode Test)

**Etapes :**
1. Aller dans **Developers > Webhooks** (ou le lien ci-dessus)
2. Cliquer **"+ Add endpoint"**
3. Renseigner l'URL :
   ```
   https://litigation-mgmt.preview.emergentagent.com/api/webhooks/stripe
   ```
4. Dans **"Select events to listen to"**, cocher exactement ces evenements :
   - `checkout.session.completed`
   - `payment_intent.succeeded`
   - `transfer.paid`
   - `transfer.failed`
   - `transfer.reversed`
   - `account.updated`
   - `account.application.deauthorized`
5. Cliquer **"Add endpoint"**
6. **Verifier** : le statut doit etre "Enabled" (pastille verte)

### A2. Recuperer le Webhook Signing Secret

**Ou :** Sur la page du webhook que vous venez de creer

1. Cliquer sur l'endpoint cree
2. Cliquer **"Reveal" a cote de "Signing secret"**
3. Copier la valeur (format : `whsec_xxxxxxxxxxxxxxxx`)
4. **Me communiquer ce secret** — je mettrai a jour le backend `.env`

> **IMPORTANT** : Le secret actuel dans le backend (`whsec_GDO3dwYM3SSpViJWwmvIByFQnU9efFQY`) a ete configure precedemment. 
> Il faut verifier qu'il correspond bien au webhook pointe sur l'URL preview ci-dessus.
> Si vous creez un NOUVEAU webhook endpoint, le secret sera different et devra etre mis a jour.

### A3. Verification rapide

Apres configuration, dans le Stripe Dashboard :
- Allez sur l'endpoint webhook
- Cliquez **"Send test webhook"**
- Selectionnez `checkout.session.completed`
- Cliquez **"Send test webhook"**
- Resultat attendu : HTTP 200 dans le log Stripe + pas d'erreur

### A4. Installation Stripe CLI (optionnel, pour tests avances)

**Methode 1 — macOS :**
```bash
brew install stripe/stripe-cli/stripe
```

**Methode 2 — Linux / Windows :**
Telecharger depuis https://docs.stripe.com/stripe-cli

**Connexion :**
```bash
stripe login
# Suivre les instructions (ouverture navigateur, validation)
```

**Mode ecoute (forward des evenements a preview) :**
```bash
stripe listen --forward-to https://litigation-mgmt.preview.emergentagent.com/api/webhooks/stripe
```
> Ceci affiche un nouveau `whsec_xxx`. Il faut me le communiquer pour mettre a jour le backend.

---

## PARTIE B — PROTOCOLE DE TEST (W1 a W8)

### Legendes
- **Pre-requis** : Etat initial necessaire avant le test
- **Declenchement** : Comment provoquer l'evenement
- **Verif DB** : Ce qu'on doit trouver dans MongoDB apres
- **Verif Logs** : Lignes de log attendues (backend.err.log / backend.out.log)
- **Verif UI** : Ce que l'utilisateur voit dans l'application

---

### W1 — checkout.session.completed (Activation RDV Organisateur)

**Objectif :** Un organisateur complete sa garantie financiere. Le webhook active le RDV (envoi invitations, sync calendrier, creation reunion video).

**Pre-requis :**
- Un RDV existant en statut `pending_organizer_guarantee`
- Un participant organisateur avec `is_organizer: true` et une garantie en attente

**Declenchement :**
- **Via Dashboard** : L'organisateur complete le checkout Stripe normalement via l'UI
- **Via Stripe CLI** :
  ```bash
  stripe trigger checkout.session.completed \
    --override checkout_session:mode=setup \
    --override checkout_session:metadata.type=nlyt_guarantee \
    --override checkout_session:metadata.appointment_id=<APPOINTMENT_ID> \
    --override checkout_session:metadata.guarantee_id=<GUARANTEE_ID>
  ```

**Verif DB :**
- `stripe_events` : document cree avec `event_type: "checkout.session.completed"`
- `appointments` : statut passe de `pending_organizer_guarantee` a `active`
- `payment_guarantees` : garantie confirmee

**Verif Logs :**
```
INFO:webhooks:RECEIVED event_id=evt_xxx type=checkout.session.completed
INFO:webhooks:CHECKOUT event_id=evt_xxx mode=setup meta_type=nlyt_guarantee appointment_id=xxx guarantee_id=xxx
INFO:webhooks:ACTIVATION event_id=evt_xxx appointment_id=xxx organizer_id=xxx success=True
```

**Verif UI :** Le RDV apparait dans "A venir" avec le statut "Confirme"

---

### W2 — checkout.session.completed (Confirmation Participant)

**Objectif :** Un participant invite complete sa garantie. Le webhook confirme et envoie un email de confirmation.

**Pre-requis :**
- Un RDV actif avec une invitation en attente de garantie
- Le participant a un `participant_id` valide avec `is_organizer: false`

**Declenchement :**
- **Via UI** : Le participant clique "Accepter" et complete le checkout Stripe
- **Via Stripe CLI** : Meme commande que W1, avec le `participant_id` correspondant au participant (non-organisateur)

**Verif DB :**
- `stripe_events` : document cree
- `payment_guarantees` : garantie participant confirmee
- `participants` : `status` passe a `confirmed`

**Verif Logs :**
```
INFO:webhooks:RECEIVED event_id=evt_xxx type=checkout.session.completed
INFO:webhooks:CHECKOUT event_id=evt_xxx mode=setup meta_type=nlyt_guarantee ...
```
(Pas de ligne ACTIVATION car ce n'est pas l'organisateur)

**Verif UI :** Le participant voit le RDV confirme dans son calendrier

---

### W3 — transfer.paid (Retrait reussi)

**Objectif :** Stripe confirme qu'un Transfer (retrait wallet -> compte Connect) est complete. Le payout passe en `completed`.

**Pre-requis :**
- Un payout existant en statut `processing` dans la collection `payouts`
- Ce payout doit avoir un `stripe_transfer_id` correspondant

**Declenchement :**
- **Via Stripe CLI** :
  ```bash
  stripe trigger transfer.paid
  ```
  > Note : l'evenement CLI utilise un transfer_id fictif. Pour un test realiste, il faut d'abord creer un vrai payout via l'UI, puis attendre que Stripe envoie l'evenement automatiquement. Alternativement, on peut injecter manuellement :
  ```bash
  curl -X POST https://litigation-mgmt.preview.emergentagent.com/api/webhooks/stripe \
    -H "Content-Type: application/json" \
    -H "Stripe-Signature: <VALIDE_PAR_CLI>" \
    -d '{
      "id": "evt_test_transfer_paid",
      "type": "transfer.paid",
      "data": {
        "object": {
          "id": "<STRIPE_TRANSFER_ID_REEL>",
          "amount": 5000,
          "metadata": {
            "payout_id": "<PAYOUT_ID_REEL>",
            "user_id": "<USER_ID>",
            "source": "nlyt_payout"
          }
        }
      }
    }'
  ```

**Verif DB :**
- `payouts` : statut passe de `processing` a `completed`, champ `completed_at` rempli
- `stripe_events` : document cree avec `event_type: "transfer.paid"`

**Verif Logs :**
```
INFO:webhooks:RECEIVED event_id=evt_xxx type=transfer.paid
INFO:webhooks:TRANSFER_PAID event_id=evt_xxx transfer_id=tr_xxx payout_id=xxx user_id=xxx amount=5000
INFO:webhooks:TRANSFER_PAID_RESULT event_id=evt_xxx transfer_id=tr_xxx result={'success': True, 'payout_id': 'xxx'}
```

**Verif UI :** Dans la page Wallet, le retrait affiche "Complete" (vert)

---

### W4 — transfer.failed (Retrait echoue — re-credit wallet)

**Objectif :** Stripe signale qu'un Transfer a echoue. Le wallet est re-credite et le payout passe en `failed`.

**Pre-requis :**
- Un payout en statut `processing` avec un `stripe_transfer_id` valide
- Noter le `available_balance` du wallet AVANT le test

**Declenchement :**
- **Via Stripe CLI** :
  ```bash
  stripe trigger transfer.failed
  ```
- **Via Dashboard** : Provoquer un echec (compte Connect invalide, etc.)

**Verif DB :**
- `payouts` : statut passe a `failed`, `failure_reason` rempli, `failed_at` rempli
- `wallets` : `available_balance` re-credite du montant du payout, `total_withdrawn` decremente
- `wallet_transactions` : nouvelle entree `type: "credit_available"`, `reference_type: "payout_reversal"`
- `stripe_events` : document cree

**Verif Logs :**
```
WARNING:webhooks:TRANSFER_FAIL event_id=evt_xxx type=transfer.failed transfer_id=tr_xxx payout_id=xxx user_id=xxx failure=xxx
INFO:webhooks:TRANSFER_FAIL_RESULT event_id=evt_xxx transfer_id=tr_xxx result={'success': True, 'payout_id': 'xxx', 're_credited': True}
```

**Verif UI :** Wallet affiche le solde initial restaure + retrait marque "Echoue"

---

### W5 — transfer.reversed (Transfer inverse — re-credit wallet)

**Objectif :** Stripe a inverse un Transfer deja effectue. Meme logique que W4 (re-credit wallet).

**Pre-requis :** Identique a W4

**Declenchement :**
- **Via Stripe CLI** :
  ```bash
  stripe trigger transfer.reversed
  ```
  > Note: `transfer.reversed` n'est pas disponible nativement dans `stripe trigger`. Utilisez plutot :
  ```bash
  # Si CLI ne supporte pas, envoyer via le forward du listener en inversant manuellement le transfer dans le Dashboard
  ```
- **Via Dashboard** : Ouvrir un Transfer dans Payments > Transfers, cliquer "Reverse transfer"

**Verif DB :** Identique a W4

**Verif Logs :**
```
WARNING:webhooks:TRANSFER_FAIL event_id=evt_xxx type=transfer.reversed transfer_id=tr_xxx ...
INFO:webhooks:TRANSFER_FAIL_RESULT ...
```

**Verif UI :** Identique a W4

---

### W6 — Doublon (Idempotence Guard)

**Objectif :** Verifier que le meme evenement recu deux fois n'est traite qu'une seule fois.

**Pre-requis :** Avoir deja execute un test W1 a W5 avec un `event_id` connu (ex: `evt_test_transfer_paid`)

**Declenchement :**
- Envoyer exactement le meme payload que lors du test precedent (meme `id`)
- Via Stripe CLI : les events ont des IDs uniques, donc pour tester l'idempotence :
  ```bash
  # Methode 1 : Replay un evenement depuis le Dashboard
  stripe events resend evt_XXXXXX
  
  # Methode 2 : Le listener Stripe CLI renvoie parfois automatiquement en cas de retry
  ```

**Verif DB :**
- `stripe_events` : PAS de nouveau document (un seul pour cet event_id)
- `payouts` / `wallets` : AUCUN changement

**Verif Logs :**
```
INFO:webhooks:DUPLICATE event_id=evt_xxx type=transfer.paid — skipping
```

**Verif UI :** Aucun changement visible

---

### W7 — Signature invalide (Securite)

**Objectif :** Verifier qu'une requete sans signature valide est rejetee avec HTTP 400.

**Pre-requis :** Aucun

**Declenchement :**
```bash
curl -X POST https://litigation-mgmt.preview.emergentagent.com/api/webhooks/stripe \
  -H "Content-Type: application/json" \
  -H "Stripe-Signature: t=9999999999,v1=fake_signature_value" \
  -d '{"id":"evt_fake","type":"transfer.paid","data":{"object":{"id":"tr_fake"}}}'
```

**Verif DB :** AUCUNE ecriture dans `stripe_events`

**Verif Logs :**
```
ERROR:webhooks:SIGNATURE_INVALID error=...
```

**Verif UI :** Aucun impact

**Resultat HTTP attendu :** `400 Bad Request` avec `{"detail": "Invalid signature"}`

---

### W8 — account.updated (Mise a jour Connect KYC)

**Objectif :** Stripe notifie un changement de statut sur un compte Connect (ex: KYC valide).

**Pre-requis :**
- Un utilisateur avec un compte Stripe Connect lie (`stripe_connect_account_id` dans son wallet)

**Declenchement :**
- **Via Stripe CLI** :
  ```bash
  stripe trigger account.updated
  ```
- **Naturellement** : Quand un utilisateur complete son KYC sur Stripe, l'evenement est envoye automatiquement

**Verif DB :**
- `stripe_events` : document cree avec `event_type: "account.updated"`
- `wallets` : `stripe_connect_status` mis a jour selon le statut reel du compte

**Verif Logs :**
```
INFO:webhooks:RECEIVED event_id=evt_xxx type=account.updated
INFO:webhooks:CONNECT_UPDATE event_id=evt_xxx account_id=acct_xxx
INFO:webhooks:CONNECT_UPDATE_RESULT event_id=evt_xxx account_id=acct_xxx result={...}
```

**Verif UI :** Dans Parametres > Wallet, le statut Connect se met a jour

---

## PARTIE C — RESUME DES CAS ET INTERVENTION REQUISE

| Cas | Evenement | Votre intervention requise ? | Details |
|-----|-----------|------------------------------|---------|
| W1 | checkout.session.completed (orga) | OUI — creer un RDV via l'UI ou CLI | Le checkout genere l'event |
| W2 | checkout.session.completed (participant) | OUI — inviter un participant | Le participant complete le checkout |
| W3 | transfer.paid | OUI si test reel — lancer un retrait | Stripe envoie l'event automatiquement |
| W4 | transfer.failed | PARTIEL — necessite un compte Connect en echec ou CLI | CLI peut simuler |
| W5 | transfer.reversed | OUI — reverser manuellement dans Dashboard | Ou CLI si dispo |
| W6 | Doublon | NON — reproductible automatiquement | Rejouer un event deja traite |
| W7 | Signature invalide | NON — simple curl sans signature | Purement technique |
| W8 | account.updated | NON si CLI dispo / OUI si KYC reel | CLI peut simuler |

---

## PARTIE D — APPROCHE RECOMMANDEE

### Phase 1 : Tests techniques (sans intervention manuelle)
Executer W6 et W7 immediatement — ils ne necessitent aucun prealable.

### Phase 2 : Tests via Stripe CLI
Installer CLI, lancer `stripe listen --forward-to`, puis trigger W3, W4, W8.

### Phase 3 : Tests end-to-end reels
Creer un vrai RDV, completer le checkout, declencher un retrait pour valider W1, W2, W3 en conditions reelles.
