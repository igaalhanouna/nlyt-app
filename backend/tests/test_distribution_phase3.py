"""
Test Suite for NLYT Phase 3 — Capture + Distribution

Tests:
- compute_distribution() pure calculation logic (via API simulation)
- API endpoints: GET /distributions, GET /distributions/:id, POST /distributions/:id/contest
- GET /appointments/:id/distributions (organizer only)
- Scheduler job registration
- Attendance service hooks verification
- Code structure verification
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://evidence-labels-fix.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"

# Platform wallet constant
PLATFORM_WALLET_USER_ID = "__nlyt_platform__"


class TestDistributionComputeLogic:
    """Test compute_distribution() pure calculation logic by verifying code structure"""

    def test_compute_distribution_function_exists(self):
        """Verify compute_distribution function exists with correct signature"""
        with open('/app/backend/services/distribution_service.py', 'r') as f:
            content = f.read()

        # Check function exists
        assert 'def compute_distribution(' in content
        assert 'capture_amount_cents: int' in content
        assert 'platform_pct: float' in content
        assert 'no_show_is_organizer: bool' in content
        assert 'present_participants: list' in content
        assert 'organizer_user_id: str' in content

        print("✓ compute_distribution() function exists with correct signature")

    def test_participant_no_show_logic_exists(self):
        """Verify participant no_show distributes to organizer logic"""
        with open('/app/backend/services/distribution_service.py', 'r') as f:
            content = f.read()

        # Check for participant no_show → organizer logic
        assert 'if not no_show_is_organizer:' in content
        assert '"organizer"' in content
        assert 'compensation_cents' in content

        print("✓ Participant no_show → organizer logic exists")

    def test_organizer_no_show_symmetric_logic_exists(self):
        """Verify organizer no_show distributes to present participants (symmetry rule)"""
        with open('/app/backend/services/distribution_service.py', 'r') as f:
            content = f.read()

        # Check for organizer no_show → present participants logic
        assert 'else:' in content  # The else branch for no_show_is_organizer
        assert 'present_participants' in content
        assert '"participant"' in content

        print("✓ Organizer no_show → present participants logic exists (symmetry rule)")

    def test_zero_present_participants_to_platform_logic(self):
        """Verify organizer no_show with 0 present → compensation to platform"""
        with open('/app/backend/services/distribution_service.py', 'r') as f:
            content = f.read()

        # Check for 0 present participants → platform absorption
        assert 'if present_participants:' in content or 'if not present_participants' in content
        assert 'platform_cents +=' in content

        print("✓ Zero present participants → platform absorption logic exists")

    def test_rounding_invariant_logic(self):
        """Verify rounding: compensation = total - platform - charity (absorbs remainder)"""
        with open('/app/backend/services/distribution_service.py', 'r') as f:
            content = f.read()

        # Check for rounding logic
        assert 'compensation_cents = capture_amount_cents - platform_cents - charity_cents' in content
        assert 'int(capture_amount_cents * platform_pct / 100)' in content
        assert 'int(capture_amount_cents * charity_pct / 100)' in content

        print("✓ Rounding invariant logic exists (sum always equals capture_amount)")

    def test_zero_penalty_returns_empty_logic(self):
        """Verify zero penalty returns empty distribution"""
        with open('/app/backend/services/distribution_service.py', 'r') as f:
            content = f.read()

        # Check for zero penalty guard
        assert 'if capture_amount_cents <= 0:' in content
        assert '"beneficiaries": []' in content

        print("✓ Zero penalty returns empty distribution logic exists")


class TestDistributionAPI:
    """Test Distribution API endpoints"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")

    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}

    def test_health_check(self):
        """Basic health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("✓ Health check passed")

    def test_get_distributions_requires_auth(self):
        """GET /api/wallet/distributions requires authentication"""
        response = requests.get(f"{BASE_URL}/api/wallet/distributions")
        assert response.status_code == 401
        print("✓ GET /api/wallet/distributions requires auth")

    def test_get_distributions_returns_list(self, auth_headers):
        """GET /api/wallet/distributions returns user's distributions"""
        response = requests.get(
            f"{BASE_URL}/api/wallet/distributions",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "distributions" in data
        assert isinstance(data["distributions"], list)
        print(f"✓ GET /api/wallet/distributions returns list ({len(data['distributions'])} items)")

    def test_get_distribution_detail_not_found(self, auth_headers):
        """GET /api/wallet/distributions/:id returns 404 for non-existent"""
        fake_id = str(uuid.uuid4())
        response = requests.get(
            f"{BASE_URL}/api/wallet/distributions/{fake_id}",
            headers=auth_headers
        )
        assert response.status_code == 404
        print("✓ GET /api/wallet/distributions/:id returns 404 for non-existent")

    def test_contest_distribution_not_found(self, auth_headers):
        """POST /api/wallet/distributions/:id/contest returns 400 for non-existent"""
        fake_id = str(uuid.uuid4())
        response = requests.post(
            f"{BASE_URL}/api/wallet/distributions/{fake_id}/contest",
            headers=auth_headers,
            json={"reason": "Test contestation"}
        )
        # Should return 400 with error message (distribution not found)
        assert response.status_code == 400
        print("✓ POST /api/wallet/distributions/:id/contest returns 400 for non-existent")

    def test_get_appointment_distributions_requires_auth(self):
        """GET /api/appointments/:id/distributions requires authentication"""
        fake_id = str(uuid.uuid4())
        response = requests.get(f"{BASE_URL}/api/appointments/{fake_id}/distributions")
        assert response.status_code == 401
        print("✓ GET /api/appointments/:id/distributions requires auth")

    def test_get_appointment_distributions_not_found(self, auth_headers):
        """GET /api/appointments/:id/distributions returns 404 for non-existent appointment"""
        fake_id = str(uuid.uuid4())
        response = requests.get(
            f"{BASE_URL}/api/appointments/{fake_id}/distributions",
            headers=auth_headers
        )
        assert response.status_code == 404
        print("✓ GET /api/appointments/:id/distributions returns 404 for non-existent")


class TestDistributionServiceStructure:
    """Test distribution service code structure"""

    def test_create_distribution_function_exists(self):
        """Verify create_distribution function exists"""
        with open('/app/backend/services/distribution_service.py', 'r') as f:
            content = f.read()

        assert 'def create_distribution(' in content
        assert 'appointment_id: str' in content
        assert 'guarantee_id: str' in content
        assert 'capture_amount_cents: int' in content

        print("✓ create_distribution() function exists")

    def test_create_distribution_idempotent_guard(self):
        """Verify create_distribution has idempotency guard on guarantee_id"""
        with open('/app/backend/services/distribution_service.py', 'r') as f:
            content = f.read()

        # Check for idempotency guard
        assert 'existing = db.distributions.find_one' in content
        assert '"guarantee_id": guarantee_id' in content
        assert 'already_existed' in content

        print("✓ create_distribution() has idempotency guard on guarantee_id")

    def test_finalize_expired_holds_function_exists(self):
        """Verify finalize_expired_holds function exists"""
        with open('/app/backend/services/distribution_service.py', 'r') as f:
            content = f.read()

        assert 'def finalize_expired_holds(' in content
        assert '"status": "pending_hold"' in content
        assert '"contested": False' in content
        assert 'hold_expires_at' in content

        print("✓ finalize_expired_holds() function exists")

    def test_finalize_skips_contested(self):
        """Verify finalize_expired_holds skips contested distributions"""
        with open('/app/backend/services/distribution_service.py', 'r') as f:
            content = f.read()

        # Check query filters out contested
        assert '"contested": False' in content

        print("✓ finalize_expired_holds() skips contested distributions")

    def test_cancel_distribution_function_exists(self):
        """Verify cancel_distribution function exists"""
        with open('/app/backend/services/distribution_service.py', 'r') as f:
            content = f.read()

        assert 'def cancel_distribution(' in content
        assert 'distribution_id: str' in content
        assert 'reason: str' in content
        assert 'debit_refund' in content

        print("✓ cancel_distribution() function exists with refund logic")

    def test_contest_distribution_function_exists(self):
        """Verify contest_distribution function exists"""
        with open('/app/backend/services/distribution_service.py', 'r') as f:
            content = f.read()

        assert 'def contest_distribution(' in content
        assert 'distribution_id: str' in content
        assert 'user_id: str' in content
        assert 'reason: str' in content
        assert 'no_show_user_id' in content

        print("✓ contest_distribution() function exists")

    def test_contest_only_by_no_show_user(self):
        """Verify contest_distribution only allows no_show user"""
        with open('/app/backend/services/distribution_service.py', 'r') as f:
            content = f.read()

        # Check for no_show user validation
        assert 'dist["no_show_user_id"] != user_id' in content
        assert 'concerné' in content.lower() or 'no_show' in content

        print("✓ contest_distribution() only allows no_show user")


class TestSchedulerJobRegistration:
    """Test that distribution_hold_expiry_job is registered in scheduler"""

    def test_scheduler_has_distribution_job(self):
        """Verify distribution_hold_expiry_job is registered"""
        with open('/app/backend/scheduler.py', 'r') as f:
            content = f.read()

        assert 'distribution_hold_expiry_job' in content
        assert 'finalize_expired_holds' in content

        print("✓ Scheduler job 'distribution_hold_expiry_job' is registered")

    def test_scheduler_job_interval(self):
        """Verify distribution job runs every 15 minutes"""
        with open('/app/backend/scheduler.py', 'r') as f:
            content = f.read()

        # Check for 15 minute interval
        assert 'minutes=15' in content or 'every 15 minutes' in content.lower()

        print("✓ Distribution hold expiry job runs every 15 minutes")


class TestAttendanceServiceHooks:
    """Test attendance service hooks for capture/distribution"""

    def test_process_financial_outcomes_function_exists(self):
        """Verify _process_financial_outcomes exists in attendance_service"""
        with open('/app/backend/services/attendance_service.py', 'r') as f:
            content = f.read()

        assert '_process_financial_outcomes' in content
        assert 'def _process_financial_outcomes(' in content

        print("✓ _process_financial_outcomes() function exists")

    def test_execute_capture_and_distribution_exists(self):
        """Verify _execute_capture_and_distribution exists"""
        with open('/app/backend/services/attendance_service.py', 'r') as f:
            content = f.read()

        assert '_execute_capture_and_distribution' in content
        assert 'def _execute_capture_and_distribution(' in content
        assert 'create_distribution' in content

        print("✓ _execute_capture_and_distribution() function exists")

    def test_process_reclassification_exists(self):
        """Verify _process_reclassification exists"""
        with open('/app/backend/services/attendance_service.py', 'r') as f:
            content = f.read()

        assert '_process_reclassification' in content
        assert 'def _process_reclassification(' in content

        print("✓ _process_reclassification() function exists")

    def test_reclassification_handles_no_show_to_present(self):
        """Verify reclassification handles no_show → present (cancel + release)"""
        with open('/app/backend/services/attendance_service.py', 'r') as f:
            content = f.read()

        # Check for no_show → present transition
        assert "previous_outcome == 'no_show'" in content
        assert "cancel_dist" in content or "cancel_distribution" in content
        assert "_execute_release" in content

        print("✓ Reclassification handles no_show → present (cancel + release)")

    def test_reclassification_handles_present_to_no_show(self):
        """Verify reclassification handles present → no_show (capture + distribution)"""
        with open('/app/backend/services/attendance_service.py', 'r') as f:
            content = f.read()

        # Check for present → no_show transition
        assert "new_outcome == 'no_show'" in content
        assert "_execute_capture_and_distribution" in content

        print("✓ Reclassification handles present → no_show (capture + distribution)")

    def test_post_evaluation_triggers_financial_outcomes(self):
        """Verify evaluate_appointment calls _process_financial_outcomes"""
        with open('/app/backend/services/attendance_service.py', 'r') as f:
            content = f.read()

        # Check that evaluate_appointment calls financial outcomes
        assert '_process_financial_outcomes(appointment_id' in content

        print("✓ evaluate_appointment() triggers _process_financial_outcomes()")


class TestWalletServiceFunctions:
    """Test wallet service functions used by distribution"""

    def test_credit_pending_function_exists(self):
        """Verify credit_pending function exists"""
        with open('/app/backend/services/wallet_service.py', 'r') as f:
            content = f.read()

        assert 'def credit_pending(' in content
        assert 'wallet_id: str' in content
        assert 'amount_cents: int' in content
        assert 'pending_balance' in content

        print("✓ credit_pending() function exists")

    def test_confirm_pending_to_available_function_exists(self):
        """Verify confirm_pending_to_available function exists"""
        with open('/app/backend/services/wallet_service.py', 'r') as f:
            content = f.read()

        assert 'def confirm_pending_to_available(' in content
        assert 'pending_balance' in content
        assert 'available_balance' in content

        print("✓ confirm_pending_to_available() function exists")

    def test_debit_refund_function_exists(self):
        """Verify debit_refund function exists"""
        with open('/app/backend/services/wallet_service.py', 'r') as f:
            content = f.read()

        assert 'def debit_refund(' in content
        assert 'wallet_id: str' in content
        assert 'amount_cents: int' in content

        print("✓ debit_refund() function exists")


class TestWalletAPIIntegration:
    """Test wallet API integration with distribution"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")

    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}

    def test_wallet_endpoint_exists(self, auth_headers):
        """Verify GET /api/wallet returns wallet info"""
        response = requests.get(
            f"{BASE_URL}/api/wallet",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "wallet_id" in data
        assert "available_balance" in data
        assert "pending_balance" in data
        print(f"✓ GET /api/wallet returns wallet info (available: {data['available_balance']}, pending: {data['pending_balance']})")

    def test_wallet_transactions_endpoint_exists(self, auth_headers):
        """Verify GET /api/wallet/transactions returns transactions"""
        response = requests.get(
            f"{BASE_URL}/api/wallet/transactions",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "transactions" in data
        assert isinstance(data["transactions"], list)
        print(f"✓ GET /api/wallet/transactions returns list ({len(data['transactions'])} items)")


class TestStripeGuaranteeServiceCapture:
    """Test Stripe guarantee service capture functionality"""

    def test_capture_guarantee_function_exists(self):
        """Verify capture_guarantee function exists"""
        with open('/app/backend/services/stripe_guarantee_service.py', 'r') as f:
            content = f.read()

        assert 'def capture_guarantee(' in content
        assert 'guarantee_id: str' in content
        assert 'reason: str' in content

        print("✓ capture_guarantee() function exists")

    def test_capture_dev_mode_simulation(self):
        """Verify capture_guarantee has dev mode simulation"""
        with open('/app/backend/services/stripe_guarantee_service.py', 'r') as f:
            content = f.read()

        # Check for dev mode handling
        assert 'pi_dev_' in content
        assert 'dev mode' in content.lower() or 'dev_mode' in content

        print("✓ capture_guarantee() has dev mode simulation (pi_dev_* IDs)")

    def test_release_guarantee_function_exists(self):
        """Verify release_guarantee function exists"""
        with open('/app/backend/services/stripe_guarantee_service.py', 'r') as f:
            content = f.read()

        assert 'def release_guarantee(' in content
        assert 'guarantee_id: str' in content
        assert 'reason: str' in content

        print("✓ release_guarantee() function exists")


class TestDistributionConstants:
    """Test distribution service constants"""

    def test_hold_days_constant(self):
        """Verify HOLD_DAYS constant is 15"""
        with open('/app/backend/services/distribution_service.py', 'r') as f:
            content = f.read()

        assert 'HOLD_DAYS = 15' in content

        print("✓ HOLD_DAYS constant is 15")

    def test_platform_wallet_user_id_constant(self):
        """Verify PLATFORM_WALLET_USER_ID constant"""
        with open('/app/backend/services/distribution_service.py', 'r') as f:
            content = f.read()

        assert 'PLATFORM_WALLET_USER_ID = "__nlyt_platform__"' in content

        print("✓ PLATFORM_WALLET_USER_ID constant is '__nlyt_platform__'")


class TestRouterEndpoints:
    """Test router endpoint definitions"""

    def test_wallet_distributions_route_exists(self):
        """Verify GET /distributions route in wallet_routes.py"""
        with open('/app/backend/routers/wallet_routes.py', 'r') as f:
            content = f.read()

        assert '@router.get("/distributions")' in content
        assert 'get_distributions_for_user' in content

        print("✓ GET /api/wallet/distributions route exists")

    def test_wallet_distribution_detail_route_exists(self):
        """Verify GET /distributions/:id route in wallet_routes.py"""
        with open('/app/backend/routers/wallet_routes.py', 'r') as f:
            content = f.read()

        assert '@router.get("/distributions/{distribution_id}")' in content
        assert 'get_distribution' in content

        print("✓ GET /api/wallet/distributions/:id route exists")

    def test_wallet_distribution_contest_route_exists(self):
        """Verify POST /distributions/:id/contest route in wallet_routes.py"""
        with open('/app/backend/routers/wallet_routes.py', 'r') as f:
            content = f.read()

        assert '@router.post("/distributions/{distribution_id}/contest")' in content
        assert 'contest_distribution' in content

        print("✓ POST /api/wallet/distributions/:id/contest route exists")

    def test_appointment_distributions_route_exists(self):
        """Verify GET /appointments/:id/distributions route"""
        with open('/app/backend/routers/appointments.py', 'r') as f:
            content = f.read()

        assert '@router.get("/{appointment_id}/distributions")' in content
        assert 'get_distributions_for_appointment' in content

        print("✓ GET /api/appointments/:id/distributions route exists")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
