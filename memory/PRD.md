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

### Fix Orphaned Collecting Phases + UX Contextualisation (2026-04-05)
- Diagnostic complet du RDV 053f405d : seul 1 participant garanti en manual_review, phase collecting bloquee sans issue
- **Migration script** : `scripts/fix_orphaned_collecting.py` — nettoie les RDV existants avec < 2 guaranteed en manual_review
- **Guard retroactif** dans `run_declarative_deadline_job()` — verifie a chaque cycle (5min) si des phases collecting sont orphelines, auto-waive si < 2 guaranteed
- **UX contextualisee** : le message du resultat financier change selon la phase declarative :
  - `collecting` → "Declarations en cours — en attente des feuilles de presence"
  - `analyzing` → "Analyse en cours des declarations — resultat imminent"
  - `disputed` → "Litige ouvert — en attente de resolution"
  - Defaut → "Decision en attente — aucune action financiere pour le moment"
- Tests : 5/5 PASS (single guaranteed, two guaranteed, zero guaranteed, mixed, resolved untouched)

### Scheduler Health Monitoring Endpoint (2026-04-05)
- Endpoint GET /api/admin/scheduler-health (admin only, 401/403 protege)
- Vue globale + vue par job avec health_status, current_state, last_run, next_run, stats
- Refactoring scheduler.py : JOB_REGISTRY centralise, run_locked_job helper

### Distributed Lock Scheduler — Multi-Pod Safety (2026-04-05)
- MongoDB advisory lock avec acquisition atomique
- 17 jobs scheduler proteges contre l'execution concurrente inter-pods
- Tests : 9/9 PASS

### Audit Securite Feuilles de Presence (2026-04-05)
- Fallback securise sur GET /attendance-sheets/{appointment_id}
- Tests : 7/7 PASS

### Notifications Feuilles de Presence — Equite declarative (2026-04-04)
- Email automatique pour TOUS les participants (avec et sans compte)
- Relance 12h avant deadline, auto-linkage etendu, idempotence complete

### Phase 1 Pre-Production — Equite & UX (2026-04-04)
- Notifications escalade/decision pour sans-compte
- Parcours register redirect, scheduler 5min

### Audit Produit Global + QA Angles Morts (2026-04-04)
- 11 angles morts testes, 5 failles corrigees, score 12/12

### V5.1: Phase Declarative Reservee aux Garantis (2026-04-03)
- Seuls les accepted_guaranteed entrent dans la phase declarative

### Refonte Moteur Declaratif V5 + Migration
- Auto-litiges elimines, unknown = neutre, 3 categories

## Data Integrity Rules
- V5: unknown = neutre, auto-litige interdit
- V5.1: seuls les accepted_guaranteed (>= 2) entrent en phase declarative
- Guard retroactif : le deadline job nettoie les orphelins toutes les 5min
- Distributed Lock : acquisition atomique, TTL auto-expire, owner-only release
- Participant-to-User Mapping : participant MUST have valid user_id if user exists

## Upcoming Tasks (P1)
- Webhook Stripe production
- Test reel Zoom/Teams avec vrais tokens

## Future Tasks (P2)
- Charity Payouts V2 (Automatisation via Stripe Connect)
- Webhooks temps reel Zoom/Teams en production
- Race condition Stripe webhook vs polling
- Notifications escalade/decision email pour l'organisateur
