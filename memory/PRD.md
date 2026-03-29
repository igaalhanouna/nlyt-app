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
- Full Trustless V4 engine
- Appointment CRUD with guarantee system
- Invitation flow with email
- Calendar integration (Google, Outlook)
- Video evidence system (Zoom/Teams participant matching)
- Attendance evaluation engine
- Dispute system with declarative resolution
- Financial distribution engine (penalty capture, compensation, charity)
- Wallet system
- Policy snapshot / contract generation

### Session 5 - Cancel Guards
- Restriction UX: blocage annulation participant post-deadline
- Blocage backend annulation organisateur pour RDV demarres/passes

### Session 6 - Disputes UX Refactor
- Regroupement des litiges par RDV sur /litiges
- Ajout contexte manquant (type, lieu, duree)
- Filtrage litiges resolus

### Session 7 - Presences UX Refactor
- Contexte enrichi sur les cartes de presences
- Mode lecture seule pour presences deja soumises

### Session 8 - Orphan Participants Fix
- Correction POST /api/invitations/{token}/respond pour lier user_id
- Migration: 144 participants repares, 1 litige debloque

### Session 9 - Modification Flow Fix (2026-03-29)
- Bug fix: "Aucun participant accepte a notifier" quand 0 participants acceptes
- Regle: 0 accepte -> modification directe, >=1 -> proposition/vote
- Statuts acceptes: accepted, accepted_pending_guarantee, accepted_guaranteed, guaranteed
- UX adaptative: Modal titre/bouton/description adaptes au mode
- Notifications: email informatif a TOUS les participants en mode direct
- Historique: modifications directes stockees comme auto_applied

### Session 10 - Organizer Participant Migration (2026-03-29)
- Audit complet: 212/345 RDV sans record participant-organisateur
- Causes identifiees: heritage pre-22/03 + seed_demo.py bypass API
- Migration: 209 records inseres + 2 flags corriges = 344/345 couverts
- 1 RDV non migrable (organizer_id=None, artefact de test)
- Fix seed_demo.py: injection org-participant dans make_apt()
- Script idempotent avec tag migrated_at pour tracabilite
- Garde-fous: deduplication email, skip si organizer introuvable
- Iterations de test: 132 (modification flow), 133 (migration)

## Data Integrity Rules
- Participant documents MUST have valid user_id when user exists
- Every appointment MUST have an is_organizer=True participant record
- Symmetric disputes: 1 per participant in manual_review, grouped by appointment_id
- Modification proposals require unanimity from accepted non-org participants
- Direct modification when 0 accepted non-org participants (organizer only)
- ObjectId exclusion from all MongoDB responses

## Upcoming Tasks (P1)
- Dashboard admin plateforme pour arbitrer les litiges escalades
- Configurer webhook Stripe en production
- Test reel Zoom/Teams avec vrais tokens

## Future Tasks (P2)
- Charity Payouts V2 (Stripe Transfers)
- Webhooks temps reel Zoom/Teams
- Notification email/push creation litige
