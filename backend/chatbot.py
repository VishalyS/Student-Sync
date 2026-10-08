"""
backend/chatbot.py

Student Sync Intelligent AI Assistant Engine.
Provides instant answers for:
1. Navigation throughout the Student Sync portal (with direct clickable deep links).
2. Subject-specific and overall attendance details, percentages, and safe bunk calculations.
3. Continuous Assessment (CA) marks and component breakdowns.
4. Weekly lecture timetables and today's class schedules.
5. Upcoming semester exam schedules, seating arrangements, and hall numbers.
6. CGPA, historical academic results, fees receipts, and hostel details.
7. Context-aware follow-up suggestions and structured interactive data cards.
"""

import re
import math
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

try:
    from database import user_collection
except ImportError:
    from backend.database import user_collection

from attendance_calculator import (
    resolve_student_attendance_records,
    summarize_student_attendance,
    calculate_safe_bunks,
    calculate_required_classes
)

try:
    from academic_calculator import parse_ca_marks_html, parse_ca_marks_fallback
except ImportError:
    try:
        from backend.academic_calculator import parse_ca_marks_html, parse_ca_marks_fallback
    except ImportError:
        parse_ca_marks_html = None
        parse_ca_marks_fallback = None

try:
    from timetable_calculator import parse_daily_schedule, parse_weekly_schedule_matrix
except ImportError:
    try:
        from backend.timetable_calculator import parse_daily_schedule, parse_weekly_schedule_matrix
    except ImportError:
        parse_daily_schedule = None
        parse_weekly_schedule_matrix = None


# Navigation routes mapping
NAV_ROUTES = [
    {
        "keywords": ["attendance", "bunk", "safe bunk", "attendance simulator", "absent", "percentage"],
        "path": "/attendance",
        "label": "Attendance Dashboard",
        "description": "View subject-wise attendance, safe bunks, and interactive simulator."
    },
    {
        "keywords": ["timetable", "schedule", "class schedule", "lecture", "period", "routine"],
        "path": "/schedule",
        "label": "Class & Exam Schedule",
        "description": "Check weekly timetable, today's lecture slots, and day-bunk analysis."
    },
    {
        "keywords": ["exam", "seating", "hall", "desk", "room", "coe", "end sem", "exam date"],
        "path": "/schedule",
        "label": "Exam Schedule & Seating",
        "description": "Check upcoming exam timetable, hall numbers, and desk allocations."
    },
    {
        "keywords": ["marks", "ca marks", "continuous assessment", "ca1", "ca2", "internal", "test marks", "grade", "cgpa", "sgpa", "gpa", "cgpa simulator"],
        "path": "/grades",
        "label": "Academic Performance & Grades",
        "description": "View CA component breakdowns, exam results, and CGPA simulator."
    },
    {
        "keywords": ["planner", "academic health", "risk", "study", "recommendation"],
        "path": "/planner",
        "label": "Personalized Academic Planner",
        "description": "View academic health score, high-risk courses, and study focus."
    },
    {
        "keywords": ["fees", "tuition", "receipt", "dues", "hostel", "mess", "leave", "circular"],
        "path": "/services",
        "label": "Campus Services & Fees",
        "description": "Access semester tuition receipts, hostel details, and campus services."
    },
    {
        "keywords": ["notification", "alert", "email", "welcome mail", "preference", "settings"],
        "path": "/welcome",
        "label": "Notification Settings",
        "description": "Manage portal change alerts, alert email, and notification preferences."
    },
    {
        "keywords": ["dashboard", "home", "profile", "overview", "main"],
        "path": "/dashboard",
        "label": "Student Dashboard",
        "description": "View your consolidated student profile and overview."
    }
]


def _clean_text(s: str) -> str:
    return re.sub(r'[^\w\s]', ' ', s.lower()).strip()


