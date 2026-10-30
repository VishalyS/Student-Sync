"""
Authenticated read-only endpoint extractor for Student Sync - Hostel subsystem.
Executes registered GET endpoints, captures raw server responses verbatim,
and packages them into an immutable RawExtractionBundle.
"""
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx

from core.exceptions import AuthenticationError, NetworkError, TimeoutError
from core.logging import get_logger
from scraper.endpoints import EndpointDefinition, HostelEndpoints
from scraper.raw import RawExtractionBundle, RawResponseRecord, calculate_payload_hash


class HostelExtractor:
    """
    Executes registered read-only endpoints against an authenticated client session.
    Enforces the critical vs non-critical partial extraction policy.
    """

    def __init__(self, client: Any, logger: Optional[Any] = None) -> None:
        self.client = client
        self.logger = logger or get_logger("student_sync_hostel.extractor")

    def extract_endpoint(
        self,
        endpoint_def: EndpointDefinition,
        rollno: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> RawResponseRecord:
        """
        Execute an individual read-only endpoint and return its RawResponseRecord.
        Captures raw JSON payloads verbatim without transformation.
        """
        if endpoint_def.requires_auth and not self.client.auth_session:
            self.logger.error("Cannot extract %s: client is not authenticated", endpoint_def.name)
            return RawResponseRecord(
                endpoint_name=endpoint_def.name,
                url_path=endpoint_def.path,
                http_status=0,
                content_type="",
                response_time_ms=0.0,
                raw_payload=None,
                is_success=False,
                error_message="Client is not authenticated",
                error_category="AUTH_REQUIRED",
                http_method=endpoint_def.method,
                extraction_run_id=run_id,
            )

        active_roll = (rollno or (self.client.auth_session.student_roll if self.client.auth_session else "")).strip().upper()

        params = {}
        if endpoint_def.requires_rollno:
            params["rollno"] = active_roll

        start_time = time.perf_counter()
        self.logger.debug("Extracting %s [%s %s]", endpoint_def.name, endpoint_def.method, endpoint_def.path)

        try:
            if endpoint_def.method.upper() == "GET":
                response = self.client.get(endpoint_def.path, params=params)
            else:
                response = self.client.post(endpoint_def.path, data=params)

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            status = response.status_code
            content_type = response.headers.get("Content-Type", "")

            # 1. Success HTTP 200
            if status == 200:
                raw_text = response.text.strip()

                # Handle empty response body
                if not raw_text:
                    self.logger.debug("Received empty body for %s", endpoint_def.name)
                    return RawResponseRecord(
                        endpoint_name=endpoint_def.name,
                        url_path=endpoint_def.path,
                        http_status=status,
                        content_type=content_type,
                        response_time_ms=duration_ms,
                        raw_payload=None,
                        is_success=True,
                        http_method=endpoint_def.method,
                        extraction_run_id=run_id,
                    )

                # Validate expected content type if defined
                if endpoint_def.expected_content_type and endpoint_def.expected_content_type not in content_type:
                    self.logger.warning(
                        "Unexpected content type for %s: got %s, expected %s",
                        endpoint_def.name, content_type, endpoint_def.expected_content_type
                    )
                    return RawResponseRecord(
                        endpoint_name=endpoint_def.name,
                        url_path=endpoint_def.path,
                        http_status=status,
                        content_type=content_type,
                        response_time_ms=duration_ms,
                        raw_payload=raw_text[:200],
                        is_success=False,
                        error_message=f"Unexpected content type: {content_type} (expected {endpoint_def.expected_content_type})",
                        error_category="UNEXPECTED_CONTENT_TYPE",
                        http_method=endpoint_def.method,
                        extraction_run_id=run_id,
                    )

                if "application/json" in content_type:
                    try:
                        raw_payload = response.json()
                        return RawResponseRecord(
                            endpoint_name=endpoint_def.name,
                            url_path=endpoint_def.path,
                            http_status=status,
                            content_type=content_type,
                            response_time_ms=duration_ms,
                            raw_payload=raw_payload,
                            is_success=True,
                            http_method=endpoint_def.method,
                            extraction_run_id=run_id,
                        )
                    except Exception as json_err:
                        self.logger.error("JSON decode error on %s: %s", endpoint_def.name, str(json_err))
                        return RawResponseRecord(
                            endpoint_name=endpoint_def.name,
                            url_path=endpoint_def.path,
                            http_status=status,
                            content_type=content_type,
                            response_time_ms=duration_ms,
                            raw_payload=raw_text[:200],
                            is_success=False,
                            error_message=f"Invalid JSON payload: {type(json_err).__name__}",
                            error_category="INVALID_JSON",
                            http_method=endpoint_def.method,
                            extraction_run_id=run_id,
                        )
                else:
                    return RawResponseRecord(
                        endpoint_name=endpoint_def.name,
                        url_path=endpoint_def.path,
                        http_status=status,
                        content_type=content_type,
                        response_time_ms=duration_ms,
                        raw_payload=raw_text,
                        is_success=True,
                        http_method=endpoint_def.method,
                        extraction_run_id=run_id,
                    )

            # 2. HTTP Error statuses
            error_cat = "CLIENT_ERROR"
            if status in (401, 403):
                error_cat = "AUTH_FAILURE"
            elif status == 404:
                error_cat = "NOT_FOUND"
            elif status == 429:
                error_cat = "RATE_LIMITED"
            elif status >= 500:
                error_cat = "SERVER_ERROR"

            self.logger.warning("Endpoint %s failed with HTTP %d (%s)", endpoint_def.name, status, error_cat)
            return RawResponseRecord(
                endpoint_name=endpoint_def.name,
                url_path=endpoint_def.path,
                http_status=status,
                content_type=content_type,
                response_time_ms=duration_ms,
                raw_payload=None,
                is_success=False,
                error_message=f"HTTP request failed with status {status}",
                error_category=error_cat,
                http_method=endpoint_def.method,
                extraction_run_id=run_id,
            )

        except TimeoutError as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self.logger.error("Timeout extracting %s after %.1fms", endpoint_def.name, duration_ms)
            return RawResponseRecord(
                endpoint_name=endpoint_def.name,
                url_path=endpoint_def.path,
                http_status=0,
                content_type="",
                response_time_ms=duration_ms,
                raw_payload=None,
                is_success=False,
                error_message=str(exc),
                error_category="TIMEOUT",
                http_method=endpoint_def.method,
                extraction_run_id=run_id,
            )

        except NetworkError as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self.logger.error("Network error extracting %s: %s", endpoint_def.name, str(exc))
            return RawResponseRecord(
                endpoint_name=endpoint_def.name,
                url_path=endpoint_def.path,
                http_status=0,
                content_type="",
                response_time_ms=duration_ms,
                raw_payload=None,
                is_success=False,
                error_message=str(exc),
                error_category="NETWORK_ERROR",
                http_method=endpoint_def.method,
                extraction_run_id=run_id,
            )

    def extract_student_view(self, run_id: Optional[str] = None) -> Optional[RawResponseRecord]:
        """
        Extract /Hostel/Student/StudentView HTML payload containing server pre-rendered tables.
        Non-critical operation capturing mess bills and transaction history.
        """
        if not self.client.auth_session:
            return None
        start_time = time.perf_counter()
        try:
            response = self.client.get("/Hostel/Student/StudentView")
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            if response.status_code == 200 and response.text:
                return RawResponseRecord(
                    endpoint_name="student_view",
                    url_path="/Hostel/Student/StudentView",
                    http_status=200,
                    content_type=response.headers.get("Content-Type", "text/html"),
                    response_time_ms=duration_ms,
                    raw_payload=response.text,
                    is_success=True,
                    http_method="GET",
                    extraction_run_id=run_id,
                )
        except Exception as exc:
            self.logger.warning("Optional student_view extraction skipped/failed: %s", exc)
        return None

    def extract_all(
        self,
        endpoints: Optional[List[EndpointDefinition]] = None,
        rollno: Optional[str] = None,
        include_view: bool = False,
    ) -> RawExtractionBundle:
        """
        Execute the standard sequence of read-only endpoints.
        Evaluates critical vs non-critical policy to produce the RawExtractionBundle.
        """
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()
        active_roll = (rollno or (self.client.auth_session.student_roll if self.client.auth_session else "")).strip().upper()

        sequence = endpoints or HostelEndpoints.get_extraction_sequence()
        responses: Dict[str, RawResponseRecord] = {}
        errors: List[str] = []
        warnings: List[str] = []
        is_success = True

        self.logger.info("Starting raw extraction sequence (run_id: %s)", run_id)

        for ep_def in sequence:
            record = self.extract_endpoint(ep_def, rollno=active_roll, run_id=run_id)
            responses[ep_def.name] = record

            if not record.is_success:
                err_msg = f"Endpoint '{ep_def.name}' failed: {record.error_category} ({record.error_message})"
                if ep_def.is_critical:
                    self.logger.error("CRITICAL ENDPOINT FAILURE: %s", err_msg)
                    errors.append(err_msg)
                    is_success = False
                else:
                    self.logger.warning("NON-CRITICAL ENDPOINT WARNING: %s", err_msg)
                    warnings.append(err_msg)

        if include_view:
            view_rec = self.extract_student_view(run_id=run_id)
            if view_rec:
                responses["student_view"] = view_rec

        self.logger.info(
            "Extraction sequence finished: success=%s, total=%d, errors=%d, warnings=%d",
            is_success,
            len(responses),
            len(errors),
            len(warnings),
        )

        return RawExtractionBundle(
            run_id=run_id,
            timestamp_utc=timestamp,
            responses=responses,
            is_success=is_success,
            errors=errors,
            warnings=warnings,
            student_roll_number=active_roll,
        )


__all__ = [
    "HostelExtractor",
    "RawResponseRecord",
    "RawExtractionBundle",
    "calculate_payload_hash",
]

