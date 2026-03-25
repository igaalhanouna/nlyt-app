# NLYT — Product Requirements Document

## Vision
SaaS de gestion d'assiduité avec garanties financières. NLYT vérifie la présence des participants via des preuves indépendantes.

## Technical Stack
Frontend: React + TailwindCSS + Shadcn/UI
Backend: FastAPI + Python + MongoDB + slowapi
Email: Resend | Payments: Stripe | Video: Zoom/Teams/Meet API

## Testing
- iteration_59: 25/25 (Financial Email Notifications)
- iteration_60: 27/27 (Workspace inline edit)
- iteration_61: 23/23 (Dashboard UX overhaul)
- iteration_62: 20/20 (Conflict Detection V1)
- iteration_63: 29/29 (Conflict Detection V2 — Calendar Integration)
- QA Manuel V2: 8/8 scénarios E2E validés

## Fix Outlook comptes personnels (Mars 2026)
- Corrigé MICROSOFT_CLIENT_ID (valeur UUID réelle au lieu de placeholder)
- Architecture à 2 niveaux OAuth Microsoft :
  - **Niveau 1 (Calendar base)** : `Calendars.ReadWrite User.Read offline_access` — universel pro+perso
  - **Niveau 2 (Teams avancé)** : ajoute `OnlineMeetings.ReadWrite OnlineMeetingArtifact.Read.All` — pro seulement
- Endpoint `/api/calendar/connect/outlook` → scopes de base
- Endpoint `/api/calendar/connect/outlook/teams-upgrade` → scopes Teams (nécessite connexion Outlook préalable)
- Callback OAuth écrit `has_online_meetings_scope` et `scope_level` basés sur scopes réellement consentis
- `meeting_provider_service.py` NON modifié — le mode délégué lit `has_online_meetings_scope` depuis la BDD
- Frontend : 2 banners (Calendar actif + Teams upgrade/actif) + toast pour upgrade Teams
- Tests: iteration_64 — 9/9 backend + 8/8 frontend + 18/18 régression

## Sélection Video Provider — Option A enrichie (Mars 2026)
- 4 providers visibles : Teams, Meet, Zoom, Autre plateforme
- Teams binaire : `can_auto_generate` UNIQUEMENT si `has_online_meetings_scope=true` (M365 pro + Teams avancé)
- Pré-sélection automatique : Teams > Meet > Zoom > External (une seule fois au chargement)
- Backend validation : rejet 400 si provider non disponible pour l'utilisateur
- "Lien externe" renommé "Autre plateforme"
- Tests: iteration_65 — 12/12 backend + 10/10 frontend

## QA Manuel — Conflict Detection V2 (Mars 2026)

### Scénarios testés
| # | Scénario | Résultat | Détail |
|---|----------|----------|--------|
| 1 | Conflit NLYT seul | ✅ | 1 conflit source=nlyt, confidence high |
| 2 | Google Calendar interrogé | ✅ | Google dans sources_checked, 0 event externe trouvé (calendrier vide sur cette fenêtre) |
| 3 | Outlook indisponible | ✅ | Fallback gracieux, pas de crash, Outlook absent de sources_checked |
| 4 | Déduplication NLYT↔Google | ✅ | RDV synchro Google, 1 seul conflit (pas de doublon) |
| 5 | Warning buffer < 30 min | ✅ | Créneau 15h00 → warning "Enchaînement serré" |
| 6 | Fallback partiel (Outlook connecté mais token mort) | ✅ | confidence=medium, detail="Source(s) indisponible(s) : Outlook" |
| 7 | Suggestions valides + futures | ✅ | 5 suggestions optimal, toutes > now |
| 8 | Affichage source + clic suggestion → revalidation | ✅ | Badge NLYT visible, clic → date mise à jour → "Créneau disponible" |

### Bugs résiduels
Aucun.

### Points UX améliorés (Polish)
- Badge source avec icône + bordure (plus visible)
- Titre conflit en 13px bold
- Wording amélioré ("Enchaînement serré", "Ce créneau chevauche...")
- Clic suggestion → clear + loading immédiat → revalidation
- Cards avec shadow-sm et rounded-lg
- Suggestions avec hover shadow + meilleur padding

## Completed — Stripe Connect (All Phases)
- Phase 1-4: Wallet, Connect, Distribution, Payouts ✅
- Phase 5: Notifications email financières ✅

