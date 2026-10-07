import sys
import os

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from notifications.change_detector import detect_granular_changes, compute_change_hash

def run_all_tests():
    print('======================================================================')
    print('GRANULAR NOTIFICATION CHANGE DETECTION TEST SUITE')
    print('======================================================================\n')

    roll_no = '25MX232'

    # Base snapshot
    base_user = {
        'rollNo': roll_no,
        'name': 'VISHALY S',
        'cgpa': '7.82',
        'studzone1': {
            'parsed_attendance': [
                {'code': '24MX11', 'name': 'Data Structures', 'percentage': '82%', 'attended': '41', 'total_classes': '50'},
                {'code': '24MX12', 'name': 'Computer Networks', 'percentage': '81%', 'attended': '40', 'total_classes': '50'}
            ],
            'parsed_marks': [
                {'code': '24MX11', 'name': 'DBMS', 'ca1': '18', 'ca2': '18', 'ca3': '-', 'total': '36'},
                {'code': '24MX12', 'name': 'Computer Networks', 'ca1': '20', 'ca2': '-', 'ca3': '-', 'total': '20'}
            ],
            'fee_status': 'Tuition Fee Cleared',
            'hostel_status': 'Hostel Room Block A-204',
            'scholarship_status': 'Submitted',
            'scholarships': {'applied': [{'title': 'Merit Scholarship'}], 'received': []},
            'feedback': [{'type': 'Course', 'status': 'Not Scheduled'}]
        },
        'studzone2': {
            'parsed_results': [
                {'sem': '3', 'code': '24MX11', 'title': 'Data Structures', 'credits': '4', 'grade': 'B+', 'grade_point': 7.0}
            ],
            'cgpa': '7.82',
            'parsed_timetable': [
                {'course_code': '24MX11', 'course_title': 'DBMS', 'exam_date': '12 Sep', 'session': 'FN', 'timing': '10:00 AM - 01:00 PM'}
            ],
            'seating_html': None,
            'circulars': [{'title': 'Guidelines 2026'}]
        }
    }

    # 1. TEST CASE 1: No change -> 0 notifications
    n1 = detect_granular_changes(roll_no, base_user, base_user['studzone1'], base_user['studzone2'])
    print('Test 1 (No change): Detected', len(n1), 'notifications ->', 'PASS' if len(n1) == 0 else 'FAIL')
    assert len(n1) == 0

    # 2. TEST CASE 2: Attendance change (82% -> 86%)
    sz1_att = {
        'parsed_attendance': [
            {'code': '24MX11', 'name': 'Data Structures', 'percentage': '86%', 'attended': '43', 'total_classes': '50'},
            {'code': '24MX12', 'name': 'Computer Networks', 'percentage': '81%', 'attended': '40', 'total_classes': '50'}
        ]
    }
    n2 = detect_granular_changes(roll_no, base_user, sz1_att, base_user['studzone2'])
    print('Test 2 (Attendance Change):', n2[0]['title'], '—', n2[0]['description'])
    assert 'Data Structures attendance changed from 82% → 86%.' in n2[0]['description']

    # 3. TEST CASE 3: Marks change (DBMS CA2 marks changed from 18 -> 21)
    sz1_marks = {
        'parsed_marks': [
            {'code': '24MX11', 'name': 'DBMS', 'ca1': '18', 'ca2': '21', 'ca3': '-', 'total': '39'},
            {'code': '24MX12', 'name': 'Computer Networks', 'ca1': '20', 'ca2': '-', 'ca3': '-', 'total': '20'}
        ]
    }
    n3 = detect_granular_changes(roll_no, base_user, sz1_marks, base_user['studzone2'])
    print('Test 3 (Marks Change):', n3[0]['title'], '—', n3[0]['description'])
    assert 'DBMS CA2 marks changed from 18 → 21.' in n3[0]['description']

    # 4. TEST CASE 4: Results published (Semester 3 results published: 6 new course results available)
    sz2_res = {
        'parsed_results': [
            {'sem': '3', 'code': '24MX11', 'title': 'Data Structures', 'credits': '4', 'grade': 'A+', 'grade_point': 10.0},
            {'sem': '3', 'code': '24MX12', 'title': 'Computer Networks', 'credits': '4', 'grade': 'A', 'grade_point': 9.0},
            {'sem': '3', 'code': '24MX13', 'title': 'DBMS', 'credits': '4', 'grade': 'A', 'grade_point': 9.0},
            {'sem': '3', 'code': '24MX14', 'title': 'Operating Systems', 'credits': '4', 'grade': 'B+', 'grade_point': 8.0},
            {'sem': '3', 'code': '24MX15', 'title': 'Software Engineering', 'credits': '4', 'grade': 'A+', 'grade_point': 10.0},
            {'sem': '3', 'code': '24MX16', 'title': 'Web Technologies', 'credits': '4', 'grade': 'O', 'grade_point': 10.0},
            {'sem': '3', 'code': '24MX17', 'title': 'Cloud Computing', 'credits': '4', 'grade': 'A+', 'grade_point': 10.0}
        ]
    }
    n4 = detect_granular_changes(roll_no, base_user, base_user['studzone1'], sz2_res)
    print('Test 4 (Results Published):', n4[0]['title'], '—', n4[0]['description'])
    assert 'Semester 3 results published: 6 new course results available.' in n4[0]['description']

    # 5. TEST CASE 5: CGPA change (7.82 -> 7.96)
    sz2_cgpa = {'cgpa': '7.96'}
    n5 = detect_granular_changes(roll_no, base_user, base_user['studzone1'], sz2_cgpa)
    print('Test 5 (CGPA Change):', n5[0]['title'], '—', n5[0]['description'])
    assert 'CGPA changed from 7.82 → 7.96.' in n5[0]['description']

    # 6. TEST CASE 6: Timetable change (DBMS exam moved from 12 Sep -> 14 Sep)
    sz2_tt = {
        'parsed_timetable': [
            {'course_code': '24MX11', 'course_title': 'DBMS', 'exam_date': '14 Sep', 'session': 'FN', 'timing': '10:00 AM - 01:00 PM'}
        ]
    }
    n6 = detect_granular_changes(roll_no, base_user, base_user['studzone1'], sz2_tt)
    print('Test 6 (Timetable Change):', n6[0]['title'], '—', n6[0]['description'])
    assert 'DBMS exam moved from 12 Sep → 14 Sep.' in n6[0]['description']

    # 7. TEST CASE 7: Seating published (DBMS seating published: Hall E201, Seat 24)
    sz2_seating = {'seating_html': '<table><tr><td>Hall E201</td><td>Seat 24</td></tr></table>'}
    n7 = detect_granular_changes(roll_no, base_user, base_user['studzone1'], sz2_seating)
    print('Test 7 (Seating Published):', n7[0]['title'], '—', n7[0]['description'])
    assert 'DBMS seating published: Hall E201, Seat 24.' in n7[0]['description']

    # 8. TEST CASE 8: Fees added (₹2,500 examination fee has been added)
    sz1_fees = {'fee_status': '₹2,500 examination fee'}
    n8 = detect_granular_changes(roll_no, base_user, sz1_fees, base_user['studzone2'])
    assert 'Fee status changed from Tuition Fee Cleared → ₹2,500 examination fee.' in n8[0]['description']

    # 9. TEST CASE 9: Feedback available (New Course Feedback form is now available)
    sz1_fb = {'feedback': [{'type': 'Course', 'status': 'Scheduled'}]}
    n9 = detect_granular_changes(roll_no, base_user, sz1_fb, base_user['studzone2'])
    print('Test 9 (Feedback Available):', n9[0]['title'], '—', n9[0]['description'])
    assert 'New Course Feedback form is now available on StudZone 1.' in n9[0]['description']

    # 10. TEST CASE 10: Hostel room allocation updated
    sz1_hostel = {'hostel_status': 'Block B-118'}
    n10 = detect_granular_changes(roll_no, base_user, sz1_hostel, base_user['studzone2'])
    print('Test 10 (Hostel Update):', n10[0]['title'], '—', n10[0]['description'])
    assert 'Hostel room allocation has been updated: Block B-118.' in n10[0]['description']

    # 11. TEST CASE 11: Scholarship status changed (Scholarship application status changed to Approved)
    sz1_schol = {'scholarship_status': 'Approved', 'scholarships': {'applied': [{'title': 'Merit Scholarship'}], 'received': []}}
    n11 = detect_granular_changes(roll_no, base_user, sz1_schol, base_user['studzone2'])
    print('Test 11 (Scholarship Status):', n11[0]['title'], '—', n11[0]['description'])
    assert 'Scholarship application status changed to Approved.' in n11[0]['description']

    # 12. TEST CASE 12: Duplicate change detection (Idempotency)
    hash1 = compute_change_hash(roll_no, 'attendance', 'Attendance', 'Attendance Updated', 'Data Structures attendance changed from 82% → 86%.')
    hash2 = compute_change_hash(roll_no, 'attendance', 'Attendance', 'Attendance Updated', 'Data Structures attendance changed from 82% → 86%.')
    print('Test 12 (Deduplication Hash Match):', hash1 == hash2, f'(Hash: {hash1[:16]}...)')
    assert hash1 == hash2

    print('\n======================================================================')
    print('ALL GRANULAR NOTIFICATION UNIT TESTS PASSED!')
    print('======================================================================')

if __name__ == '__main__':
    run_all_tests()
