# NLYT - Product Requirements Document

## Original Problem Statement
Application SaaS (React/FastAPI/MongoDB) de gestion des presences avec garanties financieres via le moteur "Trustless V4". L'objectif est d'optimiser le moteur Trustless V4 et l'UX globale.

## Core Architecture
- **Frontend**: React + Shadcn/UI
- **Backend**: FastAPI + MongoDB
- **Payments**: Stripe
- **Email**: Resend
- **Video**: Zoom, Microsoft Teams, Google Meet (OAuth)

## Completed Features

### Session 1-4 (Previous)
- Full Trustless V4 engine, Appointment CRUD, Invitation flow, Calendar integration
- Video evidence system, Attendance evaluation engine, Dispute system
- Financial distribution engine, Wallet system, Policy snapshot

### Session 5-8 (Previous)
- Cancel Guards (UX + backend restrictions)
- Disputes UX Refactor (grouped by appointment)
- Presences UX Refactor (read-only mode)
- Orphan Participants Fix (user_id linking + migration)

### Session 9 - Modification Flow Fix (2026-03-29)
- Direct modification when 0 accepted non-org participants
- Proposal mode when >=1 accepted non-org participant
- UX adaptive modal (title/button/description per mode)
- Notification emails in direct mode to all participants

### Session 10 - Organizer Participant Migration (2026-03-29)
- 209 org-participant records inserted + 2 flags corrected (344/345 covered)
- Fixed seed_demo.py to inject org-participant
- Idempotent script with migrated_at tag

### Session 11 - Modification Visibility & Bidirectional System (2026-03-29)
- API GET /api/modifications/mine
- Bidirectional response on detail page
- Dashboard modifications section
- Timeline card badges
- JWT-based participant resolution
- Participant propose from detail page

### Session 12 - Fix Modification Summary Display (2026-03-30)
- Fixed formatChangeSummary() displaying only time changes

### Session 13 - P2.1 Timeline History + P2.2 Vote Progress (2026-03-30)
- VoteProgressBar + full chronological timeline

### Session 14 - P1: Dashboard Admin Arbitrage des litiges (2026-03-30)
- Admin arbitration service, routes, frontend pages

### Session 15 - Consequences financieres + KPI cliquables (2026-03-30)
- Financial context in disputes, clickable KPI filters

### Session 16 - Onglet Decisions utilisateur (2026-03-31)
- Decisions list and detail pages

### Session 17-18 - Reorganisation navbar + Statistiques (2026-03-31)
- Navbar reorganization, Statistics page moved to Settings

### Session 19 - Fix bouton Modifier participant (2026-03-31)
### Session 20 - Guard deadline modification (2026-03-31)
### Session 21 - Harmonisation UX check-in (2026-03-31)
### Session 22 - Historique modifications sur cartes dashboard (2026-03-31)
### Session 23 - Fusion Actions requises Dashboard (2026-03-29)
### Session 24 - Notifications in-app P0+P1 (2026-03-29)
### Session 25 - Notifications email P0+P1 (2026-03-29)
### Session 27 - Fix doublon email modifications (2026-03-29)
### Session 28 - Refonte UX Decisions + Emails modifications (2026-03-29)
### Session 29 - Refonte Onboarding Invitation -> Dashboard (2026-02-25)
### Session 30 - OAuth Google + Microsoft (2026-02-25)
### Session 31 - Back-office Associations (2026-03-29)

### Session 32 - Charity Payouts V1 (2026-03-29)
**Objectif:** Permettre a l'admin d'enregistrer des virements bancaires manuels vers les associations caritatives, en debitant leur wallet interne de maniere atomique.

**Backend (`/app/backend/routers/charity_payout_routes.py`) :**
- `GET /api/admin/payouts/dashboard` : Liste des associations actives avec solde wallet, IBAN, dernier reversement
- `GET /api/admin/payouts` : Historique des reversements (enrichi avec nom admin)
- `POST /api/admin/payouts` : Creation d'un payout + debit wallet atomique
  - Verifications: association active, IBAN configure, montant > 0, montant <= available_balance
  - Flow: insert payout record -> debit wallet atomique -> rollback si echec
  - Audit trail: iban_snapshot, bic_snapshot, account_holder_snapshot, created_by, transfer_date, bank_reference

**Backend (`/app/backend/routers/charity_associations.py`) modifie :**
- Ajout champs `iban`, `bic`, `account_holder` au schema
- Validation IBAN: longueur 15-34, commence par 2 lettres + 2 chiffres, alphanumerique
- Normalisation: suppression espaces, mise en majuscules

**Backend (`/app/backend/services/wallet_service.py`) modifie :**
- Nouvelle fonction `debit_charity_payout()` : bypass du minimum 5 EUR pour les reversements charity
- Refactoring: logique commune extraite dans `_debit_payout_internal()`

**Frontend (`/app/frontend/src/pages/admin/AdminPayouts.js`) :**
- KPIs: A reverser, En attente (contestation), Total reverse
- Cartes par association: nom, solde disponible/en attente, IBAN masque (****XXXX), titulaire, dernier reversement
- Bouton "Enregistrer un virement" (desactive si pas de solde ou pas d'IBAN)
- Formulaire: montant, reference bancaire, date du virement
- Historique expandable par association avec ref, montant, admin, date

**Frontend modifie :**
- `AdminAssociations.js`: champs IBAN/BIC/titulaire dans formulaire + affichage masque en liste
- `AdminDashboard.js`: carte "Reversements" ajoutee au hub (4 sections)
- `App.js`: route `/admin/payouts`

**Schema `charity_payouts`:**
```
{
  payout_id, association_id, association_name,
  amount_cents, currency, status ("completed"),
  transfer_method ("manual_bank_transfer"),
  bank_reference, transfer_date,
  iban_snapshot, bic_snapshot, account_holder_snapshot,
  created_by, created_at
}
```

**Valide via testing_agent iteration 151 (100%: 28/28 backend, 100% frontend)**

## Data Integrity Rules
- Participant documents MUST have valid user_id when user exists
- Every appointment MUST have an is_organizer=True participant record
- Modification proposals require unanimity from all involved parties
- Direct modification when 0 accepted non-org participants
- ObjectId exclusion from all MongoDB responses
- Charity wallet debit ONLY on completed payout (never on view/prepare)

## Business Rules - Charity Payouts V1
- Manual bank transfer only (no Stripe Connect)
- Wallet debited atomically only when admin records a completed transfer
- IBAN must be configured before any payout
- Full audit trail: IBAN snapshot, admin ID, bank reference, transfer date
- No pending state — payout is always "completed"

## Upcoming Tasks (P1)
- Configurer le webhook Stripe en production pour validation end-to-end
- Test reel Zoom/Teams avec vrais tokens

## Future Tasks (P2)
- Charity Payouts V2 (Automatisation via Stripe Connect ou API bancaire tierce)
- Webhooks temps reel Zoom/Teams
