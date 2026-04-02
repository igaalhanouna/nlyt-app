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

## Completed Features

### Distributed Lock Scheduler — Multi-Pod Safety (2026-04-05)
- MongoDB advisory lock avec acquisition atomique (find_one_and_update + upsert)
- Index unique sur job_id + TTL index sur expires_at pour auto-expiration
- 16 jobs scheduler proteges contre l'execution concurrente inter-pods
- TTL adapte par job : 90s (2min interval) a 1800s (6h+ interval)
- Release par proprietaire uniquement (locked_by == INSTANCE_ID)
- Auto-expiration si le pod meurt (pas de deadlock permanent)
- Logs clairs : acquired / skipped / released
- Tests : 9/9 PASS (acquisition, blocage, TTL, recovery, double processing, owner-only release, upsert safety, independence, re-acquisition)
- Fichiers : services/distributed_lock.py (nouveau), scheduler.py (reecrit), tests/test_distributed_lock.py

### Audit Securite Feuilles de Presence (2026-04-05)
- Fallback securise ajoute sur GET /attendance-sheets/{appointment_id}
- Logique : fast path user_id → fallback participant_id (via JWT user_id + email) → 404
- Auto-heal du linkage submitted_by_user_id apres fallback
- Aucun parametre externe accepte (pas de participant_id en input)
- Coherence renforcee sur GET /pending (ajout lookup email JWT)
- Tests : 7/7 PASS (3 autorises + 4 interdits)
- Fichier : tests/test_sheet_access_security.py

### Notifications Feuilles de Presence — Equite declarative (2026-04-04)
- Email automatique a l'ouverture de la phase collecting pour TOUS les participants (avec et sans compte)
- Fix critique : les participants sans compte ne sont plus exclus de la phase declarative
- Relance automatique 12h avant deadline via scheduler
- Auto-linkage etendu : attendance_sheets liees au user_id au login
- Fallback submit_sheet : lookup par participant_id si user_id non encore lie
- Idempotence complete sur les 2 emails (sheet_pending + sheet_reminder)
- Tests : 19/19 OK

### Phase 1 Pre-Production — Equite & UX (2026-04-04)
- Notifications escalade/decision pour participants sans compte
- Parcours register → redirect litige
- Granularite scheduler : declarative deadline 5min, dispute escalation 15min
- Auto-linkage orphan participants/disputes au login
- Tests : 24/24 backend + 5/5 frontend

### Audit Produit Global + QA Angles Morts (2026-04-04)
- 11 angles morts testes, 5 failles corrigees (BS-1 critique, BS-2/3 majeur, BS-4/6 moyen)
- Score final QA : 12/12 OK
- Rapport : /app/backend/AUDIT_RAPPORT_V51.md

### V5.1: Phase Declarative Reservee aux Garantis (2026-04-03)
- Seuls les participants accepted_guaranteed en manual_review entrent dans la phase declarative
- Participants non-garantis auto-resolus en waived
- Tests: 24/24 + 32/32 QA + 5 scenarios UI

### Refonte Moteur Declaratif V5 + Migration
- Auto-litiges elimines, unknown = neutre
- 3 categories: waived / on_time / litige
- Migration: 48 litiges resolus, 23 RDV liberes

## Data Integrity Rules
- V5: unknown = neutre, absence de preuve != preuve negative, auto-litige interdit
- V5.1: seuls les accepted_guaranteed entrent en phase declarative
- Notifications: auto-cleanup des dispute_update pour litiges resolus/inexistants
- Participant-to-User Mapping: participant MUST have valid user_id if user exists
- Distributed Lock: acquisition atomique, TTL auto-expire, owner-only release

## Upcoming Tasks (P1)
- Monitoring scheduler (heartbeats + endpoint /api/admin/scheduler-health)
- Dashboard admin plateforme pour arbitrer les litiges escalades
- Webhook Stripe production
- Test reel Zoom/Teams avec vrais tokens

## Future Tasks (P2)
- Charity Payouts V2 (Automatisation via Stripe Connect)
- Webhooks temps reel Zoom/Teams en production
- Race condition Stripe webhook vs polling
- Notifications escalade/decision email pour l'organisateur
