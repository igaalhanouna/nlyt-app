# NLYT — Product Requirements Document

## Vision
SaaS de gestion d'assiduité avec garanties financières. NLYT est le **point central** pour créer, gérer et vérifier les rendez-vous physiques ET visioconférence.

## Core Requirements
1. Création de RDV (physique + vidéo) avec paramètres de pénalité
2. Invitation par email avec lien sécurisé + lien de réunion + lien NLYT Proof
3. Workflow contractuel de modification unanime
4. Garantie financière Stripe (setup mode)
5. Moteur de preuves physiques (GPS, QR, check-in)
6. **NLYT Proof System** (check-in + heartbeat + scoring) — moteur principal de vérification de présence
7. Import de présences : API auto-fetch + upload CSV/JSON (bonus, secondaire)
8. Moteur de décision d'assiduité conservateur
9. Page Intégrations avec sections Calendriers + Visioconférence
10. Emails transactionnels avec gestion correcte des timezones
11. Synchronisation calendrier (Google/Outlook)
12. **Garantie Organisateur Préalable** : l'organisateur s'engage financièrement AVANT d'engager les autres
13. **Visio décentralisée** : les utilisateurs gèrent eux-mêmes leur provider visio (Zoom/Teams/Meet) ou collent un lien externe

## Product Model — Video Provider Independence (March 2026)
### Rule
- NLYT ne crée PAS de réunions de manière centralisée
- Les utilisateurs connectent LEUR propre compte Zoom/Teams/Meet, ou collent un lien externe
- NLYT Proof (check-in + heartbeat) est le moteur PRINCIPAL de vérification de présence
- Les API vidéo (auto-fetch Zoom/Teams) sont un bonus/confirmation optionnel

### UX Wizard
- Option 1 (défaut) : "Coller un lien de visio" — champ URL libre
- Option 2 : "Connecter un provider" — Zoom, Teams, Meet (compte de l'utilisateur)
- Aucun provider auto-sélectionné, aucun badge "Recommandé"

## NLYT Proof System (March 2026)
### Architecture
- **Check-in** : Le participant ouvre son lien NLYT unique → enregistre un check-in → la visio s'ouvre dans un nouvel onglet
- **Heartbeat** : Toutes les 30s, l'onglet NLYT envoie un ping au backend pour prouver la présence continue
- **Checkout** : Le participant termine sa session → score calculé automatiquement
- **Scoring** : 0-100 basé sur : ponctualité (30pts), durée active vs attendue (40pts), confirmation API vidéo (30pts bonus)
- **Validation** : L'organisateur voit les sessions, peut valider/surcharger le statut suggéré

### Endpoints
- `GET /api/proof/{apt_id}/info?token=...` — Info rendez-vous pour page check-in
- `POST /api/proof/{apt_id}/checkin` — Démarrer session
- `POST /api/proof/{apt_id}/heartbeat` — Enregistrer ping
- `POST /api/proof/{apt_id}/checkout` — Terminer session + calcul score
- `GET /api/proof/{apt_id}/sessions` — Liste sessions (organisateur)
- `POST /api/proof/{apt_id}/validate` — Valider statut final (organisateur)

## Guarantee-First Architecture (March 2026)
### Business Rule
Un RDV ne devient jamais "active" tant que la garantie organisateur n'est pas validée.
- `pending_organizer_guarantee` = RDV créé mais invitations NON envoyées
- `active` = organisateur garanti + invitations envoyées

## Security Architecture (March 2026)
### CORS
- Production: restreint à `FRONTEND_URL`
### Rate Limiting (slowapi)
- login 10/min, register 5/min, forgot-password 3/min
- invitations 10-30/min, check-in 20-30/min, global 200/min

## Technical Stack
Frontend: React + TailwindCSS + Shadcn/UI | Backend: FastAPI + Python + MongoDB + slowapi
Email: Resend | Payments: Stripe | Video: Zoom API, Teams Graph API, Google Calendar API (tous en mode user)

## Testing
- iteration_40: 22/22 backend + 15/15 frontend (NLYT Proof System + Provider mode changes)
- Credentials: testuser_audit@nlyt.app / Test1234!

## Completed (March 2026)
- Guarantee-first architecture (pending_organizer_guarantee → active)
- CORS + SlowAPI rate limiting
- Video vs Physical check-in UX differentiation
- Meeting auto-creation regression fix
- Host experience fix (Teams lobby bypass, Meet creator email, Zoom host/participant URLs)
- Honest UX messaging (provider-specific check-in messages)
- Unified organizer identity block
- Proof availability by provider + account type
- Phase A Teams Delegated Permissions
- UX fix bandeaux Teams
- Zoom fallback CSV for free-tier accounts
- **Video Provider Independence** (March 23): Suppression mode central Zoom. Tous les providers sont mode "user". Wizard simplifié : "Coller un lien" en premier, providers connectés en secondaire. Aucun auto-select, aucun badge "Recommandé"
- **NLYT Proof System** (March 23): Système complet de vérification de présence interne. Check-in + Heartbeat (30s) + Checkout + Scoring automatique (0-100). Vue organisateur avec tableau des sessions et validation. Liens de check-in uniques par participant. Lien NLYT Proof ajouté dans les emails d'invitation

## Backlog (Prioritized)
### P1
- Stripe Connect (automatic fund distribution)
- Real-time webhooks for Zoom/Teams
### P2
- Pagination for list endpoints
- Auto-update calendar V2 (retry on failure)
### P3
- Dashboard analytics for organizers
- MongoDB connection pooling refactoring
- Extract inline HTML email templates
