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
      attendance_routes.py          # Attendance evaluation + reclassification API
      auth.py, invitations.py, participants.py, etc.
    services/
      attendance_service.py         # No-show detection engine V1
      auth_service.py, email_service.py, stripe_guarantee_service.py, etc.
    utils/
      date_utils.py                 # French date formatting + now_utc()
  frontend/
    src/
      pages/
        settings/Integrations.js    # Google + Outlook + Auto-sync UI
        appointments/AppointmentDetail.js  # Multi-provider sync + Attendance UI
        auth/SignIn.js              # Login with persistent error message
      services/api.js               # All API clients including attendanceAPI
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

### Phase 3 - Attendance Engine V1 (DONE — 2026-03-21)
- **Post-appointment no-show detection engine**
- Conservative classification: no auto on_time/late, system prepares decision but doesn't decide in doubt
- Classification rules:
  - `invited` (never responded) → `waived` (decision_basis: no_response)
  - `declined` → `waived` (decision_basis: declined)
  - `guarantee_released` → `waived` (decision_basis: guarantee_released)
  - `cancelled_by_participant` in time → `waived` (decision_basis: cancelled_in_time)
  - `cancelled_by_participant` late → `no_show` (decision_basis: cancelled_late) ← clearly distinct from pure no-show
  - `accepted` / `accepted_pending_guarantee` / `accepted_guaranteed` → `manual_review`
- `auto_capture_enabled = false` (no Stripe penalty capture in V1)
- APScheduler job: every 10 min, evaluates appointments ended > 30 min ago
- Idempotent evaluation (skips already-evaluated appointments)
- Manual reclassification by organizer (on_time, late, no_show, waived)
- Stores: previous_outcome, decision_basis, reviewer_id, notes
- **API Endpoints:**
  - `POST /api/attendance/evaluate/{appointment_id}` — manual trigger
  - `GET /api/attendance/{appointment_id}` — get results
  - `PUT /api/attendance/reclassify/{record_id}` — reclassify
  - `GET /api/attendance/pending-reviews/list` — pending reviews
- **UI:** Attendance section in AppointmentDetail (summary cards + individual records + reclassify dropdown)
- **Testing:** 24/24 tests passed (backend + frontend, iteration_12)

### Timezone Architecture
- Frontend sends `Intl.DateTimeFormat().resolvedOptions().timeZone` on connect
- Stored as `calendar_timezone` in connection document
- `_resolve_timezone()`: API detection first, fallback to stored browser TZ
- Outlook adapter: `to_windows_timezone()` maps IANA → Windows TZ IDs
- Google adapter: uses Google Settings API (works natively with IANA)

## Key DB Collections/Fields
- `calendar_connections.calendar_timezone`: IANA timezone from browser
- `calendar_sync_logs.sync_status`: "synced" | "out_of_sync" | "failed" | "deleted"
- `attendance_records`: {record_id, appointment_id, participant_id, participant_email, participant_name, outcome, decision_basis, confidence, review_required, decided_by, decided_at, notes, auto_capture_enabled, previous_outcome, previous_decision_basis}
- `appointments.attendance_evaluated`: boolean
- `appointments.attendance_summary`: {waived, no_show, manual_review, on_time, late}

## Calendar Fields (trigger auto-update)
`CALENDAR_FIELDS = {"title", "start_datetime", "duration_minutes", "location", "meeting_provider", "description"}`

## Azure AD Configuration
- App Registration: nlyt-outlook
- Client ID: 3336efa7-e695-492c-b07e-b7ffc9b8921a
- Redirect URIs: preview + app.nlyt.io
- Permissions: Calendars.ReadWrite, User.Read, MailboxSettings.Read (admin consented)

## Backlog
- P2: Stripe Connect (fund splits between participant, charity, platform) — User explicitly said NOT to touch until no-show detection is perfect
- P2: Auto-update calendrier V2 (Retry automatique en cas d'échec + notification)
- P3: Dashboard analytics organisateur
