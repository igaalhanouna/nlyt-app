# NLYT — Product Requirements Document

## Problem Statement
Construire un moteur de détection de présence ultra-conservateur avec collecte de preuves physiques pour une plateforme SaaS de gestion de rendez-vous avec garanties financières.

## Core Architecture
- **Frontend**: React.js, TailwindCSS, Shadcn/UI
- **Backend**: FastAPI, Python, APScheduler
- **Database**: MongoDB
- **Integrations**: Stripe (paiements), Resend (emails), Google/Outlook Calendar, Nominatim (géocodage)

## Key Technical Decisions
- **Timezone**: Strict UTC backend (`YYYY-MM-DDTHH:MM:SSZ`), frontend localise via `formatDateTimeFr()`
- **Modifications**: Flux contractuel avec propositions et acceptation unanime (collection `modification_proposals`)
- **Evidence Engine**: GPS, QR, check-in manuel — scoring conservateur

## What's Implemented ✅
1. Auth complète (inscription, connexion, vérification email, reset password)
2. Gestion de workspaces multi-utilisateurs
3. Wizard de création de RDV (participants, infos, règles, pénalités, révision)
4. Invitations par email avec tokens uniques
5. Page participant (accepter/décliner, garantie Stripe)
6. Synchronisation Google/Outlook Calendar (auto + manuelle)
7. Adresse avec autocomplétion (Nominatim)
8. Moteur d'évaluation de présence (attendance_service)
9. Collecte de preuves physiques (GPS, QR, check-in manuel)
10. Reclassification manuelle par l'organisateur
11. Validation dates passées (création + modification)
12. Flux contractuel de modification de RDV (propositions unanimes)
13. UX bouton "Modifier" sur bloc "Informations générales" (repositionné)
14. Reset coordonnées GPS quand le lieu est modifié via proposition
15. Gestion DST testée et validée
16. Templates de politiques d'engagement
17. Centre de litiges
18. Dashboard analytics de base
19. Stripe Guarantee Impact Assessment : capture window recalculée + flag revalidation si modification majeure (ville, date >24h, type)
20. Visibilité produit du flag `requires_revalidation` : bannière UI (InvitationPage), badge "À reconfirmer" (AppointmentDetail), email de notification (Resend), endpoint de reconfirmation Stripe

## P2 — À venir
- Stripe Connect (répartition automatique des fonds)
- Auto-update calendrier V2 (retry + notification)

## P3 — Backlog
- Dashboard analytics organisateur avancé
- Preuve de présence par vidéo
- Amélioration résolution de litiges

## Key Files
- `/app/frontend/src/pages/appointments/AppointmentDetail.js` — Détail RDV (organisateur)
- `/app/frontend/src/pages/invitations/InvitationPage.js` — Page participant
- `/app/backend/services/modification_service.py` — Logique propositions
- `/app/backend/services/evidence_service.py` — Moteur de preuves
- `/app/backend/services/attendance_service.py` — Évaluation présence
- `/app/frontend/src/utils/dateFormat.js` — Utilitaires dates UTC/local

## Test Reports
- iteration_16: Timezone fix
- iteration_17: Past date creation prevention
- iteration_18: Past date modification prevention
- iteration_19: Modification proposals flow
- iteration_20: UI repositioning of edit button (8/8 passed)
