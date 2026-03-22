# NLYT - Changelog

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
