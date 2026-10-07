from bs4 import BeautifulSoup
from database import user_collection, sub_collection
from new_scrapers.send_mail import send_email
import copy

def get_ca_marks(session, user):
    try:
        response = session.get("https://ecampus.psgtech.ac.in/StudZone/ContinuousAssessment/CAMarksView", verify=False)
        ca_marks_soup = BeautifulSoup(response.content, "html.parser")

        # Check if we're redirected to login page (indicates session expired or login failed)
        if "login" in response.url.lower() or ca_marks_soup.find("form", {"class": "form__content"}):
            print(f"Redirected to login page for {user['name']} - session may have expired")
            return

        # Retrieve all tables with the specified class
        marks_tables = ca_marks_soup.find_all('table', class_="table table-bordered table-striped")

        if not marks_tables:
            print(f"No data found in the marks tables for {user['name']}")
            return

        all_tables_html = ""

        # Process each table
        for table in marks_tables:
            rows = table.find_all('tr')

            for row in rows:
                cells = row.find_all(['th', 'td'])

                for cell in cells:
                    cell['style'] = 'border: 1px solid black; padding: 8px;'
                
                if row.find('th'):  # Style headers
                    for header_cell in row.find_all('th'):
                        header_cell['style'] += ' background-color: #ccd6e6; color: #013281;'

                # Extract subject code & name (only from data rows)
                if len(cells) >= 2:  # Ensure at least two columns exist
                    subject_code = cells[0].text.strip()
                    subject_name = cells[1].text.strip()

                    # Store subject in database if not exists
                    if not sub_collection.find_one({'subject_code': subject_code}):
                        sub_collection.insert_one({'subject_code': subject_code, 'subject_name': subject_name})
                        print(f"Added subject: {subject_code} - {subject_name}")

            all_tables_html += str(table)  # Append the modified table HTML

        # Wrap the entire HTML with table styling
        styled_tables_soup = BeautifulSoup(all_tables_html, "html.parser")
        styled_tables_soup['style'] = 'border-collapse: collapse; width: 100%;'
        table_html = str(styled_tables_soup)

        # Fetch stored marks from the user document
        stored_marks_html = user.get('marks', '')

        if not stored_marks_html:
            # If no marks are stored, save the combined HTML
            user_collection.update_one(
                {'rollNo': user['rollNo']},
                {
                    '$set': {
                        'marks': table_html,  # Store the combined HTML content
                    }
                }
            )
            print(f"Stored marks for {user['name']}.")
            return

        if stored_marks_html != table_html:
            # Create a highlighted version of the HTML for email and get changed subjects
            highlighted_table_html, changed_details = highlight_changes(stored_marks_html, table_html)
            
            # Update MongoDB with new HTML data (without highlighting)
            user_collection.update_one(
                {'rollNo': user['rollNo']},
                {
                    '$set': {
                        'marks': table_html,  # Store the original HTML content for future comparisons
                    }
                }
            )
            
            roll = user['rollNo'].lower()  # Ensure the roll number is valid
            recipient_email = roll + "@psgtech.ac.in"
            
            # Create a message about changed subjects
            subjects_message = ""
            if changed_details:
                if len(changed_details) == 1:
                    subjects_message = "<p>The following subject has updated marks:</p>"
                else:
                    subjects_message = "<p>The following subjects have updated marks:</p>"
                subjects_message += generate_html_table(changed_details)
            
            header = ""
            if len(changed_details) == 1:
                header = f"Mark Update Notification - {len(changed_details)} marks updated"
                result = send_email(
                recipient_email,
                header,
                f"""
                <html>
                    <body>
                        <p>Dear {user['name']},</p>
                        <p>We wish to inform you that your marks have been updated.</p>
                        {subjects_message}
                        <p>Details below (changes highlighted in yellow):</p>
                        {highlighted_table_html}
                        <p>Please log in to the eCampus portal to review the changes in detail.</p>
                        <p>If you need any assistance, feel free to reach out to us for support.</p>
                        <p>Best regards,</p>
                        <p>Student Sync Team</p>
                    </body>
                </html>
                """
                )
                print(f"Updated marks and email queued for {user['name']}: {result}")
            elif len(changed_details) > 1:
                header = f"Mark Update Notification - {len(changed_details)} marks updated"
            
                result = send_email(
                    recipient_email,
                    header,
                    f"""
                    <html>
                        <body>
                            <p>Dear {user['name']},</p>
                            <p>We wish to inform you that your marks have been updated.</p>
                            {subjects_message}
                            <p>Details below (changes highlighted in yellow):</p>
                            {highlighted_table_html}
                            <p>Please log in to the eCampus portal to review the changes in detail.</p>
                            <p>If you need any assistance, feel free to reach out to us for support.</p>
                            <p>Best regards,</p>
                            <p>Student Sync Team</p>
                        </body>
                    </html>
                    """
                )
                print(f"Updated marks and email queued for {user['name']}: {result}")
            else:
                print(f"Marks pending for {user['name']}.")
        else:
            print(f"No new marks for {user['name']}.")

    except Exception as e:
        print(f"Error: {e}")
        return

