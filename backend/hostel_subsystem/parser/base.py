"""
Abstract base parser interface and validation utilities for Student Sync - Hostel subsystem.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

from core.exceptions import ParserError
from scraper.raw import RawResponseRecord


class BaseDomainParser(ABC):
    """
    Abstract interface for endpoint-specific domain parsers.
    Parsers are strictly local transformations with zero network access.
    """

    @abstractmethod
    def parse(self, raw_data: Any) -> Any:
        """Parse raw response data or RawResponseRecord into typed domain model."""
        pass

    @staticmethod
    def extract_payload(input_data: Any) -> Any:
        """Extract underlying payload from a RawResponseRecord or return data as-is."""
        if isinstance(input_data, RawResponseRecord):
            return input_data.get_payload()
        return input_data

    @staticmethod
    def ensure_list(endpoint_name: str, data: Any) -> List[Any]:
        """Validate that input data is a list; raises ParserError otherwise."""
        if data is None:
            raise ParserError(f"Endpoint '{endpoint_name}' payload is None; expected list")
        if not isinstance(data, list):
            raise ParserError(
                f"Endpoint '{endpoint_name}' returned unexpected root type '{type(data).__name__}'; expected list"
            )
        return data

    @staticmethod
    def ensure_dict(endpoint_name: str, item: Any) -> Dict[str, Any]:
        """Validate that item is a dictionary; raises ParserError otherwise."""
        if not isinstance(item, dict):
            raise ParserError(
                f"Endpoint '{endpoint_name}' element is not a JSON object; got '{type(item).__name__}'"
            )
        return item

    @staticmethod
    def require_field(endpoint_name: str, item: Dict[str, Any], field_name: str) -> Any:
        """Ensure a required field exists in the item dictionary."""
        if field_name not in item:
            raise ParserError(f"Endpoint '{endpoint_name}' missing required field: '{field_name}'")
        return item[field_name]

    @staticmethod
    def validate_type(
        endpoint_name: str,
        item: Dict[str, Any],
        field_name: str,
        expected_type: Type,
        nullable: bool = False,
    ) -> Any:
        """
        Validate field presence and data type.
        Distinguishes booleans from integers to avoid Python's bool/int subclass aliasing.
        """
        if field_name not in item:
            raise ParserError(f"Endpoint '{endpoint_name}' missing required field: '{field_name}'")

        val = item[field_name]
        if val is None:
            if not nullable:
                raise ParserError(f"Endpoint '{endpoint_name}' field '{field_name}' cannot be null")
            return None

        # Guard against bool being accepted as int
        if expected_type is int and isinstance(val, bool):
            raise ParserError(
                f"Endpoint '{endpoint_name}' field '{field_name}' expected int, got boolean"
            )

        if not isinstance(val, expected_type):
            raise ParserError(
                f"Endpoint '{endpoint_name}' field '{field_name}' expected {expected_type.__name__}, got {type(val).__name__}"
            )

        return val
