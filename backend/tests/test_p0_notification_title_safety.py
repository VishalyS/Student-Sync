import unittest
import os
import sys

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from notifications.change_detector import (
    extract_student_title_map,
    resolve_course_title,
    detect_granular_changes,
    compute_change_hash
)


class TestP0NotificationTitleSafety(unittest.TestCase):
    """
    P0 Data Integrity & Notification Safety Test Suite:
    Proves that course title resolution in notifications is strictly student-specific,
    never uses stale global dictionaries, never leaks cross-student data,
    and preserves deduplication / changeHash integrity.
    """

    def setUp(self):
        # Student 25MX227 verified mock profile
        self.doc_227 = {
            "rollNo": "25MX227",
            "name": "SUDHERSON V",
            "baseline_initialized": True,
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
                "parsed_attendance": [
                    {"code": "23MX31", "percentage": "73%", "attended": "27", "total_classes": "37"},
                    {"code": "23MX36", "percentage": "81%", "attended": "42", "total_classes": "52"},
                    {"code": "23MX37", "percentage": "80%", "attended": "38", "total_classes": "48"},
                    {"code": "23MXAE", "percentage": "79%", "attended": "29", "total_classes": "37"},
                    {"code": "23MXAT", "percentage": "82%", "attended": "30", "total_classes": "37"},
                    {"code": "23MXAY", "percentage": "67%", "attended": "24", "total_classes": "36"},
                    {"code": "23MXCA", "percentage": "77%", "attended": "30", "total_classes": "39"},
                    {"code": "23MXM4", "percentage": "75%", "attended": "18", "total_classes": "24"}
                ],
                "class_schedule": []
            },
            "studzone2": {}
        }

        # Student 25MX232 verified mock profile
        self.doc_232 = {
            "rollNo": "25MX232",
            "name": "VISHALY S",
            "baseline_initialized": True,
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
                "parsed_attendance": [
                    {"code": "23MX31", "percentage": "76%", "attended": "28", "total_classes": "37"},
                    {"code": "23MX36", "percentage": "93%", "attended": "48", "total_classes": "52"},
                    {"code": "23MX37", "percentage": "88%", "attended": "42", "total_classes": "48"},
                    {"code": "23MXAE", "percentage": "87%", "attended": "32", "total_classes": "37"},
                    {"code": "23MXAF", "percentage": "75%", "attended": "27", "total_classes": "36"},
                    {"code": "23MXAO", "percentage": "79%", "attended": "29", "total_classes": "37"},
                    {"code": "23MXCA", "percentage": "80%", "attended": "31", "total_classes": "39"},
                    {"code": "23MXM4", "percentage": "88%", "attended": "21", "total_classes": "24"}
                ],
                "class_schedule": []
            },
            "studzone2": {}
        }

    def test_A_25mx227_course_title_resolution(self):
        """A. 25MX227 course title resolution:
           23MX37 -> MINI PROJECT
           23MXM4 -> PROFESSIONAL ETHICS
           23MXAT -> DevOps
           23MXAY -> SMART COMPUTING WITH ADVANCED PYTHON
        """
        title_map_227 = extract_student_title_map(self.doc_227)

        self.assertEqual(title_map_227.get("23MX37"), "MINI PROJECT")
        self.assertEqual(title_map_227.get("23MXM4"), "PROFESSIONAL ETHICS")
        self.assertEqual(title_map_227.get("23MXAT"), "DevOps")
        self.assertEqual(title_map_227.get("23MXAY"), "SMART COMPUTING WITH ADVANCED PYTHON")

        # Simulate fresh attendance change with generic / unpopulated titles
        sz1_fresh_227 = {
            "parsed_attendance": [
                {"code": "23MX37", "name": "", "percentage": "85%", "attended": "41", "total_classes": "48"},
                {"code": "23MXM4", "name": "Course 23MXM4", "percentage": "80%", "attended": "20", "total_classes": "25"},
                {"code": "23MXAT", "name": "", "percentage": "85%", "attended": "32", "total_classes": "38"},
                {"code": "23MXAY", "name": "Course 23MXAY", "percentage": "70%", "attended": "26", "total_classes": "37"}
            ]
        }

        notifs = detect_granular_changes("25MX227", self.doc_227, sz1_fresh_227, {})
        notif_map = {n["changeData"]["code"]: n for n in notifs}

        self.assertIn("23MX37", notif_map)
        self.assertEqual(notif_map["23MX37"]["changeData"]["subject"], "MINI PROJECT")
        self.assertIn("MINI PROJECT", notif_map["23MX37"]["description"])

        self.assertIn("23MXM4", notif_map)
        self.assertEqual(notif_map["23MXM4"]["changeData"]["subject"], "PROFESSIONAL ETHICS")
        self.assertIn("PROFESSIONAL ETHICS", notif_map["23MXM4"]["description"])

        self.assertIn("23MXAT", notif_map)
        self.assertEqual(notif_map["23MXAT"]["changeData"]["subject"], "DevOps")
        self.assertIn("DevOps", notif_map["23MXAT"]["description"])

        self.assertIn("23MXAY", notif_map)
        self.assertEqual(notif_map["23MXAY"]["changeData"]["subject"], "SMART COMPUTING WITH ADVANCED PYTHON")
        self.assertIn("SMART COMPUTING WITH ADVANCED PYTHON", notif_map["23MXAY"]["description"])

    def test_B_25mx232_course_title_resolution(self):
        """B. 25MX232 course title resolution:
           23MX37 -> MINI PROJECT
           23MXM4 -> PROFESSIONAL ETHICS
           23MXAF -> DATA MINING AND ANALYTICS
           23MXAO -> HUMAN COMPUTER INTERACTION
        """
        title_map_232 = extract_student_title_map(self.doc_232)

        self.assertEqual(title_map_232.get("23MX37"), "MINI PROJECT")
        self.assertEqual(title_map_232.get("23MXM4"), "PROFESSIONAL ETHICS")
        self.assertEqual(title_map_232.get("23MXAF"), "DATA MINING AND ANALYTICS")
        self.assertEqual(title_map_232.get("23MXAO"), "HUMAN COMPUTER INTERACTION")

        sz1_fresh_232 = {
            "parsed_attendance": [
                {"code": "23MX37", "name": "", "percentage": "90%", "attended": "45", "total_classes": "50"},
                {"code": "23MXM4", "name": "", "percentage": "92%", "attended": "23", "total_classes": "25"},
                {"code": "23MXAF", "name": "Course 23MXAF", "percentage": "80%", "attended": "29", "total_classes": "36"},
                {"code": "23MXAO", "name": "Course 23MXAO", "percentage": "85%", "attended": "32", "total_classes": "38"}
            ]
        }

        notifs = detect_granular_changes("25MX232", self.doc_232, sz1_fresh_232, {})
        notif_map = {n["changeData"]["code"]: n for n in notifs}

        self.assertIn("23MX37", notif_map)
        self.assertEqual(notif_map["23MX37"]["changeData"]["subject"], "MINI PROJECT")

        self.assertIn("23MXM4", notif_map)
        self.assertEqual(notif_map["23MXM4"]["changeData"]["subject"], "PROFESSIONAL ETHICS")

        self.assertIn("23MXAF", notif_map)
        self.assertEqual(notif_map["23MXAF"]["changeData"]["subject"], "DATA MINING AND ANALYTICS")

        self.assertIn("23MXAO", notif_map)
        self.assertEqual(notif_map["23MXAO"]["changeData"]["subject"], "HUMAN COMPUTER INTERACTION")

    def test_C_neutral_fallback_for_unknown_course(self):
        """C. A course with no verified title resolves neutrally to: Course <code>"""
        title = resolve_course_title("23MXXX", "", student_course_map={})
        self.assertEqual(title, "Course 23MXXX")

        title_placeholder = resolve_course_title("23MXXX", "Course 23MXXX", student_course_map={})
        self.assertEqual(title_placeholder, "Course 23MXXX")

        # Test within detect_granular_changes
        doc_unknown = {
            "rollNo": "25MX999",
            "baseline_initialized": True,
            "studzone1": {
                "parsed_attendance": [
                    {"code": "23MXXX", "percentage": "70%", "attended": "7", "total_classes": "10"}
                ]
            }
        }
        sz1_fresh = {
            "parsed_attendance": [
                {"code": "23MXXX", "name": "", "percentage": "80%", "attended": "8", "total_classes": "10"}
            ]
        }
        notifs = detect_granular_changes("25MX999", doc_unknown, sz1_fresh, {})
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0]["changeData"]["subject"], "Course 23MXXX")
        self.assertIn("Course 23MXXX attendance changed from 70% → 80%.", notifs[0]["description"])

    def test_D_cross_student_isolation(self):
        """D. One student's course names cannot leak into another student's notification."""
        map_227 = extract_student_title_map(self.doc_227)
        map_232 = extract_student_title_map(self.doc_232)

        # 25MX227 takes DevOps (23MXAT) and Advanced Python (23MXAY)
        self.assertIn("23MXAT", map_227)
        self.assertIn("23MXAY", map_227)
        # 25MX232 does NOT have 23MXAT or 23MXAY in their records
        self.assertNotIn("23MXAT", map_232)
        self.assertNotIn("23MXAY", map_232)

        # 25MX232 takes Data Mining and Analytics (23MXAF) and HCI (23MXAO)
        self.assertIn("23MXAF", map_232)
        self.assertIn("23MXAO", map_232)
        # 25MX227 does NOT have 23MXAF or 23MXAO in their records
        self.assertNotIn("23MXAF", map_227)
        self.assertNotIn("23MXAO", map_227)

        # Resolving 23MXAT with 232's map yields neutral fallback, NOT 227's title
        title_for_232 = resolve_course_title("23MXAT", "", student_course_map=map_232)
        self.assertEqual(title_for_232, "Course 23MXAT")

    def test_E_deduplication_and_change_hash(self):
        """E. Existing notification deduplication / changeHash behavior remains intact."""
        h1 = compute_change_hash("25MX227", "attendance", "Attendance", "Attendance Updated", "MINI PROJECT attendance changed from 80% → 85%.", "23MX37_80%_85%")
        h2 = compute_change_hash("25MX227", "attendance", "Attendance", "Attendance Updated", "MINI PROJECT attendance changed from 80% → 85%.", "23MX37_80%_85%")
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)  # Valid SHA-256

        # Distinct changes produce distinct hashes
        h3 = compute_change_hash("25MX227", "attendance", "Attendance", "Attendance Updated", "MINI PROJECT attendance changed from 80% → 86%.", "23MX37_80%_86%")
        self.assertNotEqual(h1, h3)


if __name__ == '__main__':
    unittest.main()
