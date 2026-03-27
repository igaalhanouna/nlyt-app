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

## Dispute Resolution Emails (Mar 2026)
- Trigger: appel non-bloquant dans `resolve_dispute()` apres toute resolution
- 3 variantes: participant cible, organisateur, beneficiaire impacte
- Source de decision: jamais "organisateur" expose (toujours "Resolution validee")
- Bloc financier: 4 cas (capture, liberation, aucun impact, dedommagement annule)
- CTA contextuel: wallet si impact financier, page RDV sinon
- Idempotence via collection `sent_emails` (email_type + dispute_id + user_id)
- Organizer = target → 1 seul email (variante target)

## Upcoming Tasks
- P1: Configurer webhook Stripe en production

## Backlog
- P2: Dashboard admin plateforme (arbitrage escalades)
- P2: Charity Payouts V2 (Stripe Transfers)
- P2: Webhooks temps reel Zoom/Teams
- P2: Detection causalite organisateur
- P2: Pages dediees charite & Leaderboard

## Test Credentials
- User 1: testuser_audit@nlyt.app / TestAudit123!
- User 2: igaal.hanouna@gmail.com / OrgTest123!
