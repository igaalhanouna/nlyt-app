# NLYT — Product Requirements Document

## Problem Statement
SaaS d'engagement ponctuel avec garantie financiere. Optimisation du "Viral Loop" et du funnel d'acquisition utilisateur. Focus sur la transparence financiere, la neutralite du systeme de penalites (Trustless V3), et l'UX contextuelle.

## Core Architecture
- React Frontend, FastAPI Backend, MongoDB
- Stripe (paiements), Resend (emails)
- Symmetric UI: memes ecrans pour organisateur et participant, actions conditionnelles

## Trustless Principles
1. Preuve technologique (Niv.1-2) surclasse tout
2. Aucun acteur avec interet financier ne peut etre decisionnaire
3. Phase declarative pour cas manual_review (unanimite + coherence + absence contradiction)
4. Conflit d'interet bloque sur: reclassification, capture Cas A, resolution contestation

## Navigation Structure
| Navbar Entry | Route | Page |
|-------------|-------|------|
| Tableau de bord | `/dashboard` | OrganizerDashboard |
| Presences | `/presences` | DisputeCenter |
| Litiges | `/litiges` | DisputesListPage |
| Contributions | `/mes-resultats` | FinancialResultsPage |
| Wallet | `/wallet` | WalletPage |
| Parametres | `/settings` | Settings |

### Redirects
- `/settings/wallet` -> `/wallet` (retrocompat)

## Wallet System

### Financial Safety P0 (Mar 2026)
1. Cas A Deadlock Fix: `reset_cas_a_overrides()` avant re-trigger post-dispute/declaratif
2. Contestation Resolution: upheld/rejected/timeout 30j
3. Ledger Reconciliation: toutes les 6h, formula `SUM(credit_pending) - SUM(debits)`
4. Conflit d'interet: organisateur bloque si beneficiaire ou flux charite

### Wallet UX (Mar 2026)
- Page `/wallet` promue en premier niveau (navbar desktop + mobile)
- 2 cartes principales: Disponible + En verification
- Ligne secondaire: Total retire
- Section "Prochains deblocages": distributions pending_hold avec dates
- Historique bidirectionnel: vert "Dedommagement recu" / gris "Retrait" / orange "Remboursement"
- Widget dashboard intelligent (affiche si: balance > 0 OU connect needed OU contestation OU payout failed)
- Wording FR applique (jamais "hold", "capture", "distribution" face utilisateur)

### Wording FR
| Technique | Utilisateur |
|-----------|-------------|
| pending_balance | En verification |
| available_balance | Disponible |
| distribution | Dedommagement |
| capture | Penalite appliquee |
| payout | Retrait |
| debit_refund | Remboursement |
| Hold 15j | Periode de verification |
| contested | Conteste |

## Buffer Zone (2 minutes)
- Constante interne `BUFFER_ZONE_MINUTES = 2` dans `attendance_service.py`
- Formule: `effective_delay = max(0, delay_minutes - 2)`
- Appliquee APRES confirmation de preuve admissible, AVANT le 3-way split
- Invisible en frontend — tolerance technique silencieuse
- Ne s'applique PAS aux cas no_show ou manual_review (exit avant le split)
- 10 tests unitaires couvrent toutes les limites (test_buffer_zone.py, 100%)

## Completed Features

### Phase 1-3 — Core, Dashboard, Financial Transparency
### Phase 4 — V3 Trustless (34 tests)
### Phase 5 — Declarative Phase & Disputes (25 tests)
### Phase 5b — Frontend Conformity (Presences + Litiges navbar)
### Phase 6 — Wallet Financial Safety P0 (21 tests)
### Phase 7 — Wallet UX (iteration_110, 100%)
### Phase 8 — Buffer Zone 2 min (10 tests, 100%) - DONE
### Phase 9 — Dispute Resolution Emails (10 tests, 100%) - DONE
### Phase 10 — Modification Emails & Video Param Fix (10 tests, 100%) - DONE
### Phase 11 — Check-in Time Window Alignment P0 (15 tests, 100%) - DONE
### Phase 12 — Agenda Calendar View V1 (14 tests frontend, 100%) - DONE
### Phase 12b — Agenda Semaine + Jour Views (iteration_112, 20/20 tests, 100%) - DONE
### Phase 12c — Toggle Harmonisation Dashboard/Agenda (iteration_113, 100%) - DONE
### Phase 13 — Auto-creation meeting on type switch (11/11 unit tests) - DONE
### Phase 14 — Presences page realignment: declarative only (iteration_114, 100%) - DONE
### Phase 15 — Dispute Decision Logic Phase 2 (iteration_115, 100%) - SUPERSEDED BY V4
### Phase 16 — V4 Trustless Symmetric Disputes (iteration_116, 100%) - DONE

