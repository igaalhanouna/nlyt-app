# NLYT — Architecture Cible (Mars 2026)

Document de référence post-pivots. Reflète l'état réel du code.

---

## 1. Séparation stricte des types de rendez-vous

| | RDV Physique | RDV Visio |
|---|---|---|
| Champ DB | `appointment_type: "physical"` | `appointment_type: "video"` |
| Preuves principales | GPS + QR + Check-in manuel | NLYT Proof (check-in + heartbeat) |
| Preuves secondaires | — | API vidéo (Zoom/Teams) — bonus |
| Scoring automatique | Non (évaluation par force de preuve) | Oui (0-100, basé sur ponctualité + durée) |
| Garde-fou backend | `/api/proof/*` retourne 400 si physique | `/api/checkin/gps` utilisable mais non lié au scoring visio |

---

## 2. RDV Physiques — Système existant (inchangé)

### Moyens de preuve

| Source | Endpoint | Description |
|---|---|---|
| Check-in manuel | `POST /api/checkin/manual` | "Je suis arrivé" — avec GPS si consent |
| QR code | `POST /api/checkin/qr/verify` | Scan QR généré par organisateur |
| GPS complémentaire | `POST /api/checkin/gps` | Envoi de coordonnées comme preuve additionnelle |

### GPS organisateur
L'organisateur envoie aussi ses coordonnées GPS au check-in (même payload que le participant : `latitude`, `longitude`, `gps_consent` via `navigator.geolocation`).

### Logique de décision (`attendance_service.py` L210-260)
Basée sur la **force de preuve agrégée** (`evidence_service.aggregate_evidence`) :

| Force | Timing | Décision | Confiance | Revue manuelle |
|---|---|---|---|---|
| `strong` | `on_time` | `on_time` | high | Non |
| `strong` | `late` | `late` | high | Non |
| `medium` | `on_time` | `on_time` | medium | Oui |
| `medium` | `late` | `late` | medium | Oui |
| `weak`/`none` | — | `manual_review` | low | Oui |

Pas de scoring numérique. Décision binaire conservatrice.

---

## 3. RDV Visio — NLYT Proof (source principale)

### Architecture

```
Participant ouvre lien NLYT → Check-in → Onglet visio s'ouvre → Heartbeat 30s → Checkout
          │                      │                                    │              │
          ▼                      ▼                                    ▼              ▼
   /proof/{id}/info      /proof/{id}/checkin              /proof/{id}/heartbeat  /proof/{id}/checkout
                                                                                       │
                                                                                  Scoring auto
```

### Endpoints NLYT Proof

| Endpoint | Auth | Description |
|---|---|---|
| `GET /api/proof/{id}/info?token=...` | Token participant | Info RDV + session active |
| `POST /api/proof/{id}/checkin` | Token participant | Démarrer session |
| `POST /api/proof/{id}/heartbeat` | Session ID | Ping toutes les 30s |
| `POST /api/proof/{id}/checkout` | Session ID | Terminer + calculer score |
| `GET /api/proof/{id}/sessions` | JWT organisateur | Liste des sessions |
| `POST /api/proof/{id}/validate` | JWT organisateur | Valider statut final |

### Scoring (`proof_routes.py` L77-123)

| Composante | Points max | Règle |
|---|---|---|
| Ponctualité (check-in) | 30 | A l'heure: 30 / ≤15min retard: 15 / >15min: 5 |
| Durée active | 40 | `(durée_active / durée_attendue) × 40` |
| Confirmation API vidéo | 30 | Bonus futur (non implémenté) |
| **Total** | **100** | |

| Score | Niveau (`proof_level`) |
|---|---|
| ≥ 70 | `strong` |
| ≥ 40 | `medium` |
| < 40 | `weak` |

### Statut suggéré automatique
- `strong` → `present`
- `medium` → `partial`
- `weak` → `absent`

L'organisateur peut **surcharger** le statut suggéré via `/validate`.

### Rôle secondaire des providers visio
L'auto-fetch Zoom/Teams (scheduler toutes les 5min) reste actif comme **bonus**. Il ne pilote plus la décision. Résultat stocké dans `evidence` avec `source: "video_conference"`, utilisé par `attendance_service.py` comme signal complémentaire (L131-208).

---

## 4. Politique Provider Visio

### Règle produit
NLYT ne crée jamais de réunion de manière centralisée. Trois options pour l'utilisateur :

| Option | Mode | Description |
|---|---|---|
| Coller un lien | `external` | L'utilisateur colle une URL Zoom/Teams/Meet/autre |
| Connecter Zoom | `user` | L'utilisateur connecte SON compte Zoom |
| Connecter Teams | `user` | L'utilisateur connecte SON compte Microsoft 365 |
| Connecter Meet | `user` | L'utilisateur connecte SON Google Calendar |

### Ce qui a été supprimé
- `mode: "central"` pour Zoom (Server-to-Server OAuth comme créateur par défaut)
- Auto-sélection Zoom par défaut dans le wizard
- Badge "Recommandé" / message "Aucun compte requis"
- `creation_mode: "central"` dans les métadonnées

