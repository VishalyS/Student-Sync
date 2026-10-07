"""
backend/academic_calculator.py

Continuous Assessment (CA) and Academic Performance Analytics Engine
for Student Sync.

Supports:
1. Multi-category CA marks parsing (Theory, Laboratory, Project, Mandatory/Audit)
2. Handling of pending ("*"), not-applicable (""), and numeric marks without treating "*" as 0
3. Historical Semester Results analytics, credit weights, grade distribution, and SGPA/CGPA verification
4. Interactive What-If CGPA Simulator (100% in-memory mathematical model)

CRITICAL RULE:
Theory courses at PSG College of Technology follow Relative Grading.
This engine strictly avoids hardcoding static numerical thresholds (e.g. O >= 90)
or automated exam target mark predictions.
"""

import re
from typing import Dict, List, Optional, Any, Tuple
from bs4 import BeautifulSoup


# Verified PSG College of Technology Letter Grade to Grade Point mapping
GRADE_POINT_MAP = {
    'O': 10.0,
    'A+': 9.0,
    'A': 8.0,
    'B+': 7.0,
    'B': 6.5,
    'C+': 6.0,
    'C': 5.0,
    'RA': 0.0,
    'F': 0.0,
    'W': 0.0,
    'SA': 0.0
}


def parse_numeric(val: Any) -> Optional[float]:
    """Safely parses a string or number to float. Returns None if invalid or pending."""
    if val is None:
        return None
    s = str(val).strip()
    if not s or s == '*' or s == '-' or s == 'None':
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def parse_ca_component(val: Any, max_val: Optional[float] = None, label: str = "") -> Dict[str, Any]:
    """
    Parses a single CA component cell.
    - '*' indicates pending / not entered yet (NOT treated as zero).
    - '' or '-' indicates not applicable (e.g. Retest when not attempted).
    - Numeric indicates entered score.
    """
    raw_str = str(val).strip() if val is not None else ""
    num_val = parse_numeric(raw_str)

    if raw_str == "*":
        status = "pending"
    elif not raw_str or raw_str == "-":
        status = "not_applicable"
    elif num_val is not None:
        status = "entered"
    else:
        status = "pending"

    pct = None
    if num_val is not None and max_val is not None and max_val > 0:
        pct = round((num_val / max_val) * 100.0, 2)

    return {
        "label": label,
        "raw_value": raw_str,
        "numeric_value": num_val,
        "max_marks": max_val,
        "status": status,
        "percentage": pct
    }


def determine_course_category(code: str, name: str, headers: List[str], conv_max: Optional[float]) -> str:
    """Classifies a course into Theory, Laboratory, Project, or Mandatory/Audit."""
    name_upper = (name or "").upper()
    headers_str = " ".join(headers).upper()

    if "ETHICS" in name_upper or "MANDATORY" in name_upper or "AUDIT" in name_upper or ("A I" in headers_str and "A II" in headers_str):
        return "Mandatory/Audit"
    if "PROJECT" in name_upper or "PRE & VV" in headers_str or "P I" in headers_str:
        return "Project"
    if "LABORATORY" in name_upper or "LAB" in name_upper or (conv_max == 60.0):
        return "Laboratory"
    if conv_max == 40.0 or "T1" in headers_str or "AP" in headers_str:
        return "Theory"

    return "Theory"


def _clean_max_header(max_str: str) -> Optional[float]:
    """Extracts numeric max value from strings like 'Max: 20' or '20'."""
    if not max_str:
        return None
    m = re.search(r'([0-9]+(?:\.[0-9]+)?)', str(max_str))
    if m:
        try:
            return float(m.group(1))
        except (ValueError, TypeError):
            return None
    return None


