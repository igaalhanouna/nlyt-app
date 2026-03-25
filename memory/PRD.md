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

## Navigation Architecture (Completed - Mars 2026)
- **AppNavbar** (`/src/components/AppNavbar.js`): Top bar persistante sur toutes les pages authentifiées
  - Logo N·L·Y·T cliquable → /dashboard
  - Liens: "Tableau de bord" | "Paramètres" (avec état actif)
  - Bouton Déconnexion
  - Sticky top avec z-40
- **AppBreadcrumb** (`/src/components/AppBreadcrumb.js`): Fil d'Ariane contextuel
  - Chemins cliquables: Tableau de bord > Paramètres > [sous-page]
  - Dernier élément en texte foncé (non cliquable)
- Suppression de tous les logos inline N·L·Y·T (remplacés par la navbar)
- Conservation des boutons "Retour" sur les pages profondes (ParticipantManagement, DisputeDetail)

## Pages avec AppNavbar + AppBreadcrumb
- OrganizerDashboard, ParticipantDashboard
- Settings hub, Profile, WorkspaceSettings, Integrations, PaymentSettings, WalletPage
- AppointmentWizard, AppointmentDetail, ParticipantManagement
- DisputeCenter, DisputeDetail
- ReviewerDashboard

## Completed Features
- [x] Stripe Connect (Phases 1-5): Wallet, Connect, Distribution, Payouts, Notifications
- [x] Physical attendance evidence engine (GPS, QR, check-in)
- [x] Video Conference Attendance Evidence MVP
- [x] Meeting API Integration (auto-create meetings, fetch attendance, CSV upload)
- [x] Google Meet creation via Calendar API
- [x] Integrations page — Calendars + Video sections
- [x] Controlled meeting provider selector in wizard
- [x] Source trust security
- [x] Smart Conflict Detection V1 & V2
- [x] Dashboard UX overhaul (impact-oriented)
- [x] Teams UX logic bug fix for standard/non-pro accounts
- [x] Calendar auto-sync settings separated by provider (Google/Outlook)
- [x] Dashboard personal impact calculation (wallet-based)
- [x] Complete Product Repositioning ("engagement solidaire" wording)
- [x] Dark theme on ImpactPage
- [x] Default compensation sliders: charity/geste solidaire first
- [x] N·L·Y·T typographic logo on ALL app pages
- [x] Navigation globale: AppNavbar + AppBreadcrumb sur toutes les pages authentifiées
- [x] Fix Settings dead-end: breadcrumb + navbar permettent toujours de revenir au dashboard
- [x] Fix Profile retour: va maintenant vers /settings (via breadcrumb) au lieu de /dashboard

## P0 — Configuration Pending
- [ ] Zoom credentials (ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET)
- [ ] Teams credentials (real MICROSOFT_TENANT_ID, CLIENT_ID, CLIENT_SECRET)

## P1 — Next Up
- [ ] Aligner les emails transactionnels backend (wording "engagement solidaire" / "temps valorisé")
- [ ] Refactorer InvitationPage.js (1400+ lignes -> composants modulaires)
- [ ] Test réel du mode calendar Teams (compte Outlook non-pro)

## P2 — Planned
- [ ] Zoom webhook auto-ingestion
- [ ] Teams webhook auto-ingestion
- [ ] Meeting link in calendar sync events

## P3 — Backlog
- [ ] Charity Payouts V2 (Stripe Transfers)
- [ ] Webhooks temps réel Zoom/Teams
- [ ] Pages dédiées charité & Leaderboard
- [ ] Dashboard analytics for organizers
- [ ] Advanced dispute resolution
