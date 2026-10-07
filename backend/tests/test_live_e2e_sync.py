import sys
import os
import certifi
import urllib3
import json
import urllib.request
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from new_scrapers.login import login as modern_login
from scrapers.login import login_student_studzone2 as legacy_login
from new_scrapers.studzone1_scraper import scrape_studzone1_all
from scrapers.studzone2_scraper import scrape_studzone2_all
from speed_ser import process_detected_changes

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env')))
MONGO_URI = os.getenv('MONGO_URI')
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['ecampus']
notifs_col = db['notifications_log']
users_col = db['new_users']

def run_real_e2e_test():
    print('======================================================================')
    print('REAL END-TO-END NOTIFICATION TEST FOR STUDENT 25MX232')
    print('======================================================================\n')

    # STEP 1: Read current data from MongoDB
    roll_no = '25MX232'
    stored_user = users_col.find_one({'rollNo': roll_no})
    if not stored_user:
        print(f"Error: Student {roll_no} not found in MongoDB.")
        return

    password = stored_user.get('password')
    print(f"1. [MongoDB] Student loaded successfully:")
    print(f"   - Name: {stored_user.get('name')}")
    print(f"   - Roll Number: {roll_no}")
    print(f"   - Stored CGPA: {stored_user.get('cgpa')}")
    print(f"   - Attendance Records: {len(stored_user.get('studzone1', {}).get('parsed_attendance', []))} subjects")
    print(f"   - CA Marks Records: {len(stored_user.get('studzone1', {}).get('parsed_marks', []))} subjects")
    print(f"   - Exam Results: {len(stored_user.get('studzone2', {}).get('parsed_results', []))} courses")
    print(f"   - Timetable Slots: {len(stored_user.get('studzone2', {}).get('parsed_timetable', []))} slots\n")

    user_credentials = {'rollNo': roll_no, 'password': password}

    # STEP 2: Authenticate and run live StudZone 1 scraper
    print("2. [Live Scraping] Connecting to StudZone 1 (Modern Portal)...")
    sz1_sess = modern_login(user_credentials)
    if isinstance(sz1_sess, tuple) or not sz1_sess:
        print(f"   Failed to authenticate to StudZone 1: {sz1_sess}")
        return
    sz1_fresh = scrape_studzone1_all(sz1_sess, roll_no, db['subjects'])
    print(f"   StudZone 1 Scrape Completed:")
    print(f"   - Profile: {bool(sz1_fresh.get('profile'))} ({sz1_fresh.get('profile', {}).get('Degree')})")
    print(f"   - Attendance: {len(sz1_fresh.get('parsed_attendance', []))} courses")
    print(f"   - CA Marks: {len(sz1_fresh.get('parsed_marks', []))} subjects")
    print(f"   - Fee Status: {sz1_fresh.get('fee_status')}")
    print(f"   - Hostel Status: {sz1_fresh.get('hostel_status')}")
    print(f"   - Feedback Schedules: {len(sz1_fresh.get('feedback', []))}\n")

    # STEP 3: Authenticate and run live StudZone 2 scraper
    print("3. [Live Scraping] Connecting to StudZone 2 (Legacy Portal)...")
    sz2_sess = legacy_login(user_credentials)
    if isinstance(sz2_sess, tuple) or not sz2_sess:
        print(f"   Failed to authenticate to StudZone 2: {sz2_sess}")
        return
    sz2_fresh = scrape_studzone2_all(sz2_sess, roll_no)
    print(f"   StudZone 2 Scrape Completed:")
    print(f"   - Calculated CGPA: {sz2_fresh.get('cgpa')}")
    print(f"   - Semester Results: {len(sz2_fresh.get('parsed_results', []))} courses")
    print(f"   - Exam Timetable: {len(sz2_fresh.get('parsed_timetable', []))} slots")
    print(f"   - Seating Arrangement: {'Available' if sz2_fresh.get('seating_html') else 'Not Published Yet'}")
    print(f"   - Circulars: {len(sz2_fresh.get('circulars', []))} PDFs\n")

    # STEP 4: Compare freshly scraped data vs MongoDB snapshot (Pass 1)
    initial_notifs_count = notifs_col.count_documents({"rollNo": roll_no})
    print(f"4. [Change Detection Pass 1] Comparing fresh data with MongoDB snapshot...")
    print(f"   Initial notification count in ecampus.notifications_log for {roll_no}: {initial_notifs_count}")

    process_detected_changes(roll_no, stored_user, sz1_fresh, sz2_fresh, db)
    
    post_pass1_count = notifs_col.count_documents({"rollNo": roll_no})
    diff_pass1 = post_pass1_count - initial_notifs_count
    print(f"   Pass 1 Completed: Generated {diff_pass1} new notifications.")

    # STEP 5: Re-run immediately with the exact same data to verify ZERO DUPLICATES (Pass 2)
    print("\n5. [Idempotency & Duplicate Check Pass 2] Running sync again with same data...")
    process_detected_changes(roll_no, stored_user, sz1_fresh, sz2_fresh, db)
    post_pass2_count = notifs_col.count_documents({"rollNo": roll_no})
    diff_pass2 = post_pass2_count - post_pass1_count
    print(f"   Pass 2 Completed: Generated {diff_pass2} duplicate notifications (Expected: 0).")
    assert diff_pass2 == 0, "Error: Duplicate notifications generated during repeated sync!"
    print("   [PASS] 100% Idempotency verified. Zero duplicates created.")

    # STEP 6: Verify MongoDB notifications structure
    print("\n6. [MongoDB Verification] Querying notifications_log for 25MX232...")
    user_notifs = list(notifs_col.find({"rollNo": roll_no}).sort("createdAt", -1).limit(5))
    print(f"   Total notifications on record for {roll_no}: {len(user_notifs)}")
    for idx, n in enumerate(user_notifs):
        print(f"   [{idx+1}] Category: {n.get('category', n.get('type'))} | Source: {n.get('source')} | Title: {n.get('title')}")
        print(f"       Description: {n.get('description', n.get('message'))}")
        print(f"       Timestamp: {n.get('createdAt')} | Read: {n.get('read')} | Hash: {n.get('changeHash')[:16]}...")
        assert 'description' in n or 'message' in n, "Notification missing description!"
        assert 'source' in n, "Notification missing source!"
        assert 'category' in n or 'type' in n, "Notification missing category!"

    # STEP 7: Test Frontend API endpoints
    print("\n7. [API & Frontend Verification]")
    
    # 7A: GET /notifications?rollNo=25MX232
    with urllib.request.urlopen(f'http://127.0.0.1:5000/notifications?rollNo={roll_no}') as res:
        api_notifs = json.loads(res.read().decode('utf-8'))
        print(f"   - GET /notifications: HTTP {res.status} | Returned {len(api_notifs.get('notifications', []))} notifications | Unread: {api_notifs.get('unreadCount')}")
        assert res.status == 200

    # 7B: GET /profile?rollNo=25MX232
    with urllib.request.urlopen(f'http://127.0.0.1:5000/profile?rollNo={roll_no}') as res:
        prof = json.loads(res.read().decode('utf-8'))
        print(f"   - GET /profile: HTTP {res.status}")
        print(f"     * Name: {prof.get('name')}")
        print(f"     * CGPA: {prof.get('cgpa')}")
        print(f"     * Attendance HTML present: {bool(prof.get('attendance'))}")
        print(f"     * CA Marks HTML present: {bool(prof.get('marks'))}")
        print(f"     * Results HTML present: {bool(prof.get('results'))}")
        print(f"     * Timetable HTML present: {bool(prof.get('timetable'))}")
        print(f"     * Seating status: {'Published' if prof.get('seating') else 'Not Published'}")
        print(f"     * Fees status: {bool(prof.get('fees'))}")
        print(f"     * Hostel status: {bool(prof.get('hostel'))}")
        print(f"     * Scholarships: {bool(prof.get('scholarships'))}")
        print(f"     * Feedback: {len(prof.get('feedback', []))} forms")
        assert res.status == 200

    # 7C: GET /stats
    with urllib.request.urlopen('http://127.0.0.1:5000/stats') as res:
        st = json.loads(res.read().decode('utf-8'))
        print(f"   - GET /stats: HTTP {res.status} | Registered: {st.get('studentsRegistered')} | Delivered: {st.get('notificationsDelivered')}")
        assert res.status == 200

    print('\n======================================================================')
    print('REAL END-TO-END NOTIFICATION TEST PASSED WITH 100% INTEGRITY!')
    print('======================================================================')

if __name__ == '__main__':
    run_real_e2e_test()
