from bs4 import BeautifulSoup
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_result_data(session):
    """
    Scrapes semester results table and structured course grade records
    from Legacy eCampus/StudZone2.
    :param session: authenticated requests.Session for studzone2
    :return: (result_data_list, final_table_html) or ([], "")
    """
    try:
        result_page = session.get("https://ecampus.psgtech.ac.in/studzone2/FrmEpsStudResult.aspx", timeout=15, verify=False)
        if not result_page.ok:
            return [], ""

        result_page_soup = BeautifulSoup(result_page.content, 'html.parser')
        result_table = result_page_soup.find('table', {'id': 'DgResult'})
        if not result_table:
            return [], ""

        # Construct clean HTML table with borders and styling
        for cell in result_table.find_all(['th', 'td']):
            cell['style'] = 'border: 1px solid black; padding: 8px;'
        if result_table.find('th'):
            for header_cell in result_table.find_all('th'):
                header_cell['style'] += ' background-color: #ccd6e6; color: #013281;'

        final_table = str(result_table)
        result_data = []
        rows = result_table.find_all('tr')
        if not rows:
            return [], final_table

        titles = [title.text.strip() for title in rows[0].find_all(['td', 'th'])]
        for row in rows[1:]:
            cells = [cell.text.strip() for cell in row.find_all(['td', 'th'])]
            if len(cells) == len(titles):
                result_data.append(dict(zip(titles, cells)))

        return result_data, final_table
    except Exception as e:
        print(f"Error processing result data: {e}")
        return [], ""