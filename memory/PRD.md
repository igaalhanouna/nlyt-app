# NLYT - Product Requirements Document

## Original Problem Statement
Application SaaS de rendez-vous avec engagement financier anti no-show. Objectif : zéro friction, automatisation maximale, logique d'engagement claire.

## Architecture
- **Frontend**: React.js + TailwindCSS + Shadcn UI + React Router
- **Backend**: FastAPI + Python + APScheduler
- **Database**: MongoDB
- **Integrations**: Resend (emails), Stripe (paiements - MOCKED), API BAN (adresses FR)

## Core Business Rules
- **Platform commission**: 20% — system constant, NEVER user-editable. Server-side enforcement.
- **Distribution constraint**: participant% + charity% ≤ 80% (100 - platform%)
- **Valid currencies**: eur, usd, gbp, chf
- **Minimum penalty**: 1€
- **Snapshot immutability**: once an appointment is created, its policy_snapshot is immutable

## Core Features Implemented

### Phase 1 - Foundation (DONE)
- [x] Auth system (JWT, register, login, verification)
- [x] Workspace management (auto-creation, multi-workspace)
- [x] Appointment CRUD with server-side validation
- [x] Participant management (invite, accept, decline, cancel)
- [x] Email notifications (invitation, confirmation, cancellation via Resend)
- [x] Policy snapshot (immutable contract at appointment creation)
- [x] PATCH endpoint with field whitelist (security)

### Phase 1.5 - Calendar & Address (DONE)
- [x] ICS file generation and export
- [x] "Add to Calendar" buttons (Google, Outlook, Apple)
- [x] ICS links in invitation/confirmation emails
- [x] French address autocomplete (API BAN)

### Phase 1.7 - Financial Guarantee (DONE - MOCKED)
- [x] Stripe Checkout Session (Setup mode) — MOCKED with dummy key
- [x] Webhook handler for checkout.session.completed
- [x] Dev mode auto-success fallback

### Phase 1.9 - Profile Defaults (DONE - VALIDATED 2026-03-20)
- [x] Profile page as source of truth for appointment defaults
- [x] Platform commission as read-only system value (20%)
- [x] Wizard prefills from profile, auto-adjusts for platform constraint
- [x] 3 invariants validated: profile ≠ RDV, wizard ≠ profile, snapshot immutable
- [x] charity_association_id + name in appointment doc AND snapshot

### Phase 2.0 - Security & Validation Audit (DONE - 2026-03-20)
- [x] PATCH endpoint: whitelist of allowed fields
- [x] Backend validates: negative penalty, invalid currency, % overflow
- [x] Server overrides platform_commission_percent regardless of client input
- [x] Profile validates distribution against system platform commission

## Pending / Blocked
- **P0**: Stripe real keys (BLOCKED — waiting for user)

## Upcoming Tasks
- **P1**: Google Calendar OAuth integration (Phase 2)
- **P1**: Outlook / Microsoft 365 OAuth integration (Phase 2)
- **P2**: No-show detection and automated penalty capture

## Key API Endpoints
- `POST /api/auth/register` / `POST /api/auth/login`
- `GET/POST /api/appointments/` (POST enforces PLATFORM_COMMISSION_PERCENT server-side)
- `PATCH /api/appointments/{id}` (field whitelist enforced)
- `GET /api/user-settings/me/appointment-defaults` (includes platform_commission_percent)
- `PUT /api/user-settings/me` (validates % ≤ 80)
- `GET/POST /api/charity-associations/`
- `POST /api/invitations/{token}/respond`
- `POST /api/webhooks/stripe`

## DB Collections
- `users` (with `appointment_defaults` nested object)
- `workspaces`, `workspace_memberships`
- `appointments` (includes charity_association_id, charity_association_name)
- `participants`
- `policy_snapshots` (immutable, includes charity_association_id/name in payout_split)
- `acceptances`
- `charity_associations`

## Test Reports
- iteration_1: ICS MVP
- iteration_2: Address Autocomplete
- iteration_3: Calendar MVP
- iteration_4: Calendar Phase 1 Email links
- iteration_5: Stripe Mock Flow
- iteration_6: Profile → Defaults → Wizard E2E validation
- iteration_7: Audit complet — platform system value, security whitelist, snapshot complétude
