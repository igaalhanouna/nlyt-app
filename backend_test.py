import requests
import sys
import json
from datetime import datetime, timedelta

class AddressAutocompleteTester:
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

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        request_headers = {'Content-Type': 'application/json'}
        if self.token:
            request_headers['Authorization'] = f'Bearer {self.token}'
        if headers:
            request_headers.update(headers)

        print(f"\n🔍 Testing {name}...")
        print(f"    URL: {url}")
        if self.token:
            print(f"    Using token: {self.token[:20]}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=request_headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=request_headers)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=request_headers)

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
        try:
            response = requests.post(
                f"{self.base_url}/api/auth/login",
                json={"email": email, "password": password},
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                response_data = response.json()
                if 'access_token' in response_data:
                    self.token = response_data['access_token']
                    self.log_result("Login", True, f"Status: 200, Token obtained")
                    self.log_result("Login Token Retrieved", True, "Access token obtained")
                    return True
                else:
                    self.log_result("Login", False, "No access_token in response")
            else:
                self.log_result("Login", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Login", False, f"Exception: {str(e)}")
        return False

    def test_ban_api_directly(self):
        """Test the BAN (Base Adresse Nationale) API directly"""
        print(f"\n🗺️  Testing BAN API directly...")
        
        test_queries = [
            "Paris",
            "10 rue de la paix",
            "Lyon", 
            "Marseille"
        ]
        
        for query in test_queries:
            try:
                url = f"https://api-adresse.data.gouv.fr/search/?q={query}&limit=5&autocomplete=1"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    features = data.get('features', [])
                    if features:
                        sample_feature = features[0]
                        properties = sample_feature.get('properties', {})
                        geometry = sample_feature.get('geometry', {})
                        coordinates = geometry.get('coordinates', [])
                        
                        self.log_result(f"BAN API Search - '{query}'", True, 
                                       f"Found {len(features)} results. Sample: {properties.get('label', 'N/A')}")
                        
                        # Test data structure
                        required_fields = ['label', 'city', 'postcode', 'id']
                        has_required = all(field in properties for field in required_fields)
                        has_coordinates = len(coordinates) == 2
                        
                        self.log_result(f"BAN API Data Structure - '{query}'", has_required and has_coordinates,
                                       f"Required fields: {has_required}, Coordinates: {has_coordinates}")
                    else:
                        self.log_result(f"BAN API Search - '{query}'", False, "No results returned")
                else:
                    self.log_result(f"BAN API Search - '{query}'", False, f"HTTP {response.status_code}")
            except Exception as e:
                self.log_result(f"BAN API Search - '{query}'", False, f"Exception: {str(e)}")

    def get_or_create_workspace(self):
        """Get or create a workspace for testing"""
        print(f"\n🏢 Getting/creating workspace for testing...")
        
        # First try to get existing workspaces
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.token}'
            }
            response = requests.get(f"{self.base_url}/api/workspaces/", headers=headers)
            
            if response.status_code == 200:
                workspaces = response.json().get('workspaces', [])
                if workspaces:
                    workspace_id = workspaces[0]['workspace_id']
                    self.log_result("Use Existing Workspace", True, f"Using workspace: {workspace_id}")
                    return workspace_id
            else:
                self.log_result("List Workspaces", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("List Workspaces", False, f"Exception: {str(e)}")
        
        # Create new workspace if none exists
        workspace_data = {
            "name": f"Test Workspace Address {datetime.now().strftime('%H%M%S')}",
            "description": "Workspace for testing address autocomplete"
        }
        
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.token}'
            }
            response = requests.post(f"{self.base_url}/api/workspaces/", json=workspace_data, headers=headers)
            
            if response.status_code == 201:
                workspace_id = response.json().get('workspace_id')
                if workspace_id:
                    self.log_result("Created New Workspace", True, f"Workspace ID: {workspace_id}")
                    return workspace_id
            else:
                self.log_result("Create Workspace", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Create Workspace", False, f"Exception: {str(e)}")
        
        self.log_result("Get/Create Workspace", False, "Failed to get or create workspace")
        return None

    def test_appointment_creation_with_location(self, workspace_id):
        """Test creating appointment with location data from address autocomplete"""
        print(f"\n📅 Testing appointment creation with location data...")
        
        # Sample data as if selected from address autocomplete
        start_time = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S')
        
        appointment_data = {
            "workspace_id": workspace_id,
            "title": "Rendez-vous test avec adresse autocomplete",
            "appointment_type": "physical",
            "location": "10 Rue de la Paix, 75002 Paris",
            "location_latitude": 48.8698,  # Sample coordinates for 10 Rue de la Paix, Paris
            "location_longitude": 2.3316,
            "location_place_id": "75102_8863_00010",
            "start_datetime": start_time,
            "duration_minutes": 60,
            "tolerated_delay_minutes": 15,
            "cancellation_deadline_hours": 24,
            "penalty_amount": 50,
            "penalty_currency": "eur",
            "affected_compensation_percent": 80.0,
            "platform_commission_percent": 20.0,
            "charity_percent": 0.0,
            "participants": [
                {
                    "first_name": "Test",
                    "last_name": "Participant", 
                    "email": "test.participant@example.com",
                    "role": "participant"
                }
            ]
        }
        
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.token}'
            }
            response = requests.post(f"{self.base_url}/api/appointments/", json=appointment_data, headers=headers)
            
            if response.status_code == 200:
                appointment_id = response.json().get('appointment_id')
                if appointment_id:
                    self.log_result("Create Appointment with Location", True, f"Appointment ID: {appointment_id}")
                    return appointment_id
            else:
                try:
                    error = response.json().get('detail', 'Unknown error')
                    self.log_result("Create Appointment with Location", False, f"Status: {response.status_code} - {error}")
                except:
                    self.log_result("Create Appointment with Location", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Create Appointment with Location", False, f"Exception: {str(e)}")
        
        return None

    def test_appointment_with_video_type(self, workspace_id):
        """Test creating video appointment (should not require location fields)"""
        print(f"\n📹 Testing video appointment creation...")
        
        start_time = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M:%S')
        
        video_appointment_data = {
            "workspace_id": workspace_id,
            "title": "Rendez-vous visio test",
            "appointment_type": "video",
            "meeting_provider": "Zoom",
            "start_datetime": start_time,
            "duration_minutes": 30,
            "tolerated_delay_minutes": 5,
            "cancellation_deadline_hours": 12,
            "penalty_amount": 25,
            "penalty_currency": "eur",
            "affected_compensation_percent": 70.0,
            "platform_commission_percent": 30.0,
            "charity_percent": 0.0,
            "participants": [
                {
                    "first_name": "Video",
                    "last_name": "Tester",
                    "email": "video.tester@example.com", 
                    "role": "participant"
                }
            ]
        }
        
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.token}'
            }
            response = requests.post(f"{self.base_url}/api/appointments/", json=video_appointment_data, headers=headers)
            
            if response.status_code == 200:
                appointment_id = response.json().get('appointment_id')
                if appointment_id:
                    self.log_result("Create Video Appointment", True, f"Appointment ID: {appointment_id}")
                    return appointment_id
            else:
                try:
                    error = response.json().get('detail', 'Unknown error')
                    self.log_result("Create Video Appointment", False, f"Status: {response.status_code} - {error}")
                except:
                    self.log_result("Create Video Appointment", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Create Video Appointment", False, f"Exception: {str(e)}")
        
        return None

    def verify_appointment_location_data(self, appointment_id):
        """Verify that location data is properly stored in the appointment"""
        print(f"\n🔍 Verifying appointment location data...")
        
        try:
            headers = {
                'Content-Type': 'application/json', 
                'Authorization': f'Bearer {self.token}'
            }
            response = requests.get(f"{self.base_url}/api/appointments/{appointment_id}", headers=headers)
            
            if response.status_code == 200:
                appointment = response.json()
                
                # Check required location fields
                location_fields = {
                    'location': appointment.get('location'),
                    'location_latitude': appointment.get('location_latitude'),
                    'location_longitude': appointment.get('location_longitude'), 
                    'location_place_id': appointment.get('location_place_id')
                }
                
                all_fields_present = all(value is not None for value in location_fields.values())
                
                self.log_result("Location Fields Stored", all_fields_present, 
                               f"Fields: {location_fields}")
                
                # Validate coordinate ranges (rough check for France)
                lat = location_fields['location_latitude']
                lng = location_fields['location_longitude']
                
                if lat and lng:
                    # France coordinates roughly: 42-51 lat, -5 to 8 lng
                    coords_valid = (42 <= lat <= 51) and (-5 <= lng <= 8)
                    self.log_result("Coordinates Valid Range", coords_valid, 
                                   f"Lat: {lat}, Lng: {lng}")
                
                return all_fields_present
            else:
                self.log_result("Get Appointment Details", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Get Appointment Details", False, f"Exception: {str(e)}")
        
        return False

def main():
    # Test credentials
    test_email = "testuser_audit@nlyt.app"
    test_password = "TestPassword123!"
    
    print("🚀 Starting Address Autocomplete Backend Tests")
    print("=" * 60)
    
    tester = AddressAutocompleteTester()
    
    # Test 1: Login
    if not tester.test_login(test_email, test_password):
        print("❌ Login failed, stopping tests")
        return 1
    
    # Test 2: BAN API direct testing
    tester.test_ban_api_directly()
    
    # Test 3: Get/Create workspace
    workspace_id = tester.get_or_create_workspace()
    if not workspace_id:
        print("❌ Workspace setup failed, stopping tests")
        return 1
    
    # Test 4: Create appointment with location data
    appointment_id = tester.test_appointment_creation_with_location(workspace_id)
    if appointment_id:
        # Test 5: Verify location data storage
        tester.verify_appointment_location_data(appointment_id)
    
    # Test 6: Create video appointment (control test)
    video_appointment_id = tester.test_appointment_with_video_type(workspace_id)
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print(f"Tests run: {tester.tests_run}")
    print(f"Tests passed: {tester.tests_passed}")
    print(f"Success rate: {(tester.tests_passed/tester.tests_run)*100:.1f}%")
    
    # Detailed results
    print("\nDetailed Results:")
    for result in tester.test_results:
        status = "✅" if result["success"] else "❌"
        print(f"  {status} {result['test']}")
        if result["details"]:
            print(f"     {result['details']}")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All backend tests passed!")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())