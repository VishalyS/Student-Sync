import re
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://ecampus.psgtech.ac.in"


def clean_html_table(soup_table):
    """Formats and cleans an HTML table from StudZone with dark theme friendly styling"""
    if not soup_table:
        return ""
    
    # Strip hardcoded background and text colors
    for tag in soup_table.find_all(['table', 'tr', 'th', 'td', 'span', 'font', 'div']):
        if tag.has_attr('bgcolor'):
            del tag['bgcolor']
        if tag.has_attr('style'):
            cleaned_style = re.sub(r'background-color\s*:[^;]+;?', '', tag['style'], flags=re.I)
            cleaned_style = re.sub(r'color\s*:[^;]+;?', '', cleaned_style, flags=re.I)
            tag['style'] = cleaned_style.strip()

    return str(soup_table)


def scrape_studzone1_profile(session, rollNo=""):
    """Scrapes profile info from /StudZone/Home/Profile and headers"""
    profile_data = {
        "Roll Number": rollNo,
        "Institution": "PSG College of Technology"
    }
    try:
        # 1. Try Profile subpage
        resp = session.get(f"{BASE_URL}/StudZone/Home/Profile", timeout=10, verify=False)
        if resp.ok and len(resp.content) > 200:
            soup = BeautifulSoup(resp.content, "html.parser")
            name_tag = soup.find('h4', class_='user-name') or soup.find('span', class_='user-name')
            if name_tag:
                profile_data['Name'] = name_tag.text.strip()
            for div in soup.find_all(['div', 'tr', 'p', 'li']):
                text = div.text.strip()
                if ':' in text and len(text) < 140:
                    parts = [p.strip() for p in text.split(':', 1)]
                    if len(parts) == 2 and parts[0] and parts[1]:
                        clean_k = re.sub(r'[^a-zA-Z0-9_ ]', '', parts[0]).strip()
                        if clean_k and len(clean_k) < 30 and clean_k not in profile_data:
                            profile_data[clean_k] = parts[1]

        # 2. Extract verified student header tags from Attendance page
        att_resp = session.get(f"{BASE_URL}/StudZone/Attendance/StudentPercentage", timeout=10, verify=False)
        if att_resp.ok:
            att_soup = BeautifulSoup(att_resp.content, "html.parser")
            for b in att_soup.find_all(['b', 'strong', 'span']):
                t = b.text.strip()
                if any(deg in t.upper() for deg in ['MCA', 'B.E', 'B.TECH', 'M.E', 'M.TECH', 'MASTER', 'BACHELOR', 'COMPUTER APPLICATIONS']):
                    profile_data['Degree'] = t
                elif rollNo and rollNo.upper() in t.upper() and len(t) < 20:
                    profile_data['Roll Number'] = t
                elif len(t) > 3 and not any(c.isdigit() for c in t) and t.isupper() and len(t) < 35 and 'PERCENTAGE' not in t and 'ATTENDANCE' not in t:
                    if 'Name' not in profile_data:
                        profile_data['Name'] = t

        return profile_data
    except Exception as e:
        print(f"Error scraping StudZone1 profile: {e}")
        return profile_data


def is_valid_course_code(code: str) -> bool:
    """Validates PSG College of Technology course codes (e.g. 23MX31, 23MXM4, 23MXAY, TWM)."""
    if not code or not isinstance(code, str):
        return False
    c = code.strip().upper()
    if any(ignore in c for ignore in ["COURSE", "MAX", "PERIOD", "TIME", "TOTAL", "HOURS", "DATE"]):
        return False
    return bool(re.match(r'^[0-9]{2}[A-Z]{2}[A-Z0-9]{2,4}$|^TWM$', c))


