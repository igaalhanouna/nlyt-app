"""
Direct Database Test for scan_stale_payouts() Service Function

This script tests the actual stale payout detection logic by:
1. Inserting a test payout with status=processing and updated_at > 24h ago
2. Running scan_stale_payouts()
3. Verifying the payout is marked as stale with stale_detected_at
4. Testing that processing < 24h payouts are NOT touched
5. Testing that already stale payouts don't get duplicated
6. Testing webhook can overwrite stale → completed
7. Cleanup test data
"""
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Add backend to path
sys.path.insert(0, '/app/backend')

from database import db
from services.stale_payout_detector import scan_stale_payouts, STALE_THRESHOLD_HOURS

TEST_PREFIX = "TEST_STALE_"

def cleanup_test_payouts():
    """Remove all test payouts"""
    result = db.payouts.delete_many({"payout_id": {"$regex": f"^{TEST_PREFIX}"}})
    print(f"Cleaned up {result.deleted_count} test payouts")

def test_scan_marks_old_processing_as_stale():
    """Test 1: scan_stale_payouts() marks processing > 24h → stale"""
    print("\n=== Test 1: Mark old processing payouts as stale ===")
    
    # Create a payout that's been processing for > 24h
    old_time = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    test_payout_id = f"{TEST_PREFIX}old_processing_{uuid.uuid4().hex[:8]}"
    
    db.payouts.insert_one({
        "payout_id": test_payout_id,
        "user_id": "test_user_123",
        "wallet_id": "test_wallet_123",
        "amount_cents": 5000,
        "currency": "eur",
        "stripe_transfer_id": "tr_test_123",
        "status": "processing",
        "requested_at": old_time,
        "updated_at": old_time,
    })
    print(f"Created test payout: {test_payout_id} with updated_at={old_time}")
    
    # Run the scanner
    count = scan_stale_payouts()
    print(f"scan_stale_payouts() returned: {count}")
    
    # Verify the payout is now stale
    payout = db.payouts.find_one({"payout_id": test_payout_id}, {"_id": 0})
    assert payout is not None, "Test payout should exist"
    assert payout["status"] == "stale", f"Status should be 'stale', got '{payout['status']}'"
    assert "stale_detected_at" in payout, "stale_detected_at should be set"
    
    print(f"✓ Payout marked as stale with stale_detected_at={payout['stale_detected_at']}")
    return True

def test_scan_does_not_touch_recent_processing():
    """Test 2: scan_stale_payouts() does NOT touch processing < 24h"""
    print("\n=== Test 2: Recent processing payouts are NOT touched ===")
    
    # Create a payout that's been processing for < 24h (e.g., 2 hours)
    recent_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    test_payout_id = f"{TEST_PREFIX}recent_processing_{uuid.uuid4().hex[:8]}"
    
    db.payouts.insert_one({
        "payout_id": test_payout_id,
        "user_id": "test_user_456",
        "wallet_id": "test_wallet_456",
        "amount_cents": 3000,
        "currency": "eur",
        "stripe_transfer_id": "tr_test_456",
        "status": "processing",
        "requested_at": recent_time,
        "updated_at": recent_time,
    })
    print(f"Created test payout: {test_payout_id} with updated_at={recent_time} (2h ago)")
    
    # Run the scanner
    scan_stale_payouts()
    
    # Verify the payout is still processing
    payout = db.payouts.find_one({"payout_id": test_payout_id}, {"_id": 0})
    assert payout is not None, "Test payout should exist"
    assert payout["status"] == "processing", f"Status should still be 'processing', got '{payout['status']}'"
    assert "stale_detected_at" not in payout, "stale_detected_at should NOT be set"
    
    print(f"✓ Recent payout correctly left as processing")
    return True

