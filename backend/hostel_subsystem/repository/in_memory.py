"""
In-Memory Repository Implementation for Student Sync - Hostel subsystem.
Provides a thread-safe, zero-dependency persistence layer for testing,
offline batch runs, and ephemeral caching.
"""
from datetime import datetime
import threading
from typing import Any, Dict, List, Optional

from pipeline.models import ExtractionResult
from repository.base import BaseHostelRepository


class InMemoryHostelRepository(BaseHostelRepository):
    """
    Thread-safe in-memory storage implementation for ExtractionResult objects.
    Useful for testing and local execution without requiring a live MongoDB server.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: Dict[str, ExtractionResult] = {}
        # Index: roll_number (uppercase) -> List[run_id] in insertion order
        self._roll_index: Dict[str, List[str]] = {}

    def save(self, extraction_result: ExtractionResult) -> str:
        """
        Store an ExtractionResult in memory and update roll number index.
        """
        with self._lock:
            run_id = extraction_result.run_id
            self._records[run_id] = extraction_result

            # Extract roll number from student dict or target roll metadata
            roll: Optional[str] = None
            if extraction_result.student and "roll_number" in extraction_result.student:
                roll = extraction_result.student["roll_number"]
            elif extraction_result.raw_bundle and extraction_result.raw_bundle.student_roll_number:
                roll = extraction_result.raw_bundle.student_roll_number

            if roll:
                roll_clean = roll.strip().upper()
                if roll_clean not in self._roll_index:
                    self._roll_index[roll_clean] = []
                if run_id not in self._roll_index[roll_clean]:
                    self._roll_index[roll_clean].append(run_id)

            return run_id

    def get_by_roll_number(self, roll_number: str) -> Optional[ExtractionResult]:
        """
        Retrieve the latest ExtractionResult for a given roll number.
        """
        with self._lock:
            roll_clean = roll_number.strip().upper()
            run_ids = self._roll_index.get(roll_clean, [])
            if not run_ids:
                return None
            latest_run_id = run_ids[-1]
            return self._records.get(latest_run_id)

    def get_by_run_id(self, run_id: str) -> Optional[ExtractionResult]:
        """
        Retrieve an ExtractionResult by its run_id.
        """
        with self._lock:
            return self._records.get(run_id)

    def list_all_runs(
        self, roll_number: Optional[str] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        List summary records of stored extractions, newest first.
        """
        with self._lock:
            if roll_number:
                roll_clean = roll_number.strip().upper()
                candidate_ids = self._roll_index.get(roll_clean, [])
            else:
                candidate_ids = list(self._records.keys())

            # Return newest first up to limit
            results: List[Dict[str, Any]] = []
            for rid in reversed(candidate_ids[-limit:]):
                item = self._records[rid]
                roll_masked = "***"
                if item.student and "roll_number" in item.student:
                    rn = item.student["roll_number"]
                    roll_masked = f"{rn[:2]}***" if len(rn) > 2 else "***"
                elif item.raw_bundle and item.raw_bundle.student_roll_number:
                    rn = item.raw_bundle.student_roll_number
                    roll_masked = f"{rn[:2]}***" if len(rn) > 2 else "***"

                results.append({
                    "run_id": item.run_id,
                    "timestamp": item.timestamp,
                    "status": item.status,
                    "roll_number": roll_masked,
                    "endpoints_count": item.endpoints_count,
                    "is_valid": item.is_valid,
                })
            return results

    def delete_by_run_id(self, run_id: str) -> bool:
        """
        Remove an extraction result from memory.
        """
        with self._lock:
            if run_id not in self._records:
                return False
            del self._records[run_id]
            for roll_clean, ids in self._roll_index.items():
                if run_id in ids:
                    ids.remove(run_id)
            return True

    def count(self) -> int:
        """Total number of stored records."""
        with self._lock:
            return len(self._records)

    def clear(self) -> None:
        """Wipe all stored records."""
        with self._lock:
            self._records.clear()
            self._roll_index.clear()
