"""
backend/tests/test_security_remediation_audit.py

Comprehensive regression test suite for SEC-01, SEC-02, SEC-03, and TST-01 remediations:
1. Unauthorized password update rejected (HTTP 401)
2. Cross-student password update forbidden (HTTP 403)
3. Authenticated password update succeeds and encrypts credential at rest
4. Password recovery request generates single-use token and OTP
5. Valid recovery token updates password unauthenticated
6. Expired recovery token rejected (HTTP 401)
7. Reused single-use recovery token rejected (HTTP 401)
8. Credential authenticated encryption/decryption roundtrip
9. Safe migration of legacy plaintext credentials without data loss
10. Tampered ciphertext decryption fails safely
11. Unauthenticated chatbot requests reject rollNo fallback and never leak student data
12. Cross-student chatbot request forbidden (HTTP 403)
13. Authenticated student chatbot queries resolve personalized data
"""

import os
import sys
import copy
import hashlib
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from crypto_service import (
    encrypt_credential,
    decrypt_credential,
    get_student_portal_password,
    is_encrypted,
    migrate_student_credentials
)
from pyserver import app, generate_auth_token


class TestSecurityRemediationAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.client = cls.app.test_client()

        cls.roll_a = "TEST_SEC_A"
        cls.roll_b = "TEST_SEC_B"

        cls.token_a = generate_auth_token(cls.roll_a)
        cls.token_b = generate_auth_token(cls.roll_b)

    def setUp(self):
        # In-memory mock database collections for pure test isolation
        self.mock_users = {
            self.roll_a: {
                "_id": "mock_id_a",
                "rollNo": self.roll_a,
                "name": "TEST SECURITY STUDENT A",
                "password": encrypt_credential("portal_password_A_123"),
                "email": "test_a@psgtech.ac.in",
                "studzone1": {"parsed_attendance": [{"code": "23MX31", "name": "CLOUD COMPUTING", "percentage": 92.0, "attended": 36, "conducted": 40, "practical_attended": 0, "practical_conducted": 0}]},
                "studzone2": {"parsed_results": []}
            },
            self.roll_b: {
                "_id": "mock_id_b",
                "rollNo": self.roll_b,
                "name": "TEST SECURITY STUDENT B",
                "password": encrypt_credential("portal_password_B_456"),
                "email": "test_b@psgtech.ac.in",
                "studzone1": {"parsed_attendance": []},
                "studzone2": {"parsed_results": []}
            }
        }
        self.mock_resets = []

        def mock_user_find_one(filter_dict, *args, **kwargs):
            if not isinstance(filter_dict, dict):
                return None
            roll = filter_dict.get("rollNo")
            if isinstance(roll, dict) and "$regex" in roll:
                # case-insensitive check
                clean = roll["$regex"].replace("^", "").replace("$", "").upper()
                return copy.deepcopy(self.mock_users.get(clean))
            if isinstance(roll, str):
                return copy.deepcopy(self.mock_users.get(roll.strip().upper()))
            return None

        def mock_user_update_one(filter_dict, update_dict, *args, **kwargs):
            roll = filter_dict.get("rollNo")
            if roll and roll in self.mock_users:
                if "$set" in update_dict:
                    self.mock_users[roll].update(update_dict["$set"])
                return MagicMock(modified_count=1)
            return MagicMock(modified_count=0)

        def mock_reset_find(filter_dict, *args, **kwargs):
            roll = filter_dict.get("rollNo")
            res = []
            for r in self.mock_resets:
                if r.get("rollNo") == roll and not r.get("used"):
                    exp_filter = filter_dict.get("expires_at")
                    if isinstance(exp_filter, dict) and "$gte" in exp_filter:
                        if r.get("expires_at") < exp_filter["$gte"]:
                            continue
                    res.append(r)
            mock_cursor = MagicMock()
            mock_cursor.sort = MagicMock(return_value=res)
            return mock_cursor

        def mock_reset_insert_one(doc, *args, **kwargs):
            d = copy.deepcopy(doc)
            d["_id"] = f"rst_{len(self.mock_resets)+1}"
            self.mock_resets.append(d)
            return MagicMock(inserted_id=d["_id"])

        def mock_reset_update_one(filter_dict, update_dict, *args, **kwargs):
            target_id = filter_dict.get("_id")
            for r in self.mock_resets:
                if r.get("_id") == target_id:
                    if filter_dict.get("used") is False and r.get("used") is True:
                        return MagicMock(modified_count=0)
                    if "$set" in update_dict:
                        r.update(update_dict["$set"])
                    return MagicMock(modified_count=1)
            return MagicMock(modified_count=0)

        def mock_reset_update_many(filter_dict, update_dict, *args, **kwargs):
            roll = filter_dict.get("rollNo")
            count = 0
            for r in self.mock_resets:
                if r.get("rollNo") == roll:
                    if "$set" in update_dict:
                        r.update(update_dict["$set"])
                    count += 1
            return MagicMock(modified_count=count)

        self.p1 = patch('pyserver.users_collection.find_one', side_effect=mock_user_find_one)
        self.p2 = patch('pyserver.users_collection.update_one', side_effect=mock_user_update_one)
        self.p3 = patch('pyserver.password_resets_collection.find', side_effect=mock_reset_find)
        self.p4 = patch('pyserver.password_resets_collection.insert_one', side_effect=mock_reset_insert_one)
        self.p5 = patch('pyserver.password_resets_collection.update_one', side_effect=mock_reset_update_one)
        self.p6 = patch('pyserver.password_resets_collection.update_many', side_effect=mock_reset_update_many)
        self.p7 = patch('pyserver.queue_tracked_email', return_value="email_sent_id")

        self.p1.start()
        self.p2.start()
        self.p3.start()
        self.p4.start()
        self.p5.start()
        self.p6.start()
        self.p7.start()

    def tearDown(self):
        self.p1.stop()
        self.p2.stop()
        self.p3.stop()
        self.p4.stop()
        self.p5.stop()
        self.p6.stop()
        self.p7.stop()

    # =========================================================================
    # 1. SEC-01: PASSWORD UPDATE & RECOVERY TESTS
    # =========================================================================

    def test_01_unauthorized_password_update_rejected(self):
        """Unauthenticated caller attempting to overwrite password must be rejected with 401"""
        resp = self.client.post('/api/update', json={
            "rollno": self.roll_a,
            "password": "hacked_password_123"
        })
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertIn("Authentication required", data.get("message", ""))

        # Verify password in DB was NOT changed
        self.assertEqual(get_student_portal_password(self.mock_users[self.roll_a]), "portal_password_A_123")

    def test_02_cross_student_password_update_forbidden(self):
        """Student authenticated as A cannot update Student B's password (HTTP 403)"""
        resp = self.client.post('/api/update', json={
            "rollno": self.roll_b,
            "password": "attempted_takeover_pwd"
        }, headers={"Authorization": f"Bearer {self.token_a}"})

        self.assertEqual(resp.status_code, 403)
        data = resp.get_json()
        self.assertIn("Cross-user access denied", data.get("message", ""))

    def test_03_authenticated_password_update_succeeds_and_encrypts(self):
        """Student authenticated as A can update their own password; stored credential is encrypted"""
        new_pwd = "brand_new_secret_pwd_789"
        resp = self.client.post('/api/update', json={
            "rollno": self.roll_a,
            "password": new_pwd
        }, headers={"Authorization": f"Bearer {self.token_a}"})

        self.assertEqual(resp.status_code, 200)
        stored_raw = self.mock_users[self.roll_a]["password"]
        self.assertTrue(is_encrypted(stored_raw), "Password in database MUST be encrypted with enc:v1: prefix")
        self.assertEqual(decrypt_credential(stored_raw), new_pwd)

    def test_04_request_reset_generates_token_and_otp(self):
        """Requesting password reset creates a single-use record with SHA-256 hashes"""
        resp = self.client.post('/api/request-reset', json={"rollNo": self.roll_a})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("otp", data)
        self.assertIn("reset_token", data)

        self.assertEqual(len(self.mock_resets), 1)
        reset_doc = self.mock_resets[0]
        self.assertEqual(reset_doc["rollNo"], self.roll_a)
        self.assertFalse(reset_doc["used"])
        # Verify hashes match
        self.assertEqual(hashlib.sha256(data["otp"].encode()).hexdigest(), reset_doc["otp_hash"])
        self.assertEqual(hashlib.sha256(data["reset_token"].encode()).hexdigest(), reset_doc["token_hash"])

    def test_05_valid_recovery_token_updates_password(self):
        """Unauthenticated caller with valid recovery OTP successfully resets password"""
        # 1. Request OTP
        req_resp = self.client.post('/api/request-reset', json={"rollNo": self.roll_a})
        otp = req_resp.get_json()["otp"]

        # 2. Reset password using OTP
        recovered_pwd = "recovered_portal_pwd_999"
        resp = self.client.post('/api/update', json={
            "rollno": self.roll_a,
            "password": recovered_pwd,
            "otp": otp
        })
        self.assertEqual(resp.status_code, 200)

        # 3. Verify OTP marked as used and password updated
        self.assertTrue(self.mock_resets[0]["used"])
        self.assertEqual(get_student_portal_password(self.mock_users[self.roll_a]), recovered_pwd)

    def test_06_reused_recovery_token_rejected(self):
        """Single-use OTP cannot be reused a second time (HTTP 401)"""
        req_resp = self.client.post('/api/request-reset', json={"rollNo": self.roll_a})
        otp = req_resp.get_json()["otp"]

        # First use -> 200
        self.client.post('/api/update', json={"rollno": self.roll_a, "password": "pwd_1", "otp": otp})

        # Second use -> 401
        second_resp = self.client.post('/api/update', json={
            "rollno": self.roll_a,
            "password": "pwd_2",
            "otp": otp
        })
        self.assertEqual(second_resp.status_code, 401)
        self.assertIn("Invalid, expired, or already used", second_resp.get_json()["message"])

    def test_07_expired_recovery_token_rejected(self):
        """Expired OTP cannot be used (HTTP 401)"""
        req_resp = self.client.post('/api/request-reset', json={"rollNo": self.roll_a})
        otp = req_resp.get_json()["otp"]

        # Expire token manually in mock DB
        self.mock_resets[0]["expires_at"] = datetime.now(timezone.utc) - timedelta(minutes=1)

        resp = self.client.post('/api/update', json={
            "rollno": self.roll_a,
            "password": "new_expired_pwd",
            "otp": otp
        })
        self.assertEqual(resp.status_code, 401)

    # =========================================================================
    # 2. SEC-02: CREDENTIAL ENCRYPTION & MIGRATION TESTS
    # =========================================================================

    def test_08_encryption_decryption_roundtrip(self):
        """Validates authenticated Fernet symmetric encryption and decryption"""
        raw_password = "Complex_Student_Portal_Pass#2026!"
        encrypted = encrypt_credential(raw_password)
        self.assertTrue(is_encrypted(encrypted))
        self.assertTrue(encrypted.startswith("enc:v1:"))
        self.assertNotEqual(raw_password, encrypted)

        decrypted = decrypt_credential(encrypted)
        self.assertEqual(raw_password, decrypted)

    def test_09_migration_of_legacy_plaintext(self):
        """Validates that legacy plaintext credentials migrate cleanly to encrypted storage"""
        mock_db_collection = MagicMock()
        mock_docs = [
            {"_id": "doc1", "rollNo": "25MX001", "password": "legacy_plain_1"},
            {"_id": "doc2", "rollNo": "25MX002", "password": "enc:v1:already_encrypted_mock"}
        ]
        mock_db_collection.find.return_value = mock_docs

        migrated_count = migrate_student_credentials(mock_db_collection)
        self.assertEqual(migrated_count, 1)
        mock_db_collection.update_one.assert_called_once()
        args, kwargs = mock_db_collection.update_one.call_args
        self.assertEqual(args[0], {"_id": "doc1"})
        new_pwd = kwargs["$set"]["password"] if "$set" in kwargs else args[1]["$set"]["password"]
        self.assertTrue(is_encrypted(new_pwd))
        self.assertEqual(decrypt_credential(new_pwd), "legacy_plain_1")

    def test_10_tampered_ciphertext_fails_safely(self):
        """Tampered or invalid ciphertext raises ValueError, never exposing plaintext or keys"""
        tampered = "enc:v1:gAAAAABq_tampered_token_garbage_bytes=="
        with self.assertRaises(ValueError):
            decrypt_credential(tampered)

    # =========================================================================
    # 3. SEC-03: CHATBOT AUTHORIZATION & IDOR PREVENTION TESTS
    # =========================================================================

    def test_11_unauthenticated_chatbot_never_leaks_student_data(self):
        """Unauthenticated caller passing rollNo in body cannot query that student's academic data"""
        resp = self.client.post('/api/chat', json={
            "message": "What is my attendance in cloud computing?",
            "rollNo": self.roll_a
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        # Must return unauthenticated navigation prompt, NOT the attendance details
        self.assertEqual(data.get("intent"), "unauthenticated")
        self.assertIn("Please log in", data.get("reply", ""))
        self.assertEqual(data.get("navigation", {}).get("path"), "/login")
        self.assertNotIn("92.0", str(data))

    def test_12_cross_student_chatbot_request_forbidden(self):
        """Authenticated caller using Token A cannot send queries targeting Student B"""
        resp = self.client.post('/api/chat', json={
            "message": "Tell me my attendance",
            "rollNo": self.roll_b
        }, headers={"Authorization": f"Bearer {self.token_a}"})

        self.assertEqual(resp.status_code, 403)
        data = resp.get_json()
        self.assertIn("error", data)
        self.assertIn("Cross-user access denied", data["error"])

    def test_13_authenticated_chatbot_resolves_personalized_query(self):
        """Authenticated caller querying their own subjects receives valid personalized response"""
        resp = self.client.post('/api/chat', json={
            "message": "what is my attendance in cloud computing",
            "rollNo": self.roll_a
        }, headers={"Authorization": f"Bearer {self.token_a}"})

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertNotEqual(data.get("intent"), "unauthenticated")
        self.assertIn("reply", data)
        self.assertIn("navigation", data)


if __name__ == '__main__':
    unittest.main()
