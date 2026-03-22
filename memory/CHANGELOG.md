# NLYT — Changelog

## 2026-03-22 — Video Meeting API Integration (Phase 2) ✅

### Meeting Provider Service (`meeting_provider_service.py`)
- **ZoomMeetingClient**: Server-to-Server OAuth, create_meeting(), fetch_attendance() — ready, needs credentials
- **TeamsMeetingClient**: Graph API app permissions, create_meeting(), fetch_attendance() — ready, needs real Azure credentials
- **GoogleMeetClient**: Calendar API with conferenceData, create_meeting() — **WORKING** (creates real meet.google.com links)
- Orchestrator `create_meeting_for_appointment()` + `fetch_attendance_for_appointment()`
- Auto-resolves user tokens (Google Calendar connection, Azure AD user ID)

### Auto-Create Meeting on Appointment
- When creating a video appointment, NLYT auto-calls the provider API
- Response includes `meeting.join_url`, `meeting.external_meeting_id`, `meeting.provider`
- Non-blocking: if API fails, appointment still created with warning

### Meeting Link in Emails
- `send_invitation_email()` now accepts `meeting_join_url` and `meeting_provider`
- Email shows "Rejoindre la réunion {Provider}" button + "En ligne ({Provider})" location

### Enhanced Import (Fallback Manuel)
- **File upload (CSV/JSON)**: `POST /api/video-evidence/{apt}/ingest-file` accepts multipart form
- CSV parsing: handles Zoom CSV export format with column name variations (FR/EN)
- **File/JSON toggle**: "Fichier (CSV/JSON)" mode (default) + "JSON avancé" mode
- **File preview**: table preview for CSV, participant count for JSON
- Instructions contextuelles: "Dans Zoom, allez dans Reports > Meeting > Participants pour exporter le CSV"

### New API Endpoints
- `POST /api/video-evidence/{apt}/create-meeting` — Create meeting via provider API
- `POST /api/video-evidence/{apt}/fetch-attendance` — Fetch + auto-ingest attendance
- `POST /api/video-evidence/{apt}/ingest-file` — File upload (CSV/JSON)
- `GET /api/video-evidence/provider-status` — Check configured providers

### Frontend UI Enhancements
- "Créer la réunion" button (shown if no meeting link yet)
- "Récupérer les présences" button (shown for Zoom/Teams, NOT for Meet)
- "Import manuel" with file upload + JSON advanced mode toggle
- Drag-and-drop file zone with format-specific instructions
- CSV/JSON preview before ingestion

### Testing
- iteration_25: 13/13 tests passed + full UI verification
- No regressions on physical appointments or existing video evidence

---

## 2026-03-22 — Video Conference Attendance Evidence MVP (Phase 1) ✅
- Modular video provider adapters (Zoom, Teams, Meet)
- Evidence ingestion service with identity matching
- Conservative attendance decision engine (Meet = always manual_review)
- Video evidence timeline UI with confidence badges
- iteration_24: 17/17 tests passed

## Previous (2026-03-21 and earlier)
- Appointment timezone field, Express creation button
- Email timezone fix, Email URL fix
- Modification UX + Stripe revalidation
- GPS evidence fix
