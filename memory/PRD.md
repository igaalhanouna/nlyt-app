# NLYT — Product Requirements Document

## Problem Statement
SaaS d'engagement ponctuel avec garantie financière. Optimisation du "Viral Loop" et du funnel d'acquisition utilisateur. Focus sur la transparence financière, la neutralité du système de pénalités (Trustless V3), et l'UX contextuelle.

## Core Architecture
- React Frontend, FastAPI Backend, MongoDB
- Stripe (paiements), Resend (emails)
- Symmetric UI: mêmes écrans pour organisateur et participant, actions conditionnelles

## Trustless Principles
1. Preuve technologique (Niv.1-2) surclasse tout
2. Aucun acteur avec intérêt financier ne peut être décisionnaire
3. Phase déclarative pour cas manual_review (unanimité + cohérence + absence contradiction)
4. Conflit d'intérêt bloqué sur: reclassification, capture Cas A, résolution contestation

## Wallet System — Financial Safety (Mar 2026)

### P0 Fixes Applied
1. **Cas A Deadlock Fix**: `reset_cas_a_overrides()` avant re-trigger financier post-dispute/déclaratif
2. **Contestation Resolution**: upheld (cancel+refund+release) / rejected (resume hold 15j) / timeout 30j
3. **Ledger Reconciliation**: `SUM(credit_pending) - SUM(debits) == available + pending`, toutes les 6h
4. **Conflit d'intérêt sur résolution contestation**: Organisateur bloqué si bénéficiaire ou si flux charité

### Contestation Access Rules
| Condition | Organisateur peut résoudre ? | Raison |
|-----------|------------------------------|--------|
| Organisateur est bénéficiaire | NON (403) | Conflit d'intérêt direct |
| Distribution inclut flux charité | NON (403) | Réservé plateforme |
| Ni bénéficiaire ni charité | OUI | Pas de conflit |
| Timeout 30 jours | Auto-rejet (system) | Filet de sécurité |

### Reconciliation Formula
```
expected = SUM(credit_pending) - SUM(debit_payout) - SUM(debit_refund)
actual = available_balance + pending_balance
drift = actual - expected (should be 0)
```

## Completed Features

### Phase 1-3 — Core, Dashboard, Financial Transparency
- Auth, CRUD, invitations, Stripe guarantees, GPS/QR/Video check-in
- Unified timeline, Action Required alerts, Temporal bucketing
- Contributions page, Check-in temporal boundaries

### Phase 4 — V3 Trustless
- 3-way delay split, Cas A/B strict, Conflict of interest — 34 tests

### Phase 5 — Declarative Phase & Disputes
- AttendanceSheetPage, DisputesListPage, DisputeDetailPage — 25 tests
- Frontend conformity audit: "Présences" + "Litiges" navbar

### Phase 6 — Wallet Financial Safety P0 (Mar 2026)
- Cas A deadlock fix, Contestation resolution, Ledger reconciliation
- Conflict of interest guard on resolve-contestation
- 21 tests, 80/80 total (100%)

## Upcoming Tasks
- P0: Wallet UX (page /wallet promue, widget dashboard)
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
