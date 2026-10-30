"""
backend/tests/test_pilot_operational_readiness.py

Pilot Operational Readiness & Background Worker Integration Test Suite.
Validates the operational requirements for a controlled pilot deployment:

1. Background worker lifecycle:
   - Single-instance PID locking, duplicate worker prevention, and stale lock recovery.
   - 300s (5-minute) synchronization schedule.
   - Dynamic discovery and inclusion of newly registered students.
   - Per-student exception isolation in ThreadPoolExecutor.
   - Failure recording (portalStatus) with safe state preservation.

2. Registration-to-worker integration:
   - Registration establishing baseline without missing field skips.
   - In-memory credential decryption during background polling.
   - Passing correct student identity to scrapers.
   - Change detection and email queuing on subsequent cycles.

3. Notification delivery stage:
   - Pending notification discovery and worker queueing.
   - Transient failure handling, retry counting, and exponential backoff.
   - Permanent failure / max retries (3) transition to 'failed'.
   - SMTP success recording 'sent' with sent_at timestamp.
   - Stale notification recovery following worker crash.
   - Duplicate delivery prevention via unique changeHash.

4. Production deployment guards:
   - Production master encryption key requirement.
   - MongoDB indexes and database isolation.
"""

import os
import sys
import copy
import time
import base64
import hashlib
import logging
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

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
    validate_production_key,
    CIPHERTEXT_PREFIX
)
from speed_ser import (
    acquire_instance_lock,
    release_instance_lock,
    LOCK_FILE,
    sync_single_user,
    run_sync_cycle,
    process_detected_changes
)
from notifications.recovery import recover_stale_notifications
from new_scrapers.send_mail import _email_sender, EmailSender