def parse_attendance_html(html_content, course_name_map=None):
    """
    Parses raw attendance table HTML into (cleaned_html, parsed_courses).
    Works on live HTTP response content or stored database HTML.
    Returns ("", []) if table is missing or has no data rows.
    """
    if not html_content:
        return "", []
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        table = soup.find('table', id="example") or soup.find('table')
        if not table:
            return "", []

        # Parse attendance table with column header mapping for robustness
        rows = table.find_all('tr')
        if not rows:
            return "", []

        # Determine column indexes from header row
        header_cells = [th.text.strip().lower() for th in rows[0].find_all(['th', 'td'])]
        col_map = {}
        for idx, title in enumerate(header_cells):
            if "course code" in title:
                col_map['code'] = idx
            elif "total hr" in title and "exemp" not in title:
                col_map['total_hr'] = idx
            elif "exemp hr" in title:
                col_map['exempt_hr'] = idx
            elif "tot absent" in title:
                col_map['absent'] = idx
            elif "total present" in title:
                col_map['present'] = idx
            elif "(%) attendance" in title or ("attendance" in title and "%" in title):
                col_map['percentage'] = idx

        # Fallback to original positions if any column missing
        if len(col_map) < 6:
            col_map = {
                'code': 0,
                'total_hr': 1,
                'exempt_hr': 2,
                'absent': 3,
                'present': 4,
                'percentage': 5,
            }

        parsed_courses = []
        for row in rows[1:]:
            cells = [td.text.strip() for td in row.find_all('td')]
            if len(cells) <= max(col_map.values()):
                continue

            course_code = cells[col_map['code']].strip().upper()
            if not course_code:
                continue

            tot_hr = cells[col_map['total_hr']]
            exempt_hr = cells[col_map['exempt_hr']]
            tot_absent = cells[col_map['absent']]
            tot_present = cells[col_map['present']]
            pct_str = cells[col_map['percentage']].replace('%', '').strip()
            try:
                pct_val = float(pct_str)
            except ValueError:
                pct_val = None

            # Look up subject name strictly from the authenticated student's own verified course map
            subj_name = ""
            if course_name_map and isinstance(course_name_map, dict):
                subj_name = course_name_map.get(course_code, "")
            
            # Neutral fallback if not found in student's own CA marks or timetable
            if not subj_name:
                subj_name = f"Subject {course_code}"

            course = {
                "code": course_code,
                "name": subj_name,
                "total_classes": tot_hr,
                "exempt_hr": exempt_hr,
                "absent": tot_absent,
                "attended": tot_present,
                "percentage": f"{pct_str}%",
                "percentage_num": pct_val,
                "status": "Good" if (pct_val is not None and pct_val >= 75) else "Low"
            }
            parsed_courses.append(course)

        return clean_html_table(table), parsed_courses
    except Exception as e:
        print(f"Error parsing attendance HTML: {e}")
        return "", []


def scrape_studzone1_attendance(session, sub_collection=None, course_name_map=None):
    """
    Scrapes attendance percentage table from /StudZone/Attendance/StudentPercentage.
    Maps course codes strictly using the authenticated student's own course_name_map.
    Never uses global hardcoded mappings or cross-student shared caches.
    """
    try:
        resp = session.get(f"{BASE_URL}/StudZone/Attendance/StudentPercentage", timeout=15, verify=False)
        if not resp.ok:
            return "", []
        return parse_attendance_html(resp.content, course_name_map=course_name_map)
    except Exception as e:
        print(f"Error scraping StudZone1 attendance: {e}")
        return "", []


def scrape_studzone1_ca_marks(session, sub_collection=None):
    """Scrapes Continuous Assessment marks from /StudZone/ContinuousAssessment/CAMarksView"""
    try:
        resp = session.get(f"{BASE_URL}/StudZone/ContinuousAssessment/CAMarksView", timeout=15, verify=False)
        if not resp.ok:
            return "", []
        
        soup = BeautifulSoup(resp.content, "html.parser")
        marks_tables = soup.find_all('table', class_="table table-bordered table-striped") or soup.find_all('table')
        if not marks_tables:
            return "", []

        all_tables_html = ""
        parsed_subjects = []

        for table in marks_tables:
            cleaned_tbl = clean_html_table(table)
            all_tables_html += cleaned_tbl + "<br>"

            rows = table.find_all('tr')
            for row in rows:
                cells = [td.text.strip() for td in row.find_all(['th', 'td'])]
                if len(cells) >= 2 and not row.find('th'):
                    subject_code = cells[0].strip().upper()
                    subject_name = cells[1].strip()
                    # Validate genuine course code and genuine title (avoiding subheaders like 'Max: 50')
                    if is_valid_course_code(subject_code) and subject_name and not subject_name.upper().startswith("MAX:"):
                        mark_entry = {
                            "code": subject_code,
                            "name": subject_name,
                            "ca1": cells[2] if len(cells) > 2 else "-",
                            "ca2": cells[3] if len(cells) > 3 else "-",
                            "ca3": cells[4] if len(cells) > 4 else "-",
                            "total": cells[-1] if len(cells) > 2 else "-",
                            "marks_data": cells[2:] if len(cells) > 2 else []
                        }
                        parsed_subjects.append(mark_entry)
                        
                        if sub_collection is not None:
                            try:
                                if not sub_collection.find_one({'subject_code': subject_code}):
                                    sub_collection.insert_one({'subject_code': subject_code, 'subject_name': subject_name, 'code': subject_code, 'name': subject_name})
                            except Exception:
                                pass

        return all_tables_html, parsed_subjects
    except Exception as e:
        print(f"Error scraping StudZone1 CA marks: {e}")
        return "", []


