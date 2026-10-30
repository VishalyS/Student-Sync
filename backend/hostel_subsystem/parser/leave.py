"""
Domain parsers for leave-related endpoints:
- /Hostel/Student/StudLeaveS (Leave Summary)
- /Hostel/Student/StudApprMngr (Leave Approvers)
- /Hostel/Student/StudentGetLeav (Leave History)
"""
from typing import Any, List

from core.exceptions import ParserError
from parser.base import BaseDomainParser
from parser.models import (
    SourceLeaveApproverItem,
    SourceLeaveHistoryItem,
    SourceLeaveSummaryItem,
)


class LeaveSummaryParser(BaseDomainParser):
    """
    Parses /Hostel/Student/StudLeaveS into List[SourceLeaveSummaryItem].
    """
    ENDPOINT = "leave_summary"

    def parse(self, raw_input: Any) -> List[SourceLeaveSummaryItem]:
        payload = self.extract_payload(raw_input)
        records = self.ensure_list(self.ENDPOINT, payload)

        results = []
        for item in records:
            data = self.ensure_dict(self.ENDPOINT, item)
            results.append(
                SourceLeaveSummaryItem(
                    leave_type=self.validate_type(self.ENDPOINT, data, "leave_type", str),
                    leave=str(self.require_field(self.ENDPOINT, data, "leave")),
                )
            )
        return results


class LeaveApproverParser(BaseDomainParser):
    """
    Parses /Hostel/Student/StudApprMngr into List[SourceLeaveApproverItem].
    """
    ENDPOINT = "leave_approvers"

    def parse(self, raw_input: Any) -> List[SourceLeaveApproverItem]:
        payload = self.extract_payload(raw_input)
        records = self.ensure_list(self.ENDPOINT, payload)

        results = []
        for item in records:
            data = self.ensure_dict(self.ENDPOINT, item)
            results.append(
                SourceLeaveApproverItem(
                    staff_id=self.validate_type(self.ENDPOINT, data, "staff_id", str),
                    staff_name=self.validate_type(self.ENDPOINT, data, "staff_name", str),
                )
            )
        return results


class LeaveHistoryParser(BaseDomainParser):
    """
    Parses /Hostel/Student/StudentGetLeav into List[SourceLeaveHistoryItem].
    Returns empty list [] when student has no filed leaves.
    """
    ENDPOINT = "leave_history"

    def parse(self, raw_input: Any) -> List[SourceLeaveHistoryItem]:
        payload = self.extract_payload(raw_input)
        records = self.ensure_list(self.ENDPOINT, payload)

        results = []
        for item in records:
            data = self.ensure_dict(self.ENDPOINT, item)
            results.append(
                SourceLeaveHistoryItem(
                    fromdate=self.validate_type(self.ENDPOINT, data, "fromdate", str),
                    todate=self.validate_type(self.ENDPOINT, data, "todate", str),
                    leave_type=self.validate_type(self.ENDPOINT, data, "leave_type", str),
                    reason=self.validate_type(self.ENDPOINT, data, "reason", str),
                    status=self.validate_type(self.ENDPOINT, data, "status", str),
                )
            )
        return results
