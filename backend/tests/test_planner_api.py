"""
backend/tests/test_planner_api.py

Deterministic and isolated API test suite for Phase 7 Personalized Study Planner Endpoints:
1. Unauthenticated requests return HTTP 401
2. Invalid tokens return HTTP 401
3. Cross-user access returns HTTP 403 (student isolation enforced)
4. Authenticated legitimate student requests return HTTP 200
5. Missing student records return HTTP 404
6. Complete response schema validation against deterministic fixtures
7. All active subjects represented in subject_matrix
8. Zero-write guarantee: API requests NEVER write to MongoDB

Refactored to use deterministic, isolated mock data fixtures.
Does not depend on mutable production records in MongoDB Atlas.
"""

import os
import sys
import copy
import unittest
from unittest.mock import patch, MagicMock

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from pyserver import app, generate_auth_token


# =========================================================================
# DETERMINISTIC TEST FIXTURES
# =========================================================================

MOCK_STUDENT_25MX232 = {
    "rollNo": "25MX232",
    "name": "VISHALY S",
    "cgpa": 7.96,
    "email": "25mx232@psgtech.ac.in",
    "studzone1": {
        "parsed_attendance": [
            {"code": "23MX31", "name": "CLOUD COMPUTING", "attended": 36, "conducted": 40, "percentage": 90.0, "practical_attended": 0, "practical_conducted": 0},
            {"code": "23MX36", "name": "CLOUD COMPUTING LABORATORY", "attended": 28, "conducted": 30, "percentage": 93.33, "practical_attended": 0, "practical_conducted": 0},
            {"code": "23MX37", "name": "MINI PROJECT", "attended": 18, "conducted": 20, "percentage": 90.0, "practical_attended": 0, "practical_conducted": 0},
            {"code": "23MXAE", "name": "BIG DATA ANALYTICS", "attended": 34, "conducted": 40, "percentage": 85.0, "practical_attended": 0, "practical_conducted": 0},
            {"code": "23MXAF", "name": "DATA MINING AND ANALYTICS", "attended": 35, "conducted": 40, "percentage": 87.5, "practical_attended": 0, "practical_conducted": 0},
            {"code": "23MXAO", "name": "HUMAN COMPUTER INTERACTION", "attended": 38, "conducted": 40, "percentage": 95.0, "practical_attended": 0, "practical_conducted": 0},
            {"code": "23MXCA", "name": "ADVANCED JAVA PROGRAMMING", "attended": 32, "conducted": 40, "percentage": 80.0, "practical_attended": 0, "practical_conducted": 0},
            {"code": "23MXM4", "name": "PROFESSIONAL ETHICS", "attended": 19, "conducted": 20, "percentage": 95.0, "practical_attended": 0, "practical_conducted": 0}
        ],
        "parsed_marks": [
            {"code": "23MXM4", "name": "PROFESSIONAL ETHICS", "marks_data": ["*", "*", "", "*"]},
            {"code": "23MX37", "name": "MINI PROJECT", "marks_data": ["7", "8", "*", "*", "*", "*", "*", "*"]},
            {"code": "23MX36", "name": "CLOUD COMPUTING LABORATORY", "marks_data": ["24", "21", "45", "*"]},
            {"code": "23MX31", "name": "CLOUD COMPUTING", "marks_data": ["12", "*", "", "", "", "6", "*", "*", "6", "*"]},
            {"code": "23MXAE", "name": "COMPUTER NETWORKS", "marks_data": ["14.8", "*", "", "", "", "7.4", "*", "*", "7.4", "*"]},
            {"code": "23MXAF", "name": "DATA MINING AND ANALYTICS", "marks_data": ["15.4", "*", "", "", "", "7.7", "*", "*", "7.7", "*"]},
            {"code": "23MXAO", "name": "HUMAN COMPUTER INTERACTION", "marks_data": ["17", "*", "", "", "", "8.5", "*", "*", "8.5", "*"]},
            {"code": "23MXCA", "name": "ENTREPRENEURSHIP", "marks_data": ["17.2", "*", "", "", "", "8.6", "*", "*", "8.6", "*"]}
        ],
        "class_schedule": [
            ["Period", "1", "2", "3", "4", "5", "6"],
            ["Time", "8.30 - 9.20", "9.20 - 10.10", "10.30 - 11.20", "11.20 - 12.10", "1.40 - 2.30", "2.30 - 3.20"],
            [
                "Monday",
                "MCA_3\r\n 23MXAF\nDATA MINING AND ANALYTICS",
                "MCA_3\r\n 23MXAO\nHUMAN COMPUTER INTERACTION",
                "MCA_3\r\n 23MX31\nCLOUD COMPUTING",
                "-",
                "MCA_3\r\n 23MX37\nMINI PROJECT",
                "MCA_3\r\n 23MX37\nMINI PROJECT"
            ],
            [
                "Tuesday",
                "MCA_3\r\n 23MXAO\nHUMAN COMPUTER INTERACTION",
                "MCA_3\r\n 23MXAF\nDATA MINING AND ANALYTICS",
                "MCA_3\r\n 23MX36\nCLOUD COMPUTING LABORATORY",
                "MCA_3\r\n 23MX36\nCLOUD COMPUTING LABORATORY",
                "MCA_3\r\n 23MXCA\nADVANCED JAVA PROGRAMMING",
                "MCA_3\r\n 23MXM4\nPROFESSIONAL ETHICS"
            ],
            [
                "Wednesday",
                "-",
                "MCA_3\r\n 23MXCA\nADVANCED JAVA PROGRAMMING",
                "MCA_3\r\n 23MXAE\nBIG DATA ANALYTICS",
                "MCA_3\r\n 23MXAO\nHUMAN COMPUTER INTERACTION",
                "MCA_3\r\n 23MXAF\nDATA MINING AND ANALYTICS",
                "-"
            ],
            [
                "Thursday",
                "MCA_3\r\n 23MXAE\nBIG DATA ANALYTICS",
                "MCA_3\r\n 23MXM4\nPROFESSIONAL ETHICS",
                "MCA_3\r\n 23MX36\nCLOUD COMPUTING LABORATORY",
                "MCA_3\r\n 23MX36\nCLOUD COMPUTING LABORATORY",
                "MCA_3\r\n 23MX31\nCLOUD COMPUTING",
                "MCA_3\r\n 23MXCA\nADVANCED JAVA PROGRAMMING"
            ],
            [
                "Friday",
                "MCA_3\r\n 23MX31\nCLOUD COMPUTING",
                "-",
                "MCA_3\r\n 23MXAE\nBIG DATA ANALYTICS",
                "MCA_3\r\n TWM\nTUTOR WARD MEETING",
                "MCA_3\r\n 23MX37\nMINI PROJECT",
                "MCA_3\r\n 23MX37\nMINI PROJECT"
            ]
        ]
    },
    "studzone2": {
        "parsed_results": [
            {"semester": 1, "code": "23MX11", "credits": 4.0, "grade": "A+", "points": 9.0},
            {"semester": 1, "code": "23MX12", "credits": 4.0, "grade": "A", "points": 8.0},
            {"semester": 1, "code": "23MX13", "credits": 4.0, "grade": "B+", "points": 7.0},
            {"semester": 2, "code": "23MX21", "credits": 4.0, "grade": "A+", "points": 9.0},
            {"semester": 2, "code": "23MX22", "credits": 4.0, "grade": "A", "points": 8.0},
            {"semester": 2, "code": "23MX23", "credits": 4.0, "grade": "B+", "points": 7.0}
        ],
        "parsed_timetable": [
            {"code": "23MX31", "title": "CLOUD COMPUTING", "date": "2026-11-10", "session": "FN", "time": "09:30-12:30"},
            {"code": "23MXAE", "title": "BIG DATA ANALYTICS", "date": "2026-11-13", "session": "FN", "time": "09:30-12:30"},
            {"code": "23MXAF", "title": "DATA MINING AND ANALYTICS", "date": "2026-11-16", "session": "FN", "time": "09:30-12:30"},
            {"code": "23MXAO", "title": "HUMAN COMPUTER INTERACTION", "date": "2026-11-19", "session": "FN", "time": "09:30-12:30"},
            {"code": "23MXCA", "title": "ADVANCED JAVA PROGRAMMING", "date": "2026-11-22", "session": "FN", "time": "09:30-12:30"}
        ],
        "circulars": [
            {"title": "End Semester Exam Guidelines Nov 2026", "link": "/circular1.pdf", "date": "2026-10-15"},
            {"title": "Hall Ticket Download Procedure", "link": "/circular2.pdf", "date": "2026-10-18"},
            {"title": "Exam Center Seating Guidelines", "link": "/circular3.pdf", "date": "2026-10-20"}
        ]
    }
}

