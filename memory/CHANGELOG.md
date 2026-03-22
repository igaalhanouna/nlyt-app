# NLYT - Changelog

## 2026-03-22 — Feature: appointment_timezone explicite

### Changement
- Nouveau champ `appointment_timezone` (IANA) stocké sur chaque RDV
- Frontend envoie `Intl.DateTimeFormat().resolvedOptions().timeZone` à la création (wizard + quick-create)
- Backend stocke le champ, fallback `'Europe/Paris'` si absent (backward compat)
- `format_email_datetime(dt_string, tz_name)` accepte maintenant une timezone explicite
- Tous les emails (invitation, confirmation, annulation, suppression, rappels, modifications) propagent la timezone du RDV

### Fichiers modifiés
- `/app/backend/models/schemas.py` — `appointment_timezone: Optional[str]` dans `AppointmentCreate`
- `/app/backend/routers/appointments.py` — stockage + propagation emails
- `/app/backend/routers/invitations.py` — propagation emails
- `/app/backend/routers/modification_routes.py` — `_build_changes_html` + emails
- `/app/backend/services/email_service.py` — `format_email_datetime(dt, tz_name)` + 5 méthodes
- `/app/backend/services/reminder_service.py` — propagation
- `/app/backend/services/event_reminder_service.py` — propagation
- `/app/frontend/src/pages/appointments/AppointmentWizard.js` — envoi timezone

### Tests
- Timezone stockée en DB (America/New_York) ✓
- format_email_datetime: Paris 14:00, NY 08:00, Tokyo 21:00 pour le même UTC ✓
- Legacy RDV sans timezone → fallback Europe/Paris ✓

---


## 2026-03-22 — Feature: Création rapide de RDV

### Changement
- Bouton "Valider avec les paramètres du profil" (data-testid=`quick-create-btn`) ajouté à l'étape 2 du wizard
- Icône Zap, style amber secondaire, à côté de "Suivant"
- Valide étapes 1+2 puis crée le RDV immédiatement avec les defaults du profil
- Toast spécifique : "Rendez-vous créé avec vos paramètres par défaut"
- Redirige vers la page détail du RDV

### Architecture
- Frontend uniquement (Option A) — réutilise l'endpoint existant POST /api/appointments/
- Les defaults sont déjà chargés au mount depuis /api/user-settings/me/appointment-defaults
- Aucun endpoint backend dédié créé

### Fichier modifié
- `/app/frontend/src/pages/appointments/AppointmentWizard.js`

### Tests (15/15 passés)
- Visibilité conditionnelle (step 2 uniquement) ✓
- Validations (titre, date, passé, lieu) ✓
- Création rapide avec defaults du profil ✓
- Wizard complet sans régression ✓
- Toasts différenciés ✓

---


## 2026-03-22 — Bugfix: Heure décalée +1h dans les emails

### Cause racine
`email_service.py` avait 5 blocs de parsing inline identiques qui traitaient les datetimes naïves comme UTC (`datetime.strptime` → `replace(tzinfo=utc)`). Or, `parse_iso_datetime` (le standard du projet) traite les datetimes naïves comme Europe/Paris. Résultat : si une datetime naïve atteignait l'email, elle était décalée de +1h (CET) ou +2h (CEST). De plus, `appointments.py` L171 passait la valeur brute du Pydantic au lieu de `utc_start`.

### Correction
- Créé `format_email_datetime(dt_string)` — **helper centralisé unique** pour TOUS les emails
- Utilise `parse_iso_datetime` (gère UTC, offsets, naive legacy) + `format_datetime_fr(dt, 'Europe/Paris')`
- Remplacé les 5 blocs inline dans `email_service.py`
- Mis à jour `modification_routes.py`, `reminder_service.py`, `event_reminder_service.py`
- Corrigé `appointments.py` L171 : `utc_start` au lieu de `appointment.start_datetime`

### Règle email
> Tous les emails utilisent `format_email_datetime()`. Aucun parsing datetime inline.
> UTC → Europe/Paris. Naive legacy → interprété comme Europe/Paris (pas UTC).

### Fichiers modifiés
- `/app/backend/services/email_service.py` (helper + 5 remplacements)
- `/app/backend/routers/modification_routes.py` (import + _build_changes_html)
- `/app/backend/routers/appointments.py` (L171)
- `/app/backend/services/reminder_service.py` (import + usage)
- `/app/backend/services/event_reminder_service.py` (import + usage)

