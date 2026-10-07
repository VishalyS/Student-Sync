import os
import sys

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import pytest
from academic_calculator import (
    parse_numeric,
    parse_ca_component,
    determine_course_category,
    parse_ca_marks_html,
    parse_ca_marks_fallback,
    summarize_ca_marks,
    summarize_historical_results,
    simulate_projected_cgpa,
    summarize_student_academics,
    GRADE_POINT_MAP
)


def test_parse_numeric():
    assert parse_numeric("12") == 12.0
    assert parse_numeric("14.8") == 14.8
    assert parse_numeric(15) == 15.0
    assert parse_numeric("*") is None
    assert parse_numeric("") is None
    assert parse_numeric("-") is None
    assert parse_numeric(None) is None
    assert parse_numeric("abc") is None


def test_parse_ca_component_pending():
    # Asterisk must NOT be treated as zero
    comp = parse_ca_component("*", max_val=20.0, label="T2")
    assert comp["status"] == "pending"
    assert comp["numeric_value"] is None
    assert comp["raw_value"] == "*"
    assert comp["percentage"] is None


def test_parse_ca_component_not_applicable():
    comp = parse_ca_component("", max_val=20.0, label="RT")
    assert comp["status"] == "not_applicable"
    assert comp["numeric_value"] is None

    comp_dash = parse_ca_component("-", max_val=20.0, label="RT1")
    assert comp_dash["status"] == "not_applicable"


def test_parse_ca_component_entered():
    comp = parse_ca_component("12", max_val=20.0, label="T1")
    assert comp["status"] == "entered"
    assert comp["numeric_value"] == 12.0
    assert comp["percentage"] == 60.0


def test_determine_course_category():
    assert determine_course_category("23MXM4", "PROFESSIONAL ETHICS", ["A I", "A II", "Total", "Conv. Total"], 100.0) == "Mandatory/Audit"
    assert determine_course_category("23MX37", "MINI PROJECT", ["P I -G", "P I -C", "Total", "Conv. Total"], 100.0) == "Project"
    assert determine_course_category("23MX36", "CLOUD COMPUTING LABORATORY", ["T1", "T2", "Total", "Conv. Total"], 60.0) == "Laboratory"
    assert determine_course_category("23MX31", "CLOUD COMPUTING", ["T1", "T2", "RT", "Total", "AP", "PD/T", "Conv. Total"], 40.0) == "Theory"


