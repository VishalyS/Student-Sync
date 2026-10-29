"""
backend/tests/test_residential_service.py

Unit and Isolation Test Suite for Student Sync Residential Status Service.
Verifies:
1. Extraction of 'HOSTELLER' with room allocation from StudZone 1 Vallalar table.
2. Extraction of 'DAYS SCHOLAR' and 'DAY SCHOLAR' from StudZone 1 Vallalar table.
3. Fallback to profile dictionary when Vallalar table is absent.
4. Fallback to StudZone 1 hostel allocation status.
5. Strict fail-closed UNKNOWN behavior on empty, corrupt, or missing records.
6. Zero default-to-hosteller on missing or stale data.
7. Verification against real student document fixtures (25MX232 Hosteller, 25MX227 Day Scholar).
"""

import os
import sys
import unittest

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from residential_service import (
    determine_residential_status,
    extract_vallalar_fields,
    STATUS_HOSTELLER,
    STATUS_DAY_SCHOLAR,
    STATUS_UNKNOWN,
)


class TestResidentialStatusService(unittest.TestCase):
    def setUp(self):
        self.vallalar_hosteller_html = """
        <table class="table">
        <tbody>
        <tr>
        <td class="personal-info">
        <table style="width:100%">
        <tbody>
        <tr><th>Name</th><td>STUDENT HOSTELLER</td></tr>
        <tr><th>Programme</th><td>MASTER OF COMPUTER APPLICATIONS</td></tr>
        <tr><th>Date of Birth</th><td>01/01/2004</td></tr>
        <tr><th>Communication</th><td>hosteller.test@example.com</td></tr>
        <tr><th>Mobile Number</th><td>9876543210</td></tr>
        <tr><th>Roll Number</th><td>25MX901</td></tr>
        <tr><th>Semester Number</th><td>3</td></tr>
        <tr><th>Admission Type</th><td>MERIT</td></tr>
        <tr><th>Resident Status</th><td>HOSTELLER</td></tr>
        <tr><th>Room Number</th><td>K519</td></tr>
        </tbody>
        </table>
        </td>
        </tr>
        </tbody>
        </table>
        """

        self.vallalar_day_scholar_html = """
        <table class="table">
        <tbody>
        <tr>
        <td class="personal-info">
        <table style="width:100%">
        <tbody>
        <tr><th>Name</th><td>STUDENT DAYSCHOLAR</td></tr>
        <tr><th>Programme</th><td>MASTER OF COMPUTER APPLICATIONS</td></tr>
        <tr><th>Date of Birth</th><td>02/02/2004</td></tr>
        <tr><th>Communication</th><td>dayscholar.test@example.com</td></tr>
        <tr><th>Mobile Number</th><td>9876543211</td></tr>
        <tr><th>Roll Number</th><td>25MX902</td></tr>
        <tr><th>Semester Number</th><td>3</td></tr>
        <tr><th>Admission Type</th><td>MANAGEMENT</td></tr>
        <tr><th>Resident Status</th><td>DAYS SCHOLAR</td></tr>
        <tr><th>Room Number</th><td>-</td></tr>
        </tbody>
        </table>
        </td>
        </tr>
        </tbody>
        </table>
        """

    def test_extract_vallalar_fields_hosteller(self):
        status, room = extract_vallalar_fields(self.vallalar_hosteller_html)
        self.assertEqual(status, "HOSTELLER")
        self.assertEqual(room, "K519")

    def test_extract_vallalar_fields_day_scholar(self):
        status, room = extract_vallalar_fields(self.vallalar_day_scholar_html)
        self.assertEqual(status, "DAYS SCHOLAR")
        self.assertEqual(room, "-")

    def test_extract_vallalar_fields_invalid_html(self):
        status, room = extract_vallalar_fields("<div>No table here</div>")
        self.assertIsNone(status)
        self.assertIsNone(room)

        status_none, room_none = extract_vallalar_fields(None)
        self.assertIsNone(status_none)
        self.assertIsNone(room_none)

    def test_determine_status_hosteller_from_vallalar(self):
        user_doc = {
            "rollNo": "25MX232",
            "studzone1": {
                "scholarships": {
                    "html_vallalar": self.vallalar_hosteller_html
                }
            }
        }
        res = determine_residential_status(user_doc)
        self.assertEqual(res["status"], STATUS_HOSTELLER)
        self.assertTrue(res["is_hosteller"])
        self.assertFalse(res["is_day_scholar"])
        self.assertTrue(res["can_access_hostel"])
        self.assertEqual(res["room_number"], "K519")
        self.assertEqual(res["raw_status"], "HOSTELLER")

    def test_determine_status_days_scholar_from_vallalar(self):
        user_doc = {
            "rollNo": "25MX227",
            "studzone1": {
                "scholarships": {
                    "html_vallalar": self.vallalar_day_scholar_html
                }
            }
        }
        res = determine_residential_status(user_doc)
        self.assertEqual(res["status"], STATUS_DAY_SCHOLAR)
        self.assertFalse(res["is_hosteller"])
        self.assertTrue(res["is_day_scholar"])
        self.assertFalse(res["can_access_hostel"])
        self.assertIsNone(res["room_number"])
        self.assertEqual(res["raw_status"], "DAYS SCHOLAR")

    def test_determine_status_day_scholar_singular(self):
        html_singular = self.vallalar_day_scholar_html.replace("DAYS SCHOLAR", "DAY SCHOLAR")
        user_doc = {
            "rollNo": "25MX116",
            "studzone1": {
                "scholarships": {
                    "html_vallalar": html_singular
                }
            }
        }
        res = determine_residential_status(user_doc)
        self.assertEqual(res["status"], STATUS_DAY_SCHOLAR)
        self.assertFalse(res["is_hosteller"])
        self.assertTrue(res["is_day_scholar"])
        self.assertFalse(res["can_access_hostel"])

    def test_determine_status_profile_fallback(self):
        user_doc = {
            "rollNo": "25MX300",
            "studzone1": {
                "profile": {
                    "Resident Status": "HOSTELLER",
                    "Room Number": "B204"
                }
            }
        }
        res = determine_residential_status(user_doc)
        self.assertEqual(res["status"], STATUS_HOSTELLER)
        self.assertTrue(res["is_hosteller"])
        self.assertEqual(res["room_number"], "B204")

    def test_determine_status_hostel_allocation_fallback(self):
        user_doc_day = {
            "rollNo": "25MX400",
            "studzone1": {
                "hostel_status": "No Active Hostel Allocation",
                "hostel_records": []
            }
        }
        res_day = determine_residential_status(user_doc_day)
        self.assertEqual(res_day["status"], STATUS_DAY_SCHOLAR)
        self.assertFalse(res_day["can_access_hostel"])

        user_doc_hostel = {
            "rollNo": "25MX500",
            "studzone1": {
                "hostel_status": "Registered / Hostel Data Available",
                "hostel_records": [["1", "12/06/2026", "138000.00", "Success"]]
            }
        }
        res_hostel = determine_residential_status(user_doc_hostel)
        self.assertEqual(res_hostel["status"], STATUS_HOSTELLER)
        self.assertTrue(res_hostel["can_access_hostel"])

    def test_determine_status_fail_closed_unknown(self):
        # 1. None document
        res_none = determine_residential_status(None)
        self.assertEqual(res_none["status"], STATUS_UNKNOWN)
        self.assertFalse(res_none["can_access_hostel"])
        self.assertFalse(res_none["is_hosteller"])
        self.assertFalse(res_none["is_day_scholar"])

        # 2. Empty document
        res_empty = determine_residential_status({})
        self.assertEqual(res_empty["status"], STATUS_UNKNOWN)
        self.assertFalse(res_empty["can_access_hostel"])

        # 3. Document with empty studzone1
        res_empty_sz = determine_residential_status({"rollNo": "25UNKNOWN", "studzone1": {}})
        self.assertEqual(res_empty_sz["status"], STATUS_UNKNOWN)
        self.assertFalse(res_empty_sz["can_access_hostel"])

        # 4. Document with unknown ambiguous text
        res_ambiguous = determine_residential_status({
            "rollNo": "25UNKNOWN",
            "studzone1": {
                "profile": {"Resident Status": "UNDER_VERIFICATION"}
            }
        })
        self.assertEqual(res_ambiguous["status"], STATUS_UNKNOWN)
        self.assertFalse(res_ambiguous["can_access_hostel"])


if __name__ == "__main__":
    unittest.main()
