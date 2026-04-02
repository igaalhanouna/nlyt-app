# NLYT - Product Requirements Document

## Original Problem Statement
Application SaaS (React/FastAPI/MongoDB) de gestion des presences avec garanties financieres via le moteur "Trustless V4". Objectif : optimiser le moteur Trustless, l'UX globale, le systeme de notifications et fournir un hub d'administration complet.

## Core Architecture
- **Frontend**: React + Shadcn/UI
- **Backend**: FastAPI + MongoDB
- **Payments**: Stripe (test mode, sk_test_*)
- **Email**: Resend
- **Video**: Zoom, Microsoft Teams (OAuth)
- **Auth**: Email/password + Google OAuth + Microsoft OAuth (common tenant)

## QA Campaign Results (2026-03-29)

### Overall: 54/56 tests passed, 2 bugs found and fixed

| Bloc | Tests | Result |
|------|-------|--------|
| A - Auth/Onboarding | 4/4 | PASS |
| B - Permissions/Roles | 2/2 | PASS |
| C - Creation/Modification RDV | 9/9 | PASS (C2 titre vide fixed) |
| D - Invitations | 2/2 | PASS |
| E - Presences | 4/4 | PASS |
| F - Litiges | 2/2 | PASS |
| G - Arbitrage Admin | 2/2 | PASS |
| H - Wallet | 6/6 | PASS (H6 double payout fixed) |
| I - Charity Payouts | 15/15 | PASS |
| J - Calendrier | 5/5 | PASS |
| K - Notifications | 3/3 | PASS |

### Bugs Fixed During QA
1. H6 CRITICAL: Double payout race condition - Fixed with cooldown 10s + idempotency key + atomic $gte guard
2. C2 MINOR: Blank title accepted - Fixed with min_length=1 + strip() validation

## Security Layers - Wallet Payouts
1. **Idempotency key** - unique per request, stored in DB with TTL 24h, prevents duplicate processing
2. **Cooldown** - rejects if last payout < 10s ago (anti double-click)
3. **Atomic $gte guard** - MongoDB prevents overdraft at DB level
4. **Rollback** - re-credits wallet if payout record creation fails
5. **Audit logging** - every step logged with request_id, user_id, amount, status

## Completed Features (Latest)

### Refonte Wording "Ce qui a ete declare" (2026-04-02)
- Toutes les declarations suivent le pattern "X declare Y status" ou "X se declare status"
- Plus aucun statut isole (Absent, Present) sans contexte
- Roles affiches en ligne (organisateur) au lieu de badges separes
- Positions du litige: "{Nom} (organisateur) maintient {Cible} {status}" / "{Cible} se maintient {status}"
- Badge "Vous" conserve comme indicateur discret, mais jamais utilise dans la phrase
- Noms utilises partout pour coherence (pas de "Vous" dans le texte des phrases)

### Refonte Section "Ce qui a ete declare" dans /decisions (2026-04-02)
- Backend: _get_anonymized_summary enrichi avec target_self_declaration, is_organizer, contradiction_level, summary_phrase
- Frontend DecisionDetailPage.js: nouveau composant DeclarationSection avec:
  - Resume de contradiction (badge + phrase contextuelle)
  - Auto-declaration de la cible affichee en premier avec badge "Cible du litige"
  - Role de chaque declarant (Organisateur/Participant)
  - Positions confirmees pendant le litige (organizer_position / participant_position)
  - Raison d'ouverture du litige
  - Phrase de liaison vers la decision finale
- Tests: 33/33 PASS (iteration 173)

### Transparence Preuves /decisions + Regroupement /arbitration (2026-04-02)
- Backend: build_evidence_summary_for_target() dans admin_arbitration_service.py
- API GET /api/disputes/{id} enrichi avec tech_evidence_summary (video, gps, nlyt, checkin, qr)
- Frontend DecisionDetailPage.js: nouveau bloc "Preuves factuelles" avec donnees structurees
- Frontend DecisionDetailPage.js: opened_reason affiché, pieces jointes listees avec type/date
- Frontend AdminArbitrationList.js: regroupement par RDV (groupByAppointment)
- 1 carte = 1 RDV avec sous-lignes par cible/dispute
- Stats KPI et filtres inchanges, label enrichi (X RDVs, Y litiges)
- Tests: 28/28 PASS (iteration 172)

### Message par Defaut a la Creation de Compte (2026-04-01)
- Inscription: appointment_defaults.default_message initialise avec le texte NLYT standard (535 chars)
- Texte multi-lignes avec \n preserves
- Utilisateurs existants: pas d'ecrasement (fallback None dans get_user_settings)
- Tests: registration verifie + DB + cleanup

