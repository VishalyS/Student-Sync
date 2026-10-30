"""
Base Repository Interface for Student Sync - Hostel subsystem.
Defines abstract data access contracts for persisting and retrieving
ExtractionResult bundles without coupling the pipeline to any specific database.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pipeline.models import ExtractionResult


class BaseHostelRepository(ABC):
    """
    Abstract interface for persisting and querying hostel extraction results.
    Guarantees that downstream storage engines (InMemory, MongoDB, Postgres)
    adhere to identical operational contracts.
    """

    @abstractmethod
    def save(self, extraction_result: ExtractionResult) -> str:
        """
        Persist an ExtractionResult.
        Returns the unique run_id associated with the stored record.
        """
        pass

    @abstractmethod
    def get_by_roll_number(self, roll_number: str) -> Optional[ExtractionResult]:
        """
        Retrieve the latest ExtractionResult for a specific resident roll number.
        Returns None if no matching records exist.
        """
        pass

    @abstractmethod
    def get_by_run_id(self, run_id: str) -> Optional[ExtractionResult]:
        """
        Retrieve an ExtractionResult by its unique extraction run_id.
        Returns None if not found.
        """
        pass

    @abstractmethod
    def list_all_runs(
        self, roll_number: Optional[str] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        List summary metadata of stored extraction runs, optionally filtered by roll number.
        Summary items must be privacy-safe and exclude sensitive credentials.
        """
        pass

    @abstractmethod
    def delete_by_run_id(self, run_id: str) -> bool:
        """
        Delete a stored extraction record by its run_id.
        Returns True if deleted, False if not found.
        """
        pass


# Alias for backward and forward compatibility
HostelRepository = BaseHostelRepository
