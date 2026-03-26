# AUDIT COMPLET NLYT - 17 Mars 2026

## RÉSUMÉ EXÉCUTIF

L'application NLYT est **fonctionnelle end-to-end** avec quelques points d'attention mineurs. Les flux critiques (création RDV, invitations, acceptation, annulation, rappels) sont opérationnels.

---

## 1. POINTS SOLIDES ✅

### Architecture
- **Structure claire** : Séparation backend (FastAPI) / frontend (React) / services bien organisés
- **MongoDB** : Utilisation correcte avec projection `{"_id": 0}` pour éviter les erreurs de sérialisation
- **Scheduler APScheduler** : Deux jobs séparés bien configurés (deadline reminders + event reminders)

### Authentification
- ✅ Signup avec création automatique de workspace
- ✅ Login avec vérification email obligatoire
- ✅ Reset password fonctionnel
- ✅ JWT bien implémenté avec middleware d'authentification
- ✅ Resend verification avec rate limiting (2 min)

### Workspace
- ✅ Auto-création invisible à l'inscription
- ✅ Multi-workspace avec switcher fonctionnel
- ✅ Membership système en place

### Rendez-vous
- ✅ Création via wizard avec participants step 1
- ✅ Invitations envoyées automatiquement à la création
- ✅ Policy snapshot généré (contrat)
- ✅ Commission 30% bien configurée (platform_commission_percent)
- ✅ Event reminders configurables (10min/1h/1jour)

### Invitations
- ✅ Tokens sécurisés UUID
- ✅ Page publique `/invitation/:token` fonctionnelle
- ✅ Accept / Decline fonctionnels
- ✅ Dashboard montre statuts des participants
- ✅ Gestion RDV annulé/supprimé sur page invitation

### Participants Statuts
- ✅ `invited` → `accepted` → `cancelled_by_participant`
- ✅ `invited` → `declined`
- ✅ Notification organizer quand participant annule

### Rappels
- ✅ **Deadline reminder** : 1h avant deadline d'annulation (reminder_service.py)
- ✅ **Event reminders** : 10min/1h/1jour avant RDV (event_reminder_service.py)
- ✅ Deux systèmes séparés comme prévu
- ✅ Jobs scheduler toutes les 5min (deadline) et 2min (event)

### Annulation / Suppression
- ✅ Cancel = statut `cancelled` + notifications participants
- ✅ Delete = soft delete (`status: deleted`) + notifications
- ✅ Invitations bloquées si RDV annulé ("Ce rendez-vous n'est plus actif")
- ✅ RDV supprimés exclus de la liste

---

## 2. POINTS À CORRIGER ⚠️

### P1 - CRITIQUE

#### 2.1 Email Resend Mode Test
- **Problème** : La clé Resend est en mode test, limite l'envoi à `igaal@hotmail.com` uniquement
- **Impact** : Aucun email ne sera envoyé à d'autres adresses
- **Solution** : Vérifier un domaine sur resend.com/domains pour production

#### 2.2 Incohérence FRONTEND_URL
- **Problème** : La variable d'environnement `FRONTEND_URL` dans backend/.env doit correspondre à l'URL déployée
- **Impact** : Les liens dans les emails pourraient pointer vers la mauvaise URL
- **Solution** : S'assurer que `FRONTEND_URL=https://fervent-feynman-6.preview.emergentagent.com` est cohérent partout

### P2 - MODÉRÉ

#### 2.3 Participants router utilise request.base_url
- **Fichier** : `/app/backend/routers/participants.py` ligne 57-58
- **Problème** : Utilise `request.base_url` au lieu de `FRONTEND_URL` pour les liens d'invitation
- **Impact** : Liens incorrects si appelé via proxy ou URL différente
- **Code actuel** :
```python
base_url = str(request.base_url).rstrip('/')
invitation_link = f"{base_url}/accept-invitation/{invitation_token}"
```
- **Solution** : Utiliser la même logique que `appointments.py` avec `get_frontend_url(request)`

#### 2.4 Double endpoint d'invitation
- **Routes** : `/accept-invitation/:token` et `/invitation/:token`
- **Impact** : Confusion potentielle
- **Recommandation** : Utiliser uniquement `/invitation/:token` (plus complet)

### P3 - MINEUR

