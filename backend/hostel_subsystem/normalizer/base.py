"""
Base normalization utilities and contract conversion helpers.
Strict, deterministic transformations for strings, numbers, dates, and placeholders.
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Set

from core.exceptions import (
    InvalidDateFormatError,
    InvalidNormalizedTypeError,
    InvalidNumericFormatError,
    NormalizationError,
)

# Canonical set of known portal placeholder strings
KNOWN_PLACEHOLDERS: Set[str] = {
    "not available",
    "na",
    "n/a",
    "nil",
    "null",
    "none",
    "-",
    "--",
}


def normalize_string(val: Optional[str]) -> Optional[str]:
    """
    Trim surrounding whitespace and convert empty strings or known placeholders to None.
    Preserves valid text unaltered.
    """
    if val is None:
        return None
    if not isinstance(val, str):
        raise InvalidNormalizedTypeError(f"Expected str or None, got {type(val).__name__}")
    
    cleaned = val.strip()
    if not cleaned or cleaned.lower() in KNOWN_PLACEHOLDERS:
        return None
    return cleaned


def normalize_required_string(val: Any, field_name: str) -> str:
    """
    Validate and trim a required string.
    Raises NormalizationError if None, empty, or a known placeholder.
    """
    if val is None:
        raise NormalizationError(f"Required field '{field_name}' cannot be None")
    if not isinstance(val, str):
        raise InvalidNormalizedTypeError(
            f"Field '{field_name}' must be str, got {type(val).__name__}"
        )
    
    cleaned = val.strip()
    if not cleaned or cleaned.lower() in KNOWN_PLACEHOLDERS:
        raise NormalizationError(
            f"Required field '{field_name}' cannot be empty or a placeholder (received {val!r})"
        )
    return cleaned


SUPPORTED_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d-%b-%y",
    "%d-%b-%Y",
)



def normalize_date(val: Optional[str], field_name: str) -> Optional[date]:
    """
    Convert an optional date string in ISO format 'YYYY-MM-DD' or server formats (e.g. 'DD-Mon-YY') into a date object.
    Returns None for empty strings, None, or placeholders.
    Raises InvalidDateFormatError for invalid date formats or impossible calendar dates.
    """
    if val is None:
        return None
    if isinstance(val, date):
        return val
    if not isinstance(val, str):
        raise InvalidNormalizedTypeError(
            f"Field '{field_name}' date must be str, got {type(val).__name__}"
        )
    
    cleaned = val.strip()
    if not cleaned or cleaned.lower() in KNOWN_PLACEHOLDERS:
        return None
    
    for fmt in SUPPORTED_DATE_FORMATS:
        for candidate in (cleaned, cleaned.title()):
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                pass

    raise InvalidDateFormatError(
        f"Field '{field_name}' date '{cleaned}' does not match any supported format (e.g. YYYY-MM-DD, DD-Mon-YY)"
    )



def normalize_required_date(val: Any, field_name: str) -> date:
    """
    Convert a required date string in ISO format 'YYYY-MM-DD' into a date object.
    Raises NormalizationError if None/empty/placeholder, or InvalidDateFormatError if malformed.
    """
    if val is None:
        raise NormalizationError(f"Required date field '{field_name}' cannot be None")
    
    parsed = normalize_date(val, field_name)
    if parsed is None:
        raise NormalizationError(
            f"Required date field '{field_name}' cannot be empty or a placeholder"
        )
    return parsed


def normalize_decimal(val: Any, field_name: str) -> Optional[Decimal]:
    """
    Convert numeric string or numeric value into Decimal without binary floating-point inaccuracy.
    Returns None for empty strings, None, or placeholders.
    Raises InvalidNumericFormatError if the string cannot be converted to Decimal.
    """
    if val is None:
        return None
    if isinstance(val, bool):
        raise InvalidNormalizedTypeError(
            f"Field '{field_name}' boolean value cannot be converted to Decimal"
        )
    if isinstance(val, Decimal):
        return val
    
    if isinstance(val, (int, float)):
        s = str(val)
    elif isinstance(val, str):
        s = val.strip()
        if not s or s.lower() in KNOWN_PLACEHOLDERS:
            return None
    else:
        raise InvalidNormalizedTypeError(
            f"Field '{field_name}' unsupported type for Decimal: {type(val).__name__}"
        )
    
    try:
        return Decimal(s)
    except InvalidOperation as e:
        raise InvalidNumericFormatError(
            f"Field '{field_name}' value '{s}' is not a valid decimal: {e}"
        ) from e


def normalize_required_decimal(val: Any, field_name: str) -> Decimal:
    """
    Convert required numeric string or numeric value into Decimal.
    Raises NormalizationError if None/empty/placeholder, or InvalidNumericFormatError if malformed.
    """
    if val is None:
        raise NormalizationError(f"Required decimal field '{field_name}' cannot be None")
    
    parsed = normalize_decimal(val, field_name)
    if parsed is None:
        raise NormalizationError(
            f"Required decimal field '{field_name}' cannot be empty or a placeholder"
        )
    return parsed


def normalize_integer(val: Any, field_name: str) -> int:
    """
    Convert string or int into a strictly validated integer.
    Rejects booleans to prevent Python bool-as-int coercion.
    Raises NormalizationError if empty/placeholder, or InvalidNumericFormatError if malformed.
    """
    if val is None:
        raise NormalizationError(f"Required integer field '{field_name}' cannot be None")
    if isinstance(val, bool):
        raise InvalidNormalizedTypeError(
            f"Field '{field_name}' boolean value cannot be normalized as integer"
        )
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        cleaned = val.strip()
        if not cleaned or cleaned.lower() in KNOWN_PLACEHOLDERS:
            raise NormalizationError(
                f"Required integer field '{field_name}' cannot be empty or placeholder"
            )
        try:
            return int(cleaned)
        except ValueError as e:
            raise InvalidNumericFormatError(
                f"Field '{field_name}' value '{cleaned}' is not a valid integer: {e}"
            ) from e
    
    raise InvalidNormalizedTypeError(
        f"Field '{field_name}' unsupported type for integer: {type(val).__name__}"
    )


def normalize_optional_integer(val: Any, field_name: str) -> Optional[int]:
    """
    Convert optional string or int into an integer or None.
    Returns None if None, empty, or placeholder.
    Rejects booleans.
    """
    if val is None:
        return None
    if isinstance(val, bool):
        raise InvalidNormalizedTypeError(
            f"Field '{field_name}' boolean value cannot be normalized as integer"
        )
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        cleaned = val.strip()
        if not cleaned or cleaned.lower() in KNOWN_PLACEHOLDERS:
            return None
        try:
            return int(cleaned)
        except ValueError as e:
            raise InvalidNumericFormatError(
                f"Field '{field_name}' value '{cleaned}' is not a valid integer: {e}"
            ) from e
    
    raise InvalidNormalizedTypeError(
        f"Field '{field_name}' unsupported type for integer: {type(val).__name__}"
    )
