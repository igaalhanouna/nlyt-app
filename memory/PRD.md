# NLYT - Product Requirements Document

## Original Problem Statement
Application SaaS NLYT - Système de rendez-vous avec engagement financier.
- Principes : zéro friction, automatisation maximale, workspace invisible, engagement clair et équitable

## Architecture
- **Frontend**: React.js with Tailwind CSS, shadcn/ui components
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **Email**: Resend API
- **Scheduler**: APScheduler for reminders

## User Personas
1. **Organizer**: Creates appointments, invites participants, manages engagement rules
2. **Participant**: Receives invitations, accepts/declines, can cancel before deadline
3. **Admin/Reviewer**: Reviews disputes, manages platform

## Core Requirements (Static)
- Authentication with email verification
- Auto-workspace creation on signup
- Appointment creation with penalty rules
- Invitation system with secure tokens
- Accept/Decline/Cancel flows
- Cancellation deadline enforcement
- Email notifications (invitation, cancellation, reminders)
- Dual reminder system (deadline + event)

## What's Been Implemented (17 Mars 2026)

### ✅ Completed Features
- Full authentication flow (signup, login, verify, reset password)
- Auto-workspace creation
- Appointment creation wizard with participants
- Invitation token system
- Public invitation page with full details
- Accept/Decline invitation
- Cancel participation by participant
- Cancel appointment by organizer
- Soft delete appointments
- Organizer dashboard with participant statuses
- Workspace switcher
- Deadline reminder service (1h before deadline)
- Event reminder service (10min/1h/1day before RDV)
- Email notifications via Resend
- **ICS file generation** (17 Mars 2026)
  - Endpoint: GET /api/calendar/export/ics/{appointment_id}
  - Description complète avec règles d'engagement
  - Compatible Google Calendar, Outlook, Apple Calendar
  - Bouton sur page détail RDV et page invitation
- **Address Autocomplete** (17 Mars 2026)
  - API BAN (Base Adresse Nationale) - gratuite, sans clé
  - Suggestions en temps réel avec debounce 300ms
  - Stockage lat/lng/place_id en base
  - Intégré au wizard step 2 (type physique)
- **Calendar MVP** (17 Mars 2026)
  - Export ICS individuel: GET /api/calendar/export/ics/{id}
  - Feed ICS subscription: GET /api/calendar/feed/{user_id}.ics
  - Gestion RDV annulés: STATUS:CANCELLED, titre [ANNULÉ], pas d'alarme
  - Boutons frontend sur page détail et page invitation
  - Compatible Google Calendar, Outlook, Apple Calendar
  - **Lien ICS dans email d'invitation** ✅
  - **Email de confirmation après acceptation avec bouton calendrier** ✅

### ⚠️ Partial/Pending
- Stripe payment integration (routes exist, not connected)
- No-show detection
- Dispute resolution flow

## Prioritized Backlog

### P0 - Critical (Before Production)
- [ ] Configure Resend domain for production emails
- [ ] Implement Stripe Setup Intent for financial guarantee
- [ ] No-show detection and penalty capture

### P1 - High Priority
- [ ] Participant dashboard view
- [ ] Calendar integration (Google/Outlook sync)
- [ ] Admin review dashboard testing

### P2 - Medium Priority
- [ ] Multi-language support (dates in French)
- [ ] Timezone-aware reminders
- [ ] Participant limit per appointment
- [ ] Rate limiting on public endpoints

### P3 - Low Priority
- [ ] Analytics dashboard enhancements
- [ ] Export appointments to CSV
- [ ] Webhook integrations

## Next Tasks
1. Stripe payment integration
2. No-show detection workflow
3. Production email domain setup

---

*Last Updated: 17 Mars 2026*
