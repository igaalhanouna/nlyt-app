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
- **Bug fix**: "Aucun participant accepte a notifier" quand l'organisateur modifie un RDV sans participants acceptes
- **Regle implementee**: 0 participant invite accepte -> modification directe (sans vote). >=1 participant invite accepte -> proposition/vote
- **Statuts acceptes**: accepted, accepted_pending_guarantee, accepted_guaranteed, guaranteed
- **UX adaptative**: Modal affiche "Modifier le rendez-vous" / "Appliquer la modification" en mode direct, "Proposer une modification" / "Envoyer la proposition" en mode proposition
- **Notifications**: En mode direct, email informatif envoye a TOUS les participants (y compris "invited")
- **Historique**: Modifications directes stockees comme `auto_applied` dans modification_proposals
- **Audit donnees**: 194/321 RDV actifs manquent le record participant-organisateur (ancien pattern, gere par la correction)
- Files: modification_service.py, modification_routes.py, AppointmentDetail.js, EditProposalModal.js

## Upcoming Tasks (P1)
- Dashboard admin plateforme pour arbitrer les litiges escalades
- Configurer webhook Stripe en production
- Test reel Zoom/Teams avec vrais tokens

## Future Tasks (P2)
- Charity Payouts V2 (Stripe Transfers)
- Webhooks temps reel Zoom/Teams
- Notification email/push creation litige

## Key Technical Rules
- Participant documents MUST have valid user_id when user exists
- Symmetric disputes: 1 per participant in manual_review, grouped by appointment_id in frontend
- Modification proposals require unanimity from accepted non-org participants
- Direct modification when 0 accepted non-org participants (organizer only)
- ObjectId exclusion from all MongoDB responses
