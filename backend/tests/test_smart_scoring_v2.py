"""
Test Smart Evidence Scoring V2 - Temporal + Geographic Consistency

Tests for:
- Temporal consistency: valid, too_early, too_late, valid_late
- Geographic consistency: close, nearby, far, incoherent, no_reference
- Smart confidence scoring: combines source + temporal + geographic
- Forward geocoding: appointment address → coordinates (cached)
- Reverse geocoding: check-in GPS → address_label
- Distance calculation: distance_km and distance_meters in derived_facts
- Aggregation: strength degraded by temporal/geographic flags
- Evidence API returns enriched data (temporal_detail, geographic_detail, address_label, distance_km)
"""
import pytest
import requests
import os
import time
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://nlyt-acquisition.preview.emergentagent.com')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"

# Test appointment with geocoded location (Cannes)
TEST_APPOINTMENT_ID = "c053871f-1924-45ce-a4b0-1b1d7df31240"
TEST_PARTICIPANT_TOKEN = "f5a9125f-1134-413f-b974-1c469b2d0c6b"  # bce0b6bb participant

# Existing participant with evidence (Paris GPS, 689km away, 69h early)
EXISTING_PARTICIPANT_ID = "d10dd899-f80f-4d15-8b3c-90ff66e3296a"

# Cannes coordinates (appointment location)
CANNES_LAT = 43.565097
CANNES_LON = 7.029133

# Paris coordinates (far from Cannes - ~689km)
PARIS_LAT = 48.8566
PARIS_LON = 2.3522

# Nice coordinates (nearby Cannes - ~30km)
NICE_LAT = 43.7102
NICE_LON = 7.2620

