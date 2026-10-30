"""
CLI Runner script for Student Sync - Hostel subsystem.
Allows operators and automated test runners to execute full extraction cycles
in either live mode (--live) or synthetic deterministic mode (--mock).
Produces formatted console summaries and optional sanitized JSON audit files.
"""
import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import HostelConfig, load_config
from core.logging import get_logger
from pipeline import HostelPipelineResult, HostelPipelineRunner, PipelineStatus
from scraper.raw import RawExtractionBundle, RawResponseRecord


def create_mock_bundle(roll_number: str, run_id: Optional[str] = None) -> RawExtractionBundle:
    """Generate a valid, synthetic in-memory RawExtractionBundle for mock runs."""
    active_run_id = run_id or f"run_mock_{int(time.time() * 1000)}"
    responses: Dict[str, RawResponseRecord] = {
        "student_details": RawResponseRecord(
            endpoint_name="student_details",
            url_path="/Hostel/Student/studDetails",
            http_status=200,
            content_type="application/json; charset=utf-8",
            response_time_ms=85.0,
            raw_payload=[
                {
                    "name": "TEST RESIDENT",
                    "rollno": roll_number,
                    "drollno": "25DTEST01",
                    "mobile": "9876543210",
                    "programme": "M.C.A. (REGULAR)",
                    "class_": "MCA-I",
                    "father": "PARENT NAME",
                    "mother": None,
                    "addr": "123 HOSTEL CAMPUS",
                    "districtName": "COIMBATORE",
                    "stateName": "TAMIL NADU",
                    "fmobile": "9876543211",
                    "mmobile": "Not Available",
                    "email": "student@example.test",
                    "imgStatus": "Y",
                    "StudPic": "mock_pic",
                    "progId": 102,
                    "degreeId": 12,
                    "semNo": 2,
                }
            ],
            is_success=True,
        ),
        "room_details": RawResponseRecord(
            endpoint_name="room_details",
            url_path="/Hostel/Student/roomDetails",
            http_status=200,
            content_type="application/json",
            response_time_ms=65.0,
            raw_payload=[
                {
                    "hostel": "BOYS HOSTEL 1",
                    "block": "B BLOCK",
                    "hos_id": 1,
                    "block_id": 2,
                    "room_type": "FOUR SHARING",
                    "doj": "2025-08-14",
                    "floor_room": "FIRST FLOOR",
                    "room": "108",
                    "warden": "WARDEN NAME",
                    "restutor": "TUTOR NAME",
                }
            ],
            is_success=True,
        ),
        "mess_details": RawResponseRecord(
            endpoint_name="mess_details",
            url_path="/Hostel/Student/StudMessDet",
            http_status=200,
            content_type="application/json",
            response_time_ms=55.0,
            raw_payload=[
                {
                    "_MessName": "A MESS - SOUTH INDIAN",
                    "_MessSupervisor": "SUPERVISOR NAME",
                    "_MessType": "NON-VEG",
                    "_MessMemberSince": "2025-08-14",
                    "_MessEggToken": "ACTIVE",
                    "_MessNvToken": "0",
                }
            ],
            is_success=True,
        ),
        "fees_details": RawResponseRecord(
            endpoint_name="fees_details",
            url_path="/Hostel/Student/StudHosFeesDet",
            http_status=200,
            content_type="application/json",
            response_time_ms=50.0,
            raw_payload=[
                {
                    "_HosFeesBalance": "1500.00",
                    "_HosFeesDeposit": "5000.00",
                    "_HosFeesEstab": "12000.00",
                    "_TokenBalance": "0.00",
                }
            ],
            is_success=True,
        ),
        "leave_summary": RawResponseRecord(
            endpoint_name="leave_summary",
            url_path="/Hostel/Student/StudLeaveS",
            http_status=200,
            content_type="application/json",
            response_time_ms=45.0,
            raw_payload=[{"leave_type": "CASUAL LEAVE", "leave": "10"}],
            is_success=True,
        ),
        "leave_approvers": RawResponseRecord(
            endpoint_name="leave_approvers",
            url_path="/Hostel/Student/StudApprMngr",
            http_status=200,
            content_type="application/json",
            response_time_ms=40.0,
            raw_payload=[{"staff_id": "STF001", "staff_name": "DR. FACULTY"}],
            is_success=True,
        ),
        "leave_history": RawResponseRecord(
            endpoint_name="leave_history",
            url_path="/Hostel/Student/StudentGetLeav",
            http_status=200,
            content_type="application/json",
            response_time_ms=40.0,
            raw_payload=[],
            is_success=True,
        ),
        "academic_year": RawResponseRecord(
            endpoint_name="academic_year",
            url_path="/Hostel/Student/GetYear",
            http_status=200,
            content_type="application/json",
            response_time_ms=35.0,
            raw_payload=[{"proc_year": "2025-2026", "amt": "75000"}],
            is_success=True,
        ),
        "hostel_fee_due": RawResponseRecord(
            endpoint_name="hostel_fee_due",
            url_path="/Hostel/Student/GetHosFee",
            http_status=200,
            content_type="application/json",
            response_time_ms=35.0,
            raw_payload=[],
            is_success=True,
        ),
    }

    return RawExtractionBundle(
        run_id=active_run_id,
        timestamp_utc="2026-10-08T06:00:00Z",
        responses=responses,
        student_roll_number=roll_number,
        is_success=True,
    )


