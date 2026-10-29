"""
backend/residential_service.py

Student Sync — Residential Status Resolution Service.
Determines whether an authenticated student is a HOSTELLER, DAY_SCHOLAR, or UNKNOWN
based on verified StudZone 1 institutional portal data.

Internal States:
- 'HOSTELLER': Verified active resident on campus with hostel room allocation.
- 'DAY_SCHOLAR': Verified non-resident student.
- 'UNKNOWN': Residential status missing, ambiguous, or unverifiable (FAILS CLOSED).

Strict Rules:
1. Never defaults to HOSTELLER on missing, corrupt, or unverified data.
2. Never trusts roll numbers, emails, or client-provided eligibility flags.
3. Derives status strictly from authenticated server-side student records.
4. Preserves zero-contamination isolation across students.
"""

import re
import logging
from typing import Any, Dict, Optional, Tuple
from bs4 import BeautifulSoup

logger = logging.getLogger("studentsync.residential.service")

# Standardized Application States
STATUS_HOSTELLER = "HOSTELLER"
STATUS_DAY_SCHOLAR = "DAY_SCHOLAR"
STATUS_UNKNOWN = "UNKNOWN"


def extract_vallalar_fields(html_content: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Extracts 'Resident Status' and 'Room Number' from StudZone 1 Vallalar Scholarship HTML table.
    Endpoint: /StudZone/Scholar/VallalarScholarship
    Returns: (resident_status_text, room_number_text)
    """
    if not html_content or not isinstance(html_content, str) or not html_content.strip():
        return None, None

    try:
        soup = BeautifulSoup(html_content, "html.parser")
        resident_status = None
        room_number = None

        for tr in soup.find_all("tr"):
            th = tr.find("th")
            td = tr.find("td")
            if th and td:
                key = th.get_text(strip=True).lower()
                val = td.get_text(strip=True)
                if not val:
                    continue

                if "resident" in key:
                    resident_status = val
                elif "room" in key:
                    room_number = val

        return resident_status, room_number
    except Exception as exc:
        logger.warning("Error parsing Vallalar HTML for residential status: %s", exc)
        return None, None


def determine_residential_status(user_doc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluates an authenticated student document and resolves the verified residential category.

    Resolution Priority:
    1. StudZone 1 Vallalar table: 'Resident Status' and 'Room Number'
       - 'HOSTELLER' -> STATUS_HOSTELLER
       - 'DAYS SCHOLAR' or 'DAY SCHOLAR' -> STATUS_DAY_SCHOLAR
    2. StudZone 1 Profile dictionary: 'Resident Status' or 'resident_status'
    3. StudZone 1 Hostel Allocation Status (/StudZone/Hostel/PaymentStart):
       - If explicitly 'No Active Hostel Allocation' or 'Not Registered' with empty records -> STATUS_DAY_SCHOLAR
       - If 'Registered / Hostel Data Available' with confirmed records and NOT marked day scholar -> STATUS_HOSTELLER
    4. Missing, unverified, or ambiguous -> STATUS_UNKNOWN (fail-closed)
    """
    default_unknown = {
        "status": STATUS_UNKNOWN,
        "is_hosteller": False,
        "is_day_scholar": False,
        "room_number": None,
        "raw_status": None,
        "verified_source": None,
        "can_access_hostel": False,
    }

    if not user_doc or not isinstance(user_doc, dict):
        return default_unknown

    sz1 = user_doc.get("studzone1")
    if not isinstance(sz1, dict):
        sz1 = {}

    raw_resident_status = None
    room_number = None
    verified_source = None

    # 1. Primary Source: StudZone 1 Vallalar Scholarship HTML Table
    sch = sz1.get("scholarships")
    if isinstance(sch, dict) and sch.get("html_vallalar"):
        v_status, v_room = extract_vallalar_fields(sch["html_vallalar"])
        if v_status:
            raw_resident_status = v_status
            room_number = v_room
            verified_source = "StudZone 1 Vallalar Portal Record"

    # 2. Secondary Source: Profile dictionary inside studzone1 or root profile
    if not raw_resident_status:
        for prof_candidate in [sz1.get("profile"), user_doc.get("profile")]:
            if isinstance(prof_candidate, dict):
                cand_status = prof_candidate.get("Resident Status") or prof_candidate.get("resident_status")
                cand_room = prof_candidate.get("Room Number") or prof_candidate.get("room_number")
                if cand_status and str(cand_status).strip():
                    raw_resident_status = str(cand_status).strip()
                    room_number = str(cand_room).strip() if cand_room else room_number
                    verified_source = "StudZone 1 Student Profile"
                    break

    # 3. Tertiary Source: StudZone 1 Hostel Payment & Allocation Status
    hostel_status_str = str(sz1.get("hostel_status") or user_doc.get("hostel_status") or "").strip()
    hostel_records = sz1.get("hostel_records") or []

    # Map raw resident status string to application states
    cleaned_status_upper = (raw_resident_status or "").strip().upper()

    # Clean room number: '-' or empty should be normalized to None
    clean_room = room_number.strip() if room_number and room_number.strip() not in ("-", "N/A", "NA", "") else None

    # Check for Hosteller
    if cleaned_status_upper == "HOSTELLER":
        return {
            "status": STATUS_HOSTELLER,
            "is_hosteller": True,
            "is_day_scholar": False,
            "room_number": clean_room,
            "raw_status": raw_resident_status,
            "verified_source": verified_source,
            "can_access_hostel": True,
        }

    # Check for Day Scholar (handles both "DAYS SCHOLAR" and "DAY SCHOLAR")
    if "DAY SCHOLAR" in cleaned_status_upper or "DAYS SCHOLAR" in cleaned_status_upper:
        return {
            "status": STATUS_DAY_SCHOLAR,
            "is_hosteller": False,
            "is_day_scholar": True,
            "room_number": None,
            "raw_status": raw_resident_status,
            "verified_source": verified_source,
            "can_access_hostel": False,
        }

    # If no explicit Resident Status was found, inspect hostel_status
    if hostel_status_str:
        hostel_upper = hostel_status_str.upper()
        if "NO ACTIVE HOSTEL ALLOCATION" in hostel_upper or "NOT REGISTERED" in hostel_upper or "NO HOSTEL ALLOCATION" in hostel_upper:
            return {
                "status": STATUS_DAY_SCHOLAR,
                "is_hosteller": False,
                "is_day_scholar": True,
                "room_number": None,
                "raw_status": hostel_status_str,
                "verified_source": "StudZone 1 Hostel Allocation Status",
                "can_access_hostel": False,
            }
        if ("REGISTERED" in hostel_upper and ("HOSTEL DATA AVAILABLE" in hostel_upper or len(hostel_records) > 0)) or "HOSTEL ROOM" in hostel_upper or "BLOCK" in hostel_upper:
            return {
                "status": STATUS_HOSTELLER,
                "is_hosteller": True,
                "is_day_scholar": False,
                "room_number": clean_room,
                "raw_status": hostel_status_str,
                "verified_source": "StudZone 1 Hostel Allocation Status",
                "can_access_hostel": True,
            }

    # Fail closed: UNKNOWN
    return {
        "status": STATUS_UNKNOWN,
        "is_hosteller": False,
        "is_day_scholar": False,
        "room_number": None,
        "raw_status": raw_resident_status,
        "verified_source": verified_source,
        "can_access_hostel": False,
    }
