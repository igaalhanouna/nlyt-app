"""
Test suite for Workspace Update (PUT /api/workspaces/{workspace_id}) feature
Tests: name/description update, validation, admin-only access
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"


class TestWorkspaceUpdate:
    """Tests for PUT /api/workspaces/{workspace_id} endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json().get("access_token")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    @pytest.fixture(scope="class")
    def workspace_id(self, auth_headers):
        """Get first workspace ID for the user"""
        response = requests.get(f"{BASE_URL}/api/workspaces/", headers=auth_headers)
        assert response.status_code == 200, f"Failed to list workspaces: {response.text}"
        workspaces = response.json().get("workspaces", [])
        assert len(workspaces) > 0, "No workspaces found for test user"
        return workspaces[0]["workspace_id"]
    
    @pytest.fixture(scope="class")
    def original_workspace(self, auth_headers, workspace_id):
        """Get original workspace data to restore after tests"""
        response = requests.get(f"{BASE_URL}/api/workspaces/{workspace_id}", headers=auth_headers)
        assert response.status_code == 200
        return response.json()
    
    def test_update_workspace_name_success(self, auth_headers, workspace_id):
        """Test updating workspace name successfully"""
        response = requests.put(
            f"{BASE_URL}/api/workspaces/{workspace_id}",
            headers=auth_headers,
            json={"name": "TEST_Updated Workspace Name"}
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data["name"] == "TEST_Updated Workspace Name"
        assert "workspace_id" in data
        assert data["workspace_id"] == workspace_id
    
    def test_update_workspace_description_success(self, auth_headers, workspace_id):
        """Test updating workspace description successfully"""
        response = requests.put(
            f"{BASE_URL}/api/workspaces/{workspace_id}",
            headers=auth_headers,
            json={"description": "TEST_Updated description for workspace"}
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data["description"] == "TEST_Updated description for workspace"
    
    def test_update_workspace_name_and_description(self, auth_headers, workspace_id):
        """Test updating both name and description"""
        response = requests.put(
            f"{BASE_URL}/api/workspaces/{workspace_id}",
            headers=auth_headers,
            json={
                "name": "TEST_Both Updated",
                "description": "TEST_Both description updated"
            }
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data["name"] == "TEST_Both Updated"
        assert data["description"] == "TEST_Both description updated"
    
    def test_update_workspace_empty_name_rejected(self, auth_headers, workspace_id):
        """Test that empty name is rejected with 400"""
        response = requests.put(
            f"{BASE_URL}/api/workspaces/{workspace_id}",
            headers=auth_headers,
            json={"name": ""}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data
        assert "vide" in data["detail"].lower() or "empty" in data["detail"].lower()
    
    def test_update_workspace_whitespace_name_rejected(self, auth_headers, workspace_id):
        """Test that whitespace-only name is rejected with 400"""
        response = requests.put(
            f"{BASE_URL}/api/workspaces/{workspace_id}",
            headers=auth_headers,
            json={"name": "   "}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
    
    def test_update_workspace_empty_description_allowed(self, auth_headers, workspace_id):
        """Test that empty description is allowed (clears description)"""
        response = requests.put(
            f"{BASE_URL}/api/workspaces/{workspace_id}",
            headers=auth_headers,
            json={"description": ""}
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data["description"] == ""
    
    def test_update_workspace_name_trimmed(self, auth_headers, workspace_id):
        """Test that name is trimmed of whitespace"""
        response = requests.put(
            f"{BASE_URL}/api/workspaces/{workspace_id}",
            headers=auth_headers,
            json={"name": "  TEST_Trimmed Name  "}
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data["name"] == "TEST_Trimmed Name"
    
    def test_update_workspace_description_trimmed(self, auth_headers, workspace_id):
        """Test that description is trimmed of whitespace"""
        response = requests.put(
            f"{BASE_URL}/api/workspaces/{workspace_id}",
            headers=auth_headers,
            json={"description": "  TEST_Trimmed Description  "}
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data["description"] == "TEST_Trimmed Description"
    
    def test_update_workspace_returns_updated_at(self, auth_headers, workspace_id):
        """Test that updated_at field is returned and updated"""
        response = requests.put(
            f"{BASE_URL}/api/workspaces/{workspace_id}",
            headers=auth_headers,
            json={"name": "TEST_Check Updated At"}
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert "updated_at" in data
    
    def test_update_workspace_unauthorized(self, workspace_id):
        """Test that unauthenticated request is rejected"""
        response = requests.put(
            f"{BASE_URL}/api/workspaces/{workspace_id}",
            headers={"Content-Type": "application/json"},
            json={"name": "TEST_Unauthorized"}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
    
    def test_get_workspace_after_update(self, auth_headers, workspace_id):
        """Test that GET returns updated data after PUT"""
        # First update
        update_response = requests.put(
            f"{BASE_URL}/api/workspaces/{workspace_id}",
            headers=auth_headers,
            json={"name": "TEST_Verify Persistence", "description": "TEST_Persisted desc"}
        )
        assert update_response.status_code == 200
        
        # Then GET to verify persistence
        get_response = requests.get(
            f"{BASE_URL}/api/workspaces/{workspace_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["name"] == "TEST_Verify Persistence"
        assert data["description"] == "TEST_Persisted desc"
    
    def test_restore_original_workspace(self, auth_headers, workspace_id, original_workspace):
        """Restore workspace to original state after tests"""
        response = requests.put(
            f"{BASE_URL}/api/workspaces/{workspace_id}",
            headers=auth_headers,
            json={
                "name": original_workspace.get("name", "Mon Workspace"),
                "description": original_workspace.get("description", "")
            }
        )
        assert response.status_code == 200, f"Failed to restore workspace: {response.text}"
        data = response.json()
        assert data["name"] == original_workspace.get("name", "Mon Workspace")
        print(f"Workspace restored to: name='{data['name']}', description='{data.get('description', '')}'")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