def test_parse_ca_marks_html_all_categories():
    sample_html = """
    <table class="table">
      <tr><th>COURSE CODE</th><th>COURSE TITLE</th><th>A I</th><th>A II</th><th>Total</th><th>Conv. Total</th></tr>
      <tr><th></th><th></th><th>Max: 50</th><th>Max: 50</th><th>Max: 100</th><th>Max: 100</th></tr>
      <tr><td>23MXM4</td><td>PROFESSIONAL ETHICS</td><td>*</td><td>*</td><td></td><td>*</td></tr>
    </table>
    <table class="table">
      <tr><th>COURSE CODE</th><th>COURSE TITLE</th><th>P I -G</th><th>P I -C</th><th>Total</th><th>Conv. Total</th></tr>
      <tr><th></th><th></th><th>Max: 10</th><th>Max: 10</th><th>Max: 100</th><th>Max: 100</th></tr>
      <tr><td>23MX37</td><td>MINI PROJECT</td><td>7</td><td>8</td><td>15</td><td>*</td></tr>
    </table>
    <table class="table">
      <tr><th>COURSE CODE</th><th>COURSE TITLE</th><th>T1</th><th>T2</th><th>Total</th><th>Conv. Total</th></tr>
      <tr><th></th><th></th><th>Max: 25</th><th>Max: 25</th><th>Max: 50</th><th>Max: 60</th></tr>
      <tr><td>23MX36</td><td>CLOUD COMPUTING LABORATORY</td><td>24</td><td>*</td><td>24</td><td>*</td></tr>
    </table>
    <table class="table">
      <tr><th>COURSE CODE</th><th>COURSE TITLE</th><th>T1</th><th>T2</th><th>RT</th><th>Total</th><th>AP</th><th>PD/T</th><th>Total</th><th>Conv. Total</th></tr>
      <tr><th></th><th></th><th>Max: 20</th><th>Max: 20</th><th>Max: 20</th><th>Max: 20</th><th>Max: 15</th><th>Max: 15</th><th>Max: 50</th><th>Max: 40</th></tr>
      <tr><td>23MX31</td><td>CLOUD COMPUTING</td><td>12</td><td>*</td><td></td><td>6</td><td>*</td><td>*</td><td>6</td><td>*</td></tr>
    </table>
    """
    courses = parse_ca_marks_html(sample_html)
    assert len(courses) == 4

    # 1. Audit
    c0 = courses[0]
    assert c0["code"] == "23MXM4"
    assert c0["category"] == "Mandatory/Audit"
    assert c0["converted_total_max"] == 100.0
    assert c0["components"][0]["status"] == "pending"

    # 2. Project
    c1 = courses[1]
    assert c1["code"] == "23MX37"
    assert c1["category"] == "Project"
    assert c1["components"][0]["numeric_value"] == 7.0
    assert c1["components"][1]["numeric_value"] == 8.0

    # 3. Lab
    c2 = courses[2]
    assert c2["code"] == "23MX36"
    assert c2["category"] == "Laboratory"
    assert c2["converted_total_max"] == 60.0
    assert c2["components"][0]["numeric_value"] == 24.0

    # 4. Theory
    c3 = courses[3]
    assert c3["code"] == "23MX31"
    assert c3["category"] == "Theory"
    assert c3["converted_total_max"] == 40.0
    assert c3["components"][0]["numeric_value"] == 12.0
    assert c3["components"][1]["status"] == "pending"
    assert c3["components"][2]["status"] == "not_applicable"  # RT was empty


def test_parse_ca_marks_fallback():
    parsed_marks = [
        {
            "code": "23MX31",
            "name": "CLOUD COMPUTING",
            "marks_data": ["12", "*", "", "", "", "6", "*", "*", "6", "*"]
        }
    ]
    courses = parse_ca_marks_fallback(parsed_marks)
    assert len(courses) == 1
    c = courses[0]
    assert c["code"] == "23MX31"
    assert c["category"] == "Theory"
    assert c["entered_components"] >= 2  # 12 and 6


def test_summarize_historical_results_math():
    results = [
        {"sem": "2", "code": "23MX21", "title": "SOFTWARE ENGINEERING", "credits": "4", "grade": "A", "grade_point": 8.0, "result_status": "Pass"},
        {"sem": "2", "code": "23MX22", "title": "ALGORITHMS", "credits": "4", "grade": "B+", "grade_point": 7.0, "result_status": "Pass"},
        {"sem": "2", "code": "23MX27", "title": "MOBILE APP", "credits": "2", "grade": "A+", "grade_point": 9.0, "result_status": "Pass"}
    ]
    # Total credits = 4 + 4 + 2 = 10
    # Total grade points = (4*8) + (4*7) + (2*9) = 32 + 28 + 18 = 78
    # GPA = 78 / 10 = 7.80
    summary = summarize_historical_results(results, stored_cgpa=7.80)
    assert summary["total_credits"] == 10.0
    assert summary["total_grade_points"] == 78.0
    assert summary["calculated_cgpa"] == 7.80
    assert summary["cgpa_verified"] is True
    assert summary["grade_distribution"] == {"A": 1, "B+": 1, "A+": 1}
    assert summary["arrears_count"] == 0
    assert summary["all_cleared"] is True


def test_summarize_historical_results_with_arrears():
    results = [
        {"sem": "1", "code": "23MX11", "title": "MATH", "credits": "4", "grade": "F", "grade_point": 0.0, "result_status": "Pass"},
        {"sem": "1", "code": "23MX15", "title": "WEB TECH", "credits": "3", "grade": "C+", "grade_point": 6.0, "result_status": "Pass"}
    ]
    # Credits = 7, Points = 0 + 18 = 18 -> CGPA = 18 / 7 = 2.57
    summary = summarize_historical_results(results, stored_cgpa=2.57)
    assert summary["total_credits"] == 7.0
    assert summary["calculated_cgpa"] == 2.57
    assert summary["arrears_count"] == 1
    assert summary["all_cleared"] is False


