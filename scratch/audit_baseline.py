import os
import json
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv('backend/.env')
uri = os.environ.get('MONGO_URI')
client = MongoClient(uri)
db = client['ecampus']

print("=== MONGO BASELINE INTEGRITY CHECK ===")
users_count = db.new_users.count_documents({})
notifs_count = db.notifications_log.count_documents({})
subjects_count = db.subjects.count_documents({})

print(f"new_users count: {users_count}")
print(f"notifications_log count: {notifs_count}")
print(f"subjects count: {subjects_count}")

users = list(db.new_users.find({}))
for u in users:
    roll = u.get('roll_number') or u.get('rollno') or u.get('username') or u.get('user_id') or str(u.get('_id'))
    name = u.get('name')
    att = u.get('attendance', {})
    courses = att.get('courses', []) if isinstance(att, dict) else []
    overall = att.get('overall', {}) if isinstance(att, dict) else {}
    ca = u.get('ca_marks', {}) or u.get('ca', {})
    acad = u.get('academic', {}) or {}
    cgpa = acad.get('cgpa') or u.get('cgpa')
    tt = u.get('timetable', {}) or {}
    services = u.get('services', {}) or u.get('fees', {}) or {}
    
    print("-" * 50)
    print(f"Student: {roll} | Name: {name}")
    print(f"  Top-level keys: {list(u.keys())}")
    print(f"  Active courses count: {len(courses)}")
    if isinstance(overall, dict):
        print(f"  Overall attendance: attended={overall.get('attended')}, conducted={overall.get('conducted')}, percentage={overall.get('percentage')}")
    print(f"  CGPA: {cgpa}")
    print(f"  CA items count: {len(ca) if hasattr(ca, '__len__') else type(ca)}")
    print(f"  Timetable days: {list(tt.keys()) if isinstance(tt, dict) else type(tt)}")
    print(f"  Services keys: {list(services.keys()) if isinstance(services, dict) else type(services)}")
    print("  Courses:")
    for c in courses:
        print(f"    - {c.get('course_code')}: {c.get('course_name')} ({c.get('attended')}/{c.get('conducted')}) = {c.get('percentage')}%")
