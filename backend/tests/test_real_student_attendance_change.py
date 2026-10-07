import os
import sys
import traceback
from datetime import datetime, timezone

# Ensure repo root is on sys.path for imports
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# Import DB collections and change detection
from database import user_collection, notifications_collection
from notifications.change_detector import detect_granular_changes
from new_scrapers.send_mail import EmailSender

def pretty_print(obj):
    import json
    print(json.dumps(obj, indent=2, default=str))

def main():
    roll_no = "25MX232"

    # 1. Fetch existing student record
    user_doc = user_collection.find_one({"rollNo": roll_no})
    if not user_doc:
        print(f"[FAIL] No student found with rollNo {roll_no}")
        sys.exit(1)

    # 2. Locate CLOUD COMPUTING attendance entry
    old_att = user_doc.get('studzone1', {}).get('parsed_attendance') or []
    cloud = None
    for entry in old_att:
        if entry.get('code') == "23MX31" or entry.get('name', '').upper() == "CLOUD COMPUTING":
            cloud = entry
            break
    if not cloud:
        print("[FAIL] CLOUD COMPUTING entry not found in stored attendance.")
        sys.exit(1)
    old_pct = str(cloud.get('percentage')).strip()
    print(f"[INFO] Old attendance value retrieved: {old_pct}")

    # 3. Simulate fresh scrape with attendance 65%
    sz1_fresh = {
        "parsed_attendance": [
            {
                "code": cloud.get('code'),
                "name": cloud.get('name'),
                "percentage": "65%",
                "attended": cloud.get('attended'),
                "total_classes": cloud.get('total_classes')
            }
        ]
    }
    sz2_fresh = {}

    # 4. Run detection
    notifications = detect_granular_changes(roll_no, user_doc, sz1_fresh, sz2_fresh)
    if len(notifications) != 1:
        print(f"[FAIL] Expected 1 notification, got {len(notifications)}")
        sys.exit(1)
    notif = notifications[0]
    print("[INFO] Detected notification:")
    pretty_print(notif)

    # Verify content
    expected_msg = f"CLOUD COMPUTING attendance changed from {old_pct} → 65%."
    if notif.get('message') != expected_msg:
        print(f"[FAIL] Unexpected message: {notif.get('message')}")
        sys.exit(1)
    if notif.get('category') != 'attendance' or notif.get('source') != 'StudZone 1':
        print("[FAIL] Category or source mismatch")
        sys.exit(1)
    print("[PASS] Notification content verified.")

    # 5. Insert notification log (mirroring production insert)
    now_iso = datetime.now(timezone.utc).isoformat()
    notif_doc = {
        "rollNo": roll_no,
        "studentRollNo": roll_no,
        "category": notif.get('category'),
        "type": notif.get('type'),
        "title": notif.get('title'),
        "description": notif.get('description'),
        "message": notif.get('message'),
        "source": notif.get('source'),
        "module": notif.get('module'),
        "timestamp": now_iso,
        "createdAt": now_iso,
        "read": False,
        "changeHash": notif.get('changeHash'),
        "changeData": notif.get('changeData'),
        "status": "pending",
        "error": None
    }
    insert_res = notifications_collection.insert_one(notif_doc)
    notif_id = insert_res.inserted_id
    print(f"[INFO] Inserted notification log _id={notif_id}, hash={notif.get('changeHash')}")

    # 6. Send email to admin only
    email_sender = EmailSender()
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
          Student: <strong style='color:#ffffff;'>{user_doc.get('name')}</strong> (<span style='font-family:monospace;color:#c4b5fd;'>{roll_no}</span>)
        </div>
        <div style='border-top:1px solid #1c202e;padding-top:14px;font-size:11px;color:#6b7280;text-align:center;'>
          © 2026 Student Sync | PSG College of Technology
        </div>
      </div>
    </body>
    </html>
    """
    success, err = email_sender.send_direct(email_sender.admin_email, subject, body, roll_no=roll_no, notif_type=notif.get('type'), notif_id=notif_id)
    if success:
        print("[PASS] SMTP delivery succeeded to admin email.")
    else:
        print(f"[FAIL] SMTP delivery error: {err}")
        sys.exit(1)

    # Update log status to sent (simulating production behavior)
    notifications_collection.update_one({"_id": notif_id}, {"$set": {"status": "sent"}})
    updated = notifications_collection.find_one({"_id": notif_id})
    if updated and updated.get('status') == 'sent':
        print("[PASS] Notification log status updated to 'sent'.")
    else:
        print("[FAIL] Log status not updated.")
        sys.exit(1)

    # 7. Duplicate prevention test – run detection again
    dup_notifs = detect_granular_changes(roll_no, user_doc, sz1_fresh, sz2_fresh)
    if len(dup_notifs) != len(notifications):
        print("[FAIL] Unexpected notification count on duplicate run.")
        sys.exit(1)
    dup_count = notifications_collection.count_documents({"changeHash": notif.get('changeHash')})
    if dup_count == 1:
        print("[PASS] Duplicate prevention confirmed – only one log entry exists.")
    else:
        print(f"[FAIL] Duplicate log entries found: {dup_count}")
        sys.exit(1)

    # 8. Cleanup test log entry (student data untouched)
    notifications_collection.delete_one({"_id": notif_id})
    print("[INFO] Cleaned up test notification record.")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
