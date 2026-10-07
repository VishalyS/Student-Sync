import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
from pymongo.errors import NetworkTimeout, ConnectionFailure, AutoReconnect
import re
import time
import urllib3
import smtplib
from email.mime.text import MIMEText
import certifi
from flask import Flask, jsonify
from threading import Thread
import datetime
import pytz

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Get IST timezone
ist = pytz.timezone('Asia/Kolkata')

def get_formatted_time():
    current_time = datetime.datetime.now(ist)
    return current_time.strftime("%I:%M:%S %p IST (%d-%m-%Y)")

# Status tracking
status_data = {
    "last_run": None,
    "last_success": None,
    "last_error": None,
    "processed_users": 0,
    "retry_users": 0
}

# Flask app
app = Flask(__name__)

@app.route('/status')
def status():
    return jsonify(status_data)

def run_status_server():
    app.run(host="0.0.0.0", port=8080)

import os
from dotenv import load_dotenv

load_dotenv()

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(
    MONGO_URI,
    connectTimeoutMS=30000,
    socketTimeoutMS=30000,
    tlsCAFile=certifi.where()
) if MONGO_URI else None
db = client['ecampus'] if client else None
user_collection = db['new_users'] if db is not None else None

# Email function
def send_email(recipient_email, subject, body):
    sender_email = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))

    if not sender_email or not password:
        return "Email error: SMTP credentials not configured in environment variables."

    msg = MIMEText(body, 'html')
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = recipient_email

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
            return f"Email sent to {recipient_email}"
    except Exception as e:
        return f"Email error: {e}"

# Login
def login(user):
    session = requests.Session()
    login_url = 'https://ecampus.psgtech.ac.in/studzone2/'

    try:
        response = session.get(login_url, verify=False)
        soup = BeautifulSoup(response.content, 'html.parser')
        viewstate = soup.find('input', {'name': '__VIEWSTATE'})['value']
        viewstate_generator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})['value']
        event_validation = soup.find('input', {'name': '__EVENTVALIDATION'})['value']

        parent_radio_data = {
            '__VIEWSTATE': viewstate,
            '__VIEWSTATEGENERATOR': viewstate_generator,
            '__EVENTVALIDATION': event_validation,
            'rdolst': 'P',
            '__EVENTTARGET': 'rdolst$3',
            '__EVENTARGUMENT': ''
        }

        post_response = session.post(login_url, data=parent_radio_data, verify=False)
        if 'Parent' not in post_response.text:
            raise ValueError("Parent login page load failed")

        soup = BeautifulSoup(post_response.content, 'html.parser')
        viewstate = soup.find('input', {'name': '__VIEWSTATE'})['value']
        viewstate_generator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})['value']
        event_validation = soup.find('input', {'name': '__EVENTVALIDATION'})['value']

        login_data = {
            '__VIEWSTATE': viewstate,
            '__VIEWSTATEGENERATOR': viewstate_generator,
            '__EVENTVALIDATION': event_validation,
            'txtusercheck': user['rollNo'],
            'txtpwdcheck': user['password'],
            'abcd3': 'Login'
        }

        response = session.post(login_url, data=login_data, verify=False)
        attendance_page_response = session.get("https://ecampus.psgtech.ac.in/studzone2/AttWfPercView.aspx", verify=False)
        if 'ASP.NET Ajax client-side framework failed to load.' in attendance_page_response.text:
            return None
        else:
            return session
    except Exception as e:
        return f"Login error: {e}"

# Get result
def get_result_data(session):
    try:
        result_page = session.get("https://ecampus.psgtech.ac.in/studzone2/FrmEpsStudResult.aspx", verify=False)
        soup = BeautifulSoup(result_page.content, 'html.parser')
        result_table = soup.find('table', {'id': 'DgResult'})
        titles = [title.text for title in result_table.find_all('tr')[0].find_all('td')]
        rows = result_table.find_all('tr')[1:]

        data = []
        for row in rows:
            cells = row.find_all('td')
            row_data = [cell.text.strip() for cell in cells]
            data.append(dict(zip(titles, row_data)))

        return data, str(result_table)
    except Exception as e:
        print(f"Result error: {e}")
        return None, None

