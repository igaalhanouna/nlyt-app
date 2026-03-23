# NLYT — Product Requirements Document

## Vision
SaaS de gestion d'assiduité avec garanties financières. NLYT vérifie la présence des participants via des preuves indépendantes, sans dépendance critique à un provider vidéo.

## Architecture cible
Voir **`/app/memory/ARCHITECTURE.md`** pour le document complet post-pivots (Mars 2026).

## Modèle produit (résumé)

### Deux systèmes distincts, jamais mélangés
- **Physique** (`appointment_type: "physical"`) → GPS / QR / Check-in manuel
- **Visio** (`appointment_type: "video"`) → NLYT Proof (check-in + heartbeat + scoring)

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
- iteration_40: 22/22 backend + 15/15 frontend (NLYT Proof + Provider mode)
- iteration_41: 8/8 backend + 9/9 frontend (Stripe webhook fix + Access control)
- iteration_42: 8/8 backend + 6/6 frontend (Organisateur proof bypass fix)
- Credentials: testuser_audit@nlyt.app / Test1234!

## Completed
- [x] Refactoring Visio provider (mode user)
- [x] Séparation stricte physique/vidéo
- [x] GPS organisateur pour check-in physique
- [x] Document ARCHITECTURE.md
- [x] NLYT Proof dans le moteur de décision
- [x] Champ "Visio Display Name" au check-in
- [x] Fix Outlook OAuth (Azure App ID)
- [x] Logique short-notice (cap deadlines, skip reminders)
- [x] Point d'entrée Visio unifié (participants + organisateur via NLYT Proof)
- [x] Fix bug sync/async webhook Stripe (P0)
- [x] Verrouillage accès RDV (ICS/visio/proof) jusqu'à garantie validée (P0)
- [x] API: meeting_join_url masqué pour participants non engagés
- [x] Email confirmation avec proof_link + appointment_timezone après webhook Stripe
- [x] Organisateur passe par NLYT Proof (suppression bypass direct visio)
- [x] Backend proof: retour meeting_host_url pour organisateur, join_url pour participant

## Roadmap
### P1
- Stripe Connect (distribution automatique des fonds)
- Calcul video_api_points (30pts bonus) dans le scoring NLYT Proof
- Webhooks temps réel Zoom/Teams

### P2
- Pagination endpoints de liste
- Auto-update calendrier V2 (retry automatique)

### P3
- Dashboard analytics organisateurs
- Refactoring MongoDB connection pooling
