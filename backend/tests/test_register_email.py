import os
import sys
import traceback
from datetime import datetime, timezone
from unittest.mock import patch

# Ensure backend directory and project root are on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from pyserver import app, notifications_collection, users_collection

def pretty_print(obj):
    import json
    print(json.dumps(obj, indent=2, default=str))

def main():
    test_roll = "TESTREG123"
    test_password = "dummy"

    # Clean any existing test data
    if users_collection is not None:
        users_collection.delete_one({"rollNo": test_roll})
    if notifications_collection is not None:
        notifications_collection.delete_many({"rollNo": test_roll})

    # Mock sync_student_dual_portal to return a minimal user document without real scraping
    mock_user = {
        "rollNo": test_roll,
        "name": "Test Student",
        "studzone1": {},
        "studzone2": {},
        "cgpa": "N/A"
    }

    with patch('pyserver.sync_student_dual_portal', return_value=(mock_user, None)),\
        patch('backend.new_scrapers.send_mail._email_sender._send_email_attempt', return_value=(True, "")):
        client = app.test_client()
        response = client.post('/register', json={"rollNo": test_roll, "password": test_password})
        print(f"[TEST] /register response status: {response.status_code}")
        print(f"[TEST] Response JSON: {response.get_json()}")

    # Verify notification logs
    if notifications_collection is not None:
        notifs = list(notifications_collection.find({"rollNo": test_roll}))
        print(f"[TEST] Notification records count: {len(notifs)}")
        for n in notifs:
            pretty_print(n)
        sent = [n for n in notifs if n.get('status') == 'sent']
        if len(sent) == 2:
            print("[PASS] Both welcome and admin notifications logged as 'sent'.")
        else:
            print(f"[FAIL] Expected 2 sent notifications, got {len(sent)}.")

    # Cleanup
    if users_collection is not None:
        users_collection.delete_one({"rollNo": test_roll})
    if notifications_collection is not None:
        notifications_collection.delete_many({"rollNo": test_roll})
    print("[INFO] Cleaned up test data.")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
