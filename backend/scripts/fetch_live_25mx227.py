import os
import sys
import certifi
import pymongo
from dotenv import load_dotenv
from bs4 import BeautifulSoup

# Ensure backend path is in sys.path
sys.path.insert(0, os.path.abspath('backend'))

from new_scrapers.login import login as modern_login

load_dotenv('backend/.env')
client = pymongo.MongoClient(os.getenv('MONGO_URI'), tlsCAFile=certifi.where())
db = client['ecampus']

user = db.new_users.find_one({'rollNo': '25MX227'})
if not user or not user.get('password'):
    print("User 25MX227 or password not found in new_users")
    sys.exit(1)

print("Authenticating 25MX227 to PSG StudZone...")
# Secure credentials dictionary without logging
creds = {'rollNo': '25MX227', 'password': user['password']}

session_res = modern_login(creds)
if isinstance(session_res, tuple) or not session_res:
    print(f"Failed to authenticate to live StudZone: {session_res}")
    sys.exit(1)

session = session_res
print("SUCCESS: Authenticated to live PSG StudZone 1 as 25MX227!")

# 1. Fetch live attendance table
att_url = "https://ecampus.psgtech.ac.in/StudZone/Attendance/StudentPercentage"
att_resp = session.get(att_url, timeout=15, verify=False)
print(f"Attendance page fetch: HTTP {att_resp.status_code}")

live_attendance_rows = []
if att_resp.ok:
    soup = BeautifulSoup(att_resp.content, "html.parser")
    table = soup.find('table', id="example") or soup.find('table')
    if table:
        for tr in table.find_all('tr'):
            cells = [td.get_text(strip=True) for td in tr.find_all(['th', 'td'])]
            if cells:
                live_attendance_rows.append(cells)

# 2. Fetch live CA marks table
ca_url = "https://ecampus.psgtech.ac.in/StudZone/ContinuousAssessment/CAMarksView"
ca_resp = session.get(ca_url, timeout=15, verify=False)
print(f"CA Marks page fetch: HTTP {ca_resp.status_code}")

live_ca_courses = {}
if ca_resp.ok:
    soup = BeautifulSoup(ca_resp.content, "html.parser")
    tables = soup.find_all('table')
    for table in tables:
        for tr in table.find_all('tr'):
            cells = [td.get_text(strip=True) for td in tr.find_all(['th', 'td'])]
            if len(cells) >= 2:
                c_code = cells[0].strip()
                c_name = cells[1].strip()
                # Exclude headers
                if c_code and c_name and "COURSE" not in c_code.upper() and "MAX" not in c_code.upper() and len(c_code) >= 5:
                    live_ca_courses[c_code] = c_name

# 3. Fetch live timetable
tt_url = "https://ecampus.psgtech.ac.in/StudZone/Attendance/TimeTable"
tt_resp = session.get(tt_url, timeout=15, verify=False)
print(f"Timetable page fetch: HTTP {tt_resp.status_code}")

print("\n=======================================================")
print("ACTUAL LIVE STUDZONE SOURCE DATA FOR 25MX227")
print("=======================================================")

print("\n--- A. ATTENDANCE TABLE FROM /StudZone/Attendance/StudentPercentage ---")
if live_attendance_rows:
    headers = live_attendance_rows[0]
    print(f"Columns: {headers}")
    for row in live_attendance_rows[1:]:
        print(f"  Row: {row}")

print("\n--- B. COURSE CODES AND TITLES FROM /StudZone/ContinuousAssessment/CAMarksView ---")
for code, name in sorted(live_ca_courses.items()):
    print(f"  {code} -> {name}")

print("\n--- C. SYNTHESIZED AUTHORITATIVE ROSTER FOR 25MX227 ---")
if live_attendance_rows and len(live_attendance_rows) > 1:
    for row in live_attendance_rows[1:]:
        if len(row) >= 6:
            code = row[0]
            tot = row[1]
            exemp = row[2]
            absent = row[3]
            pres = row[4]
            pct = row[5]
            official_title = live_ca_courses.get(code, "Unknown Title")
            print(f"Course: {code} | Name: '{official_title}' | Attended: {pres}/{tot} | Absent: {absent} | Pct: {pct}%")
