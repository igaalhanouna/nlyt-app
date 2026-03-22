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

## Guarantee-First Architecture (March 2026)
### Business Rule
Un RDV ne devient jamais "active" tant que la garantie organisateur n'est pas validée.
- `pending_organizer_guarantee` = RDV créé mais invitations NON envoyées
- `active` = organisateur garanti + invitations envoyées + flux aval autorisés

### Option A — Carte par défaut (cible idéale)
- Utilisateur enregistre une carte dans Paramètres > Paiement
- Garantie organisateur créée automatiquement avec la carte enregistrée
- RDV activé immédiatement, invitations envoyées

### Option B — Fallback Stripe redirect
- Si pas de carte par défaut, organisateur redirigé vers Stripe Checkout
- RDV reste en `pending_organizer_guarantee`
- Activation via webhook Stripe (source de vérité) + polling frontend (confort)

### Pattern Stripe
- Settings: `stripe.checkout.Session.create(mode="setup")` → captures PaymentMethod
- Auto-guarantee: PaymentMethod réutilisé (pas de nouvel appel Stripe)
- Capture (no-show): `PaymentIntent.create(off_session=True, confirm=True)`

## Security Architecture (March 2026)
### CORS
- Production: restreint au `FRONTEND_URL` uniquement
- Config via `CORS_ORIGINS` en `.env` (supporte liste CSV)
- Fallback: si vide, utilise `FRONTEND_URL`

### Rate Limiting (slowapi)
| Endpoint | Limite | Raison |
|----------|--------|--------|
| POST /auth/login | 10/min | Anti brute-force |
| POST /auth/register | 5/min | Anti spam comptes |
| POST /auth/forgot-password | 3/min | Anti abus email |
| POST /auth/reset-password | 5/min | Anti brute-force |
| POST /auth/resend-verification | 3/min | Anti spam email |
| GET /auth/verify-email | 10/min | Anti scraping |
| GET /invitations/{token} | 30/min | Anti scraping |
| POST /invitations/{token}/respond | 10/min | Anti spam |
| POST /invitations/{token}/reconfirm | 5/min | Anti abus Stripe |
| POST /invitations/{token}/cancel | 5/min | Anti abus |
| POST /checkin/manual | 20/min | Anti spam evidence |
| POST /checkin/qr/verify | 30/min | Anti brute-force QR |
| POST /checkin/gps | 20/min | Anti spam GPS |
| Default (all others) | 200/min | Protection globale |

### IP Resolution
- `X-Real-IP` > `X-Forwarded-For` > `request.client.host`
- Compatible reverse proxy / CDN / Kubernetes ingress

## Integrations Architecture
### Page Paramètres
| Carte | Route | Description |
|-------|-------|-------------|
| Profil | /settings/profile | Informations personnelles |
| Workspace | /settings/workspace | Configuration workspace |
| Intégrations | /settings/integrations | Calendriers + visioconférence |
| Paiement | /settings/payment | Carte par défaut pour garanties organisateur |

## Technical Stack
Frontend: React + TailwindCSS + Shadcn/UI | Backend: FastAPI + Python + MongoDB + slowapi
Email: Resend | Payments: Stripe | Video: Zoom API, Teams Graph API, Google Calendar API

## Key DB Schema
- `users`: stripe_customer_id, default_payment_method_id, default_payment_method_last4, default_payment_method_brand, default_payment_method_exp, payment_method_consent
- `appointments`: status (pending_organizer_guarantee | active | cancelled | completed), activated_at
- `participants`: is_organizer, status (accepted_pending_guarantee | accepted_guaranteed), guarantee_id
- `payment_guarantees`: source (default_payment_method | stripe_checkout)

## Testing
- iteration_30: 16/16 frontend + 8/9 backend (1 skipped: impossible by design)
- Manual revalidation: 7/7 critical scenarios
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
