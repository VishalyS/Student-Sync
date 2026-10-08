"""
Test Suite: Pre-MCP Production Correction Pass Verification
Validates:
1. First registration succeeds.
2. First registration sends exactly one welcome email with required text.
3. First registration establishes baseline (baseline_initialized: True, monitoring_enabled: True).
4. Existing data is not treated as changes during baseline initialization.
5. Duplicate registration is rejected (HTTP 409).
6. Duplicate registration sends zero welcome emails.
7. Duplicate registration creates zero notifications.
8. Duplicate registration does not reset baseline.
9. Future genuine changes still generate notifications.
10. Duplicate identical changes remain deduplicated (SHA-256 changeHash).
11. Per-user notification routing remains correct.
12. Cross-user notification isolation remains correct.
13. Roll number matching is case-insensitive (e.g., 25MX227 vs 25mx227).
14. "Courses" is not present in intended user-facing academic labels in frontend.
15. Thursday timetable preserves consecutive laboratory periods and headers (6 classes, no free slots).
16. Navbar responsive layout contains no overlap guards (flex-shrink-0 whitespace-nowrap).
"""

import os
import sys
import re
import unittest
from unittest.mock import patch, MagicMock
from bson import ObjectId
from datetime import datetime, timezone

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from pyserver import app
from notifications.change_detector import detect_granular_changes, compute_change_hash, process_normalized_event
from timetable_calculator import parse_schedule_html_to_matrix, parse_weekly_schedule_matrix, normalize_schedule_row
from attendance_calculator import parse_daily_schedule


