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

## V2 Phase 2 — Terminée (Mars 2026)
- [x] Endpoint GET /api/external-events/{id}/prefill — données pré-formatées pour le wizard
- [x] Champ from_external_event_id ajouté à AppointmentCreate (optionnel, rétrocompatible)
- [x] Conversion atomique: external_events.status "imported" → "converted" avec optimistic lock MongoDB
- [x] Anti-double-conversion: vérification explicite + condition atomique ($set where status=imported)
- [x] Bouton "NLYT me" sur ExternalEventCard avec prefetch-before-navigate (pas de redirection cassée)
- [x] AppointmentWizard: détection location.state.fromExternal, pré-remplissage formData + participants
- [x] Bandeau info: "Pré-rempli à partir de votre événement Google/Outlook. Tous les champs restent modifiables."
- [x] Badge "via Google/Outlook" sur EngagementCard quand converted_from.source existe
- [x] Champ converted_from stocké dans appointment doc pour traçabilité
- [x] Participants importés: split best-effort du displayName, tous les champs éditables
- [x] Testé: 100% backend (11/11), 100% frontend (iteration_83)

## V2 Phase 3 — Terminée (Mars 2026)
- [x] Sync log "adopted" créé lors de la conversion (sync_source="adopted", sync_status="synced")
- [x] perform_auto_sync SKIP si sync_log existe (pas de re-push doublon vers calendrier)
- [x] perform_auto_update utilise le sync_log adopted pour mettre à jour l'event calendrier existant
- [x] _fetch_external_events SKIP les events adoptés (via nlyt_external_ids)
- [x] Suppression d'un engagement NLYT converti: revert external_event à "imported" + suppression sync_log adopted
- [x] Anti-doublons 5 couches: sync_log, préfixe [NLYT], upsert unique, converted status, adopted sync_log
- [x] Testé: 100% backend (13/13), 100% frontend (iteration_84)

## Architecture NLYT Proof — Consolidation finale (Mars 2026)
- [x] Document de référence : `/app/backend/docs/NLYT_PROOF_ARCHITECTURE.md`
  - Positionnement clair : ce que NLYT Proof prouve (check-in temporel) et ne prouve pas (durée)
  - Hiérarchie des preuves : Niveau 1 (principales) / Niveau 2 (complémentaires) / Niveau 3 (métadonnées)
  - Structure de données gelée avec champs obligatoires/optionnels/dérivés
  - Règle produit : "Présence déclarée" vs "Présence confirmée" vs "Présence continue vérifiée"
  - Note d'architecture future : heartbeat + 1 confirmation intermédiaire (non implémenté)
- [x] Tests de non-régression : 51 tests (20 physique + 15 visio + 16 NLYT Proof temporel)
- [x] 7 invariants protégés + 5 fichiers sous protection
- [x] Limitation documentée : NLYT Proof ne mesure pas la durée sans provider externe

