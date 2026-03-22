# NLYT - Changelog

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
