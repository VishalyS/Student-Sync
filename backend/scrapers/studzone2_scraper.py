import re
import urllib3
from bs4 import BeautifulSoup

try:
    from backend.scrapers.calculate_cgpa import calculate_cgpa_from_data
except ImportError:
    try:
        from scrapers.calculate_cgpa import calculate_cgpa_from_data
    except ImportError:
        from calculate_cgpa import calculate_cgpa_from_data

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LEGACY_BASE = "https://ecampus.psgtech.ac.in/studzone2"


def clean_legacy_table(soup_table):
    """Formats and strips legacy HTML table colors for modern dark SaaS view"""
    if not soup_table:
        return ""
    for tag in soup_table.find_all(['table', 'tr', 'th', 'td', 'span', 'font']):
        if tag.has_attr('bgcolor'):
            del tag['bgcolor']
        if tag.has_attr('style'):
            cleaned_style = re.sub(r'background-color\s*:[^;]+;?', '', tag['style'], flags=re.I)
            cleaned_style = re.sub(r'color\s*:[^;]+;?', '', cleaned_style, flags=re.I)
            tag['style'] = cleaned_style.strip()
    return str(soup_table)


def scrape_studzone2_results(session):
    """Scrapes End-Semester Results from FrmEpsStudResult.aspx"""
    try:
        url = f"{LEGACY_BASE}/FrmEpsStudResult.aspx"
        resp = session.get(url, timeout=15, verify=False)
        if not resp.ok:
            return "", [], None
        
        soup = BeautifulSoup(resp.content, 'html.parser')
        res_table = soup.find('table', id='DgResult')
        if not res_table:
            return "", [], None

        courses_data = []
        for row in res_table.find_all('tr')[1:]:
            cols = [td.text.strip() for td in row.find_all(['td', 'th'])]
            if len(cols) >= 5:
                mark_str = cols[4] if len(cols) > 4 else ""
                
                # Extract numeric grade point and letter grade: e.g. "8   A" -> gp=8.0, letter="A"
                m = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z\+\*]+)', mark_str)
                if m:
                    gp = float(m.group(1))
                    grade = m.group(2).strip()
                else:
                    grade = mark_str.strip()
                    gp_map = {'O': 10.0, 'A+': 9.0, 'A': 8.0, 'B+': 7.0, 'B': 6.0, 'C': 5.0, 'RA': 0.0, 'W': 0.0, 'SA': 0.0}
                    gp = gp_map.get(grade.upper(), 0.0)

                courses_data.append({
                    "sem": cols[0] if len(cols) > 0 else "2",
                    "code": cols[1] if len(cols) > 1 else "",
                    "title": cols[2] if len(cols) > 2 else "",
                    "credits": cols[3] if len(cols) > 3 else "0",
                    "grade": grade,
                    "grade_point": gp,
                    "result_status": "Pass" if grade.upper() not in ['RA', 'W', 'SA'] else "Reappearance Required"
                })

        cgpa = calculate_cgpa_from_data(courses_data)
        return clean_legacy_table(res_table), courses_data, cgpa
    except Exception as e:
        print(f"Error scraping StudZone2 results: {e}")
        return "", [], None


def scrape_studzone2_timetable(session):
    """Scrapes Continuous Assessment & Exam Timetable from FrmEpsTimetable.aspx"""
    try:
        url = f"{LEGACY_BASE}/FrmEpsTimetable.aspx"
        resp = session.get(url, timeout=15, verify=False)
        if not resp.ok:
            return "", []
        
        soup = BeautifulSoup(resp.content, 'html.parser')
        table = soup.find('table', id='DgResult') or soup.find('table', id='table11')
        if not table:
            return "", []

        slots = []
        for row in table.find_all('tr')[1:]:
            cols = [td.text.strip() for td in row.find_all(['td', 'th'])]
            if len(cols) >= 5:
                date_val = cols[3]
                session_val = cols[4]
                slots.append({
                    "sem": cols[0] if len(cols) > 0 else "",
                    "course_code": cols[1] if len(cols) > 1 else "",
                    "course_title": cols[2] if len(cols) > 2 else "",
                    "exam_date": date_val if date_val != '*' else "Schedule Pending",
                    "session": session_val if session_val != '*' else "TBA",
                    "timing": "09:30 AM - 12:30 PM" if "FN" in session_val else ("01:30 PM - 04:30 PM" if "AN" in session_val else "Timing TBA")
                })

        return clean_legacy_table(table), slots
    except Exception as e:
        print(f"Error scraping StudZone2 timetable: {e}")
        return "", []


