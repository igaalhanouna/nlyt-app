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

## Completed Features (Latest Session - 2026-04-02)

### Refonte Moteur Declaratif V5 + Migration
- Auto-litiges elimines (guard target_user_id != organizer_user_id)
- unknown = neutre (ne cree plus de litige)
- 3 categories: waived / on_time / litige
- Migration: 48 litiges resolus, 23 RDV liberes
- Tests: 27/27 PASS (iteration 175)

### Fix Critique: waived dans /decisions (P1)
- `waived` ajoute dans OUTCOME_CFG frontend: "Classe sans suite" style gris neutre
- DecisionDetailPage: label "Classe sans suite pour {name}", sous-titre "Aucune penalite — information insuffisante"
- FinancialSection: waived = "Aucun prelevement. La garantie a ete liberee."
- Backend: financial_impact.type='neutral' pour waived (dispute_routes.py)
- Backend: financial_summary='Aucune penalite' pour waived (admin_arbitration_service.py)
- OPENED_REASON_LABELS enrichi avec les raisons V5
- Tests: 30/30 PASS (iteration 176)

### Simplification Categories Admin (P2)
- Fusion "Resolus" + "Accords mutuels" en "Clos" (1 seul filtre)
- Renommage "Positions en cours" en "En attente des parties"
- 3 KPI au lieu de 4: "A arbitrer" / "En attente des parties" / "Clos"
- Sous-indicateur: "Clos — Accord mutuel" vs "Clos — Arbitrage"
- Backend: FILTER_QUERIES closed + get_arbitration_stats total_closed
- Tests: 30/30 PASS (iteration 176)

## Categorisation Produit (Modele Cible Valide)

### Cote Utilisateur — 3 familles exclusives
| Famille | Condition | Contenu |
|---|---|---|
| Presences | declarative_phase IN (initialized, collecting) | Feuilles a remplir |
| Litiges | dispute status IN (awaiting_positions, escalated) | Litiges non clos |
| Decisions | dispute status IN (resolved, agreed_*) | Litiges clos |

### Cote Admin — 3 categories
| Categorie | Statuts | Action admin |
|---|---|---|
| A arbitrer | escalated | Trancher |
| En attente des parties | awaiting_positions | Informatif |
| Clos | resolved + agreed_* | Historique |

### Outcomes supportes dans /decisions
| Outcome | Label | Style | Impact financier |
|---|---|---|---|
| on_time | Presence validee | vert | Aucune penalite |
| no_show | Absence confirmee | rouge | Penalite |
| late_penalized | Retard confirme | ambre | Penalite |
| waived | Classe sans suite | gris | Aucune penalite |

## Data Integrity Rules
- Participant documents MUST have valid user_id when user exists
- ObjectId exclusion from all MongoDB responses
- V5: unknown = neutre, absence de preuve != preuve negative, auto-litige interdit

## Upcoming Tasks (P1)
- Test reel Zoom/Teams avec vrais tokens
- Dashboard admin plateforme pour arbitrer les litiges escalades

## Future Tasks (P2)
- Charity Payouts V2 (Automatisation via Stripe Connect)
- Webhooks temps reel Zoom/Teams en production
- Notification email/push lors de la creation d'un litige
