"""
Mess Details Normalizer for Student Sync - Hostel subsystem.
Translates SourceMessDetails into NormalizedMessDetails.
"""
from typing import Any, Optional

from core.exceptions import InvalidDateFormatError, InvalidNormalizedTypeError
from normalizer.base import (
    normalize_date,
    normalize_required_string,
    normalize_string,
)
from normalizer.models import NormalizedMessDetails
from parser.models import SourceMessDetails


class MessDetailsNormalizer:
    """
    Normalizes parsed mess subscription domain data.
    Strips leading underscores from server keys, standardizes dietary and token statuses,
    and converts membership date to date.
    """

    def normalize(self, source: Any) -> Optional[NormalizedMessDetails]:
        if source is None:
            return None
        if not isinstance(source, SourceMessDetails):
            raise InvalidNormalizedTypeError(
                f"Expected SourceMessDetails or None, got {type(source).__name__}"
            )
        
        member_since_val = None
        if source._MessMemberSince is not None:
            try:
                member_since_val = normalize_date(source._MessMemberSince, "_MessMemberSince")
            except InvalidDateFormatError:
                # Server may return a term or semester index (e.g., '2') rather than a calendar date
                member_since_val = None

        return NormalizedMessDetails(
            mess_name=normalize_required_string(source._MessName, "_MessName"),
            mess_supervisor=normalize_string(source._MessSupervisor),
            mess_type=normalize_required_string(source._MessType, "_MessType"),
            member_since=member_since_val,
            egg_token_status=normalize_string(source._MessEggToken),
            non_veg_token_status=normalize_string(source._MessNvToken),
        )

