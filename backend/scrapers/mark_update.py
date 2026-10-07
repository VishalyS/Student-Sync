import re
from database import user_collection
from scrapers.send_mail import send_email
from bs4 import BeautifulSoup
import requests

def mark_update(session, user):
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
        stored_marks_html = user.get('marks', '')  # Get stored HTML, default to empty if not found

        if stored_marks_html != all_tables_html:
            # If marks are different, update MongoDB with new HTML data
            user_collection.update_one(
                {'rollNo': user['rollNo']},
                {
                    '$set': {
                        'marks': all_tables_html,  # Store the HTML content for future comparisons
                    }
                }
            )
            print(f"Updated marks for {user['rollNo']}.")
            roll = user['rollNo'].lower()  # Ensure the roll number is valid
            name = user['name']
            recipient_email = roll + "@psgtech.ac.in"
            send_email(
                recipient_email,
                "Marks Update Notification",
                f"""
                <html>
                    <body>
                        <p>Dear {user['name']},</p>
                        <p>We wish to inform you that your marks have been updated. Please see the details below:</p>
                        {all_tables_html} 
                        <p>Please log in to the eCampus portal to review the changes in detail.</p>
                        <p>If you need any assistance, feel free to reach out to us for support.</p>
                        <p>Best regards,</p>
                        <p>Student Sync Team</p>
                    </body>
                </html>
                """
            )
        else:
            print(f"No new marks for {user['name']}.")                    

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred for user {user['name']}: {http_err}")
    except Exception as e:
        print(f"Error processing result data for {user['name']}: {e}")