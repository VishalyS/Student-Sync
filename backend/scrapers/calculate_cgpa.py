try:
    from backend.database import user_collection
except ImportError:
    try:
        from database import user_collection
    except ImportError:
        user_collection = None
import re

def calculate_cgpa_from_data(data):
    """
    Calculates CGPA from structured course result records.
    Handles 'Credit Point' / 'Credit' and 'Mark' / 'Grade/Remark' columns.
    :param data: list of dicts with course result rows
    :return: float CGPA rounded to 2 decimal places or None
    """
    try:
        if not data:
            return None

        tot_credit = 0.0
        credit_grade_product = 0.0

        for entry in data:
            if not isinstance(entry, dict):
                continue
            credit_val = entry.get('Credit Point') or entry.get('Credit') or entry.get('credits')
            grade_val = entry.get('Mark') or entry.get('Grade/Remark') or entry.get('Grade') or entry.get('grade')
            gp_val = entry.get('grade_point')

            if not credit_val:
                continue

            try:
                credit = float(credit_val)
            except (ValueError, TypeError):
                continue

            if gp_val is not None:
                try:
                    grade = float(gp_val)
                    tot_credit += credit
                    credit_grade_product += credit * grade
                    continue
                except (ValueError, TypeError):
                    pass

            if grade_val:
                # Grade conversion map
                gp_map = {'O': 10.0, 'A+': 9.0, 'A': 8.0, 'B+': 7.0, 'B': 6.0, 'C': 5.0, 'RA': 0.0, 'W': 0.0, 'SA': 0.0}
                if str(grade_val).strip().upper() in gp_map:
                    tot_credit += credit
                    credit_grade_product += credit * gp_map[str(grade_val).strip().upper()]
                    continue

                grade_match = re.search(r'\b(10|[0-9])\b', str(grade_val))
                if grade_match:
                    grade = float(grade_match.group(1))
                    tot_credit += credit
                    credit_grade_product += credit * grade

        if tot_credit > 0:
            return round(credit_grade_product / tot_credit, 2)
    except Exception as e:
        print(f"Error calculating CGPA: {e}")
    return None


def calculate_cgpa(data, user, table):
    """
    Updates the database with calculated CGPA and result table for background jobs.
    """
    try:
        if not data:
            return None

        cgpa = calculate_cgpa_from_data(data)
        if cgpa is not None and user_collection is not None:
            user_collection.update_one(
                {'rollNo': user['rollNo']},
                {'$set': {'cgpa': cgpa, 'result_table': table}}
            )
        return cgpa
    except Exception as e:
        print(f"Error in calculate_cgpa for user {user.get('rollNo', 'unknown')}: {e}")
        return None