# CGPA
def calculate_cgpa(data, user, table):
    try:
        if not data:
            print(f"No data for {user['rollNo']}")
            return

        tot_credit = 0
        grade_sum = 0
        for entry in data:
            credit = int(entry['Credit'])
            grade_match = re.search(r'\d+', entry['Grade/Remark'])
            if grade_match:
                grade = int(grade_match.group())
                tot_credit += credit
                grade_sum += credit * grade

        if tot_credit > 0:
            cgpa = grade_sum / tot_credit
            prev_table = user.get('result_table', None)
            if prev_table != table:
                user_collection.update_one({'rollNo': user['rollNo']}, {'$set': {'cgpa': cgpa, 'result_table': table}})
                email = user['rollNo'].lower() + "@psgtech.ac.in"
                send_email(
                    email,
                    "Results Published!!!!",
                    f"""
                    <html>
                        <body>
                            <p>Dear {user['name']},</p>
                            <p>Your results are published:</p>
                            {table}
                            <p>CGPA: <strong>{cgpa}</strong></p>
                            <p>Regards,<br>Student Sync Team</p>
                        </body>
                    </html>
                    """
                )
            else:
                print(f"No CGPA change for {user['rollNo']}")
    except Exception as e:
        print(f"CGPA error for {user['rollNo']}: {e}")

# Process users
def process_users():
    try:
        batch_size = 100
        total_users = user_collection.count_documents({})
        batch_num = 0
        retry_users = []

        status_data["processed_users"] = 0
        status_data["retry_users"] = 0

        while batch_num * batch_size < total_users:
            users = user_collection.find({}).skip(batch_num * batch_size).limit(batch_size)
            for user in users:
                roll = user.get('rollNo', '')
                exclude_pattern = r"^(?!.*(23.[123])).*$"
                if isinstance(user.get('notifications'), dict) and re.match(exclude_pattern, roll):
                    try:
                        session = login(user)
                        if isinstance(session, str):
                            print(session)
                            retry_users.append(user)
                            continue
                        if user['notifications'].get('results', False):
                            if 'name' not in user:
                                user_collection.update_one({'_id': user['_id']}, {'$set': {'name': user['rollNo']}})
                            result_data, table = get_result_data(session)
                            calculate_cgpa(result_data, user, table)
                            status_data["processed_users"] += 1
                    except Exception as e:
                        print(f"Error: {e}")
                        retry_users.append(user)
            batch_num += 1

        status_data["retry_users"] = len(retry_users)

        # Retry
        for user in retry_users:
            try:
                session = login(user)
                if isinstance(session, str):
                    print(session)
                    continue
                if user['notifications'].get('results', False):
                    result_data, table = get_result_data(session)
                    calculate_cgpa(result_data, user, table)
            except Exception as e:
                print(f"Retry error for {user['rollNo']}: {e}")

        return True
    except (NetworkTimeout, ConnectionFailure, AutoReconnect) as e:
        print(f"Mongo error: {e}")
        return False

# MAIN LOOP
if __name__ == "__main__":
    Thread(target=run_status_server, daemon=True).start()

    while True:
        try:
            print(f"Starting cycle at {get_formatted_time()}...")
            status_data["last_run"] = get_formatted_time()
            success = process_users()
            if success:
                status_data["last_success"] = get_formatted_time()
                print(f"Cycle completed at {get_formatted_time()}")
            else:
                status_data["last_error"] = "MongoDB error"
                print(f"MongoDB error at {get_formatted_time()}. Retrying in 30s...")
                time.sleep(30)
        except Exception as e:
            status_data["last_error"] = str(e)
            print(f"Main error at {get_formatted_time()}: {e}")
            print("Retrying in 60s...")
            time.sleep(60)
 