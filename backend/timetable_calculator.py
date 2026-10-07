"""
Student Sync — Timetable Intelligence & Day-Bunk Calculation Engine (Phase 6)
Pure mathematical & parsing helper for weekly class timetables, end-semester
examination schedules, official CoE circulars, and in-memory day-bunk simulations.

CRITICAL INVARIANTS:
- 100% READ-ONLY & IN-MEMORY: NEVER writes to MongoDB.
- Reuses attendance formulas from attendance_calculator without modifying it.
- Never invents missing exam dates or circular links.
"""

import math
import re
from datetime import datetime

# Import verified calculation utilities from attendance_calculator
from attendance_calculator import (
    calculate_attendance,
    calculate_safe_bunks,
    calculate_required_classes,
    get_attendance_status
)


TIMING_SLOTS_DEFAULT = [
    {"period": 1, "time": "8.30 - 9.20"},
    {"period": 2, "time": "9.20 - 10.10"},
    {"period": 3, "time": "10.30 - 11.20"},
    {"period": 4, "time": "11.20 - 12.10"},
    {"period": 5, "time": "1.40 - 2.30"},
    {"period": 6, "time": "2.30 - 3.20"}
]


def parse_cell_content(cell_str):
    """
    Parses a single cell from the StudZone 1 class schedule table.
    Examples:
        'MCA_3\\r\\n 23MXAF\\nDATA MINING AND ANALYTICS'
        'MCA_3\\r\\n 23MX31\\nCLOUD COMPUTING'
        'MCA_3\\r\\n TWM\\nTUTOR WARD MEETING'
        '-'
    """
    raw = str(cell_str or "").strip()
    if not raw or raw == "-" or raw == "—":
        return {
            "code": "FREE",
            "name": "Free Period",
            "section": "",
            "raw": "-",
            "is_free": True
        }

    lines = [line.strip() for line in re.split(r'[\r\n]+', raw) if line.strip()]
    section = ""
    code = ""
    name = ""

    if len(lines) == 1:
        name = lines[0]
    elif len(lines) == 2:
        # Check if line 0 looks like section or code
        if re.search(r'\b[0-9]{2}[A-Z]{2}[A-Z0-9]{2,4}\b', lines[0]):
            code = lines[0]
            name = lines[1]
        else:
            section = lines[0]
            name = lines[1]
    elif len(lines) >= 3:
        section = lines[0]
        code = lines[1]
        name = " ".join(lines[2:])

    # Regex fallback if code was ambiguous or in another position
    if not code or len(code) > 12:
        match = re.search(r'\b([0-9]{2}[A-Z]{2}[A-Z0-9]{2,4}|TWM)\b', raw)
        if match:
            code = match.group(1)

    # Clean up name if it duplicates code
    if code and name.startswith(code):
        name = name[len(code):].strip()

    return {
        "code": code or "COURSE",
        "name": name or raw,
        "section": section,
        "raw": raw,
        "is_free": False
    }


