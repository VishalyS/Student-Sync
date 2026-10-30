"""
Source Domain Models for Student Sync - Hostel subsystem.
Frozen dataclasses preserving exact server keys, structures, and data types
without premature normalization or field mutation.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from scraper.raw import RawExtractionBundle


@dataclass(frozen=True)
class SourceStudentProfile:
    """
    Parsed representation of /Hostel/Student/studDetails payload.
    Preserves exact source field names, types, and placeholder values.
    """
    name: str
    rollno: str
    drollno: str
    mobile: str
    programme: str
    class_: str
    father: str
    mother: Optional[str]
    addr: str
    districtName: str
    stateName: str
    fmobile: str
    mmobile: str
    email: str
    imgStatus: str
    StudPic: str
    progId: int
    degreeId: int
    semNo: int

    def __repr__(self) -> str:
        return (
            f"SourceStudentProfile(programme={self.programme!r}, "
            f"class_={self.class_!r}, "
            f"semNo={self.semNo}, "
            f"imgStatus={self.imgStatus!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class SourceRoomDetails:
    """
    Parsed representation of /Hostel/Student/roomDetails payload.
    Preserves facility identifiers, block, room, and warden assignments.
    """
    hostel: str
    block: str
    hos_id: int
    block_id: int
    room_type: str
    doj: str
    floor_room: str
    room: str
    warden: str
    restutor: str

    def __repr__(self) -> str:
        return (
            f"SourceRoomDetails(hostel={self.hostel!r}, "
            f"block={self.block!r}, "
            f"room={self.room!r}, "
            f"room_type={self.room_type!r}, "
            f"floor={self.floor_room!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class SourceMessDetails:
    """
    Parsed representation of /Hostel/Student/StudMessDet payload.
    Preserves exact ASP.NET leading-underscore server keys.
    """
    _MessName: str
    _MessSupervisor: str
    _MessType: str
    _MessMemberSince: str
    _MessEggToken: str
    _MessNvToken: str

    def __repr__(self) -> str:
        return (
            f"SourceMessDetails(_MessName={self._MessName!r}, "
            f"_MessType={self._MessType!r}, "
            f"_MessEggToken={self._MessEggToken!r}, "
            f"_MessNvToken={self._MessNvToken!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class SourceFeesDetails:
    """
    Parsed representation of /Hostel/Student/StudHosFeesDet payload.
    Preserves monetary balance strings as verbatim decimals without float coercion.
    """
    _HosFeesBalance: str
    _HosFeesDeposit: str
    _HosFeesEstab: str
    _TokenBalance: str

    def __repr__(self) -> str:
        return (
            f"SourceFeesDetails(_HosFeesBalance={self._HosFeesBalance!r}, "
            f"_HosFeesDeposit={self._HosFeesDeposit!r}, "
            f"_HosFeesEstab={self._HosFeesEstab!r}, "
            f"_TokenBalance={self._TokenBalance!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class SourceLeaveSummaryItem:
    """
    Parsed representation of an individual item in /Hostel/Student/StudLeaveS.
    """
    leave_type: str
    leave: str

    def __repr__(self) -> str:
        return f"SourceLeaveSummaryItem(type={self.leave_type!r}, days={self.leave!r})"

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class SourceLeaveApproverItem:
    """
    Parsed representation of an individual item in /Hostel/Student/StudApprMngr.
    """
    staff_id: str
    staff_name: str

    def __repr__(self) -> str:
        return f"SourceLeaveApproverItem(id={self.staff_id!r})"

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class SourceLeaveHistoryItem:
    """
    Parsed representation of an individual item in /Hostel/Student/StudentGetLeav.
    """
    fromdate: str
    todate: str
    leave_type: str
    reason: str
    status: str

    def __repr__(self) -> str:
        return (
            f"SourceLeaveHistoryItem(type={self.leave_type!r}, "
            f"status={self.status!r}, "
            f"from={self.fromdate!r}, "
            f"to={self.todate!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class SourceAcademicYearItem:
    """
    Parsed representation of an individual item in /Hostel/Student/GetYear.
    """
    proc_year: str
    amt: Optional[str] = None

    def __repr__(self) -> str:
        return f"SourceAcademicYearItem(year={self.proc_year!r}, amt={self.amt!r})"

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class SourceHostelFeeDueItem:
    """
    Parsed representation of an individual item in /Hostel/Student/GetHosFee.
    """
    res: Optional[str] = None
    amount: Optional[str] = None
    hostel_name: Optional[str] = None
    block_name: Optional[str] = None
    tariff_id: Optional[str] = None
    hos_id: Optional[int] = None

    def __repr__(self) -> str:
        return (
            f"SourceHostelFeeDueItem(hostel={self.hostel_name!r}, "
            f"block={self.block_name!r}, "
            f"amount={self.amount!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class ParsedHostelData:
    """
    Comprehensive immutable container consolidating all parsed source domain records
    from an extraction cycle, retaining a reference to the pristine raw extraction bundle.
    """
    extraction_run_id: str
    extracted_at: str
    profile: Optional[SourceStudentProfile]
    room: Optional[SourceRoomDetails]
    mess: Optional[SourceMessDetails]
    fees: Optional[SourceFeesDetails]
    leave_summary: List[SourceLeaveSummaryItem] = field(default_factory=list)
    leave_approvers: List[SourceLeaveApproverItem] = field(default_factory=list)
    leave_history: List[SourceLeaveHistoryItem] = field(default_factory=list)
    academic_years: List[SourceAcademicYearItem] = field(default_factory=list)
    fee_dues: List[SourceHostelFeeDueItem] = field(default_factory=list)
    mess_bills: List[Any] = field(default_factory=list)
    transactions: List[Any] = field(default_factory=list)
    raw_bundle: Optional[RawExtractionBundle] = field(default=None, repr=False)

    def __repr__(self) -> str:
        has_prof = self.profile is not None
        has_room = self.room is not None
        has_mess = self.mess is not None
        has_fees = self.fees is not None
        return (
            f"ParsedHostelData(run_id={self.extraction_run_id!r}, "
            f"profile={has_prof}, "
            f"room={has_room}, "
            f"mess={has_mess}, "
            f"fees={has_fees}, "
            f"leaves={len(self.leave_history)}, "
            f"approvers={len(self.leave_approvers)})"
        )

    def __str__(self) -> str:
        return self.__repr__()
