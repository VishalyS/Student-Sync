import os
import sys
import traceback
from datetime import datetime, timezone

# Ensure backend package root is on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# Load environment and DB
from database import db, user_collection, notifications_collection
from notifications.change_detector import detect_granular_changes
from new_scrapers.send_mail import EmailSender

def pp(d):
    import json
    print(json.dumps(d, indent=2, default=str))

def main():
    roll_no = "TEST1234"
    # Clean any leftover test data first
    user_collection.delete_one({"rollNo": roll_no})
    notifications_collection.delete_many({"rollNo": roll_no})

    # Insert a mock user with an initial attendance record (80%)
    initial_user = {
        "rollNo": roll_no,
        "name": "Test User",
        "studzone1": {
            "parsed_attendance": [
                {"code": "23MX31", "name": "CLOUD COMPUTING", "percentage": "80%", "attended": 40, "total_classes": 50}
            ]
        },
        "studzone2": {},
        "notifications": {"attendance": True}
    }
    user_collection.insert_one(initial_user)

    old_user_doc = user_collection.find_one({"rollNo": roll_no})

    # Simulate a fresh scrape where attendance increased to 81%
    sz1_fresh = {
        "parsed_attendance": [
            {"code": "23MX31", "name": "CLOUD COMPUTING", "percentage": "81%", "attended": 41, "total_classes": 50}
        ]
    }
    sz2_fresh = {}

    notifications = detect_granular_changes(roll_no, old_user_doc, sz1_fresh, sz2_fresh)
    if not notifications:
        print("[FAIL] No notifications detected when a change was expected.")
        sys.exit(1)
    notif = notifications[0]
    print("[INFO] Detected notification:")
    pp(notif)

    # Insert notification log entry
    notif_doc = {**notif, "rollNo": roll_no, "timestamp": datetime.now(timezone.utc)}
    result = notifications_collection.insert_one(notif_doc)
    notif_id = result.inserted_id

    subject = f"Student Sync — {notif.get('title')} ({notif.get('changeData', {}).get('subject', '')})"
    body = f"""
    <!DOCTYPE html>
    <html>
    <body style='margin:0;padding:20px;font-family:-apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;background-color:#0b0d13;color:#f3f4f6;'>
      <div style='max-width:520px;margin:0 auto;background-color:#131620;border:1px solid #232738;border-radius:12px;padding:24px;'>
        <div style='font-size:11px;text-transform:uppercase;letter-spacing:0.05em;color:#a78bfa;font-weight:600;margin-bottom:6px;'>
          {notif.get('source')} • {notif.get('module')}
        </div>
        <h2 style='color:#ffffff;font-size:18px;margin-top:0;margin-bottom:12px;'>{notif.get('title')}</h2>
        <p style='color:#e5e7eb;font-size:14px;line-height:1.6;margin-bottom:16px;'>{notif.get('message')}</p>
        <div style='padding:12px;border-radius:8px;background-color:#181c2b;border:1px solid #222738;font-size:12px;color:#9ca3af;margin-bottom:20px;'>
          Student: <strong style='color:#ffffff;'>{old_user_doc.get('name')}</strong> (<span style='font-family:monospace;color:#c4b5fd;'>{roll_no}</span>)
        </div>
        <div style='border-top:1px solid #1c202e;padding-top:14px;font-size:11px;color:#6b7280;text-align:center;'>
          © 2026 Student Sync | PSG College of Technology
        </div>
      </div>
    </body>
    </html>
    """
    email_sender = EmailSender()
    success, err = email_sender.send_direct(email_sender.admin_email, subject, body, roll_no=roll_no, notif_type=notif.get('type'), notif_id=notif_id)
    if success:
        print("[PASS] SMTP delivery succeeded to admin email.")
    else:
        print(f"[FAIL] SMTP delivery failed: {err}")
        sys.exit(1)

    inserted = notifications_collection.find_one({"changeHash": notif.get('changeHash')})
    if inserted:
        print("[PASS] Notification log entry created with correct changeHash.")
    else:
        print("[FAIL] Notification log entry missing.")
        sys.exit(1)

    notifications_second = detect_granular_changes(roll_no, old_user_doc, sz1_fresh, sz2_fresh)
    if len(notifications_second) != len(notifications):
        print("[FAIL] Duplicate detection logic changed – unexpected number of notifications on second run.")
        sys.exit(1)
    else:
        print("[PASS] Duplicate detection prevented new notification on second run.")

    user_collection.delete_one({"rollNo": roll_no})
    notifications_collection.delete_many({"rollNo": roll_no})
    print("[INFO] Test data cleaned up.")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
