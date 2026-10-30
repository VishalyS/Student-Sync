"""
Domain parsers for fee-related endpoints:
- /Hostel/Student/StudHosFeesDet (Hostel Fees Details)
- /Hostel/Student/GetYear (Academic Year)
- /Hostel/Student/GetHosFee (Hostel Fee Due)
"""
from typing import Any, List, Optional

from core.exceptions import ParserError
from parser.base import BaseDomainParser
from parser.models import (
    SourceAcademicYearItem,
    SourceFeesDetails,
    SourceHostelFeeDueItem,
)


class HostelFeesParser(BaseDomainParser):
    """
    Parses verified hostel fees response into Optional[SourceFeesDetails].
    Preserves monetary amounts as verbatim decimal strings without numeric conversion.
    """
    ENDPOINT = "fees_details"

    def parse(self, raw_input: Any) -> Optional[SourceFeesDetails]:
        payload = self.extract_payload(raw_input)
        records = self.ensure_list(self.ENDPOINT, payload)

        if not records:
            return None

        if len(records) > 1:
            raise ParserError(f"Endpoint '{self.ENDPOINT}' returned multiple fee records ({len(records)}); expected at most 1")

        data = self.ensure_dict(self.ENDPOINT, records[0])

        return SourceFeesDetails(
            _HosFeesBalance=self.validate_type(self.ENDPOINT, data, "_HosFeesBalance", str),
            _HosFeesDeposit=self.validate_type(self.ENDPOINT, data, "_HosFeesDeposit", str),
            _HosFeesEstab=self.validate_type(self.ENDPOINT, data, "_HosFeesEstab", str),
            _TokenBalance=self.validate_type(self.ENDPOINT, data, "_TokenBalance", str),
        )


class AcademicYearParser(BaseDomainParser):
    """
    Parses /Hostel/Student/GetYear into List[SourceAcademicYearItem].
    """
    ENDPOINT = "academic_year"

    def parse(self, raw_input: Any) -> List[SourceAcademicYearItem]:
        payload = self.extract_payload(raw_input)
        records = self.ensure_list(self.ENDPOINT, payload)

        results = []
        for item in records:
            data = self.ensure_dict(self.ENDPOINT, item)
            results.append(
                SourceAcademicYearItem(
                    proc_year=str(self.require_field(self.ENDPOINT, data, "proc_year")),
                    amt=str(data["amt"]) if data.get("amt") is not None else None,
                )
            )
        return results


class HostelFeeDueParser(BaseDomainParser):
    """
    Parses /Hostel/Student/GetHosFee into List[SourceHostelFeeDueItem].
    Returns empty list [] when student has no itemized fee dues.
    """
    ENDPOINT = "hostel_fee_due"

    def parse(self, raw_input: Any) -> List[SourceHostelFeeDueItem]:
        payload = self.extract_payload(raw_input)
        records = self.ensure_list(self.ENDPOINT, payload)

        results = []
        for item in records:
            data = self.ensure_dict(self.ENDPOINT, item)
            hos_id_val = data.get("hos_id")
            hos_id_int = int(hos_id_val) if hos_id_val is not None and str(hos_id_val).isdigit() else None
            results.append(
                SourceHostelFeeDueItem(
                    res=str(data["res"]) if "res" in data and data["res"] is not None else None,
                    amount=str(data["amount"]) if "amount" in data and data["amount"] is not None else None,
                    hostel_name=str(data["hostel_name"]) if "hostel_name" in data and data["hostel_name"] is not None else None,
                    block_name=str(data["block_name"]) if "block_name" in data and data["block_name"] is not None else None,
                    tariff_id=str(data["tariff_id"]) if "tariff_id" in data and data["tariff_id"] is not None else None,
                    hos_id=hos_id_int,
                )
            )
        return results