## Completed — UX Cleanup (Mars 2026)
- [x] Suppression /policies et /analytics (placeholders vides)
- [x] Refonte bloc Connect → "Compte bancaire"
- [x] Bug fix: lien "Modifier mon compte bancaire" inerte en dev mode
- [x] Édition inline workspace (crayon, Enter/Escape, PUT API)
- [x] Dashboard UX overhaul (interface de décision, impact, risk badges)
- [x] Dashboard orienté Impact (bloc "Votre impact" au lieu de € sécurisé/à risque)
- [x] Titre wizard: "Créer un rendez-vous avec engagement"
- [x] Suppression sélecteur Rôle dans wizard participants
- [x] UX participants compacte (badge numéroté + 3 inputs en ligne)
- [x] **Smart Conflict Detection V1** :
  - Backend: `POST /api/appointments/check-conflicts` (conflit/warning/available + suggestions)
  - Règles: overlap = conflict, <30min buffer = warning
  - Suggestions: 3-5 créneaux (optimal/comfortable/tight)
  - Frontend: panneau alerte dans Step 2, chips cliquables, "Trouver le meilleur créneau"
  - Tests: 20/20 (iteration_62)
- [x] **Conflict Detection V2 — Intégration Calendriers** (Mars 2026) :
  - GoogleCalendarAdapter.list_events + OutlookCalendarAdapter.list_events
  - Fenêtre intelligente: candidate ± BUFFER_MINUTES (pas de fenêtre fixe)
  - Déduplication: events NLYT synchronisés filtrés via calendar_sync_logs.external_event_id
  - Confidence rigoureuse: high = toutes sources OK, medium = source indisponible ou aucun calendrier
  - Performance: un seul fetch sur la fenêtre, calcul local ensuite
  - UX: badges source (NLYT/Google/Outlook) sur chaque conflit/warning
  - confidence_detail + sources_checked dans la réponse API
  - Suppression du "V2 teaser" → indicateur "Calendriers connectés actifs"
  - Tests: 29/29 (iteration_63)

## Fix Timezone Outlook/Google — Audit systémique (Fév 2026)

### Cause racine identifiée
`_build_event_data()` dans `calendar_routes.py` passait les datetime UTC en chaîne naive (sans suffix `Z`) 
associée à un timezone non-UTC (ex: `Europe/Paris` ou `Romance Standard Time`).  
Les APIs calendrier (Google/Outlook) interprétaient la valeur comme heure locale → **décalage de 1h (CET) ou 2h (CEST)**.

### Corrections appliquées
1. **`calendar_routes.py` → `_build_event_data()`** : toujours `timeZone: "UTC"`. Les datetime sont déjà en UTC,
   maintenant correctement étiquetées. Les apps calendrier convertissent automatiquement en timezone d'affichage.
