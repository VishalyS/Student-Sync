import requests
from bs4 import BeautifulSoup
from scrapers.send_mail import send_email
from database import user_collection

def get_attendance_data(session, user):
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

        # Retrieve the previous attendance table from MongoDB
        previous_attendance = user_collection.find_one({'rollNo': user['rollNo']}).get('attendance_table')

        # Compare the current attendance with the previous one
        if previous_attendance != html_table:
            # Update the user's attendance table in MongoDB
            user_collection.update_one(
                {'rollNo': user['rollNo']},
                {'$set': {'attendance_table': html_table}}
            )

            # Send an email notifying that attendance has been updated
            subject = "Attendance Update Notification"
            body = f"""
            <html>
                <body>
                    <p>Dear {user['name']},</p>

                    <p>We hope this email finds you well.</p>

                    <p>Please note that your attendance data has been updated. The latest details are provided below:</p>

                    {html_table}

                    <p>Kindly review the updated attendance on the portal.</p>
                    <p>You can modify your notification preferences in the Student Sync web application.<br>
                    Student Sync Web Application</p>

                    <p>Best regards,</p>
                    <p>Student Sync Team</p>
                </body>
            </html>
            """
            recipient_email = user['rollNo'] + "@psgtech.ac.in"
            recipient_email = recipient_email.lower()  # Ensure the email is in lowercase

            send_email(recipient_email, subject, body)
            print(f"Attendance update email sent to {user['rollNo']}")
        else:
            print(f"No change in attendance for {user['rollNo']}")

        return

    except requests.RequestException as e:
        print(f"Error fetching the attendance data: {e}")
        return None

    except Exception as e:
        print(f"Error processing attendance data: {e}")
        return None
