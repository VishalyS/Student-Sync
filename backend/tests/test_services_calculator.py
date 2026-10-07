"""
backend/tests/test_services_calculator.py

Unit tests for Campus Services & Student Dossier Calculator (Phase 8).
Validates pure deterministic normalization functions across all edge cases:
- Currency parsing, commas, symbols, and malformed fee amounts
- Fee categorization and calculated vs reported total handling
- Hostel accommodation, payment transactions, day-scholar fallback
- Scholarship parsing: strictly keeping Applied vs Received distinct
- Course feedback cycle active/scheduled counts
- Student dossier extraction and sensitive field isolation
"""

import pytest
from backend.services_calculator import (
    clean_currency_value,
    categorize_fee_item,
    parse_fee_ledger,
    parse_hostel_dossier,
    parse_scholarship_records,
    parse_feedback_status,
    build_student_dossier,
    synthesize_campus_services
)


# ============================================================================
# 1. CURRENCY PARSING & CATEGORIZATION UNIT TESTS
# ============================================================================

def test_clean_currency_value_normal_and_numeric():
    assert clean_currency_value(18000) == 18000.0
    assert clean_currency_value(5375.50) == 5375.50
    assert clean_currency_value("18000") == 18000.0


def test_clean_currency_value_symbols_and_commas():
    assert clean_currency_value("₹ 18000") == 18000.0
    assert clean_currency_value("₹ 1,38,000.00") == 138000.0
    assert clean_currency_value("$ 5,200.75") == 5200.75
    assert clean_currency_value("INR 37,300") == 37300.0


def test_clean_currency_value_malformed_and_missing():
    assert clean_currency_value(None) == 0.0
    assert clean_currency_value("") == 0.0
    assert clean_currency_value("   ") == 0.0
    assert clean_currency_value("Not Applicable") == 0.0
    assert clean_currency_value("N/A") == 0.0


def test_categorize_fee_item_various():
    assert categorize_fee_item("TUITION FEES") == "Academic"
    assert categorize_fee_item("DEVELOPMENT FEES") == "Institutional"
    assert categorize_fee_item("EXAMINATION FEES") == "Examinations"
    assert categorize_fee_item("MARK SHEET COST FEE") == "Examinations"
    assert categorize_fee_item("SPECIAL & OTHER FEES") == "Institutional"
    assert categorize_fee_item("ANNA UNIVERSITY ACADEMICS ADMINISTRATION FEE") == "University"
    assert categorize_fee_item("GRADUATE ASSOCIATION FEES") == "Association"
    assert categorize_fee_item("COMPUTER APPLICATION ASSOCIATI") == "Department"
    assert categorize_fee_item("UNIVERSITY SPORTS FEES") == "Sports"
    assert categorize_fee_item("HOSTEL FEES") == "Accommodation"
    assert categorize_fee_item("UNKNOWN LEVY") == "General"


# ============================================================================
# 2. FEE LEDGER PARSER UNIT TESTS
# ============================================================================

def test_parse_fee_ledger_normal_records():
    raw_items = [
        {"fee_type": "TUITION FEES", "amount": "₹ 18000"},
        {"fee_type": "DEVELOPMENT FEES", "amount": "₹ 5000"},
        {"fee_type": "EXAMINATION FEES", "amount": "₹ 5200"},
        {"fee_type": "TOTAL", "amount": "₹ 28200"}
    ]
    res = parse_fee_ledger("Active / Available", raw_items)
    assert res["status"] == "Active / Available"
    assert res["item_count"] == 3
    assert res["total_amount"] == 28200.0
    assert res["reported_total"] == 28200.0
    assert res["breakdown_by_category"]["Academic"] == 18000.0
    assert res["breakdown_by_category"]["Institutional"] == 5000.0
    assert res["breakdown_by_category"]["Examinations"] == 5200.0


