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
│   ├── routers/           # API routes (appointments, invitations, webhooks, user_settings)
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
- `participants`: participant_id, status (invited/accepted/accepted_pending_guarantee/accepted_guaranteed/declined/cancelled_by_participant), guarantee_id, guaranteed_at
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
14. ✅ **Participant status + counters fix post-Stripe completion** (March 2026)
    - Fixed InvitationPage getStatusBadge for accepted_guaranteed/accepted_pending_guarantee
    - Fixed backend invitation endpoint to return guaranteed_at and guarantee_id
    - Fixed can_cancel logic for guaranteed participants
    - All counters (Dashboard + AppointmentDetail) correctly counting guaranteed participants

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
