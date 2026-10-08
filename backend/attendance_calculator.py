"""
Student Sync — Attendance & Bunk Calculation Engine
Core utility for PSG Tech regulatory attendance logic, safe-bunk calculations,
attendance recovery estimations, in-memory simulation, and timetable parsing.

Reference & Formulae:
- Standard PSG Tech hourly attendance formula:
    Percentage = (Attended / Conducted) * 100
- Regulatory Thresholds:
    >= 75.0% : SAFE
    65.0% - 74.99% : WARNING (Condonation Zone)
    < 65.0% : CRITICAL (Course Redo Zone)
- Safe Bunks Formula (Max bunks while remaining >= Target%):
    Max Bunks = floor((Attended - (Target/100) * Conducted) / (Target/100))
- Attendance Recovery Formula (Min consecutive classes to reach Target%):
    Required Classes = ceil(((Target/100) * Conducted - Attended) / (1 - Target/100))
"""

import math
import re
from datetime import datetime


def calculate_attendance(attended, conducted):
    """
    Calculates attendance percentage rounded to two decimal places.
    Handles zero-division and negative values safely.
    """
    try:
        att = float(attended)
        cond = float(conducted)
        if cond <= 0:
            return 0.0
        pct = (att / cond) * 100.0
        return round(max(0.0, min(100.0, pct)), 2)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0.0


def calculate_safe_bunks(attended, conducted, target=75.0):
    """
    Determines how many upcoming classes a student can safely bunk
    while keeping attendance at or above the target percentage (default: 75%).

    Mathematical Derivation:
        Attended / (Conducted + x) >= target_fraction
        Attended >= target_fraction * Conducted + target_fraction * x
        x <= (Attended - target_fraction * Conducted) / target_fraction
        Max integer x = floor((Attended - target_fraction * Conducted) / target_fraction)

    Returns:
        int: Maximum safe classes that can be missed (0 if already below target).
    """
    try:
        att = float(attended)
        cond = float(conducted)
        tgt = float(target)

        if cond <= 0 or att <= 0:
            return 0
        if tgt <= 0.0 or tgt >= 100.0:
            return 0

        target_fraction = tgt / 100.0
        current_fraction = att / cond

        # If already strictly below the target, cannot safely bunk any classes
        if current_fraction < target_fraction:
            return 0

        # Epsilon (1e-9) prevents IEEE 754 precision artifacts from rounding down exact values
        max_bunks = math.floor(((att - target_fraction * cond) / target_fraction) + 1e-9)
        return max(0, int(max_bunks))
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


def calculate_required_classes(attended, conducted, target=75.0):
    """
    Determines the minimum number of consecutive classes a student must attend
    to recover and reach the target percentage (default: 75%).

    Mathematical Derivation:
        (Attended + y) / (Conducted + y) >= target_fraction
        Attended + y >= target_fraction * Conducted + target_fraction * y
        y * (1 - target_fraction) >= target_fraction * Conducted - Attended
        y >= (target_fraction * Conducted - Attended) / (1 - target_fraction)
        Min integer y = ceil((target_fraction * Conducted - Attended) / (1 - target_fraction))

    Returns:
        int: Minimum consecutive classes needed (0 if already at or above target).
    """
    try:
        att = float(attended)
        cond = float(conducted)
        tgt = float(target)

        if cond <= 0:
            return 0
        if tgt <= 0.0 or tgt >= 100.0:
            return 0

        target_fraction = tgt / 100.0
        current_fraction = att / cond

        # If already at or above target, no recovery classes are required
        if current_fraction >= target_fraction:
            return 0

        # Epsilon (1e-9) prevents exact integer multiples from rounding up to next integer
        required = math.ceil(((target_fraction * cond - att) / (1.0 - target_fraction)) - 1e-9)
        return max(0, int(required))
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


def get_attendance_status(percentage):
    """
    Maps attendance percentage to standard PSG Tech regulatory status:
    - >= 75.0% : SAFE
    - 65.0% to 74.99% : WARNING (Condonation Zone)
    - < 65.0% : CRITICAL (Course Redo Zone)
    """
    try:
        pct = float(percentage)
        if pct >= 75.0:
            return "SAFE"
        elif pct >= 65.0:
            return "WARNING"
        else:
            return "CRITICAL"
    except (ValueError, TypeError):
        return "UNKNOWN"


