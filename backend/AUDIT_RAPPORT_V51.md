# AUDIT PRODUIT GLOBAL — NLYT Trustless V5.1
## Rapport Critique de Robustesse

**Date** : Février 2026  
**Scope** : Architecture complète (Backend, Services, Scheduler, Finance, UI)  
**Méthode** : Lecture exhaustive du code source → Identification des angles morts → Tests QA ciblés → Corrections

---

## A. CARTOGRAPHIE PRODUIT RÉELLE

### A.1 — Cycle de vie complet d'un rendez-vous

```
CRÉATION                        ACTIVATION                      VIE DU RDV
─────────                       ──────────                      ──────────
Organisateur                    Garantie org.                   Participants
crée un RDV                     validée                         répondent
     │                               │                               │
     ▼                               ▼                               ▼
┌──────────────────┐  ─────►  ┌──────────┐  ─── invitations ──►  ┌──────────────┐
│ pending_organizer│          │  active   │                       │   invited    │
│    _guarantee    │          │          │                       │      │       │
└──────────────────┘          └──────────┘                       │      ▼       │
                                                                │  accept/     │
                                                                │  decline     │
                                                                └──────┬───────┘
                                                                       │
                                                         ┌─────────────┼─────────────┐
                                                         ▼             ▼             ▼
                                                    ┌─────────┐  ┌──────────┐  ┌─────────┐
                                                    │declined │  │accepted_ │  │accepted │
                                                    │(waived) │  │pending_  │  │(si 0€)  │
                                                    └─────────┘  │guarantee │  └─────────┘
                                                                 └────┬─────┘
                                                                      │ Stripe
                                                                      ▼
                                                                 ┌──────────┐
                                                                 │accepted_ │
                                                                 │guaranteed│
                                                                 └──────────┘
```

### A.2 — Phase post-RDV : Évaluation → Déclaratif → Litiges → Finance

```
FIN DU RDV (+ 10 min grace)
         │
         ▼
┌─────────────────────┐
│ evaluate_appointment│ ◄─── scheduler (toutes les 10 min)
│    (CAS atomique)   │
└────────┬────────────┘
         │
    Pour chaque participant :
         │
    ┌────┴────────────────────────────────────┐
    │                                          │
    ▼                                          ▼
  Statut terminal                        accepted_guaranteed
  (declined, cancelled,                  sans preuve admissible
   invited, released)                          │
    │                                          ▼
    ▼                                   ┌──────────────┐
  outcome: "waived"                     │ manual_review │
  (pas de pénalité)                     └──────┬───────┘
                                               │
                                    ┌──────────┴──────────┐
                                    │ V5.1: Seuls les     │
                                    │ accepted_guaranteed  │
                                    │ entrent en phase     │
                                    │ déclarative          │
                                    └──────────┬──────────┘
                                               │
                                               ▼
                                   ┌───────────────────────┐
                                   │ initialize_declarative │
                                   │     (collecting)       │
                                   │  ┌─ Deadline: 48h ─┐  │
                                   │  │ Chaque garanti   │  │
                                   │  │ remplit sa feuille│  │
                                   │  └──────────────────┘  │
                                   └────────────┬──────────┘
                                                │
                                         Toutes soumises
                                         (ou deadline 48h)
                                                │
                                                ▼
                                        ┌───────────────┐
                                        │ _run_analysis  │
                                        │ (CAS atomique) │
                                        │ collecting →   │
                                        │ analyzing      │
                                        └───────┬───────┘
                                                │
                              ┌─────────────────┼──────────────────┐
                              ▼                 ▼                  ▼
                         Unanimité         Désaccord        Silence total
                         positive          /absent           (0 exprimé)
                              │                 │                  │
                              ▼                 ▼                  ▼
                          "resolved"      "disputed"         "waived"
                          on_time/late    open_dispute()     (présomption)
                              │                 │
                              │                 ▼
                              │       ┌──────────────────┐
                              │       │awaiting_positions│ ◄─── 7 jours
                              │       │  Org + Target    │
                              │       │  soumettent leur │
                              │       │  position        │
                              │       └────────┬─────────┘
                              │                │
                              │     ┌──────────┴──────────┐
                              │     ▼                     ▼
                              │  Accord mutuel      Désaccord
                              │  (mêmes positions)  ou silence
                              │     │                     │
                              │     ▼                     ▼
                              │  Auto-résolu        "escalated"
                              │  (agreed_*)         → Admin arbitrage
                              │                           │
                              │                           ▼
                              │                    ┌─────────────┐
                              │                    │ resolve()   │
                              │                    │ final_outcome│
                              │                    └──────┬──────┘
                              │                           │
                              ▼                           ▼
                    ┌─────────────────────────────────────────┐
                    │        MOTEUR FINANCIER                  │
                    │                                         │
                    │  outcome = no_show/late_penalized ?      │
                    │     OUI → capture_guarantee()            │
                    │          → create_distribution()         │
                    │          → credit wallets                │
                    │                                         │
                    │  outcome = on_time/waived ?              │
                    │     OUI → release_guarantee()            │
                    │                                         │
                    │  Distribution:                           │
                    │    - pending_hold (15j) → available      │
                    │    - OU immediate_release (consensus/    │
                    │      arbitrage) → available direct       │
                    │                                         │
                    │  Contestation possible pendant le hold   │
                    └─────────────────────────────────────────┘
```

