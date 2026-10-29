"""
backend/tests/test_hostel_integration.py

Comprehensive End-to-End Integration Test Suite for Student Sync - Hostel Subsystem:
1. Unauthenticated requests return HTTP 401 Unauthorized
2. Invalid authorization tokens return HTTP 401 Unauthorized
3. Cross-user access returns HTTP 403 Forbidden (strict student isolation)
4. Authenticated hosteller accessing own record returns HTTP 200 OK
5. Authenticated day scholar accessing hostel endpoints returns HTTP 403 Forbidden (backend access control)
6. Residential status endpoint returns correct status for hosteller vs day scholar
7. Missing student records return HTTP 404 Not Found
8. Sub-endpoints (/room, /mess, /fees, /leave, /overview) return correct domain structures for hosteller
9. Data contamination protection: Student A's data NEVER appears for Student B
10. Zero-write guarantee: Hostel operations NEVER mutate academic collections ('new_users', 'subjects')
11. Privacy protection: Zero credentials, tokens, or cookies exposed in API responses
"""
import os
import sys
import unittest

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from database import user_collection, sub_collection, notifications_collection
from hostel_service import hostel_service
from pyserver import app, generate_auth_token


class TestHostelIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.client = cls.app.test_client()

        # 25MX232 and 25MX231 are verified HOSTELLERs in StudZone 1 / MongoDB
        cls.roll_a = "25MX232"
        cls.roll_c = "25MX231"
        cls.token_a = generate_auth_token(cls.roll_a)
        cls.token_c = generate_auth_token(cls.roll_c)

        # 25MX227 is a verified DAY_SCHOLAR in StudZone 1 / MongoDB
        cls.roll_day_scholar = "25MX227"
        cls.token_day_scholar = generate_auth_token(cls.roll_day_scholar)

        # Backup existing documents if any to prevent corrupting real live extractions
        cls._original_doc_a = hostel_service.repository.get_by_roll_number(cls.roll_a)
        cls._original_doc_c = hostel_service.repository.get_by_roll_number(cls.roll_c)

        # Enable synthetic test mode for test runner
        cls._orig_env = os.environ.get("HOSTEL_ALLOW_SYNTHETIC")
        os.environ["HOSTEL_ALLOW_SYNTHETIC"] = "1"

        # Pre-populate synthetic records for test hostellers in isolated hostel repository
        hostel_service.populate_synthetic_record(cls.roll_a, run_id="run_test_a_001")
        hostel_service.populate_synthetic_record(cls.roll_c, run_id="run_test_c_003")

    @classmethod
    def tearDownClass(cls):
        # Restore environment
        if cls._orig_env is not None:
            os.environ["HOSTEL_ALLOW_SYNTHETIC"] = cls._orig_env
        else:
            os.environ.pop("HOSTEL_ALLOW_SYNTHETIC", None)

        # Restore real documents in MongoDB
        if hostel_service.repository.db is not None:
            col = hostel_service.repository.db[hostel_service.repository.COLLECTION_NAME]
            if cls._original_doc_a:
                col.replace_one({"rollNo": cls.roll_a}, cls._original_doc_a, upsert=True)
            else:
                col.delete_one({"rollNo": cls.roll_a})

            if cls._original_doc_c:
                col.replace_one({"rollNo": cls.roll_c}, cls._original_doc_c, upsert=True)
            else:
                col.delete_one({"rollNo": cls.roll_c})

    # 1. Unauthenticated requests return 401
    def test_unauthenticated_request_returns_401(self):
        endpoints = [
            f"/api/v1/hostel/student/{self.roll_a}",
            f"/api/v1/hostel/student/{self.roll_a}/summary",
            f"/api/v1/hostel/student/{self.roll_a}/room",
            f"/api/v1/hostel/student/{self.roll_a}/mess",
            f"/api/v1/hostel/student/{self.roll_a}/fees",
            f"/api/v1/hostel/student/{self.roll_a}/leave",
            "/api/v1/hostel/overview",
            "/api/v1/hostel/status",
        ]
        for ep in endpoints:
            resp = self.client.get(ep)
            self.assertEqual(resp.status_code, 401, f"Failed for {ep}")
            data = resp.get_json()
            self.assertFalse(data.get("success", False))

    # 2. Invalid tokens return 401
    def test_invalid_token_returns_401(self):
        resp = self.client.get(
            f"/api/v1/hostel/student/{self.roll_a}?auth_token=invalid_dummy_token_123"
        )
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertFalse(data.get("success", False))

    # 3. Cross-user access returns 403 Forbidden (Student A requesting Student C)
    def test_cross_user_request_returns_403(self):
        resp = self.client.get(
            f"/api/v1/hostel/student/{self.roll_c}?auth_token={self.token_a}"
        )
        self.assertEqual(resp.status_code, 403)
        data = resp.get_json()
        self.assertIn("Forbidden", data.get("error", ""))

    # 4. Authenticated hosteller accessing own record returns 200 with complete schema
    def test_authenticated_hosteller_returns_200(self):
        resp = self.client.get(
            f"/api/v1/hostel/student/{self.roll_a}?auth_token={self.token_a}"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        self.assertTrue(data.get("success"))
        self.assertIn("data", data)
        self.assertIn("meta", data)

        payload = data["data"]
        for domain in ["profile", "room", "mess", "fees", "leave", "academicYear", "feeDue"]:
            self.assertIn(domain, payload)

        # Verify profile domain structure
        prof = payload["profile"]
        self.assertEqual(prof["roll_number"], self.roll_a)
        self.assertIn("programme", prof)
        self.assertIn("class_name", prof)

        # Verify room domain structure
        room = payload["room"]
        self.assertIn("hostel_name", room)
        self.assertIn("block_name", room)
        self.assertIn("room_number", room)

        # Verify fees domain structure
        fees = payload["fees"]
        self.assertIn("hostel_fee_balance", fees)
        self.assertIn("caution_deposit", fees)

        # Verify leave domain structure
        leave = payload["leave"]
        self.assertIn("summary", leave)
        self.assertIn("approvers", leave)
        self.assertIn("history", leave)

    # 5. Day scholar accessing hostel endpoints returns 403 Forbidden (backend access control)
    def test_day_scholar_denied_backend_access(self):
        headers = {"Authorization": f"Bearer {self.token_day_scholar}"}
        endpoints = [
            f"/api/v1/hostel/student/{self.roll_day_scholar}",
            f"/api/v1/hostel/student/{self.roll_day_scholar}/summary",
            f"/api/v1/hostel/student/{self.roll_day_scholar}/room",
            f"/api/v1/hostel/student/{self.roll_day_scholar}/mess",
            f"/api/v1/hostel/student/{self.roll_day_scholar}/fees",
            f"/api/v1/hostel/student/{self.roll_day_scholar}/leave",
            "/api/v1/hostel/overview",
        ]
        for ep in endpoints:
            resp = self.client.get(ep, headers=headers)
            self.assertEqual(resp.status_code, 403, f"Expected 403 for Day Scholar on {ep}")
            data = resp.get_json()
            self.assertFalse(data.get("success", True))
            self.assertIn("Day Scholar", data.get("error", ""))
            self.assertFalse(data.get("can_access_hostel", True))

    # 6. Residential status endpoint returns correct status
    def test_residential_status_endpoint(self):
        # Hosteller check
        resp_h = self.client.get(
            "/api/v1/hostel/status",
            headers={"Authorization": f"Bearer {self.token_a}"}
        )
        self.assertEqual(resp_h.status_code, 200)
        data_h = resp_h.get_json()
        self.assertTrue(data_h["success"])
        self.assertEqual(data_h["status"], "HOSTELLER")
        self.assertTrue(data_h["isHosteller"])
        self.assertFalse(data_h["isDayScholar"])
        self.assertTrue(data_h["canAccessHostel"])
        self.assertEqual(data_h["roomNumber"], "K519")

        # Day scholar check
        resp_d = self.client.get(
            "/api/v1/hostel/status",
            headers={"Authorization": f"Bearer {self.token_day_scholar}"}
        )
        self.assertEqual(resp_d.status_code, 200)
        data_d = resp_d.get_json()
        self.assertTrue(data_d["success"])
        self.assertEqual(data_d["status"], "DAY_SCHOLAR")
        self.assertFalse(data_d["isHosteller"])
        self.assertTrue(data_d["isDayScholar"])
        self.assertFalse(data_d["canAccessHostel"])

    # 7. Missing student records return 404
    def test_missing_student_returns_404(self):
        unknown_roll = "25UNKNOWN99"
        unknown_token = generate_auth_token(unknown_roll)
        resp = self.client.get(
            f"/api/v1/hostel/student/{unknown_roll}?auth_token={unknown_token}"
        )
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertFalse(data.get("success"))

    # 8. Sub-endpoints return domain-specific views for hosteller
    def test_sub_endpoints_domain_views(self):
        headers = {"Authorization": f"Bearer {self.token_a}"}

        # Room sub-endpoint
        room_resp = self.client.get(f"/api/v1/hostel/student/{self.roll_a}/room", headers=headers)
        self.assertEqual(room_resp.status_code, 200)
        room_data = room_resp.get_json()
        self.assertTrue(room_data["success"])
        self.assertIn("room_number", room_data["data"])

        # Mess sub-endpoint
        mess_resp = self.client.get(f"/api/v1/hostel/student/{self.roll_a}/mess", headers=headers)
        self.assertEqual(mess_resp.status_code, 200)
        mess_data = mess_resp.get_json()
        self.assertTrue(mess_data["success"])
        self.assertIn("mess_name", mess_data["data"])

        # Fees sub-endpoint
        fees_resp = self.client.get(f"/api/v1/hostel/student/{self.roll_a}/fees", headers=headers)
        self.assertEqual(fees_resp.status_code, 200)
        fees_data = fees_resp.get_json()
        self.assertTrue(fees_data["success"])
        self.assertIn("fees", fees_data["data"])

        # Leave sub-endpoint
        leave_resp = self.client.get(f"/api/v1/hostel/student/{self.roll_a}/leave", headers=headers)
        self.assertEqual(leave_resp.status_code, 200)
        leave_data = leave_resp.get_json()
        self.assertTrue(leave_data["success"])
        self.assertIn("summary", leave_data["data"])

        # Overview convenience endpoint
        overview_resp = self.client.get("/api/v1/hostel/overview", headers=headers)
        self.assertEqual(overview_resp.status_code, 200)
        overview_data = overview_resp.get_json()
        self.assertTrue(overview_data["success"])
        self.assertEqual(overview_data["meta"]["rollNo"], self.roll_a)

    # 9. Student isolation between hostellers
    def test_student_isolation_and_contamination_protection(self):
        """Verify Student A's records NEVER contaminate Student C's response."""
        resp_a = self.client.get(
            f"/api/v1/hostel/student/{self.roll_a}?auth_token={self.token_a}"
        )
        resp_c = self.client.get(
            f"/api/v1/hostel/student/{self.roll_c}?auth_token={self.token_c}"
        )
        self.assertEqual(resp_a.status_code, 200)
        self.assertEqual(resp_c.status_code, 200)

        data_a = resp_a.get_json()["data"]
        data_c = resp_c.get_json()["data"]

        # Ensure identities are completely isolated
        self.assertEqual(data_a["profile"]["roll_number"], self.roll_a)
        self.assertEqual(data_c["profile"]["roll_number"], self.roll_c)
        self.assertNotEqual(data_a["profile"]["roll_number"], data_c["profile"]["roll_number"])

        meta_a = resp_a.get_json()["meta"]
        meta_c = resp_c.get_json()["meta"]
        self.assertEqual(meta_a["rollNo"], self.roll_a)
        self.assertEqual(meta_c["rollNo"], self.roll_c)
        self.assertNotEqual(meta_a["runId"], meta_c["runId"])

    # 10. Zero write guarantee to academic collections
    def test_zero_write_to_academic_collections(self):
        """Ensure hostel API calls NEVER mutate 'new_users' or 'subjects' collections."""
        if user_collection is None:
            return  # Skip DB count check in purely in-memory mode

        users_count_before = user_collection.count_documents({})
        subs_count_before = sub_collection.count_documents({}) if sub_collection is not None else 0

        # Run several hostel endpoint queries
        for _ in range(3):
            self.client.get(f"/api/v1/hostel/student/{self.roll_a}?auth_token={self.token_a}")
            self.client.get(f"/api/v1/hostel/student/{self.roll_a}/room?auth_token={self.token_a}")
            self.client.get(f"/api/v1/hostel/overview?auth_token={self.token_a}")

        users_count_after = user_collection.count_documents({})
        subs_count_after = sub_collection.count_documents({}) if sub_collection is not None else 0

        self.assertEqual(users_count_before, users_count_after)
        self.assertEqual(subs_count_before, subs_count_after)

    # 11. No credentials, tokens, or cookies exposed in response
    def test_privacy_no_credentials_exposed(self):
        resp = self.client.get(
            f"/api/v1/hostel/student/{self.roll_a}?auth_token={self.token_a}"
        )
        self.assertEqual(resp.status_code, 200)
        resp_text = resp.get_data(as_text=True)

        for secret in ["password", "Bearer ey", "Cookie", "Authorization:", "session_id"]:
            self.assertNotIn(secret, resp_text)


if __name__ == "__main__":
    unittest.main()
