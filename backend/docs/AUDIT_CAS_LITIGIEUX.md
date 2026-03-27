# AUDIT — Cas Litigieux & Logique de Decision NLYT

> Date : Fevrier 2026
> Scope : attendance_service.py, evidence_service.py, distribution_service.py
> Objectif : Identifier les cas ou le systeme peut se tromper, penaliser injustement, ou produire une decision incomprehensible pour l'utilisateur.

---

## 1. MATRICE COMPLETE DES SCENARIOS

### 1A. RDV PHYSIQUES

| # | Situation | Evidence disponible | Strength | Timing | Outcome | review_required | Action financiere | Risque |
|---|-----------|-------------------|----------|--------|---------|-----------------|-------------------|--------|
| P1 | QR + GPS proche + a l'heure | qr_valid + gps_close | strong | on_time | on_time | Non | Release | SUR |
| P2 | QR + GPS proche + en retard | qr_valid + gps_close | strong | late | late | Non | CAPTURE | SUR |
| P3 | GPS proche seul + a l'heure | gps_close | medium | on_time | on_time | Non | Release | ACCEPTABLE |
| P4 | GPS proche seul + en retard | gps_close | medium | late | late | Non | CAPTURE | ACCEPTABLE |
| P5 | Check-in manuel seul + a l'heure | manual_checkin (sans GPS) | medium | on_time | on_time | Non | Release | DANGEREUX |
| P6 | Check-in manuel seul + en retard | manual_checkin (sans GPS) | medium | late | late | Non | CAPTURE | DANGEREUX |
| P7 | GPS "nearby" (500m-5km) + a l'heure | gps_close (nearby) | medium | on_time | on_time | Non | Release | AMBIGU |
| P8 | GPS "far" (5-50km) seul | gps_far | weak→manual_review | - | manual_review | Oui | BLOQUE | SUR |
| P9 | GPS "incoherent" (>50km) | gps_incoherent | weak | - | manual_review | Oui | BLOQUE | SUR |
| P10 | Aucune evidence, garanti | rien | none | - | manual_review | Oui | BLOQUE | DEADLOCK |
| P11 | Aucune evidence, non garanti | rien | none | - | manual_review | Oui | rien (pas de garantie) | OK |
| P12 | Check-in >2h avant le RDV | temporal=too_early | weak | null | manual_review | Oui | BLOQUE | SUR |
| P13 | Check-in >1h apres la fin | temporal=too_late | degrade | - | variable | Oui | BLOQUE | SUR |
| P14 | Retard de 1min au-dela de la tolerance | GPS ou check-in | medium+ | late | late | Non | CAPTURE | DANGEREUX |

### 1B. RDV VIDEO

| # | Situation | Evidence disponible | Strength | Outcome | review_required | Action financiere | Risque |
|---|-----------|-------------------|----------|---------|-----------------|-------------------|--------|
| V1 | NLYT Proof score >= 55 + a l'heure | nlyt_proof strong | strong | on_time | Non | Release | SUR |
| V2 | NLYT Proof score >= 55 + en retard | nlyt_proof strong | strong | late | Non | CAPTURE | SUR |
| V3 | NLYT Proof score 30-54 | nlyt_proof medium | medium | manual_review | Oui | BLOQUE | SUR |
| V4 | NLYT Proof score < 30 | nlyt_proof weak | weak | no_show | Oui | BLOQUE | SUR |
| V5 | Pas de NLYT Proof, Zoom API on_time | video fallback | medium | on_time | Oui | BLOQUE | DEADLOCK |
| V6 | Pas de NLYT Proof, Google Meet seul | video fallback | weak | manual_review | Oui | BLOQUE | SUR |
| V7 | Pas de NLYT Proof, rien | aucune | weak | no_show | Oui | BLOQUE | DEADLOCK |
| V8 | Check-in manuel seul (RDV video) | manual_checkin | weak (cap) | manual_review | Oui | BLOQUE | SUR |

### 1C. ANNULATIONS & STATUTS SPECIAUX

