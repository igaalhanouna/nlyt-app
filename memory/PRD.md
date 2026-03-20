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
- **Distribution constraint**: participant% + charity% = 80% (100 - platform%). Total always 100%.
- **Valid currencies**: eur, usd, gbp, chf
- **Minimum penalty**: 1€
- **Snapshot immutability**: once created, policy_snapshot is immutable

## Core Features Implemented

### Phase 1 - Foundation (DONE)
- [x] Auth system (JWT)
- [x] Workspace management
- [x] Appointment CRUD with server-side validation + PATCH whitelist
- [x] Participant management
- [x] Email notifications via Resend
- [x] Policy snapshot (immutable contract)

### Phase 1.5 - Calendar & Address (DONE)
- [x] ICS generation + Add to Calendar buttons
- [x] French address autocomplete (API BAN)

### Phase 1.7 - Financial Guarantee (DONE - MOCKED)
- [x] Stripe Checkout Session (setup mode)
- [x] Webhook handler (idempotent, signature-enforced, status-checked)
- [x] Guarantee release on participant cancel and organizer cancel
- [x] Dev mode for capture/release
- [x] cancel_participation handles accepted_guaranteed status

### Phase 1.9 - Profile Defaults (DONE)
- [x] Profile as source of truth for defaults
- [x] Platform commission = system value
- [x] Distribution always = 100%

### Phase 2.0 - Security Audit (DONE - 2026-03-20)
- [x] PATCH whitelist, platform override, currency validation
- [x] Webhook: signature mandatory in prod, idempotence, appointment status check
- [x] Guarantee lifecycle: release on cancel (participant + organizer)
- [x] parse_datetime handles all ISO formats

### Phase 2.1 - UX (DONE - 2026-03-20)
- [x] Dashboard: tabs "À venir" / "Passés" with end_time logic
- [x] Badge "En cours" for ongoing appointments
- [x] Charity association visible on appointment detail page

## Pending / Blocked
- **P0**: Real Stripe keys (STRIPE_API_KEY + STRIPE_WEBHOOK_SECRET)

## Upcoming Tasks
- **P1**: Google Calendar / Outlook OAuth (Phase 2 calendar)
- **P1**: Cleanup dead code (payments.py, payment_service.py, AcceptInvitation.js)
- **P2**: No-show detection + automated penalty capture
- **P2**: Stripe Connect for automated splits

## Test Reports
- iteration_1-5: Foundation features
- iteration_6: Profile → Defaults → Wizard E2E
- iteration_7: Audit complet platform/security
- Stripe audit: 4/4 functional tests PASS (idempotence, cancel+release, org cancel release)
