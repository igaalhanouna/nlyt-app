"""
Test: Cancelled Participants Attendance Sheets Bug Fix (Iteration 170)

Bug: When all participants of an appointment have cancelled, the system still
proposes an attendance sheet to the organizer.

Fix implemented:
1. Prevention in initialize_declarative_phase: Non-self targets in terminal status
   (cancelled_by_participant, declined, guarantee_released) are excluded. If no
   relevant non-self targets remain, no sheet is created. Self-declaration alone
   doesn't suffice. If 0 sheets created → declarative_phase = 'not_needed'.

2. Retroactive filtering in GET /api/attendance-sheets/pending: Sheets where all
   non-self targets are in terminal status are excluded from the response.

Tests:
- TERMINAL_PARTICIPANT_STATUSES contains exactly the expected statuses
- initialize_declarative_phase with all terminal participants → no sheets, phase = not_needed
- initialize_declarative_phase with at least one active participant → sheets created normally
- Self-declaration alone (no relevant non-self targets) → no sheet
- GET /pending excludes sheets with all terminal non-self targets
- GET /pending includes sheets with at least one active non-self target
"""

import pytest
import requests
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')

# Ensure backend is in path
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestTerminalParticipantStatuses:
    """Test that TERMINAL_PARTICIPANT_STATUSES constant is correctly defined"""
    
    def test_terminal_statuses_constant_exists(self):
        """Verify TERMINAL_PARTICIPANT_STATUSES contains exactly the expected statuses"""
        from services.declarative_service import TERMINAL_PARTICIPANT_STATUSES
        
        expected = frozenset({'cancelled_by_participant', 'declined', 'guarantee_released'})
        assert TERMINAL_PARTICIPANT_STATUSES == expected, \
            f"Expected {expected}, got {TERMINAL_PARTICIPANT_STATUSES}"
        print("PASS: TERMINAL_PARTICIPANT_STATUSES contains exactly: cancelled_by_participant, declined, guarantee_released")