def parse_ca_marks_html(html_str: str) -> List[Dict[str, Any]]:
    """
    High-fidelity parser for StudZone 1 CA Marks HTML table.
    Preserves exact column headers, subheader max marks, and component values.
    """
    if not html_str:
        return []

    try:
        soup = BeautifulSoup(html_str, "html.parser")
    except Exception:
        return []

    tables = soup.find_all("table")
    courses = []

    for tbl in tables:
        rows = tbl.find_all("tr")
        if not rows:
            continue

        headers = []
        max_headers = []
        data_rows = []

        for r in rows:
            ths = r.find_all("th")
            tds = r.find_all("td")
            if ths and not data_rows:
                txts = [th.get_text(strip=True) for th in ths]
                if any("Max:" in t for t in txts):
                    max_headers = txts
                else:
                    headers = txts
            elif tds:
                data_rows.append([td.get_text(strip=True) for td in tds])

        if not headers or len(headers) < 3 or not data_rows:
            continue

        # Map component headers and max values (skipping COURSE CODE, COURSE TITLE)
        comp_headers = headers[2:]
        if len(max_headers) == len(headers):
            clean_max_list = max_headers[2:]
        else:
            clean_max_list = max_headers

        comp_maxes = []
        for i in range(len(comp_headers)):
            if i < len(clean_max_list):
                comp_maxes.append(_clean_max_header(clean_max_list[i]))
            else:
                comp_maxes.append(None)

        conv_max = comp_maxes[-1] if comp_maxes else None

        for dr in data_rows:
            if len(dr) < 2:
                continue
            code = dr[0]
            name = dr[1]
            raw_comps = dr[2:]

            category = determine_course_category(code, name, comp_headers, conv_max)

            components = []
            entered_count = 0
            pending_count = 0

            for idx, h in enumerate(comp_headers):
                val = raw_comps[idx] if idx < len(raw_comps) else ""
                max_val = comp_maxes[idx] if idx < len(comp_maxes) else None
                comp = parse_ca_component(val, max_val=max_val, label=h)
                components.append(comp)

                if comp["status"] == "entered":
                    entered_count += 1
                elif comp["status"] == "pending":
                    pending_count += 1

            conv_comp = components[-1] if components else None
            conv_total = conv_comp["numeric_value"] if conv_comp and conv_comp["status"] == "entered" else None

            status_str = "In Progress"
            if pending_count == 0 and entered_count > 0:
                status_str = "Completed"
            elif entered_count == 0 and pending_count > 0:
                status_str = "Awaiting Marks"

            courses.append({
                "code": code,
                "name": name,
                "category": category,
                "components": components,
                "entered_components": entered_count,
                "pending_components": pending_count,
                "converted_total_max": conv_max,
                "converted_total": conv_total,
                "status": status_str
            })

    return courses


