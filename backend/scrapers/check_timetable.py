from bs4 import BeautifulSoup
from database import user_collection
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_timetable_data(session):
    """
    Scrapes the exam test timetable from Legacy eCampus/StudZone2.
    :param session: authenticated requests.Session for studzone2
    :return: styled HTML table string or ""
    """
    try:
        time_table_page_response = session.get("https://ecampus.psgtech.ac.in/studzone2/FrmEpsTestTimetable.aspx", timeout=15, verify=False)
        if not time_table_page_response.ok:
            return ""

        time_table_page_soup = BeautifulSoup(time_table_page_response.content, 'html.parser')
        table = time_table_page_soup.find('table', {'id': 'DgResult'})
        if table is None:
            return ""

        rows = table.find_all('tr')
        if len(rows) <= 1:
            return ""

        # Construct styled HTML table
        html_table = "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse; width: 100%;'>"
        headers = [header.text.strip() for header in rows[0].find_all(['td', 'th'])]
        html_table += "<tr style='background-color: #ccd6e6; color: #013281; font-weight: bold;'>"
        for header in headers:
            html_table += f"<th style='border: 1px solid black; padding: 8px;'>{header}</th>"
        html_table += "</tr>"

        for row in rows[1:]:
            columns = [col.text.strip() for col in row.find_all(['td', 'th'])]
            html_table += "<tr>"
            for col in columns:
                html_table += f"<td style='border: 1px solid black; padding: 8px;'>{col}</td>"
            html_table += "</tr>"

        html_table += "</table>"
        return html_table

    except Exception as e:
        print(f"Error checking test timetable: {e}")
        return ""


def check_timetable(session, user):
    """
    Updates user timetable in database if changed for background processing.
    """
    try:
        html_table = get_timetable_data(session)
        if not html_table:
            return False

        if html_table != user.get('timetable', None):
            if user_collection is not None:
                user_collection.update_one(
                    {'rollNo': user['rollNo']},
                    {'$set': {'timetable': html_table}}
                )
            return True
        return False
    except Exception as e:
        print(f"Error checking test timetable for {user.get('rollNo', 'unknown')}: {e}")
        return False
