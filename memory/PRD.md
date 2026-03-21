# NLYT - Product Requirements Document

## Original Problem Statement
Application SaaS NLYT : plateforme de rendez-vous avec engagement financier. Objectif : zéro friction, automatisation maximale, logique d'engagement claire.

## Tech Stack
- Frontend: React.js, TailwindCSS, Shadcn UI
- Backend: FastAPI, Python, APScheduler
- Database: MongoDB
- Integrations: Resend (Emails), Stripe (Payments), Google Calendar API (OAuth 2.0)

## Architecture
```
/app/
├── backend/
│   ├── adapters/          # ICS generator, Google Calendar adapter (OAuth + CRUD)
│   ├── models/            # Pydantic schemas
│   ├── routers/           # API routes (calendar_routes: OAuth + sync + ICS)
│   ├── services/          # stripe_guarantee_service, contract_service, email_service
│   ├── utils/             # date_utils, jwt_utils
│   ├── server.py
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── pages/settings/Integrations.js  # Google Calendar connect/disconnect
│   │   ├── pages/appointments/AppointmentDetail.js  # Sync button
│   │   ├── services/api.js  # calendarAPI
│   │   └── App.js
│   └── .env
```

## Key DB Collections
- `users`, `appointments`, `participants`, `payment_guarantees`, `policy_snapshots`
- `calendar_connections`: user_id, provider, google_email, access_token, refresh_token, status
- `calendar_sync_logs`: appointment_id, connection_id, external_event_id, html_link, sync_status
- `oauth_states`: user_id, provider, state (CSRF)

## Google Calendar OAuth Flow
```
1. GET /api/calendar/connect/google → returns authorization_url (user_id in state)
2. User consents on Google → redirect to /api/calendar/oauth/google/callback
3. Callback: validate state CSRF, exchange code → tokens, store connection
4. Redirect to /settings/integrations?google=connected
5. POST /api/calendar/sync/appointment/{id} → create Google event
6. DELETE /api/calendar/sync/appointment/{id} → delete Google event
7. cancel_appointment → auto-deletes Google event
```

## What's Been Implemented
1. ✅ Auth system (JWT)
2. ✅ Workspace management
3. ✅ Profile defaults
4. ✅ Appointment wizard with immutable snapshots
5. ✅ Participant invitations (Resend)
6. ✅ Invitation acceptance/decline
7. ✅ Stripe (real TEST mode)
8. ✅ Dashboard Upcoming/Past tabs
9. ✅ Appointment detail with statuses + charity
10. ✅ Penalty distribution (100%)
11. ✅ Cancellation with deadline
12. ✅ ICS export
13. ✅ Reminders (APScheduler)
14. ✅ P0: Participant status post-Stripe fix
15. ✅ P1: Stripe dead code cleanup
16. ✅ Resend invitation button fix
17. ✅ P1: Google Calendar OAuth integration (FULLY FUNCTIONAL)
    - OAuth connect/disconnect with CSRF + token refresh
    - Sync appointments (one-shot, idempotent)
    - Auto-delete Google event on RDV cancellation
    - Dynamic timezone (user's calendar TZ, not hardcoded UTC)
    - UI: connected state, sync button, already-synced indicator

## Prioritized Backlog

### P1
- Outlook/Microsoft 365 OAuth Integration

### P2
- Auto-sync on RDV modification (update event)
- Auto-sync on RDV creation (opt-in)
- No-show detection + penalty capture (cron)
- Stripe Connect (fund splits)

### P3
- Organizer analytics dashboard
- Bidirectional Google Calendar sync

## Env Variables
- GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET (configured)
- FRONTEND_URL (must match deployed domain)

## Test Credentials
- testuser_audit@nlyt.app / TestPassword123!
- Google Calendar connected for user d13498f9
