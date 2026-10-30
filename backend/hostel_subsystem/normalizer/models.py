"""
Normalized Domain Models for Student Sync - Hostel subsystem.
Strongly-typed, immutable representations of hostel data with standardized
field names, rich types (Decimal, datetime.date, int), and sanitized values.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from scraper.raw import RawExtractionBundle


@dataclass(frozen=True)
class NormalizedStudentProfile:
    """
    Canonical representation of student profile information.
    Surrounding whitespace trimmed, placeholders normalized to None,
    and internal field names standardized.
    """
    name: str
    roll_number: str
    degree_roll_number: Optional[str]
    mobile_number: Optional[str]
    programme: str
    class_name: str
    father_name: Optional[str]
    mother_name: Optional[str]
    address: Optional[str]
    district_name: Optional[str]
    state_name: Optional[str]
    father_mobile: Optional[str]
    mother_mobile: Optional[str]
    email: Optional[str]
    image_status: Optional[str]
    photo_base64: Optional[str]
    programme_id: int
    degree_id: int
    semester_number: int

    def __repr__(self) -> str:
        return (
            f"NormalizedStudentProfile(programme={self.programme!r}, "
            f"class_name={self.class_name!r}, "
            f"semester_number={self.semester_number}, "
            f"image_status={self.image_status!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class NormalizedRoomDetails:
    """
    Canonical representation of resident room allotment and faculty oversight.
    Date strings converted to datetime.date; identifiers preserved as integers.
    """
    hostel_name: str
    block_name: str
    hostel_id: int
    block_id: int
    room_type: str
    date_of_joining: Optional[date]
    floor_description: Optional[str]
    room_number: str
    warden_name: Optional[str]
    resident_tutor: Optional[str]

    def __repr__(self) -> str:
        return (
            f"NormalizedRoomDetails(hostel_name={self.hostel_name!r}, "
            f"block_name={self.block_name!r}, "
            f"room_number={self.room_number!r}, "
            f"room_type={self.room_type!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class NormalizedMessDetails:
    """
    Canonical representation of mess subscription and token authorizations.
    Removes server leading underscores and normalizes membership date to date.
    """
    mess_name: str
    mess_supervisor: Optional[str]
    mess_type: str
    member_since: Optional[date]
    egg_token_status: Optional[str]
    non_veg_token_status: Optional[str]

    def __repr__(self) -> str:
        return (
            f"NormalizedMessDetails(mess_name={self.mess_name!r}, "
            f"mess_type={self.mess_type!r}, "
            f"egg_token_status={self.egg_token_status!r}, "
            f"non_veg_token_status={self.non_veg_token_status!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class NormalizedFeesDetails:
    """
    Canonical representation of hostel fee balances.
    Monetary strings converted to precise Decimal representations.
    """
    hostel_fee_balance: Decimal
    caution_deposit: Decimal
    establishment_fee: Decimal
    mess_token_balance: Decimal

    def __repr__(self) -> str:
        return (
            f"NormalizedFeesDetails(balance={self.hostel_fee_balance}, "
            f"deposit={self.caution_deposit}, "
            f"establishment={self.establishment_fee}, "
            f"token={self.mess_token_balance})"
        )

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class NormalizedLeaveSummaryItem:
    """
    Canonical representation of allocated leave quotas.
    Quota string converted to integer.
    """
    leave_type: str
    allocated_days: int

    def __repr__(self) -> str:
        return f"NormalizedLeaveSummaryItem(type={self.leave_type!r}, days={self.allocated_days})"

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class NormalizedLeaveApproverItem:
    """
    Canonical representation of designated leave approval authority.
    """
    staff_id: str
    staff_name: str

    def __repr__(self) -> str:
        return f"NormalizedLeaveApproverItem(id={self.staff_id!r})"

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class NormalizedLeaveHistoryItem:
    """
    Canonical representation of submitted leave request record.
    Application dates converted to datetime.date.
    """
    from_date: date
    to_date: date
    leave_type: str
    reason: str
    status: str

    def __repr__(self) -> str:
        return (
            f"NormalizedLeaveHistoryItem(type={self.leave_type!r}, "
            f"status={self.status!r}, "
            f"from={self.from_date}, "
            f"to={self.to_date})"
        )

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class NormalizedAcademicYearItem:
    """
    Canonical representation of fee context processing year.
    Preserves academic year identifier and converts optional amount to Decimal.
    """
    academic_year: str
    amount: Optional[Decimal] = None

    def __repr__(self) -> str:
        return f"NormalizedAcademicYearItem(year={self.academic_year!r}, amount={self.amount})"

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class NormalizedHostelFeeDueItem:
    """
    Canonical representation of itemized hostel fee dues.
    Converts amount to Decimal and preserves facility and tariff identifiers.
    """
    reservation_status: Optional[str] = None
    amount: Optional[Decimal] = None
    hostel_name: Optional[str] = None
    block_name: Optional[str] = None
    tariff_id: Optional[str] = None
    hostel_id: Optional[int] = None

    def __repr__(self) -> str:
        return (
            f"NormalizedHostelFeeDueItem(hostel={self.hostel_name!r}, "
            f"block={self.block_name!r}, "
            f"amount={self.amount})"
        )

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class NormalizedHostelData:
    """
    Consolidated container for all normalized hostel domain datasets from an extraction run,
    retaining a reference to the source RawExtractionBundle for full audit lineage.
    """
    extraction_run_id: str
    extracted_at: str
    profile: Optional[NormalizedStudentProfile]
    room: Optional[NormalizedRoomDetails]
    mess: Optional[NormalizedMessDetails]
    fees: Optional[NormalizedFeesDetails]
    leave_summary: List[NormalizedLeaveSummaryItem] = field(default_factory=list)
    leave_approvers: List[NormalizedLeaveApproverItem] = field(default_factory=list)
    leave_history: List[NormalizedLeaveHistoryItem] = field(default_factory=list)
    academic_years: List[NormalizedAcademicYearItem] = field(default_factory=list)
    fee_dues: List[NormalizedHostelFeeDueItem] = field(default_factory=list)
    mess_bills: List[Any] = field(default_factory=list)
    transactions: List[Any] = field(default_factory=list)
    raw_bundle: Optional[RawExtractionBundle] = field(default=None, repr=False)

    def __repr__(self) -> str:
        has_prof = self.profile is not None
        has_room = self.room is not None
        has_mess = self.mess is not None
        has_fees = self.fees is not None
        return (
            f"NormalizedHostelData(run_id={self.extraction_run_id!r}, "
            f"profile={has_prof}, "
            f"room={has_room}, "
            f"mess={has_mess}, "
            f"fees={has_fees}, "
            f"leaves={len(self.leave_history)}, "
            f"approvers={len(self.leave_approvers)})"
        )

    def __str__(self) -> str:
        return self.__repr__()
