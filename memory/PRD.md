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
- Weak/no proof = manual_checkin only, NLYT < 30, no evidence → manual_review → Presences
- Small groups (< 3 participants): no longer bypass Presences. Sheets always created.
- Self-declaration: targeted participants declare on themselves (is_self_declaration=true)
- Small group analysis: direct comparison, agreement → resolve, disagreement → dispute
- Old _escalate_all_manual_reviews() REMOVED (dead code)
- Wording: "Votre declaration sur les presences" / "Votre position sur le litige"
- Lock-down tests: /app/backend/tests/test_strong_proof_lockdown.py (9 tests, 100%)
- Flow tests: /app/backend/tests/test_presences_flow.py (5 tests)

### Phase 17 — Schema Alignment & Data Cleanup (Feb 2026) - DONE
- **Bug fix**: `_has_admissible_proof()` was checking `evidence_type` (nearly unused in DB) and root-level `gps_within_radius` (doesn't exist). Fixed to check `source` field and `derived_facts` nested dict.
- **DB schema reality**: `source` = "gps"|"qr"|"video_conference"|"manual_checkin", `gps_within_radius` inside `derived_facts`, `provider` inside `derived_facts`
- **Video conference validation**: Zoom/Teams require `provider_evidence_ceiling=strong` AND `video_attendance_outcome` in (joined_on_time, joined_late). Google Meet (assisted) correctly excluded.
- **Tests expanded**: 6 → 9 tests (added Teams, Meet exclusion, GPS-outside-radius)
- **Data cleanup script**: `/app/backend/scripts/clean_ghost_disputes.py`
  - 6 misclassified manual_review records deleted (had strong proof)
  - 11 ghost disputes purged (4 test, 4 strong-proof, 2 cancelled-apt, 1 resolved-strong)
  - 1 orphan sheet removed
  - 17 backups saved in `cleanup_backups` collection
  - 5 appointments reset for re-evaluation


- /litiges page shows ONLY active disputes (awaiting_positions, escalated)
- Resolved disputes (agreed_present, agreed_absent, agreed_late_penalized, resolved) hidden from list
- Resolved disputes remain accessible via direct URL /litiges/{id}
- Empty state: "Aucun litige en cours" when all resolved
- No "Litiges résolus" section — page is purely an action list
- COMPLETE REWORK: Replaced asymmetric accuser/accused model with symmetric positions
- Rule: No penalty without DOUBLE EXPLICIT confirmation (organizer + participant)
- Rule: Silence = uncertainty = automatic escalation (NEVER a penalty)
- Covers BOTH no_show AND late_penalized statuses identically
- Both parties use POST /api/disputes/{id}/position with values: confirmed_present | confirmed_absent | confirmed_late_penalized
- Mutual agreement auto-resolves; disagreement auto-escalates to platform
- Old endpoints /concede and /maintain REMOVED
- Frontend: Symmetric DisputeDetailPage with 3 position buttons, confirmation modal, clear blocks (Ce qui s'est passe, Votre declaration, Votre position)
- Frontend: DisputesListPage with action hints (Votre reponse est attendue / En attente de l'autre partie)
- Migration: /app/backend/scripts/migrate_disputes_v4.py ran for 28 existing disputes

## Agenda Calendar View (Mar 2026)
- Route: /agenda, navbar position: juste apres "Tableau de bord"
- 3 vues: Mois, Semaine, Jour (toggle Mois/Semaine/Jour)
- Donnees: appointmentAPI.myTimeline() + externalEventsAPI.list(), merge client-side
- Tri: heure croissante, NLYT prioritaire a meme heure
- Differentiation: dots solides (NLYT) vs dots creux (Google/Microsoft)
- Vue Mois: grille calendrier, clic jour ouvre panneau detail
- Vue Semaine: grille temporelle 7j (Lun-Dim), blocs positionnes, clic colonne -> vue Jour
- Vue Jour: grille temporelle + sidebar liste detaillee (compteur evenements)
- Navigation: fleches prev/next adaptees par vue, bouton Aujourd'hui
- Clic NLYT: navigate vers /appointments/{id}
- Clic externe: non-cliquable
- CalendarSyncPanel integre pour toggle Google/Microsoft
- Aucun endpoint backend ajoute, zero logique metier nouvelle
- Tests: iteration_112, 100% (4 backend + 16 frontend)

## Toggle Harmonisation Dashboard/Agenda (Mar 2026)
- Refetch cible: toggle ON dans Agenda ne refetch que external-events, pas my-timeline
- Guard anti double-clic: useRef settingChangeRef sur Dashboard ET Agenda
- Auto-refresh 2min: Agenda aligne sur Dashboard (syncIntervalRef, 120s, sync+refetch events)
- lastAutoCheckAt passe au CalendarSyncPanel dans les deux pages
- Condition refetch ON: verifie res.data?.sync?.synced (identique Dashboard)
- Tests: iteration_113, 100%

## Check-in Time Window (Mar 2026)
- Regle unique: ouverture start-30min, fermeture end+60min
- Source de verite: CHECKIN_WINDOW_BEFORE_MINUTES=30, CHECKIN_WINDOW_AFTER_HOURS=1 (evidence_service.py)
- Backend physique (checkin_routes.py): deja aligne
- Backend visio (proof_routes.py): time gate ajoute via _enforce_time_gate() sur /checkin et /info
- Frontend physique (InvitationCheckinSection.js): windowClose corrige de durationMin+toleratedDelay vers durationMin+60
- Frontend visio (CheckinPage.js): etats before/during/after ajoutes avec messages FR
- P1 restant: RÉSOLU — AppointmentHeader.js + OrganizerCheckinBlock.js alignés avec time gate

## Modification Emails (Mar 2026)
- Email "Engagement modifie" envoye apres toute modification acceptee
- Destinataires: participants engages (accepted_*) + organisateur (si non-proposeur)
- Tableau avant/apres avec labels FR (Format, Duree, Lieu, Plateforme visio)
- Bloc acces conditionnel: proof_link pour visio, check-in GPS pour physique
- Pas de reset du flag confirmation_email_sent — email unique suffit
- 3 callers invitation corrigés (participants.py, invitations.py, appointments.py) pour passer meeting_provider/meeting_join_url
- Nettoyage complet visio->physique: meeting_provider + meeting_join_url + external_meeting_id

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
- P2: Dashboard admin plateforme (arbitrage final des litiges escalades "maintained")

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