def calculate_simulated_attendance(attended, conducted, additional_attended=0, additional_bunked=0, target=75.0):
    """
    Simulates hypothetical attendance shifts in-memory without modifying any database records.

    Args:
        attended: Base classes attended.
        conducted: Base classes conducted.
        additional_attended: Hypothetical future classes to attend.
        additional_bunked: Hypothetical future classes to miss/bunk.
        target: Target percentage threshold (default 75.0).

    Returns:
        dict: Complete comparison payload with initial and projected values.
    """
    try:
        base_att = max(0, int(float(attended)))
        base_cond = max(0, int(float(conducted)))
        delta_att = max(0, int(float(additional_attended)))
        delta_bunk = max(0, int(float(additional_bunked)))
        tgt = float(target)
    except (ValueError, TypeError):
        base_att, base_cond, delta_att, delta_bunk, tgt = 0, 0, 0, 0, 75.0

    initial_pct = calculate_attendance(base_att, base_cond)
    initial_safe = calculate_safe_bunks(base_att, base_cond, target=tgt)
    initial_req = calculate_required_classes(base_att, base_cond, target=tgt)
    initial_status = get_attendance_status(initial_pct)

    sim_att = base_att + delta_att
    sim_cond = base_cond + delta_att + delta_bunk
    sim_pct = calculate_attendance(sim_att, sim_cond)
    sim_safe = calculate_safe_bunks(sim_att, sim_cond, target=tgt)
    sim_req = calculate_required_classes(sim_att, sim_cond, target=tgt)
    sim_status = get_attendance_status(sim_pct)

    delta_pct = round(sim_pct - initial_pct, 2)

    return {
        "initial": {
            "attended": base_att,
            "conducted": base_cond,
            "percentage": initial_pct,
            "safe_bunks": initial_safe,
            "required_classes": initial_req,
            "status": initial_status
        },
        "simulation": {
            "additional_attended": delta_att,
            "additional_bunked": delta_bunk,
            "attended": sim_att,
            "conducted": sim_cond,
            "percentage": sim_pct,
            "safe_bunks": sim_safe,
            "required_classes": sim_req,
            "status": sim_status,
            "percentage_change": delta_pct
        },
        "target": tgt
    }


def parse_daily_schedule(class_schedule_matrix, day_name=None, class_timetable_html=None):
    """
    Parses the 2D timetable matrix stored in user['studzone1']['class_schedule'].
    If class_timetable_html is provided, re-extracts the matrix with precise colspan handling.

    Structure in StudZone 1:
        Row 0: ["Period", "1", "2", "3", "4", "5", "6"]
        Row 1: ["Time", "8.30 - 9.20", "9.20 - 10.10", ...]
        Rows 2+: ["Monday", "MCA_3\\r\\n 23MX31\\nCLOUD COMPUTING", ...]

    Args:
        class_schedule_matrix (list): 2D array of rows from StudZone 1.
        day_name (str, optional): Target day (e.g. 'Monday'). Defaults to today's weekday.
        class_timetable_html (str, optional): StudZone 1 timetable HTML table with colspan.

    Returns:
        dict: {
            "day": str,
            "classes": [
                {
                    "period": int,
                    "time": str,
                    "code": str,
                    "name": str,
                    "section": str,
                    "raw": str,
                    "is_free": bool
                }, ...
            ]
        }
    """
    if class_timetable_html:
        try:
            from timetable_calculator import parse_schedule_html_to_matrix
            html_matrix = parse_schedule_html_to_matrix(class_timetable_html)
            if html_matrix:
                class_schedule_matrix = html_matrix
        except Exception:
            pass

    if not class_schedule_matrix or not isinstance(class_schedule_matrix, list) or len(class_schedule_matrix) < 3:
        return {"day": day_name or datetime.now().strftime("%A"), "classes": []}

    target_day = (day_name or datetime.now().strftime("%A")).strip().capitalize()
    
    # Extract period labels and timings from header rows
    periods_row = class_schedule_matrix[0]
    times_row = class_schedule_matrix[1]

    # Map column index -> period metadata
    period_meta = {}
    for col_idx in range(1, len(periods_row)):
        period_num = periods_row[col_idx].strip() if col_idx < len(periods_row) else str(col_idx)
        time_slot = times_row[col_idx].strip() if col_idx < len(times_row) else "TBA"
        period_meta[col_idx] = {
            "period": int(period_num) if period_num.isdigit() else col_idx,
            "time": time_slot
        }

    # Locate row matching target_day
    matched_row = None
    for row in class_schedule_matrix[2:]:
        if row and isinstance(row, list) and len(row) > 0:
            row_day = str(row[0]).strip().capitalize()
            if row_day.lower() == target_day.lower():
                matched_row = row
                break

    if not matched_row:
        return {"day": target_day, "classes": []}

    try:
        from timetable_calculator import normalize_schedule_row
        matched_row = normalize_schedule_row(matched_row, total_periods=len(periods_row) - 1)
    except Exception:
        pass

    classes = []
    for col_idx in range(1, len(matched_row)):
        meta = period_meta.get(col_idx, {"period": col_idx, "time": "TBA"})
        raw_cell = str(matched_row[col_idx]).strip()

        if not raw_cell or raw_cell == "-":
            classes.append({
                "period": meta["period"],
                "time": meta["time"],
                "code": "FREE",
                "name": "Free Period",
                "section": "",
                "raw": "-",
                "is_free": True
            })
            continue

        # Parse cell content: often "MCA_3\r\n 23MX31\nCLOUD COMPUTING"
        lines = [line.strip() for line in re.split(r'[\r\n]+', raw_cell) if line.strip()]
        section = ""
        code = ""
        name = ""

        if len(lines) == 1:
            name = lines[0]
        elif len(lines) == 2:
            code = lines[0]
            name = lines[1]
        elif len(lines) >= 3:
            section = lines[0]
            code = lines[1]
            name = " ".join(lines[2:])

        # Course code pattern matcher if lines splitting was ambiguous
        if not code or len(code) > 12:
            match = re.search(r'\b([0-9]{2}[A-Z]{2}[A-Z0-9]{2,4})\b', raw_cell)
            if match:
                code = match.group(1)

        classes.append({
            "period": meta["period"],
            "time": meta["time"],
            "code": code or "COURSE",
            "name": name or raw_cell,
            "section": section,
            "raw": raw_cell,
            "is_free": False
        })

    return {"day": target_day, "classes": classes}