## V4.2 Strong Proof Lockdown & Small Group Declarative (Mar 2026)
- RULE: Strong technological proof NEVER creates manual_review, attendance_sheet, or dispute
- Strong proof = GPS valid, QR code, NLYT Proof >= 55, Video API (Zoom/Teams)
- Weak/no proof = manual_checkin only, NLYT < 30, no evidence -> manual_review -> Presences
- Small groups (< 3 participants): no longer bypass Presences. Sheets always created.
- Self-declaration: targeted participants declare on themselves (is_self_declaration=true)
- Small group analysis: direct comparison, agreement -> resolve, disagreement -> dispute
- Old _escalate_all_manual_reviews() REMOVED (dead code)
- Wording: "Votre declaration sur les presences" / "Votre position sur le litige"
- Lock-down tests: /app/backend/tests/test_strong_proof_lockdown.py (9 tests, 100%)
- Flow tests: /app/backend/tests/test_presences_flow.py (5 tests)

### Phase 17 — Schema Alignment & Data Cleanup (Feb 2026) - DONE
- Bug fix: `_has_admissible_proof()` fixed to check `source` field and `derived_facts` nested dict
- DB schema reality: `source` = "gps"|"qr"|"video_conference"|"manual_checkin", `gps_within_radius` inside `derived_facts`
- Video conference validation: Zoom/Teams require `provider_evidence_ceiling=strong` AND `video_attendance_outcome` in (joined_on_time, joined_late)
- Tests expanded: 6 -> 9 tests
- Data cleanup script: `/app/backend/scripts/clean_ghost_disputes.py`

### Phase 17b — Limbo Appointments Recovery (Feb 2026) - DONE
- 4 appointments stuck in limbo state after Phase 17 cleanup (stale `declarative_phase: 'disputed'`, no sheets/disputes)
- Root cause: cleanup script reset `attendance_evaluated` but not `declarative_phase`, `attendance_summary`, or orphaned sheets/disputes
- Fix: full state reset + re-evaluation with corrected logic for all 4 affected appointments
- Script `clean_ghost_disputes.py` updated: Phase 1 now does full state reset + sheet/dispute cleanup + auto re-evaluation; Phase 2 resets `declarative_phase` when all disputes purged

### Phase 18 — UX Cleanup: Single Entry Point for Declarations (Feb 2026) - DONE
- Product rule: attendance declarations ONLY via `/presences` page
- Deleted: `PendingReviewSection.js` (unilateral reclassification from appointment detail)
- Deleted: `DisputeCenter.js` (dead code — imported but never mounted on a route)
- `AttendancePanel.js`: rewritten as read-only (status badges only, no action buttons)
- Declarative CTA banner: now navigates to `/presences` (was `/appointments/:id/attendance-sheet`)
- Check-in wording: "Confirmer ma présence" → "Effectuer mon check-in" / "Check-in avec GPS"
- Confirmed state: "Présence confirmée" → "Check-in effectué"
- Pending state: "Présence non confirmée" → "Check-in non effectué"
- Removed handlers: `handleEvaluateAttendance`, `handleReevaluateAttendance`, `handleReclassify`
- Removed states: `evaluating`, `reclassifying`, `reclassifyDropdown`
- Tests: 10/10 frontend tests passed (iteration_117)

## Upcoming Tasks
- P1: Dashboard admin plateforme (arbitrage final des litiges escalades "maintained")
- P1: Configurer webhook Stripe en production
- P1: Test reel Zoom/Teams avec vrais tokens

## Backlog
- P2: Charity Payouts V2 (Stripe Transfers)
- P2: Webhooks temps reel Zoom/Teams
- P2: Detection causalite organisateur
- P2: Pages dediees charite & Leaderboard
- P2: Delete API externe lors d'un switch visio -> physique (V2)
- P2: Notification push/email a l'accusateur lors de la creation d'un litige

## Test Credentials
- User 1: testuser_audit@nlyt.app / TestAudit123!
- User 2: igaal.hanouna@gmail.com / OrgTest123!
- User 3: igaal@hotmail.com / Test123!
