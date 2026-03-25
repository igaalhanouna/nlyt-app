# NLYT — Product Requirements Document

## Vision
SaaS de gestion d'assiduité avec garanties financières. Repositionné en "engagements solidaires" avec un framing premium.

## Technical Stack
Frontend: React + TailwindCSS + Shadcn/UI
Backend: FastAPI + Python + MongoDB + slowapi
Email: Resend | Payments: Stripe | Video: Zoom/Teams/Meet API

## Branding
- Logo typographique: N·L·Y·T + "Never Lose Your Time" (toujours visible, jamais masqué)
- Site: dark theme (#0A0A0B) public, light theme dashboard
- Wording: "Engagement solidaire", "Geste solidaire", "Temps valorisé"
- SITE_URL: https://app.nlyt.io (all outbound links)
- RÈGLE: Le wording ne doit JAMAIS être modifié pour le mobile. Le mobile affiche exactement le même texte que le desktop.

## Email Design System (Mars 2026)
- Base template: `_base_template()` in email_service.py
- Header: #0A0A0B dark with N·L·Y·T typographic logo (subtitle OUTSIDE `<a>` tag)
- Subtitle color: #64748B (matches landing page text-slate-500)
- All links point to SITE_URL = https://app.nlyt.io
- 9 emails refactored via shared template

## Mobile Design System (Mars 2026)
### Principes
- Mobile-first, même contenu que desktop (aucune modification wording)
- Breakpoint principal: md (768px) = desktop/mobile switch
- Boutons CTA: min-h-[44px] sur mobile, full-width
- Padding: px-4 (mobile) → px-6 (desktop), p-4 → p-6 pour les cards
- Zéro overflow horizontal sur toutes les pages

### Navigation
- AppNavbar: hamburger icon → slide drawer (right), backdrop blur, liens complets
- AppBreadcrumb: scroll horizontal caché, texte complet (pas de shortLabel)
- Landing/Impact nav: flex-wrap, CTA full-width en dessous sur mobile

### Composants
- Cards: full-width, p-4 md:p-6
- Modals: boutons empilés verticalement (flex-col-reverse sm:flex-row)
- Tabs: scroll horizontal + gradient fade indicator (md:hidden)
- Stepper wizard: compact, overflow-x-auto, text-[11px] labels
- Participant rows: flex-col sm:flex-row, name+badge wrapping
- Inputs: h-11 sm:h-9 dans les formulaires
- Delete buttons: toujours visibles (pas opacity-0 group-hover)

## Completed Features
- [x] All core features (Stripe, evidence, meetings, calendars, conflicts)
- [x] Product repositioning ("engagement solidaire")
- [x] Navigation globale (AppNavbar + AppBreadcrumb)
- [x] SettingsPageLayout harmonization
- [x] Impact page aligned with Landing DA
- [x] Email design system: 9 templates refactored
- [x] URL fix: nlyt.io → app.nlyt.io (6 links, 3 files)
- [x] Email logo: subtitle hors du `<a>` (fix Outlook blue override)
- [x] P0 Mobile: AppNavbar hamburger, AppBreadcrumb compact, SettingsPageLayout responsive, Dashboard CTAs, Landing/Impact nav
- [x] P1 Mobile: Dashboard tabs scroll+fade, AppointmentDetail layout, AppointmentWizard stepper+nav+inputs, ParticipantManagement, Settings sub-pages padding+buttons

## Completed — Homepage Mobile UX (Mars 2026)
- [x] Restructuration mobile LandingPage.js : Hero compact (CTA visible above fold), réordonnancement sections, preuve sociale remontée, espacement réduit, nav CTA masqué mobile
- [x] Vérifié : 0 overflow horizontal (375px), desktop (1280px) intact, aucun texte/wording modifié

## Upcoming Tasks
- [ ] Refactorer InvitationPage.js (1400+ lignes → modules)
- [ ] Test réel Teams (compte non-pro)

## Backlog
- [ ] Charity Payouts V2 (Stripe Transfers)
- [ ] Webhooks temps réel Zoom/Teams
- [ ] Pages charité & Leaderboard
