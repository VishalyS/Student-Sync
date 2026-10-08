"""
Hostel Service Layer for Student Sync Backend.
Bridges Student Sync API routes with the standalone Hostel extraction subsystem
and the isolated 'hostel_students' MongoDB collection.
Enforces strict student isolation and non-destructive operations.
"""
import os
import sys
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("studentsync.hostel.service")

# Ensure standalone hostel subsystem is on sys.path
HOSTEL_SUBSYSTEM_PATH = os.getenv(
    "HOSTEL_SUBSYSTEM_PATH",
    r"C:\Users\visha\OneDrive\Desktop\Student Sync - Hostel"
)
if os.path.exists(HOSTEL_SUBSYSTEM_PATH) and HOSTEL_SUBSYSTEM_PATH not in sys.path:
    sys.path.insert(0, HOSTEL_SUBSYSTEM_PATH)

from hostel_repository import HostelMongoRepository

try:
    from pipeline import ExtractionResult, HostelExtractionService, HostelPipelineRunner
    from scripts.run_capture import create_mock_bundle
except ImportError as exc:
    logger.warning("Could not import standalone hostel package: %s", exc)
    HostelPipelineRunner = None
    create_mock_bundle = None
    ExtractionResult = None

try:
    from database import db
except ImportError:
    try:
        from backend.database import db
    except ImportError:
        db = None


class HostelService:
    """
    Application service managing hostel data extraction, caching, and retrieval.
    Decoupled from academic scrapers (StudZone 1 & 2).
    """

    def __init__(self, repository: Optional[HostelMongoRepository] = None) -> None:
        self.repository = repository or HostelMongoRepository(db=db)
        self.runner = HostelPipelineRunner() if HostelPipelineRunner else None

    def get_student_hostel_overview(
        self,
        roll_number: str,
        force_refresh: bool = False,
        password: Optional[str] = None,
    ) -> Tuple[Optional[Dict[str, Any]], int, Optional[str]]:
        """
        Retrieve complete hostel data for an authenticated resident.
        Returns (response_payload, status_code, error_message).
        """
        roll_clean = roll_number.strip().upper()
        if not roll_clean:
            return None, 400, "Invalid roll number."

        # 1. Check existing record in repository unless force_refresh is requested
        if not force_refresh:
            existing_doc = self.repository.get_by_roll_number(roll_clean)
            if existing_doc:
                return self._format_response(existing_doc), 200, None

        # 2. If force_refresh or missing, attempt to extract if credentials are provided
        if self.runner and password:
            try:
                extraction = self.runner.extract(
                    roll_number=roll_clean,
                    password=password,
                    raise_on_error=False,
                )
                if extraction.is_success:
                    self.repository.save_extraction(extraction)
                    doc = self.repository.get_by_roll_number(roll_clean)
                    if doc:
                        return self._format_response(doc), 200, None
            except Exception as exc:
                logger.warning("Live hostel extraction failed for %s***: %s", roll_clean[:2], exc)

        # 3. If record still missing after check
        existing_doc = self.repository.get_by_roll_number(roll_clean)
        if existing_doc:
            return self._format_response(existing_doc), 200, None

        return None, 404, f"No hostel allocation record found for student {roll_clean}."

    def get_student_room(
        self, roll_number: str, force_refresh: bool = False, password: Optional[str] = None
    ) -> Tuple[Optional[Dict[str, Any]], int, Optional[str]]:
        """Retrieve room allocation section."""
        overview, status, err = self.get_student_hostel_overview(
            roll_number=roll_number, force_refresh=force_refresh, password=password
        )
        if err or not overview:
            return None, status, err

        return {
            "success": True,
            "data": overview["data"].get("room"),
            "meta": overview["meta"],
        }, 200, None

    def get_student_mess(
        self, roll_number: str, force_refresh: bool = False, password: Optional[str] = None
    ) -> Tuple[Optional[Dict[str, Any]], int, Optional[str]]:
        """Retrieve mess subscription section."""
        overview, status, err = self.get_student_hostel_overview(
            roll_number=roll_number, force_refresh=force_refresh, password=password
        )
        if err or not overview:
            return None, status, err

        return {
            "success": True,
            "data": overview["data"].get("mess"),
            "meta": overview["meta"],
        }, 200, None

    def get_student_fees(
        self, roll_number: str, force_refresh: bool = False, password: Optional[str] = None
    ) -> Tuple[Optional[Dict[str, Any]], int, Optional[str]]:
        """Retrieve hostel fee balance and dues."""
        overview, status, err = self.get_student_hostel_overview(
            roll_number=roll_number, force_refresh=force_refresh, password=password
        )
        if err or not overview:
            return None, status, err

        return {
            "success": True,
            "data": {
                "fees": overview["data"].get("fees"),
                "feeDue": overview["data"].get("feeDue"),
            },
            "meta": overview["meta"],
        }, 200, None

    def get_student_leave(
        self, roll_number: str, force_refresh: bool = False, password: Optional[str] = None
    ) -> Tuple[Optional[Dict[str, Any]], int, Optional[str]]:
        """Retrieve leave summary, approvers, and application history."""
        overview, status, err = self.get_student_hostel_overview(
            roll_number=roll_number, force_refresh=force_refresh, password=password
        )
        if err or not overview:
            return None, status, err

        return {
            "success": True,
            "data": overview["data"].get("leave"),
            "meta": overview["meta"],
        }, 200, None

    def populate_synthetic_record(
        self, roll_number: str, run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Populate an isolated synthetic hostel record for deterministic testing.
        Guarantees 100% offline testing without touching the live portal.
        """
        if not create_mock_bundle or not self.runner:
            raise RuntimeError("Standalone hostel package not available for mock bundle creation.")

        roll_clean = roll_number.strip().upper()
        mock_bundle = create_mock_bundle(roll_clean, run_id=run_id)
        extraction = self.runner.extract_from_raw(mock_bundle, target_roll_number=roll_clean)
        self.repository.save_extraction(extraction)
        return self.repository.get_by_roll_number(roll_clean)

    def _format_response(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Wrap database document into clean, standardized API response envelope."""
        source_meta = doc.get("source", {})
        return {
            "success": True,
            "data": {
                "profile": doc.get("profile"),
                "room": doc.get("room"),
                "mess": doc.get("mess"),
                "fees": doc.get("fees"),
                "leave": doc.get("leave"),
                "academicYear": doc.get("academicYear"),
                "feeDue": doc.get("feeDue"),
            },
            "meta": {
                "rollNo": doc.get("rollNo"),
                "updatedAt": doc.get("updatedAt"),
                "source": source_meta.get("source", "PSG Tech Hostel Portal"),
                "runId": source_meta.get("runId"),
            },
        }


# Global default service instance
hostel_service = HostelService()
