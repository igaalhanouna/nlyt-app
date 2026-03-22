# NLYT — Changelog

## 2026-03-22 — Organisateur comme participant (symétrie complète)

### Backend (`appointments.py`)
- Auto-injection de l'organisateur comme participant à chaque création de RDV
- `is_organizer: true`, `role: "organizer"`, `status: "accepted_pending_guarantee"`
- Création d'une session Stripe pour la garantie organisateur (même flow que participants)
- `organizer_checkout_url`, `organizer_participant_id`, `organizer_invitation_token` dans la réponse
- Skip email d'invitation si l'email du participant = email organisateur (pas de doublon)
- Si penalty_amount = 0 → statut directement `accepted_guaranteed`

### Frontend (`AppointmentWizard.js`)
- Redirection vers Stripe après création si `organizer_checkout_url` présent

### Frontend (`AppointmentDetail.js`)
- Section "Mon check-in (organisateur)" avec bouton check-in manuel
- Section "Garantie organisateur requise" si statut `accepted_pending_guarantee`
- Badge "Organisateur" dans la liste des participants
- Bouton "Renvoyer invitation" masqué pour l'organisateur

### Testing
- iteration_29: 12/12 tests passés (9 backend + 4 frontend), 0 régression

---

## 2026-03-22 — Sécurisation meeting_provider (validation conditionnelle)

### Backend (`schemas.py`)
- `field_validator` : `""` → `None`
- `model_validator` : `meeting_provider` obligatoire si `video`, forcé à `None` si `physical`

### Backend (`modification_service.py`)
- Switch physical → `meeting_provider: None` (était `""`)

### Frontend (`AppointmentWizard.js`, `AppointmentDetail.js`)
- Init `meeting_provider: null` (était `""`)
- Nettoyage payload : suppression du champ si `appointment_type !== 'video'`

### Testing
- 7/7 tests unitaires + 6/6 tests API

---

## 2026-03-22 — Sécurité imports manuels + Guides configuration

### Backend — source_trust (`video_evidence_service.py`, `evidence_service.py`, `attendance_service.py`)
- Nouveau champ `source_trust` dans `derived_facts` de chaque evidence vidéo : `api_verified` | `manual_upload`
- `ingest_video_attendance()` accepte un paramètre `source_trust` (default: `manual_upload`)
- Route `fetch-attendance` passe `source_trust="api_verified"` (données récupérées via API provider)
- Routes `ingest` et `ingest-file` gardent `source_trust="manual_upload"` (fichiers uploadés par l'organisateur)
- `source_trust` stocké dans le log d'ingestion et dans chaque `evidence_item`
- `aggregate_evidence()` extrait et retourne `video_source_trust`
- **Plafonnement moteur** : `manual_upload` cap la strength à `"medium"` max (jamais `"strong"`) → `review_required: true`
- `attendance_service` ajoute `source_trust` dans `video_context` de chaque décision

### Frontend (`AppointmentDetail.js`)
- Badge `source_trust` dans la timeline de preuves vidéo :
  - "Vérifié par API" (bleu, icône Shield) pour `api_verified`
  - "Import manuel" (orange, icône Upload) pour `manual_upload`
- data-testid=`source-trust-badge-{evidence_id}`

### Testing
- iteration_28: 10/10 tests passés, 0 régression

---

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
