"""
Tier 2: Domain Integrity & Cross-Endpoint Validation for Student Sync - Hostel subsystem.
Enforces resident identity invariants, facility configuration consistency, financial sanity,
chronological order on leaves, and full audit lineage.
"""
from decimal import Decimal
from typing import List, Optional

from core.exceptions import (
    FacilityConsistencyError,
    FinancialSanityError,
    IdentityMismatchError,
    MissingCriticalEndpointError,
    TemporalIntegrityError,
    ValidationError,
)
from normalizer.models import NormalizedHostelData
from validator.models import (
    ValidationCategory,
    ValidationFinding,
    ValidationSeverity,
)


class IntegrityValidator:
    """
    Tier 2 Domain Integrity & Business Rule Validator.
    Verifies NormalizedHostelData against domain invariants, preventing cross-student
    leakage, corrupted balances, invalid date spans, and orphaned facilities.
    """

    def validate(
        self,
        data: NormalizedHostelData,
        target_roll_number: str,
    ) -> List[ValidationFinding]:
        """
        Execute comprehensive Tier 2 domain integrity validations on normalized data.
        """
        findings: List[ValidationFinding] = []
        target_roll_clean = (target_roll_number or "").strip().upper()

        # ---------------------------------------------------------
        # 1. Identity Invariant & Cross-Student Isolation
        # ---------------------------------------------------------
        if not target_roll_clean:
            findings.append(
                ValidationFinding(
                    rule_name="AUTHENTICATED_ROLLNO_REQUIRED",
                    category=ValidationCategory.IDENTITY,
                    severity=ValidationSeverity.ERROR,
                    message="Target authenticated roll number is empty or blank",
                )
            )

        if data.profile is None:
            findings.append(
                ValidationFinding(
                    rule_name="MANDATORY_PROFILE_PRESENT",
                    category=ValidationCategory.IDENTITY,
                    severity=ValidationSeverity.ERROR,
                    message="Student profile is missing from normalized data; profile is mandatory",
                )
            )
        else:
            extracted_roll = data.profile.roll_number.strip().upper()
            if not extracted_roll:
                findings.append(
                    ValidationFinding(
                        rule_name="STUDENT_ROLL_NON_EMPTY",
                        category=ValidationCategory.IDENTITY,
                        severity=ValidationSeverity.ERROR,
                        message="Extracted student roll number is blank",
                    )
                )
            elif extracted_roll != target_roll_clean:
                # CRITICAL: Cross-student data corruption protection
                findings.append(
                    ValidationFinding(
                        rule_name="IDENTITY_ROLL_MISMATCH",
                        category=ValidationCategory.IDENTITY,
                        severity=ValidationSeverity.ERROR,
                        message=(
                            f"Identity mismatch detected: extracted roll number does not match "
                            f"authenticated roll number"
                        ),
                        context={"extracted_roll_prefix": extracted_roll[:2], "target_roll_prefix": target_roll_clean[:2]},
                    )
                )

            if not data.profile.name or not data.profile.name.strip():
                findings.append(
                    ValidationFinding(
                        rule_name="STUDENT_NAME_NON_EMPTY",
                        category=ValidationCategory.IDENTITY,
                        severity=ValidationSeverity.ERROR,
                        message="Student profile has empty name",
                    )
                )

        # ---------------------------------------------------------
        # 2. Facility Consistency & Room Allocation
        # ---------------------------------------------------------
        if data.room is not None:
            # Positive facility and block identifiers
            if data.room.hostel_id <= 0:
                findings.append(
                    ValidationFinding(
                        rule_name="FACILITY_HOSTEL_ID_POSITIVE",
                        category=ValidationCategory.FACILITY,
                        severity=ValidationSeverity.ERROR,
                        message=f"Hostel ID must be a positive integer, got {data.room.hostel_id}",
                        field_name="hostel_id",
                    )
                )

            if data.room.block_id <= 0:
                findings.append(
                    ValidationFinding(
                        rule_name="FACILITY_BLOCK_ID_POSITIVE",
                        category=ValidationCategory.FACILITY,
                        severity=ValidationSeverity.ERROR,
                        message=f"Block ID must be a positive integer, got {data.room.block_id}",
                        field_name="block_id",
                    )
                )

            if not data.room.hostel_name or not data.room.hostel_name.strip():
                findings.append(
                    ValidationFinding(
                        rule_name="HOSTEL_NAME_NON_EMPTY",
                        category=ValidationCategory.FACILITY,
                        severity=ValidationSeverity.ERROR,
                        message="Allocated room has empty hostel name",
                        field_name="hostel_name",
                    )
                )

            if not data.room.block_name or not data.room.block_name.strip():
                findings.append(
                    ValidationFinding(
                        rule_name="BLOCK_NAME_NON_EMPTY",
                        category=ValidationCategory.FACILITY,
                        severity=ValidationSeverity.ERROR,
                        message="Allocated room has empty block name",
                        field_name="block_name",
                    )
                )

            if not data.room.room_number or not data.room.room_number.strip():
                findings.append(
                    ValidationFinding(
                        rule_name="ROOM_NUMBER_NON_EMPTY",
                        category=ValidationCategory.FACILITY,
                        severity=ValidationSeverity.ERROR,
                        message="Allocated room has empty room number",
                        field_name="room_number",
                    )
                )
        else:
            findings.append(
                ValidationFinding(
                    rule_name="ROOM_ALLOCATION_STATUS",
                    category=ValidationCategory.FACILITY,
                    severity=ValidationSeverity.INFO,
                    message="Resident currently has no allocated room (unallocated/day scholar)",
                )
            )

        # Itemized fee dues facility validation
        for idx, due in enumerate(data.fee_dues):
            if due.hostel_id is not None and due.hostel_id <= 0:
                findings.append(
                    ValidationFinding(
                        rule_name="FEE_DUE_HOSTEL_ID_POSITIVE",
                        category=ValidationCategory.FACILITY,
                        severity=ValidationSeverity.ERROR,
                        message=f"Fee due at index {idx} has invalid hostel_id: {due.hostel_id}",
                        field_name="hostel_id",
                    )
                )

        # ---------------------------------------------------------
        # 3. Financial Sanity
        # ---------------------------------------------------------
        if data.fees is not None:
            if data.fees.caution_deposit < Decimal("0.00"):
                findings.append(
                    ValidationFinding(
                        rule_name="CAUTION_DEPOSIT_NON_NEGATIVE",
                        category=ValidationCategory.FINANCIAL,
                        severity=ValidationSeverity.ERROR,
                        message=f"Caution deposit cannot be negative, got {data.fees.caution_deposit}",
                        field_name="caution_deposit",
                    )
                )

            if data.fees.establishment_fee < Decimal("0.00"):
                findings.append(
                    ValidationFinding(
                        rule_name="ESTABLISHMENT_FEE_NON_NEGATIVE",
                        category=ValidationCategory.FINANCIAL,
                        severity=ValidationSeverity.ERROR,
                        message=f"Establishment fee cannot be negative, got {data.fees.establishment_fee}",
                        field_name="establishment_fee",
                    )
                )

            if data.fees.mess_token_balance < Decimal("0.00"):
                findings.append(
                    ValidationFinding(
                        rule_name="TOKEN_BALANCE_NON_NEGATIVE",
                        category=ValidationCategory.FINANCIAL,
                        severity=ValidationSeverity.WARNING,
                        message=f"Mess token balance is negative: {data.fees.mess_token_balance}",
                        field_name="mess_token_balance",
                    )
                )

        # Fee due items non-negative
        for idx, due in enumerate(data.fee_dues):
            if due.amount is not None and due.amount < Decimal("0.00"):
                findings.append(
                    ValidationFinding(
                        rule_name="FEE_DUE_AMOUNT_NON_NEGATIVE",
                        category=ValidationCategory.FINANCIAL,
                        severity=ValidationSeverity.ERROR,
                        message=f"Fee due amount at index {idx} cannot be negative: {due.amount}",
                        field_name="amount",
                    )
                )

        # Academic year amounts non-negative
        for idx, ay in enumerate(data.academic_years):
            if ay.amount is not None and ay.amount < Decimal("0.00"):
                findings.append(
                    ValidationFinding(
                        rule_name="ACADEMIC_YEAR_AMOUNT_NON_NEGATIVE",
                        category=ValidationCategory.FINANCIAL,
                        severity=ValidationSeverity.ERROR,
                        message=f"Academic year amount at index {idx} cannot be negative: {ay.amount}",
                        field_name="amount",
                    )
                )

        # ---------------------------------------------------------
        # 4. Temporal Integrity
        # ---------------------------------------------------------
        for idx, leave in enumerate(data.leave_history):
            if leave.from_date > leave.to_date:
                findings.append(
                    ValidationFinding(
                        rule_name="LEAVE_DATE_CHRONOLOGICAL",
                        category=ValidationCategory.TEMPORAL,
                        severity=ValidationSeverity.ERROR,
                        message=(
                            f"Leave history record at index {idx} has from_date ({leave.from_date}) "
                            f"after to_date ({leave.to_date})"
                        ),
                        context={"from_date": str(leave.from_date), "to_date": str(leave.to_date)},
                    )
                )

        for idx, quota in enumerate(data.leave_summary):
            if quota.allocated_days < 0:
                findings.append(
                    ValidationFinding(
                        rule_name="LEAVE_QUOTA_NON_NEGATIVE",
                        category=ValidationCategory.TEMPORAL,
                        severity=ValidationSeverity.ERROR,
                        message=(
                            f"Leave quota at index {idx} ({quota.leave_type}) has negative allocated days: "
                            f"{quota.allocated_days}"
                        ),
                    )
                )

        if not data.extracted_at or not data.extracted_at.strip():
            findings.append(
                ValidationFinding(
                    rule_name="EXTRACTION_TIMESTAMP_NON_EMPTY",
                    category=ValidationCategory.TEMPORAL,
                    severity=ValidationSeverity.ERROR,
                    message="Extracted timestamp is missing or empty",
                )
            )

        # ---------------------------------------------------------
        # 5. Mess & Approver Integrity
        # ---------------------------------------------------------
        if data.mess is not None:
            if not data.mess.mess_name or not data.mess.mess_name.strip():
                findings.append(
                    ValidationFinding(
                        rule_name="MESS_NAME_NON_EMPTY",
                        category=ValidationCategory.SCHEMA,
                        severity=ValidationSeverity.ERROR,
                        message="Allocated mess has empty mess name",
                        field_name="mess_name",
                    )
                )
            if not data.mess.mess_type or not data.mess.mess_type.strip():
                findings.append(
                    ValidationFinding(
                        rule_name="MESS_TYPE_NON_EMPTY",
                        category=ValidationCategory.SCHEMA,
                        severity=ValidationSeverity.ERROR,
                        message="Allocated mess has empty mess type",
                        field_name="mess_type",
                    )
                )

        for idx, approver in enumerate(data.leave_approvers):
            if not approver.staff_id or not approver.staff_id.strip():
                findings.append(
                    ValidationFinding(
                        rule_name="APPROVER_STAFF_ID_NON_EMPTY",
                        category=ValidationCategory.SCHEMA,
                        severity=ValidationSeverity.ERROR,
                        message=f"Leave approver at index {idx} has empty staff_id",
                    )
                )
            if not approver.staff_name or not approver.staff_name.strip():
                findings.append(
                    ValidationFinding(
                        rule_name="APPROVER_STAFF_NAME_NON_EMPTY",
                        category=ValidationCategory.SCHEMA,
                        severity=ValidationSeverity.ERROR,
                        message=f"Leave approver at index {idx} has empty staff_name",
                    )
                )

        # ---------------------------------------------------------
        # 6. Lineage & Traceability
        # ---------------------------------------------------------
        if not data.extraction_run_id or not data.extraction_run_id.strip():
            findings.append(
                ValidationFinding(
                    rule_name="EXTRACTION_RUN_ID_NON_EMPTY",
                    category=ValidationCategory.ORCHESTRATION,
                    severity=ValidationSeverity.ERROR,
                    message="Extraction run_id is missing or empty",
                )
            )

        if data.raw_bundle is not None:
            if data.raw_bundle.run_id != data.extraction_run_id:
                findings.append(
                    ValidationFinding(
                        rule_name="LINEAGE_RUN_ID_MATCH",
                        category=ValidationCategory.ORCHESTRATION,
                        severity=ValidationSeverity.ERROR,
                        message=(
                            f"Lineage broken: Normalized data run_id '{data.extraction_run_id}' "
                            f"does not match attached raw bundle run_id '{data.raw_bundle.run_id}'"
                        ),
                    )
                )

            bundle_roll_val = getattr(data.raw_bundle, "student_roll_number", None) or getattr(data.raw_bundle, "roll_number", None)
            if bundle_roll_val:
                bundle_roll = str(bundle_roll_val).strip().upper()
                if bundle_roll != target_roll_clean:
                    findings.append(
                        ValidationFinding(
                            rule_name="LINEAGE_ROLL_MATCH",
                            category=ValidationCategory.IDENTITY,
                            severity=ValidationSeverity.ERROR,
                            message="Raw bundle roll number does not match target roll number",
                        )
                    )

        return findings


    def assert_integrity(
        self,
        data: NormalizedHostelData,
        target_roll_number: str,
    ) -> None:
        """
        Strictly assert domain integrity. Raises the most specific ValidationError subclass
        if any ERROR-level findings exist.
        """
        findings = self.validate(data, target_roll_number)
        errors = [f for f in findings if f.severity == ValidationSeverity.ERROR]
        if not errors:
            return

        first = errors[0]
        if first.category == ValidationCategory.IDENTITY:
            raise IdentityMismatchError(first.message)
        elif first.category == ValidationCategory.FACILITY:
            raise FacilityConsistencyError(first.message)
        elif first.category == ValidationCategory.FINANCIAL:
            raise FinancialSanityError(first.message)
        elif first.category == ValidationCategory.TEMPORAL:
            raise TemporalIntegrityError(first.message)
        elif first.category == ValidationCategory.ORCHESTRATION:
            if "MANDATORY" in first.rule_name or "CRITICAL" in first.rule_name:
                raise MissingCriticalEndpointError(first.message)
            raise ValidationError(first.message)
        else:
            raise ValidationError(first.message)
