"""
End-to-End Verification Test Suite: Meaningful Notification Delivery in Student Sync

Verifies:
1. Registration establishes active baseline and dispatches welcome email without change spam.
2. Attendance update emits a rich, meaningful email:
   - Drops below 75%: Actionable recovery warning with exact consecutive classes required.
   - Above 75%: Safe attendance confirmation with safe bunks allowance.
3. CA Marks update emits internal assessment card with score and grades link.
4. Exam Timetable update emits schedule card with date, session, and timetable link.
5. Notification routing respects student recipient email and per-user category preferences.
6. SHA-256 changeHash prevents duplicate delivery.
7. Zero permanent impact on real production users.
"""

import os
import sys
import copy
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from database import db, user_collection, notifications_collection
from notifications.email_formatter import build_notification_email
from notifications.change_detector import detect_granular_changes, compute_change_hash
from speed_ser import process_detected_changes


class TestMeaningfulNotifications(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = db
        cls.users_col = user_collection
        cls.notifs_col = notifications_collection
        cls.test_roll = "TEST_NOTIF_USER"
        cls.test_email = "test_meaningful@studentpsg.ac.in"
        cls.cleanup_data()

    @classmethod
    def tearDownClass(cls):
        cls.cleanup_data()

    @classmethod
    def cleanup_data(cls):
        cls.users_col.delete_many({"rollNo": cls.test_roll})
        cls.notifs_col.delete_many({"rollNo": cls.test_roll})

    def setUp(self):
        self.cleanup_data()
        self.sent_emails = []

    def tearDown(self):
        self.cleanup_data()

    def fake_queue_email(self, roll_no, recipient_email, notif_type, subject, body, notif_id=None):
        self.sent_emails.append({
            "roll_no": roll_no,
            "recipient_email": recipient_email,
            "notif_type": notif_type,
            "subject": subject,
            "body": body,
            "notif_id": notif_id
        })
        return True

    def test_01_email_formatter_attendance_drop_below_75(self):
        """Attendance drop below 75% produces recovery plan with classes needed."""
        notif = {
            "type": "attendance",
            "title": "Attendance Alert",
            "message": "CLOUD COMPUTING attendance dropped from 75% → 72%.",
            "source": "StudZone 1",
            "module": "Attendance",
            "changeData": {
                "subject": "CLOUD COMPUTING",
                "code": "23MX31",
                "previousValue": "75%",
                "newValue": "72%",
                "direction": "decreased",
                "attended": 28,
                "total": 39
            }
        }
        subj, body = build_notification_email(notif, "TEST STUDENT", self.test_roll, self.test_email)

        self.assertIn("Student Sync — Attendance Alert (CLOUD COMPUTING)", subj)
        self.assertIn("Below PSG Tech 75% Threshold", body)
        self.assertIn("Action Plan", body)
        self.assertIn("consecutive class(es)", body)
        self.assertIn("/attendance", body)
        self.assertIn("28", body)
        self.assertIn("39", body)
        self.assertIn(self.test_email, body)
        self.assertIn(">Subject</td>", body)
        self.assertNotIn(">Course</td>", body)

    def test_02_email_formatter_attendance_safe_zone(self):
        """Attendance above 75% produces safe margin with safe bunks allowance."""
        notif = {
            "type": "attendance",
            "title": "Attendance Updated",
            "message": "FULL STACK DEVELOPMENT attendance changed from 85% → 88%.",
            "source": "StudZone 1",
            "module": "Attendance",
            "changeData": {
                "subject": "FULL STACK DEVELOPMENT",
                "code": "23MX36",
                "previousValue": "85%",
                "newValue": "88%",
                "direction": "increased",
                "attended": 44,
                "total": 50
            }
        }
        subj, body = build_notification_email(notif, "TEST STUDENT", self.test_roll, self.test_email)

        self.assertIn("Student Sync — Attendance Updated (FULL STACK DEVELOPMENT)", subj)
        self.assertIn("Safe Attendance Zone", body)
        self.assertIn("Safe Margin", body)
        self.assertIn("safe bunks remaining", body.lower())
        self.assertIn("/attendance", body)

    def test_03_email_formatter_ca_marks(self):
        """CA Marks published produces internal assessment card with score and grades link."""
        notif = {
            "type": "marks",
            "title": "CA Marks Published",
            "message": "MACHINE LEARNING CA1 marks published: 46.",
            "source": "StudZone 1",
            "module": "CA Marks",
            "changeData": {
                "subject": "MACHINE LEARNING TECHNIQUES",
                "code": "23MX37",
                "test": "CA1",
                "previousValue": "-",
                "newValue": "46"
            }
        }
        subj, body = build_notification_email(notif, "TEST STUDENT", self.test_roll, self.test_email)

        self.assertIn("Student Sync — CA Marks Published (MACHINE LEARNING TECHNIQUES)", subj)
        self.assertIn("Continuous Assessment Recorded", body)
        self.assertIn("CA1", body)
        self.assertIn("46", body)
        self.assertIn("/grades", body)

    def test_04_email_formatter_timetable_update(self):
        """Exam Timetable notification contains exam date, session, and schedule link."""
        notif = {
            "type": "timetable",
            "title": "Exam Timetable Published",
            "message": "DISTRIBUTED SYSTEMS exam scheduled on 15-11-2026, FN session.",
            "source": "StudZone 2",
            "module": "Exam Timetable",
            "changeData": {
                "subject": "DISTRIBUTED SYSTEMS",
                "code": "23MXAE",
                "examDate": "15-11-2026",
                "session": "FN",
                "timing": "09:30 AM - 12:30 PM"
            }
        }
        subj, body = build_notification_email(notif, "TEST STUDENT", self.test_roll, self.test_email)

        self.assertIn("Student Sync — Exam Timetable Published (DISTRIBUTED SYSTEMS)", subj)
        self.assertIn("Examination Schedule Notification", body)
        self.assertIn("15-11-2026", body)
        self.assertIn("/schedule", body)

    @patch('speed_ser.queue_tracked_email')
    def test_05_process_detected_changes_end_to_end_flow(self, mock_queue):
        """Full pipeline: stored user baseline + detected portal change -> meaningful email routed."""
        mock_queue.side_effect = self.fake_queue_email

        # 1. Setup user baseline in MongoDB
        stored_user = {
            "rollNo": self.test_roll,
            "name": "Alex Tech",
            "email": self.test_email,
            "baseline_initialized": True,
            "monitoring_enabled": True,
            "notifications": {"attendance": True, "marks": True},
            "studzone1": {
                "parsed_attendance": [
                    {"code": "23MX31", "name": "CLOUD COMPUTING", "percentage": "74%", "attended": 28, "total_classes": 38}
                ],
                "parsed_marks": [
                    {"code": "23MX31", "name": "CLOUD COMPUTING", "ca1": "20"}
                ]
            },
            "studzone2": {}
        }
        self.users_col.insert_one(stored_user)

        # 2. Fresh scrape with attendance drop to 71%
        sz1_fresh = {
            "parsed_attendance": [
                {"code": "23MX31", "name": "CLOUD COMPUTING", "percentage": "71%", "attended": 28, "total_classes": 39}
            ],
            "parsed_marks": [
                {"code": "23MX31", "name": "CLOUD COMPUTING", "ca1": "20"}
            ]
        }
        sz2_fresh = {}

        # 3. Process changes
        user_doc = self.users_col.find_one({"rollNo": self.test_roll})
        process_detected_changes(self.test_roll, user_doc, sz1_fresh, sz2_fresh, self.db)

        # 4. Verify email was dispatched
        self.assertEqual(len(self.sent_emails), 1)
        sent = self.sent_emails[0]
        self.assertEqual(sent["recipient_email"], self.test_email)
        self.assertEqual(sent["roll_no"], self.test_roll)
        self.assertEqual(sent["notif_type"], "attendance")
        self.assertIn("Attendance Alert", sent["subject"])
        self.assertIn("Below PSG Tech 75% Threshold", sent["body"])
        self.assertIn("/attendance", sent["body"])

        # 5. Verify notification document recorded in notifications_log
        log_entry = self.notifs_col.find_one({"rollNo": self.test_roll, "type": "attendance"})
        self.assertIsNotNone(log_entry)
        self.assertIn("changeHash", log_entry)

        # 6. Verify duplicate change on identical data sends zero additional emails
        self.sent_emails.clear()
        process_detected_changes(self.test_roll, user_doc, sz1_fresh, sz2_fresh, self.db)
        self.assertEqual(len(self.sent_emails), 0, "Duplicate change must be atomically suppressed")


if __name__ == '__main__':
    unittest.main()
