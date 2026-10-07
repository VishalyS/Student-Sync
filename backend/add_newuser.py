from flask import jsonify
import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
import smtplib
from email.mime.text import MIMEText
import re
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI) if MONGO_URI else None
db = client['ecampus'] if client else None
user_collection = db['new_users'] if db is not None else None
attendance_collection = db['attendance'] if db is not None else None
result_collection = db['result'] if db is not None else None
session = requests.Session()

def send_email(recipient_email, subject, body):
    sender_email = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))

    if not sender_email or not password:
        print("Warning: SMTP credentials not configured in environment variables.")
        return

    # Create the MIMEText message object with HTML content
    msg = MIMEText(body, 'html')  # 'html' specifies the format

    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = recipient_email

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
            print(f"Email successfully sent to {recipient_email}")
    except Exception as e:
        print(f"Error sending email: {e}")

def get_attendance_data(session):
    try:
        # Fetch the attendance page
        attendance_page_response = session.get("https://ecampus.psgtech.ac.in/studzone2/AttWfPercView.aspx")
        soup = BeautifulSoup(attendance_page_response.content, 'html.parser')

        # Find the attendance table
        table = soup.find('table', id='PDGcourpercView')
        if table is None:
            print("Attendance table not found.")
            return

        # Construct the HTML table
        html_table = "<table border='1' cellpadding='5' cellspacing='0'>"
        
        # Extract table headers
        headers = [header.get_text(strip=True) for header in table.find_all('th')]
        html_table += "<tr>"
        for header in headers:
            html_table += f"<th>{header}</th>"
        html_table += "</tr>"

        # Extract table rows, skipping the first row (header)
        for row in table.find_all('tr'):
            columns = [col.get_text(strip=True) for col in row.find_all('td')]
            html_table += "<tr>"
            for col in columns:
                html_table += f"<td>{col}</td>"
            html_table += "</tr>"
        
        html_table += "</table>"

        return html_table        
    except requests.RequestException as e:
        print(f"Error fetching the attendance data: {e}")
        return None

    except Exception as e:
        print(f"Error processing attendance data: {e}")
        return None

def login_as_parent(rollNo, password):
    login_url = 'https://ecampus.psgtech.ac.in/studzone2/'

    try:
        # Step 1: Access the initial login page
        response = session.get(login_url)
        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract the necessary form data (__VIEWSTATE, __VIEWSTATEGENERATOR, __EVENTVALIDATION)
        viewstate = soup.find('input', {'name': '__VIEWSTATE'})['value']
        viewstate_generator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})['value']
        event_validation = soup.find('input', {'name': '__EVENTVALIDATION'})['value']

        # Step 2: Simulate the selection of the "Parent" radio button (rdolst_3) with a POST request
        parent_radio_data = {
            '__VIEWSTATE': viewstate,
            '__VIEWSTATEGENERATOR': viewstate_generator,
            '__EVENTVALIDATION': event_validation,
            'rdolst': 'P',  # Selecting "Parent"
            '__EVENTTARGET': 'rdolst$3',  # Trigger the postback for the "Parent" option
            '__EVENTARGUMENT': ''  # Keep this blank as per POST-back behavior
        }

        # Send POST request to select "Parent" option
        post_response = session.post(login_url, data=parent_radio_data)

        # Check if we reached the parent login page
        if 'Parent' not in post_response.text:
            raise ValueError("Failed to reach the parent login page.")

        # Parse the response again to get updated form data
        soup = BeautifulSoup(post_response.content, 'html.parser')
        viewstate = soup.find('input', {'name': '__VIEWSTATE'})['value']
        viewstate_generator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})['value']
        event_validation = soup.find('input', {'name': '__EVENTVALIDATION'})['value']

        # Step 3: Perform the login as Parent
        login_data = {
            '__VIEWSTATE': viewstate,
            '__VIEWSTATEGENERATOR': viewstate_generator,
            '__EVENTVALIDATION': event_validation,
            'txtusercheck': rollNo,  # This is the 10-digit mobile number as roll number
            'txtpwdcheck': password,  # This is the password (usually mobile number)
            'abcd3': 'Login'
        }

        # Send login request
        response = session.post(login_url, data=login_data)

        # Step 4: Check if login was successful and access the attendance page
        attendance_page_response = session.get("https://ecampus.psgtech.ac.in/studzone2/AttWfStudMenu.aspx")
        if 'ASP.NET Ajax client-side framework failed to load.' in attendance_page_response.text:
            return False
        else:
            return session
    except requests.exceptions.HTTPError as http_err:
        return f"HTTP error occurred: {http_err}"
    except ValueError as val_err:
        return f"Value error: {val_err}"
    except Exception as err:
        return f"An error occurred: {err}"

