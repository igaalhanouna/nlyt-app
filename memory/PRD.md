# NLYT - Product Requirements Document

## Original Problem Statement
Application SaaS de rendez-vous avec engagement financier. Objectif : zéro friction, automatisation maximale, logique d'engagement claire.

## Architecture
- **Frontend**: React.js + TailwindCSS + Shadcn UI + React Router
- **Backend**: FastAPI + Python + APScheduler
- **Database**: MongoDB
- **Integrations**: Resend (emails), Stripe (paiements - MOCKED), API BAN (adresses FR)

## Core Features Implemented

### Phase 1 - Foundation (DONE)
- [x] Auth system (JWT, register, login, verification)
- [x] Workspace management (auto-creation, multi-workspace)
- [x] Appointment CRUD (create wizard, list, detail, cancel, delete)
- [x] Participant management (invite, accept, decline, cancel)
- [x] Email notifications (invitation, confirmation, cancellation via Resend)
- [x] Policy snapshot (immutable contract at appointment creation)

### Phase 1.5 - Calendar & Address (DONE)
- [x] ICS file generation and export
- [x] "Add to Calendar" buttons (Google, Outlook, Apple)
- [x] ICS links in invitation/confirmation emails
- [x] French address autocomplete (API BAN)

### Phase 1.7 - Financial Guarantee (DONE - MOCKED)
- [x] Stripe Checkout Session (Setup mode) - **MOCKED with dummy key `sk_test_emergent`**
- [x] Webhook handler for `checkout.session.completed`
- [x] Dev mode auto-success fallback
- [x] Participant status flow: invited → accepted_pending_guarantee → accepted_guaranteed

### Phase 1.9 - Profile Defaults (DONE - VALIDATED 2026-03-20)
- [x] Profile page (/settings/profile) as source of truth for appointment defaults
- [x] Backend API: GET/PUT /api/user-settings/me, GET /api/user-settings/me/appointment-defaults
- [x] Charity associations management (CRUD + selection)
- [x] Wizard prefills from profile defaults on mount
- [x] Freemium mode: platform commission locked at 20%, charity auto-adjusted
- [x] Snapshot immutability verified: profile changes don't affect existing appointments
- [x] Three invariants validated:
  1. Profile modification ≠ existing appointments modification
  2. Wizard modification ≠ profile modification
  3. Defaults used only at creation time (copy by value)

### Cleanup (DONE)
- [x] Hardcoded preview URL audit and removal
- [x] Canonical URL enforcement via .env variables
- [x] System audit and frontend JSON parsing bugfix

## Pending / Blocked

### P0: Stripe Real Integration (BLOCKED)
- Waiting for user to provide real Stripe keys (STRIPE_API_KEY, STRIPE_WEBHOOK_SECRET)
- Code ready, currently in dev/mock mode

## Upcoming Tasks

### P1: Calendar Phase 2
- Google Calendar OAuth integration
- Outlook / Microsoft 365 OAuth integration
- `/app/backend/adapters/google_calendar_adapter.py` exists (skeleton)

### P2: No-Show Detection
- Automated penalty capture via cron/scheduler
- APScheduler already integrated for reminders

## Key API Endpoints
- `POST /api/auth/register` / `POST /api/auth/login`
- `GET/POST /api/appointments/`
- `GET /api/user-settings/me/appointment-defaults`
- `PUT /api/user-settings/me`
- `GET/POST /api/charity-associations/`
- `POST /api/invitations/{token}/respond`
- `POST /api/webhooks/stripe`
- `GET /api/calendar/export/ics/{appointment_id}`

## DB Collections
- `users` (with `appointment_defaults` nested object)
- `workspaces`, `workspace_memberships`
- `appointments`, `participants`
- `policy_snapshots` (immutable)
- `acceptances`
- `charity_associations`

## Test Credentials (Preview)
- Email: testuser_audit@nlyt.app
- Password: TestPassword123!

## Test Reports
- iteration_1: ICS MVP
- iteration_2: Address Autocomplete
- iteration_3: Calendar MVP
- iteration_4: Calendar Phase 1 Email links
- iteration_5: Stripe Mock Flow
- iteration_6: Profile → Defaults → Wizard E2E validation
