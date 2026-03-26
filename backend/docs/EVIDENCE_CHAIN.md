# Chaîne de Preuves de Présence — Documentation Technique

> **ZONE PROTÉGÉE** — Toute modification de cette chaîne doit être
> explicitement signalée dans le summary de livraison.

## Vue d'ensemble

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  COLLECTE    │───>│  STOCKAGE    │───>│  AGRÉGATION  │───>│  AFFICHAGE   │
│  (check-in)  │    │  (MongoDB)   │    │  (API)       │    │  (Frontend)  │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

---

## 1. COLLECTE — Points d'entrée du check-in

### Fichier : `backend/routers/checkin_routes.py`

Trois types de check-in, tous publics (auth par `invitation_token`) :

| Endpoint              | Source evidence | Déclencheur                        |
|-----------------------|----------------|------------------------------------|
| `POST /api/checkin/manual` | `gps` ou `manual_checkin` | Bouton "Je suis arrivé"   |
| `POST /api/checkin/gps`    | `gps`                     | Preuve GPS complémentaire  |
| `POST /api/checkin/qr/verify` | `qr`                  | Scan de QR code            |

### Résolution du participant : `_resolve_participant(invitation_token)`

1. Recherche dans `participants` par `invitation_token`
2. Vérifie que le statut est dans : `['accepted', 'accepted_pending_guarantee', 'accepted_guaranteed']`
3. Vérifie que le rendez-vous est `active`
4. Retourne `(participant, appointment)`

> **RÈGLE** : Organisateurs et participants utilisent le même mécanisme.
> Aucun traitement différencié par `is_organizer`.

### Détermination du `source`

Dans `process_manual_checkin` (evidence_service.py L406) :
- Si GPS fourni (`latitude` + `longitude` présents) → `source = "gps"`
- Sinon → `source = "manual_checkin"`

> **CONSÉQUENCE** : La majorité des check-ins manuels avec GPS activé
> créent une evidence de source `"gps"`, pas `"manual_checkin"`.

---

## 2. STOCKAGE — Collection `evidence_items`

### Fichier : `backend/services/evidence_service.py` (fonction `create_evidence`)

### Schéma du document

```json
{
  "evidence_id":     "uuid4",              // OBLIGATOIRE — identifiant unique
  "appointment_id":  "uuid4",              // OBLIGATOIRE — lien vers le RDV
  "participant_id":  "uuid4",              // OBLIGATOIRE — lien vers le participant
  "source":          "gps|manual_checkin|qr|video_conference|system",  // OBLIGATOIRE
  "source_timestamp": "ISO 8601",          // OBLIGATOIRE — heure du check-in
  "created_at":      "ISO 8601",           // OBLIGATOIRE — heure d'insertion
  "confidence_score": "high|medium|low",   // OBLIGATOIRE — score calculé
  "created_by":      "participant|system",
  "raw_payload_reference": null,
  "derived_facts": {
    "device_info":              "string",   // User-Agent du navigateur
    "latitude":                 48.86550,   // OBLIGATOIRE si GPS
    "longitude":                2.32941,    // OBLIGATOIRE si GPS
    "temporal_consistency":     "valid|valid_late|too_early|too_late|unknown",
    "temporal_detail":          "Arrivé 12min avant le RDV",
    "geographic_consistency":   "close|nearby|far|incoherent|no_reference|no_gps",
    "geographic_detail":        "À 0m du lieu du RDV",
    "distance_meters":          0.0,
    "distance_km":              0.0,
    "gps_within_radius":        true,
    "gps_radius_meters":        200,
    "address_label":            "Quartier Vendôme, Paris...",
    "confidence_factors":       "temporal=valid, geographic=close",
    // QR spécifique :
    "qr_window":                12345,
    "qr_valid":                 true,
    "scanned_by":               "uuid4"     // Si scanné par un autre participant
  }
}
```

### Champs obligatoires pour chaque evidence

| Champ              | Toujours présent | Condition                       |
|--------------------|------------------|---------------------------------|
| `evidence_id`      | Oui              |                                 |
| `appointment_id`   | Oui              |                                 |
| `participant_id`   | Oui              |                                 |
| `source`           | Oui              |                                 |
| `source_timestamp` | Oui              |                                 |
| `confidence_score` | Oui              |                                 |
| `latitude`         | Non              | Uniquement si source=gps        |
| `longitude`        | Non              | Uniquement si source=gps        |

### Protection anti-doublon

Avant chaque insertion, vérification d'evidence existante :
- `manual_checkin` : cherche `source IN ["manual_checkin", "gps"]` pour le même participant
- `gps` : cherche `source = "gps"` pour le même participant
- `qr` : cherche `source = "qr"` pour le même participant

---

## 3. AGRÉGATION — API de restitution

### Fichier : `backend/routers/checkin_routes.py`

