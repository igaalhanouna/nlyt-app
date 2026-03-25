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

## Email Design System (Mars 2026)
- Base template: `_base_template()` in email_service.py
- Header: #0A0A0B dark with N·L·Y·T typographic logo
- Accent bars: info (blue), success (green), warning (amber), danger (red), neutral (slate)
- Buttons: `_btn()` dark bg, `_btn_secondary()` outline
- Helpers: `_greeting()`, `_paragraph()`, `_section_title()`, `_info_box()`, `_alert_box()`, `_detail_row()`, `_small()`, `_fallback_link()`
- Footer: "© 2026 N·L·Y·T — Never Lose Your Time"
- 9 emails refactored: verification, password_reset, invitation, acceptance, checkin, participant_cancellation, appointment_cancelled, appointment_deleted, guarantee_revalidation

## Navigation
- AppNavbar: persistent top bar, logo clickable
- AppBreadcrumb: contextual breadcrumb
- SettingsPageLayout: standardized settings pages

## Completed Features
- [x] All core features (Stripe, evidence, meetings, calendars, conflicts)
- [x] Product repositioning ("engagement solidaire")
- [x] Navigation globale (AppNavbar + AppBreadcrumb)
- [x] SettingsPageLayout harmonization
- [x] Impact page aligned with Landing DA
- [x] Email design system: 9 templates refactored

## P1 — Next Up
- [ ] Refactorer InvitationPage.js (1400+ lignes)
- [ ] Test réel Teams (compte non-pro)

## P3 — Backlog
- [ ] Charity Payouts V2 (Stripe Transfers)
- [ ] Webhooks temps réel Zoom/Teams
- [ ] Pages charité & Leaderboard
