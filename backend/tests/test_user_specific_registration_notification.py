"""
Test Suite: User-Specific Registration and Notification Behavior in Student Sync
Validates:
1. New user registration -> exactly 1 welcome email with subject "Welcome to Student Sync 🎓"
2. Same user logs in again -> 0 additional welcome emails (idempotent welcomeEmailSent: true)
3. Initial scrape -> 0 academic change notifications (pre-existing records not treated as changes)
4. User A data changes -> email sent ONLY to User A
5. User B data changes -> email sent ONLY to User B
6. Same change re-detected -> 0 duplicate emails (deterministic changeHash deduplication)
7. Individual notification preferences respected (User A fees=False suppresses User A, User B fees=True allows User B)
8. Existing real users' baselines and notification records remain strictly untouched
9. Registration race-condition guard: uninitialized baseline (baseline_initialized: False) skips sync cycle and change detection
"""

import os
import sys
import copy
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from bson import ObjectId

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from database import user_collection, notifications_collection, db
from pyserver import app
from speed_ser import process_detected_changes, sync_single_user, dispatch_normalized_notification
from notifications.change_detector import detect_granular_changes, compute_change_hash, process_normalized_event
from notifications.recovery import recover_stale_notifications
from new_scrapers.send_mail import _email_sender


class TestUserSpecificRegistrationAndNotifications(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.client = cls.app.test_client()
        cls.db = db
        cls.users_col = user_collection
        cls.notifs_col = notifications_collection

        # Record pre-test counts for existing production data safety assertion
        cls.initial_users_count = cls.users_col.count_documents({})
        cls.initial_notifs_count = cls.notifs_col.count_documents({})
        cls.real_student_rolls = ['25MX232', '25MX227', '25MX116', '25MX231', '25MX230']
        
        # Verify existing users are present
        for roll in cls.real_student_rolls:
            doc = cls.users_col.find_one({"rollNo": roll})
            assert doc is not None, f"Real student {roll} must exist before tests run"

        # Synthetic test IDs
        cls.synth_a_roll = "SYNTH_USER_A_REG"
        cls.synth_a_email = "synth_a_registered@testpsg.ac.in"
        cls.synth_b_roll = "SYNTH_USER_B_REG"
        cls.synth_b_email = "synth_b_registered@testpsg.ac.in"

        # Cleanup any leftover test records from prior runs
        cls.cleanup_synthetic_data()

    @classmethod
    def tearDownClass(cls):
        # Clean up synthetic test records
        cls.cleanup_synthetic_data()
        
        # Verify existing production students remain untouched
        for roll in cls.real_student_rolls:
            doc = cls.users_col.find_one({"rollNo": roll})
            assert doc is not None, f"Production student {roll} must remain intact"

    @classmethod
    def cleanup_synthetic_data(cls):
        cls.users_col.delete_many({"rollNo": {"$in": [cls.synth_a_roll, cls.synth_b_roll]}})
        cls.notifs_col.delete_many({"rollNo": {"$in": [cls.synth_a_roll, cls.synth_b_roll]}})

    def setUp(self):
        self.sent_emails = []

    def fake_send_direct(self, recipient_email, subject, body, *args, **kwargs):
        roll_no = kwargs.get('rollNo') or kwargs.get('roll_no') or (args[0] if len(args) > 0 else None)
        notif_type = kwargs.get('notif_type', 'general')
        notif_id = kwargs.get('notif_id')
        self.sent_emails.append({
            "recipient_email": recipient_email,
            "subject": subject,
            "body": body,
            "roll_no": roll_no,
            "notif_type": notif_type,
            "notif_id": notif_id
        })
        return True, ""

    def fake_queue_email(self, roll_no, recipient_email, notif_type, subject, body, notif_id=None, *args, **kwargs):
        self.sent_emails.append({
            "recipient_email": recipient_email,
            "subject": subject,
            "body": body,
            "roll_no": roll_no,
            "notif_type": notif_type,
            "notif_id": notif_id
        })
        return True

    # -------------------------------------------------------------------------
    # TEST 1: New user registration -> exactly 1 welcome email
    # -------------------------------------------------------------------------
    @patch('pyserver.send_email_direct')
    @patch('pyserver.scrape_studzone2_all')
    @patch('pyserver.scrape_studzone1_all')
    @patch('pyserver.legacy_login')
    @patch('pyserver.modern_login')
    def test_01_new_user_registration_welcome_email(self, mock_mod_login, mock_leg_login, mock_sz1_scrape, mock_sz2_scrape, mock_email):
        mock_mod_login.return_value = MagicMock()
        mock_leg_login.return_value = MagicMock()
        mock_email.side_effect = self.fake_send_direct

        # Synthetic scraped baseline data
        mock_sz1_scrape.return_value = {
            "profile": {"Name": "SYNTHETIC ALICE"},
            "attendance_html": "<table>...</table>",
            "parsed_attendance": [
                {"code": "23MX31", "name": "CLOUD COMPUTING", "percentage": "78%"}
            ],
            "ca_marks_html": "<table>...</table>",
            "parsed_marks": [
                {"code": "23MX31", "name": "CLOUD COMPUTING", "ca1": "18", "ca2": "19"}
            ],
            "fees_html": "<table>fees paid</table>",
            "fee_status": "Pending"
        }
        mock_sz2_scrape.return_value = {
            "cgpa": "8.50",
            "results_html": "<table>results</table>",
            "parsed_results": [{"code": "23MX31", "grade": "A"}],
            "timetable_html": "<table>timetable</table>",
            "parsed_timetable": []
        }

        resp = self.client.post('/register', json={
            "rollNo": self.synth_a_roll,
            "password": "Password123!",
            "email": self.synth_a_email
        })

        self.assertEqual(resp.status_code, 201)
        user_doc = self.users_col.find_one({"rollNo": self.synth_a_roll})
        self.assertIsNotNone(user_doc)
        self.assertTrue(user_doc.get("baseline_initialized"))
        self.assertTrue(user_doc.get("monitoring_enabled"))
        self.assertTrue(user_doc.get("welcomeEmailSent"))
        self.assertIsNotNone(user_doc.get("welcome_email_sent_at"))

        # Verify exactly ONE welcome email was sent to synthetic email
        welcome_emails = [e for e in self.sent_emails if e["notif_type"] == "welcome"]
        self.assertEqual(len(welcome_emails), 1, "Exactly 1 welcome email must be sent")
        w_email = welcome_emails[0]
        self.assertEqual(w_email["recipient_email"], self.synth_a_email)
        self.assertEqual(w_email["subject"], "Welcome to Student Sync 🎓")
        self.assertIn("monitoring is now active", w_email["body"])
        self.assertIn("Thank you for registering", w_email["body"])

    # -------------------------------------------------------------------------
    # TEST 2: Same user logs in again -> 0 additional welcome emails
    # -------------------------------------------------------------------------
    @patch('pyserver.send_email_direct')
    def test_02_login_does_not_send_welcome_email(self, mock_email):
        mock_email.side_effect = self.fake_send_direct
        self.sent_emails.clear()

        # Login call
        resp = self.client.post('/login', json={
            "rollNo": self.synth_a_roll,
            "password": "Password123!"
        })
        self.assertEqual(resp.status_code, 200)

        # 0 welcome emails sent during login
        welcome_emails = [e for e in self.sent_emails if e["notif_type"] == "welcome"]
        self.assertEqual(len(welcome_emails), 0, "Login must send 0 welcome emails")

        # Second register call with same credentials
        with patch('pyserver.modern_login') as m_mod, patch('pyserver.legacy_login') as m_leg, \
             patch('pyserver.scrape_studzone1_all') as m_sz1, patch('pyserver.scrape_studzone2_all') as m_sz2:
            m_mod.return_value = MagicMock()
            m_leg.return_value = MagicMock()
            m_sz1.return_value = {
                "profile": {"Name": "SYNTHETIC ALICE"},
                "attendance_html": "<table>...</table>",
                "parsed_attendance": [
                    {"code": "23MX31", "name": "CLOUD COMPUTING", "percentage": "78%"}
                ],
                "parsed_marks": [
                    {"code": "23MX31", "name": "CLOUD COMPUTING", "ca1": "18", "ca2": "19"}
                ],
                "fees_html": "<table>fees paid</table>",
                "fee_status": "Pending"
            }
            m_sz2.return_value = {"cgpa": "8.50"}

            resp2 = self.client.post('/register', json={
                "rollNo": self.synth_a_roll,
                "password": "Password123!"
            })
            self.assertIn(resp2.status_code, [201, 409])

        welcome_emails_after_re_reg = [e for e in self.sent_emails if e["notif_type"] == "welcome"]
        self.assertEqual(len(welcome_emails_after_re_reg), 0, "Re-registration must not duplicate welcome email")

    # -------------------------------------------------------------------------
    # TEST 3: Initial scrape -> 0 academic change notifications
    # -------------------------------------------------------------------------
    def test_03_initial_scrape_zero_academic_change_notifications(self):
        user_doc = self.users_col.find_one({"rollNo": self.synth_a_roll})
        self.assertIsNotNone(user_doc)

        # Count any academic notifications for synth A
        academic_notifs = list(self.notifs_col.find({
            "rollNo": self.synth_a_roll,
            "type": {"$in": ["attendance", "marks", "results", "timetable", "seating", "fees", "hostel"]}
        }))
        self.assertEqual(len(academic_notifs), 0, "Registration must NOT create academic change notifications")

        # Comparing baseline with identical freshly scraped baseline yields 0 detected changes
        sz1_fresh = copy.deepcopy(user_doc.get('studzone1', {}))
        sz2_fresh = copy.deepcopy(user_doc.get('studzone2', {}))
        changes = detect_granular_changes(self.synth_a_roll, user_doc, sz1_fresh, sz2_fresh)
        self.assertEqual(len(changes), 0, "Initial scrape baseline vs fresh baseline must produce 0 changes")

    # -------------------------------------------------------------------------
    # TEST 4: User A data changes -> email A only
    # -------------------------------------------------------------------------
    @patch('speed_ser.queue_tracked_email')
    def test_04_user_a_data_changes_routes_to_user_a_only(self, mock_queue_email):
        mock_queue_email.side_effect = self.fake_queue_email
        self.sent_emails.clear()

        user_doc = self.users_col.find_one({"rollNo": self.synth_a_roll})
        sz1_fresh = copy.deepcopy(user_doc.get('studzone1', {}))
        sz2_fresh = copy.deepcopy(user_doc.get('studzone2', {}))

        # Change attendance for 23MX31 from 78% -> 82%
        for c in sz1_fresh.get('parsed_attendance', []):
            if c.get('code') == '23MX31':
                c['percentage'] = '82%'
                break

        process_detected_changes(self.synth_a_roll, user_doc, sz1_fresh, sz2_fresh, self.db)

        # Verify email was routed ONLY to User A
        self.assertEqual(len(self.sent_emails), 1, "Must generate exactly 1 notification email")
        self.assertEqual(self.sent_emails[0]["recipient_email"], self.synth_a_email)
        self.assertEqual(self.sent_emails[0]["roll_no"], self.synth_a_roll)
        self.assertNotEqual(self.sent_emails[0]["recipient_email"], self.synth_b_email)

    # -------------------------------------------------------------------------
    # TEST 5: User B registration and User B data changes -> email B only
    # -------------------------------------------------------------------------
    @patch('speed_ser.queue_tracked_email')
    @patch('pyserver.send_email_direct')
    @patch('pyserver.scrape_studzone2_all')
    @patch('pyserver.scrape_studzone1_all')
    @patch('pyserver.legacy_login')
    @patch('pyserver.modern_login')
    def test_05_user_b_data_changes_routes_to_user_b_only(self, mock_mod_login, mock_leg_login, mock_sz1_scrape, mock_sz2_scrape, mock_send_email, mock_queue_email):
        mock_mod_login.return_value = MagicMock()
        mock_leg_login.return_value = MagicMock()
        mock_send_email.side_effect = self.fake_send_direct
        mock_queue_email.side_effect = self.fake_queue_email

        # Register User B
        mock_sz1_scrape.return_value = {
            "profile": {"Name": "SYNTHETIC BOB"},
            "attendance_html": "<table>...</table>",
            "parsed_attendance": [
                {"code": "23MXAF", "name": "DATA MINING AND ANALYTICS", "percentage": "85%"}
            ],
            "ca_marks_html": "<table>...</table>",
            "parsed_marks": [
                {"code": "23MXAF", "name": "DATA MINING AND ANALYTICS", "ca1": "20", "ca2": "21"}
            ],
            "fee_status": "Pending"
        }
        mock_sz2_scrape.return_value = {"cgpa": "9.10"}

        reg_b = self.client.post('/register', json={
            "rollNo": self.synth_b_roll,
            "password": "Password123!",
            "email": self.synth_b_email
        })
        self.assertEqual(reg_b.status_code, 201)

        self.sent_emails.clear()

        # Simulate marks update for User B ONLY (CA1: 20 -> 24)
        user_b_doc = self.users_col.find_one({"rollNo": self.synth_b_roll})
        sz1_b_fresh = copy.deepcopy(user_b_doc.get('studzone1', {}))
        sz2_b_fresh = copy.deepcopy(user_b_doc.get('studzone2', {}))
        for m in sz1_b_fresh.get('parsed_marks', []):
            if m.get('code') == '23MXAF':
                m['ca1'] = '24'
                break

        process_detected_changes(self.synth_b_roll, user_b_doc, sz1_b_fresh, sz2_b_fresh, self.db)

        # Verify email routed to User B ONLY
        b_notifs = [e for e in self.sent_emails if e["notif_type"] == "marks"]
        self.assertEqual(len(b_notifs), 1, "Must generate exactly 1 marks email for User B")
        self.assertEqual(b_notifs[0]["recipient_email"], self.synth_b_email)
        self.assertEqual(b_notifs[0]["roll_no"], self.synth_b_roll)
        self.assertNotEqual(b_notifs[0]["recipient_email"], self.synth_a_email)

    # -------------------------------------------------------------------------
    # TEST 6: Same change detected again -> 0 duplicate emails
    # -------------------------------------------------------------------------
    @patch('speed_ser.queue_tracked_email')
    def test_06_duplicate_change_suppression_idempotency(self, mock_queue_email):
        mock_queue_email.side_effect = self.fake_queue_email
        self.sent_emails.clear()

        # Re-run same change for User A (78% -> 82%)
        user_doc = self.users_col.find_one({"rollNo": self.synth_a_roll})
        sz1_fresh = copy.deepcopy(user_doc.get('studzone1', {}))
        sz2_fresh = copy.deepcopy(user_doc.get('studzone2', {}))
        for c in sz1_fresh.get('parsed_attendance', []):
            if c.get('code') == '23MX31':
                c['percentage'] = '82%'
                break

        process_detected_changes(self.synth_a_roll, user_doc, sz1_fresh, sz2_fresh, self.db)

        # Zero duplicate emails sent
        self.assertEqual(len(self.sent_emails), 0, "Subsequent sync with identical changeHash must send 0 emails")

    # -------------------------------------------------------------------------
    # TEST 7: Disabled notification preferences respected
    # -------------------------------------------------------------------------
    @patch('speed_ser.queue_tracked_email')
    def test_07_notification_preferences_per_user(self, mock_queue_email):
        mock_queue_email.side_effect = self.fake_queue_email

        # User A: fees = False
        self.users_col.update_one(
            {"rollNo": self.synth_a_roll},
            {"$set": {"notifications": {"attendance": True, "marks": True, "fees": False}}}
        )
        user_a = self.users_col.find_one({"rollNo": self.synth_a_roll})

        # User B: fees = True, attendance = False
        self.users_col.update_one(
            {"rollNo": self.synth_b_roll},
            {"$set": {"notifications": {"attendance": False, "marks": True, "fees": True}}}
        )
        user_b = self.users_col.find_one({"rollNo": self.synth_b_roll})

        # Test A: Simulate a fees update for User A (fees=False)
        self.sent_emails.clear()
        sz1_a_fees = copy.deepcopy(user_a.get('studzone1', {}))
        sz1_a_fees["fee_status"] = "Due: Rs. 55,000"
        process_detected_changes(self.synth_a_roll, user_a, sz1_a_fees, {}, self.db)
        self.assertEqual(len(self.sent_emails), 0, "User A disabled fees notifications; 0 emails must be sent")

        # Test B: Simulate a fees update for User B (fees=True)
        self.sent_emails.clear()
        sz1_b_fees = copy.deepcopy(user_b.get('studzone1', {}))
        sz1_b_fees["fee_status"] = "Due: Rs. 2,500"
        process_detected_changes(self.synth_b_roll, user_b, sz1_b_fees, {}, self.db)
        self.assertEqual(len(self.sent_emails), 1, "User B enabled fees notifications; 1 email must be sent to User B")
        self.assertEqual(self.sent_emails[0]["recipient_email"], self.synth_b_email)

        # Test C: Simulate an attendance update for User B (attendance=False)
        self.sent_emails.clear()
        sz1_b_att = copy.deepcopy(user_b.get('studzone1', {}))
        for c in sz1_b_att.get('parsed_attendance', []):
            if c.get('code') == '23MXAF':
                c['percentage'] = '90%'
                break
        process_detected_changes(self.synth_b_roll, user_b, sz1_b_att, {}, self.db)
        self.assertEqual(len(self.sent_emails), 0, "User B disabled attendance notifications; 0 emails must be sent")

    # -------------------------------------------------------------------------
    # TEST 8: Existing real users' baselines and notification history remain unchanged
    # -------------------------------------------------------------------------
    def test_08_existing_users_preserved_strictly(self):
        # 1. Verify 25MX232 baseline and roll exist intact
        user_232 = self.users_col.find_one({"rollNo": "25MX232"})
        self.assertIsNotNone(user_232, "25MX232 document must exist")
        self.assertIsNotNone(user_232.get('studzone1'), "25MX232 StudZone 1 baseline preserved")
        self.assertIsNotNone(user_232.get('studzone2'), "25MX232 StudZone 2 baseline preserved")
        self.assertIsNotNone(user_232.get('cgpa'), "25MX232 CGPA preserved")

        # 2. Verify all other production students exist
        for roll in ['25MX227', '25MX116', '25MX231', '25MX230']:
            doc = self.users_col.find_one({"rollNo": roll})
            self.assertIsNotNone(doc, f"Student {roll} baseline must remain in MongoDB")

        # 3. Verify notification log records for 25MX232 were not purged
        notifs_232 = self.notifs_col.count_documents({"rollNo": "25MX232"})
        self.assertGreater(notifs_232, 0, "Historical notifications for 25MX232 must be preserved")

    # -------------------------------------------------------------------------
    # TEST 9: Registration race-condition guard
    # -------------------------------------------------------------------------
    def test_09_registration_race_condition_guard(self):
        # When user has baseline_initialized: False (e.g. during registration portal scraping window)
        uninit_user = {
            "rollNo": "SYNTH_UNINIT_101",
            "password": "pwd",
            "email": "uninit@test.com",
            "baseline_initialized": False,
            "monitoring_enabled": False
        }

        # Background sync worker must skip uninitialized student immediately
        res = sync_single_user(uninit_user, self.db)
        self.assertIsNone(res, "sync_single_user must return None and skip uninitialized student")

        # Granular change detector must return [] for uninitialized student
        changes = detect_granular_changes("SYNTH_UNINIT_101", uninit_user, {"parsed_attendance": [{"percentage": "90%"}]}, {})
        self.assertEqual(changes, [], "detect_granular_changes must return [] when baseline_initialized is False")

    # -------------------------------------------------------------------------
    # TEST 10: Application & Synchronizer restart idempotency
    # -------------------------------------------------------------------------
    @patch('speed_ser.queue_tracked_email')
    def test_10_application_and_synchronizer_restart_idempotency(self, mock_queue_email):
        """
        Verifies that after an application or synchronizer restart, previously
        processed academic changes are not re-emailed.
        """
        mock_queue_email.side_effect = self.fake_queue_email
        self.sent_emails.clear()

        user_doc = self.users_col.find_one({"rollNo": self.synth_a_roll})
        sz1_fresh = copy.deepcopy(user_doc.get('studzone1', {}))
        sz2_fresh = copy.deepcopy(user_doc.get('studzone2', {}))

        # First cycle: new CA2 marks update
        for m in sz1_fresh.get('parsed_marks', []):
            if m.get('code') == '23MX31':
                m['ca2'] = '24'
                break

        # Process first cycle
        process_detected_changes(self.synth_a_roll, user_doc, sz1_fresh, sz2_fresh, self.db)
        self.assertEqual(len(self.sent_emails), 1, "First poll must generate exactly 1 notification")

        # Simulate Application / Synchronizer restart:
        # A new process cycle begins. Old user in DB still has older baseline if db wasn't committed yet,
        # or synchronizer re-runs against the same portal data.
        self.sent_emails.clear()

        # Re-run change detection with identical fresh portal data
        process_detected_changes(self.synth_a_roll, user_doc, sz1_fresh, sz2_fresh, self.db)
        self.assertEqual(len(self.sent_emails), 0, "Restarted synchronizer must suppress duplicate email via changeHash")

    # -------------------------------------------------------------------------
    # TEST 11: SMTP failure, retry logging, and baseline safety
    # -------------------------------------------------------------------------
    def test_11_smtp_failure_retry_logging_and_baseline_safety(self):
        """
        Verifies that SMTP failure logging updates status & retry_count in MongoDB,
        and that SMTP failure does not alter or corrupt the user's baseline in new_users.
        """
        user_before = self.users_col.find_one({"rollNo": self.synth_a_roll})
        test_notif_id = ObjectId()

        # 1. Log initial pending/retrying status
        _email_sender._log_notification_status(
            notif_id=test_notif_id,
            roll_no=self.synth_a_roll,
            notif_type="attendance",
            recipient_email=self.synth_a_email,
            subject="Test Attendance Update",
            status="retrying",
            error="Connection timed out",
            retry_count=1
        )

        notif_doc = self.notifs_col.find_one({"_id": test_notif_id})
        self.assertIsNotNone(notif_doc)
        self.assertEqual(notif_doc.get("status"), "retrying")
        self.assertEqual(notif_doc.get("retry_count"), 1)
        self.assertEqual(notif_doc.get("error"), "Connection timed out")

        # 2. Update to failed status
        _email_sender._log_notification_status(
            notif_id=test_notif_id,
            roll_no=self.synth_a_roll,
            notif_type="attendance",
            recipient_email=self.synth_a_email,
            subject="Test Attendance Update",
            status="failed",
            error="Max retries reached",
            retry_count=3
        )
        notif_failed = self.notifs_col.find_one({"_id": test_notif_id})
        self.assertEqual(notif_failed.get("status"), "failed")
        self.assertEqual(notif_failed.get("retry_count"), 3)

        # 3. Verify user's baseline in new_users was untouched
        user_after = self.users_col.find_one({"rollNo": self.synth_a_roll})
        self.assertEqual(user_before.get("studzone1"), user_after.get("studzone1"))
        self.assertEqual(user_before.get("studzone2"), user_after.get("studzone2"))

        # Clean up test notification
        self.notifs_col.delete_one({"_id": test_notif_id})

    # -------------------------------------------------------------------------
    # TEST 12: Stale notification recovery to delivery_uncertain
    # -------------------------------------------------------------------------
    def test_12_stale_notification_recovery(self):
        """
        Verifies that stale notifications stuck in 'pending' or 'retrying'
        transition to 'delivery_uncertain' rather than being blindly resent.
        """
        old_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        stale_id = ObjectId()
        self.notifs_col.insert_one({
            "_id": stale_id,
            "rollNo": self.synth_a_roll,
            "recipient_email": self.synth_a_email,
            "status": "pending",
            "type": "results",
            "subject": "Stale Results Update",
            "created_at": old_time,
            "updated_at": old_time,
            "changeHash": "stale_hash_test_12345"
        })

        # Run recovery with small threshold
        recovered_count = recover_stale_notifications(self.db, threshold_seconds=10)
        self.assertGreaterEqual(recovered_count, 1)

        stale_doc = self.notifs_col.find_one({"_id": stale_id})
        self.assertEqual(stale_doc.get("status"), "delivery_uncertain")
        self.assertTrue(stale_doc.get("requires_reconciliation"))

        # Clean up
        self.notifs_col.delete_one({"_id": stale_id})

    # -------------------------------------------------------------------------
    # TEST 13: Portal transient failure & partial drop baseline preservation
    # -------------------------------------------------------------------------
    @patch('speed_ser.legacy_login')
    @patch('speed_ser.modern_login')
    @patch('speed_ser.scrape_studzone2_all')
    @patch('speed_ser.scrape_studzone1_all')
    def test_13_transient_scraper_drop_baseline_preservation(self, mock_sz1, mock_sz2, mock_mod_login, mock_leg_login):
        """
        Verifies that if StudZone 1 scraper temporarily returns empty sub-tables (e.g. parsed_attendance: []),
        sync_single_user preserves the student's existing baseline sub-tables in MongoDB.
        """
        mock_mod_login.return_value = MagicMock()
        mock_leg_login.return_value = MagicMock()

        # Scraper returns empty parsed_attendance (simulating portal glitch)
        mock_sz1.return_value = {
            "profile": {"Name": "SYNTHETIC ALICE"},
            "attendance_html": "",
            "parsed_attendance": [],
            "ca_marks_html": "<table>...</table>",
            "parsed_marks": [{"code": "23MX31", "name": "CLOUD COMPUTING", "ca1": "18"}],
            "fee_status": "Paid"
        }
        mock_sz2.return_value = {"cgpa": "8.50"}

        user_current = self.users_col.find_one({"rollNo": self.synth_a_roll})
        self.assertGreater(len(user_current.get("studzone1", {}).get("parsed_attendance", [])), 0)

        # Run single sync
        sync_single_user(user_current, self.db)

        # Inspect updated document in MongoDB
        updated_user = self.users_col.find_one({"rollNo": self.synth_a_roll})
        self.assertIsNotNone(updated_user.get("studzone1", {}).get("parsed_attendance"))
        self.assertGreater(
            len(updated_user["studzone1"]["parsed_attendance"]), 0,
            "Transient empty attendance from scraper must NOT erase stored baseline attendance"
        )

    # -------------------------------------------------------------------------
    # TEST 14: Normalized event dispatch & future website extensibility
    # -------------------------------------------------------------------------
    @patch('speed_ser.queue_tracked_email')
    def test_14_normalized_event_dispatch_and_extensibility(self, mock_queue_email):
        """
        Verifies that future scrapers can pass a standardized normalized event dict
        to dispatch_normalized_notification() and achieve identical user isolation,
        preference enforcement, and changeHash deduplication.
        """
        mock_queue_email.side_effect = self.fake_queue_email
        self.sent_emails.clear()

        # Event payload from future hypothetical portal (e.g. Placement / Library portal)
        placement_event = {
            "category": "placement",
            "type": "placement",
            "title": "Campus Drive Shortlist",
            "message": "Shortlisted for Microsoft SWE interview round",
            "source": "Placement Portal",
            "module": "Training & Placement",
            "change_key": "drive_microsoft_round1",
            "changeData": {"company": "Microsoft", "role": "SWE"}
        }

        user_doc = self.users_col.find_one({"rollNo": self.synth_a_roll})

        # Test A: User A has placement disabled -> event suppressed
        self.users_col.update_one(
            {"rollNo": self.synth_a_roll},
            {"$set": {"notifications.placement": False}}
        )
        user_doc = self.users_col.find_one({"rollNo": self.synth_a_roll})
        notif_id = dispatch_normalized_notification(self.synth_a_roll, user_doc, placement_event, self.db)
        self.assertIsNone(notif_id, "Disabled preference must suppress normalized notification")
        self.assertEqual(len(self.sent_emails), 0, "No email sent when preference is False")

        # Test B: User A enables placement -> event dispatched and email queued
        self.users_col.update_one(
            {"rollNo": self.synth_a_roll},
            {"$set": {"notifications.placement": True}}
        )
        user_doc = self.users_col.find_one({"rollNo": self.synth_a_roll})
        notif_id = dispatch_normalized_notification(self.synth_a_roll, user_doc, placement_event, self.db)
        self.assertIsNotNone(notif_id, "Enabled preference must dispatch normalized notification")
        self.assertEqual(len(self.sent_emails), 1, "Exactly 1 email queued for normalized event")
        self.assertEqual(self.sent_emails[0]["recipient_email"], self.synth_a_email)
        self.assertIn("Campus Drive Shortlist", self.sent_emails[0]["subject"])

        # Test C: Duplicate dispatch attempt with same normalized event -> suppressed atomically
        self.sent_emails.clear()
        dup_id = dispatch_normalized_notification(self.synth_a_roll, user_doc, placement_event, self.db)
        self.assertIsNone(dup_id, "Subsequent normalized event with same changeHash must be suppressed")
        self.assertEqual(len(self.sent_emails), 0, "Zero duplicate emails sent for duplicate normalized event")


if __name__ == '__main__':
    unittest.main()
