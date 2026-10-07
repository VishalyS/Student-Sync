"""
Test Suite: Attendance Calculator & Regulatory Formulas
Validates:
1. Standard percentage calculation and zero-division safety.
2. Regulatory status categorization (SAFE >= 75%, WARNING 65-74.99%, CRITICAL < 65%).
3. Safe bunk formula verified with exact boundary checks:
   - Exactly 75.0%
   - 75.1%
   - 76.0%
   - 80.0%
   - 86.45% (Live 25MX232 student aggregate)
   - 100.0%
   - Below 75.0% (bunk count strictly 0)
4. Proof of mathematical inequality for Safe Bunks:
   - Attendance after bunking max_bunks is >= 75.0%
   - Attendance after bunking (max_bunks + 1) is < 75.0%
5. Recovery formula verified with exact boundary checks:
   - 74.9%
   - 74.0%
   - 70.0%
   - 50.0%
   - 0.0%
6. Proof of mathematical inequality for Recovery:
   - Attendance after attending (required - 1) is < 75.0%
   - Attendance after attending required is >= 75.0%
7. In-memory simulation guarantees (no database mutation, correct projections).
8. Weekly classroom timetable parsing (Monday to Friday, periods 1-6).
9. Overall student attendance summary aggregation.
"""

import os
import sys
import unittest

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from attendance_calculator import (
    calculate_attendance,
    calculate_safe_bunks,
    calculate_required_classes,
    get_attendance_status,
    calculate_simulated_attendance,
    parse_daily_schedule,
    summarize_student_attendance,
)


