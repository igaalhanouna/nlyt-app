import requests
import sys
import re
from datetime import datetime

class ICSCalendarTester:
    def __init__(self, base_url="https://nlyt-engage.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_result(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
        
        result = {
            "test": name,
            "success": success,
            "details": details
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")
        if details:
            print(f"    Details: {details}")

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None, check_content=False):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        request_headers = {'Content-Type': 'application/json'}
        if self.token:
            request_headers['Authorization'] = f'Bearer {self.token}'
        if headers:
            request_headers.update(headers)

        print(f"\n🔍 Testing {name}...")
        print(f"    URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=request_headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=request_headers)

            success = response.status_code == expected_status
            details = f"Status: {response.status_code}"
            
            if not success:
                details += f" (Expected {expected_status})"
                if response.status_code >= 400:
                    try:
                        error_body = response.json()
                        details += f" - Error: {error_body.get('detail', 'Unknown error')}"
                    except:
                        details += f" - Response: {response.text[:200]}"

            self.log_result(name, success, details)

            return success, response

        except Exception as e:
            self.log_result(name, False, f"Exception: {str(e)}")
            return False, None

    def test_login(self, email, password):
        """Test login and get token"""
        print(f"\n🔐 Logging in as {email}...")
        success, response = self.run_test(
            "Login",
            "POST",
            "api/auth/login",
            200,
            data={"email": email, "password": password}
        )
        
        if success and response:
            try:
                response_data = response.json()
                if 'access_token' in response_data:
                    self.token = response_data['access_token']
                    self.log_result("Login Token Retrieved", True, "Access token obtained")
                    return True
                else:
                    self.log_result("Login Token Retrieved", False, "No access_token in response")
            except:
                self.log_result("Login Token Retrieved", False, "Could not parse login response")
        return False

    def test_ics_export_endpoint(self, appointment_id):
        """Test ICS export endpoint"""
        print(f"\n📅 Testing ICS Export for appointment {appointment_id}...")
        
        # Test the ICS export endpoint
        success, response = self.run_test(
            "ICS Export Endpoint",
            "GET", 
            f"api/calendar/export/ics/{appointment_id}",
            200
        )
        
        if not success or not response:
            return False, None
            
        return True, response

    def validate_ics_content(self, ics_content, appointment_id):
        """Validate ICS file content"""
        print(f"\n🔍 Validating ICS content...")
        
        results = []
        
        # Check required ICS components
        required_components = [
            ('BEGIN:VCALENDAR', 'VCALENDAR start'),
            ('END:VCALENDAR', 'VCALENDAR end'),
            ('BEGIN:VEVENT', 'VEVENT start'),
            ('END:VEVENT', 'VEVENT end'),
            ('DTSTART:', 'Start datetime'),
            ('DTEND:', 'End datetime'),
            ('SUMMARY:', 'Event title'),
            ('DESCRIPTION:', 'Event description'),
        ]
        
        for component, description in required_components:
            found = component in ics_content
            results.append((description, found))
            self.log_result(f"ICS Contains {description}", found)
        
        # Check timezone format (UTC)
        dtstart_match = re.search(r'DTSTART:(\d{8}T\d{6}Z)', ics_content)
        dtend_match = re.search(r'DTEND:(\d{8}T\d{6}Z)', ics_content)
        
        utc_format_valid = bool(dtstart_match and dtend_match)
        self.log_result("UTC Timezone Format", utc_format_valid, 
                       f"DTSTART: {dtstart_match.group(1) if dtstart_match else 'Not found'}, DTEND: {dtend_match.group(1) if dtend_match else 'Not found'}")
        
        # Check for engagement rules in description
        description_match = re.search(r'DESCRIPTION:(.*?)(?:\r\n[A-Z]|\r\n\r\n|\nEND:|$)', ics_content, re.DOTALL)
        if description_match:
            description_content = description_match.group(1).replace('\\n', '\n').replace('\\;', ';')
            
            engagement_keywords = ['RÈGLES D\'ENGAGEMENT', 'Délai d\'annulation', 'Retard toléré', 'Pénalité']
            engagement_rules_found = any(keyword in description_content for keyword in engagement_keywords)
            self.log_result("Engagement Rules in Description", engagement_rules_found, 
                           f"Found keywords: {[kw for kw in engagement_keywords if kw in description_content]}")
            
            print(f"    Description content: {description_content[:200]}...")
        else:
            self.log_result("Engagement Rules in Description", False, "Description not found")
        
        # Check UID contains appointment ID
        uid_match = re.search(r'UID:([^\r\n]+)', ics_content)
        uid_valid = uid_match and appointment_id in uid_match.group(1)
        self.log_result("UID Contains Appointment ID", uid_valid, 
                       f"UID: {uid_match.group(1) if uid_match else 'Not found'}")
        
        return all(result[1] for result in results)

    def validate_ics_headers(self, response):
        """Validate HTTP headers for ICS download"""
        print(f"\n📋 Validating ICS HTTP headers...")
        
        # Check Content-Type
        content_type = response.headers.get('Content-Type', '')
        content_type_valid = 'text/calendar' in content_type.lower()
        self.log_result("Content-Type Header", content_type_valid, f"Content-Type: {content_type}")
        
        # Check Content-Disposition for download
        content_disposition = response.headers.get('Content-Disposition', '')
        disposition_valid = 'attachment' in content_disposition.lower()
        self.log_result("Content-Disposition Header", disposition_valid, f"Content-Disposition: {content_disposition}")
        
        # Check if filename is present
        filename_present = 'filename' in content_disposition.lower()
        self.log_result("Filename in Content-Disposition", filename_present, f"Filename present: {filename_present}")
        
        return content_type_valid and disposition_valid

def main():
    # Test credentials
    test_email = "testuser_audit@nlyt.app"
    test_password = "TestPassword123!"
    test_appointment_id = "2b76f8d8-e46f-4d5f-8665-8112bf0d1a7b"
    
    print("🚀 Starting ICS Calendar Export Tests")
    print("=" * 50)
    
    tester = ICSCalendarTester()
    
    # Test login
    if not tester.test_login(test_email, test_password):
        print("❌ Login failed, stopping tests")
        return 1
    
    # Test ICS export endpoint
    success, response = tester.test_ics_export_endpoint(test_appointment_id)
    if not success:
        print("❌ ICS export endpoint failed, stopping tests")
        return 1
    
    # Validate headers
    headers_valid = tester.validate_ics_headers(response)
    
    # Validate ICS content
    ics_content = response.text
    content_valid = tester.validate_ics_content(ics_content, test_appointment_id)
    
    # Print summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print(f"Tests run: {tester.tests_run}")
    print(f"Tests passed: {tester.tests_passed}")
    print(f"Success rate: {(tester.tests_passed/tester.tests_run)*100:.1f}%")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())