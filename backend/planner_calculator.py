"""
backend/planner_calculator.py

Personalized Study Planner & Cross-Module Academic Intelligence Engine
for Student Sync (Phase 7).

Synthesizes data across Attendance, Timetable, CA Marks, Historical Results,
CGPA, and Exam Schedules into transparent, deterministic daily priorities
and subject-level risk assessments.

ABSOLUTE ARCHITECTURAL RULES:
1. 100% READ-ONLY: Pure in-memory calculation. Zero database writes.
2. NO SPECULATIVE GRADE PREDICTIONS: Strictly avoids hardcoded cutoffs (O >= 90)
   or SEE target score predictions.
3. NEUTRAL ACADEMIC TERMINOLOGY: Uses neutral labels ("Critical Attendance",
   "Below Target", "Attendance Boundary", "Low Bunk Margin") instead of
   unsupported institutional claims.
4. SAFE MISSING DATA HANDLING: Never converts pending '*' marks to zero;
   never fabricates exam dates or assignment deadlines.
"""

from datetime import datetime
import re
from typing import Dict, List, Optional, Any, Tuple

# Protected calculator imports (strictly read-only usage)
from attendance_calculator import (
    calculate_attendance,
    calculate_safe_bunks,
    get_attendance_status,
    summarize_student_attendance
)
from academic_calculator import (
    summarize_student_academics
)
from timetable_calculator import (
    parse_weekly_schedule_matrix,
    parse_exam_schedule_records,
    parse_circulars
)


# Standard academic weekdays
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


def get_current_or_target_weekday(target_day: Optional[str] = None) -> str:
    """
    Determines the target weekday.
    Defaults to current real weekday if Monday-Friday, else defaults to Monday.
    Can be explicitly overridden by target_day parameter.
    """
    if target_day and isinstance(target_day, str):
        day_clean = target_day.strip().capitalize()
        if day_clean in WEEKDAYS:
            return day_clean

    current_idx = datetime.now().weekday()  # 0=Monday, 4=Friday, 5=Saturday, 6=Sunday
    if current_idx < 5:
        return WEEKDAYS[current_idx]
    return "Monday"


