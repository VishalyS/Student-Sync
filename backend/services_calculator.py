"""
backend/services_calculator.py

Campus Services & Student Dossier Intelligence Engine for Student Sync (Phase 8).

Pure deterministic parser and normalization functions for:
1. Student Identity Dossier
2. Institutional Fee Ledger
3. Hostel & Accommodation Records
4. Scholarships (Applied & Received/Disbursed kept strictly distinct)
5. Institutional Course Feedback Cycles

STRICT ARCHITECTURAL RULES:
1. Pure functions: 100% in-memory calculations, zero database writes.
2. Read-only: Never mutates incoming parameters or persistent state.
3. No speculative guesswork: Preserves actual source values; never invents
   payment statuses, scholarship approvals, room numbers, or fee amounts.
4. Safe missing/malformed data handling with graceful fallbacks.
"""

import re
from typing import Dict, List, Optional, Any, Union
from bs4 import BeautifulSoup


def clean_currency_value(val: Any) -> float:
    """
    Normalizes currency representations into a clean float.
    Handles numeric strings, commas, currency symbols (₹, $, INR), and whitespace.
    Returns 0.0 for empty, missing, or malformed inputs.
    """
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    
    val_str = str(val).strip()
    if not val_str:
        return 0.0
        
    # Strip everything except digits and decimal point
    cleaned = re.sub(r'[^\d.]', '', val_str)
    if not cleaned:
        return 0.0
        
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def categorize_fee_item(fee_type: str) -> str:
    """
    Categorizes fee ledger line items into standard institutional categories.
    """
    ft_upper = (fee_type or "").upper()
    if "TUITION" in ft_upper:
        return "Academic"
    elif "DEVELOPMENT" in ft_upper:
        return "Institutional"
    elif "EXAMINATION" in ft_upper or "MARK SHEET" in ft_upper:
        return "Examinations"
    elif "SPECIAL" in ft_upper or "OTHER" in ft_upper:
        return "Institutional"
    elif "ANNA UNIVERSITY" in ft_upper or "UNIVERSITY" in ft_upper and "SPORTS" not in ft_upper:
        return "University"
    elif "ASSOCIATION" in ft_upper and "COMPUTER" not in ft_upper:
        return "Association"
    elif "COMPUTER APPLICATION" in ft_upper:
        return "Department"
    elif "SPORTS" in ft_upper:
        return "Sports"
    elif "HOSTEL" in ft_upper:
        return "Accommodation"
    elif "LIBRARY" in ft_upper:
        return "Library"
    return "General"


def parse_fee_ledger(
    raw_fees: Any,
    raw_items: Optional[List[Dict[str, Any]]]
) -> Dict[str, Any]:
    """
    Parses and normalizes the institutional fee ledger.
    - Normalizes currency amounts
    - Deduplicates repeated line items if present in scraper output
    - Categorizes fee items
    - Extracts reported total and computes verified sum from items
    - Preserves actual source fee status
    """
    # 1. Determine status
    status = "Active / Available"
    if isinstance(raw_fees, str) and raw_fees.strip():
        status = raw_fees.strip()
    elif isinstance(raw_fees, dict) and raw_fees.get("status"):
        status = str(raw_fees.get("status")).strip()

    if not raw_items or not isinstance(raw_items, list):
        return {
            "status": status if status != "Active / Available" else "No Records Available",
            "total_amount": 0.0,
            "reported_total": 0.0,
            "currency": "INR",
            "item_count": 0,
            "items": [],
            "breakdown_by_category": {}
        }

    # 2. Process items, handling deduplication and TOTAL row
    seen_keys = set()
    parsed_items = []
    reported_total: Optional[float] = None

    for item in raw_items:
        if not isinstance(item, dict):
            continue

        fee_name = str(item.get("fee_type") or item.get("name") or "").strip()
        if not fee_name:
            continue

        raw_amt = item.get("amount")
        amount = clean_currency_value(raw_amt)

        # Check if this row is the summary TOTAL row
        if fee_name.upper() == "TOTAL":
            if reported_total is None or reported_total == 0.0:
                reported_total = amount
            continue

        # Deduplication key: (name, amount)
        dedup_key = (fee_name.upper(), amount)
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        category = categorize_fee_item(fee_name)
        parsed_items.append({
            "name": fee_name,
            "amount": amount,
            "raw_amount": str(raw_amt) if raw_amt is not None else "",
            "category": category,
            "details": item.get("details", [])
        })

    # 3. Calculate verified sum
    calculated_total = sum(item["amount"] for item in parsed_items)

    # 4. Compute breakdown by category
    category_totals: Dict[str, float] = {}
    for item in parsed_items:
        cat = item["category"]
        category_totals[cat] = category_totals.get(cat, 0.0) + item["amount"]

    # Final total priority: calculated sum if items exist, else reported total
    final_total = calculated_total if parsed_items else (reported_total or 0.0)

    return {
        "status": status,
        "total_amount": round(final_total, 2),
        "reported_total": round(reported_total, 2) if reported_total is not None else round(final_total, 2),
        "currency": "INR",
        "item_count": len(parsed_items),
        "items": parsed_items,
        "breakdown_by_category": {k: round(v, 2) for k, v in category_totals.items()}
    }


