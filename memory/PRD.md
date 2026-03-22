# NLYT — Product Requirements Document

## Vision
SaaS de gestion d'assiduité avec garanties financières. NLYT est le **point central** pour créer, gérer et vérifier les rendez-vous physiques ET visioconférence.

## Core Requirements
1. Création de RDV (physique + vidéo) avec paramètres de pénalité
2. Création automatique de réunions Zoom/Teams/Meet via API
3. Invitation par email avec lien sécurisé + lien de réunion
4. Workflow contractuel de modification unanime
5. Garantie financière Stripe (setup mode)
6. Moteur de preuves physiques (GPS, QR, check-in)
7. Moteur de preuves vidéo (Zoom, Teams, Google Meet)
8. Import de présences : API auto-fetch + upload CSV/JSON
9. Moteur de décision d'assiduité conservateur
10. **Page Intégrations** avec sections Calendriers + Visioconférence
11. Emails transactionnels avec gestion correcte des timezones
12. Synchronisation calendrier (Google/Outlook)

## Integrations Architecture
### Page Paramètres > Intégrations
- **Section CALENDRIERS** : Google Calendar (+ badge Meet), Outlook/Microsoft 365
- **Section VISIOCONFÉRENCE** : Zoom (carte dédiée), Microsoft Teams (carte dédiée), Google Meet (note liée à Calendar)
- **Auto-sync** : section dédiée si au moins 1 calendrier connecté

### Provider Connection Model
| Provider | Modèle | Stockage |
|----------|--------|----------|
| Google Calendar + Meet | OAuth per-user | `calendar_connections` |
| Outlook | OAuth per-user | `calendar_connections` |
| Zoom | User config + Platform env | `user_settings` (per-user) + env vars |
| Teams | User config + Platform env | `user_settings` (per-user) + env vars |

### Feature Matrix
| Provider | Calendrier | Création meeting | Présences auto |
|----------|-----------|-----------------|----------------|
| Google   | Oui       | Oui (Meet)      | Non            |
| Outlook  | Oui       | Non             | Non            |
| Zoom     | Non       | Oui             | Oui            |
| Teams    | Non       | Oui             | Oui            |

## Technical Stack
Frontend: React + TailwindCSS + Shadcn/UI | Backend: FastAPI + Python + MongoDB
Email: Resend | Payments: Stripe | Video: Zoom API, Teams Graph API, Google Calendar API

## Testing
- iteration_24: 17/17 (Video evidence MVP)
- iteration_25: 13/13 (Meeting API integration)
- iteration_26: 15/15 + full UI (Integrations page)
- Credentials: testuser_audit@nlyt.app / Test1234!
