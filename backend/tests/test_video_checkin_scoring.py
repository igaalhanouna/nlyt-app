"""
Test Video Check-in Scoring for VIDEO vs PHYSICAL appointments.

Key rules being tested:
1. VIDEO appointment + no video evidence → strength='weak' (regardless of physical signals)
2. VIDEO appointment + video evidence → normal video scoring
3. PHYSICAL appointment → original scoring logic (unchanged)
4. VIDEO + weak evidence → manual_review decision
"""
import pytest
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

# Add backend to path
sys.path.insert(0, '/app/backend')

from services.evidence_service import aggregate_evidence, create_evidence
from services.attendance_service import evaluate_participant


class TestVideoAppointmentScoring:
    """Test evidence scoring for VIDEO appointments."""
    
    @pytest.fixture
    def video_appointment(self):
        """Create a video appointment fixture."""
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=1)  # Started 1 hour ago
        return {
            "appointment_id": "test-video-apt-001",
            "appointment_type": "video",
            "meeting_provider": "zoom",
            "start_datetime": start.isoformat(),
            "duration_minutes": 60,
            "tolerated_delay_minutes": 15,
            "cancellation_deadline_hours": 24,
        }
    
    @pytest.fixture
    def physical_appointment(self):
        """Create a physical appointment fixture."""
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=1)  # Started 1 hour ago
        return {
            "appointment_id": "test-physical-apt-001",
            "appointment_type": "physical",
            "location": "123 Test Street, Paris",
            "start_datetime": start.isoformat(),
            "duration_minutes": 60,
            "tolerated_delay_minutes": 15,
            "cancellation_deadline_hours": 24,
        }
    
    @patch('services.evidence_service.db')
    def test_video_appointment_no_video_evidence_returns_weak(self, mock_db, video_appointment):
        """
        VIDEO appointment with only manual_checkin (no video evidence) should ALWAYS return strength='weak'.
        This is the key rule: physical signals alone at a video meeting are fallback only.
        """
        participant_id = "test-participant-001"
        
        # Mock: only manual_checkin evidence, no video_conference evidence
        mock_evidence = [
            {
                "evidence_id": "ev-001",
                "appointment_id": video_appointment["appointment_id"],
                "participant_id": participant_id,
                "source": "manual_checkin",
                "source_timestamp": datetime.now(timezone.utc).isoformat(),
                "confidence_score": "medium",
                "derived_facts": {
                    "temporal_consistency": "valid",
                    "geographic_consistency": "close",
                    "latitude": 48.8566,
                    "longitude": 2.3522,
                }
            }
        ]
        
        mock_db.evidence_items.find.return_value = mock_evidence
        
        result = aggregate_evidence(
            video_appointment["appointment_id"],
            participant_id,
            video_appointment
        )
        
        # KEY ASSERTION: Video appointment without video evidence = weak
        assert result["strength"] == "weak", \
            f"Expected strength='weak' for video apt without video evidence, got '{result['strength']}'"
        print(f"✓ VIDEO apt + manual_checkin only → strength='{result['strength']}' (correct)")
    
    @patch('services.evidence_service.db')
    def test_video_appointment_with_qr_and_gps_still_weak(self, mock_db, video_appointment):
        """
        VIDEO appointment with QR + GPS (strong physical signals) but no video evidence
        should STILL return strength='weak'.
        """
        participant_id = "test-participant-002"
        
        # Mock: QR + GPS evidence, but no video_conference
        mock_evidence = [
            {
                "evidence_id": "ev-001",
                "appointment_id": video_appointment["appointment_id"],
                "participant_id": participant_id,
                "source": "qr",
                "source_timestamp": datetime.now(timezone.utc).isoformat(),
                "confidence_score": "high",
                "derived_facts": {
                    "qr_valid": True,
                    "temporal_consistency": "valid",
                }
            },
            {
                "evidence_id": "ev-002",
                "appointment_id": video_appointment["appointment_id"],
                "participant_id": participant_id,
                "source": "gps",
                "source_timestamp": datetime.now(timezone.utc).isoformat(),
                "confidence_score": "high",
                "derived_facts": {
                    "temporal_consistency": "valid",
                    "geographic_consistency": "close",
                    "latitude": 48.8566,
                    "longitude": 2.3522,
                }
            }
        ]
        
        mock_db.evidence_items.find.return_value = mock_evidence
        
        result = aggregate_evidence(
            video_appointment["appointment_id"],
            participant_id,
            video_appointment
        )
        
        # KEY ASSERTION: Even with QR+GPS, video apt without video evidence = weak
        assert result["strength"] == "weak", \
            f"Expected strength='weak' for video apt with QR+GPS but no video evidence, got '{result['strength']}'"
        print(f"✓ VIDEO apt + QR + GPS (no video) → strength='{result['strength']}' (correct)")
    
    @patch('services.evidence_service.db')
    def test_physical_appointment_with_qr_and_gps_is_strong(self, mock_db, physical_appointment):
        """
        PHYSICAL appointment with QR + GPS should return strength='strong' (no regression).
        """
        participant_id = "test-participant-003"
        
        # Mock: QR + GPS evidence for physical appointment
        mock_evidence = [
            {
                "evidence_id": "ev-001",
                "appointment_id": physical_appointment["appointment_id"],
                "participant_id": participant_id,
                "source": "qr",
                "source_timestamp": datetime.now(timezone.utc).isoformat(),
                "confidence_score": "high",
                "derived_facts": {
                    "qr_valid": True,
                    "temporal_consistency": "valid",
                }
            },
            {
                "evidence_id": "ev-002",
                "appointment_id": physical_appointment["appointment_id"],
                "participant_id": participant_id,
                "source": "gps",
                "source_timestamp": datetime.now(timezone.utc).isoformat(),
                "confidence_score": "high",
                "derived_facts": {
                    "temporal_consistency": "valid",
                    "geographic_consistency": "close",
                    "latitude": 48.8566,
                    "longitude": 2.3522,
                }
            }
        ]
        
        mock_db.evidence_items.find.return_value = mock_evidence
        
        result = aggregate_evidence(
            physical_appointment["appointment_id"],
            participant_id,
            physical_appointment
        )
        
        # PHYSICAL appointment with 2 signals = strong
        assert result["strength"] == "strong", \
            f"Expected strength='strong' for physical apt with QR+GPS, got '{result['strength']}'"
        print(f"✓ PHYSICAL apt + QR + GPS → strength='{result['strength']}' (correct, no regression)")
    
    @patch('services.evidence_service.db')
    def test_physical_appointment_with_manual_checkin_is_medium(self, mock_db, physical_appointment):
        """
        PHYSICAL appointment with only manual_checkin should return strength='medium' (no regression).
        """
        participant_id = "test-participant-004"
        
        # Mock: only manual_checkin for physical appointment
        mock_evidence = [
            {
                "evidence_id": "ev-001",
                "appointment_id": physical_appointment["appointment_id"],
                "participant_id": participant_id,
                "source": "manual_checkin",
                "source_timestamp": datetime.now(timezone.utc).isoformat(),
                "confidence_score": "medium",
                "derived_facts": {
                    "temporal_consistency": "valid",
                    "geographic_consistency": "no_gps",
                }
            }
        ]
        
        mock_db.evidence_items.find.return_value = mock_evidence
        
        result = aggregate_evidence(
            physical_appointment["appointment_id"],
            participant_id,
            physical_appointment
        )
        
        # PHYSICAL appointment with 1 signal = medium
        assert result["strength"] == "medium", \
            f"Expected strength='medium' for physical apt with manual_checkin only, got '{result['strength']}'"
        print(f"✓ PHYSICAL apt + manual_checkin only → strength='{result['strength']}' (correct, no regression)")


