# NLYT — Changelog

## 2026-03-22 — Video Conference Attendance Evidence MVP (P0) ✅

### Architecture
- Created modular video provider adapters: `backend/adapters/video_providers/`
  - `base.py`: Abstract interface (`VideoProviderAdapter`, `NormalizedAttendanceRecord`)
  - `zoom_adapter.py`: Zoom attendance report normalization (ceiling: strong)
  - `teams_adapter.py`: Teams Graph API attendance normalization (ceiling: strong)
  - `meet_adapter.py`: Google Meet attendance normalization (ceiling: **assisted** — always low confidence)

### Models / Schema
- Added `external_meeting_id`, `meeting_join_url` to `AppointmentCreate` and `AppointmentResponse`
- Added these fields to appointment document creation and PATCH whitelist
- New collection: `video_ingestion_logs` (audit trail with payload hash dedup)
- New collection: `video_webhook_logs` (scaffolded for future webhook processing)

### Ingestion Service (`video_evidence_service.py`)
- `ingest_video_attendance()`: Main entry point — validates, normalizes, matches, creates evidence
- Identity matching: exact email (high), domain+name (medium), name-only (low)
- Duplicate detection via payload hash
- Creates `evidence_items` with `source="video_conference"` and rich `derived_facts`

### Evidence Engine Extension (`evidence_service.py`)
- Added `video_conference` as a new evidence source
- Video-aware strength calculation:
  - Video appointments: video evidence is primary signal
  - Physical appointments: video can boost physical evidence
  - Google Meet: always weak without physical boost
- Return includes `video_provider`, `video_provider_ceiling`, `video_identity_confidence`, `video_outcome`

### Attendance Decision Engine Extension (`attendance_service.py`)
- Video appointment branch with conservative rules:
  - Zoom/Teams + strong evidence + on_time → `on_time` (auto)
  - Zoom/Teams + strong evidence + late → `late` (auto)
  - Zoom/Teams + medium evidence → outcome + review required
  - Meet assisted → ALWAYS `manual_review`
  - Weak/ambiguous → ALWAYS `manual_review`
- Physical appointment logic: UNCHANGED (no regression)

### API Routes (`video_evidence_routes.py`)
- `POST /api/video-evidence/{apt_id}/ingest` — Organizer imports attendance report
- `GET /api/video-evidence/{apt_id}` — Get video evidence
- `GET /api/video-evidence/{apt_id}/logs` — Get ingestion logs
- `GET /api/video-evidence/{apt_id}/log/{id}` — Get specific ingestion log
- `POST /api/video-evidence/webhook/{provider}` — Webhook scaffold (logs only in V1)

### Frontend UI (`AppointmentDetail.js`)
- Provider badge display (Zoom/Teams/Meet with colors)
- External meeting ID + join URL link
- Video evidence timeline: join/leave times, duration, identity confidence badge, temporal info, matching details
- Ingestion form: provider dropdown, meeting ID, URL, JSON textarea, context-specific placeholders
- Google Meet warning banner in ingestion form
- Ingestion logs history section
- Decision labels extended for video-specific outcomes

### Testing
- 17/17 tests passed (backend + frontend)
- Test report: `/app/test_reports/iteration_24.json`
- Backend tests: `/app/backend/tests/test_video_evidence.py`
- Conservative rules all verified:
  - ✅ Google Meet always low confidence, always manual_review
  - ✅ Zoom/Teams high identity → auto-decision
  - ✅ Ambiguous identity → manual_review
  - ✅ Physical appointments: no regression

### Known Limitations (V1)
- Webhooks scaffolded but not auto-processed (manual ingestion only)
- No real-time Zoom/Teams API integration (organizer exports + imports reports)
- Google Meet always requires manual review
- No video recording evidence yet

---

## Previous Changelog (from earlier sessions)

### 2026-03-21 — Appointment Timezone & Domain Fix
- Added `appointment_timezone` field (captured from browser)
- Fixed Resend sender domain to `notify.nlyt.io`

### 2026-03-21 — Express Creation Button
- "Validation express" button in wizard step 2

### 2026-03-20 — Email Timezone Fix
- Centralized `format_email_datetime` for consistent timezone handling

### 2026-03-20 — Email URL Fix
- Fixed broken relative URLs in emails → absolute with FRONTEND_URL

### 2026-03-19 — Modification UX + Stripe Revalidation
- Moved edit button to header
- Stripe guarantee revalidation on significant changes
- UI and emails for guarantee reconfirmation

### 2026-03-18 — GPS Evidence Fix
- Old coordinates cleared and recalculated on address change
