"""
Core exception hierarchy for Student Sync - Hostel subsystem.
"""


class HostelError(Exception):
    """Base exception for all Student Sync - Hostel subsystem errors."""
    pass


class ConfigurationError(HostelError):
    """Raised when configuration values are missing, invalid, or unreadable."""
    pass


class NetworkError(HostelError):
    """Raised when an HTTP, connection, or transport-level network error occurs."""
    pass


class TimeoutError(NetworkError):
    """Raised when an HTTP request exceeds the configured timeout threshold."""
    pass


class AuthenticationError(HostelError):
    """Raised when authentication fails (invalid credentials, dummy roll number, expired session)."""
    pass


class SchemaError(HostelError):
    """Raised when a server response body does not match the expected structural contract."""
    pass


class ResponseStatusError(SchemaError):
    """Raised when an HTTP response status code is not 200 OK."""
    pass


class ResponseContentTypeError(SchemaError):
    """Raised when a response Content-Type header does not indicate JSON."""
    pass


class ResponseRootTypeError(SchemaError):
    """Raised when the root JSON payload is not the expected type (e.g., list vs dict)."""
    pass


class MissingRequiredKeysError(SchemaError):
    """Raised when verified mandatory keys are absent from a response payload."""
    pass


class ParserError(HostelError):
    """Raised when parsing or extracting fields from a verified response payload fails."""
    pass


class ValidationError(HostelError):
    """Raised when domain business rules or cross-endpoint data integrity checks fail."""
    pass


class IdentityMismatchError(ValidationError):
    """Raised when student roll number does not match authenticated identity or cross-student leakage occurs."""
    pass


class FacilityConsistencyError(ValidationError):
    """Raised when facility IDs (hos_id, block_id) or room allocations violate domain integrity rules."""
    pass


class FinancialSanityError(ValidationError):
    """Raised when monetary amounts, deposits, or balances violate non-negativity or reasonable ranges."""
    pass


class TemporalIntegrityError(ValidationError):
    """Raised when dates or timestamps violate chronological order or validity."""
    pass


class MissingCriticalEndpointError(ValidationError):
    """Raised when a critical endpoint (profile or room) is missing or unpopulated."""
    pass


class NormalizationError(HostelError):
    """Raised when normalizing parsed domain data into canonical representations fails."""
    pass


class InvalidNormalizedTypeError(NormalizationError):
    """Raised when an unexpected or unsupported type is encountered during normalization."""
    pass


class InvalidDateFormatError(NormalizationError):
    """Raised when a date or datetime string cannot be parsed according to verified contract formats."""
    pass


class InvalidNumericFormatError(NormalizationError):
    """Raised when a numeric or monetary value cannot be parsed into Decimal or integer."""
    pass


class DatabaseError(HostelError):
    """Raised when database or repository persistence operations fail."""
    pass


class DatabaseNotConfiguredError(DatabaseError):
    """Raised when persistence operations are attempted without an active database configuration."""
    pass


