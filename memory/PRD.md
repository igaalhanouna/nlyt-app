# NLYT — Product Requirements Document

## Vision
SaaS de gestion d'assiduité avec garanties financières. NLYT vérifie la présence des participants via des preuves indépendantes.

## Technical Stack
Frontend: React + TailwindCSS + Shadcn/UI
Backend: FastAPI + Python + MongoDB + slowapi
Email: Resend | Payments: Stripe | Video: Zoom/Teams/Meet API

## Testing
- iteration_59: 25/25 (Financial Email Notifications)
- iteration_60: 27/27 (Workspace inline edit)
- iteration_61: 23/23 (Dashboard UX overhaul)
- iteration_62: 20/20 (Conflict Detection)

## Completed — Stripe Connect (All Phases)
- Phase 1-4: Wallet, Connect, Distribution, Payouts ✅
- Phase 5: Notifications email financières ✅

## Completed — UX Cleanup (Mars 2026)
- [x] Suppression /policies et /analytics (placeholders vides)
- [x] Refonte bloc Connect → "Compte bancaire"
- [x] Bug fix: lien "Modifier mon compte bancaire" inerte en dev mode
- [x] Édition inline workspace (crayon, Enter/Escape, PUT API)
- [x] Dashboard UX overhaul (interface de décision, impact, risk badges)
- [x] Dashboard orienté Impact (bloc "Votre impact" au lieu de € sécurisé/à risque)
- [x] Titre wizard: "Créer un rendez-vous avec engagement"
- [x] Suppression sélecteur Rôle dans wizard participants
- [x] UX participants compacte (badge numéroté + 3 inputs en ligne)
- [x] **Smart Conflict Detection V1** :
  - Backend: `POST /api/appointments/check-conflicts` (conflit/warning/available + suggestions)
  - Règles: overlap = conflict, <30min buffer = warning
  - Suggestions: 3-5 créneaux (optimal/comfortable/tight)
  - Frontend: panneau alerte dans Step 2, chips cliquables, "Trouver le meilleur créneau"
  - Transparence: "vérifié uniquement sur vos engagements NLYT"
  - V2 teaser: "Google Calendar / Outlook : bientôt"
  - Tests: 20/20 (iteration_62)

## Roadmap

### P2
- Pagination endpoints de liste (API + UI)
- Auto-update calendrier V2 (retry automatique)
- Découpe InvitationPage.js (1409 lignes)

### P3
- Dashboard analytics organisateurs
- Payout charité vers associations
- Templates email externalisés (HTML)
- Pages dédiées par association + leaderboard
- Index MongoDB (performance)
- Conflict Detection V2: FreeBusy Google Calendar + Graph Outlook