def check_timetable(session):
    try:
        # Step 4: Fetch timetable page and parse
        time_table_page_response = session.get("https://ecampus.psgtech.ac.in/studzone2/FrmEpsTestTimetable.aspx")
        time_table_page_soup = BeautifulSoup(time_table_page_response.content, 'html.parser')
        
        # Step 5: Find and extract the table data
        table = time_table_page_soup.find('table', {'id': 'DgResult'})
        if table is None:
            print("Test timetable not found.")
            return
        
        # Construct the HTML table
        html_table = "<table border='1' cellpadding='5' cellspacing='0'>"
        
        # Extract table headers
        headers = [header.text.strip() for header in table.find_all('tr')[0].find_all('td')]
        html_table += "<tr>"
        for header in headers:
            html_table += f"<th>{header}</th>"
        html_table += "</tr>"

        # Extract table rows
        for row in table.find_all('tr')[1:]:
            columns = [col.text.strip() for col in row.find_all('td')]
            html_table += "<tr>"
            for col in columns:
                html_table += f"<td>{col}</td>"
            html_table += "</tr>"
        
        html_table += "</table>"
        return html_table

    except Exception as e:
        print(f"Error checking test timetable: {e}")
        return None
def register(rollNo, password):

    try:
        # Check if the user already exists in the database
        existing_user = user_collection.find_one({"rollNo": rollNo})
        if existing_user:
            # return jsonify({"message": "User already registered."}), 409
            print(f"User {rollNo} already registered.")
            return

        # Attempt to login to eCampus with provided credentials
        session = login_as_parent(rollNo, password)
        if not session:
            # return jsonify({"message": "Login failed. Invalid credentials."}), 401
            print(f"Login failed for user {rollNo}. Invalid credentials.")
            return

        # If login successful, save the user to the database
        new_user = {
            "rollNo": rollNo,
            "password": password,
            "notifications": {
                "attendance": True,
                "marks": True,
                "timetable": True,
                "seatingArrangement": True,
                "results": False,
            },
            "cgpa": None,
            "timetable": None,
            
        }

        # Fetch results and update the user data
        result, table = get_result_data(session)
        new_user['cgpa'] = calculate_cgpa(result)
        new_user['marks'] = mark_update(session)
        new_user['timetable'] = check_timetable(session)
        new_user['result_table'] = table
        new_user['attendance'] = get_attendance_data(session)

        # Save new user data to MongoDB
        user_collection.insert_one(new_user)
        subject = "Introducing Student Sync: Stay Updated with Real-Time College Notifications"
        body = f"""
        <html>
        <body>
            <p>Dear Student,</p>
            <p>We are thrilled to welcome you to <strong>Student Sync</strong>, your personalized Automated College Portal Notification System. With Student Sync, staying informed has never been easier. Receive timely updates on all your essential academic information directly to your email.</p>
            <p>Here’s how Student Sync can make your academic journey smoother:</p>
            <ul>
                <li><strong>Real-Time Notifications:</strong> Get instant alerts for:
                    <ul>
                        <li>Exam schedules</li>
                        <li>Timetable releases</li>
                        <li>Result announcements</li>
                        <li>Continuous Assessment (CA) scores</li>
                        <li>Attendance summaries</li>
                        <li>Seating arrangements</li>
                    </ul>
                </li>
                <p>Note: Result notifications are disabled by default. You can enable them by updating your preferences in your profile settings.</p>
                <li><strong>Automated Updates:</strong> Student Sync monitors your college portal for new updates, so you don’t have to. Stay focused on your academics while we handle the rest.</li>
                <li><strong>Customizable Preferences:</strong> Choose the notifications you care about the most. Manage your preferences effortlessly through our intuitive interface.</li>
                <li><strong>Efficient Communication:</strong> Receive accurate and timely updates, helping you stay organized and well-prepared for all academic activities.</li>
            </ul>
            <p>To start enjoying the benefits of Student Sync, ensure you’ve completed your registration and customized your preferences via your profile.</p>
            <p>We’re confident that Student Sync will enhance your academic experience by keeping you informed and connected.</p>
            <p>Best regards,<br>The Student Sync Team, PSG Tech</p>
            <p>Student Sync Web Application</p>
            <p>For any questions, reach out to us at <a href="mailto:student.sync12@gmail.com">student.sync12@gmail.com</a>.</p>
        </body>
        </html>
        """
        send_email(subject, body, f"{rollNo}@psgtech.ac.in")

        print(f"User {rollNo} registered successfully.")    

    except Exception as e:
        print(f"Error during registration: {str(e)}")
        # return jsonify({"message": "Server error. Please try again later."}), 500
        print(f"Server error. Please try again later.")

