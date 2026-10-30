"""
Domain Parsing layer for Student Sync - Hostel subsystem.
Translates verified raw API payloads into structured Source Domain models.
"""
from parser.base import BaseDomainParser
from parser.engine import HostelDomainParser
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

__all__ = [
    # Parsers
    "BaseDomainParser",
    "HostelDomainParser",
    "StudentProfileParser",
    "RoomDetailsParser",
    "MessDetailsParser",
    "HostelFeesParser",
    "AcademicYearParser",
    "HostelFeeDueParser",
    "LeaveSummaryParser",
    "LeaveApproverParser",
    "LeaveHistoryParser",
    # Models
    "ParsedHostelData",
    "SourceStudentProfile",
    "SourceRoomDetails",
    "SourceMessDetails",
    "SourceFeesDetails",
    "SourceLeaveSummaryItem",
    "SourceLeaveApproverItem",
    "SourceLeaveHistoryItem",
    "SourceAcademicYearItem",
    "SourceHostelFeeDueItem",
]