## Consolidation — Chaîne de Preuves de Présence (Mars 2026)
- [x] Documentation complète : `/app/backend/docs/EVIDENCE_CHAIN.md` (structure, mapping, invariants, fichiers)
- [x] Tests de non-régression : `/app/backend/tests/test_evidence_chain.py` (35 tests : 20 physique + 15 visio)
- [x] Garde-fous dans le code : commentaires ZONE PROTÉGÉE + INVARIANT dans les 4 fichiers critiques
- [x] Fichiers protégés : `checkin_routes.py`, `evidence_service.py`, `EvidenceDashboard.js`, `InvitationCheckinSection.js`
- [x] EvidenceDashboard unifié : supporte physique ET visio dans un seul composant
- [x] Visio : provider badge, outcome, rôle provider (host/attendee), join/leave, durée, identité match
- [x] Adaptateurs Zoom/Teams : capture du `provider_role` dans `derived_facts`
- [x] `checked_in` inclut `video_conference` comme preuve valide
- [x] Testé : 100% backend (35/35), 100% frontend (iteration_87)
- [x] Simulation NLYT Proof autonome : 8 cas validés (tous à l'heure, retard, absent, avance, partiel)
- [x] Limitation documentée : NLYT Proof ne capture pas la durée de présence (pas de check-out)

## Libellés Produit NLYT Proof — Vérification complète (Mars 2026)
- [x] 4 libellés implémentés dans `EvidenceDashboard.js` via `getPresenceLabel()`
- [x] "Absent" : 0 preuve → badge gris ✅
- [x] "Présence déclarée" : check-in NLYT seul → badge bleu ✅
- [x] "Présence confirmée" : GPS close / QR / vidéo → badge vert ✅
- [x] "Présence continue vérifiée" : vidéo + durée ≥80% → badge vert foncé ✅
- [x] Vérifié sur RDV physique (Igaal Hanouna: QR+GPS → Confirmée, Fresh Checkin → Absent)
- [x] Vérifié sur RDV visio (Alice: Zoom 56min/60min → Continue vérifiée, Charlie: check-in → Déclarée)
- [x] 51/51 tests backend passent (non-régression)

## Bug Fix — Evidence Dashboard (Mars 2026)
- [x] Bug: "Check-ins & Preuves" affichait "Aucune preuve" pour tous les participants malgré les preuves en base
- [x] Cause racine 1: `EvidenceDashboard.js` L43 — mauvais chemin de données (`evidenceData.evidence` au lieu de `evidenceData.participants[].evidence`)
- [x] Cause racine 2: `EvidenceDashboard.js` L55 — filtre `!p.is_organizer` excluait l'organisateur de l'affichage
- [x] Fix: `getParticipantEvidence` utilise `evidenceData.participants.find()` + filtre par statut accepté
- [x] Testé: 100% (iteration_86) — vérifié visuellement sur apt bb90f3e8 (Test Audit + Igaal Hanouna)
- [x] Chaque personne affiche: nom, email, source GPS, confiance, coordonnées, distance, heure, adresse

## Bug Fix — Check-in Participants P0 (Mars 2026)
- [x] Diagnostic: `InvitationCheckinSection.js` ligne 49 excluait `accepted_pending_guarantee` de `isEngaged`
- [x] Fix frontend: `isEngaged = ['accepted', 'accepted_guaranteed', 'accepted_pending_guarantee'].includes(effectiveStatus)`
- [x] Fix backend: `checkin_routes.py` ligne 256 — `checked_in` n'incluait pas le GPS. Corrigé: `has_checkin or has_qr or has_gps`
- [x] Cause racine: les participants avec garantie en attente voyaient "Accès verrouillé" au lieu des boutons de check-in
- [x] Traçabilité vérifiée: 3 preuves distinctes dans `evidence_items`, rapport organisateur correct, statut individuel correct
- [x] Testé: 100% backend (14/14), 100% frontend (iteration_85) + test traçabilité E2E
- [x] 4 scénarios simulés: 1) org+part OK, 2) org+multi OK, 3) non-auth OK, 4) invited bloqué OK

## Fix — Bouton crayon modification RDV (Mars 2026)
- [x] Audit complet du flow crayon → formulaire de modification
- [x] Cause racine : formulaire caché dans `<details>` replié en bas de page (régression refactor)
- [x] Fix : passage en modal Dialog (Shadcn) — ouverture immédiate au clic
- [x] Nouveau composant : `EditProposalModal.js`
- [x] `ModificationProposals.js` nettoyé (formulaire retiré, ne conserve que bannière active + historique)
- [x] `AppointmentDetail.js` : modal indépendant, `<details>` réservé à proposition active + historique
- [x] Testé : ouverture, fermeture (3 méthodes), pré-remplissage, overlay, pas de régression
- [x] Polish UX : auto-focus premier champ, loading bloque fermeture pendant soumission, fermeture auto + toast succès