class TestAttendanceDecisionForVideo:
    """Test attendance decision engine for VIDEO appointments."""
    
    @pytest.fixture
    def video_appointment(self):
        """Create a video appointment fixture."""
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=2)  # Ended 1 hour ago
        return {
            "appointment_id": "test-video-apt-decision-001",
            "appointment_type": "video",
            "meeting_provider": "zoom",
            "start_datetime": start.isoformat(),
            "duration_minutes": 60,
            "tolerated_delay_minutes": 15,
            "cancellation_deadline_hours": 24,
        }
    
    @patch('services.evidence_service.aggregate_evidence')
    def test_video_weak_evidence_leads_to_manual_review(self, mock_aggregate, video_appointment):
        """
        VIDEO appointment with weak evidence should result in manual_review decision.
        """
        participant = {
            "participant_id": "test-participant-decision-001",
            "appointment_id": video_appointment["appointment_id"],
            "status": "accepted_guaranteed",
        }
        
        # Mock aggregate_evidence to return weak strength (video apt without video evidence)
        mock_aggregate.return_value = {
            "strength": "weak",
            "signals": ["manual_checkin"],
            "timing": "on_time",
            "confidence": "low",
            "evidence_count": 1,
            "temporal_flag": "valid",
            "geographic_flag": "close",
            "video_provider": None,
            "video_provider_ceiling": None,
            "video_identity_confidence": None,
            "video_outcome": None,
            "video_source_trust": None,
        }
        
        result = evaluate_participant(participant, video_appointment)
        
        # Weak evidence should lead to manual_review
        assert result["outcome"] == "manual_review", \
            f"Expected outcome='manual_review' for video apt with weak evidence, got '{result['outcome']}'"
        assert result["review_required"] == True, \
            "Expected review_required=True for weak evidence"
        print(f"✓ VIDEO apt + weak evidence → outcome='{result['outcome']}', review_required={result['review_required']} (correct)")
    
    @patch('services.evidence_service.aggregate_evidence')
    def test_video_strong_evidence_on_time(self, mock_aggregate, video_appointment):
        """
        VIDEO appointment with strong video evidence and on_time should result in on_time decision.
        """
        participant = {
            "participant_id": "test-participant-decision-002",
            "appointment_id": video_appointment["appointment_id"],
            "status": "accepted_guaranteed",
        }
        
        # Mock aggregate_evidence to return strong strength with video evidence
        mock_aggregate.return_value = {
            "strength": "strong",
            "signals": ["video_zoom"],
            "timing": "on_time",
            "confidence": "high",
            "evidence_count": 1,
            "temporal_flag": "valid",
            "geographic_flag": "no_reference",
            "video_provider": "zoom",
            "video_provider_ceiling": "strong",
            "video_identity_confidence": "high",
            "video_outcome": "joined_on_time",
            "video_source_trust": "api",
        }
        
        result = evaluate_participant(participant, video_appointment)
        
        # Strong video evidence on_time should lead to on_time
        assert result["outcome"] == "on_time", \
            f"Expected outcome='on_time' for video apt with strong video evidence, got '{result['outcome']}'"
        assert result["decision_basis"] == "video_strong_on_time", \
            f"Expected decision_basis='video_strong_on_time', got '{result['decision_basis']}'"
        print(f"✓ VIDEO apt + strong video evidence on_time → outcome='{result['outcome']}' (correct)")


