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

### Scheduler Health Monitoring Endpoint (2026-04-05)
- Endpoint GET /api/admin/scheduler-health (admin only, 401/403 protege)
- Vue globale : global_status (ok/warning/error) + summary (total/ok/warning/error)
- Vue par job : nom, intervalle, TTL, health_status, current_state (idle/running), last_run (at, duration_ms, result), next_run, lock info, stats (total/successful/failed runs)
- Detection problemes : job jamais execute (warning), lock stale >80% TTL (warning), derniere execution echouee (error)
- Tri automatique : erreurs en premier, puis warnings, puis ok
- Refactoring scheduler.py : JOB_REGISTRY centralise, run_locked_job helper (lock + tracking en un seul appel), code reduit de 352 a 210 lignes
- Tests : endpoint live verifie (3 jobs ok apres 2min, 14 warning = pas encore execute, 0 error)

### Distributed Lock Scheduler — Multi-Pod Safety (2026-04-05)
- MongoDB advisory lock avec acquisition atomique (find_one_and_update + upsert)
- Index unique sur job_id + TTL index sur expires_at pour auto-expiration
- 17 jobs scheduler proteges contre l'execution concurrente inter-pods
- TTL adapte par job : 90s (2min interval) a 1800s (6h+ interval)
- Release par proprietaire uniquement (locked_by == INSTANCE_ID)
- Execution tracking : scheduler_job_history collection (start, duration, success/failure, run counts)
- Tests : 9/9 PASS

### Audit Securite Feuilles de Presence (2026-04-05)
- Fallback securise sur GET /attendance-sheets/{appointment_id}
- Aucun parametre externe accepte, tout vient du JWT
- Tests : 7/7 PASS (3 autorises + 4 interdits)

### Notifications Feuilles de Presence — Equite declarative (2026-04-04)
- Email automatique a l'ouverture de la phase collecting pour TOUS les participants
- Relance automatique 12h avant deadline, auto-linkage etendu, idempotence complete
- Tests : 19/19 OK

### Phase 1 Pre-Production — Equite & UX (2026-04-04)
- Notifications escalade/decision pour sans-compte, parcours register redirect, scheduler 5min
- Tests : 24/24 backend + 5/5 frontend

### Audit Produit Global + QA Angles Morts (2026-04-04)
- 11 angles morts testes, 5 failles corrigees
- Score final QA : 12/12 OK

### V5.1: Phase Declarative Reservee aux Garantis (2026-04-03)
- Seuls les accepted_guaranteed entrent dans la phase declarative
- Tests: 24/24 + 32/32 QA + 5 scenarios UI

### Refonte Moteur Declaratif V5 + Migration
- Auto-litiges elimines, unknown = neutre, 3 categories
- Migration: 48 litiges resolus, 23 RDV liberes

## Data Integrity Rules
- V5: unknown = neutre, auto-litige interdit
- V5.1: seuls les accepted_guaranteed entrent en phase declarative
- Distributed Lock: acquisition atomique, TTL auto-expire, owner-only release
- Participant-to-User Mapping: participant MUST have valid user_id if user exists

## Upcoming Tasks (P1)
- Dashboard admin plateforme pour arbitrer les litiges escalades
- Webhook Stripe production
- Test reel Zoom/Teams avec vrais tokens

## Future Tasks (P2)
- Charity Payouts V2 (Automatisation via Stripe Connect)
- Webhooks temps reel Zoom/Teams en production
- Race condition Stripe webhook vs polling
- Notifications escalade/decision email pour l'organisateur