### Message par Defaut dans les Parametres (2026-04-01)
- Backend: champ default_message (Optional[str], max 2000) dans AppointmentDefaults
- Sauvegarde dans users.appointment_defaults via PUT /api/user-settings/me
- Retourne dans GET /api/user-settings/me/appointment-defaults
- Frontend Settings: textarea dans /settings/profile avec compteur X/2000
- Frontend Wizard: pre-remplissage description si !fromExternalData && !prev.description
- Priorite: NLYT me > description existante > default_message > vide
- Tests: 13/13 PASS (iteration 171)

### Logique Feuilles de Presence — Cibles Pertinentes (2026-04-01)
- Prevention: initialize_declarative_phase exclut les cibles non-self en statut terminal
- Statuts terminaux: cancelled_by_participant, declined, guarantee_released (frozenset)
- Auto-declaration seule sans cible non-self pertinente -> sheet non creee
- Si 0 sheets creees -> declarative_phase = "not_needed"
- Filtrage retroactif: GET /pending exclut les sheets dont toutes les cibles non-self sont terminales
- Aucune modification frontend necessaire
- Tests: 14/14 PASS (iteration 170)

### Champ Description / Message pour les Participants (2026-04-01)
- Backend: ajout description: Optional[str] (max 2000) dans AppointmentCreate
- Stocke en DB, modifiable via PATCH (deja dans la whitelist)
- Prefill: description recuperee depuis external_events lors du flow "NLYT me"
- Outlook adapter: body.content (full text) remplace bodyPreview (tronque 255 chars)
- Calendar sync: automatique via _build_event_data (Google description, Outlook body.content)
- Frontend wizard: textarea "Message pour les participants" + compteur X/2000 + recap
- Frontend detail: affichage conditionnel dans AppointmentHeader (data-testid=appointment-description)
- Tests: 14/14 PASS (iteration 169)

### Hook useCalendarAutoSync (2026-04-01)
- Extraction du code duplique (Dashboard + Agenda) dans /hooks/useCalendarAutoSync.js
- Interval 2 min, guards anti-double (syncInProgressRef, syncingRef, document.hidden)
- Pause quand onglet inactif (document.visibilitychange), sync immediate au retour si >60s
- Retourne { lastAutoCheckAt } pour l'indicateur UX CalendarSyncPanel
- Tests: 24/24 PASS (iteration 168)

### Bouton "NLYT me" en Vue Planning/Agenda (2026-04-01)
- Ajout du bouton "NLYT me" (pill noir + Zap) sur les evenements externes dans les 3 vues de l'Agenda
- Vue Mois (detail panel) + Vue Jour (sidebar) : bouton dans EventRow pour events source !== 'nlyt'
- Vue Semaine (time grid) : popover au clic sur un event externe avec titre, heure et bouton "NLYT me"
- Meme flow metier que le dashboard : externalEventsAPI.prefill() -> navigate /appointments/create
- Tests: 15/15 PASS (iteration 167)

### Harmonisation Droits Video Organisateur/Participant (2026-03-31)
- Backend: helper _is_accepted_participant + _require_organizer_or_participant dans video_evidence_routes.py
- 6 endpoints ouverts aux participants acceptes
- Tests: 12/12 PASS (iteration 166)

### RBAC (2026-03-31)
- 5 roles: admin, arbitrator, payer, accreditor, user
- Tests: 23/23 PASS (iteration 165)

### Fix Redirection Post-Stripe (2026-03-31)
- Tests: 13/13 PASS (iteration 164)

### Fix Annulation Participant (2026-03-30)
- Tests: 13/13 PASS (iteration 163)

## Data Integrity Rules
- Participant documents MUST have valid user_id when user exists
- Every appointment MUST have an is_organizer=True participant record
- Charity wallet debit ONLY on completed payout
- Payout idempotency keys auto-expire after 24h (TTL index)
- ObjectId exclusion from all MongoDB responses
- GUARANTEE RULE: No guarantee without Stripe verification
- pm_dev_ payment methods rejected with real Stripe key
- BUSINESS STATUS RULE: Le statut participant metier ne doit JAMAIS etre ecrase par un statut financier

## Upcoming Tasks (P1)
- Implementation de la refonte /decisions et /arbitration (DONE - 2026-04-02)
- Test reel Zoom/Teams avec vrais tokens

## Future Tasks (P2)
- Charity Payouts V2 (Automatisation via Stripe Connect)
- Webhooks temps reel Zoom/Teams en production
- Notification email/push lors de la creation d'un litige
