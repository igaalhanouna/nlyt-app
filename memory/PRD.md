# NLYT - Product Requirements Document

## Vision
SaaS de prise de rendez-vous avec garanties financières (Stripe), détection de présence et preuves physiques.

## Architecture
- **Frontend**: React.js, TailwindCSS, Shadcn/UI
- **Backend**: FastAPI, Python, APScheduler, MongoDB
- **Intégrations**: Stripe (paiements), Resend (emails), Google/Outlook Calendar, Nominatim (géocodage)

## Règle fondamentale — Gestion des dates
- **Backend** : stocke et retourne TOUTES les dates en **UTC ISO** (`2026-03-22T00:04:00Z`)
- **Frontend** : convertit en heure locale via `Intl.DateTimeFormat().resolvedOptions().timeZone`
- **Utilitaire unique** : `/app/frontend/src/utils/dateFormat.js` — toutes les pages utilisent `formatDateTimeFr()`, `formatTimeFr()`, etc.
- **Backend normalization** : `normalize_to_utc()` dans `date_utils.py` — gère les dates naïves legacy (interprétées comme Europe/Paris)

## Core Features (Implémentées)
1. Auth (JWT) + Workspace management
2. Appointment creation with financial guarantees
3. Stripe payment integration for guarantee deposits
4. Invitation system with accept/decline/cancel flows
5. Calendar sync (Google/Outlook)
6. Email reminders (cancellation deadline + event)
7. Attendance Evaluation Engine V1 (APScheduler)
8. Physical Evidence System (QR, GPS, Manual check-in)
9. Smart Evidence Scoring V2 (Temporal + Geographic consistency, Nominatim reverse geocoding)
10. Participant Check-in UX (4 temporal states)

## Database Collections
- `users`, `workspaces`, `workspace_memberships`
- `appointments` (start_datetime stored in UTC with 'Z')
- `participants` (status, accepted_at, etc.)
- `evidence_items` (evidence_id, confidence_score, derived_facts)
- `checkins`, `attendance_evaluations`

## Key API Endpoints
- `POST /api/auth/login` → access_token
- `GET/POST /api/appointments/`
- `GET /api/invitations/{token}`
- `POST /api/checkin/manual`, `POST /api/checkin/qr/verify`
- `POST /api/attendance/reevaluate/{appointment_id}`

## Test Credentials
- Email: `testuser_audit@nlyt.app`
- Password: `Test1234!`

## Backlog
- P2: Stripe Connect (automated fund splits — DO NOT TOUCH YET)
- P2: Calendar sync V2 (auto-retry + notifications)
- P3: Dashboard analytics organisateur
