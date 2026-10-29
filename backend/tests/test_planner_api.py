"""
backend/tests/test_planner_api.py

API test suite for Phase 7 Personalized Study Planner Endpoints:
1. Unauthenticated requests return HTTP 401
2. Invalid tokens return HTTP 401
3. Cross-user access returns HTTP 403 (student isolation enforced)
4. Authenticated legitimate student requests return HTTP 200
5. Missing student records return HTTP 404
6. Complete response schema validation
7. All active subjects represented in subject_matrix
8. Zero-write guarantee: API requests NEVER write to MongoDB
"""

import os
import sys
import unittest
import copy

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from database import user_collection, notifications_collection, sub_collection
from pyserver import app, generate_auth_token


class TestPlannerApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.client = cls.app.test_client()
        cls.users_col = user_collection

        cls.roll_a = "25MX232"
        cls.roll_b = "25MX227"

        cls.token_a = generate_auth_token(cls.roll_a)
        cls.token_b = generate_auth_token(cls.roll_b)

        # Baseline snapshots for zero-mutation verification
        user_a = cls.users_col.find_one({"rollNo": cls.roll_a})
        assert user_a is not None, f"Student {cls.roll_a} must exist in MongoDB"
        cls.initial_user_a = copy.deepcopy(user_a)
        cls.initial_users_count = cls.users_col.count_documents({})
        cls.initial_notifs_count = notifications_collection.count_documents({})
        cls.initial_subs_count = sub_collection.count_documents({})

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
        # 1. Capture MongoDB document before call
        user_before = self.users_col.find_one({"rollNo": self.roll_a})
        self.assertIsNotNone(user_before)

        # 2. Make multiple API calls (different days)
        for d in ["Monday", "Friday"]:
            resp = self.client.get(
                f'/api/planner/intelligence?auth_token={self.token_a}&rollNo={self.roll_a}&day={d}'
            )
            self.assertEqual(resp.status_code, 200)

        # 3. Capture MongoDB document after call
        user_after = self.users_col.find_one({"rollNo": self.roll_a})

        # 4. Assert strict byte-for-byte dictionary equality
        self.assertEqual(user_before, user_after, "MongoDB user document must not be mutated by planner API")

        # 5. Assert collection counts unchanged
        self.assertEqual(self.users_col.count_documents({}), self.initial_users_count)
        self.assertEqual(notifications_collection.count_documents({}), self.initial_notifs_count)
        self.assertEqual(sub_collection.count_documents({}), self.initial_subs_count)


if __name__ == '__main__':
    unittest.main()
