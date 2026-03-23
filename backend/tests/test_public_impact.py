"""
Test Public Impact API — NLYT
Tests GET /api/impact endpoint (public, no auth required)

Features tested:
- Public access (no authentication required)
- Response structure validation
- Associations sorted by total_cents desc
- Data consistency checks
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestPublicImpactAPI:
    """Tests for GET /api/impact public endpoint"""

    def test_impact_endpoint_is_public_no_auth_required(self):
        """GET /api/impact should return 200 without any authentication"""
        response = requests.get(f"{BASE_URL}/api/impact")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/impact returns 200 without authentication (public endpoint)")

    def test_impact_returns_total_captured_cents(self):
        """Response should include total_captured_cents"""
        response = requests.get(f"{BASE_URL}/api/impact")
        assert response.status_code == 200
        data = response.json()
        assert "total_captured_cents" in data, "Missing total_captured_cents"
        assert isinstance(data["total_captured_cents"], int), "total_captured_cents should be int"
        print(f"✓ total_captured_cents: {data['total_captured_cents']}")

    def test_impact_returns_total_distributed_cents(self):
        """Response should include total_distributed_cents"""
        response = requests.get(f"{BASE_URL}/api/impact")
        assert response.status_code == 200
        data = response.json()
        assert "total_distributed_cents" in data, "Missing total_distributed_cents"
        assert isinstance(data["total_distributed_cents"], int), "total_distributed_cents should be int"
        print(f"✓ total_distributed_cents: {data['total_distributed_cents']}")

    def test_impact_returns_total_charity_cents(self):
        """Response should include total_charity_cents"""
        response = requests.get(f"{BASE_URL}/api/impact")
        assert response.status_code == 200
        data = response.json()
        assert "total_charity_cents" in data, "Missing total_charity_cents"
        assert isinstance(data["total_charity_cents"], int), "total_charity_cents should be int"
        print(f"✓ total_charity_cents: {data['total_charity_cents']}")

    def test_impact_returns_distributions_count(self):
        """Response should include distributions_count"""
        response = requests.get(f"{BASE_URL}/api/impact")
        assert response.status_code == 200
        data = response.json()
        assert "distributions_count" in data, "Missing distributions_count"
        assert isinstance(data["distributions_count"], int), "distributions_count should be int"
        print(f"✓ distributions_count: {data['distributions_count']}")

    def test_impact_returns_events_count(self):
        """Response should include events_count"""
        response = requests.get(f"{BASE_URL}/api/impact")
        assert response.status_code == 200
        data = response.json()
        assert "events_count" in data, "Missing events_count"
        assert isinstance(data["events_count"], int), "events_count should be int"
        print(f"✓ events_count: {data['events_count']}")

    def test_impact_returns_participants_count(self):
        """Response should include participants_count"""
        response = requests.get(f"{BASE_URL}/api/impact")
        assert response.status_code == 200
        data = response.json()
        assert "participants_count" in data, "Missing participants_count"
        assert isinstance(data["participants_count"], int), "participants_count should be int"
        print(f"✓ participants_count: {data['participants_count']}")

    def test_impact_returns_refreshed_at_timestamp(self):
        """Response should include refreshed_at timestamp"""
        response = requests.get(f"{BASE_URL}/api/impact")
        assert response.status_code == 200
        data = response.json()
        assert "refreshed_at" in data, "Missing refreshed_at"
        assert isinstance(data["refreshed_at"], str), "refreshed_at should be string (ISO timestamp)"
        assert len(data["refreshed_at"]) > 10, "refreshed_at should be a valid ISO timestamp"
        print(f"✓ refreshed_at: {data['refreshed_at']}")

    def test_impact_returns_associations_array(self):
        """Response should include associations array"""
        response = requests.get(f"{BASE_URL}/api/impact")
        assert response.status_code == 200
        data = response.json()
        assert "associations" in data, "Missing associations"
        assert isinstance(data["associations"], list), "associations should be a list"
        print(f"✓ associations array with {len(data['associations'])} items")

    def test_impact_associations_have_required_fields(self):
        """Each association should have name, total_cents, distributions_count, events_count"""
        response = requests.get(f"{BASE_URL}/api/impact")
        assert response.status_code == 200
        data = response.json()
        
        if len(data["associations"]) == 0:
            pytest.skip("No associations in data to validate")
        
        for assoc in data["associations"]:
            assert "association_id" in assoc, "Missing association_id"
            assert "name" in assoc, "Missing name"
            assert "total_cents" in assoc, "Missing total_cents"
            assert "distributions_count" in assoc, "Missing distributions_count"
            assert "events_count" in assoc, "Missing events_count"
            print(f"  ✓ Association: {assoc['name']} - {assoc['total_cents']}c, {assoc['distributions_count']} distributions, {assoc['events_count']} events")
        
        print(f"✓ All {len(data['associations'])} associations have required fields")

    def test_impact_associations_sorted_by_total_cents_desc(self):
        """Associations should be sorted by total_cents descending"""
        response = requests.get(f"{BASE_URL}/api/impact")
        assert response.status_code == 200
        data = response.json()
        
        if len(data["associations"]) < 2:
            pytest.skip("Need at least 2 associations to verify sorting")
        
        totals = [a["total_cents"] for a in data["associations"]]
        assert totals == sorted(totals, reverse=True), f"Associations not sorted by total_cents desc: {totals}"
        print(f"✓ Associations sorted by total_cents desc: {totals}")

    def test_impact_currency_is_eur(self):
        """Currency should be 'eur'"""
        response = requests.get(f"{BASE_URL}/api/impact")
        assert response.status_code == 200
        data = response.json()
        assert data.get("currency") == "eur", f"Expected currency 'eur', got {data.get('currency')}"
        print("✓ Currency is 'eur'")

    def test_impact_demo_data_present(self):
        """Demo data should be present: 5 distributions, 2 associations"""
        response = requests.get(f"{BASE_URL}/api/impact")
        assert response.status_code == 200
        data = response.json()
        
        # Verify demo data expectations
        assert data["distributions_count"] >= 5, f"Expected at least 5 distributions, got {data['distributions_count']}"
        assert len(data["associations"]) >= 2, f"Expected at least 2 associations, got {len(data['associations'])}"
        
        # Check for expected associations
        assoc_ids = [a["association_id"] for a in data["associations"]]
        assert "asso_medecins" in assoc_ids, "Missing asso_medecins association"
        assert "asso_croix_rouge" in assoc_ids, "Missing asso_croix_rouge association"
        
        print(f"✓ Demo data present: {data['distributions_count']} distributions, {len(data['associations'])} associations")
        print(f"  - Médecins Sans Frontières: present")
        print(f"  - Croix-Rouge française: present")

    def test_impact_total_charity_equals_sum_of_associations(self):
        """total_charity_cents should equal sum of all association total_cents"""
        response = requests.get(f"{BASE_URL}/api/impact")
        assert response.status_code == 200
        data = response.json()
        
        sum_associations = sum(a["total_cents"] for a in data["associations"])
        assert data["total_charity_cents"] == sum_associations, \
            f"total_charity_cents ({data['total_charity_cents']}) != sum of associations ({sum_associations})"
        print(f"✓ total_charity_cents ({data['total_charity_cents']}) = sum of associations ({sum_associations})")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
