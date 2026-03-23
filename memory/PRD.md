# NLYT — Product Requirements Document

## Vision
SaaS de gestion d'assiduité avec garanties financières. NLYT vérifie la présence des participants via des preuves indépendantes, sans dépendance critique à un provider vidéo.

## Architecture cible
Voir **`/app/memory/ARCHITECTURE.md`** pour le document complet post-pivots (Mars 2026).

## Modèle produit (résumé)

### Deux systèmes distincts, jamais mélangés
- **Physique** (`appointment_type: "physical"`) : GPS / QR / Check-in manuel
- **Visio** (`appointment_type: "video"`) : NLYT Proof (check-in + heartbeat + scoring)

### Provider vidéo = support, pas source de vérité
- L'utilisateur gère sa propre visio (coller un lien OU connecter Zoom/Teams/Meet)
- NLYT ne crée pas de réunion centralisée
- Les APIs vidéo sont un bonus secondaire

### Verrouillage d'accès (Guarantee-First Architecture)
- Les participants NE PEUVENT PAS accéder au fichier ICS, au lien de visio, ni au lien NLYT Proof tant qu'ils n'ont pas finalisé leur engagement
- Statuts finalisés : `accepted` (sans garantie) ou `accepted_guaranteed` (garantie payée)
- `accepted_pending_guarantee` = verrouillé
- L'email d'invitation initial N'INCLUT PAS les liens ICS/proof/visio
- L'email de confirmation (avec liens) est envoyé uniquement après finalisation

## Core Requirements
1. Création de RDV (physique + vidéo) avec paramètres de pénalité
2. Invitation par email avec liens sécurisés + lien NLYT Proof (visio uniquement)
3. Workflow contractuel de modification unanime
4. Garantie financière Stripe (setup mode, guarantee-first architecture)
5. Preuves physiques : GPS, QR, check-in (organisateur inclus avec GPS)
6. NLYT Proof System : check-in + heartbeat 30s + scoring 0-100 + validation organisateur
7. Import de présences : API auto-fetch + CSV/JSON (bonus)
8. Moteur de décision d'assiduité conservateur
9. Page Intégrations (Calendriers + Visioconférence)
10. Emails transactionnels avec gestion correcte des timezones
11. Synchronisation calendrier (Google/Outlook)
12. Verrouillage d'accès RDV jusqu'à validation garantie (ICS, visio, proof)

## Technical Stack
Frontend: React + TailwindCSS + Shadcn/UI
Backend: FastAPI + Python + MongoDB + slowapi
Email: Resend | Payments: Stripe | Video: Zoom/Teams/Meet API (mode user)

## Testing
- iteration_50: 13/13 backend + 10/10 frontend (Consolidation non-régression)
- Credentials: testuser_audit@nlyt.app / Test1234!

## Completed — Consolidation Phase (Fév 2026)
- [x] **Centralisation MongoClient** : 64 instances dispersées -> 1 instance unique dans `database.py`. 32 fichiers migrés.
- [x] **Découpe AppointmentDetail.js** : 2701 -> 1592 lignes. 5 sous-composants extraits :
  - `ProofSessionsPanel.js` (181L) — Sessions NLYT Proof
  - `VideoEvidencePanel.js` (453L) — Preuves vidéo (ingest, fetch, CSV, logs)
  - `AttendancePanel.js` (139L) — Détection de présence + reclassification
  - `ModificationProposals.js` (224L) — Propositions de modification
  - `EvidenceDashboard.js` (111L) — Dashboard check-ins physiques
- [x] **Nettoyage enums mortes** : `GuaranteeMode.AUTH_NOW` et `AUTH_LATER` supprimés
- [x] **Protection debug.py** : Endpoints protégés par `require_admin` (workspace owner uniquement)
- [x] **Clarification statut** : `accepted` = sans garantie (actif), `accepted_guaranteed` = avec garantie (actif)

## Completed — Earlier
- [x] Fix P0 "Erreur réseau" GPS check-in (gestion GeolocationPositionError + mapping HTTP)
- [x] Fix "body stream already read" (pattern `.text()` + `JSON.parse()` dans InvitationPage.js)
- [x] Fix Azure Outlook OAuth (MICROSOFT_CLIENT_ID corrigé)
- [x] Rééquilibrage scoring NLYT Proof (check-in 40pts, durée 30pts, flow bonus 10pts, API 20pts, seuil strong ≥ 55)
- [x] Toutes les features listées dans ARCHITECTURE.md

## Stripe Connect — Progression
Architecture complète documentée dans `/app/memory/STRIPE_CONNECT_ARCHITECTURE.md`

### Phase 1 — Wallet + Ledger ✅ (Fév 2026)
- [x] `wallet_service.py` — CRUD wallet + ledger (credit_pending, confirm_available, debit_payout, debit_refund)
- [x] `wallet_routes.py` — GET /api/wallet (solde) + GET /api/wallet/transactions (historique)
- [x] Auto-création wallet à l'inscription (auth_service.py)
- [x] Wallet idempotent via `ensure_wallet()`
- [x] Montants en centimes (int), minimum payout 500c (5€)
- [x] Collections MongoDB : `wallets`, `wallet_transactions`
- [x] Tests : iteration_52 — 13/13 backend