def fuzzy_match_subject(query: str, subjects: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Finds the most matching subject by course code or words in course title.
    """
    if not subjects:
        return None

    q_clean = _clean_text(query)
    q_words = set(q_clean.split())

    # 1. Exact course code match (e.g. "23MX31" or "MX31" or "31")
    for subj in subjects:
        code = str(subj.get("code", "")).strip().upper()
        if code and code.lower() in q_clean:
            return subj
        # Check numeric suffix if 4+ chars
        if len(code) >= 4 and code[-4:].lower() in q_clean:
            return subj

    # 2. Match by subject name words
    best_match = None
    best_score = 0

    # Common generic words to ignore when matching subject names
    stop_words = {"my", "what", "is", "the", "in", "for", "attendance", "marks", "ca", "grade", "subject", "classes", "bunk", "can", "i", "how", "much", "percentage", "show", "tell", "details", "status"}

    query_content_words = q_words - stop_words

    for subj in subjects:
        name = str(subj.get("name", "")).strip().lower()
        if not name:
            continue
        name_words = set(_clean_text(name).split())

        # Exact phrase match in query
        if name in q_clean:
            return subj

        # Overlap of content words
        overlap = len(query_content_words.intersection(name_words))
        if overlap > best_score:
            best_score = overlap
            best_match = subj

    if best_score >= 1:
        return best_match

    return None


def get_student_academic_snapshot(roll_no: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Loads verified student document from MongoDB and computes rich attendance summary.
    """
    if user_collection is None:
        return None, None

    roll_clean = roll_no.strip().upper()
    user_doc = user_collection.find_one({
        "rollNo": {"$regex": f"^{re.escape(roll_clean)}$", "$options": "i"}
    })
    if not user_doc:
        return None, None

    records, is_prev, is_upd = resolve_student_attendance_records(user_doc)
    summary = summarize_student_attendance(records, target=75.0, user_doc=user_doc)

    return user_doc, summary


def process_chatbot_query(query: str, roll_no: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """
    Main entry point for processing a student's chatbot message.
    Extracts intent, queries real student records, formats response, and provides navigation.
    """
    q_raw = query.strip()
    q_lower = q_raw.lower()
    q_clean = _clean_text(q_lower)

    user_doc, att_summary = get_student_academic_snapshot(roll_no)
    if not user_doc:
        return {
            "reply": f"I couldn't find a student account for roll number **{roll_no}**. Please log in or check your credentials.",
            "intent": "unknown_student",
            "navigation": {"path": "/login", "label": "Go to Login Page"},
            "suggestions": ["How do I register?", "Take me to Login"]
        }

    student_name = user_doc.get("name") or roll_no
    first_name = student_name.split()[0].capitalize()
    subjects = att_summary.get("subjects", []) if att_summary else []
    overall = att_summary.get("overall", {}) if att_summary else {}
    is_updating = att_summary.get("is_updating", False) if att_summary else False

    # Check for direct Navigation request first
    is_explicit_nav = any(kw in q_clean for kw in ["go to", "take me to", "navigate to", "open", "show me page", "where is", "open page", "visit"])
    if is_explicit_nav:
        for route in NAV_ROUTES:
            if any(k in q_clean for k in route["keywords"]):
                return {
                    "reply": f"Sure {first_name}! Navigating you to the **{route['label']}**.\n\n_{route['description']}_",
                    "intent": "navigation",
                    "navigation": {
                        "path": route["path"],
                        "label": f"Open {route['label']} →"
                    },
                    "suggestions": [
                        "What is my overall attendance?",
                        "What classes do I have today?",
                        "Show my CA marks"
                    ]
                }

    # 1. SUBJECT-SPECIFIC ATTENDANCE OR BUNKS
    matched_subj = fuzzy_match_subject(q_raw, subjects)
    is_asking_attendance = any(kw in q_clean for kw in ["attendance", "present", "absent", "conducted", "attended", "percent", "status"])
    is_asking_bunk = any(kw in q_clean for kw in ["bunk", "safe bunk", "miss", "skip", "cut"])

    if matched_subj and (is_asking_attendance or is_asking_bunk or len(q_clean.split()) <= 4):
        subj_name = matched_subj.get("name", "Unknown Course")
        subj_code = matched_subj.get("code", "")
        pct = matched_subj.get("percentage", 0.0)
        attended = matched_subj.get("attended", 0)
        conducted = matched_subj.get("conducted", 0)
        absent = matched_subj.get("absent", 0)
        safe_bunks = matched_subj.get("safe_bunks", 0)
        req_classes = matched_subj.get("required_classes", 0)
        status = matched_subj.get("status", "SAFE")

        status_emoji = "🟢" if status == "SAFE" else ("🟡" if status == "WARNING" else "🔴")

        if is_asking_bunk:
            if safe_bunks > 0:
                bunk_text = f"✅ You can safely bunk **{safe_bunks}** class{'es' if safe_bunks > 1 else ''} in **{subj_name}** while maintaining at least 75.0% attendance."
            elif req_classes > 0:
                bunk_text = f"⚠️ You **cannot bunk** any classes in **{subj_name}**. You need to attend the next **{req_classes}** consecutive class{'es' if req_classes > 1 else ''} to recover above 75.0%!"
            else:
                bunk_text = f"⚠️ Your attendance is right at the 75.0% threshold. Any bunk will drop you below 75%!"
            
            reply = (
                f"### {status_emoji} Bunk Analysis for {subj_name} (`{subj_code}`)\n\n"
                f"- **Current Attendance:** **{pct:.2f}%** ({attended}/{conducted} lectures attended)\n"
                f"- **Total Absences:** {absent} lectures\n\n"
                f"{bunk_text}\n\n"
                f"{'*(Note: PSG StudZone is currently publishing updates; displaying verified stored baseline.)*' if is_updating else ''}"
            )
        else:
            advice = (
                f"You have **{safe_bunks}** safe bunk(s) available." if safe_bunks > 0
                else (f"⚠️ Attend next **{req_classes}** class(es) to recover above 75%!" if req_classes > 0 else "Attendance is on the 75% threshold line.")
            )
            reply = (
                f"### {status_emoji} {subj_name} (`{subj_code}`)\n\n"
                f"- **Attendance:** **{pct:.2f}%**\n"
                f"- **Classes Attended:** {attended} of {conducted}\n"
                f"- **Classes Absent:** {absent}\n"
                f"- **Status:** **{status}**\n\n"
                f"💡 **Advice:** {advice}\n\n"
                f"{'*(Note: PSG StudZone is currently publishing updates; displaying verified stored baseline.)*' if is_updating else ''}"
            )

        return {
            "reply": reply,
            "intent": "subject_attendance",
            "navigation": {
                "path": "/attendance",
                "label": f"View {subj_code} in Simulator →"
            },
            "data_card": {
                "type": "subject_attendance",
                "code": subj_code,
                "name": subj_name,
                "percentage": pct,
                "attended": attended,
                "conducted": conducted,
                "safe_bunks": safe_bunks,
                "required_classes": req_classes,
                "status": status
            },
            "suggestions": [
                f"How many classes can I bunk in {subj_name}?",
                "Which subjects are below 75%?",
                "What is my overall attendance?",
                "Take me to Attendance Dashboard"
            ]
        }

    # 2. OVERALL ATTENDANCE OR GENERAL BUNK QUERY
    if any(kw in q_clean for kw in ["overall attendance", "total attendance", "my attendance", "attendance percentage", "average attendance", "how much attendance"]):
        ov_pct = overall.get("percentage", 0.0)
        ov_att = overall.get("attended", 0)
        ov_cond = overall.get("conducted", 0)
        ov_abs = overall.get("absent", 0)
        ov_bunks = overall.get("safe_bunks", 0)
        ov_status = overall.get("status", "SAFE")
        status_emoji = "🟢" if ov_status == "SAFE" else ("🟡" if ov_status == "WARNING" else "🔴")

        # Check for subjects needing attention
        low_subjs = [s for s in subjects if s.get("percentage", 0) < 75.0]
        warning_subjs = [s for s in subjects if 75.0 <= s.get("percentage", 0) < 80.0]

        low_text = ""
        if low_subjs:
            low_text = "\n\n⚠️ **Subjects below 75%:**\n" + "\n".join(
                [f"- **{s.get('name')}** (`{s.get('code')}`): **{s.get('percentage'):.2f}%** (Need {s.get('required_classes')} classes)" for s in low_subjs]
            )
        elif warning_subjs:
            low_text = "\n\n⚡ **Subjects in Caution Zone (75% - 80%):**\n" + "\n".join(
                [f"- **{s.get('name')}**: **{s.get('percentage'):.2f}%** ({s.get('safe_bunks')} bunk left)" for s in warning_subjs]
            )
        else:
            low_text = "\n\n🎉 **All subjects are comfortably above 80%! Keep it up!**"

        reply = (
            f"### {status_emoji} Overall Attendance Summary\n\n"
            f"- **Consolidated Percentage:** **{ov_pct:.2f}%**\n"
            f"- **Lectures Attended:** **{ov_att}** / {ov_cond}\n"
            f"- **Total Absences:** {ov_abs} lectures\n"
            f"- **Overall Safe Bunks:** **{ov_bunks}** class(es) across all courses\n"
            f"- **System Standing:** **{ov_status}**"
            f"{low_text}\n\n"
            f"{'*(Note: PSG StudZone is currently publishing updates; displaying verified stored baseline.)*' if is_updating else ''}"
        )

        return {
            "reply": reply,
            "intent": "overall_attendance",
            "navigation": {
                "path": "/attendance",
                "label": "Open Attendance Dashboard →"
            },
            "data_card": {
                "type": "overall_attendance",
                "percentage": ov_pct,
                "attended": ov_att,
                "conducted": ov_cond,
                "safe_bunks": ov_bunks,
                "status": ov_status
            },
            "suggestions": [
                "Which subjects are below 75%?",
                "What classes do I have today?",
                "Show my CA marks",
                "Take me to Attendance"
            ]
        }

    # 3. LOW ATTENDANCE / SHORTAGE / CRITICAL COURSES
    if any(kw in q_clean for kw in ["below 75", "low attendance", "shortage", "danger", "critical", "warning", "risk", "can i bunk"]):
        low_subjs = [s for s in subjects if s.get("percentage", 0) < 75.0]
        if low_subjs:
            lines = []
            for s in low_subjs:
                lines.append(f"- 🔴 **{s.get('name')}** (`{s.get('code')}`): **{s.get('percentage'):.2f}%** (Attended: {s.get('attended')}/{s.get('conducted')}) • Needs **{s.get('required_classes')}** classes to reach 75%")
            reply = (
                f"### ⚠️ You have {len(low_subjs)} subject{'s' if len(low_subjs) > 1 else ''} below 75% attendance:\n\n"
                + "\n".join(lines)
                + "\n\n**Action Required:** Prioritize attending these lectures consecutively to avoid semester exam hall ticket stoppage."
            )
        else:
            reply = (
                f"### 🎉 Great news, {first_name}!\n\n"
                f"You currently have **0 subjects below 75%**! All your courses meet the PSG Tech minimum attendance requirement.\n\n"
                f"Your overall attendance is **{overall.get('percentage', 0.0):.2f}%**."
            )

        return {
            "reply": reply,
            "intent": "critical_attendance",
            "navigation": {"path": "/attendance", "label": "Simulate Recovery in Attendance →"},
            "suggestions": [
                "What is my overall attendance?",
                "Can I bunk tomorrow?",
                "Show my today's timetable"
            ]
        }

    # 4. CONTINUOUS ASSESSMENT (CA) MARKS
    if any(kw in q_clean for kw in ["marks", "ca marks", "ca1", "ca2", "internal", "test marks", "assessment", "score"]):
        ca_html = (user_doc.get("studzone1") or {}).get("ca_marks_html") or user_doc.get("marks", "")
        ca_parsed = (user_doc.get("studzone1") or {}).get("parsed_marks", [])
        
        parsed_courses = []
        if parse_ca_marks_html and ca_html:
            parsed_courses = parse_ca_marks_html(ca_html)
        elif parse_ca_marks_fallback and ca_parsed:
            parsed_courses = parse_ca_marks_fallback(ca_parsed)

        if matched_subj and parsed_courses:
            m_code = matched_subj.get("code", "")
            target_course = next((c for c in parsed_courses if c.get("code") == m_code), None)
            if target_course:
                comps = target_course.get("components", [])
                lines = []
                for comp in comps:
                    val = comp.get("mark")
                    max_val = comp.get("max_mark", "")
                    val_str = f"{val}/{max_val}" if val is not None else "Pending / TBA"
                    lines.append(f"- **{comp.get('name')}:** {val_str}")

                reply = (
                    f"### 📝 Continuous Assessment Marks: {target_course.get('name')} (`{m_code}`)\n\n"
                    + ("\n".join(lines) if lines else "No published CA component marks found yet for this course.")
                )
                return {
                    "reply": reply,
                    "intent": "subject_marks",
                    "navigation": {"path": "/grades", "label": "View Full CA Breakdown in Grades →"},
                    "suggestions": ["Show all my CA marks", "What is my CGPA?", "Go to Grades"]
                }

        if parsed_courses:
            lines = []
            for c in parsed_courses[:6]:
                # find total or CA1
                comps = c.get("components", [])
                comp_summary = ", ".join([f"{cmp.get('name')}: {cmp.get('mark')}" for cmp in comps[:2] if cmp.get('mark') is not None])
                lines.append(f"- **{c.get('name')}** (`{c.get('code')}`): {comp_summary or 'In progress'}")

            reply = (
                f"### 📝 Continuous Assessment (CA) Overview\n\n"
                + "\n".join(lines)
                + "\n\n*(Full component breakups including CA1, CA2, assignments, and tutorials are on the Grades page.)*"
            )
        else:
            reply = "Your Continuous Assessment marks are currently being synced or haven't been published yet on StudZone."

        return {
            "reply": reply,
            "intent": "ca_marks",
            "navigation": {"path": "/grades", "label": "Open Academic Performance →"},
            "suggestions": ["What is my CGPA?", "What is my attendance?", "Take me to Grades"]
        }

    # 5. TODAY'S SCHEDULE & CLASS TIMETABLE
    if any(kw in q_clean for kw in ["today", "classes today", "schedule today", "lecture today", "timetable", "routine", "period", "next class"]):
        sz1 = user_doc.get("studzone1") or {}
        raw_schedule = sz1.get("class_schedule", [])
        raw_tt_html = sz1.get("class_timetable_html", "")

        today_name = datetime.now().strftime("%A")
        
        # Check if user asked for a specific day
        for d in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
            if d.lower() in q_clean:
                today_name = d
                break

        if parse_daily_schedule and (raw_schedule or raw_tt_html):
            daily_slots = parse_daily_schedule(raw_schedule, day_name=today_name, class_timetable_html=raw_tt_html)
            if daily_slots and len(daily_slots) > 0:
                lines = []
                for slot in daily_slots:
                    period = slot.get("period", "")
                    time_str = slot.get("time", "")
                    code = slot.get("code", "")
                    name = slot.get("name", "")
                    room = slot.get("room") or "Assigned Hall"
                    if code == "FREE" or not code:
                        lines.append(f"- **Period {period}** ({time_str}): *Free Period / Break*")
                    else:
                        lines.append(f"- **Period {period}** ({time_str}): **{name}** (`{code}`) • Room: {room}")

                reply = (
                    f"### 🗓️ Lecture Schedule for {today_name}\n\n"
                    + "\n".join(lines)
                    + f"\n\nTotal periods today: **{len(daily_slots)}**"
                )
            else:
                reply = f"### 🗓️ No classes scheduled for **{today_name}**! Enjoy your free day! 🎉"
        else:
            reply = f"Your timetable for {today_name} is currently available in the Class Schedule view."

        return {
            "reply": reply,
            "intent": "timetable",
            "navigation": {"path": "/schedule", "label": "Open Weekly Timetable Grid →"},
            "suggestions": [
                "Can I bunk tomorrow?",
                "What is my attendance in Cloud Computing?",
                "Upcoming exam dates",
                "Take me to Schedule"
            ]
        }

    # 6. EXAM SCHEDULE & SEATING ARRANGEMENTS
    if any(kw in q_clean for kw in ["exam", "seating", "hall", "desk", "room number", "coe", "end sem", "test room"]):
        seating_data = user_doc.get("seating") or (user_doc.get("studzone2") or {}).get("seating_html")
        sz2 = user_doc.get("studzone2") or {}
        parsed_seating = sz2.get("parsed_seating", [])
        parsed_timetable = sz2.get("parsed_timetable", [])

        if parsed_seating and len(parsed_seating) > 0:
            lines = []
            for seat in parsed_seating[:5]:
                date = seat.get("date", "TBA")
                session = seat.get("session", "")
                hall = seat.get("hall", "TBA")
                desk = seat.get("desk", "TBA")
                course = seat.get("course_code") or seat.get("course_name", "")
                lines.append(f"- **{course}**: {date} ({session}) • **Hall {hall}**, Desk **{desk}**")
            
            reply = (
                f"### 🪑 Exam Seating Allocations\n\n"
                + "\n".join(lines)
            )
        elif parsed_timetable and len(parsed_timetable) > 0:
            lines = []
            for exam in parsed_timetable[:5]:
                date = exam.get("date", "TBA")
                session = exam.get("session", "")
                course = exam.get("course_code") or exam.get("course_name", "")
                lines.append(f"- **{course}**: {date} ({session})")

            reply = (
                f"### 📝 Examination Timetable\n\n"
                + "\n".join(lines)
                + "\n\n*(Individual hall desk numbers will appear once published by CoE.)*"
            )
        else:
            reply = (
                f"### ℹ️ Examination & Seating Status\n\n"
                f"End-semester exam hall allocations have not been released by the CoE yet for your batch. "
                f"Check back closer to test dates or view the schedule dashboard."
            )

        return {
            "reply": reply,
            "intent": "exam_seating",
            "navigation": {"path": "/schedule", "label": "Open Exam Schedule & Seating →"},
            "suggestions": [
                "What is my attendance?",
                "What is my CGPA?",
                "Take me to Schedule"
            ]
        }

    # 7. CGPA & RESULTS
    if any(kw in q_clean for kw in ["cgpa", "sgpa", "gpa", "grade", "result", "credits", "standing"]):
        cgpa = user_doc.get("cgpa")
        cgpa_str = f"**{cgpa:.2f}**" if isinstance(cgpa, (int, float)) else (str(cgpa) if cgpa else "N/A")

        reply = (
            f"### 🎓 Cumulative Grade Point Average (CGPA)\n\n"
            f"- **Student:** {student_name} (`{roll_no}`)\n"
            f"- **Current Official CGPA:** {cgpa_str}\n"
            f"- **Academic Standing:** Excellent / In Good Standing\n\n"
            f"You can use the **What-If CGPA Simulator** on the Grades page to simulate future semester grades and see your projected graduation CGPA!"
        )

        return {
            "reply": reply,
            "intent": "cgpa_results",
            "navigation": {"path": "/grades", "label": "Simulate Projected CGPA →"},
            "data_card": {
                "type": "cgpa",
                "cgpa": cgpa,
                "student": student_name
            },
            "suggestions": [
                "What is my overall attendance?",
                "Show my CA marks",
                "Take me to Grades"
            ]
        }

    # 8. FEES, HOSTEL, CAMPUS SERVICES
    if any(kw in q_clean for kw in ["fee", "tuition", "dues", "hostel", "mess", "receipt"]):
        fees_html = user_doc.get("fees") or (user_doc.get("studzone1") or {}).get("fees_html", "")
        hostel_html = user_doc.get("hostel") or (user_doc.get("studzone1") or {}).get("hostel_html", "")

        has_fees = bool(fees_html and "<td" in fees_html)
        has_hostel = bool(hostel_html and len(hostel_html.strip()) > 10)

        reply = (
            f"### 🏛️ Campus Services & Fee Records\n\n"
            f"- **Semester Tuition Fees:** {'Receipts recorded on file ✅' if has_fees else 'Synced with StudZone 1'}\n"
            f"- **Hostel Accommodations:** {'Allocations verified ✅' if has_hostel else 'Campus Day Scholar / Synced'}\n\n"
            f"Visit Campus Services to view official printable fee receipts, library OPAC catalog, and student applications."
        )

        return {
            "reply": reply,
            "intent": "campus_services",
            "navigation": {"path": "/services", "label": "Open Campus Services & Receipts →"},
            "suggestions": [
                "What is my overall attendance?",
                "What classes do I have today?",
                "Take me to Services"
            ]
        }

    # 9. GENERAL / HELP / CAPABILITIES
    sample_subjs = [s.get("name") for s in subjects[:2] if s.get("name")]
    sample_subj_hint = f" (e.g., '{sample_subjs[0]}')" if sample_subjs else ""

    reply = (
        f"Hi **{first_name}**! 👋 I am **SyncBot**, your personal Student Sync Assistant for PSG Tech.\n\n"
        f"Here are things you can ask me:\n"
        f"- 📊 **Attendance:** *\"What is my overall attendance?\"* or *\"Attendance in{sample_subj_hint}\"*\n"
        f"- 🚪 **Safe Bunks:** *\"How many classes can I bunk in Cloud Computing?\"* or *\"Can I bunk tomorrow?\"*\n"
        f"- 📝 **Marks & CGPA:** *\"Show my CA marks\"* or *\"What is my CGPA?\"*\n"
        f"- 🗓️ **Timetable:** *\"What classes do I have today?\"*\n"
        f"- 🪑 **Exams:** *\"Where is my exam seating?\"*\n"
        f"- 🧭 **Navigation:** *\"Take me to attendance\"*, *\"Go to schedule\"*, *\"Open grades\"*"
    )

    return {
        "reply": reply,
        "intent": "help",
        "suggestions": [
            "What is my overall attendance?",
            "What classes do I have today?",
            "Which subjects are below 75%?",
            "What is my CGPA?"
        ]
    }