def compute_academic_priority_score(
    attendance_data: Dict[str, Any],
    ca_data: Dict[str, Any],
    timetable_slots_today: List[Dict[str, Any]],
    exam_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Computes the deterministic Academic Priority Score and transparent rationales.

    Point allocation:
    - Attendance:
        * Critical (<65%): +50 ("Critical Attendance")
        * Below Target (65% to <75%): +40 ("Below Target")
        * Attendance Boundary (>=75% with 0 safe bunks): +30 ("Attendance Boundary")
        * Low Bunk Margin (1-2 safe bunks): +15 ("Low Bunk Margin")
        * Healthy Attendance (>2 safe bunks): +0
    - Timetable:
        * Scheduled today: +25 ("Scheduled today")
    - Continuous Assessment:
        * 3+ pending evaluations: +15 ("High CA Activity")
        * 1-2 pending evaluations: +10 ("Active CA Activity")
        * 0 pending evaluations: +0
    - Examination:
        * Known exam date <= 14 days: +35 ("Final Exam Soon")
        * Registered with date pending: +5 ("Exam Schedule Pending")

    Priority Levels:
        * 60+  -> HIGH
        * 35-59 -> MEDIUM
        * 0-34  -> LOW
    """
    reasons: List[str] = []
    urgency_tags: List[str] = []
    score = 0

    # 1. Attendance Urgency
    pct = float(attendance_data.get("percentage", 100.0))
    safe_bunks = int(attendance_data.get("safe_bunks", 0))

    if pct < 65.0:
        score += 50
        urgency_tags.append("CRITICAL_ATTENDANCE")
        reasons.append(f"Critical Attendance: {pct:.2f}% (Below 65% threshold)")
    elif pct < 75.0:
        score += 40
        urgency_tags.append("BELOW_TARGET")
        reasons.append(f"Below Target: {pct:.2f}% (Below 75.0% institutional baseline)")
    elif safe_bunks == 0:
        score += 30
        urgency_tags.append("ATTENDANCE_BOUNDARY")
        reasons.append(f"Attendance Boundary: {pct:.2f}% with 0 safe bunks remaining (Next bunk drops below 75%)")
    elif safe_bunks in (1, 2):
        score += 15
        urgency_tags.append("LOW_BUNK_MARGIN")
        reasons.append(f"Low Bunk Margin: Only {safe_bunks} safe bunk(s) available")
    else:
        urgency_tags.append("HEALTHY_ATTENDANCE")

    # 2. Timetable Urgency (Scheduled Today)
    today_periods_count = len(timetable_slots_today)
    if today_periods_count > 0:
        score += 25
        urgency_tags.append("SCHEDULED_TODAY")
        period_numbers = [str(slot.get("period", "")) for slot in timetable_slots_today if slot.get("period")]
        period_str = f"Period {', '.join(period_numbers)}" if period_numbers else f"{today_periods_count} class(es)"
        reasons.append(f"Scheduled today: {today_periods_count} period(s) ({period_str})")

    # 3. Continuous Assessment (CA) Activity
    pending_ca = int(ca_data.get("pending_evaluations", 0))
    if pending_ca >= 3:
        score += 15
        urgency_tags.append("HIGH_CA_ACTIVITY")
        reasons.append(f"High CA Activity: {pending_ca} pending evaluation components")
    elif pending_ca in (1, 2):
        score += 10
        urgency_tags.append("CA_ACTIVITY")
        reasons.append(f"Active CA: {pending_ca} pending evaluation component(s)")

    # 4. Examination Schedule
    is_exam_registered = bool(exam_data.get("is_registered", False))
    days_to_exam = exam_data.get("days_remaining")

    if is_exam_registered:
        if days_to_exam is not None and days_to_exam <= 14:
            score += 35
            urgency_tags.append("EXAM_SOON")
            reasons.append(f"Final Exam Soon: Scheduled in {days_to_exam} day(s)")
        else:
            score += 5
            urgency_tags.append("EXAM_PENDING")
            reasons.append("End-Semester Theory Exam registered (Date Pending)")

    # Assign Priority Level
    if score >= 60:
        level = "HIGH"
    elif score >= 35:
        level = "MEDIUM"
    else:
        level = "LOW"
        if not reasons:
            reasons.append("Stable attendance and academic margin; routine study focus")

    return {
        "score": score,
        "level": level,
        "reasons": reasons,
        "urgency_tags": urgency_tags
    }


def synthesize_academic_planner(
    user_doc: Optional[Dict[str, Any]],
    target_day: Optional[str] = None
) -> Dict[str, Any]:
    """
    Synthesizes the complete Personalized Academic Planner intelligence payload.
    Unifies:
    1. Student & Verified Academic Health Metrics
    2. Today's Context & Scheduled Focus
    3. Cross-Module Subject Intelligence Matrix
    4. Registered End-Semester Examination Status
    """
    if not user_doc or not isinstance(user_doc, dict):
        return {
            "error": "Invalid or missing user document",
            "student": {},
            "subject_matrix": [],
            "today_context": {}
        }

    roll_no = user_doc.get("rollNo", "")
    name = re.sub(r'\s+', ' ', user_doc.get("name", "")).strip()
    stored_cgpa = user_doc.get("cgpa")
    try:
        stored_cgpa = float(stored_cgpa) if stored_cgpa is not None else None
    except (ValueError, TypeError):
        stored_cgpa = None

    sz1 = user_doc.get("studzone1", {})
    sz2 = user_doc.get("studzone2", {})

    parsed_attendance = sz1.get("parsed_attendance", [])
    raw_schedule = sz1.get("class_schedule", [])
    parsed_timetable = sz2.get("parsed_timetable", [])
    circulars_raw = sz2.get("circulars", [])

    # 1. Execute Read-Only Calculator Engines (resolving student-specific course titles)
    att_summary = summarize_student_attendance(parsed_attendance, user_doc=user_doc)
    acad_profile = summarize_student_academics(user_doc)
    weekly_matrix = parse_weekly_schedule_matrix(raw_schedule)
    exam_summary = parse_exam_schedule_records(parsed_timetable, circulars=circulars_raw)
    circulars_summary = parse_circulars(circulars_raw)

    verified_historical_credits = acad_profile.get("results", {}).get("total_credits", 0.0)

    # 2. Build Lookups by Normalized Course Code
    # Timetable slots by course code and day
    schedule_by_code_all_week: Dict[str, List[Dict[str, Any]]] = {}
    schedule_by_code_by_day: Dict[str, Dict[str, List[Dict[str, Any]]]] = {day: {} for day in WEEKDAYS}

    for d in weekly_matrix.get("days", []):
        day_name = d.get("day")
        if day_name not in schedule_by_code_by_day:
            continue
        for p in d.get("periods", []):
            if not p.get("is_free"):
                c_code = str(p.get("code") or "").strip().upper()
                slot_info = {
                    "day": day_name,
                    "period": p.get("period"),
                    "time": p.get("time"),
                    "section": p.get("section")
                }
                if c_code not in schedule_by_code_all_week:
                    schedule_by_code_all_week[c_code] = []
                schedule_by_code_all_week[c_code].append(slot_info)

                if c_code not in schedule_by_code_by_day[day_name]:
                    schedule_by_code_by_day[day_name][c_code] = []
                schedule_by_code_by_day[day_name][c_code].append(slot_info)

    # CA summary by course code
    ca_lookup: Dict[str, Dict[str, Any]] = {}
    total_pending_ca_evaluations = 0
    total_entered_ca_evaluations = 0

    for c in acad_profile.get("ca_marks", {}).get("courses", []):
        code_norm = str(c.get("code") or "").strip().upper()
        entered_cnt = c.get("entered_components", 0)
        pending_cnt = c.get("pending_components", 0)
        total_entered_ca_evaluations += entered_cnt
        total_pending_ca_evaluations += pending_cnt
        ca_lookup[code_norm] = {
            "entered_evaluations": entered_cnt,
            "pending_evaluations": pending_cnt,
            "category": c.get("category", "Theory"),
            "components": c.get("components", []),
            "converted_ca": c.get("converted_ca"),
            "converted_max": c.get("converted_max")
        }

    # Exam lookup by course code
    exam_lookup: Dict[str, Dict[str, Any]] = {}
    for ex in exam_summary.get("exams", []):
        code_norm = str(ex.get("course_code") or "").strip().upper()
        exam_lookup[code_norm] = ex

    # 3. Determine Active / Selected Weekday
    active_day = get_current_or_target_weekday(target_day)

    # 4. Construct Subject Intelligence Matrix (for all registered attendance courses)
    subject_matrix: List[Dict[str, Any]] = []
    high_priority_count = 0
    attention_needed_count = 0

    for sub in att_summary.get("subjects", []):
        c_code = str(sub.get("code") or "").strip().upper()
        c_name = str(sub.get("name") or c_code).strip()

        att_pct = float(sub.get("percentage", 0.0))
        att_cond = int(sub.get("total_classes", sub.get("conducted", 0)))
        att_done = int(sub.get("attended", 0))
        safe_bunks = int(sub.get("safe_bunks", 0))
        status_label = sub.get("status", "NORMAL")

        weekly_slots = schedule_by_code_all_week.get(c_code, [])
        weekly_hours = len(weekly_slots)

        today_slots = schedule_by_code_by_day.get(active_day, {}).get(c_code, [])

        ca_info = ca_lookup.get(c_code, {
            "entered_evaluations": 0,
            "pending_evaluations": 0,
            "category": "Theory",
            "components": [],
            "converted_ca": None,
            "converted_max": None
        })

        ex_info = exam_lookup.get(c_code, {
            "course_code": c_code,
            "exam_date": "Schedule Pending",
            "session": "TBA",
            "timing": "Timing TBA",
            "status": "PENDING",
            "is_registered": False,
            "days_remaining": None
        })

        # Calculate Priority Score for this subject on active_day
        prio = compute_academic_priority_score(
            attendance_data={"percentage": att_pct, "safe_bunks": safe_bunks},
            ca_data={"pending_evaluations": ca_info["pending_evaluations"]},
            timetable_slots_today=today_slots,
            exam_data={
                "is_registered": bool(ex_info.get("is_registered", c_code in exam_lookup)),
                "days_remaining": ex_info.get("days_remaining")
            }
        )

        if prio["level"] == "HIGH":
            high_priority_count += 1
        if prio["level"] in ("HIGH", "MEDIUM") or safe_bunks == 0 or att_pct < 75.0:
            attention_needed_count += 1

        subject_item = {
            "code": c_code,
            "name": c_name,
            "category": ca_info.get("category", "Theory"),
            "attendance": {
                "attended": att_done,
                "conducted": att_cond,
                "percentage": att_pct,
                "safe_bunks": safe_bunks,
                "classes_to_attend": sub.get("classes_to_attend", 0),
                "status": status_label
            },
            "schedule": {
                "weekly_periods": weekly_hours,
                "scheduled_today": len(today_slots) > 0,
                "today_slots": today_slots
            },
            "ca_progress": {
                "entered": ca_info["entered_evaluations"],
                "pending": ca_info["pending_evaluations"],
                "total_components": ca_info["entered_evaluations"] + ca_info["pending_evaluations"],
                "converted_ca": ca_info["converted_ca"],
                "converted_max": ca_info["converted_max"]
            },
            "exam": {
                "is_registered": bool(c_code in exam_lookup),
                "exam_date": ex_info.get("exam_date", "Schedule Pending"),
                "session": ex_info.get("session", "TBA"),
                "timing": ex_info.get("timing", "Timing TBA"),
                "status": ex_info.get("status", "PENDING")
            },
            "priority": prio,
            "attention_needed": prio["level"] in ("HIGH", "MEDIUM") or safe_bunks == 0 or att_pct < 75.0
        }
        subject_matrix.append(subject_item)

    # 5. Build "Today's Focus & Priority Recommendations"
    # Filter subjects scheduled today on active_day and sort by priority score descending
    today_scheduled_subjects = [s for s in subject_matrix if s["schedule"]["scheduled_today"]]
    today_scheduled_subjects.sort(key=lambda x: x["priority"]["score"], reverse=True)

    # In case there are no classes scheduled (e.g. holiday or weekend), fall back to top priority courses overall
    if not today_scheduled_subjects:
        recommended_focus = sorted(subject_matrix, key=lambda x: x["priority"]["score"], reverse=True)[:3]
        has_classes_today = False
    else:
        recommended_focus = today_scheduled_subjects
        has_classes_today = True

    # Compute overall scheduled periods today
    today_periods_total = sum(len(s["schedule"]["today_slots"]) for s in today_scheduled_subjects)

    # 6. Registered Exams Summary
    total_registered_exams = len(exam_lookup)
    exam_dates_pending = any(ex.get("exam_date") == "Schedule Pending" for ex in exam_lookup.values())

    return {
        "student": {
            "rollNo": roll_no,
            "name": name,
            "cgpa": stored_cgpa,
            "verified_historical_credits": verified_historical_credits,
            "active_courses_count": len(subject_matrix)
        },
        "attendance": {
            "attended": att_summary.get("overall", {}).get("attended", 0),
            "conducted": att_summary.get("overall", {}).get("conducted", 0),
            "percentage": att_summary.get("overall", {}).get("percentage", 0.0),
            "safe_bunks": att_summary.get("overall", {}).get("safe_bunks", 0),
            "status": att_summary.get("overall", {}).get("status", "NORMAL")
        },
        "today_context": {
            "day_name": active_day,
            "available_weekdays": WEEKDAYS,
            "has_classes_today": has_classes_today,
            "scheduled_subjects_count": len(today_scheduled_subjects),
            "scheduled_periods_count": today_periods_total,
            "recommended_focus": recommended_focus
        },
        "subject_matrix": subject_matrix,
        "academic_health": {
            "high_priority_count": high_priority_count,
            "attention_needed_count": attention_needed_count,
            "total_pending_ca": total_pending_ca_evaluations,
            "total_entered_ca": total_entered_ca_evaluations,
            "registered_exams_count": total_registered_exams,
            "exam_dates_pending": exam_dates_pending
        },
        "registered_exams_summary": {
            "total_registered": total_registered_exams,
            "schedule_status": "Schedule Pending" if exam_dates_pending else "Announced",
            "circular_count": len(circulars_summary) if isinstance(circulars_summary, list) else 0
        },
        "disclaimer": (
            "Study targets and daily recommendations are derived deterministically from verified portal records. "
            "Personal study goals are maintained privately in your browser with zero modifications to academic records."
        )
    }
