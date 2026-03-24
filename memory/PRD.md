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

## Roadmap

### P1
- Pagination endpoints de liste (API + UI)
- Auto-update calendrier V2 (retry automatique)
- Découpe InvitationPage.js (1409 lignes)

### P2
- Apple Calendar (export ICS)

### P3
- Dashboard analytics organisateurs
- Payout charité vers associations
- Templates email externalisés (HTML)
- Pages dédiées par association + leaderboard
- Index MongoDB (performance)
- Webhooks temps réel Zoom/Teams