def test_simulate_projected_cgpa_single_course():
    # Base: 24 credits, CGPA 7.96 -> points = 191.04
    # Sim: 1 course, 4 credits, Grade 'O' (GP 10.0) -> points = 40
    # Total credits = 28, Total points = 231.04
    # Projected CGPA = 231.04 / 28 = 8.2514 -> 8.25
    sim_res = simulate_projected_cgpa(
        base_credits=24.0,
        base_cgpa=7.96,
        simulated_courses=[
            {"course_name": "Deep Learning", "credits": 4.0, "grade": "O"}
        ]
    )
    assert sim_res["base_credits"] == 24.0
    assert sim_res["simulated_credits"] == 4.0
    assert sim_res["total_credits"] == 28.0
    assert sim_res["projected_cgpa"] == 8.25
    assert sim_res["cgpa_delta"] == 0.29
    assert len(sim_res["courses_simulated"]) == 1


def test_simulate_projected_cgpa_multiple_courses():
    sim_res = simulate_projected_cgpa(
        base_credits=24.0,
        base_cgpa=8.0,
        simulated_courses=[
            {"course_name": "Course 1", "credits": 4.0, "grade": "A+"},  # 4 * 9 = 36
            {"course_name": "Course 2", "credits": 4.0, "grade": "A"},   # 4 * 8 = 32
            {"course_name": "Course 3", "credits": 2.0, "grade": "B+"}   # 2 * 7 = 14
        ]
    )
    # Base points = 24 * 8.0 = 192.0
    # Sim points = 36 + 32 + 14 = 82.0
    # Total points = 274.0, Total credits = 34.0
    # Projected = 274.0 / 34.0 = 8.0588 -> 8.06
    assert sim_res["simulated_credits"] == 10.0
    assert sim_res["total_credits"] == 34.0
    assert sim_res["projected_cgpa"] == 8.06
    assert sim_res["cgpa_delta"] == 0.06


def test_simulate_projected_cgpa_validation():
    with pytest.raises(ValueError):
        simulate_projected_cgpa(-5, 8.0, [])

    with pytest.raises(ValueError):
        simulate_projected_cgpa(24.0, 11.5, [])

    # Ignores invalid grade strings or zero credits safely
    res = simulate_projected_cgpa(24.0, 8.0, [
        {"credits": 0, "grade": "O"},
        {"credits": 4.0, "grade": "INVALID_GRADE"}
    ])
    assert res["simulated_credits"] == 0.0
    assert res["projected_cgpa"] == 8.0


def test_summarize_student_academics_end_to_end():
    mock_user = {
        "rollNo": "25MX232",
        "name": "Vishal",
        "cgpa": 7.96,
        "studzone1": {
            "ca_marks_html": """
            <table>
              <tr><th>COURSE CODE</th><th>COURSE TITLE</th><th>T1</th><th>T2</th><th>Total</th><th>Conv. Total</th></tr>
              <tr><th></th><th></th><th>Max: 20</th><th>Max: 20</th><th>Max: 50</th><th>Max: 40</th></tr>
              <tr><td>23MX31</td><td>CLOUD COMPUTING</td><td>12</td><td>*</td><td>12</td><td>*</td></tr>
            </table>
            """
        },
        "studzone2": {
            "parsed_results": [
                {"sem": "2", "code": "23MX21", "title": "SOFTWARE ENGINEERING", "credits": "4", "grade": "A", "grade_point": 8.0, "result_status": "Pass"}
            ]
        }
    }
    summary = summarize_student_academics(mock_user)
    assert summary["rollNo"] == "25MX232"
    assert summary["base_credits"] == 4.0
    assert summary["base_cgpa"] == 7.96
    assert len(summary["ca_marks"]["courses"]) == 1
    assert len(summary["results"]["courses"]) == 1
