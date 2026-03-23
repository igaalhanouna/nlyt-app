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
- iteration_32: 22/22 frontend + 12/13 backend (meeting auto-creation fix)
- iteration_33: 7/7 frontend + 16/16 backend (host experience improvements)
- iteration_34: all frontend + 11/11 backend (honest UX messaging)
- iteration_35: 11/11 frontend + 6/6 backend (unified organizer identity block)
- iteration_36: 25/25 frontend + 7/7 backend (proof availability by provider + account type)
- iteration_37: 21/21 frontend + 6/6 backend (Phase A Teams delegated permissions)
- iteration_38: 17/17 frontend (UX fix bandeaux Teams — visibility + text wrapping)
- Credentials: testuser_audit@nlyt.app / Test1234!

## Completed (March 2026)
- Guarantee-first architecture (pending_organizer_guarantee → active)
- CORS + SlowAPI rate limiting
- Video vs Physical check-in UX differentiation
- **Meeting auto-creation regression fix** (March 22): Restored Microsoft Teams credentials, improved is_configured() guard, added error logging in lifecycle
- **Host experience fix** (March 22): Teams lobby bypass (scope=everyone, allowedPresenters=organizer), Meet creator email hint in UI, Zoom host/participant URL distinction in frontend
- **Honest UX messaging** (March 22): Provider-specific check-in messages (auto-fetch Zoom/Teams, manual import Meet), contextual evidence action bars, auto-fetch scheduler job (5min interval after meeting end)
- **Unified organizer identity block** (March 22): "Connexion en tant qu'organisateur" for all providers — shows creator email (Google/Microsoft/Zoom), provider-specific guidance, only visible to organizer (not participants)
- **Proof availability by provider + account type** (March 22): Meet Gmail perso = ❌ rouge (no auto proof, manual check-in promoted as primary), Meet Workspace = ⚠️ ambre (import manual), Teams/Zoom = ✅ vert (auto-fetch). Check-in button promoted for Meet personal, hidden as fallback for auto-fetch providers
- **Phase A Teams Delegated Permissions** (March 22): Refonte création Teams via /me/onlineMeetings avec token utilisateur délégué. Scope OnlineMeetings.ReadWrite ajouté à OAuth Outlook. Fallback explicite sur app permissions avec bandeau orange 'Mode legacy — identité technique'. Bandeau de reconnexion dans Settings. Metadata stocke creation_mode: delegated|application_fallback
- **UX fix bandeaux Teams** (March 22): Tous les bandeaux Teams (legacy orange, delegated vert, attention ambre) et Outlook (mise à jour recommandée) refaits avec text-sm, fonds colorés, icônes, padding et wrap correct. Plus aucun texte tronqué ou invisible
- **Zoom provider grand public** (March 23): Zoom comme provider principal en mode central (aucun compte requis pour les participants). UI refaite avec badges: Zoom=Recommandé, Teams=Avancé, Meet=Limité, Externe=Manuel. Auto-sélection Zoom quand configuré. join_before_host:true, creation_mode:'central'. Fallback propre si Zoom pas encore configuré ('Configuration en cours')

## Backlog (Prioritized)
### P1
- Stripe Connect (automatic fund distribution)
- Zoom real API keys configuration
- Real-time webhooks for Zoom/Teams
### P2
- Pagination for list endpoints
- Auto-update calendar V2 (retry on failure)
### P3
- Dashboard analytics for organizers
- MongoDB connection pooling refactoring
- Extract inline HTML email templates
