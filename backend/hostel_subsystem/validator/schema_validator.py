"""
Tier 1: Response & Schema Validation for Student Sync - Hostel subsystem.
Enforces HTTP transport status, JSON content types, root structure contracts,
and required source field keys according to Phase 1B specifications.
"""
from typing import Any, Dict, List, Optional, Set

from core.exceptions import (
    MissingRequiredKeysError,
    ResponseContentTypeError,
    ResponseRootTypeError,
    ResponseStatusError,
    SchemaError,
)
from scraper.endpoints import EndpointDefinition, HostelEndpoints
from scraper.raw import RawExtractionBundle, RawResponseRecord
from validator.models import (
    ValidationCategory,
    ValidationFinding,
    ValidationSeverity,
)

# Verified mandatory keys per endpoint documented in Phase 1B Source Contract
REQUIRED_ENDPOINT_KEYS: Dict[str, Set[str]] = {
    "student_details": {
        "name",
        "rollno",
        "drollno",
        "mobile",
        "programme",
        "class_",
        "father",
        "addr",
        "districtName",
        "stateName",
        "fmobile",
        "mmobile",
        "email",
        "imgStatus",
        "StudPic",
        "progId",
        "degreeId",
        "semNo",
    },
    "room_details": {
        "hostel",
        "block",
        "hos_id",
        "block_id",
        "room_type",
        "doj",
        "floor_room",
        "room",
        "warden",
        "restutor",
    },
    "mess_details": {
        "_MessName",
        "_MessSupervisor",
        "_MessType",
        "_MessMemberSince",
        "_MessEggToken",
        "_MessNvToken",
    },
    "fees_details": {
        "_HosFeesBalance",
        "_HosFeesDeposit",
        "_HosFeesEstab",
        "_TokenBalance",
    },
    "leave_summary": {
        "leave_type",
        "leave",
    },
    "leave_approvers": {
        "staff_id",
        "staff_name",
    },
    "leave_history": {
        "fromdate",
        "todate",
        "leave_type",
        "reason",
        "status",
    },
    "academic_year": {
        "proc_year",
    },
    "hostel_fee_due": set(),  # May be empty list [] or list of itemized due objects
}