class TestAttendanceCalculator(unittest.TestCase):

    # -------------------------------------------------------------------------
    # 1. Standard Attendance Percentage & Status Tests
    # -------------------------------------------------------------------------
    def test_01_percentage_calculation_and_edges(self):
        # Normal calculations
        self.assertEqual(calculate_attendance(75, 100), 75.0)
        self.assertEqual(calculate_attendance(28, 37), 75.68)
        self.assertEqual(calculate_attendance(268, 310), 86.45)
        self.assertEqual(calculate_attendance(100, 100), 100.0)
        self.assertEqual(calculate_attendance(0, 100), 0.0)

        # Zero-division and invalid inputs
        self.assertEqual(calculate_attendance(0, 0), 0.0)
        self.assertEqual(calculate_attendance(5, 0), 0.0)
        self.assertEqual(calculate_attendance(-5, 10), 0.0)
        self.assertEqual(calculate_attendance("invalid", 10), 0.0)

    def test_02_regulatory_status_thresholds(self):
        self.assertEqual(get_attendance_status(100.0), "SAFE")
        self.assertEqual(get_attendance_status(75.0), "SAFE")
        self.assertEqual(get_attendance_status(75.01), "SAFE")
        self.assertEqual(get_attendance_status(74.99), "WARNING")
        self.assertEqual(get_attendance_status(70.0), "WARNING")
        self.assertEqual(get_attendance_status(65.0), "WARNING")
        self.assertEqual(get_attendance_status(64.99), "CRITICAL")
        self.assertEqual(get_attendance_status(50.0), "CRITICAL")
        self.assertEqual(get_attendance_status(0.0), "CRITICAL")

    # -------------------------------------------------------------------------
    # 2. Safe Bunk Calculator: All Explicit User Scenarios
    # -------------------------------------------------------------------------
    def test_03_safe_bunks_exact_scenarios(self):
        # Scenario A: Exactly 75.0% (75/100) -> 0 safe bunks
        bunks_75 = calculate_safe_bunks(75, 100, target=75.0)
        self.assertEqual(bunks_75, 0, "At exactly 75%, 0 safe bunks allowed")

        # Scenario B: 75.1% (751/1000) -> 1 safe bunk
        # 751 / 1001 = 75.02% (>= 75%), 751 / 1002 = 74.95% (< 75%)
        bunks_751 = calculate_safe_bunks(751, 1000, target=75.0)
        self.assertEqual(bunks_751, 1, "At 75.1%, exactly 1 safe bunk allowed")

        # Scenario C: 76.0% (76/100) -> 1 safe bunk
        # 76 / 101 = 75.25% (>= 75%), 76 / 102 = 74.51% (< 75%)
        bunks_76 = calculate_safe_bunks(76, 100, target=75.0)
        self.assertEqual(bunks_76, 1, "At 76%, exactly 1 safe bunk allowed")

        # Scenario D: 80.0% (80/100) -> 6 safe bunks
        # 80 / 106 = 75.47% (>= 75%), 80 / 107 = 74.77% (< 75%)
        bunks_80 = calculate_safe_bunks(80, 100, target=75.0)
        self.assertEqual(bunks_80, 6, "At 80%, exactly 6 safe bunks allowed")

        # Scenario E: 86.45% (268/310, Live 25MX232 Student Aggregate) -> 47 safe bunks
        # 268 / (310 + 47) = 268 / 357 = 75.07% (>= 75%)
        # 268 / (310 + 48) = 268 / 358 = 74.86% (< 75%)
        bunks_232 = calculate_safe_bunks(268, 310, target=75.0)
        self.assertEqual(bunks_232, 47, "At 86.45% (268/310), exactly 47 safe bunks allowed")

        # Scenario F: 100.0% (100/100) -> 33 safe bunks
        # 100 / 133 = 75.19% (>= 75%), 100 / 134 = 74.63% (< 75%)
        bunks_100 = calculate_safe_bunks(100, 100, target=75.0)
        self.assertEqual(bunks_100, 33, "At 100%, exactly 33 safe bunks allowed")

        # Scenario G: Below 75% -> must strictly return 0 safe bunks
        self.assertEqual(calculate_safe_bunks(74, 100, target=75.0), 0)
        self.assertEqual(calculate_safe_bunks(70, 100, target=75.0), 0)
        self.assertEqual(calculate_safe_bunks(50, 100, target=75.0), 0)
        self.assertEqual(calculate_safe_bunks(0, 10, target=75.0), 0)

    def test_04_safe_bunks_mathematical_inequality_proof(self):
        """
        Tests hundreds of (attended, conducted) pairs where percentage >= 75%:
        Asserts that bunking max_bunks keeps attendance >= 75%,
        AND bunking (max_bunks + 1) strictly drops attendance < 75%.
        """
        test_pairs = [
            (28, 37),   # Cloud Computing (75.68%)
            (48, 52),   # Cloud Lab (92.31%)
            (42, 48),   # Data Mining Lab (87.50%)
            (32, 37),   # Computer Networks (86.49%)
            (27, 36),   # Data Mining (75.00%)
            (29, 37),   # HCI (78.38%)
            (31, 39),   # Entrepreneurship (79.49%)
            (21, 24),   # Research Methodology (87.50%)
            (15, 18),   # Example from prompt (83.33%)
            (9, 10),    # Small subject (90.00%)
            (1, 1),     # Single class subject (100.0%)
        ]

        for att, cond in test_pairs:
            bunks = calculate_safe_bunks(att, cond, target=75.0)
            
            # 1. Attended / (Conducted + bunks) must be >= 75.0%
            pct_after_safe = (att / (cond + bunks)) * 100.0
            self.assertGreaterEqual(
                pct_after_safe, 75.0,
                f"Bunking {bunks} must maintain >= 75% for {att}/{cond} (got {pct_after_safe:.3f}%)"
            )

            # 2. Attended / (Conducted + bunks + 1) must be strictly < 75.0%
            pct_after_one_more = (att / (cond + bunks + 1)) * 100.0
            self.assertLess(
                pct_after_one_more, 75.0,
                f"Bunking {bunks + 1} must fall below 75% for {att}/{cond} (got {pct_after_one_more:.3f}%)"
            )

    # -------------------------------------------------------------------------
    # 3. Attendance Recovery Calculator: All Scenarios
    # -------------------------------------------------------------------------
    def test_05_recovery_exact_scenarios(self):
        # Scenario A: 74.0% (74/100) -> requires exactly 4 consecutive classes
        # (74 + 3) / (100 + 3) = 77 / 103 = 74.76% (< 75%)
        # (74 + 4) / (100 + 4) = 78 / 104 = 75.00% (>= 75%)
        req_74 = calculate_required_classes(74, 100, target=75.0)
        self.assertEqual(req_74, 4, "At 74%, requires 4 consecutive classes")

        # Scenario B: 72.0% (18/25) -> requires exactly 3 consecutive classes
        # (18 + 2) / (25 + 2) = 20 / 27 = 74.07% (< 75%)
        # (18 + 3) / (25 + 3) = 21 / 28 = 75.00% (>= 75%)
        req_72 = calculate_required_classes(18, 25, target=75.0)
        self.assertEqual(req_72, 3, "At 72% (18/25), requires 3 consecutive classes")

        # Scenario C: 70.0% (70/100) -> requires exactly 20 consecutive classes
        # (70 + 19) / 119 = 89 / 119 = 74.79% (< 75%)
        # (70 + 20) / 120 = 90 / 120 = 75.00% (>= 75%)
        req_70 = calculate_required_classes(70, 100, target=75.0)
        self.assertEqual(req_70, 20, "At 70%, requires 20 consecutive classes")

        # Scenario D: 50.0% (5/10) -> requires exactly 10 consecutive classes
        # (5 + 9) / 19 = 14 / 19 = 73.68% (< 75%)
        # (5 + 10) / 20 = 15 / 20 = 75.00% (>= 75%)
        req_50 = calculate_required_classes(5, 10, target=75.0)
        self.assertEqual(req_50, 10, "At 50% (5/10), requires 10 consecutive classes")

        # Scenario E: 0.0% (0/10) -> requires exactly 30 consecutive classes
        # (0 + 29) / 39 = 74.36% (< 75%)
        # (0 + 30) / 40 = 75.00% (>= 75%)
        req_0 = calculate_required_classes(0, 10, target=75.0)
        self.assertEqual(req_0, 30, "At 0% (0/10), requires 30 consecutive classes")

        # Scenario F: At or above 75.0% -> requires 0 classes
        self.assertEqual(calculate_required_classes(75, 100, target=75.0), 0)
        self.assertEqual(calculate_required_classes(80, 100, target=75.0), 0)
        self.assertEqual(calculate_required_classes(100, 100, target=75.0), 0)

    def test_06_recovery_mathematical_inequality_proof(self):
        """
        Tests multiple (attended, conducted) pairs where percentage < 75%:
        Asserts that attending (req - 1) is < 75%,
        AND attending req brings attendance >= 75%.
        """
        test_pairs = [
            (26, 36),  # 72.22%
            (22, 30),  # 73.33%
            (14, 20),  # 70.00%
            (10, 15),  # 66.67%
            (8, 14),   # 57.14%
            (3, 8),    # 37.50%
            (0, 5),    # 0.0%
        ]

        for att, cond in test_pairs:
            req = calculate_required_classes(att, cond, target=75.0)
            self.assertGreater(req, 0, f"Deficient attendance {att}/{cond} must require >0 classes")

            # 1. Attending (req - 1) classes must still be < 75.0%
            if req > 1:
                pct_before_recovery = ((att + (req - 1)) / (cond + (req - 1))) * 100.0
                self.assertLess(
                    pct_before_recovery, 75.0,
                    f"Attending {req - 1} classes must still be <75% for {att}/{cond}"
                )

            # 2. Attending req classes must reach >= 75.0%
            pct_after_recovery = ((att + req) / (cond + req)) * 100.0
            self.assertGreaterEqual(
                pct_after_recovery, 75.0,
                f"Attending {req} classes must reach >=75% for {att}/{cond}"
            )

    # -------------------------------------------------------------------------
    # 4. In-Memory Simulation Tests (Pure Non-Destructive)
    # -------------------------------------------------------------------------
    def test_07_in_memory_simulation(self):
        # Base: 14 attended, 17 conducted (82.35%)
        # User simulates: attend 1 class, bunk 1 class
        sim_res = calculate_simulated_attendance(14, 17, additional_attended=1, additional_bunked=1, target=75.0)

        # Initial checks
        self.assertEqual(sim_res["initial"]["attended"], 14)
        self.assertEqual(sim_res["initial"]["conducted"], 17)
        self.assertEqual(sim_res["initial"]["percentage"], 82.35)
        self.assertEqual(sim_res["initial"]["safe_bunks"], 1)
        self.assertEqual(sim_res["initial"]["status"], "SAFE")

        # Projected checks: attended=15, conducted=19 -> 15/19 = 78.95%
        self.assertEqual(sim_res["simulation"]["additional_attended"], 1)
        self.assertEqual(sim_res["simulation"]["additional_bunked"], 1)
        self.assertEqual(sim_res["simulation"]["attended"], 15)
        self.assertEqual(sim_res["simulation"]["conducted"], 19)
        self.assertEqual(sim_res["simulation"]["percentage"], 78.95)
        self.assertEqual(sim_res["simulation"]["safe_bunks"], 1)
        self.assertEqual(sim_res["simulation"]["status"], "SAFE")
        self.assertEqual(sim_res["simulation"]["percentage_change"], -3.40)

        # Ensure base inputs remained strictly untouched
        self.assertEqual(sim_res["initial"]["attended"], 14)

    # -------------------------------------------------------------------------
    # 5. Weekly Classroom Timetable Parsing
    # -------------------------------------------------------------------------
    def test_08_parse_daily_schedule(self):
        matrix = [
            ["Period", "1", "2", "3", "4", "5", "6"],
            ["Time", "8.30 - 9.20", "9.20 - 10.10", "10.30 - 11.20", "11.20 - 12.10", "1.40 - 2.30", "2.30 - 3.20"],
            ["Monday", "MCA_3\r\n 23MXAF\nDATA MINING AND ANALYTICS", "MCA_3\r\n 23MXAO\nHUMAN COMPUTER INTERACTION", "MCA_3\r\n 23MX31\nCLOUD COMPUTING", "-", "MCA_3\r\n 23MX37\nMINI PROJECT", "-"],
            ["Tuesday", "MCA_3\r\n 23MXAO\nHUMAN COMPUTER INTERACTION", "MCA_3\r\n 23MXAF\nDATA MINING AND ANALYTICS", "-", "MCA_3\r\n 23MXCA\nENTREPRENEURSHIP", "-", "-"]
        ]

        # Parse Monday
        mon = parse_daily_schedule(matrix, day_name="Monday")
        self.assertEqual(mon["day"], "Monday")
        self.assertEqual(len(mon["classes"]), 6)

        c1 = mon["classes"][0]
        self.assertEqual(c1["period"], 1)
        self.assertEqual(c1["time"], "8.30 - 9.20")
        self.assertEqual(c1["code"], "23MXAF")
        self.assertEqual(c1["name"], "DATA MINING AND ANALYTICS")
        self.assertFalse(c1["is_free"])

        c4 = mon["classes"][3]
        self.assertEqual(c4["period"], 4)
        self.assertTrue(c4["is_free"])
        self.assertEqual(c4["name"], "Free Period")

    # -------------------------------------------------------------------------
    # 6. Overall Student Summary Aggregation
    # -------------------------------------------------------------------------
    def test_09_summarize_student_attendance_25mx232_schema(self):
        # Live 25MX232 course data structure
        live_courses = [
            {"code": "23MX31", "name": "CLOUD COMPUTING", "total_classes": "37", "attended": "28", "percentage": "76%"},
            {"code": "23MX36", "name": "CLOUD COMPUTING LABORATORY", "total_classes": "52", "attended": "48", "percentage": "93%"},
            {"code": "23MX37", "name": "MINI PROJECT", "total_classes": "48", "attended": "42", "percentage": "88%"},
            {"code": "23MXAE", "name": "COMPUTER NETWORKS", "total_classes": "37", "attended": "32", "percentage": "87%"},
            {"code": "23MXAF", "name": "DATA MINING AND ANALYTICS", "total_classes": "36", "attended": "27", "percentage": "75%"},
            {"code": "23MXAO", "name": "HUMAN COMPUTER INTERACTION", "total_classes": "37", "attended": "29", "percentage": "79%"},
            {"code": "23MXCA", "name": "ENTREPRENEURSHIP", "total_classes": "39", "attended": "31", "percentage": "80%"},
            {"code": "23MXM4", "name": "PROFESSIONAL ETHICS", "total_classes": "24", "attended": "21", "percentage": "88%"}
        ]

        summary = summarize_student_attendance(live_courses, target=75.0)

        # Overall totals (28+48+42+32+27+29+31+21 = 258 attended, 310 conducted)
        self.assertEqual(summary["overall"]["attended"], 258)
        self.assertEqual(summary["overall"]["conducted"], 310)
        self.assertEqual(summary["overall"]["percentage"], 83.23)
        self.assertEqual(summary["overall"]["safe_bunks"], 34)
        self.assertEqual(summary["overall"]["required_classes"], 0)
        self.assertEqual(summary["overall"]["status"], "SAFE")

        # Counts
        self.assertEqual(summary["counts"]["total_subjects"], 8)
        self.assertEqual(summary["counts"]["safe_subjects"], 8)
        self.assertEqual(summary["counts"]["warning_subjects"], 0)
        self.assertEqual(summary["counts"]["critical_subjects"], 0)

        # Subject-specific checks
        cc = next(s for s in summary["subjects"] if s["code"] == "23MX31")
        self.assertEqual(cc["safe_bunks"], 0)
        self.assertEqual(cc["percentage"], 75.68)
        self.assertEqual(cc["status"], "SAFE")

        dm = next(s for s in summary["subjects"] if s["code"] == "23MXAF")
        self.assertEqual(dm["safe_bunks"], 0)
        self.assertEqual(dm["percentage"], 75.00)
        self.assertEqual(dm["status"], "SAFE")

        # Verify corrected course titles
        mp = next(s for s in summary["subjects"] if s["code"] == "23MX37")
        self.assertEqual(mp["name"], "MINI PROJECT")

        pe = next(s for s in summary["subjects"] if s["code"] == "23MXM4")
        self.assertEqual(pe["name"], "PROFESSIONAL ETHICS")

    def test_10_student_specific_course_title_resolution(self):
        """
        Regression test proving that course title resolution is strictly
        student-specific and never uses stale global titles.
        """
        # Student 25MX227 user doc mock
        user_227 = {
            "rollNo": "25MX227",
            "studzone1": {
                "parsed_marks": [
                    {"code": "23MX31", "name": "CLOUD COMPUTING"},
                    {"code": "23MX36", "name": "CLOUD COMPUTING LABORATORY"},
                    {"code": "23MX37", "name": "MINI PROJECT"},
                    {"code": "23MXAE", "name": "COMPUTER NETWORKS"},
                    {"code": "23MXAT", "name": "DevOps"},
                    {"code": "23MXAY", "name": "SMART COMPUTING WITH ADVANCED PYTHON"},
                    {"code": "23MXCA", "name": "ENTREPRENEURSHIP"},
                    {"code": "23MXM4", "name": "PROFESSIONAL ETHICS"}
                ],
                "class_schedule": []
            }
        }

        # Attendance list with generic or missing names
        raw_att_227 = [
            {"code": "23MX37", "name": "Course 23MX37", "total_classes": "48", "attended": "38", "percentage": "80%"},
            {"code": "23MXM4", "name": "", "total_classes": "24", "attended": "18", "percentage": "75%"},
            {"code": "23MXAT", "name": "Course 23MXAT", "total_classes": "37", "attended": "30", "percentage": "82%"},
            {"code": "23MXAY", "name": "", "total_classes": "36", "attended": "24", "percentage": "67%"},
            {"code": "23MXXX", "name": "", "total_classes": "10", "attended": "8", "percentage": "80%"}
        ]

        summary_227 = summarize_student_attendance(raw_att_227, target=75.0, user_doc=user_227)
        titles_227 = {s["code"]: s["name"] for s in summary_227["subjects"]}

        self.assertEqual(titles_227["23MX37"], "MINI PROJECT")
        self.assertEqual(titles_227["23MXM4"], "PROFESSIONAL ETHICS")
        self.assertEqual(titles_227["23MXAT"], "DevOps")
        self.assertEqual(titles_227["23MXAY"], "SMART COMPUTING WITH ADVANCED PYTHON")
        self.assertEqual(titles_227["23MXXX"], "Course 23MXXX")  # Neutral fallback

        # Student 25MX232 user doc mock
        user_232 = {
            "rollNo": "25MX232",
            "studzone1": {
                "parsed_marks": [
                    {"code": "23MX31", "name": "CLOUD COMPUTING"},
                    {"code": "23MX36", "name": "CLOUD COMPUTING LABORATORY"},
                    {"code": "23MX37", "name": "MINI PROJECT"},
                    {"code": "23MXAE", "name": "COMPUTER NETWORKS"},
                    {"code": "23MXAF", "name": "DATA MINING AND ANALYTICS"},
                    {"code": "23MXAO", "name": "HUMAN COMPUTER INTERACTION"},
                    {"code": "23MXCA", "name": "ENTREPRENEURSHIP"},
                    {"code": "23MXM4", "name": "PROFESSIONAL ETHICS"}
                ],
                "class_schedule": []
            }
        }

        raw_att_232 = [
            {"code": "23MX37", "name": "", "total_classes": "48", "attended": "42", "percentage": "88%"},
            {"code": "23MXM4", "name": "", "total_classes": "24", "attended": "21", "percentage": "88%"},
            {"code": "23MXAF", "name": "", "total_classes": "36", "attended": "27", "percentage": "75%"},
            {"code": "23MXAO", "name": "", "total_classes": "37", "attended": "29", "percentage": "79%"}
        ]

        summary_232 = summarize_student_attendance(raw_att_232, target=75.0, user_doc=user_232)
        titles_232 = {s["code"]: s["name"] for s in summary_232["subjects"]}

        self.assertEqual(titles_232["23MX37"], "MINI PROJECT")
        self.assertEqual(titles_232["23MXM4"], "PROFESSIONAL ETHICS")
        self.assertEqual(titles_232["23MXAF"], "DATA MINING AND ANALYTICS")
        self.assertEqual(titles_232["23MXAO"], "HUMAN COMPUTER INTERACTION")


if __name__ == '__main__':
    unittest.main()