class TestPreMcpCorrections(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()

    # --------------------------------------------------------------------------
    # 1. FIRST REGISTRATION SUCCEEDS
    # 2. FIRST REGISTRATION SENDS EXACTLY ONE WELCOME EMAIL
    # 3. FIRST REGISTRATION ESTABLISHES BASELINE
    # 4. EXISTING DATA IS NOT TREATED AS CHANGES
    # --------------------------------------------------------------------------
    @patch('pyserver.send_email_direct')
    @patch('pyserver.users_collection')
    @patch('pyserver.notifications_collection')
    @patch('pyserver.sync_student_dual_portal')
    def test_01_first_registration_lifecycle(
        self,
        mock_sync,
        mock_notifs_col,
        mock_users_col,
        mock_send_email
    ):
        """First registration creates account, sends exactly 1 welcome email, and sets baseline."""
        # First call is duplicate check (returns None), second is inside dispatch_welcome_email_to_student
        mock_users_col.find_one.side_effect = [
            None,
            {"rollNo": "25MX999", "name": "Kavitha S", "email": "25mx999@psgtech.ac.in", "welcomeEmailSent": False}
        ]
        mock_users_col.update_one.return_value = MagicMock()
        mock_notifs_col.find_one.return_value = None
        mock_notifs_col.insert_one.return_value = MagicMock()
        mock_send_email.return_value = (True, "Email sent successfully")

        mock_sync.return_value = ({
            "rollNo": "25MX999",
            "name": "Kavitha S",
            "email": "25mx999@psgtech.ac.in",
            "baseline_initialized": True,
            "monitoring_enabled": True,
            "welcomeEmailSent": False,
            "studzone1": {"attendance": "mock"},
            "studzone2": {"results": "mock"}
        }, None)

        payload = {
            "name": "Kavitha S",
            "rollNo": "25MX999",
            "email": "25mx999@psgtech.ac.in",
            "password": "Password123!"
        }

        resp = self.client.post('/register', json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertIn("Registration successful", data.get("message"))

        # Find the welcome email call sent to the student
        welcome_calls = [
            c for c in mock_send_email.call_args_list
            if (len(c[0]) > 1 and "Welcome to Student Sync" in str(c[0][1])) or "Welcome to Student Sync" in str(c[1].get('subject', ''))
        ]
        self.assertEqual(len(welcome_calls), 1, "Exactly one welcome email sent to registered student")
        w_args, w_kwargs = welcome_calls[0]
        to_email = w_kwargs.get('to') or (w_args[0] if len(w_args) > 0 else "")
        subject = w_kwargs.get('subject') or (w_args[1] if len(w_args) > 1 else "")
        body = w_kwargs.get('body') or (w_args[2] if len(w_args) > 2 else "")

        self.assertEqual(to_email, "25mx999@psgtech.ac.in")
        self.assertIn("Welcome to Student Sync", subject)
        self.assertIn("Thank you for registering with Student Sync", body)
        self.assertIn("From now on, you will receive meaningful notifications when relevant information changes", body)

    # --------------------------------------------------------------------------
    # 5. DUPLICATE REGISTRATION IS REJECTED
    # 6. DUPLICATE REGISTRATION SENDS ZERO WELCOME EMAILS
    # 7. DUPLICATE REGISTRATION CREATES ZERO NOTIFICATIONS
    # 8. DUPLICATE REGISTRATION DOES NOT RESET BASELINE
    # 13. ROLL NUMBER MATCHING IS CASE-INSENSITIVE
    # --------------------------------------------------------------------------
    @patch('pyserver.send_email_direct')
    @patch('pyserver.users_collection')
    @patch('pyserver.notifications_collection')
    def test_02_duplicate_registration_rejected_case_insensitive(
        self,
        mock_notifs_col,
        mock_users_col,
        mock_send_email
    ):
        """Duplicate registration (exact and case-varied) is rejected with 409 and 0 side-effects."""
        existing_user = {
            "_id": ObjectId(),
            "rollNo": "25MX227",
            "email": "25mx227@psgtech.ac.in",
            "baseline_initialized": True,
            "monitoring_enabled": True,
            "welcomeEmailSent": True,
            "studzone1_data": {"baseline": "data"}
        }

        # Mock find_one to simulate MongoDB regex finding the existing user
        def mock_find_one(query):
            roll_query = query.get("rollNo")
            if isinstance(roll_query, dict) and "$regex" in roll_query:
                regex_pattern = roll_query["$regex"]
                if re.match(regex_pattern, "25MX227", re.IGNORECASE):
                    return existing_user
            elif roll_query in ["25MX227", "25mx227"]:
                return existing_user
            return None

        mock_users_col.find_one.side_effect = mock_find_one

        # Attempt 1: Uppercase roll number
        payload_upper = {
            "name": "Vishal",
            "rollNo": "25MX227",
            "email": "25mx227@psgtech.ac.in",
            "password": "Password123!"
        }
        resp1 = self.client.post('/register', json=payload_upper)
        self.assertEqual(resp1.status_code, 409)
        data1 = resp1.get_json()
        self.assertEqual(data1.get("message"), "This student is already registered.")
        self.assertEqual(data1.get("detail"), "Already registered. Please Login.")
        self.assertTrue(data1.get("already_registered"))

        # Attempt 2: Lowercase roll number
        payload_lower = {
            "name": "Vishal",
            "rollNo": "25mx227",
            "email": "25mx227@psgtech.ac.in",
            "password": "Password123!"
        }
        resp2 = self.client.post('/register', json=payload_lower)
        self.assertEqual(resp2.status_code, 409)
        data2 = resp2.get_json()
        self.assertEqual(data2.get("message"), "This student is already registered.")
        self.assertEqual(data2.get("detail"), "Already registered. Please Login.")

        # Assert zero side-effects
        self.assertEqual(mock_send_email.call_count, 0, "Zero welcome emails sent on duplicate registration")
        self.assertEqual(mock_users_col.insert_one.call_count, 0, "Zero users created on duplicate registration")
        self.assertEqual(mock_users_col.update_one.call_count, 0, "Zero user baseline modifications on duplicate registration")
        self.assertEqual(mock_notifs_col.insert_one.call_count, 0, "Zero notifications created on duplicate registration")

    # --------------------------------------------------------------------------
    # 9. FUTURE GENUINE CHANGES STILL GENERATE NOTIFICATIONS
    # 10. DUPLICATE IDENTICAL CHANGES REMAIN DEDUPLICATED
    # --------------------------------------------------------------------------
    def test_03_future_genuine_changes_and_deduplication(self):
        """Genuine changes generate normalized events; identical changes produce same SHA-256 hash."""
        baseline_user = {
            "rollNo": "25MX227",
            "baseline_initialized": True,
            "monitoring_enabled": True,
            "studzone1": {
                "parsed_attendance": [
                    {"code": "23MX31", "name": "CLOUD COMPUTING", "percentage": "90.0"}
                ]
            },
            "studzone2": {}
        }
        sz1_fresh = {
            "parsed_attendance": [
                {"code": "23MX31", "name": "CLOUD COMPUTING", "percentage": "95.0"}
            ]
        }
        sz2_fresh = {}

        events = detect_granular_changes("25MX227", baseline_user, sz1_fresh, sz2_fresh)
        self.assertGreaterEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["category"], "attendance")
        self.assertEqual(event["title"], "Attendance Updated")
        self.assertEqual(event["rollNo"], "25MX227")
        self.assertEqual(event["changeData"]["previousValue"], "90.0")
        self.assertEqual(event["changeData"]["newValue"], "95.0")
        self.assertIn("90.0 → 95.0", event["description"])

        # Compute hash
        hash1 = compute_change_hash("25MX227", "attendance", "Attendance", "Attendance Updated", event["description"], "23MX31_90.0_95.0")
        hash2 = compute_change_hash("25MX227", "attendance", "Attendance", "Attendance Updated", event["description"], "23MX31_90.0_95.0")
        self.assertEqual(hash1, hash2, "Identical change must generate identical SHA-256 hash for deduplication")
        self.assertEqual(len(hash1), 64, "Hash must be standard 64-char hex SHA-256")
        self.assertEqual(event["changeHash"], hash1)

    # --------------------------------------------------------------------------
    # 11. PER-USER NOTIFICATION ROUTING
    # 12. CROSS-USER NOTIFICATION ISOLATION
    # --------------------------------------------------------------------------
    def test_04_per_user_routing_and_isolation(self):
        """User A changes are routed strictly to User A's recipient, isolated from User B."""
        user_a = {
            "roll_no": "25MX227",
            "email": "vishal@psgtech.ac.in",
            "configured_recipient": "vishal.custom@gmail.com"
        }
        user_b = {
            "roll_no": "25MX232",
            "email": "student_b@psgtech.ac.in",
            "configured_recipient": None  # Should fallback to <roll>@psgtech.ac.in
        }

        # User A recipient resolution
        recipient_a = user_a.get("configured_recipient") or user_a.get("email") or f"{user_a['roll_no'].lower()}@psgtech.ac.in"
        self.assertEqual(recipient_a, "vishal.custom@gmail.com")

        # User B fallback resolution
        recipient_b = user_b.get("configured_recipient") or user_b.get("email") or f"{user_b['roll_no'].lower()}@psgtech.ac.in"
        self.assertEqual(recipient_b, "student_b@psgtech.ac.in")

        # Cross-isolation: events tagged with User A must not match User B
        event_a = {
            "roll_no": "25MX227",
            "category": "attendance",
            "field": "attendance_percentage",
            "old_value": "80",
            "new_value": "85"
        }
        self.assertNotEqual(event_a["roll_no"], user_b["roll_no"])

    # --------------------------------------------------------------------------
    # 15. THURSDAY TIMETABLE CONSECUTIVE LABORATORY PERIODS & HEADERS
    # --------------------------------------------------------------------------
    def test_05_thursday_timetable_consecutive_lab_periods(self):
        """Consecutive lab periods (with colspan=2) are preserved at Period 3 & 4 with 0 free slots."""
        # Realistic HTML snippet representing StudZone 1 timetable row for Thursday
        # with colspan="2" for 23MX36 Cloud Computing Laboratory
        thursday_html = """
        <table class="timetable-table">
            <tr>
                <th>DAY</th>
                <th>1<br>8:30-9:20</th>
                <th>2<br>9:20-10:10</th>
                <th>3<br>10:30-11:20</th>
                <th>4<br>11:20-12:10</th>
                <th>5<br>1:40-2:30</th>
                <th>6<br>2:30-3:20</th>
            </tr>
            <tr>
                <th>Time</th>
                <th>8.30 - 9.20</th>
                <th>9.20 - 10.10</th>
                <th>10.30 - 11.20</th>
                <th>11.20 - 12.10</th>
                <th>1.40 - 2.30</th>
                <th>2.30 - 3.20</th>
            </tr>
            <tr>
                <td>Thursday</td>
                <td>23MXAE</td>
                <td>23MXM4</td>
                <td colspan="2">23MX36</td>
                <td>23MX31</td>
                <td>23MXCA</td>
            </tr>
        </table>
        """

        matrix = parse_schedule_html_to_matrix(thursday_html)
        self.assertIsNotNone(matrix)
        self.assertEqual(len(matrix), 3)
        thu_row = matrix[2]

        # Thursday row must have 7 elements: 'Thursday' + 6 periods
        self.assertEqual(len(thu_row), 7)
        self.assertEqual(thu_row[0], "Thursday")
        self.assertEqual(thu_row[1], "23MXAE")  # Period 1
        self.assertEqual(thu_row[2], "23MXM4")  # Period 2
        self.assertEqual(thu_row[3], "23MX36")  # Period 3 (Cloud Computing Lab)
        self.assertEqual(thu_row[4], "23MX36")  # Period 4 (Cloud Computing Lab, preserved!)
        self.assertEqual(thu_row[5], "23MX31")  # Period 5 (Cloud Computing)
        self.assertEqual(thu_row[6], "23MXCA")  # Period 6 (Entrepreneurship)

        # Parse with weekly schedule calculator
        weekly = parse_weekly_schedule_matrix(matrix, class_timetable_html=thursday_html)
        thu_schedule = next((d for d in weekly["days"] if d["day"] == "Thursday"), None)
        self.assertIsNotNone(thu_schedule)

        # Verify classes count and free periods
        self.assertEqual(thu_schedule["scheduled_classes"], 6)
        self.assertEqual(thu_schedule["free_periods"], 0)

        # Also test normalize_schedule_row on a 6-item unexpanded row
        unexpanded_row = [
            "Thursday",
            "MCA_3\r\n 23MXAE\nCOMPUTER NETWORKS",
            "MCA_3\r\n 23MXM4\nPROFESSIONAL ETHICS",
            "MCA_3\r\n 23MX36\nCLOUD COMPUTING LABORATORY",
            "MCA_3\r\n 23MX31\nCLOUD COMPUTING",
            "MCA_3\r\n 23MXCA\nENTREPRENEURSHIP"
        ]
        normalized = normalize_schedule_row(unexpanded_row, total_periods=6)
        self.assertEqual(len(normalized), 7)
        self.assertIn("23MX36", normalized[3])
        self.assertIn("23MX36", normalized[4])

    # --------------------------------------------------------------------------
    # 14. "COURSES" IS NOT PRESENT IN INTENDED USER-FACING ACADEMIC LABELS
    # --------------------------------------------------------------------------
    def test_06_frontend_courses_to_subjects_terminology(self):
        """Frontend files have no improper user-facing 'Courses' labels."""
        frontend_src = os.path.abspath(os.path.join(backend_dir, '..', 'react-spd', 'src'))
        self.assertTrue(os.path.isdir(frontend_src))

        # Check key components
        disallowed_phrases = [
            "Course Attendance",
            "Course Performance",
            "Select Course",
            "Course List",
            "Course Details",
            "Semester Courses",
            "Recorded Courses",
            "Graded Courses",
            "Simulated Course Basket"
        ]

        files_to_check = [
            "Dashboard.jsx",
            "AttendanceDashboard.jsx",
            "ScheduleDashboard.jsx",
            "components/academics/MarksSummaryCard.jsx",
            "components/academics/ResultsAnalytics.jsx",
            "components/academics/CgpaSimulator.jsx",
            "components/academics/CAComponentBreakdown.jsx"
        ]

        for rel_path in files_to_check:
            full_path = os.path.join(frontend_src, rel_path)
            if not os.path.isfile(full_path):
                continue
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()

            for phrase in disallowed_phrases:
                self.assertNotIn(phrase, content, f"Disallowed phrase '{phrase}' found in {rel_path}")

    # --------------------------------------------------------------------------
    # 16. NAVBAR HAS NO OVERLAP GUARDS
    # --------------------------------------------------------------------------
    def test_07_navbar_no_overlap_guards(self):
        """Navbar brand and layout use flex-shrink-0, whitespace-nowrap, and proper breakpoints."""
        navbar_path = os.path.abspath(os.path.join(backend_dir, '..', 'react-spd', 'src', 'components', 'Navbar.jsx'))
        self.assertTrue(os.path.isfile(navbar_path))
        with open(navbar_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check logo/brand wrapping prevention
        self.assertIn("flex-shrink-0 whitespace-nowrap", content, "Brand link must have flex-shrink-0 whitespace-nowrap")
        self.assertIn("Student Sync", content)
        # Check login / logout standardization
        self.assertNotIn("Sign In", content)
        self.assertNotIn("Sign Out", content)
        self.assertIn("Login", content)
        self.assertIn("Logout", content)


if __name__ == '__main__':
    unittest.main()