### A.3 — Interactions critiques entre modules

| Transition | Module Source | Module Cible | Mécanisme |
|---|---|---|---|
| RDV terminé → Évaluation | `scheduler.py` | `attendance_service` | Cron job 10 min, CAS atomique |
| Évaluation → Phase déclarative | `attendance_service` | `declarative_service` | Appel synchrone si manual_review |
| Sheets soumises → Analyse | `declarative_service` | `declarative_service` | CAS collecting→analyzing |
| Analyse → Litige | `declarative_service` | `declarative_service` | open_dispute() |
| Litige deadline → Escalade | `scheduler.py` | `declarative_service` | Cron job 15 min |
| Résolution litige → Finance | `declarative_service` | `distribution_service` + `wallet_service` | resolve_dispute() |
| Review timeout → Auto-waive | `scheduler.py` | `attendance_service` | Cron job 6h (15 jours) |
| Hold expiré → Available | `scheduler.py` | `distribution_service` | Cron job 15 min |
| Reclassification → Annulation dist. | `attendance_service` | `distribution_service` | cancel_distribution() |

### A.4 — Jobs planifiés (scheduler.py)

| Job | Fréquence | Rôle | Impact si absent |
|---|---|---|---|
| Attendance evaluation | 10 min | Déclenche évaluation post-RDV | RDV jamais évalués |
| Declarative deadline | 15 min | Force les sheets non soumises | Phase collecting infinie |
| Dispute deadline | 15 min | Escalade litiges expirés | Litiges bloqués |
| Distribution hold expiry | 15 min | Libère les fonds après 15j | Argent bloqué en pending |
| Review timeout | 6h | Auto-waive après 15j | Deadlock financier |
| Reconciliation | 6h | Vérifie cohérence wallets | Drift non détecté |
| Contestation timeout | 12h | Rejette contestations > 30j | Contestations infinies |

---

## B. ANGLES MORTS IDENTIFIÉS

### BS-1 — Review timeout vs phase déclarative active (CRITIQUE)

**Description** : Le job `run_review_timeout_job()` auto-waive les participants dont le `attendance_record` est en `manual_review` depuis > 15 jours. Mais il ne vérifiait PAS si une phase déclarative ou un litige était actif pour ce participant.

**Pourquoi c'est risqué** : Un litige peut facilement durer > 15 jours (7j de positions + escalade + arbitrage). Si le review timeout se déclenche pendant un litige actif, il :
- Auto-waive silencieusement le participant
- Libère sa garantie financière
- Rend le litige en cours inutile (la pénalité a déjà été annulée)

**Impact utilisateur** : L'organisateur attend la résolution du litige, mais la garantie est déjà libérée. Quand l'admin arbitre "no_show", la capture échoue silencieusement. L'organisateur ne reçoit aucune compensation.

**Statut** : CORRIGÉ. Guard ajouté dans `attendance_service.py` : le job vérifie désormais si l'appointment a une phase déclarative active (`collecting`, `analyzing`, `disputed`) ou si le participant a un litige ouvert.

---

### BS-2 — Réconciliation wallet vs credit_available_direct (MAJEUR)

**Description** : La formule de réconciliation ne comptait que `credit_pending` comme entrée d'argent. Les crédits via `credit_available_direct` (distributions avec `immediate_release` après consensus ou arbitrage) étaient ignorés.

**Pourquoi c'est risqué** : Tout litige résolu par accord mutuel ou arbitrage utilise `immediate_release=True`, ce qui credite directement via `credit_available_direct`. Ces wallets étaient systématiquement reportés comme ayant un "drift" — un faux positif qui masquerait de vrais drifts en production.