# Email setup
def send_email(subject, body, recipient):
    sender_email = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))

    if not sender_email or not password:
        print("Warning: SMTP credentials not configured in environment variables.")
        return

    msg = MIMEText(body, 'html')
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = recipient

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, password)
            server.sendmail(sender_email, recipient, msg.as_string())
    except Exception as e:
        print(f"Error sending email: {e}")


def get_result_data(session):
    try:
        result_page = session.get("https://ecampus.psgtech.ac.in/studzone2/FrmEpsStudResult.aspx")
        result_page_soup = BeautifulSoup(result_page.content, 'html.parser')

        result_table = result_page_soup.find('table', {'id': 'DgResult'})
        result_data = []
        titles = [title.text for title in result_table.find_all('tr')[0].find_all('td')]

        final_table = str(result_table)


        rows = result_table.find_all('tr')[1:]  # Skip the header row
        for row in rows:
            cells = row.find_all('td')
            row_data = [cell.text.strip() for cell in cells]
            result_data.append(dict(zip(titles, row_data)))

        return result_data, final_table
    except Exception as e:
        print(f"Error processing result data: {e}")
        return None
    
def calculate_cgpa(data):
    try:
        tot_credit = 0
        credit_grade_product = 0

        # Calculate total credits and grade-credit product
        for entry in data:
            credit = int(entry['Credit'])
            tot_credit += credit
            # Extract numeric grade using regex
            grade_match = re.search(r'\d+', entry['Grade/Remark'])
            if grade_match:
                grade = int(grade_match.group())
                credit_grade_product += credit * grade

        if tot_credit > 0:
            cgpa = credit_grade_product / tot_credit
            return cgpa
        else:
            print(f"No valid credit data for user.")
    except Exception as e:
        print(f"Error calculating CGPA for user: {e}")

    

def mark_update(session):
    try:
        # Step 4: Access the marks page
        marks_page_url = "https://ecampus.psgtech.ac.in/studzone2/CAMarks_View.aspx"
        marks_page = session.get(marks_page_url)
        marks_page.raise_for_status()

        marks_page_soup = BeautifulSoup(marks_page.content, 'html.parser')

        # Step 5: Iterate over all tables on the page
        regex_pattern = re.compile(r'^8')  # Regular expression for IDs starting with '8'
        all_tables = marks_page_soup.find_all('table', id=regex_pattern)  # Find all tables
        all_tables_html = ""  # String to store concatenated HTML for all tables

        for table in all_tables:
            # Append each table's HTML representation to the combined HTML string
            all_tables_html += str(table) + "<br>"  # Adding a line break between tables for readability

        # Step 6: Check for changes in marks
        return all_tables_html

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred for user")
    except Exception as e:
        print(f"Error processing result data for : {e}")


# Usage
data = [ 
    ('22Z369', '9655974180'),
    ('22Z370', '8098116088'),
    ('22Z371', '9820733639'),
    ('22Z372', '9952362597'),
    ('22Z373', '9842226523'),
    ('22Z374', '9500250802'),
    ('22Z375', '7005973116'),
    ('22Z377', '9842781616'),
    ('22Z378', '9840384279'),
    ('22Z379', '9842762053'),
    ('23Z461', '8754656950'),
    ('23Z463', '9626505823'),
    ('23Z464', '7708821117'),
    ('23Z465', '8220240516'),
    ('23Z466', '9443561272'),
    ('23Z467', '9843096700')
]






for rollNo, password in data:
    register(rollNo, password)
    