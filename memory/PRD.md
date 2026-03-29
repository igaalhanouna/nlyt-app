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

### Session 12 - Fix Modification Summary Display (2026-03-30)
- Fixed formatChangeSummary() displaying only time changes, ignoring DATE/LIEU/VISIO
- Now shows: Date (old → new), Horaire (old → new), Lieu (old → new), Visio (old → new), Durée
- Validated via testing_agent iteration 135 (100% pass rate)

### Session 13 - P2.1 Timeline History + P2.2 Vote Progress (2026-03-30)
- P2.2: VoteProgressBar component with X/Y counter + colored progress bar (emerald=100%, amber=partial)
  - Displayed in: active proposal banner (detail page), Dashboard modification cards, Dashboard timeline context banners
- P2.1: Full chronological timeline replacing minimal history list
  - Vertical line with colored dots per status (green=accepted, red=rejected, grey=expired/cancelled)
  - Each entry shows: date, proposer, mode (Direct/Vote), old→new values per changed field, individual vote responses
- Fixed nested <a> HTML warning in Dashboard timeline cards
- Validated via testing_agent iteration 136 (100% pass rate: 9/9 backend, 12/12 frontend)

### Session 14 - P1: Dashboard Admin Arbitrage des litiges (2026-03-30)
- Backend: admin_arbitration_service.py (tech dossier builder, analyse système, enriched list/detail)
- Backend: admin.py rewrite (GET /arbitration, /stats, /:id, POST /:id/resolve) with require_admin guard
- Backend: role field added to JWT payload + user response on login
- Backend: promote_admin.py script (testuser_audit@nlyt.app → admin)
- Frontend: AdminArbitrationList.js (stats KPIs, dispute cards with proof badge, positions, age indicator)
- Frontend: AdminArbitrationDetail.js (5 blocs: verdict tech, analyse système, positions, déclarations, arbitrage)
- Frontend: Navbar updated (admin-only "Arbitrage" link desktop + mobile)
- Wording: "Analyse système" (pas recommandation), "Charge de la preuve sur le participant"
- Validated via testing_agent iteration 137 (100%: 14/14 backend, 14/14 frontend)

### Session 15 - Consequences financieres + KPI cliquables (2026-03-30)
- Backend: financial_context added to dispute detail (penalty_amount, platform/charity/compensation breakdown)
- Backend: financial_summary added to list cards for resolved disputes ("10EUR preleves — 5EUR verses")
- Backend: GET /api/admin/arbitration?filter=escalated|awaiting|resolved|agreed (new param)
- Frontend detail (Zone 4): Dynamic FinancialPreview component showing full breakdown when outcome selected
- Frontend list: financial_summary badge on each resolved/agreed card (green=no penalty, red=penalty)
- Frontend list: KPI stats are now clickable filters with active ring indicator
- All lint clean, visually verified

## Upcoming Tasks (P1)
- Configurer le webhook Stripe en production pour validation end-to-end
- Configurer webhook Stripe en production
- Test reel Zoom/Teams avec vrais tokens

## Future Tasks (P2)
- Notifications in-app (P2.3)
- Charity Payouts V2 (Stripe Transfers)
- Webhooks temps reel Zoom/Teams
- Notification email/push creation litige
