# NLYT - Product Requirements Document

## Original Problem Statement
Application SaaS (React/FastAPI/MongoDB) de gestion des presences avec garanties financieres via le moteur "Trustless V4". Objectif : optimiser le moteur Trustless, l'UX globale, le systeme de notifications et fournir un hub d'administration complet.

## Core Architecture
- **Frontend**: React + Shadcn/UI
- **Backend**: FastAPI + MongoDB
- **Payments**: Stripe (test mode, sk_test_*)
- **Email**: Resend
- **Video**: Zoom, Microsoft Teams (OAuth)
- **Auth**: Email/password + Google OAuth + Microsoft OAuth (common tenant)

## QA Campaign Results (2026-03-29)

### Overall: 54/56 tests passed, 2 bugs found and fixed

| Bloc | Tests | Result |
|------|-------|--------|
| A - Auth/Onboarding | 4/4 | PASS |
| B - Permissions/Roles | 2/2 | PASS |
| C - Creation/Modification RDV | 9/9 | PASS (C2 titre vide fixed) |
| D - Invitations | 2/2 | PASS |
| E - Presences | 4/4 | PASS |
| F - Litiges | 2/2 | PASS |
| G - Arbitrage Admin | 2/2 | PASS |
| H - Wallet | 6/6 | PASS (H6 double payout fixed) |
| I - Charity Payouts | 15/15 | PASS |
| J - Calendrier | 5/5 | PASS |
| K - Notifications | 3/3 | PASS |

### Bugs Fixed During QA
1. H6 CRITICAL: Double payout race condition → Fixed with cooldown 10s + idempotency key + atomic $gte guard
2. C2 MINOR: Blank title accepted → Fixed with min_length=1 + strip() validation

## Security Layers - Wallet Payouts
1. **Idempotency key** — unique per request, stored in DB with TTL 24h, prevents duplicate processing
2. **Cooldown** — rejects if last payout < 10s ago (anti double-click)
3. **Atomic $gte guard** — MongoDB prevents overdraft at DB level
4. **Rollback** — re-credits wallet if payout record creation fails
5. **Audit logging** — every step logged with request_id, user_id, amount, status

## Completed Features (Latest)

### Charity Payouts V1 (2026-03-29)
- Manual bank transfers to charity associations
- Admin records completed transfer → wallet debited atomically
- IBAN validation, masked display, snapshot with each payout
- Dashboard with KPIs, history per association

### Wallet Security Reinforcement (2026-03-29)
- Idempotency key system (frontend generation + backend enforcement)
- Cooldown protection (10s between payouts)
- Atomic debit with rollback on failure
- Structured audit logging with request_id

### Stripe Connect Refresh (2026-03-29)
- POST /api/connect/refresh-status syncs account status from Stripe API
- Bypasses webhook dependency for status updates

### User Payout Flexible Amount (2026-03-29)
- Amount input field pre-filled with total, editable
- Validation: amount > 0 and <= available_balance

### Dashboard Search (2026-03-29)
- Search bar in Engagements section (right of tabs)
- Filters on title, location, counterparty name, status
- Works on both "A venir" and "Historique" tabs

### Association Dedup (2026-03-29)
- Merged "Restos du Coeur" and "Les Restos du Coeur" into single entry
- 1 appointment migrated, wallet preserved

## Data Integrity Rules
- Participant documents MUST have valid user_id when user exists
- Every appointment MUST have an is_organizer=True participant record
- Charity wallet debit ONLY on completed payout (never on view/prepare)
- Payout idempotency keys auto-expire after 24h (TTL index)
- ObjectId exclusion from all MongoDB responses

## Upcoming Tasks (P1)
- Configurer le webhook Stripe en production (coherence wallet/payout/Stripe states)
- Test reel Zoom/Teams avec vrais tokens

## Future Tasks (P2)
- Charity Payouts V2 (Automatisation via Stripe Connect)
- Webhooks temps reel Zoom/Teams
