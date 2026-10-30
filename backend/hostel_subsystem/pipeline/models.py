"""
Pipeline models for Student Sync - Hostel subsystem.
Provides strongly-typed, immutable execution results and status classifications
for end-to-end extraction cycles.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from normalizer.models import NormalizedHostelData
from parser.models import ParsedHostelData
from scraper.raw import RawExtractionBundle
from validator.models import ValidationResult


class PipelineStatus(str, Enum):
    """
    Execution status classifications for an end-to-end pipeline run.
    """
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"


@dataclass(frozen=True)
class HostelPipelineResult:
    """
    Immutable comprehensive result container for an end-to-end extraction pipeline cycle.
    Preserves complete lineage from raw evidence through domain parsing, normalization,
    and two-tier validation.
    Personal identifiers are unconditionally masked in representations and serialized exports.
    """
    status: PipelineStatus
    run_id: str
    extracted_at: str
    target_roll_number: str
    raw_bundle: Optional[RawExtractionBundle] = field(default=None, repr=False)
    parsed_data: Optional[ParsedHostelData] = field(default=None, repr=False)
    normalized_data: Optional[NormalizedHostelData] = field(default=None, repr=False)
    validation_result: Optional[ValidationResult] = field(default=None, repr=False)
    execution_time_seconds: float = 0.0
    error_message: Optional[str] = None

    @property
    def is_success(self) -> bool:
        """True if pipeline execution succeeded completely or with non-critical warnings."""
        return self.status in (PipelineStatus.SUCCESS, PipelineStatus.PARTIAL_SUCCESS)

    @property
    def is_valid(self) -> bool:
        """True if validation completed and discovered zero error-severity findings."""
        return self.validation_result.is_valid if self.validation_result else False

    @property
    def endpoints_count(self) -> int:
        """Total number of endpoints captured in raw evidence."""
        return len(self.raw_bundle.responses) if self.raw_bundle else 0

    @property
    def error_count(self) -> int:
        """Total number of validation errors encountered."""
        return len(self.validation_result.errors) if self.validation_result else (1 if not self.is_success else 0)

    @property
    def warning_count(self) -> int:
        """Total number of validation warnings encountered."""
        return len(self.validation_result.warnings) if self.validation_result else 0

    def to_extraction_result(self) -> "ExtractionResult":
        """Convert pipeline execution result into canonical ExtractionResult."""
        return ExtractionResult.from_pipeline_result(self)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize pipeline execution summary into a JSON-compatible dictionary.
        Strictly masks student roll number and excludes sensitive PII fields.
        """
        masked_roll = (
            f"{self.target_roll_number[:2]}***"
            if len(self.target_roll_number) > 2
            else "***"
        )
        return {
            "status": self.status.value,
            "run_id": self.run_id,
            "target_roll_number": masked_roll,
            "extracted_at": self.extracted_at,
            "execution_time_seconds": round(self.execution_time_seconds, 3),
            "is_success": self.is_success,
            "is_valid": self.is_valid,
            "endpoints_extracted": self.endpoints_count,
            "validation_summary": self.validation_result.to_dict() if self.validation_result else None,
            "error_message": self.error_message,
        }

    def __repr__(self) -> str:
        return (
            f"HostelPipelineResult(status={self.status.value}, "
            f"run_id={self.run_id!r}, "
            f"endpoints={self.endpoints_count}, "
            f"is_valid={self.is_valid}, "
            f"duration={self.execution_time_seconds:.2f}s)"
        )

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class ExtractionResult:
    """
    Authoritative, stable top-level extraction result for the Student Sync - Hostel subsystem.
    Contains structured, normalized data for all 9 hostel domains, audit metadata,
    and two-tier validation summaries.
    Maintains clean separation from raw network artifacts while keeping raw lineage accessible.
    Strictly excludes all credentials, authorization headers, cookies, and tokens.
    """
    run_id: str
    timestamp: str
    status: str
    student: Optional[Dict[str, Any]] = None
    room: Optional[Dict[str, Any]] = None
    mess: Optional[Dict[str, Any]] = None
    fees: Optional[Dict[str, Any]] = None
    leave: Optional[Dict[str, Any]] = None
    academic_year: Optional[List[Dict[str, Any]]] = None
    fee_due: Optional[List[Dict[str, Any]]] = None
    mess_bills: Optional[List[Dict[str, Any]]] = None
    transactions: Optional[List[Dict[str, Any]]] = None
    validation: Optional[Dict[str, Any]] = None
    source_metadata: Dict[str, Any] = field(default_factory=dict)
    raw_bundle: Optional[RawExtractionBundle] = field(default=None, repr=False)

    @property
    def is_success(self) -> bool:
        """True if extraction succeeded completely or with non-critical warnings."""
        return self.status in ("SUCCESS", "PARTIAL_SUCCESS")

    @property
    def is_valid(self) -> bool:
        """True if validation concluded without errors."""
        if not self.validation:
            return False
        return self.validation.get("is_valid", False)

    @property
    def endpoints_count(self) -> int:
        """Count of endpoints present in source metadata or raw bundle."""
        if "endpoints_count" in self.source_metadata:
            return int(self.source_metadata["endpoints_count"])
        return len(self.raw_bundle.responses) if self.raw_bundle else 0

    def to_dict(self, mask_pii: bool = False) -> Dict[str, Any]:
        """
        Serialize extraction result into a pure JSON-serializable dictionary.
        Optionally masks student roll number.
        """
        student_data = self.student
        if mask_pii and student_data and "roll_number" in student_data:
            rn = student_data.get("roll_number", "")
            masked_rn = f"{rn[:2]}***" if len(rn) > 2 else "***"
            student_data = dict(student_data)
            student_data["roll_number"] = masked_rn

        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "status": self.status,
            "student": student_data,
            "room": self.room,
            "mess": self.mess,
            "fees": self.fees,
            "leave": self.leave,
            "academic_year": self.academic_year,
            "fee_due": self.fee_due,
            "mess_bills": self.mess_bills or [],
            "transactions": self.transactions or [],
            "validation": self.validation,
            "source_metadata": self.source_metadata,
        }

    @classmethod
    def from_pipeline_result(cls, pipeline_result: HostelPipelineResult) -> "ExtractionResult":
        """
        Factory method constructing an ExtractionResult from an executed HostelPipelineResult.
        Lineage to raw bundle is preserved in memory while serializable representations are generated.
        """
        nd = pipeline_result.normalized_data

        student_dict: Optional[Dict[str, Any]] = None
        room_dict: Optional[Dict[str, Any]] = None
        mess_dict: Optional[Dict[str, Any]] = None
        fees_dict: Optional[Dict[str, Any]] = None
        leave_dict: Optional[Dict[str, Any]] = None
        academic_years_list: Optional[List[Dict[str, Any]]] = None
        fee_dues_list: Optional[List[Dict[str, Any]]] = None

        if nd is not None:
            if nd.profile:
                student_dict = {
                    "name": nd.profile.name,
                    "roll_number": nd.profile.roll_number,
                    "degree_roll_number": nd.profile.degree_roll_number,
                    "mobile_number": nd.profile.mobile_number,
                    "programme": nd.profile.programme,
                    "class_name": nd.profile.class_name,
                    "father_name": nd.profile.father_name,
                    "mother_name": nd.profile.mother_name,
                    "address": nd.profile.address,
                    "district_name": nd.profile.district_name,
                    "state_name": nd.profile.state_name,
                    "father_mobile": nd.profile.father_mobile,
                    "mother_mobile": nd.profile.mother_mobile,
                    "email": nd.profile.email,
                    "image_status": nd.profile.image_status,
                    "photo_base64": nd.profile.photo_base64,
                    "programme_id": nd.profile.programme_id,
                    "degree_id": nd.profile.degree_id,
                    "semester_number": nd.profile.semester_number,
                }

            if nd.room:
                room_dict = {
                    "hostel_name": nd.room.hostel_name,
                    "block_name": nd.room.block_name,
                    "hostel_id": nd.room.hostel_id,
                    "block_id": nd.room.block_id,
                    "room_type": nd.room.room_type,
                    "date_of_joining": nd.room.date_of_joining.isoformat() if nd.room.date_of_joining else None,
                    "floor_description": nd.room.floor_description,
                    "room_number": nd.room.room_number,
                    "warden_name": nd.room.warden_name,
                    "resident_tutor": nd.room.resident_tutor,
                }

            if nd.mess:
                mess_dict = {
                    "mess_name": nd.mess.mess_name,
                    "mess_supervisor": nd.mess.mess_supervisor,
                    "mess_type": nd.mess.mess_type,
                    "member_since": nd.mess.member_since.isoformat() if nd.mess.member_since else None,
                    "egg_token_status": nd.mess.egg_token_status,
                    "non_veg_token_status": nd.mess.non_veg_token_status,
                }

            if nd.fees:
                fees_dict = {
                    "hostel_fee_balance": str(nd.fees.hostel_fee_balance),
                    "caution_deposit": str(nd.fees.caution_deposit),
                    "establishment_fee": str(nd.fees.establishment_fee),
                    "mess_token_balance": str(nd.fees.mess_token_balance),
                }

            leave_dict = {
                "summary": [
                    {"leave_type": item.leave_type, "allocated_days": item.allocated_days}
                    for item in nd.leave_summary
                ],
                "approvers": [
                    {"staff_id": item.staff_id, "staff_name": item.staff_name}
                    for item in nd.leave_approvers
                ],
                "history": [
                    {
                        "from_date": item.from_date.isoformat(),
                        "to_date": item.to_date.isoformat(),
                        "leave_type": item.leave_type,
                        "reason": item.reason,
                        "status": item.status,
                    }
                    for item in nd.leave_history
                ],
            }

            academic_years_list = [
                {
                    "academic_year": item.academic_year,
                    "amount": str(item.amount) if item.amount is not None else None,
                }
                for item in nd.academic_years
            ]

            fee_dues_list = [
                {
                    "reservation_status": item.reservation_status,
                    "amount": str(item.amount) if item.amount is not None else None,
                    "hostel_name": item.hostel_name,
                    "block_name": item.block_name,
                    "tariff_id": item.tariff_id,
                    "hostel_id": item.hostel_id,
                }
                for item in nd.fee_dues
            ]

        mess_bills_list = [
            item.to_dict() if hasattr(item, "to_dict") else item
            for item in getattr(nd, "mess_bills", [])
        ] if nd else []

        transactions_list = [
            item.to_dict() if hasattr(item, "to_dict") else item
            for item in getattr(nd, "transactions", [])
        ] if nd else []

        # Privacy-safe source metadata
        raw_bundle = pipeline_result.raw_bundle
        roll = pipeline_result.target_roll_number
        masked_roll = f"{roll[:2]}***" if len(roll) > 2 else "***"

        source_meta: Dict[str, Any] = {
            "target_roll_number_masked": masked_roll,
            "execution_time_seconds": round(pipeline_result.execution_time_seconds, 3),
            "endpoints_extracted": list(raw_bundle.responses.keys()) if raw_bundle else [],
            "endpoints_count": pipeline_result.endpoints_count,
            "payload_hashes": {k: getattr(v, "payload_hash", getattr(v, "sha256_hash", "")) for k, v in raw_bundle.responses.items()} if raw_bundle else {},
            "error_message": pipeline_result.error_message,
        }

        val_dict = pipeline_result.validation_result.to_dict() if pipeline_result.validation_result else None

        return cls(
            run_id=pipeline_result.run_id,
            timestamp=pipeline_result.extracted_at,
            status=pipeline_result.status.value,
            student=student_dict,
            room=room_dict,
            mess=mess_dict,
            fees=fees_dict,
            leave=leave_dict,
            academic_year=academic_years_list,
            fee_due=fee_dues_list,
            mess_bills=mess_bills_list,
            transactions=transactions_list,
            validation=val_dict,
            source_metadata=source_meta,
            raw_bundle=raw_bundle,
        )
