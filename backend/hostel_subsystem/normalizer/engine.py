"""
Hostel Data Normalization Engine for Student Sync - Hostel subsystem.
Translates comprehensive ParsedHostelData into canonical NormalizedHostelData.
"""
from typing import Any, List, Optional

from core.exceptions import InvalidNormalizedTypeError
from normalizer.fees import (
    AcademicYearNormalizer,
    HostelFeeDueNormalizer,
    HostelFeesNormalizer,
)
from normalizer.leave import (
    LeaveApproverNormalizer,
    LeaveHistoryNormalizer,
    LeaveSummaryNormalizer,
)
from normalizer.mess import MessDetailsNormalizer
from normalizer.models import (
    NormalizedAcademicYearItem,
    NormalizedFeesDetails,
    NormalizedHostelData,
    NormalizedHostelFeeDueItem,
    NormalizedLeaveApproverItem,
    NormalizedLeaveHistoryItem,
    NormalizedLeaveSummaryItem,
    NormalizedMessDetails,
    NormalizedRoomDetails,
    NormalizedStudentProfile,
)
from normalizer.room import RoomDetailsNormalizer
from normalizer.student import StudentProfileNormalizer
from normalizer.view import StudentViewNormalizer
from parser.models import ParsedHostelData


class HostelDataNormalizer:
    """
    Unified normalization orchestrator.
    Consumes ParsedHostelData and produces canonical, immutable NormalizedHostelData.
    """

    def __init__(self) -> None:
        self.profile_normalizer = StudentProfileNormalizer()
        self.room_normalizer = RoomDetailsNormalizer()
        self.mess_normalizer = MessDetailsNormalizer()
        self.fees_normalizer = HostelFeesNormalizer()
        self.leave_summary_normalizer = LeaveSummaryNormalizer()
        self.leave_approver_normalizer = LeaveApproverNormalizer()
        self.leave_history_normalizer = LeaveHistoryNormalizer()
        self.academic_year_normalizer = AcademicYearNormalizer()
        self.fee_due_normalizer = HostelFeeDueNormalizer()
        self.view_normalizer = StudentViewNormalizer()

    def normalize(self, parsed_data: Any) -> NormalizedHostelData:
        """
        Normalize all parsed domain structures within a ParsedHostelData container.
        Preserves reference to raw bundle for full traceability and lineage.
        """
        if not isinstance(parsed_data, ParsedHostelData):
            raise InvalidNormalizedTypeError(
                f"Expected ParsedHostelData, got {type(parsed_data).__name__}"
            )

        norm_profile = (
            self.profile_normalizer.normalize(parsed_data.profile)
            if parsed_data.profile is not None
            else None
        )

        norm_room = (
            self.room_normalizer.normalize(parsed_data.room)
            if parsed_data.room is not None
            else None
        )

        norm_mess = (
            self.mess_normalizer.normalize(parsed_data.mess)
            if parsed_data.mess is not None
            else None
        )

        norm_fees = (
            self.fees_normalizer.normalize(parsed_data.fees)
            if parsed_data.fees is not None
            else None
        )

        norm_leave_summary = self.leave_summary_normalizer.normalize(
            parsed_data.leave_summary
        )

        norm_leave_approvers = self.leave_approver_normalizer.normalize(
            parsed_data.leave_approvers
        )

        norm_leave_history = self.leave_history_normalizer.normalize(
            parsed_data.leave_history
        )

        norm_academic_years = self.academic_year_normalizer.normalize(
            parsed_data.academic_years
        )

        norm_fee_dues = self.fee_due_normalizer.normalize(
            parsed_data.fee_dues
        )

        norm_mess_bills = self.view_normalizer.normalize_mess_bills(
            getattr(parsed_data, "mess_bills", [])
        )

        norm_transactions = self.view_normalizer.normalize_transactions(
            getattr(parsed_data, "transactions", [])
        )

        return NormalizedHostelData(
            extraction_run_id=parsed_data.extraction_run_id,
            extracted_at=parsed_data.extracted_at,
            profile=norm_profile,
            room=norm_room,
            mess=norm_mess,
            fees=norm_fees,
            leave_summary=norm_leave_summary,
            leave_approvers=norm_leave_approvers,
            leave_history=norm_leave_history,
            academic_years=norm_academic_years,
            fee_dues=norm_fee_dues,
            mess_bills=norm_mess_bills,
            transactions=norm_transactions,
            raw_bundle=parsed_data.raw_bundle,
        )

    # Convenience individual normalization helpers
    def normalize_profile(self, parsed_profile: Any) -> NormalizedStudentProfile:
        return self.profile_normalizer.normalize(parsed_profile)

    def normalize_room(self, parsed_room: Any) -> Optional[NormalizedRoomDetails]:
        return self.room_normalizer.normalize(parsed_room)

    def normalize_mess(self, parsed_mess: Any) -> Optional[NormalizedMessDetails]:
        return self.mess_normalizer.normalize(parsed_mess)

    def normalize_fees(self, parsed_fees: Any) -> Optional[NormalizedFeesDetails]:
        return self.fees_normalizer.normalize(parsed_fees)

    def normalize_leave_summary(self, parsed_summary: Any) -> List[NormalizedLeaveSummaryItem]:
        return self.leave_summary_normalizer.normalize(parsed_summary)

    def normalize_leave_approvers(self, parsed_approvers: Any) -> List[NormalizedLeaveApproverItem]:
        return self.leave_approver_normalizer.normalize(parsed_approvers)

    def normalize_leave_history(self, parsed_history: Any) -> List[NormalizedLeaveHistoryItem]:
        return self.leave_history_normalizer.normalize(parsed_history)

    def normalize_academic_years(self, parsed_years: Any) -> List[NormalizedAcademicYearItem]:
        return self.academic_year_normalizer.normalize(parsed_years)

    def normalize_fee_dues(self, parsed_dues: Any) -> List[NormalizedHostelFeeDueItem]:
        return self.fee_due_normalizer.normalize(parsed_dues)
