"""
Domain parser for /Hostel/Student/StudentView HTML payload.
Parses server pre-rendered tables:
1. Mess Bill table (Year, Month, Total)
2. Transaction History table (Accordion by Year: S No, Txn Date, Txn Amount, Status)
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup

from core.logging import get_logger


@dataclass(frozen=True)
class SourceMessBillRow:
    """Raw parsed row from messBillTable in StudentView."""
    year: str
    month: str
    total_amount: str


@dataclass(frozen=True)
class SourceTransactionRow:
    """Raw parsed row from payment transactions accordion in StudentView."""
    year: str
    serial_number: str
    transaction_date: str
    transaction_amount: str
    status: str


class StudentViewParser:
    """
    Parses pre-rendered HTML tables from /Hostel/Student/StudentView.
    Extracts itemized monthly mess bills and financial payment transactions.
    """

    def __init__(self, logger: Optional[Any] = None) -> None:
        self.logger = logger or get_logger("student_sync_hostel.parser.view")

    def parse_mess_bills(self, html_content: str) -> List[SourceMessBillRow]:
        """Parse rows from #messBillTable."""
        if not html_content or not isinstance(html_content, str):
            return []

        soup = BeautifulSoup(html_content, "html.parser")
        table = soup.find("table", {"id": "messBillTable"})
        if not table:
            return []

        tbody = table.find("tbody")
        if not tbody:
            return []

        rows: List[SourceMessBillRow] = []
        for tr in tbody.find_all("tr"):
            tds = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(tds) >= 3:
                rows.append(
                    SourceMessBillRow(
                        year=tds[0],
                        month=tds[1],
                        total_amount=tds[2],
                    )
                )
        return rows

    def parse_transactions(self, html_content: str) -> List[SourceTransactionRow]:
        """Parse payment transaction records from accordion table."""
        if not html_content or not isinstance(html_content, str):
            return []

        soup = BeautifulSoup(html_content, "html.parser")
        transactions: List[SourceTransactionRow] = []

        for table in soup.find_all("table"):
            headers = [th.get_text(strip=True) for th in table.find_all("th")]
            if "Txn Amount" in headers and "S No" in headers:
                # Determine academic year from accordion header or parent
                year = "CURRENT"
                acc = table.find_parent(class_="accordion-item")
                if acc:
                    header_el = acc.find(class_="accordion-header")
                    if header_el:
                        year = header_el.get_text(strip=True)

                for tr in table.find_all("tr"):
                    tds = [td.get_text(strip=True) for td in tr.find_all("td")]
                    if len(tds) >= 4:
                        transactions.append(
                            SourceTransactionRow(
                                year=year,
                                serial_number=tds[0],
                                transaction_date=tds[1],
                                transaction_amount=tds[2],
                                status=tds[3],
                            )
                        )

        return transactions