def print_banner() -> None:
    print("=" * 68)
    print("       STUDENT SYNC - HOSTEL PIPELINE EXTRACTION RUNNER")
    print("=" * 68)



def print_summary(result: HostelPipelineResult) -> None:
    print("\n" + "-" * 68)
    print("                     EXTRACTION SUMMARY REPORT")
    print("-" * 68)
    print(f" Status:             {result.status.value}")
    print(f" Run ID:             {result.run_id}")
    print(f" Target Resident:    {result.target_roll_number[:2]}***")
    print(f" Timestamp:          {result.extracted_at}")
    print(f" Total Duration:     {result.execution_time_seconds:.3f}s")
    print(f" Endpoints Captured: {result.endpoints_count}/9")
    print(f" Validation Result:  {'PASS (100% VALID)' if result.is_valid else 'FAIL'}")
    print(f" Validation Errors:  {result.error_count}")
    print(f" Validation Warnings:{result.warning_count}")

    if result.normalized_data:
        nd = result.normalized_data
        print("\n" + "-" * 68)
        print("                 EXTRACTED RESIDENT ALLOCATION DATA")
        print("-" * 68)
        if nd.profile:
            print(f" Programme:          {nd.profile.programme} (Sem {nd.profile.semester_number})")
            print(f" Class:              {nd.profile.class_name}")

        if nd.room:
            print(f" Hostel / Facility:  {nd.room.hostel_name}")
            print(f" Block & Room:       {nd.room.block_name} - Room {nd.room.room_number} ({nd.room.room_type})")
            if nd.room.floor_description:
                print(f" Floor:              {nd.room.floor_description}")
            if nd.room.warden_name:
                print(f" Warden:             {nd.room.warden_name}")
        else:
            print(" Room Allocation:    No active room allocation (Day Scholar / Unallocated)")

        if nd.mess:
            print(f" Mess Subscribed:    {nd.mess.mess_name} ({nd.mess.mess_type})")
            print(f" Token Statuses:     Egg: {nd.mess.egg_token_status or 'N/A'}, Non-Veg: {nd.mess.non_veg_token_status or 'N/A'}")
        else:
            print(" Mess Allocation:    No active mess allotment")

        if nd.fees:
            print(f" Fee Balance Due:    Rs. {nd.fees.hostel_fee_balance}")
            print(f" Caution Deposit:    Rs. {nd.fees.caution_deposit}")
            print(f" Establishment Fee:  Rs. {nd.fees.establishment_fee}")
            print(f" Mess Token Balance: Rs. {nd.fees.mess_token_balance}")

        if nd.academic_years:
            years = ", ".join(ay.academic_year for ay in nd.academic_years)
            print(f" Academic Year(s):   {years}")

    if result.validation_result and result.validation_result.findings:
        print("\n Validation Findings:")
        for f in result.validation_result.findings:
            print(f"   [{f.severity.value}] [{f.category.value}] {f.rule_name}: {f.message}")

    if result.error_message:
        print(f"\n Error Message:      {result.error_message}")
    print("-" * 68 + "\n")



def main() -> int:
    parser = argparse.ArgumentParser(
        description="Student Sync - Hostel Scraper Pipeline Runner"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Execute live extraction using credentials from local .env",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Execute synthetic in-memory capture without hitting the live portal",
    )
    parser.add_argument(
        "--roll",
        type=str,
        default=None,
        help="Override resident roll number",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to write sanitized JSON audit output file",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error code 1 if any warnings exist",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable detailed debug logging",
    )

    args = parser.parse_args()

    log_level = "DEBUG" if args.verbose else "INFO"
    logger = get_logger("student_sync_hostel.cli", level=log_level)


    print_banner()

    runner = HostelPipelineRunner(logger=logger)

    # Determine execution mode: live vs mock
    if args.live:
        print("[MODE] LIVE PORTAL EXTRACTION")
        try:
            config = load_config()
            roll_to_use = (args.roll or config.username).strip().upper()
            print(f"[INFO] Target: {roll_to_use[:2]}*** @ {config.base_url}")
            runner.config = config
            result = runner.run(roll_number=roll_to_use)
        except Exception as exc:
            print(f"[ERROR] Failed to initialize live execution: {exc}")
            return 1
    else:
        # Default to safe mock execution
        roll_to_use = (args.roll or "25TEST01").strip().upper()
        print(f"[MODE] SYNTHETIC MOCK EXTRACTION (Resident: {roll_to_use[:2]}***)")
        mock_bundle = create_mock_bundle(roll_to_use)
        result = runner.run_from_raw(mock_bundle, target_roll_number=roll_to_use)

    print_summary(result)

    # Write output JSON file if requested
    if args.output:
        out_path = Path(args.output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        dump_data = result.to_dict()
        dump_data["extraction"] = result.to_extraction_result().to_dict(mask_pii=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(dump_data, f, indent=2)
        print(f"[INFO] Saved audit results to: {out_path}")

    # Determine exit code
    if result.status == PipelineStatus.FAILED:
        return 1
    if args.strict and result.warning_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
