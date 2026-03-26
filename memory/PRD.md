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

## Completed — Public Pages Mobile UX (Mars 2026)
- [x] Homepage (LandingPage.js) : Hero compact, réordonnancement sections, preuve sociale en validation finale (avant CTA), nav CTA masqué mobile
- [x] Impact (ImpactPage.js) : Hero compact + CTA above fold, Comment ça fonctionne remonté, 344€ proéminent, KPIs compacts (3 cols), Associations 3 max + toggle, Historique 3 max + toggle, CTA doublon supprimé, Transparence compacte
- [x] Vérifié : 0 overflow horizontal (375px), desktop (1280px) intact, aucun texte/wording modifié sur les 2 pages

## Completed — AppointmentDetail Refactoring (Mars 2026)
- [x] Décomposition de AppointmentDetail.js (1633 lignes → 8 fichiers, orchestrateur ~280 lignes)
- [x] Layout mobile-first: 3.9 écrans → 1.3 écrans (−67%), 0 overflow, CTA dynamique, grid asymétrique, signal confiance, signal social, preuves repliées
- [x] Ordre validé utilisateur: Header+CTA → Essentials → Actions immédiates (calendrier+annuler visible) → Engagement financier → Participants → Checkin #6 → Preuves (replié) → Modifications (replié)
- [x] 9 sous-composants: AppointmentHeader, AppointmentEssentials, EngagementSummary, FinancialBreakdown, ParticipantsSection, SecondaryActions, OrganizerCheckinBlock, CancelModal, + existants

## Completed — Default Workspace (Mars 2026)
- [x] Backend: champ `default_workspace_id` dans user settings, validation ownership, endpoint PUT /api/user-settings/me
- [x] Frontend: WorkspaceContext utilise default > localStorage > premier workspace, auto-set si unique, badge "Par défaut" + bouton "Défaut" dans WorkspaceSettings
- [x] Testé: API backend OK, badge affiché, auto-set single workspace

## Completed — Stripe Connect Fix (Mars 2026)
- [x] Diagnostic: clé Stripe système (`sk_test_emergent`) overridait le .env (vraie clé `sk_test_51TDBIh...`)
- [x] Fix: `load_dotenv(override=True)` dans server.py pour que .env prenne le dessus
- [x] Purge: 106 comptes fictifs (`acct_dev_*`/`acct_demo_*`) supprimés de la DB
- [x] Fix: `create_dashboard_link()` détecte maintenant `acct_dev_*` ET `acct_demo_*`
- [x] Testé: création compte Express réel, URL onboarding Stripe, redirect depuis le frontend
- [x] Stripe Connect Marketplace activé sur le dashboard Stripe par l'utilisateur

## Completed — Stripe Connect Multi-Profil (Mars 2026)
- [x] Sélecteur en 2 étapes : Step 1 (Particulier / Professionnel) → Step 2 inline (Indépendant / Société)
- [x] 3 profils NLYT : `particulier`, `independant`, `company` → mappés vers Stripe `individual` / `company`
- [x] Backend: pré-remplissage adapté par type (individual: first/last name, company: company name)
- [x] Backend: `POST /api/connect/reset` intelligent — mise à jour DB seule si même type Stripe, suppression Stripe si type différent
- [x] Frontend: badge profil NLYT dans ConnectStatusCard
- [x] Frontend: modal changement avec 3 options + avertissement Stripe conditionnel
- [x] Frontend: responsive mobile (cards empilées, sous-options inline)
- [x] Testé: 100% backend (18/18) + 100% frontend (sélecteur 2 étapes, badge, modal, mobile)

## Completed — InvitationPage Refactoring (Mars 2026)
- [x] Décomposition de InvitationPage.js (1419 lignes → 11 fichiers, orchestrateur ~576 lignes)
- [x] 10 sous-composants: InvitationStatusBadge, AppointmentUnavailableCard, InvitationCardHeader, GuaranteeRevalidationBanner, InvitationAppointmentDetails, ModificationProposalSection, EngagementRulesCard, InvitationResponseSection, InvitationCheckinSection, QRDisplayModal
- [x] 51 data-testid préservés, 0 régression, 100% tests passés (backend 7/7, frontend 100%)
- [x] Pattern identique à AppointmentDetail.js (orchestrateur + sous-composants props-driven)

## Completed — V2 Phase 1: Import Calendrier Externe (Mars 2026)
- [x] Adapters enrichis: Google + Outlook retournent location, attendees, organizer, conference_url, conference_provider, is_all_day
- [x] Collection `external_events` avec index (user+status+date, event_id+source unique, nlyt_appointment_id sparse)
- [x] Service `external_events_service.py`: import/dédup/upsert, cache 5min, détection events NLYT (sync_log + préfixe [NLYT])
- [x] 4 endpoints API: GET/PUT /import-settings, POST /sync, GET / (liste events)
- [x] Frontend: `CalendarSyncPanel` (toggle ON/OFF par provider, last_synced_at, event_count, refresh manuel)
- [x] Frontend: `ExternalEventCard` (badge Google/Outlook, date, durée, lieu, visio, participants)
- [x] Frontend: merge chronologique NLYT + events externes dans la timeline "À venir" du dashboard
- [x] Toggle stocké dans `calendar_connections` (pas dans users): champ `import_sync_enabled`, `import_last_synced_at`, `import_event_count`
- [x] Règle UX: panel masqué si aucun calendrier connecté, events masqués si toggle OFF
- [x] Déduplication 4 couches: sync_log, préfixe [NLYT], upsert unique, converted status
- [x] Testé: 100% backend (19/19), 100% frontend

## V2 Phase 2 — À implémenter
- [ ] Bouton "NLYT me" sur les cards d'événements importés
- [ ] Endpoint GET /api/external-events/{id}/prefill pour pré-remplir le wizard
- [ ] Enrichir AppointmentWizard avec support `?from_external=<id>` + pré-remplissage
- [ ] Conversion: créer appointment NLYT + mettre à jour external_events.status="converted"
- [ ] Badge "via Google/Outlook" sur les engagements NLYT convertis
- [ ] Protection: event converti ne réapparaît jamais comme importé

## V2 Phase 3 — Backlog
- [ ] Sync log "adopted" (calendar_sync_log avec sync_source="adopted")
- [ ] Anti-doublons complet: perform_auto_sync skip si sync_log adopted
- [ ] Cohérence auto-sync: perform_auto_update met à jour l'event calendrier existant

## Upcoming Tasks
- [ ] Test réel Teams (compte non-pro)
- [ ] Configurer le webhook Stripe en production

## Backlog
- [ ] Charity Payouts V2 (Stripe Transfers)
- [ ] Webhooks temps réel Zoom/Teams
- [ ] Pages charité & Leaderboard
