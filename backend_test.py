import requests
import sys
from datetime import datetime
import json

class CalendarAPITester:
    def __init__(self, base_url="https://nlyt-engage.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        
        # Test credentials from review request
        self.test_email = "testuser_audit@nlyt.app"
        self.test_password = "TestPassword123!"
        self.test_user_id = "d13498f9-9c0d-47d4-b48f-9e327e866127"
        self.active_appointment_id = "2b76f8d8-e46f-4d5f-8665-8112bf0d1a7b"
        self.cancelled_appointment_id = "3250f725-9daf-4911-bedc-b001f733c4d7"
        self.invitation_token = "277bfb9d-37c8-4d54-be12-a86a01d3abd6"

    def run_test(self, name, method, endpoint, expected_status, data=None, check_content=False, expected_content_type=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)

            success = response.status_code == expected_status
            
            result = {
                'test_name': name,
                'endpoint': endpoint,
                'method': method,
                'expected_status': expected_status,
                'actual_status': response.status_code,
                'success': success,
                'response_data': None,
                'content_type': response.headers.get('content-type', ''),
                'content_length': len(response.content) if response.content else 0
            }
            
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                
                if expected_content_type:
                    content_type = response.headers.get('content-type', '')
                    if expected_content_type.lower() in content_type.lower():
                        print(f"✅ Content-Type correct: {content_type}")
                        result['content_type_valid'] = True
                    else:
                        print(f"⚠️  Content-Type mismatch - Expected: {expected_content_type}, Got: {content_type}")
                        result['content_type_valid'] = False
                
                if check_content and response.content:
                    try:
                        content = response.content.decode('utf-8')
                        result['content_full'] = content  # Store full content for validation
                        result['content_sample'] = content[:200] + '...' if len(content) > 200 else content
                        print(f"📄 Content sample: {result['content_sample']}")
                    except Exception:
                        result['content_sample'] = f"Binary content ({len(response.content)} bytes)"
                        print(f"📄 Binary content: {len(response.content)} bytes")
                
                try:
                    if response.headers.get('content-type', '').lower().startswith('application/json'):
                        result['response_data'] = response.json()
                except:
                    pass
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    result['error_detail'] = error_data.get('detail', 'Unknown error')
                    print(f"   Error: {result['error_detail']}")
                except:
                    result['error_detail'] = response.text[:200] if response.text else "No error message"
                    print(f"   Error: {result['error_detail']}")

            self.test_results.append(result)
            return success, result

        except Exception as e:
            print(f"❌ Failed - Exception: {str(e)}")
            result = {
                'test_name': name,
                'endpoint': endpoint,
                'method': method,
                'expected_status': expected_status,
                'actual_status': 'EXCEPTION',
                'success': False,
                'error_detail': str(e)
            }
            self.test_results.append(result)
            return False, result

    def test_login(self):
        """Test login and get token"""
        print(f"\n🔐 Testing authentication...")
        success, result = self.run_test(
            "User Authentication", 
            "POST", 
            "auth/login", 
            200,
            data={"email": self.test_email, "password": self.test_password}
        )
        if success and result.get('response_data', {}).get('access_token'):
            self.token = result['response_data']['access_token']
            print(f"✅ Authentication successful, token obtained")
            return True
        print(f"❌ Authentication failed")
        return False

    def test_active_appointment_ics_export(self):
        """Test ICS export for active appointment"""
        success, result = self.run_test(
            "Export ICS for Active Appointment",
            "GET",
            f"calendar/export/ics/{self.active_appointment_id}",
            200,
            check_content=True,
            expected_content_type="text/calendar"
        )
        
        if success and result.get('content_full'):
            content = result.get('content_full', '')
            # Check for required ICS components
            required_fields = ['VCALENDAR', 'VEVENT', 'DTSTART', 'DTEND', 'SUMMARY', 'DESCRIPTION', 'UID', 'STATUS']
            missing_fields = []
            for field in required_fields:
                if field not in content:
                    missing_fields.append(field)
            
            if missing_fields:
                print(f"⚠️  Missing required ICS fields: {missing_fields}")
                result['missing_ics_fields'] = missing_fields
            else:
                print(f"✅ All required ICS fields present")
                result['ics_validation'] = 'PASSED'
            
            # Check for timezone format (YYYYMMDDTHHMMSSZ)
            import re
            utc_datetime_pattern = r'\d{8}T\d{6}Z'
            if re.search(utc_datetime_pattern, content):
                print(f"✅ UTC timezone format detected")
                result['timezone_format'] = 'UTC_CORRECT'
            else:
                print(f"⚠️  UTC timezone format not found")
                result['timezone_format'] = 'UTC_MISSING'
        
        return success

    def test_cancelled_appointment_ics_export(self):
        """Test ICS export for cancelled appointment"""
        success, result = self.run_test(
            "Export ICS for Cancelled Appointment",
            "GET", 
            f"calendar/export/ics/{self.cancelled_appointment_id}",
            200,
            check_content=True,
            expected_content_type="text/calendar"
        )
        
        if success and result.get('content_full'):
            content = result.get('content_full', '')
            # Check for STATUS:CANCELLED
            if 'STATUS:CANCELLED' in content:
                print(f"✅ STATUS:CANCELLED found in ICS")
                result['cancelled_status'] = 'PRESENT'
            else:
                print(f"❌ STATUS:CANCELLED not found in ICS")
                result['cancelled_status'] = 'MISSING'
            
            # Check for [ANNULÉ] prefix in title
            if '[ANNULÉ]' in content or 'ANNULÉ' in content:
                print(f"✅ [ANNULÉ] prefix found in title")
                result['cancelled_title_prefix'] = 'PRESENT'
            else:
                print(f"❌ [ANNULÉ] prefix not found in title")
                result['cancelled_title_prefix'] = 'MISSING'
            
            # Check that VALARM is not present for cancelled events
            if 'VALARM' not in content:
                print(f"✅ No VALARM for cancelled appointment (correct)")
                result['no_alarm_for_cancelled'] = 'CORRECT'
            else:
                print(f"❌ VALARM found in cancelled appointment (should not be present)")
                result['no_alarm_for_cancelled'] = 'INCORRECT'
        
        return success

    def test_user_ics_feed(self):
        """Test ICS subscription feed for user"""
        success, result = self.run_test(
            "User ICS Subscription Feed",
            "GET",
            f"calendar/feed/{self.test_user_id}.ics",
            200,
            check_content=True,
            expected_content_type="text/calendar"
        )
        
        if success and result.get('content_full'):
            content = result.get('content_full', '')
            # Check for multiple VEVENT entries (feed format)
            vevent_count = content.count('BEGIN:VEVENT')
            print(f"📊 Found {vevent_count} VEVENT entries in feed")
            result['vevent_count'] = vevent_count
            
            # Check for feed-specific headers
            if 'X-WR-CALNAME:' in content:
                print(f"✅ Feed calendar name header found")
                result['feed_headers'] = 'PRESENT'
            else:
                print(f"⚠️  Feed calendar name header missing")
                result['feed_headers'] = 'MISSING'
        
        return success

    def test_nonexistent_appointment_ics(self):
        """Test ICS export for non-existent appointment"""
        fake_appointment_id = "00000000-0000-0000-0000-000000000000"
        success, result = self.run_test(
            "Export ICS for Non-existent Appointment",
            "GET",
            f"calendar/export/ics/{fake_appointment_id}",
            404
        )
        return success

    def validate_ics_format(self, ics_content):
        """Validate ICS content format"""
        validation_results = {
            'has_vcalendar': 'BEGIN:VCALENDAR' in ics_content and 'END:VCALENDAR' in ics_content,
            'has_vevent': 'BEGIN:VEVENT' in ics_content and 'END:VEVENT' in ics_content,
            'has_required_fields': all(field in ics_content for field in ['DTSTART', 'DTEND', 'SUMMARY', 'UID']),
            'proper_line_endings': '\r\n' in ics_content,
            'utc_format': bool(__import__('re').search(r'\d{8}T\d{6}Z', ics_content))
        }
        return validation_results

def main():
    print("🚀 Starting Calendar API Tests...")
    print("=" * 50)
    
    tester = CalendarAPITester()
    
    # Step 1: Authenticate
    if not tester.test_login():
        print("\n❌ Authentication failed - cannot proceed with protected endpoint tests")
        print(f"\n📊 Final Results: {tester.tests_passed}/{tester.tests_run} tests passed")
        return 1
    
    print("\n📅 Testing Calendar Export Endpoints...")
    print("=" * 50)
    
    # Step 2: Test ICS exports
    tester.test_active_appointment_ics_export()
    tester.test_cancelled_appointment_ics_export()
    tester.test_user_ics_feed()
    tester.test_nonexistent_appointment_ics()
    
    # Print detailed summary
    print("\n" + "=" * 50)
    print(f"📊 FINAL TEST RESULTS")
    print("=" * 50)
    print(f"Tests Run: {tester.tests_run}")
    print(f"Tests Passed: {tester.tests_passed}")
    print(f"Success Rate: {(tester.tests_passed/tester.tests_run)*100:.1f}%")
    
    print(f"\n📋 DETAILED TEST BREAKDOWN:")
    for i, result in enumerate(tester.test_results, 1):
        status = "✅ PASS" if result['success'] else "❌ FAIL"
        print(f"{i:2d}. {status} - {result['test_name']}")
        if not result['success'] and 'error_detail' in result:
            print(f"    Error: {result['error_detail']}")
        if 'content_type_valid' in result and not result['content_type_valid']:
            print(f"    ⚠️  Content-Type issue")
        if 'missing_ics_fields' in result:
            print(f"    ⚠️  Missing ICS fields: {result['missing_ics_fields']}")
        if 'cancelled_status' in result and result['cancelled_status'] == 'MISSING':
            print(f"    ❌ Missing STATUS:CANCELLED for cancelled appointment")
        if 'cancelled_title_prefix' in result and result['cancelled_title_prefix'] == 'MISSING':
            print(f"    ❌ Missing [ANNULÉ] prefix for cancelled appointment")
    
    # Return exit code
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())