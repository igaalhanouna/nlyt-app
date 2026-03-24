"""
Test Impact Caritatif Feature — NLYT V1
Tests GET /api/impact and GET /api/impact/charity endpoints

Features tested:
- GET /api/impact (existing endpoint) returns correct structure
- GET /api/impact/charity returns charity-focused impact with contributions
- Pagination works with skip/limit params
- Response structure validation (total_charity_cents, associations, contributions, payout_status, payout_message)
- Correct French wording (fléchés, not reversé/donné)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestPublicImpactEndpoint:
    """Tests for GET /api/impact (existing public endpoint)"""

    def test_impact_endpoint_returns_200(self):
        """GET /api/impact should return 200 without authentication"""
        response = requests.get(f"{BASE_URL}/api/impact")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/impact returns 200 (public endpoint)")

    def test_impact_returns_total_charity_cents(self):
        """Response should include total_charity_cents"""
        response = requests.get(f"{BASE_URL}/api/impact")
        assert response.status_code == 200
        data = response.json()
        assert "total_charity_cents" in data, "Missing total_charity_cents"
        assert isinstance(data["total_charity_cents"], int), "total_charity_cents should be int"
        print(f"✓ total_charity_cents: {data['total_charity_cents']}")

    def test_impact_returns_associations_array(self):
        """Response should include associations array"""
        response = requests.get(f"{BASE_URL}/api/impact")
        assert response.status_code == 200
        data = response.json()
        assert "associations" in data, "Missing associations"
        assert isinstance(data["associations"], list), "associations should be a list"
        print(f"✓ associations array with {len(data['associations'])} items")


class TestCharityImpactEndpoint:
    """Tests for GET /api/impact/charity (new charity-focused endpoint)"""

    def test_charity_endpoint_returns_200(self):
        """GET /api/impact/charity should return 200 without authentication"""
        response = requests.get(f"{BASE_URL}/api/impact/charity")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/impact/charity returns 200 (public endpoint)")

    def test_charity_returns_total_charity_cents(self):
        """Response should include total_charity_cents"""
        response = requests.get(f"{BASE_URL}/api/impact/charity")
        assert response.status_code == 200
        data = response.json()
        assert "total_charity_cents" in data, "Missing total_charity_cents"
        assert isinstance(data["total_charity_cents"], int), "total_charity_cents should be int"
        print(f"✓ total_charity_cents: {data['total_charity_cents']}")

    def test_charity_returns_total_distributed_cents(self):
        """Response should include total_distributed_cents"""
        response = requests.get(f"{BASE_URL}/api/impact/charity")
        assert response.status_code == 200
        data = response.json()
        assert "total_distributed_cents" in data, "Missing total_distributed_cents"
        assert isinstance(data["total_distributed_cents"], int), "total_distributed_cents should be int"
        print(f"✓ total_distributed_cents: {data['total_distributed_cents']}")

    def test_charity_returns_associations_array(self):
        """Response should include associations array"""
        response = requests.get(f"{BASE_URL}/api/impact/charity")
        assert response.status_code == 200
        data = response.json()
        assert "associations" in data, "Missing associations"
        assert isinstance(data["associations"], list), "associations should be a list"
        print(f"✓ associations array with {len(data['associations'])} items")

    def test_charity_returns_events_count(self):
        """Response should include events_count"""
        response = requests.get(f"{BASE_URL}/api/impact/charity")
        assert response.status_code == 200
        data = response.json()
        assert "events_count" in data, "Missing events_count"
        assert isinstance(data["events_count"], int), "events_count should be int"
        print(f"✓ events_count: {data['events_count']}")

    def test_charity_returns_participants_count(self):
        """Response should include participants_count"""
        response = requests.get(f"{BASE_URL}/api/impact/charity")
        assert response.status_code == 200
        data = response.json()
        assert "participants_count" in data, "Missing participants_count"
        assert isinstance(data["participants_count"], int), "participants_count should be int"
        print(f"✓ participants_count: {data['participants_count']}")

    def test_charity_returns_currency_eur(self):
        """Response should have currency='eur'"""
        response = requests.get(f"{BASE_URL}/api/impact/charity")
        assert response.status_code == 200
        data = response.json()
        assert data.get("currency") == "eur", f"Expected currency 'eur', got {data.get('currency')}"
        print("✓ currency is 'eur'")

    def test_charity_returns_payout_status_accumulating(self):
        """Response should have payout_status='accumulating'"""
        response = requests.get(f"{BASE_URL}/api/impact/charity")
        assert response.status_code == 200
        data = response.json()
        assert "payout_status" in data, "Missing payout_status"
        assert data["payout_status"] == "accumulating", f"Expected 'accumulating', got {data['payout_status']}"
        print("✓ payout_status is 'accumulating'")

    def test_charity_returns_payout_message_with_correct_wording(self):
        """Response should have payout_message with 'fléchés' wording (not reversé/donné)"""
        response = requests.get(f"{BASE_URL}/api/impact/charity")
        assert response.status_code == 200
        data = response.json()
        assert "payout_message" in data, "Missing payout_message"
        
        message = data["payout_message"]
        assert "fléchés" in message, f"payout_message should contain 'fléchés': {message}"
        assert "reversé" not in message.lower(), f"payout_message should NOT contain 'reversé': {message}"
        assert "donné" not in message.lower(), f"payout_message should NOT contain 'donné': {message}"
        assert "reversement automatique" in message.lower(), f"payout_message should mention 'reversement automatique': {message}"
        print(f"✓ payout_message has correct wording: '{message[:80]}...'")

    def test_charity_returns_contributions_object(self):
        """Response should include contributions object with items, total, skip, limit, has_more"""
        response = requests.get(f"{BASE_URL}/api/impact/charity")
        assert response.status_code == 200
        data = response.json()
        
        assert "contributions" in data, "Missing contributions"
        contributions = data["contributions"]
        
        assert "items" in contributions, "contributions missing 'items'"
        assert "total" in contributions, "contributions missing 'total'"
        assert "skip" in contributions, "contributions missing 'skip'"
        assert "limit" in contributions, "contributions missing 'limit'"
        assert "has_more" in contributions, "contributions missing 'has_more'"
        
        assert isinstance(contributions["items"], list), "contributions.items should be a list"
        assert isinstance(contributions["total"], int), "contributions.total should be int"
        assert isinstance(contributions["skip"], int), "contributions.skip should be int"
        assert isinstance(contributions["limit"], int), "contributions.limit should be int"
        assert isinstance(contributions["has_more"], bool), "contributions.has_more should be bool"
        
        print(f"✓ contributions object: {contributions['total']} total, {len(contributions['items'])} items, has_more={contributions['has_more']}")

    def test_charity_returns_refreshed_at(self):
        """Response should include refreshed_at timestamp"""
        response = requests.get(f"{BASE_URL}/api/impact/charity")
        assert response.status_code == 200
        data = response.json()
        assert "refreshed_at" in data, "Missing refreshed_at"
        print(f"✓ refreshed_at: {data['refreshed_at']}")


class TestCharityPagination:
    """Tests for pagination in GET /api/impact/charity"""

    def test_pagination_default_limit(self):
        """Default limit should be applied (20 or as specified)"""
        response = requests.get(f"{BASE_URL}/api/impact/charity")
        assert response.status_code == 200
        data = response.json()
        
        contributions = data["contributions"]
        # Default limit is 50 in backend, but frontend requests 10
        assert contributions["limit"] > 0, "limit should be positive"
        print(f"✓ Default limit: {contributions['limit']}")

    def test_pagination_with_custom_limit(self):
        """Custom limit parameter should work"""
        response = requests.get(f"{BASE_URL}/api/impact/charity?limit=5")
        assert response.status_code == 200
        data = response.json()
        
        contributions = data["contributions"]
        assert contributions["limit"] == 5, f"Expected limit=5, got {contributions['limit']}"
        assert len(contributions["items"]) <= 5, f"Items should be <= 5, got {len(contributions['items'])}"
        print(f"✓ Custom limit=5 works: {len(contributions['items'])} items returned")

    def test_pagination_with_skip(self):
        """Skip parameter should work"""
        response = requests.get(f"{BASE_URL}/api/impact/charity?skip=2&limit=5")
        assert response.status_code == 200
        data = response.json()
        
        contributions = data["contributions"]
        assert contributions["skip"] == 2, f"Expected skip=2, got {contributions['skip']}"
        print(f"✓ Skip=2 works: skip={contributions['skip']}, limit={contributions['limit']}")

    def test_pagination_has_more_calculation(self):
        """has_more should be true when skip+limit < total"""
        # First get total
        response = requests.get(f"{BASE_URL}/api/impact/charity?limit=1")
        assert response.status_code == 200
        data = response.json()
        
        total = data["contributions"]["total"]
        
        if total > 1:
            # Request with limit=1 should have has_more=true
            assert data["contributions"]["has_more"] == True, "has_more should be true when more items exist"
            print(f"✓ has_more=true when total={total} > limit=1")
        else:
            print(f"✓ Only {total} contributions, skipping has_more test")

    def test_pagination_no_overlap(self):
        """Consecutive pages should not have overlapping items"""
        # Get first page
        response1 = requests.get(f"{BASE_URL}/api/impact/charity?skip=0&limit=3")
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Get second page
        response2 = requests.get(f"{BASE_URL}/api/impact/charity?skip=3&limit=3")
        assert response2.status_code == 200
        data2 = response2.json()
        
        items1 = data1["contributions"]["items"]
        items2 = data2["contributions"]["items"]
        
        if len(items1) > 0 and len(items2) > 0:
            ids1 = {item.get("distribution_id") for item in items1}
            ids2 = {item.get("distribution_id") for item in items2}
            overlap = ids1 & ids2
            assert len(overlap) == 0, f"Pages should not overlap: {overlap}"
            print(f"✓ No overlap between page 1 ({len(items1)} items) and page 2 ({len(items2)} items)")
        else:
            print("✓ Not enough items to test pagination overlap")


class TestContributionItemStructure:
    """Tests for individual contribution item structure"""

    def test_contribution_item_has_required_fields(self):
        """Each contribution item should have required fields"""
        response = requests.get(f"{BASE_URL}/api/impact/charity?limit=10")
        assert response.status_code == 200
        data = response.json()
        
        items = data["contributions"]["items"]
        
        if len(items) == 0:
            pytest.skip("No contribution items to validate")
        
        required_fields = ["distribution_id", "amount_cents", "status", "created_at"]
        
        for item in items:
            for field in required_fields:
                assert field in item, f"Contribution item missing '{field}': {item}"
            
            # Validate types
            assert isinstance(item["amount_cents"], int), "amount_cents should be int"
            assert item["amount_cents"] > 0, "amount_cents should be positive"
        
        print(f"✓ All {len(items)} contribution items have required fields")

    def test_contribution_item_has_appointment_title(self):
        """Contribution items should be enriched with appointment_title"""
        response = requests.get(f"{BASE_URL}/api/impact/charity?limit=10")
        assert response.status_code == 200
        data = response.json()
        
        items = data["contributions"]["items"]
        
        if len(items) == 0:
            pytest.skip("No contribution items to validate")
        
        for item in items:
            assert "appointment_title" in item, f"Contribution item missing 'appointment_title': {item}"
        
        print(f"✓ All {len(items)} contribution items have appointment_title")

    def test_contribution_item_has_association_info(self):
        """Contribution items should have association_id and association_name"""
        response = requests.get(f"{BASE_URL}/api/impact/charity?limit=10")
        assert response.status_code == 200
        data = response.json()
        
        items = data["contributions"]["items"]
        
        if len(items) == 0:
            pytest.skip("No contribution items to validate")
        
        for item in items:
            assert "association_id" in item, f"Contribution item missing 'association_id': {item}"
            # association_name may be null if not found in DB
            assert "association_name" in item, f"Contribution item missing 'association_name': {item}"
        
        print(f"✓ All {len(items)} contribution items have association info")


class TestAssociationStructure:
    """Tests for association structure in response"""

    def test_association_has_required_fields(self):
        """Each association should have required fields"""
        response = requests.get(f"{BASE_URL}/api/impact/charity")
        assert response.status_code == 200
        data = response.json()
        
        associations = data["associations"]
        
        if len(associations) == 0:
            pytest.skip("No associations to validate")
        
        required_fields = ["association_id", "total_cents", "distributions_count", "events_count"]
        
        for assoc in associations:
            for field in required_fields:
                assert field in assoc, f"Association missing '{field}': {assoc}"
            
            # name may be null
            assert "name" in assoc, f"Association missing 'name': {assoc}"
        
        print(f"✓ All {len(associations)} associations have required fields")

    def test_associations_sorted_by_total_cents_desc(self):
        """Associations should be sorted by total_cents descending"""
        response = requests.get(f"{BASE_URL}/api/impact/charity")
        assert response.status_code == 200
        data = response.json()
        
        associations = data["associations"]
        
        if len(associations) < 2:
            pytest.skip("Need at least 2 associations to verify sorting")
        
        totals = [a["total_cents"] for a in associations]
        assert totals == sorted(totals, reverse=True), f"Associations not sorted by total_cents desc: {totals}"
        print(f"✓ Associations sorted by total_cents desc: {totals}")


class TestDataConsistency:
    """Tests for data consistency between endpoints"""

    def test_charity_total_matches_impact_total(self):
        """total_charity_cents should match between /api/impact and /api/impact/charity"""
        response_impact = requests.get(f"{BASE_URL}/api/impact")
        response_charity = requests.get(f"{BASE_URL}/api/impact/charity")
        
        assert response_impact.status_code == 200
        assert response_charity.status_code == 200
        
        impact_total = response_impact.json()["total_charity_cents"]
        charity_total = response_charity.json()["total_charity_cents"]
        
        assert impact_total == charity_total, \
            f"total_charity_cents mismatch: /api/impact={impact_total}, /api/impact/charity={charity_total}"
        print(f"✓ total_charity_cents consistent: {impact_total}")

    def test_associations_match_between_endpoints(self):
        """associations should match between /api/impact and /api/impact/charity"""
        response_impact = requests.get(f"{BASE_URL}/api/impact")
        response_charity = requests.get(f"{BASE_URL}/api/impact/charity")
        
        assert response_impact.status_code == 200
        assert response_charity.status_code == 200
        
        impact_assocs = response_impact.json()["associations"]
        charity_assocs = response_charity.json()["associations"]
        
        assert len(impact_assocs) == len(charity_assocs), \
            f"associations count mismatch: /api/impact={len(impact_assocs)}, /api/impact/charity={len(charity_assocs)}"
        print(f"✓ associations count consistent: {len(impact_assocs)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
