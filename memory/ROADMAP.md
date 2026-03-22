# NLYT — Roadmap

## Completed
- [x] Physical attendance evidence engine (GPS, QR, check-in)
- [x] Conservative attendance decision engine
- [x] Financial guarantees (Stripe Checkout setup mode)
- [x] Contractual modification workflow
- [x] Email notifications with timezone handling
- [x] Express creation button
- [x] Video Conference Attendance Evidence MVP (adapters, ingestion, decision)
- [x] **Meeting API Integration** (auto-create meetings, fetch attendance, CSV upload)
- [x] **Google Meet creation** via Calendar API (WORKING)
- [x] **Integrations page** — Calendars + Video sections with connection status
- [x] **Controlled meeting provider selector** in wizard (enum, connection status, external fallback)

## P0 — Configuration Pending
- [ ] Zoom credentials (ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET)
- [ ] Teams credentials (real MICROSOFT_TENANT_ID, CLIENT_ID, CLIENT_SECRET)

## P1 — Next Up
- [ ] Zoom webhook auto-ingestion (real-time after meeting ends)
- [ ] Teams webhook auto-ingestion
- [ ] Meeting link in calendar sync events (Google/Outlook)
- [ ] Dispute resolution for video appointments

## P2 — Planned
- [ ] Stripe Connect (automatic fund distribution)
- [ ] Calendar auto-update V2 (retry + notification)
- [ ] Video recording evidence (short clip as proof)

## P3 — Backlog
- [ ] Dashboard analytics for organizers
- [ ] Google Meet Activity API (Workspace Enterprise)
- [ ] Advanced dispute resolution
- [ ] Multi-provider per appointment (hybrid)
- [ ] Participant self-service video evidence upload