class TestInitializeDeclarativePhaseWithTerminalParticipants:
    """Test initialize_declarative_phase behavior with terminal participants"""
    
    @pytest.fixture(autouse=True)
    def setup_db(self):
        """Setup and cleanup test data"""
        from database import db
        self.db = db
        self.test_prefix = f"TEST_ITER170_{uuid.uuid4().hex[:8]}"
        yield
        # Cleanup
        self.db.appointments.delete_many({"appointment_id": {"$regex": f"^{self.test_prefix}"}})
        self.db.participants.delete_many({"appointment_id": {"$regex": f"^{self.test_prefix}"}})
        self.db.attendance_records.delete_many({"appointment_id": {"$regex": f"^{self.test_prefix}"}})
        self.db.attendance_sheets.delete_many({"appointment_id": {"$regex": f"^{self.test_prefix}"}})
        self.db.users.delete_many({"user_id": {"$regex": f"^{self.test_prefix}"}})
    
    def test_all_participants_terminal_no_sheets_created(self):
        """
        When all participants in manual_review have terminal status (cancelled_by_participant),
        NO sheet should be created and declarative_phase = 'not_needed'
        """
        from services.declarative_service import initialize_declarative_phase
        
        apt_id = f"{self.test_prefix}_apt_all_terminal"
        org_user_id = f"{self.test_prefix}_org_user"
        participant1_id = f"{self.test_prefix}_p1"
        participant2_id = f"{self.test_prefix}_p2"
        
        # Create organizer user
        self.db.users.insert_one({
            "user_id": org_user_id,
            "email": f"{self.test_prefix}_org@test.com",
            "first_name": "Test",
            "last_name": "Organizer"
        })
        
        # Create appointment
        self.db.appointments.insert_one({
            "appointment_id": apt_id,
            "organizer_id": org_user_id,
            "title": "Test Appointment All Terminal",
            "start_datetime": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            "status": "completed",
            "declarative_phase": None
        })
        
        # Create organizer as participant (active)
        self.db.participants.insert_one({
            "participant_id": f"{self.test_prefix}_org_p",
            "appointment_id": apt_id,
            "user_id": org_user_id,
            "email": f"{self.test_prefix}_org@test.com",
            "status": "accepted_guaranteed"
        })
        
        # Create participant 1 with TERMINAL status (cancelled_by_participant)
        self.db.participants.insert_one({
            "participant_id": participant1_id,
            "appointment_id": apt_id,
            "user_id": f"{self.test_prefix}_user1",
            "email": f"{self.test_prefix}_user1@test.com",
            "status": "cancelled_by_participant"  # TERMINAL
        })
        
        # Create participant 2 with TERMINAL status (declined)
        self.db.participants.insert_one({
            "participant_id": participant2_id,
            "appointment_id": apt_id,
            "user_id": f"{self.test_prefix}_user2",
            "email": f"{self.test_prefix}_user2@test.com",
            "status": "declined"  # TERMINAL
        })
        
        # Create attendance records in manual_review for both participants
        self.db.attendance_records.insert_one({
            "record_id": f"{self.test_prefix}_rec1",
            "appointment_id": apt_id,
            "participant_id": participant1_id,
            "review_required": True,
            "outcome": "manual_review"
        })
        self.db.attendance_records.insert_one({
            "record_id": f"{self.test_prefix}_rec2",
            "appointment_id": apt_id,
            "participant_id": participant2_id,
            "review_required": True,
            "outcome": "manual_review"
        })
        
        # Call initialize_declarative_phase
        initialize_declarative_phase(apt_id)
        
        # Verify: NO sheets should be created
        sheets_count = self.db.attendance_sheets.count_documents({"appointment_id": apt_id})
        assert sheets_count == 0, f"Expected 0 sheets, got {sheets_count}"
        
        # Verify: declarative_phase should be 'not_needed'
        apt = self.db.appointments.find_one({"appointment_id": apt_id})
        assert apt['declarative_phase'] == 'not_needed', \
            f"Expected declarative_phase='not_needed', got '{apt['declarative_phase']}'"
        
        print("PASS: All participants terminal → 0 sheets created, phase = not_needed")
    
    def test_at_least_one_active_participant_sheets_created(self):
        """
        When at least one participant in manual_review has active status (accepted_guaranteed),
        sheets SHOULD be created normally
        """
        from services.declarative_service import initialize_declarative_phase
        
        apt_id = f"{self.test_prefix}_apt_one_active"
        org_user_id = f"{self.test_prefix}_org_user2"
        participant1_id = f"{self.test_prefix}_p1_active"
        participant2_id = f"{self.test_prefix}_p2_terminal"
        
        # Create organizer user
        self.db.users.insert_one({
            "user_id": org_user_id,
            "email": f"{self.test_prefix}_org2@test.com",
            "first_name": "Test",
            "last_name": "Organizer2"
        })
        
        # Create appointment
        self.db.appointments.insert_one({
            "appointment_id": apt_id,
            "organizer_id": org_user_id,
            "title": "Test Appointment One Active",
            "start_datetime": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            "status": "completed",
            "declarative_phase": None
        })
        
        # Create organizer as participant (active)
        self.db.participants.insert_one({
            "participant_id": f"{self.test_prefix}_org_p2",
            "appointment_id": apt_id,
            "user_id": org_user_id,
            "email": f"{self.test_prefix}_org2@test.com",
            "status": "accepted_guaranteed"
        })
        
        # Create participant 1 with ACTIVE status (accepted_guaranteed)
        self.db.participants.insert_one({
            "participant_id": participant1_id,
            "appointment_id": apt_id,
            "user_id": f"{self.test_prefix}_user1_active",
            "email": f"{self.test_prefix}_user1_active@test.com",
            "status": "accepted_guaranteed"  # ACTIVE
        })
        
        # Create participant 2 with TERMINAL status (cancelled_by_participant)
        self.db.participants.insert_one({
            "participant_id": participant2_id,
            "appointment_id": apt_id,
            "user_id": f"{self.test_prefix}_user2_terminal",
            "email": f"{self.test_prefix}_user2_terminal@test.com",
            "status": "cancelled_by_participant"  # TERMINAL
        })
        
        # Create attendance records in manual_review for both participants
        self.db.attendance_records.insert_one({
            "record_id": f"{self.test_prefix}_rec1_active",
            "appointment_id": apt_id,
            "participant_id": participant1_id,
            "review_required": True,
            "outcome": "manual_review"
        })
        self.db.attendance_records.insert_one({
            "record_id": f"{self.test_prefix}_rec2_terminal",
            "appointment_id": apt_id,
            "participant_id": participant2_id,
            "review_required": True,
            "outcome": "manual_review"
        })
        
        # Call initialize_declarative_phase
        initialize_declarative_phase(apt_id)
        
        # Verify: Sheets SHOULD be created (at least 1)
        sheets_count = self.db.attendance_sheets.count_documents({"appointment_id": apt_id})
        assert sheets_count >= 1, f"Expected at least 1 sheet, got {sheets_count}"
        
        # Verify: declarative_phase should be 'collecting'
        apt = self.db.appointments.find_one({"appointment_id": apt_id})
        assert apt['declarative_phase'] == 'collecting', \
            f"Expected declarative_phase='collecting', got '{apt['declarative_phase']}'"
        
        # Verify: Sheets should NOT contain terminal participant as target
        sheets = list(self.db.attendance_sheets.find({"appointment_id": apt_id}))
        for sheet in sheets:
            for decl in sheet.get('declarations', []):
                if not decl.get('is_self_declaration'):
                    # Non-self target should NOT be the terminal participant
                    assert decl['target_participant_id'] != participant2_id, \
                        f"Terminal participant {participant2_id} should not be a target"
        
        print(f"PASS: At least one active participant → {sheets_count} sheets created, phase = collecting")
    
    def test_self_declaration_alone_no_sheet(self):
        """
        Self-declaration alone (without relevant non-self targets) should NOT generate a sheet.
        If a participant is in manual_review but all OTHER participants are terminal,
        the self-declaration alone doesn't justify creating a sheet.
        """
        from services.declarative_service import initialize_declarative_phase
        
        apt_id = f"{self.test_prefix}_apt_self_only"
        org_user_id = f"{self.test_prefix}_org_user3"
        participant1_id = f"{self.test_prefix}_p1_self"
        
        # Create organizer user
        self.db.users.insert_one({
            "user_id": org_user_id,
            "email": f"{self.test_prefix}_org3@test.com",
            "first_name": "Test",
            "last_name": "Organizer3"
        })
        
        # Create appointment
        self.db.appointments.insert_one({
            "appointment_id": apt_id,
            "organizer_id": org_user_id,
            "title": "Test Appointment Self Only",
            "start_datetime": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            "status": "completed",
            "declarative_phase": None
        })
        
        # Create organizer as participant (active) - this is the only active participant
        self.db.participants.insert_one({
            "participant_id": f"{self.test_prefix}_org_p3",
            "appointment_id": apt_id,
            "user_id": org_user_id,
            "email": f"{self.test_prefix}_org3@test.com",
            "status": "accepted_guaranteed"
        })
        
        # Create participant 1 with TERMINAL status
        self.db.participants.insert_one({
            "participant_id": participant1_id,
            "appointment_id": apt_id,
            "user_id": f"{self.test_prefix}_user1_self",
            "email": f"{self.test_prefix}_user1_self@test.com",
            "status": "cancelled_by_participant"  # TERMINAL
        })
        
        # Create attendance record in manual_review ONLY for the terminal participant
        # This simulates a scenario where the only person in review has cancelled
        self.db.attendance_records.insert_one({
            "record_id": f"{self.test_prefix}_rec1_self",
            "appointment_id": apt_id,
            "participant_id": participant1_id,
            "review_required": True,
            "outcome": "manual_review"
        })
        
        # Call initialize_declarative_phase
        initialize_declarative_phase(apt_id)
        
        # Verify: NO sheets should be created (self-declaration alone doesn't suffice)
        sheets_count = self.db.attendance_sheets.count_documents({"appointment_id": apt_id})
        assert sheets_count == 0, f"Expected 0 sheets (self-declaration alone), got {sheets_count}"
        
        # Verify: declarative_phase should be 'not_needed'
        apt = self.db.appointments.find_one({"appointment_id": apt_id})
        assert apt['declarative_phase'] == 'not_needed', \
            f"Expected declarative_phase='not_needed', got '{apt['declarative_phase']}'"
        
        print("PASS: Self-declaration alone → 0 sheets created, phase = not_needed")
    
    def test_guarantee_released_is_terminal(self):
        """
        Verify that 'guarantee_released' status is also treated as terminal
        """
        from services.declarative_service import initialize_declarative_phase
        
        apt_id = f"{self.test_prefix}_apt_guarantee_released"
        org_user_id = f"{self.test_prefix}_org_user4"
        participant1_id = f"{self.test_prefix}_p1_gr"
        
        # Create organizer user
        self.db.users.insert_one({
            "user_id": org_user_id,
            "email": f"{self.test_prefix}_org4@test.com",
            "first_name": "Test",
            "last_name": "Organizer4"
        })
        
        # Create appointment
        self.db.appointments.insert_one({
            "appointment_id": apt_id,
            "organizer_id": org_user_id,
            "title": "Test Appointment Guarantee Released",
            "start_datetime": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            "status": "completed",
            "declarative_phase": None
        })
        
        # Create organizer as participant (active)
        self.db.participants.insert_one({
            "participant_id": f"{self.test_prefix}_org_p4",
            "appointment_id": apt_id,
            "user_id": org_user_id,
            "email": f"{self.test_prefix}_org4@test.com",
            "status": "accepted_guaranteed"
        })
        
        # Create participant 1 with guarantee_released status (TERMINAL)
        self.db.participants.insert_one({
            "participant_id": participant1_id,
            "appointment_id": apt_id,
            "user_id": f"{self.test_prefix}_user1_gr",
            "email": f"{self.test_prefix}_user1_gr@test.com",
            "status": "guarantee_released"  # TERMINAL
        })
        
        # Create attendance record in manual_review
        self.db.attendance_records.insert_one({
            "record_id": f"{self.test_prefix}_rec1_gr",
            "appointment_id": apt_id,
            "participant_id": participant1_id,
            "review_required": True,
            "outcome": "manual_review"
        })
        
        # Call initialize_declarative_phase
        initialize_declarative_phase(apt_id)
        
        # Verify: NO sheets should be created
        sheets_count = self.db.attendance_sheets.count_documents({"appointment_id": apt_id})
        assert sheets_count == 0, f"Expected 0 sheets (guarantee_released is terminal), got {sheets_count}"
        
        # Verify: declarative_phase should be 'not_needed'
        apt = self.db.appointments.find_one({"appointment_id": apt_id})
        assert apt['declarative_phase'] == 'not_needed', \
            f"Expected declarative_phase='not_needed', got '{apt['declarative_phase']}'"
        
        print("PASS: guarantee_released is treated as terminal → 0 sheets, phase = not_needed")


