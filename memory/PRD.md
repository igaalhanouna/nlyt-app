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
- Harmonisation droits Organisateur/Participant pour preuves video
- Charity Payouts V2 (Automatisation via Stripe Connect)
- Webhooks temps reel Zoom/Teams en production
- Notification email/push lors de la creation d'un litige