def parse_hostel_dossier(
    raw_hostel: Any,
    profile: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Parses hostel accommodation records and residency status.
    - Handles hosteller vs. day-scholar status
    - Extracts room allocation
    - Normalizes payment transaction history (receipt ID, date, amount, status)
    - Safely handles empty states
    """
    profile = profile or {}
    
    # 1. Determine resident status and room number from profile
    resident_status = str(profile.get("Resident Status") or profile.get("resident_status") or "").strip().upper()
    room_number = str(profile.get("Room Number") or profile.get("room_number") or "").strip()

    # 2. Extract records and status from raw_hostel
    hostel_status = "Not Registered"
    hostel_records_list: List[Any] = []
    hostel_html = ""

    if isinstance(raw_hostel, dict):
        hostel_status = raw_hostel.get("hostel_status") or raw_hostel.get("status") or hostel_status
        hostel_records_list = raw_hostel.get("hostel_records") or raw_hostel.get("records") or []
        hostel_html = raw_hostel.get("hostel_html") or ""
    elif isinstance(raw_hostel, list):
        hostel_records_list = raw_hostel
        hostel_status = "Registered / Hostel Data Available"
    elif isinstance(raw_hostel, str) and raw_hostel.strip():
        hostel_status = raw_hostel.strip()

    is_not_registered = "NOT REGISTERED" in hostel_status.upper() or "DAY SCHOLAR" in resident_status
    if resident_status == "HOSTELLER":
        is_hosteller = True
    elif is_not_registered:
        is_hosteller = False
    else:
        is_hosteller = bool(hostel_records_list) or ("REGISTERED" in hostel_status.upper())

    # 3. Parse receipt IDs from hostel_html if available
    receipt_ids: List[str] = []
    if hostel_html:
        try:
            receipt_matches = re.findall(r"TxnReceipt\(['\"]([^'\"]+)['\"]\)", hostel_html)
            receipt_ids = receipt_matches
        except Exception:
            receipt_ids = []

    # 4. Parse payment records
    payments: List[Dict[str, Any]] = []
    for idx, rec in enumerate(hostel_records_list):
        if isinstance(rec, (list, tuple)) and len(rec) >= 4:
            s_no = str(rec[0]).strip()
            txn_date = str(rec[1]).strip()
            txn_amt = clean_currency_value(rec[2])
            txn_status = str(rec[3]).strip()
            
            # Use extracted receipt ID if index matches, else fallback to s_no
            receipt_id = receipt_ids[idx] if idx < len(receipt_ids) else s_no

            payments.append({
                "receipt_id": receipt_id,
                "s_no": s_no,
                "date": txn_date,
                "amount": txn_amt,
                "status": txn_status
            })
        elif isinstance(rec, dict):
            payments.append({
                "receipt_id": str(rec.get("receipt_id") or rec.get("s_no") or idx + 1),
                "s_no": str(rec.get("s_no") or idx + 1),
                "date": str(rec.get("date") or rec.get("txn_date") or "").strip(),
                "amount": clean_currency_value(rec.get("amount") or rec.get("txn_amount")),
                "status": str(rec.get("status") or "").strip()
            })

    total_paid = sum(p["amount"] for p in payments)

    return {
        "status": hostel_status,
        "is_hosteller": is_hosteller,
        "resident_type": "Hosteller" if is_hosteller else "Day Scholar",
        "room_number": room_number if room_number else ("N/A" if not is_hosteller else "Not Assigned"),
        "payment_count": len(payments),
        "total_paid": round(total_paid, 2),
        "payments": payments
    }


def parse_scholarship_records(
    raw_scholarships: Any
) -> Dict[str, Any]:
    """
    Parses scholarship schemes, keeping Applied records and Received/Disbursed records
    STRICTLY SEPARATE.
    Preserves actual source scheme names, academic years, and statuses without
    inferring eligibility or predicting approval.
    """
    if not raw_scholarships or not isinstance(raw_scholarships, dict):
        return {
            "applied_count": 0,
            "received_count": 0,
            "applied": [],
            "received": []
        }

    applied_list: List[Dict[str, Any]] = []
    received_list: List[Dict[str, Any]] = []

    # 1. Parse Applied Scholarships (prefer html_apply if present for full tabular fidelity)
    html_apply = raw_scholarships.get("html_apply", "")
    parsed_from_html_apply = False

    if html_apply and isinstance(html_apply, str):
        try:
            soup = BeautifulSoup(html_apply, "html.parser")
            tbody = soup.find("tbody")
            if tbody:
                for tr in tbody.find_all("tr"):
                    tds = [td.get_text(strip=True) for td in tr.find_all("td")]
                    if len(tds) >= 6:
                        # Columns: Year, Scholarship Id (hidden), Name, Tutor, Received/Status, Amount
                        yr = tds[0]
                        s_id = tds[1]
                        s_name = tds[2]
                        tutor = tds[3]
                        app_status = tds[4]
                        amt = clean_currency_value(tds[5])
                        applied_list.append({
                            "year": yr,
                            "scholarship_id": s_id,
                            "scheme_name": s_name,
                            "tutor_approval": tutor,
                            "application_status": app_status,
                            "amount": amt
                        })
                        parsed_from_html_apply = True
        except Exception:
            parsed_from_html_apply = False

    # Fallback to structured dict array if HTML parsing did not extract items
    if not parsed_from_html_apply:
        raw_applied = raw_scholarships.get("applied", [])
        if isinstance(raw_applied, list):
            for item in raw_applied:
                if isinstance(item, dict):
                    applied_list.append({
                        "year": str(item.get("name") or item.get("year") or "").strip(),
                        "scholarship_id": str(item.get("type") or item.get("scholarship_id") or "").strip(),
                        "scheme_name": str(item.get("status") or item.get("scheme_name") or item.get("name") or "").strip(),
                        "tutor_approval": str(item.get("tutor_approval") or "N/A").strip(),
                        "application_status": str(item.get("application_status") or item.get("status") or "Applied").strip(),
                        "amount": clean_currency_value(item.get("amount", 0))
                    })

    # 2. Parse Received / Disbursed Scholarships (prefer html_received if present)
    html_received = raw_scholarships.get("html_received", "")
    parsed_from_html_rec = False

    if html_received and isinstance(html_received, str):
        try:
            soup = BeautifulSoup(html_received, "html.parser")
            tbody = soup.find("tbody")
            if tbody:
                for tr in tbody.find_all("tr"):
                    tds = [td.get_text(strip=True) for td in tr.find_all("td")]
                    if len(tds) >= 4:
                        # Columns: Year, Scholarship Name, Received, Amount
                        yr = tds[0]
                        s_name = tds[1]
                        rec_status = tds[2]
                        amt = clean_currency_value(tds[3])
                        received_list.append({
                            "year": yr,
                            "scheme_name": s_name,
                            "disbursement_status": rec_status,
                            "amount": amt
                        })
                        parsed_from_html_rec = True
        except Exception:
            parsed_from_html_rec = False

    # Fallback to structured dict array if HTML parsing did not extract items
    if not parsed_from_html_rec:
        raw_received = raw_scholarships.get("received", [])
        if isinstance(raw_received, list):
            for item in raw_received:
                if isinstance(item, dict):
                    received_list.append({
                        "year": str(item.get("name") or item.get("year") or "").strip(),
                        "scheme_name": str(item.get("amount") or item.get("scheme_name") or item.get("name") or "").strip(),
                        "disbursement_status": str(item.get("academic_year") or item.get("disbursement_status") or "Received").strip(),
                        "amount": clean_currency_value(item.get("amount", 0))
                    })

    return {
        "applied_count": len(applied_list),
        "received_count": len(received_list),
        "applied": applied_list,
        "received": received_list
    }


def parse_feedback_status(
    raw_feedback: Any
) -> Dict[str, Any]:
    """
    Parses course and institutional feedback cycle statuses.
    Counts active/open forms.
    Never submits feedback.
    """
    if not raw_feedback or not isinstance(raw_feedback, list):
        return {
            "active_count": 0,
            "total_cycles": 0,
            "cycles": []
        }

    cycles: List[Dict[str, Any]] = []
    active_count = 0

    for item in raw_feedback:
        if not isinstance(item, dict):
            continue
        cycle_type = str(item.get("type") or "Institutional Feedback").strip()
        status = str(item.get("status") or "Not Scheduled").strip()
        desc = str(item.get("description") or "").strip()
        
        is_active = status.lower() not in ("not scheduled", "closed", "completed", "inactive")
        if is_active:
            active_count += 1

        cycles.append({
            "type": cycle_type,
            "status": status,
            "description": desc,
            "is_active": is_active
        })

    return {
        "active_count": active_count,
        "total_cycles": len(cycles),
        "cycles": cycles
    }


def build_student_dossier(
    user_doc: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Builds the consolidated Student Identity Dossier from verified authenticated records.
    Extracts identity from root fields, studzone1.profile, and html_vallalar.
    Only includes fields that actually exist and non-null.
    Excludes passwords, database IDs, and internal security fields.
    """
    if not user_doc or not isinstance(user_doc, dict):
        return {}

    dossier: Dict[str, Any] = {}

    # 1. Primary Identifiers from root document
    roll_no = str(user_doc.get("rollNo") or "").strip()
    name = str(user_doc.get("name") or "").strip()
    email = str(user_doc.get("email") or "").strip()

    if roll_no:
        dossier["rollNo"] = roll_no
    if name:
        dossier["name"] = name
    if email:
        dossier["email"] = email

    # 2. Extract from StudZone 1 profile
    sz1 = user_doc.get("studzone1", {})
    if isinstance(sz1, dict):
        profile = sz1.get("profile", {})
        if isinstance(profile, dict):
            if profile.get("Institution") and "institution" not in dossier:
                dossier["institution"] = str(profile.get("Institution")).strip()
            if profile.get("Degree") and "degree" not in dossier:
                dossier["degree"] = str(profile.get("Degree")).strip()
            if profile.get("Programme") and "degree" not in dossier:
                dossier["degree"] = str(profile.get("Programme")).strip()
            if profile.get("Roll Number") and "rollNo" not in dossier:
                dossier["rollNo"] = str(profile.get("Roll Number")).strip()
            if profile.get("Name") and "name" not in dossier:
                dossier["name"] = str(profile.get("Name")).strip()

        # 3. Extract extended verified dossier fields from html_vallalar if present
        sch = sz1.get("scholarships", {})
        if isinstance(sch, dict) and sch.get("html_vallalar"):
            try:
                soup = BeautifulSoup(sch["html_vallalar"], "html.parser")
                for tr in soup.find_all("tr"):
                    th = tr.find("th")
                    td = tr.find("td")
                    if th and td:
                        key = th.get_text(strip=True).lower()
                        val = td.get_text(strip=True)
                        if not val:
                            continue

                        if "date of birth" in key:
                            dossier["dob"] = val
                        elif "mobile" in key:
                            dossier["mobile"] = val
                        elif "communication" in key and not dossier.get("email"):
                            dossier["email"] = val
                        elif "semester" in key:
                            try:
                                dossier["semester"] = int(val)
                            except (ValueError, TypeError):
                                dossier["semester"] = val
                        elif "admission" in key:
                            dossier["admission_type"] = val
                        elif "resident" in key:
                            dossier["resident_status"] = val
                        elif "room" in key:
                            dossier["room_number"] = val
                        elif "programme" in key and "degree" not in dossier:
                            dossier["degree"] = val
            except Exception:
                pass

        # 4. Check profile for Resident Status & Room Number if not populated by vallalar
        if isinstance(profile, dict):
            if profile.get("Resident Status") and "resident_status" not in dossier:
                dossier["resident_status"] = str(profile.get("Resident Status")).strip()
            if profile.get("Room Number") and "room_number" not in dossier:
                dossier["room_number"] = str(profile.get("Room Number")).strip()

    return dossier


def synthesize_campus_services(
    user_doc: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Main aggregator function for the Campus Services & Student Dossier Hub.
    Synthesizes:
    - Student Identity Dossier
    - Institutional Fee Ledger
    - Hostel & Accommodation Records
    - Scholarships Summary (Applied vs. Received/Disbursed)
    - Course & Institutional Feedback Cycles
    """
    if not user_doc or not isinstance(user_doc, dict):
        return {
            "error": "Invalid or missing student document",
            "student_dossier": {},
            "fees": {},
            "hostel": {},
            "scholarships": {},
            "feedback": {},
            "disclaimer": "Official campus records sourced directly from StudZone 1 portal."
        }

    sz1 = user_doc.get("studzone1", {})
    if not isinstance(sz1, dict):
        sz1 = {}

    # Extract raw sub-components
    raw_fees = sz1.get("fee_status") or user_doc.get("fees")
    raw_fee_items = sz1.get("fee_items") or []

    raw_hostel = {
        "hostel_status": sz1.get("hostel_status") or user_doc.get("hostel"),
        "hostel_records": sz1.get("hostel_records") or [],
        "hostel_html": sz1.get("hostel_html") or ""
    }
    raw_profile = sz1.get("profile") or {}

    raw_scholarships = sz1.get("scholarships") or user_doc.get("scholarships") or {}
    raw_feedback = sz1.get("feedback") or user_doc.get("feedback") or []

    # Execute deterministic parsers
    dossier = build_student_dossier(user_doc)
    fees = parse_fee_ledger(raw_fees, raw_fee_items)
    
    # Merge resolved dossier fields into profile for hostel parser
    hostel_profile = dict(raw_profile)
    if dossier.get("room_number"):
        hostel_profile["Room Number"] = dossier["room_number"]
    if dossier.get("resident_status"):
        hostel_profile["Resident Status"] = dossier["resident_status"]

    hostel = parse_hostel_dossier(raw_hostel, profile=hostel_profile)
    scholarships = parse_scholarship_records(raw_scholarships)
    feedback = parse_feedback_status(raw_feedback)

    return {
        "student_dossier": dossier,
        "fees": fees,
        "hostel": hostel,
        "scholarships": scholarships,
        "feedback": feedback,
        "disclaimer": "Official campus records sourced directly from StudZone 1 portal. Zero modifications permitted."
    }