class TestGetPendingSheetsRetroactiveFiltering:
    """Test GET /api/attendance-sheets/pending retroactive filtering"""
    
    @pytest.fixture(autouse=True)
    def setup_db_and_auth(self):
        """Setup test data and get auth token"""
        from database import db
        self.db = db
        self.test_prefix = f"TEST_ITER170_PENDING_{uuid.uuid4().hex[:8]}"
        
        # Get auth token
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testuser_audit@nlyt.app",
            "password": "TestAudit123!"
        })
        if login_resp.status_code == 200:
            data = login_resp.json()
            self.token = data.get('access_token') or data.get('token')
            self.user_id = data.get('user', {}).get('user_id')
        else:
            pytest.skip("Authentication failed - skipping authenticated tests")
        
        yield
        
        # Cleanup
        self.db.appointments.delete_many({"appointment_id": {"$regex": f"^{self.test_prefix}"}})
        self.db.participants.delete_many({"appointment_id": {"$regex": f"^{self.test_prefix}"}})
        self.db.attendance_records.delete_many({"appointment_id": {"$regex": f"^{self.test_prefix}"}})
        self.db.attendance_sheets.delete_many({"appointment_id": {"$regex": f"^{self.test_prefix}"}})
    
    def test_pending_excludes_sheets_with_all_terminal_targets(self):
        """
        GET /api/attendance-sheets/pending should EXCLUDE sheets where all
        non-self targets have terminal status
        """
        apt_id = f"{self.test_prefix}_apt_exclude"
        participant1_id = f"{self.test_prefix}_p1_exclude"
        
        # Create appointment in collecting phase
        self.db.appointments.insert_one({
            "appointment_id": apt_id,
            "organizer_id": self.user_id,
            "title": "Test Appointment Exclude",
            "start_datetime": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            "status": "completed",
            "declarative_phase": "collecting",
            "declarative_deadline": (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()
        })
        
        # Create participant with TERMINAL status
        self.db.participants.insert_one({
            "participant_id": participant1_id,
            "appointment_id": apt_id,
            "user_id": f"{self.test_prefix}_user1_exclude",
            "email": f"{self.test_prefix}_user1_exclude@test.com",
            "status": "cancelled_by_participant"  # TERMINAL
        })
        
        # Create a sheet for the current user with the terminal participant as target
        self.db.attendance_sheets.insert_one({
            "sheet_id": f"{self.test_prefix}_sheet_exclude",
            "appointment_id": apt_id,
            "submitted_by_user_id": self.user_id,
            "submitted_by_participant_id": f"{self.test_prefix}_org_p_exclude",
            "status": "pending",
            "declarations": [
                {
                    "target_participant_id": participant1_id,
                    "target_user_id": f"{self.test_prefix}_user1_exclude",
                    "declared_status": None,
                    "is_self_declaration": False
                }
            ],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "deadline": (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()
        })
        
        # Call GET /pending
        headers = {"Authorization": f"Bearer {self.token}"}
        resp = requests.get(f"{BASE_URL}/api/attendance-sheets/pending", headers=headers)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify: The sheet should NOT be in the response (all non-self targets are terminal)
        sheet_ids = [s.get('sheet_id') for s in data.get('pending_sheets', [])]
        assert f"{self.test_prefix}_sheet_exclude" not in sheet_ids, \
            f"Sheet with all terminal targets should be excluded from /pending"
        
        print("PASS: GET /pending excludes sheets with all terminal non-self targets")
    
    def test_pending_includes_sheets_with_active_targets(self):
        """
        GET /api/attendance-sheets/pending should INCLUDE sheets where at least
        one non-self target has active status
        """
        apt_id = f"{self.test_prefix}_apt_include"
        participant1_id = f"{self.test_prefix}_p1_include"
        
        # Create appointment in collecting phase
        self.db.appointments.insert_one({
            "appointment_id": apt_id,
            "organizer_id": self.user_id,
            "title": "Test Appointment Include",
            "start_datetime": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            "status": "completed",
            "declarative_phase": "collecting",
            "declarative_deadline": (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()
        })
        
        # Create participant with ACTIVE status
        self.db.participants.insert_one({
            "participant_id": participant1_id,
            "appointment_id": apt_id,
            "user_id": f"{self.test_prefix}_user1_include",
            "email": f"{self.test_prefix}_user1_include@test.com",
            "status": "accepted_guaranteed"  # ACTIVE
        })
        
        # Create a sheet for the current user with the active participant as target
        self.db.attendance_sheets.insert_one({
            "sheet_id": f"{self.test_prefix}_sheet_include",
            "appointment_id": apt_id,
            "submitted_by_user_id": self.user_id,
            "submitted_by_participant_id": f"{self.test_prefix}_org_p_include",
            "status": "pending",
            "declarations": [
                {
                    "target_participant_id": participant1_id,
                    "target_user_id": f"{self.test_prefix}_user1_include",
                    "declared_status": None,
                    "is_self_declaration": False
                }
            ],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "deadline": (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()
        })
        
        # Call GET /pending
        headers = {"Authorization": f"Bearer {self.token}"}
        resp = requests.get(f"{BASE_URL}/api/attendance-sheets/pending", headers=headers)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify: The sheet SHOULD be in the response (has active non-self target)
        sheet_ids = [s.get('sheet_id') for s in data.get('pending_sheets', [])]
        assert f"{self.test_prefix}_sheet_include" in sheet_ids, \
            f"Sheet with active targets should be included in /pending. Got: {sheet_ids}"
        
        print("PASS: GET /pending includes sheets with active non-self targets")
    
    def test_pending_excludes_self_declaration_only_sheets(self):
        """
        GET /api/attendance-sheets/pending should EXCLUDE sheets where only
        self-declarations remain (no non-self targets)
        """
        apt_id = f"{self.test_prefix}_apt_self_only"
        
        # Create appointment in collecting phase
        self.db.appointments.insert_one({
            "appointment_id": apt_id,
            "organizer_id": self.user_id,
            "title": "Test Appointment Self Only",
            "start_datetime": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            "status": "completed",
            "declarative_phase": "collecting",
            "declarative_deadline": (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()
        })
        
        # Create a sheet with ONLY self-declaration (no non-self targets)
        self.db.attendance_sheets.insert_one({
            "sheet_id": f"{self.test_prefix}_sheet_self_only",
            "appointment_id": apt_id,
            "submitted_by_user_id": self.user_id,
            "submitted_by_participant_id": f"{self.test_prefix}_org_p_self",
            "status": "pending",
            "declarations": [
                {
                    "target_participant_id": f"{self.test_prefix}_org_p_self",
                    "target_user_id": self.user_id,
                    "declared_status": None,
                    "is_self_declaration": True  # ONLY self-declaration
                }
            ],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "deadline": (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()
        })
        
        # Call GET /pending
        headers = {"Authorization": f"Bearer {self.token}"}
        resp = requests.get(f"{BASE_URL}/api/attendance-sheets/pending", headers=headers)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify: The sheet should NOT be in the response (only self-declarations)
        sheet_ids = [s.get('sheet_id') for s in data.get('pending_sheets', [])]
        assert f"{self.test_prefix}_sheet_self_only" not in sheet_ids, \
            f"Sheet with only self-declarations should be excluded from /pending"
        
        print("PASS: GET /pending excludes sheets with only self-declarations")


class TestMixedScenarios:
    """Test mixed scenarios with both terminal and active participants"""
    
    @pytest.fixture(autouse=True)
    def setup_db(self):
        """Setup and cleanup test data"""
        from database import db
        self.db = db
        self.test_prefix = f"TEST_ITER170_MIXED_{uuid.uuid4().hex[:8]}"
        yield
        # Cleanup
        self.db.appointments.delete_many({"appointment_id": {"$regex": f"^{self.test_prefix}"}})
        self.db.participants.delete_many({"appointment_id": {"$regex": f"^{self.test_prefix}"}})
        self.db.attendance_records.delete_many({"appointment_id": {"$regex": f"^{self.test_prefix}"}})
        self.db.attendance_sheets.delete_many({"appointment_id": {"$regex": f"^{self.test_prefix}"}})
        self.db.users.delete_many({"user_id": {"$regex": f"^{self.test_prefix}"}})
    
    def test_mixed_terminal_and_active_only_active_as_targets(self):
        """
        When some participants are terminal and some are active,
        only active participants should appear as targets in sheets
        """
        from services.declarative_service import initialize_declarative_phase
        
        apt_id = f"{self.test_prefix}_apt_mixed"
        org_user_id = f"{self.test_prefix}_org_user"
        active_participant_id = f"{self.test_prefix}_p_active"
        terminal_participant_id = f"{self.test_prefix}_p_terminal"
        
        # Create organizer user
        self.db.users.insert_one({
            "user_id": org_user_id,
            "email": f"{self.test_prefix}_org@test.com",
            "first_name": "Test",
            "last_name": "Organizer"
        })
        
        # Create appointment
        self.db.appointments.insert_one({
            "appointment_id": apt_id,
            "organizer_id": org_user_id,
            "title": "Test Appointment Mixed",
            "start_datetime": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            "status": "completed",
            "declarative_phase": None
        })
        
        # Create organizer as participant (active)
        self.db.participants.insert_one({
            "participant_id": f"{self.test_prefix}_org_p",
            "appointment_id": apt_id,
            "user_id": org_user_id,
            "email": f"{self.test_prefix}_org@test.com",
            "status": "accepted_guaranteed"
        })
        
        # Create ACTIVE participant
        self.db.participants.insert_one({
            "participant_id": active_participant_id,
            "appointment_id": apt_id,
            "user_id": f"{self.test_prefix}_user_active",
            "email": f"{self.test_prefix}_user_active@test.com",
            "status": "accepted_guaranteed"  # ACTIVE
        })
        
        # Create TERMINAL participant
        self.db.participants.insert_one({
            "participant_id": terminal_participant_id,
            "appointment_id": apt_id,
            "user_id": f"{self.test_prefix}_user_terminal",
            "email": f"{self.test_prefix}_user_terminal@test.com",
            "status": "cancelled_by_participant"  # TERMINAL
        })
        
        # Create attendance records in manual_review for BOTH
        self.db.attendance_records.insert_one({
            "record_id": f"{self.test_prefix}_rec_active",
            "appointment_id": apt_id,
            "participant_id": active_participant_id,
            "review_required": True,
            "outcome": "manual_review"
        })
        self.db.attendance_records.insert_one({
            "record_id": f"{self.test_prefix}_rec_terminal",
            "appointment_id": apt_id,
            "participant_id": terminal_participant_id,
            "review_required": True,
            "outcome": "manual_review"
        })
        
        # Call initialize_declarative_phase
        initialize_declarative_phase(apt_id)
        
        # Verify: Sheets should be created
        sheets = list(self.db.attendance_sheets.find({"appointment_id": apt_id}))
        assert len(sheets) >= 1, f"Expected at least 1 sheet, got {len(sheets)}"
        
        # Verify: Terminal participant should NOT be a target in any sheet
        for sheet in sheets:
            for decl in sheet.get('declarations', []):
                if not decl.get('is_self_declaration'):
                    assert decl['target_participant_id'] != terminal_participant_id, \
                        f"Terminal participant should not be a target"
        
        # Verify: Active participant SHOULD be a target
        all_targets = []
        for sheet in sheets:
            for decl in sheet.get('declarations', []):
                if not decl.get('is_self_declaration'):
                    all_targets.append(decl['target_participant_id'])
        
        assert active_participant_id in all_targets, \
            f"Active participant should be a target. Targets: {all_targets}"
        
        print("PASS: Mixed scenario → only active participants as targets")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