### Tests (17/17 passés)
- UTC CET: 13:00Z → 14:00 ✓
- UTC CEST: 12:00Z → 14:00 ✓
- Naive legacy: "14:00" → 14:00 (pas 16:00) ✓
- DST transition: OK ✓
- Edge cases (empty, None): OK ✓

---


## 2026-03-22 — Bugfix: URLs cassées dans les emails de modification

### Cause racine
`modification_routes.py` L211 et L326 utilisaient `REACT_APP_BACKEND_URL` (variable frontend, absente du backend) au lieu de `FRONTEND_URL` (variable backend correcte). Résultat: `base_url = ""` → liens relatifs `/invitation/<token>` au lieu d'absolus.

### Correction
Remplacé `os.environ.get('REACT_APP_BACKEND_URL', os.environ.get('BASE_URL', ''))` par `os.environ.get('FRONTEND_URL', '').rstrip('/')` aux deux endroits.

### Fichier modifié
- `/app/backend/routers/modification_routes.py` (L211, L326)

### Audit complet des emails
| Email | Fichier | Variable URL | Status |
|---|---|---|---|
| Invitation initiale | `invitations.py` | `FRONTEND_URL` | ✅ OK |
| Modification proposée (participant) | `modification_routes.py` | ~~`REACT_APP_BACKEND_URL`~~ → `FRONTEND_URL` | ✅ Corrigé |
| Modification proposée (organisateur) | `modification_routes.py` | ~~`REACT_APP_BACKEND_URL`~~ → `FRONTEND_URL` | ✅ Corrigé |
| Modification acceptée | `modification_routes.py` | ~~`REACT_APP_BACKEND_URL`~~ → `FRONTEND_URL` | ✅ Corrigé |
| Garantie à reconfirmer | `modification_service.py` | `FRONTEND_URL` | ✅ OK |
| Confirmation acceptation | `invitations.py` | `FRONTEND_URL` | ✅ OK |

### Tests
- 5/5 types d'emails vérifiés avec URLs absolues correctes
- Email réellement envoyé via Resend avec succès (id: ebab7d70)
- Pages /invitation/ et /appointments/ retournent HTTP 200

---


## 2026-03-22 — E2E Verification: GPS Coordinates Reset on Location Modification

### Résultat: 9/9 tests PASS
- Paris→Lyon : coordonnées effacées, re-géocodées à 226m de Lyon
- Check-in près de Lyon : 147m, consistency=`close`
- Check-in près de Paris (ancien lieu) : 394km, consistency=`incoherent`
- Aucun cache résiduel incorrect

### Fichier vérifié
- `/app/backend/services/modification_service.py` (L249-253) — le reset fonctionne parfaitement

---


## 2026-03-22 — Feature: Visibilité produit du flag requires_revalidation

### Backend
- `GET /api/invitations/{token}` — retourne `guarantee_revalidation` avec `requires_revalidation`, `reason`, `flagged_at`
- `POST /api/invitations/{token}/reconfirm-guarantee` — crée nouvelle session Stripe, marque l'ancienne garantie comme `superseded`
- `GET /api/appointments/` et `GET /api/participants/` — enrichissent chaque participant avec `guarantee_requires_revalidation` et `guarantee_revalidation_reason`
- `send_guarantee_revalidation_email()` — email Resend envoyé automatiquement lors du flag (non-bloquant si Resend non configuré)

### Frontend — InvitationPage.js
- Bannière amber `guarantee-revalidation-banner` avec raisons (city_change, date_shift, type_change) et bouton "Reconfirmer ma garantie"
- Badge "À reconfirmer" (`status-badge-revalidation`) dans le header
- Section réponse avec icône warning amber au lieu de green shield
- Bouton de reconfirmation redirige vers Stripe checkout

### Frontend — AppointmentDetail.js
- Badge "À reconfirmer" (`badge-revalidation-{participant_id}`) dans la liste participants côté organisateur
- `getParticipantStatusBadge` accepte maintenant l'objet participant complet

### Tests
- 15/15 tests passés (iteration_21) : 7 backend + 8 frontend
- Scénarios: flag actif, flag absent, reconfirmation, endpoint 400, bannière visible/invisible

---


## 2026-03-22 — Feature: Stripe Guarantee Impact Assessment après modification

### Logique
- **Capture window recalculée** systématiquement après chaque modification acceptée (`capture_deadline` = fin RDV + 30min grâce)
- **Modification majeure** détectée si : date shift > 24h, changement de ville (via Nominatim), ou changement de type RDV
- **Flag `requires_revalidation`** posé sur les garanties `completed` si majeur — prépare le terrain pour un futur re-checkout
- **Modification mineure** : garantie conservée intacte, seul le `capture_deadline` est mis à jour

