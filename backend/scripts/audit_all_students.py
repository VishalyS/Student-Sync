import os
import certifi
import pymongo
from dotenv import load_dotenv
from bs4 import BeautifulSoup

load_dotenv('backend/.env')
client = pymongo.MongoClient(os.getenv('MONGO_URI'), tlsCAFile=certifi.where())
db = client['ecampus']

rolls = ['25MX232', '25MX227', '25MX116', '25MX231', '25MX230']

print("======================================================================")
print("AUDIT OF ALL 5 PRODUCTION STUDENTS")
print("======================================================================\n")

for r in rolls:
    u = db.new_users.find_one({'rollNo': r})
    if not u:
        print(f"Student {r} NOT FOUND in new_users!")
        continue
    
    sz1 = u.get('studzone1', {})
    sz2 = u.get('studzone2', {})
    pa = sz1.get('parsed_attendance', [])
    pm = sz1.get('parsed_marks', [])
    tt = sz1.get('class_schedule', [])
    
    # Extract CA marks courses
    ca_courses = {}
    for m in pm:
        c = m.get('code')
        n = m.get('name')
        if c and n:
            ca_courses[c] = n

    print(f"--- Student {r}: {u.get('name')} ({u.get('email')}) ---")
    print(f"Attendance records count: {len(pa)}")
    for item in pa:
        code = item.get('code')
        att_name = item.get('name')
        ca_name = ca_courses.get(code, 'NOT IN CA')
        tot = item.get('total_classes')
        pres = item.get('attended')
        pct = item.get('percentage')
        mismatch = " [MISMATCH!]" if att_name != ca_name and ca_name != 'NOT IN CA' else ""
        print(f"  {code}: AttendanceName='{att_name}' | CAName='{ca_name}' | {pres}/{tot} ({pct}){mismatch}")
    
    # Check timetable sample
    print(f"Class Schedule rows: {len(tt)}")
    if tt:
        print(f"  Sample timetable row 0: {tt[0]}")
    print()
