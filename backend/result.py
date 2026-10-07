from database import user_collection
from scrapers.login import login
from scrapers.get_result_data import get_result_data
from scrapers.calculate_cgpa import calculate_cgpa
from pymongo.errors import NetworkTimeout, ConnectionFailure, AutoReconnect
import re, time

def process_users():
    try:
        batch_size = 100  # Define the size of each batch
        total_users = user_collection.count_documents({})  # Get the total number of users
        batch_num = 0
        retry_users = []  # List to store users that need to be retried

        # Process all users in batches
        while batch_num * batch_size < total_users:
            # Fetch the next batch of users
            users = user_collection.find({}).skip(batch_num * batch_size).limit(batch_size)

            for user in users:
                # Exclude roll numbers matching 22_anyletter_2, 22_anyletter_3, or 23_anyletter_4
                roll_no = user.get('rollNo', '')
                if isinstance(user.get('notifications'), dict):
                    try:
                        # Get the session from login
                        session_result = login(user)
                        
                        # Check if login was successful (session is not a tuple)
                        if isinstance(session_result, tuple):
                            print(f"Login failed for {user['rollNo']}: {session_result[1]}")
                            retry_users.append(user)  # Add to retry list
                            continue
                        
                        # If we got a valid session, proceed with scraping
                        session = session_result
                        
                        if user['notifications'].get('results', False):
                            if 'name' not in user:
                                user_collection.update_one({'_id': user['_id']}, {'$set': {'name': user['rollNo']}})
                            result_data, table = get_result_data(session)
                            calculate_cgpa(result_data, user, table)
                            
                    except Exception as e:
                        print(f"Error processing user {user.get('rollNo', 'unknown')}: {str(e)}")
                        retry_users.append(user)  # Add to retry list if any exception occurred
                        
            batch_num += 1

        # Process retry users after completing a full round
        if retry_users:
            print(f"\n=== Retrying {len(retry_users)} failed users ===\n")
            for user in retry_users:
                try:
                    print(f"Retrying user: {user['rollNo']}")
                    session_result = login(user)
                    
                    if isinstance(session_result, tuple):
                        print(f"Retry failed for {user['rollNo']}: {session_result[1]}")
                        continue
                        
                    session = session_result
                    
                    if user['notifications'].get('results', False):
                        if 'name' not in user:
                            user_collection.update_one({'_id': user['_id']}, {'$set': {'name': user['rollNo']}})
                        result_data, table = get_result_data(session)
                        calculate_cgpa(result_data, user, table)
                    print(f"Successfully processed {user['rollNo']} on retry")
                except Exception as e:
                    print(f"Error processing user {user.get('rollNo', 'unknown')} on retry: {str(e)}")
        
        return True  # Successfully completed processing
    except (NetworkTimeout, ConnectionFailure, AutoReconnect) as e:
        print(f"MongoDB connection error: {str(e)}")
        return False  # Signal that we need to retry due to connection issue

# Main loop with continuous retry
while True:
    try:
        print("Starting user processing cycle...")
        success = process_users()
        
        if success:
            print("Processing cycle completed successfully.")
            break  # Exit the loop if processing was successful
        else:
            # If there was a connection error, wait and retry
            print("MongoDB connection failed. Retrying in 30 seconds...")
            time.sleep(30)
    except Exception as e:
        print(f"Unexpected error occurred: {str(e)}")
        print("Retrying in 60 seconds...")
        time.sleep(60)