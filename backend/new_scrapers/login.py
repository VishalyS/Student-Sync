import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def login(user):
    """
    Logs in to the eCampus website using the provided roll number and password.
    :param user: dict, Contains 'rollNo' and 'password' keys.
    :return: session object if login successful, else (False, error message)
    """
    url = "https://ecampus.psgtech.ac.in/StudZone"
    session = requests.Session()

    # Configure retry strategy
    retry_strategy = Retry(
        total=3,  # Retry up to 3 times
        backoff_factor=0.5,  # Wait 0.5s, 1s, 2s between retries
        status_forcelist=[500, 502, 503, 504],  # Retry on these HTTP status codes
        allowed_methods=["GET", "POST"]  # Retry for GET and POST requests
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    rollno = user.get('rollNo') or user.get('rollno')
    password = user.get('password') or user.get('pass_word')
    if not rollno or not password:
        return False, "Missing roll number or password."

    try:
        response = session.get(url, timeout=10, verify=False)  # SSL verification disabled (temporary workaround)
        if not response.ok:
            return False, f"Failed to fetch login page. HTTP {response.status_code}"

        soup = BeautifulSoup(response.content, "html.parser")
        form = soup.find("form", {"class": "form__content"})
        if not form:
            return False, "Login form not found."

        payload = {tag.get("name"): tag.get("value", "") for tag in form.find_all("input")}
        if "rollno" in payload: payload["rollno"] = rollno
        if "password" in payload: payload["password"] = password
        # Set the terms checkbox as checked (required for login)
        payload["chkterms"] = "on"

        login_url = requests.compat.urljoin(url, form.get("action"))
        login_response = session.post(login_url, data=payload, timeout=12, verify=False)
        if not login_response.ok:
            return False, f"Login failed. HTTP {login_response.status_code}"

        # If the login form is still present on the page, credentials were rejected
        resp_soup = BeautifulSoup(login_response.content, "html.parser")
        if resp_soup.find("form", {"class": "form__content"}) or resp_soup.find("div", {"class": "login-error"}):
            return False, "Invalid credentials."

        # Verify authenticated session
        test_check = session.get("https://ecampus.psgtech.ac.in/StudZone/Attendance/StudentPercentage", timeout=12, verify=False)
        if "login" in test_check.url.lower() or BeautifulSoup(test_check.content, "html.parser").find("form", {"class": "form__content"}):
            return False, "Invalid credentials."

        return session  # Login successful

    except requests.exceptions.RequestException as e:
        return False, f"Network error: {e}"

    except Exception as e:
        return False, f"Unexpected error: {e}"