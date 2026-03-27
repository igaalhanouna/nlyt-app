# NLYT — Product Requirements Document

## Problem Statement
SaaS d'engagement ponctuel avec garantie financière. Optimisation du "Viral Loop" et du funnel d'acquisition utilisateur. Focus sur la transparence financière, la neutralité du système de pénalités (Trustless V3), et l'UX contextuelle (navigation, scroll).

## Core Architecture
- React Frontend, FastAPI Backend, MongoDB
- Stripe (paiements), Resend (emails)
- Symmetric UI: mêmes écrans pour organisateur et participant, actions conditionnelles

## V3 Trustless Penalty System (Feb 2026)

### Outcomes
| Outcome | Condition | Capture | Bénéficiaire |
|---------|-----------|---------|-------------|
| `on_time` | delay <= 0, preuve admissible | Non | Oui |
| `late` | 0 < delay <= tolerated, preuve admissible | Non | Oui |
| `late_penalized` | delay > tolerated, preuve admissible | Oui | Non |
| `no_show` | Absent | Oui | Non |
| `manual_review` | Preuve insuffisante | Bloqué | Bloqué |
| `waived` | Décliné/annulé | Non | Non |

### Conflict of Interest
- Reclassification vers `no_show` ou `late_penalized` bloquée si l'organisateur en serait bénéficiaire

### Declarative Phase (Feb 2026)
- Feuille de présence collaborative pour cas `manual_review`
- 3 conditions cumulatives pour résolution automatique (MEDIUM confidence): unanimité, cohérence globale, absence de contradiction
- Échec → Dispute (LOW confidence) avec soumission de preuves complémentaires

## Navigation Structure
| Navbar Entry | Route | Page |
|-------------|-------|------|
| Tableau de bord | `/dashboard` | OrganizerDashboard |
| Présences | `/presences` | DisputeCenter |
| Litiges | `/litiges` | DisputesListPage |
| Contributions | `/mes-resultats` | FinancialResultsPage |
| Paramètres | `/settings` | Settings |

## Wallet System — Financial Safety (Mar 2026)

### Architecture
- `wallets` collection: available_balance, pending_balance (centimes)
- `wallet_transactions` collection: append-only ledger (credit_pending, credit_available, debit_payout, debit_refund)
- `distributions` collection: capture → beneficiaries, 15-day hold, contestation
- `payouts` collection: Stripe Transfer
- `reconciliation_reports` collection: drift detection

### P0 Fixes Applied (Mar 2026)
1. **Cas A Deadlock Fix**: `reset_cas_a_overrides()` clears `cas_a_override` and `review_required` flags before financial re-trigger after declarative/dispute resolution. Ensures captures previously blocked by Cas A can re-evaluate with new beneficiaries.
2. **Contestation Resolution**: Two exit paths for `contested` distributions:
   - `upheld` → cancel distribution, refund wallets, release guarantee
   - `rejected` → resume hold (new 15-day window)
   - Auto-reject timeout at 30 days (scheduler job every 12h)
3. **Ledger Reconciliation**: Scheduler job every 6h verifies `SUM(credit_pending) - SUM(debits) == available + pending`. No destructive corrections. Reports stored in `reconciliation_reports`.

### Contestation State Machine
```
pending_hold → contested → cancelled (upheld)
                         → pending_hold (rejected, new expiry)
                         → pending_hold (auto-rejected after 30d)
```

### Reconciliation Formula
```
expected = SUM(credit_pending) - SUM(debit_payout) - SUM(debit_refund)
actual = available_balance + pending_balance
drift = actual - expected (should be 0)
```
Note: `credit_available` is an internal move (pending→available), net-zero on total.

## Completed Features

### Phase 1 — Core
- Auth (JWT), appointments CRUD, invitations, Stripe guarantees
- GPS + QR + Video check-in, Evidence chain, NLYT Proof

### Phase 2 — Dashboard & UX
- Unified timeline, Action Required alerts, Temporal bucketing
- Contextual navigation, Scroll preservation

### Phase 3 — Financial Transparency
- Contributions page, Check-in temporal boundaries

### Phase 4 — V3 Trustless
- 3-way delay split, Cas A/B V3 strict, Conflict of interest
- 34 tests (100%)

### Phase 5 — Declarative Phase & Disputes
- Backend + Frontend: AttendanceSheetPage, DisputesListPage, DisputeDetailPage
- 59 tests (100%), E2E frontend tested (iteration_108, 109)

### Phase 5b — Frontend Conformity Audit (Mar 2026)
- Renamed "Décisions" → "Présences", added "Litiges" navbar entry
- Routes restructured, AppNavbar added to all pages

### Phase 6 — Wallet Financial Safety P0 (Mar 2026)
- Cas A deadlock fix (reset_cas_a_overrides)
- Contestation resolution (upheld/rejected/timeout)
- Ledger reconciliation job
- 16 new tests, 75/75 total (100%)

## Upcoming Tasks
- P0: Wallet UX (promote /wallet page, dashboard widget)
- P1: Email notification participant après résolution dispute
- P1: Buffer zone retard (2 min grâce)

## Backlog
- P2: Dashboard admin (arbitrage escaladés)
- P2: Charity Payouts V2 (Stripe Transfers)
- P2: Webhooks temps réel Zoom/Teams
- P2: Détection causalité organisateur
- P2: Pages dédiées charité & Leaderboard

## Test Credentials
- User 1: testuser_audit@nlyt.app / TestAudit123!
- User 2: igaal.hanouna@gmail.com / OrgTest123!