def scrape_studzone1_class_timetable(session):
    """Scrapes weekly class timetable from /StudZone/Attendance/TimeTable"""
    try:
        resp = session.get(f"{BASE_URL}/StudZone/Attendance/TimeTable", timeout=15, verify=False)
        if not resp.ok:
            return "", []
        
        soup = BeautifulSoup(resp.content, "html.parser")
        table = soup.find('table', class_=re.compile(r'timetable-table|table-bordered', re.I)) or soup.find('table')
        if not table:
            return "", []

        # Parse schedule rows, expanding colspan for multi-period slots (e.g. laboratory sessions)
        schedule_rows = []
        for row in table.find_all('tr'):
            cells = []
            for td in row.find_all(['th', 'td']):
                colspan_str = td.get('colspan')
                try:
                    colspan = max(1, int(colspan_str)) if colspan_str else 1
                except (ValueError, TypeError):
                    colspan = 1
                cell_text = td.text.strip()
                for _ in range(colspan):
                    cells.append(cell_text)
            if cells:
                schedule_rows.append(cells)

        return clean_html_table(table), schedule_rows
    except Exception as e:
        print(f"Error scraping StudZone1 class timetable: {e}")
        return "", []


def scrape_studzone1_fees(session):
    """Scrapes Semester Fees & Payment History from /StudZone/Fees/Fees"""
    try:
        resp = session.get(f"{BASE_URL}/StudZone/Fees/Fees", timeout=15, verify=False)
        if not resp.ok:
            return "", [], "Not Available"
        
        soup = BeautifulSoup(resp.content, "html.parser")
        tables = soup.find_all('table')
        if not tables:
            return "", [], "No Fee Records Published"

        combined_html = ""
        for t in tables:
            combined_html += clean_html_table(t) + "<br>"

        # Parse fee items if possible
        fee_items = []
        for t in tables:
            for row in t.find_all('tr'):
                cells = [td.text.strip() for td in row.find_all('td')]
                if len(cells) >= 2:
                    fee_items.append({
                        "fee_type": cells[0],
                        "amount": cells[1],
                        "details": cells[2:] if len(cells) > 2 else []
                    })

        return combined_html, fee_items, "Active / Available"
    except Exception as e:
        print(f"Error scraping StudZone1 fees: {e}")
        return "", [], "Error fetching fees"


def scrape_studzone1_hostel(session):
    """Scrapes Hostel Status & Fee Payment from /StudZone/Hostel/PaymentStart"""
    try:
        resp = session.get(f"{BASE_URL}/StudZone/Hostel/PaymentStart", timeout=15, verify=False)
        if not resp.ok:
            return "", "Not Available", []
        
        soup = BeautifulSoup(resp.content, "html.parser")
        tables = soup.find_all('table')
        combined_html = ""
        for t in tables:
            combined_html += clean_html_table(t) + "<br>"

        status_text = "Registered / Hostel Data Available" if tables else "No Active Hostel Allocation"
        
        hostel_records = []
        for t in tables:
            for row in t.find_all('tr'):
                cells = [td.text.strip() for td in row.find_all('td')]
                if cells:
                    hostel_records.append(cells)

        return combined_html, status_text, hostel_records
    except Exception as e:
        print(f"Error scraping StudZone1 hostel: {e}")
        return "", "Error fetching hostel", []


