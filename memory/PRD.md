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

### Declarative Phase (Feb 2026)
- Feuille de présence collaborative pour cas `manual_review`
- 3 conditions cumulatives pour résolution automatique (MEDIUM confidence): unanimité, cohérence globale, absence de contradiction
- Échec → Dispute (LOW confidence) avec soumission de preuves complémentaires
- Deadline: 48h pour déclarations, 7 jours pour preuves complémentaires

## Navigation Structure
| Navbar Entry | Route | Page | Description |
|-------------|-------|------|-------------|
| Tableau de bord | `/dashboard` | OrganizerDashboard | Timeline engagements |
| Présences | `/presences` | DisputeCenter | Cas `manual_review` à vérifier |
| Litiges | `/litiges` | DisputesListPage | Litiges déclaratifs ouverts/résolus |
| Contributions | `/mes-resultats` | FinancialResultsPage | Synthèse financière |
| Paramètres | `/settings` | Settings | Configuration compte |

### Sub-routes
- `/litiges/:id` → DisputeDetailPage (détail litige + soumission preuves)
- `/appointments/:id/attendance-sheet` → AttendanceSheetPage (feuille de présence collaborative)

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

### Phase 4 — V3 Trustless
- 3-way delay split: on_time / late / late_penalized
- evaluate_participant restructured (physical + video)
- _process_financial_outcomes: Cas A/B V3 strict
- Conflict of interest extended to late_penalized
- 34 tests passing (100%)

### Phase 5 — Declarative Phase & Disputes
- Backend: declarative_service.py, declarative_routes.py, dispute_routes.py
- Frontend: AttendanceSheetPage, DisputesListPage, DisputeDetailPage
- AppointmentDetail CTA banners (collecting/disputed phases)
- 59/59 backend tests passing, E2E frontend tested (iteration_108)

### Phase 5b — Frontend Conformity Audit (Mar 2026)
- Renamed "Décisions" → "Présences" (navbar, breadcrumbs, page title, banner)
- Added "Litiges" navbar entry → /litiges
- Routes restructured: /presences (DisputeCenter), /litiges (DisputesListPage)
- Added AppNavbar to all new pages (DisputesListPage, DisputeDetailPage, AttendanceSheetPage)
- PendingReviewBanner updated: links to /presences, wording "présences à vérifier"
- Removed dead file DisputeDetail.js
- E2E frontend tested (iteration_109, 100%)

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
- User 1: testuser_audit@nlyt.app / TestAudit123!
- User 2: igaal.hanouna@gmail.com / OrgTest123!
