# NLYT - Product Requirements Document

## Problem Statement
SaaS application for booking appointments with financial guarantees. Zero friction, maximum automation, clear engagement logic.

## Tech Stack
- **Frontend**: React.js, TailwindCSS, Shadcn UI
- **Backend**: FastAPI, Python, APScheduler
- **Database**: MongoDB
- **Integrations**: Stripe, Resend (Emails), Google Calendar API, Microsoft Graph API (Outlook), Nominatim/OpenStreetMap (geocoding)

## Core Architecture
```
/app/
  backend/
    adapters/
      google_calendar_adapter.py
      outlook_calendar_adapter.py
      ics_generator.py
    routers/
      attendance_routes.py          # Attendance evaluation + reclassification + re-evaluate
      checkin_routes.py             # Check-in (manual, QR, GPS) + evidence API
      calendar_routes.py, appointments.py, invitations.py, webhooks.py
    services/
      attendance_service.py         # No-show detection V2 (with evidence)
      evidence_service.py           # Smart evidence scoring V2 (temporal + geographic + geocoding)
      stripe_guarantee_service.py
      email_service.py
    utils/
      date_utils.py
  frontend/
    src/
      components/
        QRCheckin.js                # QR scanner (camera + manual fallback)
      pages/
        appointments/AppointmentDetail.js   # Evidence dashboard + attendance
        invitations/InvitationPage.js       # Check-in section (3 modes)
      services/api.js
```

## Completed Features

### Phase 0-2 - Core + Stripe + Calendar (DONE)
- User auth, workspaces, appointment wizard, participants, Stripe guarantee, disputes
- Google Calendar + Outlook OAuth, Auto-Sync, Auto-Update
- Timezone fix (IANA→Windows mapping)

### Phase 3 - Attendance Engine V1 (DONE — 2026-03-21)
- Conservative classification, APScheduler every 10min, manual reclassification

### Phase 4 - Evidence-Based Attendance V2 (DONE — 2026-03-21)
- Symmetric check-in, QR code system (neutral, rotating 60s, HMAC-signed), GPS one-shot
- Camera QR scan (html5-qrcode) + manual code fallback
- Evidence aggregation, extended decision engine, re-evaluation

### Phase 5 - Smart Evidence Scoring V2 (DONE — 2026-03-21)
**Temporal consistency:**
- Window: RDV_start - 2h to RDV_end + 1h
- Before window → `too_early` (degrades confidence severely; >24h = always weak)
- After window → `too_late` (degrades confidence)
- In window → `valid` or `valid_late`

**Geographic consistency:**
- close (<500m) → boosts confidence
- nearby (<5km) → acceptable
- far (<50km) → suspicious, degrades
- incoherent (>50km) → catastrophic, always weak

**Smart confidence formula:**
- Base score from source type (QR=3, checkin=2, GPS=1)
- Temporal modifiers: +1 valid, -1/-2/-3 for early/late
- Geographic modifiers: +2 close, +1 nearby, -1 far, -3 incoherent
- Result: high (≥4), medium (≥2), low (<2)

**Geocoding:**
- Forward: Appointment text address → lat/lon (Nominatim, cached in DB)
- Reverse: Check-in GPS → human-readable address (address_label in derived_facts)

**UI enrichments:**
- Temporal badge: "Hors fenêtre (trop tôt/tard)"
- Geographic badge: "Lieu incohérent" / "Lieu suspect"
- Address estimée from reverse geocoding
- Distance du lieu du RDV in km with consistency label
- "Voir sur la carte" (Google Maps link)
- Confidence badge per evidence item

**Testing:** 36/37 tests passed (iteration_14), 1 skipped (no QR evidence)

## Key DB Collections
- `evidence_items`: {evidence_id, appointment_id, participant_id, source, source_timestamp, confidence_score, derived_facts (temporal_consistency, geographic_consistency, distance_km, address_label, ...), created_by}
- `attendance_records`: outcome, decision_basis, evidence_summary, decided_by
- `appointments`: location_latitude, location_longitude, location_geocoded, location_display_name (auto-filled by geocoding)

## Philosophy
1. No proof → no automatic penalty
2. System observes signals, doesn't assume
3. Organizer is not more reliable than participant
4. Any ambiguity → manual_review
5. V1 simple > complex unstable system

## Backlog
- P2: Stripe Connect (fund splits) — NOT to touch until detection is perfect
- P2: Auto-update calendar V2 (retry + notification)
- P3: Organizer analytics dashboard
- P3: Video-based attendance proof
- P3: Dispute resolution improvements
