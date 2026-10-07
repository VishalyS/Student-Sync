import os
import sys
import time
import unittest
from datetime import datetime, timezone
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

try:
    from backend.new_scrapers.send_mail import _email_sender, send_email_direct
    from backend.speed_ser import process_detected_changes
    from backend.notifications.change_detector import detect_granular_changes
    from backend.database import db, notifications_collection, user_collection
    from backend.pyserver import app
except ImportError:
    from new_scrapers.send_mail import _email_sender, send_email_direct
    from speed_ser import process_detected_changes
    from notifications.change_detector import detect_granular_changes
    from database import db, notifications_collection, user_collection
    from pyserver import app

class TestPhase1EmailRepair(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = db
        cls.test_roll = "TEST_PHASE1_ROLL"
        cls.recipient = f"{cls.test_roll.lower()}@psgtech.ac.in"

    def setUp(self):
        # Drain any residual queue items
        while not _email_sender.email_queue.empty():
            try:
                _email_sender.email_queue.get_nowait()
                _email_sender.email_queue.task_done()
            except Exception:
                pass

        if self.db is not None:
            self.db['notifications_log'].delete_many({"rollNo": self.test_roll})
            self.db['new_users'].delete_many({"rollNo": self.test_roll})

    def tearDown(self):
        # Drain queue
        while not _email_sender.email_queue.empty():
            try:
                _email_sender.email_queue.get_nowait()
                _email_sender.email_queue.task_done()
            except Exception:
                pass

        if self.db is not None:
            self.db['notifications_log'].delete_many({"rollNo": self.test_roll})
            self.db['new_users'].delete_many({"rollNo": self.test_roll})

    def test_studzone1_attendance_success(self):
        """Test StudZone 1 attendance change creates pending notification, then transitions to sent on SMTP success."""
        old_user = {
            "rollNo": self.test_roll,
            "name": "Test Student",
            "notifications": {"attendance": True},
            "studzone1": {
                "parsed_attendance": [
                    {"code": "20CS101", "name": "Operating Systems", "percentage": "85.0", "attended": "34", "total": "40"}
                ]
            }
        }
        sz1_fresh = {
            "parsed_attendance": [
                {"code": "20CS101", "name": "Operating Systems", "percentage": "80.0", "attended": "34", "total": "42.5"}
            ]
        }
        sz2_fresh = {}

        with patch.object(_email_sender, '_send_email_attempt', return_value=(True, "")):
            process_detected_changes(self.test_roll, old_user, sz1_fresh, sz2_fresh, self.db)
            _email_sender.email_queue.join()
            
            notifs = list(self.db['notifications_log'].find({"rollNo": self.test_roll, "type": "attendance"}))
            self.assertEqual(len(notifs), 1, "Should create exactly 1 attendance notification")
            notif = notifs[0]
            self.assertEqual(notif["status"], "sent", "Status must update to 'sent' after successful SMTP delivery")
            self.assertIsNotNone(notif.get("sent_at"), "sent_at must be populated on success")
            self.assertIsNone(notif.get("error"), "error must be None on success")
            self.assertEqual(notif.get("recipient_email"), self.recipient)
            self.assertIn("Operating Systems", notif.get("description", ""))

    def test_studzone1_marks_delivery_failure(self):
        """Test StudZone 1 CA marks change transitions to failed on permanent SMTP error without credential exposure."""
        old_user = {
            "rollNo": self.test_roll,
            "name": "Test Student",
            "notifications": {"marks": True},
            "studzone1": {
                "parsed_marks": [
                    {"code": "20CS102", "name": "Database Systems", "ca1": "40", "ca2": "42"}
                ]
            }
        }
        sz1_fresh = {
            "parsed_marks": [
                {"code": "20CS102", "name": "Database Systems", "ca1": "40", "ca2": "48"}
            ]
        }
        sz2_fresh = {}

        simulated_error = "Authentication failed: 535 5.7.8 Username and Password not accepted."
        with patch.object(_email_sender, '_send_email_attempt', return_value=(False, simulated_error)):
            process_detected_changes(self.test_roll, old_user, sz1_fresh, sz2_fresh, self.db)
            _email_sender.email_queue.join()
            
            notifs = list(self.db['notifications_log'].find({"rollNo": self.test_roll, "type": "marks"}))
            self.assertEqual(len(notifs), 1, "Should create exactly 1 marks notification")
            notif = notifs[0]
            self.assertEqual(notif["status"], "failed", "Status must update to 'failed' on delivery failure")
            self.assertIsNone(notif.get("sent_at"), "sent_at must remain None on failure")
            self.assertEqual(notif.get("error"), simulated_error, "Error details must be captured safely")
            self.assertEqual(notif.get("recipient_email"), self.recipient)

    def test_studzone2_results_cgpa_timetable(self):
        """Test StudZone 2 results, CGPA, and timetable changes are detected and queued."""
        old_user = {
            "rollNo": self.test_roll,
            "name": "Test Student",
            "cgpa": "8.50",
            "notifications": {"results": True, "timetable": True},
            "studzone2": {
                "results": [
                    {"code": "20CS101", "name": "Operating Systems", "grade": "B+"}
                ],
                "parsed_timetable": [
                    {"course_code": "20CS101", "course_title": "Operating Systems", "exam_date": "2026-10-10", "session": "FN"}
                ]
            }
        }
        sz1_fresh = {}
        sz2_fresh = {
            "cgpa": "8.75",
            "results": [
                {"code": "20CS101", "name": "Operating Systems", "grade": "A"}
            ],
            "parsed_timetable": [
                {"course_code": "20CS101", "course_title": "Operating Systems", "exam_date": "2026-10-12", "session": "AN"}
            ]
        }

        with patch.object(_email_sender, '_send_email_attempt', return_value=(True, "")):
            process_detected_changes(self.test_roll, old_user, sz1_fresh, sz2_fresh, self.db)
            _email_sender.email_queue.join()

            notifs = list(self.db['notifications_log'].find({"rollNo": self.test_roll}))
            types = {n["type"] for n in notifs}
            self.assertIn("results", types, "Should detect grade and CGPA change")
            self.assertIn("timetable", types, "Should detect timetable change")
            for n in notifs:
                self.assertEqual(n["status"], "sent")
                self.assertEqual(n["recipient_email"], self.recipient)
                self.assertIsNotNone(n.get("sent_at"))

    def test_seating_preference_enabled_vs_disabled(self):
        """Test seating notification is queued when enabled, but completely suppressed when seatingArrangement=False."""
        old_user = {
            "rollNo": self.test_roll,
            "name": "Test Student",
            "notifications": {"seatingArrangement": False},  # Disabled by student in preferences
            "studzone2": {}
        }
        sz1_fresh = {}
        sz2_fresh = {
            "seating_html": "<table><tr><td>Hall E201</td><td>Seat 24</td></tr></table>"
        }

        with patch.object(_email_sender, '_send_email_attempt', return_value=(True, "")):
            # 1. When disabled in preferences (seatingArrangement = False):
            process_detected_changes(self.test_roll, old_user, sz1_fresh, sz2_fresh, self.db)
            _email_sender.email_queue.join()
            notifs = list(self.db['notifications_log'].find({"rollNo": self.test_roll, "type": "seating"}))
            self.assertEqual(len(notifs), 0, "Seating notification MUST NOT be recorded when seatingArrangement is False")

            # 2. When enabled in preferences (seatingArrangement = True):
            old_user["notifications"]["seatingArrangement"] = True
            process_detected_changes(self.test_roll, old_user, sz1_fresh, sz2_fresh, self.db)
            _email_sender.email_queue.join()
            notifs = list(self.db['notifications_log'].find({"rollNo": self.test_roll, "type": "seating"}))
            self.assertEqual(len(notifs), 1, "Seating notification MUST be recorded when seatingArrangement is True")
            self.assertEqual(notifs[0]["status"], "sent")
            self.assertEqual(notifs[0]["recipient_email"], self.recipient)

    def test_changehash_deduplication(self):
        """Test that calling process_detected_changes multiple times does not produce duplicate notifications."""
        old_user = {
            "rollNo": self.test_roll,
            "name": "Test Student",
            "notifications": {"attendance": True},
            "studzone1": {
                "parsed_attendance": [
                    {"code": "20CS101", "name": "OS", "percentage": "80.0", "attended": "32", "total": "40"}
                ]
            }
        }
        sz1_fresh = {
            "parsed_attendance": [
                {"code": "20CS101", "name": "OS", "percentage": "82.5", "attended": "33", "total": "40"}
            ]
        }
        sz2_fresh = {}

        with patch.object(_email_sender, '_send_email_attempt', return_value=(True, "")):
            # First run: inserts notification
            process_detected_changes(self.test_roll, old_user, sz1_fresh, sz2_fresh, self.db)
            _email_sender.email_queue.join()
            count1 = self.db['notifications_log'].count_documents({"rollNo": self.test_roll})
            self.assertEqual(count1, 1)

            # Second run with same changes: must deduplicate and skip
            process_detected_changes(self.test_roll, old_user, sz1_fresh, sz2_fresh, self.db)
            _email_sender.email_queue.join()
            count2 = self.db['notifications_log'].count_documents({"rollNo": self.test_roll})
            self.assertEqual(count2, 1, "Deduplication via changeHash must prevent duplicate records")

    def test_no_changes_produces_no_notifications(self):
        """Test that identical snapshots produce 0 notifications."""
        old_user = {
            "rollNo": self.test_roll,
            "name": "Test Student",
            "notifications": {"attendance": True, "marks": True},
            "studzone1": {
                "parsed_attendance": [{"code": "20CS101", "percentage": "85.0"}],
                "parsed_marks": [{"code": "20CS101", "ca1": "45"}]
            }
        }
        sz1_fresh = {
            "parsed_attendance": [{"code": "20CS101", "percentage": "85.0"}],
            "parsed_marks": [{"code": "20CS101", "ca1": "45"}]
        }
        sz2_fresh = {}

        with patch.object(_email_sender, '_send_email_attempt', return_value=(True, "")):
            process_detected_changes(self.test_roll, old_user, sz1_fresh, sz2_fresh, self.db)
            _email_sender.email_queue.join()
            count = self.db['notifications_log'].count_documents({"rollNo": self.test_roll})
            self.assertEqual(count, 0, "No notifications should be generated when data is identical")

    def test_direct_registration_email(self):
        """Test send_email_direct successfully transitions notification status from pending to sent."""
        notif_doc = {
            "rollNo": self.test_roll,
            "studentRollNo": self.test_roll,
            "recipient_email": self.recipient,
            "category": "welcome",
            "type": "welcome",
            "title": "Welcome to Student Sync",
            "description": "Welcome",
            "status": "pending",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        res = self.db['notifications_log'].insert_one(notif_doc)
        notif_id = res.inserted_id

        # Verify initial pending state
        initial_doc = self.db['notifications_log'].find_one({"_id": notif_id})
        self.assertEqual(initial_doc["status"], "pending")

        with patch.object(_email_sender, '_send_email_attempt', return_value=(True, "")):
            success, err = send_email_direct(
                self.recipient,
                "Welcome to Student Sync",
                "<p>Welcome</p>",
                rollNo=self.test_roll,
                notif_type="welcome",
                notif_id=notif_id
            )
            self.assertTrue(success)
            self.assertEqual(err, "")

            updated_doc = self.db['notifications_log'].find_one({"_id": notif_id})
            self.assertEqual(updated_doc["status"], "sent")
            self.assertIsNotNone(updated_doc.get("sent_at"))
            self.assertIsNone(updated_doc.get("error"))

    def test_recipient_email_custom_vs_default(self):
        """Test recipient selection respects custom student email and falls back to psgtech.ac.in."""
        custom_email = "student_custom@domain.com"
        old_user = {
            "rollNo": self.test_roll,
            "name": "Custom Email Student",
            "email": custom_email,
            "notifications": {"attendance": True},
            "studzone1": {
                "parsed_attendance": [
                    {"code": "20CS101", "name": "OS", "percentage": "80.0", "attended": "32", "total": "40"}
                ]
            }
        }
        sz1_fresh = {
            "parsed_attendance": [
                {"code": "20CS101", "name": "OS", "percentage": "85.0", "attended": "34", "total": "40"}
            ]
        }
        sz2_fresh = {}

        with patch.object(_email_sender, '_send_email_attempt', return_value=(True, "")):
            process_detected_changes(self.test_roll, old_user, sz1_fresh, sz2_fresh, self.db)
            _email_sender.email_queue.join()

            notif = self.db['notifications_log'].find_one({"rollNo": self.test_roll, "type": "attendance"})
            self.assertIsNotNone(notif)
            self.assertEqual(notif.get("recipient_email"), custom_email, "Must use custom email from student document")
            self.assertEqual(notif["status"], "sent")

    def test_studzone1_fees_suppression_and_hostel_delivery(self):
        """Test StudZone 1 hostel updates deliver successfully while disabled fees notifications are suppressed."""
        old_user = {
            "rollNo": self.test_roll,
            "name": "Test Student",
            "notifications": {"fees": False, "hostel": True},  # fees disabled, hostel enabled
            "studzone1": {
                "fee_status": "Tuition Fee Cleared",
                "hostel_status": "Block B-101"
            }
        }
        sz1_fresh = {
            "fee_status": "₹5,000 examination fee due",
            "hostel_status": "Block C-204"
        }
        sz2_fresh = {}

        with patch.object(_email_sender, '_send_email_attempt', return_value=(True, "")):
            process_detected_changes(self.test_roll, old_user, sz1_fresh, sz2_fresh, self.db)
            _email_sender.email_queue.join()

            # Fees must be completely suppressed
            fee_notifs = list(self.db['notifications_log'].find({"rollNo": self.test_roll, "type": "fees"}))
            self.assertEqual(len(fee_notifs), 0, "Fee notification must be suppressed when user preference is False")

            # Hostel must be queued and sent
            hostel_notifs = list(self.db['notifications_log'].find({"rollNo": self.test_roll, "type": "hostel"}))
            self.assertEqual(len(hostel_notifs), 1, "Hostel notification must be queued when preference is True")
            self.assertEqual(hostel_notifs[0]["status"], "sent")
            self.assertEqual(hostel_notifs[0]["recipient_email"], self.recipient)

    def test_studzone2_timetable_and_results_preference_suppression(self):
        """Test StudZone 2 timetable and results notifications are suppressed when disabled in user preferences."""
        old_user = {
            "rollNo": self.test_roll,
            "name": "Test Student",
            "cgpa": "8.50",
            "notifications": {"timetable": False, "results": False},  # Both disabled
            "studzone2": {
                "results": [{"code": "20CS101", "grade": "B+"}],
                "parsed_timetable": [{"course_code": "20CS101", "exam_date": "2026-10-10", "session": "FN"}]
            }
        }
        sz1_fresh = {}
        sz2_fresh = {
            "cgpa": "8.80",
            "results": [{"code": "20CS101", "grade": "A"}],
            "parsed_timetable": [{"course_code": "20CS101", "exam_date": "2026-10-14", "session": "AN"}]
        }

        with patch.object(_email_sender, '_send_email_attempt', return_value=(True, "")):
            process_detected_changes(self.test_roll, old_user, sz1_fresh, sz2_fresh, self.db)
            _email_sender.email_queue.join()

            notifs = list(self.db['notifications_log'].find({"rollNo": self.test_roll}))
            self.assertEqual(len(notifs), 0, "Both timetable and results must be suppressed by preferences")

    def test_student_email_update_via_api(self):
        """Test student email and notification preferences update via /notifications POST endpoint."""
        # Insert initial user
        user_doc = {
            "rollNo": self.test_roll,
            "name": "API Student",
            "email": f"{self.test_roll.lower()}@psgtech.ac.in",
            "notifications": {"attendance": True, "marks": True}
        }
        user_collection.insert_one(user_doc)

        client = app.test_client()
        new_email = "new_contact@example.com"
        new_prefs = {"attendance": False, "marks": True, "seatingArrangement": False}

        resp = client.post('/notifications', json={
            "rollNo": self.test_roll,
            "email": new_email,
            "notifications": new_prefs
        })
        self.assertEqual(resp.status_code, 200)

        updated_user = user_collection.find_one({"rollNo": self.test_roll})
        self.assertEqual(updated_user.get("email"), new_email)
        self.assertEqual(updated_user.get("notifications"), new_prefs)

    def test_studzone1_scholarship_and_feedback(self):
        """Test StudZone 1 scholarship status update and course feedback notification delivery."""
        old_user = {
            "rollNo": self.test_roll,
            "name": "Test Student",
            "notifications": {"scholarships": True, "feedback": True},
            "studzone1": {
                "scholarship_status": "Under Review",
                "feedback": [{"type": "Course", "status": "Not Scheduled"}]
            }
        }
        sz1_fresh = {
            "scholarship_status": "Approved",
            "feedback": [{"type": "Course", "status": "Scheduled"}]
        }
        sz2_fresh = {}

        with patch.object(_email_sender, '_send_email_attempt', return_value=(True, "")):
            process_detected_changes(self.test_roll, old_user, sz1_fresh, sz2_fresh, self.db)
            _email_sender.email_queue.join()

            notifs = list(self.db['notifications_log'].find({"rollNo": self.test_roll}))
            types = {n["type"] for n in notifs}
            self.assertIn("scholarships", types, "Scholarship status update must be detected")
            self.assertIn("feedback", types, "Course feedback availability must be detected")
            for n in notifs:
                self.assertEqual(n["status"], "sent")
                self.assertEqual(n["recipient_email"], self.recipient)
                self.assertIsNotNone(n.get("sent_at"))

if __name__ == '__main__':
    unittest.main(verbosity=2)
