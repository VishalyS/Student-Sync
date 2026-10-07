"""
Test Suite: Attendance API Endpoints & Authorization Security (Phase 2)
Validates:
1. Valid summary endpoint (/api/attendance/summary)
2. Correct overall attendance aggregation
3. Correct subject calculations
4. Correct today's lecture schedule parsing
5. Valid interactive simulation (/api/attendance/simulate)
6. Simulation does NOT mutate MongoDB (100% in-memory guarantee)
7. Unknown subject returns 404
8. Invalid payload returns 400
9. Negative values return 400
10. Unauthorized request returns 401
11. Cross-user access attempt returns 403 (User isolation enforced)
"""

import os
import sys
import unittest
import copy

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


class TestAttendanceApi(unittest.TestCase):
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

    # -------------------------------------------------------------------------
    # 1. Valid Summary & Overall Aggregation
    # -------------------------------------------------------------------------
    def test_01_valid_summary_and_overall_aggregation(self):
        resp = self.client.get(
            '/api/attendance/summary',
            headers={'Authorization': f'Bearer {self.token_a}'}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        # Required root fields
        self.assertEqual(data.get("rollNo"), self.roll_a)
        self.assertIn("name", data)
        self.assertEqual(data.get("total_attended"), 258)
        self.assertEqual(data.get("total_conducted"), 310)
        self.assertEqual(data.get("overall_percentage"), 83.23)
        self.assertEqual(data.get("overall_status"), "SAFE")
        self.assertEqual(data.get("overall_safe_bunks"), 34)
        self.assertEqual(data.get("overall_required_classes"), 0)
        self.assertEqual(data.get("target"), 75.0)

        # Subjects and schedule present
        self.assertIsInstance(data.get("subjects"), list)
        self.assertGreater(len(data["subjects"]), 0)
        self.assertIn("today_schedule", data)

    # -------------------------------------------------------------------------
    # 2. Correct Subject Calculations
    # -------------------------------------------------------------------------
    def test_02_correct_subject_calculations(self):
        resp = self.client.get(
            '/api/attendance/summary',
            headers={'Authorization': f'Bearer {self.token_a}'}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        subjects = {s["code"]: s for s in data["subjects"]}

        # 23MX31 (Cloud Computing: 28 / 37)
        self.assertIn("23MX31", subjects)
        cc = subjects["23MX31"]
        self.assertEqual(cc["attended"], 28)
        self.assertEqual(cc["conducted"], 37)
        self.assertEqual(cc["percentage"], 75.68)
        self.assertEqual(cc["safe_bunks"], 0)
        self.assertEqual(cc["required_classes"], 0)
        self.assertEqual(cc["status"], "SAFE")

        # 23MX36 (Cloud Lab: 48 / 52)
        self.assertIn("23MX36", subjects)
        lab = subjects["23MX36"]
        self.assertEqual(lab["attended"], 48)
        self.assertEqual(lab["conducted"], 52)
        self.assertEqual(lab["percentage"], 92.31)
        self.assertEqual(lab["safe_bunks"], 12)
        self.assertEqual(lab["required_classes"], 0)
        self.assertEqual(lab["status"], "SAFE")

        # 23MXAF (Data Mining: 27 / 36)
        self.assertIn("23MXAF", subjects)
        dm = subjects["23MXAF"]
        self.assertEqual(dm["attended"], 27)
        self.assertEqual(dm["conducted"], 36)
        self.assertEqual(dm["percentage"], 75.0)
        self.assertEqual(dm["safe_bunks"], 0)
        self.assertEqual(dm["required_classes"], 0)
        self.assertEqual(dm["status"], "SAFE")

    # -------------------------------------------------------------------------
    # 3. Correct Today's Schedule Parsing
    # -------------------------------------------------------------------------
    def test_03_correct_today_schedule(self):
        # Query Monday schedule explicitly
        resp = self.client.get(
            '/api/attendance/summary?day=Monday',
            headers={'Authorization': f'Bearer {self.token_a}'}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        sched = data.get("today_schedule", {})
        self.assertEqual(sched.get("day"), "Monday")
        classes = sched.get("classes", [])
        self.assertGreaterEqual(len(classes), 5)

        # Period 1 Monday: 23MXAF (Data Mining)
        p1 = classes[0]
        self.assertEqual(p1["period"], 1)
        self.assertEqual(p1["time"], "8.30 - 9.20")
        self.assertEqual(p1["code"], "23MXAF")
        self.assertIn("DATA MINING", p1["name"])

        # Period 3 Monday: 23MX31 (Cloud Computing)
        p3 = classes[2]
        self.assertEqual(p3["period"], 3)
        self.assertEqual(p3["code"], "23MX31")

    # -------------------------------------------------------------------------
    # 4. Valid Simulation
    # -------------------------------------------------------------------------
    def test_04_valid_simulation(self):
        # Base: 23MX31 has 28 attended, 37 conducted (75.68%)
        # User simulates: attend 2 classes, bunk 1 class
        # Projected: attended = 30, conducted = 40 -> 30/40 = exactly 75.0%
        sim_payload = {
            "subject_code": "23MX31",
            "additional_attended": 2,
            "additional_bunked": 1,
            "target": 75.0
        }
        resp = self.client.post(
            '/api/attendance/simulate',
            json=sim_payload,
            headers={'Authorization': f'Bearer {self.token_a}'}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        self.assertEqual(data.get("subject_code"), "23MX31")
        self.assertEqual(data.get("simulated_attended"), 30)
        self.assertEqual(data.get("simulated_conducted"), 40)
        self.assertEqual(data.get("simulated_percentage"), 75.0)
        self.assertEqual(data.get("simulated_status"), "SAFE")
        self.assertEqual(data.get("simulated_safe_bunks"), 0)
        self.assertEqual(data.get("simulated_required_classes"), 0)

        # Original remains 28/37
        self.assertEqual(data["original"]["attended"], 28)
        self.assertEqual(data["original"]["conducted"], 37)
        self.assertEqual(data["original"]["percentage"], 75.68)

    # -------------------------------------------------------------------------
    # 5. Simulation Does NOT Mutate MongoDB (Pure In-Memory Guarantee)
    # -------------------------------------------------------------------------
    def test_05_simulation_does_not_modify_mongodb(self):
        # Capture raw document before simulation
        user_before = self.users_col.find_one({"rollNo": self.roll_a})
        att_before = copy.deepcopy(user_before["studzone1"]["parsed_attendance"])

        # Run several simulations with large values
        self.client.post(
            '/api/attendance/simulate',
            json={"subject_code": "23MX31", "additional_attended": 50, "additional_bunked": 50},
            headers={'Authorization': f'Bearer {self.token_a}'}
        )

        # Inspect raw document in MongoDB immediately after simulation
        user_after = self.users_col.find_one({"rollNo": self.roll_a})
        att_after = user_after["studzone1"]["parsed_attendance"]

        # Strictly assert zero mutations
        self.assertEqual(att_before, att_after, "MongoDB attendance must remain 100% UNTOUCHED by simulation")

    # -------------------------------------------------------------------------
    # 6. Unknown Subject Returns 404
    # -------------------------------------------------------------------------
    def test_06_unknown_subject_returns_404(self):
        resp = self.client.post(
            '/api/attendance/simulate',
            json={"subject_code": "UNKNOWN_COURSE_999", "additional_attended": 1, "additional_bunked": 0},
            headers={'Authorization': f'Bearer {self.token_a}'}
        )
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertIn("not found", data.get("error", "").lower())

    # -------------------------------------------------------------------------
    # 7. Invalid Payload Returns 400
    # -------------------------------------------------------------------------
    def test_07_invalid_payload_returns_400(self):
        # Missing subject_code
        resp1 = self.client.post(
            '/api/attendance/simulate',
            json={"additional_attended": 1},
            headers={'Authorization': f'Bearer {self.token_a}'}
        )
        self.assertEqual(resp1.status_code, 400)

        # Non-JSON content
        resp2 = self.client.post(
            '/api/attendance/simulate',
            data="not a json",
            headers={'Authorization': f'Bearer {self.token_a}', 'Content-Type': 'text/plain'}
        )
        self.assertEqual(resp2.status_code, 400)

        # Non-numerical values
        resp3 = self.client.post(
            '/api/attendance/simulate',
            json={"subject_code": "23MX31", "additional_attended": "invalid_string"},
            headers={'Authorization': f'Bearer {self.token_a}'}
        )
        self.assertEqual(resp3.status_code, 400)

    # -------------------------------------------------------------------------
    # 8. Negative Values Return 400
    # -------------------------------------------------------------------------
    def test_08_negative_values_returns_400(self):
        # Negative additional_attended
        resp1 = self.client.post(
            '/api/attendance/simulate',
            json={"subject_code": "23MX31", "additional_attended": -3, "additional_bunked": 0},
            headers={'Authorization': f'Bearer {self.token_a}'}
        )
        self.assertEqual(resp1.status_code, 400)
        self.assertIn("negative", resp1.get_json().get("error", "").lower())

        # Negative additional_bunked
        resp2 = self.client.post(
            '/api/attendance/simulate',
            json={"subject_code": "23MX31", "additional_attended": 0, "additional_bunked": -5},
            headers={'Authorization': f'Bearer {self.token_a}'}
        )
        self.assertEqual(resp2.status_code, 400)

        # Invalid target percentage (< 1 or > 100)
        resp3 = self.client.post(
            '/api/attendance/simulate',
            json={"subject_code": "23MX31", "additional_attended": 1, "target": 150.0},
            headers={'Authorization': f'Bearer {self.token_a}'}
        )
        self.assertEqual(resp3.status_code, 400)

    # -------------------------------------------------------------------------
    # 9. Unauthorized Request Returns 401
    # -------------------------------------------------------------------------
    def test_09_unauthorized_request_returns_401(self):
        # No header
        resp1 = self.client.get('/api/attendance/summary')
        self.assertEqual(resp1.status_code, 401)

        # Invalid bearer token
        resp2 = self.client.get(
            '/api/attendance/summary',
            headers={'Authorization': 'Bearer INVALID_FORGED_TOKEN_12345'}
        )
        self.assertEqual(resp2.status_code, 401)

        # Post simulation without auth
        resp3 = self.client.post(
            '/api/attendance/simulate',
            json={"subject_code": "23MX31", "additional_attended": 1}
        )
        self.assertEqual(resp3.status_code, 401)

    # -------------------------------------------------------------------------
    # 10. Cross-User Access Attempt Returns 403 (User Isolation Enforced)
    # -------------------------------------------------------------------------
    def test_10_cross_user_access_attempt_returns_403(self):
        # Student A (token_a) attempts to query Student B (roll_b) in query params
        resp1 = self.client.get(
            f'/api/attendance/summary?rollNo={self.roll_b}',
            headers={'Authorization': f'Bearer {self.token_a}'}
        )
        self.assertEqual(resp1.status_code, 403, "Cross-user query in GET must return 403 Forbidden")
        self.assertIn("cross-user", resp1.get_json().get("error", "").lower())

        # Student A (token_a) attempts to simulate on Student B in JSON body
        resp2 = self.client.post(
            '/api/attendance/simulate',
            json={"rollNo": self.roll_b, "subject_code": "23MX31", "additional_attended": 1},
            headers={'Authorization': f'Bearer {self.token_a}'}
        )
        self.assertEqual(resp2.status_code, 403, "Cross-user query in POST must return 403 Forbidden")
        self.assertIn("cross-user", resp2.get_json().get("error", "").lower())


if __name__ == '__main__':
    unittest.main()
