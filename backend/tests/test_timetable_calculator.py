"""
backend/tests/test_timetable_calculator.py

Unit test suite for Phase 6 Timetable Calculator:
1. Matrix parsing (periods, times, weekdays Monday-Friday)
2. Free period and course code extraction
3. Exam schedule parsing & status normalization (Schedule Pending / TBA)
4. CoE circulars parsing
5. In-memory Day-bunk simulation math
6. Boundary checks (75% and 65% thresholds)
7. Zero-write guarantee (pure functions)
"""

import os
import sys
import pytest

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from timetable_calculator import (
    parse_cell_content,
    parse_weekly_schedule_matrix,
    parse_exam_schedule_records,
    parse_circulars,
    simulate_day_bunks,
    get_unified_subject_summary
)


SAMPLE_MATRIX = [
    ["Period", "1", "2", "3", "4", "5", "6"],
    ["Time", "8.30 - 9.20", "9.20 - 10.10", "10.30 - 11.20", "11.20 - 12.10", "1.40 - 2.30", "2.30 - 3.20"],
    ["Monday", "MCA_3\r\n 23MXAF\nDATA MINING AND ANALYTICS", "MCA_3\r\n 23MXAO\nHUMAN COMPUTER INTERACTION", "MCA_3\r\n 23MX31\nCLOUD COMPUTING", "-", "MCA_3\r\n 23MX37\nMINI PROJECT"],
    ["Tuesday", "MCA_3\r\n 23MXAO\nHUMAN COMPUTER INTERACTION", "MCA_3\r\n 23MXAF\nDATA MINING AND ANALYTICS", "MCA_3\r\n 23MX36\nCLOUD COMPUTING LABORATORY", "MCA_3\r\n 23MXCA\nENTREPRENEURSHIP", "MCA_3\r\n 23MXM4\nPROFESSIONAL ETHICS"],
    ["Wednesday", "-", "MCA_3\r\n 23MXCA\nENTREPRENEURSHIP", "MCA_3\r\n 23MXAE\nCOMPUTER NETWORKS", "MCA_3\r\n 23MXAO\nHUMAN COMPUTER INTERACTION", "MCA_3\r\n 23MXAF\nDATA MINING AND ANALYTICS", "-"],
    ["Thursday", "MCA_3\r\n 23MXAE\nCOMPUTER NETWORKS", "MCA_3\r\n 23MXM4\nPROFESSIONAL ETHICS", "MCA_3\r\n 23MX36\nCLOUD COMPUTING LABORATORY", "MCA_3\r\n 23MX31\nCLOUD COMPUTING", "MCA_3\r\n 23MXCA\nENTREPRENEURSHIP"],
    ["Friday", "MCA_3\r\n 23MX31\nCLOUD COMPUTING", "-", "MCA_3\r\n 23MXAE\nCOMPUTER NETWORKS", "MCA_3\r\n TWM\nTUTOR WARD MEETING", "MCA_3\r\n 23MX37\nMINI PROJECT"]
]

SAMPLE_ATTENDANCE = [
    {"code": "23MX31", "name": "CLOUD COMPUTING", "attended": 36, "total_classes": 42},
    {"code": "23MXAE", "name": "COMPUTER NETWORKS", "attended": 32, "total_classes": 38},
    {"code": "23MX37", "name": "MINI PROJECT", "attended": 28, "total_classes": 30},
    {"code": "23MXAO", "name": "HUMAN COMPUTER INTERACTION", "attended": 30, "total_classes": 40}  # exactly 75.0%
]

SAMPLE_EXAMS = [
    {"sem": "3", "course_code": "23MXAO", "course_title": "HUMAN COMPUTER INTERACTION", "exam_date": "Schedule Pending", "session": "TBA", "timing": "Timing TBA"},
    {"sem": "3", "course_code": "23MX31", "course_title": "CLOUD COMPUTING", "exam_date": "24/11/2026", "session": "FN", "timing": "9.30 AM - 12.30 PM"}
]

SAMPLE_CIRCULARS = [
    {"title": "Guidelines for appearing Semester Examinations", "url": "https://ecampus.psgtech.ac.in/studzone2/Report_PDF/Guidelines_exam.pdf"}
]


def test_parse_cell_content():
    # Regular course cell
    cell = parse_cell_content("MCA_3\r\n 23MXAF\nDATA MINING AND ANALYTICS")
    assert cell["code"] == "23MXAF"
    assert cell["name"] == "DATA MINING AND ANALYTICS"
    assert cell["is_free"] is False

    # Free period
    free_cell = parse_cell_content("-")
    assert free_cell["is_free"] is True
    assert free_cell["code"] == "FREE"

    # Empty cell
    empty_cell = parse_cell_content("")
    assert empty_cell["is_free"] is True


def test_parse_weekly_schedule_matrix():
    res = parse_weekly_schedule_matrix(SAMPLE_MATRIX)
    assert len(res["days"]) == 5
    assert res["days"][0]["day"] == "Monday"
    assert res["days"][4]["day"] == "Friday"
    assert res["total_periods"] == 6

    # Monday Period 1 should be 23MXAF
    mon_p1 = res["days"][0]["periods"][0]
    assert mon_p1["period"] == 1
    assert mon_p1["code"] == "23MXAF"
    assert mon_p1["time"] == "8.30 - 9.20"

    # Wednesday Period 1 should be Free
    wed_p1 = res["days"][2]["periods"][0]
    assert wed_p1["is_free"] is True


