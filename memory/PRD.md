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

## Guarantee-First Architecture (NEW - March 2026)
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

## Integrations Architecture
### Page Paramètres
| Carte | Route | Description |
|-------|-------|-------------|
| Profil | /settings/profile | Informations personnelles |
| Workspace | /settings/workspace | Configuration workspace |
| Intégrations | /settings/integrations | Calendriers + visioconférence |
| Paiement | /settings/payment | Carte par défaut pour garanties organisateur |

### Provider Connection Model
| Provider | Modèle | Stockage |
|----------|--------|----------|
| Google Calendar + Meet | OAuth per-user | `calendar_connections` |
| Outlook | OAuth per-user | `calendar_connections` |
| Zoom | User config + Platform env | `user_settings` + env vars |
| Teams | User config + Platform env | `user_settings` + env vars |

## Technical Stack
Frontend: React + TailwindCSS + Shadcn/UI | Backend: FastAPI + Python + MongoDB
Email: Resend | Payments: Stripe | Video: Zoom API, Teams Graph API, Google Calendar API

## Key DB Schema
- `users`: stripe_customer_id, default_payment_method_id, default_payment_method_last4, default_payment_method_brand, default_payment_method_exp, payment_method_consent
- `appointments`: status (pending_organizer_guarantee | active | cancelled | completed), activated_at
- `participants`: is_organizer, status (accepted_pending_guarantee | accepted_guaranteed), guarantee_id
- `payment_guarantees`: source (default_payment_method | stripe_checkout)

## Testing
- iteration_24: 17/17 (Video evidence MVP)
- iteration_25: 13/13 (Meeting API integration)
- iteration_26: 15/15 + full UI (Integrations page)
- iteration_30: 16/16 frontend + 8/9 backend (Guarantee-First feature)
- Credentials: testuser_audit@nlyt.app / Test1234!

## Backlog (Prioritized)
### P0
- Rate limiting and CORS restriction (security pre-launch)

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