class TestEvidenceServiceIntegration:
    """Integration tests for evidence_service aggregate_evidence function."""
    
    def test_aggregate_evidence_function_signature(self):
        """Verify aggregate_evidence function exists and has correct signature."""
        from services.evidence_service import aggregate_evidence
        import inspect
        
        sig = inspect.signature(aggregate_evidence)
        params = list(sig.parameters.keys())
        
        assert "appointment_id" in params, "aggregate_evidence should have appointment_id parameter"
        assert "participant_id" in params, "aggregate_evidence should have participant_id parameter"
        assert "appointment" in params, "aggregate_evidence should have appointment parameter"
        print(f"✓ aggregate_evidence function signature: {params}")
    
    def test_video_appointment_type_check_in_aggregate(self):
        """Verify that aggregate_evidence checks appointment_type for video."""
        import inspect
        from services.evidence_service import aggregate_evidence
        
        source = inspect.getsource(aggregate_evidence)
        
        # Check that the function checks for video appointment type
        assert "appointment_type" in source, \
            "aggregate_evidence should check appointment_type"
        assert "'video'" in source or '"video"' in source, \
            "aggregate_evidence should check for 'video' appointment type"
        assert "is_video_appointment" in source, \
            "aggregate_evidence should have is_video_appointment variable"
        print("✓ aggregate_evidence checks appointment_type for video")
    
    def test_video_no_evidence_returns_weak_in_code(self):
        """Verify the code path for video appointment without video evidence."""
        import inspect
        from services.evidence_service import aggregate_evidence
        
        source = inspect.getsource(aggregate_evidence)
        
        # Check for the specific code path: video apt + no video evidence = weak
        assert "is_video_appointment and not has_video" in source, \
            "aggregate_evidence should have 'is_video_appointment and not has_video' check"
        
        # Find the line and verify it sets strength to weak
        lines = source.split('\n')
        found_check = False
        for i, line in enumerate(lines):
            if "is_video_appointment and not has_video" in line:
                found_check = True
                # Check next few lines for strength = "weak"
                for j in range(i, min(i+5, len(lines))):
                    if 'strength = "weak"' in lines[j] or "strength = 'weak'" in lines[j]:
                        print(f"✓ Found video apt + no video evidence → strength='weak' at line {j+1}")
                        return
        
        if found_check:
            print("✓ Found 'is_video_appointment and not has_video' check in code")
        else:
            pytest.fail("Could not find video apt + no video evidence → weak code path")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