def extract_student_course_titles(user_doc=None):
    """
    Extracts authoritative, student-specific course code -> course name mappings
    from the authenticated student's own StudZone data (CA marks and class schedule).
    Never uses global or cross-student mappings.
    """
    if not user_doc or not isinstance(user_doc, dict):
        return {}
    
    mapping = {}
    sz1 = user_doc.get("studzone1", {})
    if not isinstance(sz1, dict):
        return {}
    
    # 1. Extract from student's own parsed_marks (from CA marks view)
    for m in sz1.get("parsed_marks", []):
        if isinstance(m, dict):
            c_code = str(m.get("code") or "").strip().upper()
            c_name = str(m.get("name") or "").strip()
            if c_code and c_name and not c_name.startswith("Course ") and not c_name.upper().startswith("MAX:"):
                mapping[c_code] = c_name
    
    # 2. Extract from student's own class_schedule (timetable matrix)
    for row in sz1.get("class_schedule", []):
        if isinstance(row, list):
            for cell in row:
                cell_str = str(cell)
                match = re.search(r'\b([0-9]{2}[A-Z]{2}[A-Z0-9]{2,4})\b', cell_str)
                if match:
                    c_code = match.group(1).upper()
                    if c_code not in mapping:
                        lines = [l.strip() for l in re.split(r'[\r\n]+', cell_str) if l.strip()]
                        if len(lines) >= 3:
                            name = " ".join(lines[2:]).strip()
                            if name and not name.upper().startswith("MAX:"):
                                mapping[c_code] = name
    return mapping


def resolve_student_attendance_records(user_doc, target_col=None):
    """
    Safely resolves attendance records for a student document with resilient fallback:
    1. Returns current parsed_attendance from studzone1 if available and non-empty.
    2. If current attendance is empty/updating, falls back to previously stored data:
       - previous_parsed_attendance in user_doc or studzone1
       - parses stored HTML tables: attendance_table, previous_attendance, attendance, attendance_html
    3. If neither current nor previous data is available, returns empty list.

    Returns:
        tuple: (records_list, is_previous_data, is_updating)
    """
    if not user_doc or not isinstance(user_doc, dict):
        return [], False, False

    sz1 = user_doc.get("studzone1") or {}
    current_parsed = sz1.get("parsed_attendance") if isinstance(sz1, dict) else None

    def has_valid_records(att_list):
        if not att_list or not isinstance(att_list, list):
            return False
        for item in att_list:
            if isinstance(item, dict) and item.get("code"):
                return True
        return False

    # 1. Current data available?
    if has_valid_records(current_parsed):
        return current_parsed, False, False

    # 2. Check explicitly stored previous_parsed_attendance
    prev_parsed = user_doc.get("previous_parsed_attendance") or (sz1.get("previous_parsed_attendance") if isinstance(sz1, dict) else None)
    if has_valid_records(prev_parsed):
        return prev_parsed, True, True

    # 3. Check and parse stored HTML tables in MongoDB
    student_course_map = extract_student_course_titles(user_doc)
    html_candidates = [
        user_doc.get("attendance_table"),
        user_doc.get("previous_attendance"),
        user_doc.get("attendance"),
        sz1.get("attendance_html") if isinstance(sz1, dict) else None
    ]

    try:
        from new_scrapers.studzone1_scraper import parse_attendance_html
    except ImportError:
        try:
            from backend.new_scrapers.studzone1_scraper import parse_attendance_html
        except ImportError:
            parse_attendance_html = None

    if parse_attendance_html:
        for html_candidate in html_candidates:
            if html_candidate and isinstance(html_candidate, str) and "<td" in html_candidate:
                _, parsed = parse_attendance_html(html_candidate, course_name_map=student_course_map)
                if has_valid_records(parsed):
                    return parsed, True, True

    # 4. Neither current nor previous data is available in the database
    return [], False, False


