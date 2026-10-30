"""
Room Details Normalizer for Student Sync - Hostel subsystem.
Translates SourceRoomDetails into NormalizedRoomDetails.
"""
from typing import Any, Optional

from core.exceptions import InvalidNormalizedTypeError
from normalizer.base import (
    normalize_date,
    normalize_integer,
    normalize_required_string,
    normalize_string,
)
from normalizer.models import NormalizedRoomDetails
from parser.models import SourceRoomDetails


class RoomDetailsNormalizer:
    """
    Normalizes parsed room allotment domain data.
    Converts allotment date string to date, maps identifiers,
    and supports unallocated room states (None).
    """

    def normalize(self, source: Any) -> Optional[NormalizedRoomDetails]:
        if source is None:
            return None
        if not isinstance(source, SourceRoomDetails):
            raise InvalidNormalizedTypeError(
                f"Expected SourceRoomDetails or None, got {type(source).__name__}"
            )
        
        return NormalizedRoomDetails(
            hostel_name=normalize_required_string(source.hostel, "hostel"),
            block_name=normalize_required_string(source.block, "block"),
            hostel_id=normalize_integer(source.hos_id, "hos_id"),
            block_id=normalize_integer(source.block_id, "block_id"),
            room_type=normalize_required_string(source.room_type, "room_type"),
            date_of_joining=normalize_date(source.doj, "doj"),
            floor_description=normalize_string(source.floor_room),
            room_number=normalize_required_string(source.room, "room"),
            warden_name=normalize_string(source.warden),
            resident_tutor=normalize_string(source.restutor),
        )
