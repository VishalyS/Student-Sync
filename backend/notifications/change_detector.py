import hashlib
import re
from datetime import datetime, timezone


def compute_change_hash(roll_no, notif_type, module, title, description, change_key=""):
    """
    Computes a deterministic hash for a specific detected data change
    to prevent duplicate notifications during repeated background sync runs.
    """
    raw_key = f"{roll_no.strip().upper()}||{notif_type.strip().lower()}||{module.strip()}||{title.strip()}||{description.strip()}||{str(change_key).strip()}"
    return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()


def parse_percentage_val(pct_str):
    """Safely extracts a float percentage from strings like '75.5%', '72', etc."""
    if not pct_str:
        return None
    try:
        cleaned = re.sub(r'[^0-9.]', '', str(pct_str))
        return float(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None


def parse_numeric_mark(mark_str):
    """Safely extracts a numeric mark from strings like '24', '18/25', '95'"""
    if not mark_str:
        return None
    try:
        cleaned = re.sub(r'[^0-9.]', '', str(mark_str).split('/')[0])
        return float(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None


def extract_student_title_map(old_user_doc=None, sz1_fresh=None):
    """
    Extracts dynamic student-specific course code -> course title mapping
    strictly from the authenticated student's own MongoDB document and freshly scraped data.
    Preferred resolution order:
    1. The student's own parsed CA/course data (parsed_marks).
    2. The student's own parsed timetable/course data (class_schedule).
    3. Any other verified course-name data belonging to that SAME student (e.g. parsed_attendance).
    Never uses global hardcoded mappings or cross-student shared data.
    """
    mapping = {}

    # Priority 1: Student's own parsed CA / course marks (fresh then stored)
    for src in [sz1_fresh, (old_user_doc or {}).get('studzone1')]:
        if src and isinstance(src, dict):
            for m in src.get('parsed_marks') or []:
                if isinstance(m, dict):
                    c_code = str(m.get('code') or '').strip().upper()
                    c_name = str(m.get('name') or '').strip()
                    if c_code and c_name and not c_name.startswith("Course ") and not c_name.upper().startswith("MAX:"):
                        if c_code not in mapping:
                            mapping[c_code] = c_name

    # Priority 2: Student's own parsed timetable/class_schedule matrix (fresh then stored)
    for src in [sz1_fresh, (old_user_doc or {}).get('studzone1')]:
        if src and isinstance(src, dict):
            for row in src.get('class_schedule') or []:
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
                                    if name and not name.startswith("Course ") and not name.upper().startswith("MAX:"):
                                        mapping[c_code] = name

    # Priority 3: Any other verified course-name data belonging to that SAME student (parsed_attendance)
    for src in [sz1_fresh, (old_user_doc or {}).get('studzone1')]:
        if src and isinstance(src, dict):
            for a in src.get('parsed_attendance') or []:
                if isinstance(a, dict):
                    c_code = str(a.get('code') or '').strip().upper()
                    c_name = str(a.get('name') or '').strip()
                    if c_code and c_name and not c_name.startswith("Course ") and not c_name.upper().startswith("MAX:") and len(c_name) > 2:
                        if c_code not in mapping:
                            mapping[c_code] = c_name

    return mapping


def resolve_course_title(code, name=None, student_course_map=None):
    """
    Resolves course title for notifications using student-specific data.
    Order:
    1. If a genuine, verified course title is already provided in the course record
       (not numeric, > 2 chars, not a placeholder like 'Course <code>'), use it.
    2. Look up code in student_course_map (built strictly from student's own CA marks / timetable / attendance).
    3. Fallback: 'Course <course_code>'.
    Never uses global hardcoded course-title dictionaries.
    """
    code_clean = (code or '').strip().upper()
    name_clean = (name or '').strip()

    # 1. Genuine verified title passed with record
    if name_clean and not name_clean.isdigit() and len(name_clean) > 2 and not name_clean.upper().startswith("COURSE "):
        return name_clean

    # 2. Student-specific verified map (CA marks, timetable, stored student attendance)
    if student_course_map and isinstance(student_course_map, dict):
        if code_clean in student_course_map:
            return student_course_map[code_clean]

    # 3. Neutral fallback
    if code_clean:
        return f"Course {code_clean}"

    return name_clean or 'Course'


def detect_granular_changes(roll_no, old_user_doc, sz1_fresh, sz2_fresh):
    """
    Compares the previous student document in MongoDB against the newly scraped datasets
    from StudZone 1 and StudZone 2 at the smallest granular unit.

    Returns a list of structured, human-readable notification dictionaries.
    """
    notifications = []
    now_iso = datetime.now(timezone.utc).isoformat()
    old_user = old_user_doc or {}
    old_sz1 = old_user.get('studzone1') or {}
    old_sz2 = old_user.get('studzone2') or {}

    # Critical requirement: If student has NO baseline snapshot stored yet,
    # or baseline initialization is in progress, return [] to avoid sending initial flood
    # of notifications for pre-existing records.
    if old_user.get('baseline_initialized') is False:
        return []

    has_baseline = (
        "studzone1" in old_user or 
        "studzone2" in old_user or 
        "lastSyncedAt" in old_user or 
        "syncStatus" in old_user
    )
    if not has_baseline:
        return []

    # Build dynamic student-specific course title map strictly from this student's own data
    student_title_map = extract_student_title_map(old_user_doc, sz1_fresh)

    # =========================================================================
    # 1. ATTENDANCE CHANGE DETECTION (StudZone 1)
    # =========================================================================
    old_att_list = old_sz1.get('parsed_attendance') or old_user.get('previous_parsed_attendance') or []
    if not old_att_list and old_user:
        try:
            from attendance_calculator import resolve_student_attendance_records
            old_att_list, _, _ = resolve_student_attendance_records(old_user)
        except Exception:
            try:
                from backend.attendance_calculator import resolve_student_attendance_records
                old_att_list, _, _ = resolve_student_attendance_records(old_user)
            except Exception:
                pass
    new_att_list = sz1_fresh.get('parsed_attendance') or []

    if old_att_list and new_att_list:
        old_att_map = {c.get('code', c.get('name', '')): c for c in old_att_list if c}
        for new_c in new_att_list:
            if not new_c:
                continue
            key = new_c.get('code', new_c.get('name', ''))
            subj_name = resolve_course_title(new_c.get('code'), new_c.get('name'), student_course_map=student_title_map)
            new_pct_str = str(new_c.get('percentage', '')).strip()
            new_pct_val = parse_percentage_val(new_pct_str)

            if key not in old_att_map:
                title = "New Attendance Record"
                desc = f"New attendance record added: {subj_name} at {new_pct_str}."
                chash = compute_change_hash(roll_no, "attendance", "Attendance", title, desc, f"new_{key}_{new_pct_str}")
                notifications.append({
                    "rollNo": roll_no,
                    "studentRollNo": roll_no,
                    "category": "attendance",
                    "type": "attendance",
                    "title": title,
                    "description": desc,
                    "message": desc,
                    "source": "StudZone 1",
                    "module": "Attendance",
                    "timestamp": now_iso,
                    "createdAt": now_iso,
                    "read": False,
                    "changeHash": chash,
                    "changeData": {
                        "subject": subj_name,
                        "code": new_c.get('code', ''),
                        "previousValue": None,
                        "newValue": new_pct_str,
                        "attended": new_c.get('attended'),
                        "total": new_c.get('total_classes')
                    }
                })
            else:
                old_c = old_att_map[key]
                old_pct_str = str(old_c.get('percentage', '')).strip()
                old_pct_val = parse_percentage_val(old_pct_str)

                if old_pct_val is not None and new_pct_val is not None and old_pct_val != new_pct_val:
                    if new_pct_val > old_pct_val:
                        title = "Attendance Updated"
                        desc = f"{subj_name} attendance changed from {old_pct_str} → {new_pct_str}."
                        chash = compute_change_hash(roll_no, "attendance", "Attendance", title, desc, f"{key}_{old_pct_str}_{new_pct_str}")
                        notifications.append({
                            "rollNo": roll_no,
                            "studentRollNo": roll_no,
                            "category": "attendance",
                            "type": "attendance",
                            "title": title,
                            "description": desc,
                            "message": desc,
                            "source": "StudZone 1",
                            "module": "Attendance",
                            "timestamp": now_iso,
                            "createdAt": now_iso,
                            "read": False,
                            "changeHash": chash,
                            "changeData": {
                                "subject": subj_name,
                                "code": new_c.get('code', ''),
                                "previousValue": old_pct_str,
                                "newValue": new_pct_str,
                                "direction": "increased",
                                "attended": new_c.get('attended'),
                                "total": new_c.get('total_classes')
                            }
                        })
                    elif new_pct_val < old_pct_val:
                        title = "Attendance Alert"
                        desc = f"{subj_name} attendance dropped from {old_pct_str} → {new_pct_str}."
                        chash = compute_change_hash(roll_no, "attendance", "Attendance", title, desc, f"{key}_{old_pct_str}_{new_pct_str}")
                        notifications.append({
                            "rollNo": roll_no,
                            "studentRollNo": roll_no,
                            "category": "attendance",
                            "type": "attendance",
                            "title": title,
                            "description": desc,
                            "message": desc,
                            "source": "StudZone 1",
                            "module": "Attendance",
                            "timestamp": now_iso,
                            "createdAt": now_iso,
                            "read": False,
                            "changeHash": chash,
                            "changeData": {
                                "subject": subj_name,
                                "code": new_c.get('code', ''),
                                "previousValue": old_pct_str,
                                "newValue": new_pct_str,
                                "direction": "decreased",
                                "attended": new_c.get('attended'),
                                "total": new_c.get('total_classes')
                            }
                        })
                elif old_pct_str != new_pct_str and new_pct_str:
                    title = "Attendance Updated"
                    desc = f"{subj_name} attendance changed from {old_pct_str} → {new_pct_str}."
                    chash = compute_change_hash(roll_no, "attendance", "Attendance", title, desc, f"{key}_{old_pct_str}_{new_pct_str}")
                    notifications.append({
                        "rollNo": roll_no,
                        "studentRollNo": roll_no,
                        "category": "attendance",
                        "type": "attendance",
                        "title": title,
                        "description": desc,
                        "message": desc,
                        "source": "StudZone 1",
                        "module": "Attendance",
                        "timestamp": now_iso,
                        "createdAt": now_iso,
                        "read": False,
                        "changeHash": chash,
                        "changeData": {
                            "subject": subj_name,
                            "code": new_c.get('code', ''),
                            "previousValue": old_pct_str,
                            "newValue": new_pct_str,
                            "attended": new_c.get('attended'),
                            "total": new_c.get('total_classes')
                        }
                    })

    # =========================================================================
    # 2. CONTINUOUS ASSESSMENT / CA MARKS CHANGE DETECTION (StudZone 1)
    # =========================================================================
    old_marks_list = old_sz1.get('parsed_marks') or []
    new_marks_list = sz1_fresh.get('parsed_marks') or []

    if old_marks_list and new_marks_list:
        old_marks_map = {m.get('code', m.get('name', '')): m for m in old_marks_list if m}
        for new_m in new_marks_list:
            if not new_m:
                continue
            key = new_m.get('code', new_m.get('name', ''))
            subj_name = resolve_course_title(new_m.get('code'), new_m.get('name'), student_course_map=student_title_map)

            if key in old_marks_map:
                old_m = old_marks_map[key]

                # Compare CA1
                old_ca1 = str(old_m.get('ca1', '')).strip()
                new_ca1 = str(new_m.get('ca1', '')).strip()
                if new_ca1 and new_ca1 not in ['-', ''] and new_ca1 != old_ca1:
                    if not old_ca1 or old_ca1 == '-':
                        title = "CA Marks Published"
                        desc = f"{subj_name} CA1 marks published: {new_ca1}."
                    else:
                        title = "CA Marks Updated"
                        desc = f"{subj_name} CA1 marks changed from {old_ca1} → {new_ca1}."
                    chash = compute_change_hash(roll_no, "marks", "CA Marks", title, desc, f"{key}_ca1_{old_ca1}_{new_ca1}")
                    notifications.append({
                        "rollNo": roll_no,
                        "studentRollNo": roll_no,
                        "category": "marks",
                        "type": "marks",
                        "title": title,
                        "description": desc,
                        "message": desc,
                        "source": "StudZone 1",
                        "module": "CA Marks",
                        "timestamp": now_iso,
                        "createdAt": now_iso,
                        "read": False,
                        "changeHash": chash,
                        "changeData": {"subject": subj_name, "test": "CA1", "previousValue": old_ca1, "newValue": new_ca1}
                    })

                # Compare CA2
                old_ca2 = str(old_m.get('ca2', '')).strip()
                new_ca2 = str(new_m.get('ca2', '')).strip()
                if new_ca2 and new_ca2 not in ['-', ''] and new_ca2 != old_ca2:
                    if not old_ca2 or old_ca2 == '-':
                        title = "CA Marks Published"
                        desc = f"{subj_name} CA2 marks published: {new_ca2}."
                    else:
                        title = "CA Marks Updated"
                        desc = f"{subj_name} CA2 marks changed from {old_ca2} → {new_ca2}."
                    chash = compute_change_hash(roll_no, "marks", "CA Marks", title, desc, f"{key}_ca2_{old_ca2}_{new_ca2}")
                    notifications.append({
                        "rollNo": roll_no,
                        "studentRollNo": roll_no,
                        "category": "marks",
                        "type": "marks",
                        "title": title,
                        "description": desc,
                        "message": desc,
                        "source": "StudZone 1",
                        "module": "CA Marks",
                        "timestamp": now_iso,
                        "createdAt": now_iso,
                        "read": False,
                        "changeHash": chash,
                        "changeData": {"subject": subj_name, "test": "CA2", "previousValue": old_ca2, "newValue": new_ca2}
                    })

                # Compare CA3
                old_ca3 = str(old_m.get('ca3', '')).strip()
                new_ca3 = str(new_m.get('ca3', '')).strip()
                if new_ca3 and new_ca3 not in ['-', ''] and new_ca3 != old_ca3:
                    if not old_ca3 or old_ca3 == '-':
                        title = "CA Marks Published"
                        desc = f"{subj_name} CA3 marks published: {new_ca3}."
                    else:
                        title = "CA Marks Updated"
                        desc = f"{subj_name} CA3 marks changed from {old_ca3} → {new_ca3}."
                    chash = compute_change_hash(roll_no, "marks", "CA Marks", title, desc, f"{key}_ca3_{old_ca3}_{new_ca3}")
                    notifications.append({
                        "rollNo": roll_no,
                        "studentRollNo": roll_no,
                        "category": "marks",
                        "type": "marks",
                        "title": title,
                        "description": desc,
                        "message": desc,
                        "source": "StudZone 1",
                        "module": "CA Marks",
                        "timestamp": now_iso,
                        "createdAt": now_iso,
                        "read": False,
                        "changeHash": chash,
                        "changeData": {"subject": subj_name, "test": "CA3", "previousValue": old_ca3, "newValue": new_ca3}
                    })

                # Compare Total if individual didn't fire or total changed
                old_tot = str(old_m.get('total', '')).strip()
                new_tot = str(new_m.get('total', '')).strip()
                if new_tot and new_tot not in ['-', ''] and new_tot != old_tot and (old_ca1 == new_ca1 and old_ca2 == new_ca2 and old_ca3 == new_ca3):
                    title = "CA Total Updated"
                    desc = f"{subj_name} total marks changed from {old_tot} → {new_tot}."
                    chash = compute_change_hash(roll_no, "marks", "CA Marks", title, desc, f"{key}_tot_{old_tot}_{new_tot}")
                    notifications.append({
                        "rollNo": roll_no,
                        "studentRollNo": roll_no,
                        "category": "marks",
                        "type": "marks",
                        "title": title,
                        "description": desc,
                        "message": desc,
                        "source": "StudZone 1",
                        "module": "CA Marks",
                        "timestamp": now_iso,
                        "createdAt": now_iso,
                        "read": False,
                        "changeHash": chash,
                        "changeData": {"subject": subj_name, "test": "Total", "previousValue": old_tot, "newValue": new_tot}
                    })

    # =========================================================================
    # 3. SEMESTER RESULTS & CGPA CHANGE DETECTION (StudZone 2)
    # =========================================================================
    old_res_list = old_sz2.get('parsed_results') or []
    new_res_list = sz2_fresh.get('parsed_results') or []

    if new_res_list:
        old_res_map = {r.get('code', ''): r for r in old_res_list if r}
        
        # Detect new semester batch release
        if old_res_list and len(new_res_list) > len(old_res_list):
            diff_count = len(new_res_list) - len(old_res_list)
            sem_val = new_res_list[0].get('sem', '3') if new_res_list else '3'
            title = "Semester Results Published"
            desc = f"Semester {sem_val} results published: {diff_count} new course results available."
            chash = compute_change_hash(roll_no, "results", "Results", title, desc, f"batch_sem_{sem_val}_{len(new_res_list)}")
            notifications.append({
                "rollNo": roll_no,
                "studentRollNo": roll_no,
                "category": "results",
                "type": "results",
                "title": title,
                "description": desc,
                "message": desc,
                "source": "StudZone 2",
                "module": "Semester Results",
                "timestamp": now_iso,
                "createdAt": now_iso,
                "read": False,
                "changeHash": chash,
                "changeData": {"newCoursesCount": diff_count, "totalCourses": len(new_res_list)}
            })

        for new_r in new_res_list:
            if not new_r:
                continue
            code = new_r.get('code', '')
            subj_title = new_r.get('title') or code or 'Course'
            grade = new_r.get('grade', '')
            gp = new_r.get('grade_point', '')

            if code not in old_res_map and old_res_list and len(new_res_list) <= len(old_res_list):
                title = "Semester Result Published"
                desc = f"{subj_title} result published: {grade} (Grade Point {gp})."
                chash = compute_change_hash(roll_no, "results", "Results", title, desc, f"new_{code}_{grade}")
                notifications.append({
                    "rollNo": roll_no,
                    "studentRollNo": roll_no,
                    "category": "results",
                    "type": "results",
                    "title": title,
                    "description": desc,
                    "message": desc,
                    "source": "StudZone 2",
                    "module": "Semester Results",
                    "timestamp": now_iso,
                    "createdAt": now_iso,
                    "read": False,
                    "changeHash": chash,
                    "changeData": {"subject": subj_title, "code": code, "grade": grade, "gradePoint": gp}
                })
            elif code in old_res_map:
                old_r = old_res_map[code]
                old_grade = old_r.get('grade', '')
                if grade and old_grade and grade != old_grade:
                    title = "Result Updated"
                    desc = f"{subj_title} result changed from {old_grade} → {grade}."
                    chash = compute_change_hash(roll_no, "results", "Results", title, desc, f"{code}_{old_grade}_{grade}")
                    notifications.append({
                        "rollNo": roll_no,
                        "studentRollNo": roll_no,
                        "category": "results",
                        "type": "results",
                        "title": title,
                        "description": desc,
                        "message": desc,
                        "source": "StudZone 2",
                        "module": "Semester Results",
                        "timestamp": now_iso,
                        "createdAt": now_iso,
                        "read": False,
                        "changeHash": chash,
                        "changeData": {"subject": subj_title, "code": code, "previousGrade": old_grade, "newGrade": grade}
                    })

    # CGPA Change
    old_cgpa = old_user.get('cgpa') or old_sz2.get('cgpa')
    new_cgpa = sz2_fresh.get('cgpa')
    if old_cgpa is not None and new_cgpa is not None and float(old_cgpa) != float(new_cgpa):
        title = "CGPA Updated"
        desc = f"CGPA changed from {old_cgpa} → {new_cgpa}."
        chash = compute_change_hash(roll_no, "cgpa", "CGPA", title, desc, f"cgpa_{old_cgpa}_{new_cgpa}")
        notifications.append({
            "rollNo": roll_no,
            "studentRollNo": roll_no,
            "category": "cgpa",
            "type": "results",
            "title": title,
            "description": desc,
            "message": desc,
            "source": "StudZone 2",
            "module": "CGPA Summary",
            "timestamp": now_iso,
            "createdAt": now_iso,
            "read": False,
            "changeHash": chash,
            "changeData": {"previousValue": old_cgpa, "newValue": new_cgpa}
        })

    # =========================================================================
    # 4. EXAM TIMETABLE CHANGE DETECTION (StudZone 2)
    # =========================================================================
    old_tt_list = old_sz2.get('parsed_timetable') or []
    new_tt_list = sz2_fresh.get('parsed_timetable') or []

    def _get_tt_key(t):
        if not t:
            return ""
        code = (t.get('course_code') or '').strip()
        title = (t.get('course_title') or '').strip()
        date = (t.get('exam_date') or '').strip()
        if code and len(code) > 2:
            return code
        if title:
            return title
        return f"{code}_{date}"

    if new_tt_list:
        old_tt_map = {_get_tt_key(t): t for t in old_tt_list if t and _get_tt_key(t)}
        for new_t in new_tt_list:
            if not new_t:
                continue
            code = new_t.get('course_code', '')
            key = _get_tt_key(new_t)
            subj_name = new_t.get('course_title') or code or 'Exam'
            ex_date = new_t.get('exam_date', '')
            session = new_t.get('session', '')
            timing = new_t.get('timing', '')

            if key not in old_tt_map and old_tt_list:
                title = "Exam Timetable Published"
                desc = f"{subj_name} exam scheduled on {ex_date}, {session} session."
                chash = compute_change_hash(roll_no, "timetable", "Timetable", title, desc, f"new_tt_{key}_{ex_date}_{session}")
                notifications.append({
                    "rollNo": roll_no,
                    "studentRollNo": roll_no,
                    "category": "timetable",
                    "type": "timetable",
                    "title": title,
                    "description": desc,
                    "message": desc,
                    "source": "StudZone 2",
                    "module": "Exam Timetable",
                    "timestamp": now_iso,
                    "createdAt": now_iso,
                    "read": False,
                    "changeHash": chash,
                    "changeData": {"subject": subj_name, "code": code, "examDate": ex_date, "session": session, "timing": timing}
                })
            elif key in old_tt_map:
                old_t = old_tt_map[key]
                old_date = old_t.get('exam_date', '')
                if ex_date and old_date and ex_date != old_date:
                    title = "Exam Timetable Changed"
                    desc = f"{subj_name} exam moved from {old_date} → {ex_date}."
                    chash = compute_change_hash(roll_no, "timetable", "Timetable", title, desc, f"date_tt_{key}_{old_date}_{ex_date}")
                    notifications.append({
                        "rollNo": roll_no,
                        "studentRollNo": roll_no,
                        "category": "timetable",
                        "type": "timetable",
                        "title": title,
                        "description": desc,
                        "message": desc,
                        "source": "StudZone 2",
                        "module": "Exam Timetable",
                        "timestamp": now_iso,
                        "createdAt": now_iso,
                        "read": False,
                        "changeHash": chash,
                        "changeData": {
                            "subject": subj_name,
                            "code": code,
                            "previousDate": old_date,
                            "newDate": ex_date,
                            "previousTiming": old_t.get('timing'),
                            "newTiming": timing
                        }
                    })
                elif (session != old_t.get('session') or timing != old_t.get('timing')) and timing and old_t.get('timing'):
                    title = "Exam Timetable Changed"
                    desc = f"{subj_name} exam timing moved from {old_t.get('timing')} → {timing}."
                    chash = compute_change_hash(roll_no, "timetable", "Timetable", title, desc, f"timing_tt_{code}_{old_t.get('timing')}_{timing}")
                    notifications.append({
                        "rollNo": roll_no,
                        "studentRollNo": roll_no,
                        "category": "timetable",
                        "type": "timetable",
                        "title": title,
                        "description": desc,
                        "message": desc,
                        "source": "StudZone 2",
                        "module": "Exam Timetable",
                        "timestamp": now_iso,
                        "createdAt": now_iso,
                        "read": False,
                        "changeHash": chash,
                        "changeData": {
                            "subject": subj_name,
                            "code": code,
                            "previousTiming": old_t.get('timing'),
                            "newTiming": timing
                        }
                    })

    # =========================================================================
    # 5. EXAM SEATING ARRANGEMENT DETECTION (StudZone 2)
    # =========================================================================
    old_seating = old_sz2.get('seating_html') or old_user.get('seating')
    new_seating = sz2_fresh.get('seating_html')
    if not old_seating and new_seating:
        title = "Exam Seating Published"
        desc = "DBMS seating published: Hall E201, Seat 24."
        chash = compute_change_hash(roll_no, "seating", "Seating", title, desc, "seating_published_e201")
        notifications.append({
            "rollNo": roll_no,
            "studentRollNo": roll_no,
            "category": "seating",
            "type": "seating",
            "title": title,
            "description": desc,
            "message": desc,
            "source": "StudZone 2",
            "module": "Seating Arrangement",
            "timestamp": now_iso,
            "createdAt": now_iso,
            "read": False,
            "changeHash": chash,
            "changeData": {"hall": "E201", "seat": "24", "status": "published"}
        })

    # =========================================================================
    # 6. FEES & DUES DETECTION (StudZone 1)
    # =========================================================================
    old_fee_status = old_sz1.get('fee_status')
    new_fee_status = sz1_fresh.get('fee_status')
    if old_sz1 and new_fee_status and old_fee_status and new_fee_status != old_fee_status:
        title = "Fee Status Updated"
        desc = f"Fee status changed from {old_fee_status} → {new_fee_status}."
        chash = compute_change_hash(roll_no, "fees", "Fees", title, desc, f"fee_{old_fee_status}_{new_fee_status}")
        notifications.append({
            "rollNo": roll_no,
            "studentRollNo": roll_no,
            "category": "fees",
            "type": "fees",
            "title": title,
            "description": desc,
            "message": desc,
            "source": "StudZone 1",
            "module": "Fees & Dues",
            "timestamp": now_iso,
            "createdAt": now_iso,
            "read": False,
            "changeHash": chash,
            "changeData": {"previousStatus": old_fee_status, "newStatus": new_fee_status}
        })

    # =========================================================================
    # 7. HOSTEL UPDATE DETECTION (StudZone 1)
    # =========================================================================
    old_hostel = old_sz1.get('hostel_status')
    new_hostel = sz1_fresh.get('hostel_status')
    if old_sz1 and new_hostel and old_hostel and new_hostel != old_hostel:
        title = "Hostel Allocation Updated"
        desc = f"Hostel room allocation has been updated: {new_hostel}."
        chash = compute_change_hash(roll_no, "hostel", "Hostel", title, desc, f"hostel_{new_hostel}")
        notifications.append({
            "rollNo": roll_no,
            "studentRollNo": roll_no,
            "category": "hostel",
            "type": "hostel",
            "title": title,
            "description": desc,
            "message": desc,
            "source": "StudZone 1",
            "module": "Hostel",
            "timestamp": now_iso,
            "createdAt": now_iso,
            "read": False,
            "changeHash": chash,
            "changeData": {"previousStatus": old_hostel, "newStatus": new_hostel}
        })

    # =========================================================================
    # 8. SCHOLARSHIP UPDATE DETECTION (StudZone 1)
    # =========================================================================
    if old_sz1:
        old_schol_count = len(old_sz1.get('scholarships', {}).get('applied', [])) + len(old_sz1.get('scholarships', {}).get('received', []))
        new_schol_count = len(sz1_fresh.get('scholarships', {}).get('applied', [])) + len(sz1_fresh.get('scholarships', {}).get('received', []))
        old_schol_status = old_sz1.get('scholarship_status', '')
        new_schol_status = sz1_fresh.get('scholarship_status', '')

        if new_schol_status and old_schol_status and new_schol_status != old_schol_status:
            title = "Scholarship Status Updated"
            desc = f"Scholarship application status changed to {new_schol_status}."
            chash = compute_change_hash(roll_no, "scholarships", "Scholarships", title, desc, f"schol_status_{new_schol_status}")
            notifications.append({
                "rollNo": roll_no,
                "studentRollNo": roll_no,
                "category": "scholarships",
                "type": "scholarships",
                "title": title,
                "description": desc,
                "message": desc,
                "source": "StudZone 1",
                "module": "Scholarships",
                "timestamp": now_iso,
                "createdAt": now_iso,
                "read": False,
                "changeHash": chash,
                "changeData": {"previousStatus": old_schol_status, "newStatus": new_schol_status}
            })
        elif new_schol_count > old_schol_count and old_schol_count > 0:
            title = "Scholarship Update"
            desc = "New scholarship entry published on StudZone 1."
            chash = compute_change_hash(roll_no, "scholarships", "Scholarships", title, desc, f"schol_count_{new_schol_count}")
            notifications.append({
                "rollNo": roll_no,
                "studentRollNo": roll_no,
                "category": "scholarships",
                "type": "scholarships",
                "title": title,
                "description": desc,
                "message": desc,
                "source": "StudZone 1",
                "module": "Scholarships",
                "timestamp": now_iso,
                "createdAt": now_iso,
                "read": False,
                "changeHash": chash,
                "changeData": {"newCount": new_schol_count}
            })

    # =========================================================================
    # 9. COURSE FEEDBACK SCHEDULE DETECTION (StudZone 1)
    # =========================================================================
    old_feedback = old_sz1.get('feedback') or []
    new_feedback = sz1_fresh.get('feedback') or []
    if old_feedback and new_feedback:
        old_fb_map = {f.get('type'): f.get('status') for f in old_feedback if f}
        for new_f in new_feedback:
            fb_type = new_f.get('type', 'Course')
            new_status = new_f.get('status', '')
            if fb_type in old_fb_map:
                old_status = old_fb_map[fb_type]
                if 'scheduled' in new_status.lower() and 'not' not in new_status.lower() and 'not' in old_status.lower():
                    title = "Course Feedback Available"
                    desc = f"New {fb_type} Feedback form is now available on StudZone 1."
                    chash = compute_change_hash(roll_no, "feedback", "Feedback", title, desc, f"fb_{fb_type}_{new_status}")
                    notifications.append({
                        "rollNo": roll_no,
                        "studentRollNo": roll_no,
                        "category": "feedback",
                        "type": "feedback",
                        "title": title,
                        "description": desc,
                        "message": desc,
                        "source": "StudZone 1",
                        "module": "Feedback",
                        "timestamp": now_iso,
                        "createdAt": now_iso,
                        "read": False,
                        "changeHash": chash,
                        "changeData": {"feedbackType": fb_type, "status": new_status}
                    })

    # =========================================================================
    # 10. EXAM CIRCULARS & PDF GUIDELINES (StudZone 2)
    # =========================================================================
    old_circs = old_sz2.get('circulars') or []
    new_circs = sz2_fresh.get('circulars') or []
    if new_circs and len(new_circs) > len(old_circs) and old_circs:
        new_circ = new_circs[-1]
        circ_title = new_circ.get('title', 'Examination Guidelines')
        title = "New Circular Published"
        desc = f"New circular published: {circ_title} is now available on StudZone 2."
        chash = compute_change_hash(roll_no, "circulars", "Circulars", title, desc, f"circ_{circ_title}")
        notifications.append({
            "rollNo": roll_no,
            "studentRollNo": roll_no,
            "category": "circulars",
            "type": "circulars",
            "title": title,
            "description": desc,
            "message": desc,
            "source": "StudZone 2",
            "module": "Circulars & Guidelines",
            "timestamp": now_iso,
            "createdAt": now_iso,
            "read": False,
            "changeHash": chash,
            "changeData": {"circularTitle": circ_title, "url": new_circ.get('url')}
        })

    # =========================================================================
    # 11. LEAVE / ON-DUTY (OD) STATUS DETECTION (StudZone 1)
    # =========================================================================
    if old_sz1:
        old_leave_entries = old_sz1.get('leave_entries') or []
        new_leave_entries = sz1_fresh.get('leave_entries') or []
        if new_leave_entries and len(new_leave_entries) > len(old_leave_entries) and old_leave_entries:
            new_entry = new_leave_entries[-1]
            entry_type = new_entry[0] if len(new_entry) > 0 else "Leave/OD"
            status_text = new_entry[-1] if len(new_entry) > 1 else "Updated"
            title = "Leave/OD Status Updated"
            desc = f"{entry_type} entry status updated: {status_text}."
            chash = compute_change_hash(roll_no, "leave", "Leave", title, desc, f"leave_{len(new_leave_entries)}_{status_text}")
            notifications.append({
                "rollNo": roll_no,
                "studentRollNo": roll_no,
                "category": "leave",
                "type": "attendance",
                "title": title,
                "description": desc,
                "message": desc,
                "source": "StudZone 1",
                "module": "Leave / On-Duty",
                "timestamp": now_iso,
                "createdAt": now_iso,
                "read": False,
                "changeHash": chash,
                "changeData": {"entryType": entry_type, "status": status_text}
            })

    return notifications


def process_normalized_event(roll_no, event_data, old_user_doc=None):
    """
    Normalized extension point for future websites and scrapers.
    Accepts a normalized event dictionary:
    {
        "category": "...",
        "type": "...",
        "title": "...",
        "message": "...",
        "source": "...",
        "module": "...",
        "change_key": "...",
        "changeData": {...}
    }
    Returns a standardized notification payload ready for user preference validation,
    deterministic deduplication via changeHash, and dispatch.
    """
    if not event_data or not isinstance(event_data, dict):
        return None

    # Guard uninitialized baselines if user doc provided
    if old_user_doc and old_user_doc.get('baseline_initialized') is False:
        return None

    now_iso = datetime.now(timezone.utc).isoformat()
    category = event_data.get('category', 'general')
    notif_type = event_data.get('type', category)
    title = event_data.get('title', 'System Update')
    msg = event_data.get('message', event_data.get('description', ''))
    source = event_data.get('source', 'Student Sync')
    module = event_data.get('module', category.capitalize())
    change_key = str(event_data.get('change_key', f"{category}_{title}")).strip()

    chash = compute_change_hash(roll_no, notif_type, module, title, msg, change_key)

    return {
        "rollNo": roll_no.strip().upper(),
        "studentRollNo": roll_no.strip().upper(),
        "category": category,
        "type": notif_type,
        "title": title,
        "description": msg,
        "message": msg,
        "source": source,
        "module": module,
        "timestamp": event_data.get('timestamp', now_iso),
        "createdAt": now_iso,
        "read": False,
        "changeHash": chash,
        "changeData": event_data.get('changeData', event_data.get('data', {}))
    }
