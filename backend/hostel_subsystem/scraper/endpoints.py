"""
Centralized endpoint registry for Student Sync - Hostel subsystem.
Encapsulates all verified read-only endpoints, HTTP methods, paths,
authentication requirements, and criticality tiers.
"""
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


@dataclass(frozen=True)
class EndpointDefinition:
    """
    Immutable metadata definition for a target portal endpoint.
    """
    name: str
    method: str
    path: str
    requires_auth: bool
    requires_rollno: bool
    is_critical: bool
    expected_content_type: str = "application/json"
    expected_root_type: type = list
    timeout_seconds: float = 10.0


class HostelEndpoints(Enum):
    """
    Registry of verified endpoints established during Phase 1A/1B reconnaissance.
    Paths and casings match the exact target ASP.NET Core server implementation.
    """
    # Critical Endpoints (Failure aborts extraction run)
    STUDENT_DETAILS = EndpointDefinition(
        name="student_details",
        method="GET",
        path="/Hostel/Student/studDetails",
        requires_auth=True,
        requires_rollno=True,
        is_critical=True,
        expected_content_type="application/json",
        expected_root_type=list,
    )
    ROOM_DETAILS = EndpointDefinition(
        name="room_details",
        method="GET",
        path="/Hostel/Student/roomDetails",
        requires_auth=True,
        requires_rollno=True,
        is_critical=True,
        expected_content_type="application/json",
        expected_root_type=list,
    )

    # Non-Critical Endpoints (Failure generates warning; run succeeds)
    MESS_DETAILS = EndpointDefinition(
        name="mess_details",
        method="GET",
        path="/Hostel/Student/StudMessDet",
        requires_auth=True,
        requires_rollno=True,
        is_critical=False,
        expected_content_type="application/json",
        expected_root_type=list,
    )
    FEES_DETAILS = EndpointDefinition(
        name="fees_details",
        method="GET",
        path="/Hostel/Student/StudHosFeesDet",
        requires_auth=True,
        requires_rollno=True,
        is_critical=False,
        expected_content_type="application/json",
        expected_root_type=list,
    )
    LEAVE_SUMMARY = EndpointDefinition(
        name="leave_summary",
        method="GET",
        path="/Hostel/Student/StudLeaveS",
        requires_auth=True,
        requires_rollno=True,
        is_critical=False,
        expected_content_type="application/json",
        expected_root_type=list,
    )
    LEAVE_APPROVERS = EndpointDefinition(
        name="leave_approvers",
        method="GET",
        path="/Hostel/Student/StudApprMngr",
        requires_auth=True,
        requires_rollno=True,
        is_critical=False,
        expected_content_type="application/json",
        expected_root_type=list,
    )
    LEAVE_HISTORY = EndpointDefinition(
        name="leave_history",
        method="GET",
        path="/Hostel/Student/StudentGetLeav",
        requires_auth=True,
        requires_rollno=True,
        is_critical=False,
        expected_content_type="application/json",
        expected_root_type=list,
    )
    ACADEMIC_YEAR = EndpointDefinition(
        name="academic_year",
        method="GET",
        path="/Hostel/Student/GetYear",
        requires_auth=True,
        requires_rollno=False,
        is_critical=False,
        expected_content_type="application/json",
        expected_root_type=list,
    )
    HOSTEL_FEE_DUE = EndpointDefinition(
        name="hostel_fee_due",
        method="GET",
        path="/Hostel/Student/GetHosFee",
        requires_auth=True,
        requires_rollno=False,
        is_critical=False,
        expected_content_type="application/json",
        expected_root_type=list,
    )

    @classmethod
    def get_extraction_sequence(cls) -> List[EndpointDefinition]:
        """
        Return the standard sequence of read-only endpoints to extract,
        ordered by critical dependency followed by non-critical sections.
        """
        return [
            cls.STUDENT_DETAILS.value,
            cls.ROOM_DETAILS.value,
            cls.MESS_DETAILS.value,
            cls.FEES_DETAILS.value,
            cls.LEAVE_SUMMARY.value,
            cls.LEAVE_APPROVERS.value,
            cls.LEAVE_HISTORY.value,
            cls.ACADEMIC_YEAR.value,
            cls.HOSTEL_FEE_DUE.value,
        ]
