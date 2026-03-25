# NLYT — Product Requirements Document

## Vision
SaaS de gestion d'assiduité avec garanties financières. NLYT vérifie la présence des participants via des preuves indépendantes. Repositionné en "engagements solidaires" avec un framing premium.

## Technical Stack
Frontend: React + TailwindCSS + Shadcn/UI
Backend: FastAPI + Python + MongoDB + slowapi
Email: Resend | Payments: Stripe | Video: Zoom/Teams/Meet API

## Branding
- Logo typographique: `N·L·Y·T` (text-lg font-bold tracking-[0.35em]) avec `NEVER LOSE YOUR TIME` (text-[10px] uppercase tracking-[0.25em] text-slate-400/500) en dessous
- Pages publiques (Landing, Impact): dark theme (#0A0A0B)
- Dashboard/Settings: light theme propre
- Wording: "Engagement solidaire" au lieu de "rendez-vous", "Geste solidaire" au lieu de "pénalité", "Temps valorisé"
- Custom domain: app.nlyt.io (production)

## Navigation Architecture (Mars 2026)
- **AppNavbar** (`/src/components/AppNavbar.js`): Top bar persistante, logo cliquable, état actif
- **AppBreadcrumb** (`/src/components/AppBreadcrumb.js`): Fil d'Ariane contextuel
- **SettingsPageLayout** (`/src/components/SettingsPageLayout.js`): Layout standardisé pour toutes les pages /settings/*

## Settings Design System Rules
- Container: max-w-4xl mx-auto px-6 pb-16
- Background: bg-background (toujours, jamais bg-slate-50)
- Title: text-2xl font-bold text-slate-900
- Description: text-sm text-slate-500 mb-8
- Action CTA: aligné à droite du titre via prop `action`
- Cards: bg-white rounded-xl border border-slate-200 p-6 mb-6
- No icons before page titles
- Spacing: mb-8 between header and content, mb-6 between sections

## Completed Features
- [x] Stripe Connect (Phases 1-5)
- [x] Physical attendance evidence engine
- [x] Video Conference Attendance Evidence MVP
- [x] Meeting API Integration
- [x] Smart Conflict Detection V1 & V2
- [x] Dashboard UX overhaul
- [x] Complete Product Repositioning
- [x] N·L·Y·T typographic logo on ALL app pages
- [x] Navigation globale: AppNavbar + AppBreadcrumb sur toutes les pages authentifiées
- [x] SettingsPageLayout: Harmonisation complète des 6 pages /settings/*

## P0 — Configuration Pending
- [ ] Zoom credentials
- [ ] Teams credentials

## P1 — Next Up
- [ ] Aligner les emails transactionnels backend (wording "engagement solidaire")
- [ ] Refactorer InvitationPage.js (1400+ lignes)
- [ ] Test réel Teams (compte non-pro)

## P2 — Planned
- [ ] Zoom webhook auto-ingestion
- [ ] Teams webhook auto-ingestion

## P3 — Backlog
- [ ] Charity Payouts V2 (Stripe Transfers)
- [ ] Webhooks temps réel Zoom/Teams
- [ ] Pages dédiées charité & Leaderboard
