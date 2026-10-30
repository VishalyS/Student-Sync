"""
Normalizer for Mess Bills and Transaction History records extracted from StudentView.
Translates string rows into canonical dataclasses with Decimal financial values.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from normalizer.base import normalize_required_string, normalize_string
from parser.view import SourceMessBillRow, SourceTransactionRow


@dataclass(frozen=True)
class NormalizedMessBillItem:
    """Canonical representation of an itemized monthly mess bill."""
    year: str
    month: str
    total_amount: Decimal

    def to_dict(self) -> dict:
        return {
            "year": self.year,
            "month": self.month,
            "total_amount": float(self.total_amount),
        }


@dataclass(frozen=True)
class NormalizedTransactionItem:
    """Canonical representation of a hostel fee payment transaction."""
    year: str
    serial_number: str
    transaction_date: str
    transaction_amount: Decimal
    status: str

    def to_dict(self) -> dict:
        return {
            "year": self.year,
            "serial_number": self.serial_number,
            "transaction_date": self.transaction_date,
            "transaction_amount": float(self.transaction_amount),
            "status": self.status,
        }


class StudentViewNormalizer:
    """Normalizes raw parsed view rows into typed canonical items."""

    def normalize_mess_bills(self, rows: List[SourceMessBillRow]) -> List[NormalizedMessBillItem]:
        items: List[NormalizedMessBillItem] = []
        for r in rows:
            clean_amt = r.total_amount.replace(",", "").strip()
            try:
                amt = Decimal(clean_amt)
            except (InvalidOperation, ValueError):
                amt = Decimal("0.00")

            items.append(
                NormalizedMessBillItem(
                    year=normalize_required_string(r.year, "year"),
                    month=normalize_required_string(r.month, "month").upper(),
                    total_amount=amt,
                )
            )
        return items

    def normalize_transactions(self, rows: List[SourceTransactionRow]) -> List[NormalizedTransactionItem]:
        items: List[NormalizedTransactionItem] = []
        for r in rows:
            clean_amt = r.transaction_amount.replace(",", "").strip()
            try:
                amt = Decimal(clean_amt)
            except (InvalidOperation, ValueError):
                amt = Decimal("0.00")

            items.append(
                NormalizedTransactionItem(
                    year=normalize_required_string(r.year, "year"),
                    serial_number=normalize_required_string(r.serial_number, "serial_number"),
                    transaction_date=normalize_required_string(r.transaction_date, "transaction_date"),
                    transaction_amount=amt,
                    status=normalize_required_string(r.status, "status"),
                )
            )
        return items
