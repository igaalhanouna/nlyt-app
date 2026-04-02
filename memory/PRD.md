# NLYT - Product Requirements Document

## Original Problem Statement
Application SaaS (React/FastAPI/MongoDB) de gestion des presences avec garanties financieres via le moteur "Trustless V5". Objectif : optimiser le moteur Trustless, l'UX globale, le systeme de notifications et fournir un hub d'administration complet.

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

## Security Layers - Wallet Payouts
1. **Idempotency key** - unique per request, stored in DB with TTL 24h
2. **Cooldown** - rejects if last payout < 10s ago
3. **Atomic $gte guard** - MongoDB prevents overdraft at DB level
4. **Rollback** - re-credits wallet if payout record creation fails
5. **Audit logging** - every step logged with request_id, user_id, amount, status

## Completed Features (Latest)

### Refonte Moteur Declaratif V5 + Migration Donnees (2026-04-02)
- **Faille 1 corrigee: Auto-litiges** — Guard dans `open_dispute`: si `target_user_id == organizer_user_id` -> pas de litige, auto-resolution en `waived` avec `decision_source=auto_no_self_dispute`
- **Faille 2 corrigee: Fausse interpretation des unknown** — `unknown` est desormais neutre, ne cree plus de litige
- **Nouvelle logique en 3 categories**:
  - `waived` : absence d'information -> garantie liberee, pas de penalite
  - `on_time` : presence confirmee (declarations unanimes positives) -> garantie liberee
  - Litige : signal negatif explicite (au moins 1 declaration "absent" ou preuve tech negative)
- **Petits groupes (<3)**: 0 exprime + pas neg tech -> waived | >=1 toutes positives -> on_time | tout absent -> litige
- **Grands groupes (>=3)**: 0 exprime -> waived | 1 positif -> waived | 1 negatif -> litige | >=2 unanimes positifs -> on_time | >=2 unanimes absent -> checks contradiction existants
- **Migration V5**: Script `fix_v4_legacy_disputes.py` execute — 48 litiges resolus (22 auto-litiges + 26 unknown-based), 23 RDV liberes, moteur financier relance pour liberation des garanties
- Tests: 27/27 PASS (18 unit + 9 API, iteration 175)
- Fichiers: `declarative_service.py` (8 edits), `fix_v4_legacy_disputes.py` (migration)

### Fix Duplication counterpart_name dans /arbitration (2026-04-02)
- Fix: counterpart_name = target_name

### Refonte Wording Detail Financier /decisions (2026-04-02)
- "Montant preleve a {Nom}", "Montant recu par {Nom} (organisateur)"
- Tests: 20/20 PASS (iteration 174)

### Harmonisation Wording Arbitration (2026-04-02)
- "{Name} maintient que {Target} {status}"
- Tests: 20/20 PASS (iteration 174)

### Refonte Wording "Ce qui a ete declare" (2026-04-02)
- "X declare Y status" partout
- Tests: 33/33 PASS (iteration 173)

### Transparence Preuves /decisions + Regroupement /arbitration (2026-04-02)
- tech_evidence_summary + regroupement par RDV
- Tests: 28/28 PASS (iteration 172)

## Data Integrity Rules
- Participant documents MUST have valid user_id when user exists
- Every appointment MUST have an is_organizer=True participant record
- Charity wallet debit ONLY on completed payout
- ObjectId exclusion from all MongoDB responses
- GUARANTEE RULE: No guarantee without Stripe verification
- BUSINESS STATUS RULE: Le statut participant metier ne doit JAMAIS etre ecrase par un statut financier
- **V5: Unknown = neutre, absence de preuve != preuve negative, auto-litige interdit**

## Upcoming Tasks (P1)
- Test reel Zoom/Teams avec vrais tokens
- Dashboard admin plateforme pour arbitrer les litiges escalades

## Future Tasks (P2)
- Charity Payouts V2 (Automatisation via Stripe Connect)
- Webhooks temps reel Zoom/Teams en production
- Notification email/push lors de la creation d'un litige