## Auto-refresh calendriers synchronisés (Mars 2026)
- [x] Interval 2 minutes pour providers actifs (toggle ON)
- [x] Guard anti-doublon (`syncInProgressRef`)
- [x] Nettoyage propre des intervals (démontage, toggle OFF)
- [x] Appel `sync(force=false)` — respecte le cache backend TTL 5min
- [x] Indicateur "Dernière sync" en temps réel (ticker 30s dans CalendarSyncPanel)
- [x] Erreurs silencieuses, retry cycle suivant
- [x] Aucun flash/scroll — mise à jour discrète via setState
- [x] FIX: Dépendance useEffect sur booléen stable `hasAnyProviderEnabled` (useMemo) au lieu de l'objet `importSettings`
- [x] FIX: Suppression de `syncing` des dépendances (utilise `syncingRef` à la place)
- [x] FIX: Indicateur "Contrôle auto : il y a X s" dans CalendarSyncPanel (feedback visible indépendant du cache backend)
- [x] Vérifié factuellement : interval tire toutes les 10s (test), API appelée, indicateur mis à jour, puis restauré à 120s

## Inscription depuis invitation — Flow viral Phase 1 (Mars 2026)
- [x] Backend: `POST /api/invitations/:token/accept-with-account` — endpoint transactionnel (création compte + acceptation + Stripe en 1 appel)
- [x] Backend: `POST /api/invitations/:token/login-and-accept` — connexion + acceptation pour utilisateurs existants
- [x] Backend: `has_existing_account` ajouté à `GET /api/invitations/:token`
- [x] Backend: auto-vérification email bornée (invitation flow uniquement, token valide, email exact)
- [x] Frontend: `InvitationAccountChoice.js` — panneau intercalé AVANT Stripe redirect
- [x] Frontend: données pré-remplies (prénom, nom, email non éditables), 1 seul champ mot de passe
- [x] Frontend: CTA dominant "Créer mon espace et continuer" + lien secondaire "Continuer sans compte"
- [x] Frontend: variante "Connectez-vous pour accepter" si compte existant + lien "Mot de passe oublié"
- [x] Testé E2E: acceptation → panneau → mot de passe → compte créé (auto-vérifié) → redirect Stripe Checkout → DB cohérente

## Completed — Viral Loop Phase 2: Invitation Email Redesign (Fév 2026)
- [x] Email d'invitation redesigné en "mini landing page" (copywriting + hiérarchie)
- [x] Accroche personnalisée : "[Nom] vous propose un engagement"
- [x] Headline : "Le temps ne se perd plus"
- [x] Explication simplifiée mobile-first : ✔ Présent → rien débité / ✖ Absent → garantie utilisée → pour vous ou association
- [x] Phrase clé : "Dans tous les cas, votre temps a de la valeur."
- [x] CTA principal : "Voir l'invitation et répondre"
- [x] Variante non-inscrit : "Création de compte en 1 clic si vous acceptez"
- [x] Variante inscrit : "Vous avez déjà un espace NLYT — accédez à votre tableau de bord"
- [x] Preuve sociale : "Des milliers d'engagements déjà créés sur NLYT"
- [x] Paramètre `has_existing_account` ajouté à `send_invitation_email()` + 4 appelants mis à jour
- [x] Charte graphique existante strictement conservée (couleurs, boutons, typographies)
- [x] Vérifié : rendu desktop (700px) + mobile (375px), 0 overflow, lisible en 3 secondes

