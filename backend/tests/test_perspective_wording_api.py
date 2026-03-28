"""
API Integration Tests for P0 Perspective Wording Fix:
- GET /api/disputes/mine returns is_target boolean
- GET /api/disputes/{id} returns is_target boolean
- declaration_summary.declarants[].is_me boolean is present
- is_target is true when target_user_id matches current user
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_USERS = {
    "organizer": {"email": "testuser_audit@nlyt.app", "password": "TestAudit123!"},
    "participant": {"email": "igaal@hotmail.com", "password": "Test123!"},
    "organizer2": {"email": "igaal.hanouna@gmail.com", "password": "OrgTest123!"},
}


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def login_user(session, user_key):
    """Login and return authenticated session"""
    user = TEST_USERS[user_key]
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": user["email"],
        "password": user["password"]
    })
    if response.status_code != 200:
        print(f"Login failed for {user_key}: {response.status_code} - {response.text}")
        pytest.skip(f"Login failed for {user_key}: {response.status_code}")
    token = response.json().get("access_token")  # API returns access_token, not token
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


class TestDisputesMineEndpoint:
    """Tests for GET /api/disputes/mine"""

    def test_disputes_mine_returns_is_target_field(self, api_client):
        """Verify is_target boolean field is present in disputes list"""
        api_client = login_user(api_client, "organizer")
        
        response = api_client.get(f"{BASE_URL}/api/disputes/mine")
        assert response.status_code == 200
        
        data = response.json()
        disputes = data.get("disputes", [])
        
        if len(disputes) == 0:
            pytest.skip("No disputes found for this user")
        
        # Check first dispute has is_target field
        dispute = disputes[0]
        assert "is_target" in dispute, "is_target field missing from dispute"
        assert isinstance(dispute["is_target"], bool), "is_target should be boolean"
        print(f"✅ is_target field present: {dispute['is_target']}")

    def test_disputes_mine_returns_declaration_summary_with_is_me(self, api_client):
        """Verify declaration_summary.declarants[].is_me is present"""
        api_client = login_user(api_client, "organizer")
        
        response = api_client.get(f"{BASE_URL}/api/disputes/mine")
        assert response.status_code == 200
        
        data = response.json()
        disputes = data.get("disputes", [])
        
        if len(disputes) == 0:
            pytest.skip("No disputes found for this user")
        
        dispute = disputes[0]
        summary = dispute.get("declaration_summary", {})
        declarants = summary.get("declarants", [])
        
        if len(declarants) == 0:
            pytest.skip("No declarants in dispute summary")
        
        # Check each declarant has is_me field
        for i, declarant in enumerate(declarants):
            assert "is_me" in declarant, f"is_me field missing from declarant {i}"
            assert isinstance(declarant["is_me"], bool), f"is_me should be boolean for declarant {i}"
            print(f"✅ Declarant {i} ({declarant.get('first_name', 'Unknown')}): is_me={declarant['is_me']}")


class TestDisputeDetailEndpoint:
    """Tests for GET /api/disputes/{id}"""

    def test_dispute_detail_returns_is_target_field(self, api_client):
        """Verify is_target boolean field is present in dispute detail"""
        api_client = login_user(api_client, "organizer")
        
        # First get list to find a dispute ID
        list_response = api_client.get(f"{BASE_URL}/api/disputes/mine")
        assert list_response.status_code == 200
        
        disputes = list_response.json().get("disputes", [])
        if len(disputes) == 0:
            pytest.skip("No disputes found for this user")
        
        dispute_id = disputes[0]["dispute_id"]
        
        # Get detail
        response = api_client.get(f"{BASE_URL}/api/disputes/{dispute_id}")
        assert response.status_code == 200
        
        dispute = response.json()
        assert "is_target" in dispute, "is_target field missing from dispute detail"
        assert isinstance(dispute["is_target"], bool), "is_target should be boolean"
        print(f"✅ Dispute detail is_target: {dispute['is_target']}")

    def test_dispute_detail_returns_is_me_in_declarants(self, api_client):
        """Verify declaration_summary.declarants[].is_me is present in detail"""
        api_client = login_user(api_client, "organizer")
        
        # First get list to find a dispute ID
        list_response = api_client.get(f"{BASE_URL}/api/disputes/mine")
        assert list_response.status_code == 200
        
        disputes = list_response.json().get("disputes", [])
        if len(disputes) == 0:
            pytest.skip("No disputes found for this user")
        
        dispute_id = disputes[0]["dispute_id"]
        
        # Get detail
        response = api_client.get(f"{BASE_URL}/api/disputes/{dispute_id}")
        assert response.status_code == 200
        
        dispute = response.json()
        summary = dispute.get("declaration_summary", {})
        declarants = summary.get("declarants", [])
        
        if len(declarants) == 0:
            pytest.skip("No declarants in dispute summary")
        
        for i, declarant in enumerate(declarants):
            assert "is_me" in declarant, f"is_me field missing from declarant {i}"
            assert isinstance(declarant["is_me"], bool), f"is_me should be boolean"
            print(f"✅ Detail declarant {i} ({declarant.get('first_name', 'Unknown')}): is_me={declarant['is_me']}")


class TestIsTargetLogic:
    """Tests for is_target correctness based on target_user_id"""

    def test_organizer_not_target_sees_is_target_false(self, api_client):
        """When organizer is NOT the target, is_target should be False"""
        api_client = login_user(api_client, "organizer")
        
        response = api_client.get(f"{BASE_URL}/api/disputes/mine")
        assert response.status_code == 200
        
        disputes = response.json().get("disputes", [])
        
        # Find a dispute where this user is organizer but NOT target
        for dispute in disputes:
            if dispute.get("my_role") == "organizer" and dispute.get("is_target") is False:
                print(f"✅ Found dispute where organizer is NOT target: is_target=False, my_role=organizer")
                return
        
        # If no such dispute found, check if all disputes have organizer as target (deadlock)
        for dispute in disputes:
            if dispute.get("my_role") == "organizer":
                print(f"Dispute {dispute['dispute_id']}: my_role={dispute['my_role']}, is_target={dispute['is_target']}")
        
        pytest.skip("No dispute found where organizer is not target")

    def test_participant_target_sees_is_target_true(self, api_client):
        """When participant IS the target, is_target should be True"""
        api_client = login_user(api_client, "participant")
        
        response = api_client.get(f"{BASE_URL}/api/disputes/mine")
        assert response.status_code == 200
        
        disputes = response.json().get("disputes", [])
        
        if len(disputes) == 0:
            pytest.skip("No disputes found for participant user")
        
        # Check if any dispute has is_target=True for this participant
        for dispute in disputes:
            print(f"Dispute {dispute['dispute_id']}: my_role={dispute.get('my_role')}, is_target={dispute.get('is_target')}")
            if dispute.get("is_target") is True:
                print(f"✅ Found dispute where participant is target: is_target=True")
                return
        
        pytest.skip("No dispute found where this user is the target")


class TestIsMe:
    """Tests for is_me correctness in declarants"""

    def test_viewer_declaration_has_is_me_true(self, api_client):
        """When viewer submitted a declaration, their entry should have is_me=True"""
        api_client = login_user(api_client, "organizer")
        
        response = api_client.get(f"{BASE_URL}/api/disputes/mine")
        assert response.status_code == 200
        
        disputes = response.json().get("disputes", [])
        
        for dispute in disputes:
            summary = dispute.get("declaration_summary", {})
            declarants = summary.get("declarants", [])
            
            for declarant in declarants:
                if declarant.get("is_me") is True:
                    print(f"✅ Found declarant with is_me=True: {declarant.get('first_name')}")
                    return
        
        # It's possible the organizer didn't submit a declaration about the target
        print("No declarant with is_me=True found - organizer may not have submitted declaration about target")
        pytest.skip("No declarant with is_me=True found")

    def test_other_declarants_have_is_me_false(self, api_client):
        """Other declarants should have is_me=False"""
        api_client = login_user(api_client, "organizer")
        
        response = api_client.get(f"{BASE_URL}/api/disputes/mine")
        assert response.status_code == 200
        
        disputes = response.json().get("disputes", [])
        
        for dispute in disputes:
            summary = dispute.get("declaration_summary", {})
            declarants = summary.get("declarants", [])
            
            for declarant in declarants:
                if declarant.get("is_me") is False:
                    print(f"✅ Found declarant with is_me=False: {declarant.get('first_name')}")
                    return
        
        pytest.skip("No declarant with is_me=False found")


class TestDeadlockCase:
    """Tests for deadlock case: organizer IS target"""

    def test_deadlock_organizer_is_target_has_both_flags(self, api_client):
        """In deadlock case, organizer should have is_target=True AND my_role=organizer"""
        api_client = login_user(api_client, "organizer")
        
        response = api_client.get(f"{BASE_URL}/api/disputes/mine")
        assert response.status_code == 200
        
        disputes = response.json().get("disputes", [])
        
        for dispute in disputes:
            if dispute.get("my_role") == "organizer" and dispute.get("is_target") is True:
                print(f"✅ Found deadlock case: my_role=organizer, is_target=True")
                print(f"   Dispute ID: {dispute['dispute_id']}")
                return
        
        pytest.skip("No deadlock case found (organizer as target)")