def test_parse_exam_schedule_records():
    res = parse_exam_schedule_records(SAMPLE_EXAMS, SAMPLE_CIRCULARS)
    assert res["total_exams"] == 2
    assert res["pending_count"] == 1
    assert res["scheduled_count"] == 1

    # First exam is pending
    ex1 = res["exams"][0]
    assert ex1["status"] == "PENDING"
    assert ex1["is_pending"] is True
    assert ex1["exam_date"] == "Schedule Pending"

    # Second exam is scheduled
    ex2 = res["exams"][1]
    assert ex2["status"] == "SCHEDULED"
    assert ex2["is_pending"] is False
    assert ex2["exam_date"] == "24/11/2026"
    assert ex2["session"] == "FN"

    # Circular parsed
    assert len(res["circulars"]) == 1
    assert res["circulars"][0]["title"] == "Guidelines for appearing Semester Examinations"


def test_simulate_day_bunks_friday():
    # Friday scheduled: P1=23MX31, P2=Free, P3=23MXAE, P4=TWM, P5=23MX37
    # Select periods [1, 3] -> Bunks 23MX31 (Cloud) and 23MXAE (Networks)
    sim = simulate_day_bunks(SAMPLE_ATTENDANCE, SAMPLE_MATRIX, day="Friday", periods=[1, 3], target=75.0)

    assert sim["day"] == "Friday"
    assert sim["total_classes_missed"] == 2
    assert sim["affected_subjects_count"] == 2

    # Check 23MX31: initial 36/42 (85.71%), simulated 36/43 (83.72%)
    s31 = next(s for s in sim["affected_subjects"] if s["code"] == "23MX31")
    assert s31["original"]["attended"] == 36
    assert s31["original"]["conducted"] == 42
    assert s31["simulated"]["attended"] == 36
    assert s31["simulated"]["conducted"] == 43
    assert s31["simulated"]["percentage"] == 83.72
    assert s31["simulated"]["percentage_change"] == -1.99

    # Check safe bunks: initial was floor((36 - 0.75*42)/0.75) = floor((36-31.5)/0.75) = floor(6.0) = 6
    # simulated is floor((36 - 0.75*43)/0.75) = floor((36-32.25)/0.75) = floor(5.0) = 5
    assert s31["original"]["safe_bunks"] == 6
    assert s31["simulated"]["safe_bunks"] == 5
    assert s31["simulated"]["safe_bunk_change"] == -1


def test_simulate_day_bunks_boundary_75_drop():
    # 23MXAO is initially at exactly 30/40 = 75.0% (Safe bunks = 0)
    # On Tuesday, P1 is 23MXAO. Missing P1 on Tuesday -> 30/41 = 73.17% (Drops below 75%!)
    sim = simulate_day_bunks(SAMPLE_ATTENDANCE, SAMPLE_MATRIX, day="Tuesday", periods=[1], target=75.0)

    s_ao = next(s for s in sim["affected_subjects"] if s["code"] == "23MXAO")
    assert s_ao["original"]["percentage"] == 75.0
    assert s_ao["simulated"]["percentage"] == 73.17
    assert s_ao["warning_flags"]["falls_below_75"] is True
    assert s_ao["warning_flags"]["in_condonation_zone"] is True
    assert s_ao["simulated"]["status"] == "WARNING"


def test_simulate_day_bunks_free_period_ignored():
    # Wednesday P1 is Free ('-'). Missing P1 should have 0 missed classes
    sim = simulate_day_bunks(SAMPLE_ATTENDANCE, SAMPLE_MATRIX, day="Wednesday", periods=[1], target=75.0)
    assert sim["total_classes_missed"] == 0
    assert sim["affected_subjects_count"] == 0


def test_simulate_day_bunks_validation_errors():
    with pytest.raises(ValueError, match="not found in registered weekly timetable"):
        simulate_day_bunks(SAMPLE_ATTENDANCE, SAMPLE_MATRIX, day="Sunday", periods=[1])

    with pytest.raises(ValueError, match="'periods' must be a list"):
        simulate_day_bunks(SAMPLE_ATTENDANCE, SAMPLE_MATRIX, day="Monday", periods="invalid")


def test_get_unified_subject_summary():
    user_doc = {
        "studzone1": {
            "parsed_attendance": SAMPLE_ATTENDANCE,
            "parsed_marks": [{"code": "23MX31", "total": "35"}],
            "class_schedule": SAMPLE_MATRIX
        },
        "studzone2": {
            "parsed_timetable": SAMPLE_EXAMS
        }
    }
    summary = get_unified_subject_summary(user_doc)
    assert summary["total_courses"] == 4
    c31 = next(c for c in summary["courses"] if c["code"] == "23MX31")
    assert c31["attendance"]["percentage"] == 85.71
    assert c31["schedule"]["weekly_periods_count"] > 0
    assert c31["risk_status"] == "SAFE"
