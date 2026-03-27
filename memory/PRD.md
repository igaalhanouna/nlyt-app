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
| `on_time` | delay ≤ 0, preuve admissible | Non | Oui |
| `late` | 0 < delay ≤ tolerated, preuve admissible | Non | Oui |
| `late_penalized` | delay > tolerated, preuve admissible | Oui | Non |
| `no_show` | Absent | Oui | Non |
| `manual_review` | Preuve insuffisante | Bloqué | Bloqué |
| `waived` | Décliné/annulé | Non | Non |

### Key Rules
- Preuve admissible (Niveau 1-2) requise pour tout outcome définitif
- Preuve insuffisante → toujours `manual_review`
- Cas B: aucun outcome définitif dans le RDV → tout gelé
- Cas A (par-payeur): absence établie mais aucun bénéficiaire → capture bloquée
- `waived` ne compte pas comme outcome définitif
- `tolerated_delay_minutes = 0` → pas de zone `late`, directement `late_penalized`

### Conflict of Interest
- Reclassification vers `no_show` ou `late_penalized` bloquée si l'organisateur en serait bénéficiaire

## Completed Features

### Phase 1 — Core
- Auth (JWT), appointments CRUD, invitations, Stripe guarantees
- GPS + QR + Video check-in
- Evidence chain, proof sessions (NLYT Proof)

### Phase 2 — Dashboard & UX
- Unified timeline dashboard (organizer + participant)
- Action Required alerts (both roles)
- Temporal bucketing (end_time based)
- Contextual navigation (state passing via React Router)
- Scroll preservation (useScrollRestore hook + sessionStorage)

### Phase 3 — Financial Transparency
- "Contributions" page (/mes-resultats) with global synthesis
- Wording: "dédommagé de", "indemnisé le ou les participants", "geste solidaire"
- Check-in temporal boundaries [start-30m, end+1h]

### Phase 4 — V3 Trustless (Current)
- 3-way delay split: on_time / late / late_penalized
- evaluate_participant restructured (physical + video)
- _process_financial_outcomes: Cas A/B V3 strict
- _process_reclassification: PENALIZED = (no_show, late_penalized)
- Conflict of interest extended to late_penalized
- Frontend labels updated (6 outcome categories)
- 34 tests passing (100%)

## Upcoming Tasks
- P0: Wallet System
- P1: Email notification participant après résolution dispute
- P1: Buffer zone retard (2 min grâce)

## Backlog
- P2: Dashboard admin (arbitrage escaladés)
- P2: Charity Payouts V2 (Stripe Transfers)
- P2: Webhooks temps réel Zoom/Teams
- P2: Détection causalité organisateur
- P2: Pages dédiées charité & Leaderboard

## Test Credentials
- User 1: testuser_audit@nlyt.app
- User 2: igaal.hanouna@gmail.com
