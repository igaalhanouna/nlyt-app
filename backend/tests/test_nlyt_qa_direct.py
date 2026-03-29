"""
NLYT QA Direct Tests — Iteration 152
Direct API testing without pytest fixtures to avoid rate limiting issues
"""
import requests
import time
import concurrent.futures

BASE_URL = 'https://litigation-mgmt.preview.emergentagent.com'

# Credentials
ADMIN_EMAIL = "testuser_audit@nlyt.app"
ADMIN_PASSWORD = "TestAudit123!"
USER1_EMAIL = "igaal@hotmail.com"
USER1_PASSWORD = "Test123!"
USER2_EMAIL = "igaal.hanouna@gmail.com"
USER2_PASSWORD = "OrgTest123!"

def login(email, password):
    """Login and return token"""
    resp = requests.post(f'{BASE_URL}/api/auth/login', json={'email': email, 'password': password})
    if resp.status_code == 200:
        return resp.json().get('access_token')
    print(f"Login failed for {email}: {resp.status_code} - {resp.text[:100]}")
    return None

def get_headers(token):
    return {'Authorization': f'Bearer {token}'}

def run_tests():
    results = {
        'passed': [],
        'failed': [],
        'skipped': []
    }
    
    print("=" * 60)
    print("NLYT QA RECETTE — ITERATION 152")
    print("=" * 60)
    
    # Login all users once
    print("\n[SETUP] Logging in users...")
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    time.sleep(1)  # Avoid rate limit
    user1_token = login(USER1_EMAIL, USER1_PASSWORD)
    time.sleep(1)
    user2_token = login(USER2_EMAIL, USER2_PASSWORD)
    
    if not admin_token:
        print("CRITICAL: Admin login failed!")
        return results
    
    print(f"  Admin: {'OK' if admin_token else 'FAILED'}")
    print(f"  User1: {'OK' if user1_token else 'FAILED'}")
    print(f"  User2: {'OK' if user2_token else 'FAILED'}")
    
    # ═══════════════════════════════════════════════════════════════
    # BLOC A — AUTH
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("BLOC A — AUTH/ONBOARDING")
    print("=" * 60)
    
    # A1: Admin login success (already done)
    print("\n[A1] Admin login → dashboard accessible")
    if admin_token:
        results['passed'].append('A1')
        print("  ✓ PASS: Admin login successful")
    else:
        results['failed'].append('A1')
        print("  ✗ FAIL: Admin login failed")
    
    # A2: Wrong password
    print("\n[A2] Wrong password → error message")
    resp = requests.post(f'{BASE_URL}/api/auth/login', json={'email': ADMIN_EMAIL, 'password': 'WrongPass!'})
    if resp.status_code == 401:
        results['passed'].append('A2')
        print("  ✓ PASS: Wrong password returns 401")
    else:
        results['failed'].append('A2')
        print(f"  ✗ FAIL: Expected 401, got {resp.status_code}")
    
    # A9: Double registration
    print("\n[A9] Double registration same email → rejected")
    resp = requests.post(f'{BASE_URL}/api/auth/register', json={
        'email': ADMIN_EMAIL, 'password': 'NewPass123!', 'first_name': 'Test', 'last_name': 'Dup'
    })
    if resp.status_code == 400:
        results['passed'].append('A9')
        print("  ✓ PASS: Double registration rejected")
    else:
        results['failed'].append('A9')
        print(f"  ✗ FAIL: Expected 400, got {resp.status_code}")
    
    # A6: No auth access
    print("\n[A6] No auth → 401")
    resp = requests.get(f'{BASE_URL}/api/appointments')
    if resp.status_code == 401:
        results['passed'].append('A6')
        print("  ✓ PASS: No auth returns 401")
    else:
        results['failed'].append('A6')
        print(f"  ✗ FAIL: Expected 401, got {resp.status_code}")
    
    # ═══════════════════════════════════════════════════════════════
    # BLOC B — PERMISSIONS (PRIORITY 1)
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("BLOC B — PERMISSIONS/ROLES [SECURITY]")
    print("=" * 60)
    
    # B3: Non-admin access to admin URL
    print("\n[B3] Non-admin access /admin → 403")
    if user1_token:
        resp = requests.get(f'{BASE_URL}/api/admin/arbitration', headers=get_headers(user1_token))
        if resp.status_code == 403:
            results['passed'].append('B3')
            print("  ✓ PASS: Non-admin gets 403 on admin endpoint")
        else:
            results['failed'].append('B3')
            print(f"  ✗ FAIL: Expected 403, got {resp.status_code}")
    else:
        results['skipped'].append('B3')
        print("  ⚠ SKIP: User1 login failed")
    
    # B4: Multiple admin endpoints with non-admin token
    print("\n[B4] Non-admin token on admin APIs → 403")
    if user1_token:
        endpoints = ['/api/admin/users', '/api/admin/arbitration', '/api/admin/analytics/overview']
        all_403 = True
        for ep in endpoints:
            resp = requests.get(f'{BASE_URL}{ep}', headers=get_headers(user1_token))
            if resp.status_code != 403:
                all_403 = False
                print(f"  ✗ {ep} returned {resp.status_code} instead of 403")
        if all_403:
            results['passed'].append('B4')
            print("  ✓ PASS: All admin endpoints return 403 for non-admin")
        else:
            results['failed'].append('B4')
    else:
        results['skipped'].append('B4')
        print("  ⚠ SKIP: User1 login failed")
    
    # B4 complement: Admin can access
    print("\n[B4+] Admin token on admin APIs → 200")
    resp = requests.get(f'{BASE_URL}/api/admin/users', headers=get_headers(admin_token))
    if resp.status_code == 200:
        results['passed'].append('B4+')
        print("  ✓ PASS: Admin can access admin endpoints")
    else:
        results['failed'].append('B4+')
        print(f"  ✗ FAIL: Admin got {resp.status_code}")
    
    # B6: Refresh endpoints
    print("\n[B6] Dashboard/Wallet/Admin endpoints respond")
    endpoints = ['/api/appointments', '/api/wallet', '/api/admin/payouts/dashboard']
    all_ok = True
    for ep in endpoints:
        resp = requests.get(f'{BASE_URL}{ep}', headers=get_headers(admin_token))
        if resp.status_code != 200:
            all_ok = False
            print(f"  ✗ {ep} returned {resp.status_code}")
    if all_ok:
        results['passed'].append('B6')
        print("  ✓ PASS: All dashboard endpoints respond correctly")
    else:
        results['failed'].append('B6')
    
    # ═══════════════════════════════════════════════════════════════
    # BLOC F — LITIGES (PRIORITY 3)
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("BLOC F — LITIGES [CRITICAL]")
    print("=" * 60)
    
    # F1: Dispute visibility for both parties
    print("\n[F1] Dispute visibility for both parties")
    admin_disputes = requests.get(f'{BASE_URL}/api/disputes/mine', headers=get_headers(admin_token))
    if admin_disputes.status_code == 200:
        admin_data = admin_disputes.json()
        print(f"  Admin sees {admin_data.get('count', 0)} disputes")
        
        # Check target_user_id is set
        disputes = admin_data.get('disputes', [])
        missing_target = [d for d in disputes if not d.get('target_user_id')]
        if missing_target:
            results['failed'].append('F1')
            print(f"  ✗ FAIL: {len(missing_target)} disputes missing target_user_id")
        else:
            results['passed'].append('F1')
            print("  ✓ PASS: All disputes have target_user_id set")
            for d in disputes[:3]:
                print(f"    - {d.get('dispute_id')[:8]}... status={d.get('status')} target={d.get('target_user_id')[:8]}...")
    else:
        results['failed'].append('F1')
        print(f"  ✗ FAIL: Disputes API returned {admin_disputes.status_code}")
    
    # F7: Submit position on resolved dispute
    print("\n[F7] Submit position on resolved dispute → error")
    disputes_data = admin_disputes.json() if admin_disputes.status_code == 200 else {'disputes': []}
    resolved = [d for d in disputes_data.get('disputes', []) if d.get('status') in ('resolved', 'agreed_present', 'agreed_absent')]
    if resolved:
        dispute_id = resolved[0]['dispute_id']
        resp = requests.post(
            f'{BASE_URL}/api/disputes/{dispute_id}/position',
            headers=get_headers(admin_token),
            json={'position': 'confirmed_present'}
        )
        if resp.status_code == 400:
            results['passed'].append('F7')
            print(f"  ✓ PASS: Cannot submit position on resolved dispute")
        else:
            results['failed'].append('F7')
            print(f"  ✗ FAIL: Expected 400, got {resp.status_code}")
    else:
        results['skipped'].append('F7')
        print("  ⚠ SKIP: No resolved disputes found")
    
    # ═══════════════════════════════════════════════════════════════
    # BLOC G — ARBITRAGE ADMIN (PRIORITY 5)
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("BLOC G — ARBITRAGE ADMIN [FINANCIAL SAFETY]")
    print("=" * 60)
    
    # G1: Arbitration filters
    print("\n[G1] Arbitration list with filters")
    filters = ['escalated', 'all', 'resolved']
    all_ok = True
    for f in filters:
        resp = requests.get(f'{BASE_URL}/api/admin/arbitration?filter={f}', headers=get_headers(admin_token))
        if resp.status_code != 200:
            all_ok = False
            print(f"  ✗ Filter '{f}' returned {resp.status_code}")
        else:
            print(f"  Filter '{f}': {resp.json().get('count', 0)} disputes")
    if all_ok:
        results['passed'].append('G1')
        print("  ✓ PASS: All filters work")
    else:
        results['failed'].append('G1')
    
    # G4: Double resolution prevention
    print("\n[G4] Double resolution prevention")
    resolved_resp = requests.get(f'{BASE_URL}/api/admin/arbitration?filter=resolved', headers=get_headers(admin_token))
    if resolved_resp.status_code == 200:
        resolved_disputes = resolved_resp.json().get('disputes', [])
        if resolved_disputes:
            dispute_id = resolved_disputes[0]['dispute_id']
            resp = requests.post(
                f'{BASE_URL}/api/admin/arbitration/{dispute_id}/resolve',
                headers=get_headers(admin_token),
                json={'final_outcome': 'on_time', 'resolution_note': 'Test double resolution'}
            )
            if resp.status_code == 400:
                results['passed'].append('G4')
                print(f"  ✓ PASS: Double resolution rejected")
            else:
                results['failed'].append('G4')
                print(f"  ✗ FAIL: Expected 400, got {resp.status_code}")
        else:
            results['skipped'].append('G4')
            print("  ⚠ SKIP: No resolved disputes in admin view")
    else:
        results['failed'].append('G4')
        print(f"  ✗ FAIL: Could not get resolved disputes")
    
    # ═══════════════════════════════════════════════════════════════
    # BLOC H — WALLET (PRIORITY 4)
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("BLOC H — WALLET [FINANCIAL SAFETY]")
    print("=" * 60)
    
    # H1: Wallet balance coherence
    print("\n[H1] Wallet balance coherence")
    wallet_resp = requests.get(f'{BASE_URL}/api/wallet', headers=get_headers(admin_token))
    if wallet_resp.status_code == 200:
        wallet = wallet_resp.json()
        available = wallet.get('available_balance', 0)
        pending = wallet.get('pending_balance', 0)
        total = wallet.get('total_balance', 0)
        
        if total == available + pending:
            results['passed'].append('H1')
            print(f"  ✓ PASS: Balance coherent - available={available/100:.2f} EUR")
        else:
            results['failed'].append('H1')
            print(f"  ✗ FAIL: Balance mismatch - total={total}, available+pending={available+pending}")
    else:
        results['failed'].append('H1')
        print(f"  ✗ FAIL: Wallet API returned {wallet_resp.status_code}")
    
    # H4: Payout exceeds balance
    print("\n[H4] Payout exceeds balance → rejected")
    initial_balance = wallet.get('available_balance', 0) if wallet_resp.status_code == 200 else 0
    resp = requests.post(
        f'{BASE_URL}/api/wallet/payout',
        headers=get_headers(admin_token),
        json={'amount_cents': 99999900}
    )
    if resp.status_code == 400:
        # Verify balance unchanged
        wallet_after = requests.get(f'{BASE_URL}/api/wallet', headers=get_headers(admin_token))
        final_balance = wallet_after.json().get('available_balance', 0) if wallet_after.status_code == 200 else -1
        if final_balance == initial_balance:
            results['passed'].append('H4')
            print("  ✓ PASS: Excessive payout rejected, balance unchanged")
        else:
            results['failed'].append('H4')
            print(f"  ✗ FAIL: Balance changed from {initial_balance} to {final_balance}")
    else:
        results['failed'].append('H4')
        print(f"  ✗ FAIL: Expected 400, got {resp.status_code}")
    
    # H5: Zero amount payout
    print("\n[H5] Zero amount payout → rejected")
    resp = requests.post(
        f'{BASE_URL}/api/wallet/payout',
        headers=get_headers(admin_token),
        json={'amount_cents': 0}
    )
    if resp.status_code == 400:
        results['passed'].append('H5')
        print("  ✓ PASS: Zero payout rejected")
    else:
        results['failed'].append('H5')
        print(f"  ✗ FAIL: Expected 400, got {resp.status_code}")
    
    # H6: Double payout concurrent (CRITICAL)
    print("\n[H6] CRITICAL: Double payout concurrent")
    wallet_resp = requests.get(f'{BASE_URL}/api/wallet', headers=get_headers(admin_token))
    if wallet_resp.status_code == 200:
        wallet = wallet_resp.json()
        initial_balance = wallet.get('available_balance', 0)
        
        if initial_balance < 1000:
            results['skipped'].append('H6')
            print(f"  ⚠ SKIP: Balance too low ({initial_balance/100:.2f} EUR)")
        else:
            payout_amount = max(500, initial_balance // 2)
            
            def make_payout():
                return requests.post(
                    f'{BASE_URL}/api/wallet/payout',
                    headers=get_headers(admin_token),
                    json={'amount_cents': payout_amount}
                )
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(make_payout) for _ in range(2)]
                responses = [f.result() for f in concurrent.futures.as_completed(futures)]
            
            successes = sum(1 for r in responses if r.status_code == 200)
            failures = sum(1 for r in responses if r.status_code == 400)
            
            print(f"  Concurrent payouts: {successes} succeeded, {failures} failed")
            
            # Check final balance
            wallet_after = requests.get(f'{BASE_URL}/api/wallet', headers=get_headers(admin_token))
            final_balance = wallet_after.json().get('available_balance', 0) if wallet_after.status_code == 200 else -1
            
            if successes == 1:
                expected = initial_balance - payout_amount
                if final_balance == expected:
                    results['passed'].append('H6')
                    print(f"  ✓ PASS: Only 1 payout succeeded, balance correct")
                else:
                    results['failed'].append('H6')
                    print(f"  ✗ FAIL: Balance mismatch - expected {expected}, got {final_balance}")
            elif successes == 0:
                if final_balance == initial_balance:
                    results['passed'].append('H6')
                    print(f"  ✓ PASS: Both rejected (pending payout exists)")
                else:
                    results['failed'].append('H6')
                    print(f"  ✗ FAIL: Balance changed despite both failing")
            else:
                results['failed'].append('H6')
                print(f"  ✗ CRITICAL FAIL: {successes} payouts succeeded - DOUBLE DEBIT BUG!")
    else:
        results['failed'].append('H6')
        print(f"  ✗ FAIL: Could not get wallet")
    
    # H7: Connect refresh status
    print("\n[H7] Connect refresh status")
    resp = requests.post(f'{BASE_URL}/api/connect/refresh-status', headers=get_headers(admin_token))
    if resp.status_code in (200, 400):
        results['passed'].append('H7')
        print(f"  ✓ PASS: Connect refresh responds ({resp.status_code})")
    else:
        results['failed'].append('H7')
        print(f"  ✗ FAIL: Unexpected status {resp.status_code}")
    
    # H8: Transaction history
    print("\n[H8] Transaction history")
    resp = requests.get(f'{BASE_URL}/api/wallet/transactions', headers=get_headers(admin_token))
    if resp.status_code == 200:
        data = resp.json()
        txs = data.get('transactions', [])
        # Check chronological order
        ordered = True
        for i in range(len(txs) - 1):
            if txs[i].get('created_at', '') < txs[i+1].get('created_at', ''):
                ordered = False
                break
        if ordered:
            results['passed'].append('H8')
            print(f"  ✓ PASS: {data.get('total', 0)} transactions in chronological order")
        else:
            results['failed'].append('H8')
            print(f"  ✗ FAIL: Transactions not in chronological order")
    else:
        results['failed'].append('H8')
        print(f"  ✗ FAIL: Transactions API returned {resp.status_code}")
    
    # ═══════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"PASSED:  {len(results['passed'])} - {', '.join(results['passed'])}")
    print(f"FAILED:  {len(results['failed'])} - {', '.join(results['failed'])}")
    print(f"SKIPPED: {len(results['skipped'])} - {', '.join(results['skipped'])}")
    
    total = len(results['passed']) + len(results['failed'])
    if total > 0:
        success_rate = len(results['passed']) / total * 100
        print(f"\nSuccess rate: {success_rate:.1f}%")
    
    return results

if __name__ == '__main__':
    run_tests()
