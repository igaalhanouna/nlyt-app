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
10. Page Intégrations avec sections Calendriers + Visioconférence
11. Emails transactionnels avec gestion correcte des timezones
12. Synchronisation calendrier (Google/Outlook)
13. **Garantie Organisateur Préalable** : l'organisateur s'engage financièrement AVANT d'engager les autres
14. **Check-in différencié visio/physique** : preuve connexion visio = primaire, check-in manuel = fallback

## Guarantee-First Architecture (March 2026)
### Business Rule
Un RDV ne devient jamais "active" tant que la garantie organisateur n'est pas validée.
- `pending_organizer_guarantee` = RDV créé mais invitations NON envoyées
- `active` = organisateur garanti + invitations envoyées

## Video vs Physical Check-in Logic (March 2026)
### Rule
- **Physical** : manual check-in / QR / GPS = preuves normales
- **Video** : preuve connexion conférence = primaire. Manual check-in = fallback exceptionnel

### UX
- Video RDV: CTA principal "Rejoindre la réunion" (bleu). Manual check-in relégué dans section pliable "Problème de connexion ? Check-in de secours" (ambre)
- Physical RDV: CTA principal "Je suis arrivé" (vert) + QR/GPS (inchangé)

### Scoring Backend
- Video + preuve vidéo native = "strong" (confiance haute)
- Video + aucune preuve vidéo = "weak" (toujours, peu importe les preuves physiques) → manual_review
- Physical : scoring inchangé (QR+GPS = strong, manual seul = medium, etc.)

## Security Architecture (March 2026)
### CORS
- Production: restreint à `FRONTEND_URL`
### Rate Limiting (slowapi)
- login 10/min, register 5/min, forgot-password 3/min
- invitations 10-30/min, check-in 20-30/min, global 200/min

## Technical Stack
Frontend: React + TailwindCSS + Shadcn/UI | Backend: FastAPI + Python + MongoDB + slowapi
Email: Resend | Payments: Stripe | Video: Zoom API, Teams Graph API, Google Calendar API

## Testing
- iteration_30: 16/16 frontend + 8/9 backend (guarantee-first)
- iteration_31: 23/23 frontend + 9/9 backend (video check-in differentiation)
- Credentials: testuser_audit@nlyt.app / Test1234!

## Backlog (Prioritized)
### P1
- Stripe Connect (automatic fund distribution)
- Zoom real API keys configuration
- Real-time webhooks for Zoom/Teams
- Microsoft Teams auto-creation (pending MS propagation)
### P2
- Pagination for list endpoints
- Auto-update calendar V2 (retry on failure)
### P3
- Dashboard analytics for organizers
- MongoDB connection pooling refactoring
- Extract inline HTML email templates
