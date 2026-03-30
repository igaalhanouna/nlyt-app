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
1. H6 CRITICAL: Double payout race condition → Fixed with cooldown 10s + idempotency key + atomic $gte guard
2. C2 MINOR: Blank title accepted → Fixed with min_length=1 + strip() validation

## Security Layers - Wallet Payouts
1. **Idempotency key** — unique per request, stored in DB with TTL 24h, prevents duplicate processing
2. **Cooldown** — rejects if last payout < 10s ago (anti double-click)
3. **Atomic $gte guard** — MongoDB prevents overdraft at DB level
4. **Rollback** — re-credits wallet if payout record creation fails
5. **Audit logging** — every step logged with request_id, user_id, amount, status

## Completed Features (Latest)

### Charity Payouts V1 (2026-03-29)
- Manual bank transfers to charity associations
- Admin records completed transfer → wallet debited atomically
- IBAN validation, masked display, snapshot with each payout
- Dashboard with KPIs, history per association

### Wallet Security Reinforcement (2026-03-29)
- Idempotency key system (frontend generation + backend enforcement)
- Cooldown protection (10s between payouts)
- Atomic debit with rollback on failure
- Structured audit logging with request_id

### Stripe Connect Refresh (2026-03-29)
- POST /api/connect/refresh-status syncs account status from Stripe API
- Bypasses webhook dependency for status updates

### User Payout Flexible Amount (2026-03-29)
- Amount input field pre-filled with total, editable
- Validation: amount > 0 and <= available_balance

### Dashboard Search (2026-03-29)
- Search bar in Engagements section (right of tabs)
- Filters on title, location, counterparty name, status
- Works on both "A venir" and "Historique" tabs

### Association Dedup (2026-03-29)
- Merged "Restos du Coeur" and "Les Restos du Coeur" into single entry
- 1 appointment migrated, wallet preserved

## Data Integrity Rules
- Participant documents MUST have valid user_id when user exists
- Every appointment MUST have an is_organizer=True participant record
- Charity wallet debit ONLY on completed payout (never on view/prepare)
- Payout idempotency keys auto-expire after 24h (TTL index)
- ObjectId exclusion from all MongoDB responses
- GUARANTEE RULE: No guarantee can be marked "completed" without Stripe verification (SetupIntent or Checkout). Auto-guarantee with saved card MUST call create_guarantee_with_saved_card() which verifies via Stripe API.
- pm_dev_ payment methods are rejected when a real Stripe key is configured

## Upcoming Tasks (P1)
- Executer le protocole de test webhook W1-W8 (apres validation utilisateur)
- Configurer le webhook Stripe en production (coherence wallet/payout/Stripe states)
- Job planifie : detection payouts bloques en `processing` > 24h
- Test reel Zoom/Teams avec vrais tokens

## Future Tasks (P2)
- Charity Payouts V2 (Automatisation via Stripe Connect)
- Webhooks temps reel Zoom/Teams

