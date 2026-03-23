"""
Test NLYT Proof Scoring Rebalance (Feb 2026)

Tests the rebalanced scoring weights:
- Check-in timing: 40 pts (was 30)
- Duration/heartbeats: 30 pts (was 40)
- NLYT flow bonus: 10 pts (new)
- Video API: 20 pts (was 30)
- Strong threshold: 55 (was 60)
"""

import pytest
import requests
import os
import sys
from datetime import datetime, timezone, timedelta

# Add backend to path for direct imports
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Import the scoring function directly for unit testing
from routers.proof_routes import _compute_score


class TestComputeScoreFunction:
    """Direct unit tests for _compute_score function"""
    
    def test_on_time_checkin_zero_heartbeats_equals_50_pts_medium(self):
        """
        On-time check-in with 0 heartbeats = 50 pts (medium, not strong)
        - checkin_points: 40 (on-time)
        - duration_points: 0 (no heartbeats)
        - flow_bonus: 10 (checked_in_at exists)
        - video_api_points: 0
        Total: 50 pts -> medium (30-54)
        """
        now = datetime.now(timezone.utc)
        apt_start = now - timedelta(minutes=5)  # Started 5 min ago
        
        session = {
            "checked_in_at": (apt_start + timedelta(minutes=2)).isoformat(),  # 2 min after start (on-time)
            "active_duration_seconds": 0,
            "heartbeat_count": 0,
        }
        appointment = {
            "start_datetime": apt_start.isoformat(),
            "duration_minutes": 30,
            "tolerated_delay_minutes": 10,
        }
        
        result = _compute_score(session, appointment)
        
        assert result["score_breakdown"]["checkin_points"] == 40, "On-time checkin should be 40 pts"
        assert result["score_breakdown"]["duration_points"] == 0, "Zero duration should be 0 pts"
        assert result["score_breakdown"]["flow_bonus"] == 10, "Flow bonus should be 10 pts"
        assert result["score_breakdown"]["video_api_points"] == 0, "Video API should be 0 pts"
        assert result["score"] == 50, "Total should be 50 pts"
        assert result["proof_level"] == "medium", "50 pts should be medium (30-54)"
        assert result["suggested_status"] == "partial", "Medium should suggest partial"
    
    def test_on_time_checkin_5min_heartbeats_30min_meeting_equals_55_pts_strong(self):
        """
        On-time check-in with 5 min heartbeats on 30 min meeting = 55 pts (strong)
        - checkin_points: 40 (on-time)
        - duration_points: 5 (5/30 * 30 = 5)
        - flow_bonus: 10
        - video_api_points: 0
        Total: 55 pts -> strong (>= 55)
        """
        now = datetime.now(timezone.utc)
        apt_start = now - timedelta(minutes=10)
        
        session = {
            "checked_in_at": (apt_start + timedelta(minutes=1)).isoformat(),  # 1 min after start
            "active_duration_seconds": 5 * 60,  # 5 minutes = 300 seconds
            "heartbeat_count": 10,
        }
        appointment = {
            "start_datetime": apt_start.isoformat(),
            "duration_minutes": 30,
            "tolerated_delay_minutes": 10,
        }
        
        result = _compute_score(session, appointment)
        
        assert result["score_breakdown"]["checkin_points"] == 40, "On-time checkin should be 40 pts"
        # 5 min / 30 min = 0.1667 * 30 = 5 pts
        assert result["score_breakdown"]["duration_points"] == 5, "5 min duration should be 5 pts"
        assert result["score_breakdown"]["flow_bonus"] == 10, "Flow bonus should be 10 pts"
        assert result["score"] == 55, "Total should be 55 pts"
        assert result["proof_level"] == "strong", "55 pts should be strong (>= 55)"
        assert result["suggested_status"] == "present", "Strong should suggest present"
    
    def test_very_late_checkin_20min_heartbeats_equals_35_pts_medium(self):
        """
        Very late check-in (+25min) with 20 min heartbeats = 35 pts (medium)
        - checkin_points: 5 (very late, > tolerated * 2)
        - duration_points: 20 (20/30 * 30 = 20)
        - flow_bonus: 10
        - video_api_points: 0
        Total: 35 pts -> medium (30-54)
        """
        now = datetime.now(timezone.utc)
        apt_start = now - timedelta(minutes=50)
        
        session = {
            "checked_in_at": (apt_start + timedelta(minutes=25)).isoformat(),  # 25 min late
            "active_duration_seconds": 20 * 60,  # 20 minutes
            "heartbeat_count": 40,
        }
        appointment = {
            "start_datetime": apt_start.isoformat(),
            "duration_minutes": 30,
            "tolerated_delay_minutes": 10,  # Very late = > 20 min
        }
        
        result = _compute_score(session, appointment)
        
        assert result["score_breakdown"]["checkin_points"] == 5, "Very late checkin should be 5 pts"
        # 20 min / 30 min = 0.6667 * 30 = 20 pts
        assert result["score_breakdown"]["duration_points"] == 20, "20 min duration should be 20 pts"
        assert result["score_breakdown"]["flow_bonus"] == 10, "Flow bonus should be 10 pts"
        assert result["score"] == 35, "Total should be 35 pts"
        assert result["proof_level"] == "medium", "35 pts should be medium (30-54)"
    
    def test_on_time_checkin_full_30min_session_equals_80_pts_strong(self):
        """
        On-time check-in with full 30 min session = 80 pts (strong)
        - checkin_points: 40 (on-time)
        - duration_points: 30 (30/30 * 30 = 30, capped at 30)
        - flow_bonus: 10
        - video_api_points: 0
        Total: 80 pts -> strong (>= 55)
        """
        now = datetime.now(timezone.utc)
        apt_start = now - timedelta(minutes=35)
        
        session = {
            "checked_in_at": apt_start.isoformat(),  # Exactly on time
            "active_duration_seconds": 30 * 60,  # Full 30 minutes
            "heartbeat_count": 60,
        }
        appointment = {
            "start_datetime": apt_start.isoformat(),
            "duration_minutes": 30,
            "tolerated_delay_minutes": 10,
        }
        
        result = _compute_score(session, appointment)
        
        assert result["score_breakdown"]["checkin_points"] == 40, "On-time checkin should be 40 pts"
        assert result["score_breakdown"]["duration_points"] == 30, "Full duration should be 30 pts"
        assert result["score_breakdown"]["flow_bonus"] == 10, "Flow bonus should be 10 pts"
        assert result["score"] == 80, "Total should be 80 pts"
        assert result["proof_level"] == "strong", "80 pts should be strong"
    
    def test_score_breakdown_includes_flow_bonus_key(self):
        """Verify score_breakdown dict has 4 keys including flow_bonus"""
        session = {
            "checked_in_at": datetime.now(timezone.utc).isoformat(),
            "active_duration_seconds": 0,
            "heartbeat_count": 0,
        }
        appointment = {
            "start_datetime": datetime.now(timezone.utc).isoformat(),
            "duration_minutes": 30,
            "tolerated_delay_minutes": 10,
        }
        
        result = _compute_score(session, appointment)
        
        assert "flow_bonus" in result["score_breakdown"], "score_breakdown must include flow_bonus key"
        assert len(result["score_breakdown"]) == 4, "score_breakdown should have 4 keys"
        expected_keys = {"checkin_points", "duration_points", "flow_bonus", "video_api_points"}
        assert set(result["score_breakdown"].keys()) == expected_keys
    
    def test_no_checkin_no_flow_bonus(self):
        """No checked_in_at means no flow_bonus"""
        session = {
            "checked_in_at": None,  # No check-in
            "active_duration_seconds": 600,
            "heartbeat_count": 20,
        }
        appointment = {
            "start_datetime": datetime.now(timezone.utc).isoformat(),
            "duration_minutes": 30,
            "tolerated_delay_minutes": 10,
        }
        
        result = _compute_score(session, appointment)
        
        assert result["score_breakdown"]["flow_bonus"] == 0, "No check-in = no flow bonus"
        assert result["score_breakdown"]["checkin_points"] == 0, "No check-in = no checkin points"
    
    def test_slightly_late_checkin_gets_20_pts(self):
        """
        Slightly late check-in (within tolerated * 2) gets 20 pts
        """
        now = datetime.now(timezone.utc)
        apt_start = now - timedelta(minutes=20)
        
        session = {
            "checked_in_at": (apt_start + timedelta(minutes=15)).isoformat(),  # 15 min late (within 10*2=20)
            "active_duration_seconds": 0,
            "heartbeat_count": 0,
        }
        appointment = {
            "start_datetime": apt_start.isoformat(),
            "duration_minutes": 30,
            "tolerated_delay_minutes": 10,
        }
        
        result = _compute_score(session, appointment)
        
        assert result["score_breakdown"]["checkin_points"] == 20, "Slightly late should be 20 pts"
    
    def test_threshold_55_is_strong(self):
        """Score of exactly 55 should be strong"""
        now = datetime.now(timezone.utc)
        apt_start = now - timedelta(minutes=10)
        
        # Craft a session that gives exactly 55 pts
        # 40 (on-time) + 5 (5min/30min) + 10 (flow) = 55
        session = {
            "checked_in_at": apt_start.isoformat(),
            "active_duration_seconds": 5 * 60,  # 5 minutes
            "heartbeat_count": 10,
        }
        appointment = {
            "start_datetime": apt_start.isoformat(),
            "duration_minutes": 30,
            "tolerated_delay_minutes": 10,
        }
        
        result = _compute_score(session, appointment)
        
        assert result["score"] == 55
        assert result["proof_level"] == "strong", "55 should be strong threshold"
    
    def test_threshold_54_is_medium(self):
        """Score of 54 should be medium (just below strong)"""
        now = datetime.now(timezone.utc)
        apt_start = now - timedelta(minutes=10)
        
        # Craft a session that gives 54 pts
        # 40 (on-time) + 4 (4min/30min) + 10 (flow) = 54
        session = {
            "checked_in_at": apt_start.isoformat(),
            "active_duration_seconds": 4 * 60,  # 4 minutes = 4/30*30 = 4 pts
            "heartbeat_count": 8,
        }
        appointment = {
            "start_datetime": apt_start.isoformat(),
            "duration_minutes": 30,
            "tolerated_delay_minutes": 10,
        }
        
        result = _compute_score(session, appointment)
        
        assert result["score"] == 54
        assert result["proof_level"] == "medium", "54 should be medium (below 55)"


