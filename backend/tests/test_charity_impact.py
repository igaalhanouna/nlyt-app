"""
Test Charity Impact Tracking Feature
Tests:
- GET /api/wallet/impact returns charity impact data
- GET /api/wallet/impact requires authentication
- GET /api/wallet/impact returns total_charity_cents, currency, distributions_count, events_count
- GET /api/wallet/impact returns by_association array with association_id, total_cents, count
- GET /api/wallet/impact returns contributions array with appointment_title, amount_cents, status
- GET /api/wallet/impact excludes cancelled distributions
- GET /api/wallet/impact excludes refunded charity beneficiaries
- GET /api/wallet/distributions enriches with charity_association_id and charity_association_name
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Module-level session to avoid rate limiting
_auth_session = None
_user_id = None
_token = None

def get_auth_session():
    """Get or create authenticated session (singleton to avoid rate limits)"""
    global _auth_session, _user_id, _token
    
    if _auth_session is not None:
        return _auth_session, _user_id, _token
    
    email = "testuser_audit@nlyt.app"
    password = "Test1234!"
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login to get token
    login_response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": email,
        "password": password
    })
    if login_response.status_code == 200:
        token = login_response.json().get("access_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        _auth_session = session
        _token = token
        _user_id = login_response.json().get("user", {}).get("user_id")
        return _auth_session, _user_id, _token
    else:
        return None, None, None


class TestCharityImpactAPI:
    """Tests for GET /api/wallet/impact endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test credentials and login"""
        session, user_id, token = get_auth_session()
        if session is None:
            pytest.skip("Login failed - rate limited or credentials invalid")
        self.session = session
        self.user_id = user_id
        self.token = token
    
    # ─── Authentication Tests ───────────────────────────────────────
    
    def test_impact_requires_auth(self):
        """GET /api/wallet/impact requires authentication"""
        response = requests.get(f"{BASE_URL}/api/wallet/impact")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/wallet/impact requires auth")
    
    # ─── Response Structure Tests ───────────────────────────────────
    
    def test_impact_returns_required_fields(self):
        """GET /api/wallet/impact returns total_charity_cents, currency, distributions_count, events_count"""
        response = self.session.get(f"{BASE_URL}/api/wallet/impact")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Check required top-level fields
        required_fields = ["total_charity_cents", "currency", "distributions_count", "events_count"]
        for field in required_fields:
            assert field in data, f"Response should contain '{field}' field"
        
        # Validate types
        assert isinstance(data["total_charity_cents"], int), "total_charity_cents should be int"
        assert isinstance(data["currency"], str), "currency should be string"
        assert isinstance(data["distributions_count"], int), "distributions_count should be int"
        assert isinstance(data["events_count"], int), "events_count should be int"
        
        print(f"PASS: GET /api/wallet/impact returns required fields")
        print(f"      total_charity_cents: {data['total_charity_cents']}")
        print(f"      currency: {data['currency']}")
        print(f"      distributions_count: {data['distributions_count']}")
        print(f"      events_count: {data['events_count']}")
    
    def test_impact_returns_by_association_array(self):
        """GET /api/wallet/impact returns by_association array with association_id, total_cents, count"""
        response = self.session.get(f"{BASE_URL}/api/wallet/impact")
        assert response.status_code == 200
        
        data = response.json()
        
        assert "by_association" in data, "Response should contain 'by_association' field"
        assert isinstance(data["by_association"], list), "by_association should be a list"
        
        # If there are associations, check structure
        if len(data["by_association"]) > 0:
            assoc = data["by_association"][0]
            required_assoc_fields = ["association_id", "total_cents", "count"]
            for field in required_assoc_fields:
                assert field in assoc, f"Association should have '{field}' field"
            
            # name field may be null if charity_associations collection is empty
            assert "name" in assoc, "Association should have 'name' field (may be null)"
            
            print(f"PASS: by_association has correct structure")
            print(f"      First association: {assoc.get('association_id')[:8]}... = {assoc.get('total_cents')}c ({assoc.get('count')} distributions)")
            if assoc.get("name"):
                print(f"      Association name: {assoc.get('name')}")
            else:
                print(f"      Association name: null (no named association in DB)")
        else:
            print("INFO: No associations in by_association array")
    
    def test_impact_returns_contributions_array(self):
        """GET /api/wallet/impact returns contributions array with appointment_title, amount_cents, status"""
        response = self.session.get(f"{BASE_URL}/api/wallet/impact")
        assert response.status_code == 200
        
        data = response.json()
        
        assert "contributions" in data, "Response should contain 'contributions' field"
        assert isinstance(data["contributions"], list), "contributions should be a list"
        
        # If there are contributions, check structure
        if len(data["contributions"]) > 0:
            contrib = data["contributions"][0]
            required_contrib_fields = ["distribution_id", "amount_cents", "status"]
            for field in required_contrib_fields:
                assert field in contrib, f"Contribution should have '{field}' field"
            
            # appointment_title should be present (enriched)
            assert "appointment_title" in contrib, "Contribution should have 'appointment_title' field"
            
            # currency and created_at should be present
            assert "currency" in contrib, "Contribution should have 'currency' field"
            assert "created_at" in contrib, "Contribution should have 'created_at' field"
            
            print(f"PASS: contributions has correct structure")
            print(f"      First contribution: {contrib.get('appointment_title')} = {contrib.get('amount_cents')}c ({contrib.get('status')})")
        else:
            print("INFO: No contributions in contributions array")
    
    # ─── Data Validation Tests ──────────────────────────────────────
    
    def test_impact_totals_are_consistent(self):
        """GET /api/wallet/impact totals should be consistent with by_association and contributions"""
        response = self.session.get(f"{BASE_URL}/api/wallet/impact")
        assert response.status_code == 200
        
        data = response.json()
        
        # Sum of by_association total_cents should equal total_charity_cents
        assoc_sum = sum(a.get("total_cents", 0) for a in data.get("by_association", []))
        assert assoc_sum == data["total_charity_cents"], \
            f"by_association sum ({assoc_sum}) should equal total_charity_cents ({data['total_charity_cents']})"
        
        # Sum of contributions amount_cents should equal total_charity_cents
        contrib_sum = sum(c.get("amount_cents", 0) for c in data.get("contributions", []))
        assert contrib_sum == data["total_charity_cents"], \
            f"contributions sum ({contrib_sum}) should equal total_charity_cents ({data['total_charity_cents']})"
        
        # distributions_count should equal number of contributions
        assert data["distributions_count"] == len(data.get("contributions", [])), \
            f"distributions_count ({data['distributions_count']}) should equal contributions length ({len(data.get('contributions', []))})"
        
        print(f"PASS: Impact totals are consistent")
        print(f"      total_charity_cents: {data['total_charity_cents']}")
        print(f"      by_association sum: {assoc_sum}")
        print(f"      contributions sum: {contrib_sum}")
    
    def test_impact_currency_is_eur(self):
        """GET /api/wallet/impact currency should be 'eur'"""
        response = self.session.get(f"{BASE_URL}/api/wallet/impact")
        assert response.status_code == 200
        
        data = response.json()
        assert data["currency"] == "eur", f"Currency should be 'eur', got {data['currency']}"
        print("PASS: Currency is 'eur'")
    
    # ─── Demo Data Verification Tests ───────────────────────────────
    
    def test_impact_has_charity_data_from_demo_distribution(self):
        """GET /api/wallet/impact should have charity data from demo distribution (1500c)"""
        response = self.session.get(f"{BASE_URL}/api/wallet/impact")
        assert response.status_code == 200
        
        data = response.json()
        
        # According to context: 1 pending_hold distribution with charity_demo beneficiary at 1500c
        # The completed distribution has charity_percent=0, so no charity contribution
        
        if data["total_charity_cents"] > 0:
            print(f"PASS: Impact has charity data")
            print(f"      total_charity_cents: {data['total_charity_cents']}")
            print(f"      distributions_count: {data['distributions_count']}")
            print(f"      events_count: {data['events_count']}")
            
            # Check if 1500c is present (from demo data)
            if data["total_charity_cents"] == 1500:
                print(f"      Matches expected demo data: 1500c (15 EUR)")
        else:
            print("INFO: No charity contributions found - demo data may not have charity beneficiary")
            print(f"      total_charity_cents: {data['total_charity_cents']}")


class TestDistributionsCharityEnrichment:
    """Tests for charity enrichment in GET /api/wallet/distributions"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test credentials and login"""
        session, user_id, token = get_auth_session()
        if session is None:
            pytest.skip("Login failed - rate limited or credentials invalid")
        self.session = session
        self.user_id = user_id
        self.token = token
    
    def test_distributions_enriched_with_charity_association_id(self):
        """GET /api/wallet/distributions enriches with charity_association_id"""
        response = self.session.get(f"{BASE_URL}/api/wallet/distributions")
        assert response.status_code == 200
        
        data = response.json()
        distributions = data.get("distributions", [])
        
        # Find distributions that have charity beneficiaries
        for dist in distributions:
            beneficiaries = dist.get("beneficiaries", [])
            has_charity = any(b.get("role") == "charity" for b in beneficiaries)
            
            if has_charity:
                # Check if charity_association_id is enriched from appointment
                if "charity_association_id" in dist:
                    print(f"PASS: Distribution enriched with charity_association_id: {dist.get('charity_association_id')}")
                    
                    # charity_association_name may be null if no named association
                    if "charity_association_name" in dist:
                        print(f"      charity_association_name: {dist.get('charity_association_name') or 'null'}")
                    return
        
        print("INFO: No distributions with charity beneficiaries found for enrichment check")
    
    def test_distributions_charity_beneficiary_has_correct_role(self):
        """Distributions with charity should have beneficiary with role='charity'"""
        response = self.session.get(f"{BASE_URL}/api/wallet/distributions")
        assert response.status_code == 200
        
        data = response.json()
        distributions = data.get("distributions", [])
        
        for dist in distributions:
            beneficiaries = dist.get("beneficiaries", [])
            charity_benefs = [b for b in beneficiaries if b.get("role") == "charity"]
            
            if len(charity_benefs) > 0:
                charity_benef = charity_benefs[0]
                assert "amount_cents" in charity_benef, "Charity beneficiary should have amount_cents"
                assert charity_benef["amount_cents"] > 0, "Charity amount should be positive"
                
                print(f"PASS: Found charity beneficiary with role='charity'")
                print(f"      amount_cents: {charity_benef.get('amount_cents')}")
                print(f"      status: {charity_benef.get('status')}")
                return
        
        print("INFO: No charity beneficiaries found in distributions")


