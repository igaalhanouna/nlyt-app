# NLYT — Changelog

## 2026-03-22 — Page Intégrations Visioconférence ✅

### Architecture retenue
- **Google Meet** : enrichissement de la carte Google Calendar existante (même OAuth) — badge "Google Meet" + note "Création de liens Meet activée"
- **Zoom** : carte dédiée dans section Visioconférence — connect/disconnect, email, feature badges
- **Teams** : carte dédiée dans section Visioconférence — connect/disconnect, Azure AD ID, email, feature badges
- **Pas de carte Google Meet séparée** : même connexion que Google Calendar

### Frontend (`Integrations.js` — réécriture complète)
- **Section CALENDRIERS** : Google Calendar (badge Calendrier + badge Google Meet avec checkmark si connecté), Outlook (badge Calendrier uniquement)
- **Section VISIOCONFÉRENCE** : Zoom card, Teams card, Google Meet note
- Chaque carte : nom, usage, état connexion, email/compte, bouton connecter/déconnecter, badges features
- Badges : "Création de réunion", "Présences auto", "Calendrier", "Google Meet"
- Zoom config form : email Zoom + avertissement si credentials serveur manquants
- Teams config form : Azure AD User ID + email Teams + avertissement si credentials manquants
- Note Google Meet : "Activé via votre connexion Google Calendar" ou "Connectez Google Calendar pour activer Meet"

### Backend (endpoints ajoutés)
- `GET /api/video-evidence/provider-status` — enrichi avec statut per-user (email, connected_at, features, requires)
- `POST /api/video-evidence/connect/zoom` — sauvegarde config Zoom dans user_settings
- `DELETE /api/video-evidence/connect/zoom` — supprime config Zoom
- `POST /api/video-evidence/connect/teams` — sauvegarde Azure AD + Teams email dans user_settings
- `DELETE /api/video-evidence/connect/teams` — supprime config Teams

### Testing
- iteration_26: 15/15 backend + UI complète vérifiée, 0 régression

---

## 2026-03-22 — Video Meeting API Integration ✅
- Meeting creation API (Zoom/Teams/Meet), auto-create on appointment, CSV/JSON upload, meeting link in emails
- iteration_25: 13/13 passed

## 2026-03-22 — Video Conference Attendance Evidence MVP ✅
- Modular adapters, evidence ingestion, conservative decision engine
- iteration_24: 17/17 passed

## Previous: Timezone, Express creation, Email fixes, Modification UX, GPS fix
