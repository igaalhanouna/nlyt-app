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
      outlook_calendar_adapter.py   # Outlook/M365 Calendar OAuth + CRUD + IANA→Windows TZ mapping
      ics_generator.py              # ICS file generation
    routers/
      calendar_routes.py            # Multi-provider sync + auto-sync + auto-update + timezone resolution
      appointments.py               # Appointment CRUD + auto-sync + auto-update triggers
      auth.py, invitations.py, participants.py, etc.
    services/
      auth_service.py, email_service.py, stripe_guarantee_service.py, etc.
  frontend/
    src/
      pages/
        settings/Integrations.js    # Google + Outlook + Auto-sync UI
        appointments/AppointmentDetail.js  # Multi-provider sync + out_of_sync + auto-sync badge
        auth/SignIn.js              # Login with persistent error message
      services/api.js               # Fixed 401 interceptor + browser timezone on connect
```

## Completed Features

### Phase 0 - Core (DONE)
- User auth, workspaces, appointment wizard, participants, Stripe guarantee, disputes, admin, reminders

### Phase 1 - Stripe Flow (DONE)
- Post-Stripe UI fix, dead code cleanup, resend invitation

### Phase 2 - Calendar Integrations (DONE — User Validated)
- Google Calendar OAuth + Outlook/M365 OAuth
- ICS export
- Auto-Sync V1 (toggle + preferred provider, triggers at appointment creation)
- Auto-Update V1 (calendar fields change → update all synced providers, out_of_sync on failure)
- **Timezone fix**: Browser TZ sent on connect, stored in connection, IANA→Windows mapping for Outlook personal accounts
- Login error message fix (401 interceptor excluded auth routes)

### Timezone Architecture
- Frontend sends `Intl.DateTimeFormat().resolvedOptions().timeZone` on connect
- Stored as `calendar_timezone` in connection document
- `_resolve_timezone()`: API detection first, fallback to stored browser TZ
- Outlook adapter: `to_windows_timezone()` maps IANA → Windows TZ IDs (required by Microsoft Graph for personal accounts)
- Google adapter: uses Google Settings API (works natively with IANA)

## Key DB Fields
- `calendar_connections.calendar_timezone`: IANA timezone from browser (e.g. "Europe/Paris")
- `calendar_sync_logs.sync_status`: "synced" | "out_of_sync" | "failed" | "deleted"
- `calendar_sync_logs.sync_source`: "auto" | "manual"
- `calendar_sync_logs.sync_error_reason`: string (when out_of_sync)
- `users.auto_sync_enabled`: boolean
- `users.auto_sync_provider`: "google" | "outlook" | null

## Calendar Fields (trigger auto-update)
`CALENDAR_FIELDS = {"title", "start_datetime", "duration_minutes", "location", "meeting_provider", "description"}`

## Azure AD Configuration
- App Registration: nlyt-outlook
- Client ID: 3336efa7-e695-492c-b07e-b7ffc9b8921a
- Redirect URIs: preview + app.nlyt.io
- Permissions: Calendars.ReadWrite, User.Read, MailboxSettings.Read (admin consented)

## Backlog
- P2: No-show detection + automated penalty capture
- P2: Stripe Connect (fund splits)
- P3: Organizer analytics dashboard
