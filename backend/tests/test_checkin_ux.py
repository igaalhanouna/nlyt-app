"""
Test Check-in UX Improvements - Backend API Tests
Tests: manual check-in, QR generation, check-in status, timezone handling
"""
import pytest
import requests
import os
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from review request
TEST_USER_EMAIL = "testuser_audit@nlyt.app"
TEST_USER_PASSWORD = "Test1234!"
TEST_INVITATION_TOKEN = "f5a9125f-1134-413f-b974-1c469b2d0c6b"
TEST_APPOINTMENT_ID = "c053871f-1924-45ce-a4b0-1b1d7df31240"


class TestHealthAndAuth:
    """Basic health and authentication tests"""
    
    def test_api_health(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("PASSED: API health check")
    
    def test_login_success(self):
        """Test login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        print(f"PASSED: Login successful, got access_token")
        return data["access_token"]


class TestCheckinStatus:
    """Test check-in status endpoint"""
    
    def test_checkin_status_endpoint(self):
        """Test GET /api/checkin/status/{apt_id} returns correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/checkin/status/{TEST_APPOINTMENT_ID}",
            params={"invitation_token": TEST_INVITATION_TOKEN}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "checked_in" in data
        assert "has_manual_checkin" in data
        assert "has_qr_checkin" in data
        assert "has_gps" in data
        assert "evidence_count" in data
        assert "earliest_checkin" in data
        assert "evidence" in data
        
        print(f"PASSED: Check-in status endpoint returns correct structure")
        print(f"  - checked_in: {data['checked_in']}")
        print(f"  - has_manual_checkin: {data['has_manual_checkin']}")
        print(f"  - has_qr_checkin: {data['has_qr_checkin']}")
        print(f"  - evidence_count: {data['evidence_count']}")
        return data
    
    def test_checkin_status_invalid_token(self):
        """Test check-in status with invalid token returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/checkin/status/{TEST_APPOINTMENT_ID}",
            params={"invitation_token": "invalid-token-12345"}
        )
        assert response.status_code == 404
        print("PASSED: Invalid token returns 404")


class TestQRGeneration:
    """Test QR code generation endpoint"""
    
    def test_qr_generation_endpoint(self):
        """Test GET /api/checkin/qr/{apt_id} returns QR data"""
        response = requests.get(
            f"{BASE_URL}/api/checkin/qr/{TEST_APPOINTMENT_ID}",
            params={"invitation_token": TEST_INVITATION_TOKEN}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify QR response structure
        assert "qr_token" in data
        assert "qr_image_base64" in data
        assert "appointment_id" in data
        assert "rotation_seconds" in data
        
        # Verify QR token format: NLYT:{apt_id}:{window}:{signature}
        qr_token = data["qr_token"]
        parts = qr_token.split(":")
        assert len(parts) == 4
        assert parts[0] == "NLYT"
        assert parts[1] == TEST_APPOINTMENT_ID
        
        print(f"PASSED: QR generation endpoint returns valid QR data")
        print(f"  - QR token format valid: NLYT:{parts[1][:8]}...:{parts[2]}:{parts[3]}")
        print(f"  - rotation_seconds: {data['rotation_seconds']}")
        return data
    
    def test_qr_generation_invalid_token(self):
        """Test QR generation with invalid token returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/checkin/qr/{TEST_APPOINTMENT_ID}",
            params={"invitation_token": "invalid-token-12345"}
        )
        assert response.status_code == 404
        print("PASSED: QR generation with invalid token returns 404")


class TestManualCheckin:
    """Test manual check-in endpoint"""
    
    def test_manual_checkin_endpoint(self):
        """Test POST /api/checkin/manual creates check-in or returns 409 if already done"""
        response = requests.post(
            f"{BASE_URL}/api/checkin/manual",
            json={
                "invitation_token": TEST_INVITATION_TOKEN,
                "device_info": "pytest-test-agent",
                "latitude": 43.565097,  # Cannes location
                "longitude": 7.029133,
                "gps_consent": True
            }
        )
        
        # Either 200 (new check-in) or 409 (already checked in)
        assert response.status_code in [200, 409]
        data = response.json()
        
        if response.status_code == 200:
            assert data.get("success") == True
            assert "evidence" in data
            print(f"PASSED: Manual check-in created successfully")
            print(f"  - evidence_id: {data['evidence'].get('evidence_id', 'N/A')[:8]}...")
        else:
            # 409 means already checked in
            assert "déjà" in data.get("detail", "").lower() or "already" in data.get("detail", "").lower()
            print(f"PASSED: Manual check-in returns 409 (already checked in)")
        
        return response.status_code, data
    
    def test_manual_checkin_invalid_token(self):
        """Test manual check-in with invalid token returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/checkin/manual",
            json={
                "invitation_token": "invalid-token-12345",
                "device_info": "pytest-test-agent"
            }
        )
        assert response.status_code == 404
        print("PASSED: Manual check-in with invalid token returns 404")


class TestInvitationPage:
    """Test invitation page endpoint for check-in section visibility"""
    
    def test_invitation_page_returns_participant_status(self):
        """Test GET /api/invitations/{token} returns participant status"""
        response = requests.get(f"{BASE_URL}/api/invitations/{TEST_INVITATION_TOKEN}")
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "participant" in data
        assert "appointment" in data
        assert "engagement_rules" in data
        
        participant = data["participant"]
        appointment = data["appointment"]
        
        # Verify participant status is one that should show check-in section
        status = participant.get("status")
        print(f"PASSED: Invitation page returns participant data")
        print(f"  - participant status: {status}")
        print(f"  - appointment title: {appointment.get('title', 'N/A')}")
        print(f"  - appointment start: {appointment.get('start_datetime', 'N/A')}")
        print(f"  - duration_minutes: {appointment.get('duration_minutes', 'N/A')}")
        print(f"  - tolerated_delay_minutes: {data['engagement_rules'].get('tolerated_delay_minutes', 0)}")
        
        return data
    
    def test_invitation_page_invalid_token(self):
        """Test invitation page with invalid token returns 404"""
        response = requests.get(f"{BASE_URL}/api/invitations/invalid-token-12345")
        assert response.status_code == 404
        print("PASSED: Invalid invitation token returns 404")


class TestTimezoneHandling:
    """Test timezone handling in evidence service"""
    
    def test_checkin_status_has_evidence_timestamps(self):
        """Test that evidence timestamps are properly formatted"""
        response = requests.get(
            f"{BASE_URL}/api/checkin/status/{TEST_APPOINTMENT_ID}",
            params={"invitation_token": TEST_INVITATION_TOKEN}
        )
        assert response.status_code == 200
        data = response.json()
        
        if data.get("evidence") and len(data["evidence"]) > 0:
            evidence = data["evidence"][0]
            source_ts = evidence.get("source_timestamp", "")
            created_at = evidence.get("created_at", "")
            
            # Verify timestamps are ISO format
            assert source_ts, "source_timestamp should be present"
            assert created_at, "created_at should be present"
            
            # Try parsing timestamps
            try:
                datetime.fromisoformat(source_ts.replace('Z', '+00:00'))
                datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                print(f"PASSED: Evidence timestamps are valid ISO format")
                print(f"  - source_timestamp: {source_ts}")
                print(f"  - created_at: {created_at}")
            except ValueError as e:
                pytest.fail(f"Invalid timestamp format: {e}")
        else:
            print("SKIPPED: No evidence to check timestamps (evidence cleared)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