**Impact utilisateur** : Pas d'impact direct visible, mais en production, l'équipe ops verrait des alertes de drift constantes et finirait par les ignorer (cry-wolf effect), ratant les vrais problèmes.

**Statut** : CORRIGÉ. `MONEY_IN_TYPES` inclut désormais `("credit_pending", "credit_available_direct")`.

---

### BS-3 — Phase "analyzing" bloquée sans recovery (MAJEUR)

**Description** : L'analyse déclarative utilise un CAS atomique `collecting → analyzing`. Si le processus crash entre la transition CAS et la fin de l'analyse (erreur DB, timeout, OOM), l'appointment reste bloqué en `analyzing` pour toujours. Le deadline job ne cherche que les phases `collecting`.

**Pourquoi c'est risqué** : Un crash serveur pendant l'analyse (certes rare, mais possible en production) crée un deadlock permanent. L'appointment ne peut plus progresser, les sheets sont soumises mais pas analysées, les garanties restent capturées indéfiniment.

**Impact utilisateur** : L'organisateur voit "Analyse en cours..." indéfiniment. Aucun bouton d'action. Aucun moyen de débloquer la situation sans intervention technique.

**Statut** : CORRIGÉ. Recovery automatique ajouté dans `run_declarative_deadline_job()` : détecte les phases `analyzing` bloquées depuis > 30 minutes, reset à `collecting`, et relance l'analyse. Le timestamp `declarative_analyzing_started_at` est désormais enregistré lors du CAS.

---

### BS-4 — Reclassification après distribution immediate_release (MOYEN)

**Description** : Quand un litige est résolu (consensus ou arbitrage) avec un outcome `no_show`, une distribution `immediate_release` est créée (status = `completed`). Si l'organisateur reclassifie ensuite le participant (par erreur ou nouvelle info), `_process_reclassification()` tentait d'annuler la distribution mais la garde `status not in ('cancelled', 'completed')` la bloquait silencieusement.

**Pourquoi c'est risqué** : La reclassification semble réussir côté UI (le statut change), mais les fonds ne sont jamais restitués. Le participant pénalisé à tort garde sa pénalité, et l'organisateur garde sa compensation indue.

**Impact utilisateur** : L'organisateur pense avoir corrigé une erreur, mais la correction financière n'a pas eu lieu. Le participant continue de voir un débit injustifié dans son wallet.

**Statut** : CORRIGÉ. Double fix : (1) `cancel_distribution()` accepte désormais les distributions `completed` (seules les `cancelled` sont rejetées). (2) `_process_reclassification()` n'exclut plus `completed` de l'appel à `cancel_distribution()`.

---

### BS-5 — debit_refund multi-distribution et ordre de débit (BAS)

**Description** : `debit_refund()` pioche d'abord dans `pending_balance` puis dans `available_balance`, sans distinction de la distribution source. Si un wallet a des fonds pending de Distribution A et pending de Distribution B, un refund pour B pourrait prendre les fonds de A.

**Pourquoi on l'a testé** : Risque théorique de solde pending négatif lors de l'expiration du hold de Distribution A si ses fonds ont été consommés par le refund de B.

**Résultat** : Le test montre que le scénario fonctionne correctement — le pending_balance total reste suffisant. Le risque est théorique et ne se manifeste que dans des cas extrêmes de multi-distribution sur un même wallet avec des timings très serrés.

**Statut** : OK — Pas de correction nécessaire. Risque acceptable.

---

### BS-6 — Observateur voit litiges non concernés (PRODUIT)

**Description** : Le endpoint `GET /disputes/mine` retournait TOUS les litiges de TOUS les RDV où l'utilisateur est participant, même s'il n'est pas partie prenante du litige. Dans un RDV à 5 personnes, chaque participant voyait les litiges des autres.

**Pourquoi c'est risqué** : Confusion UX majeure. Un participant C voit un litige entre l'Organisateur et le Participant A, avec un rôle "observer" qui ne lui permet aucune action. Il reçoit potentiellement des informations (positions, preuves) qu'il ne devrait pas voir. C'est aussi un problème de confidentialité.

**Impact utilisateur** : "Pourquoi je vois un litige qui ne me concerne pas ?" — question légitime. L'interface est polluée par des litiges où l'utilisateur ne peut rien faire.

**Statut** : CORRIGÉ. Filtrage ajouté dans `dispute_routes.py` : seuls les litiges où l'utilisateur est `organizer`, `target`, ou `counterpart` (a soumis une déclaration sur la cible) sont retournés.

