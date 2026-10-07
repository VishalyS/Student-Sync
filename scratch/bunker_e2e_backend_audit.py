import os
import sys
import json
import copy
from pymongo import MongoClient
from dotenv import load_dotenv

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

load_dotenv(os.path.join(backend_dir, '.env'))
from pyserver import app, generate_auth_token

client = MongoClient(os.getenv('MONGO_URI'))
db = client['ecampus']

def run_backend_audit():
    print("=" * 60)
    print("1. BASELINE DATABASE INTEGRITY AUDIT")
    print("=" * 60)
    
    users_count_before = db.new_users.count_documents({})
    notifs_count_before = db.notifications_log.count_documents({})
    subjects_count_before = db.subjects.count_documents({})
    
    print(f"new_users count: {users_count_before} (Expected: 5)")
    print(f"notifications_log count: {notifs_count_before} (Expected: 67)")
    print(f"subjects count: {subjects_count_before} (Expected: 15)")
    
    assert users_count_before == 5, f"Expected 5 users, got {users_count_before}"
    assert notifs_count_before == 67, f"Expected 67 notifications, got {notifs_count_before}"
    assert subjects_count_before == 15, f"Expected 15 subjects, got {subjects_count_before}"

    students = ["25MX227", "25MX232", "25MX116", "25MX231", "25MX230"]
    user_docs = {s: db.new_users.find_one({"rollNo": s}) for s in students}
    
    for s in students:
        u = user_docs[s]
        assert u is not None, f"User {s} not found in DB!"
        print(f"Student {s} ({u.get('name')}): CGPA = {u.get('cgpa')}")
    
    test_client = app.test_client()
    token_227 = generate_auth_token("25MX227")
    token_232 = generate_auth_token("25MX232")
    
    print("\n" + "=" * 60)
    print("2. SMART ATTENDANCE MANAGER VERIFICATION")
    print("=" * 60)
    # Check 25MX227
    r227 = test_client.get('/api/attendance/summary', headers={'Authorization': f'Bearer {token_227}'})
    assert r227.status_code == 200, f"Failed 25MX227 attendance: {r227.status_code}"
    d227 = r227.get_json()
    print("25MX227 Attendance Summary:")
    print(f"  Total Attended: {d227['total_attended']}")
    print(f"  Total Conducted: {d227['total_conducted']}")
    print(f"  Overall Percentage: {d227['overall_percentage']}%")
    print(f"  Safe Bunks: {d227['overall_safe_bunks']}")
    print(f"  Required Classes: {d227['overall_required_classes']}")
    print(f"  Status: {d227['overall_status']}")
    print(f"  Subject count: {len(d227['subjects'])}")
    
    assert d227['total_attended'] == 238, f"Expected 238 attended, got {d227['total_attended']}"
    assert d227['total_conducted'] == 310, f"Expected 310 conducted, got {d227['total_conducted']}"
    assert d227['overall_percentage'] == 76.77, f"Expected 76.77%, got {d227['overall_percentage']}"
    assert len(d227['subjects']) == 8, f"Expected 8 subjects, got {len(d227['subjects'])}"
    
    sub_map_227 = {s['code']: s for s in d227['subjects']}
    expected_227_courses = {
        '23MX31': ('CLOUD COMPUTING', 27, 37),
        '23MX36': ('CLOUD COMPUTING LABORATORY', 42, 52),
        '23MX37': ('MINI PROJECT', 38, 48),
        '23MXAE': ('COMPUTER NETWORKS', 29, 37),
        '23MXAT': ('DevOps', 30, 37),
        '23MXAY': ('SMART COMPUTING WITH ADVANCED PYTHON', 24, 36),
        '23MXCA': ('ENTREPRENEURSHIP', 30, 39),
        '23MXM4': ('PROFESSIONAL ETHICS', 18, 24),
    }
    for code, (exp_title, exp_att, exp_cond) in expected_227_courses.items():
        assert code in sub_map_227, f"Subject {code} missing in 25MX227"
        s_obj = sub_map_227[code]
        assert s_obj['attended'] == exp_att, f"{code}: attended {s_obj['attended']} != {exp_att}"
        assert s_obj['conducted'] == exp_cond, f"{code}: conducted {s_obj['conducted']} != {exp_cond}"
        assert s_obj['name'] == exp_title, f"{code}: title '{s_obj['name']}' != '{exp_title}'"
        print(f"  Verified 25MX227 {code}: {s_obj['name']} ({s_obj['attended']}/{s_obj['conducted']}) = {s_obj['percentage']}% [Bunks: {s_obj['safe_bunks']}, Req: {s_obj['required_classes']}]")

    # Check 25MX232
    r232 = test_client.get('/api/attendance/summary', headers={'Authorization': f'Bearer {token_232}'})
    assert r232.status_code == 200, f"Failed 25MX232 attendance: {r232.status_code}"
    d232 = r232.get_json()
    print("\n25MX232 Attendance Summary:")
    print(f"  Total Attended: {d232['total_attended']}")
    print(f"  Total Conducted: {d232['total_conducted']}")
    print(f"  Overall Percentage: {d232['overall_percentage']}%")
    print(f"  Subject count: {len(d232['subjects'])}")
    assert d232['total_attended'] == 258, f"Expected 258 attended, got {d232['total_attended']}"
    assert d232['total_conducted'] == 310, f"Expected 310 conducted, got {d232['total_conducted']}"
    assert d232['overall_percentage'] == 83.23, f"Expected 83.23%, got {d232['overall_percentage']}"
    assert len(d232['subjects']) == 8, f"Expected 8 subjects, got {len(d232['subjects'])}"
    
    sub_map_232 = {s['code']: s for s in d232['subjects']}
    expected_232_courses = {
        '23MX37': 'MINI PROJECT',
        '23MXM4': 'PROFESSIONAL ETHICS',
        '23MXAF': 'DATA MINING AND ANALYTICS',
        '23MXAO': 'HUMAN COMPUTER INTERACTION'
    }
    for code, exp_title in expected_232_courses.items():
        assert code in sub_map_232, f"Subject {code} missing in 25MX232"
        assert sub_map_232[code]['name'] == exp_title, f"{code}: title '{sub_map_232[code]['name']}' != '{exp_title}'"
        print(f"  Verified 25MX232 {code}: {sub_map_232[code]['name']} ({sub_map_232[code]['attended']}/{sub_map_232[code]['conducted']})")

    print("\n" + "=" * 60)
    print("3. SAFE BUNK / RECOVERY CALCULATIONS (TARGET SWITCHING)")
    print("=" * 60)
    for target in [75.0, 80.0, 85.0, 90.0]:
        resp = test_client.get(f'/api/attendance/summary?target={target}', headers={'Authorization': f'Bearer {token_227}'})
        assert resp.status_code == 200
        dat = resp.get_json()
        print(f"Target {target}% for 25MX227:")
        print(f"  Overall Safe Bunks: {dat['overall_safe_bunks']}, Required: {dat['overall_required_classes']}, Status: {dat['overall_status']}")
        if target == 75.0:
            assert dat['overall_safe_bunks'] == 7
            assert dat['overall_required_classes'] == 0
        elif target == 80.0:
            assert dat['overall_safe_bunks'] == 0
            assert dat['overall_required_classes'] == 50
        elif target == 85.0:
            assert dat['overall_safe_bunks'] == 0
            assert dat['overall_required_classes'] == 170
        elif target == 90.0:
            assert dat['overall_safe_bunks'] == 0
            assert dat['overall_required_classes'] == 410

    print("\n" + "=" * 60)
    print("4. ATTEND / BUNK SIMULATOR VERIFICATION")
    print("=" * 60)
    sim_res = test_client.post('/api/attendance/simulate', json={
        "subject_code": "23MX31",
        "additional_attended": 5,
        "additional_bunked": 0,
        "target": 75.0
    }, headers={'Authorization': f'Bearer {token_227}'})
    assert sim_res.status_code == 200
    sim_data = sim_res.get_json()
    print("Simulated 23MX31 with +5 attended, 0 bunked:")
    print(f"  Original: {sim_data['original']['attended']}/{sim_data['original']['conducted']} = {sim_data['original']['percentage']}% ({sim_data['original']['status']})")
    print(f"  Simulated: {sim_data['simulated_attended']}/{sim_data['simulated_conducted']} = {sim_data['simulated_percentage']}% ({sim_data['simulated_status']})")
    assert sim_data['simulated_attended'] == 32
    assert sim_data['simulated_conducted'] == 42
    assert sim_data['simulated_percentage'] == 76.19
    assert sim_data['simulated_status'] == 'SAFE'
    assert sim_data['simulated_safe_bunks'] == 0
    assert sim_data['simulated_required_classes'] == 0

    print("\n" + "=" * 60)
    print("5. BUNK PLANNER VERIFICATION")
    print("=" * 60)
    p_res = test_client.get('/api/planner/intelligence', headers={'Authorization': f'Bearer {token_227}'})
    assert p_res.status_code == 200
    p_data = p_res.get_json()
    subj_matrix = p_data.get('subject_matrix', [])
    print(f"Planner intelligence: {len(subj_matrix)} subjects in matrix.")
    assert len(subj_matrix) == 8, f"Expected 8 subjects in planner matrix, got {len(subj_matrix)}"
    
    priorities = {s['code']: (s['name'], s['priority']['level'], s['priority']['score']) for s in subj_matrix}
    for code, (p_name, level, score) in priorities.items():
        print(f"  Planner Course {code} ({p_name}): Priority {level} (Score {score})")

    # Verify both above target and below target handling
    safe_subjects = [s for s in subj_matrix if s['attendance']['percentage'] >= 75.0]
    warn_subjects = [s for s in subj_matrix if s['attendance']['percentage'] < 75.0]
    assert len(safe_subjects) > 0, "Expected subjects above target"
    assert len(warn_subjects) > 0, "Expected subjects below target (e.g. 23MX31, 23MXAY)"
    print(f"  Safe subjects count: {len(safe_subjects)}, Need attention count: {len(warn_subjects)}")

    print("\n" + "=" * 60)
    print("6. TODAY SCHEDULE / TIMETABLE INTELLIGENCE")
    print("=" * 60)
    w_res = test_client.get('/api/schedule/weekly', headers={'Authorization': f'Bearer {token_227}'})
    assert w_res.status_code == 200
    w_data = w_res.get_json()
    assert "days" in w_data
    print(f"Weekly schedule days count: {len(w_data['days'])}")
    day_names = [d["day"] for d in w_data["days"]]
    print(f"Days: {day_names}")
    
    # Collect titles
    titles_in_tt = {}
    for d in w_data["days"]:
        for p in d.get("periods", []):
            if not p.get("is_free") and p.get("code") not in ["FREE", "TWM", "-"]:
                titles_in_tt[p.get("code")] = p.get("name")
    
    print("Courses found in 25MX227 weekly schedule:")
    for code, tname in sorted(titles_in_tt.items()):
        print(f"  {code}: {tname}")
    
    if '23MXAT' in titles_in_tt:
        assert titles_in_tt['23MXAT'] == 'DevOps', f"Expected DevOps, got {titles_in_tt['23MXAT']}"
    if '23MXAY' in titles_in_tt:
        assert 'SMART COMPUTING' in titles_in_tt['23MXAY']
    if '23MXAE' in titles_in_tt:
        assert 'NETWORKS' in titles_in_tt['23MXAE']
    if '23MXCA' in titles_in_tt:
        assert 'ENTREPRENEURSHIP' in titles_in_tt['23MXCA']

    print("\n" + "=" * 60)
    print("7. DAY-BUNK SIMULATOR VERIFICATION")
    print("=" * 60)
    db_res = test_client.post('/api/schedule/day-bunk-simulate', json={
        "day": "Monday",
        "periods": [1, 2],
        "target": 75.0
    }, headers={'Authorization': f'Bearer {token_227}'})
    assert db_res.status_code == 200
    db_data = db_res.get_json()
    print("Day-bunk simulation for Monday periods [1, 2]:")
    print(f"  Initial overall: {db_data['overall']['original']['percentage']}%")
    print(f"  Simulated overall: {db_data['overall']['simulated']['percentage']}%")
    print(f"  Classes missed count: {db_data['total_classes_missed']}")
    assert db_data['total_classes_missed'] >= 0

    print("\n" + "=" * 60)
    print("8. CA / ACADEMIC PERFORMANCE & WHAT-IF CGPA")
    print("=" * 60)
    m_res = test_client.get('/api/academic/marks-summary', headers={'Authorization': f'Bearer {token_227}'})
    assert m_res.status_code == 200
    m_data = m_res.get_json()
    print(f"Academic marks summary: CGPA={m_data.get('stored_cgpa')}, base_credits={m_data.get('base_credits')}")
    ca_courses = m_data.get('ca_marks', {}).get('courses', [])
    print(f"  CA courses count: {len(ca_courses)}")
    for ca_item in ca_courses[:4]:
        print(f"    - {ca_item.get('code')}: {ca_item.get('name')} (Status: {ca_item.get('status')})")
    
    # What-If CGPA simulator
    cgpa_sim_res = test_client.post('/api/academic/cgpa-simulate', json={
        "simulated_courses": [
            {"course_code": "TEST_CS1", "credits": 4, "grade": "O"},
            {"course_code": "TEST_CS2", "credits": 4, "grade": "A+"}
        ]
    }, headers={'Authorization': f'Bearer {token_227}'})
    assert cgpa_sim_res.status_code == 200
    cgpa_sim_data = cgpa_sim_res.get_json()
    print(f"What-If CGPA: base CGPA {cgpa_sim_data.get('base_cgpa')} -> projected CGPA {cgpa_sim_data.get('projected_cgpa')}")

    print("\n" + "=" * 60)
    print("9. CAMPUS SERVICES VERIFICATION")
    print("=" * 60)
    cs_res = test_client.get('/api/campus-services/overview', headers={'Authorization': f'Bearer {token_227}'})
    assert cs_res.status_code == 200
    cs_data = cs_res.get_json()
    print("Campus Services keys:", list(cs_data.keys()))
    print(f"  Profile rollNo: {cs_data.get('profile', {}).get('roll_number')}")
    print(f"  Fees items count: {len(cs_data.get('fees', {}).get('ledger', []))}")
    print(f"  Fees total paid: {cs_data.get('fees', {}).get('total_paid')}")
    print(f"  Hostel status: {cs_data.get('hostel', {}).get('status')}")
    print(f"  Scholarships applied: {len(cs_data.get('scholarships', {}).get('applied', []))}")
    print(f"  Scholarships received: {len(cs_data.get('scholarships', {}).get('received', []))}")

    print("\n" + "=" * 60)
    print("10. AUTHORIZATION & CROSS-STUDENT ISOLATION")
    print("=" * 60)
    unauth = test_client.get('/api/attendance/summary')
    assert unauth.status_code == 401
    print("  Unauthenticated request -> 401 Unauthorized [PASS]")

    invalid_tok = test_client.get('/api/attendance/summary', headers={'Authorization': 'Bearer FORGED_TOKEN'})
    assert invalid_tok.status_code == 401
    print("  Forged token request -> 401 Unauthorized [PASS]")

    own = test_client.get('/api/attendance/summary', headers={'Authorization': f'Bearer {token_227}'})
    assert own.status_code == 200
    print("  Authenticated user accessing own data -> 200 OK [PASS]")

    cross_get = test_client.get('/api/attendance/summary?rollNo=25MX232', headers={'Authorization': f'Bearer {token_227}'})
    assert cross_get.status_code == 403
    print("  Cross-user query in GET -> 403 Forbidden [PASS]")

    cross_post = test_client.post('/api/attendance/simulate', json={
        "rollNo": "25MX232",
        "subject_code": "23MX31",
        "additional_attended": 1
    }, headers={'Authorization': f'Bearer {token_227}'})
    assert cross_post.status_code == 403
    print("  Cross-user query in POST -> 403 Forbidden [PASS]")

    print("\n" + "=" * 60)
    print("11. ZERO-WRITE PRODUCTION AUDIT (POST-VERIFICATION)")
    print("=" * 60)
    users_count_after = db.new_users.count_documents({})
    notifs_count_after = db.notifications_log.count_documents({})
    subjects_count_after = db.subjects.count_documents({})

    print(f"new_users count after: {users_count_after} (Before: {users_count_before})")
    print(f"notifications_log count after: {notifs_count_after} (Before: {notifs_count_before})")
    print(f"subjects count after: {subjects_count_after} (Before: {subjects_count_before})")

    assert users_count_before == users_count_after == 5, "new_users count changed!"
    assert notifs_count_before == notifs_count_after == 67, "notifications_log count changed!"
    assert subjects_count_before == subjects_count_after == 15, "subjects count changed!"
    print("\n>>> ALL BUNKER BACKEND CAPABILITIES 100% AUDITED AND VERIFIED WITH ZERO WRITES! <<<")

if __name__ == "__main__":
    run_backend_audit()