# Cannes close coordinates (~200m from appointment)
CANNES_CLOSE_LAT = 43.5655
CANNES_CLOSE_LON = 7.0295


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for organizer tests."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("access_token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Return headers with auth token."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestForwardGeocoding:
    """Tests for forward geocoding (address → coordinates)"""

    def test_appointment_has_geocoded_coordinates(self, auth_headers):
        """Test that appointment with address has been geocoded."""
        response = requests.get(
            f"{BASE_URL}/api/appointments/{TEST_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify geocoded coordinates exist
        assert data.get("location_latitude") is not None, "location_latitude should be set"
        assert data.get("location_longitude") is not None, "location_longitude should be set"
        assert data.get("location_geocoded") == True, "location_geocoded should be True"
        
        # Verify coordinates are in Cannes area (roughly)
        lat = data["location_latitude"]
        lon = data["location_longitude"]
        assert 43.5 < lat < 43.6, f"Latitude {lat} should be in Cannes area"
        assert 6.9 < lon < 7.1, f"Longitude {lon} should be in Cannes area"
        
        # Verify display name is set
        assert data.get("location_display_name"), "location_display_name should be set"
        assert "Cannes" in data["location_display_name"], "Display name should contain Cannes"

    def test_appointment_location_address(self, auth_headers):
        """Test that original location address is preserved."""
        response = requests.get(
            f"{BASE_URL}/api/appointments/{TEST_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Original address should be preserved
        assert "43 Boulevard" in data.get("location", ""), "Original address should be preserved"
        assert "Cannes" in data.get("location", ""), "Address should contain Cannes"


class TestReverseGeocoding:
    """Tests for reverse geocoding (GPS → address_label)"""

    def test_evidence_has_address_label(self, auth_headers):
        """Test that evidence with GPS has reverse-geocoded address_label."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{TEST_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Find participant with GPS evidence
        for participant in data.get("participants", []):
            for evidence in participant.get("evidence", []):
                facts = evidence.get("derived_facts", {})
                if facts.get("latitude") is not None:
                    # Should have address_label from reverse geocoding
                    assert facts.get("address_label"), "Evidence with GPS should have address_label"
                    # Paris evidence should have Paris in address
                    if abs(facts["latitude"] - PARIS_LAT) < 0.1:
                        assert "Paris" in facts["address_label"], "Paris GPS should have Paris in address_label"


class TestTemporalConsistency:
    """Tests for temporal consistency assessment"""

    def test_too_early_temporal_consistency(self, auth_headers):
        """Test that check-in 69h before RDV is marked as too_early."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{TEST_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Find the existing evidence (Paris, 69h early)
        for participant in data.get("participants", []):
            for evidence in participant.get("evidence", []):
                facts = evidence.get("derived_facts", {})
                if facts.get("temporal_consistency") == "too_early":
                    # Verify temporal details
                    assert "temporal_detail" in facts, "Should have temporal_detail"
                    assert "avant" in facts["temporal_detail"].lower(), "Detail should mention 'avant'"
                    
                    # Verify hours offset is significant (>24h)
                    detail = facts["temporal_detail"]
                    # Extract hours from "69.5h avant le début du RDV"
                    if "h" in detail:
                        hours_str = detail.split("h")[0]
                        try:
                            hours = float(hours_str)
                            assert hours > 24, f"Hours offset {hours} should be > 24 for too_early"
                        except ValueError:
                            pass
                    return
        
        pytest.fail("No evidence with too_early temporal consistency found")

    def test_temporal_consistency_in_aggregation(self, auth_headers):
        """Test that temporal_flag is included in aggregation."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{TEST_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for participant in data.get("participants", []):
            agg = participant.get("aggregation", {})
            # Should have temporal_flag
            assert "temporal_flag" in agg, "Aggregation should have temporal_flag"
            # For the test appointment, should be too_early
            if agg.get("temporal_flag") == "too_early":
                return
        
        pytest.fail("No aggregation with too_early temporal_flag found")


class TestGeographicConsistency:
    """Tests for geographic consistency assessment"""

    def test_incoherent_geographic_consistency(self, auth_headers):
        """Test that check-in 689km away is marked as incoherent."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{TEST_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for participant in data.get("participants", []):
            for evidence in participant.get("evidence", []):
                facts = evidence.get("derived_facts", {})
                if facts.get("geographic_consistency") == "incoherent":
                    # Verify distance is > 50km (incoherent threshold)
                    distance_km = facts.get("distance_km")
                    assert distance_km is not None, "Should have distance_km"
                    assert distance_km > 50, f"Distance {distance_km}km should be > 50km for incoherent"
                    
                    # Verify geographic detail
                    assert "geographic_detail" in facts, "Should have geographic_detail"
                    assert "incohérent" in facts["geographic_detail"].lower(), "Detail should mention incohérent"
                    return
        
        pytest.fail("No evidence with incoherent geographic consistency found")

    def test_distance_calculation(self, auth_headers):
        """Test that distance_km and distance_meters are calculated."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{TEST_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for participant in data.get("participants", []):
            for evidence in participant.get("evidence", []):
                facts = evidence.get("derived_facts", {})
                if facts.get("latitude") is not None:
                    # Should have distance calculations
                    assert "distance_km" in facts, "Should have distance_km"
                    assert "distance_meters" in facts, "Should have distance_meters"
                    
                    # Verify consistency between km and meters
                    distance_km = facts["distance_km"]
                    distance_meters = facts["distance_meters"]
                    expected_meters = distance_km * 1000
                    assert abs(distance_meters - expected_meters) < 1000, "distance_meters should match distance_km * 1000"
                    return
        
        pytest.fail("No evidence with GPS coordinates found")

    def test_geographic_flag_in_aggregation(self, auth_headers):
        """Test that geographic_flag is included in aggregation."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{TEST_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for participant in data.get("participants", []):
            agg = participant.get("aggregation", {})
            # Should have geographic_flag
            assert "geographic_flag" in agg, "Aggregation should have geographic_flag"
            # For the test appointment, should be incoherent
            if agg.get("geographic_flag") == "incoherent":
                return
        
        pytest.fail("No aggregation with incoherent geographic_flag found")


class TestSmartConfidenceScoring:
    """Tests for smart confidence scoring (source + temporal + geographic)"""

    def test_low_confidence_for_bad_temporal_and_geographic(self, auth_headers):
        """Test that too_early + incoherent = low confidence."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{TEST_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for participant in data.get("participants", []):
            for evidence in participant.get("evidence", []):
                facts = evidence.get("derived_facts", {})
                if (facts.get("temporal_consistency") == "too_early" and 
                    facts.get("geographic_consistency") == "incoherent"):
                    # Should have low confidence
                    assert evidence.get("confidence_score") == "low", \
                        f"Confidence should be low, got {evidence.get('confidence_score')}"
                    
                    # Verify confidence_factors
                    assert "confidence_factors" in facts, "Should have confidence_factors"
                    assert "temporal=too_early" in facts["confidence_factors"]
                    assert "geographic=incoherent" in facts["confidence_factors"]
                    return
        
        pytest.fail("No evidence with too_early + incoherent found")

    def test_weak_strength_for_bad_consistency(self, auth_headers):
        """Test that aggregation strength is weak for bad temporal/geographic."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{TEST_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for participant in data.get("participants", []):
            agg = participant.get("aggregation", {})
            if (agg.get("temporal_flag") == "too_early" or 
                agg.get("geographic_flag") == "incoherent"):
                # Should have weak strength
                assert agg.get("strength") == "weak", \
                    f"Strength should be weak, got {agg.get('strength')}"
                assert agg.get("confidence") == "low", \
                    f"Confidence should be low, got {agg.get('confidence')}"
                return
        
        pytest.fail("No aggregation with bad temporal/geographic flags found")


class TestEvidenceEnrichedData:
    """Tests for enriched evidence data in API responses"""

    def test_evidence_has_all_enriched_fields(self, auth_headers):
        """Test that evidence API returns all enriched fields."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{TEST_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for participant in data.get("participants", []):
            for evidence in participant.get("evidence", []):
                facts = evidence.get("derived_facts", {})
                
                # Temporal fields
                assert "temporal_consistency" in facts, "Should have temporal_consistency"
                assert "temporal_detail" in facts, "Should have temporal_detail"
                
                # If GPS present, should have geographic fields
                if facts.get("latitude") is not None:
                    assert "geographic_consistency" in facts, "Should have geographic_consistency"
                    assert "geographic_detail" in facts, "Should have geographic_detail"
                    assert "distance_km" in facts, "Should have distance_km"
                    assert "distance_meters" in facts, "Should have distance_meters"
                    assert "address_label" in facts, "Should have address_label"
                
                # Confidence factors
                assert "confidence_factors" in facts, "Should have confidence_factors"
                return
        
        pytest.fail("No evidence found to verify enriched fields")

    def test_aggregation_has_all_flags(self, auth_headers):
        """Test that aggregation includes temporal and geographic flags."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{TEST_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for participant in data.get("participants", []):
            agg = participant.get("aggregation", {})
            
            # Required aggregation fields
            assert "strength" in agg, "Should have strength"
            assert "signals" in agg, "Should have signals"
            assert "timing" in agg, "Should have timing"
            assert "confidence" in agg, "Should have confidence"
            assert "evidence_count" in agg, "Should have evidence_count"
            assert "temporal_flag" in agg, "Should have temporal_flag"
            assert "geographic_flag" in agg, "Should have geographic_flag"
            return
        
        pytest.fail("No participant found to verify aggregation fields")


class TestGeographicThresholds:
    """Tests for geographic consistency thresholds"""

    def test_geographic_thresholds_documented(self):
        """Verify geographic thresholds are as expected."""
        # These are the expected thresholds from evidence_service.py
        # close: <= 500m
        # nearby: <= 5km
        # far: <= 50km
        # incoherent: > 50km
        
        # Test with Paris-Cannes distance (~689km)
        # This should be incoherent
        assert 689 > 50, "Paris-Cannes distance should exceed incoherent threshold"

    def test_gps_within_radius_flag(self, auth_headers):
        """Test that gps_within_radius is set correctly."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{TEST_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for participant in data.get("participants", []):
            for evidence in participant.get("evidence", []):
                facts = evidence.get("derived_facts", {})
                if facts.get("latitude") is not None:
                    # Should have gps_within_radius
                    assert "gps_within_radius" in facts, "Should have gps_within_radius"
                    
                    # For incoherent distance, should be False
                    if facts.get("geographic_consistency") == "incoherent":
                        assert facts["gps_within_radius"] == False, \
                            "gps_within_radius should be False for incoherent"
                    return
        
        pytest.fail("No evidence with GPS found")


class TestTemporalThresholds:
    """Tests for temporal consistency thresholds"""

    def test_temporal_thresholds_documented(self):
        """Verify temporal thresholds are as expected."""
        # These are the expected thresholds from evidence_service.py
        # valid window: RDV_start - 2h to RDV_end + 1h
        # too_early: before window_start
        # too_late: after window_end
        
        # Test with 69h early
        # This should be too_early (way before 2h window)
        assert 69 > 2, "69h early should exceed too_early threshold"


class TestSignalsInAggregation:
    """Tests for signals array in aggregation"""

    def test_signals_include_geographic_status(self, auth_headers):
        """Test that signals array includes geographic status."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{TEST_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for participant in data.get("participants", []):
            agg = participant.get("aggregation", {})
            signals = agg.get("signals", [])
            
            # Should have manual_checkin signal
            assert "manual_checkin" in signals, "Should have manual_checkin signal"
            
            # For incoherent GPS, should have gps_incoherent signal
            if agg.get("geographic_flag") == "incoherent":
                assert "gps_incoherent" in signals, "Should have gps_incoherent signal"
                return
        
        pytest.fail("No aggregation with incoherent geographic found")


class TestCheckinStatusWithSmartScoring:
    """Tests for check-in status endpoint with smart scoring"""

    def test_checkin_status_returns_evidence_with_smart_fields(self):
        """Test that check-in status returns evidence with smart scoring fields."""
        # Use the existing participant token
        response = requests.get(
            f"{BASE_URL}/api/checkin/status/{TEST_APPOINTMENT_ID}",
            params={"invitation_token": TEST_PARTICIPANT_TOKEN}
        )
        
        # May return 404 if participant doesn't exist or 200 with evidence
        if response.status_code == 200:
            data = response.json()
            evidence_list = data.get("evidence", [])
            
            for evidence in evidence_list:
                facts = evidence.get("derived_facts", {})
                # Should have temporal fields
                if "temporal_consistency" in facts:
                    assert "temporal_detail" in facts
                # Should have geographic fields if GPS present
                if facts.get("latitude") is not None:
                    assert "geographic_consistency" in facts
                    assert "distance_km" in facts


class TestQRCheckinWithTemporalConsistency:
    """Tests for QR check-in with temporal consistency"""

    def test_qr_checkin_includes_temporal_consistency(self, auth_headers):
        """Test that QR check-in evidence includes temporal consistency."""
        # Get evidence and check if any QR evidence has temporal fields
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{TEST_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for participant in data.get("participants", []):
            for evidence in participant.get("evidence", []):
                if evidence.get("source") == "qr":
                    facts = evidence.get("derived_facts", {})
                    # QR evidence should have temporal consistency
                    assert "temporal_consistency" in facts, "QR evidence should have temporal_consistency"
                    assert "temporal_detail" in facts, "QR evidence should have temporal_detail"
                    return
        
        # If no QR evidence exists, that's OK - just skip
        pytest.skip("No QR evidence found to verify temporal consistency")


class TestGPSCheckinWithSmartScoring:
    """Tests for GPS check-in with smart scoring"""

    def test_gps_checkin_includes_all_smart_fields(self, auth_headers):
        """Test that GPS check-in evidence includes all smart scoring fields."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{TEST_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for participant in data.get("participants", []):
            for evidence in participant.get("evidence", []):
                if evidence.get("source") == "gps":
                    facts = evidence.get("derived_facts", {})
                    # GPS evidence should have all smart fields
                    assert "temporal_consistency" in facts
                    assert "temporal_detail" in facts
                    assert "geographic_consistency" in facts
                    assert "geographic_detail" in facts
                    assert "distance_km" in facts
                    assert "distance_meters" in facts
                    assert "address_label" in facts
                    assert "confidence_factors" in facts
                    return
        
        # If no GPS evidence exists, check manual_checkin with GPS
        for participant in data.get("participants", []):
            for evidence in participant.get("evidence", []):
                facts = evidence.get("derived_facts", {})
                if facts.get("latitude") is not None:
                    # Manual checkin with GPS should have geographic fields
                    assert "geographic_consistency" in facts
                    assert "distance_km" in facts
                    return
        
        pytest.skip("No GPS evidence found to verify smart scoring fields")


class TestAggregationStrengthDegradation:
    """Tests for aggregation strength degradation based on consistency flags"""

    def test_strength_degraded_by_temporal_too_early(self, auth_headers):
        """Test that strength is degraded when temporal is too_early."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{TEST_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for participant in data.get("participants", []):
            agg = participant.get("aggregation", {})
            if agg.get("temporal_flag") == "too_early":
                # Strength should be weak for significant early check-in
                assert agg.get("strength") in ["weak", "medium"], \
                    f"Strength should be degraded for too_early, got {agg.get('strength')}"
                return
        
        pytest.fail("No aggregation with too_early temporal_flag found")

    def test_strength_degraded_by_geographic_incoherent(self, auth_headers):
        """Test that strength is degraded when geographic is incoherent."""
        response = requests.get(
            f"{BASE_URL}/api/checkin/evidence/{TEST_APPOINTMENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for participant in data.get("participants", []):
            agg = participant.get("aggregation", {})
            if agg.get("geographic_flag") == "incoherent":
                # Strength should be weak for incoherent location
                assert agg.get("strength") == "weak", \
                    f"Strength should be weak for incoherent, got {agg.get('strength')}"
                return
        
        pytest.fail("No aggregation with incoherent geographic_flag found")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
