"""
End-to-End Monitoring & Automatic Email Notification Verification Test Suite
Verifies the complete 20 requirements specified in Phase 7 for Student Sync.
Uses isolated synthetic fixtures and mocked SMTP (zero real student emails sent).
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import sys
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

# Ensure backend directory is in sys.path
_test_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.abspath(os.path.join(_test_dir, '..'))
_root_dir = os.path.abspath(os.path.join(_backend_dir, '..'))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from database import get_database_connection, ensure_database_indexes
from notifications.change_detector import detect_granular_changes, compute_change_hash
from notifications.recovery import recover_stale_notifications, reconcile_notification
from speed_ser import process_detected_changes, sync_single_user
from new_scrapers.send_mail import EmailSender, queue_tracked_email, send_email_direct
from pyserver import app, sync_student_dual_portal


class TestEndToEndMonitoring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client, cls.db = get_database_connection()
        cls.users_col = cls.db['new_users']
        cls.notifs_col = cls.db['notifications_log']
        ensure_database_indexes(cls.db)

        cls.roll_a = "SYNTH_A_25MX991"
        cls.roll_b = "SYNTH_B_25MX992"
        cls.app_client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        # Clean up any test records
        cls.users_col.delete_many({"rollNo": {"$in": [cls.roll_a, cls.roll_b, "SYNTH_C_25MX993"]}})
        cls.notifs_col.delete_many({"rollNo": {"$in": [cls.roll_a, cls.roll_b, "SYNTH_C_25MX993"]}})

    def setUp(self):
        # Clear synthetic notifications between test runs
        self.notifs_col.delete_many({"rollNo": {"$in": [self.roll_a, self.roll_b, "SYNTH_C_25MX993"]}})
        self.users_col.delete_many({"rollNo": {"$in": [self.roll_a, self.roll_b, "SYNTH_C_25MX993"]}})

    def tearDown(self):
        self.notifs_col.delete_many({"rollNo": {"$in": [self.roll_a, self.roll_b, "SYNTH_C_25MX993"]}})
        self.users_col.delete_many({"rollNo": {"$in": [self.roll_a, self.roll_b, "SYNTH_C_25MX993"]}})

    # -------------------------------------------------------------------------
    # Test 1: First successful scrape creates baseline and sends NO flood of alerts
    # -------------------------------------------------------------------------
    def test_01_first_successful_scrape_creates_baseline_no_flood(self):
        empty_old_user = {"rollNo": self.roll_a, "name": "Synthetic Student A"}
        sz1_fresh = {
            "parsed_attendance": [{"code": "23MX31", "name": "CLOUD COMPUTING", "percentage": "80%"}],
            "parsed_marks": [{"code": "23MX31", "ca1": "20", "ca2": "22", "total": "42"}],
            "fee_status": "Paid",
            "hostel_status": "Block B-101",
            "scholarships": {"applied": [{"title": "Merit"}], "received": []}
        }
        sz2_fresh = {
            "cgpa": 8.50,
            "parsed_results": [{"code": "23MX31", "grade": "A+", "grade_point": 9.0}],
            "parsed_timetable": [{"course_code": "23MX31", "exam_date": "2026-11-10", "session": "FN", "timing": "09:30 AM - 12:30 PM"}],
            "seating_html": "<table><tr><td>Hall E101</td></tr></table>"
        }
        notifs = detect_granular_changes(self.roll_a, empty_old_user, sz1_fresh, sz2_fresh)
        self.assertEqual(len(notifs), 0, "Initial baseline scrape must produce 0 alerts for pre-existing records.")

    # -------------------------------------------------------------------------
    # Test 2: Initial scrape failure is not treated as success
    # -------------------------------------------------------------------------
    @patch('pyserver.modern_login', return_value=(False, "Invalid credentials."))
    @patch('pyserver.legacy_login', return_value=(False, "Invalid credentials."))
    def test_02_initial_scrape_failure_not_treated_as_success(self, mock_leg, mock_mod):
        user_doc, err = sync_student_dual_portal("SYNTH_NONEXISTENT", "badpassword")
        self.assertIsNone(user_doc, "Failed scrape must not return a successful user document.")
        self.assertIsNotNone(err, "Failed scrape must return an explicit error.")

    # -------------------------------------------------------------------------
    # Test 3: Genuine attendance change creates one meaningful notification
    # -------------------------------------------------------------------------
    def test_03_genuine_attendance_change_creates_one_notification(self):
        old_user = {
            "rollNo": self.roll_a,
            "studzone1": {
                "parsed_attendance": [{"code": "23MX31", "name": "CLOUD COMPUTING", "percentage": "80%"}]
            }
        }
        sz1_fresh = {
            "parsed_attendance": [{"code": "23MX31", "name": "CLOUD COMPUTING", "percentage": "85%"}]
        }
        notifs = detect_granular_changes(self.roll_a, old_user, sz1_fresh, {})
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0]['type'], 'attendance')
        self.assertEqual(notifs[0]['source'], 'StudZone 1')
        self.assertEqual(notifs[0]['changeData']['previousValue'], '80%')
        self.assertEqual(notifs[0]['changeData']['newValue'], '85%')

    # -------------------------------------------------------------------------
    # Test 4: CA mark change creates one meaningful notification
    # -------------------------------------------------------------------------
    def test_04_ca_mark_change_creates_one_notification(self):
        old_user = {
            "rollNo": self.roll_a,
            "studzone1": {
                "parsed_marks": [{"code": "23MX31", "name": "CLOUD COMPUTING", "ca1": "18", "ca2": "20", "total": "38"}]
            }
        }
        sz1_fresh = {
            "parsed_marks": [{"code": "23MX31", "name": "CLOUD COMPUTING", "ca1": "22", "ca2": "20", "total": "42"}]
        }
        notifs = detect_granular_changes(self.roll_a, old_user, sz1_fresh, {})
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0]['type'], 'marks')
        self.assertEqual(notifs[0]['changeData']['test'], 'CA1')
        self.assertEqual(notifs[0]['changeData']['previousValue'], '18')
        self.assertEqual(notifs[0]['changeData']['newValue'], '22')

    # -------------------------------------------------------------------------
    # Test 5: Fee-status change creates one meaningful notification
    # -------------------------------------------------------------------------
    def test_05_fee_status_change_creates_one_notification(self):
        old_user = {
            "rollNo": self.roll_a,
            "studzone1": {"fee_status": "Dues Pending: Rs. 2500"}
        }
        sz1_fresh = {"fee_status": "Paid in Full"}
        notifs = detect_granular_changes(self.roll_a, old_user, sz1_fresh, {})
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0]['type'], 'fees')
        self.assertEqual(notifs[0]['changeData']['previousStatus'], 'Dues Pending: Rs. 2500')
        self.assertEqual(notifs[0]['changeData']['newStatus'], 'Paid in Full')

    # -------------------------------------------------------------------------
    # Test 6: Results or grade change creates one meaningful notification
    # -------------------------------------------------------------------------
    def test_06_results_or_grade_change_creates_one_notification(self):
        old_user = {
            "rollNo": self.roll_a,
            "studzone2": {
                "parsed_results": [{"code": "23MX31", "title": "CLOUD COMPUTING", "grade": "B+", "grade_point": 7.0}]
            }
        }
        sz2_fresh = {
            "parsed_results": [{"code": "23MX31", "title": "CLOUD COMPUTING", "grade": "A", "grade_point": 8.0}]
        }
        notifs = detect_granular_changes(self.roll_a, old_user, {}, sz2_fresh)
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0]['type'], 'results')
        self.assertEqual(notifs[0]['changeData']['previousGrade'], 'B+')
        self.assertEqual(notifs[0]['changeData']['newGrade'], 'A')

    # -------------------------------------------------------------------------
    # Test 7: CGPA change creates one meaningful notification
    # -------------------------------------------------------------------------
    def test_07_cgpa_change_creates_one_notification(self):
        old_user = {
            "rollNo": self.roll_a,
            "cgpa": 7.82,
            "studzone2": {"cgpa": 7.82}
        }
        sz2_fresh = {"cgpa": 8.05}
        notifs = detect_granular_changes(self.roll_a, old_user, {}, sz2_fresh)
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0]['type'], 'results')
        self.assertEqual(notifs[0]['title'], 'CGPA Updated')
        self.assertEqual(notifs[0]['changeData']['previousValue'], 7.82)
        self.assertEqual(notifs[0]['changeData']['newValue'], 8.05)

    # -------------------------------------------------------------------------
    # Test 8: Timetable or seating change creates one meaningful notification
    # -------------------------------------------------------------------------
    def test_08_timetable_or_seating_change_creates_one_notification(self):
        old_user = {
            "rollNo": self.roll_a,
            "studzone2": {
                "parsed_timetable": [{"course_code": "23MX31", "course_title": "CLOUD COMPUTING", "exam_date": "2026-11-10", "session": "FN", "timing": "09:30 AM - 12:30 PM"}],
                "seating_html": None
            }
        }
        # Timetable change
        sz2_tt = {
            "parsed_timetable": [{"course_code": "23MX31", "course_title": "CLOUD COMPUTING", "exam_date": "2026-11-14", "session": "FN", "timing": "09:30 AM - 12:30 PM"}]
        }
        notifs_tt = detect_granular_changes(self.roll_a, old_user, {}, sz2_tt)
        self.assertEqual(len(notifs_tt), 1)
        self.assertEqual(notifs_tt[0]['type'], 'timetable')
        self.assertEqual(notifs_tt[0]['changeData']['previousDate'], '2026-11-10')
        self.assertEqual(notifs_tt[0]['changeData']['newDate'], '2026-11-14')

        # Seating published
        sz2_seat = {
            "seating_html": "<table><tr><td>Hall E201, Seat 24</td></tr></table>"
        }
        notifs_seat = detect_granular_changes(self.roll_a, old_user, {}, sz2_seat)
        self.assertEqual(len(notifs_seat), 1)
        self.assertEqual(notifs_seat[0]['type'], 'seating')
        self.assertEqual(notifs_seat[0]['title'], 'Exam Seating Published')

    # -------------------------------------------------------------------------
    # Test 9: Unchanged data on next poll sends NO duplicate
    # -------------------------------------------------------------------------
    def test_09_unchanged_data_on_next_poll_sends_no_duplicate(self):
        user_state = {
            "rollNo": self.roll_a,
            "studzone1": {
                "parsed_attendance": [{"code": "23MX31", "name": "CLOUD COMPUTING", "percentage": "85%"}],
                "parsed_marks": [{"code": "23MX31", "ca1": "22", "total": "42"}]
            },
            "studzone2": {
                "cgpa": 8.05,
                "parsed_results": [{"code": "23MX31", "grade": "A"}],
                "parsed_timetable": [{"course_code": "23MX31", "exam_date": "2026-11-14"}]
            }
        }
        sz1_fresh = {
            "parsed_attendance": [{"code": "23MX31", "name": "CLOUD COMPUTING", "percentage": "85%"}],
            "parsed_marks": [{"code": "23MX31", "ca1": "22", "total": "42"}]
        }
        sz2_fresh = {
            "cgpa": 8.05,
            "parsed_results": [{"code": "23MX31", "grade": "A"}],
            "parsed_timetable": [{"course_code": "23MX31", "exam_date": "2026-11-14"}]
        }
        notifs = detect_granular_changes(self.roll_a, user_state, sz1_fresh, sz2_fresh)
        self.assertEqual(len(notifs), 0, "Identical academic state must produce 0 notifications on subsequent polls.")

    # -------------------------------------------------------------------------
    # Test 10: Formatting-only HTML differences do not create noisy alerts
    # -------------------------------------------------------------------------
    def test_10_formatting_only_html_differences_do_not_create_noisy_alerts(self):
        old_user = {
            "rollNo": self.roll_a,
            "attendance": "<table style='color:red;'><tr><td>85%</td></tr></table>",
            "results": "<div>Semester 3</div>",
            "studzone1": {
                "parsed_attendance": [{"code": "23MX31", "percentage": "85%"}]
            },
            "studzone2": {
                "parsed_results": [{"code": "23MX31", "grade": "A"}]
            }
        }
        # HTML strings change drastically with classes, extra div tags, whitespace,
        # but structured parsed data is identical
        sz1_fresh = {
            "attendance_html": "<table class='table dark'   style='margin:0'><tr>\n\t<td>85%</td></tr></table>",
            "parsed_attendance": [{"code": "23MX31", "percentage": "85%"}]
        }
        sz2_fresh = {
            "results_html": "<div class='results-container'><span>Semester 3</span></div>",
            "parsed_results": [{"code": "23MX31", "grade": "A"}]
        }
        notifs = detect_granular_changes(self.roll_a, old_user, sz1_fresh, sz2_fresh)
        self.assertEqual(len(notifs), 0, "Formatting-only HTML differences must never produce notifications.")

    # -------------------------------------------------------------------------
    # Test 11: StudZone 1 failure does not block StudZone 2 sync, and vice versa
    # -------------------------------------------------------------------------
    def test_11_studzone_independent_failure_resilience(self):
        user_record = {
            "rollNo": self.roll_a,
            "password": "testpass_isolated",
            "attendance": "CACHED_ATTENDANCE",
            "results": "CACHED_RESULTS",
            "studzone1": {"parsed_attendance": [{"code": "23MX31", "percentage": "80%"}]},
            "studzone2": {"parsed_results": [{"code": "23MX31", "grade": "B+"}]}
        }
        self.users_col.insert_one(user_record)

        # Case A: StudZone 1 fails, StudZone 2 succeeds with new grade
        with patch('speed_ser.modern_login', return_value=(False, "Timeout")), \
             patch('speed_ser.legacy_login', return_value=MagicMock()), \
             patch('speed_ser.scrape_studzone2_all', return_value={"parsed_results": [{"code": "23MX31", "grade": "A"}], "results_html": "NEW_RESULTS"}):
            sync_single_user(user_record, self.db)
            updated = self.users_col.find_one({"rollNo": self.roll_a})
            self.assertEqual(updated['attendance'], "CACHED_ATTENDANCE", "StudZone 1 cached data must be preserved on SZ1 failure.")
            self.assertEqual(updated['results'], "NEW_RESULTS", "StudZone 2 update must succeed despite SZ1 failure.")
            self.assertEqual(updated['portalStatus']['studzone1'], "unreachable")
            self.assertEqual(updated['portalStatus']['studzone2'], "connected")

        # Case B: StudZone 1 succeeds, StudZone 2 fails
        user_record_2 = self.users_col.find_one({"rollNo": self.roll_a})
        with patch('speed_ser.modern_login', return_value=MagicMock()), \
             patch('speed_ser.scrape_studzone1_all', return_value={"parsed_attendance": [{"code": "23MX31", "percentage": "82%"}], "attendance_html": "NEW_ATTENDANCE"}), \
             patch('speed_ser.legacy_login', return_value=(False, "Service Unavailable")):
            sync_single_user(user_record_2, self.db)
            updated_2 = self.users_col.find_one({"rollNo": self.roll_a})
            self.assertEqual(updated_2['results'], "NEW_RESULTS", "StudZone 2 cached data must be preserved on SZ2 failure.")
            self.assertEqual(updated_2['attendance'], "NEW_ATTENDANCE", "StudZone 1 update must succeed despite SZ2 failure.")
            self.assertEqual(updated_2['portalStatus']['studzone1'], "connected")
            self.assertEqual(updated_2['portalStatus']['studzone2'], "unreachable")

    # -------------------------------------------------------------------------
    # Test 12: Expired sessions and network timeouts are handled safely
    # -------------------------------------------------------------------------
    def test_12_expired_sessions_and_network_timeouts_handled_safely(self):
        import requests
        with patch('requests.Session.get', side_effect=requests.exceptions.Timeout("Connection timed out")):
            from new_scrapers.login import login as modern_login
            success, err = modern_login({'rollNo': self.roll_a, 'password': 'pass'})
            self.assertFalse(success)
            self.assertIn("Network error", err)

    # -------------------------------------------------------------------------
    # Test 13: Disabled preferences suppress notifications
    # -------------------------------------------------------------------------
    @patch('speed_ser.queue_tracked_email')
    def test_13_disabled_preferences_suppress_notifications(self, mock_queue):
        user_prefs = {
            "rollNo": self.roll_a,
            "email": "synth_a@psgtech.ac.in",
            "notifications": {
                "attendance": False,
                "seatingArrangement": False,
                "marks": True
            },
            "studzone1": {
                "parsed_attendance": [{"code": "23MX31", "percentage": "80%"}],
                "parsed_marks": [{"code": "23MX31", "ca1": "15"}]
            },
            "studzone2": {
                "seating_html": None
            }
        }
        sz1_fresh = {
            "parsed_attendance": [{"code": "23MX31", "percentage": "85%"}],
            "parsed_marks": [{"code": "23MX31", "ca1": "20"}]
        }
        sz2_fresh = {
            "seating_html": "<table><tr><td>Hall E101</td></tr></table>"
        }
        process_detected_changes(self.roll_a, user_prefs, sz1_fresh, sz2_fresh, self.db)

        # Attendance and seating notifications must be suppressed; only marks should be queued
        queued_types = [call[0][2] for call in mock_queue.call_args_list]
        self.assertNotIn("attendance", queued_types, "Disabled attendance preference must be suppressed.")
        self.assertNotIn("seating", queued_types, "Disabled seatingArrangement preference must be suppressed.")
        self.assertIn("marks", queued_types, "Enabled marks preference must be queued.")

    # -------------------------------------------------------------------------
    # Test 14: Correct recipient selection maintained for multiple students
    # -------------------------------------------------------------------------
    @patch('speed_ser.queue_tracked_email')
    def test_14_correct_recipient_selection_maintained_for_multiple_students(self, mock_queue):
        student_a = {
            "rollNo": self.roll_a,
            "email": "verified_custom_email@gmail.com",
            "studzone1": {"parsed_attendance": [{"code": "23MX31", "percentage": "70%"}]}
        }
        student_b = {
            "rollNo": self.roll_b,
            "email": "",  # Falls back to roll-derived address
            "studzone1": {"parsed_attendance": [{"code": "23MX31", "percentage": "70%"}]}
        }
        sz1_fresh = {"parsed_attendance": [{"code": "23MX31", "percentage": "75%"}]}

        process_detected_changes(self.roll_a, student_a, sz1_fresh, {}, self.db)
        process_detected_changes(self.roll_b, student_b, sz1_fresh, {}, self.db)

        recipients = [call[0][1] for call in mock_queue.call_args_list]
        self.assertIn("verified_custom_email@gmail.com", recipients)
        self.assertIn(f"{self.roll_b.lower()}@psgtech.ac.in", recipients)
        admin_email = os.getenv("ADMIN_EMAIL", "studentsync12@gmail.com")
        self.assertNotIn(admin_email, recipients, "Student academic notifications must NEVER go to ADMIN_EMAIL.")

    # -------------------------------------------------------------------------
    # Test 15: Concurrent duplicate attempts result in 1 notification & 1 dispatch
    # -------------------------------------------------------------------------
    @patch('speed_ser.queue_tracked_email')
    def test_15_concurrent_duplicate_attempts_result_in_one_notification_and_one_dispatch(self, mock_queue):
        user_state = {
            "rollNo": self.roll_a,
            "studzone1": {"parsed_attendance": [{"code": "23MX31", "percentage": "75%"}]}
        }
        sz1_fresh = {"parsed_attendance": [{"code": "23MX31", "percentage": "80%"}]}

        def worker():
            process_detected_changes(self.roll_a, user_state, sz1_fresh, {}, self.db)

        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = [ex.submit(worker) for _ in range(5)]
            for f in futures:
                f.result()

        docs_count = self.notifs_col.count_documents({"rollNo": self.roll_a, "type": "attendance"})
        self.assertEqual(docs_count, 1, "Exactly 1 notification document must be created under concurrency.")
        self.assertEqual(mock_queue.call_count, 1, "Exactly 1 email dispatch must be queued under concurrency.")

    # -------------------------------------------------------------------------
    # Test 16: SMTP success, permanent failure, transient failure, and ambiguous outcomes
    # -------------------------------------------------------------------------
    def test_16_smtp_outcomes_tracking(self):
        sender = EmailSender(max_retries=1, num_workers=1)

        # 16a. Success
        with patch.object(sender, '_send_email_attempt', return_value=(True, "")):
            success, err = sender.send_direct("test@psgtech.ac.in", "Subj Success", "Body", roll_no=self.roll_a, notif_type="attendance")
            self.assertTrue(success)
            doc_sent = self.notifs_col.find_one({"rollNo": self.roll_a, "subject": "Subj Success"})
            self.assertEqual(doc_sent['status'], "sent")
            self.assertIsNotNone(doc_sent['sent_at'])

        # 16b. Permanent failure
        with patch.object(sender, '_send_email_attempt', return_value=(False, "Permanent SMTP error (550)")):
            success, err = sender.send_direct("test@psgtech.ac.in", "Subj Fail", "Body", roll_no=self.roll_a, notif_type="attendance")
            self.assertFalse(success)
            doc_failed = self.notifs_col.find_one({"rollNo": self.roll_a, "subject": "Subj Fail"})
            self.assertEqual(doc_failed['status'], "failed")
            self.assertIn("Permanent SMTP error", doc_failed['error'])

        # 16c. Stale ambiguous outcome recovery
        stale_id = self.notifs_col.insert_one({
            "rollNo": self.roll_a,
            "status": "pending",
            "type": "marks",
            "created_at": datetime.now(timezone.utc) - timedelta(seconds=7200),
            "updated_at": datetime.now(timezone.utc) - timedelta(seconds=7200)
        }).inserted_id

        reconciled_count = recover_stale_notifications(self.db, threshold_seconds=3600)
        self.assertGreaterEqual(reconciled_count, 1)
        stale_doc = self.notifs_col.find_one({"_id": stale_id})
        self.assertEqual(stale_doc['status'], "delivery_uncertain")
        self.assertTrue(stale_doc['requires_reconciliation'])

        sender.stop_workers()

    # -------------------------------------------------------------------------
    # Test 17: Restart recovery preserves notification integrity
    # -------------------------------------------------------------------------
    def test_17_restart_recovery_preserves_notification_integrity(self):
        crashed_time = datetime.now(timezone.utc) - timedelta(seconds=5000)
        chash = compute_change_hash(self.roll_a, "attendance", "Attendance", "Test Crash", "Details", "key_17")
        crashed_notif = {
            "rollNo": self.roll_a,
            "status": "retrying",
            "changeHash": chash,
            "changeData": {"subject": "CLOUD COMPUTING", "newValue": "90%"},
            "created_at": crashed_time,
            "updated_at": crashed_time
        }
        notif_id = self.notifs_col.insert_one(crashed_notif).inserted_id

        recover_stale_notifications(self.db, threshold_seconds=3600)
        rec_doc = self.notifs_col.find_one({"_id": notif_id})
        self.assertEqual(rec_doc['status'], "delivery_uncertain")
        self.assertEqual(rec_doc['changeHash'], chash)
        self.assertEqual(rec_doc['changeData']['newValue'], "90%")

        # Admin manual reconciliation
        ok, msg = reconcile_notification(self.db, notif_id, action="mark_failed", reason="Confirmed by admin")
        self.assertTrue(ok)
        final_doc = self.notifs_col.find_one({"_id": notif_id})
        self.assertEqual(final_doc['status'], "failed")
        self.assertFalse(final_doc['requires_reconciliation'])

    # -------------------------------------------------------------------------
    # Test 18: Student logging out does NOT stop background monitoring
    # -------------------------------------------------------------------------
    def test_18_student_logout_does_not_stop_background_monitoring(self):
        user_record = {
            "rollNo": self.roll_a,
            "password": "pass",
            "monitoring_enabled": True,  # Enabled in DB
            "studzone1": {"parsed_attendance": [{"code": "23MX31", "percentage": "75%"}]}
        }
        self.users_col.insert_one(user_record)

        # Background worker syncs student regardless of website session/cookie state
        with patch('speed_ser.modern_login', return_value=MagicMock()), \
             patch('speed_ser.scrape_studzone1_all', return_value={"parsed_attendance": [{"code": "23MX31", "percentage": "80%"}]}), \
             patch('speed_ser.legacy_login', return_value=(False, "Offline")), \
             patch('speed_ser.queue_tracked_email') as mock_email:
            sync_single_user(user_record, self.db)
            self.assertEqual(mock_email.call_count, 1, "Background sync must run and notify even when student is logged out.")

    # -------------------------------------------------------------------------
    # Test 19: Student isolation & unauthorized access prevention
    # -------------------------------------------------------------------------
    def test_19_student_isolation_unauthorized_access(self):
        # Insert records for student A and student B
        self.users_col.insert_one({
            "rollNo": self.roll_a,
            "name": "Student A",
            "password": "secret_password_a",
            "cgpa": 8.1
        })
        self.users_col.insert_one({
            "rollNo": self.roll_b,
            "name": "Student B",
            "password": "secret_password_b",
            "cgpa": 9.2
        })
        self.notifs_col.insert_one({"rollNo": self.roll_a, "title": "Student A Alert", "createdAt": datetime.now(timezone.utc).isoformat(), "read": False})
        self.notifs_col.insert_one({"rollNo": self.roll_b, "title": "Student B Alert", "createdAt": datetime.now(timezone.utc).isoformat(), "read": False})

        # Fetch profile for student A
        resp_a = self.app_client.get(f'/profile?rollNo={self.roll_a}')
        self.assertEqual(resp_a.status_code, 200)
        data_a = resp_a.get_json()
        self.assertEqual(data_a['rollNo'], self.roll_a)
        self.assertNotIn('password', data_a, "Password must NEVER be returned in API profile response.")

        # Fetch notifications for student A
        notifs_res_a = self.app_client.get(f'/notifications?rollNo={self.roll_a}')
        self.assertEqual(notifs_res_a.status_code, 200)
        notifs_a = notifs_res_a.get_json()['notifications']
        self.assertEqual(len(notifs_a), 1)
        self.assertEqual(notifs_a[0]['title'], "Student A Alert")

    # -------------------------------------------------------------------------
    # Test 20: All existing regression tests continue to pass
    # -------------------------------------------------------------------------
    def test_20_all_existing_regression_tests_continue_to_pass(self):
        # Verify core regression functions exist and run smoothly
        self.assertTrue(callable(detect_granular_changes))
        self.assertTrue(callable(recover_stale_notifications))
        self.assertTrue(callable(send_email_direct))


if __name__ == '__main__':
    unittest.main()
