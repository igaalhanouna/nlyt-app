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
7. Google Calendar OAuth integration

## Tech Stack
- Frontend: React.js, TailwindCSS, Shadcn UI
- Backend: FastAPI, Python, APScheduler
- Database: MongoDB
- Integrations: Resend (Emails), Stripe (Payments), Google Calendar API (OAuth 2.0)

## Architecture
```
/app/
├── backend/
│   ├── adapters/          # ICS generator, Google Calendar adapter
│   ├── models/            # Pydantic schemas
│   ├── routers/           # API routes (calendar_routes.py has OAuth + ICS + sync)
│   ├── services/          # Business logic
│   ├── utils/             # date_utils, jwt_utils
│   ├── server.py
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── pages/settings/Integrations.js  # Google Calendar connect/disconnect UI
│   │   ├── pages/appointments/AppointmentDetail.js  # Sync to Google Calendar button
│   │   ├── services/api.js  # calendarAPI.connectGoogle/disconnectGoogle/syncAppointment
│   │   └── App.js
│   └── .env
```

## Key DB Schema
- `users`: user_id, email, appointment_defaults
- `appointments`: appointment_id, policy_snapshot_id, start_datetime, duration_minutes, status
- `participants`: participant_id, status, guarantee_id, guaranteed_at
- `payment_guarantees`: guarantee_id, stripe_session_id, status
- `policy_snapshots`: snapshot_id, is_immutable
- `calendar_connections`: connection_id, user_id, provider, google_email, access_token, refresh_token, status
- `calendar_sync_logs`: log_id, appointment_id, connection_id, external_event_id, html_link, sync_status
- `oauth_states`: user_id, provider, state, created_at

## Participant Status Flow
```
invited → accepted (no penalty)
invited → accepted_pending_guarantee → accepted_guaranteed (with Stripe)
accepted/accepted_guaranteed → cancelled_by_participant
```

## Google Calendar OAuth Flow
```
1. Frontend: GET /api/calendar/connect/google (auth required)
2. Backend: encodes user_id in state, stores in oauth_states, returns authorization_url
3. Frontend: redirects user to Google consent screen
4. Google: redirects to {FRONTEND_URL}/api/calendar/oauth/google/callback?code=xxx&state=yyy
5. Backend callback: decodes state, validates CSRF, exchanges code for tokens
6. Backend: stores connection in calendar_connections, redirects to frontend
7. Frontend: /settings/integrations?google=connected → shows success toast
```

## What's Been Implemented (Completed)
1. ✅ Auth system (JWT, email verification, password reset)
2. ✅ Workspace management
3. ✅ Profile defaults management
4. ✅ Appointment creation wizard with immutable policy snapshots
5. ✅ Participant invitations via email (Resend)
6. ✅ Invitation acceptance/decline
7. ✅ Stripe integration (real TEST mode)
8. ✅ Dashboard with Upcoming/Past tabs
9. ✅ Appointment detail with participant statuses and charity info
10. ✅ Penalty distribution validation (100%)
11. ✅ Participant cancellation with deadline enforcement
12. ✅ ICS calendar export
13. ✅ Event reminders (APScheduler)
14. ✅ P0 FIX: Participant status + counters post-Stripe
15. ✅ P1: Stripe dead code cleanup
16. ✅ BUG FIX: Resend invitation button
17. ✅ P1: Google Calendar OAuth integration (PENDING CREDENTIALS)
    - Backend: OAuth flow (connect, callback, disconnect, sync, status)
    - Frontend: Integrations page with connect/disconnect UI
    - Frontend: AppointmentDetail sync button
    - Architecture extensible for Outlook
    - Waiting for GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET

## Prioritized Backlog

### P1
- Outlook/Microsoft 365 OAuth Integration (Phase 2, architecture ready)

### P2
- No-show detection and automated penalty capture (cron/scheduler)
- Stripe Connect: Automated fund splits (participant, charity, platform)

### P3
- Organizer analytics dashboard

## Test Credentials
- testuser_audit@nlyt.app / TestPassword123!

## Environment Variables Needed
- GOOGLE_CLIENT_ID (pending from user)
- GOOGLE_CLIENT_SECRET (pending from user)
- FRONTEND_URL must match the actual preview/production domain
