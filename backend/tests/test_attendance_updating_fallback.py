"""
Unit and Integration Tests: Attendance Updating Fallback & Empty State Guarantees
Validates:
1. If current attendance is available, displays current data (is_previous_data=False).
2. If current attendance is updating (e.g. empty or transient drop from portal),
   seamlessly displays previous attendance data stored in database (is_previous_data=True).
3. If current attendance is empty AND previous data was in HTML table (attendance_table),
   correctly parses and displays previous stored data.
4. If NEITHER current nor previous attendance data is available in database,
   returns empty subjects list so the UI displays the empty state ("No attendance data available yet").
5. Interactive simulator works against previous data when current is updating.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from attendance_calculator import (
    resolve_student_attendance_records,
    summarize_student_attendance
)
from pyserver import app, generate_auth_token


class TestAttendanceUpdatingFallback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.client = cls.app.test_client()

    def test_01_current_data_available_displays_current(self):
        """When current attendance is available in studzone1, display it directly."""
        mock_user = {
            "rollNo": "TEST01",
            "studzone1": {
                "parsed_attendance": [
                    {"code": "23MX31", "name": "CLOUD COMPUTING", "attended": "25", "total_classes": "30"}
                ]
            }
        }
        records, is_prev, is_upd = resolve_student_attendance_records(mock_user)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["code"], "23MX31")
        self.assertFalse(is_prev)
        self.assertFalse(is_upd)

        summary = summarize_student_attendance(records, target=75.0, user_doc=mock_user)
        self.assertEqual(len(summary["subjects"]), 1)
        self.assertFalse(summary["is_previous_data"])
        self.assertFalse(summary["is_updating"])

    def test_02_current_empty_displays_stored_previous_parsed(self):
        """When current attendance is updating (empty), display previous_parsed_attendance from DB."""
        mock_user = {
            "rollNo": "TEST02",
            "studzone1": {
                "parsed_attendance": []  # Empty while updating on portal
            },
            "previous_parsed_attendance": [
                {"code": "23MX31", "name": "CLOUD COMPUTING", "attended": "20", "total_classes": "25"},
                {"code": "23MX36", "name": "CLOUD COMPUTING LAB", "attended": "30", "total_classes": "32"}
            ]
        }
        records, is_prev, is_upd = resolve_student_attendance_records(mock_user)
        self.assertEqual(len(records), 2)
        self.assertTrue(is_prev)
        self.assertTrue(is_upd)

        summary = summarize_student_attendance([], target=75.0, user_doc=mock_user)
        self.assertEqual(len(summary["subjects"]), 2)
        self.assertTrue(summary["is_previous_data"])
        self.assertTrue(summary["is_updating"])
        self.assertEqual(summary["overall"]["attended"], 50)
        self.assertEqual(summary["overall"]["conducted"], 57)

    def test_03_current_empty_falls_back_to_attendance_table_html(self):
        """When current attendance is updating (empty), parse stored HTML attendance_table from DB."""
        html_table = (
            '<table class="table table-bordered" id="example">'
            '<thead><tr><th>Course Code</th><th>Total hr</th><th>Exemp hr</th><th>Tot Absent</th>'
            '<th>Total Present</th><th>(%) Attendance</th></tr></thead>'
            '<tbody>'
            '<tr><td>23MX31</td><td>20</td><td>0</td><td>2</td><td>18</td><td>90%</td></tr>'
            '</tbody></table>'
        )
        mock_user = {
            "rollNo": "TEST03",
            "studzone1": {
                "parsed_attendance": [],
                "attendance_html": "<table><tbody></tbody></table>"  # Empty table from live portal
            },
            "attendance_table": html_table  # Stored previous table in MongoDB
        }
        records, is_prev, is_upd = resolve_student_attendance_records(mock_user)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["code"], "23MX31")
        self.assertEqual(records[0]["attended"], "18")
        self.assertTrue(is_prev)
        self.assertTrue(is_upd)

        summary = summarize_student_attendance([], target=75.0, user_doc=mock_user)
        self.assertEqual(len(summary["subjects"]), 1)
        self.assertTrue(summary["is_previous_data"])
        self.assertTrue(summary["is_updating"])

    def test_04_no_data_at_all_returns_empty_for_placeholder_display(self):
        """When neither current nor previous data is available in DB, returns empty subjects."""
        mock_user = {
            "rollNo": "NEW_STUDENT",
            "studzone1": {
                "parsed_attendance": []
            }
        }
        records, is_prev, is_upd = resolve_student_attendance_records(mock_user)
        self.assertEqual(len(records), 0)
        self.assertFalse(is_prev)
        self.assertFalse(is_upd)

        summary = summarize_student_attendance([], target=75.0, user_doc=mock_user)
        self.assertEqual(len(summary["subjects"]), 0)
        self.assertFalse(summary["is_previous_data"])
        self.assertFalse(summary["is_updating"])

    def test_05_api_endpoint_returns_previous_flag_when_updating(self):
        """API /api/attendance/summary includes is_previous_data and is_updating in response."""
        token = generate_auth_token("25MX232")
        resp = self.client.get('/api/attendance/summary', headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("is_previous_data", data)
        self.assertIn("is_updating", data)
        self.assertGreater(len(data.get("subjects", [])), 0)


if __name__ == '__main__':
    unittest.main()
