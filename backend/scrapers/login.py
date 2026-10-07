import requests
from bs4 import BeautifulSoup
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def login_student_studzone2(user):
    """
    Authenticates a student to the Legacy eCampus/StudZone2 portal
    using their normal Roll Number and StudZone password (Student Mode, rdolst='S').
    :param user: dict with 'rollNo'/'rollno' and 'password'/'pass_word'
    :return: authenticated requests.Session or (False, error_msg)
    """
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    login_url = 'https://ecampus.psgtech.ac.in/studzone2/'

    rollno = user.get('rollNo') or user.get('rollno')
    password = user.get('password') or user.get('pass_word')

    if not rollno or not password:
        return False, "Missing roll number or password."

    try:
        # Step 1: GET the initial login page (Student mode is selected by default)
        response = session.get(login_url, timeout=15, verify=False)
        if not response.ok:
            return False, f"Failed to reach portal. HTTP {response.status_code}"

        soup = BeautifulSoup(response.content, 'html.parser')
        form = soup.find('form')
        if not form:
            return False, "Login form not found on portal."

        viewstate = soup.find('input', {'name': '__VIEWSTATE'})
        viewstate_generator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
        event_validation = soup.find('input', {'name': '__EVENTVALIDATION'})

        if not viewstate or not viewstate_generator or not event_validation:
            return False, "Could not extract ASP.NET viewstate tokens."

        # Step 2: Submit credentials in Student Mode (rdolst='S')
        login_data = {
            '__VIEWSTATE': viewstate['value'],
            '__VIEWSTATEGENERATOR': viewstate_generator['value'],
            '__EVENTVALIDATION': event_validation['value'],
            'rdolst': 'S',
            'txtusercheck': rollno.lower(),
            'txtpwdcheck': password,
            'abcd3': 'Login'
        }

        post_url = requests.compat.urljoin(login_url, form.get('action', './'))
        login_response = session.post(post_url, data=login_data, timeout=15, verify=False)
        
        # Step 3: Verify authenticated session on student menu
        check_url = "https://ecampus.psgtech.ac.in/studzone2/AttWfStudMenu.aspx"
        menu_response = session.get(check_url, timeout=15, verify=False)
        menu_soup = BeautifulSoup(menu_response.content, 'html.parser')

        # If the login inputs are still present, authentication failed
        if menu_soup.find('input', {'name': 'txtusercheck'}) or menu_soup.find('input', {'name': 'txtpwdcheck'}):
            return False, "Invalid credentials."

        return session

    except requests.exceptions.RequestException as e:
        return False, f"Network error: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"

# Backward compatibility alias
login = login_student_studzone2
login_to_ecampus = login_student_studzone2
