# NLYT Proof — Architecture de Référence

> **DOCUMENT GELÉ — Version 1.0 — Mars 2026**
> Toute modification de cette architecture doit être signalée dans le summary de livraison.

---

## 1. CE QUE NLYT PROOF PROUVE — ET NE PROUVE PAS

### NLYT Proof valide :

| Fait prouvé | Mécanisme | Fiabilité |
|-------------|-----------|-----------|
| **L'instant du check-in** | Timestamp UTC serveur au moment de l'appel API | Forte (horloge serveur) |
| **L'identité du participant** | Résolution par `invitation_token` → `participant_id` | Forte (token unique) |
| **La position GPS** (physique) | Coordonnées navigateur au moment du check-in | Moyenne (dépend du consentement) |
| **La proximité géographique** (physique) | Haversine entre GPS participant et lieu du RDV | Moyenne (GPS falsifiable) |
| **La cohérence temporelle** | Écart entre check-in et heure de début du RDV | Forte (calcul serveur) |

### NLYT Proof NE prouve PAS :

| Fait NON prouvé | Raison | Alternative |
|-----------------|--------|-------------|
| **La durée réelle de présence** | Un seul point de mesure (check-in), pas de check-out | Provider visio (Zoom/Teams) |
| **La présence continue** | Aucun mécanisme de vérification après le check-in | Heartbeat (future) |
| **L'identité physique** | Le token peut être partagé (un tiers check-in pour quelqu'un) | QR scan croisé |
| **L'attention/participation active** | Aucune mesure d'engagement dans la réunion | Provider analytics |

### Définitions claires

- **Check-in temporel** : Preuve qu'un participant identifié a déclaré sa présence à un instant T.
  C'est un fait binaire (présent ou absent à l'instant T), pas une mesure continue.

- **Présence prolongée** : Preuve qu'un participant est resté pendant une durée D.
  Nécessite deux points de mesure minimum (entrée + sortie) ou un heartbeat.
  **NLYT Proof seul ne la mesure pas.**

- **Provider evidence** : Données d'attendance fournies par Zoom/Teams/Meet via leur API.
  Contient `joined_at`, `left_at`, `duration_seconds` → mesure la durée réelle.
  Dépend d'un compte pro chez le provider.

---

## 2. HIÉRARCHIE DES PREUVES

### Niveaux de preuve

```
NIVEAU 1 — PREUVES PRINCIPALES (déterminent le statut)
├── NLYT Proof check-in         → prouve la présence à l'instant T
├── GPS (physique)              → prouve la proximité géographique
└── Provider attendance (visio) → prouve la durée de présence

NIVEAU 2 — PREUVES COMPLÉMENTAIRES (renforcent la confiance)
├── QR Code scan croisé         → prouve la co-localisation
├── Cohérence temporelle        → renforce si dans les temps
└── Reverse geocoding           → enrichit l'adresse

NIVEAU 3 — MÉTADONNÉES (enrichissement, pas de poids décisionnel)
├── provider_role (host/attendee) → informatif
├── device_info                   → traçabilité
├── identity_match_method         → transparence du matching
└── source_trust                  → provenance de la donnée
```

### Règle de priorité

1. **NLYT Proof est TOUJOURS la preuve principale.** C'est la seule preuve que NLYT contrôle de bout en bout.
2. **Les données provider sont complémentaires.** Elles enrichissent (durée, rôle) mais ne remplacent pas le check-in NLYT.
3. **Aucune donnée de Niveau 3 ne peut modifier le statut de présence** (présent/absent/retard). Ces données sont affichées mais ne pèsent pas dans le calcul.

### Calcul du score de confiance

```
Score de base :
  manual_checkin = 1 point
  gps            = 2 points (plus fort car vérifiable)
  qr             = 3 points (co-localisation prouvée)
  video_conference = 2 points (provider vérifié)

Modificateurs temporels :
  valid          = +1
  valid_late     = +0
  too_early      = -1
  too_late       = -2

Modificateurs géographiques (physique uniquement) :
  close (<500m)  = +2
  nearby (<5km)  = +1
  far (<50km)    = -1
  incoherent     = -3

Score final :
  ≥ 4 → high
  ≥ 2 → medium
  < 2 → low
```

