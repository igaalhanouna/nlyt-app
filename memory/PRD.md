# NLYT - Product Requirements Document

## Original Problem Statement
Application SaaS NLYT : plateforme de rendez-vous avec engagement financier. Objectif : zéro friction, automatisation maximale, logique d'engagement claire.

## User Personas
- **Organisateur** : Crée des rendez-vous avec pénalités financières, gère les participants
- **Participant** : Reçoit des invitations, accepte/refuse, fournit une garantie Stripe

## Core Requirements
1. Profil avec paramètres par défaut (pénalité, délai, distribution)
2. Wizard de création de rendez-vous avec snapshot immutable
3. Invitations par email avec lien public
4. Garantie financière via Stripe (SetupIntent/Checkout)
5. Dashboard organisateur avec onglets À venir / Passés
6. Page détail rendez-vous avec participants et statuts

## Tech Stack
- Frontend: React.js, TailwindCSS, Shadcn UI
- Backend: FastAPI, Python, APScheduler
- Database: MongoDB
- Integrations: Resend (Emails), Stripe (Payments - SetupIntents & Webhooks)

## Architecture
```
/app/
├── backend/
│   ├── adapters/          # ICS generator, Calendar adapters
│   ├── models/            # Pydantic schemas (schemas.py)
│   ├── routers/           # API routes (appointments, invitations, webhooks, user_settings, participants)
│   ├── services/          # Business logic (stripe_guarantee_service, contract_service, email_service)
│   ├── server.py          # FastAPI entry point
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── components/    # UI components (AddressAutocomplete, Shadcn)
│   │   ├── pages/         # dashboard, appointments, invitations, settings
│   │   ├── services/      # Axios API calls
│   │   └── App.js
│   └── .env
```

## Key DB Schema
- `users`: user_id, email, appointment_defaults
- `appointments`: appointment_id, policy_snapshot_id, start_datetime, duration_minutes, status
- `participants`: participant_id, status, guarantee_id, guaranteed_at, stripe_customer_id, stripe_payment_method_id
- `payment_guarantees`: guarantee_id, stripe_session_id, status (pending/completed/captured/released)
- `policy_snapshots`: snapshot_id, is_immutable

## Participant Status Flow
```
invited → accepted (no penalty)
invited → accepted_pending_guarantee → accepted_guaranteed (with Stripe)
accepted/accepted_guaranteed → cancelled_by_participant
accepted_guaranteed → guarantee_released (organizer cancels appointment)
```

## What's Been Implemented (Completed)
1. ✅ Auth system (JWT, email verification, password reset)
2. ✅ Workspace management (create, switch, membership)
3. ✅ Profile defaults management
4. ✅ Appointment creation wizard with immutable policy snapshots
5. ✅ Participant invitations via email (Resend)
6. ✅ Invitation acceptance/decline (public pages)
7. ✅ Stripe integration (real TEST mode) - Checkout Sessions, SetupIntents, Webhooks
8. ✅ Dashboard with Upcoming/Past tabs
9. ✅ Appointment detail page with participant statuses and charity info
10. ✅ Penalty distribution validation (Participant + Charity + Platform = 100%)
11. ✅ Participant cancellation with deadline enforcement
12. ✅ ICS calendar export
13. ✅ Event reminders (APScheduler)
14. ✅ **P0 FIX: Participant status + counters post-Stripe** (March 20, 2026)
    - Root cause: InvitationPage getStatusBadge() didn't handle accepted_guaranteed/accepted_pending_guarantee
    - Fixed frontend: getStatusBadge with ShieldCheck/CreditCard icons, other_participants badges
    - Fixed backend: invitation endpoint returns guaranteed_at/guarantee_id, can_cancel for guaranteed
    - Tested: 9/9 automated tests + 11 visual verifications all passed

## Prioritized Backlog

### P1
- Clean up dead Stripe code: payments.py, payment_service.py, AcceptInvitation.js
- Google Calendar OAuth Integration (Phase 2)
- Outlook/Microsoft 365 OAuth Integration (Phase 2)

### P2
- No-show detection and automated penalty capture (cron/scheduler)
- Stripe Connect: Automated fund splits (participant, charity, platform)

### P3
- Organizer analytics dashboard

## Test Credentials
- testuser_audit@nlyt.app / TestPassword123!
- Key appointment: 222f28ec-cc2d-4734-b330-bd08b2dcdb20 (Test Statut Stripe, 3 statuts mixtes)
- Key invitation token: df4600be-e050-4c9c-a8fe-250950227052 (accepted_guaranteed, real Stripe)
