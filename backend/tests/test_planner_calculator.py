"""
backend/tests/test_planner_calculator.py

Unit test suite for Phase 7 Personalized Study Planner Calculator
Tests all boundary conditions, transparent priority scoring rules, neutral
academic terminology, and robust missing-data handling.
"""

import os
import sys
import unittest

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from planner_calculator import (
    compute_academic_priority_score,
    get_current_or_target_weekday,
    synthesize_academic_planner,
    WEEKDAYS
)


class TestPlannerCalculator(unittest.TestCase):

    # 1. Attendance boundaries
    def test_attendance_under_65_critical(self):
        """Attendance < 65% yields +50 points and CRITICAL_ATTENDANCE tag."""
        res = compute_academic_priority_score(
            attendance_data={"percentage": 64.99, "safe_bunks": 0},
            ca_data={"pending_evaluations": 0},
            timetable_slots_today=[],
            exam_data={"is_registered": False}
        )
        self.assertEqual(res["score"], 50)
        self.assertEqual(res["level"], "MEDIUM")
        self.assertIn("CRITICAL_ATTENDANCE", res["urgency_tags"])
        self.assertTrue(any("Critical Attendance" in r for r in res["reasons"]))

    def test_attendance_exactly_65_below_target(self):
        """Attendance exactly 65.0% yields +40 points and BELOW_TARGET tag."""
        res = compute_academic_priority_score(
            attendance_data={"percentage": 65.0, "safe_bunks": 0},
            ca_data={"pending_evaluations": 0},
            timetable_slots_today=[],
            exam_data={"is_registered": False}
        )
        self.assertEqual(res["score"], 40)
        self.assertEqual(res["level"], "MEDIUM")
        self.assertIn("BELOW_TARGET", res["urgency_tags"])
        self.assertTrue(any("Below Target" in r for r in res["reasons"]))

    def test_attendance_65_to_74_99_below_target(self):
        """Attendance 74.99% yields +40 points and BELOW_TARGET tag."""
        res = compute_academic_priority_score(
            attendance_data={"percentage": 74.99, "safe_bunks": 0},
            ca_data={"pending_evaluations": 0},
            timetable_slots_today=[],
            exam_data={"is_registered": False}
        )
        self.assertEqual(res["score"], 40)
        self.assertEqual(res["level"], "MEDIUM")
        self.assertIn("BELOW_TARGET", res["urgency_tags"])

    def test_attendance_exactly_75_zero_safe_bunks(self):
        """Attendance exactly 75.0% with 0 safe bunks yields +30 points."""
        res = compute_academic_priority_score(
            attendance_data={"percentage": 75.0, "safe_bunks": 0},
            ca_data={"pending_evaluations": 0},
            timetable_slots_today=[],
            exam_data={"is_registered": False}
        )
        self.assertEqual(res["score"], 30)
        self.assertEqual(res["level"], "LOW")
        self.assertIn("ATTENDANCE_BOUNDARY", res["urgency_tags"])
        self.assertTrue(any("Attendance Boundary" in r for r in res["reasons"]))

    def test_attendance_above_75_zero_safe_bunks(self):
        """Attendance 75.68% with 0 safe bunks yields +30 points."""
        res = compute_academic_priority_score(
            attendance_data={"percentage": 75.68, "safe_bunks": 0},
            ca_data={"pending_evaluations": 0},
            timetable_slots_today=[],
            exam_data={"is_registered": False}
        )
        self.assertEqual(res["score"], 30)
        self.assertIn("ATTENDANCE_BOUNDARY", res["urgency_tags"])

    def test_attendance_one_safe_bunk(self):
        """Attendance with 1 safe bunk yields +15 points and LOW_BUNK_MARGIN tag."""
        res = compute_academic_priority_score(
            attendance_data={"percentage": 78.38, "safe_bunks": 1},
            ca_data={"pending_evaluations": 0},
            timetable_slots_today=[],
            exam_data={"is_registered": False}
        )
        self.assertEqual(res["score"], 15)
        self.assertEqual(res["level"], "LOW")
        self.assertIn("LOW_BUNK_MARGIN", res["urgency_tags"])

    def test_attendance_two_safe_bunks(self):
        """Attendance with 2 safe bunks yields +15 points and LOW_BUNK_MARGIN tag."""
        res = compute_academic_priority_score(
            attendance_data={"percentage": 79.49, "safe_bunks": 2},
            ca_data={"pending_evaluations": 0},
            timetable_slots_today=[],
            exam_data={"is_registered": False}
        )
        self.assertEqual(res["score"], 15)
        self.assertIn("LOW_BUNK_MARGIN", res["urgency_tags"])

    def test_attendance_healthy_three_plus_safe_bunks(self):
        """Attendance with >2 safe bunks yields +0 points and HEALTHY_ATTENDANCE tag."""
        res = compute_academic_priority_score(
            attendance_data={"percentage": 92.31, "safe_bunks": 12},
            ca_data={"pending_evaluations": 0},
            timetable_slots_today=[],
            exam_data={"is_registered": False}
        )
        self.assertEqual(res["score"], 0)
        self.assertEqual(res["level"], "LOW")
        self.assertIn("HEALTHY_ATTENDANCE", res["urgency_tags"])

    # 2. Continuous Assessment (CA) activity
    def test_ca_three_plus_pending(self):
        """3+ pending CA evaluations yields +15 points and HIGH_CA_ACTIVITY."""
        res = compute_academic_priority_score(
            attendance_data={"percentage": 90.0, "safe_bunks": 10},
            ca_data={"pending_evaluations": 4},
            timetable_slots_today=[],
            exam_data={"is_registered": False}
        )
        self.assertEqual(res["score"], 15)
        self.assertIn("HIGH_CA_ACTIVITY", res["urgency_tags"])
        self.assertTrue(any("High CA Activity" in r for r in res["reasons"]))

    def test_ca_one_to_two_pending(self):
        """1-2 pending CA evaluations yields +10 points and CA_ACTIVITY."""
        for count in [1, 2]:
            res = compute_academic_priority_score(
                attendance_data={"percentage": 90.0, "safe_bunks": 10},
                ca_data={"pending_evaluations": count},
                timetable_slots_today=[],
                exam_data={"is_registered": False}
            )
            self.assertEqual(res["score"], 10)
            self.assertIn("CA_ACTIVITY", res["urgency_tags"])

    def test_ca_zero_pending(self):
        """0 pending CA evaluations yields +0 points."""
        res = compute_academic_priority_score(
            attendance_data={"percentage": 90.0, "safe_bunks": 10},
            ca_data={"pending_evaluations": 0},
            timetable_slots_today=[],
            exam_data={"is_registered": False}
        )
        self.assertEqual(res["score"], 0)

    # 3. Timetable schedule
    def test_subject_scheduled_today(self):
        """Subject scheduled today yields +25 points and SCHEDULED_TODAY tag."""
        res = compute_academic_priority_score(
            attendance_data={"percentage": 90.0, "safe_bunks": 10},
            ca_data={"pending_evaluations": 0},
            timetable_slots_today=[{"period": 1, "time": "8.30 - 9.20"}],
            exam_data={"is_registered": False}
        )
        self.assertEqual(res["score"], 25)
        self.assertIn("SCHEDULED_TODAY", res["urgency_tags"])
        self.assertTrue(any("Scheduled today: 1 period" in r for r in res["reasons"]))

    def test_subject_not_scheduled_today(self):
        """Subject not scheduled today yields +0 timetable points."""
        res = compute_academic_priority_score(
            attendance_data={"percentage": 90.0, "safe_bunks": 10},
            ca_data={"pending_evaluations": 0},
            timetable_slots_today=[],
            exam_data={"is_registered": False}
        )
        self.assertNotIn("SCHEDULED_TODAY", res["urgency_tags"])

    # 4. Examination status
    def test_exam_soon_within_14_days(self):
        """Known exam <= 14 days yields +35 points and EXAM_SOON tag."""
        res = compute_academic_priority_score(
            attendance_data={"percentage": 90.0, "safe_bunks": 10},
            ca_data={"pending_evaluations": 0},
            timetable_slots_today=[],
            exam_data={"is_registered": True, "days_remaining": 7}
        )
        self.assertEqual(res["score"], 35)
        self.assertEqual(res["level"], "MEDIUM")
        self.assertIn("EXAM_SOON", res["urgency_tags"])

    def test_exam_registered_date_pending(self):
        """Registered exam with date pending yields +5 points and EXAM_PENDING tag."""
        res = compute_academic_priority_score(
            attendance_data={"percentage": 90.0, "safe_bunks": 10},
            ca_data={"pending_evaluations": 0},
            timetable_slots_today=[],
            exam_data={"is_registered": True, "days_remaining": None}
        )
        self.assertEqual(res["score"], 5)
        self.assertIn("EXAM_PENDING", res["urgency_tags"])

    # 5. Composite priority scoring & level brackets
    def test_high_priority_composite(self):
        """Boundary attendance (30) + Scheduled today (25) + High CA (15) = 70 (HIGH)."""
        res = compute_academic_priority_score(
            attendance_data={"percentage": 75.68, "safe_bunks": 0},
            ca_data={"pending_evaluations": 4},
            timetable_slots_today=[{"period": 1}],
            exam_data={"is_registered": True, "days_remaining": None}  # +5 -> 75
        )
        self.assertEqual(res["score"], 75)
        self.assertEqual(res["level"], "HIGH")

    def test_medium_priority_composite(self):
        """Scheduled today (25) + High CA (15) + Exam pending (5) = 45 (MEDIUM)."""
        res = compute_academic_priority_score(
            attendance_data={"percentage": 86.49, "safe_bunks": 5},
            ca_data={"pending_evaluations": 4},
            timetable_slots_today=[{"period": 3}],
            exam_data={"is_registered": True, "days_remaining": None}
        )
        self.assertEqual(res["score"], 45)
        self.assertEqual(res["level"], "MEDIUM")

    def test_low_priority_composite(self):
        """Healthy attendance (0) + Not today (0) + Exam pending (5) = 5 (LOW)."""
        res = compute_academic_priority_score(
            attendance_data={"percentage": 92.31, "safe_bunks": 12},
            ca_data={"pending_evaluations": 0},
            timetable_slots_today=[],
            exam_data={"is_registered": True, "days_remaining": None}
        )
        self.assertEqual(res["score"], 5)
        self.assertEqual(res["level"], "LOW")

    # 6. Neutral academic terminology enforcement
    def test_no_unsupported_institutional_claims(self):
        """Ensures prohibited terminology is NEVER present in reasons or tags."""
        test_cases = [
            {"percentage": 50.0, "safe_bunks": 0},
            {"percentage": 68.0, "safe_bunks": 0},
            {"percentage": 75.0, "safe_bunks": 0},
            {"percentage": 85.0, "safe_bunks": 5}
        ]
        for att in test_cases:
            res = compute_academic_priority_score(
                attendance_data=att,
                ca_data={"pending_evaluations": 3},
                timetable_slots_today=[{"period": 1}],
                exam_data={"is_registered": True}
            )
            combined_text = " ".join(res["reasons"] + res["urgency_tags"]).lower()
            self.assertNotIn("course redo zone", combined_text)
            self.assertNotIn("condonation zone", combined_text)

    # 7. Day handling
    def test_target_weekday_selection(self):
        """Allows explicit override or defaults to Monday-Friday."""
        for day in WEEKDAYS:
            self.assertEqual(get_current_or_target_weekday(day.lower()), day)
            self.assertEqual(get_current_or_target_weekday(day.upper()), day)
        self.assertIn(get_current_or_target_weekday(None), WEEKDAYS)
        self.assertEqual(get_current_or_target_weekday("InvalidDay"), get_current_or_target_weekday(None))

    # 8. Missing data handling in synthesize_academic_planner
    def test_synthesize_academic_planner_empty_doc(self):
        """Handles empty user document gracefully."""
        res = synthesize_academic_planner(None)
        self.assertIn("error", res)
        self.assertEqual(res["subject_matrix"], [])

    def test_synthesize_academic_planner_partial_doc(self):
        """Handles user doc with missing fields without throwing exceptions."""
        partial_user = {
            "rollNo": "TEST01",
            "name": "TEST STUDENT",
            "studzone1": {
                "parsed_attendance": [
                    {"code": "SUB01", "name": "Subject 1", "attended": 10, "total_classes": 10, "percentage": "100%"}
                ]
            }
        }
        res = synthesize_academic_planner(partial_user)
        self.assertEqual(res["student"]["rollNo"], "TEST01")
        self.assertEqual(len(res["subject_matrix"]), 1)
        self.assertEqual(res["subject_matrix"][0]["code"], "SUB01")
        self.assertEqual(res["registered_exams_summary"]["total_registered"], 0)


if __name__ == '__main__':
    unittest.main()