def parse_weekly_schedule_matrix(class_schedule_matrix):
    """
    Parses the 7-row class_schedule 2D matrix from StudZone 1:
        Row 0: Header row (['Period', '1', '2', '3', '4', '5', '6'])
        Row 1: Time row (['Time', '8.30 - 9.20', ...])
        Rows 2-6: Weekday rows (Monday to Friday)
    """
    if not class_schedule_matrix or not isinstance(class_schedule_matrix, list) or len(class_schedule_matrix) < 2:
        return {
            "days": [],
            "timing_slots": TIMING_SLOTS_DEFAULT,
            "total_periods": 6,
            "course_codes": []
        }

    # Extract timings from Row 0 and Row 1
    periods_row = class_schedule_matrix[0] if len(class_schedule_matrix) > 0 else []
    times_row = class_schedule_matrix[1] if len(class_schedule_matrix) > 1 else []

    timing_slots = []
    max_periods = max(6, len(periods_row) - 1, len(times_row) - 1)
    for p in range(1, max_periods + 1):
        time_text = times_row[p].strip() if p < len(times_row) and str(times_row[p]).strip() else f"Period {p}"
        timing_slots.append({"period": p, "time": time_text})

    valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    days_data = []
    all_codes = set()

    for row in class_schedule_matrix[2:]:
        if not row or not isinstance(row, list) or len(row) == 0:
            continue
        day_raw = str(row[0]).strip().capitalize()
        # Match against valid days
        matched_day = None
        for vd in valid_days:
            if vd.lower() == day_raw.lower():
                matched_day = vd
                break

        day_name = matched_day or day_raw
        periods = []

        for p_idx in range(1, len(timing_slots) + 1):
            t_slot = timing_slots[p_idx - 1]
            raw_cell = row[p_idx] if p_idx < len(row) else "-"
            cell_parsed = parse_cell_content(raw_cell)

            periods.append({
                "period": p_idx,
                "time": t_slot["time"],
                "code": cell_parsed["code"],
                "name": cell_parsed["name"],
                "section": cell_parsed["section"],
                "is_free": cell_parsed["is_free"],
                "raw": cell_parsed["raw"]
            })

            if not cell_parsed["is_free"] and cell_parsed["code"] != "FREE" and cell_parsed["code"] != "TWM":
                all_codes.add(cell_parsed["code"])

        # Determine stats for the day
        scheduled_count = sum(1 for p in periods if not p["is_free"])
        free_count = sum(1 for p in periods if p["is_free"])

        days_data.append({
            "day": day_name,
            "periods": periods,
            "scheduled_classes": scheduled_count,
            "free_periods": free_count
        })

    return {
        "days": days_data,
        "timing_slots": timing_slots,
        "total_periods": len(timing_slots),
        "course_codes": sorted(list(all_codes))
    }


def parse_exam_schedule_records(parsed_timetable, circulars=None):
    """
    Parses and standardizes end-semester examination records from StudZone 2.
    Accurately reflects official status (e.g. 'Schedule Pending', 'TBA') without
    inventing or predicting dates.
    """
    records = []
    pending_count = 0
    scheduled_count = 0

    raw_list = parsed_timetable if isinstance(parsed_timetable, list) else []

    for item in raw_list:
        if not isinstance(item, dict):
            continue

        course_code = str(item.get("course_code") or item.get("code") or "").strip().upper()
        course_title = str(item.get("course_title") or item.get("title") or item.get("name") or "").strip()
        exam_date = str(item.get("exam_date") or item.get("date") or "").strip()
        session = str(item.get("session") or item.get("slot") or "").strip()
        timing = str(item.get("timing") or "").strip()
        sem = str(item.get("sem") or item.get("semester") or "").strip()

        # Classify status safely
        is_pending = False
        if not exam_date or "pending" in exam_date.lower() or "tba" in exam_date.lower():
            is_pending = True
            exam_date_display = "Schedule Pending"
            status = "PENDING"
            pending_count += 1
        else:
            exam_date_display = exam_date
            status = "SCHEDULED"
            scheduled_count += 1

        session_display = session if session and "tba" not in session.lower() else "TBA"
        timing_display = timing if timing and "tba" not in timing.lower() else "Timing TBA"

        records.append({
            "sem": sem or "Current",
            "course_code": course_code or "COURSE",
            "course_title": course_title or "Subject",
            "exam_date": exam_date_display,
            "session": session_display,
            "timing": timing_display,
            "status": status,
            "is_pending": is_pending
        })

    parsed_circulars = parse_circulars(circulars) if circulars else []

    return {
        "exams": records,
        "total_exams": len(records),
        "pending_count": pending_count,
        "scheduled_count": scheduled_count,
        "all_pending": pending_count == len(records) if records else True,
        "circulars": parsed_circulars
    }