---

## 3. STRUCTURE DE DONNÉES STABLE

### Document `evidence_items` — Schéma gelé

```
┌─────────────────────────────────────────────────────────┐
│ CHAMPS OBLIGATOIRES (tous types de preuve)              │
├─────────────────────────────────────────────────────────┤
│ evidence_id        : uuid4          clé primaire        │
│ appointment_id     : uuid4          lien vers le RDV    │
│ participant_id     : uuid4          lien vers la person │
│ source             : enum           voir ci-dessous     │
│ source_timestamp   : ISO 8601 UTC   instant de preuve   │
│ created_at         : ISO 8601 UTC   instant d'insertion │
│ confidence_score   : high|medium|low score calculé      │
│ created_by         : participant|system auteur          │
├─────────────────────────────────────────────────────────┤
│ CHAMP OPTIONNEL                                         │
├─────────────────────────────────────────────────────────┤
│ raw_payload_reference : string|null  référence brute    │
├─────────────────────────────────────────────────────────┤
│ CHAMP DÉRIVÉ (objet)                                    │
├─────────────────────────────────────────────────────────┤
│ derived_facts : {                                       │
│   ── Commun à tous ──                                   │
│   temporal_consistency   : valid|valid_late|too_early|…  │
│   temporal_detail        : "Arrivé 5min avant le RDV"   │
│   device_info            : string (User-Agent)          │
│                                                         │
│   ── Physique (GPS) ──                                  │
│   latitude               : float                        │
│   longitude              : float                        │
│   geographic_consistency : close|nearby|far|incoherent  │
│   geographic_detail      : "À 50m du lieu"              │
│   distance_meters        : float                        │
│   distance_km            : float                        │
│   gps_within_radius      : bool                         │
│   gps_radius_meters      : int (200 par défaut)         │
│   address_label          : string (reverse geocodé)     │
│                                                         │
│   ── Physique (QR) ──                                   │
│   qr_window              : int                          │
│   qr_valid               : bool                         │
│   scanned_by             : uuid4 (qui a scanné)         │
│                                                         │
│   ── Visio (provider) ──                                │
│   provider               : zoom|teams|meet              │
│   external_meeting_id    : string                       │
│   joined_at              : ISO 8601                     │
│   left_at                : ISO 8601                     │
│   duration_seconds       : int                          │
│   identity_confidence    : high|medium|low              │
│   identity_match_method  : email_exact|name_fuzzy|…     │
│   identity_match_detail  : string                       │
│   video_attendance_outcome : joined_on_time|joined_late │
│                              |no_join_detected          │
│   participant_email_from_provider : string              │
│   participant_name_from_provider  : string              │
│   provider_role          : host|attendee|organizer|…    │
│   provider_evidence_ceiling : verified|assisted         │
│   source_trust           : provider_api|manual_upload   │
│ }                                                       │
└─────────────────────────────────────────────────────────┘
```

### Enum `source`

| Valeur | Type | Auteur | Prouve |
|--------|------|--------|--------|
| `manual_checkin` | physique/visio | participant | Check-in sans GPS |
| `gps` | physique | participant | Check-in + position GPS |
| `qr` | physique | participant | Scan QR croisé |
| `video_conference` | visio | system | Présence + durée (provider) |
| `system` | tout | system | Preuve générée automatiquement |

### Clé de jointure

```
evidence_items.participant_id  ←→  participants.participant_id
evidence_items.appointment_id  ←→  appointments.appointment_id
```

**`participant_id` est l'identité.** Pas l'email, pas le nom, pas le token.

---

## 4. GARDE-FOUS — RÈGLES DE PROTECTION

### Fichiers sous protection

