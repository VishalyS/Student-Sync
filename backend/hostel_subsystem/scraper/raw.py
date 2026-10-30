"""
Raw Response Preservation & Evidence Layer for Student Sync - Hostel subsystem.
Provides immutable, traceable, and cryptographically verified in-memory containers
for extracted hostel responses, strictly decoupled from parsing and normalization.
"""
import copy
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def calculate_payload_hash(payload: Any) -> str:
    """
    Calculate a deterministic SHA-256 hash of a raw API response payload.
    Ensures consistent key ordering and canonical formatting for dictionaries and lists.
    """
    if payload is None:
        canonical_bytes = b"null"
    elif isinstance(payload, (dict, list)):
        canonical_str = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        canonical_bytes = canonical_str.encode("utf-8")
    elif isinstance(payload, str):
        canonical_bytes = payload.encode("utf-8")
    elif isinstance(payload, (int, float, bool)):
        canonical_bytes = str(payload).encode("utf-8")
    else:
        canonical_bytes = repr(payload).encode("utf-8")

    return hashlib.sha256(canonical_bytes).hexdigest()


@dataclass(frozen=True)
class RawResponseRecord:
    """
    Immutable, audit-ready container for an individual endpoint's raw HTTP response.
    Guarantees that raw server payloads cannot be modified in-place by parsers or normalizers.
    """
    endpoint_name: str
    url_path: str
    http_status: int
    content_type: str
    response_time_ms: float
    _raw_payload: Any = field(repr=False, default=None)
    is_success: bool = True
    error_message: Optional[str] = None
    error_category: Optional[str] = None
    http_method: str = "GET"
    extracted_at: str = ""
    extraction_run_id: Optional[str] = None
    payload_hash: str = ""

    def __init__(
        self,
        endpoint_name: str,
        url_path: str,
        http_status: int,
        content_type: str,
        response_time_ms: float,
        raw_payload: Any = None,
        is_success: bool = True,
        error_message: Optional[str] = None,
        error_category: Optional[str] = None,
        http_method: str = "GET",
        extracted_at: Optional[str] = None,
        extraction_run_id: Optional[str] = None,
        payload_hash: Optional[str] = None,
    ) -> None:
        object.__setattr__(self, "endpoint_name", str(endpoint_name))
        object.__setattr__(self, "url_path", str(url_path))
        object.__setattr__(self, "http_status", int(http_status))
        object.__setattr__(self, "content_type", str(content_type))
        object.__setattr__(self, "response_time_ms", float(response_time_ms))
        object.__setattr__(self, "_raw_payload", copy.deepcopy(raw_payload))
        object.__setattr__(self, "is_success", bool(is_success))
        object.__setattr__(self, "error_message", error_message)
        object.__setattr__(self, "error_category", error_category)
        object.__setattr__(self, "http_method", str(http_method).upper())

        timestamp = extracted_at or datetime.now(timezone.utc).isoformat()
        object.__setattr__(self, "extracted_at", timestamp)
        object.__setattr__(self, "extraction_run_id", extraction_run_id)

        digest = payload_hash or calculate_payload_hash(raw_payload)
        object.__setattr__(self, "payload_hash", digest)

    @property
    def raw_payload(self) -> Any:
        """
        Return a defensive deep copy of the raw payload to prevent accidental in-place mutation.
        """
        return copy.deepcopy(self._raw_payload)

    @property
    def sha256_hash(self) -> str:
        """Cryptographic SHA-256 payload hash alias."""
        return self.payload_hash

    def get_payload(self, defensive_copy: bool = True) -> Any:
        """
        Retrieve raw response payload. If defensive_copy is True (default),
        a full deep copy is returned to ensure immutability of stored evidence.
        """
        return copy.deepcopy(self._raw_payload) if defensive_copy else self._raw_payload

    def verify_integrity(self) -> bool:
        """
        Verify that the internal payload matches its computed cryptographic SHA-256 hash.
        """
        current_hash = calculate_payload_hash(self._raw_payload)
        return current_hash == self.payload_hash

    def to_dict(self) -> Dict[str, Any]:
        """
        Return an auditable, sanitized dictionary representation of the raw response record.
        """
        return {
            "endpoint_name": self.endpoint_name,
            "http_method": self.http_method,
            "url_path": self.url_path,
            "http_status": self.http_status,
            "content_type": self.content_type,
            "response_time_ms": self.response_time_ms,
            "extracted_at": self.extracted_at,
            "extraction_run_id": self.extraction_run_id,
            "is_success": self.is_success,
            "payload_hash": self.payload_hash,
            "error_message": self.error_message,
            "error_category": self.error_category,
            "raw_payload": self.get_payload(defensive_copy=True),
        }

    def __repr__(self) -> str:
        count = len(self._raw_payload) if isinstance(self._raw_payload, list) else (1 if self._raw_payload is not None else 0)
        hash_preview = f"{self.payload_hash[:8]}..." if self.payload_hash else "none"
        return (
            f"RawResponseRecord(endpoint={self.endpoint_name!r}, "
            f"method={self.http_method!r}, "
            f"status={self.http_status}, "
            f"success={self.is_success}, "
            f"items={count}, "
            f"hash={hash_preview!r}, "
            f"duration={self.response_time_ms:.1f}ms)"
        )

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class RawExtractionBundle:
    """
    Immutable container bundling raw extraction records across an extraction run.
    Provides a decoupled access API for downstream parsers without direct HTTP client dependency.
    Personal identifiers are omitted from string representations and dictionary exports.
    """
    run_id: str
    timestamp_utc: str
    _responses: Dict[str, RawResponseRecord] = field(repr=False, default_factory=dict)
    is_success: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    _student_roll_number: Optional[str] = field(repr=False, default=None)

    def __init__(
        self,
        run_id: str,
        timestamp_utc: str,
        arg3: Any = None,
        arg4: Any = None,
        is_success: bool = True,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        student_roll_number: Optional[str] = None,
        responses: Optional[Dict[str, RawResponseRecord]] = None,
    ) -> None:
        object.__setattr__(self, "run_id", str(run_id))
        object.__setattr__(self, "timestamp_utc", str(timestamp_utc))

        final_responses = responses
        final_roll = student_roll_number
        final_success = is_success

        if isinstance(arg3, dict):
            final_responses = arg3
            if arg4 is not None:
                final_success = bool(arg4)
        elif isinstance(arg3, str):
            final_roll = arg3
            if isinstance(arg4, dict):
                final_responses = arg4

        object.__setattr__(self, "_responses", dict(final_responses or {}))
        object.__setattr__(self, "is_success", bool(final_success))
        object.__setattr__(self, "errors", list(errors or []))
        object.__setattr__(self, "warnings", list(warnings or []))
        object.__setattr__(self, "_student_roll_number", final_roll)

    @property
    def responses(self) -> Dict[str, RawResponseRecord]:
        """
        Return a copy of the responses dictionary to prevent consumer dictionary mutation.
        """
        return dict(self._responses)

    @property
    def student_roll_number(self) -> Optional[str]:
        """
        Internal accessor for student identifier when required by caller.
        Never exposed in string representations or JSON exports.
        """
        return self._student_roll_number

    @property
    def extraction_run_id(self) -> str:
        """Alias for run_id to support data lineage queries."""
        return self.run_id

    @property
    def extracted_at(self) -> str:
        """Alias for timestamp_utc to support data lineage queries."""
        return self.timestamp_utc

    def get_response(self, endpoint_name: str) -> Optional[RawResponseRecord]:
        """
        Access API: Retrieve the RawResponseRecord for a specific endpoint name.
        """
        return self._responses.get(endpoint_name)

    def get_payload(self, endpoint_name: str, defensive_copy: bool = True) -> Any:
        """
        Access API: Retrieve the raw payload for an endpoint.
        Returns None if endpoint is not in bundle or record failed with None payload.
        Returns a defensive deep copy by default.
        """
        record = self._responses.get(endpoint_name)
        if record is None:
            return None
        return record.get_payload(defensive_copy=defensive_copy)

    def has_endpoint(self, endpoint_name: str) -> bool:
        """
        Access API: Check if an endpoint response is present in this bundle.
        """
        return endpoint_name in self._responses

    def list_endpoints(self) -> List[str]:
        """
        Access API: List all endpoint names included in this bundle.
        """
        return list(self._responses.keys())

    def verify_integrity(self) -> bool:
        """
        Access API: Cryptographically verify integrity of all enclosed endpoint payloads.
        Returns True if and only if all records match their stored SHA-256 hashes.
        """
        return all(record.verify_integrity() for record in self._responses.values())

    def to_dict(self) -> Dict[str, Any]:
        """
        Return a sanitized, serializable dictionary representation of the bundle.
        Personal identifiers, credentials, cookies, and tokens are strictly excluded.
        """
        return {
            "run_id": self.run_id,
            "extraction_run_id": self.run_id,
            "timestamp_utc": self.timestamp_utc,
            "extracted_at": self.timestamp_utc,
            "is_success": self.is_success,
            "total_endpoints": len(self._responses),
            "responses": {
                name: record.to_dict() for name, record in self._responses.items()
            },
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }

    def to_json(self, indent: int = 2) -> str:
        """
        Serialize bundle metadata and preserved payloads into a deterministic JSON string.
        """
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def __repr__(self) -> str:
        return (
            f"RawExtractionBundle(run_id={self.run_id!r}, "
            f"success={self.is_success}, "
            f"endpoints={len(self._responses)}, "
            f"errors={len(self.errors)}, "
            f"warnings={len(self.warnings)})"
        )

    def __str__(self) -> str:
        return self.__repr__()
