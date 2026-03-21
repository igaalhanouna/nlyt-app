# NLYT - Product Requirements Document

## Problem Statement
SaaS application for booking appointments with financial guarantees. Zero friction, maximum automation, clear engagement logic.

## Tech Stack
- **Frontend**: React.js, TailwindCSS, Shadcn UI
- **Backend**: FastAPI, Python, APScheduler
- **Database**: MongoDB
- **Integrations**: Stripe, Resend (Emails), Google Calendar API, Microsoft Graph API (Outlook), Nominatim/OpenStreetMap (geocoding)

## Completed Features

### Phase 0-2 - Core + Stripe + Calendar (DONE)
### Phase 3 - Attendance Engine V1 (DONE)
### Phase 4 - Evidence-Based Attendance V2 (DONE)
### Phase 5 - Smart Evidence Scoring V2 (DONE)

### Phase 6 - Check-in UX + Timezone Fix (DONE — 2026-03-21)
**Check-in UX (InvitationPage):**
- Standalone prominent card (not buried inside acceptance)
- 4 time-aware states:
  - **Before window** (>30min before RDV): countdown, disabled buttons, opening time displayed
  - **During window** (30min before → end + tolerated_delay): active buttons (Je suis arrivé, Scanner QR, Afficher QR)
  - **After check-in**: green confirmation with exact time + source badges (Arrivée confirmée, QR validé, Position GPS)
  - **After window** (past end + delay): closed message with window times
- Check-in section only visible for accepted/accepted_guaranteed/accepted_pending_guarantee

**Timezone fix:**
- Backend: `_parse_appointment_start()` uses `zoneinfo.ZoneInfo('Europe/Paris')` for naive datetimes
- Frontend: `formatEvidenceDate()` uses `timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone`
- Temporal calculation now correct: CET offset applied (69.5h → 68.5h for Paris)

**Testing:** 19/19 tests passed (iteration_15)

## Key Constants
- Check-in window: opens 30min before RDV start, closes at RDV end + tolerated_delay
- Temporal window (evidence scoring): valid = RDV - 2h to RDV end + 1h
- Geographic thresholds: close (<500m), nearby (<5km), far (<50km), incoherent (>50km)
- QR rotation: 60 seconds, HMAC-signed
- Default timezone: Europe/Paris (for naive datetimes)

## Backlog
- P2: Stripe Connect (fund splits) — NOT to touch until detection is perfect
- P2: Auto-update calendar V2 (retry + notification)
- P3: Organizer analytics dashboard
- P3: Video-based attendance proof
- P3: Dispute resolution improvements
