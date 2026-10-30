"""
Validation Engine for Student Sync - Hostel subsystem.
Unifies Tier 1 (Schema & Transport) and Tier 2 (Domain Integrity) validation
into a consolidated execution interface producing comprehensive ValidationResult audits.
"""
from typing import List, Optional

from normalizer.models import NormalizedHostelData
from scraper.raw import RawExtractionBundle
from validator.integrity_validator import IntegrityValidator
from validator.models import ValidationFinding, ValidationResult
from validator.schema_validator import SchemaValidator


class HostelValidationEngine:
    """
    Unified validation orchestrator.
    Executes Tier 1 schema/transport verification and Tier 2 domain integrity checks,
    producing an immutable, privacy-safe ValidationResult audit bundle.
    """

    def __init__(self) -> None:
        self.schema_validator = SchemaValidator()
        self.integrity_validator = IntegrityValidator()

    def validate(
        self,
        data: NormalizedHostelData,
        target_roll_number: str,
        raw_bundle: Optional[RawExtractionBundle] = None,
    ) -> ValidationResult:
        """
        Execute full two-tier validation on normalized data and its raw evidence bundle.
        Returns a complete ValidationResult without raising exceptions.
        """
        all_findings: List[ValidationFinding] = []

        # 1. Tier 1: Schema & Response Validation (if raw bundle is available)
        active_bundle = raw_bundle or data.raw_bundle
        if active_bundle is not None:
            tier1_findings = self.schema_validator.validate_bundle(active_bundle)
            all_findings.extend(tier1_findings)

        # 2. Tier 2: Domain Integrity & Business Invariants Validation
        tier2_findings = self.integrity_validator.validate(data, target_roll_number)
        all_findings.extend(tier2_findings)

        # Check if any error severity findings exist
        has_errors = any(f.severity.value == "ERROR" for f in all_findings)

        return ValidationResult(
            is_valid=not has_errors,
            run_id=data.extraction_run_id,
            target_roll_number=target_roll_number,
            findings=all_findings,
        )

    def validate_and_assert(
        self,
        data: NormalizedHostelData,
        target_roll_number: str,
        raw_bundle: Optional[RawExtractionBundle] = None,
    ) -> ValidationResult:
        """
        Execute full validation and immediately raise the corresponding domain exception
        if any ERROR-severity findings are detected.
        """
        result = self.validate(
            data=data,
            target_roll_number=target_roll_number,
            raw_bundle=raw_bundle,
        )
        result.raise_for_errors()
        return result

    # Convenience delegator methods
    def validate_bundle(self, bundle: RawExtractionBundle) -> List[ValidationFinding]:
        """Convenience method to execute Tier 1 validation on a RawExtractionBundle alone."""
        return self.schema_validator.validate_bundle(bundle)

    def validate_integrity(
        self,
        data: NormalizedHostelData,
        target_roll_number: str,
    ) -> List[ValidationFinding]:
        """Convenience method to execute Tier 2 integrity validation on NormalizedHostelData alone."""
        return self.integrity_validator.validate(data, target_roll_number)
