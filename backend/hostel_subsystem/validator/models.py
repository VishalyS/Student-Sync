"""
Validation Models for Student Sync - Hostel subsystem.
Provides strongly-typed, immutable structures for representing validation
findings, severities, categories, and audit summary results.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from core.exceptions import (
    FacilityConsistencyError,
    FinancialSanityError,
    IdentityMismatchError,
    MissingCriticalEndpointError,
    SchemaError,
    TemporalIntegrityError,
    ValidationError,
)


class ValidationSeverity(str, Enum):
    """Severity classification for validation findings."""
    VALID = "VALID"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL_ERROR = "CRITICAL_ERROR"
    INFO = "INFO"


class ValidationCategory(str, Enum):
    """Categorical classification for validation findings."""
    TRANSPORT = "TRANSPORT"
    SCHEMA = "SCHEMA"
    IDENTITY = "IDENTITY"
    FACILITY = "FACILITY"
    FINANCIAL = "FINANCIAL"
    TEMPORAL = "TEMPORAL"
    ORCHESTRATION = "ORCHESTRATION"


@dataclass(frozen=True)
class ValidationFinding:
    """
    Immutable representation of an individual validation finding.
    Designed with privacy-safe string representations preventing PII leakage.
    Provides standard fields: severity, domain, field, rule, message.
    """
    rule_name: str
    category: ValidationCategory
    severity: ValidationSeverity
    message: str
    endpoint_name: Optional[str] = None
    field_name: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    domain: Optional[str] = None
    field: Optional[str] = None
    rule: Optional[str] = None

    def __post_init__(self) -> None:
        """Ensure domain, field, and rule alias attributes are populated."""
        if self.domain is None and self.endpoint_name is not None:
            object.__setattr__(self, "domain", self.endpoint_name)
        if self.field is None and self.field_name is not None:
            object.__setattr__(self, "field", self.field_name)
        if self.rule is None and self.rule_name is not None:
            object.__setattr__(self, "rule", self.rule_name)

    def __repr__(self) -> str:
        return (
            f"ValidationFinding(rule={self.rule or self.rule_name!r}, "
            f"severity={self.severity.value}, "
            f"category={self.category.value}, "
            f"domain={self.domain or self.endpoint_name!r})"
        )

    def __str__(self) -> str:
        endpoint_str = f" [domain={self.domain or self.endpoint_name}]" if (self.domain or self.endpoint_name) else ""
        field_str = f" [field={self.field or self.field_name}]" if (self.field or self.field_name) else ""
        return (
            f"[{self.severity.value}][{self.category.value}] "
            f"{self.rule or self.rule_name}: {self.message}{endpoint_str}{field_str}"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert finding into a serializable dictionary."""
        return {
            "severity": self.severity.value,
            "domain": self.domain or self.endpoint_name,
            "field": self.field or self.field_name,
            "rule": self.rule or self.rule_name,
            "message": self.message,
            "rule_name": self.rule_name,
            "category": self.category.value,
            "endpoint_name": self.endpoint_name,
            "field_name": self.field_name,
            "context": self.context,
        }


@dataclass(frozen=True)
class ValidationResult:
    """
    Consolidated summary and container for all findings produced during a validation run.
    Provides diagnostic counts, error-raising helpers, and PII-masked representations.
    """
    is_valid: bool
    run_id: str
    target_roll_number: str
    findings: List[ValidationFinding] = field(default_factory=list)

    @property
    def critical_errors(self) -> List[ValidationFinding]:
        """Returns all findings with CRITICAL_ERROR severity."""
        return [f for f in self.findings if f.severity == ValidationSeverity.CRITICAL_ERROR]

    @property
    def errors(self) -> List[ValidationFinding]:
        """Returns all findings with ERROR or CRITICAL_ERROR severity."""
        return [
            f for f in self.findings
            if f.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL_ERROR)
        ]

    @property
    def warnings(self) -> List[ValidationFinding]:
        """Returns all findings with WARNING severity."""
        return [f for f in self.findings if f.severity == ValidationSeverity.WARNING]

    @property
    def infos(self) -> List[ValidationFinding]:
        """Returns all findings with INFO severity."""
        return [f for f in self.findings if f.severity == ValidationSeverity.INFO]

    @property
    def has_errors(self) -> bool:
        """True if any error or critical error findings exist."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """True if any warning findings exist."""
        return len(self.warnings) > 0

    def raise_for_errors(self) -> None:
        """
        Raises the most specific domain ValidationError if any ERROR findings exist.
        Prioritizes category-specific exceptions (IdentityMismatchError, etc.).
        """
        errors = self.errors
        if not errors:
            return

        first_err = errors[0]
        # Map category to specific exception type
        if first_err.category == ValidationCategory.IDENTITY:
            raise IdentityMismatchError(f"Identity validation failed: {first_err.message}")
        elif first_err.category == ValidationCategory.FACILITY:
            raise FacilityConsistencyError(f"Facility consistency violation: {first_err.message}")
        elif first_err.category == ValidationCategory.FINANCIAL:
            raise FinancialSanityError(f"Financial sanity violation: {first_err.message}")
        elif first_err.category == ValidationCategory.TEMPORAL:
            raise TemporalIntegrityError(f"Temporal integrity violation: {first_err.message}")
        elif first_err.category == ValidationCategory.ORCHESTRATION:
            if "CRITICAL" in first_err.rule_name or "MANDATORY" in first_err.rule_name:
                raise MissingCriticalEndpointError(f"Critical endpoint orchestration error: {first_err.message}")
            raise ValidationError(f"Orchestration validation failed: {first_err.message}")
        elif first_err.category in (ValidationCategory.SCHEMA, ValidationCategory.TRANSPORT):
            raise SchemaError(f"Schema validation failed: {first_err.message}")
        else:
            raise ValidationError(f"Validation failed: {first_err.message}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert result summary and findings into a dictionary with masked roll number."""
        masked_roll = (
            f"{self.target_roll_number[:2]}***"
            if len(self.target_roll_number) > 2
            else "***"
        )
        return {
            "is_valid": self.is_valid,
            "run_id": self.run_id,
            "target_roll_number": masked_roll,
            "total_findings": len(self.findings),
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "info_count": len(self.infos),
            "findings": [f.to_dict() for f in self.findings],
        }

    def __repr__(self) -> str:
        return (
            f"ValidationResult(is_valid={self.is_valid}, "
            f"run_id={self.run_id!r}, "
            f"errors={len(self.errors)}, "
            f"warnings={len(self.warnings)}, "
            f"infos={len(self.infos)})"
        )

    def __str__(self) -> str:
        return self.__repr__()