def test_parse_fee_ledger_deduplication():
    # Scraper occasionally outputs table rows twice
    raw_items = [
        {"fee_type": "TUITION FEES", "amount": "₹ 18000"},
        {"fee_type": "DEVELOPMENT FEES", "amount": "₹ 5000"},
        {"fee_type": "TOTAL", "amount": "₹ 23000"},
        {"fee_type": "TUITION FEES", "amount": "₹ 18000"},
        {"fee_type": "DEVELOPMENT FEES", "amount": "₹ 5000"},
        {"fee_type": "TOTAL", "amount": "₹ 23000"}
    ]
    res = parse_fee_ledger("Active / Available", raw_items)
    assert res["item_count"] == 2
    assert res["total_amount"] == 23000.0
    assert res["reported_total"] == 23000.0


def test_parse_fee_ledger_empty_and_missing():
    res = parse_fee_ledger(None, None)
    assert res["status"] == "No Records Available"
    assert res["item_count"] == 0
    assert res["total_amount"] == 0.0
    assert res["items"] == []

    res2 = parse_fee_ledger("Fees Cleared", [])
    assert res2["status"] == "Fees Cleared"
    assert res2["total_amount"] == 0.0


def test_parse_fee_ledger_malformed_amounts():
    raw_items = [
        {"fee_type": "LIBRARY FEE", "amount": "Pending Verification"},
        {"fee_type": "LAB CHARGES", "amount": "Free"},
        {"fee_type": "TUITION", "amount": "₹ 12,500.00"}
    ]
    res = parse_fee_ledger("Active", raw_items)
    assert res["item_count"] == 3
    assert res["total_amount"] == 12500.0
    assert res["items"][0]["amount"] == 0.0
    assert res["items"][1]["amount"] == 0.0
    assert res["items"][2]["amount"] == 12500.0


# ============================================================================
# 3. HOSTEL & ACCOMMODATION PARSER UNIT TESTS
# ============================================================================

def test_parse_hostel_dossier_valid_hosteller():
    raw_hostel = {
        "hostel_status": "Registered / Hostel Data Available",
        "hostel_records": [
            ["1", "12/06/2026", "138000.00", "Success"]
        ],
        "hostel_html": "TxnReceipt('PSGHOS122904621140')"
    }
    profile = {
        "Resident Status": "HOSTELLER",
        "Room Number": "K519"
    }
    res = parse_hostel_dossier(raw_hostel, profile)
    assert res["is_hosteller"] is True
    assert res["resident_type"] == "Hosteller"
    assert res["room_number"] == "K519"
    assert res["payment_count"] == 1
    assert res["total_paid"] == 138000.0
    assert res["payments"][0]["receipt_id"] == "PSGHOS122904621140"
    assert res["payments"][0]["status"] == "Success"


def test_parse_hostel_dossier_day_scholar():
    raw_hostel = {
        "hostel_status": "Not Registered",
        "hostel_records": []
    }
    profile = {
        "Resident Status": "DAY SCHOLAR"
    }
    res = parse_hostel_dossier(raw_hostel, profile)
    assert res["is_hosteller"] is False
    assert res["resident_type"] == "Day Scholar"
    assert res["room_number"] == "N/A"
    assert res["payment_count"] == 0
    assert res["total_paid"] == 0.0
    assert res["payments"] == []


def test_parse_hostel_dossier_missing_data():
    res = parse_hostel_dossier(None, None)
    assert res["is_hosteller"] is False
    assert res["status"] == "Not Registered"
    assert res["payment_count"] == 0
    assert res["total_paid"] == 0.0


def test_parse_hostel_dossier_dict_format_records():
    raw_hostel = {
        "hostel_records": [
            {"receipt_id": "REC001", "date": "15/07/2026", "amount": "45,000", "status": "Paid"}
        ]
    }
    res = parse_hostel_dossier(raw_hostel, {"Resident Status": "HOSTELLER"})
    assert res["is_hosteller"] is True
    assert res["payment_count"] == 1
    assert res["total_paid"] == 45000.0
    assert res["payments"][0]["receipt_id"] == "REC001"