def scrape_studzone2_seating(session):
    """Scrapes Exam Seating Arrangement from EpsWfSeating.aspx"""
    try:
        url = f"{LEGACY_BASE}/EpsWfSeating.aspx"
        resp = session.get(url, timeout=15, verify=False)
        if not resp.ok:
            return None, []
        
        soup = BeautifulSoup(resp.content, 'html.parser')
        tables = soup.find_all('table')
        for t in tables:
            t_id = t.get('id', '')
            if 'Dg' in t_id or 'Seating' in t_id:
                # Parse seating items
                seats = []
                for row in t.find_all('tr')[1:]:
                    cells = [td.text.strip() for td in row.find_all(['td', 'th'])]
                    if cells:
                        seats.append(cells)
                return clean_legacy_table(t), seats
        return None, []
    except Exception as e:
        print(f"Error scraping StudZone2 seating: {e}")
        return None, []


def scrape_studzone2_reappearance(session):
    """Scrapes Reappearance Exam Results from FrmEpsSuppStudResult.aspx"""
    try:
        url = f"{LEGACY_BASE}/FrmEpsSuppStudResult.aspx"
        resp = session.get(url, timeout=15, verify=False)
        if not resp.ok:
            return None, []
        
        soup = BeautifulSoup(resp.content, 'html.parser')
        table = soup.find('table', id='DgResult')
        if table:
            reappearances = []
            for row in table.find_all('tr')[1:]:
                cells = [td.text.strip() for td in row.find_all(['td', 'th'])]
                if cells:
                    reappearances.append(cells)
            return clean_legacy_table(table), reappearances
        return None, []
    except Exception as e:
        print(f"Error scraping StudZone2 reappearance: {e}")
        return None, []


def scrape_studzone2_revaluation(session):
    """Scrapes Revaluation Results from FrmEpsRevalStudResult.aspx"""
    try:
        url = f"{LEGACY_BASE}/FrmEpsRevalStudResult.aspx"
        resp = session.get(url, timeout=15, verify=False)
        if not resp.ok:
            return None, []
        
        soup = BeautifulSoup(resp.content, 'html.parser')
        table = soup.find('table', id='DgResult')
        if table:
            reval_entries = []
            for row in table.find_all('tr')[1:]:
                cells = [td.text.strip() for td in row.find_all(['td', 'th'])]
                if cells:
                    reval_entries.append(cells)
            return clean_legacy_table(table), reval_entries
        return None, []
    except Exception as e:
        print(f"Error scraping StudZone2 revaluation: {e}")
        return None, []


def scrape_studzone2_applications(session):
    """Scrapes Retotalling & Revaluation instructions and status from portal"""
    apps = {
        "retotalling_instructions": "",
        "revaluation_instructions": ""
    }
    try:
        # 1. Retotalling Application
        r_retot = session.get(f"{LEGACY_BASE}/FrmEpsImpInstRetot.aspx", timeout=12, verify=False)
        if r_retot.ok:
            s = BeautifulSoup(r_retot.content, 'html.parser')
            t = s.find('table', class_='GenCSS') or s.find('table')
            apps['retotalling_instructions'] = clean_legacy_table(t) if t else ""

        # 2. Revaluation Application
        r_reval = session.get(f"{LEGACY_BASE}/FrmEpsImpInst.aspx", timeout=12, verify=False)
        if r_reval.ok:
            s = BeautifulSoup(r_reval.content, 'html.parser')
            t = s.find('table', class_='GenCSS') or s.find('table')
            apps['revaluation_instructions'] = clean_legacy_table(t) if t else ""

    except Exception as e:
        print(f"Error scraping StudZone2 applications: {e}")

    return apps


