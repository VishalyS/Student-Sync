"""
backend/tests/test_academic_api.py

Test Suite: Academic Marks & CGPA Simulator API Endpoints (Phase 5)
Validates:
1. Unauthorized request returns 401
2. Cross-user access attempt returns 403 (User isolation enforced)
3. Authenticated student access returns 200 with complete academic summary
4. CA marks breakdown returned with correct categories and component statuses
5. Historical results returned with verified credits and matching CGPA
6. What-If CGPA simulator returns accurate projected CGPA
7. Multiple courses simulation accuracy
8. In-memory simulation does NOT mutate MongoDB (zero-write guarantee)
9. Negative credits / invalid inputs validation returns 400
10. Reset/empty simulation defaults to base CGPA
"""

import os
import sys
import unittest

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from database import user_collection
from pyserver import app, generate_auth_token


class TestAcademicApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.client = cls.app.test_client()
        cls.users_col = user_collection

        # Existing production students for read-only test assertions
        cls.roll_a = "25MX232"
        cls.roll_b = "25MX227"

        # Generate cryptographic bearer tokens
        cls.token_a = generate_auth_token(cls.roll_a)
        cls.token_b = generate_auth_token(cls.roll_b)

        # Verify students exist in MongoDB before tests
        user_a = cls.users_col.find_one({"rollNo": cls.roll_a})
        assert user_a is not None, f"Student {cls.roll_a} must exist in MongoDB"
        user_b = cls.users_col.find_one({"rollNo": cls.roll_b})
        assert user_b is not None, f"Student {cls.roll_b} must exist in MongoDB"

        # Capture snapshot of user_a for zero-mutation verification
        cls.initial_cgpa = user_a.get("cgpa")
        cls.initial_parsed_marks = user_a.get("studzone1", {}).get("parsed_marks")
        cls.initial_parsed_results = user_a.get("studzone2", {}).get("parsed_results")

    # 1. Unauthorized Access Returns 401
    def test_unauthorized_access_returns_401(self):
        resp_get = self.client.get('/api/academic/marks-summary')
        self.assertEqual(resp_get.status_code, 401)
        self.assertIn("Authentication required", resp_get.get_json().get("error", ""))

        resp_post = self.client.post('/api/academic/cgpa-simulate', json={"simulated_courses": []})
        self.assertEqual(resp_post.status_code, 401)

    # 2. Cross-User Access Attempt Returns 403 Forbidden
    def test_cross_user_access_returns_403(self):
        # Student A token attempting to query Student B rollNo
        headers = {'Authorization': f'Bearer {self.token_a}'}
        resp = self.client.get(f'/api/academic/marks-summary?rollNo={self.roll_b}', headers=headers)
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Cross-user access denied", resp.get_json().get("error", ""))

        # Cross-user attempt via POST body
        resp_post = self.client.post(
            '/api/academic/cgpa-simulate',
            headers=headers,
            json={"rollNo": self.roll_b, "simulated_courses": []}
        )
        self.assertEqual(resp_post.status_code, 403)

    # 3. Authenticated Access Returns 200 with Academic Summary
    def test_authenticated_summary_success(self):
        headers = {'Authorization': f'Bearer {self.token_a}'}
        resp = self.client.get('/api/academic/marks-summary', headers=headers)
        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertEqual(data.get("rollNo"), self.roll_a)
        self.assertEqual(data.get("stored_cgpa"), 7.96)
        self.assertEqual(data.get("base_credits"), 24.0)
        self.assertIn("ca_marks", data)
        self.assertIn("results", data)
        self.assertIn("grade_point_map", data)

    # 4. CA Marks Breakdown Details
    def test_ca_marks_breakdown_categories(self):
        headers = {'Authorization': f'Bearer {self.token_a}'}
        resp = self.client.get('/api/academic/marks-summary', headers=headers)
        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        ca = data["ca_marks"]
        self.assertEqual(ca["total_courses"], 8)
        self.assertGreater(ca["entered_evaluations"], 0)
        self.assertGreater(ca["pending_evaluations"], 0)

        # Check theory course category
        theory_courses = [c for c in ca["courses"] if c["category"] == "Theory"]
        self.assertGreater(len(theory_courses), 0)
        for tc in theory_courses:
            self.assertEqual(tc["converted_total_max"], 40.0)

        # Check lab course category
        lab_courses = [c for c in ca["courses"] if c["category"] == "Laboratory"]
        self.assertEqual(len(lab_courses), 1)
        self.assertEqual(lab_courses[0]["converted_total_max"], 60.0)

    # 5. Historical Results Analytics & CGPA Proof
    def test_results_analytics_cgpa_match(self):
        headers = {'Authorization': f'Bearer {self.token_a}'}
        resp = self.client.get('/api/academic/marks-summary', headers=headers)
        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        results = data["results"]
        self.assertEqual(results["total_credits"], 24.0)
        self.assertEqual(results["total_grade_points"], 191.0)
        self.assertEqual(results["calculated_cgpa"], 7.96)
        self.assertTrue(results["cgpa_verified"])
        self.assertTrue(results["all_cleared"])
        self.assertEqual(results["arrears_count"], 0)

    # 6. What-If CGPA Simulator Single Course
    def test_cgpa_simulator_single_course(self):
        headers = {'Authorization': f'Bearer {self.token_a}'}
        payload = {
            "simulated_courses": [
                {"course_name": "Cloud Architecture", "credits": 4.0, "grade": "O"}
            ]
        }
        resp = self.client.post('/api/academic/cgpa-simulate', headers=headers, json=payload)
        self.assertEqual(resp.status_code, 200)

        res = resp.get_json()
        self.assertEqual(res["base_credits"], 24.0)
        self.assertEqual(res["base_cgpa"], 7.96)
        self.assertEqual(res["simulated_credits"], 4.0)
        self.assertEqual(res["total_credits"], 28.0)
        # (24 * 7.96 + 4 * 10) / 28 = 231.04 / 28 = 8.2514 -> 8.25
        self.assertEqual(res["projected_cgpa"], 8.25)
        self.assertEqual(res["cgpa_delta"], 0.29)
        self.assertIn("in-memory mathematical what-if model", res["disclaimer"])

    # 7. What-If CGPA Simulator Multiple Courses
    def test_cgpa_simulator_multiple_courses(self):
        headers = {'Authorization': f'Bearer {self.token_a}'}
        payload = {
            "simulated_courses": [
                {"course_name": "Course 1", "credits": 4.0, "grade": "A+"},  # 4 * 9 = 36
                {"course_name": "Course 2", "credits": 3.0, "grade": "A"},   # 3 * 8 = 24
                {"course_name": "Course 3", "credits": 2.0, "grade": "B+"}   # 2 * 7 = 14
            ]
        }
        resp = self.client.post('/api/academic/cgpa-simulate', headers=headers, json=payload)
        self.assertEqual(resp.status_code, 200)

        res = resp.get_json()
        self.assertEqual(res["simulated_credits"], 9.0)
        self.assertEqual(res["total_credits"], 33.0)
        # Total points = 191.04 + 74 = 265.04 / 33 = 8.0315 -> 8.03
        self.assertEqual(res["projected_cgpa"], 8.03)

    # 8. Zero-Mutation Verification (100% In-Memory Guarantee)
    def test_simulation_does_not_mutate_mongodb(self):
        headers = {'Authorization': f'Bearer {self.token_a}'}
        # Run multiple aggressive simulations
        for grade in ["O", "A", "C", "RA"]:
            self.client.post(
                '/api/academic/cgpa-simulate',
                headers=headers,
                json={"simulated_courses": [{"credits": 5.0, "grade": grade}]}
            )

        # Check database directly
        user_after = self.users_col.find_one({"rollNo": self.roll_a})
        self.assertEqual(user_after.get("cgpa"), self.initial_cgpa)
        self.assertEqual(user_after.get("studzone1", {}).get("parsed_marks"), self.initial_parsed_marks)
        self.assertEqual(user_after.get("studzone2", {}).get("parsed_results"), self.initial_parsed_results)

    # 9. Validation of Invalid Inputs
    def test_simulation_input_validation(self):
        headers = {'Authorization': f'Bearer {self.token_a}'}
        # Non-JSON
        resp_bad = self.client.post('/api/academic/cgpa-simulate', headers=headers, data="not a json")
        self.assertEqual(resp_bad.status_code, 400)

        # Negative base credits
        resp_neg = self.client.post(
            '/api/academic/cgpa-simulate',
            headers=headers,
            json={"base_credits": -10, "simulated_courses": []}
        )
        self.assertEqual(resp_neg.status_code, 400)

    # 10. Empty Simulation Defaults to Base CGPA
    def test_empty_simulation_returns_base(self):
        headers = {'Authorization': f'Bearer {self.token_a}'}
        resp = self.client.post('/api/academic/cgpa-simulate', headers=headers, json={"simulated_courses": []})
        self.assertEqual(resp.status_code, 200)

        res = resp.get_json()
        self.assertEqual(res["simulated_credits"], 0.0)
        self.assertEqual(res["total_credits"], 24.0)
        self.assertEqual(res["projected_cgpa"], 7.96)
        self.assertEqual(res["cgpa_delta"], 0.0)


if __name__ == '__main__':
    unittest.main()
