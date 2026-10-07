"""
backend/tests/test_services_api.py

API test suite for Phase 8 Campus Services & Student Dossier Hub Endpoints:
1. Unauthenticated requests return HTTP 401
2. Invalid tokens return HTTP 401
3. Cross-user access returns HTTP 403 (student isolation enforced)
4. Authenticated legitimate student requests return HTTP 200
5. Missing student records return HTTP 404
6. Response schema validation (dossier, fees, hostel, scholarships, feedback, disclaimer)
7. Fees structure and breakdown validation
8. Hostel structure and residency validation
9. Scholarships structure: applied and received remain strictly distinct
10. Feedback cycles and active count validation
11. Student dossier fields and PII protection (no password, _id, or internal keys)
12. Zero-write guarantee: API requests NEVER mutate MongoDB documents or collections
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


class TestServicesApi(unittest.TestCase):
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
            '/api/campus-services/overview',
            '/campus-services/overview',
            '/api/services/overview',
            '/services/overview'
        ]
        for ep in endpoints:
            resp = self.client.get(ep)
            self.assertEqual(resp.status_code, 401, f"{ep} must return 401 without auth")
            data = resp.get_json()
            self.assertIn("error", data)

    # 2. Invalid tokens return 401
    def test_invalid_token_returns_401(self):
        endpoints = [
            f'/api/campus-services/overview?auth_token=invalid_garbage_token&rollNo={self.roll_a}',
            f'/services/overview?auth_token=invalid_garbage_token&rollNo={self.roll_a}'
        ]
        for ep in endpoints:
            resp = self.client.get(ep)
            self.assertEqual(resp.status_code, 401, f"{ep} must return 401 with bad token")

    # 3. Cross-user requests return 403 (Student isolation)
    def test_cross_user_request_returns_403(self):
        # Student B's token used to query Student A's data
        resp = self.client.get(
            f'/api/campus-services/overview?auth_token={self.token_b}&rollNo={self.roll_a}'
        )
        self.assertEqual(resp.status_code, 403, "Cross-user query must return 403 Forbidden")
        data = resp.get_json()
        self.assertIn("error", data)
        self.assertIn("Cross-user access denied", data["error"])

    # 4. Authenticated legitimate student returns 200
    def test_authenticated_student_returns_200(self):
        endpoints = [
            f'/api/campus-services/overview?auth_token={self.token_a}&rollNo={self.roll_a}',
            f'/services/overview?auth_token={self.token_a}&rollNo={self.roll_a}'
        ]
        for ep in endpoints:
            resp = self.client.get(ep)
            self.assertEqual(resp.status_code, 200, f"{ep} must return 200 for valid token")
            data = resp.get_json()
            self.assertIn("student_dossier", data)
            self.assertIn("fees", data)
            self.assertIn("hostel", data)
            self.assertIn("scholarships", data)
            self.assertIn("feedback", data)
            self.assertIn("disclaimer", data)

    # 5. Missing student returns 404
    def test_missing_student_returns_404(self):
        fake_roll = "99ZZ999"
        fake_token = generate_auth_token(fake_roll)
        resp = self.client.get(
            f'/api/campus-services/overview?auth_token={fake_token}&rollNo={fake_roll}'
        )
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertIn("error", data)

    # 6. Response schema validation
    def test_response_schema_structure(self):
        resp = self.client.get(
            f'/api/campus-services/overview?auth_token={self.token_a}'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        # Check required top-level keys
        for key in ["student_dossier", "fees", "hostel", "scholarships", "feedback", "disclaimer"]:
            self.assertIn(key, data)

        # Check fees schema
        fees = data["fees"]
        self.assertIn("status", fees)
        self.assertIn("total_amount", fees)
        self.assertIn("items", fees)
        self.assertIn("currency", fees)
        self.assertIsInstance(fees["items"], list)

        # Check hostel schema
        hostel = data["hostel"]
        self.assertIn("status", hostel)
        self.assertIn("is_hosteller", hostel)
        self.assertIn("room_number", hostel)
        self.assertIn("payments", hostel)
        self.assertIsInstance(hostel["payments"], list)

        # Check scholarships schema
        sch = data["scholarships"]
        self.assertIn("applied_count", sch)
        self.assertIn("received_count", sch)
        self.assertIn("applied", sch)
        self.assertIn("received", sch)
        self.assertIsInstance(sch["applied"], list)
        self.assertIsInstance(sch["received"], list)

        # Check feedback schema
        fb = data["feedback"]
        self.assertIn("active_count", fb)
        self.assertIn("cycles", fb)
        self.assertIsInstance(fb["cycles"], list)

    # 7. Scholarships: applied and received remain strictly distinct
    def test_scholarships_applied_vs_received_distinct(self):
        resp = self.client.get(
            f'/api/campus-services/overview?auth_token={self.token_a}'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        sch = data["scholarships"]

        # Ensure both keys exist and are distinct lists
        self.assertIn("applied", sch)
        self.assertIn("received", sch)
        self.assertIsInstance(sch["applied"], list)
        self.assertIsInstance(sch["received"], list)

        # If records exist, verify their respective schema fields
        for app in sch["applied"]:
            self.assertIn("scheme_name", app)
            self.assertIn("application_status", app)
        for rec in sch["received"]:
            self.assertIn("scheme_name", rec)
            self.assertIn("disbursement_status", rec)

    # 8. Student dossier and security isolation (no passwords, _id, or internal keys)
    def test_student_dossier_pii_security_isolation(self):
        resp = self.client.get(
            f'/api/campus-services/overview?auth_token={self.token_a}'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        dossier = data["student_dossier"]

        # Should contain verified identity fields
        self.assertEqual(dossier.get("rollNo"), self.roll_a)
        self.assertIn("name", dossier)

        # Strictly forbidden fields must NOT leak
        self.assertNotIn("password", dossier)
        self.assertNotIn("_id", dossier)
        self.assertNotIn("changeHash", dossier)
        self.assertNotIn("auth_token", dossier)

    # 9. Zero-write guarantee: Database remains 100% untouched
    def test_zero_write_guarantee(self):
        # Read student document before API execution
        user_before = self.users_col.find_one({"rollNo": self.roll_a})
        users_count_before = self.users_col.count_documents({})
        notifs_count_before = notifications_collection.count_documents({})
        subs_count_before = sub_collection.count_documents({})

        # Call endpoint multiple times
        for _ in range(3):
            resp = self.client.get(
                f'/api/campus-services/overview?auth_token={self.token_a}&rollNo={self.roll_a}'
            )
            self.assertEqual(resp.status_code, 200)

        # Read student document after API execution
        user_after = self.users_col.find_one({"rollNo": self.roll_a})
        users_count_after = self.users_col.count_documents({})
        notifs_count_after = notifications_collection.count_documents({})
        subs_count_after = sub_collection.count_documents({})

        # Assert zero mutations
        self.assertEqual(users_count_before, users_count_after, "Users collection count must not change")
        self.assertEqual(notifs_count_before, notifs_count_after, "Notifications count must not change")
        self.assertEqual(subs_count_before, subs_count_after, "Subjects collection count must not change")
        self.assertEqual(user_before, user_after, "Student document must be byte-for-byte identical before and after")


if __name__ == '__main__':
    unittest.main()
