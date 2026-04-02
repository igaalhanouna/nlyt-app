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

## Completed Features (Latest Session - 2026-04-02/03)

### Notifications Feuilles de Presence — Equite declarative (2026-04-04)
- Email automatique a l'ouverture de la phase collecting pour TOUS les participants (avec et sans compte)
- Fix critique : les participants sans compte ne sont plus exclus de la phase declarative (sheets creees avec email placeholder)
- Relance automatique 12h avant deadline via scheduler (job toutes les 30 min)
- Auto-linkage etendu : attendance_sheets liees au user_id au login (en plus des participants et disputes)
- Fallback submit_sheet : lookup par participant_id si user_id non encore lie
- Templates email : contexte RDV, action attendue, deadline exacte, consequence du silence, CTA contextuel
- Idempotence complete sur les 2 emails (sheet_pending + sheet_reminder)
- Tests : 19/19 OK + 0 regression (43/43 total)
- Fichiers modifies : declarative_service.py, notification_service.py, email_service.py, auth_service.py, scheduler.py

### Phase 1 Pre-Production — Equite & UX (2026-04-04)
- Notifications escalade/decision pour participants sans compte : email avec CTA "creer mon compte" (3 etapes couvertes)
- Parcours register → redirect litige : route /register alias, propagation redirect param SignUp↔SignIn↔OAuth, auto-linkage participant/dispute au login
- Granularite scheduler : declarative deadline 5min (was 15), dispute escalation 15min (was 6h)
- Auto-linkage orphan participants/disputes : fonction _auto_link_user_to_participants au login email+OAuth
- Tests : 24/24 backend (notifications 12/12, audit 12/12) + 5/5 frontend
- Fichiers modifies : notification_service.py, email_service.py, auth_service.py, oauth_routes.py, scheduler.py, App.js, SignIn.js, SignUp.js, OAuthButtons.js, AuthCallback.js

### Notification Email Litige — Equite d'information (2026-04-04)
- Email automatique envoye des l'ouverture d'un litige a TOUTES les parties
- 3 cas couverts :
  - Cible avec compte NLYT : notification in-app + email avec lien direct /litiges/{id}
  - Cible sans compte NLYT : email avec CTA "Creer mon compte et repondre" (lien /register?redirect=/litiges/{id})
  - Cas degrade (aucun email) : log d'alerte equite, pas de crash
- Contenu enrichi : montant de la garantie en jeu, delai de 7 jours, CTA contextuel
- Idempotence : tracking via create_notification + mark_email_sent (meme pour les non-comptes)
- Organisateur aussi notifie avec variante specifique ("en tant qu'organisateur")
- Tests : 9/9 OK (qa_dispute_notification.py) + 0 regression sur audit (12/12)
- Fichiers modifies : notification_service.py, email_service.py

### Audit Produit Global + QA Angles Morts (2026-04-04)
- Audit exhaustif du code source : cartographie complete des flux, transitions, interactions inter-modules
- 11 angles morts testes, 5 failles identifiees et corrigees :
  - BS-1 (CRITIQUE) : Review timeout auto-waivait les participants en litige actif → guard ajoute
  - BS-2 (MAJEUR) : Reconciliation ignorait credit_available_direct → formule corrigee
  - BS-3 (MAJEUR) : Phase analyzing bloquee sans recovery → detection + retry auto (30 min)
  - BS-4 (MOYEN) : Reclassification apres immediate_release silencieusement ignoree → cancel_distribution accepte completed
  - BS-6 (PRODUIT) : Observateurs voyaient les litiges non concernes → filtrage par role dans /disputes/mine
- 7 tests confirmes robustes : CAS idempotence, guard auto-litige, capture released, Cas A, dispute sans deadline
- Score final QA : 12/12 OK post-corrections
- Rapport complet : /app/backend/AUDIT_RAPPORT_V51.md
- Tests : /app/backend/tests/qa_blind_spots.py

### V5.1: Phase Declarative Reservee aux Garantis (2026-04-03)
- Seuls les participants `accepted_guaranteed` en `manual_review` entrent dans la phase declarative
- Participants non-garantis auto-resolus en `waived` (decision_source: `non_guaranteed_auto_waived`)
- Si < 2 participants garantis restants, `declarative_phase = not_needed`, aucune feuille creee
- Participants auto-waived exclus des createurs de feuilles
- Garanties: pas de pending sheet, pas de litige, pas d'arbitrage admin, pas de penalite
- Fix: participants garantis restants (< 2) aussi waived (decision_source: `insufficient_guaranteed_participants`) pour eviter badges financiers fantomes
- Tests: 24/24 unit PASS + 32/32 QA PASS + recette UI 5 scenarios PASS (iterations 177-179)

### UX Timeline Cards — Visibilite des participants inactifs (2026-04-03)
- Banniere explicite: "Tous les participants ont decline" / "ont annule" / "ont annule ou decline"
- Progress bar corrigee: exclut l'organisateur des compteurs (participants_count, accepted_count = non-org seulement)
- Progress bar masquee si 0 participants actifs (no_active_participants=true)
- Badge discret "Sans participant" (gris, icone UserX) combine avec badge temporel
- Statut `declined` desormais visible (etait invisible auparavant)
- Counterparty corrige: ne montre plus l'organisateur lui-meme, affiche "Aucun participant" si aucun actif
- Tests: 100% PASS (iteration 178) — API + frontend + 0 regression sur 30 cartes

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
- V5.1: seuls les `accepted_guaranteed` entrent en phase declarative, les autres sont `waived` immediatement
- Notifications: auto-cleanup des dispute_update pour litiges resolus/inexistants

## Upcoming Tasks (P1)
- Test reel Zoom/Teams avec vrais tokens
- Dashboard admin plateforme pour arbitrer les litiges escalades
- Distributed lock pour scheduler multi-pod (identifie dans l'audit)

## Future Tasks (P2)
- Charity Payouts V2 (Automatisation via Stripe Connect)
- Webhooks temps reel Zoom/Teams en production
- Notifications email pour escalade et decision rendue (templates deja implementes)
