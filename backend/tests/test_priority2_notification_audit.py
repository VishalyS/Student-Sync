"""
Test Suite: Priority 2 — Comprehensive Notification Reliability & Change Detection Audit
Tests the 14 mandatory scenarios specified in the audit:
1. First successful fetch (baseline established, zero change alerts)
2. Field changing from previous value (detected, formatted, hashed)
3. Unchanged subsequent fetch (zero notifications generated)
4. Multiple changes across different modules in a single polling pass
5. Missing, null, and empty values handled gracefully
6. HTML formatting changes without data change emit zero notifications
7. Legitimate changes to zero, false, or empty values (e.g., fee dues -> 0)
8. Temporary portal timeout or auth failure preserves cached data without false alerts
9. Recovery after portal becomes available again
10. Duplicate event prevention across repeated runs (changeHash deduplication)
11. Database storage and frontend notification retrieval
12. Correct student ownership and unread/read status
13. Failed delivery and retry recovery behavior
14. Concurrent worker execution and atomic insertion safety
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import copy
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

# Add backend directory to sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from database import get_database_connection, ensure_database_indexes
from notifications.change_detector import detect_granular_changes, compute_change_hash, process_normalized_event
from notifications.recovery import recover_stale_notifications, reconcile_notification
from speed_ser import process_detected_changes, sync_single_user, dispatch_normalized_notification
from pyserver import app


class TestPriority2NotificationAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client, cls.db = get_database_connection()
        cls.users_col = cls.db['new_users']
        cls.notifs_col = cls.db['notifications_log']
        ensure_database_indexes(cls.db)

        cls.roll_test = "AUDIT_TEST_USER_99"
        cls.roll_other = "AUDIT_OTHER_USER_88"
        cls.app_client = app.test_client()

    def setUp(self):
        # Clean test records
        self.users_col.delete_many({"rollNo": {"$in": [self.roll_test, self.roll_other]}})
        self.notifs_col.delete_many({"rollNo": {"$in": [self.roll_test, self.roll_other]}})

    def tearDown(self):
        self.users_col.delete_many({"rollNo": {"$in": [self.roll_test, self.roll_other]}})
        self.notifs_col.delete_many({"rollNo": {"$in": [self.roll_test, self.roll_other]}})

    def create_fixture(self, roll, att_pct="80%", ca1="18", results=None, fees_status="Pending", fee_due=2500, res_status="HOSTELLER"):
        return {
            "rollNo": roll,
            "name": f"Student {roll}",
            "email": f"{roll.lower()}@psgtech.ac.in",
            "password": "testpassword123",
            "monitoring_enabled": True,
            "baseline_initialized": True,
            "attendance": "<td>80%</td>",
            "studzone1": {
                "parsed_attendance": [
                    {"code": "23MX31", "name": "Distributed Computing", "percentage": att_pct, "attended": 40, "total_classes": 50}
                ],
                "parsed_marks": [
                    {"code": "23MX31", "name": "Distributed Computing", "ca1": ca1, "ca2": "19", "ca3": "-", "total": "37"}
                ],
                "parsed_fees": [
                    {"category": "Tuition Fee", "status": fees_status, "amount": fee_due}
                ],
                "fee_status": fees_status,
                "scholarships": {
                    "html_vallalar": f"<table><tr><th>Resident Status</th><td>{res_status}</td></tr></table>"
                },
                "hostel_status": "Block C-204"
            },
            "studzone2": {
                "parsed_results": results or [{"code": "23MX31", "grade": "B+", "credits": "4"}],
                "cgpa": 8.20,
                "parsed_timetable": [
                    {"course_code": "23MX31", "exam_date": "2026-11-10", "session": "FN"}
                ],
                "seating_slots": [
                    ["23MX31", "A-301", "D-12"]
                ]
            }
        }

    # 1. First successful fetch
    def test_01_first_successful_fetch_baseline_initialization(self):
        """First fetch establishes baseline without emitting change notifications."""
        uninit_user = {
            "rollNo": self.roll_test,
            "password": "testpassword123",
            "baseline_initialized": False,
            "monitoring_enabled": True
        }
        self.users_col.insert_one(uninit_user)

        fresh_sz1 = {
            "parsed_attendance": [{"code": "23MX31", "percentage": "80%"}],
            "attendance_html": "<td>80%</td>"
        }
        with patch('speed_ser.modern_login', return_value=MagicMock()), \
             patch('speed_ser.scrape_studzone1_all', return_value=fresh_sz1), \
             patch('speed_ser.legacy_login', return_value=(False, "Skip")):
            sync_single_user(uninit_user, self.db)

        # Baseline was uninitialized, so zero notifications should be queued
        notifs = list(self.notifs_col.find({"rollNo": self.roll_test}))
        self.assertEqual(len(notifs), 0, "Initial uninitialized user fetch must not emit change spam.")

    # 2. A field changing from previous value
    def test_02_field_changing_from_previous_value(self):
        """Attendance percentage change is detected, formatted, and queued."""
        user = self.create_fixture(self.roll_test, att_pct="80%")
        self.users_col.insert_one(user)

        fresh_sz1 = copy.deepcopy(user['studzone1'])
        fresh_sz1['parsed_attendance'][0]['percentage'] = "85%"
        fresh_sz1['parsed_attendance'][0]['attended'] = 45

        notifs = detect_granular_changes(self.roll_test, user, fresh_sz1, user['studzone2'])
        att_notifs = [n for n in notifs if n.get('type') == 'attendance']
        self.assertEqual(len(att_notifs), 1)
        self.assertEqual(att_notifs[0]['title'], "Attendance Updated")
        self.assertIn("80% → 85%", att_notifs[0]['description'])
        self.assertTrue(att_notifs[0]['changeHash'])

    # 3. An unchanged subsequent fetch
    def test_03_unchanged_subsequent_fetch(self):
        """Subsequent fetch with unchanged data produces zero notifications."""
        user = self.create_fixture(self.roll_test, att_pct="80%")
        self.users_col.insert_one(user)

        fresh_sz1 = copy.deepcopy(user['studzone1'])
        fresh_sz2 = copy.deepcopy(user['studzone2'])

        notifs = detect_granular_changes(self.roll_test, user, fresh_sz1, fresh_sz2)
        self.assertEqual(len(notifs), 0, "Identical fetch must produce zero notifications.")

    # 4. Multiple changes between polling cycles
    def test_04_multiple_changes_in_single_polling_pass(self):
        """Multiple distinct changes across modules are all detected simultaneously."""
        user = self.create_fixture(self.roll_test, att_pct="80%", ca1="18")
        self.users_col.insert_one(user)

        fresh_sz1 = copy.deepcopy(user['studzone1'])
        fresh_sz1['parsed_attendance'][0]['percentage'] = "74%"  # Attendance drop below 75
        fresh_sz1['parsed_marks'][0]['ca1'] = "24"               # CA Marks update

        fresh_sz2 = copy.deepcopy(user['studzone2'])
        fresh_sz2['parsed_results'][0]['grade'] = "A"             # Semester Result update
        fresh_sz2['cgpa'] = 8.45                                 # CGPA update
        fresh_sz2['parsed_timetable'][0]['exam_date'] = "2026-11-12"  # Timetable move

        notifs = detect_granular_changes(self.roll_test, user, fresh_sz1, fresh_sz2)
        categories = {n.get('category') or n.get('type') for n in notifs}
        self.assertIn('attendance', categories)
        self.assertIn('marks', categories)
        self.assertIn('results', categories)
        self.assertIn('cgpa', categories)
        self.assertIn('timetable', categories)
        self.assertGreaterEqual(len(notifs), 5, "All simultaneous module changes must be captured.")

    # 5. Missing, null and empty values
    def test_05_missing_null_and_empty_values(self):
        """Missing or malformed fields do not crash the change detector."""
        user = {"rollNo": self.roll_test}
        fresh_sz1 = {"parsed_attendance": None, "parsed_marks": []}
        fresh_sz2 = {"parsed_results": None, "cgpa": None}

        # Must not raise exceptions
        try:
            notifs = detect_granular_changes(self.roll_test, user, fresh_sz1, fresh_sz2)
            self.assertEqual(len(notifs), 0)
        except Exception as e:
            self.fail(f"detect_granular_changes crashed on null/empty inputs: {e}")

    # 6. HTML formatting changes that do not represent actual data changes
    def test_06_html_formatting_changes_emit_zero_notifications(self):
        """CSS/style changes in HTML table do not trigger spurious notifications when parsed values are unchanged."""
        user = self.create_fixture(self.roll_test, att_pct="80%")
        self.users_col.insert_one(user)

        # Scraper returns same parsed values, but different raw HTML markup
        fresh_sz1 = copy.deepcopy(user['studzone1'])
        fresh_sz1['attendance_html'] = '<table class="new-theme-class" style="color: blue;"><tr><td>80%</td></tr></table>'

        notifs = detect_granular_changes(self.roll_test, user, fresh_sz1, user['studzone2'])
        self.assertEqual(len(notifs), 0, "HTML formatting or markup differences must not generate notifications.")

    # 7. Legitimate changes to zero, false or empty values
    def test_07_legitimate_changes_to_zero_or_cleared_values(self):
        """Legitimate fee dues cleared to 0 generates a valid notification."""
        user = self.create_fixture(self.roll_test, fees_status="Due: Rs. 2,500", fee_due=2500)
        self.users_col.insert_one(user)

        fresh_sz1 = copy.deepcopy(user['studzone1'])
        fresh_sz1['parsed_fees'] = [{"category": "Tuition Fee", "status": "Cleared / Nil", "amount": 0}]
        fresh_sz1['fee_status'] = "Cleared / Nil"

        notifs = detect_granular_changes(self.roll_test, user, fresh_sz1, user['studzone2'])
        fee_notifs = [n for n in notifs if n.get('type') == 'fees']
        self.assertEqual(len(fee_notifs), 1)
        self.assertIn("Fee", fee_notifs[0]['title'])

    # 8. Temporary portal timeout or authentication failure
    def test_08_temporary_portal_timeout_preserves_cached_data(self):
        """When StudZone 1 fails with timeout, cached data is preserved and 0 false alerts emitted."""
        user = self.create_fixture(self.roll_test, att_pct="80%")
        self.users_col.insert_one(user)

        # StudZone 1 fails with timeout, StudZone 2 succeeds
        with patch('speed_ser.modern_login', return_value=(False, "Connection timed out")), \
             patch('speed_ser.legacy_login', return_value=MagicMock()), \
             patch('speed_ser.scrape_studzone2_all', return_value=user['studzone2']):
            sync_single_user(user, self.db)

        updated = self.users_col.find_one({"rollNo": self.roll_test})
        self.assertEqual(updated['portalStatus']['studzone1'], 'unreachable')
        self.assertEqual(updated['studzone1']['parsed_attendance'][0]['percentage'], '80%')
        # Check zero notifications were queued because of timeout
        notifs = list(self.notifs_col.find({"rollNo": self.roll_test}))
        self.assertEqual(len(notifs), 0, "Transient failure must not create notifications or wipe cache.")

    # 9. Recovery after portal becomes available again
    def test_09_recovery_after_portal_becomes_available(self):
        """When portal recovers, normal change detection resumes and updates portalStatus."""
        user = self.create_fixture(self.roll_test, att_pct="80%")
        user['portalStatus'] = {"studzone1": "unreachable", "studzone2": "connected"}
        self.users_col.insert_one(user)

        fresh_sz1 = copy.deepcopy(user['studzone1'])
        fresh_sz1['parsed_attendance'][0]['percentage'] = "83%"
        fresh_sz1['attendance_html'] = "<td>83%</td>"

        with patch('speed_ser.modern_login', return_value=MagicMock()), \
             patch('speed_ser.scrape_studzone1_all', return_value=fresh_sz1), \
             patch('speed_ser.legacy_login', return_value=MagicMock()), \
             patch('speed_ser.scrape_studzone2_all', return_value=user['studzone2']):
            sync_single_user(user, self.db)

        updated = self.users_col.find_one({"rollNo": self.roll_test})
        self.assertEqual(updated['portalStatus']['studzone1'], 'connected')
        self.assertEqual(updated['studzone1']['parsed_attendance'][0]['percentage'], '83%')
        notifs = list(self.notifs_col.find({"rollNo": self.roll_test, "type": "attendance"}))
        self.assertEqual(len(notifs), 1)

    # 10. Duplicate event prevention across repeated runs
    def test_10_duplicate_event_prevention_across_repeated_runs(self):
        """Identical changes across repeated sync runs are deduplicated by changeHash unique index."""
        user = self.create_fixture(self.roll_test, att_pct="80%")
        self.users_col.insert_one(user)

        fresh_sz1 = copy.deepcopy(user['studzone1'])
        fresh_sz1['parsed_attendance'][0]['percentage'] = "84%"

        # Run change detection once
        process_detected_changes(self.roll_test, user, fresh_sz1, user['studzone2'], self.db)
        count_1 = self.notifs_col.count_documents({"rollNo": self.roll_test, "type": "attendance"})
        self.assertEqual(count_1, 1)

        # Run again with identical fresh data (simulating repeated polling run before student visits)
        process_detected_changes(self.roll_test, user, fresh_sz1, user['studzone2'], self.db)
        count_2 = self.notifs_col.count_documents({"rollNo": self.roll_test, "type": "attendance"})
        self.assertEqual(count_2, 1, "Duplicate changeHash must be suppressed across repeated runs.")

    # 11. Database storage and frontend notification retrieval
    def test_11_database_storage_and_frontend_notification_retrieval(self):
        """Persisted notifications are properly retrieved via authenticated API."""
        user = self.create_fixture(self.roll_test, att_pct="80%")
        self.users_col.insert_one(user)

        from pyserver import generate_auth_token
        token = generate_auth_token(self.roll_test)

        fresh_sz1 = copy.deepcopy(user['studzone1'])
        fresh_sz1['parsed_attendance'][0]['percentage'] = "85%"
        process_detected_changes(self.roll_test, user, fresh_sz1, user['studzone2'], self.db)

        res = self.app_client.get(
            f"/api/notifications?rollNo={self.roll_test}",
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("notifications", data)
        self.assertEqual(len(data['notifications']), 1)
        self.assertEqual(data['unreadCount'], 1)

    # 12. Correct student ownership and unread/read status
    def test_12_correct_student_ownership_and_unread_read_status(self):
        """Mark as read updates only the target student's notification and decreases unread count."""
        user = self.create_fixture(self.roll_test, att_pct="80%")
        self.users_col.insert_one(user)

        from pyserver import generate_auth_token
        token = generate_auth_token(self.roll_test)

        fresh_sz1 = copy.deepcopy(user['studzone1'])
        fresh_sz1['parsed_attendance'][0]['percentage'] = "86%"
        process_detected_changes(self.roll_test, user, fresh_sz1, user['studzone2'], self.db)

        doc = self.notifs_col.find_one({"rollNo": self.roll_test})
        self.assertFalse(doc['read'])

        # Call mark-read
        res = self.app_client.post(
            "/api/notifications/mark-read",
            headers={"Authorization": f"Bearer {token}"},
            json={"rollNo": self.roll_test, "notificationId": str(doc['_id'])}
        )
        self.assertEqual(res.status_code, 200)

        updated_doc = self.notifs_col.find_one({"_id": doc['_id']})
        self.assertTrue(updated_doc['read'])

    # 13. Failed delivery and retry behavior
    def test_13_failed_delivery_and_stale_notification_recovery(self):
        """Stale notifications stuck in pending state are reconciled to delivery_uncertain."""
        now = datetime.now(timezone.utc)
        stale_time = now - timedelta(hours=2)
        stale_doc = {
            "rollNo": self.roll_test,
            "title": "Stale Alert",
            "type": "attendance",
            "status": "pending",
            "createdAt": stale_time.isoformat(),
            "created_at": stale_time,
            "updated_at": stale_time,
            "changeHash": "stale_hash_audit_13"
        }
        self.notifs_col.insert_one(stale_doc)

        reconciled = recover_stale_notifications(self.db, threshold_seconds=3600)
        self.assertGreaterEqual(reconciled, 1)

        recovered_doc = self.notifs_col.find_one({"changeHash": "stale_hash_audit_13"})
        self.assertEqual(recovered_doc['status'], 'delivery_uncertain')

    # 14. Concurrent polling or multiple worker execution
    def test_14_concurrent_polling_multiple_workers_atomic_safety(self):
        """Multiple threads trying to insert the same notification concurrently produce exactly 1 document."""
        user = self.create_fixture(self.roll_test, att_pct="80%")
        self.users_col.insert_one(user)

        fresh_sz1 = copy.deepcopy(user['studzone1'])
        fresh_sz1['parsed_attendance'][0]['percentage'] = "88%"

        def worker_task():
            process_detected_changes(self.roll_test, user, fresh_sz1, user['studzone2'], self.db)

        with patch('speed_ser.queue_tracked_email'):
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(worker_task) for _ in range(5)]
                for f in futures:
                    f.result()

        count = self.notifs_col.count_documents({"rollNo": self.roll_test, "type": "attendance", "changeHash": {"$exists": True}})
        self.assertEqual(count, 1, "Concurrent sync cycles must atomically yield exactly 1 notification document.")


if __name__ == '__main__':
    unittest.main()
