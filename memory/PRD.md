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

### Fix waived dans /decisions (P1 Critique)
- waived affiche "Classe sans suite" style gris neutre
- Impact financier: "Aucune penalite" (et non "Debite de X")
- OUTCOME_CFG, STATUS_LABELS, OUTCOME_PHRASES, OPENED_REASON_LABELS enrichis
- Backend: financial_impact.type='neutral' pour waived
- Tests: 30/30 PASS (iteration 176)

### Simplification Categories Admin (P2)
- 3 KPI: "A arbitrer" / "En attente des parties" / "Clos"
- Fusion "Resolus" + "Accords mutuels" en "Clos" avec sous-indicateur
- Tests: 30/30 PASS (iteration 176)

### Fix Badge Litiges (compteur bloque)
- Root cause: notifications dispute_update pour litiges resolus restaient is_read=false
- Fix: auto-nettoyage self-healing dans get_unread_counts() via _cleanup_resolved_dispute_notifications()
- Logique: avant chaque comptage, verifie si les litiges references sont resolus ou inexistants → mark as read
- Resultat: badge passe de 5 a 0 immediatement, se met a jour pour chaque user a la prochaine connexion
- Fichier modifie: notification_service.py

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

### Outcomes dans /decisions
| Outcome | Label | Style | Impact financier |
|---|---|---|---|
| on_time | Presence validee | vert | Aucune penalite |
| no_show | Absence confirmee | rouge | Penalite |
| late_penalized | Retard confirme | ambre | Penalite |
| waived | Classe sans suite | gris | Aucune penalite |

## Data Integrity Rules
- V5: unknown = neutre, absence de preuve != preuve negative, auto-litige interdit
- Notifications: auto-cleanup des dispute_update pour litiges resolus/inexistants

## Upcoming Tasks (P1)
- Test reel Zoom/Teams avec vrais tokens
- Dashboard admin plateforme pour arbitrer les litiges escalades

## Future Tasks (P2)
- Charity Payouts V2 (Automatisation via Stripe Connect)
- Webhooks temps reel Zoom/Teams en production
- Notification email/push lors de la creation d'un litige
