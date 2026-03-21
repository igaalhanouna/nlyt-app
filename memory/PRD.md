# NLYT - Product Requirements Document

## Problem Statement
SaaS application for booking appointments with financial guarantees. Zero friction, maximum automation, clear engagement logic.

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
      google_calendar_adapter.py
      outlook_calendar_adapter.py
      ics_generator.py
    routers/
      attendance_routes.py          # Attendance evaluation + reclassification + re-evaluate
      checkin_routes.py             # Check-in (manual, QR, GPS) + evidence API
      calendar_routes.py
      appointments.py
      invitations.py
      webhooks.py
    services/
      attendance_service.py         # No-show detection V2 (with evidence)
      evidence_service.py           # Evidence CRUD, QR tokens, GPS, aggregation
      stripe_guarantee_service.py
      email_service.py
    utils/
      date_utils.py
  frontend/
    src/
      components/
        QRCheckin.js                # QR scanner (camera + manual fallback)
        ui/                         # Shadcn components
      pages/
        appointments/
          AppointmentDetail.js      # Evidence dashboard + attendance + re-evaluate
        invitations/
          InvitationPage.js         # Check-in section (3 modes)
        auth/SignIn.js
      services/api.js
```

## Completed Features

### Phase 0 - Core (DONE)
- User auth, workspaces, appointment wizard, participants, Stripe guarantee, disputes, admin, reminders

### Phase 1 - Stripe Flow (DONE)
- Post-Stripe UI fix, dead code cleanup, resend invitation

### Phase 2 - Calendar Integrations (DONE)
- Google Calendar + Outlook/M365 OAuth
- Auto-Sync V1, Auto-Update V1
- Timezone fix (IANA to Windows mapping for Outlook)

### Phase 3 - Attendance Engine V1 (DONE — 2026-03-21)
- Conservative classification: invited->waived, cancelled_late->no_show, accepted->manual_review
- APScheduler job every 10 min, grace window 30 min
- Manual reclassification by organizer

### Phase 4 - Evidence-Based Attendance V2 (DONE — 2026-03-21)
- **Evidence data model** (`evidence_items` collection)
- **Symmetric check-in**: "Je suis arrivé" button (timestamp + device + optional GPS)
- **QR Code system**: Dynamic, system-owned, rotating every 60s, HMAC-signed
  - Any participant can display QR, any can scan it
  - Camera scan via html5-qrcode + manual code fallback
- **GPS check-in**: One-shot, configurable radius (default 200m), consent-based
- **Evidence aggregation**: strong (2+ signals), medium (1 signal), weak (isolated), none
- **Extended decision engine**:
  - Strong evidence on_time → auto on_time
  - Strong evidence late → auto late
  - Medium evidence → classified but review_required=true
  - No/weak evidence → manual_review (conservative)
- **Re-evaluation**: Organizer can re-evaluate with fresh evidence (preserves manual reclassifications)
- **API Endpoints**:
  - `POST /api/checkin/manual` — manual check-in
  - `GET /api/checkin/qr/{apt_id}` — generate QR code (base64 + token)
  - `POST /api/checkin/qr/verify` — verify scanned QR
  - `POST /api/checkin/gps` — GPS evidence
  - `GET /api/checkin/status/{apt_id}` — check-in status
  - `GET /api/checkin/evidence/{apt_id}` — organizer evidence view
  - `POST /api/attendance/reevaluate/{apt_id}` — re-evaluate with evidence
- **UI**:
  - InvitationPage: 3 check-in modes (manual, scan QR, display QR)
  - AppointmentDetail: Check-ins & Preuves dashboard + evidence indicators on attendance records
  - QR display modal with auto-refresh
  - QR scanner modal (camera + manual fallback)
  - Re-évaluer button
- **Testing**: 30/30 tests passed (iteration_13)

## Key DB Collections
- `evidence_items`: {evidence_id, appointment_id, participant_id, source, source_timestamp, confidence_score, derived_facts, raw_payload_reference, created_by, created_at}
- `attendance_records`: {record_id, appointment_id, participant_id, outcome, decision_basis, confidence, review_required, evidence_summary, decided_by, notes, previous_outcome, auto_capture_enabled}
- `appointments.attendance_evaluated`, `appointments.attendance_summary`
- `calendar_connections`, `calendar_sync_logs`

## Philosophy
1. No proof → no automatic penalty
2. System observes signals, doesn't assume
3. Organizer is not more reliable than participant
4. Any ambiguity → manual_review
5. V1 simple > complex unstable system

## Backlog
- P2: Stripe Connect (fund splits) — User explicitly said NOT to touch until detection is perfect
- P2: Auto-update calendar V2 (retry + notification)
- P3: Organizer analytics dashboard
- P3: Video-based attendance proof
- P3: Dispute resolution system improvements