2. **`outlook_calendar_adapter.py` → `list_events()`** : ajout header `Prefer: outlook.timezone="UTC"` 
   pour forcer Graph API à retourner toutes les datetime en UTC (lecture d'événements pour conflit detection).

### Composants audités (pas de bug)
- Frontend `dateFormat.js` : `localInputToUTC()` correct (JavaScript `toISOString()` = UTC) ✅
- Frontend `AppointmentWizard.js` : envoi `start_datetime` en UTC + `appointment_timezone` ✅
- Backend `date_utils.py` : `normalize_to_utc()` correct (Z passthrough, offset conversion) ✅
- Backend `appointments.py` : stockage UTC en MongoDB ✅
- `ics_generator.py` : DTSTART/DTEND avec suffix Z (RFC 5545 conforme) ✅

### Tests
- 13/13 tests timezone (winter/summer, E2E flow, ICS, mapping Windows TZ)
- 18/18 tests conflit detection (régression OK)
- 11/11 tests ICS (régression OK)

## Auto-Sync Multi-Provider (Mars 2026)
- **Avant** : auto-sync vers UN seul provider (choix exclusif Google OU Outlook)
- **Après** : auto-sync vers TOUS les calendriers connectés simultanément
- Backend `perform_auto_sync` : itère sur toutes les `calendar_connections` actives
- Backend settings : simplifié à un toggle `auto_sync_enabled` (plus de `auto_sync_provider`)
- API `GET/PUT /api/calendar/auto-sync/settings` : retourne `connected_providers[]` en plus
- Frontend : sélecteur exclusif remplacé par toggle ON/OFF + badges des calendriers connectés
- `perform_auto_update` : déjà multi-provider (met à jour tous les sync_logs existants) — inchangé
- Tests : 74/74 régression OK

## Auto-update Calendar V2 — Retry automatique (Mars 2026)
- **Service** : `services/calendar_retry_service.py`
- **Backoff exponentiel** : 2min → 5min → 15min → 60min (max 4 tentatives)
- **Statuts sync_log** : `synced` → (échec) → `retry_pending` → `synced` ou `permanently_failed`
- **Scheduler** : job toutes les 2 minutes (`calendar_retry_job`) scanne les `retry_pending` dont `next_retry_at` est passé
- **perform_auto_sync** (création) : en cas d'échec, programme le premier retry au lieu de rester `failed`
- **perform_auto_update** (mise à jour) : en cas d'échec, programme un retry au lieu de marquer `out_of_sync`
- **Endpoint sync status** : enrichi avec `retry_pending`, `retry_count`, `max_retries_reached`
- **Sync manuelle** : détecte les logs `retry_pending`/`permanently_failed` pour re-sync
- **Sécurités** : skip les RDV annulés/supprimés, skip les connexions déconnectées (mais retry quand même)
- Tests : 12/12 (backoff, schedule_retry, job, intégration) + 86/86 régression OK

## Export ICS pour Apple Calendar (Mars 2026)
- **Endpoint** : `GET /api/calendar/export/ics/{appointment_id}` — existait, enrichi avec `SEQUENCE` dynamique et `METHOD:CANCEL`
- **ICS Generator** : supporte maintenant `sequence` (incrémenté à chaque modification) et `method` (`PUBLISH`/`CANCEL`)
- **`modification_service.py`** : incrémente `update_count` à chaque modification → Apple Calendar met à jour via le même `UID`
- **AppointmentDetail.js** : bouton "Ajouter à Apple Calendar" avec tooltip explicatif
- **InvitationPage.js** : bouton "Ajouter à Apple Calendar" + sous-texte compatibilité
- **Integrations.js** : section "Apple Calendar & autres" avec explication de l'export manuel
- **Wording** : conforme au cadrage utilisateur — pas de "synchronisation", export manuel assumé
- Tests : 86/86 régression OK

## Pagination "Voir plus" (Mars 2026)
- **Backend** : `GET /api/appointments/` supporte `skip`, `limit`, `time_filter` (upcoming|past|all)
- **Réponse** : `{items, total, skip, limit, has_more}`
- **Frontend** : deux appels parallèles (upcoming + past) au chargement, "Voir plus" indépendant par section
- **Terminologie** : "engagements" (pas "rendez-vous")
- **UX** : bouton discret, compteur "X sur N engagements", pas de scroll reset, loader léger
- Tests : 15/15 backend + 9/9 frontend (testing agent iteration_66)

## Indexation MongoDB (Mars 2026)
- 20+ index créés sur les collections critiques : appointments, participants, calendar_sync_logs, users, wallets, payment_guarantees, etc.
- Index composites pour les requêtes fréquentes (workspace_id+status, sync_status+next_retry_at)
- Index unique sur les IDs métier (appointment_id, participant_id, etc.)
- Fonction `ensure_indexes()` dans `database.py`, appelée au démarrage (idempotente)
- L'ancien index email idempotency migré depuis server.py vers database.py

## Dashboard Analytics Organisateur V1 (Mars 2026)
- Nouvel onglet "Statistiques" dans le dashboard existant
- 6 KPI cards : Engagements créés, Taux de présence, Taux d'acceptation, Dédommagement personnel, Impact caritatif, Engagements non honorés
- Message global contextuel basé sur le taux de présence (positif/neutre/attention)
- Endpoint `GET /api/appointments/analytics/stats` — all-time, pas de filtre temporel
- Tests : 13/13 backend + 13/13 frontend (testing agent iteration_67)

## Impact Caritatif V1 (Mars 2026)
- **Page publique** `/impact` entièrement refondue : focus transparence charité
- **Wording strict** : "montants fléchés", "réservés pour des associations", jamais "reversé" ou "donné"
- **Bloc de transparence** : explique que les montants sont accumulés, reversement automatique = fonctionnalité future
- **Backend** : nouveau `GET /api/impact/charity` — endpoint public, paginé, avec historique des contributions
  - Retourne `payout_status: "accumulating"`, `payout_message` avec wording validé
  - Contributions individuelles avec enrichissement (titre engagement, nom association)
  - Pagination `skip`/`limit` avec `has_more`
- **Frontend** : KPIs (fléchés, associations, engagements, total redistribué), liste associations, historique contributions, "Comment ça fonctionne"
- **Cohérence dashboard** : ImpactCard → "fléchés pour des associations", KPI analytics → "Fléchés pour des associations"
- **Fix noms associations** : `refresh_impact_stats()` utilise le fallback sur la liste statique `VALIDATED_ASSOCIATIONS`
- Tests : 21/21 backend + 7/7 frontend (testing agent iteration_68)

## Dataset de Démonstration (Mars 2026)
- **Script** : `/app/backend/scripts/seed_demo.py` — idempotent (clean + insert)
- **Marqueur** : `_seed_demo: true` sur tous les documents pour nettoyage ciblé
- **Mot de passe commun** : `Demo2026!`
- **23 utilisateurs** : profiles variés (coach, freelance, RH, CTO, notaire, startup...)
- **34 connexions calendrier** : Google (17), Outlook (17), dont 5 avec Teams avancé
- **45 rendez-vous** : 15 futurs actifs, 15 passés évalués, 5 annulés, 3 pending, 2 buffer warning, 5 premium
- **Providers** : Teams (8), Meet (6), Zoom (12), externe (7), physique (12)
- **101 participants** : guaranteed (45), pending (25), invited (19), cancelled (12)
- **Présence** : on_time (12), late (7), no_show (4)
- **4 distributions** avec 3 associations caritatives → 52€ fléchés
- **24 wallets** + 12 transactions
- **3 utilisateurs premium** :
  - `clara.deschamps@demo-nlyt.fr` — 2 RDV en conflit (28 mars 14h00/14h15, Teams vs Meet)
  - `victor.fontaine@demo-nlyt.fr` — créneau optimal entre 10h et 14h
  - `aurelie.marchand@demo-nlyt.fr` — pénalité appliquée (100€, MSF)

## Fix Teams Configuration Flow (Mars 2026)
- **Bug A** : `provider-status` retourne maintenant `configured`, `features`, `connection_mode` pour Teams
- **Bug B** : `is_configured()` validé avec format UUID (rejette `datetime-debug`, `common`, etc.)
- **Bug C** : UX non bloquante — sauvegarde possible sans credentials serveur, warning informatif
- **Bug D** : Note explicative recommandant le mode délégué (Outlook Teams avancé)
- **3 modes Teams** : délégué (Outlook scope), application (Azure AD form), non connecté
- Tests : 20/20 backend + 10/10 frontend (testing agent iteration_69)

## Alignement Teams / Google Meet (Mars 2026)
- **Nouveau mode "calendar"** : création Teams via `isOnlineMeeting: true` sur événement calendrier — fonctionne pour comptes perso + pro
- **Chaîne de fallback** : Calendar → Delegated OnlineMeetings → Application (Azure AD legacy)
- **`provider-status` enrichi** : champ `level` (advanced/standard/application/null), `has_attendance` (pro only)
- **`can_auto_generate: true`** dès qu'Outlook est connecté (même sans scope OnlineMeetings)
- **Wording prudent** : "Microsoft Teams disponible via votre compte Outlook" (standard), affirmatif seulement pour advanced (validé en prod)
- **UX simplifiée** : formulaire Azure AD masqué derrière "Configuration avancée", message Outlook en priorité
- Tests : 25/25 backend + 13/13 frontend (testing agent iteration_70)

## Fix UX Teams non-pro accounts (Mars 2026)
- **Bug** : L'encart Teams s'affichait en vert "actif" pour les comptes non-pro (standard) dans les Intégrations ET le wizard de création de RDV
- **Fix Wizard** : `AppointmentWizard.js` — condition Teams changée de `p?.can_auto_generate` à `p?.level === 'advanced'`
  - Auto-sélection : Teams n'est auto-sélectionné que pour `level === 'advanced'`
  - Message adapté pour `standard` : "Réservé aux comptes Microsoft 365 Pro. Activez Teams avancé dans Paramètres > Intégrations."
  - Confirmation auto-création : même logique `level === 'advanced'` pour Teams
- **Fix Intégrations** : `Integrations.js` — carte Teams note utilise `teamsLevel === 'advanced'` pour l'état vert (déjà corrigé par l'agent précédent)
- **Résultat** :
  - `advanced` → Teams vert, sélectionnable, badge "Automatique"
  - `standard` → Teams grisé, non-sélectionnable, message informatif
  - `null` → Teams grisé, message "Connectez Outlook"
- Tests : 17/17 frontend (testing agent iteration_71)

## Roadmap

### P1
- Découpe InvitationPage.js (1409 lignes)

### P2
- Templates email externalisés (HTML)

### P3
- Charity Payouts V2 — Implémentation des Stripe Transfers réels
- Pages dédiées par association + leaderboard
- Webhooks temps réel Zoom/Teams
