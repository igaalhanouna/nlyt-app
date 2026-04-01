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

### Message par Defaut a la Creation de Compte (2026-04-01)
- Inscription: appointment_defaults.default_message initialise avec le texte NLYT standard (535 chars)
- Texte multi-lignes avec \n preserves
- Utilisateurs existants: pas d'ecrasement (fallback None dans get_user_settings)
- Tests: registration verifie + DB + cleanup

### Message par Defaut dans les Parametres (2026-04-01)
- Backend: champ default_message (Optional[str], max 2000) dans AppointmentDefaults
- Sauvegardé dans users.appointment_defaults via PUT /api/user-settings/me
- Retourné dans GET /api/user-settings/me/appointment-defaults
- Frontend Settings: textarea dans /settings/profile avec compteur X/2000
- Frontend Wizard: pre-remplissage description si !fromExternalData && !prev.description
- Priorité: NLYT me > description existante > default_message > vide
- Tests: 13/13 PASS (iteration 171)

### Logique Feuilles de Presence — Cibles Pertinentes (2026-04-01)
- Prévention: initialize_declarative_phase exclut les cibles non-self en statut terminal
- Statuts terminaux: cancelled_by_participant, declined, guarantee_released (frozenset)
- Auto-déclaration seule sans cible non-self pertinente → sheet non créée
- Si 0 sheets créées → declarative_phase = "not_needed"
- Filtrage rétroactif: GET /pending exclut les sheets dont toutes les cibles non-self sont terminales
- Aucune modification frontend nécessaire
- Tests: 14/14 PASS (iteration 170)

### Champ Description / Message pour les Participants (2026-04-01)
- Backend: ajout description: Optional[str] (max 2000) dans AppointmentCreate
- Stocké en DB, modifiable via PATCH (déjà dans la whitelist)
- Prefill: description récupérée depuis external_events lors du flow "NLYT me"
- Outlook adapter: body.content (full text) remplace bodyPreview (tronqué 255 chars)
- Calendar sync: automatique via _build_event_data (Google description, Outlook body.content)
- Frontend wizard: textarea "Message pour les participants" + compteur X/2000 + récap
- Frontend détail: affichage conditionnel dans AppointmentHeader (data-testid=appointment-description)
- Tests: 14/14 PASS (iteration 169)

### Hook useCalendarAutoSync — Centralisation Auto-Sync (2026-04-01)
- Extraction du code duplique (Dashboard + Agenda) dans /hooks/useCalendarAutoSync.js
- Interval 2 min, guards anti-double (syncInProgressRef, syncingRef, document.hidden)
- Pause quand onglet inactif (document.visibilitychange), sync immediate au retour si >60s
- Retourne { lastAutoCheckAt } pour l'indicateur UX CalendarSyncPanel
- Suppression du code duplique dans OrganizerDashboard.js et AgendaPage.js
- Tests: 24/24 PASS (iteration 168)

### Bouton "NLYT me" en Vue Planning/Agenda (2026-04-01)
- Ajout du bouton "NLYT me" (pill noir + Zap) sur les événements externes dans les 3 vues de l'Agenda
- Vue Mois (detail panel) + Vue Jour (sidebar) : bouton dans EventRow pour events source !== 'nlyt'
- Vue Semaine (time grid) : popover au clic sur un event externe avec titre, heure et bouton "NLYT me"
- Même flow métier que le dashboard : externalEventsAPI.prefill() → navigate /appointments/create
- State loading (spinner) pour éviter les double-clics
- Gestion 409 (événement déjà converti) cohérente avec le dashboard
- Events NLYT non affectés (clic → détail RDV, chevron, pas de bouton NLYT me)
- Tests: 15/15 PASS (iteration 167)

### Harmonisation Droits Video Organisateur/Participant (2026-03-31)
- Backend: helper _is_accepted_participant + _require_organizer_or_participant dans video_evidence_routes.py
- 6 endpoints ouverts aux participants acceptes: ingest, fetch-attendance, ingest-file, GET evidence, logs, log/{id}
- create-meeting reste organisateur uniquement
- GET evidence: fallback participant si pas membre workspace
- Frontend: fix bug data.appointment_type → apt.appointment_type dans AppointmentDetail.js
- Frontend: videoIngestionLogs charge pour tous les roles (plus seulement organisateur)
- VideoEvidencePanel: boutons "Recuperer les presences" et "Import manuel" visibles pour les participants
- Tests: 12/12 PASS (iteration 166)

### RBAC — Système de Rôles et Permissions (2026-03-31)
- 5 rôles: admin, arbitrator, payer, accreditor, user
- Mapping centralisé dans `utils/permissions.py` (backend) et `utils/permissions.js` (frontend)
- Backend: `require_permission()` remplace `require_admin()` sur toutes les routes admin granulaires
- Frontend: `PermissionGuard` composant route guard + `canAccess()` dans AuthContext
- Page `/admin/users` avec dropdown de rôle (5 valeurs) et compteurs par rôle
- Menu admin conditionnel (visible seulement si au moins une permission admin)
- AdminDashboard filtre les sections selon les permissions du rôle
- Migration: 121 users existants mis à jour avec role='user'
- Tests: 23/23 PASS (iteration 165)