def scrape_studzone2_circulars(session):
    """Scrapes Examination Circulars, Guidelines & PDF links from Menu"""
    circulars = []
    try:
        url = f"{LEGACY_BASE}/AttWfStudMenu.aspx"
        resp = session.get(url, timeout=12, verify=False)
        if resp.ok:
            soup = BeautifulSoup(resp.content, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                text = a.text.strip()
                if '.pdf' in href.lower() or 'report_pdf' in href.lower():
                    normalized_href = href.replace('\\', '/')
                    clean_url = f"{LEGACY_BASE}/{normalized_href}"
                    circulars.append({
                        "title": text if text else "Examination Guidelines & Regulations",
                        "url": clean_url
                    })
    except Exception as e:
        print(f"Error scraping StudZone2 circulars: {e}")
    return circulars


def scrape_studzone2_all(session, rollNo):
    """
    Executes complete data extraction across all StudZone 2 modules:
    - Semester Results
    - CGPA
    - Exam Timetable
    - Exam Seating Arrangement
    - Reappearance Exam Results
    - Revaluation Results
    - Retotalling & Revaluation Applications
    - Examination Guidelines & Circulars
    """
    results_html, parsed_results, cgpa = scrape_studzone2_results(session)
    print(f"[StudZone2] Results: {'SUCCESS' if parsed_results or results_html else 'NO_DATA'}")
    print(f"[StudZone2] CGPA: {'SUCCESS' if cgpa is not None else 'NO_DATA'}")

    timetable_html, parsed_timetable = scrape_studzone2_timetable(session)
    print(f"[StudZone2] Timetable: {'SUCCESS' if parsed_timetable or timetable_html else 'NO_DATA'}")

    seating_html, seating_slots = scrape_studzone2_seating(session)
    print(f"[StudZone2] Seating: {'SUCCESS' if seating_html or seating_slots else 'NO_DATA'}")

    reappearance_html, reappearance_slots = scrape_studzone2_reappearance(session)
    print(f"[StudZone2] Reappearance: {'SUCCESS' if reappearance_html or reappearance_slots else 'NO_DATA'}")

    revaluation_html, revaluation_slots = scrape_studzone2_revaluation(session)
    print(f"[StudZone2] Revaluation: {'SUCCESS' if revaluation_html or revaluation_slots else 'NO_DATA'}")

    applications = scrape_studzone2_applications(session)
    print(f"[StudZone2] Applications (Retotalling/Revaluation): {'SUCCESS' if applications.get('retotalling_instructions') or applications.get('revaluation_instructions') else 'NO_DATA'}")

    circulars = scrape_studzone2_circulars(session)
    print(f"[StudZone2] Circulars: {'SUCCESS' if circulars else 'NO_DATA'}")

    # Explicit audit of legacy services redirected to StudZone 1
    print("[StudZone2] Fees: NO_DATA (Hosted on StudZone 1)")
    print("[StudZone2] Feedback: NO_DATA (Hosted on StudZone 1)")
    print("[StudZone2] Hostel: NO_DATA (Hosted on StudZone 1)")
    print("[StudZone2] Scholarships: NO_DATA (Hosted on StudZone 1)")

    return {
        "results_html": results_html,
        "parsed_results": parsed_results,
        "cgpa": cgpa,
        "timetable_html": timetable_html,
        "parsed_timetable": parsed_timetable,
        "seating_html": seating_html,
        "seating_slots": seating_slots,
        "reappearance_html": reappearance_html,
        "reappearance_slots": reappearance_slots,
        "revaluation_html": revaluation_html,
        "revaluation_slots": revaluation_slots,
        "applications": applications,
        "circulars": circulars
    }