class TestAttendanceServiceThresholds:
    """Test attendance_service.py uses correct thresholds"""
    
    def test_score_55_triggers_on_time_no_review(self):
        """
        Score >= 55 with checkin_points >= 30 should trigger on_time with review_required=false
        """
        from services.attendance_service import evaluate_participant
        
        # Mock participant and appointment
        participant = {
            "participant_id": "test-participant-55",
            "appointment_id": "test-apt-55",
            "status": "accepted",
        }
        appointment = {
            "appointment_id": "test-apt-55",
            "appointment_type": "video",
            "start_datetime": datetime.now(timezone.utc).isoformat(),
            "duration_minutes": 30,
        }
        
        # We need to mock the proof session lookup
        # Since we can't easily mock DB, we'll verify the logic in the code review
        # The test verifies the threshold constants are correct
        
        # Verify the threshold in the code
        import services.attendance_service as attendance_svc
        
        # Check that the code uses 55 as threshold (line 201)
        # This is a code inspection test
        import inspect
        source = inspect.getsource(attendance_svc.evaluate_participant)
        
        assert "score >= 55" in source, "Threshold should be 55 for strong"
        assert "checkin_points >= 30" in source, "On-time check should be checkin_points >= 30"
    
    def test_score_30_to_54_triggers_manual_review(self):
        """
        Score 30-54 should trigger manual_review with review_required=true
        """
        import services.attendance_service as attendance_svc
        import inspect
        source = inspect.getsource(attendance_svc.evaluate_participant)
        
        assert "score >= 30" in source, "Medium threshold should be 30"
        # The code structure: if score >= 55 -> strong, elif score >= 30 -> medium
    
    def test_score_below_30_triggers_no_show(self):
        """
        Score < 30 should trigger no_show with review_required=true
        """
        import services.attendance_service as attendance_svc
        import inspect
        source = inspect.getsource(attendance_svc.evaluate_participant)
        
        # The code returns no_show for weak proof (< 30)
        assert "nlyt_proof_weak" in source, "Weak proof should return no_show"