### Phase 2 — Stripe Connect Express (Fév 2026) ✅
- [x] `connect_service.py` — Onboarding Express (create account, account link, dev mode fallback)
- [x] `connect_routes.py` — POST /api/connect/onboard, GET /api/connect/status, POST /api/connect/dashboard
- [x] Webhook handlers: `account.updated` + `account.application.deauthorized` dans `webhooks.py`
- [x] Frontend `WalletPage.js` : solde, statut Connect, historique transactions
- [x] Navigation Settings → Wallet
- [x] Idempotence onboarding (réutilise account_id existant)
- [x] 5 statuts normalisés: not_started, onboarding, restricted, active, disabled
- [x] Dev mode: simulation automatique si Stripe Connect non activé
- [x] Tests : iteration_53 — 12/12 backend + 100% frontend

### Phase 3 — Capture + Distribution (Fév 2026) ✅
- [x] `distribution_service.py` — Moteur de calcul pur (compute_distribution) + create/finalize/cancel/contest
- [x] Invariant strict: sum(beneficiaries) == capture_amount_cents toujours (centimes int, jamais float)
- [x] Symétrie: organisateur no_show → sa compensation répartie entre participants présents, jamais à lui-même
- [x] Symétrie: charité + plateforme inchangées même en cas de no_show organisateur
- [x] Wallet platform (type=platform, user_id=__nlyt_platform__) crédité automatiquement
- [x] Wallet charity (type=charity) créé par association configurée
- [x] Hook post-évaluation: no_show haute confiance → capture + distribution automatique
- [x] Hook post-évaluation: on_time/late haute confiance → release automatique
- [x] Hook post-reclassification: manual_review→no_show → capture + distribution
- [x] Hook post-reclassification: no_show→on_time → cancel distribution + release
- [x] Scheduler job finalize_expired_holds() toutes les 15 minutes
- [x] Hold 15 jours: pending_balance → available_balance après expiration
- [x] Contestation bloque la finalisation (status=contested)
- [x] Annulation: refund via debit_refund() sur chaque wallet crédité
- [x] Idempotence stricte sur guarantee_id
- [x] Endpoints API: GET /distributions, GET /distributions/:id, POST /distributions/:id/contest
- [x] GET /api/appointments/:id/distributions (vue organisateur)
- [x] Tests: iteration_54 — 42/42 backend (100%)

### Phase 3b — WalletPage enrichie (Fév 2026) ✅
- [x] 3 cartes de solde pédagogiques: En attente / Disponible / Retirable
- [x] Distinction claire entre fonds en hold, fonds disponibles, fonds retirables
- [x] Section "Distributions en cours" (pending_hold + contested)
- [x] Section "Distributions passées" (completed + cancelled)
- [x] Cartes expandables: explication contextuelle + répartition détaillée
- [x] Breakdown: NLYT (commission) / Association / Organisateur / Participant(s)
- [x] Badge "(vous)" sur la ligne du bénéficiaire courant
- [x] Date de disponibilité (hold expiry) affichée
- [x] Contestation MVP: bouton visible uniquement pour le no_show pendant le hold
- [x] Formulaire de signalement: motif + soumission tracée
- [x] Statuts: En attente / Contestée / Finalisée / Annulée avec couleurs
- [x] Tests: iteration_55 — 17/17 backend + 13/13 frontend (100%)

### Charity Impact Tracking (Fév 2026) ✅
- [x] `GET /api/wallet/impact` — agrégation fiable depuis le ledger (distributions.beneficiaries.role=charity)
- [x] Totaux recalculables : total_charity_cents, distributions_count, events_count
- [x] Ventilation par association (by_association[])
- [x] Détail par événement (contributions[] avec appointment_title, amount, status)
- [x] Exclut les distributions annulées et les bénéficiaires refunded
- [x] Frontend : section "Votre impact solidaire" dans WalletPage
- [x] 3 cartes stats : Total contribué / Distributions / Événements
- [x] Ligne par association avec montant
- [x] Détail expandable par événement avec badge statut (en attente / finalisé)
- [x] Section masquée si aucune contribution (total = 0)
- [x] Tests: iteration_56 — 11/11 backend + 13/13 frontend (100%)

### Phase 4 — Payouts (à faire)
- [ ] POST /api/wallet/payout
- [ ] Stripe Transfer vers compte Connect

### Phase 5 — UI (à faire)
- [ ] DistributionPanel.js (AppointmentDetail)
- [ ] WalletSettings.js (page wallet)
- [ ] Emails notifications (capture, distribution, payout)

## Roadmap
### P1 — En cours
- Stripe Connect Phases 4-5
- Calcul `video_api_points` (20pts bonus) dans le scoring NLYT Proof
- Webhooks temps réel Zoom/Teams

### P2
- Pagination endpoints de liste
- Auto-update calendrier V2 (retry automatique)
- Découpe InvitationPage.js (1409 lignes)

### P3
- Dashboard analytics organisateurs
- Templates email externalisés (fichiers HTML)
- Index MongoDB (performance)
