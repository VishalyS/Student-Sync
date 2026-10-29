import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from notifications.change_detector import detect_granular_changes, process_normalized_event


def create_student_fixture(residential_status="HOSTELLER", hostel_status="Hostel Room Block A-204"):
    html_status = "HOSTELLER" if residential_status == "HOSTELLER" else "DAYS SCHOLAR"
    room_val = "K519" if residential_status == "HOSTELLER" else "-"

    html = f"""
    <table>
        <tr><th>Resident Status</th><td>{html_status}</td></tr>
        <tr><th>Room Number</th><td>{room_val}</td></tr>
    </table>
    """ if residential_status != "UNKNOWN" else ""

    return {
        "rollNo": "25MX232",
        "name": "TEST STUDENT",
        "baseline_initialized": True,
        "studzone1": {
            "scholarships": {"html_vallalar": html} if html else {},
            "hostel_status": hostel_status,
            "parsed_attendance": [
                {"code": "24MX11", "name": "Data Structures", "percentage": "82%", "attended": "41", "total_classes": "50"}
            ],
            "parsed_marks": [
                {"code": "24MX11", "name": "DBMS", "ca1": "18", "ca2": "18", "ca3": "-", "total": "36"}
            ]
        },
        "studzone2": {
            "parsed_results": [],
            "cgpa": "8.5"
        }
    }


class TestHostelNotifications:

    def test_hosteller_receives_hostel_change_notification(self):
        """Hosteller with updated hostel status generates a notification."""
        user = create_student_fixture("HOSTELLER", "Block A-204")
        fresh_sz1 = {"hostel_status": "Block B-118"}

        notifs = detect_granular_changes("25MX232", user, fresh_sz1, user["studzone2"])

        hostel_notifs = [n for n in notifs if n.get("category") == "hostel"]
        assert len(hostel_notifs) == 1
        assert hostel_notifs[0]["title"] == "Hostel Allocation Updated"
        assert "Block B-118" in hostel_notifs[0]["description"]

    def test_day_scholar_suppresses_hostel_change_notification(self):
        """Day Scholar receives ZERO hostel notifications even if hostel_status changes."""
        user = create_student_fixture("DAY_SCHOLAR", "No Active Hostel Allocation")
        fresh_sz1 = {"hostel_status": "No Active Hostel Allocation — Updated"}

        notifs = detect_granular_changes("25MX232", user, fresh_sz1, user["studzone2"])

        hostel_notifs = [n for n in notifs if n.get("category") == "hostel"]
        assert len(hostel_notifs) == 0

    def test_unknown_status_suppresses_hostel_change_notification(self):
        """Unknown status student (fail-closed) receives ZERO hostel notifications."""
        user = create_student_fixture("UNKNOWN", "")
        user["studzone1"]["hostel_status"] = ""
        fresh_sz1 = {"hostel_status": "Block C-301"}

        notifs = detect_granular_changes("25MX232", user, fresh_sz1, user["studzone2"])

        hostel_notifs = [n for n in notifs if n.get("category") == "hostel"]
        assert len(hostel_notifs) == 0

    def test_academic_notifications_unaffected_for_day_scholars(self):
        """Day scholars continue to receive attendance, marks, and academic notifications normally."""
        user = create_student_fixture("DAY_SCHOLAR", "No Active Hostel Allocation")
        fresh_sz1 = {
            "parsed_attendance": [
                {"code": "24MX11", "name": "Data Structures", "percentage": "88%", "attended": "44", "total_classes": "50"}
            ]
        }

        notifs = detect_granular_changes("25MX232", user, fresh_sz1, user["studzone2"])

        att_notifs = [n for n in notifs if n.get("category") == "attendance"]
        assert len(att_notifs) == 1
        assert "82% → 88%" in att_notifs[0]["description"]

    def test_process_normalized_event_hostel_allowed_for_hosteller(self):
        """Hostel normalized event is processed for verified HOSTELLER."""
        user = create_student_fixture("HOSTELLER", "Block A-204")
        event = {
            "category": "hostel",
            "type": "hostel_leave",
            "title": "Leave Request Approved",
            "message": "Your weekend home pass has been sanctioned.",
            "source": "Hostel Portal",
            "module": "Hostel Leave"
        }

        result = process_normalized_event("25MX232", event, user)
        assert result is not None
        assert result["title"] == "Leave Request Approved"
        assert result["category"] == "hostel"

    def test_process_normalized_event_hostel_rejected_for_day_scholar(self):
        """Hostel normalized event returns None for DAY_SCHOLAR."""
        user = create_student_fixture("DAY_SCHOLAR", "No Active Hostel Allocation")
        event = {
            "category": "hostel",
            "type": "hostel_fee",
            "title": "Mess Fee Due",
            "message": "Monthly mess bill generated.",
            "source": "Hostel Portal",
            "module": "Hostel Fee"
        }

        result = process_normalized_event("25MX232", event, user)
        assert result is None

    def test_process_normalized_event_hostel_rejected_for_unknown(self):
        """Hostel normalized event returns None for UNKNOWN / missing student doc."""
        user = create_student_fixture("UNKNOWN", "")
        event = {
            "category": "hostel",
            "type": "hostel",
            "title": "Room Inspection",
            "message": "Inspection scheduled for tomorrow.",
            "source": "Hostel Portal",
            "module": "Hostel"
        }

        # When doc has unknown status
        assert process_normalized_event("25MX232", event, user) is None
        # When doc is None
        assert process_normalized_event("25MX232", event, None) is None

    def test_process_normalized_event_academic_allowed_for_all(self):
        """Academic events pass through regardless of residential status."""
        day_scholar = create_student_fixture("DAY_SCHOLAR", "No Active Hostel Allocation")
        event = {
            "category": "academics",
            "type": "marks",
            "title": "CA Marks Released",
            "message": "DBMS CA2 marks have been uploaded.",
            "source": "StudZone 1",
            "module": "Academics"
        }

        result = process_normalized_event("25MX232", event, day_scholar)
        assert result is not None
        assert result["title"] == "CA Marks Released"
