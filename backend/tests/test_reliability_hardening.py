import os
import sys
import time
import unittest
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, MagicMock

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from pymongo.errors import DuplicateKeyError

try:
    from backend.database import db, notifications_collection, user_collection, ensure_database_indexes
    from backend.new_scrapers.send_mail import _email_sender, queue_tracked_email
    from backend.speed_ser import process_detected_changes
    from backend.notifications.recovery import (
        recover_stale_notifications,
        get_unreconciled_notifications,
        reconcile_notification
    )
except ImportError:
    from database import db, notifications_collection, user_collection, ensure_database_indexes
    from new_scrapers.send_mail import _email_sender, queue_tracked_email
    from speed_ser import process_detected_changes
    from notifications.recovery import (
        recover_stale_notifications,
        get_unreconciled_notifications,
        reconcile_notification
    )


class TestReliabilityHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = db
        cls.notifs_col = cls.db['notifications_log'] if cls.db is not None else None
        cls.users_col = cls.db['new_users'] if cls.db is not None else None
        cls.test_roll = "TEST_RELIABILITY_ROLL"
        cls.recipient = f"{cls.test_roll.lower()}@psgtech.ac.in"
        # Ensure database index is present
        if cls.db is not None:
            ensure_database_indexes(cls.db)

    def setUp(self):
        # Drain queue
        while not _email_sender.email_queue.empty():
            try:
                _email_sender.email_queue.get_nowait()
                _email_sender.email_queue.task_done()
            except Exception:
                pass

        if self.notifs_col is not None:
            self.notifs_col.delete_many({"rollNo": self.test_roll})
        if self.users_col is not None:
            self.users_col.delete_many({"rollNo": self.test_roll})

    def tearDown(self):
        # Drain queue
        while not _email_sender.email_queue.empty():
            try:
                _email_sender.email_queue.get_nowait()
                _email_sender.email_queue.task_done()
            except Exception:
                pass

        if self.notifs_col is not None:
            self.notifs_col.delete_many({"rollNo": self.test_roll})
        if self.users_col is not None:
            self.users_col.delete_many({"rollNo": self.test_roll})

    def test_01_unique_sparse_index_enforcement(self):
        """Verify that changeHash unique index rejects duplicates with DuplicateKeyError while allowing documents without hash."""
        test_hash = f"test_hash_unique_{int(time.time())}"
        doc1 = {
            "rollNo": self.test_roll,
            "type": "attendance",
            "changeHash": test_hash,
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        res1 = self.notifs_col.insert_one(doc1)
        self.assertIsNotNone(res1.inserted_id)

        # Second document with identical changeHash must raise DuplicateKeyError
        doc2 = {
            "rollNo": self.test_roll,
            "type": "attendance",
            "changeHash": test_hash,
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        with self.assertRaises(DuplicateKeyError):
            self.notifs_col.insert_one(doc2)

        # Document without changeHash must still be permitted (sparse index property)
        doc3 = {
            "rollNo": self.test_roll,
            "type": "system",
            "status": "sent",
            "created_at": datetime.now(timezone.utc)
        }
        res3 = self.notifs_col.insert_one(doc3)
        self.assertIsNotNone(res3.inserted_id)

    def test_02_concurrent_duplicate_notification_attempts(self):
        """Simulate concurrent threads detecting the exact same event; verify only 1 DB doc and 1 email occur."""
        old_user = {
            "rollNo": self.test_roll,
            "name": "Reliability Student",
            "notifications": {"attendance": True},
            "studzone1": {
                "parsed_attendance": [
                    {"code": "20CS501", "name": "Distributed Systems", "percentage": "80.0", "attended": "32", "total": "40"}
                ]
            }
        }
        sz1_fresh = {
            "parsed_attendance": [
                {"code": "20CS501", "name": "Distributed Systems", "percentage": "75.0", "attended": "32", "total": "42.6"}
            ]
        }
        sz2_fresh = {}

        sent_emails = []

        def mock_attempt(recipient, subject, body):
            sent_emails.append((recipient, subject))
            return True, ""

        with patch.object(_email_sender, '_send_email_attempt', side_effect=mock_attempt):
            # Run 5 concurrent threads trying to process the exact same detected change
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [
                    executor.submit(process_detected_changes, self.test_roll, old_user, sz1_fresh, sz2_fresh, self.db)
                    for _ in range(5)
                ]
                for f in as_completed(futures):
                    f.result()

            _email_sender.email_queue.join()

            docs = list(self.notifs_col.find({"rollNo": self.test_roll, "type": "attendance"}))
            self.assertEqual(len(docs), 1, "Exactly one notification document must exist despite 5 concurrent attempts")
            self.assertEqual(docs[0]["status"], "sent")
            self.assertEqual(len(sent_emails), 1, "Exactly one email delivery must occur despite 5 concurrent attempts")

    def test_03_recovery_of_stale_pending_records(self):
        """Verify stale pending/retrying notifications (>1h old) transition to 'delivery_uncertain' with audit context."""
        stale_time = datetime.now(timezone.utc) - timedelta(hours=2)
        stale_doc = {
            "rollNo": self.test_roll,
            "type": "marks",
            "subject": "Student Sync — CA Marks Updated",
            "recipient_email": self.recipient,
            "status": "pending",
            "retry_count": 1,
            "created_at": stale_time,
            "updated_at": stale_time,
            "createdAt": stale_time.isoformat()
        }
        res = self.notifs_col.insert_one(stale_doc)
        notif_id = res.inserted_id

        recovered_count = recover_stale_notifications(self.db, threshold_seconds=3600)
        self.assertGreaterEqual(recovered_count, 1)

        doc = self.notifs_col.find_one({"_id": notif_id})
        self.assertEqual(doc["status"], "delivery_uncertain", "Stale record must transition to 'delivery_uncertain'")
        self.assertTrue(doc.get("requires_reconciliation"), "Must require reconciliation")
        self.assertIn("withheld automatic resend", doc.get("error", ""))
        self.assertIsNotNone(doc.get("stale_recovered_at"))

    def test_04_recent_pending_records_untouched(self):
        """Verify recent pending notifications (<1h old) are NOT prematurely modified by the recovery sweep."""
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        recent_doc = {
            "rollNo": self.test_roll,
            "type": "marks",
            "subject": "Student Sync — CA Marks In Flight",
            "recipient_email": self.recipient,
            "status": "pending",
            "created_at": recent_time,
            "updated_at": recent_time,
            "createdAt": recent_time.isoformat()
        }
        res = self.notifs_col.insert_one(recent_doc)
        notif_id = res.inserted_id

        # Sweep with 1 hour threshold (3600s)
        recover_stale_notifications(self.db, threshold_seconds=3600)

        doc = self.notifs_col.find_one({"_id": notif_id})
        self.assertEqual(doc["status"], "pending", "Recent record (<1h old) must remain in 'pending' status")
        self.assertFalse(doc.get("requires_reconciliation", False))

    def test_05_ambiguous_smtp_outcomes_not_blindly_resent(self):
        """Verify recover_stale_notifications NEVER dispatches emails or marks status as 'sent'."""
        stale_time = datetime.now(timezone.utc) - timedelta(hours=3)
        stale_doc = {
            "rollNo": self.test_roll,
            "type": "seating",
            "subject": "Student Sync — Seating Allocated",
            "recipient_email": self.recipient,
            "status": "retrying",
            "retry_count": 2,
            "created_at": stale_time,
            "updated_at": stale_time,
            "createdAt": stale_time.isoformat()
        }
        res = self.notifs_col.insert_one(stale_doc)
        notif_id = res.inserted_id

        with patch.object(_email_sender, 'queue_email') as mock_queue, \
             patch.object(_email_sender, '_send_email_attempt') as mock_attempt:
            recover_stale_notifications(self.db, threshold_seconds=3600)

            # Neither email queueing nor SMTP attempts should ever be invoked
            mock_queue.assert_not_called()
            mock_attempt.assert_not_called()

        doc = self.notifs_col.find_one({"_id": notif_id})
        self.assertNotEqual(doc["status"], "sent", "Ambiguous notification must never be marked as 'sent'")
        self.assertEqual(doc["status"], "delivery_uncertain")

    def test_06_manual_reconciliation_path(self):
        """Verify administrator manual reconciliation transitions delivery_uncertain documents safely."""
        now = datetime.now(timezone.utc)
        uncertain_doc = {
            "rollNo": self.test_roll,
            "type": "results",
            "status": "delivery_uncertain",
            "requires_reconciliation": True,
            "recipient_email": self.recipient,
            "created_at": now - timedelta(hours=2),
            "updated_at": now
        }
        res = self.notifs_col.insert_one(uncertain_doc)
        notif_id = res.inserted_id

        # Verify it shows up in get_unreconciled_notifications
        unrec = get_unreconciled_notifications(self.db)
        unrec_ids = [str(d["_id"]) for d in unrec]
        self.assertIn(str(notif_id), unrec_ids)

        # Action: mark_failed
        ok, msg = reconcile_notification(self.db, notif_id, action="mark_failed", reason="Verified email not delivered")
        self.assertTrue(ok)

        doc = self.notifs_col.find_one({"_id": notif_id})
        self.assertEqual(doc["status"], "failed")
        self.assertFalse(doc.get("requires_reconciliation"))
        self.assertIn("Verified email not delivered", doc.get("error", ""))


if __name__ == '__main__':
    unittest.main(verbosity=2)
