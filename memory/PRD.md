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
      calendar_routes.py            # Multi-provider sync + auto-sync settings
      appointments.py               # Appointment CRUD + auto-sync trigger
      auth.py, invitations.py, participants.py, etc.
    services/
      auth_service.py, email_service.py, stripe_guarantee_service.py, etc.
    middleware/auth_middleware.py
    scheduler.py
    server.py
  frontend/
    src/
      pages/
        settings/Integrations.js    # Google + Outlook + Auto-sync UI
        appointments/AppointmentDetail.js  # Multi-provider sync + auto-sync badge
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

### Phase 1 - Stripe Flow (DONE)
- Post-Stripe UI bug fixed (participant status + counters)
- Dead Stripe code cleanup
- Resend Invitation button functional

### Phase 2 - Calendar Integrations (DONE - User Validated)
- **Google Calendar OAuth**: connect, disconnect, sync, unsync, auto-delete on cancellation, timezone support — USER VALIDATED
- **Outlook / Microsoft 365 Calendar**: Full OAuth flow, sync, unsync, auto-delete on cancellation — USER VALIDATED
- **ICS Export**: Per-appointment + subscription feed
- **Auto-Sync V1** (DONE - 21/21 tests passed):
  - Toggle ON/OFF in Settings > Integrations
  - User chooses ONE preferred provider for auto-sync
  - Auto-sync triggers on appointment creation (status → active)
  - Idempotent (no duplicates)
  - sync_source field: 'auto' vs 'manual' in sync logs + status
  - Zap icon in AppointmentDetail for auto-synced events
  - Manual sync buttons always available for other providers
  - No auto-update on modification (V2)
  - Auto-delete on cancellation already handled

## Key DB Collections
- `calendar_connections`: {user_id, provider, access_token, refresh_token, google_email/outlook_email, status}
- `calendar_sync_logs`: {appointment_id, connection_id, external_event_id, html_link, provider, sync_status, sync_source}
- `oauth_states`: CSRF protection for OAuth flows
- `users`: {auto_sync_enabled, auto_sync_provider} — auto-sync preferences

## API Endpoints - Calendar
- `GET /api/calendar/connect/{provider}` - Initiate OAuth (google/outlook)
- `GET /api/calendar/oauth/{provider}/callback` - OAuth callback
- `GET /api/calendar/connections` - List user's connections
- `DELETE /api/calendar/connections/{provider}` - Disconnect
- `POST /api/calendar/sync/appointment/{id}?provider=` - Manual sync
- `DELETE /api/calendar/sync/appointment/{id}` - Unsync
- `GET /api/calendar/sync/status/{id}` - Multi-provider sync status (includes sync_source)
- `GET /api/calendar/auto-sync/settings` - Get auto-sync preferences
- `PUT /api/calendar/auto-sync/settings` - Update auto-sync preferences

## Environment Variables
### Configured
- MONGO_URL, DB_NAME, JWT_SECRET
- FRONTEND_URL, CORS_ORIGINS
- RESEND_API_KEY, SENDER_EMAIL
- STRIPE_API_KEY, STRIPE_WEBHOOK_SECRET
- GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
- MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, MICROSOFT_TENANT_ID

## Backlog
- P2: Auto-update calendar event on appointment modification
- P2: No-show detection + automated penalty capture
- P2: Stripe Connect (fund splits)
- P3: Organizer analytics dashboard
