"""
Test: Charity Associations Migration to MongoDB (Iteration 150)

Tests:
- Public API: GET /api/charity-associations/ returns 8 active associations from MongoDB
- Public API: Response format unchanged (association_id, name, description, website, logo_url, is_active)
- Public API: GET /api/charity-associations/{id} returns correct association for all 8 IDs
- Admin API: GET /api/charity-associations/admin/list returns ALL associations including inactive (requires auth)
- Admin API: POST /api/charity-associations/admin/create creates new association with auto-generated ID
- Admin API: PUT /api/charity-associations/admin/{id} updates association fields
- Admin API: PATCH /api/charity-associations/admin/{id}/toggle toggles is_active
- Toggle behavior: Toggling off removes from public GET, toggling on makes it reappear
- Existing association_id format preserved (assoc_croix_rouge, assoc_restos_coeur, etc.)
- Admin endpoints require authentication (401 without JWT)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Expected 8 migrated associations
EXPECTED_ASSOCIATION_IDS = [
    "assoc_croix_rouge",
    "assoc_restos_coeur",
    "assoc_secours_populaire",
    "assoc_medecins_sans_frontieres",
    "assoc_unicef",
    "assoc_emmaus",
    "assoc_fondation_abbe_pierre",
    "assoc_action_contre_faim"
]


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "testuser_audit@nlyt.app",
        "password": "TestAudit123!"
    })
    if response.status_code == 200:
        data = response.json()
        # API returns access_token, not token
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    }


class TestPublicAPI:
    """Tests for public charity associations API"""
    
    def test_list_associations_returns_8_active(self):
        """GET /api/charity-associations/ returns 8 active associations"""
        response = requests.get(f"{BASE_URL}/api/charity-associations/")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "associations" in data, "Response should have 'associations' key"
        assert "count" in data, "Response should have 'count' key"
        
        associations = data["associations"]
        assert len(associations) >= 8, f"Expected at least 8 associations, got {len(associations)}"
        
        # All should be active
        for assoc in associations:
            assert assoc.get("is_active") == True, f"Association {assoc.get('association_id')} should be active"
    
    def test_response_format_unchanged(self):
        """Response format has required fields: association_id, name, description, website, logo_url, is_active"""
        response = requests.get(f"{BASE_URL}/api/charity-associations/")
        assert response.status_code == 200
        
        data = response.json()
        associations = data["associations"]
        assert len(associations) > 0, "Should have at least one association"
        
        required_fields = ["association_id", "name", "description", "website", "logo_url", "is_active"]
        for assoc in associations:
            for field in required_fields:
                assert field in assoc, f"Missing field '{field}' in association {assoc.get('association_id', 'unknown')}"
    
    def test_all_8_expected_ids_present(self):
        """All 8 expected association IDs are present"""
        response = requests.get(f"{BASE_URL}/api/charity-associations/")
        assert response.status_code == 200
        
        data = response.json()
        returned_ids = [a["association_id"] for a in data["associations"]]
        
        for expected_id in EXPECTED_ASSOCIATION_IDS:
            assert expected_id in returned_ids, f"Expected association '{expected_id}' not found in response"
    
    def test_get_single_association_by_id(self):
        """GET /api/charity-associations/{id} returns correct association for all 8 IDs"""
        for assoc_id in EXPECTED_ASSOCIATION_IDS:
            response = requests.get(f"{BASE_URL}/api/charity-associations/{assoc_id}")
            assert response.status_code == 200, f"Failed to get {assoc_id}: {response.status_code}"
            
            data = response.json()
            assert data["association_id"] == assoc_id, f"Returned ID mismatch for {assoc_id}"
            assert "name" in data, f"Missing 'name' for {assoc_id}"
            assert data["is_active"] == True, f"{assoc_id} should be active"
    
    def test_get_nonexistent_association_returns_404(self):
        """GET /api/charity-associations/{id} returns 404 for non-existent ID"""
        response = requests.get(f"{BASE_URL}/api/charity-associations/assoc_nonexistent_xyz")
        assert response.status_code == 404


class TestAdminAPIAuth:
    """Tests for admin API authentication requirements"""
    
    def test_admin_list_requires_auth(self):
        """GET /api/charity-associations/admin/list returns 401 without JWT"""
        response = requests.get(f"{BASE_URL}/api/charity-associations/admin/list")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_admin_create_requires_auth(self):
        """POST /api/charity-associations/admin/create returns 401 without JWT"""
        response = requests.post(f"{BASE_URL}/api/charity-associations/admin/create", json={
            "name": "Test Association"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_admin_update_requires_auth(self):
        """PUT /api/charity-associations/admin/{id} returns 401 without JWT"""
        response = requests.put(f"{BASE_URL}/api/charity-associations/admin/assoc_croix_rouge", json={
            "name": "Updated Name"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_admin_toggle_requires_auth(self):
        """PATCH /api/charity-associations/admin/{id}/toggle returns 401 without JWT"""
        response = requests.patch(f"{BASE_URL}/api/charity-associations/admin/assoc_croix_rouge/toggle")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestAdminAPI:
    """Tests for admin CRUD operations"""
    
    def test_admin_list_returns_all_associations(self, auth_headers):
        """GET /api/charity-associations/admin/list returns ALL associations including inactive"""
        response = requests.get(f"{BASE_URL}/api/charity-associations/admin/list", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "associations" in data
        assert "count" in data
        
        # Should have at least 8 (the migrated ones) + possibly charity-001 legacy
        assert len(data["associations"]) >= 8, f"Expected at least 8 associations, got {len(data['associations'])}"
    
    def test_admin_create_association(self, auth_headers):
        """POST /api/charity-associations/admin/create creates new association with auto-generated ID"""
        import time
        test_name = f"TEST_Association Iter150_{int(time.time())}"
        response = requests.post(
            f"{BASE_URL}/api/charity-associations/admin/create",
            headers=auth_headers,
            json={
                "name": test_name,
                "description": "Test association for iteration 150",
                "website": "https://test-iter150.example.com",
                "contact_email": "test@iter150.example.com"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "association_id" in data, "Response should have 'association_id'"
        assert data["association_id"].startswith("assoc_"), f"ID should start with 'assoc_', got {data['association_id']}"
        assert data["name"] == test_name
        assert data["is_active"] == True, "New association should be active by default"
        
        # Store for cleanup
        pytest.created_assoc_id = data["association_id"]
    
    def test_admin_update_association(self, auth_headers):
        """PUT /api/charity-associations/admin/{id} updates association fields"""
        # Use the created association from previous test
        assoc_id = getattr(pytest, 'created_assoc_id', None)
        if not assoc_id:
            pytest.skip("No test association created")
        
        new_description = "Updated description for iter150 test"
        response = requests.put(
            f"{BASE_URL}/api/charity-associations/admin/{assoc_id}",
            headers=auth_headers,
            json={
                "description": new_description
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["description"] == new_description, "Description should be updated"
        
        # Verify with GET
        get_response = requests.get(f"{BASE_URL}/api/charity-associations/{assoc_id}")
        assert get_response.status_code == 200
        assert get_response.json()["description"] == new_description
    
    def test_admin_toggle_deactivates_association(self, auth_headers):
        """PATCH /api/charity-associations/admin/{id}/toggle deactivates association"""
        assoc_id = getattr(pytest, 'created_assoc_id', None)
        if not assoc_id:
            pytest.skip("No test association created")
        
        # Toggle OFF
        response = requests.patch(
            f"{BASE_URL}/api/charity-associations/admin/{assoc_id}/toggle",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["is_active"] == False, "Association should be deactivated"
        
        # Verify it's NOT in public list
        public_response = requests.get(f"{BASE_URL}/api/charity-associations/")
        assert public_response.status_code == 200
        public_ids = [a["association_id"] for a in public_response.json()["associations"]]
        assert assoc_id not in public_ids, "Deactivated association should not appear in public list"
        
        # Verify GET by ID returns 404 for inactive
        get_response = requests.get(f"{BASE_URL}/api/charity-associations/{assoc_id}")
        assert get_response.status_code == 404, "Inactive association should return 404 on public GET"
    
    def test_admin_toggle_reactivates_association(self, auth_headers):
        """PATCH /api/charity-associations/admin/{id}/toggle reactivates association"""
        assoc_id = getattr(pytest, 'created_assoc_id', None)
        if not assoc_id:
            pytest.skip("No test association created")
        
        # Toggle ON
        response = requests.patch(
            f"{BASE_URL}/api/charity-associations/admin/{assoc_id}/toggle",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["is_active"] == True, "Association should be reactivated"
        
        # Verify it's back in public list
        public_response = requests.get(f"{BASE_URL}/api/charity-associations/")
        assert public_response.status_code == 200
        public_ids = [a["association_id"] for a in public_response.json()["associations"]]
        assert assoc_id in public_ids, "Reactivated association should appear in public list"
    
    def test_admin_create_duplicate_id_returns_409(self, auth_headers):
        """POST /api/charity-associations/admin/create returns 409 for duplicate ID (same slug)"""
        import time
        # First create a test association
        test_name = f"TEST_Duplicate Check {int(time.time())}"
        response1 = requests.post(
            f"{BASE_URL}/api/charity-associations/admin/create",
            headers=auth_headers,
            json={"name": test_name, "description": "First"}
        )
        assert response1.status_code == 200, f"First create failed: {response1.status_code} - {response1.text}"
        created_id = response1.json()["association_id"]
        
        # Try to create with exact same name (will generate same slug/ID)
        response2 = requests.post(
            f"{BASE_URL}/api/charity-associations/admin/create",
            headers=auth_headers,
            json={"name": test_name, "description": "Second"}
        )
        assert response2.status_code == 409, f"Expected 409 for duplicate ID, got {response2.status_code}"
        
        # Cleanup: deactivate the test association
        requests.patch(
            f"{BASE_URL}/api/charity-associations/admin/{created_id}/toggle",
            headers=auth_headers
        )
    
    def test_admin_update_nonexistent_returns_404(self, auth_headers):
        """PUT /api/charity-associations/admin/{id} returns 404 for non-existent ID"""
        response = requests.put(
            f"{BASE_URL}/api/charity-associations/admin/assoc_nonexistent_xyz",
            headers=auth_headers,
            json={"name": "Test"}
        )
        assert response.status_code == 404
    
    def test_admin_toggle_nonexistent_returns_404(self, auth_headers):
        """PATCH /api/charity-associations/admin/{id}/toggle returns 404 for non-existent ID"""
        response = requests.patch(
            f"{BASE_URL}/api/charity-associations/admin/assoc_nonexistent_xyz/toggle",
            headers=auth_headers
        )
        assert response.status_code == 404


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_association(self, auth_headers):
        """Deactivate test association created during tests"""
        assoc_id = getattr(pytest, 'created_assoc_id', None)
        if not assoc_id:
            pytest.skip("No test association to clean up")
        
        # First check if it's active
        admin_response = requests.get(f"{BASE_URL}/api/charity-associations/admin/list", headers=auth_headers)
        if admin_response.status_code == 200:
            associations = admin_response.json().get("associations", [])
            test_assoc = next((a for a in associations if a["association_id"] == assoc_id), None)
            if test_assoc and test_assoc.get("is_active"):
                # Deactivate it
                requests.patch(
                    f"{BASE_URL}/api/charity-associations/admin/{assoc_id}/toggle",
                    headers=auth_headers
                )
        
        print(f"Cleaned up test association: {assoc_id}")
