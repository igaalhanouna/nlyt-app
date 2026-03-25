# NLYT — Product Requirements Document

## Vision
SaaS de gestion d'assiduité avec garanties financières. Repositionné en "engagements solidaires" avec un framing premium.

## Technical Stack
Frontend: React + TailwindCSS + Shadcn/UI
Backend: FastAPI + Python + MongoDB + slowapi
Email: Resend | Payments: Stripe | Video: Zoom/Teams/Meet API

## Branding
- Logo typographique: N·L·Y·T + "Never Lose Your Time"
- Site: dark theme (#0A0A0B) public, light theme dashboard
- Wording: "Engagement solidaire", "Geste solidaire", "Temps valorisé"
- SITE_URL: https://app.nlyt.io (all outbound links)

## Email Design System (Mars 2026)
- Base template: `_base_template()` in email_service.py
- Header: #0A0A0B dark with N·L·Y·T typographic logo (subtitle OUTSIDE `<a>` tag to avoid Outlook blue override)
- Subtitle color: #64748B (matches landing page text-slate-500)
- All links point to SITE_URL = https://app.nlyt.io
- Accent bars: info (blue), success (green), warning (amber), danger (red), neutral (slate)
- Buttons: `_btn()` dark bg, `_btn_secondary()` outline
- Helpers: `_greeting()`, `_paragraph()`, `_section_title()`, `_info_box()`, `_alert_box()`, `_detail_row()`, `_small()`, `_fallback_link()`
- Footer: "© 2026 N·L·Y·T — Never Lose Your Time"
- 9 emails refactored: verification, password_reset, invitation, acceptance, checkin, participant_cancellation, appointment_cancelled, appointment_deleted, guarantee_revalidation

## Navigation
- AppNavbar: persistent top bar, logo clickable, hamburger drawer on mobile (<md)
- AppBreadcrumb: contextual breadcrumb, compact on mobile with shortLabels
- SettingsPageLayout: standardized settings pages, responsive padding

## Mobile Design System (Mars 2026)
- Breakpoint principal: md (768px) = desktop/mobile switch
- Navbar mobile: hamburger icon → slide drawer (right), backdrop blur
- Breadcrumb mobile: scroll horizontal caché, labels courts
- Boutons CTA: min-h-[44px] sur mobile, full-width
- Padding: px-4 (mobile) → px-6 (desktop)
- Cards: full-width sur mobile
- Modals: boutons empilés verticalement sur mobile
- Tabs: scroll horizontal sans scrollbar visible
- Animation drawer: slideInFromRight 0.2s ease-out
- CSS utilities: .scrollbar-none, .animate-in.slide-in-from-right

## Completed Features
- [x] All core features (Stripe, evidence, meetings, calendars, conflicts)
- [x] Product repositioning ("engagement solidaire")
- [x] Navigation globale (AppNavbar + AppBreadcrumb)
- [x] SettingsPageLayout harmonization
- [x] Impact page aligned with Landing DA
- [x] Email design system: 9 templates refactored
- [x] URL fix: nlyt.io → app.nlyt.io (6 links, 3 files)
- [x] Email logo: subtitle hors du `<a>` (fix Outlook blue override)
- [x] P0 Mobile responsive: AppNavbar hamburger, AppBreadcrumb compact, SettingsPageLayout responsive, Dashboard CTAs, Landing/Impact nav

## P1 — Next Up
- [ ] Dashboard cards P1 improvements (status lisibilité, actions rapides)
- [ ] AppointmentDetail mobile responsive
- [ ] AppointmentWizard mobile responsive
- [ ] Participants page mobile responsive
- [ ] Settings sub-pages CTA refinements
- [ ] Refactorer InvitationPage.js (1400+ lignes)
- [ ] Test réel Teams (compte non-pro)

## P3 — Backlog
- [ ] Charity Payouts V2 (Stripe Transfers)
- [ ] Webhooks temps réel Zoom/Teams
- [ ] Pages charité & Leaderboard
