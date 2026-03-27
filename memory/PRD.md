# NLYT — Product Requirements Document

## Vision
SaaS de gestion de presence avec garanties financieres. Optimisation du "Viral Loop" et funnel d'acquisition.

## Architecture
- **Frontend**: React (Shadcn UI, Tailwind CSS)
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **Paiements**: Stripe
- **Emails**: Resend

## Core Philosophy
- "Same information, different powers" — Participants et Organisateurs partagent les memes ecrans, seules les actions different
- Systeme financier defensif : doute en faveur du participant
- 3 niveaux de decision : AUTO (~55%), REVIEW (~30%), TIMEOUT (~15%)

---

## Implemented Features

### Phase 1 — Core
- [x] Auth (JWT)
- [x] Workspaces
- [x] Appointment CRUD (create, read, update, cancel)
- [x] Invitation system (email, accept, decline)
- [x] Participant management

### Phase 2 — Check-in & Evidence
- [x] Manual check-in (physical)
- [x] GPS check-in with geolocation
- [x] QR code check-in
- [x] Video check-in (Zoom, Teams, Meet)
- [x] NLYT Proof sessions (video identity verification)
- [x] Evidence aggregation & strength scoring
- [x] Symmetric UI (organizer/participant same data, different actions)

### Phase 3 — Financial
- [x] Stripe guarantee setup (SetupIntents)
- [x] Card reuse (1-click guarantee)
- [x] Penalty capture (late/no_show)
- [x] Distribution to beneficiaries (organizer, affected participants, charity, platform)
- [x] Hold period (15 days) for contest
- [x] Financial result display in appointment detail

### Phase 4 — Attendance Evaluation
- [x] Automatic attendance evaluation (scheduler job)
- [x] Outcome mapping: on_time, late, no_show, waived, manual_review
- [x] review_required flag for ambiguous cases
- [x] Reclassification API (PUT /api/attendance/reclassify/{record_id})

### Phase 5 — Dashboard & UX
- [x] Unified timeline dashboard (organizer + participant)
- [x] Action Required sections (participant: pending invites/guarantees, organizer: low engagement alerts)
- [x] Temporal bucketing (upcoming vs past based on end_time)
- [x] Calendar sync (Google, Outlook)
- [x] Event reminders (10min, 1h, 1 day)

### Phase 6 — Audit & Robustness (March 2026)
- [x] Production deployment fix (load_dotenv override removed)
- [x] accepted_pending_guarantee CTA and flow fix
- [x] Penalty logic correction (late beyond tolerance = capture)
- [x] E2E Stripe capture validation
- [x] **Audit des cas litigieux** — full product-oriented audit delivered
- [x] **GPS radius fix** — gps_within_radius now uses actual configured radius, not permissive categories
- [x] **Manual check-in review** — check-in without GPS → review_required=True (no auto-validation on self-declaration)
- [x] **PendingReviewSection** — UI for organizers to review ambiguous attendance (Present/Absent buttons)
- [x] **Review timeout** — auto-release guarantee after 15 days without review (defensive, no penalty)
- [x] **gps_radius_meters persistence** — field now saved in appointment creation/update
- [x] **AttendancePanel reclassify fix** — uses record_id instead of participant_id

---

## Pending / Upcoming Tasks

### P0 — Wallet System
- User wallet for managing balances
- wallet_service.py already has base functions
- Will track: earnings, penalties, payouts

### P1 — Manual Review UI Enhancements
- [x] Dashboard notification for organizers with pending reviews (PendingReviewBanner)
- [x] Page Decisions en attente (/disputes) — centralized review center
- [x] Navbar badge with live counter
- [x] Email notification to organizer when review cases are created
- [ ] Email notification to participants when status is resolved

### P2 — Future
- [ ] Charity Payouts V2 (Stripe Transfers)
- [ ] Webhooks temps reel Zoom/Teams
- [ ] Pages dediees charite & Leaderboard
- [ ] Grace period for tolerance boundary (2min buffer)
- [ ] Causality detection (organizer late → don't penalize participants)

---

## Key Decision Rules (Post-Audit)

### Evidence Strength (Physical)
| Signal | Category |
|--------|----------|
| QR code | Strong signal |
| GPS close (<=500m) | Strong signal |
| GPS nearby (500m-5km) | Weak signal (does NOT count as positive) |
| Manual check-in (no GPS) | Medium BUT review_required=True |

### Financial Flow
| Outcome | review_required | Action |
|---------|-----------------|--------|
| on_time | False | Release guarantee |
| late | False | Capture + distribute |
| no_show | False | Capture + distribute |
| any | True | BLOCKED → organizer review → timeout after 15 days |
| waived | - | No action (released) |

### Timeout Rule
- After 15 days without organizer review → guarantee released without penalty
- decided_by = "system_timeout"
- Runs every 6 hours via scheduler

---

## Test Credentials
- Organizer: igaal.hanouna@gmail.com / OrgTest123!
- Participant: testuser_audit@nlyt.app / TestAudit123!
