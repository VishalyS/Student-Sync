import requests
from bs4 import BeautifulSoup
from database import user_collection, sub_collection
from new_scrapers.send_mail import send_email

def get_attendance(session, user):
    try:
        # Fetch attendance page
        response = session.get("https://ecampus.psgtech.ac.in/StudZone/Attendance/StudentPercentage", verify=False)
        attendance_soup = BeautifulSoup(response.content, "html.parser")
        
        # Check if we're redirected to login page (indicates session expired or login failed)
        if "login" in response.url.lower() or attendance_soup.find("form", {"class": "form__content"}):
            print(f"Redirected to login page for {user['name']} - session may have expired")
            return
        
        # Extract the attendance table
        attendance_table = attendance_soup.find('table', id="example")
        if not attendance_table:
            print(f"Attendance table not found for {user['name']}")
            return
            
        if len(attendance_table.find_all('td')) == 0:
            print(f"No data found in the attendance table for {user['name']}")
            return
        if attendance_table:
            table_html = str(attendance_table)  # Store raw HTML before modification

            # Fetch the user's previous attendance table from MongoDB
            user_data = user_collection.find_one({'rollNo': user['rollNo']})
            previous_attendance = user_data.get('attendance_table', None) if user_data else None

            # Proceed only if attendance has changed
            if previous_attendance != table_html:
                # Store only the original table in MongoDB
                user_collection.update_one(
                    {'rollNo': user['rollNo']},
                    {'$set': {'attendance_table': table_html}}
                )

                # **Modify table only for email**
                modified_table = attendance_table

                if len(modified_table.find_all('td')) == 0:
                    print(f"No data found in the attendance table for {user['name']}")
                    return

                # Find the header row and modify it to remove "Unknown" and add "Course Name" correctly
                header_row = modified_table.find('tr')
                if header_row:
                    # Remove any "Unknown" header if it exists
                    for th in header_row.find_all('th'):
                        if th.text.strip() == "Unknown":
                            th.decompose()
                    
                    # Add Course Name header after Course Code
                    headers = header_row.find_all('th')
                    course_code_index = 0  # Assuming Course Code is the first column
                    course_name_header = BeautifulSoup("<th>Course Name</th>", "html.parser").th
                    headers[course_code_index].insert_after(course_name_header)
                    
                    # Add Bunk Count header at the end with light red background and red text
                    bunk_count_header = BeautifulSoup("<th>Bunk Count(85%)</th>", "html.parser").th
                    bunk_count_header['style'] = 'border: 1px solid black; padding: 8px; background-color: #ffcccc; color: #cc0000; font-weight: bold;'
                    header_row.append(bunk_count_header)

                # Function to get color based on attendance percentage
                def get_attendance_color(percentage_text):
                    try:
                        # Extract percentage value from text (remove % symbol if present)
                        percentage = float(percentage_text.replace('%', '').strip())
                        if percentage < 85:
                            return {'color': '#cc0000', 'background': '#ffcccc'}  # Red text, light red background
                        elif percentage < 90:
                            return {'color': '#cc6600', 'background': '#fff2cc'}  # Orange text, light yellow background
                        else:
                            return {'color': '#006600', 'background': '#ccffcc'}  # Green text, light green background
                    except (ValueError, AttributeError):
                        return {'color': '#000000', 'background': '#ffffff'}  # Default black text, white background

                # Function to calculate bunk count (classes can miss while maintaining 75% attendance)
                def calculate_bunk_count(total_hours, present_hours):
                    try:
                        total_hours = int(total_hours)
                        present_hours = int(present_hours)
                        
                        # Calculate maximum classes that can be bunked while maintaining 75% attendance
                        # Formula: present_hours / (total_hours + future_classes) >= 0.75
                        # Rearranging: future_classes <= (present_hours / 0.75) - total_hours
                        max_total_for_75_percent = present_hours / 0.85
                        bunk_count = int(max_total_for_75_percent - total_hours)
                        
                        # If already below 75%, bunk count is 0
                        current_percentage = (present_hours / total_hours) * 100 if total_hours > 0 else 0
                        if current_percentage < 75:
                            return 0
                        
                        return max(0, bunk_count)  # Ensure non-negative
                    except (ValueError, ZeroDivisionError):
                        return 0

                # Modify the table rows and apply styling
                rows = modified_table.find_all('tr')
                for row_index, row in enumerate(rows):
                    # Remove any "Unknown" cell if it exists
                    # for cell in row.find_all('td'):
                    #     if cell.text.strip() == "Unknown":
                    #         cell.decompose()
                    
                    cells = row.find_all(['th', 'td'])

                    # Apply cell styling
                    for cell in cells:
                        cell['style'] = 'border: 1px solid black; padding: 8px;'

                    # Style header row
                    if row.find('th'):
                        for header_cell in row.find_all('th'):
                            header_cell['style'] += ' background-color: #ccd6e6; color: #013281;'

                    # Modify the subject code column to include course name, skipping header row
                    if len(cells) > 1 and cells[0].name == 'td':  # Make sure it's not a header cell
                        subject_code = cells[0].text.strip()
                        subject_data = sub_collection.find_one({'subject_code': subject_code})

                        if subject_data:
                            subject_name = subject_data['subject_name']
                        else:
                            subject_name = "Unknown"

                        # Insert the course name cell right after the course code
                        course_name_cell = BeautifulSoup(f"<td>{subject_name}</td>", "html.parser").td
                        course_name_cell['style'] = 'border: 1px solid black; padding: 8px;'  # Apply styling
                        cells[0].insert_after(course_name_cell)

                        # Calculate and add bunk count
                        # Extract total hours and present hours from the cells
                        # Assuming the structure: Course Code, Course Name, Total hr, Exemp hr, Tot Absent, Total Present, ...
                        try:
                            updated_cells = row.find_all(['th', 'td'])  # Get updated cell list after adding course name
                            if len(updated_cells) >= 6:  # Ensure we have enough cells
                                total_hours = updated_cells[2].text.strip()  # Total hr column
                                present_hours = updated_cells[5].text.strip()  # Total Present column
                                
                                bunk_count = calculate_bunk_count(total_hours, present_hours)
                                
                                # Create bunk count cell with appropriate styling
                                bunk_count_cell = BeautifulSoup(f"<td>{bunk_count}</td>", "html.parser").td
                                bunk_count_cell['style'] = 'border: 1px solid black; padding: 8px;'
                                
                                # Color code based on bunk count
                                if bunk_count == 0:
                                    bunk_count_cell['style'] += ' color: #ff4444; font-weight: bold;'  # Red for no bunks
                                elif bunk_count <= 2:
                                    bunk_count_cell['style'] += ' color: #ffaa00; font-weight: bold;'  # Yellow for low bunks
                                else:
                                    bunk_count_cell['style'] += ' color: #00aa44; font-weight: bold;'  # Green for safe bunks
                                
                                # Add the bunk count cell at the end of the row
                                row.append(bunk_count_cell)
                        except (IndexError, ValueError) as e:
                            # If there's an error calculating bunk count, add a default cell
                            bunk_count_cell = BeautifulSoup("<td>-</td>", "html.parser").td
                            bunk_count_cell['style'] = 'border: 1px solid black; padding: 8px;'
                            row.append(bunk_count_cell)

                        # Apply color coding only to specific percentage columns
                        # First, get the header row to identify column positions
                        header_row = modified_table.find('tr')
                        percentage_column_indices = []
                        
                        if header_row:
                            headers = header_row.find_all('th')
                            for idx, header in enumerate(headers):
                                header_text = header.text.strip()
                                # Only apply color to these specific percentage columns
                                if header_text in ['(%) Attendance', '(%) Exemp', '(%) Exemp - MED']:
                                    percentage_column_indices.append(idx)
                        
                        # Apply color coding only to cells in the identified percentage columns
                        updated_cells = row.find_all(['th', 'td'])
                        for cell_index, cell in enumerate(updated_cells):
                            if cell_index in percentage_column_indices:
                                cell_text = cell.text.strip()
                                # Apply color coding to the percentage value
                                if cell_text and cell_text != '0':  # Don't color empty or zero values
                                    color_info = get_attendance_color(cell_text)
                                    cell['style'] += f' color: {color_info["color"]}; background-color: {color_info["background"]}; font-weight: bold;'

                # Extract modified table HTML for email
                updated_table_html = str(modified_table)

                # Prepare and send an email notification
                subject = "Attendance Update Notification"
                body = f"""
                <html>
                    <body>
                        <p>Dear {user['name']},</p>
                        <p>Please note that your attendance data has been updated. The latest details are provided below:</p>

                        {updated_table_html}

                        <p>Kindly review the updated attendance on the portal.</p>
                        <p>You can modify your notification preferences in the Student Sync web application.<br>
                        Student Sync Web Application</p>

                        <p>Best regards,</p>
                        <p>Student Sync Team</p>
                    </body>
                </html>
                """
                recipient_email = f"{user['rollNo'].lower()}@psgtech.ac.in"
                result = send_email(recipient_email, subject, body)
                print(f"Attendance update email queued for {user['name']}: {result}")
            else:
                print(f"No change in attendance for {user['rollNo']}")
        else:
            print(f"Attendance Table Not Found for {user['name']}")
    except requests.RequestException as e:
        print(f"Error fetching the attendance data: {e}")
    except Exception as e:
        print(f"Error processing attendance data: {e}")