def scrape_studzone1_scholarships(session):
    """Scrapes Scholarship Apply, Received & Vallalar entries"""
    try:
        results = {
            "applied": [],
            "received": [],
            "vallalar": [],
            "html_apply": "",
            "html_received": "",
            "html_vallalar": ""
        }

        # Apply
        try:
            r = session.get(f"{BASE_URL}/StudZone/Scholar/ScholarshipApply", timeout=10, verify=False)
            if r.ok:
                s = BeautifulSoup(r.content, "html.parser")
                t = s.find('table', id="example") or s.find('table')
                if t:
                    results["html_apply"] = clean_html_table(t)
                    for row in t.find_all('tr')[1:]:
                        cells = [td.text.strip() for td in row.find_all('td')]
                        if cells:
                            results["applied"].append({
                                "name": cells[0] if len(cells) > 0 else "",
                                "type": cells[1] if len(cells) > 1 else "",
                                "status": cells[2] if len(cells) > 2 else "Available"
                            })
        except Exception:
            pass

        # Received
        try:
            r = session.get(f"{BASE_URL}/StudZone/Scholar/ScholarshipRecieved", timeout=10, verify=False)
            if r.ok:
                s = BeautifulSoup(r.content, "html.parser")
                t = s.find('table', id="example") or s.find('table')
                if t:
                    results["html_received"] = clean_html_table(t)
                    for row in t.find_all('tr')[1:]:
                        cells = [td.text.strip() for td in row.find_all('td')]
                        if cells:
                            results["received"].append({
                                "name": cells[0] if len(cells) > 0 else "",
                                "amount": cells[1] if len(cells) > 1 else "",
                                "academic_year": cells[2] if len(cells) > 2 else ""
                            })
        except Exception:
            pass

        # Vallalar
        try:
            r = session.get(f"{BASE_URL}/StudZone/Scholar/VallalarScholarship", timeout=10, verify=False)
            if r.ok:
                s = BeautifulSoup(r.content, "html.parser")
                t = s.find('table')
                if t:
                    results["html_vallalar"] = clean_html_table(t)
        except Exception:
            pass

        return results
    except Exception as e:
        print(f"Error scraping StudZone1 scholarships: {e}")
        return {}


def scrape_studzone1_feedback(session):
    """Scrapes Course & Intermediate feedback schedules"""
    try:
        schedules = []
        for path, ftype in [
            ('/StudZone/Feedback/endsemester', 'End Semester'),
            ('/StudZone/Feedback/Intermediate', 'Intermediate')
        ]:
            try:
                r = session.get(f"{BASE_URL}{path}", timeout=10, verify=False)
                if r.ok:
                    soup = BeautifulSoup(r.content, "html.parser")
                    text = ' '.join(soup.stripped_strings)
                    is_open = "NOT SCHEDULED" not in text.upper()
                    schedules.append({
                        "type": ftype,
                        "status": "Scheduled / Open" if is_open else "Not Scheduled",
                        "description": "Feedback window active on portal" if is_open else "Feedback is currently not scheduled for this session."
                    })
            except Exception:
                pass
        return schedules
    except Exception as e:
        print(f"Error scraping StudZone1 feedback: {e}")
        return []


def scrape_studzone1_leave(session):
    """Scrapes student leave & On-Duty records from /StudZone/Attendance/leaveentry"""
    try:
        resp = session.get(f"{BASE_URL}/StudZone/Attendance/leaveentry", timeout=15, verify=False)
        if not resp.ok:
            return "", []
        
        soup = BeautifulSoup(resp.content, "html.parser")
        table = soup.find('table')
        if not table:
            return "", []

        entries = []
        for row in table.find_all('tr')[1:]:
            cells = [td.text.strip() for td in row.find_all(['td', 'th'])]
            if cells:
                entries.append(cells)

        return clean_html_table(table), entries
    except Exception as e:
        print(f"Error scraping StudZone1 leave: {e}")
        return "", []