---

### BS-7 — CAS idempotence : double évaluation concurrente (ROBUSTESSE)

**Description** : Deux appels simultanés à `evaluate_appointment()` ne doivent pas créer de doublons.

**Résultat** : Le CAS atomique (`attendance_evaluated: false → true`) fonctionne parfaitement. Le second appel est bloqué.

**Statut** : OK — Protection robuste.

---

### BS-8 — Dispute sans champ deadline (ROBUSTESSE)

**Description** : Un litige sans champ `deadline` (données historiques, bug) ne doit pas crasher le job d'escalade.

**Résultat** : Le job skip proprement les litiges sans deadline. Aucune escalade incorrecte.

**Statut** : OK — Gestion défensive correcte.

---

### BS-9 — Capture sur garantie déjà libérée (ROBUSTESSE)

**Description** : Tentative de capture d'une garantie déjà en status `released`.

**Résultat** : Rejet propre avec message d'erreur explicite ("Guarantee not in completed state").

**Statut** : OK — Protection correcte. Mais le message d'erreur ne remontera pas à l'utilisateur si le moteur financier échoue silencieusement (cf. BS-1 — maintenant corrigé).

---

### BS-10 — Dispute résolue no_show sans bénéficiaire éligible (EDGE)

**Description** : Tous les participants sont en manual_review (aucune preuve), un litige est résolu en no_show. Qui reçoit la compensation ?

**Résultat** : Le système applique correctement le "Cas A override" : pas de distribution créée, le record est marqué `cas_a_override=True`. La capture est bloquée car il n'y a aucun bénéficiaire prouvé.

**Statut** : OK — Cas A correctement implémenté.

---

### BS-11 — Auto-litige organisateur vs organisateur (EDGE)

**Description** : L'organisateur est aussi participant et en manual_review. L'analyse déclarative ne doit pas créer un litige "org vs org" (deadlock).

**Résultat** : Le guard `target_user_id == organizer_user_id` détecte le cas et auto-resolve en `waived` avec log explicite.

**Statut** : OK — Protection robuste.

---

## C. TESTS RÉALISÉS — RÉSULTATS

| Test | Scénario | Résultat PRÉ-FIX | Résultat POST-FIX |
|------|----------|-------------------|---------------------|
| **BS-1** | Review timeout (15j) sur participant avec litige ouvert | **KO** — Participant auto-waived malgré le litige | **OK** — Waive bloqué, litige continue |
| **BS-2** | Reconciliation wallet après credit_available_direct | **KO** — Faux drift de 1000c reporté | **OK** — Aucun drift, wallet clean |
| **BS-3** | Phase analyzing bloquée (simulée > 30 min) | **KO** — Phase reste en analyzing indéfiniment | **OK** — Recovery auto, transition vers resolved |
| **BS-4** | Reclassification no_show→on_time après immediate_release | **KO** — Distribution status=completed non annulée | **OK** — Distribution annulée, fonds restitués |
| **BS-5** | debit_refund sur wallet multi-distribution | OK — Fonds suffisants, pas de conflit | OK |
| **BS-6** | Observateur B voit litige A vs Org | **KO** — B voit 1 litige non concerné | **OK** — B ne voit plus le litige |
| **BS-7** | Double évaluation concurrente | OK — CAS atomique bloque la 2e | OK |
| **BS-8** | Dispute sans champ deadline + job escalade | OK — Job ne crash pas | OK |
| **BS-8b** | Dispute sans deadline non escaladée | OK — Statut inchangé | OK |
| **BS-9** | Capture guarantee status=released | OK — Rejet propre | OK |
| **BS-10** | Dispute no_show sans bénéficiaire | OK — Cas A override appliqué | OK |
| **BS-11** | Auto-litige org vs org | OK — Guard + auto-waive | OK |

**Score final : 12/12 OK** (après corrections de 5 failles)

---

## D. CONCLUSION CRITIQUE

### Ce qui est vraiment solide

1. **CAS atomique sur l'évaluation et l'analyse** — Les transitions critiques (`attendance_evaluated: false→true`, `collecting→analyzing`) sont protégées par des Compare-And-Swap MongoDB atomiques. Impossible de doubler une évaluation ou une analyse.

2. **Cas A (absence de bénéficiaire)** — Le système gère correctement le cas où personne n'a de preuve admissible. Pas de capture, pas de distribution, override explicite tracé en DB.

