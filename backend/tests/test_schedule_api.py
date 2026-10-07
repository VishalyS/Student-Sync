"""
backend/tests/test_schedule_api.py

API test suite for Phase 6 Timetable, Exam & Day-Bunk Simulator Endpoints:
1. Unauthenticated requests return HTTP 401
2. Invalid tokens return HTTP 401
3. Cross-user access returns HTTP 403 (student isolation enforced)
4. Authenticated legitimate student requests return HTTP 200
5. Malformed day-bunk simulation requests return HTTP 400
6. Valid day-bunk simulation returns accurate projected metrics
7. Unified courses summary returns combined attendance, marks, schedule, and exam data
8. Zero-write guarantee: API requests NEVER write to MongoDB
"""

import os
import sys
import unittest

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from database import user_collection
from pyserver import app, generate_auth_token


class TestScheduleApi(unittest.TestCase):
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
        cls.initial_att = user_a.get("studzone1", {}).get("parsed_attendance")
        cls.initial_sched = user_a.get("studzone1", {}).get("class_schedule")
        cls.initial_cgpa = user_a.get("cgpa")

    # 1. Unauthenticated access returns 401
    def test_unauthenticated_requests_return_401(self):
        endpoints = [
            ('/api/schedule/weekly', 'GET'),
            ('/api/schedule/exams', 'GET'),
            ('/api/courses/unified-summary', 'GET'),
            ('/api/schedule/day-bunk-simulate', 'POST')
        ]
        for ep, method in endpoints:
            if method == 'GET':
                resp = self.client.get(ep)
            else:
                resp = self.client.post(ep, json={"day": "Friday"})
            self.assertEqual(resp.status_code, 401, f"{ep} must return 401 without auth")
            self.assertIn("Authentication required", resp.get_json().get("error", ""))

    # 2. Invalid token returns 401
    def test_invalid_token_returns_401(self):
        headers = {'Authorization': 'Bearer INVALID_MALFORMED_TOKEN'}
        resp = self.client.get('/api/schedule/weekly', headers=headers)
        self.assertEqual(resp.status_code, 401)

    # 3. Cross-user access returns 403 Forbidden
    def test_cross_user_access_returns_403(self):
        # Student A token attempting to query Student B's data
        headers = {'Authorization': f'Bearer {self.token_a}'}
        resp = self.client.get(f'/api/schedule/weekly?rollNo={self.roll_b}', headers=headers)
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Cross-user access denied", resp.get_json().get("error", ""))

        resp_exam = self.client.get(f'/api/schedule/exams?rollNo={self.roll_b}', headers=headers)
        self.assertEqual(resp_exam.status_code, 403)

        resp_courses = self.client.get(f'/api/courses/unified-summary?rollNo={self.roll_b}', headers=headers)
        self.assertEqual(resp_courses.status_code, 403)

    # 4. Authenticated legitimate request returns 200 for weekly schedule
    def test_weekly_schedule_success(self):
        headers = {'Authorization': f'Bearer {self.token_a}'}
        resp = self.client.get('/api/schedule/weekly', headers=headers)
        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertEqual(data.get("rollNo"), self.roll_a)
        self.assertIn("days", data)
        self.assertEqual(len(data["days"]), 5)  # Monday through Friday
        self.assertIn("timing_slots", data)
        self.assertEqual(data["total_periods"], 6)

        # Check Monday schedule structure
        mon = data["days"][0]
        self.assertEqual(mon["day"], "Monday")
        self.assertEqual(len(mon["periods"]), 6)
        self.assertIn("code", mon["periods"][0])
        self.assertIn("time", mon["periods"][0])

    # 5. Authenticated legitimate request returns 200 for exams & circulars
    def test_exams_schedule_success(self):
        headers = {'Authorization': f'Bearer {self.token_a}'}
        resp = self.client.get('/api/schedule/exams', headers=headers)
        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertEqual(data.get("rollNo"), self.roll_a)
        self.assertIn("exams", data)
        self.assertGreater(data["total_exams"], 0)
        self.assertIn("circulars", data)
        self.assertGreater(len(data["circulars"]), 0)

        # Verify exact portal status preserved without fabricated dates
        for ex in data["exams"]:
            self.assertIn("course_code", ex)
            self.assertIn("exam_date", ex)
            self.assertIn("status", ex)
            self.assertIn(ex["status"], ["PENDING", "SCHEDULED"])

    # 6. Malformed day-bunk simulation returns 400
    def test_day_bunk_simulate_validation_errors(self):
        headers = {'Authorization': f'Bearer {self.token_a}'}

        # Missing day
        resp = self.client.post('/api/schedule/day-bunk-simulate', headers=headers, json={})
        self.assertEqual(resp.status_code, 400)

        # Invalid target
        resp = self.client.post('/api/schedule/day-bunk-simulate', headers=headers, json={"day": "Friday", "target": 150.0})
        self.assertEqual(resp.status_code, 400)

        # Invalid day name
        resp = self.client.post('/api/schedule/day-bunk-simulate', headers=headers, json={"day": "Funday"})
        self.assertEqual(resp.status_code, 400)

    # 7. Valid day-bunk simulation returns 200 with accurate metrics
    def test_day_bunk_simulate_success(self):
        headers = {'Authorization': f'Bearer {self.token_a}'}
        payload = {
            "day": "Friday",
            "periods": [1, 3],
            "target": 75.0
        }
        resp = self.client.post('/api/schedule/day-bunk-simulate', headers=headers, json=payload)
        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertEqual(data["day"], "Friday")
        self.assertEqual(data["target"], 75.0)
        self.assertIn("overall", data)
        self.assertIn("affected_subjects", data)

        # Overall conducted must increase by missed classes
        orig_cond = data["overall"]["original"]["conducted"]
        sim_cond = data["overall"]["simulated"]["conducted"]
        missed = data["total_classes_missed"]
        self.assertEqual(sim_cond, orig_cond + missed)

        # Percentage change must be non-positive (attendance dropped or neutral)
        self.assertLessEqual(data["overall"]["simulated"]["percentage_change"], 0.0)

    # 8. Unified courses summary returns 200
    def test_courses_unified_summary_success(self):
        headers = {'Authorization': f'Bearer {self.token_a}'}
        resp = self.client.get('/api/courses/unified-summary', headers=headers)
        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertEqual(data.get("rollNo"), self.roll_a)
        self.assertIn("courses", data)
        self.assertEqual(data["total_courses"], 8)

        # Check fields on first course
        c0 = data["courses"][0]
        self.assertIn("code", c0)
        self.assertIn("name", c0)
        self.assertIn("attendance", c0)
        self.assertIn("schedule", c0)
        self.assertIn("exam", c0)
        self.assertIn("risk_status", c0)

    # 9. Zero-write guarantee: Simulation calls do NOT mutate MongoDB
    def test_simulation_does_not_mutate_mongodb(self):
        headers = {'Authorization': f'Bearer {self.token_a}'}
        # Run multiple simulations
        for d in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
            self.client.post('/api/schedule/day-bunk-simulate', headers=headers, json={"day": d, "target": 75.0})

        # Query user in MongoDB fresh
        user_fresh = self.users_col.find_one({"rollNo": self.roll_a})
        self.assertEqual(user_fresh.get("cgpa"), self.initial_cgpa)
        self.assertEqual(user_fresh.get("studzone1", {}).get("parsed_attendance"), self.initial_att)
        self.assertEqual(user_fresh.get("studzone1", {}).get("class_schedule"), self.initial_sched)


if __name__ == "__main__":
    unittest.main()
