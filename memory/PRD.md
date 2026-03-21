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
      calendar_routes.py            # Multi-provider sync + auto-sync + auto-update
      appointments.py               # Appointment CRUD + auto-sync trigger + auto-update trigger
      auth.py, invitations.py, participants.py, etc.
    services/
      auth_service.py, email_service.py, stripe_guarantee_service.py, etc.
  frontend/
    src/
      pages/
        settings/Integrations.js    # Google + Outlook + Auto-sync UI
        appointments/AppointmentDetail.js  # Multi-provider sync + out_of_sync + auto-sync badge
        auth/SignIn.js              # Login with persistent error message
      services/api.js               # Fixed 401 interceptor
```

## Completed Features

### Phase 0 - Core (DONE)
- User auth, workspaces, appointment wizard, participants, Stripe guarantee, disputes, admin, reminders

### Phase 1 - Stripe Flow (DONE)
- Post-Stripe UI fix, dead code cleanup, resend invitation

### Phase 2 - Calendar Integrations (DONE)
- Google Calendar OAuth + Outlook/M365 OAuth (connect, disconnect, sync, unsync)
- ICS export

### Phase 2.1 - Auto-Sync (DONE — 21/21 tests)
- Toggle ON/OFF + provider preference in Integrations
- Auto-sync at appointment creation (→ active) to preferred provider
- Idempotent, sync_source: auto/manual, Zap icon for auto-synced

### Phase 2.2 - Auto-Update (DONE — 27/27 tests)
- Calendar fields that trigger auto-update: title, start_datetime, duration_minutes, location, meeting_provider, description
- Non-calendar fields (penalty_amount, etc.) do NOT trigger update
- Updates ALL already-synced providers (not just preferred)
- On failure: sync_status → "out_of_sync" with sync_error_reason
- Out-of-sync UI: amber AlertTriangle button with error reason tooltip
- Manual re-sync on out_of_sync does UPDATE (not CREATE)
- Never blocks appointment save

### Bug Fix - Login Error Message (DONE)
- 401 interceptor now excludes auth routes (was causing page reload on login failure)
- Persistent red error message in login form

## Key DB Fields
- `calendar_sync_logs.sync_status`: "synced" | "out_of_sync" | "failed"
- `calendar_sync_logs.sync_source`: "auto" | "manual"
- `calendar_sync_logs.sync_error_reason`: string (when out_of_sync)
- `users.auto_sync_enabled`: boolean
- `users.auto_sync_provider`: "google" | "outlook" | null

## Calendar Fields (trigger auto-update)
`CALENDAR_FIELDS = {"title", "start_datetime", "duration_minutes", "location", "meeting_provider", "description"}`

## Backlog
- P2: No-show detection + automated penalty capture
- P2: Stripe Connect (fund splits)
- P3: Organizer analytics dashboard
