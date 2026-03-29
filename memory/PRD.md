# NLYT - Product Requirements Document

## Original Problem Statement
Application SaaS (React/FastAPI/MongoDB) de gestion des presences avec garanties financieres via le moteur "Trustless V4". L'objectif est d'optimiser le moteur Trustless V4 et l'UX globale.

## Core Architecture
- **Frontend**: React + Shadcn/UI
- **Backend**: FastAPI + MongoDB
- **Payments**: Stripe
- **Email**: Resend
- **Video**: Zoom, Microsoft Teams, Google Meet (OAuth)

## Completed Features

### Session 1-4 (Previous)
- Full Trustless V4 engine, Appointment CRUD, Invitation flow, Calendar integration
- Video evidence system, Attendance evaluation engine, Dispute system
- Financial distribution engine, Wallet system, Policy snapshot

### Session 5-8 (Previous)
- Cancel Guards (UX + backend restrictions)
- Disputes UX Refactor (grouped by appointment)
- Presences UX Refactor (read-only mode)
- Orphan Participants Fix (user_id linking + migration)

### Session 9 - Modification Flow Fix (2026-03-29)
- Direct modification when 0 accepted non-org participants
- Proposal mode when >=1 accepted non-org participant
- UX adaptive modal (title/button/description per mode)
- Notification emails in direct mode to all participants

### Session 10 - Organizer Participant Migration (2026-03-29)
- 209 org-participant records inserted + 2 flags corrected (344/345 covered)
- Fixed seed_demo.py to inject org-participant
- Idempotent script with migrated_at tag

### Session 11 - Modification Visibility & Bidirectional System (2026-03-29)
**P0.1 - API GET /api/modifications/mine**
- Returns all proposals involving current user (as organizer or participant)
- Fields: proposal_id, appointment_id, appointment_title, start_datetime, proposed_by, changes, original_values, status, mode, expires_at, created_at, my_role, my_response_status, is_action_required, participants_summary
- is_action_required = true when my_response_status=pending AND proposal status=pending

**P0.4 - Bidirectional response on detail page**
- ModificationProposals component accepts viewerParticipantId + isOrganizer
- Shows Accept/Reject for ANY user with pending response (not just organizer)
- Shows Cancel for the proposer (organizer or participant)

**P0.2 - Dashboard modifications section**
- "Modifications en attente" section with amber background
- Only shows proposals where is_action_required=true
- Links to appointment detail page

**P0.3 - Timeline card badges**
- Amber "Action requise" badge when user must respond
- Blue "Modification en cours" badge when pending but no action needed from user

**P1.2 - JWT-based participant resolution**
- POST /api/modifications/ accepts participant via JWT (resolves user_id to participant record)
- POST /api/modifications/{id}/respond accepts both organizer and participant via JWT
- POST /api/modifications/{id}/cancel accepts both roles via JWT
- Participants must have accepted status to propose

**P1.1 - Participant propose from detail page**
- "Modifier" button visible to accepted participants (not just organizer)
- Edit modal opens same proposal form
- Backend resolves participant via JWT automatically

### Session 12 - Fix Modification Summary Display (2026-03-30)
- Fixed formatChangeSummary() displaying only time changes, ignoring DATE/LIEU/VISIO
- Now shows: Date (old -> new), Horaire (old -> new), Lieu (old -> new), Visio (old -> new), Duree
- Validated via testing_agent iteration 135 (100% pass rate)

### Session 13 - P2.1 Timeline History + P2.2 Vote Progress (2026-03-30)
- P2.2: VoteProgressBar component with X/Y counter + colored progress bar
- P2.1: Full chronological timeline replacing minimal history list
- Validated via testing_agent iteration 136 (100% pass rate: 9/9 backend, 12/12 frontend)

