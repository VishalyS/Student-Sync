"""
Hostel MongoDB Repository for Student Sync Application.
Provides a dedicated, isolated data access layer for the 'hostel_students'
collection in the Student Sync MongoDB database.
Guarantees zero contamination of academic collections ('new_users', 'subjects').
"""
import os
import sys
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("studentsync.hostel.repository")

# Ensure standalone hostel subsystem is on sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_bundled_hostel = os.path.join(_current_dir, "hostel_subsystem")
_env_hostel = os.getenv("HOSTEL_SUBSYSTEM_PATH")
_win_hostel_fallback = r"C:\Users\visha\OneDrive\Desktop\Student Sync - Hostel"

HOSTEL_SUBSYSTEM_PATH = None
if _env_hostel and os.path.exists(_env_hostel):
    HOSTEL_SUBSYSTEM_PATH = _env_hostel
elif os.path.exists(_bundled_hostel):
    HOSTEL_SUBSYSTEM_PATH = _bundled_hostel
elif os.path.exists(_win_hostel_fallback):
    HOSTEL_SUBSYSTEM_PATH = _win_hostel_fallback

if HOSTEL_SUBSYSTEM_PATH and HOSTEL_SUBSYSTEM_PATH not in sys.path:
    sys.path.insert(0, HOSTEL_SUBSYSTEM_PATH)

try:
    from pipeline.models import ExtractionResult
    from repository.base import BaseHostelRepository
    from repository.in_memory import InMemoryHostelRepository
except ImportError as exc:
    logger.warning("Could not import standalone hostel package: %s", exc)
    BaseHostelRepository = object
    InMemoryHostelRepository = None
    ExtractionResult = None


class HostelMongoRepository:
    """
    MongoDB repository targeting the 'hostel_students' collection.
    If MongoDB is disconnected or unavailable, transparently delegates
    to an in-memory repository to guarantee 100% offline testability.
    """

    COLLECTION_NAME = "hostel_students"

    def __init__(self, db: Optional[Any] = None) -> None:
        self.db = db
        self._in_memory_fallback = InMemoryHostelRepository() if InMemoryHostelRepository else None
        self._initialized_indexes = False
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Create unique index on rollNo if connected to MongoDB."""
        if self.db is None or self._initialized_indexes:
            return
        try:
            col = self.db[self.COLLECTION_NAME]
            existing_indexes = col.index_information()
            if "rollNo_1" not in existing_indexes and "rollNo_unique" not in existing_indexes:
                col.create_index("rollNo", unique=True, name="rollNo_unique")
                logger.info("Created unique index 'rollNo_unique' on %s", self.COLLECTION_NAME)
            self._initialized_indexes = True
        except Exception as exc:
            logger.warning("Failed to create index on %s: %s", self.COLLECTION_NAME, exc)

    def save_extraction(self, extraction_result: Any) -> str:
        """
        Persist an ExtractionResult document to the 'hostel_students' collection.
        Uses rollNo as unique upsert key.
        """
        # Always mirror in in-memory fallback
        if self._in_memory_fallback:
            self._in_memory_fallback.save(extraction_result)

        if self.db is None:
            return extraction_result.run_id

        # Determine target roll number
        roll_no = None
        if extraction_result.student and "roll_number" in extraction_result.student:
            roll_no = extraction_result.student["roll_number"]
        elif extraction_result.raw_bundle and extraction_result.raw_bundle.student_roll_number:
            roll_no = extraction_result.raw_bundle.student_roll_number

        if not roll_no:
            roll_no = "UNKNOWN"
        roll_no = roll_no.strip().upper()

        now_iso = datetime.now(timezone.utc).isoformat()

        doc: Dict[str, Any] = {
            "rollNo": roll_no,
            "profile": extraction_result.student,
            "room": extraction_result.room,
            "mess": extraction_result.mess,
            "fees": extraction_result.fees,
            "leave": extraction_result.leave,
            "academicYear": extraction_result.academic_year,
            "feeDue": extraction_result.fee_due,
            "source": {
                "runId": extraction_result.run_id,
                "capturedAt": extraction_result.timestamp,
                "source": "PSG Tech Hostel Portal",
                "endpointsCount": extraction_result.endpoints_count,
            },
            "validation": extraction_result.validation,
            "updatedAt": now_iso,
        }

        is_synthetic = bool(
            extraction_result.run_id.startswith("run_test_")
            or extraction_result.run_id.startswith("run_mock_")
            or (extraction_result.student and str(extraction_result.student.get("name", "")).upper() == "TEST RESIDENT")
            or getattr(extraction_result, "is_synthetic", False)
        )
        if is_synthetic:
            doc["is_synthetic"] = True
            doc["source"]["is_synthetic"] = True
            doc["source"]["source"] = "Synthetic Test Fixture"

        col = self.db[self.COLLECTION_NAME]
        col.update_one(
            {"rollNo": roll_no},
            {"$set": doc},
            upsert=True
        )
        logger.info("Saved hostel record for resident %s*** in %s", roll_no[:2], self.COLLECTION_NAME)
        return extraction_result.run_id

    def get_by_roll_number(self, roll_number: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve hostel document for a given roll number.
        """
        roll_clean = roll_number.strip().upper()
        if self.db is not None:
            col = self.db[self.COLLECTION_NAME]
            doc = col.find_one({"rollNo": roll_clean}, {"_id": 0})
            if doc:
                return doc

        # Fallback to in-memory store
        if self._in_memory_fallback:
            mem_result = self._in_memory_fallback.get_by_roll_number(roll_clean)
            if mem_result:
                return {
                    "rollNo": roll_clean,
                    "profile": mem_result.student,
                    "room": mem_result.room,
                    "mess": mem_result.mess,
                    "fees": mem_result.fees,
                    "leave": mem_result.leave,
                    "academicYear": mem_result.academic_year,
                    "feeDue": mem_result.fee_due,
                    "source": {
                        "runId": mem_result.run_id,
                        "capturedAt": mem_result.timestamp,
                        "source": "PSG Tech Hostel Portal",
                        "endpointsCount": mem_result.endpoints_count,
                    },
                    "validation": mem_result.validation,
                    "updatedAt": mem_result.timestamp,
                }

        return None

    def get_by_run_id(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve hostel document by extraction runId."""
        if self.db is not None:
            col = self.db[self.COLLECTION_NAME]
            doc = col.find_one({"source.runId": run_id}, {"_id": 0})
            if doc:
                return doc

        if self._in_memory_fallback:
            mem_result = self._in_memory_fallback.get_by_run_id(run_id)
            if mem_result:
                return self.get_by_roll_number(
                    mem_result.student.get("roll_number", "") if mem_result.student else ""
                )

        return None

    def delete_by_roll(self, roll_number: str) -> bool:
        """Remove a student hostel record."""
        roll_clean = roll_number.strip().upper()
        deleted = False
        if self.db is not None:
            res = self.db[self.COLLECTION_NAME].delete_one({"rollNo": roll_clean})
            deleted = res.deleted_count > 0
        if self._in_memory_fallback:
            mem_res = self._in_memory_fallback.get_by_roll_number(roll_clean)
            if mem_res:
                self._in_memory_fallback.delete_by_run_id(mem_res.run_id)
                deleted = True
        return deleted

    def count(self) -> int:
        """Count total stored hostel documents."""
        if self.db is not None:
            return self.db[self.COLLECTION_NAME].count_documents({})
        if self._in_memory_fallback:
            return self._in_memory_fallback.count()
        return 0
