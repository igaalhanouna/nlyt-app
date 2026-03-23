# NLYT — Product Requirements Document

## Vision
SaaS de gestion d'assiduité avec garanties financières. NLYT vérifie la présence des participants via des preuves indépendantes, sans dépendance critique à un provider vidéo.

## Architecture cible
Voir **`/app/memory/ARCHITECTURE.md`** pour le document complet post-pivots (Mars 2026).

## Modèle produit (résumé)

### Deux systèmes distincts, jamais mélangés
- **Physique** (`appointment_type: "physical"`) : GPS / QR / Check-in manuel
- **Visio** (`appointment_type: "video"`) : NLYT Proof (check-in + heartbeat + scoring)

### Provider vidéo = support, pas source de vérité
- L'utilisateur gère sa propre visio (coller un lien OU connecter Zoom/Teams/Meet)
- NLYT ne crée pas de réunion centralisée
- Les APIs vidéo sont un bonus secondaire

### Verrouillage d'accès (Guarantee-First Architecture)
- Les participants NE PEUVENT PAS accéder au fichier ICS, au lien de visio, ni au lien NLYT Proof tant qu'ils n'ont pas finalisé leur engagement
- Statuts finalisés : `accepted` (sans garantie) ou `accepted_guaranteed` (garantie payée)
- `accepted_pending_guarantee` = verrouillé
- L'email d'invitation initial N'INCLUT PAS les liens ICS/proof/visio
- L'email de confirmation (avec liens) est envoyé uniquement après finalisation

## Core Requirements
1. Création de RDV (physique + vidéo) avec paramètres de pénalité
2. Invitation par email avec liens sécurisés + lien NLYT Proof (visio uniquement)
3. Workflow contractuel de modification unanime
4. Garantie financière Stripe (setup mode, guarantee-first architecture)
5. Preuves physiques : GPS, QR, check-in (organisateur inclus avec GPS)
6. NLYT Proof System : check-in + heartbeat 30s + scoring 0-100 + validation organisateur
7. Import de présences : API auto-fetch + CSV/JSON (bonus)
8. Moteur de décision d'assiduité conservateur
9. Page Intégrations (Calendriers + Visioconférence)
10. Emails transactionnels avec gestion correcte des timezones
11. Synchronisation calendrier (Google/Outlook)
12. Verrouillage d'accès RDV jusqu'à validation garantie (ICS, visio, proof)

## Technical Stack
Frontend: React + TailwindCSS + Shadcn/UI
Backend: FastAPI + Python + MongoDB + slowapi
Email: Resend | Payments: Stripe | Video: Zoom/Teams/Meet API (mode user)

## Testing
- iteration_59: 25/25 backend (Financial Email Notifications)
- Credentials: testuser_audit@nlyt.app / Test1234!

## Completed — Consolidation Phase (Fév 2026)
- [x] **Centralisation MongoClient** : 64 instances dispersées -> 1 instance unique dans `database.py`. 32 fichiers migrés.
- [x] **Découpe AppointmentDetail.js** : 2701 -> 1592 lignes. 5 sous-composants extraits
- [x] **Nettoyage enums mortes** : `GuaranteeMode.AUTH_NOW` et `AUTH_LATER` supprimés
- [x] **Protection debug.py** : Endpoints protégés par `require_admin`
- [x] **Clarification statut** : `accepted` = sans garantie, `accepted_guaranteed` = avec garantie

## Completed — Earlier
- [x] Fix P0 "Erreur réseau" GPS check-in
- [x] Fix "body stream already read"
- [x] Fix Azure Outlook OAuth
- [x] Rééquilibrage scoring NLYT Proof
- [x] Toutes les features listées dans ARCHITECTURE.md

## Stripe Connect — Progression

### Phase 1 — Wallet + Ledger ✅
- [x] wallet_service.py, wallet_routes.py, auto-création wallet, montants en centimes

### Phase 2 — Stripe Connect Express ✅
- [x] connect_service.py, connect_routes.py, webhooks, WalletPage UI, dev mode

### Phase 3 — Capture + Distribution ✅
- [x] distribution_service.py, symétrie organisateur no-show, hold 15 jours, contestation

### Phase 3b — WalletPage enrichie ✅
- [x] 3 cartes solde, distributions en cours/passées, contestation MVP

### Charity Impact Tracking ✅
- [x] GET /api/wallet/impact, agrégation ledger, ventilation par association, UI WalletPage

### Page publique Impact NLYT ✅
- [x] GET /api/impact, cache scheduler, KPIs globaux, associations, UI /impact

### Phase 4 — Payouts réels ✅
- [x] payout_service.py, Stripe Transfer, débit atomique, webhooks, UI modal payout

### Phase 5 — Notifications email financières ✅ (Fév 2026)
- [x] `financial_emails.py` — Module complet avec 5 types d'emails
- [x] Idempotence via `sent_emails` collection + index unique composite (email_type + reference_id + user_id)
- [x] Non-bloquant via daemon threads (`_send_async`)
- [x] Hook 1: `send_capture_email` → attendance_service._execute_capture_and_distribution
- [x] Hook 2: `send_distribution_created_email` → distribution_service.create_distribution (organizer/participant uniquement)
- [x] Hook 3: `send_distribution_available_email` → distribution_service._finalize_single_distribution (sur completed)
- [x] Hook 4: `send_payout_completed_email` → payout_service._execute_dev_payout + handle_transfer_paid
- [x] Hook 5: `send_payout_failed_email` → payout_service._execute_stripe_transfer + handle_transfer_failed
- [x] Wording correct : "crédit en attente enregistré" (jamais "vous avez reçu")
- [x] Tests: iteration_59 — 25/25 backend (100%)

## Roadmap
### P1
- Webhooks temps réel Zoom/Teams

### P2
- Pagination endpoints de liste (API + UI)
- Auto-update calendrier V2 (retry automatique)
- Découpe InvitationPage.js (1409 lignes)

### P3
- Payout charité vers les associations
- Dashboard analytics organisateurs
- Templates email externalisés (fichiers HTML)
- Pages dédiées par association + Partage social + leaderboard
- Index MongoDB (performance)
