"""
Normalization package for Student Sync - Hostel subsystem.
Translates parsed source domain models into canonical, typed, immutable data structures.
"""
from core.exceptions import (
    InvalidDateFormatError,
    InvalidNormalizedTypeError,
    InvalidNumericFormatError,
    NormalizationError,
)
from normalizer.engine import HostelDataNormalizer
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

__all__ = [
    "NormalizationError",
    "InvalidNormalizedTypeError",
    "InvalidDateFormatError",
    "InvalidNumericFormatError",
    "NormalizedStudentProfile",
    "NormalizedRoomDetails",
    "NormalizedMessDetails",
    "NormalizedFeesDetails",
    "NormalizedLeaveSummaryItem",
    "NormalizedLeaveApproverItem",
    "NormalizedLeaveHistoryItem",
    "NormalizedAcademicYearItem",
    "NormalizedHostelFeeDueItem",
    "NormalizedHostelData",
    "StudentProfileNormalizer",
    "RoomDetailsNormalizer",
    "MessDetailsNormalizer",
    "HostelFeesNormalizer",
    "LeaveSummaryNormalizer",
    "LeaveApproverNormalizer",
    "LeaveHistoryNormalizer",
    "AcademicYearNormalizer",
    "HostelFeeDueNormalizer",
    "HostelDataNormalizer",
]
