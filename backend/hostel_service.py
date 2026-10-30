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
    from hostel_repository import HostelMongoRepository
except ImportError:
    from backend.hostel_repository import HostelMongoRepository

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


def is_synthetic_document(doc: Optional[Dict[str, Any]]) -> bool:
    """Returns True if the document was generated from a synthetic/mock test fixture."""
    if not doc or not isinstance(doc, dict):
        return False
    source = doc.get("source", {})
    run_id = str(source.get("runId", "")).lower()
    student_name = str((doc.get("profile") or {}).get("student_name", "")).upper()
    return (
        run_id.startswith("run_test_")
        or run_id.startswith("run_mock_")
        or student_name == "TEST RESIDENT"
        or bool(doc.get("is_synthetic"))
        or bool(source.get("is_synthetic"))
    )


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
        allow_synthetic: bool = False,
    ) -> Tuple[Optional[Dict[str, Any]], int, Optional[str]]:
        """
        Retrieve complete hostel data for an authenticated resident.
        Guarantees that live portal data is retrieved and synthetic test data is never served to real students.
        Returns (response_payload, status_code, error_message).
        """
        roll_clean = roll_number.strip().upper()
        if not roll_clean:
            return None, 400, "Invalid roll number."

        # Check existing record in repository
        existing_doc = self.repository.get_by_roll_number(roll_clean)
        is_synthetic = is_synthetic_document(existing_doc)

        # 1. If valid, real live record exists and no refresh requested, return it
        if existing_doc and not is_synthetic and not force_refresh:
            return self._format_response(existing_doc), 200, None

        # 2. If force_refresh is requested, record is missing, OR record is synthetic:
        # attempt live extraction from the hostel portal if student credentials are provided
        if self.runner and password:
            try:
                extraction = self.runner.extract(
                    roll_number=roll_clean,
                    password=password,
                    raise_on_error=False,
                )
                if extraction.is_success:
                    prev_room = (existing_doc.get("room") or {}).get("room_number") if existing_doc else None
                    prev_mess = (existing_doc.get("mess") or {}).get("mess_name") if existing_doc else None
                    self.repository.save_extraction(extraction)
                    doc = self.repository.get_by_roll_number(roll_clean)

                    if doc and not is_synthetic:
                        new_room = (doc.get("room") or {}).get("room_number")
                        new_mess = (doc.get("mess") or {}).get("mess_name")
                        if prev_room and new_room and prev_room != new_room:
                            try:
                                from speed_ser import dispatch_normalized_notification
                                dispatch_normalized_notification(
                                    roll_no=roll_clean,
                                    user=None,
                                    event_data={
                                        "category": "hostel",
                                        "type": "hostel_room",
                                        "module": "Hostel",
                                        "source": "Hostel Portal",
                                        "title": "Hostel Room Updated",
                                        "message": f"Your hostel room allocation has changed from {prev_room} to {new_room}.",
                                        "change_key": f"room_{new_room}",
                                        "changeData": {"previousRoom": prev_room, "newRoom": new_room}
                                    }
                                )
                            except Exception as notif_err:
                                logger.warning("Could not dispatch hostel room notification: %s", notif_err)

                        if prev_mess and new_mess and prev_mess != new_mess:
                            try:
                                from speed_ser import dispatch_normalized_notification
                                dispatch_normalized_notification(
                                    roll_no=roll_clean,
                                    user=None,
                                    event_data={
                                        "category": "hostel",
                                        "type": "hostel_mess",
                                        "module": "Hostel",
                                        "source": "Hostel Portal",
                                        "title": "Hostel Mess Updated",
                                        "message": f"Your hostel mess subscription has changed from {prev_mess} to {new_mess}.",
                                        "change_key": f"mess_{new_mess}",
                                        "changeData": {"previousMess": prev_mess, "newMess": new_mess}
                                    }
                                )
                            except Exception as notif_err:
                                logger.warning("Could not dispatch hostel mess notification: %s", notif_err)

                    if doc:
                        return self._format_response(doc), 200, None
                else:
                    error_msg = extraction.error_message if hasattr(extraction, "error_message") else None
                    logger.warning("Live hostel extraction failed for %s***: %s", roll_clean[:2], error_msg)
            except Exception as exc:
                logger.warning("Live hostel extraction exception for %s***: %s", roll_clean[:2], exc)

        # 3. Fallback: If a valid real record exists from an earlier live run, return it
        if existing_doc and not is_synthetic:
            return self._format_response(existing_doc), 200, None

        # 4. Explicit test mode fallback only
        allow_mock = allow_synthetic or (os.getenv("HOSTEL_ALLOW_SYNTHETIC", "").lower() in ("1", "true"))
        if existing_doc and is_synthetic and allow_mock:
            return self._format_response(existing_doc), 200, None

        return None, 404, f"No verified hostel records found for student {roll_clean}. Please verify portal credentials or sync status."

    def get_student_room(
        self, roll_number: str, force_refresh: bool = False, password: Optional[str] = None, allow_synthetic: bool = False
    ) -> Tuple[Optional[Dict[str, Any]], int, Optional[str]]:
        """Retrieve room allocation section."""
        overview, status, err = self.get_student_hostel_overview(
            roll_number=roll_number, force_refresh=force_refresh, password=password, allow_synthetic=allow_synthetic
        )
        if err or not overview:
            return None, status, err

        return {
            "success": True,
            "data": overview["data"].get("room"),
            "meta": overview["meta"],
        }, 200, None

    def get_student_mess(
        self, roll_number: str, force_refresh: bool = False, password: Optional[str] = None, allow_synthetic: bool = False
    ) -> Tuple[Optional[Dict[str, Any]], int, Optional[str]]:
        """Retrieve mess subscription section."""
        overview, status, err = self.get_student_hostel_overview(
            roll_number=roll_number, force_refresh=force_refresh, password=password, allow_synthetic=allow_synthetic
        )
        if err or not overview:
            return None, status, err

        return {
            "success": True,
            "data": overview["data"].get("mess"),
            "meta": overview["meta"],
        }, 200, None

    def get_student_fees(
        self, roll_number: str, force_refresh: bool = False, password: Optional[str] = None, allow_synthetic: bool = False
    ) -> Tuple[Optional[Dict[str, Any]], int, Optional[str]]:
        """Retrieve hostel fee balance and dues."""
        overview, status, err = self.get_student_hostel_overview(
            roll_number=roll_number, force_refresh=force_refresh, password=password, allow_synthetic=allow_synthetic
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
        self, roll_number: str, force_refresh: bool = False, password: Optional[str] = None, allow_synthetic: bool = False
    ) -> Tuple[Optional[Dict[str, Any]], int, Optional[str]]:
        """Retrieve leave summary, approvers, and application history."""
        overview, status, err = self.get_student_hostel_overview(
            roll_number=roll_number, force_refresh=force_refresh, password=password, allow_synthetic=allow_synthetic
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
