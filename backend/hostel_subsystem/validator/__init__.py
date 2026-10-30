"""
Validation package for Student Sync - Hostel subsystem.
Exports Tier 1 (SchemaValidator), Tier 2 (IntegrityValidator), and unified
orchestrator (HostelValidationEngine) alongside validation models and categories.
"""
from core.exceptions import (
    FacilityConsistencyError,
    FinancialSanityError,
    IdentityMismatchError,
    MissingCriticalEndpointError,
    MissingRequiredKeysError,
    ResponseContentTypeError,
    ResponseRootTypeError,
    ResponseStatusError,
    TemporalIntegrityError,
    ValidationError,
)
from validator.engine import HostelValidationEngine
from validator.integrity_validator import IntegrityValidator
from validator.models import (
    ValidationCategory,
    ValidationFinding,
    ValidationResult,
    ValidationSeverity,
)
from validator.schema_validator import (
    REQUIRED_ENDPOINT_KEYS,
    SchemaValidator,
)

__all__ = [
    "HostelValidationEngine",
    "SchemaValidator",
    "IntegrityValidator",
    "REQUIRED_ENDPOINT_KEYS",
    "ValidationCategory",
    "ValidationFinding",
    "ValidationResult",
    "ValidationSeverity",
    "ValidationError",
    "IdentityMismatchError",
    "FacilityConsistencyError",
    "FinancialSanityError",
    "TemporalIntegrityError",
    "MissingCriticalEndpointError",
    "ResponseStatusError",
    "ResponseContentTypeError",
    "ResponseRootTypeError",
    "MissingRequiredKeysError",
]
