"""
VALIDATION COMPLÈTE — Bug Timezone (P0)

3 volets de vérification demandés par l'utilisateur :
1. Vérification réelle : RDV à 15:00 → payload calendrier à 15:00
2. Vérification DST : transitions heure d'été/hiver
3. Format ISO : aucune datetime naive dans le flux

Ce fichier simule le flux END-TO-END :
  Frontend (datetime-local) → Backend (normalize_to_utc) → MongoDB (UTC Z)
  → _build_event_data → Outlook/Google API payload → affichage calendrier
"""
import pytest
import sys
sys.path.insert(0, '/app/backend')

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from routers.calendar_routes import _build_event_data
from utils.date_utils import normalize_to_utc, parse_iso_datetime
from adapters.outlook_calendar_adapter import to_windows_timezone
from adapters.ics_generator import ICSGenerator


# ═══════════════════════════════════════════════════════════════
# VOLET 1 : VÉRIFICATION RÉELLE — RDV à 15:00
# ═══════════════════════════════════════════════════════════════

class TestRealVerification:
    """Simule un utilisateur à Paris qui crée un RDV à 15:00."""

    def _simulate_frontend(self, local_year, local_month, local_day, local_hour, local_minute, tz_name="Europe/Paris"):
        """Simule JavaScript: new Date("YYYY-MM-DDTHH:MM").toISOString()"""
        tz = ZoneInfo(tz_name)
        local_dt = datetime(local_year, local_month, local_day, local_hour, local_minute, tzinfo=tz)
        utc_dt = local_dt.astimezone(timezone.utc)
        # JavaScript toISOString() format
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def _simulate_full_flow(self, local_hour, local_month, local_day, tz_name="Europe/Paris"):
        """Full E2E: frontend → backend → calendar API → expected display time."""
        # 1. Frontend converts local time to UTC
        frontend_utc = self._simulate_frontend(2026, local_month, local_day, local_hour, 0, tz_name)

        # 2. Backend normalizes (should pass through Z strings)
        stored_utc = normalize_to_utc(frontend_utc)

        # 3. Build calendar event data
        appointment = {
            "title": f"RDV {local_hour}:00",
            "start_datetime": stored_utc,
            "duration_minutes": 60,
            "cancellation_deadline_hours": 24,
            "tolerated_delay_minutes": 15,
            "penalty_amount": 50,
            "penalty_currency": "EUR",
        }
        event = _build_event_data(appointment, calendar_tz="Europe/Paris")

        # 4. Verify: what the calendar API receives
        api_dt_str = event["start_datetime"]
        api_tz = event["timeZone"]

        # 5. What the user sees in their calendar
        # Calendar API: datetime in api_tz → display in user's timezone
        if api_tz == "UTC":
            api_dt = datetime.strptime(api_dt_str, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        else:
            raise AssertionError(f"Expected UTC timezone, got {api_tz}")

        display_dt = api_dt.astimezone(ZoneInfo(tz_name))
        return display_dt

    def test_rdv_15h_winter_paris(self):
        """User crée RDV à 15:00 Paris (janvier = CET, UTC+1).
        Calendar doit afficher 15:00 Paris."""
        display = self._simulate_full_flow(local_hour=15, local_month=1, local_day=15)
        assert display.hour == 15, f"Expected 15:00 Paris, got {display.hour}:00"

    def test_rdv_15h_summer_paris(self):
        """User crée RDV à 15:00 Paris (juillet = CEST, UTC+2).
        Calendar doit afficher 15:00 Paris."""
        display = self._simulate_full_flow(local_hour=15, local_month=7, local_day=15)
        assert display.hour == 15, f"Expected 15:00 Paris, got {display.hour}:00"

    def test_rdv_09h_winter_paris(self):
        """RDV 9:00 Paris en hiver."""
        display = self._simulate_full_flow(local_hour=9, local_month=2, local_day=10)
        assert display.hour == 9

    def test_rdv_20h_summer_paris(self):
        """RDV 20:00 Paris en été."""
        display = self._simulate_full_flow(local_hour=20, local_month=8, local_day=5)
        assert display.hour == 20

    def test_rdv_15h_new_york(self):
        """User à New York crée RDV à 15:00 EST (hiver)."""
        display = self._simulate_full_flow(local_hour=15, local_month=1, local_day=15, tz_name="America/New_York")
        assert display.hour == 15

    def test_rdv_15h_tokyo(self):
        """User à Tokyo crée RDV à 15:00 JST."""
        display = self._simulate_full_flow(local_hour=15, local_month=6, local_day=15, tz_name="Asia/Tokyo")
        assert display.hour == 15

    def test_rdv_midnight_paris(self):
        """Edge case: RDV à 00:00 Paris en hiver → 23:00 UTC jour précédent."""
        frontend_utc = self._simulate_frontend(2026, 1, 15, 0, 0)
        # 00:00 CET = 23:00 UTC (Jan 14)
        assert "2026-01-14T23:00:00.000Z" == frontend_utc

        appointment = {
            "title": "Minuit",
            "start_datetime": frontend_utc,
            "duration_minutes": 60,
            "cancellation_deadline_hours": 24,
            "tolerated_delay_minutes": 0,
            "penalty_amount": 0,
            "penalty_currency": "EUR",
        }
        event = _build_event_data(appointment)
        assert event["timeZone"] == "UTC"
        assert event["start_datetime"] == "2026-01-14T23:00:00"

        # Verify display
        api_dt = datetime(2026, 1, 14, 23, 0, 0, tzinfo=timezone.utc)
        display = api_dt.astimezone(ZoneInfo("Europe/Paris"))
        assert display.hour == 0
        assert display.day == 15


# ═══════════════════════════════════════════════════════════════
# VOLET 2 : VÉRIFICATION DST — Transitions heure d'été/hiver
# ═══════════════════════════════════════════════════════════════

class TestDSTTransitions:
    """
    En 2026 pour Europe/Paris :
    - Passage à l'heure d'été : dimanche 29 mars à 02:00 → 03:00 (CET → CEST)
    - Retour à l'heure d'hiver : dimanche 25 octobre à 03:00 → 02:00 (CEST → CET)
    """

    def _full_flow(self, year, month, day, hour, minute=0, tz_name="Europe/Paris"):
        """Simulate full frontend→calendar flow, return display hour in tz_name."""
        tz = ZoneInfo(tz_name)
        local_dt = datetime(year, month, day, hour, minute, tzinfo=tz)
        utc_dt = local_dt.astimezone(timezone.utc)
        frontend_utc = utc_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        stored = normalize_to_utc(frontend_utc)
        appointment = {
            "title": "DST Test",
            "start_datetime": stored,
            "duration_minutes": 60,
            "cancellation_deadline_hours": 0,
            "tolerated_delay_minutes": 0,
            "penalty_amount": 0,
            "penalty_currency": "EUR",
        }
        event = _build_event_data(appointment)
        assert event["timeZone"] == "UTC"

        api_dt = datetime.strptime(event["start_datetime"], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        display = api_dt.astimezone(ZoneInfo(tz_name))
        return display

    # ── Avant le passage à l'heure d'été (28 mars 2026, encore CET) ──

    def test_before_spring_forward_10h(self):
        """28 mars 10:00 CET (UTC+1) → doit afficher 10:00."""
        display = self._full_flow(2026, 3, 28, 10)
        assert display.hour == 10

    def test_before_spring_forward_23h(self):
        """28 mars 23:00 CET → doit afficher 23:00."""
        display = self._full_flow(2026, 3, 28, 23)
        assert display.hour == 23

    # ── Jour du passage à l'heure d'été (29 mars 2026) ──

    def test_spring_forward_day_01h(self):
        """29 mars 01:00 CET (avant le saut) → doit afficher 01:00."""
        display = self._full_flow(2026, 3, 29, 1)
        assert display.hour == 1

    def test_spring_forward_day_03h(self):
        """29 mars 03:00 CEST (après le saut, 02:00 n'existe pas) → doit afficher 03:00."""
        display = self._full_flow(2026, 3, 29, 3)
        assert display.hour == 3

    def test_spring_forward_day_10h(self):
        """29 mars 10:00 CEST (UTC+2) → doit afficher 10:00."""
        display = self._full_flow(2026, 3, 29, 10)
        assert display.hour == 10

    def test_spring_forward_day_15h(self):
        """29 mars 15:00 CEST → doit afficher 15:00."""
        display = self._full_flow(2026, 3, 29, 15)
        assert display.hour == 15

    # ── Après le passage (30 mars, maintenant CEST) ──

    def test_after_spring_forward(self):
        """30 mars 15:00 CEST (UTC+2) → doit afficher 15:00."""
        display = self._full_flow(2026, 3, 30, 15)
        assert display.hour == 15

    # ── Avant le retour à l'heure d'hiver (24 octobre 2026, encore CEST) ──

    def test_before_fall_back(self):
        """24 oct 15:00 CEST → doit afficher 15:00."""
        display = self._full_flow(2026, 10, 24, 15)
        assert display.hour == 15

    # ── Jour du retour à l'heure d'hiver (25 octobre 2026) ──

    def test_fall_back_day_01h(self):
        """25 oct 01:00 CEST (avant le retour) → doit afficher 01:00."""
        display = self._full_flow(2026, 10, 25, 1)
        assert display.hour == 1

    def test_fall_back_day_04h(self):
        """25 oct 04:00 CET (après le retour) → doit afficher 04:00."""
        display = self._full_flow(2026, 10, 25, 4)
        assert display.hour == 4

    def test_fall_back_day_15h(self):
        """25 oct 15:00 CET → doit afficher 15:00."""
        display = self._full_flow(2026, 10, 25, 15)
        assert display.hour == 15

    # ── Après le retour (26 oct, maintenant CET) ──

    def test_after_fall_back(self):
        """26 oct 15:00 CET (UTC+1) → doit afficher 15:00."""
        display = self._full_flow(2026, 10, 26, 15)
        assert display.hour == 15

    # ── Cross-timezone DST check (New York) ──

    def test_ny_spring_forward(self):
        """NY DST 2026: March 8. RDV at 15:00 EDT (March 9) → must show 15:00."""
        display = self._full_flow(2026, 3, 9, 15, tz_name="America/New_York")
        assert display.hour == 15

    def test_ny_fall_back(self):
        """NY DST fall back 2026: Nov 1. RDV at 15:00 EST (Nov 2) → must show 15:00."""
        display = self._full_flow(2026, 11, 2, 15, tz_name="America/New_York")
        assert display.hour == 15


# ═══════════════════════════════════════════════════════════════
# VOLET 3 : FORMAT ISO — Aucune datetime naive
# ═══════════════════════════════════════════════════════════════

class TestISOFormat:
    """Vérifier que toutes les datetime du flux sont explicites (avec Z ou offset)."""

    def test_frontend_to_utc_always_has_z(self):
        """localInputToUTC produit toujours un string avec Z."""
        # Simulate JS: new Date("2026-03-24T15:00").toISOString()
        paris = ZoneInfo("Europe/Paris")
        local = datetime(2026, 3, 24, 15, 0, tzinfo=paris)
        utc = local.astimezone(timezone.utc)
        iso = utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        assert iso.endswith("Z"), f"Missing Z suffix: {iso}"

    def test_normalize_to_utc_preserves_z(self):
        """normalize_to_utc ne perd jamais le Z."""
        inputs = [
            "2026-03-24T13:00:00.000Z",
            "2026-03-24T13:00:00Z",
            "2026-06-15T12:00:00.000Z",
        ]
        for inp in inputs:
            result = normalize_to_utc(inp)
            assert result.endswith("Z"), f"Lost Z suffix: {inp} → {result}"

    def test_normalize_to_utc_converts_offset_to_z(self):
        """Strings with +offset get converted to Z."""
        result = normalize_to_utc("2026-03-24T14:00:00+01:00")
        assert result.endswith("Z"), f"Missing Z: {result}"
        assert result == "2026-03-24T13:00:00Z"

    def test_normalize_to_utc_handles_naive_legacy(self):
        """Legacy naive strings get Z after conversion."""
        result = normalize_to_utc("2026-01-15T14:00:00")
        assert result.endswith("Z"), f"Missing Z: {result}"

    def test_build_event_data_timezone_always_utc(self):
        """_build_event_data always sets timeZone to UTC, never a local timezone."""
        timezones_to_test = [
            "Europe/Paris", "America/New_York", "Asia/Tokyo",
            "Romance Standard Time", "Eastern Standard Time",
            "UTC", None
        ]
        for tz in timezones_to_test:
            appointment = {
                "title": "ISO Test",
                "start_datetime": "2026-06-15T12:00:00Z",
                "duration_minutes": 60,
                "cancellation_deadline_hours": 0,
                "tolerated_delay_minutes": 0,
                "penalty_amount": 0,
                "penalty_currency": "EUR",
            }
            event = _build_event_data(appointment, calendar_tz=tz)
            assert event["timeZone"] == "UTC", \
                f"Expected UTC for calendar_tz={tz}, got {event['timeZone']}"

    def test_outlook_payload_structure(self):
        """Simulate the exact Outlook Graph API payload and verify timezone."""
        appointment = {
            "title": "Outlook Test",
            "start_datetime": "2026-03-24T13:00:00Z",
            "duration_minutes": 60,
            "cancellation_deadline_hours": 24,
            "tolerated_delay_minutes": 15,
            "penalty_amount": 50,
            "penalty_currency": "EUR",
        }
        event = _build_event_data(appointment, "Europe/Paris")

        # Simulate what OutlookCalendarAdapter.create_event does
        calendar_tz = to_windows_timezone(event.get('timeZone', 'UTC'))
        outlook_payload = {
            'start': {
                'dateTime': event['start_datetime'],
                'timeZone': calendar_tz,
            },
            'end': {
                'dateTime': event['end_datetime'],
                'timeZone': calendar_tz,
            },
        }

        # Verify: timezone must be "UTC"
        assert outlook_payload['start']['timeZone'] == "UTC"
        assert outlook_payload['end']['timeZone'] == "UTC"
        # Verify: datetime values are UTC
        assert outlook_payload['start']['dateTime'] == "2026-03-24T13:00:00"
        assert outlook_payload['end']['dateTime'] == "2026-03-24T14:00:00"

    def test_google_payload_structure(self):
        """Simulate the exact Google Calendar API payload."""
        appointment = {
            "title": "Google Test",
            "start_datetime": "2026-07-01T10:00:00Z",
            "duration_minutes": 90,
            "cancellation_deadline_hours": 24,
            "tolerated_delay_minutes": 15,
            "penalty_amount": 50,
            "penalty_currency": "EUR",
        }
        event = _build_event_data(appointment, "Europe/Paris")

        # Simulate what GoogleCalendarAdapter.create_event does
        google_payload = {
            'start': {
                'dateTime': event['start_datetime'],
                'timeZone': event.get('timeZone', 'UTC'),
            },
            'end': {
                'dateTime': event['end_datetime'],
                'timeZone': event.get('timeZone', 'UTC'),
            },
        }

        assert google_payload['start']['timeZone'] == "UTC"
        assert google_payload['start']['dateTime'] == "2026-07-01T10:00:00"
        assert google_payload['end']['dateTime'] == "2026-07-01T11:30:00"

    def test_ics_always_utc_with_z(self):
        """ICS DTSTART/DTEND must always use Z suffix (UTC)."""
        event_data = {
            "appointment_id": "test-ics",
            "title": "ICS UTC Test",
            "start_datetime": "2026-03-24T13:00:00Z",
            "end_datetime": "2026-03-24T14:00:00Z",
        }
        ics = ICSGenerator.generate_ics(event_data)

        # DTSTART must end with Z
        import re
        dtstart_match = re.search(r'DTSTART:(\S+)', ics)
        assert dtstart_match, "DTSTART not found in ICS"
        assert dtstart_match.group(1).endswith("Z"), f"DTSTART not UTC: {dtstart_match.group(1)}"

        dtend_match = re.search(r'DTEND:(\S+)', ics)
        assert dtend_match, "DTEND not found in ICS"
        assert dtend_match.group(1).endswith("Z"), f"DTEND not UTC: {dtend_match.group(1)}"

    def test_parse_iso_datetime_always_aware(self):
        """parse_iso_datetime must always return timezone-aware UTC datetime."""
        test_cases = [
            "2026-03-24T13:00:00Z",
            "2026-03-24T13:00:00.000Z",
            "2026-03-24T14:00:00+01:00",
            "2026-03-24T13:00:00",  # Legacy naive → interpreted as Paris
        ]
        for tc in test_cases:
            dt = parse_iso_datetime(tc)
            assert dt is not None, f"Failed to parse: {tc}"
            assert dt.tzinfo is not None, f"Naive datetime returned for: {tc}"
            # All should be in UTC
            assert dt.tzinfo == timezone.utc or dt.utcoffset() == timedelta(0), \
                f"Not UTC for {tc}: tzinfo={dt.tzinfo}"


# ═══════════════════════════════════════════════════════════════
# VOLET BONUS : Régression — l'ancien bug ne revient pas
# ═══════════════════════════════════════════════════════════════

class TestRegressionOldBug:
    """Vérifie que l'ancien bug (datetime UTC + timezone non-UTC) ne peut plus revenir."""

    def test_old_bug_would_show_wrong_time(self):
        """
        Preuve de l'ancien bug :
        Si on envoyait "13:00:00" avec "Europe/Paris", le calendrier affichait 13:00 Paris
        au lieu de 14:00 Paris. Vérifions que c'est bien corrigé.
        """
        appointment = {
            "title": "Bug Check",
            "start_datetime": "2026-03-24T13:00:00Z",  # 13 UTC = 14 Paris (CET)
            "duration_minutes": 60,
            "cancellation_deadline_hours": 24,
            "tolerated_delay_minutes": 0,
            "penalty_amount": 0,
            "penalty_currency": "EUR",
        }

        # Current (fixed) behavior
        event = _build_event_data(appointment, "Europe/Paris")

        # The old bug: event["start_datetime"] was "2026-03-24T13:00:00" + timeZone="Europe/Paris"
        # → Calendar shows 13:00 Paris (WRONG - should be 14:00)

        # Fixed behavior: timeZone is always UTC
        assert event["timeZone"] == "UTC", "REGRESSION: timeZone is not UTC!"

        # Verify the calendar would show the correct time
        api_dt = datetime.strptime(event["start_datetime"], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        paris_display = api_dt.astimezone(ZoneInfo("Europe/Paris"))
        assert paris_display.hour == 14, f"REGRESSION: Calendar shows {paris_display.hour}:00 instead of 14:00"

    def test_old_bug_summer_2h_offset(self):
        """
        En été (CEST, UTC+2), l'ancien bug causait 2h de décalage.
        12:00 UTC = 14:00 CEST, mais l'ancien code envoyait "12:00" + "Europe/Paris"
        → calendrier affichait 12:00 Paris au lieu de 14:00.
        """
        appointment = {
            "title": "Summer Bug Check",
            "start_datetime": "2026-07-15T12:00:00Z",  # 12 UTC = 14 CEST
            "duration_minutes": 60,
            "cancellation_deadline_hours": 0,
            "tolerated_delay_minutes": 0,
            "penalty_amount": 0,
            "penalty_currency": "EUR",
        }

        event = _build_event_data(appointment, "Europe/Paris")
        assert event["timeZone"] == "UTC"

        api_dt = datetime.strptime(event["start_datetime"], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        paris_display = api_dt.astimezone(ZoneInfo("Europe/Paris"))
        assert paris_display.hour == 14, f"REGRESSION: Summer offset shows {paris_display.hour}:00 instead of 14:00"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