def summarize_student_attendance(parsed_attendance_list, target=75.0, user_doc=None):
    """
    Generates a full, enriched attendance summary from a student's parsed_attendance list.
    Resolves course names from the student's own verified CA marks/timetable data when user_doc is provided.
    If parsed_attendance_list is empty/updating and user_doc is provided, seamlessly recovers stored previous data.
    Operates in read-only mode without mutating the input list.

    Returns:
        dict: {
            "overall": {
                "attended": int,
                "conducted": int,
                "absent": int,
                "percentage": float,
                "safe_bunks": int,
                "required_classes": int,
                "status": str
            },
            "subjects": [ ... enriched subjects ... ],
            "counts": {
                "total_subjects": int,
                "safe_subjects": int,
                "warning_subjects": int,
                "critical_subjects": int
            },
            "target": float,
            "is_previous_data": bool,
            "is_updating": bool
        }
    """
    is_prev = False
    is_upd = False

    if (not parsed_attendance_list or not isinstance(parsed_attendance_list, list)) and user_doc:
        resolved, is_prev, is_upd = resolve_student_attendance_records(user_doc)
        if resolved:
            parsed_attendance_list = resolved

    if not parsed_attendance_list or not isinstance(parsed_attendance_list, list):
        return {
            "overall": {
                "attended": 0,
                "conducted": 0,
                "absent": 0,
                "percentage": 0.0,
                "safe_bunks": 0,
                "required_classes": 0,
                "status": "UNKNOWN"
            },
            "subjects": [],
            "counts": {
                "total_subjects": 0,
                "safe_subjects": 0,
                "warning_subjects": 0,
                "critical_subjects": 0
            },
            "target": target,
            "is_previous_data": False,
            "is_updating": False
        }

    student_titles = extract_student_course_titles(user_doc) if user_doc else {}

    total_att = 0
    total_cond = 0
    total_abs = 0
    enriched_subjects = []

    safe_count = 0
    warn_count = 0
    crit_count = 0

    for item in parsed_attendance_list:
        try:
            att = int(float(item.get("attended", 0)))
        except (ValueError, TypeError):
            att = 0

        try:
            cond = int(float(item.get("total_classes", item.get("conducted", 0))))
        except (ValueError, TypeError):
            cond = 0

        try:
            absent = int(float(item.get("absent", max(0, cond - att))))
        except (ValueError, TypeError):
            absent = max(0, cond - att)

        pct = calculate_attendance(att, cond)
        safe = calculate_safe_bunks(att, cond, target=target)
        req = calculate_required_classes(att, cond, target=target)
        status = get_attendance_status(pct)

        if status == "SAFE":
            safe_count += 1
        elif status == "WARNING":
            warn_count += 1
        else:
            crit_count += 1

        total_att += att
        total_cond += cond
        total_abs += absent

        code = str(item.get("code", "")).strip().upper()
        # Authoritative title resolution from student's own records
        if code in student_titles:
            resolved_name = student_titles[code]
        elif item.get("name") and not str(item.get("name")).startswith("Course "):
            resolved_name = str(item.get("name")).strip()
        else:
            resolved_name = f"Course {code}"

        enriched_subjects.append({
            "code": code,
            "name": resolved_name,
            "attended": att,
            "conducted": cond,
            "absent": absent,
            "exempt_hr": item.get("exempt_hr", "0"),
            "percentage": pct,
            "safe_bunks": safe,
            "required_classes": req,
            "status": status,
            "raw_status": item.get("status", "Good")
        })

    overall_pct = calculate_attendance(total_att, total_cond)
    overall_safe = calculate_safe_bunks(total_att, total_cond, target=target)
    overall_req = calculate_required_classes(total_att, total_cond, target=target)
    overall_status = get_attendance_status(overall_pct)

    return {
        "overall": {
            "attended": total_att,
            "conducted": total_cond,
            "absent": total_abs,
            "percentage": overall_pct,
            "safe_bunks": overall_safe,
            "required_classes": overall_req,
            "status": overall_status
        },
        "subjects": enriched_subjects,
        "counts": {
            "total_subjects": len(enriched_subjects),
            "safe_subjects": safe_count,
            "warning_subjects": warn_count,
            "critical_subjects": crit_count
        },
        "target": target,
        "is_previous_data": is_prev,
        "is_updating": is_upd
    }
