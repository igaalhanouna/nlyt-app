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

## Navigation Structure
| Navbar Entry | Route | Page |
|-------------|-------|------|
| Tableau de bord | `/dashboard` | OrganizerDashboard |
| Présences | `/presences` | DisputeCenter |
| Litiges | `/litiges` | DisputesListPage |
| Contributions | `/mes-resultats` | FinancialResultsPage |
| Wallet | `/wallet` | WalletPage |
| Paramètres | `/settings` | Settings |

### Redirects
- `/settings/wallet` → `/wallet` (rétrocompat)

## Wallet System

### Financial Safety P0 (Mar 2026)
1. Cas A Deadlock Fix: `reset_cas_a_overrides()` avant re-trigger post-dispute/déclaratif
2. Contestation Resolution: upheld/rejected/timeout 30j
3. Ledger Reconciliation: toutes les 6h, formula `SUM(credit_pending) - SUM(debits)`
4. Conflit d'intérêt: organisateur bloqué si bénéficiaire ou flux charité

### Wallet UX (Mar 2026)
- Page `/wallet` promue en premier niveau (navbar desktop + mobile)
- 2 cartes principales: Disponible + En vérification
- Ligne secondaire: Total retiré
- Section "Prochains déblocages": distributions pending_hold avec dates
- Historique bidirectionnel: vert "Dédommagement reçu" / gris "Retrait" / orange "Remboursement"
- Widget dashboard intelligent (affiché si: balance > 0 OU connect needed OU contestation OU payout failed)
- Wording FR appliqué (jamais "hold", "capture", "distribution" face utilisateur)

### Wording FR
| Technique | Utilisateur |
|-----------|-------------|
| pending_balance | En vérification |
| available_balance | Disponible |
| distribution | Dédommagement |
| capture | Pénalité appliquée |
| payout | Retrait |
| debit_refund | Remboursement |
| Hold 15j | Période de vérification |
| contested | Contesté |

## Completed Features

### Phase 1-3 — Core, Dashboard, Financial Transparency
### Phase 4 — V3 Trustless (34 tests)
### Phase 5 — Declarative Phase & Disputes (25 tests)
### Phase 5b — Frontend Conformity (Présences + Litiges navbar)
### Phase 6 — Wallet Financial Safety P0 (21 tests)
### Phase 7 — Wallet UX (iteration_110, 100%)

## Upcoming Tasks
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