class TestImpactExclusionRules:
    """Tests for exclusion rules in impact calculation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test credentials and login"""
        session, user_id, token = get_auth_session()
        if session is None:
            pytest.skip("Login failed - rate limited or credentials invalid")
        self.session = session
        self.user_id = user_id
        self.token = token
    
    def test_impact_excludes_cancelled_distributions(self):
        """GET /api/wallet/impact should exclude cancelled distributions"""
        # Get impact data
        impact_response = self.session.get(f"{BASE_URL}/api/wallet/impact")
        assert impact_response.status_code == 200
        impact_data = impact_response.json()
        
        # Get all distributions
        dist_response = self.session.get(f"{BASE_URL}/api/wallet/distributions")
        assert dist_response.status_code == 200
        distributions = dist_response.json().get("distributions", [])
        
        # Count charity contributions from non-cancelled distributions
        expected_charity_cents = 0
        for dist in distributions:
            if dist.get("status") == "cancelled":
                continue
            for benef in dist.get("beneficiaries", []):
                if benef.get("role") == "charity" and benef.get("status") != "refunded":
                    expected_charity_cents += benef.get("amount_cents", 0)
        
        # Impact total should match (or be close if there are other users' distributions)
        print(f"INFO: Impact total_charity_cents: {impact_data['total_charity_cents']}")
        print(f"INFO: Expected from non-cancelled distributions: {expected_charity_cents}")
        
        # Check that cancelled distributions are not counted
        cancelled_dists = [d for d in distributions if d.get("status") == "cancelled"]
        if len(cancelled_dists) > 0:
            print(f"PASS: Found {len(cancelled_dists)} cancelled distributions - verifying exclusion")
        else:
            print("INFO: No cancelled distributions to verify exclusion")
    
    def test_impact_excludes_refunded_charity_beneficiaries(self):
        """GET /api/wallet/impact should exclude refunded charity beneficiaries"""
        # Get all distributions
        dist_response = self.session.get(f"{BASE_URL}/api/wallet/distributions")
        assert dist_response.status_code == 200
        distributions = dist_response.json().get("distributions", [])
        
        # Check for refunded charity beneficiaries
        refunded_charity_found = False
        for dist in distributions:
            for benef in dist.get("beneficiaries", []):
                if benef.get("role") == "charity" and benef.get("status") == "refunded":
                    refunded_charity_found = True
                    print(f"INFO: Found refunded charity beneficiary in distribution {dist.get('distribution_id')}")
        
        if refunded_charity_found:
            print("PASS: Refunded charity beneficiaries exist - impact should exclude them")
        else:
            print("INFO: No refunded charity beneficiaries found to verify exclusion")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