### Endpoint organisateur : `GET /api/checkin/evidence/{appointment_id}`

**Auth** : JWT (organisateur via `get_current_user` + vérification workspace)

**Réponse** :
```json
{
  "appointment_id": "uuid4",
  "participants": [
    {
      "participant_id": "uuid4",
      "participant_name": "Igaal Hanouna",
      "participant_email": "igaal@hotmail.com",
      "evidence": [
        {
          "evidence_id": "...",
          "source": "gps",
          "source_timestamp": "2026-03-26T20:18:51",
          "confidence_score": "high",
          "derived_facts": { "latitude": 48.86550, "longitude": 2.32941, ... }
        }
      ],
      "aggregation": {
        "strength": "medium",
        "signals": ["gps_close"],
        "timing": "on_time",
        "confidence": "medium",
        "evidence_count": 1,
        "earliest_evidence": "...",
        "temporal_flag": "valid",
        "geographic_flag": "close"
      }
    }
  ],
  "total_evidence": 2
}
```

**Règles d'inclusion** :
- TOUS les participants avec statut `accepted`, `accepted_pending_guarantee`, ou `accepted_guaranteed`
- PAS de filtre sur `is_organizer` — l'organisateur est inclus
- UNE entrée par participant, même s'il a 0 evidence

### Endpoint participant : `GET /api/checkin/status/{appointment_id}?invitation_token=...`

**Auth** : `invitation_token` (public)

**Réponse** :
```json
{
  "checked_in": true,
  "has_manual_checkin": false,
  "has_qr_checkin": false,
  "has_gps": true,
  "evidence_count": 1,
  "earliest_checkin": "2026-03-26T20:18:51",
  "evidence": [...]
}
```

**Règle `checked_in`** : `has_manual_checkin OR has_qr OR has_gps`

---

## 4. AFFICHAGE — Frontend

### Fichier : `frontend/src/pages/appointments/EvidenceDashboard.js`

**Données d'entrée** : `evidenceData` (réponse de `GET /api/checkin/evidence/{apt_id}`)

**Mapping** :
```
evidenceData.participants  →  tableau par participant
  └── .find(p => p.participant_id === pid)
        └── .evidence  →  tableau de preuves de ce participant
```

**Filtre d'affichage** : statut `['accepted', 'accepted_pending_guarantee', 'accepted_guaranteed']`
- L'organisateur N'EST PAS filtré
- Chaque participant a son propre bloc

**Champs rendus par evidence item** :
- Source (GPS / QR / Manuel) avec icône et couleur
- Score de confiance (high/medium/low) avec badge coloré
- Timestamp formaté en français
- Coordonnées GPS (latitude, longitude à 5 décimales)
- Distance au lieu du RDV (mètres ou km)
- Détail temporel ("Arrivé 12min avant le RDV")
- Adresse (reverse geocodée)

---

## 5. INVARIANTS CRITIQUES

Ces règles ne doivent JAMAIS être violées :

1. **1 participant = 1 entrée dans le rapport** — pas de fusion, pas d'omission
2. **Organisateur inclus** — aucun filtre sur `is_organizer` dans l'agrégation ou l'affichage
3. **`participant_id` est la clé de jointure** — entre `evidence_items` et `participants`
4. **3 statuts acceptés** : `accepted`, `accepted_pending_guarantee`, `accepted_guaranteed`
5. **`checked_in` inclut GPS** : `has_manual OR has_qr OR has_gps`
6. **Pas de modification silencieuse** — tout changement dans cette chaîne doit être signalé

---

## Fichiers de la chaîne

| Couche       | Fichier                                                    | Rôle                               |
|-------------|------------------------------------------------------------|------------------------------------|
| Collecte    | `backend/routers/checkin_routes.py`                        | Endpoints check-in                 |
| Service     | `backend/services/evidence_service.py`                     | Logique métier, scoring, stockage  |
| Agrégation  | `backend/routers/checkin_routes.py` L268-313               | Endpoint `/evidence/{apt_id}`      |
| Affichage   | `frontend/src/pages/appointments/EvidenceDashboard.js`     | Rendu "Check-ins & Preuves"        |
| Orchestrateur | `frontend/src/pages/appointments/AppointmentDetail.js`   | Charge et passe `evidenceData`     |
| Statut      | `backend/routers/checkin_routes.py` L231-263               | Endpoint `/status/{apt_id}`        |
| Check-in UI | `frontend/src/pages/invitations/InvitationCheckinSection.js` | UI participant check-in          |

---

## Tests de non-régression

Fichier : `backend/tests/test_evidence_chain.py`

Couvre les 5 scénarios :
1. Organisateur seul
2. Organisateur + 1 participant
3. Organisateur + 2 participants
4. Uniquement participants (sans organisateur)
5. Vérification que chaque personne a son entrée distincte