### Ce qui est conservé
- Code des adapters Zoom/Teams/Meet (utilisable si l'utilisateur connecte son propre compte)
- Auto-fetch attendance scheduler (bonus, secondaire)
- Fallback CSV upload pour Zoom Free Plan

---

## 5. Impacts UX

### Wizard (`AppointmentWizard.js`)
- Section A (défaut) : "Coller un lien de visio" — badge "Simple"
- Séparateur : "ou connecter un provider"
- Section B : Zoom / Teams / Meet — chacun avec état "Connecté" ou lien vers Paramètres
- Note auto-création : "Le lien sera créé via votre compte {provider}"

### Invitation (`InvitationPage.js`)
- RDV physique : check-in avec GPS, QR scan
- RDV visio : pas de changement côté invitation (le participant utilise le lien NLYT Proof)

### Page détail (`AppointmentDetail.js`)
- Section "Mon check-in (organisateur)" :
  - Physique : bouton "Check-in avec GPS" (demande `navigator.geolocation`)
  - Visio : messages provider-specific + check-in de secours
- Section "NLYT Proof — Sessions de présence" :
  - **Visible uniquement pour `appointment_type === 'video'`**
  - Tableau : participant, check-in, durée, heartbeats, score/100, niveau, statut, actions
  - Liens de check-in copiables par participant
  - Boutons de validation (Présent / Partiel / Absent)
- Section "Preuves de présence" : identité organisateur, mode Teams, proof availability
  - NLYT Proof affiché comme source principale
  - API vidéo affiché comme "Bonus"

### Emails (`email_service.py`)
- RDV physique : pas de section NLYT Proof (proof_link = None)
- RDV visio : section bleue "Confirmer ma présence le jour J" avec lien NLYT unique

---

## 6. État du code

### Implémenté et testé

| Composant | Fichier(s) | Status |
|---|---|---|
| NLYT Proof backend (6 endpoints) | `proof_routes.py` | OK — testé (22/22) |
| NLYT Proof frontend (CheckinPage) | `CheckinPage.js` | OK — testé (15/15) |
| Vue organisateur sessions | `AppointmentDetail.js` | OK |
| Séparation physique/visio | `proof_routes.py`, `AppointmentDetail.js`, `appointment_lifecycle.py` | OK |
| Provider mode "user" | `video_evidence_routes.py`, `meeting_provider_service.py` | OK |
| Wizard simplifié | `AppointmentWizard.js` | OK |
| GPS organisateur (physique) | `AppointmentDetail.js` | OK |
| Proof link dans emails (visio) | `email_service.py`, `appointment_lifecycle.py` | OK |
| Guarantee-first architecture | `appointment_lifecycle.py`, `stripe_guarantee_service.py` | OK |
| CORS + Rate limiting | `server.py` | OK |
| Check-in physique (GPS/QR/manuel) | `checkin_routes.py`, `evidence_service.py` | OK |
| Moteur de décision conservateur | `attendance_service.py` | OK |
| **NLYT Proof → Moteur de décision (visio)** | `attendance_service.py` | OK — 6/6 scénarios |
| Auto-fetch Zoom/Teams | `auto_fetch_attendance_service.py`, `scheduler.py` | OK |
| CSV/JSON import fallback | `video_evidence_routes.py` | OK |

### Reste à faire

| Tâche | Priorité | Description |
|---|---|---|
| Bonus API vidéo dans scoring | P1 | `video_api_points` (30pts) dans le scoring NLYT Proof est déclaré mais pas encore calculé |
| Stripe Connect | P1 | Distribution automatique des fonds aux organisateurs/associations |
| Webhooks temps réel Zoom/Teams | P1 | `meeting.ended` webhook pour déclencher le fetch immédiatement |
| Pagination endpoints | P2 | Listes longues (appointments, participants) |
| Auto-update calendrier V2 | P2 | Retry automatique en cas d'échec |
| Dashboard analytics | P3 | Tableaux de bord pour organisateurs |
| MongoDB connection pooling | P3 | Refactoring des instances MongoClient séparées |
| Templates email extractés | P3 | Sortir le HTML inline dans des fichiers séparés |

### Abandonné

| Élément | Raison |
|---|---|
| Zoom mode central (Server-to-Server comme host) | Modèle non scalable, dépendance critique, Zoom Free Plan limite l'API |
| Auto-sélection provider par défaut | Crée une dépendance implicite, UX trompeuse |
| Provider comme source de vérité | APIs trop restrictives/payantes, pas fiable pour un produit universel |

---

## 7. Roadmap priorisée

### P0 — Court terme
- [x] ~~Intégrer `proof_sessions` dans `attendance_service.evaluate_participant` pour les RDV visio~~ **DONE**

### P1 — Moyen terme
- [ ] Stripe Connect (distribution automatique)
- [ ] Webhooks temps réel Zoom (`meeting.ended`) / Teams
- [ ] Calculer `video_api_points` (30pts bonus) quand l'API vidéo confirme la présence

### P2 — Backlog actif
- [ ] Pagination endpoints (appointments, participants)
- [ ] Auto-update calendrier V2 (retry)

### P3 — Backlog futur
- [ ] Dashboard analytics organisateurs
- [ ] MongoDB connection pooling
- [ ] Extraction templates email HTML