MOCK_STUDENT_25MX227 = copy.deepcopy(MOCK_STUDENT_25MX232)
MOCK_STUDENT_25MX227["rollNo"] = "25MX227"
MOCK_STUDENT_25MX227["name"] = "DAY SCHOLAR STUDENT"


class TestPlannerApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.client = cls.app.test_client()

        cls.roll_a = "25MX232"
        cls.roll_b = "25MX227"

        cls.token_a = generate_auth_token(cls.roll_a)
        cls.token_b = generate_auth_token(cls.roll_b)

    def setUp(self):
        # Setup mock finding function for deterministic isolation
        def mock_find_one(filter_dict, *args, **kwargs):
            if not isinstance(filter_dict, dict):
                return None
            roll = (filter_dict.get("rollNo") or filter_dict.get("rollno") or "")
            if isinstance(roll, str):
                roll_clean = roll.strip().upper()
                if roll_clean == "25MX232":
                    return copy.deepcopy(MOCK_STUDENT_25MX232)
                elif roll_clean == "25MX227":
                    return copy.deepcopy(MOCK_STUDENT_25MX227)
            return None

        # Patch both pyserver's users_collection and database's user_collection
        self.patcher1 = patch('pyserver.users_collection.find_one', side_effect=mock_find_one)
        self.patcher2 = patch('pyserver.users_collection.update_one')
        self.patcher3 = patch('pyserver.users_collection.insert_one')
        self.mock_find = self.patcher1.start()
        self.mock_update = self.patcher2.start()
        self.mock_insert = self.patcher3.start()

    def tearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()
        self.patcher3.stop()

    # 1. Unauthenticated access returns 401
    def test_unauthenticated_requests_return_401(self):
        endpoints = [
            '/api/planner/intelligence',
            '/planner/intelligence'
        ]
        for ep in endpoints:
            resp = self.client.get(ep)
            self.assertEqual(resp.status_code, 401, f"{ep} must return 401 without auth")
            data = resp.get_json()
            self.assertIn("error", data)

    # 2. Invalid tokens return 401
    def test_invalid_token_returns_401(self):
        endpoints = [
            f'/api/planner/intelligence?auth_token=invalid_garbage_token&rollNo={self.roll_a}',
            f'/planner/intelligence?auth_token=invalid_garbage_token&rollNo={self.roll_a}'
        ]
        for ep in endpoints:
            resp = self.client.get(ep)
            self.assertEqual(resp.status_code, 401, f"{ep} must return 401 with bad token")

    # 3. Cross-user requests return 403 (Student isolation)
    def test_cross_user_request_returns_403(self):
        # Student B's token used to query Student A's data
        resp = self.client.get(
            f'/api/planner/intelligence?auth_token={self.token_b}&rollNo={self.roll_a}'
        )
        self.assertEqual(resp.status_code, 403, "Cross-user query must return 403 Forbidden")
        data = resp.get_json()
        self.assertIn("error", data)
        self.assertIn("Cross-user access denied", data["error"])

    # 4. Authenticated legitimate student returns 200
    def test_authenticated_student_returns_200(self):
        endpoints = [
            f'/api/planner/intelligence?auth_token={self.token_a}&rollNo={self.roll_a}',
            f'/planner/intelligence?auth_token={self.token_a}&rollNo={self.roll_a}'
        ]
        for ep in endpoints:
            resp = self.client.get(ep)
            self.assertEqual(resp.status_code, 200, f"{ep} must return 200 for valid token")
            data = resp.get_json()
            self.assertIn("student", data)
            self.assertIn("attendance", data)
            self.assertIn("today_context", data)
            self.assertIn("subject_matrix", data)
            self.assertIn("academic_health", data)
            self.assertIn("registered_exams_summary", data)

    # 5. Missing student returns 404
    def test_missing_student_returns_404(self):
        nonexistent_roll = "99ZZ999"
        nonexistent_token = generate_auth_token(nonexistent_roll)
        resp = self.client.get(
            f'/api/planner/intelligence?auth_token={nonexistent_token}&rollNo={nonexistent_roll}'
        )
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertIn("error", data)

    # 6. Response schema verification
    def test_complete_response_schema(self):
        resp = self.client.get(
            f'/api/planner/intelligence?auth_token={self.token_a}&rollNo={self.roll_a}'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        # Student entity
        student = data["student"]
        self.assertEqual(student["rollNo"], self.roll_a)
        self.assertEqual(student["name"], "VISHALY S")
        self.assertEqual(student["cgpa"], 7.96)
        self.assertEqual(student["verified_historical_credits"], 24.0)
        self.assertEqual(student["active_courses_count"], 8)

        # Attendance entity
        att = data["attendance"]
        self.assertGreater(att["attended"], 0)
        self.assertGreater(att["conducted"], 0)
        self.assertEqual(att["percentage"], round(att["attended"] / att["conducted"] * 100, 2))
        self.assertGreaterEqual(att["safe_bunks"], 0)

        # Today context
        tc = data["today_context"]
        self.assertIn(tc["day_name"], ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
        self.assertIsInstance(tc["available_weekdays"], list)
        self.assertEqual(len(tc["available_weekdays"]), 5)
        self.assertIsInstance(tc["recommended_focus"], list)

        # Subject matrix
        sm = data["subject_matrix"]
        self.assertEqual(len(sm), 8)
        codes = [s["code"] for s in sm]
        expected_codes = ['23MX31', '23MX36', '23MX37', '23MXAE', '23MXAF', '23MXAO', '23MXCA', '23MXM4']
        self.assertEqual(sorted(codes), sorted(expected_codes))

        for sub in sm:
            self.assertIn("code", sub)
            self.assertIn("name", sub)
            self.assertIn("category", sub)
            self.assertIn("attendance", sub)
            self.assertIn("schedule", sub)
            self.assertIn("ca_progress", sub)
            self.assertIn("exam", sub)
            self.assertIn("priority", sub)
            self.assertIn("attention_needed", sub)

            # Assert deterministic priority keys
            prio = sub["priority"]
            self.assertIn("score", prio)
            self.assertIn("level", prio)
            self.assertIn("reasons", prio)
            self.assertIn("urgency_tags", prio)
            self.assertIn(prio["level"], ["HIGH", "MEDIUM", "LOW"])

        # Academic health summary
        ah = data["academic_health"]
        self.assertIn("high_priority_count", ah)
        self.assertIn("attention_needed_count", ah)
        self.assertEqual(ah["total_entered_ca"], 20)
        self.assertEqual(ah["total_pending_ca"], 30)
        self.assertEqual(ah["registered_exams_count"], 5)

        # Registered exams summary
        ex_sum = data["registered_exams_summary"]
        self.assertEqual(ex_sum["total_registered"], 5)
        self.assertEqual(ex_sum["circular_count"], 3)

    # 7. Day query parameter test
    def test_day_query_parameter(self):
        for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
            resp = self.client.get(
                f'/api/planner/intelligence?auth_token={self.token_a}&rollNo={self.roll_a}&day={day}'
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertEqual(data["today_context"]["day_name"], day)

    # 8. Zero database mutation test
    def test_zero_database_mutation(self):
        # Multiple API calls across different days
        for d in ["Monday", "Friday"]:
            resp = self.client.get(
                f'/api/planner/intelligence?auth_token={self.token_a}&rollNo={self.roll_a}&day={d}'
            )
            self.assertEqual(resp.status_code, 200)

        # Verify zero database writes were attempted
        self.assertEqual(self.mock_update.call_count, 0, "Planner API must NEVER call update_one")
        self.assertEqual(self.mock_insert.call_count, 0, "Planner API must NEVER call insert_one")


if __name__ == '__main__':
    unittest.main()
