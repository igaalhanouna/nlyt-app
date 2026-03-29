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

## Upcoming Tasks (P1)
- Dashboard admin plateforme pour arbitrer les litiges escalades
- Configurer webhook Stripe en production
- Test reel Zoom/Teams avec vrais tokens

## Future Tasks (P2)
- Timeline/historique complet des modifications (P2.1)
- Compteur progression votes (P2.2)
- Notifications in-app (P2.3)
- Charity Payouts V2 (Stripe Transfers)
- Webhooks temps reel Zoom/Teams
- Notification email/push creation litige
