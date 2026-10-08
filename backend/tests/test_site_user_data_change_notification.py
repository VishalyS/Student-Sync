import unittest
import requests
import os
import certifi
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

BASE_URL = "http://127.0.0.1:5000"
MONGO_URI = os.getenv('MONGO_URI')


class TestSiteUserDataChangeNotifications(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
        cls.db = cls.client['ecampus']
        cls.users_col = cls.db['new_users']
        cls.notifs_col = cls.db['notifications_log']

        cls.test_roll = "TESTUSER999"
        cls.test_email = "testuser999@psgtech.ac.in"
        cls.test_pass = "InitialPass123"

        # Create clean synthetic test user in MongoDB
        cls.users_col.delete_one({"rollNo": cls.test_roll})
        cls.notifs_col.delete_many({"rollNo": cls.test_roll})

        cls.user_doc = {
            "rollNo": cls.test_roll,
            "name": "Test Student User",
            "email": cls.test_email,
            "password": cls.test_pass,
            "monitoring_enabled": True,
            "baseline_initialized": True,
            "notifications": {
                "attendance": True,
                "marks": True,
                "timetable": True,
                "seatingArrangement": True,
                "results": True,
                "fees": True,
                "hostel": True
            },
            "studzone1": {
                "parsed_attendance": [
                    {
                        "code": "23MX01",
                        "name": "Software Engineering",
                        "percentage": "80%",
                        "attended": 16,
                        "total_classes": 20
                    }
                ],
                "parsed_marks": [
                    {
                        "code": "23MX01",
                        "name": "Software Engineering",
                        "ca1": "18",
                        "ca2": "19",
                        "total": "37"
                    }
                ]
            },
            "studzone2": {
                "cgpa": 8.12
            }
        }
        cls.users_col.insert_one(cls.user_doc)

    @classmethod
    def tearDownClass(cls):
        # Clean up test user and test notifications
        cls.users_col.delete_one({"rollNo": cls.test_roll})
        cls.notifs_col.delete_many({"rollNo": cls.test_roll})
        cls.client.close()

    def test_01_password_update_creates_security_notification_and_queues_email(self):
        """Test POST /update endpoint updates password, logs security notification, and queues email."""
        new_password = "UpdatedPassword456"
        res = requests.post(f"{BASE_URL}/update", json={
            "rollno": self.test_roll,
            "password": new_password
        })
        self.assertEqual(res.status_code, 200, f"Expected 200 OK, got {res.status_code}: {res.text}")
        data = res.json()
        self.assertIn("Password updated successfully", data.get("message", ""))

        # Verify password in database
        updated_user = self.users_col.find_one({"rollNo": self.test_roll})
        self.assertEqual(updated_user.get("password"), new_password)
        self.assertIsNotNone(updated_user.get("passwordUpdatedAt"))

        # Verify security notification in notifications_log
        security_notif = self.notifs_col.find_one({
            "rollNo": self.test_roll,
            "type": "security"
        })
        self.assertIsNotNone(security_notif, "Expected security notification logged in notifications_log")
        self.assertEqual(security_notif.get("category"), "security")
        self.assertIn("Portal Password Updated", security_notif.get("title"))
        self.assertIn(self.test_email, security_notif.get("recipient_email"))

    def test_02_notification_preferences_update_creates_notification_and_queues_email(self):
        """Test POST /notifications logs preferences notification when settings change."""
        updated_prefs = {
            "attendance": True,
            "marks": False,  # Changed from True to False
            "timetable": True,
            "seatingArrangement": True,
            "results": True,
            "fees": True,
            "hostel": True
        }
        new_alert_email = "testuser999_alt@gmail.com"

        res = requests.post(f"{BASE_URL}/notifications", json={
            "rollNo": self.test_roll,
            "notifications": updated_prefs,
            "email": new_alert_email,
            "monitoring_enabled": True
        })
        self.assertEqual(res.status_code, 200, f"Expected 200 OK, got {res.status_code}: {res.text}")

        # Verify in database
        user = self.users_col.find_one({"rollNo": self.test_roll})
        self.assertEqual(user.get("email"), new_alert_email)
        self.assertFalse(user.get("notifications", {}).get("marks"))

        # Verify notification logged in notifications_log
        pref_notif = self.notifs_col.find_one({
            "rollNo": self.test_roll,
            "category": "preferences"
        })
        self.assertIsNotNone(pref_notif, "Expected preferences notification logged in notifications_log")
        self.assertIn("Account Settings Updated", pref_notif.get("title"))
        self.assertIn("marks: OFF", pref_notif.get("message"))
        self.assertIn(new_alert_email, pref_notif.get("recipient_email"))

    def test_03_academic_change_detection_dispatches_email_and_logs(self):
        try:
            from backend.speed_ser import process_detected_changes
        except ImportError:
            from speed_ser import process_detected_changes

        # Fresh data with attendance updated from 80% -> 85%
        sz1_fresh = {
            "parsed_attendance": [
                {
                    "code": "23MX01",
                    "name": "Software Engineering",
                    "percentage": "85%",
                    "attended": 17,
                    "total_classes": 20
                }
            ],
            "parsed_marks": self.user_doc["studzone1"]["parsed_marks"]
        }
        sz2_fresh = self.user_doc["studzone2"]

        # Run process_detected_changes
        current_user = self.users_col.find_one({"rollNo": self.test_roll})
        process_detected_changes(self.test_roll, current_user, sz1_fresh, sz2_fresh, self.db)

        # Verify notification was logged
        att_notif = self.notifs_col.find_one({
            "rollNo": self.test_roll,
            "type": "attendance"
        })
        self.assertIsNotNone(att_notif, "Expected attendance notification logged")
        self.assertEqual(att_notif.get("changeData", {}).get("previousValue"), "80%")
        self.assertEqual(att_notif.get("changeData", {}).get("newValue"), "85%")
        self.assertIn("80% → 85%", att_notif.get("message"))

        # Verify deduplication: run again with same data
        prev_count = self.notifs_col.count_documents({"rollNo": self.test_roll, "type": "attendance"})
        process_detected_changes(self.test_roll, current_user, sz1_fresh, sz2_fresh, self.db)
        post_count = self.notifs_col.count_documents({"rollNo": self.test_roll, "type": "attendance"})
        self.assertEqual(prev_count, post_count, "Duplicate notification should be prevented by changeHash")


if __name__ == '__main__':
    unittest.main()
