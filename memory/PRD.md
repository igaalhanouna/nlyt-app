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

### Stripe Webhook Production-Ready — P0 + P1 (2026-04-05)
- **P0: Handler `payment_intent.payment_failed`** — capture de penalite echouee → garantie `capture_failed` + alerte admin critique auto-generee
- **P1a: Handler `charge.dispute.created`** — chargeback detecte → wallet gele automatiquement + alerte admin critique
- **P1b: Cleanup garanties abandonnees** — job scheduler (15min) expire les garanties `pending` > 1h, revert participant a `accepted`
- **P1c: Endpoint admin `/api/admin/stripe-webhook-status`** — monitoring events recus, alertes actives, statuts garanties, wallets geles
- Configuration Stripe Dashboard : 9 evenements configures par l'utilisateur
- Tests : data flow chargeback + cleanup stale guarantee valides

### Fix Orphaned Collecting Phases + UX Contextualisation (2026-04-05)
- Migration script : `scripts/fix_orphaned_collecting.py`
- Guard retroactif dans `run_declarative_deadline_job()` : auto-waive si < 2 guaranteed
- UX contextualisee : messages differencies par phase (collecting/analyzing/disputed)
- Tests : 5/5 PASS

### Scheduler Health Monitoring Endpoint (2026-04-05)
- GET /api/admin/scheduler-health (admin only)
- Vue globale + detail par job avec health_status, stats
- JOB_REGISTRY centralise, run_locked_job helper

### Distributed Lock Scheduler — Multi-Pod Safety (2026-04-05)
- MongoDB advisory lock, 18 jobs proteges
- Tests : 9/9 PASS

### Audit Securite Feuilles de Presence (2026-04-05)
- Fallback securise sur GET /attendance-sheets/{appointment_id}
- Tests : 7/7 PASS

### Notifications Feuilles de Presence — Equite declarative (2026-04-04)
- Email pour TOUS les participants, relance 12h, auto-linkage, idempotence

### Phase 1 Pre-Production — Equite & UX (2026-04-04)
- Notifications escalade/decision pour sans-compte, redirect, scheduler 5min

### Audit Produit Global + QA Angles Morts (2026-04-04)
- 11 angles morts, 5 failles corrigees, score 12/12

### V5.1: Phase Declarative Reservee aux Garantis (2026-04-03)
- Seuls les accepted_guaranteed (>= 2) entrent en phase declarative

### Refonte Moteur Declaratif V5 + Migration
- Auto-litiges elimines, unknown = neutre, 3 categories

## Upcoming Tasks (P1)
- Test reel Zoom/Teams avec vrais tokens
- Configurer STRIPE_WEBHOOK_SECRET de production dans .env prod (apres test live du webhook)

## Future Tasks (P2)
- Charity Payouts V2 (Automatisation via Stripe Connect)
- Webhooks temps reel Zoom/Teams en production
- Race condition Stripe webhook vs polling
- Notifications escalade/decision email pour l'organisateur
- Monitoring retries Stripe (deduplication multi-event_id)
