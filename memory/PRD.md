# NLYT - Product Requirements Document

## Problem Statement
SaaS application for booking appointments with financial guarantees (engagement financier). Zero friction, maximum automation, clear engagement logic.

## Tech Stack
- **Frontend**: React.js, TailwindCSS, Shadcn UI
- **Backend**: FastAPI, Python, APScheduler
- **Database**: MongoDB
- **Integrations**: Stripe, Resend (Emails), Google Calendar API, Microsoft Graph API (Outlook)

## Core Architecture
```
/app/
  backend/
    adapters/
      google_calendar_adapter.py    # Google Calendar OAuth + CRUD
      outlook_calendar_adapter.py   # Outlook/M365 Calendar OAuth + CRUD
      ics_generator.py              # ICS file generation
    routers/
      calendar_routes.py            # Multi-provider calendar routes
      appointments.py               # Appointment CRUD + cancellation
      auth.py, invitations.py, participants.py, etc.
    services/
      auth_service.py, email_service.py, stripe_guarantee_service.py, etc.
    middleware/auth_middleware.py
    scheduler.py
    server.py
  frontend/
    src/
      pages/
        settings/Integrations.js    # Google + Outlook connection UI
        appointments/AppointmentDetail.js  # Multi-provider sync buttons
      services/api.js               # All API methods
```

## Completed Features

### Phase 0 - Core
- User auth (register, login, email verification, password reset)
- Workspaces
- Appointment creation wizard (multi-step)
- Participant management with invitation emails
- Stripe payment guarantee flow
- Policy templates and contract snapshots
- Dispute system
- Admin dashboard
- Reminders via APScheduler

### Phase 1 - Stripe Flow
- Post-Stripe UI bug fixed (participant status + counters)
- Dead Stripe code cleanup
- Resend Invitation button functional

### Phase 2 - Calendar Integrations (DONE - User Validated)
- **Google Calendar OAuth**: connect, disconnect, sync, unsync, auto-delete on cancellation, timezone support — USER VALIDATED ✅
- **Outlook / Microsoft 365 Calendar**: 
  - OAuth flow (connect, callback, disconnect) — USER VALIDATED ✅
  - Sync appointment to Outlook Calendar — USER VALIDATED ✅
  - Token refresh, idempotency (no duplicates), event_id storage
  - Auto-delete on appointment cancellation
  - Multi-provider sync status API
  - Frontend: Integrations page + AppointmentDetail sync buttons
- **ICS Export**: Per-appointment + subscription feed

## Key DB Collections
- `calendar_connections`: {user_id, provider, access_token, refresh_token, google_email/outlook_email, status, connection_id}
- `calendar_sync_logs`: {appointment_id, connection_id, external_event_id, html_link, provider, sync_status}
- `oauth_states`: CSRF protection for OAuth flows

## API Endpoints - Calendar
- `GET /api/calendar/connect/{provider}` - Initiate OAuth (google/outlook)
- `GET /api/calendar/oauth/{provider}/callback` - OAuth callback
- `GET /api/calendar/connections` - List user's connections
- `DELETE /api/calendar/connections/{provider}` - Disconnect
- `POST /api/calendar/sync/appointment/{id}?provider=` - Sync to calendar
- `DELETE /api/calendar/sync/appointment/{id}` - Unsync from all calendars
- `GET /api/calendar/sync/status/{id}` - Multi-provider sync status

## Environment Variables
### Configured ✅
- MONGO_URL, DB_NAME, JWT_SECRET
- FRONTEND_URL, CORS_ORIGINS
- RESEND_API_KEY, SENDER_EMAIL
- STRIPE_API_KEY, STRIPE_WEBHOOK_SECRET
- GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
- MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, MICROSOFT_TENANT_ID

## Backlog
- P2: Auto-sync on appointment creation/modification
- P2: No-show detection + automated penalty capture
- P2: Stripe Connect (fund splits)
- P3: Organizer analytics dashboard
