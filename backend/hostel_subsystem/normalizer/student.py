"""
Student Profile Normalizer for Student Sync - Hostel subsystem.
Translates SourceStudentProfile into NormalizedStudentProfile.
"""
from typing import Any

from core.exceptions import InvalidNormalizedTypeError
from normalizer.base import (
    normalize_integer,
    normalize_required_string,
    normalize_string,
)
from normalizer.models import NormalizedStudentProfile
from parser.models import SourceStudentProfile


class StudentProfileNormalizer:
    """
    Normalizes parsed student profile domain data.
    Sanitizes string attributes, converts placeholders to None,
    and maps source keys to canonical internal attributes.
    """

    def normalize(self, source: Any) -> NormalizedStudentProfile:
        if not isinstance(source, SourceStudentProfile):
            raise InvalidNormalizedTypeError(
                f"Expected SourceStudentProfile, got {type(source).__name__}"
            )
        
        return NormalizedStudentProfile(
            name=normalize_required_string(source.name, "name"),
            roll_number=normalize_required_string(source.rollno, "rollno"),
            degree_roll_number=normalize_string(source.drollno),
            mobile_number=normalize_string(source.mobile),
            programme=normalize_required_string(source.programme, "programme"),
            class_name=normalize_required_string(source.class_, "class_"),
            father_name=normalize_string(source.father),
            mother_name=normalize_string(source.mother),
            address=normalize_string(source.addr),
            district_name=normalize_string(source.districtName),
            state_name=normalize_string(source.stateName),
            father_mobile=normalize_string(source.fmobile),
            mother_mobile=normalize_string(source.mmobile),
            email=normalize_string(source.email),
            image_status=normalize_string(source.imgStatus),
            photo_base64=normalize_string(source.StudPic),
            programme_id=normalize_integer(source.progId, "progId"),
            degree_id=normalize_integer(source.degreeId, "degreeId"),
            semester_number=normalize_integer(source.semNo, "semNo"),
        )
