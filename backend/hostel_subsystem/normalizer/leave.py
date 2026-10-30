"""
Leave Normalizers for Student Sync - Hostel subsystem.
Translates leave summary, approver staff, and leave application records into canonical representations.
"""
from typing import Any, List

from core.exceptions import InvalidNormalizedTypeError
from normalizer.base import (
    normalize_integer,
    normalize_required_date,
    normalize_required_string,
)
from normalizer.models import (
    NormalizedLeaveApproverItem,
    NormalizedLeaveHistoryItem,
    NormalizedLeaveSummaryItem,
)
from parser.models import (
    SourceLeaveApproverItem,
    SourceLeaveHistoryItem,
    SourceLeaveSummaryItem,
)


class LeaveSummaryNormalizer:
    """
    Normalizes parsed leave quota summaries.
    Converts quota string into integer.
    """

    def normalize(self, source: Any) -> List[NormalizedLeaveSummaryItem]:
        if not isinstance(source, list):
            raise InvalidNormalizedTypeError(
                f"Expected list of SourceLeaveSummaryItem, got {type(source).__name__}"
            )
        
        normalized_items: List[NormalizedLeaveSummaryItem] = []
        for item in source:
            if not isinstance(item, SourceLeaveSummaryItem):
                raise InvalidNormalizedTypeError(
                    f"Expected SourceLeaveSummaryItem, got {type(item).__name__}"
                )
            
            leave_raw = item.leave.strip()
            # Portal returns leave category names (e.g. 'Leave', 'Permission') rather than numeric quotas
            if leave_raw.lower() in ("leave", "permission", "on duty", "general"):
                allocated_days = 0
            else:
                allocated_days = normalize_integer(item.leave, "leave")

            normalized_items.append(
                NormalizedLeaveSummaryItem(
                    leave_type=normalize_required_string(item.leave_type, "leave_type"),
                    allocated_days=allocated_days,
                )
            )
        return normalized_items



class LeaveApproverNormalizer:
    """
    Normalizes parsed leave approval staff records.
    Sanitizes staff ID and full name.
    """

    def normalize(self, source: Any) -> List[NormalizedLeaveApproverItem]:
        if not isinstance(source, list):
            raise InvalidNormalizedTypeError(
                f"Expected list of SourceLeaveApproverItem, got {type(source).__name__}"
            )
        
        normalized_items: List[NormalizedLeaveApproverItem] = []
        for item in source:
            if not isinstance(item, SourceLeaveApproverItem):
                raise InvalidNormalizedTypeError(
                    f"Expected SourceLeaveApproverItem, got {type(item).__name__}"
                )
            normalized_items.append(
                NormalizedLeaveApproverItem(
                    staff_id=normalize_required_string(item.staff_id, "staff_id"),
                    staff_name=normalize_required_string(item.staff_name, "staff_name"),
                )
            )
        return normalized_items


class LeaveHistoryNormalizer:
    """
    Normalizes parsed leave application history records.
    Converts start and end date strings to date objects.
    """

    def normalize(self, source: Any) -> List[NormalizedLeaveHistoryItem]:
        if not isinstance(source, list):
            raise InvalidNormalizedTypeError(
                f"Expected list of SourceLeaveHistoryItem, got {type(source).__name__}"
            )
        
        normalized_items: List[NormalizedLeaveHistoryItem] = []
        for item in source:
            if not isinstance(item, SourceLeaveHistoryItem):
                raise InvalidNormalizedTypeError(
                    f"Expected SourceLeaveHistoryItem, got {type(item).__name__}"
                )
            normalized_items.append(
                NormalizedLeaveHistoryItem(
                    from_date=normalize_required_date(item.fromdate, "fromdate"),
                    to_date=normalize_required_date(item.todate, "todate"),
                    leave_type=normalize_required_string(item.leave_type, "leave_type"),
                    reason=normalize_required_string(item.reason, "reason"),
                    status=normalize_required_string(item.status, "status"),
                )
            )
        return normalized_items