# ============================================================================
# 4. SCHOLARSHIP PARSER UNIT TESTS
# ============================================================================

def test_parse_scholarship_records_html_fidelity():
    raw_sch = {
        "html_apply": """
        <table><tbody>
        <tr>
            <td>2025-2026</td>
            <td>180</td>
            <td>Tamil Nadu Unorganised Workers Welfare Board</td>
            <td>Yes</td>
            <td>Not Approved</td>
            <td>6000</td>
        </tr>
        </tbody></table>
        """,
        "html_received": """
        <table><tbody>
        <tr>
            <td>2025-2026</td>
            <td>Tamil Nadu Unorganised Workers Welfare Board</td>
            <td>Yes</td>
            <td>6000</td>
        </tr>
        </tbody></table>
        """,
        "applied": [],
        "received": []
    }
    res = parse_scholarship_records(raw_sch)
    assert res["applied_count"] == 1
    assert res["received_count"] == 1
    
    app = res["applied"][0]
    assert app["year"] == "2025-2026"
    assert app["scholarship_id"] == "180"
    assert app["scheme_name"] == "Tamil Nadu Unorganised Workers Welfare Board"
    assert app["tutor_approval"] == "Yes"
    assert app["application_status"] == "Not Approved"
    assert app["amount"] == 6000.0

    rec = res["received"][0]
    assert rec["year"] == "2025-2026"
    assert rec["scheme_name"] == "Tamil Nadu Unorganised Workers Welfare Board"
    assert rec["disbursement_status"] == "Yes"
    assert rec["amount"] == 6000.0


def test_parse_scholarship_records_structured_array_fallback():
    raw_sch = {
        "applied": [
            {"name": "2024-2025", "type": "101", "status": "Merit Scholarship", "application_status": "Submitted", "amount": 10000}
        ],
        "received": [
            {"name": "2023-2024", "amount": "First Graduate Scheme", "academic_year": "Disbursed", "amount": 25000}
        ]
    }
    res = parse_scholarship_records(raw_sch)
    assert res["applied_count"] == 1
    assert res["received_count"] == 1
    assert res["applied"][0]["year"] == "2024-2025"
    assert res["applied"][0]["scholarship_id"] == "101"
    assert res["received"][0]["amount"] == 25000.0


def test_parse_scholarship_records_empty():
    res = parse_scholarship_records(None)
    assert res["applied_count"] == 0
    assert res["received_count"] == 0
    assert res["applied"] == []
    assert res["received"] == []


def test_parse_scholarship_records_applied_and_received_remain_distinct():
    # Critical test ensuring applied and received remain distinct concepts
    raw_sch = {
        "applied": [
            {"name": "2025-2026", "type": "99", "status": "Central Sector", "application_status": "Under Review"}
        ],
        "received": []
    }
    res = parse_scholarship_records(raw_sch)
    assert res["applied_count"] == 1
    assert res["received_count"] == 0
    assert len(res["applied"]) == 1
    assert len(res["received"]) == 0


# ============================================================================
# 5. COURSE FEEDBACK PARSER UNIT TESTS
# ============================================================================

def test_parse_feedback_status_not_scheduled():
    raw_fb = [
        {"type": "End Semester", "status": "Not Scheduled", "description": "Feedback is currently not scheduled."},
        {"type": "Intermediate", "status": "Not Scheduled", "description": "Feedback is currently not scheduled."}
    ]
    res = parse_feedback_status(raw_fb)
    assert res["total_cycles"] == 2
    assert res["active_count"] == 0
    assert res["cycles"][0]["is_active"] is False


def test_parse_feedback_status_active_cycle():
    raw_fb = [
        {"type": "Mid Semester Feedback", "status": "Open", "description": "Please submit before 15th."},
        {"type": "End Semester Feedback", "status": "Closed", "description": "Session ended."}
    ]
    res = parse_feedback_status(raw_fb)
    assert res["total_cycles"] == 2
    assert res["active_count"] == 1
    assert res["cycles"][0]["is_active"] is True
    assert res["cycles"][1]["is_active"] is False