## Webhook Infrastructure (2026-03-30)
- Logging structure complet dans `webhooks.py` (7 print() remplaces par logger.info/warning/error)
- Chaque log inclut : event_id, event_type, contexte metier (transfer_id, payout_id, user_id, account_id, amount)
- Protocole de test detaille W1-W8 redige dans `/app/docs/WEBHOOK_TEST_PROTOCOL.md`
- Cas couverts : checkout (orga + participant), transfer.paid/failed/reversed, doublon, signature invalide, account.updated
- CORRECTION CRITIQUE: Alignement evenements Stripe reels (transfer.paid/failed n'existent pas → remplaces par transfer.created/reversed/updated)

## Guarantee Security Fix (2026-03-30)
- BUG CRITIQUE: L'auto-garantie organisateur creait une garantie "completed" directement en DB sans verification Stripe
- FIX: Remplacement par appel a create_guarantee_with_saved_card() qui verifie via SetupIntent Stripe
- FIX: Si carte invalide/expiree/SCA → fallback vers Stripe Checkout redirect + nettoyage donnees obsoletes
- FIX: Rejet des pm_dev_ avec une vraie cle Stripe (pas de bypass dev en production)
- Corrige dans 2 endroits : create_appointment() et retry-organizer-guarantee()

## Stripe Redirect UX Fix (2026-03-30)
- BUG UX: Apres enregistrement carte via Stripe Checkout, un user connecte etait redirige vers /invitation/ au lieu de /appointments/{id}
- CAUSE: create_guarantee_session() codait en dur success_url vers /invitation/{token} pour tous les contextes
- FIX: Ajout parametre return_url optionnel a create_guarantee_session()
  - Depuis appointments.py (user connecte): return_url=/appointments/{id} → retour dans l'app
  - Depuis invitations.py (flow invitation): pas de return_url → /invitation/{token} preserve
- Frontend: AppointmentDetail.js detecte ?guarantee_status=success, nettoie l'URL, attend 2s, verifie activation, affiche toast

## ActionCard UX Overhaul (2026-03-30)
- Carte cliquable: zone contenu (titre, date, lieu) wrappee dans <Link> vers /appointments/{id}
- Icone corbeille: ajoutee pour organisateur (via handleDeleteClick existant), absente pour participant
- Bouton Quitter: ajout pour participants ayant deja accepte (status != invited/pending_guarantee)
- Bouton 'Voir details' supprime (carte elle-meme cliquable)
- Tous les CTA existants preserves (Accept, Refuse, Relancer, Annuler, Finaliser)
- Alignement complet avec le pattern TimelineCard

## safeFetchJson Standardization (2026-03-30)
- Helper cree: /app/frontend/src/utils/safeFetchJson.js
- Pattern: resp.text() + JSON.parse() avec fallback (evite "body stream already read")
- 12 fichiers migres, 0 appel .json() brut restant dans toute l'app
- Fichiers: OrganizerDashboard, AppointmentDetail, AppointmentWizard, InvitationPage, Profile, AuthCallback, OAuthButtons, AdminAssociations, AdminPayouts, AdminUsers, QRCheckin, LandingPage, AddressAutocomplete

## Test Results - Iteration 155 (2026-03-30)
- FLUX1 (suppression carte sans auto-recovery): PASS
- FLUX2 (creation RDV sans carte → Stripe redirect): PASS
- W3-W8 (webhook protocol): 6/6 PASS
- Frontend (payment settings, login, dashboard): 4/4 PASS
- Total: 16/16 PASS

## Organizer Guarantee UX Fix (2026-03-30)
- BUG UX: Les RDV en `pending_organizer_guarantee` n'affichaient aucun CTA sur le dashboard → l'utilisateur ne voyait pas l'action requise
- CAUSE BACKEND: La logique `action_required` du timeline API ne verifiait que les garanties participants, pas le statut du RDV lui-meme
- FIX BACKEND: Ajout d'un flag `needs_organizer_guarantee` force a `true` quand status=`pending_organizer_guarantee`. Force `action_required=true` avec un label explicite
- FIX FRONTEND: Ajout CTA "Garantir le RDV" dans ActionCard et TimelineCard. Handler `handleGuaranteeOrganizer` appelle `retry-organizer-guarantee` et redirige vers Stripe ou active avec carte sauvegardee

## Stripe Redirect to Dashboard (2026-03-30)
- BUG UX: Apres paiement Stripe, retour sur /appointments/{id} au lieu du dashboard
- FIX: `return_url` change de `/appointments/{id}` vers `/dashboard` dans les 2 flows (create_appointment + retry-organizer-guarantee)
- FIX FRONTEND: Dashboard detecte `?guarantee_status=success` au retour Stripe, affiche toast, nettoie URL, rafraichit timeline
- Fichiers modifies: appointments.py, OrganizerDashboard.js

## Test Results - Iteration 159 (2026-03-30)
- Backend (7/7): timeline flags, labels, retry endpoint, appointment detail
- Frontend (6/6): boutons garantie, clic→API, reuse carte, URL handling, autres flows intacts
- Total: 13/13 PASS

## Navbar Action Required Badge (2026-03-30)
- Ajout badge rouge sur "Tableau de bord" dans la navbar avec le nombre d'actions requises
- Fetch via `appointmentAPI.myTimeline()` toutes les 60s (meme pattern que les autres badges)
- Visible en desktop et mobile (hamburger dot rouge inclus)
- Fichier modifie: AppNavbar.js

## Fix Regression Actions Requises sur RDV passes (2026-03-30)
- BUG: La condition `pending_organizer_guarantee` ajoutee precedemment ne verifiait pas `is_ended`, causant l'affichage de RDV passes dans "Actions requises"
- FIX: Ajout de `and not is_ended` a la condition (ligne 1017 de appointments.py)
- Resultat: 10 → 4 items (6 RDV passes correctement reclasses dans l'historique)

## Stale Payout Detection V1 (2026-03-30)
- Job planifie toutes les 6h : scan payouts en `processing` > 24h, marquage → `stale`
- Service: `services/stale_payout_detector.py` avec logs structures
- Route admin: `GET /api/admin/stale-payouts` (403 pour non-admin, enrichi avec email utilisateur)
- Page admin: `/admin/stale-payouts` avec etat vide, cartes STALE, montant, lien Stripe
- Lien dans le dashboard admin (`AdminDashboard.js`)
- Le webhook Stripe peut toujours ecraser stale → completed/failed
- Tests: 15/15 PASS (iteration 160)

## Test reel Zoom/Teams (2026-03-30)
- Zoom S2S OAuth: token acquis + meeting cree (https://us05web.zoom.us/j/83755430702)
- Teams delegated OAuth: meeting cree via connexion Outlook existante (https://teams.microsoft.com/l/meetup-join/...)
- Les deux integrations sont operationnelles avec de vrais tokens
- Aucun correctif necessaire

## Webhooks temps reel Zoom/Teams (2026-03-30)
- POST /api/webhooks/zoom : CRC challenge + meeting.ended → fetch attendance immediat (60s delay)
- POST /api/webhooks/teams : validation token + callRecords → fetch attendance (30s delay)
- Dedup via video_webhook_events collection
- Routes admin: GET /api/admin/webhooks/status + POST /api/admin/webhooks/teams-subscribe
- Scheduler: renouvellement subscriptions Graph toutes les 24h
- ZOOM_WEBHOOK_SECRET_TOKEN configure dans .env
- Tests: 15/15 PASS (iteration 161)