class SchemaValidator:
    """
    Tier 1 Schema and Response Validator.
    Verifies raw HTTP response records and extraction bundles against source contracts.
    """

    def __init__(self) -> None:
        # Cache endpoint definitions indexed by endpoint name
        self._endpoint_defs: Dict[str, EndpointDefinition] = {
            ep.value.name: ep.value for ep in HostelEndpoints
        }

    def validate_record(
        self,
        record: RawResponseRecord,
        endpoint_def: Optional[EndpointDefinition] = None,
    ) -> List[ValidationFinding]:
        """
        Validate a single RawResponseRecord against Tier 1 contracts.
        """
        findings: List[ValidationFinding] = []
        ep_def = endpoint_def or self._endpoint_defs.get(record.endpoint_name)
        is_critical = ep_def.is_critical if ep_def else False
        expected_root = ep_def.expected_root_type if ep_def else list

        # 1. Transport Success / Extraction Status Check
        if not record.is_success:
            severity = ValidationSeverity.ERROR if is_critical else ValidationSeverity.WARNING
            findings.append(
                ValidationFinding(
                    rule_name="ENDPOINT_EXTRACTION_SUCCESS",
                    category=ValidationCategory.TRANSPORT,
                    severity=severity,
                    message=f"Endpoint extraction failed: {record.error_message or 'Unknown error'}",
                    endpoint_name=record.endpoint_name,
                    context={"error_category": record.error_category},
                )
            )
            return findings

        # 2. HTTP Status Code Check
        if record.http_status != 200:
            severity = ValidationSeverity.ERROR if is_critical else ValidationSeverity.WARNING
            findings.append(
                ValidationFinding(
                    rule_name="HTTP_STATUS_200",
                    category=ValidationCategory.TRANSPORT,
                    severity=severity,
                    message=f"Expected HTTP 200, received status {record.http_status}",
                    endpoint_name=record.endpoint_name,
                    context={"http_status": record.http_status},
                )
            )

        # 3. Content-Type Header Check
        expected_ct = ep_def.expected_content_type if (ep_def and ep_def.expected_content_type) else ("text/html" if record.endpoint_name == "student_view" else "application/json")
        content_type = (record.content_type or "").lower()
        if expected_ct and expected_ct not in content_type:
            findings.append(
                ValidationFinding(
                    rule_name="CONTENT_TYPE_JSON",
                    category=ValidationCategory.TRANSPORT,
                    severity=ValidationSeverity.ERROR,
                    message=f"Expected Content-Type containing '{expected_ct}', got {record.content_type!r}",
                    endpoint_name=record.endpoint_name,
                    context={"content_type": record.content_type},
                )
            )

        payload = record.raw_payload

        # 4. Root Payload Structure Check
        expected_root = ep_def.expected_root_type if (ep_def and ep_def.expected_root_type) else (str if record.endpoint_name == "student_view" else list)
        if not isinstance(payload, expected_root):
            findings.append(
                ValidationFinding(
                    rule_name="ROOT_PAYLOAD_TYPE",
                    category=ValidationCategory.SCHEMA,
                    severity=ValidationSeverity.ERROR,
                    message=(
                        f"Expected root payload of type '{expected_root.__name__}', "
                        f"received '{type(payload).__name__}'"
                    ),
                    endpoint_name=record.endpoint_name,
                    context={"expected": expected_root.__name__, "actual": type(payload).__name__},
                )
            )
            return findings

        # 5. Required Source Fields Check (when payload is a list)
        if isinstance(payload, list):
            required_keys = REQUIRED_ENDPOINT_KEYS.get(record.endpoint_name, set())

            # Student profile cannot be empty
            if record.endpoint_name == "student_details":
                if len(payload) == 0:
                    findings.append(
                        ValidationFinding(
                            rule_name="MANDATORY_PROFILE_POPULATED",
                            category=ValidationCategory.SCHEMA,
                            severity=ValidationSeverity.ERROR,
                            message="Student details response is empty; profile is mandatory",
                            endpoint_name=record.endpoint_name,
                        )
                    )
                    return findings
                elif len(payload) > 1:
                    findings.append(
                        ValidationFinding(
                            rule_name="SINGLE_PROFILE_RECORD",
                            category=ValidationCategory.SCHEMA,
                            severity=ValidationSeverity.WARNING,
                            message=f"Expected 1 student profile record, found {len(payload)}",
                            endpoint_name=record.endpoint_name,
                        )
                    )

            # Room details cardinality check
            if record.endpoint_name == "room_details" and len(payload) > 1:
                findings.append(
                    ValidationFinding(
                        rule_name="SINGLE_ROOM_RECORD",
                        category=ValidationCategory.SCHEMA,
                        severity=ValidationSeverity.WARNING,
                        message=f"Expected at most 1 room record, found {len(payload)}",
                        endpoint_name=record.endpoint_name,
                    )
                )

            # Validate element structure and keys
            for idx, item in enumerate(payload):
                if not isinstance(item, dict):
                    findings.append(
                        ValidationFinding(
                            rule_name="RECORD_ITEM_OBJECT",
                            category=ValidationCategory.SCHEMA,
                            severity=ValidationSeverity.ERROR,
                            message=f"Item at index {idx} is of type '{type(item).__name__}', expected JSON object",
                            endpoint_name=record.endpoint_name,
                        )
                    )
                    continue

                missing_keys = required_keys - set(item.keys())
                if missing_keys:
                    findings.append(
                        ValidationFinding(
                            rule_name="REQUIRED_SOURCE_KEYS",
                            category=ValidationCategory.SCHEMA,
                            severity=ValidationSeverity.ERROR,
                            message=(
                                f"Record at index {idx} missing required key(s): "
                                f"{', '.join(sorted(missing_keys))}"
                            ),
                            endpoint_name=record.endpoint_name,
                            context={"missing_keys": sorted(list(missing_keys))},
                        )
                    )

        return findings

    def validate_bundle(self, bundle: RawExtractionBundle) -> List[ValidationFinding]:
        """
        Validate all records in an extraction bundle, checking endpoint completeness
        and criticality rules.
        """
        findings: List[ValidationFinding] = []

        # Check bundle success
        if not bundle.is_success:
            findings.append(
                ValidationFinding(
                    rule_name="BUNDLE_EXTRACTION_SUCCESS",
                    category=ValidationCategory.ORCHESTRATION,
                    severity=ValidationSeverity.ERROR,
                    message="Extraction bundle marked as overall failure",
                    context={"errors": bundle.errors},
                )
            )

        # Check critical endpoint presence
        for ep_key, ep_def in self._endpoint_defs.items():
            if not bundle.has_endpoint(ep_key):
                if ep_def.is_critical:
                    findings.append(
                        ValidationFinding(
                            rule_name="CRITICAL_ENDPOINT_PRESENT",
                            category=ValidationCategory.ORCHESTRATION,
                            severity=ValidationSeverity.ERROR,
                            message=f"Critical endpoint '{ep_key}' is missing from extraction bundle",
                            endpoint_name=ep_key,
                        )
                    )
                else:
                    findings.append(
                        ValidationFinding(
                            rule_name="NON_CRITICAL_ENDPOINT_PRESENT",
                            category=ValidationCategory.ORCHESTRATION,
                            severity=ValidationSeverity.WARNING,
                            message=f"Non-critical endpoint '{ep_key}' is missing from extraction bundle",
                            endpoint_name=ep_key,
                        )
                    )

        # Validate each individual record present in bundle
        bundle_records = list(bundle.responses.values()) if hasattr(bundle, "responses") else getattr(bundle, "records", [])
        for record in bundle_records:
            ep_def = self._endpoint_defs.get(record.endpoint_name)
            rec_findings = self.validate_record(record, endpoint_def=ep_def)
            findings.extend(rec_findings)


        return findings

    def assert_record_valid(
        self,
        record: RawResponseRecord,
        endpoint_def: Optional[EndpointDefinition] = None,
    ) -> None:
        """
        Strictly assert that a RawResponseRecord satisfies Tier 1 schema requirements.
        Raises the specific SchemaError subclass on failure.
        """
        findings = self.validate_record(record, endpoint_def=endpoint_def)
        errors = [f for f in findings if f.severity == ValidationSeverity.ERROR]
        if not errors:
            return

        first = errors[0]
        if first.rule_name == "HTTP_STATUS_200":
            raise ResponseStatusError(first.message)
        elif first.rule_name == "CONTENT_TYPE_JSON":
            raise ResponseContentTypeError(first.message)
        elif first.rule_name == "ROOT_PAYLOAD_TYPE":
            raise ResponseRootTypeError(first.message)
        elif first.rule_name in ("REQUIRED_SOURCE_KEYS", "MANDATORY_PROFILE_POPULATED"):
            raise MissingRequiredKeysError(first.message)
        else:
            raise SchemaError(first.message)

    def assert_bundle_valid(self, bundle: RawExtractionBundle) -> None:
        """
        Strictly assert that a RawExtractionBundle satisfies Tier 1 schema requirements.
        Raises SchemaError if any ERROR-level findings exist.
        """
        findings = self.validate_bundle(bundle)
        errors = [f for f in findings if f.severity == ValidationSeverity.ERROR]
        if not errors:
            return
        summary = "; ".join(e.message for e in errors[:3])
        if len(errors) > 3:
            summary += f" (... and {len(errors) - 3} more errors)"
        raise SchemaError(f"Bundle schema validation failed: {summary}")
