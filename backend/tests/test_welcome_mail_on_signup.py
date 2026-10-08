import unittest
import os
import certifi
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv
from unittest.mock import patch
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

load_dotenv(os.path.join(BASE_DIR, '.env'))

from pyserver import app, users_collection, notifications_collection


class TestWelcomeMailOnSignup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = MongoClient(os.getenv('MONGO_URI'), tlsCAFile=certifi.where())
        cls.db = cls.client['ecampus']
        cls.test_roll_1 = "TESTSIGNUP01"
        cls.test_email_1 = "testsignup01@example.com"
        cls.test_roll_2 = "TESTSIGNUP02"

        # Clean existing test fixtures
        if users_collection is not None:
            users_collection.delete_many({"rollNo": {"$in": [cls.test_roll_1, cls.test_roll_2]}})
        if notifications_collection is not None:
            notifications_collection.delete_many({"rollNo": {"$in": [cls.test_roll_1, cls.test_roll_2]}})

    @classmethod
    def tearDownClass(cls):
        # Clean up test records
        if users_collection is not None:
            users_collection.delete_many({"rollNo": {"$in": [cls.test_roll_1, cls.test_roll_2]}})
        if notifications_collection is not None:
            notifications_collection.delete_many({"rollNo": {"$in": [cls.test_roll_1, cls.test_roll_2]}})
        cls.client.close()

    def test_01_signup_with_custom_email_sends_welcome_mail(self):
        """Test signup with custom email dispatches welcome email and marks welcomeEmailSent=True"""
        mock_user = {
            "rollNo": self.test_roll_1,
            "password": "MockPassword123",
            "name": "Alex Student",
            "studzone1": {
                "parsed_attendance": [{"code": "23MX01", "name": "Cloud Computing", "percentage": "88%"}]
            },
            "studzone2": {"cgpa": 8.5},
            "cgpa": 8.5
        }

        with patch('pyserver.sync_student_dual_portal', return_value=(mock_user, None)), \
             patch('backend.new_scrapers.send_mail._email_sender._send_email_attempt', return_value=(True, "")):
            test_client = app.test_client()
            res = test_client.post('/register', json={
                "rollNo": self.test_roll_1,
                "password": "MockPassword123",
                "email": self.test_email_1
            })

            self.assertEqual(res.status_code, 201, f"Expected 201, got {res.status_code}: {res.get_json()}")
            data = res.get_json()
            self.assertEqual(data.get("email"), self.test_email_1)
            self.assertIn("Welcome to Student Sync", data.get("message", ""))

        # Verify welcome notification in notifications_log
        welcome_notif = notifications_collection.find_one({
            "rollNo": self.test_roll_1,
            "type": "welcome"
        })
        self.assertIsNotNone(welcome_notif, "Welcome notification record must exist in notifications_log")
        self.assertEqual(welcome_notif.get("category"), "welcome")
        self.assertEqual(welcome_notif.get("recipient_email"), self.test_email_1)
        self.assertEqual(welcome_notif.get("status"), "sent")
        self.assertIn("Welcome to Student Sync", welcome_notif.get("title", ""))

        # Verify welcomeEmailSent flag on student document in users collection
        user_doc = users_collection.find_one({"rollNo": self.test_roll_1})
        self.assertTrue(user_doc.get("welcomeEmailSent"), "welcomeEmailSent must be set to True")
        self.assertIsNotNone(user_doc.get("welcome_email_sent_at"))

    def test_02_signup_without_custom_email_derives_college_email_and_sends_welcome_mail(self):
        """Test signup without custom email derives PSG Tech email and sends welcome mail"""
        expected_derived_email = f"{self.test_roll_2.lower()}@psgtech.ac.in"
        mock_user = {
            "rollNo": self.test_roll_2,
            "name": "Jordan Student",
            "studzone1": {},
            "studzone2": {},
            "cgpa": "N/A"
        }

        with patch('pyserver.sync_student_dual_portal', return_value=(mock_user, None)), \
             patch('backend.new_scrapers.send_mail._email_sender._send_email_attempt', return_value=(True, "")):
            test_client = app.test_client()
            res = test_client.post('/register', json={
                "rollNo": self.test_roll_2,
                "password": "MockPassword456"
            })

            self.assertEqual(res.status_code, 201)
            data = res.get_json()
            self.assertEqual(data.get("email"), expected_derived_email)

        welcome_notif = notifications_collection.find_one({
            "rollNo": self.test_roll_2,
            "type": "welcome"
        })
        self.assertIsNotNone(welcome_notif)
        self.assertEqual(welcome_notif.get("recipient_email"), expected_derived_email)
        self.assertEqual(welcome_notif.get("status"), "sent")

    def test_03_duplicate_signup_blocked_no_duplicate_welcome_mail(self):
        """Test duplicate registration returns existing account without triggering duplicate welcome mail"""
        with patch('pyserver.modern_login', return_value={'session': 'mock'}):
            test_client = app.test_client()
            res = test_client.post('/register', json={
                "rollNo": self.test_roll_1,
                "password": "MockPassword123"
            })
            self.assertEqual(res.status_code, 200)
            self.assertTrue(res.get_json().get("already_registered"))

        # Verify only 1 welcome notification exists for TESTSIGNUP01
        welcome_count = notifications_collection.count_documents({
            "rollNo": self.test_roll_1,
            "type": "welcome"
        })
        self.assertEqual(welcome_count, 1, "There must be exactly 1 welcome notification for a student")


if __name__ == '__main__':
    unittest.main()
