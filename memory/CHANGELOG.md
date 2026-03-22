# NLYT — Changelog

## 2026-03-22 — Sélecteur de plateforme visio contrôlé (Wizard)

### Backend (`schemas.py`, `appointments.py`)
- Ajout de l'enum `MeetingProvider` (zoom, teams, meet, external) dans schemas.py
- `AppointmentCreate.meeting_provider` typé `Optional[MeetingProvider]` — Pydantic rejette toute valeur hors enum (422)
- Validation serveur : `external` sans `meeting_join_url` → 400

### Frontend (`AppointmentWizard.js`)
- Remplacement du champ texte libre par un sélecteur de 4 providers avec états connecté/non-connecté
- Providers connectés : sélectionnables, badge vert, email affiché
- Providers non connectés : grisés (opacity), lien vers Paramètres > Intégrations
- "Lien externe" : toujours disponible, affiche un champ URL obligatoire
- Note auto-création affichée quand un provider connecté est sélectionné
- Validation frontend : provider requis, non-connecté bloqué, URL externe obligatoire

### Frontend (`AppointmentDetail.js`)
- Formulaire de modification : input texte remplacé par select contrôlé (zoom/teams/meet/external)

### Testing
- iteration_27: 14/14 tests passés (8 backend + 6 frontend), 0 régression

---

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
