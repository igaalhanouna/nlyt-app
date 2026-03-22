# NLYT — Product Requirements Document

## Vision
SaaS de gestion d'assiduité avec garanties financières. Preuves de présence incontestables pour les RDV physiques ET visioconférence, avec moteur de décision conservateur.

## Personas
- **Organisateur**: Crée des RDV, définit les règles (pénalité, délai toléré), suit la présence
- **Participant**: Accepte les invitations, prouve sa présence, conteste si nécessaire

## Core Requirements
1. Création de RDV (physique + vidéo) avec paramètres de pénalité
2. Invitation par email avec lien sécurisé
3. Workflow contractuel de modification unanime
4. Garantie financière Stripe (setup mode)
5. Moteur de preuves physiques (GPS, QR, check-in manuel)
6. **Moteur de preuves vidéo (Zoom, Teams, Google Meet)** ← NEW
7. Moteur de décision d'assiduité conservateur
8. Flow de modification contractuel avec revalidation de garantie
9. Emails transactionnels (Resend) avec gestion correcte des timezones
10. Bouton de création express

## Technical Stack
- Frontend: React.js + TailwindCSS + Shadcn/UI
- Backend: FastAPI + Python + Pydantic
- Database: MongoDB
- Email: Resend (notify.nlyt.io)
- Payments: Stripe
- Geo: Nominatim (OpenStreetMap)

## Architecture
```
/app/backend/
├── adapters/
│   ├── google_calendar_adapter.py
│   ├── outlook_calendar_adapter.py
│   └── video_providers/         ← NEW
│       ├── base.py              (Interface VideoProviderAdapter)
│       ├── zoom_adapter.py      (Ceiling: strong)
│       ├── teams_adapter.py     (Ceiling: strong)
│       └── meet_adapter.py      (Ceiling: assisted)
├── models/schemas.py
├── routers/
│   ├── appointments.py
│   ├── attendance_routes.py
│   ├── checkin_routes.py
│   ├── video_evidence_routes.py ← NEW
│   └── ...
├── services/
│   ├── attendance_service.py    (Extended: video decision rules)
│   ├── evidence_service.py      (Extended: video_conference source)
│   ├── video_evidence_service.py ← NEW
│   └── ...
```

## Key Data Models
- `appointments`: appointment_type, meeting_provider, external_meeting_id, meeting_join_url, appointment_timezone
- `evidence_items`: source="video_conference", derived_facts={provider, joined_at, left_at, identity_confidence, video_attendance_outcome, provider_evidence_ceiling}
- `video_ingestion_logs`: ingestion audit trail with payload hash dedup
- `attendance_records`: outcome, decision_basis, video_context (for video RDV)

## Video Evidence Rules (V1)
| Provider | Evidence Ceiling | Identity | Auto-Decision? |
|----------|-----------------|----------|----------------|
| Zoom     | strong          | high (email match) | Yes: on_time/late |
| Teams    | strong          | high (AAD email)   | Yes: on_time/late |
| Meet     | **assisted**    | **always low**     | **NEVER** → manual_review |

- Google Meet seul ne déclenche JAMAIS de pénalité automatique
- Identité ambiguë → manual_review
- Logs ambigus → manual_review
- Durée < 50% → manual_review

## Testing
- Test reports: /app/test_reports/
- Test credentials: testuser_audit@nlyt.app / Test1234!

## Status
- P0 Video Evidence MVP: DONE ✅ (2026-03-22)
- All tests: 17/17 passed