### Session 14 - P1: Dashboard Admin Arbitrage des litiges (2026-03-30)
- Backend: admin_arbitration_service.py (tech dossier builder, analyse systeme, enriched list/detail)
- Backend: admin.py rewrite (GET /arbitration, /stats, /:id, POST /:id/resolve) with require_admin guard
- Backend: role field added to JWT payload + user response on login
- Backend: promote_admin.py script (testuser_audit@nlyt.app -> admin)
- Frontend: AdminArbitrationList.js (stats KPIs, dispute cards with proof badge, positions, age indicator)
- Frontend: AdminArbitrationDetail.js (5 blocs: verdict tech, analyse systeme, positions, declarations, arbitrage)
- Frontend: Navbar updated (admin-only "Arbitrage" link desktop + mobile)
- Validated via testing_agent iteration 137 (100%: 14/14 backend, 14/14 frontend)

### Session 15 - Consequences financieres + KPI cliquables (2026-03-30)
- Backend: financial_context added to dispute detail
- Backend: financial_summary added to list cards for resolved disputes
- Backend: GET /api/admin/arbitration?filter=escalated|awaiting|resolved|agreed (new param)
- Frontend detail: Dynamic FinancialPreview component
- Frontend list: financial_summary badge + KPI clickable filters
- All lint clean, visually verified

### Session 16 - Onglet Decisions utilisateur (2026-03-31)
- Backend: GET /api/disputes/decisions/mine (resolved disputes enriched with financial_impact per user role)
- Frontend: Page standalone DecisionsListPage.js accessible via /decisions
- Frontend: DecisionDetailPage.js (5 sections: contexte RDV, decision finale, detail financier, declarations, statut)
- Frontend: Route /decisions et /decisions/:disputeId dans App.js
- Validated via testing_agent iteration 139 (100%: 12/12 backend, 17/17 frontend)

### Session 17 - Reorganisation navbar (2026-03-31)
- Retrait de "Wallet" du menu principal (desktop + mobile), accessible uniquement via Parametres
- Ajout de "Decisions" comme page standalone dans la navbar (juste apres Litiges)
- Nouvel ordre: Agenda, Tableau de bord, Presences, Litiges, Decisions, Arbitrage (admin), Contributions, Parametres
- Suppression des icones Scale sur Arbitrage et Decisions (texte pur)
- Retrait de l'onglet Decisions du OrganizerDashboard (reste: A venir, Historique, Statistiques)
- Nettoyage imports inutilises (Scale, Wallet, disputeAPI, ArrowRight dans le dashboard)

### Session 18 - Statistiques vers Parametres (2026-03-31)
- Creation de StatisticsPage.js standalone accessible via /settings/statistics
- Ajout du lien Statistiques + Wallet dans la page Parametres (6 cartes au total)
- Retrait de l'onglet Statistiques du OrganizerDashboard (reste: A venir, Historique)
- Dashboard simplifie et oriente action
- Nettoyage imports inutilises (Loader2, analytics state/callback)

### Session 19 - Fix bouton Modifier participant (2026-03-31)
- Bug: Le bouton crayon "Modifier" sur la page detail d'un RDV ne faisait rien pour les participants
- Cause: EditProposalModal etait rendu uniquement quand isOrganizer=true (ligne 903)
- Fix 1: Condition changee de {isOrganizer} a {(isOrganizer || viewerCanPropose)}
- Fix 2: viewerCanPropose utilisait user_id (parfois null) -> corrige pour utiliser viewerParticipantStatus (toujours fiable)
- Valide via testing_agent iteration 140 (100%: 8/8 frontend)