def parse_ca_marks_fallback(parsed_marks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Fallback parser for studzone1.parsed_marks when raw HTML is not provided.
    Reconstructs components from marks_data and course metadata.
    """
    if not parsed_marks or not isinstance(parsed_marks, list):
        return []

    courses = []
    for item in parsed_marks:
        if not isinstance(item, dict):
            continue
        code = item.get("code", "")
        name = item.get("name", "")
        marks_data = item.get("marks_data", [])

        # Heuristic detection based on length and course name
        name_upper = (name or "").upper()
        if "ETHICS" in name_upper or len(marks_data) == 4 and "ETHICS" in name_upper:
            category = "Mandatory/Audit"
            labels = ["A I", "A II", "Total", "Conv. Total"]
            maxes = [50.0, 50.0, 100.0, 100.0]
        elif "PROJECT" in name_upper or len(marks_data) == 8:
            category = "Project"
            labels = ["P I -G", "P I -C", "P II -G", "P II -C", "PRE & VV G", "PRE & VV C", "Total", "Conv. Total"]
            maxes = [10.0, 10.0, 15.0, 15.0, 25.0, 25.0, 100.0, 100.0]
        elif "LABORATORY" in name_upper or "LAB" in name_upper or len(marks_data) == 4:
            category = "Laboratory"
            labels = ["T1", "T2", "Total", "Conv. Total"]
            maxes = [25.0, 25.0, 50.0, 60.0]
        else:
            category = "Theory"
            labels = ["T1", "T2", "RT", "RT1", "RT2", "Total", "AP", "PD/T", "Total", "Conv. Total"]
            maxes = [20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 15.0, 15.0, 50.0, 40.0]

        components = []
        entered_count = 0
        pending_count = 0

        # Use marks_data if available, otherwise ca1, ca2, ca3, total
        if marks_data and len(marks_data) == len(labels):
            vals = marks_data
        else:
            vals = [item.get("ca1", ""), item.get("ca2", ""), item.get("ca3", ""), item.get("total", "")]
            labels = labels[:len(vals)]
            maxes = maxes[:len(vals)]

        for idx, lbl in enumerate(labels):
            val = vals[idx] if idx < len(vals) else ""
            m_val = maxes[idx] if idx < len(maxes) else None
            comp = parse_ca_component(val, max_val=m_val, label=lbl)
            components.append(comp)

            if comp["status"] == "entered":
                entered_count += 1
            elif comp["status"] == "pending":
                pending_count += 1

        conv_max = maxes[-1] if maxes else None
        conv_comp = components[-1] if components else None
        conv_total = conv_comp["numeric_value"] if conv_comp and conv_comp["status"] == "entered" else None

        courses.append({
            "code": code,
            "name": name,
            "category": category,
            "components": components,
            "entered_components": entered_count,
            "pending_components": pending_count,
            "converted_total_max": conv_max,
            "converted_total": conv_total,
            "status": "In Progress" if pending_count > 0 else "Completed"
        })

    return courses


def summarize_ca_marks(studzone1_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Summarizes CA marks using ca_marks_html if available, falling back to parsed_marks.
    """
    if not studzone1_data:
        return {"courses": [], "total_courses": 0, "entered_evaluations": 0, "pending_evaluations": 0}

    html = studzone1_data.get("ca_marks_html", "")
    parsed_marks = studzone1_data.get("parsed_marks", [])

    courses = []
    if html:
        courses = parse_ca_marks_html(html)

    if not courses and parsed_marks:
        courses = parse_ca_marks_fallback(parsed_marks)

    tot_entered = sum(c.get("entered_components", 0) for c in courses)
    tot_pending = sum(c.get("pending_components", 0) for c in courses)

    return {
        "courses": courses,
        "total_courses": len(courses),
        "entered_evaluations": tot_entered,
        "pending_evaluations": tot_pending,
        "active_semester_notice": "CA marks are synchronized from StudZone 1. Asterisks (*) represent pending evaluations."
    }


def summarize_historical_results(results_list: Optional[List[Dict[str, Any]]], stored_cgpa: Optional[float] = None) -> Dict[str, Any]:
    """
    Analyzes verified results from studzone2.parsed_results.
    Calculates total credits, weighted GPA, grade distribution, and semester groups.
    """
    if not results_list or not isinstance(results_list, list):
        return {
            "courses": [],
            "total_credits": 0.0,
            "total_grade_points": 0.0,
            "calculated_cgpa": 0.0,
            "stored_cgpa": stored_cgpa,
            "grade_distribution": {},
            "semester_breakdown": [],
            "arrears_count": 0,
            "all_cleared": True
        }

    courses = []
    tot_credits = 0.0
    tot_points = 0.0
    grade_dist: Dict[str, int] = {}
    sem_groups: Dict[str, List[Dict[str, Any]]] = {}
    arrears = 0

    for r in results_list:
        if not isinstance(r, dict):
            continue

        c_str = r.get("credits", "0")
        try:
            credits = float(c_str)
        except (ValueError, TypeError):
            credits = 0.0

        gp_raw = r.get("grade_point")
        try:
            gp = float(gp_raw) if gp_raw is not None else 0.0
        except (ValueError, TypeError):
            gp = 0.0

        grade = str(r.get("grade", "")).strip().upper()
        sem = str(r.get("sem", "")).strip() or "General"
        status = str(r.get("result_status", "Pass")).strip()

        points = credits * gp
        tot_credits += credits
        tot_points += points

        if grade:
            grade_dist[grade] = grade_dist.get(grade, 0) + 1

        if gp == 0.0 or status.lower() != "pass":
            arrears += 1

        course_entry = {
            "sem": sem,
            "code": r.get("code", ""),
            "title": r.get("title", ""),
            "credits": credits,
            "grade": grade,
            "grade_point": gp,
            "points_earned": round(points, 2),
            "result_status": status
        }
        courses.append(course_entry)

        if sem not in sem_groups:
            sem_groups[sem] = []
        sem_groups[sem].append(course_entry)

    calc_cgpa = round(tot_points / tot_credits, 2) if tot_credits > 0 else 0.0

    # Semester breakdown
    sem_breakdown = []
    for sem_id, sem_courses in sem_groups.items():
        s_credits = sum(c["credits"] for c in sem_courses)
        s_points = sum(c["points_earned"] for c in sem_courses)
        sgpa = round(s_points / s_credits, 2) if s_credits > 0 else 0.0
        sem_breakdown.append({
            "semester": sem_id,
            "courses_count": len(sem_courses),
            "credits": s_credits,
            "points": round(s_points, 2),
            "sgpa": sgpa
        })

    return {
        "courses": courses,
        "total_credits": tot_credits,
        "total_grade_points": round(tot_points, 2),
        "calculated_cgpa": calc_cgpa,
        "stored_cgpa": stored_cgpa,
        "cgpa_verified": (stored_cgpa is not None and abs(calc_cgpa - float(stored_cgpa)) < 0.02),
        "grade_distribution": grade_dist,
        "semester_breakdown": sem_breakdown,
        "arrears_count": arrears,
        "all_cleared": (arrears == 0)
    }


def simulate_projected_cgpa(
    base_credits: float,
    base_cgpa: float,
    simulated_courses: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    In-memory What-If CGPA Simulator.
    Calculates projected CGPA when hypothetical courses and grades are added.

    Formula:
    Projected CGPA = (base_credits * base_cgpa + sum(sim_credits * sim_grade_point))
                    / (base_credits + sim_credits)

    Strictly does not write or modify database records.
    """
    try:
        b_credits = float(base_credits)
        b_cgpa = float(base_cgpa)
    except (ValueError, TypeError):
        raise ValueError("base_credits and base_cgpa must be valid numbers")

    if b_credits < 0 or b_cgpa < 0 or b_cgpa > 10.0:
        raise ValueError("base_credits and base_cgpa must be non-negative and <= 10.0")

    sim_credits_tot = 0.0
    sim_points_tot = 0.0
    processed_sims = []

    for item in simulated_courses:
        if not isinstance(item, dict):
            continue

        c_val = item.get("credits")
        try:
            credits = float(c_val)
        except (ValueError, TypeError):
            continue

        if credits <= 0:
            continue

        grade = str(item.get("grade", "")).strip().upper()
        if grade not in GRADE_POINT_MAP:
            continue

        gp = GRADE_POINT_MAP[grade]
        pts = credits * gp

        sim_credits_tot += credits
        sim_points_tot += pts

        processed_sims.append({
            "course_name": str(item.get("course_name") or item.get("code") or f"Course {len(processed_sims)+1}").strip(),
            "credits": credits,
            "grade": grade,
            "grade_point": gp,
            "points": round(pts, 2)
        })

    tot_credits = b_credits + sim_credits_tot
    if tot_credits > 0:
        tot_points = (b_credits * b_cgpa) + sim_points_tot
        proj_cgpa = round(tot_points / tot_credits, 2)
    else:
        proj_cgpa = b_cgpa

    delta = round(proj_cgpa - b_cgpa, 2)

    return {
        "base_credits": b_credits,
        "base_cgpa": b_cgpa,
        "simulated_credits": sim_credits_tot,
        "total_credits": tot_credits,
        "projected_cgpa": proj_cgpa,
        "cgpa_delta": delta,
        "courses_simulated": processed_sims,
        "disclaimer": "This is an in-memory mathematical what-if model. Official academic grades and database records remain unmodified."
    }


def summarize_student_academics(user_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Unified academic summary for authenticated student.
    Combines CA marks, historical results, and verified baseline metrics.
    """
    if not user_doc or not isinstance(user_doc, dict):
        return {}

    roll_no = user_doc.get("rollNo", "")
    stored_cgpa = user_doc.get("cgpa")
    try:
        stored_cgpa = float(stored_cgpa) if stored_cgpa is not None else None
    except (ValueError, TypeError):
        stored_cgpa = None

    sz1 = user_doc.get("studzone1", {})
    sz2 = user_doc.get("studzone2", {})

    ca_summary = summarize_ca_marks(sz1)
    results_summary = summarize_historical_results(sz2.get("parsed_results", []), stored_cgpa=stored_cgpa)

    # Base credits for simulation defaults: use results total credits if verified, else 0.0
    base_credits = results_summary.get("total_credits", 0.0)
    base_cgpa = stored_cgpa if stored_cgpa is not None else results_summary.get("calculated_cgpa", 0.0)

    return {
        "rollNo": roll_no,
        "name": user_doc.get("name", ""),
        "stored_cgpa": stored_cgpa,
        "base_credits": base_credits,
        "base_cgpa": base_cgpa,
        "ca_marks": ca_summary,
        "results": results_summary,
        "grade_point_map": GRADE_POINT_MAP
    }
