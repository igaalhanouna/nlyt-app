# NLYT — Product Requirements Document

## Vision
SaaS de gestion d'assiduité avec garanties financières. NLYT vérifie la présence des participants via des preuves indépendantes.

## Core Requirements
1. Création d'engagements (physique + vidéo) avec paramètres de pénalité
2. Invitation par email avec liens sécurisés
3. Workflow contractuel de modification unanime
4. Garantie financière Stripe (setup mode, guarantee-first)
5. Preuves physiques : GPS, QR, check-in
6. NLYT Proof System : check-in + heartbeat + scoring
7. Import de présences : API auto-fetch
8. Moteur de décision d'assiduité conservateur
9. Page Intégrations (Calendriers + Visioconférence)
10. Emails transactionnels
11. Synchronisation calendrier (Google/Outlook)
12. Verrouillage d'accès jusqu'à validation garantie

## Technical Stack
Frontend: React + TailwindCSS + Shadcn/UI
Backend: FastAPI + Python + MongoDB + slowapi
Email: Resend | Payments: Stripe | Video: Zoom/Teams/Meet API

## Testing
- iteration_59: 25/25 backend (Financial Email Notifications)
- iteration_60: 27/27 (Workspace inline edit)
- iteration_61: 23/23 (Dashboard UX overhaul + remind endpoint)

## Completed — Stripe Connect (All Phases)
- Phase 1-4: Wallet, Connect, Distribution, Payouts ✅
- Phase 5: Notifications email financières ✅

## Completed — UX Cleanup (Mars 2026)
- [x] Suppression /policies et /analytics (placeholders vides)
- [x] Refonte bloc Connect → "Compte bancaire" (zéro mention Stripe visible)
- [x] Bug fix: lien "Modifier mon compte bancaire" inerte en dev mode
- [x] Édition inline workspace (crayon, Enter/Escape, PUT API)
- [x] **Dashboard UX overhaul** — Interface de décision :
  - Header : "Bonjour [Name]" + stats (X engagements | X à risque | €Y engagés)
  - Financial summary : € sécurisé / € à risque
  - Section priorité "À traiter maintenant" (risque élevé <24h)
  - Cartes engagement : titre, date, type, durée, pénalité, barre de progression participants, risk badges (Sécurisé/À surveiller/Risque élevé)
  - Actions par carte : "Voir détails" + "Relancer" (participants en attente)
  - CTA : "Créer un engagement"
  - Backend : POST /api/appointments/{id}/remind (relance email participants pending)

## Roadmap

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
- Webhooks temps réel Zoom/Teams (conditionnel, pas de dépendance)
