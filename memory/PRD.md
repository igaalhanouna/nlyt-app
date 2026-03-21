# NLYT - Product Requirements Document

## Original Problem Statement
Application SaaS NLYT : plateforme de rendez-vous avec engagement financier. Objectif : zéro friction, automatisation maximale, logique d'engagement claire.

## Tech Stack
- Frontend: React.js, TailwindCSS, Shadcn UI
- Backend: FastAPI, Python, APScheduler
- Database: MongoDB
- Integrations: Resend (Emails), Stripe (Payments), Google Calendar API (OAuth 2.0)

## What's Been Implemented
1. ✅ Auth system (JWT)
2. ✅ Workspace management
3. ✅ Profile defaults
4. ✅ Appointment wizard with immutable snapshots
5. ✅ Participant invitations (Resend) + resend button
6. ✅ Invitation acceptance/decline
7. ✅ Stripe integration (real TEST mode)
8. ✅ Dashboard Upcoming/Past tabs
9. ✅ Appointment detail with participant statuses + charity
10. ✅ Penalty distribution (100%)
11. ✅ Cancellation with deadline
12. ✅ ICS export
13. ✅ Reminders (APScheduler)
14. ✅ P0: Participant status post-Stripe fix
15. ✅ P1: Stripe dead code cleanup
16. ✅ P1: Google Calendar OAuth integration (FULLY FUNCTIONAL + TESTED BY USER)
    - OAuth: connect/disconnect, CSRF state, token refresh, scope validation
    - Scopes: calendar + email + profile + openid (all granted)
    - Sync: one-shot idempotent, timezone from user's calendar
    - Cancel: auto-deletes Google event
    - UI: connected email, sync button, synced indicator, expired state
    - User tested: igaal.hanouna@gmail.com connected, event created successfully

## Prioritized Backlog

### P1
- Outlook/Microsoft 365 OAuth Integration

### P2
- Auto-sync on RDV modification (update_event ready in adapter)
- Auto-sync on RDV creation (opt-in)
- No-show detection + penalty capture (cron)
- Stripe Connect (fund splits)

### P3
- Organizer analytics dashboard

## Test Credentials
- testuser_audit@nlyt.app / TestPassword123!
- Google: igaal.hanouna@gmail.com (connected, scopes validated)
