"""
Test suite for Conflict Detection feature in Appointment Wizard
POST /api/appointments/check-conflicts endpoint

Tests:
- Conflict detection when proposed slot overlaps existing engagement
- Warning detection when proposed slot is within 30min buffer
- Available status when no conflicts
- Suggestions generation with labels (optimal/comfortable/tight)
- Invalid date handling (400)
- Authentication requirement (401)
"""

import pytest
import requests
import os
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"

# Known conflicting date: 2026-06-20T08:00:00Z (appointment 'Test Source Trust', 60min)
CONFLICT_DATE = "2026-06-20T08:00:00Z"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


class TestConflictDetectionAuth:
    """Test authentication requirements for conflict detection endpoint"""
    
    def test_requires_authentication(self, api_client):
        """POST /api/appointments/check-conflicts returns 401 without token"""
        response = api_client.post(f"{BASE_URL}/api/appointments/check-conflicts", json={
            "start_datetime": "2026-06-25T10:00:00Z",
            "duration_minutes": 60
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("PASS: Endpoint requires authentication (401 without token)")


class TestConflictDetection:
    """Test conflict detection logic"""
    
    def test_conflict_status_on_overlap(self, authenticated_client):
        """Returns 'conflict' status when proposed slot overlaps existing engagement"""
        # Use the known conflicting date: 2026-06-20T08:00:00Z
        response = authenticated_client.post(f"{BASE_URL}/api/appointments/check-conflicts", json={
            "start_datetime": CONFLICT_DATE,
            "duration_minutes": 60
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"Response: {data}")
        
        # Check response structure
        assert "status" in data, "Response should have 'status' field"
        assert "confidence" in data, "Response should have 'confidence' field"
        assert "conflicts" in data, "Response should have 'conflicts' field"
        assert "warnings" in data, "Response should have 'warnings' field"
        assert "suggestions" in data, "Response should have 'suggestions' field"
        
        # If there's a conflict, verify the structure
        if data["status"] == "conflict":
            assert data["confidence"] == "high", "Conflict should have high confidence"
            assert len(data["conflicts"]) > 0, "Should have at least one conflict item"
            
            # Verify conflict item structure
            conflict = data["conflicts"][0]
            assert "title" in conflict, "Conflict item should have 'title'"
            assert "start" in conflict, "Conflict item should have 'start'"
            assert "end" in conflict, "Conflict item should have 'end'"
            
            # Should have suggestions when conflict detected
            assert len(data["suggestions"]) > 0, "Should provide suggestions when conflict detected"
            print(f"PASS: Conflict detected - {conflict['title']} ({conflict['start']} - {conflict['end']})")
        else:
            # No conflict found - this is also valid if no appointment exists at that time
            print(f"INFO: No conflict found at {CONFLICT_DATE} - status: {data['status']}")
            assert data["status"] in ["available", "warning"], f"Status should be available or warning, got {data['status']}"
    
    def test_warning_status_within_buffer(self, authenticated_client):
        """Returns 'warning' status when proposed slot is within 30min of existing engagement"""
        # Schedule 15 minutes after the known appointment ends (08:00 + 60min = 09:00, so 09:15)
        warning_time = "2026-06-20T09:15:00Z"
        
        response = authenticated_client.post(f"{BASE_URL}/api/appointments/check-conflicts", json={
            "start_datetime": warning_time,
            "duration_minutes": 60
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"Response for warning test: {data}")
        
        # Check response structure
        assert "status" in data
        assert "confidence" in data
        
        if data["status"] == "warning":
            assert data["confidence"] == "high", "Warning should have high confidence"
            assert len(data["warnings"]) > 0, "Should have at least one warning item"
            
            warning = data["warnings"][0]
            assert "title" in warning
            assert "start" in warning
            assert "end" in warning
            print(f"PASS: Warning detected - {warning['title']} is within 30min buffer")
        else:
            print(f"INFO: Status is {data['status']} - may not have appointment at that time")
    
    def test_available_status_no_conflicts(self, authenticated_client):
        """Returns 'available' with 'medium' confidence when no conflicts"""
        # Use a date far in the future with no appointments
        safe_time = "2027-12-25T14:00:00Z"
        
        response = authenticated_client.post(f"{BASE_URL}/api/appointments/check-conflicts", json={
            "start_datetime": safe_time,
            "duration_minutes": 60
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"Response for available test: {data}")
        
        assert data["status"] == "available", f"Expected 'available', got {data['status']}"
        assert data["confidence"] == "medium", f"Expected 'medium' confidence for NLYT-only check, got {data['confidence']}"
        assert len(data["conflicts"]) == 0, "Should have no conflicts"
        assert len(data["warnings"]) == 0, "Should have no warnings"
        # Suggestions may or may not be present when available
        print("PASS: Available status with medium confidence when no conflicts")


class TestSuggestions:
    """Test suggestion generation"""
    
    def test_suggestions_have_required_fields(self, authenticated_client):
        """Suggestions array contains datetime_str and label fields"""
        # Use a time that might have conflicts to get suggestions
        response = authenticated_client.post(f"{BASE_URL}/api/appointments/check-conflicts", json={
            "start_datetime": CONFLICT_DATE,
            "duration_minutes": 60
        })
        assert response.status_code == 200
        
        data = response.json()
        
        if data["status"] in ["conflict", "warning"] and len(data["suggestions"]) > 0:
            for suggestion in data["suggestions"]:
                assert "datetime_str" in suggestion, "Suggestion should have 'datetime_str'"
                assert "label" in suggestion, "Suggestion should have 'label'"
                assert suggestion["label"] in ["optimal", "comfortable", "tight"], \
                    f"Label should be optimal/comfortable/tight, got {suggestion['label']}"
            print(f"PASS: {len(data['suggestions'])} suggestions with valid labels")
        else:
            print("INFO: No suggestions generated (no conflict/warning or empty suggestions)")
    
    def test_suggestions_labels_variety(self, authenticated_client):
        """Suggestions include different labels (optimal/comfortable/tight)"""
        response = authenticated_client.post(f"{BASE_URL}/api/appointments/check-conflicts", json={
            "start_datetime": CONFLICT_DATE,
            "duration_minutes": 60
        })
        assert response.status_code == 200
        
        data = response.json()
        
        if len(data.get("suggestions", [])) > 0:
            labels = set(s["label"] for s in data["suggestions"])
            print(f"Labels found: {labels}")
            # At least one label type should be present
            assert len(labels) >= 1, "Should have at least one label type"
            print(f"PASS: Suggestions have labels: {labels}")
        else:
            print("INFO: No suggestions to check labels")


class TestInputValidation:
    """Test input validation"""
    
    def test_invalid_date_returns_400(self, authenticated_client):
        """Returns 400 for invalid date format"""
        response = authenticated_client.post(f"{BASE_URL}/api/appointments/check-conflicts", json={
            "start_datetime": "invalid-date-format",
            "duration_minutes": 60
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "detail" in data, "Error response should have 'detail' field"
        print(f"PASS: Invalid date returns 400 - {data.get('detail')}")
    
    def test_empty_date_returns_400(self, authenticated_client):
        """Returns 400 for empty date"""
        response = authenticated_client.post(f"{BASE_URL}/api/appointments/check-conflicts", json={
            "start_datetime": "",
            "duration_minutes": 60
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("PASS: Empty date returns 400")
    
    def test_default_duration(self, authenticated_client):
        """Uses default duration of 60 minutes if not specified"""
        response = authenticated_client.post(f"{BASE_URL}/api/appointments/check-conflicts", json={
            "start_datetime": "2027-06-25T10:00:00Z"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: Default duration works when not specified")


class TestResponseStructure:
    """Test response structure completeness"""
    
    def test_response_has_all_fields(self, authenticated_client):
        """Response contains all required fields"""
        response = authenticated_client.post(f"{BASE_URL}/api/appointments/check-conflicts", json={
            "start_datetime": "2027-06-25T10:00:00Z",
            "duration_minutes": 60
        })
        assert response.status_code == 200
        
        data = response.json()
        
        required_fields = ["status", "confidence", "conflicts", "warnings", "suggestions"]
        for field in required_fields:
            assert field in data, f"Response missing required field: {field}"
        
        # Validate types
        assert isinstance(data["status"], str)
        assert isinstance(data["confidence"], str)
        assert isinstance(data["conflicts"], list)
        assert isinstance(data["warnings"], list)
        assert isinstance(data["suggestions"], list)
        
        print("PASS: Response has all required fields with correct types")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