| # | Situation | Outcome | review_required | Action financiere | Risque |
|---|-----------|---------|-----------------|-------------------|--------|
| S1 | Annulation dans les delais | waived | Non | Release | SUR |
| S2 | Annulation hors delais (timestamp OK) | no_show | Non | CAPTURE | SUR |
| S3 | Annulation hors delais (pas de timestamp) | no_show | Oui | BLOQUE | SUR |
| S4 | Declined | waived | Non | rien | SUR |
| S5 | Invited (jamais repondu) | waived | Non | rien | SUR |
| S6 | guarantee_released | waived | Non | rien | SUR |

---

## 2. CLASSIFICATION : SUR / AMBIGU / DANGEREUX

### CAS SURS — Automatique OK (~55% des cas estimes)

Le systeme decide correctement et la decision est comprehensible :

- **QR + GPS + timing clair** : preuve multiple, decision indiscutable
- **NLYT Proof >= 55** : presence video prouvee par le systeme
- **Annulation dans les delais** : regle explicite, pas d'ambiguite
- **Annulation tardive avec timestamp** : regle explicite
- **Declined / Invited / guarantee_released** : pas d'engagement = pas de penalite
- **GPS incoherent (>50km)** : flagge correctement en review
- **Check-in trop tot (>2h)** : flagge correctement en review

### CAS AMBIGUS — Doivent etre revus (~25% des cas estimes)

La decision n'est pas fausse mais pourrait etre contestee :

- **P7 — GPS "nearby" (500m-5km)** : Le systeme compte 5km comme "GPS valide". Un utilisateur a 4.9km du lieu est auto-valide. Le champ `gps_within_radius: True` affiche un faux sentiment de precision alors que le vrai rayon configure est 200m.
- **P14 — Retard a la limite de la tolerance** : 10min01 de retard avec 10min de tolerance = penalite pleine. Pas de zone tampon. Coupure binaire.
- **V5 — Zoom dit "present" mais pas de NLYT Proof** : Le systeme dit `on_time` mais force `review_required: True`. Resultat positif mais bloque financierement.
- **Organisateur ET participant en retard** : Chacun evalue independamment. Si l'organisateur etait en retard de 20min et le participant de 15min, le participant est penalise meme si c'est l'organisateur qui a cause le retard.

### CAS DANGEREUX — Risque d'erreur produit (~20% des cas estimes)

La decision est potentiellement injuste ou incomprehensible :

---

#### DANGER 1 : Check-in manuel sans GPS = auto-valide (P5)

| | Detail |
|--|--------|
| **Situation** | Participant clique "Confirmer ma presence" sans GPS active |
| **Donnees** | 1 seul signal : `manual_checkin`. Aucune coordonnee geographique. |
| **Decision actuelle** | strength=medium, timing=on_time → `on_time`, review_required=**False** |
| **Action financiere** | Garantie **liberee automatiquement** |
| **Probleme** | La personne peut cliquer depuis chez elle. Aucune verification de localisation. Le systeme la declare "presente" sur la seule base d'un clic. |
| **Comprehensible pour l'utilisateur ?** | L'organisateur ne comprendra pas pourquoi quelqu'un est marque "present" sans preuve. |
| **Defensible ?** | Non. Un simple clic ne constitue pas une preuve de presence physique. |

#### DANGER 2 : Check-in manuel en retard = auto-penalise (P6)

| | Detail |
|--|--------|
| **Situation** | Participant clique "Confirmer ma presence" 15min apres le debut (tolerance: 10min), sans GPS |
| **Donnees** | 1 seul signal : `manual_checkin`. Timing = late. |
| **Decision actuelle** | strength=medium, timing=late → `late`, review_required=**False** |
| **Action financiere** | Garantie **capturee automatiquement** — penalite prelevee |
| **Probleme** | La personne etait peut-etre presente a l'heure mais a clique en retard. Ou elle n'etait pas la du tout. Le systeme ne peut pas distinguer les deux, mais penalise quand meme automatiquement. |
| **Comprehensible ?** | "J'ai clique 5 minutes trop tard et j'ai ete penalise de 25EUR ?" → incomprehensible |
| **Defensible ?** | Non. Prelevement base sur 1 clic auto-declare. Inacceptable. |

#### DANGER 3 : Deadlock financier — review_required sans UI (P10, V5, V7)