### Fix Redirection Post-Stripe pour Participants Connectés (2026-03-31)
- BUG: Un user connecté qui ajoutait sa carte via Stripe était renvoyé vers /invitation/{token} au lieu de /dashboard
- CAUSE RACINE: La route `respond` n'envoyait jamais `return_url` à `create_guarantee_session`, et `login-and-accept` non plus
- FIX BACKEND (Option A): Détection optionnelle du Bearer token dans `respond` → si authentifié, `return_url="/dashboard"`. Route `login-and-accept` passe toujours `return_url="/dashboard"`.
- FIX FRONTEND (Option C): `pollGuaranteeStatus` dans InvitationPage redirige immédiatement vers /dashboard si user connecté (avec check localStorage pour éviter closure stale)
- Tests: 13/13 PASS (iteration 164)

### Fix Annulation Participant — Statut Métier Préservé (2026-03-30)
- BUG CRITIQUE: `release_guarantee()` écrasait le statut métier `cancelled_by_participant` par `guarantee_released`
- FIX BACKEND: `release_guarantee()` ne touche plus au statut participant si celui-ci est terminal (cancelled_by_participant, declined)
- FIX BACKEND: Timeline organisateur exclut les participants annulés/refusés des compteurs actifs + affiche "Participation annulée par [Nom]"
- FIX BACKEND: Timeline participant affiche "Vous avez annulé votre participation" + classement en historique
- FIX FRONTEND: `guarantee_released` traité comme alias de `cancelled_by_participant` dans 7 composants (OrganizerDashboard, ParticipantsSection, ParticipantManagement, InvitationStatusBadge, InvitationResponseSection, InvitationCardHeader, InvitationPage)
- MIGRATION: 3 participants historiques corrigés (guarantee_released → cancelled_by_participant)
- Tests: 13/13 PASS (iteration 163)

### Wording Ponctualite & Accents Fix (2026-03-30)
- Remplacement "present" par "present a l'heure" sur tout le frontend
- Correction accents manquants dans AttendanceSheetPage.js ("Present(e) a l'heure" -> "Present(e) a l'heure" avec accents)

### Stripe Payout Delay Info (2026-03-30)
- Hint "Virement recu sous 2 a 4 jours ouvres" sous le bouton retirer (BalanceCards)
- Bandeau info dans la modale de confirmation de retrait
- Hint contextuel dans l'historique des payouts (statut processing/pending)
- Toast de confirmation enrichi avec delai de virement
- Tests: 6/6 PASS (iteration 162)

### Immediate Release (Bypass Hold) (2026-03-30)
- Flag immediate_release=True envoie l'argent directement en balance available
- Champ release_reason ("hold", "consensus", "admin_arbitration") pour tracabilite
- credit_available_direct dans wallet_service.py

### Dossier Technique Arbitrage (2026-03-30)
- Backend build_tech_dossier avec donnees brutes par participant
- Frontend AdminArbitrationDetail.js avec cartes video_sessions, GPS, proof_sessions
- Phrases clarifiees: "Auto-declaration" vs "Declaration sur autrui"

### Evidence Dashboard Semantic Fix (2026-03-30)
- "Absent" remplace par "Aucune preuve technique" (signal vs decision)
- Bandeau explicatif ajoute

### Charity Payouts V1 (2026-03-29)
- Manual bank transfers to charity associations
- Admin records completed transfer - wallet debited atomically
- IBAN validation, masked display, snapshot with each payout
- Dashboard with KPIs, history per association

### Wallet Security Reinforcement (2026-03-29)
- Idempotency key system (frontend generation + backend enforcement)
- Cooldown protection (10s between payouts)
- Atomic debit with rollback on failure
- Structured audit logging with request_id

### Stripe Connect Refresh (2026-03-29)
- POST /api/connect/refresh-status syncs account status from Stripe API

### Dashboard Search (2026-03-29)
- Search bar in Engagements section
- Filters on title, location, counterparty name, status

### ActionCard UX Overhaul (2026-03-30)
- Carte cliquable, icone corbeille, bouton Quitter pour participants

### Webhook Infrastructure (2026-03-30)
- Logging structure complet, protocole W1-W8
- Correction alignement evenements Stripe reels

### Guarantee Security Fix (2026-03-30)
- Auto-garantie via create_guarantee_with_saved_card() avec verification Stripe
- Rejet pm_dev_ en production

### Navbar Action Required Badge (2026-03-30)
- Badge rouge sur "Tableau de bord" avec nombre d'actions requises

### Stale Payout Detection V1 (2026-03-30)
- Job planifie toutes les 6h, route admin, page admin

### Webhooks temps reel Zoom/Teams (2026-03-30)
- POST /api/webhooks/zoom et /api/webhooks/teams
- Dedup, routes admin, scheduler renouvellement

## Data Integrity Rules
- Participant documents MUST have valid user_id when user exists
- Every appointment MUST have an is_organizer=True participant record
- Charity wallet debit ONLY on completed payout
- Payout idempotency keys auto-expire after 24h (TTL index)
- ObjectId exclusion from all MongoDB responses
- GUARANTEE RULE: No guarantee without Stripe verification
- pm_dev_ payment methods rejected with real Stripe key
- BUSINESS STATUS RULE: Le statut participant métier (cancelled_by_participant, declined) ne doit JAMAIS être écrasé par un statut financier (guarantee_released). release_guarantee() vérifie le statut avant d'écrire.

## Upcoming Tasks (P1)
- Configurer le webhook Stripe en production
- Test reel Zoom/Teams avec vrais tokens

## Future Tasks (P2)
- Charity Payouts V2 (Automatisation via Stripe Connect)
- Webhooks temps reel Zoom/Teams en production
- Notification email/push lors de la creation d'un litige
