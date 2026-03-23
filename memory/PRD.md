# NLYT — Product Requirements Document

## Vision
SaaS de gestion d'assiduité avec garanties financières. NLYT vérifie la présence des participants via des preuves indépendantes, sans dépendance critique à un provider vidéo.

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
- iteration_60: 27/27 backend+frontend (Workspace inline edit)
- Credentials: testuser_audit@nlyt.app / Test1234!

## Completed — Stripe Connect (All Phases)
- Phase 1: Wallet + Ledger ✅
- Phase 2: Stripe Connect Express ✅
- Phase 3: Capture + Distribution ✅
- Phase 3b: WalletPage enrichie ✅
- Charity Impact Tracking ✅
- Page publique Impact NLYT ✅
- Phase 4: Payouts réels ✅
- Phase 5: Notifications email financières ✅

## Completed — UX Cleanup (Mars 2026)
- [x] Suppression /policies et /analytics (placeholders vides)
- [x] Refonte bloc Connect → "Compte bancaire" (zéro mention Stripe visible)
- [x] Bug fix: lien "Modifier mon compte bancaire" inerte en dev mode → toast informatif
- [x] Édition inline workspace : icône crayon, input nom + textarea description, Enter/Escape, sauvegarde PUT, "Ajouter une description" cliquable

## Roadmap
### P1
- Webhooks temps réel Zoom/Teams

### P2
- Pagination endpoints de liste (API + UI)
- Auto-update calendrier V2 (retry automatique)
- Découpe InvitationPage.js (1409 lignes)

### P3
- Dashboard analytics organisateurs (avec vraie spec + données ledger)
- Payout charité vers les associations
- Templates email externalisés (fichiers HTML)
- Pages dédiées par association + Partage social + leaderboard
- Index MongoDB (performance)