### Fichier modifié
- `/app/backend/services/modification_service.py` — Ajout de :
  - `_extract_city_from_address()` (Nominatim + fallback regex)
  - `_assess_modification_impact()` (détection majeur/mineur)
  - `_recalculate_capture_window()` (mise à jour deadline)
  - `_flag_guarantees_if_major()` (flag revalidation)
  - `_handle_guarantees_after_modification()` (hook principal)
  - Hook dans `_apply_proposal()` après application des changements

### Champs ajoutés sur `payment_guarantees`
- `capture_deadline` (ISO UTC)
- `capture_window_updated_at` (ISO UTC)
- `requires_revalidation` (bool)
- `revalidation_reason` (string, ex: "city_change:Paris->Lyon")
- `revalidation_flagged_at` (ISO UTC)

### Tests manuels passés
1. Minor (même ville Paris) → `requires_revalidation: false`, `capture_deadline` recalculé ✓
2. Major (ville Paris → Lyon) → `requires_revalidation: true`, raison `city_change:Paris->Lyon` ✓
3. Major (date shift 72h) → `requires_revalidation: true`, raison `date_shift_72.0h` ✓
4. Major (type physical → video) → `requires_revalidation: true`, raison `type_change:physical->video` ✓

---


## 2026-03-22 — UX: Repositionnement du bouton de modification de RDV

### Changement
- **Suppression** du crayon (edit-datetime-btn) qui était collé au champ "Date et heure"
- **Ajout** d'un bouton "Modifier" (edit-general-info-btn) à droite du titre "Informations générales"
- Le bouton couvre clairement tout le bloc : date, durée, lieu, type de RDV
- Design : bouton discret avec bordure, icône crayon + texte "Modifier", hover bleu

### Fichier modifié
- `/app/frontend/src/pages/appointments/AppointmentDetail.js`

### Tests
- 8/8 tests passés (iteration_20) : visibilité, ouverture formulaire, masquage RDV passé, pas d'impact autres blocs

---

## 2026-03-22 — Fix: GPS Coordinates Reset on Location Modification

### Changement
- Dans `_apply_proposal()`, quand le champ `location` change, les champs `location_latitude`, `location_longitude`, `location_geocoded`, `location_display_name` sont réinitialisés à `None`/`False`
- Force le re-géocodage par le moteur de preuves

### Fichier modifié
- `/app/backend/services/modification_service.py`

---


## 2026-02-22 — Feature: Flow contractuel de modification de RDV

### Architecture
- Nouvelle collection MongoDB: `modification_proposals`
- Nouveau service: `/app/backend/services/modification_service.py`
- Nouveau routeur: `/app/backend/routers/modification_routes.py`
- APScheduler job: expiration automatique à 24h

### Modèle de données
```
modification_proposals: {
  proposal_id, appointment_id,
  proposed_by: { user_id?, participant_id?, role, name },
  changes: { start_datetime?, duration_minutes?, location?, meeting_provider?, appointment_type? },
  original_values: { ... },
  responses: [{ participant_id, first_name, last_name, email, status, responded_at }],
  organizer_response: { status, responded_at },
  status: pending|accepted|rejected|expired|cancelled,
  expires_at, created_at, resolved_at
}
```

### Endpoints
- `POST /api/modifications/` — créer (organizer JWT ou participant token)
- `GET /api/modifications/appointment/{id}` — historique
- `GET /api/modifications/active/{id}` — proposition active
- `POST /api/modifications/{id}/respond` — accepter/refuser
- `POST /api/modifications/{id}/cancel` — annuler

### Logique
- Unanimité requise (organizer + tous participants acceptés)
- Rejet immédiat si un refuse
- Timeout 24h → expiration automatique
- Une seule proposition active par RDV
- RDV inchangé tant que non unanimement accepté
- Calendrier mis à jour après acceptation
- Stripe: aucun changement en V1 (hook préparé)
- Email notifications via Resend

### Tests
- 10/10 backend + 9/9 frontend = 100%
- Rapport: `/app/test_reports/iteration_19.json`

## 2026-02-22 — Bug Fix: Modification RDV vers date passée (P0)

### Problème
Un RDV existant pouvait être modifié vers une date passée via l'API PATCH.

