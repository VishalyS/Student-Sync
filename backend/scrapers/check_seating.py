from bs4 import BeautifulSoup
from database import user_collection
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_seating_data(session):
    """
    Scrapes the exam hall seating arrangement from Legacy eCampus/StudZone2.
    :param session: authenticated requests.Session for studzone2
    :return: styled HTML table string or None
    """
    try:
        seating_page = session.get("https://ecampus.psgtech.ac.in/studzone2/EpsWfSeating.aspx", timeout=15, verify=False)
        if not seating_page.ok:
            return None

        seating_page_soup = BeautifulSoup(seating_page.content, 'html.parser')
        seating_table = seating_page_soup.find('table', id="DgSeat") or seating_page_soup.find('table', id="DgResult")
        
        if not seating_table:
            return None

        rows = seating_table.find_all('tr')
        if len(rows) <= 1:
            return None

        # Apply clean styling
        for cell in seating_table.find_all(['th', 'td']):
            cell['style'] = 'border: 1px solid black; padding: 8px;'
        if seating_table.find('th'):
            for header_cell in seating_table.find_all('th'):
                header_cell['style'] += ' background-color: #ccd6e6; color: #013281;'

        return str(seating_table)
    except Exception as e:
        print(f"Error scraping seating arrangement: {e}")
        return None


def check_seating(session, user):
    """
    Updates user seating table in database if changed for background processing.
    """
    try:
        current_seating_html = get_seating_data(session)
        if not current_seating_html:
            return False

        previous_seating_html = user.get('seating', '')
        if previous_seating_html != current_seating_html:
            if user_collection is not None:
                user_collection.update_one(
                    {'rollNo': user['rollNo']},
                    {'$set': {'seating': current_seating_html}}
                )
            return True
        return False
    except Exception as e:
        print(f"Error checking seating for {user.get('rollNo', 'unknown')}: {e}")
        return False