def parse_circulars(circulars_list):
    """
    Standardizes official CoE examination circulars from StudZone 2.
    Preserves exact official URL and title.
    """
    if not circulars_list or not isinstance(circulars_list, list):
        return []

    parsed = []
    for c in circulars_list:
        if isinstance(c, dict) and c.get("title"):
            parsed.append({
                "title": str(c.get("title")).strip(),
                "url": str(c.get("url") or "").strip(),
                "source": "PSG College of Technology Controller of Examinations"
            })
    return parsed


def simulate_day_bunks(parsed_attendance_list, class_schedule_matrix, day, periods=None, target=75.0):
    """
    Interactive In-Memory Day-Bunk Simulator:
    Evaluates attendance shifts if a student bunks selected class periods on a given weekday.

    Args:
        parsed_attendance_list (list): Student's current parsed_attendance list.
        class_schedule_matrix (list): Student's 2D class_schedule matrix.
        day (str): Weekday name (e.g. 'Monday', 'Friday').
        periods (list of int, optional): Selected period numbers (1-6). Defaults to all scheduled classes on that day.
        target (float): Regulatory target percentage (default: 75.0).

    Returns:
        dict: In-memory simulation response with subject-level and aggregate shifts.
    """
    weekly = parse_weekly_schedule_matrix(class_schedule_matrix)
    target_day_name = str(day or "").strip().capitalize()

    # Find the requested day's periods
    day_entry = None
    for d in weekly["days"]:
        if d["day"].lower() == target_day_name.lower():
            day_entry = d
            break

    if not day_entry:
        raise ValueError(f"Day '{day}' not found in registered weekly timetable.")

    # If periods not specified, default to all periods scheduled for that day
    scheduled_periods = [p["period"] for p in day_entry["periods"] if not p["is_free"]]
    selected_periods = periods if periods is not None else scheduled_periods

    if not isinstance(selected_periods, list):
        raise ValueError("'periods' must be a list of period numbers.")

    # Normalize attendance lookup by course code
    att_lookup = {}
    total_attended_orig = 0
    total_conducted_orig = 0

    if parsed_attendance_list and isinstance(parsed_attendance_list, list):
        for sub in parsed_attendance_list:
            code = str(sub.get("code") or "").strip().upper()
            try:
                att = int(float(sub.get("attended", 0)))
                cond = int(float(sub.get("total_classes", sub.get("conducted", 0))))
            except (ValueError, TypeError):
                att, cond = 0, 0

            att_lookup[code] = {
                "name": str(sub.get("name") or code),
                "attended": att,
                "conducted": cond
            }
            total_attended_orig += att
            total_conducted_orig += cond

    # Count missed classes per course on this day for the selected periods
    missed_counts_by_code = {}
    selected_period_details = []

    for p_num in selected_periods:
        # Match period in day_entry
        matched_period = next((p for p in day_entry["periods"] if p["period"] == p_num), None)
        if not matched_period:
            continue

        selected_period_details.append({
            "period": matched_period["period"],
            "time": matched_period["time"],
            "code": matched_period["code"],
            "name": matched_period["name"],
            "is_free": matched_period["is_free"]
        })

        if matched_period["is_free"]:
            continue

        code = matched_period["code"].upper()
        missed_counts_by_code[code] = missed_counts_by_code.get(code, 0) + 1

    # Compute subject-level simulation
    affected_subjects = []
    total_additional_missed = sum(missed_counts_by_code.values())

    for code, missed_count in missed_counts_by_code.items():
        base_sub = att_lookup.get(code)
        orig_att = base_sub["attended"] if base_sub else 0
        orig_cond = base_sub["conducted"] if base_sub else 0
        sub_name = base_sub["name"] if base_sub else code

        orig_pct = calculate_attendance(orig_att, orig_cond)
        orig_status = get_attendance_status(orig_pct)
        orig_bunks = calculate_safe_bunks(orig_att, orig_cond, target=target)
        orig_req = calculate_required_classes(orig_att, orig_cond, target=target)

        sim_att = orig_att
        sim_cond = orig_cond + missed_count
        sim_pct = calculate_attendance(sim_att, sim_cond)
        sim_status = get_attendance_status(sim_pct)
        sim_bunks = calculate_safe_bunks(sim_att, sim_cond, target=target)
        sim_req = calculate_required_classes(sim_att, sim_cond, target=target)

        delta_pct = round(sim_pct - orig_pct, 2)
        delta_bunks = sim_bunks - orig_bunks

        falls_below_75 = (orig_pct >= 75.0 and sim_pct < 75.0)
        falls_below_65 = (orig_pct >= 65.0 and sim_pct < 65.0)

        affected_subjects.append({
            "code": code,
            "name": sub_name,
            "missed_classes_today": missed_count,
            "original": {
                "attended": orig_att,
                "conducted": orig_cond,
                "percentage": orig_pct,
                "status": orig_status,
                "safe_bunks": orig_bunks,
                "required_classes": orig_req
            },
            "simulated": {
                "attended": sim_att,
                "conducted": sim_cond,
                "percentage": sim_pct,
                "status": sim_status,
                "safe_bunks": sim_bunks,
                "required_classes": sim_req,
                "percentage_change": delta_pct,
                "safe_bunk_change": delta_bunks
            },
            "warning_flags": {
                "falls_below_75": falls_below_75,
                "falls_below_65": falls_below_65,
                "in_condonation_zone": (65.0 <= sim_pct < 75.0),
                "in_redo_zone": (sim_pct < 65.0)
            }
        })

    # Overall consolidated impact
    orig_overall_pct = calculate_attendance(total_attended_orig, total_conducted_orig)
    sim_overall_cond = total_conducted_orig + total_additional_missed
    sim_overall_pct = calculate_attendance(total_attended_orig, sim_overall_cond)
    delta_overall_pct = round(sim_overall_pct - orig_overall_pct, 2)

    orig_overall_bunks = calculate_safe_bunks(total_attended_orig, total_conducted_orig, target=target)
    sim_overall_bunks = calculate_safe_bunks(total_attended_orig, sim_overall_cond, target=target)

    return {
        "day": day_entry["day"],
        "target": target,
        "selected_periods": selected_periods,
        "period_details": selected_period_details,
        "total_classes_missed": total_additional_missed,
        "affected_subjects_count": len(affected_subjects),
        "affected_subjects": affected_subjects,
        "overall": {
            "original": {
                "attended": total_attended_orig,
                "conducted": total_conducted_orig,
                "percentage": orig_overall_pct,
                "status": get_attendance_status(orig_overall_pct),
                "safe_bunks": orig_overall_bunks
            },
            "simulated": {
                "attended": total_attended_orig,
                "conducted": sim_overall_cond,
                "percentage": sim_overall_pct,
                "status": get_attendance_status(sim_overall_pct),
                "safe_bunks": sim_overall_bunks,
                "percentage_change": delta_overall_pct,
                "safe_bunk_change": sim_overall_bunks - orig_overall_bunks
            }
        },
        "is_safe_day_bunk": all(not s["warning_flags"]["falls_below_75"] and not s["warning_flags"]["in_redo_zone"] for s in affected_subjects)
    }


