"""
Top-level Domain Parser orchestrator for Student Sync - Hostel subsystem.
Consumes RawExtractionBundle to produce structured ParsedHostelData without network dependency.
"""
from typing import Any, List, Optional

from parser.fees import AcademicYearParser, HostelFeeDueParser, HostelFeesParser
from parser.leave import (
    LeaveApproverParser,
    LeaveHistoryParser,
    LeaveSummaryParser,
)
from parser.mess import MessDetailsParser
from parser.models import (
    ParsedHostelData,
    SourceAcademicYearItem,
    SourceFeesDetails,
    SourceHostelFeeDueItem,
    SourceLeaveApproverItem,
    SourceLeaveHistoryItem,
    SourceLeaveSummaryItem,
    SourceMessDetails,
    SourceRoomDetails,
    SourceStudentProfile,
)
from parser.room import RoomDetailsParser
from parser.student import StudentProfileParser
from parser.view import StudentViewParser
from scraper.raw import RawExtractionBundle


class HostelDomainParser:
    """
    Unified domain parser orchestrator.
    Consumes verified raw extraction bundles and produces immutable ParsedHostelData.
    """

    def __init__(self) -> None:
        self.profile_parser = StudentProfileParser()
        self.room_parser = RoomDetailsParser()
        self.mess_parser = MessDetailsParser()
        self.fees_parser = HostelFeesParser()
        self.leave_summary_parser = LeaveSummaryParser()
        self.leave_approver_parser = LeaveApproverParser()
        self.leave_history_parser = LeaveHistoryParser()
        self.academic_year_parser = AcademicYearParser()
        self.fee_due_parser = HostelFeeDueParser()
        self.view_parser = StudentViewParser()

    def parse_bundle(self, bundle: RawExtractionBundle) -> ParsedHostelData:
        """
        Parse all verified endpoint responses contained within a RawExtractionBundle.
        Preserves reference to raw bundle for full traceability and audit lineage.
        """
        profile = None
        if bundle.has_endpoint("student_details"):
            rec = bundle.get_response("student_details")
            if rec and rec.is_success and rec.get_payload() is not None:
                profile = self.profile_parser.parse(rec)

        room = None
        if bundle.has_endpoint("room_details"):
            rec = bundle.get_response("room_details")
            if rec and rec.is_success and rec.get_payload() is not None:
                room = self.room_parser.parse(rec)

        mess = None
        if bundle.has_endpoint("mess_details"):
            rec = bundle.get_response("mess_details")
            if rec and rec.is_success and rec.get_payload() is not None:
                mess = self.mess_parser.parse(rec)

        fees = None
        if bundle.has_endpoint("fees_details"):
            rec = bundle.get_response("fees_details")
            if rec and rec.is_success and rec.get_payload() is not None:
                fees = self.fees_parser.parse(rec)

        leave_summary: List[SourceLeaveSummaryItem] = []
        if bundle.has_endpoint("leave_summary"):
            rec = bundle.get_response("leave_summary")
            if rec and rec.is_success and rec.get_payload() is not None:
                leave_summary = self.leave_summary_parser.parse(rec)

        leave_approvers: List[SourceLeaveApproverItem] = []
        if bundle.has_endpoint("leave_approvers"):
            rec = bundle.get_response("leave_approvers")
            if rec and rec.is_success and rec.get_payload() is not None:
                leave_approvers = self.leave_approver_parser.parse(rec)

        leave_history: List[SourceLeaveHistoryItem] = []
        if bundle.has_endpoint("leave_history"):
            rec = bundle.get_response("leave_history")
            if rec and rec.is_success and rec.get_payload() is not None:
                leave_history = self.leave_history_parser.parse(rec)

        academic_years: List[SourceAcademicYearItem] = []
        if bundle.has_endpoint("academic_year"):
            rec = bundle.get_response("academic_year")
            if rec and rec.is_success and rec.get_payload() is not None:
                academic_years = self.academic_year_parser.parse(rec)

        fee_dues: List[SourceHostelFeeDueItem] = []
        if bundle.has_endpoint("hostel_fee_due"):
            rec = bundle.get_response("hostel_fee_due")
            if rec and rec.is_success and rec.get_payload() is not None:
                fee_dues = self.fee_due_parser.parse(rec)

        mess_bills = []
        transactions = []
        if bundle.has_endpoint("student_view"):
            rec = bundle.get_response("student_view")
            if rec and rec.is_success and rec.get_payload():
                payload = rec.get_payload()
                if isinstance(payload, str):
                    mess_bills = self.view_parser.parse_mess_bills(payload)
                    transactions = self.view_parser.parse_transactions(payload)

        return ParsedHostelData(
            extraction_run_id=bundle.run_id,
            extracted_at=bundle.timestamp_utc,
            profile=profile,
            room=room,
            mess=mess,
            fees=fees,
            leave_summary=leave_summary,
            leave_approvers=leave_approvers,
            leave_history=leave_history,
            academic_years=academic_years,
            fee_dues=fee_dues,
            mess_bills=mess_bills,
            transactions=transactions,
            raw_bundle=bundle,
        )

    # Direct individual parsing helpers
    def parse_profile(self, raw_input: Any) -> SourceStudentProfile:
        return self.profile_parser.parse(raw_input)

    def parse_room(self, raw_input: Any) -> Optional[SourceRoomDetails]:
        return self.room_parser.parse(raw_input)

    def parse_mess(self, raw_input: Any) -> Optional[SourceMessDetails]:
        return self.mess_parser.parse(raw_input)

    def parse_fees(self, raw_input: Any) -> Optional[SourceFeesDetails]:
        return self.fees_parser.parse(raw_input)

    def parse_leave_summary(self, raw_input: Any) -> List[SourceLeaveSummaryItem]:
        return self.leave_summary_parser.parse(raw_input)

    def parse_leave_approvers(self, raw_input: Any) -> List[SourceLeaveApproverItem]:
        return self.leave_approver_parser.parse(raw_input)

    def parse_leave_history(self, raw_input: Any) -> List[SourceLeaveHistoryItem]:
        return self.leave_history_parser.parse(raw_input)

    def parse_academic_years(self, raw_input: Any) -> List[SourceAcademicYearItem]:
        return self.academic_year_parser.parse(raw_input)

    def parse_fee_dues(self, raw_input: Any) -> List[SourceHostelFeeDueItem]:
        return self.fee_due_parser.parse(raw_input)
