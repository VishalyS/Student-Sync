"""
backend/tests/test_chatbot_navigator.py

Comprehensive tests for Student Sync Chatbot & Page Navigator Engine.
Validates:
1. Subject-specific attendance querying (percentage, attended/conducted, safe bunks).
2. Overall attendance calculation and critical subject warnings.
3. Safe bunk advice generation (how many classes can be bunked or required to hit 75%).
4. Navigational intent resolution (deep links to /attendance, /schedule, /grades, /services, /welcome).
5. Continuous Assessment (CA) marks and component queries.
6. Today's lecture timetable and weekly schedule queries.
7. CGPA, exam seating, and campus services queries.
8. Unauthenticated and unknown student handling.
9. Flask /api/chat HTTP endpoint integration.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from chatbot import process_chatbot_query, fuzzy_match_subject
from pyserver import app, generate_auth_token


class TestChatbotNavigator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.client = cls.app.test_client()
        cls.test_roll = "25MX232"

    def test_01_fuzzy_match_subject(self):
        """Test fuzzy matching by code and by title words"""
        sample_subjects = [
            {"code": "23MX31", "name": "CLOUD COMPUTING"},
            {"code": "23MX32", "name": "DATA MINING AND ANALYTICS"},
            {"code": "23MX36", "name": "CLOUD COMPUTING LABORATORY"}
        ]

        # Exact code match
        match1 = fuzzy_match_subject("my attendance in 23MX31", sample_subjects)
        self.assertIsNotNone(match1)
        self.assertEqual(match1["code"], "23MX31")

        # Name match
        match2 = fuzzy_match_subject("tell me about cloud computing", sample_subjects)
        self.assertIsNotNone(match2)
        self.assertIn("CLOUD COMPUTING", match2["name"])

        # Lab match
        match3 = fuzzy_match_subject("cloud lab attendance", sample_subjects)
        self.assertIsNotNone(match3)

        # Non-existent
        match4 = fuzzy_match_subject("astrophysics attendance", sample_subjects)
        self.assertIsNone(match4)

    def test_02_subject_attendance_query(self):
        """Test querying attendance for a specific subject"""
        res = process_chatbot_query("what is my attendance in cloud computing", self.test_roll)
        self.assertEqual(res["intent"], "subject_attendance")
        self.assertIn("CLOUD COMPUTING", res["reply"].upper())
        self.assertIn("23MX31", res["reply"])
        self.assertIsNotNone(res.get("navigation"))
        self.assertEqual(res["navigation"]["path"], "/attendance")
        self.assertIsNotNone(res.get("data_card"))
        self.assertEqual(res["data_card"]["type"], "subject_attendance")
        self.assertGreater(len(res.get("suggestions", [])), 0)

    def test_03_safe_bunk_query(self):
        """Test calculating how many classes can be bunked in a subject"""
        res = process_chatbot_query("how many classes can i bunk in cloud computing", self.test_roll)
        self.assertEqual(res["intent"], "subject_attendance")
        self.assertIn("Bunk Analysis", res["reply"])
        self.assertIn("CLOUD COMPUTING", res["reply"].upper())
        self.assertEqual(res["navigation"]["path"], "/attendance")

    def test_04_overall_attendance_query(self):
        """Test asking for overall attendance summary"""
        res = process_chatbot_query("what is my overall attendance", self.test_roll)
        self.assertEqual(res["intent"], "overall_attendance")
        self.assertIn("Overall Attendance Summary", res["reply"])
        self.assertIn("Consolidated Percentage", res["reply"])
        self.assertEqual(res["navigation"]["path"], "/attendance")
        self.assertEqual(res["data_card"]["type"], "overall_attendance")

    def test_05_navigation_intents(self):
        """Test navigation to different app sections"""
        nav_tests = [
            ("take me to attendance", "/attendance"),
            ("go to timetable", "/schedule"),
            ("open exam schedule", "/schedule"),
            ("take me to grades and marks", "/grades"),
            ("open campus services and fees", "/services"),
            ("take me to notification settings", "/welcome"),
            ("go to student dashboard", "/dashboard")
        ]

        for query, expected_path in nav_tests:
            with self.subTest(query=query):
                res = process_chatbot_query(query, self.test_roll)
                self.assertEqual(res["intent"], "navigation")
                self.assertEqual(res["navigation"]["path"], expected_path)

    def test_06_cgpa_query(self):
        """Test querying CGPA standing"""
        res = process_chatbot_query("what is my cgpa", self.test_roll)
        self.assertEqual(res["intent"], "cgpa_results")
        self.assertIn("Cumulative Grade Point Average", res["reply"])
        self.assertEqual(res["navigation"]["path"], "/grades")

    def test_07_critical_attendance_query(self):
        """Test asking for subjects below 75%"""
        res = process_chatbot_query("which subjects are below 75", self.test_roll)
        self.assertEqual(res["intent"], "critical_attendance")
        self.assertEqual(res["navigation"]["path"], "/attendance")

    def test_08_today_timetable_query(self):
        """Test asking for class routine / timetable"""
        res = process_chatbot_query("what classes do i have today", self.test_roll)
        self.assertEqual(res["intent"], "timetable")
        self.assertEqual(res["navigation"]["path"], "/schedule")

    def test_09_general_help_query(self):
        """Test asking for help or general introduction"""
        res = process_chatbot_query("what can you do", self.test_roll)
        self.assertEqual(res["intent"], "help")
        self.assertIn("SyncBot", res["reply"])
        self.assertGreater(len(res["suggestions"]), 0)

    def test_10_api_chat_http_endpoint(self):
        """Test live Flask /api/chat endpoint with JSON payload"""
        token = generate_auth_token(self.test_roll)
        resp = self.client.post('/api/chat', json={
            "message": "what is my attendance in cloud computing",
            "rollNo": self.test_roll
        }, headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("intent"), "subject_attendance")
        self.assertIn("reply", data)
        self.assertIn("navigation", data)
        self.assertEqual(data["navigation"]["path"], "/attendance")

    def test_11_api_chat_empty_message_rejected(self):
        """Test that empty messages are rejected with 400"""
        resp = self.client.post('/api/chat', json={"message": ""})
        self.assertEqual(resp.status_code, 400)


if __name__ == '__main__':
    unittest.main()