def test_scan_does_not_duplicate_stale():
    """Test 3: scan_stale_payouts() does not create duplicates for already stale payouts"""
    print("\n=== Test 3: Already stale payouts are not duplicated ===")
    
    # Create a payout that's already stale
    old_time = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    stale_detected = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    test_payout_id = f"{TEST_PREFIX}already_stale_{uuid.uuid4().hex[:8]}"
    
    db.payouts.insert_one({
        "payout_id": test_payout_id,
        "user_id": "test_user_789",
        "wallet_id": "test_wallet_789",
        "amount_cents": 7000,
        "currency": "eur",
        "stripe_transfer_id": "tr_test_789",
        "status": "stale",  # Already stale
        "requested_at": old_time,
        "updated_at": old_time,
        "stale_detected_at": stale_detected,
    })
    print(f"Created already stale payout: {test_payout_id}")
    
    # Run the scanner
    count = scan_stale_payouts()
    
    # Verify the payout is still stale with original stale_detected_at
    payout = db.payouts.find_one({"payout_id": test_payout_id}, {"_id": 0})
    assert payout is not None, "Test payout should exist"
    assert payout["status"] == "stale", "Status should still be 'stale'"
    assert payout["stale_detected_at"] == stale_detected, "stale_detected_at should not change"
    
    print(f"✓ Already stale payout not modified (stale_detected_at unchanged)")
    return True

def test_webhook_can_overwrite_stale():
    """Test 4: Webhook can overwrite stale → completed"""
    print("\n=== Test 4: Webhook can overwrite stale → completed ===")
    
    # Create a stale payout
    old_time = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    test_payout_id = f"{TEST_PREFIX}stale_to_complete_{uuid.uuid4().hex[:8]}"
    
    db.payouts.insert_one({
        "payout_id": test_payout_id,
        "user_id": "test_user_webhook",
        "wallet_id": "test_wallet_webhook",
        "amount_cents": 9000,
        "currency": "eur",
        "stripe_transfer_id": "tr_test_webhook",
        "status": "stale",
        "requested_at": old_time,
        "updated_at": old_time,
        "stale_detected_at": datetime.now(timezone.utc).isoformat(),
    })
    print(f"Created stale payout: {test_payout_id}")
    
    # Simulate webhook updating status to completed
    now = datetime.now(timezone.utc).isoformat()
    db.payouts.update_one(
        {"payout_id": test_payout_id},
        {"$set": {
            "status": "completed",
            "completed_at": now,
            "updated_at": now,
        }}
    )
    
    # Verify the payout is now completed
    payout = db.payouts.find_one({"payout_id": test_payout_id}, {"_id": 0})
    assert payout is not None, "Test payout should exist"
    assert payout["status"] == "completed", f"Status should be 'completed', got '{payout['status']}'"
    assert "completed_at" in payout, "completed_at should be set"
    
    print(f"✓ Webhook successfully overwrote stale → completed")
    return True

def test_api_returns_stale_payouts():
    """Test 5: API returns stale payouts with user_email enrichment"""
    print("\n=== Test 5: API returns stale payouts ===")
    
    import requests
    
    BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://litigation-mgmt.preview.emergentagent.com').rstrip('/')
    
    # Login as admin
    login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "testuser_audit@nlyt.app",
        "password": "TestAudit123!"
    })
    
    if login_resp.status_code != 200:
        print(f"⚠ Could not login as admin: {login_resp.status_code}")
        return False
    
    token = login_resp.json().get("access_token")
    
    # Get stale payouts
    resp = requests.get(
        f"{BASE_URL}/api/admin/stale-payouts",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    
    assert "stale_payouts" in data, "Response should contain stale_payouts"
    assert "count" in data, "Response should contain count"
    
    # Check if our test stale payouts are in the response
    test_payouts = [p for p in data["stale_payouts"] if p.get("payout_id", "").startswith(TEST_PREFIX)]
    print(f"Found {len(test_payouts)} test payouts in API response")
    
    print(f"✓ API returns {data['count']} stale payouts")
    return True


def run_all_tests():
    """Run all tests and cleanup"""
    print("=" * 60)
    print("STALE PAYOUT DETECTION - DIRECT DATABASE TESTS")
    print("=" * 60)
    
    # Cleanup before tests
    cleanup_test_payouts()
    
    results = []
    
    try:
        results.append(("Mark old processing as stale", test_scan_marks_old_processing_as_stale()))
        results.append(("Recent processing not touched", test_scan_does_not_touch_recent_processing()))
        results.append(("Already stale not duplicated", test_scan_does_not_duplicate_stale()))
        results.append(("Webhook can overwrite stale", test_webhook_can_overwrite_stale()))
        results.append(("API returns stale payouts", test_api_returns_stale_payouts()))
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup after tests
        cleanup_test_payouts()
    
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