3. **Guard auto-litige organisateur** — Le cas piège où l'organisateur est aussi la cible du litige est détecté et résolu sans deadlock.

4. **Idempotence des emails de confirmation** — Mécanisme atomique `confirmation_email_sent` qui empêche les doublons même en cas de concurrence webhook/polling.

5. **Stripe guarantee capture/release** — Les guards (`status != completed`, `status in (released, captured)`) empêchent les doubles captures et les opérations sur des garanties déjà traitées.

6. **V5.1 : Exclusion stricte des non-garantis** — Seuls les `accepted_guaranteed` créent des feuilles de présence. Les non-garantis sont auto-waived immédiatement, ce qui simplifie la chaîne déclarative.

### Ce qui était fragile (maintenant corrigé)

1. **Le review timeout était un tueur silencieux** (BS-1) — C'était la faille la plus dangereuse. En production, avec des litiges qui prennent 2-3 semaines, le timeout de 15 jours aurait systématiquement court-circuité le processus de litige. Corrigé.

2. **La réconciliation financière était aveugle** (BS-2) — Faux positifs sur tous les wallets ayant reçu des fonds par immediate_release. En production, cela aurait noyé les alertes réelles. Corrigé.

3. **L'analyzing crash == deadlock permanent** (BS-3) — Aucun mécanisme de recovery. Un simple restart serveur pendant une analyse aurait bloqué un appointment indéfiniment. Corrigé.

4. **La reclassification post-consensus était trompeuse** (BS-4) — L'UI montrait un changement de statut, mais l'argent ne bougeait pas. Violation du principe de moindre surprise. Corrigé.

5. **La visibilité des litiges était trop large** (BS-6) — Problème de confidentialité et de confusion UX. Corrigé.

### Ce qui peut encore casser en production

1. **Concurrence scheduler multi-instance** — Si l'application est déployée sur plusieurs pods Kubernetes, les cron jobs (APScheduler) s'exécuteront en parallèle sur chaque pod. Les CAS MongoDB protègent contre les doubles-exécutions, mais les jobs qui ne sont PAS protégés par CAS (review_timeout, declarative_deadline, dispute_deadline) pourraient produire des doublons de logs ou des mises à jour redondantes. Recommandation : utiliser un distributed lock (MongoDB advisory lock ou Redis) pour les jobs scheduler.

2. **Stripe webhook race condition** — Le webhook `checkout.session.completed` et le polling endpoint `get_guarantee_status` peuvent tous deux appeler `handle_checkout_completed`. La protection actuelle (idempotence via `status != completed`) est correcte, mais un pic de latence webhook pourrait créer une fenêtre où le participant voit un état incohérent pendant quelques secondes.

3. **Email de notification litige vers cible sans compte** — Si `target_user_id` est null (participant sans compte NLYT), aucune notification de litige n'est envoyée. Le participant ne sait pas qu'il a 7 jours pour répondre. Le délai passe → escalade automatique → décision admin sans la voix du participant. C'est un risque d'équité.

4. **Granularité des jobs scheduler** — Le job d'évaluation tourne toutes les 10 minutes, mais le declarative deadline ne tourne que toutes les 15 minutes. Un utilisateur pourrait attendre jusqu'à 25 minutes entre la fin de la deadline et l'analyse forcée. Pas critique, mais perceptible.

### Niveau de confiance global

**7.5/10** — Le noyau Trustless est robuste (CAS, guards financiers, V5.1). Les 5 failles identifiées et corrigées auraient pu causer des problèmes sérieux en production, mais elles sont maintenant patchées. Les risques résiduels (multi-pod, notification cible, granularité scheduler) sont des améliorations opérationnelles, pas des bugs critiques.

Le système est **prêt pour des tests utilisateur réels** sur une instance single-pod. Un audit supplémentaire sera nécessaire avant un déploiement multi-pod ou à forte charge.

---

*Script de test : `/app/backend/tests/qa_blind_spots.py` (12 tests, 100% OK post-corrections)*
*Fichiers modifiés :*
- *`/app/backend/services/attendance_service.py` (BS-1 guard + BS-4 reclassification fix)*
- *`/app/backend/services/wallet_service.py` (BS-2 reconciliation fix)*
- *`/app/backend/services/declarative_service.py` (BS-3 analyzing recovery)*
- *`/app/backend/services/distribution_service.py` (BS-4 cancel_distribution fix)*
- *`/app/backend/routers/dispute_routes.py` (BS-6 observer filtering)*
