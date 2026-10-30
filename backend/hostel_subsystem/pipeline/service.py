"""
Service Layer for Student Sync - Hostel subsystem.
Provides a clean, unified backend API interface coordinating extraction runs
and repository persistence for downstream consumers (REST APIs, CLI, MCP agents).
"""
from typing import Any, Dict, List, Optional

from pipeline.models import ExtractionResult
from pipeline.runner import HostelPipelineRunner
from repository.base import BaseHostelRepository
from repository.in_memory import InMemoryHostelRepository
from scraper.raw import RawExtractionBundle


class HostelExtractionService:
    """
    Unified application service for hostel operations.
    Bridges the scraper pipeline runner with the storage repository.
    """

    def __init__(
        self,
        runner: Optional[HostelPipelineRunner] = None,
        repository: Optional[BaseHostelRepository] = None,
    ) -> None:
        self.runner = runner or HostelPipelineRunner()
        self.repository = repository or InMemoryHostelRepository()

    def extract_student(
        self,
        roll_number: Optional[str] = None,
        password: Optional[str] = None,
        persist: bool = True,
        raise_on_error: bool = False,
    ) -> ExtractionResult:
        """
        Execute full extraction pipeline for a resident and optionally persist the result.
        """
        extraction_res = self.runner.extract(
            roll_number=roll_number,
            password=password,
            raise_on_error=raise_on_error,
        )
        if persist and extraction_res.is_success:
            self.repository.save(extraction_res)
        return extraction_res

    def extract_from_raw(
        self,
        bundle: RawExtractionBundle,
        target_roll_number: Optional[str] = None,
        persist: bool = True,
        raise_on_error: bool = False,
    ) -> ExtractionResult:
        """
        Execute offline extraction from a RawExtractionBundle and optionally persist.
        """
        extraction_res = self.runner.extract_from_raw(
            bundle=bundle,
            target_roll_number=target_roll_number,
            raise_on_error=raise_on_error,
        )
        if persist and extraction_res.is_success:
            self.repository.save(extraction_res)
        return extraction_res

    def get_student_record(self, roll_number: str) -> Optional[ExtractionResult]:
        """Query repository for the latest extraction record of a student."""
        return self.repository.get_by_roll_number(roll_number)

    def get_run_record(self, run_id: str) -> Optional[ExtractionResult]:
        """Query repository for an extraction record by run_id."""
        return self.repository.get_by_run_id(run_id)

    def list_history(
        self, roll_number: Optional[str] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """List past extraction history from repository."""
        return self.repository.list_all_runs(roll_number=roll_number, limit=limit)