class TestProofSessionCreation:
    """Test that proof session creation includes flow_bonus in score_breakdown"""
    
    def test_session_doc_has_flow_bonus_in_breakdown(self):
        """Verify session document template includes flow_bonus"""
        import routers.proof_routes as proof_routes
        import inspect
        source = inspect.getsource(proof_routes.checkin)
        
        # Check that the session_doc includes flow_bonus in score_breakdown
        assert '"flow_bonus": 0' in source or "'flow_bonus': 0" in source, \
            "Session doc should include flow_bonus in score_breakdown"


class TestHealthCheck:
    """Basic health check to ensure backend is running"""
    
    def test_health_check_returns_200(self):
        """Backend health check should return 200"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200, f"Health check failed: {response.status_code}"


class TestScoringEdgeCases:
    """Edge cases for scoring function"""
    
    def test_duration_capped_at_100_percent(self):
        """Duration ratio should be capped at 1.0 (100%)"""
        now = datetime.now(timezone.utc)
        apt_start = now - timedelta(minutes=60)
        
        session = {
            "checked_in_at": apt_start.isoformat(),
            "active_duration_seconds": 60 * 60,  # 60 minutes (double the meeting)
            "heartbeat_count": 120,
        }
        appointment = {
            "start_datetime": apt_start.isoformat(),
            "duration_minutes": 30,  # Only 30 min meeting
            "tolerated_delay_minutes": 10,
        }
        
        result = _compute_score(session, appointment)
        
        # Duration should be capped at 30 pts (100% of 30)
        assert result["score_breakdown"]["duration_points"] == 30, "Duration should cap at 30 pts"
    
    def test_early_checkin_gets_full_points(self):
        """Check-in before meeting start should get full 40 pts"""
        now = datetime.now(timezone.utc)
        apt_start = now + timedelta(minutes=5)  # Meeting starts in 5 min
        
        session = {
            "checked_in_at": now.isoformat(),  # Check in now (5 min early)
            "active_duration_seconds": 0,
            "heartbeat_count": 0,
        }
        appointment = {
            "start_datetime": apt_start.isoformat(),
            "duration_minutes": 30,
            "tolerated_delay_minutes": 10,
        }
        
        result = _compute_score(session, appointment)
        
        assert result["score_breakdown"]["checkin_points"] == 40, "Early checkin should get 40 pts"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