def generate_html_table(changed_details):
    """
    Generate an HTML table from the changed details, with centered values.
    """
    table_html = """
    <table border="1" style="border-collapse: collapse; width: 100%; text-align: center;">
        <thead>
            <tr style="background-color: #ccd6e6; color: #013281;">
                <th style="padding: 8px; text-align: center;">Subject Code</th>
                <th style="padding: 8px; text-align: center;">Subject Title</th>
                <th style="padding: 8px; text-align: center;">Test Name</th>
                <th style="padding: 8px; text-align: center;">Old Mark</th>
                <th style="padding: 8px; text-align: center;">New Mark</th>
            </tr>
        </thead>
        <tbody>
    """
    for detail in changed_details:
        table_html += f"""
            <tr>
                <td style="padding: 8px; text-align: center;">{detail['subject_code']}</td>
                <td style="padding: 8px; text-align: center;">{detail['subject_title']}</td>
                <td style="padding: 8px; text-align: center;">{detail['test_name']}</td>
                <td style="padding: 8px; text-align: center;">{detail['old_mark']}</td>
                <td style="padding: 8px; text-align: center;">{detail['new_mark']}</td>
            </tr>
        """
    table_html += """
        </tbody>
    </table>
    """
    return table_html


def highlight_changes(old_html, new_html):
    """
    Compare old and new HTML tables, highlighting changed values.
    Also returns a structured list of changed subjects with test details.
    """
    old_soup = BeautifulSoup(old_html, "html.parser")
    new_soup = BeautifulSoup(new_html, "html.parser")
    
    # Create a deep copy of the new soup for highlighting
    highlighted_soup = BeautifulSoup(new_html, "html.parser")
    
    # Get all tables from both soups
    old_tables = old_soup.find_all('table')
    new_tables = new_soup.find_all('table')
    highlighted_tables = highlighted_soup.find_all('table')
    
    changed_details = []  # List to store changes in subjects and test marks
    
    # Process each table
    for table_index, (old_table, new_table, highlighted_table) in enumerate(zip(old_tables, new_tables, highlighted_tables)):
        # Get all rows from both tables
        old_rows = old_table.find_all('tr')
        new_rows = new_table.find_all('tr')
        highlighted_rows = highlighted_table.find_all('tr')

        if not new_rows or not old_rows or not highlighted_rows:
            continue

        # Extract test names from the header row (2nd row usually contains CA1, CA2, Mid-Sem, etc.)
        header_cells = new_rows[0].find_all(['th', 'td'])
        test_names = [cell.text.strip() for cell in header_cells]  # Store test names
        
        # Process each row (excluding the header row)
        for row_index in range(1, min(len(old_rows), len(new_rows), len(highlighted_rows))):
            old_cells = old_rows[row_index].find_all(['td', 'th'])
            new_cells = new_rows[row_index].find_all(['td', 'th'])
            highlighted_cells = highlighted_rows[row_index].find_all(['td', 'th'])

            if len(new_cells) < 2 or len(old_cells) < 2 or len(highlighted_cells) < 2:
                continue
            
            subject_code = new_cells[0].text.strip()  # First column is subject code
            subject_title = new_cells[1].text.strip()  # Second column is subject name
            
            for cell_index in range(2, min(len(new_cells), len(old_cells), len(highlighted_cells))):  # Start from the 3rd column (marks start here)
                old_value = old_cells[cell_index].text.strip()
                new_value = new_cells[cell_index].text.strip()
                
                if old_value != new_value and new_value != "Pending" and "Max" not in new_value:
                    # Highlight the changed cell
                    highlighted_cells[cell_index]['style'] = "background-color: #FFFF00; text-align: center;"
                    
                    # Find the test name corresponding to this column
                    test_name = test_names[cell_index] if cell_index < len(test_names) else f"Test {cell_index - 1}"
                    
                    # Ignore updates for total test names
                    if "total" in test_name.lower():
                        continue
                    # Store detailed change information
                    changed_details.append({
                        "subject_code": subject_code,
                        "subject_title": subject_title,
                        "test_name": test_name,
                        "old_mark": old_value,
                        "new_mark": new_value
                    })
    
    return str(highlighted_soup), changed_details
