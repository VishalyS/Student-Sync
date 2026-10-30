"""
Domain parser for /Hostel/Student/studDetails (Student Profile).
"""
from typing import Any, List

from core.exceptions import ParserError
from parser.base import BaseDomainParser
from parser.models import SourceStudentProfile


class StudentProfileParser(BaseDomainParser):
    """
    Parses verified student details response into SourceStudentProfile.
    """
    ENDPOINT = "student_details"

    def parse(self, raw_input: Any) -> SourceStudentProfile:
        payload = self.extract_payload(raw_input)
        records = self.ensure_list(self.ENDPOINT, payload)

        if not records:
            raise ParserError(f"Endpoint '{self.ENDPOINT}' returned empty list; student profile is mandatory")
        if len(records) > 1:
            raise ParserError(f"Endpoint '{self.ENDPOINT}' returned multiple profile records ({len(records)}); expected 1")

        data = self.ensure_dict(self.ENDPOINT, records[0])

        return SourceStudentProfile(
            name=self.validate_type(self.ENDPOINT, data, "name", str),
            rollno=self.validate_type(self.ENDPOINT, data, "rollno", str),
            drollno=self.validate_type(self.ENDPOINT, data, "drollno", str),
            mobile=self.validate_type(self.ENDPOINT, data, "mobile", str),
            programme=self.validate_type(self.ENDPOINT, data, "programme", str),
            class_=self.validate_type(self.ENDPOINT, data, "class_", str),
            father=self.validate_type(self.ENDPOINT, data, "father", str),
            mother=self.validate_type(self.ENDPOINT, data, "mother", str, nullable=True),
            addr=self.validate_type(self.ENDPOINT, data, "addr", str),
            districtName=self.validate_type(self.ENDPOINT, data, "districtName", str),
            stateName=self.validate_type(self.ENDPOINT, data, "stateName", str),
            fmobile=self.validate_type(self.ENDPOINT, data, "fmobile", str),
            mmobile=self.validate_type(self.ENDPOINT, data, "mmobile", str),
            email=self.validate_type(self.ENDPOINT, data, "email", str),
            imgStatus=self.validate_type(self.ENDPOINT, data, "imgStatus", str),
            StudPic=self.validate_type(self.ENDPOINT, data, "StudPic", str),
            progId=self.validate_type(self.ENDPOINT, data, "progId", int),
            degreeId=self.validate_type(self.ENDPOINT, data, "degreeId", int),
            semNo=self.validate_type(self.ENDPOINT, data, "semNo", int),
        )
