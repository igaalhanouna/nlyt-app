# NLYT — Product Requirements Document

## Vision
SaaS de gestion d'assiduité avec garanties financières. NLYT est le **point central** pour créer, gérer et vérifier les rendez-vous physiques ET visioconférence.

## Core Requirements
1. Création de RDV (physique + vidéo) avec paramètres de pénalité
2. **Création automatique de réunions** Zoom/Teams/Meet via API
3. Invitation par email avec lien sécurisé + lien de réunion
4. Workflow contractuel de modification unanime
5. Garantie financière Stripe (setup mode)
6. Moteur de preuves physiques (GPS, QR, check-in)
7. Moteur de preuves vidéo (Zoom, Teams, Google Meet)
8. **Import de présences** : API auto-fetch (Zoom/Teams) + upload CSV/JSON + JSON avancé
9. Moteur de décision d'assiduité conservateur
10. Emails transactionnels avec gestion correcte des timezones
11. Synchronisation calendrier (Google/Outlook)

## Technical Stack
- Frontend: React.js + TailwindCSS + Shadcn/UI
- Backend: FastAPI + Python + Pydantic + MongoDB
- Email: Resend (notify.nlyt.io), Payments: Stripe
- Video: Zoom API, Teams Graph API, Google Calendar API (Meet)

## Architecture
```
backend/
├── adapters/
│   ├── google_calendar_adapter.py
│   ├── outlook_calendar_adapter.py
│   └── video_providers/
│       ├── base.py (VideoProviderAdapter interface)
│       ├── zoom_adapter.py (ceiling: strong)
│       ├── teams_adapter.py (ceiling: strong)
│       └── meet_adapter.py (ceiling: assisted)
├── services/
│   ├── meeting_provider_service.py (ZoomMeetingClient, TeamsMeetingClient, GoogleMeetClient)
│   ├── video_evidence_service.py (ingestion + matching)
│   ├── evidence_service.py (extended: video_conference)
│   ├── attendance_service.py (extended: video decision)
│   └── email_service.py (meeting_join_url in emails)
├── routers/
│   ├── video_evidence_routes.py (create-meeting, fetch-attendance, ingest, ingest-file, provider-status)
│   └── appointments.py (auto-create meeting on video apt)
```

## Meeting Creation Flow
1. User creates video appointment → NLYT auto-calls provider API
2. Provider returns meeting_id + join_url → stored in appointment
3. Join link displayed in UI + sent in invitation emails + synced to calendar
4. After meeting: fetch attendance via API (Zoom/Teams) or manual import (Meet/fallback)

## Provider Configuration
| Provider | Status | Features | Credentials |
|----------|--------|----------|-------------|
| Zoom | Ready (needs credentials) | create_meeting, fetch_attendance | ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET |
| Teams | Ready (needs credentials) | create_meeting, fetch_attendance | MICROSOFT_TENANT_ID, MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET |
| Meet | **CONFIGURED** | create_meeting (via Calendar API) | GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET (existing) |

## Video Evidence Rules (V1)
| Provider | Evidence Ceiling | Identity Match | Auto-Decision |
|----------|-----------------|---------------|---------------|
| Zoom | strong | high (email) | Yes |
| Teams | strong | high (AAD) | Yes |
| Meet | **assisted** | **always low** | **NEVER** |

## Testing
- iteration_24: 17/17 MVP tests passed
- iteration_25: 13/13 API integration tests passed + full UI verification
- Credentials: testuser_audit@nlyt.app / Test1234!