def get_unified_subject_summary(user_doc):
    """
    Unites Attendance, CA Marks, Weekly Timetable Schedule, and Exam Slots
    on a per-subject basis for the authenticated student.
    Operates strictly in-memory (100% read-only).
    """
    if not user_doc or not isinstance(user_doc, dict):
        return {"courses": [], "total_courses": 0}

    sz1 = user_doc.get("studzone1", {})
    sz2 = user_doc.get("studzone2", {})

    parsed_att = sz1.get("parsed_attendance", [])
    parsed_marks = sz1.get("parsed_marks", [])
    class_sched = sz1.get("class_schedule", [])
    parsed_timetable = sz2.get("parsed_timetable", [])

    weekly = parse_weekly_schedule_matrix(class_sched)
    exams_data = parse_exam_schedule_records(parsed_timetable)

    # Build weekly schedule slot lookup by course code
    schedule_slots_by_code = {}
    for d in weekly["days"]:
        day_name = d["day"]
        for p in d["periods"]:
            if not p["is_free"]:
                code = p["code"].upper()
                if code not in schedule_slots_by_code:
                    schedule_slots_by_code[code] = []
                schedule_slots_by_code[code].append({
                    "day": day_name,
                    "period": p["period"],
                    "time": p["time"],
                    "section": p["section"]
                })

    # Build exam lookup by course code
    exam_lookup = {}
    for ex in exams_data["exams"]:
        code = ex["course_code"].upper()
        exam_lookup[code] = ex

    # Build CA marks lookup by course code
    marks_lookup = {}
    for m in parsed_marks:
        if isinstance(m, dict):
            code = str(m.get("code") or "").strip().upper()
            marks_lookup[code] = m

    unified_courses = []

    # Iterate through registered attendance subjects (canonical registered list)
    for sub in parsed_att:
        code = str(sub.get("code") or "").strip().upper()
        ca_raw = marks_lookup.get(code, {})
        
        # Authoritative student-specific course title resolution
        if ca_raw.get("name") and not str(ca_raw.get("name")).startswith("Course "):
            name = str(ca_raw.get("name")).strip()
        elif str(sub.get("name") or "").strip() and not str(sub.get("name")).startswith("Course "):
            name = str(sub.get("name")).strip()
        elif schedule_slots_by_code.get(code) and schedule_slots_by_code[code][0].get("name"):
            name = schedule_slots_by_code[code][0]["name"]
        else:
            name = f"Course {code}"

        try:
            att = int(float(sub.get("attended", 0)))
            cond = int(float(sub.get("total_classes", sub.get("conducted", 0))))
        except (ValueError, TypeError):
            att, cond = 0, 0

        pct = calculate_attendance(att, cond)
        status = get_attendance_status(pct)
        safe_bunks = calculate_safe_bunks(att, cond, target=75.0)

        # Weekly slots
        slots = schedule_slots_by_code.get(code, [])
        weekly_hours = len(slots)

        # Exam info
        exam_info = exam_lookup.get(code, {
            "exam_date": "Schedule Pending",
            "session": "TBA",
            "timing": "Timing TBA",
            "status": "PENDING",
            "is_pending": True
        })

        # CA marks
        ca_raw = marks_lookup.get(code, {})
        ca_total = ca_raw.get("total", "*")

        # Determine Unified Risk Indicator
        if status == "CRITICAL":
            risk = "CRITICAL"
            risk_desc = "Attendance below 65% (Course Redo Zone)"
        elif status == "WARNING":
            risk = "WARNING"
            risk_desc = "Attendance between 65% and 74.99% (Condonation Zone)"
        elif safe_bunks == 0:
            risk = "ATTENTION"
            risk_desc = "Attendance on target boundary (0 safe bunks remaining)"
        else:
            risk = "SAFE"
            risk_desc = f"Healthy attendance ({safe_bunks} safe bunks available)"

        unified_courses.append({
            "code": code,
            "name": name,
            "attendance": {
                "attended": att,
                "conducted": cond,
                "percentage": pct,
                "status": status,
                "safe_bunks": safe_bunks
            },
            "schedule": {
                "weekly_periods_count": weekly_hours,
                "slots": slots
            },
            "exam": exam_info,
            "ca_marks_summary": {
                "total": ca_total
            },
            "risk_status": risk,
            "risk_description": risk_desc
        })

    return {
        "courses": unified_courses,
        "total_courses": len(unified_courses)
    }