def scrape_studzone1_all(session, rollNo, sub_collection=None):
    """
    Executes complete data extraction across all StudZone 1 modules:
    - Profile
    - Attendance Percentage
    - CA Marks
    - Weekly Class Timetable
    - Fees & Dues
    - Hostel Details
    - Scholarships
    - Feedback
    - Leave / OD
    """
    profile = scrape_studzone1_profile(session, rollNo)
    print(f"[StudZone1] Profile: {'SUCCESS' if profile else 'NO_DATA'}")

    # 1. Scrape CA Marks FIRST to build authoritative student-specific course mapping
    ca_marks_html, parsed_marks = scrape_studzone1_ca_marks(session, sub_collection)
    print(f"[StudZone1] CA Marks: {'SUCCESS' if parsed_marks or ca_marks_html else 'NO_DATA'}")

    # 2. Scrape Class Timetable SECOND to capture any additional student courses
    class_timetable_html, class_schedule = scrape_studzone1_class_timetable(session)
    print(f"[StudZone1] Class Timetable: {'SUCCESS' if class_timetable_html else 'NO_DATA'}")

    # 3. Build authenticated student's own {course_code: course_name} map
    student_course_map = {}
    for m in parsed_marks:
        if isinstance(m, dict):
            c_code = (m.get('code') or '').strip().upper()
            c_name = (m.get('name') or '').strip()
            if is_valid_course_code(c_code) and c_name and not c_name.upper().startswith("MAX:"):
                student_course_map[c_code] = c_name

    # Supplement from timetable matrix if any scheduled course wasn't in CA marks
    if class_schedule and isinstance(class_schedule, list):
        for row in class_schedule:
            if isinstance(row, list):
                for cell in row:
                    cell_str = str(cell)
                    match = re.search(r'\b([0-9]{2}[A-Z]{2}[A-Z0-9]{2,4})\b', cell_str)
                    if match:
                        code = match.group(1).upper()
                        if code not in student_course_map and is_valid_course_code(code):
                            lines = [l.strip() for l in re.split(r'[\r\n]+', cell_str) if l.strip()]
                            if len(lines) >= 3:
                                name = " ".join(lines[2:]).strip()
                                if name and not name.upper().startswith("MAX:"):
                                    student_course_map[code] = name

    # 4. Scrape Attendance THIRD using the authenticated student's own verified course map
    attendance_html, parsed_attendance = scrape_studzone1_attendance(session, sub_collection, course_name_map=student_course_map)
    print(f"[StudZone1] Attendance: {'SUCCESS' if parsed_attendance or attendance_html else 'NO_DATA'}")

    fees_html, fee_items, fee_status = scrape_studzone1_fees(session)
    print(f"[StudZone1] Fees: {'SUCCESS' if fees_html else 'NO_DATA'}")

    hostel_html, hostel_status, hostel_records = scrape_studzone1_hostel(session)
    print(f"[StudZone1] Hostel: {'SUCCESS' if hostel_html or hostel_status else 'NO_DATA'}")

    scholarships = scrape_studzone1_scholarships(session)
    print(f"[StudZone1] Scholarships: {'SUCCESS' if scholarships else 'NO_DATA'}")

    feedback = scrape_studzone1_feedback(session)
    print(f"[StudZone1] Feedback: {'SUCCESS' if feedback else 'NO_DATA'}")

    leave_html, leave_entries = scrape_studzone1_leave(session)
    print(f"[StudZone1] Leave: {'SUCCESS' if leave_html else 'NO_DATA'}")

    return {
        "profile": profile,
        "attendance_html": attendance_html,
        "parsed_attendance": parsed_attendance,
        "ca_marks_html": ca_marks_html,
        "parsed_marks": parsed_marks,
        "class_timetable_html": class_timetable_html,
        "class_schedule": class_schedule,
        "fees_html": fees_html,
        "fee_items": fee_items,
        "fee_status": fee_status,
        "hostel_html": hostel_html,
        "hostel_status": hostel_status,
        "hostel_records": hostel_records,
        "scholarships": scholarships,
        "feedback": feedback,
        "leave_html": leave_html,
        "leave_entries": leave_entries
    }
