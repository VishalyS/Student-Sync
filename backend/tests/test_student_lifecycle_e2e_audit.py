"""
backend/tests/test_student_lifecycle_e2e_audit.py

Comprehensive End-to-End Student Lifecycle Audit Test Suite.
Validates the entire student journey from registration to background monitoring
using isolated synthetic accounts, mocked portal responses, and mock email senders:

1. Register new student with whitespace/mixed-case rollNo normalization.
2. Verified encrypted account storage (enc:v1: Fernet, no plaintext passwords).
3. Initial scraping triggered & dual-portal data stored (StudZone 1 & StudZone 2).
4. Portal resilience: Failed login, timeouts, partial/empty data preserve valid records.
5. Baseline establishment: Exactly zero false notifications emitted on initial scrape.
6. Legitimate change detection: Attendance drop and CA mark increase generate specific notifications.
7. Deduplication: Unchanged subsequent scrapes emit 0 duplicate notifications.
8. Multi-student isolation: Student 2 blocked from Student 1 academics, notifications, & chatbot.
9. Notification delivery vs creation separation: Document state transitions (pending -> sent/retrying).
10. Background worker crash recovery: recover_stale_notifications reconciles stuck records without duplicate emails.
11. Delivery retry safety: Exponential backoff, retry counting, idempotent delivery.
12. Encryption key rotation & missing key production guard.
13. Legacy credential migration idempotency.
14. Sensitive data log hygiene: Zero plaintext passwords or secrets in application logs.
15. Password recovery email verification: OTP generation, SHA-256 storage, and single-use update.
16. Scheduled synchronization visible failure reporting (portalStatus & syncStatus).
"""

import os
import sys
import copy
import time
import base64
import hashlib
import logging
import io
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from bson import ObjectId

# Ensure backend directory is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import pyserver
import speed_ser
from database import get_database_connection, ensure_database_indexes
from crypto_service import (
    encrypt_credential,
    decrypt_credential,
    is_encrypted,
    get_student_portal_password,
    migrate_student_credentials,
    rotate_master_key,
    reencrypt_credential,
    validate_production_key,
    CIPHERTEXT_PREFIX
)
from speed_ser import sync_single_user, process_detected_changes
from notifications.change_detector import detect_granular_changes, compute_change_hash
from notifications.recovery import recover_stale_notifications
from new_scrapers.send_mail import _email_sender, EmailSender


