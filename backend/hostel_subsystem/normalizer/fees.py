"""
Hostel Fees, Academic Year, and Fee Due Normalizers for Student Sync - Hostel subsystem.
Translates fee domain records into canonical models with Decimal monetary precision.
"""
from typing import Any, List, Optional

from core.exceptions import InvalidNormalizedTypeError
from normalizer.base import (
    normalize_decimal,
    normalize_optional_integer,
    normalize_required_decimal,
    normalize_required_string,
    normalize_string,
)
from normalizer.models import (
    NormalizedAcademicYearItem,
    NormalizedFeesDetails,
    NormalizedHostelFeeDueItem,
)
from parser.models import (
    SourceAcademicYearItem,
    SourceFeesDetails,
    SourceHostelFeeDueItem,
)


class HostelFeesNormalizer:
    """
    Normalizes parsed hostel fee balances.
    Translates monetary decimal strings into high-precision Decimal instances.
    """

    def normalize(self, source: Any) -> Optional[NormalizedFeesDetails]:
        if source is None:
            return None
        if not isinstance(source, SourceFeesDetails):
            raise InvalidNormalizedTypeError(
                f"Expected SourceFeesDetails or None, got {type(source).__name__}"
            )
        
        return NormalizedFeesDetails(
            hostel_fee_balance=normalize_required_decimal(
                source._HosFeesBalance, "_HosFeesBalance"
            ),
            caution_deposit=normalize_required_decimal(
                source._HosFeesDeposit, "_HosFeesDeposit"
            ),
            establishment_fee=normalize_required_decimal(
                source._HosFeesEstab, "_HosFeesEstab"
            ),
            mess_token_balance=normalize_required_decimal(
                source._TokenBalance, "_TokenBalance"
            ),
        )


class AcademicYearNormalizer:
    """
    Normalizes parsed academic year processing records.
    Preserves academic year identifier and normalizes optional amounts to Decimal.
    """

    def normalize(self, source: Any) -> List[NormalizedAcademicYearItem]:
        if not isinstance(source, list):
            raise InvalidNormalizedTypeError(
                f"Expected list of SourceAcademicYearItem, got {type(source).__name__}"
            )
        
        normalized_items: List[NormalizedAcademicYearItem] = []
        for item in source:
            if not isinstance(item, SourceAcademicYearItem):
                raise InvalidNormalizedTypeError(
                    f"Expected SourceAcademicYearItem, got {type(item).__name__}"
                )
            normalized_items.append(
                NormalizedAcademicYearItem(
                    academic_year=normalize_required_string(item.proc_year, "proc_year"),
                    amount=normalize_decimal(item.amt, "amt"),
                )
            )
        return normalized_items


class HostelFeeDueNormalizer:
    """
    Normalizes parsed itemized hostel fee dues.
    Converts amount strings to Decimal and preserves facility/tariff context.
    """

    def normalize(self, source: Any) -> List[NormalizedHostelFeeDueItem]:
        if not isinstance(source, list):
            raise InvalidNormalizedTypeError(
                f"Expected list of SourceHostelFeeDueItem, got {type(source).__name__}"
            )
        
        normalized_items: List[NormalizedHostelFeeDueItem] = []
        for item in source:
            if not isinstance(item, SourceHostelFeeDueItem):
                raise InvalidNormalizedTypeError(
                    f"Expected SourceHostelFeeDueItem, got {type(item).__name__}"
                )
            normalized_items.append(
                NormalizedHostelFeeDueItem(
                    reservation_status=normalize_string(item.res),
                    amount=normalize_decimal(item.amount, "amount"),
                    hostel_name=normalize_string(item.hostel_name),
                    block_name=normalize_string(item.block_name),
                    tariff_id=normalize_string(item.tariff_id),
                    hostel_id=normalize_optional_integer(item.hos_id, "hos_id"),
                )
            )
        return normalized_items
