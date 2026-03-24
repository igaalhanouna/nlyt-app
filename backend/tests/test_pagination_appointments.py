"""
Test suite for appointments pagination feature (Voir plus / Load more)
Tests: skip/limit/time_filter params on GET /api/appointments/
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')

# Test credentials
TEST_EMAIL = "testuser_audit@nlyt.app"
TEST_PASSWORD = "Test1234!"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test user"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert "access_token" in data, "No access_token in login response"
    return data["access_token"]


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Create authenticated session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestPaginationBasics:
    """Basic pagination parameter tests"""

    def test_upcoming_filter_returns_paginated_response(self, api_client):
        """GET /api/appointments/?time_filter=upcoming returns paginated structure"""
        response = api_client.get(
            f"{BASE_URL}/api/appointments/",
            params={"time_filter": "upcoming", "skip": 0, "limit": 5}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify paginated response structure
        assert "items" in data, "Response missing 'items' field"
        assert "total" in data, "Response missing 'total' field"
        assert "has_more" in data, "Response missing 'has_more' field"
        assert "skip" in data, "Response missing 'skip' field"
        assert "limit" in data, "Response missing 'limit' field"
        
        # Verify types
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["has_more"], bool)
        assert isinstance(data["skip"], int)
        assert isinstance(data["limit"], int)
        
        print(f"✓ Upcoming: {len(data['items'])} items, total={data['total']}, has_more={data['has_more']}")

    def test_past_filter_returns_paginated_response(self, api_client):
        """GET /api/appointments/?time_filter=past returns paginated structure"""
        response = api_client.get(
            f"{BASE_URL}/api/appointments/",
            params={"time_filter": "past", "skip": 0, "limit": 5}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify paginated response structure
        assert "items" in data
        assert "total" in data
        assert "has_more" in data
        
        print(f"✓ Past: {len(data['items'])} items, total={data['total']}, has_more={data['has_more']}")

    def test_skip_limit_parameters_work(self, api_client):
        """GET /api/appointments/?skip=5&limit=5 returns correct pagination"""
        response = api_client.get(
            f"{BASE_URL}/api/appointments/",
            params={"skip": 5, "limit": 5}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["skip"] == 5
        assert data["limit"] == 5
        assert len(data["items"]) <= 5
        
        print(f"✓ Skip/limit: skip={data['skip']}, limit={data['limit']}, returned={len(data['items'])}")


class TestPaginationLogic:
    """Test pagination logic and has_more calculation"""

    def test_has_more_true_when_more_items_exist(self, api_client):
        """has_more=true when skip+limit < total"""
        # First get total count
        response = api_client.get(
            f"{BASE_URL}/api/appointments/",
            params={"time_filter": "upcoming", "skip": 0, "limit": 100}
        )
        assert response.status_code == 200
        total = response.json()["total"]
        
        if total > 2:
            # Request with small limit
            response = api_client.get(
                f"{BASE_URL}/api/appointments/",
                params={"time_filter": "upcoming", "skip": 0, "limit": 2}
            )
            assert response.status_code == 200
            data = response.json()
            
            # has_more should be true since total > 2
            assert data["has_more"] == True, f"Expected has_more=True when total={total} > limit=2"
            print(f"✓ has_more=True when total={total} > limit=2")
        else:
            pytest.skip(f"Not enough upcoming appointments (total={total}) to test has_more=True")

    def test_has_more_false_when_all_loaded(self, api_client):
        """has_more=false when skip+limit >= total"""
        # Get total count
        response = api_client.get(
            f"{BASE_URL}/api/appointments/",
            params={"time_filter": "upcoming", "skip": 0, "limit": 100}
        )
        assert response.status_code == 200
        total = response.json()["total"]
        
        # Request all items
        response = api_client.get(
            f"{BASE_URL}/api/appointments/",
            params={"time_filter": "upcoming", "skip": 0, "limit": total + 10}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["has_more"] == False, f"Expected has_more=False when limit={total+10} >= total={total}"
        print(f"✓ has_more=False when all items loaded (total={total})")

    def test_pagination_no_overlap(self, api_client):
        """Pagination: skip=0&limit=2 then skip=2&limit=2 returns different items"""
        # First page
        response1 = api_client.get(
            f"{BASE_URL}/api/appointments/",
            params={"time_filter": "upcoming", "skip": 0, "limit": 2}
        )
        assert response1.status_code == 200
        page1 = response1.json()
        
        if page1["total"] < 4:
            pytest.skip(f"Not enough appointments (total={page1['total']}) to test pagination overlap")
        
        # Second page
        response2 = api_client.get(
            f"{BASE_URL}/api/appointments/",
            params={"time_filter": "upcoming", "skip": 2, "limit": 2}
        )
        assert response2.status_code == 200
        page2 = response2.json()
        
        # Extract appointment IDs
        ids_page1 = {item["appointment_id"] for item in page1["items"]}
        ids_page2 = {item["appointment_id"] for item in page2["items"]}
        
        # No overlap
        overlap = ids_page1 & ids_page2
        assert len(overlap) == 0, f"Pages should not overlap, but found: {overlap}"
        
        print(f"✓ No overlap: page1 has {len(ids_page1)} items, page2 has {len(ids_page2)} items, overlap=0")


class TestTimeFilterSorting:
    """Test time_filter sorting behavior"""

    def test_upcoming_sorted_ascending(self, api_client):
        """Upcoming appointments sorted by start_datetime ascending (nearest first)"""
        response = api_client.get(
            f"{BASE_URL}/api/appointments/",
            params={"time_filter": "upcoming", "skip": 0, "limit": 10}
        )
        assert response.status_code == 200
        items = response.json()["items"]
        
        if len(items) >= 2:
            dates = [item["start_datetime"] for item in items]
            for i in range(len(dates) - 1):
                assert dates[i] <= dates[i+1], f"Upcoming not sorted ascending: {dates[i]} > {dates[i+1]}"
            print(f"✓ Upcoming sorted ascending (nearest first): {len(items)} items verified")
        else:
            print(f"✓ Only {len(items)} upcoming items, sorting verified trivially")

    def test_past_sorted_descending(self, api_client):
        """Past appointments sorted by start_datetime descending (most recent first)"""
        response = api_client.get(
            f"{BASE_URL}/api/appointments/",
            params={"time_filter": "past", "skip": 0, "limit": 10}
        )
        assert response.status_code == 200
        items = response.json()["items"]
        
        if len(items) >= 2:
            dates = [item["start_datetime"] for item in items]
            for i in range(len(dates) - 1):
                assert dates[i] >= dates[i+1], f"Past not sorted descending: {dates[i]} < {dates[i+1]}"
            print(f"✓ Past sorted descending (most recent first): {len(items)} items verified")
        else:
            print(f"✓ Only {len(items)} past items, sorting verified trivially")


class TestTotalCounts:
    """Test total counts for test user (expected: 49 upcoming, 71 past)"""

    def test_upcoming_total_count(self, api_client):
        """Verify upcoming appointments total count"""
        response = api_client.get(
            f"{BASE_URL}/api/appointments/",
            params={"time_filter": "upcoming", "skip": 0, "limit": 1}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Test user should have ~49 upcoming appointments
        print(f"✓ Upcoming total: {data['total']} appointments")
        assert data["total"] > 0, "Expected at least some upcoming appointments"

    def test_past_total_count(self, api_client):
        """Verify past appointments total count"""
        response = api_client.get(
            f"{BASE_URL}/api/appointments/",
            params={"time_filter": "past", "skip": 0, "limit": 1}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Test user should have ~71 past appointments
        print(f"✓ Past total: {data['total']} appointments")
        assert data["total"] > 0, "Expected at least some past appointments"


class TestLoadMoreScenario:
    """Simulate the 'Voir plus' (load more) user flow"""

    def test_load_more_upcoming_flow(self, api_client):
        """Simulate clicking 'Voir plus' for upcoming appointments"""
        PAGE_SIZE = 20
        
        # Initial load
        response = api_client.get(
            f"{BASE_URL}/api/appointments/",
            params={"time_filter": "upcoming", "skip": 0, "limit": PAGE_SIZE}
        )
        assert response.status_code == 200
        data = response.json()
        
        loaded_items = data["items"]
        total = data["total"]
        has_more = data["has_more"]
        
        print(f"Initial load: {len(loaded_items)}/{total} items, has_more={has_more}")
        
        # Simulate clicking "Voir plus" until all loaded
        page = 1
        while has_more and page < 10:  # Safety limit
            response = api_client.get(
                f"{BASE_URL}/api/appointments/",
                params={"time_filter": "upcoming", "skip": len(loaded_items), "limit": PAGE_SIZE}
            )
            assert response.status_code == 200
            data = response.json()
            
            new_items = data["items"]
            loaded_items.extend(new_items)
            has_more = data["has_more"]
            page += 1
            
            print(f"Page {page}: loaded {len(new_items)} more, total loaded={len(loaded_items)}/{total}, has_more={has_more}")
        
        # Verify we loaded all items
        assert len(loaded_items) == total, f"Expected to load all {total} items, got {len(loaded_items)}"
        assert has_more == False, "has_more should be False after loading all items"
        
        # Verify no duplicates
        ids = [item["appointment_id"] for item in loaded_items]
        assert len(ids) == len(set(ids)), "Found duplicate appointment IDs"
        
        print(f"✓ Load more flow complete: loaded all {total} items in {page} pages, no duplicates")

    def test_load_more_past_flow(self, api_client):
        """Simulate clicking 'Voir plus' for past appointments"""
        PAGE_SIZE = 20
        
        # Initial load
        response = api_client.get(
            f"{BASE_URL}/api/appointments/",
            params={"time_filter": "past", "skip": 0, "limit": PAGE_SIZE}
        )
        assert response.status_code == 200
        data = response.json()
        
        loaded_items = data["items"]
        total = data["total"]
        has_more = data["has_more"]
        
        print(f"Initial load (past): {len(loaded_items)}/{total} items, has_more={has_more}")
        
        # Load one more page if available
        if has_more:
            response = api_client.get(
                f"{BASE_URL}/api/appointments/",
                params={"time_filter": "past", "skip": len(loaded_items), "limit": PAGE_SIZE}
            )
            assert response.status_code == 200
            data = response.json()
            
            new_items = data["items"]
            
            # Verify no overlap with first page
            ids_page1 = {item["appointment_id"] for item in loaded_items}
            ids_page2 = {item["appointment_id"] for item in new_items}
            overlap = ids_page1 & ids_page2
            assert len(overlap) == 0, f"Pages should not overlap: {overlap}"
            
            print(f"✓ Second page loaded: {len(new_items)} items, no overlap with first page")
        else:
            print(f"✓ All past items fit in first page ({total} items)")


class TestEdgeCases:
    """Edge case tests"""

    def test_empty_result_when_skip_exceeds_total(self, api_client):
        """Skip beyond total returns empty items but correct total"""
        response = api_client.get(
            f"{BASE_URL}/api/appointments/",
            params={"time_filter": "upcoming", "skip": 1000, "limit": 20}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) == 0, "Expected empty items when skip exceeds total"
        assert data["has_more"] == False, "has_more should be False when skip exceeds total"
        assert data["total"] >= 0, "Total should still be returned"
        
        print(f"✓ Skip=1000: empty items, total={data['total']}, has_more=False")

    def test_default_limit_when_not_specified(self, api_client):
        """Default limit is applied when not specified"""
        response = api_client.get(
            f"{BASE_URL}/api/appointments/",
            params={"time_filter": "upcoming"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Default limit should be 20
        assert data["limit"] == 20, f"Expected default limit=20, got {data['limit']}"
        print(f"✓ Default limit=20 applied")

    def test_no_time_filter_returns_all(self, api_client):
        """Without time_filter, returns all appointments (upcoming + past)"""
        # Get upcoming count
        resp_up = api_client.get(
            f"{BASE_URL}/api/appointments/",
            params={"time_filter": "upcoming", "skip": 0, "limit": 1}
        )
        upcoming_total = resp_up.json()["total"]
        
        # Get past count
        resp_past = api_client.get(
            f"{BASE_URL}/api/appointments/",
            params={"time_filter": "past", "skip": 0, "limit": 1}
        )
        past_total = resp_past.json()["total"]
        
        # Get all (no filter)
        resp_all = api_client.get(
            f"{BASE_URL}/api/appointments/",
            params={"skip": 0, "limit": 1}
        )
        all_total = resp_all.json()["total"]
        
        # All should equal upcoming + past
        assert all_total == upcoming_total + past_total, \
            f"Expected all={upcoming_total}+{past_total}={upcoming_total+past_total}, got {all_total}"
        
        print(f"✓ No filter: total={all_total} = upcoming({upcoming_total}) + past({past_total})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