## Completed — Viral Loop Phase 3: Cartes de résultat partageables (Mars 2026)
- [x] 3 types de cartes virales : engagement_respected (vert), compensation_received (bleu), charity_donation (ambre)
- [x] Copywriting émotionnel v2 : "Engagement respecté. / Tout le monde était là.", "Vous avez récupéré X€. / Parce que votre temps compte.", "Votre temps perdu a aidé quelqu'un. / X€ reversés à [association]."
- [x] Brand line unifiée sur toutes les cartes : "Le temps ne se perd plus."
- [x] Compteur de vues retiré (priorité impact émotionnel)
- [x] Backend: POST /api/result-cards (auth, idempotent) + GET /api/result-cards/{id} (public, view_count) + GET /api/result-cards/my-cards
- [x] Frontend: composant ResultCard + ResultCardActions (Partager + Copier le lien)
- [x] Page publique /card/:cardId — accessible sans auth, CTA "Découvrir NLYT"
- [x] Intégration dans AppointmentDetail (ResultCardSection) — visible après évaluation de présence
- [x] Mobile-first, minimaliste, cohérent charte existante (#0A0A0B header, accent strip, rounded cards)
- [x] Testé: 100% backend (14/14), 100% frontend (iteration_88)

## Completed — Viral Loop Phase 4: Emails post-engagement viraux (Mars 2026)
- [x] 3 variantes d'email post-engagement : "Engagement respecté", "Vous avez récupéré X€", "Votre temps a aidé quelqu'un"
- [x] Carte de résultat intégrée visuellement dans chaque email (HTML inline, accent colors)
- [x] CTA principal : "Créer un engagement" (conversion participant → organisateur)
- [x] CTA secondaire : "Partager mon résultat" (lien vers /card/:cardId public)
- [x] Auto-création idempotente des result_cards en DB lors de l'envoi
- [x] Hooké dans evaluate_appointment() (non-bloquant, fire-and-forget)
- [x] Idempotence via sent_emails collection (email_type: post_engagement_{card_type})
- [x] Testé: 100% backend (23/23), 100% frontend (iteration_89)

## Completed — Viral Loop Phase 5: Bannière connexion InvitationPage (Mars 2026)
- [x] Bannière bleue "Vous avez déjà un compte NLYT — connectez-vous pour accepter plus vite"
- [x] Visible uniquement quand has_existing_account=true ET status=invited
- [x] Lien direct /signin?redirect=/invitation/{token}
- [x] Testé: 100% backend + frontend (iteration_90)

## Completed — Viral Loop Phase 6: Milestones wallet + CTA Organiser (Mars 2026)
- [x] Endpoint GET /api/wallet/milestones (attended_count, milestones 1/3/5/10/25/50/100, next_milestone, show_organizer_cta)
- [x] Composant MilestonesSection dans WalletPage (compteur, barre de progression, badges, CTA)
- [x] CTA "Organiser un engagement" affiché quand organized_count=0 ET attended_count>=1
- [x] Testé: 100% backend + frontend (iteration_90)

## Completed — Fix critique: Auto-save carte Stripe sur profil utilisateur (Mars 2026)
- [x] AUDIT: carte saisie via invitation checkout n'était PAS propagée au profil users (double saisie requise)
- [x] FIX webhook: propagation automatique du payment_method vers users.default_payment_method_id après checkout réussi
- [x] FIX dev mode: même propagation dans get_guarantee_status (polling path)
- [x] Condition: ne PAS écraser une carte existante ($exists + $ne: None)
- [x] Bug MongoDB résolu: projection vide retournant {} (falsy) causait skip silencieux
- [x] Testé: scénario A (new user → carte auto-sauvée ✅), scénario B (existing user → carte non écrasée ✅)
- [x] Vérifié: GET /api/user-settings/me/payment-method retourne has_payment_method=true après flow

## Completed — Fix critique: Réutilisation carte existante lors d'acceptation (Mars 2026)
- [x] AUDIT: le backend créait TOUJOURS une session Stripe Checkout, même si l'utilisateur avait une carte enregistrée
- [x] Nouvelle méthode create_guarantee_with_saved_card() — crée la garantie directement sans Stripe redirect
- [x] 3 endpoints modifiés: respond_to_invitation, login_and_accept, accept-with-account (check saved card avant Checkout)
- [x] Frontend gère le retour reused_card=true (message de confirmation, pas de redirect)
- [x] Testé: 100% backend (iteration_92), flow E2E vérifié via curl

## Completed — Vue participant alignée sur vue organisateur (Fév 2026)
- [x] Résumé décisionnel en haut de page : montant garantie, tolérance retard, délai annulation (visible en 1 seconde)
- [x] Trust signal : "X participant(s) a/ont déjà confirmé son/leur engagement" (affiché uniquement si confirmed_count > 0)
- [x] Lien meeting en bloc d'action clé : "Rejoindre la réunion →" (visible uniquement pour participants avec engagement finalisé)
- [x] Adresse complète (location_display_name) au lieu de l'adresse courte
- [x] Répartition financière : bloc dédié (compensation %, commission %, charité %)
- [x] Sécurité préservée : meeting_join_url masqué pour participants non-finalisés
- [x] Composants réutilisés : EngagementSummary + FinancialBreakdown de la vue organisateur
- [x] Backend enrichi : endpoint invitation retourne confirmed_count, total_participants, et tous les champs financiers dans l'objet appointment
- [x] Testé : 100% backend (17 tests) + frontend (11 tests) — iteration_95

## Completed — Dashboard unifié : timeline organisateur + participant (Fév 2026)
- [x] Nouvel endpoint `GET /api/appointments/my-timeline` : fusionne engagements organisateur + invitations participant en 3 buckets (`action_required`, `upcoming`, `past`)
- [x] Structure stable par item : `role`, `status`, `action_required`, `starts_at`, `sort_date`, `counterparty_name`, `is_user_organizer`, `is_user_participant`, `actions`, `pending_label`
- [x] Wording différencié : organisateur → "En attente de réponse (N)" / participant → "Votre réponse est attendue"
- [x] Labels rôle : "Créé par vous" / "Invitation de [Nom]" visibles immédiatement
- [x] CTAs contextuels : Accepter/Refuser (participant), Relancer (organisateur), Voir détails
- [x] Section "Action requise" en haut du dashboard avec priorité maximale
- [x] Déduplication : si user est à la fois organisateur et participant, affiché une seule fois (en tant qu'organisateur)
- [x] Composants existants conservés : Impact card, Calendar sync, Workspace switcher, Stats
- [x] Charte graphique strictement conservée (couleurs, badges, composants)
- [x] FIX: "Action requise" contient UNIQUEMENT invitations participant non traitées (0 items organisateur)
- [x] UX: Cartes enrichies avec adresse, garantie, tolérance retard, conditions d'annulation en grille verticale aérée
- [x] Testé : 100% backend + frontend (iteration_93 + iteration_94)

## Completed — Validation Stripe réelle pour réutilisation de carte (Fév 2026)
- [x] BUG CRITIQUE CORRIGÉ: `SetupIntent.create()` manquait `payment_method_types=["card"]` → la validation silencieuse échouait systématiquement en production
- [x] BUG MINEUR CORRIGÉ: flag `dev_mode` incorrectement calculé quand `pm_dev_*` utilisé avec une vraie clé Stripe
- [x] SetupIntent Stripe RÉEL créé et confirmé (usage=off_session) pour chaque réutilisation de carte
- [x] Gestion SCA/3DS: si authentification requise → fallback Checkout standard (pas de blocage UX)
- [x] Gestion carte expirée/détachée/invalide: refus propre → fallback Checkout
- [x] Gestion PM inexistant: refus propre → fallback Checkout
- [x] Cohérence DB: aucun double état possible après fallback
- [x] Capture future prouvée: PaymentIntent off_session réussit sur carte validée par SetupIntent
- [x] Dev mode préservé: pm_dev_* skip validation Stripe correctement
- [x] Testé: 9/9 scénarios Stripe réels passés (test_stripe_card_reuse.py)

## Upcoming Tasks
- [ ] P2: Test réel Teams (compte non-pro)
- [ ] P2: Configurer le webhook Stripe en production

## Backlog
- [ ] Charity Payouts V2 (Stripe Transfers)
- [ ] Webhooks temps réel Zoom/Teams
- [ ] Pages charité & Leaderboard