#### 2.5 Statut cancelled_by_participant pas dans ParticipantStatus enum
- **Fichier** : `/app/backend/models/schemas.py`
- **Problème** : L'enum `ParticipantStatus` ne contient pas `cancelled_by_participant`
- **Impact** : Incohérence entre code et schéma (fonctionne car MongoDB accepte tout)
- **Solution** : Ajouter `CANCELLED_BY_PARTICIPANT = "cancelled_by_participant"` à l'enum

#### 2.6 Format date en anglais sur page invitation
- **Observation** : "Thursday 19 March 2026" au lieu de "Jeudi 19 mars 2026"
- **Impact** : Expérience utilisateur incohérente (reste de l'UI en français)
- **Solution** : Utiliser `toLocaleDateString('fr-FR')` côté frontend

---

## 3. RISQUES TECHNIQUES 🔴

### 3.1 Race Condition sur Scheduler
- **Scénario** : Si deux instances du backend tournent, les rappels peuvent être envoyés en double
- **Atténuation actuelle** : Flag `reminder_sent` et `event_reminders_sent` dans DB
- **Recommandation** : Ajouter un lock distribué ou utiliser un service de queue (Redis/RabbitMQ) en prod

### 3.2 Pas de validation timezone
- **Problème** : Les dates sont stockées en UTC mais pas de gestion explicite des timezones utilisateur
- **Impact** : Rappels pourraient arriver à des heures inattendues
- **Recommandation** : Stocker et utiliser le timezone du participant pour les rappels

### 3.3 Pas de limite sur participants
- **Problème** : Aucune limite de participants par RDV
- **Impact** : Potentiel abus/spam
- **Recommandation** : Ajouter une limite configurable (ex: 20 participants max)

---

## 4. RISQUES PRODUIT 🟡

### 4.1 Annulation après deadline
- **Comportement actuel** : Message "Le délai d'annulation est dépassé"
- **Question** : Que se passe-t-il si le participant ne vient vraiment pas ?
- **Manquant** : Flux de capture de pénalité (no-show detection + Stripe capture)

### 4.2 Paiement non implémenté
- **Observation** : Routes `/api/payments/*` existent mais le flux Stripe n'est pas connecté
- **Impact** : L'engagement financier n'est pas réel actuellement
- **Fichiers concernés** : `payment_service.py`, `routers/payments.py`

### 4.3 Disputes
- **Observation** : Système de disputes existe (`routers/disputes.py`)
- **État** : Non testé dans cet audit
- **Recommandation** : Tester le flux complet disputes avant production

---

## 5. EDGE CASES VALIDÉS ✅

| Scénario | Résultat |
|----------|----------|
| Accepter invitation RDV annulé | ❌ Bloqué - "Ce rendez-vous n'est plus actif" |
| Annuler participation déjà annulée | ❌ Bloqué - "Seule une invitation acceptée peut être annulée" |
| Double accept | ❌ Bloqué - "Vous avez déjà répondu à cette invitation" |
| Accept après début RDV | ❌ Bloqué - "Ce rendez-vous a déjà commencé" |
| Supprimer RDV avec participants | ✅ Soft delete + notifications envoyées |
| Lister RDV supprimés | ✅ Exclus de la liste (status != deleted) |

---

## 6. TESTS EFFECTUÉS

### Backend API
- ✅ Health check
- ✅ Register (avec échec email attendu en mode test)
- ✅ Login
- ✅ List workspaces
- ✅ Create appointment avec participants
- ✅ List appointments
- ✅ Get invitation (public)
- ✅ Accept invitation
- ✅ Cancel participation
- ✅ Cancel appointment (organizer)
- ✅ Delete appointment

### Frontend
- ✅ Landing page
- ✅ Sign in + redirect dashboard
- ✅ Dashboard avec liste RDV et statuts
- ✅ Page invitation (RDV actif)
- ✅ Page invitation (RDV annulé)

---

## 7. RECOMMANDATIONS IMMÉDIATES

1. **Avant mise en prod** : Vérifier domaine Resend pour emails
2. **Priorité haute** : Implémenter le flux Stripe complet
3. **Corriger** : Uniformiser l'utilisation de `FRONTEND_URL` partout
4. **Ajouter** : `cancelled_by_participant` à l'enum ParticipantStatus

---

## 8. PROCHAINE FEATURE SUGGÉRÉE

En fonction de la roadmap produit, les candidats logiques seraient :
- **Stripe Setup Intent** : Pour l'engagement financier réel
- **No-show detection** : Marquage automatique + capture pénalité
- **Dashboard participant** : Vue dédiée pour les participants invités

---

*Audit réalisé le 17 Mars 2026*
