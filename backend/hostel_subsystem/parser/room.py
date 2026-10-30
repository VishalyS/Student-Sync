"""
Domain parser for /Hostel/Student/roomDetails (Room Details).
"""
from typing import Any, Optional

from core.exceptions import ParserError
from parser.base import BaseDomainParser
from parser.models import SourceRoomDetails


class RoomDetailsParser(BaseDomainParser):
    """
    Parses verified room details response into Optional[SourceRoomDetails].
    Returns None if student has no allocated room (empty list []).
    """
    ENDPOINT = "room_details"

    def parse(self, raw_input: Any) -> Optional[SourceRoomDetails]:
        payload = self.extract_payload(raw_input)
        records = self.ensure_list(self.ENDPOINT, payload)

        if not records:
            return None

        if len(records) > 1:
            raise ParserError(f"Endpoint '{self.ENDPOINT}' returned multiple room records ({len(records)}); expected at most 1")

        data = self.ensure_dict(self.ENDPOINT, records[0])

        return SourceRoomDetails(
            hostel=self.validate_type(self.ENDPOINT, data, "hostel", str),
            block=self.validate_type(self.ENDPOINT, data, "block", str),
            hos_id=self.validate_type(self.ENDPOINT, data, "hos_id", int),
            block_id=self.validate_type(self.ENDPOINT, data, "block_id", int),
            room_type=self.validate_type(self.ENDPOINT, data, "room_type", str),
            doj=self.validate_type(self.ENDPOINT, data, "doj", str),
            floor_room=self.validate_type(self.ENDPOINT, data, "floor_room", str),
            room=self.validate_type(self.ENDPOINT, data, "room", str),
            warden=self.validate_type(self.ENDPOINT, data, "warden", str),
            restutor=self.validate_type(self.ENDPOINT, data, "restutor", str),
        )