### Fix
**Double validation (identique à la création)** :
- **Backend** (`appointments.py` PATCH) : vérification `start_datetime <= now_utc()` → HTTP 400
- **Frontend** (`AppointmentDetail.js`) : mode édition inline avec `min` dynamique, message d'erreur rouge, bouton "Enregistrer" désactivé si date passée
- L'icône crayon n'apparaît que si le RDV n'est pas annulé et pas terminé

### Tests
- 6/6 backend (hier, heure passée, heure future, demain, champ non-date)
- 7/7 frontend (icône visible, input min, erreur inline, bouton désactivé/activé, sauvegarde, annulation)
- Rapport: `/app/test_reports/iteration_18.json`

## 2026-02-20 — Bug Fix: Création RDV dans le passé (P0)

### Problème
Il était possible de créer un rendez-vous avec une date passée, sans aucune validation.

### Fix
**Double validation** :
- **Frontend** : attribut `min` dynamique sur `<input type="datetime-local">` + message d'erreur inline rouge + toast + blocage du bouton "Suivant"
- **Backend** : vérification `start_datetime <= now_utc()` → HTTP 400 "Impossible de créer un rendez-vous dans le passé"

### Tests
- 6/6 backend (hier, heure passée, heure exacte, heure future, demain, edge case)
- 5/5 frontend (min attribute, error message, toast, navigation bloquée, navigation OK si futur)
- Rapport: `/app/test_reports/iteration_17.json`

## 2026-02-20 — DST Timezone Validation

### Scénarios testés (CET → CEST, 29 mars 2026)
1. Veille (28 mars 23:00 CET = 22:00 UTC) → Affiche 23:00 ✅
2. Dernière heure avant switch (01:30 CET = 00:30 UTC) → Affiche 01:30 ✅
3. Gap DST (01:30 UTC → 03:30 CEST, 02:30 n'existe pas) → Affiche 03:30 ✅
4. Après switch (02:00 UTC = 04:00 CEST) → Affiche 04:00 ✅

### Vérifications
- API: 4/4 endpoints retournent la même valeur UTC ✅
- Frontend invitation (Playwright + Europe/Paris): 4/4 heures correctes ✅
- Cross-page consistency (Node.js): 4/4 identiques ✅
- Aucun bug DST détecté

## 2026-02-20 — Timezone Bug Fix (P0 Critical)

### Root Cause
- Backend stockait les dates comme des chaînes naïves (sans timezone)
- `InvitationPage.js` ajoutait artificiellement `'Z'` aux dates naïves → décalage de 1h
- `invitations.py` avait un `parse_datetime` local qui traitait les naïves comme UTC
- `evidence_service.py` utilisait `ZoneInfo('Europe/Paris')` pour deviner la timezone

### Fix appliqué
1. **Backend `date_utils.py`** : Nouveau `normalize_to_utc()` — dates naïves legacy interprétées comme Europe/Paris, converties en UTC
2. **Backend `appointments.py`** : Normalisation UTC à la création, mise à jour ET lecture
3. **Backend `invitations.py`** : Suppression du `parse_datetime` local, utilisation de `parse_iso_datetime` unifié
4. **Backend `evidence_service.py`** : Suppression de `DEFAULT_TIMEZONE`, utilisation de `parse_iso_datetime`
5. **Frontend `dateFormat.js`** : Utilitaire unique (`formatDateTimeFr`, `formatTimeFr`, `localInputToUTC`, etc.)
6. **Frontend pages** : InvitationPage, AppointmentDetail, OrganizerDashboard, ParticipantManagement, Integrations — tous utilisent le même utilitaire

### Fichiers modifiés
- `/app/backend/utils/date_utils.py`
- `/app/backend/routers/appointments.py`
- `/app/backend/routers/invitations.py`
- `/app/backend/services/evidence_service.py`
- `/app/backend/services/attendance_service.py`
- `/app/backend/services/event_reminder_service.py`
- `/app/backend/services/reminder_service.py`
- `/app/frontend/src/utils/dateFormat.js` (NOUVEAU)
- `/app/frontend/src/pages/invitations/InvitationPage.js`
- `/app/frontend/src/pages/appointments/AppointmentDetail.js`
- `/app/frontend/src/pages/appointments/AppointmentWizard.js`
- `/app/frontend/src/pages/appointments/ParticipantManagement.js`
- `/app/frontend/src/pages/dashboard/OrganizerDashboard.js`
- `/app/frontend/src/pages/settings/Integrations.js`

### Tests
- 13/13 backend tests passed (normalization, parsing, consistency)
- 4/4 frontend UI tests passed (identical display across pages)
- Test report: `/app/test_reports/iteration_16.json`