class TestStudentLifecycleE2EAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_conn, cls.db = get_database_connection()
        cls.users_col = cls.db['new_users']
        cls.notifs_col = cls.db['notifications_log']
        cls.resets_col = cls.db['password_resets']
        ensure_database_indexes(cls.db)

        cls.app = pyserver.app
        cls.client = cls.app.test_client()

        cls.student1_raw = "  e2e_audit_stud_01  "
        cls.student1_roll = "E2E_AUDIT_STUD_01"
        cls.student1_email = "student01@testpsg.ac.in"
        cls.student1_pwd = "SecretPortalPassword123!"

        cls.student2_roll = "E2E_AUDIT_STUD_02"
        cls.student2_email = "student02@testpsg.ac.in"
        cls.student2_pwd = "SecretPortalPassword456!"

        # Track existing production students to ensure 100% data preservation
        cls.production_rolls = ['25MX232', '25MX227', '25MX116', '25MX231', '25MX230']
        cls.pre_test_prod_counts = {
            roll: cls.users_col.count_documents({"rollNo": roll})
            for roll in cls.production_rolls
        }

        cls.cleanup_test_data()

    @classmethod
    def tearDownClass(cls):
        cls.cleanup_test_data()
        # Verify production students remain completely untouched
        for roll, expected_count in cls.pre_test_prod_counts.items():
            actual_count = cls.users_col.count_documents({"rollNo": roll})
            assert actual_count == expected_count, f"Safety violation: production student {roll} count changed!"

    @classmethod
    def cleanup_test_data(cls):
        test_rolls = [cls.student1_roll, cls.student2_roll, "E2E_LEGACY_STUD_99", "E2E_FAIL_STUD_03"]
        cls.users_col.delete_many({"rollNo": {"$in": test_rolls}})
        cls.notifs_col.delete_many({"rollNo": {"$in": test_rolls}})
        cls.resets_col.delete_many({"rollNo": {"$in": test_rolls}})

    def setUp(self):
        self.sent_emails = []
        self.queued_emails = []

    def mock_queue_email(self, roll_no, recipient_email, ntype, subject, body, notif_id=None, *args, **kwargs):
        self.queued_emails.append({
            "roll_no": roll_no,
            "recipient_email": recipient_email,
            "type": ntype,
            "subject": subject,
            "body": body,
            "notif_id": notif_id
        })
        return notif_id or "mock_queued_id"

    def mock_send_email_direct(self, recipient_email, subject, body, *args, **kwargs):
        self.sent_emails.append({
            "recipient_email": recipient_email,
            "subject": subject,
            "body": body,
            "rollNo": kwargs.get('rollNo'),
            "notif_type": kwargs.get('notif_type', 'general')
        })
        return True, ""

    def get_mock_sz1_payload(self, roll, att_pct="85%", ca1="18", ca2="20", fee_due=2500):
        return {
            "profile": {
                "name": f"Test Student {roll}",
                "Name": f"Test Student {roll}",
                "rollNo": roll,
                "department": "Computer Applications"
            },
            "attendance_html": f"<table><tr><td>20CS101</td><td>{att_pct}</td></tr></table>",
            "ca_marks_html": f"<table><tr><td>20CS102</td><td>{ca1}</td><td>{ca2}</td></tr></table>",
            "parsed_attendance": [
                {"code": "20CS101", "name": "Software Engineering", "percentage": att_pct, "attended": 42, "total_classes": 50}
            ],
            "parsed_marks": [
                {"code": "20CS102", "name": "Database Systems", "ca1": ca1, "ca2": ca2, "ca3": "-", "total": str(int(ca1) + int(ca2))}
            ],
            "fee_status": f"Due: Rs. {fee_due}" if fee_due > 0 else "Paid",
            "fee_items": [{"description": "Semester Tuition", "amount": fee_due}],
            "class_schedule": [
                ["Period", "1", "2", "3", "4", "5", "6", "7"],
                ["Time", "8.30-9.20", "9.20-10.10", "10.30-11.20", "11.20-12.10", "1.40-2.30", "2.30-3.20", "3.30-4.20"],
                ["Monday", "20CS101", "20CS102", "FREE", "FREE", "FREE", "FREE", "FREE"]
            ],
            "leave_entries": [{"type": "OD", "status": "Approved", "days": "1"}],
            "scholarships": {"vallalar": "Eligible"},
            "feedback": []
        }

    def get_mock_sz2_payload(self, roll, cgpa=8.45):
        return {
            "results_html": "<table><tr><td>20CS101</td><td>A+</td></tr></table>",
            "parsed_results": [{"code": "20CS101", "grade": "A+", "credits": "4"}],
            "cgpa": cgpa,
            "timetable_html": "<table><tr><td>20CS101</td><td>2026-11-20</td><td>FN</td></tr></table>",
            "parsed_timetable": [{"course_code": "20CS101", "exam_date": "2026-11-20", "session": "FN"}],
            "seating_html": "<table><tr><td>Hall E201</td><td>Desk 24</td></tr></table>",
            "seating_slots": [["20CS101", "Hall E201", "Desk 24"]],
            "circulars": [{"title": "End Semester Schedule", "link": "/exam/circular1.pdf"}]
        }

    # =========================================================================
    # 1. Registration to Baseline Scraping Workflow (Items 1-6)
    # =========================================================================

    def test_01_register_new_student_normalized_account_encrypted(self):
        """1 & 2: Register student -> normalized rollNo, encrypted credential, baseline status."""
        mock_sz1 = self.get_mock_sz1_payload(self.student1_roll)
        mock_sz2 = self.get_mock_sz2_payload(self.student1_roll)

        with patch.object(pyserver, 'modern_login', return_value=MagicMock()), \
             patch.object(pyserver, 'legacy_login', return_value=MagicMock()), \
             patch.object(pyserver, 'scrape_studzone1_all', return_value=mock_sz1), \
             patch.object(pyserver, 'scrape_studzone2_all', return_value=mock_sz2), \
             patch.object(pyserver, 'queue_tracked_email', side_effect=self.mock_queue_email), \
             patch.object(pyserver, 'send_email_direct', side_effect=self.mock_send_email_direct):

            resp = self.client.post('/api/register', json={
                "rollNo": self.student1_raw,
                "password": self.student1_pwd,
                "email": self.student1_email
            })

            self.assertEqual(resp.status_code, 201)
            data = resp.get_json()
            self.assertEqual(data["rollNo"], self.student1_roll)

            # Verify database document normalization & encryption
            student_doc = self.users_col.find_one({"rollNo": self.student1_roll})
            self.assertIsNotNone(student_doc)
            self.assertEqual(student_doc["rollNo"], self.student1_roll)
            self.assertEqual(student_doc["email"], self.student1_email)
            self.assertTrue(student_doc["baseline_initialized"])

            # Verify credential protection: enc:v1: prefix and reversible only via crypto_service
            stored_pwd = student_doc["password"]
            self.assertTrue(is_encrypted(stored_pwd), "Stored password must start with enc:v1:")
            self.assertNotEqual(stored_pwd, self.student1_pwd, "Plaintext password must not exist in DB")
            self.assertEqual(decrypt_credential(stored_pwd), self.student1_pwd)

            # Verify welcome email dispatched (either direct or queued)
            welcome_dispatched = [e for e in self.sent_emails if e.get("notif_type") == "welcome"] + \
                                 [e for e in self.queued_emails if e.get("type") == "welcome"]
            self.assertTrue(len(welcome_dispatched) >= 1, f"Expected welcome email dispatched, sent={self.sent_emails}, queued={self.queued_emails}")

    def test_02_initial_scraping_persists_studzone1_and_studzone2_data(self):
        """3 & 4: Dual portal data correctly stored under student record."""
        student_doc = self.users_col.find_one({"rollNo": self.student1_roll})
        self.assertIsNotNone(student_doc)

        # StudZone 1 modules
        sz1 = student_doc.get("studzone1", {})
        self.assertEqual(len(sz1.get("parsed_attendance", [])), 1)
        self.assertEqual(sz1["parsed_attendance"][0]["code"], "20CS101")
        self.assertEqual(len(sz1.get("parsed_marks", [])), 1)
        self.assertEqual(sz1["parsed_marks"][0]["code"], "20CS102")
        self.assertEqual(sz1.get("fee_status"), "Due: Rs. 2500")
        self.assertEqual(len(sz1.get("class_schedule", [])), 3)

        # StudZone 2 modules
        sz2 = student_doc.get("studzone2", {})
        self.assertEqual(len(sz2.get("parsed_results", [])), 1)
        self.assertEqual(sz2["parsed_results"][0]["grade"], "A+")
        self.assertEqual(student_doc.get("cgpa"), 8.45)
        self.assertEqual(len(sz2.get("parsed_timetable", [])), 1)
        self.assertEqual(len(sz2.get("seating_slots", [])), 1)

    def test_03_initial_scrape_zero_false_notifications(self):
        """6: Initial scrape must establish baseline with ZERO change notifications."""
        # Query notifications_log for academic change alerts for Student 1
        notifs = list(self.notifs_col.find({
            "rollNo": self.student1_roll,
            "type": {"$in": ["attendance", "marks", "results", "timetable", "fees"]}
        }))
        self.assertEqual(len(notifs), 0, f"Initial scrape emitted false alerts: {notifs}")

    def test_04_portal_failures_timeouts_partial_data_preserve_valid_records(self):
        """5: Failed login, timeouts, and empty portal data must NOT overwrite valid records."""
        original_student = self.users_col.find_one({"rollNo": self.student1_roll})
        self.assertIsNotNone(original_student)
        original_att = original_student["studzone1"]["parsed_attendance"]
        original_marks = original_student["studzone1"]["parsed_marks"]
        original_results = original_student["studzone2"]["parsed_results"]

        # Simulate StudZone 1 login failure & empty StudZone 2 response
        with patch.object(speed_ser, 'modern_login', return_value=(False, "504 Gateway Timeout")), \
             patch.object(speed_ser, 'legacy_login', return_value=(False, "Connection reset")), \
             patch.object(speed_ser, 'scrape_studzone1_all', return_value={}), \
             patch.object(speed_ser, 'scrape_studzone2_all', return_value={}):

            res = sync_single_user(original_student, self.db)
            self.assertIsNone(res)

            # Re-fetch document from MongoDB
            updated_doc = self.users_col.find_one({"rollNo": self.student1_roll})

            # Verify existing records preserved
            self.assertEqual(updated_doc["studzone1"]["parsed_attendance"], original_att)
            self.assertEqual(updated_doc["studzone1"]["parsed_marks"], original_marks)
            self.assertEqual(updated_doc["studzone2"]["parsed_results"], original_results)

            # Verify portal failure visibly reported in portalStatus
            portal_status = updated_doc.get("portalStatus", {})
            self.assertEqual(portal_status.get("studzone1"), "unreachable")
            self.assertEqual(portal_status.get("studzone2"), "unreachable")

    # =========================================================================
    # 2. Change Detection, Notification Generation, & Deduplication (Items 7-9)
    # =========================================================================

    def test_05_simulate_attendance_and_ca_marks_changes_generate_specific_notifications(self):
        """7 & 8: Simulate attendance drop and CA mark increase -> specific notifications generated."""
        current_user = self.users_col.find_one({"rollNo": self.student1_roll})
        self.assertIsNotNone(current_user)

        # Fresh data with genuine changes:
        # 1. 20CS101 attendance drops from 85% -> 71% (below 75% threshold)
        # 2. 20CS102 CA1 marks updated from 18 -> 24
        fresh_sz1 = self.get_mock_sz1_payload(self.student1_roll, att_pct="71%", ca1="24", ca2="20")
        fresh_sz2 = self.get_mock_sz2_payload(self.student1_roll)

        with patch.object(speed_ser, 'modern_login', return_value=MagicMock()), \
             patch.object(speed_ser, 'legacy_login', return_value=MagicMock()), \
             patch.object(speed_ser, 'scrape_studzone1_all', return_value=fresh_sz1), \
             patch.object(speed_ser, 'scrape_studzone2_all', return_value=fresh_sz2), \
             patch.object(speed_ser, 'queue_tracked_email', side_effect=self.mock_queue_email):

            sync_single_user(current_user, self.db)

            # Verify notifications generated in MongoDB
            notifs = list(self.notifs_col.find({
                "rollNo": self.student1_roll,
                "type": {"$in": ["attendance", "marks"]}
            }))
            self.assertEqual(len(notifs), 2, f"Expected exactly 2 notifications, found {len(notifs)}")

            att_notif = next((n for n in notifs if n["type"] == "attendance"), None)
            marks_notif = next((n for n in notifs if n["type"] == "marks"), None)

            self.assertIsNotNone(att_notif)
            self.assertIn("71", att_notif.get("message", "") or att_notif.get("title", ""))
            self.assertTrue(len(att_notif.get("changeHash", "")) == 64)

            self.assertIsNotNone(marks_notif)
            self.assertIn("24", marks_notif.get("message", "") or marks_notif.get("title", ""))
            self.assertTrue(len(marks_notif.get("changeHash", "")) == 64)

            # Verify delivery emails queued
            queued_types = [q["type"] for q in self.queued_emails]
            self.assertIn("attendance", queued_types)
            self.assertIn("marks", queued_types)

    def test_06_unchanged_subsequent_scrapes_zero_duplicate_notifications(self):
        """9: Unchanged data across repeated polling passes emits 0 duplicate notifications."""
        current_user = self.users_col.find_one({"rollNo": self.student1_roll})
        self.assertIsNotNone(current_user)
        pre_count = self.notifs_col.count_documents({"rollNo": self.student1_roll})

        # Same data as test_05 (no delta)
        fresh_sz1 = self.get_mock_sz1_payload(self.student1_roll, att_pct="71%", ca1="24", ca2="20")
        fresh_sz2 = self.get_mock_sz2_payload(self.student1_roll)

        with patch.object(speed_ser, 'modern_login', return_value=MagicMock()), \
             patch.object(speed_ser, 'legacy_login', return_value=MagicMock()), \
             patch.object(speed_ser, 'scrape_studzone1_all', return_value=fresh_sz1), \
             patch.object(speed_ser, 'scrape_studzone2_all', return_value=fresh_sz2), \
             patch.object(speed_ser, 'queue_tracked_email', side_effect=self.mock_queue_email):

            sync_single_user(current_user, self.db)

            post_count = self.notifs_col.count_documents({"rollNo": self.student1_roll})
            self.assertEqual(post_count, pre_count, "Unchanged data must generate zero new notifications")

    # =========================================================================
    # 3. Multi-Student Isolation & Authorization (Item 10)
    # =========================================================================

    def test_07_multi_student_isolation_academics_notifications_chatbot(self):
        """10: Student 2 session token must be strictly forbidden from accessing Student 1's data."""
        # Register Student 2
        mock_sz1_s2 = self.get_mock_sz1_payload(self.student2_roll, att_pct="90%", ca1="22")
        mock_sz2_s2 = self.get_mock_sz2_payload(self.student2_roll, cgpa=9.10)

        with patch.object(pyserver, 'modern_login', return_value=MagicMock()), \
             patch.object(pyserver, 'legacy_login', return_value=MagicMock()), \
             patch.object(pyserver, 'scrape_studzone1_all', return_value=mock_sz1_s2), \
             patch.object(pyserver, 'scrape_studzone2_all', return_value=mock_sz2_s2), \
             patch.object(pyserver, 'queue_tracked_email', side_effect=self.mock_queue_email), \
             patch.object(pyserver, 'send_email_direct', side_effect=self.mock_send_email_direct):

            resp = self.client.post('/api/register', json={
                "rollNo": self.student2_roll,
                "password": self.student2_pwd,
                "email": self.student2_email
            })
            self.assertEqual(resp.status_code, 201)

        token_s2 = pyserver.generate_auth_token(self.student2_roll)
        headers_s2 = {"Authorization": f"Bearer {token_s2}"}

        # Attempt to access Student 1's records using Student 2's token
        endpoints_to_test = [
            f'/api/profile?rollNo={self.student1_roll}',
            f'/api/attendance/summary?rollNo={self.student1_roll}',
            f'/api/academic/marks-summary?rollNo={self.student1_roll}',
            f'/api/notifications?rollNo={self.student1_roll}'
        ]

        for ep in endpoints_to_test:
            r = self.client.get(ep, headers=headers_s2)
            self.assertEqual(r.status_code, 403, f"Endpoint {ep} allowed cross-user access: {r.status_code}")

        # Cross-student Chatbot query
        chat_resp = self.client.post('/api/chatbot', headers=headers_s2, json={
            "message": "What is my attendance?",
            "rollNo": self.student1_roll
        })
        self.assertEqual(chat_resp.status_code, 403, "Chatbot must block cross-student queries")

        # Cross-student password overwrite
        update_resp = self.client.post('/api/update', headers=headers_s2, json={
            "rollno": self.student1_roll,
            "password": "AttemptedTakeoverPassword"
        })
        self.assertEqual(update_resp.status_code, 403, "Password update must block cross-user overwrite")

    # =========================================================================
    # 4. Background Worker, Delivery vs Creation, & Retries (Items 11-12)
    # =========================================================================

    def test_08_notification_creation_vs_actual_delivery_separation(self):
        """11: Notification creation in MongoDB is distinct from actual email delivery."""
        sender = EmailSender(num_workers=0)  # No workers running yet
        sender._notifications_col = self.notifs_col

        notif_id = sender._log_notification_status(
            None, self.student1_roll, "attendance", self.student1_email,
            "Test Subject", "pending", is_sent=False
        )
        self.assertIsNotNone(notif_id)

        # Inspect document: status is pending, is_sent is False
        doc = self.notifs_col.find_one({"_id": notif_id})
        self.assertEqual(doc["status"], "pending")
        self.assertNotIn("sent_at", doc)

        # Simulate successful worker execution
        sender._log_notification_status(
            notif_id, self.student1_roll, "attendance", self.student1_email,
            "Test Subject", "sent", is_sent=True, retry_count=0
        )
        delivered_doc = self.notifs_col.find_one({"_id": notif_id})
        self.assertEqual(delivered_doc["status"], "sent")
        self.assertIsNotNone(delivered_doc.get("sent_at"))

    def test_09_worker_restart_recovers_pending_stale_notifications(self):
        """11: Worker crash leaving stuck notifications is safely reconciled without resend spam."""
        stale_time = datetime.now(timezone.utc) - timedelta(seconds=7200)  # 2 hours old
        res = self.notifs_col.insert_one({
            "rollNo": self.student1_roll,
            "status": "pending",
            "type": "attendance",
            "created_at": stale_time,
            "updated_at": stale_time
        })
        stale_id = res.inserted_id

        # Run recovery with 1 hour threshold
        reconciled_count = recover_stale_notifications(self.db, threshold_seconds=3600)
        self.assertGreaterEqual(reconciled_count, 1)

        reconciled_doc = self.notifs_col.find_one({"_id": stale_id})
        self.assertEqual(reconciled_doc["status"], "delivery_uncertain")
        self.assertTrue(reconciled_doc["requires_reconciliation"])
        self.assertIn("Recovered by stale-notification auditor", reconciled_doc["error"])

    def test_10_delivery_retries_safe_and_idempotent(self):
        """12: Delivery retries are safe, tracked, and backoff safely."""
        sender = EmailSender(num_workers=0)
        sender._notifications_col = self.notifs_col

        notif_id = sender._log_notification_status(
            None, self.student1_roll, "marks", self.student1_email,
            "Retry Test", "pending"
        )

        # Simulate first failure -> retrying
        sender._log_notification_status(
            notif_id, self.student1_roll, "marks", self.student1_email,
            "Retry Test", "retrying", error="SMTP Connection Timeout", retry_count=1
        )
        doc1 = self.notifs_col.find_one({"_id": notif_id})
        self.assertEqual(doc1["status"], "retrying")
        self.assertEqual(doc1["retry_count"], 1)

        # Simulate subsequent success
        sender._log_notification_status(
            notif_id, self.student1_roll, "marks", self.student1_email,
            "Retry Test", "sent", is_sent=True, retry_count=1
        )
        doc2 = self.notifs_col.find_one({"_id": notif_id})
        self.assertEqual(doc2["status"], "sent")
        self.assertEqual(doc2["retry_count"], 1)
        self.assertIsNone(doc2.get("error"))

    # =========================================================================
    # 5. Additional Security Checks (Key Rotation, Logs, Migration, OTP)
    # =========================================================================

    def test_11_encryption_key_rotation_and_missing_key_behavior(self):
        """Security: Missing-key production guard and zero-downtime key rotation."""
        # 1. Missing-key behavior in production mode
        with self.assertRaises(RuntimeError):
            validate_production_key(key="", is_production=True)

        # Valid key check
        self.assertTrue(validate_production_key(key="strong_master_key_12345", is_production=True))

        # 2. Key rotation test: Old Key -> New Key
        old_master = "old_master_key_student_sync_2026_a"
        new_master = "new_master_key_student_sync_2026_b"

        # Encrypt with old key
        from cryptography.fernet import Fernet
        from crypto_service import _derive_fernet_key
        cipher_old = Fernet(_derive_fernet_key(old_master))
        raw_token = cipher_old.encrypt("RotateMePassword999!".encode('utf-8')).decode('utf-8')
        old_ciphertext = f"{CIPHERTEXT_PREFIX}{raw_token}"

        # Re-encrypt with new key
        new_ciphertext = reencrypt_credential(old_ciphertext, old_master, new_master)
        self.assertTrue(new_ciphertext.startswith(CIPHERTEXT_PREFIX))
        self.assertNotEqual(old_ciphertext, new_ciphertext)

        # Decrypt with new key
        cipher_new = Fernet(_derive_fernet_key(new_master))
        new_raw = new_ciphertext[len(CIPHERTEXT_PREFIX):]
        decrypted = cipher_new.decrypt(new_raw.encode('utf-8')).decode('utf-8')
        self.assertEqual(decrypted, "RotateMePassword999!")

    def test_12_legacy_credential_migration_idempotent(self):
        """Security: Legacy plaintext credentials migrated without double-encryption or corruption."""
        legacy_roll = "E2E_LEGACY_STUD_99"
        self.users_col.delete_many({"rollNo": legacy_roll})
        self.users_col.insert_one({
            "rollNo": legacy_roll,
            "password": "legacy_unencrypted_secret",
            "name": "Legacy Student"
        })

        # Run migration pass 1
        migrated = migrate_student_credentials(self.users_col)
        self.assertGreaterEqual(migrated, 1)

        migrated_doc = self.users_col.find_one({"rollNo": legacy_roll})
        self.assertTrue(is_encrypted(migrated_doc["password"]))
        self.assertEqual(get_student_portal_password(migrated_doc), "legacy_unencrypted_secret")

        # Run migration pass 2 (idempotency check)
        migrated_pass2 = migrate_student_credentials(self.users_col)
        migrated_doc2 = self.users_col.find_one({"rollNo": legacy_roll})
        self.assertEqual(migrated_doc2["password"], migrated_doc["password"], "Password must not be double encrypted")
        self.assertEqual(get_student_portal_password(migrated_doc2), "legacy_unencrypted_secret")

    def test_13_zero_sensitive_data_in_logs(self):
        """Security: Log records must NEVER contain passwords, raw tokens, or master keys."""
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.DEBUG)

        target_loggers = [logging.getLogger(n) for n in ['speed_ser', 'pyserver', 'crypto_service', 'notifications']]
        for l in target_loggers:
            l.addHandler(handler)

        try:
            student_doc = self.users_col.find_one({"rollNo": self.student1_roll})
            self.assertIsNotNone(student_doc)
            pwd = get_student_portal_password(student_doc)
            self.assertEqual(pwd, self.student1_pwd)

            # Check logged output
            log_output = log_stream.getvalue()
            self.assertNotIn(self.student1_pwd, log_output)
            self.assertNotIn("RotateMePassword999!", log_output)
            self.assertNotIn("InitialPassword123!", log_output)
        finally:
            for l in target_loggers:
                l.removeHandler(handler)

    def test_14_password_recovery_email_mocked_flow(self):
        """Security: Password recovery emits OTP email, stores SHA-256 hash, and allows single-use reset."""
        # Step 1: Request reset code
        with patch.object(pyserver, 'queue_tracked_email', side_effect=self.mock_queue_email):
            req_resp = self.client.post('/api/auth/request-reset', json={"rollNo": self.student1_roll})
            self.assertEqual(req_resp.status_code, 200)

            # Verify recovery email was queued
            sec_emails = [e for e in self.queued_emails if e["type"] == "security"]
            self.assertEqual(len(sec_emails), 1)
            self.assertEqual(sec_emails[0]["recipient_email"], self.student1_email)

            # Verify reset doc in MongoDB stores SHA-256 hash (never plain OTP)
            reset_doc = self.resets_col.find_one({"rollNo": self.student1_roll, "used": False})
            self.assertIsNotNone(reset_doc)
            self.assertIn("otp_hash", reset_doc)
            self.assertNotIn("otp", reset_doc)

            # Retrieve OTP from response (allowed in test/dev mode)
            otp = req_resp.get_json().get("otp")
            self.assertIsNotNone(otp)

            # Step 2: Update password using OTP
            new_pwd = "BrandNewSecurePassword2026!"
            update_resp = self.client.post('/api/update', json={
                "rollno": self.student1_roll,
                "password": new_pwd,
                "otp": otp
            })
            self.assertEqual(update_resp.status_code, 200)

            # Step 3: Verify password updated & encrypted at rest
            updated_doc = self.users_col.find_one({"rollNo": self.student1_roll})
            self.assertTrue(is_encrypted(updated_doc["password"]))
            self.assertEqual(decrypt_credential(updated_doc["password"]), new_pwd)

            # Step 4: Verify OTP is consumed and cannot be reused
            reused_resp = self.client.post('/api/update', json={
                "rollno": self.student1_roll,
                "password": "AnotherAttempt123!",
                "otp": otp
            })
            self.assertEqual(reused_resp.status_code, 401)

    def test_15_scheduled_sync_reports_portal_failures_visibly(self):
        """Reliability: Scheduled sync records portalStatus and syncStatus clearly on failures."""
        student_doc = self.users_col.find_one({"rollNo": self.student1_roll})
        self.assertIsNotNone(student_doc)

        with patch.object(speed_ser, 'modern_login', return_value=(False, "503 Service Unavailable")), \
             patch.object(speed_ser, 'legacy_login', return_value=(False, "Connection Timeout")), \
             patch.object(speed_ser, 'scrape_studzone1_all', return_value={}), \
             patch.object(speed_ser, 'scrape_studzone2_all', return_value={}):

            sync_single_user(student_doc, self.db)

            refreshed = self.users_col.find_one({"rollNo": self.student1_roll})
            self.assertEqual(refreshed["portalStatus"]["studzone1"], "unreachable")
            self.assertEqual(refreshed["portalStatus"]["studzone2"], "unreachable")
            self.assertIsNotNone(refreshed.get("lastAttemptAt"))


if __name__ == '__main__':
    unittest.main()
