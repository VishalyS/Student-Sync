"""
Domain parser for /Hostel/Student/StudMessDet (Mess Details).
"""
from typing import Any, Optional

from core.exceptions import ParserError
from parser.base import BaseDomainParser
from parser.models import SourceMessDetails


class MessDetailsParser(BaseDomainParser):
    """
    Parses verified mess details response into Optional[SourceMessDetails].
    Returns None if student has no allocated mess facility (empty list []).
    """
    ENDPOINT = "mess_details"

    def parse(self, raw_input: Any) -> Optional[SourceMessDetails]:
        payload = self.extract_payload(raw_input)
        records = self.ensure_list(self.ENDPOINT, payload)

        if not records:
            return None

        if len(records) > 1:
            raise ParserError(f"Endpoint '{self.ENDPOINT}' returned multiple mess records ({len(records)}); expected at most 1")

        data = self.ensure_dict(self.ENDPOINT, records[0])

        return SourceMessDetails(
            _MessName=self.validate_type(self.ENDPOINT, data, "_MessName", str),
            _MessSupervisor=self.validate_type(self.ENDPOINT, data, "_MessSupervisor", str),
            _MessType=self.validate_type(self.ENDPOINT, data, "_MessType", str),
            _MessMemberSince=self.validate_type(self.ENDPOINT, data, "_MessMemberSince", str),
            _MessEggToken=self.validate_type(self.ENDPOINT, data, "_MessEggToken", str),
            _MessNvToken=self.validate_type(self.ENDPOINT, data, "_MessNvToken", str),
        )