| Fichier | Rôle | Marqueur |
|---------|------|----------|
| `backend/routers/checkin_routes.py` | Endpoints check-in + API evidence | `!! ZONE PROTÉGÉE !!` |
| `backend/services/evidence_service.py` | Scoring, stockage, agrégation | Docstring d'en-tête |
| `backend/services/video_evidence_service.py` | Ingestion vidéo | Docstring d'en-tête |
| `frontend/src/pages/appointments/EvidenceDashboard.js` | Rendu preuves | `!! ZONE PROTÉGÉE !!` |
| `frontend/src/pages/invitations/InvitationCheckinSection.js` | UI check-in participant | `INVARIANT` |

### Invariants à ne jamais violer

1. **1 participant = 1 entrée dans le rapport** (pas de fusion, pas d'omission)
2. **Organisateur inclus** (aucun filtre sur `is_organizer`)
3. **3 statuts acceptés** : `accepted`, `accepted_pending_guarantee`, `accepted_guaranteed`
4. **`checked_in` = `manual OR qr OR gps OR video`** (toute preuve vaut check-in)
5. **`participant_id` est la seule clé de jointure** (pas email, pas nom)
6. **Physique et visio utilisent la même structure** `evidence_items`
7. **Les données provider de Niveau 3 ne modifient pas le statut**

### Tests de non-régression

Fichier : `backend/tests/test_evidence_chain.py` (35 tests)

| Catégorie | Tests | Couvre |
|-----------|-------|-------|
| Physique — Org seul | 5 | Check-in, champs, GPS, agrégation |
| Physique — Org + 1 | 5 | Distinction, identités, GPS distinct |
| Physique — Org + 2 | 2 | 3 preuves distinctes, agrégation |
| Physique — Parts seuls | 2 | Org sans preuve, strength=none |
| Invariants physiques | 6 | Anti-doublon, no _id, GPS=checked_in, no leakage, statuts |
| Visio — Org + 1 | 5 | Evidence vidéo, rôle host/attendee, champs |
| Visio — Multi + absent | 4 | 3 présents, 1 absent, late |
| Visio — Partiel | 2 | Courte durée, preuve existante |
| Invariants visio | 4 | Structure, no leakage, provider_role, API |

---

## 5. LIMITATION DE DURÉE — Traitement produit

### A. Documentation interne

La limitation est documentée dans ce fichier (section 1) et dans `EVIDENCE_CHAIN.md` (section 7).

**Formulation de référence** :

> NLYT Proof valide un **check-in temporel** : la preuve qu'un participant identifié
> a déclaré sa présence à un instant précis. Il ne mesure pas la **durée réelle
> de présence**. Pour mesurer la durée, un provider visio (Zoom/Teams) avec
> compte pro est nécessaire.

### B. Interface utilisateur

**Recommandation : oui, l'exprimer dans l'UI.**

Pour un RDV visio sans provider, le rapport de présence devrait afficher :

```
Marie Dupont — Check-in NLYT · 10:00
  ✓ Présence déclarée à 10:00
  ⓘ Durée non mesurée (aucun provider visio connecté)
```

Au lieu de laisser croire que la présence totale est confirmée.

**Implémentation proposée** (non codée ici) :
- Si `source = manual_checkin` et `appointment_type = video` → afficher la mention
- Si `source = video_conference` → la durée est mesurée, pas de mention

### C. Éviter la confusion "check-in validé" vs "présence continue"

| Terme UI | Signification exacte | Quand l'afficher |
|----------|---------------------|------------------|
| **"Présence déclarée"** | Check-in NLYT reçu (physique ou visio) | Toujours si source=manual_checkin |
| **"Présence confirmée"** | Check-in + GPS ou Check-in + Provider | Si GPS close OU video_conference |
| **"Présence continue vérifiée"** | Provider attendance avec durée ≥ 80% du RDV | Uniquement si video + durée longue |
| **"Absent"** | Aucune preuve | 0 evidence_items |

**Règle : ne jamais afficher "Présence confirmée" quand on a uniquement un check-in NLYT sans GPS ni provider.**

---

## 6. OPTIONS FUTURES — Mesure de durée sans provider

### Option A — Heartbeat navigateur

**Principe** : Le navigateur envoie un ping toutes les X minutes tant que l'onglet NLYT est actif.

| Aspect | Détail |
|--------|--------|
| Précision | Bonne (~5min de granularité) |
| Coût technique | Moyen — endpoint `/api/checkin/heartbeat`, stockage périodique |
| Coût UX | Faible — transparent si onglet ouvert |
| Limites | Nécessite onglet actif, ne fonctionne pas si l'utilisateur est sur Zoom en plein écran |
| Fiabilité | Moyenne — l'onglet peut être ouvert sans réelle attention |
| Anti-triche | Faible — un onglet ouvert en arrière-plan envoie des heartbeats |

**Verdict** : Bonne approximation pour "l'utilisateur était sur NLYT", pas pour "l'utilisateur participait activement à la réunion".

### Option B — Confirmation de présence en cours de session

**Principe** : NLYT affiche une notification à T+15min, T+30min, T+45min demandant "Êtes-vous toujours là ?" avec un bouton à cliquer.

| Aspect | Détail |
|--------|--------|
| Précision | Bonne (confirmation humaine explicite) |
| Coût technique | Faible — scheduler + notification UI |
| Coût UX | **Élevé** — interruptif, perçu comme intrusif |
| Limites | L'utilisateur peut cliquer machinalement |
| Fiabilité | Moyenne à bonne — action humaine requise |
| Anti-triche | Moyenne — nécessite une action, mais automatisable |

**Verdict** : Fiable mais friction UX forte. Acceptable pour des RDV à enjeux élevés (forte pénalité financière).

### Option C — Check-out manuel

**Principe** : Le participant clique "Je quitte le RDV" en fin de session.

| Aspect | Détail |
|--------|--------|
| Précision | Dépend de la bonne volonté de l'utilisateur |
| Coût technique | Faible — nouveau endpoint `/api/checkin/checkout` |
| Coût UX | Faible si en fin de RDV, mais oubli très fréquent |
| Limites | Taux d'oubli potentiellement > 50% |
| Fiabilité | Faible — pas de garantie que l'utilisateur le fera |
| Anti-triche | Faible — peut être cliqué sans avoir été présent |

**Verdict** : Trop dépendant du comportement utilisateur. Ne peut pas servir de preuve fiable seul.

### Option D — Ping onglet actif (Page Visibility API)

**Principe** : Utiliser l'API `document.visibilityState` pour détecter si l'onglet NLYT est au premier plan.

| Aspect | Détail |
|--------|--------|
| Précision | Bonne pour "onglet visible", pas pour "utilisateur attentif" |
| Coût technique | Faible — événement JS natif |
| Coût UX | Nul — transparent |
| Limites | L'onglet est en arrière-plan pendant la visio (Zoom/Teams en premier plan) |
| Fiabilité | **Très faible pour la visio** — l'onglet sera caché la plupart du temps |
| Anti-triche | Faible |

**Verdict** : **Inutilisable pour les RDV visio** (l'onglet est toujours masqué pendant l'appel).

### Recommandation

Pour une V2 future, la combinaison la plus pragmatique serait :

1. **Heartbeat (Option A)** comme signal de base (faible friction, bonne couverture)
2. **1 confirmation intermédiaire (Option B allégée)** — une seule à T+30min, pas 3

Cela donnerait :
- Check-in NLYT à T0
- Heartbeats toutes les 5min (silencieux)
- 1 confirmation à T+30min ("Toujours en réunion ?")
- → Estimation de durée : de T0 jusqu'au dernier heartbeat reçu

**Coût estimé** : 2-3 jours de développement. **Ne pas implémenter maintenant.**

---

## 7. FICHIERS DE RÉFÉRENCE

| Document | Chemin | Rôle |
|----------|--------|------|
| Architecture NLYT Proof | `backend/docs/NLYT_PROOF_ARCHITECTURE.md` | Ce fichier |
| Chaîne de preuves technique | `backend/docs/EVIDENCE_CHAIN.md` | Mapping technique complet |
| Tests de non-régression | `backend/tests/test_evidence_chain.py` | 35 tests (physique + visio) |
| PRD | `memory/PRD.md` | Suivi produit |