### Session 20 - Guard deadline modification (2026-03-31)
- Regle metier: Les modifications suivent la meme fenetre temporelle que les annulations (cancellation_deadline_hours)
- Backend: Guard ajoute dans create_proposal() - verifie now_utc() < start_datetime - cancellation_deadline_hours
- Frontend: Ajout de isBeyondDeadline dans le calcul de canEdit (meme logique que SecondaryActions pour l'annulation)
- Tests curl: Apres deadline -> 400 "Le delai de modification est depasse" / Avant deadline -> auto_applied OK

### Session 21 - Harmonisation UX check-in (2026-03-31)
- Cause: Header CTA proéminent reserve a isOrganizer, participant n'avait qu'un petit bouton outline
- AppointmentHeader.js: Condition canCheckin generalisee (status accepted_guaranteed + fenetre temporelle, quel que soit le role)
- AppointmentHeader.js: Props generiques (participantRecord, checkinDone, checkinData, handleCheckin) au lieu de org-specific
- CheckinBlock.js: Transforme en bloc details-only (GPS coords, distance, adresse) — zero CTA
- AppointmentDetail.js: Ajout viewerCheckinDone/Data + handleViewerCheckin + props unifiees activeCheckin*
- OrganizerCheckinBlock.js: Supprime (dead code)
- Wording harmonise: "Check-in GPS" (physique) / "Effectuer mon check-in" (video) / "Check-in effectue" (apres)
- Valide via testing_agent iteration 141 (100%: 7/7 frontend)

### Session 22 - Historique modifications sur cartes dashboard (2026-03-31)
- Chargement des modifications appliquees (auto_applied/approved) en plus des pending
- Calcul modHistoryByAptId: map des 2 dernieres modifications appliquees par RDV
- Bloc d'historique sur TimelineCard: icone crayon + formatChangeSummary (ex: Date : 3 avr -> 1 avr)
- Style discret coherent (text-[11px] text-slate-400, border-b border-slate-100)
- Harmonise: meme placement, style, wording pour organisateur et participant
- Teste visuellement: 3 blocs affichés organisateur, 0 participant (correct), zero erreur console

## Data Integrity Rules
- Participant documents MUST have valid user_id when user exists
- Every appointment MUST have an is_organizer=True participant record
- Modification proposals require unanimity from all involved parties
- Direct modification when 0 accepted non-org participants
- ObjectId exclusion from all MongoDB responses

## Business Rules - Modification System
- Unanimity required (coherent with Trustless engine)
- Organizer proposes -> all accepted non-org participants vote
- Participant proposes -> organizer + all other accepted non-org participants vote
- 24h expiry on proposals
- Direct modification if no accepted non-org participants exist

### Session 23 - Fusion "Actions requises" Dashboard (2026-03-29)
- Section unifiée "Actions requises" sur OrganizerDashboard.js (lignes 982-1061)
- Sous-section 1: "Action immédiate — Invitations & garanties" (ActionCards)
- Sous-section 2: "Modifications à valider" (cartes modification avec barre de progression + CTA "Examiner")
- Rendu conditionnel: section masquée si aucune action requise
- Divider entre sous-sections quand les deux ont des données
- Validé via testing_agent iteration 142 (100%: 12/12 backend, 10/10 frontend)

### Session 24 - Notifications in-app P0+P1 (2026-03-29)
**Backend:**
- Collection `user_notifications` avec logique lu/non-lu
- Service notification_service.py: create, counts, mark_read, unread_ids
- Routes notification_routes.py: GET /counts, GET /unread-ids/{type}, POST /mark-read
- Triggers automatiques dans declarative_service.py:
  - open_dispute() → notifie les 2 parties (dispute_update)
  - submit_dispute_position() → notifie l'autre partie (dispute_update)
  - _check_positions_and_resolve() escalade → notifie les 2 parties (dispute_update)
  - resolve_dispute() → notifie les 2 parties (decision)

**Frontend:**
- AppNavbar.js: Badge rouge Décisions + badge Litiges (avec polling 30s)
- DecisionsListPage.js: Point bleu + fond bleu sur cartes non lues
- DecisionDetailPage.js: Marque comme lu à l'ouverture
- DisputesListPage.js: Point bleu sur cartes de litige non lues
- DisputeDetailPage.js: Marque comme lu à l'ouverture
- Mobile: badges + dot notification sur hamburger
- Validé via testing_agent iteration 143 (100%: 13/13 backend, 13/13 frontend)

### Session 25 - Notifications email P0+P1 (2026-03-29)
**Emails ajoutés (charte graphique NLYT respectée):**
- send_decision_rendered_email: accent dynamique selon outcome (success/danger/warning)
- send_dispute_opened_email: accent warning, CTA "Voir le litige et répondre"
- send_dispute_escalated_email: accent warning, CTA secondaire "Suivre le dossier"
**Triggers email dans notification_service.py:**
- notify_decision_rendered → email aux 2 parties + in-app
- notify_dispute_opened → email aux 2 parties + in-app
- notify_dispute_escalated → email aux 2 parties + in-app
- notify_dispute_position_submitted → in-app seul (pas d'email, stratégie validée)
**Idempotence:** champ email_sent dans user_notifications, vérification was_email_sent() avant envoi
**Garde-fou:** notification in-app créée AVANT l'email. Si email échoue, in-app reste visible
- Validé via testing_agent iteration 144 (100%: 19/19 backend, 14/14 frontend)

### Session 27 - Fix doublon email modifications (2026-03-29)
**Bug:** Deux systèmes d'envoi email coexistaient pour les modifications de RDV
- ANCIEN: _send_proposal_emails() + _send_acceptance_emails() dans modification_routes.py (HTML inline, pas d'idempotence)
- NOUVEAU: _notify_modification_proposed() + _notify_modification_applied() dans modification_service.py (charte NLYT, idempotent)
**Fix:** Suppression des 2 fonctions legacy de modification_routes.py (170 lignes de dead code)
- Source de vérité unique = modification_service.py
- Seuls email_types actifs: 'modification_proposed' et 'modification_applied'
- Prouvé: 1 proposition = 1 email (avant: 2 emails)
- Validé via testing_agent iteration 146 (100%: 21/21 backend, 6/6 frontend)
**Emails ajoutés:**
- send_modification_proposed_email: accent info, tableau avant/après, CTA "Voter sur la modification"
- send_modification_reminder_email: accent warning, alerte expiration imminente, CTA "Voter avant expiration"
**Triggers dans modification_service.py:**
- _notify_modification_proposed(): après create_proposal() → email + in-app aux votants
- _notify_modification_applied(): après _apply_proposal() → in-app toujours, email seulement si structurant
- Filtre structurant: start_datetime, location, appointment_type, meeting_provider
**Rappel J-1:**
- send_modification_vote_reminders(): scheduler toutes les 15min
- Ne s'active que si la proposition expire dans < 1h ET entre 9h-20h Paris
- Ciblé: uniquement les votants n'ayant pas répondu
- Idempotent via clé {proposal_id}_reminder
**Compteurs:** GET /api/notifications/counts inclut désormais modifications
- Validé via testing_agent iteration 145 (100%: 21/21 backend, 7/7 frontend)

## Upcoming Tasks (P1)
- Configurer le webhook Stripe en production pour validation end-to-end
- Test reel Zoom/Teams avec vrais tokens

## Future Tasks (P2)
- P2: Triggers notifications in-app pour les modifications de RDV (persistance lu/non-lu)
- Charity Payouts V2 (Stripe Transfers)
- Webhooks temps reel Zoom/Teams

### P2 — Notifications email/push (cahier des charges)
**Contrainte** : Respecter strictement la charte graphique email existante (email_service.py : _base_template, ACCENT_COLORS, _btn, _info_box, _alert_box, _detail_row, _greeting, _paragraph, _brand_note).

**Evenements declencheurs** :

| Evenement | Destinataire | Accent | Sujet type |
|---|---|---|---|
| Demande de feuille de presence | Organisateur | info (#3B82F6) | "Feuille de presence a completer" |
| Creation d'un litige | Les 2 parties (org + participant) | warning (#F59E0B) | "Un litige a ete ouvert" |
| Decision d'arbitrage rendue | Les 2 parties | neutral (#64748B) ou success/danger selon outcome | "Decision rendue sur votre litige" |
| Position adverse soumise sur un litige | L'autre partie | info | "Nouvelle position soumise" |
| Litige escalade vers arbitrage | Les 2 parties | danger (#EF4444) | "Litige transmis a un arbitre" |
| Proposition de modification de RDV | Tous les votants | info | "Modification proposee — vote requis" |
| Modification de RDV appliquee | Tous les participants | success (#10B981) | "Votre RDV a ete modifie" |
| Rappel : vote modification expirant (J-1) | Votants n'ayant pas vote | warning | "Vote en attente — expiration demain" |

**Principes** :
- Chaque email utilise _base_template() avec l'accent adapte
- CTA principal vers la page concernee (ex: /decisions/{id}, /litiges/{id})
- Info box avec details du RDV (titre, date, lieu, type)
- Ton professionnel, concis, meme hierarchie que les emails existants
- Pas de push navigateur dans un premier temps (email uniquement)