| | Detail |
|--|--------|
| **Situation** | Participant garanti, a fait un check-in mais evidence faible, OU aucune evidence |
| **Donnees** | Variables |
| **Decision actuelle** | `manual_review` ou `no_show` avec review_required=**True** |
| **Action financiere** | **RIEN** — ni capture, ni release. Argent bloque indefiniment. |
| **Probleme** | L'API de reclassification existe (`PUT /api/attendance/reclassify/{id}`) mais il n'y a AUCUNE interface frontend. L'organisateur ne sait pas qu'il doit agir. Le participant ne sait pas que sa garantie est en suspens. |
| **Comprehensible ?** | "Mon RDV est termine depuis 3 semaines et ma garantie n'est toujours pas liberee" → incomprehensible |
| **Defensible ?** | Non. Deadlock silencieux. |

#### DANGER 4 : GPS "nearby" trop permissif + label trompeur (P7)

| | Detail |
|--|--------|
| **Situation** | GPS a 1.5km du lieu avec rayon configure a 200m |
| **Donnees** | distance_meters=1452, gps_radius_meters=200, gps_within_radius=True |
| **Decision actuelle** | `gps_within_radius: True` car "nearby" (< 5km) est traite comme "valide" |
| **Probleme double** | 1) Le label `gps_within_radius: True` est factuellement faux (1452m > 200m). 2) Le signal GPS "nearby" (jusqu'a 5km) compte comme preuve positive de presence. |
| **Comprehensible ?** | L'organisateur voit "GPS dans le rayon : oui" alors que la personne est a 1.5km. |
| **Defensible ?** | Non. Le rayon affiche est 200m, la personne est a 1.5km, mais le systeme dit "dans le rayon". |

---

## 3. LE DEADLOCK `review_required`

### Comment ca marche aujourd'hui

```
evaluate_participant() → outcome + review_required
       ↓
_process_financial_outcomes()
       ↓
if review_required == True → SKIP (ligne 633)
       → ni capture, ni release
       → argent bloque INDEFINIMENT
```

### Qui est concerne ?

Tout participant dont l'evaluation produit `review_required: True` :
- Evidence faible/nulle (physique)
- NLYT Proof score 30-54 (video)
- Video API fallback sans NLYT Proof
- Annulation sans timestamp
- GPS incoherent

### Quel est le probleme produit ?

1. **L'organisateur ne sait pas** qu'il doit agir (pas de notification, pas d'UI)
2. **Le participant ne sait pas** que sa garantie est en suspens
3. **L'API existe** (`GET /api/attendance/pending-reviews/list` + `PUT /api/attendance/reclassify/{id}`) mais le frontend ne l'utilise pas
4. **Pas de timeout** : si l'organisateur ne fait rien, l'argent reste bloque a vie

### Combien de cas sont concernes ?

En estimant :
- RDV physique sans QR : ~30% des cas (check-in manuel seul = medium = pas bloque, mais...)
- RDV video sans NLYT Proof : ~40% des cas → tous bloques
- Evidence faible ou absente : ~15% des cas → tous bloques

→ **Environ 25-40% des evaluations finissent en review_required: True avec deadlock financier.**

---

## 4. LE BUG GPS RADIUS

### Code actuel (evidence_service.py)

```python
# Ligne 440 et 559
derived_facts["gps_within_radius"] = geographic['consistency'] in ('close', 'nearby')
derived_facts["gps_radius_meters"] = appointment.get('gps_radius_meters', 200)
```

### Seuils geographiques actuels

| Categorie | Distance | Traite comme preuve positive ? |
|-----------|----------|-------------------------------|
| close | 0-500m | Oui |
| nearby | 500m-5km | Oui (!) |
| far | 5km-50km | Non |
| incoherent | >50km | Non |

### Probleme

Le `gps_within_radius` ne compare JAMAIS la distance au rayon configure (`gps_radius_meters`). Il utilise uniquement les categories "close" et "nearby" qui ont des seuils fixes.

**Consequence** : Un RDV avec rayon=200m traite une personne a 4.9km exactement comme une personne a 50m. Les deux obtiennent `gps_within_radius: True`.

### Fix recommande

```python
# Remplacer :
derived_facts["gps_within_radius"] = geographic['consistency'] in ('close', 'nearby')

# Par :
actual_radius = appointment.get('gps_radius_meters', DEFAULT_GPS_RADIUS_METERS)
derived_facts["gps_within_radius"] = (
    geographic['distance_meters'] is not None 
    and geographic['distance_meters'] <= actual_radius
)
```

Et dans `aggregate_evidence()`, separer `has_gps_close` (categorie "close" ≤500m) de `has_gps_nearby` (500m-5km), avec traitement differencie :
- `close` = signal positif fort
- `nearby` = signal positif faible (devrait decoter la strength)

---

## 5. RECOMMANDATION PRODUIT

### Principe : 3 niveaux de decision

| Niveau | Critere | Action | % estime |
|--------|---------|--------|----------|
| **AUTO** | Evidence strong/medium + timing clair + aucune anomalie geo | Decision finale automatique (capture ou release) | ~55% |
| **REVIEW** | Evidence faible, timing ambigu, GPS suspect | Organisateur doit trancher via UI simple | ~30% |
| **TIMEOUT** | Review non traite apres X jours | Regle par defaut s'applique | ~15% |

### Changements necessaires (par priorite)

#### PRIORITE 1 — Securiser les cas dangereux (avant Wallet)

1. **Check-in manuel sans GPS = review_required**
   - Si `strength == medium` ET le seul signal est `manual_checkin` (pas de GPS, pas de QR) → forcer `review_required: True`
   - Impact : empeche l'auto-validation sur un simple clic
   - **Simple** : 5 lignes de code dans `evaluate_participant()`

2. **Fix GPS radius**
   - `gps_within_radius` doit utiliser le vrai rayon configure
   - "nearby" (500m-5km) doit decoter la strength, pas la valider
   - **Simple** : 10 lignes dans `evidence_service.py`

3. **Timeout par defaut pour review_required**
   - Si review non traite apres 15 jours → appliquer regle par defaut :
     - Evidence medium → on_time (doute en faveur du participant)
     - Evidence weak/none → no_show
   - Aligne avec le `HOLD_DAYS = 15` de distribution_service
   - **Simple** : 15 lignes dans le scheduler

#### PRIORITE 2 — UI minimale de review (avec Wallet)

1. **Notification organisateur** : section "A traiter" dans le dashboard quand des records sont en review_required
2. **Ecran de reclassification** : pour chaque participant en review, afficher l'evidence disponible et 3 boutons : "Present" / "Absent" / "Garder en review"
3. **Notification participant** : email quand le statut est tranche

#### PRIORITE 3 — Ameliorations futures

1. **Zone tampon retard** : ajouter 2 minutes de grace au-dela de la tolerance (buffer de latence reseau/GPS)
2. **Detection causalite** : si organisateur est en retard, ne pas penaliser les participants arrives apres l'organisateur
3. **Historique d'audit** : chaque reclassification est deja tracee (`previous_outcome`, `decided_by`, `notes`)

---

## 6. RESUME EXECUTIF

### Ce qui marche bien
- La hierarchie des preuves (QR > GPS > check-in) est coherente
- Les cas d'annulation sont bien geres
- Le systeme video (NLYT Proof) est correctement conservateur
- L'idempotence financiere (pas de double capture) est solide
- Le contest de distribution (hold 15j) protege l'utilisateur

### Ce qui doit changer AVANT la mise en production financiere

| # | Probleme | Severite | Effort |
|---|----------|----------|--------|
| 1 | Check-in manuel seul = auto-valide | CRITIQUE | 5 lignes |
| 2 | GPS "nearby" trop permissif + label trompeur | MAJEUR | 10 lignes |
| 3 | Deadlock review_required sans UI ni timeout | CRITIQUE | 15 lignes (timeout) + UI (P2) |
| 4 | Retard a ±1min de la tolerance = binaire | MINEUR | 3 lignes |

### Decision a prendre

Avant d'implementer quoi que ce soit, 2 questions pour vous :

**Question A** : Pour le check-in manuel sans GPS sur RDV physique → doit-il :
- (a) Toujours passer en review (plus strict, moins fluide)
- (b) Etre accepte mais avec confidence "low" et signal dans le dashboard (plus fluide, moins sur)

**Question B** : Pour le timeout des reviews non traites → la regle par defaut doit-elle :
- (a) Favoriser le participant : evidence medium → on_time (doute en sa faveur)
- (b) Etre stricte : evidence < strong → no_show
- (c) Liberer la garantie sans penalite dans tous les cas (position la plus defensive)

---

*Document genere a partir de l'analyse du code source. Tous les numeros de lignes referent aux fichiers au moment de l'audit.*
