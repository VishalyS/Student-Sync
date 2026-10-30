"""
End-to-End Pipeline Runner for Student Sync - Hostel subsystem.
Orchestrates Authentication, HTTP Extraction, Raw Evidence Preservation,
Domain Parsing, Normalization, and Two-Tier Validation into a cohesive execution flow.
"""
from datetime import datetime, timezone
import time
from typing import Any, Optional
import httpx

from config.settings import HostelConfig, load_config
from core.exceptions import (
    AuthenticationError,
    HostelError,
    NetworkError,
    TimeoutError,
    ValidationError,
)
from core.logging import get_logger
from normalizer.engine import HostelDataNormalizer
from parser.engine import HostelDomainParser
from pipeline.models import ExtractionResult, HostelPipelineResult, PipelineStatus
from scraper.client import HostelHttpClient
from scraper.extractor import HostelExtractor
from scraper.raw import RawExtractionBundle
from validator.engine import HostelValidationEngine


class HostelPipelineRunner:
    """
    Unified end-to-end scraper pipeline runner.
    Coordinates every phase from authentication through two-tier validation.
    Supports live execution, custom transport injection for deterministic testing,
    and offline in-memory execution from historical raw bundles.
    """

    def __init__(
        self,
        config: Optional[HostelConfig] = None,
        client: Optional[HostelHttpClient] = None,
        transport: Optional[httpx.BaseTransport] = None,
        logger: Optional[Any] = None,
    ) -> None:
        self.config = config
        self._injected_client = client
        self.transport = transport
        self.logger = logger or get_logger("student_sync_hostel.pipeline")

        # Transformation engines
        self.domain_parser = HostelDomainParser()
        self.normalizer = HostelDataNormalizer()
        self.validator = HostelValidationEngine()

    def run(
        self,
        roll_number: Optional[str] = None,
        password: Optional[str] = None,
        raise_on_error: bool = False,
    ) -> HostelPipelineResult:
        """
        Execute complete live/transport pipeline cycle:
        Authentication ➔ Extraction ➔ Raw Preservation ➔ Parsing ➔ Normalization ➔ Validation
        """
        start_time = time.perf_counter()
        run_id_fallback = f"run_pipeline_{int(time.time())}"
        timestamp_fallback = datetime.now(timezone.utc).isoformat()

        # 1. Resolve configuration and credentials
        resolved_config = self.config
        if resolved_config is None:
            if self._injected_client is not None:
                resolved_config = self._injected_client.config
            else:
                try:
                    overrides = {}
                    if roll_number:
                        overrides["HOSTEL_USERNAME"] = roll_number
                    if password:
                        overrides["HOSTEL_PASSWORD"] = password
                    resolved_config = load_config(overrides=overrides if overrides else None)
                except Exception as exc:
                    self.logger.error("Failed to load configuration: %s", exc)
                    if raise_on_error:
                        raise
                    return HostelPipelineResult(
                        status=PipelineStatus.FAILED,
                        run_id=run_id_fallback,
                        extracted_at=timestamp_fallback,
                        target_roll_number=roll_number or "UNKNOWN",
                        execution_time_seconds=time.perf_counter() - start_time,
                        error_message=f"Configuration error: {exc}",
                    )

        target_roll = (roll_number or resolved_config.username).strip().upper()
        target_password = password or resolved_config.password

        # 2. Manage HTTP Client lifecycle
        owns_client = self._injected_client is None
        client = (
            self._injected_client
            if self._injected_client is not None
            else HostelHttpClient(config=resolved_config, transport=self.transport, logger=self.logger)
        )

        try:
            self.logger.info("Initiating hostel extraction pipeline for roll: %s***", target_roll[:2])

            # Step 1: Authentication
            self.logger.debug("Executing Step 1: Authentication")
            client.authenticate(username=target_roll, password=target_password)

            # Step 2: Endpoint Extraction & Raw Preservation
            self.logger.debug("Executing Step 2: Read-Only Endpoint Extraction")
            extractor = HostelExtractor(client=client, logger=self.logger)
            raw_bundle = extractor.extract_all(rollno=target_roll, include_view=True)

            # Step 3: Domain Parsing
            self.logger.debug("Executing Step 3: Domain Model Parsing")
            parsed_data = self.domain_parser.parse_bundle(raw_bundle)

            # Step 4: Normalization
            self.logger.debug("Executing Step 4: Data Normalization")
            normalized_data = self.normalizer.normalize(parsed_data)

            # Step 5: Two-Tier Validation (Tier 1 Schema + Tier 2 Domain Integrity)
            self.logger.debug("Executing Step 5: Two-Tier Data Validation")
            val_result = self.validator.validate(
                data=normalized_data,
                target_roll_number=target_roll,
                raw_bundle=raw_bundle,
            )

            # Determine final status
            if not raw_bundle.is_success or not val_result.is_valid:
                status = PipelineStatus.FAILED
                error_summary = "; ".join(e.message for e in val_result.errors) if val_result.has_errors else "; ".join(raw_bundle.errors)
            elif raw_bundle.warnings or val_result.has_warnings:
                status = PipelineStatus.PARTIAL_SUCCESS
                error_summary = None
            else:
                status = PipelineStatus.SUCCESS
                error_summary = None

            duration = time.perf_counter() - start_time
            self.logger.info(
                "Pipeline execution complete: status=%s in %.2fs (errors=%d, warnings=%d)",
                status.value,
                duration,
                len(val_result.errors),
                len(val_result.warnings),
            )

            result = HostelPipelineResult(
                status=status,
                run_id=raw_bundle.run_id,
                extracted_at=raw_bundle.extracted_at,
                target_roll_number=target_roll,
                raw_bundle=raw_bundle,
                parsed_data=parsed_data,
                normalized_data=normalized_data,
                validation_result=val_result,
                execution_time_seconds=duration,
                error_message=error_summary,
            )

            if raise_on_error and status == PipelineStatus.FAILED:
                if val_result.has_errors:
                    val_result.raise_for_errors()
                elif raw_bundle.errors:
                    raise HostelError(f"Extraction failed: {'; '.join(raw_bundle.errors)}")

            return result

        except Exception as exc:
            duration = time.perf_counter() - start_time
            self.logger.error("Pipeline failure: %s", exc)
            if raise_on_error:
                raise
            return HostelPipelineResult(
                status=PipelineStatus.FAILED,
                run_id=run_id_fallback,
                extracted_at=timestamp_fallback,
                target_roll_number=target_roll,
                execution_time_seconds=duration,
                error_message=str(exc),
            )

        finally:
            if owns_client:
                client.close()

    def run_from_raw(
        self,
        bundle: RawExtractionBundle,
        target_roll_number: Optional[str] = None,
        raise_on_error: bool = False,
    ) -> HostelPipelineResult:
        """
        Execute offline/in-memory pipeline from a preserved RawExtractionBundle:
        Parsing ➔ Normalization ➔ Validation (zero network / zero auth).
        """
        start_time = time.perf_counter()
        target_roll = (
            target_roll_number
            or getattr(bundle, "student_roll_number", None)
            or getattr(bundle, "roll_number", None)
            or ""
        ).strip().upper()

        try:
            # 1. Parsing
            parsed_data = self.domain_parser.parse_bundle(bundle)

            # 2. Normalization
            normalized_data = self.normalizer.normalize(parsed_data)

            # 3. Validation
            val_result = self.validator.validate(
                data=normalized_data,
                target_roll_number=target_roll,
                raw_bundle=bundle,
            )

            # Determine status
            if not bundle.is_success or not val_result.is_valid:
                status = PipelineStatus.FAILED
                err_msg = "; ".join(e.message for e in val_result.errors) if val_result.has_errors else "; ".join(bundle.errors)
            elif bundle.warnings or val_result.has_warnings:
                status = PipelineStatus.PARTIAL_SUCCESS
                err_msg = None
            else:
                status = PipelineStatus.SUCCESS
                err_msg = None

            duration = time.perf_counter() - start_time

            result = HostelPipelineResult(
                status=status,
                run_id=bundle.run_id,
                extracted_at=bundle.extracted_at,
                target_roll_number=target_roll,
                raw_bundle=bundle,
                parsed_data=parsed_data,
                normalized_data=normalized_data,
                validation_result=val_result,
                execution_time_seconds=duration,
                error_message=err_msg,
            )

            if raise_on_error and status == PipelineStatus.FAILED:
                if val_result.has_errors:
                    val_result.raise_for_errors()
                elif bundle.errors:
                    raise HostelError(f"Raw bundle failed: {'; '.join(bundle.errors)}")

            return result

        except Exception as exc:
            duration = time.perf_counter() - start_time
            if raise_on_error:
                raise
            return HostelPipelineResult(
                status=PipelineStatus.FAILED,
                run_id=bundle.run_id,
                extracted_at=bundle.extracted_at,
                target_roll_number=target_roll,
                raw_bundle=bundle,
                execution_time_seconds=duration,
                error_message=str(exc),
            )

    def extract(
        self,
        roll_number: Optional[str] = None,
        password: Optional[str] = None,
        raise_on_error: bool = False,
    ) -> ExtractionResult:
        """
        Execute complete extraction pipeline and return the canonical, stable ExtractionResult.
        """
        pipeline_res = self.run(roll_number=roll_number, password=password, raise_on_error=raise_on_error)
        return pipeline_res.to_extraction_result()

    def extract_from_raw(
        self,
        bundle: RawExtractionBundle,
        target_roll_number: Optional[str] = None,
        raise_on_error: bool = False,
    ) -> ExtractionResult:
        """
        Execute offline pipeline from a RawExtractionBundle and return the canonical ExtractionResult.
        """
        pipeline_res = self.run_from_raw(bundle=bundle, target_roll_number=target_roll_number, raise_on_error=raise_on_error)
        return pipeline_res.to_extraction_result()