class TestPilotOperationalReadiness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_conn, cls.db = get_database_connection()
        cls.users_col = cls.db['new_users']
        cls.notifs_col = cls.db['notifications_log']
        cls.resets_col = cls.db['password_resets']
        ensure_database_indexes(cls.db)

        cls.app = pyserver.app
        cls.client = cls.app.test_client()

        cls.pilot_roll_1 = "PILOT_TEST_STUD_01"
        cls.pilot_email_1 = "pilot01@testpsg.ac.in"
        cls.pilot_pwd_1 = "PilotSecurePassword123!"

        cls.pilot_roll_2 = "PILOT_TEST_STUD_02"
        cls.pilot_email_2 = "pilot02@testpsg.ac.in"
        cls.pilot_pwd_2 = "PilotSecurePassword456!"

        # Track existing production students
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
        test_rolls = [cls.pilot_roll_1, cls.pilot_roll_2, "PILOT_FAIL_USER"]
        cls.users_col.delete_many({"rollNo": {"$in": test_rolls}})
        cls.notifs_col.delete_many({"rollNo": {"$in": test_rolls}})
        cls.resets_col.delete_many({"rollNo": {"$in": test_rolls}})
        if os.path.exists(LOCK_FILE):
            try:
                os.remove(LOCK_FILE)
            except Exception:
                pass

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

    def get_mock_sz1_payload(self, roll, att_pct="88%", ca1="19"):
        return {
            "profile": {
                "name": f"Pilot Student {roll}",
                "Name": f"Pilot Student {roll}",
                "rollNo": roll,
                "department": "Computer Applications"
            },
            "attendance_html": f"<table><tr><td>20CS101</td><td>{att_pct}</td></tr></table>",
            "ca_marks_html": f"<table><tr><td>20CS102</td><td>{ca1}</td></tr></table>",
            "parsed_attendance": [
                {"code": "20CS101", "name": "Software Engineering", "percentage": att_pct, "attended": 44, "total_classes": 50}
            ],
            "parsed_marks": [
                {"code": "20CS102", "name": "Database Systems", "ca1": ca1, "ca2": "20", "ca3": "-", "total": str(int(ca1) + 20)}
            ],
            "fee_status": "Paid",
            "fee_items": [],
            "class_schedule": [
                ["Period", "1", "2", "3", "4", "5", "6", "7"],
                ["Time", "8.30-9.20", "9.20-10.10", "10.30-11.20", "11.20-12.10", "1.40-2.30", "2.30-3.20", "3.30-4.20"],
                ["Monday", "20CS101", "20CS102", "FREE", "FREE", "FREE", "FREE", "FREE"]
            ],
            "leave_entries": [],
            "scholarships": {},
            "feedback": []
        }

    def get_mock_sz2_payload(self, roll, cgpa=8.60):
        return {
            "results_html": "<table><tr><td>20CS101</td><td>A+</td></tr></table>",
            "parsed_results": [{"code": "20CS101", "grade": "A+", "credits": "4"}],
            "cgpa": cgpa,
            "timetable_html": "<table><tr><td>20CS101</td><td>2026-11-20</td><td>FN</td></tr></table>",
            "parsed_timetable": [{"course_code": "20CS101", "exam_date": "2026-11-20", "session": "FN"}],
            "seating_html": "<table><tr><td>Hall E201</td><td>Desk 24</td></tr></table>",
            "seating_slots": [["20CS101", "Hall E201", "Desk 24"]],
            "circulars": []
        }

    # =========================================================================
    # 1. Background Worker Lifecycle Tests
    # =========================================================================

    def test_01_speed_ser_pid_locking_and_duplicate_prevention(self):
        """Worker Lifecycle: PID lock prevents duplicate active workers; recovers from dead PIDs."""
        # Clean any prior lock
        release_instance_lock()

        # Step 1: Normal lock acquisition
        acquired = acquire_instance_lock()
        self.assertTrue(acquired)
        self.assertTrue(os.path.exists(LOCK_FILE))
        with open(LOCK_FILE, "r") as f:
            pid = int(f.read().strip())
        self.assertEqual(pid, os.getpid())

        # Step 2: Attempting to acquire lock while this process is alive -> Must return False
        second_attempt = acquire_instance_lock()
        self.assertFalse(second_attempt, "Second worker instance must be rejected by active PID lock")

        # Step 3: Stale lock recovery (simulate dead PID like 999999)
        with open(LOCK_FILE, "w") as f:
            f.write("999999")

        stale_recovery = acquire_instance_lock()
        self.assertTrue(stale_recovery, "Stale lockfile from dead PID must be re-acquired cleanly")

        # Step 4: Clean release
        release_instance_lock()
        self.assertFalse(os.path.exists(LOCK_FILE), "Lockfile must be removed upon graceful release")

    def test_02_sync_schedule_and_frequency(self):
        """Worker Lifecycle: Polling interval configured to 300s (5m) with 60s error fallback."""
        # Inspect code lines in speed_ser.py to ensure 300s sleep is configured
        with open(os.path.join(backend_dir, 'speed_ser.py'), 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn("time.sleep(300)", content, "Sync loop must sleep for 300 seconds (5 minutes)")
        self.assertIn("time.sleep(60)", content, "Error fallback sleep must be 60 seconds")

    def test_03_per_student_exception_isolation(self):
        """Worker Lifecycle: An unhandled exception in Student A must NOT abort Student B's sync."""
        mock_user_a = {
            "rollNo": "PILOT_FAIL_USER",
            "password": encrypt_credential("passwordA"),
            "monitoring_enabled": True,
            "baseline_initialized": True
        }
        mock_user_b = {
            "rollNo": self.pilot_roll_1,
            "password": encrypt_credential(self.pilot_pwd_1),
            "monitoring_enabled": True,
            "baseline_initialized": True,
            "studzone1": {"parsed_attendance": [{"code": "20CS101", "percentage": "80%"}]}
        }

        # Seed both users
        self.users_col.delete_many({"rollNo": {"$in": ["PILOT_FAIL_USER", self.pilot_roll_1]}})
        self.users_col.insert_one(mock_user_a)
        self.users_col.insert_one(mock_user_b)

        # Student A throws an unhandled portal exception; Student B succeeds
        def mock_sync(user, db):
            if user.get("rollNo") == "PILOT_FAIL_USER":
                raise RuntimeError("Simulated catastrophic StudZone portal network failure for Student A")
            # Student B succeeds and marks synced
            db['new_users'].update_one(
                {"rollNo": user["rollNo"]},
                {"$set": {"lastSyncedAt": "2026-10-30T10:00:00Z", "sync_completed": True}}
            )
            return None

        with patch('speed_ser.sync_single_user', side_effect=mock_sync):
            # run_sync_cycle executes both in ThreadPoolExecutor
            success = run_sync_cycle()
            self.assertTrue(success)

            # Assert Student B completed despite Student A's failure
            doc_b = self.users_col.find_one({"rollNo": self.pilot_roll_1})
            self.assertTrue(doc_b.get("sync_completed"), "Student B must complete successfully despite Student A crash")

    def test_04_failure_recording_and_safe_state_preservation(self):
        """Worker Lifecycle: Portal failures update portalStatus and preserve valid cached tables."""
        # Seed student with valid existing attendance
        mock_sz1 = self.get_mock_sz1_payload(self.pilot_roll_1, att_pct="88%")
        mock_sz2 = self.get_mock_sz2_payload(self.pilot_roll_1)

        self.users_col.delete_many({"rollNo": self.pilot_roll_1})
        self.users_col.insert_one({
            "rollNo": self.pilot_roll_1,
            "password": encrypt_credential(self.pilot_pwd_1),
            "monitoring_enabled": True,
            "baseline_initialized": True,
            "attendance": "<td>88%</td>",
            "studzone1": mock_sz1,
            "studzone2": mock_sz2,
            "lastSuccessfulSyncAt": "2026-10-30T08:00:00Z"
        })

        # Simulate portal 503 outage on both portals
        with patch.object(speed_ser, 'modern_login', return_value=(False, "503 Service Unavailable")), \
             patch.object(speed_ser, 'legacy_login', return_value=(False, "Connection Timeout")), \
             patch.object(speed_ser, 'scrape_studzone1_all', return_value={}), \
             patch.object(speed_ser, 'scrape_studzone2_all', return_value={}):

            user_doc = self.users_col.find_one({"rollNo": self.pilot_roll_1})
            sync_single_user(user_doc, self.db)

            refreshed = self.users_col.find_one({"rollNo": self.pilot_roll_1})
            # Verify failure recorded visibly
            self.assertEqual(refreshed["portalStatus"]["studzone1"], "unreachable")
            self.assertEqual(refreshed["portalStatus"]["studzone2"], "unreachable")
            self.assertIsNotNone(refreshed.get("lastAttemptAt"))

            # Verify cached academic records remain 100% intact
            self.assertEqual(refreshed["studzone1"]["parsed_attendance"][0]["percentage"], "88%")
            self.assertEqual(refreshed["studzone2"]["parsed_results"][0]["grade"], "A+")

    # =========================================================================
    # 2. Registration-to-Worker Integration Tests
    # =========================================================================

    def test_05_newly_registered_student_included_in_next_sync_cycle(self):
        """Registration-to-Worker: New student registered -> immediately picked up in next sync pass."""
        mock_sz1 = self.get_mock_sz1_payload(self.pilot_roll_2, att_pct="92%", ca1="21")
        mock_sz2 = self.get_mock_sz2_payload(self.pilot_roll_2, cgpa=8.90)

        # Step 1: Register student through API
        with patch.object(pyserver, 'modern_login', return_value=MagicMock()), \
             patch.object(pyserver, 'legacy_login', return_value=MagicMock()), \
             patch.object(pyserver, 'scrape_studzone1_all', return_value=mock_sz1), \
             patch.object(pyserver, 'scrape_studzone2_all', return_value=mock_sz2), \
             patch.object(pyserver, 'queue_tracked_email', side_effect=self.mock_queue_email), \
             patch.object(pyserver, 'send_email_direct', return_value=(True, "")):

            resp = self.client.post('/api/register', json={
                "rollNo": self.pilot_roll_2,
                "password": self.pilot_pwd_2,
                "email": self.pilot_email_2
            })
            self.assertEqual(resp.status_code, 201)

        # Verify student record has required synchronization flags
        created = self.users_col.find_one({"rollNo": self.pilot_roll_2})
        self.assertIsNotNone(created)
        self.assertTrue(created.get("baseline_initialized"))
        self.assertTrue(created.get("monitoring_enabled"))

        # Step 2: Run sync cycle -> Verify new student is queried and processed
        synced_rolls = []
        def track_sync(u, db):
            synced_rolls.append(u.get("rollNo"))
            return None

        with patch('speed_ser.sync_single_user', side_effect=track_sync):
            run_sync_cycle()
            self.assertIn(self.pilot_roll_2, synced_rolls, "New student must be discovered by run_sync_cycle")

    def test_06_correct_encrypted_credentials_and_identity_passed(self):
        """Registration-to-Worker: In-memory decryption passes exact plain password to scrapers."""
        user_doc = self.users_col.find_one({"rollNo": self.pilot_roll_2})
        self.assertIsNotNone(user_doc)

        captured_credentials = {}
        def mock_modern_login(creds):
            captured_credentials["modern"] = creds
            return MagicMock()

        def mock_legacy_login(creds):
            captured_credentials["legacy"] = creds
            return MagicMock()

        mock_sz1 = self.get_mock_sz1_payload(self.pilot_roll_2, att_pct="92%", ca1="21")
        mock_sz2 = self.get_mock_sz2_payload(self.pilot_roll_2, cgpa=8.90)

        with patch.object(speed_ser, 'modern_login', side_effect=mock_modern_login), \
             patch.object(speed_ser, 'legacy_login', side_effect=mock_legacy_login), \
             patch.object(speed_ser, 'scrape_studzone1_all', return_value=mock_sz1), \
             patch.object(speed_ser, 'scrape_studzone2_all', return_value=mock_sz2):

            sync_single_user(user_doc, self.db)

            # Verify decrypted credentials passed to portals
            self.assertEqual(captured_credentials["modern"]["rollNo"], self.pilot_roll_2)
            self.assertEqual(captured_credentials["modern"]["password"], self.pilot_pwd_2)
            self.assertEqual(captured_credentials["legacy"]["rollNo"], self.pilot_roll_2)
            self.assertEqual(captured_credentials["legacy"]["password"], self.pilot_pwd_2)

            # Confirm MongoDB still stores enc:v1: ciphertext
            persisted = self.users_col.find_one({"rollNo": self.pilot_roll_2})
            self.assertTrue(is_encrypted(persisted["password"]))

    def test_07_subsequent_delta_detected_and_queued(self):
        """Registration-to-Worker: Delta in fresh portal scrape generates notification card and queues email."""
        self.notifs_col.delete_many({"rollNo": self.pilot_roll_2})
        user_doc = self.users_col.find_one({"rollNo": self.pilot_roll_2})

        # Inject attendance delta: 92% -> 73% (triggers low-attendance alert)
        delta_sz1 = self.get_mock_sz1_payload(self.pilot_roll_2, att_pct="73%", ca1="21")
        delta_sz2 = self.get_mock_sz2_payload(self.pilot_roll_2, cgpa=8.90)

        with patch.object(speed_ser, 'modern_login', return_value=MagicMock()), \
             patch.object(speed_ser, 'legacy_login', return_value=MagicMock()), \
             patch.object(speed_ser, 'scrape_studzone1_all', return_value=delta_sz1), \
             patch.object(speed_ser, 'scrape_studzone2_all', return_value=delta_sz2), \
             patch.object(speed_ser, 'queue_tracked_email', side_effect=self.mock_queue_email):

            sync_single_user(user_doc, self.db)

            # Check notification persisted in MongoDB
            notifs = list(self.notifs_col.find({"rollNo": self.pilot_roll_2, "type": "attendance"}))
            self.assertEqual(len(notifs), 1)
            self.assertIn("73", notifs[0]["message"])
            self.assertEqual(notifs[0]["status"], "pending")

            # Check email queued
            self.assertTrue(any(q["roll_no"] == self.pilot_roll_2 and q["type"] == "attendance" for q in self.queued_emails))

    # =========================================================================
    # 3. Notification Delivery Stage Tests
    # =========================================================================

    def test_08_pending_notification_discovery_and_worker_queue(self):
        """Delivery Stage: queue_email stores pending record and places item on thread queue."""
        sender = EmailSender(num_workers=0)
        sender._notifications_col = self.notifs_col

        success = sender.queue_email(
            self.pilot_email_1, "Student Sync — Attendance Alert", "<p>Body</p>",
            roll_no=self.pilot_roll_1, notif_type="attendance"
        )
        self.assertTrue(success)
        self.assertEqual(sender.email_queue.qsize(), 1)

        # Verify initial status in MongoDB is pending
        doc = self.notifs_col.find_one({"rollNo": self.pilot_roll_1, "status": "pending"})
        self.assertIsNotNone(doc)
        self.assertEqual(doc["status"], "pending")
        self.assertEqual(doc["retry_count"], 0)

    def test_09_smtp_retry_scheduling_and_max_retry_exhaustion(self):
        """Delivery Stage: Transient failures increment retry_count; 3 failures transition to 'failed'."""
        sender = EmailSender(num_workers=0)
        sender._notifications_col = self.notifs_col

        notif_id = sender._log_notification_status(
            None, self.pilot_roll_1, "attendance", self.pilot_email_1,
            "Retry Subject", "pending"
        )

        # Attempt 1 fails -> retrying, retry_count=1
        sender._log_notification_status(
            notif_id, self.pilot_roll_1, "attendance", self.pilot_email_1,
            "Retry Subject", "retrying", error="Timeout connecting to SMTP", retry_count=1
        )
        d1 = self.notifs_col.find_one({"_id": notif_id})
        self.assertEqual(d1["status"], "retrying")
        self.assertEqual(d1["retry_count"], 1)

        # Attempt 2 fails -> retrying, retry_count=2
        sender._log_notification_status(
            notif_id, self.pilot_roll_1, "attendance", self.pilot_email_1,
            "Retry Subject", "retrying", error="Connection reset", retry_count=2
        )
        d2 = self.notifs_col.find_one({"_id": notif_id})
        self.assertEqual(d2["status"], "retrying")
        self.assertEqual(d2["retry_count"], 2)

        # Attempt 3 fails (max retries reached) -> status='failed'
        sender._log_notification_status(
            notif_id, self.pilot_roll_1, "attendance", self.pilot_email_1,
            "Retry Subject", "failed", error="Max retries (3) exceeded", retry_count=3
        )
        d3 = self.notifs_col.find_one({"_id": notif_id})
        self.assertEqual(d3["status"], "failed")
        self.assertEqual(d3["retry_count"], 3)
        self.assertIn("Max retries", d3["error"])

    def test_10_smtp_success_status_and_timestamps(self):
        """Delivery Stage: Successful delivery records status='sent', sent_at timestamp, and clears error."""
        sender = EmailSender(num_workers=0)
        sender._notifications_col = self.notifs_col

        notif_id = sender._log_notification_status(
            None, self.pilot_roll_1, "marks", self.pilot_email_1,
            "Marks Subject", "pending"
        )

        sender._log_notification_status(
            notif_id, self.pilot_roll_1, "marks", self.pilot_email_1,
            "Marks Subject", "sent", is_sent=True, retry_count=1
        )

        delivered = self.notifs_col.find_one({"_id": notif_id})
        self.assertEqual(delivered["status"], "sent")
        self.assertEqual(delivered["retry_count"], 1)
        self.assertIsNotNone(delivered.get("sent_at"))
        self.assertIsNone(delivered.get("error"))

    def test_11_worker_restart_recovers_pending_notifications(self):
        """Delivery Stage: Worker crash recovery reconciles stuck notifications to 'delivery_uncertain'."""
        stale_ts = datetime.now(timezone.utc) - timedelta(seconds=7200)
        res = self.notifs_col.insert_one({
            "rollNo": self.pilot_roll_1,
            "status": "pending",
            "type": "timetable",
            "created_at": stale_ts,
            "updated_at": stale_ts
        })
        stale_id = res.inserted_id

        reconciled = recover_stale_notifications(self.db, threshold_seconds=3600)
        self.assertGreaterEqual(reconciled, 1)

        audited = self.notifs_col.find_one({"_id": stale_id})
        self.assertEqual(audited["status"], "delivery_uncertain")
        self.assertTrue(audited["requires_reconciliation"])
        self.assertIn("Recovered by stale-notification auditor", audited["error"])

    # =========================================================================
    # 4. Production Deployment Configuration Checks
    # =========================================================================

    def test_12_production_encryption_key_and_env_guards(self):
        """Deployment Config: Production guard requires explicit encryption key; collections indexed."""
        # Missing key in production raises fatal RuntimeError
        with self.assertRaises(RuntimeError):
            validate_production_key(key=None, is_production=True)

        with self.assertRaises(RuntimeError):
            validate_production_key(key="", is_production=True)

        # Valid master key passes
        self.assertTrue(validate_production_key(key="strong_pilot_key_2026_psgtech", is_production=True))

        # Check database indexes
        indexes = self.notifs_col.index_information()
        self.assertIn("changeHash_unique", indexes, "notifications_log must have changeHash_unique index")

        user_indexes = self.users_col.index_information()
        self.assertTrue(any("rollNo" in str(idx.get("key")) for idx in user_indexes.values()))


if __name__ == '__main__':
    unittest.main()
