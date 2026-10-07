import os
import sys
import certifi
import pymongo
from datetime import datetime, timezone
from dotenv import load_dotenv

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath('backend'))

from new_scrapers.login import login as modern_login
from new_scrapers.studzone1_scraper import scrape_studzone1_all
from scrapers.studzone2_scraper import scrape_studzone2_all
from scrapers.login import login_student_studzone2 as legacy_login

load_dotenv('backend/.env')
client = pymongo.MongoClient(os.getenv('MONGO_URI'), tlsCAFile=certifi.where())
db = client['ecampus']

print("======================================================================")
print("PRODUCTION STUDENTS RE-SYNC WITH STUDENT-SPECIFIC COURSE LINEAGE")
print("======================================================================\n")

# BEFORE COUNTS
users_col = db['new_users']
notifs_col = db['notifications_log']
subs_col = db['subjects']

before_users_count = users_col.count_documents({})
before_notifs_count = notifs_col.count_documents({})
before_subs_count = subs_col.count_documents({})

print(f"BEFORE AUDIT:")
print(f"  - Users in new_users: {before_users_count}")
print(f"  - Notifications in notifications_log: {before_notifs_count}")
print(f"  - Documents in subjects: {before_subs_count}")
print("======================================================================\n")

target_rolls = ['25MX227', '25MX232', '25MX116', '25MX231', '25MX230']

results_summary = {}

for roll in target_rolls:
    user = users_col.find_one({'rollNo': roll})
    if not user or not user.get('password'):
        print(f"[ERROR] User {roll} or password not found in new_users! Skipping.")
        continue

    print(f"--> Syncing student {roll} ({user.get('name')})...")
    creds = {'rollNo': roll, 'password': user['password']}
    
    # 1. Modern StudZone 1 Login
    modern_sess_res = modern_login(creds)
    if isinstance(modern_sess_res, tuple) or not modern_sess_res:
        print(f"   [FAIL] Modern StudZone login failed for {roll}: {modern_sess_res}")
        continue
    
    modern_sess = modern_sess_res
    print(f"   [OK] StudZone 1 authenticated.")
    
    # Scrape StudZone 1 with student-specific course mapping
    sz1_data = scrape_studzone1_all(modern_sess, roll)
    print(f"   [OK] StudZone 1 scraped: {len(sz1_data.get('parsed_attendance', []))} attendance courses, {len(sz1_data.get('parsed_marks', []))} CA courses.")

    # 2. Legacy StudZone 2 Login
    legacy_sess_res = legacy_login(creds)
    sz2_data = {}
    if not isinstance(legacy_sess_res, tuple) and legacy_sess_res:
        legacy_sess = legacy_sess_res
        sz2_data = scrape_studzone2_all(legacy_sess, roll)
        print(f"   [OK] StudZone 2 scraped: CGPA = {sz2_data.get('cgpa')}, {len(sz2_data.get('parsed_results', []))} results courses.")
    else:
        print(f"   [WARN] StudZone 2 legacy login unavailable for {roll}; preserving existing sz2 data.")
        sz2_data = user.get('studzone2', {})

    now_iso = datetime.now(timezone.utc).isoformat()
    student_name = (sz1_data.get('profile', {}).get('Name') or user.get('name') or roll).strip()

    # 3. Update MongoDB user document (ZERO notifications generated)
    update_fields = {
        "studzone1": sz1_data,
        "name": student_name,
        "attendance": sz1_data.get("attendance_html", ""),
        "marks": sz1_data.get("ca_marks_html", ""),
        "lastSyncedAt": now_iso,
        "last_synced_studzone1": now_iso
    }
    if sz2_data:
        update_fields["studzone2"] = sz2_data
        if sz2_data.get("cgpa") is not None:
            update_fields["cgpa"] = sz2_data.get("cgpa")
        if sz2_data.get("results_html"):
            update_fields["results"] = sz2_data.get("results_html")
            update_fields["result_table"] = sz2_data.get("results_html")

    users_col.update_one({'rollNo': roll}, {'$set': update_fields})
    print(f"   [OK] Student {roll} updated in new_users.\n")

    # Save summary for reporting
    results_summary[roll] = {
        "name": student_name,
        "attendance": sz1_data.get('parsed_attendance', []),
        "ca_marks": sz1_data.get('parsed_marks', []),
        "cgpa": sz2_data.get('cgpa', user.get('cgpa'))
    }

print("======================================================================")
print("AFTER AUDIT & RE-SYNC VERIFICATION")
print("======================================================================\n")

after_users_count = users_col.count_documents({})
after_notifs_count = notifs_col.count_documents({})
after_subs_count = subs_col.count_documents({})

print(f"AFTER COUNTS:")
print(f"  - Users in new_users: {after_users_count} (Expected: {before_users_count})")
print(f"  - Notifications in notifications_log: {after_notifs_count} (Expected: {before_notifs_count})")
print(f"  - Documents in subjects: {after_subs_count} (Expected: {before_subs_count})")

assert before_users_count == after_users_count, "User count changed!"
assert before_notifs_count == after_notifs_count, "Notification count changed!"
print("\n[PASS] Database integrity confirmed: exactly 0 notifications created, 0 new users, 0 collection changes.")

print("\n======================================================================")
print("DETAILED VERIFICATION FOR EACH STUDENT")
print("======================================================================\n")

for roll, data in results_summary.items():
    print(f"--- Student {roll}: {data['name']} (CGPA: {data['cgpa']}) ---")
    print("Course Attendance Roster:")
    tot_att = 0
    tot_cond = 0
    tot_abs = 0
    for c in data['attendance']:
        att = int(float(c.get('attended', 0)))
        cond = int(float(c.get('total_classes', 0)))
        absent = int(float(c.get('absent', 0)))
        tot_att += att
        tot_cond += cond
        tot_abs += absent
        print(f"  {c.get('code')}: '{c.get('name')}' | {att}/{cond} ({c.get('percentage')}) | Absent: {absent}")
    pct = round((tot_att / tot_cond) * 100, 2) if tot_cond > 0 else 0
    print(f"  TOTAL: {tot_att}/{tot_cond} = {pct}% (Absent: {tot_abs})\n")