def test_parse_feedback_status_empty():
    res = parse_feedback_status([])
    assert res["total_cycles"] == 0
    assert res["active_count"] == 0
    assert res["cycles"] == []


# ============================================================================
# 6. STUDENT DOSSIER BUILDER UNIT TESTS
# ============================================================================

def test_build_student_dossier_complete():
    user_doc = {
        "rollNo": "25MX232",
        "name": "VISHALY S",
        "email": "25mx232@psgtech.ac.in",
        "password": "hashed_secret_password",  # must NOT be in output
        "_id": "66d0c1e4f45123456789abcd",     # must NOT be in output
        "studzone1": {
            "profile": {
                "Institution": "PSG College of Technology",
                "Degree": "MASTER OF COMPUTER APPLICATIONS"
            },
            "scholarships": {
                "html_vallalar": """
                <table><tbody>
                <tr><th>Date of Birth</th><td>12/04/2005</td></tr>
                <tr><th>Mobile Number</th><td>9976477887</td></tr>
                <tr><th>Semester Number</th><td>3</td></tr>
                <tr><th>Admission Type</th><td>MERIT</td></tr>
                <tr><th>Resident Status</th><td>HOSTELLER</td></tr>
                <tr><th>Room Number</th><td>K519</td></tr>
                </tbody></table>
                """
            }
        }
    }
    dossier = build_student_dossier(user_doc)
    assert dossier["rollNo"] == "25MX232"
    assert dossier["name"] == "VISHALY S"
    assert dossier["email"] == "25mx232@psgtech.ac.in"
    assert dossier["institution"] == "PSG College of Technology"
    assert dossier["degree"] == "MASTER OF COMPUTER APPLICATIONS"
    assert dossier["dob"] == "12/04/2005"
    assert dossier["mobile"] == "9976477887"
    assert dossier["semester"] == 3
    assert dossier["admission_type"] == "MERIT"
    assert dossier["resident_status"] == "HOSTELLER"
    assert dossier["room_number"] == "K519"
    
    # Confirm security isolation: NO password or internal database keys
    assert "password" not in dossier
    assert "_id" not in dossier


def test_build_student_dossier_minimal():
    user_doc = {
        "rollNo": "24CS101",
        "name": "ARUN K"
    }
    dossier = build_student_dossier(user_doc)
    assert dossier["rollNo"] == "24CS101"
    assert dossier["name"] == "ARUN K"
    assert "dob" not in dossier
    assert "mobile" not in dossier
    assert "degree" not in dossier


def test_build_student_dossier_none():
    assert build_student_dossier(None) == {}
    assert build_student_dossier({}) == {}


# ============================================================================
# 7. MAIN AGGREGATOR SYNTHESIS UNIT TESTS
# ============================================================================

def test_synthesize_campus_services_aggregate_shape():
    user_doc = {
        "rollNo": "25MX232",
        "name": "VISHALY S",
        "email": "test@psgtech.ac.in",
        "studzone1": {
            "fee_status": "Active / Available",
            "fee_items": [
                {"fee_type": "TUITION FEES", "amount": "₹ 18000"}
            ],
            "hostel_status": "Registered / Hostel Data Available",
            "hostel_records": [
                ["1", "12/06/2026", "138000.00", "Success"]
            ],
            "scholarships": {
                "applied": [],
                "received": []
            },
            "feedback": [
                {"type": "End Semester", "status": "Not Scheduled"}
            ]
        }
    }
    res = synthesize_campus_services(user_doc)
    assert "student_dossier" in res
    assert "fees" in res
    assert "hostel" in res
    assert "scholarships" in res
    assert "feedback" in res
    assert "disclaimer" in res
    assert res["fees"]["total_amount"] == 18000.0
    assert res["hostel"]["is_hosteller"] is True
    assert res["feedback"]["active_count"] == 0
