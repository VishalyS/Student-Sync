import os
import sys
import certifi
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
root_dir = os.path.abspath(os.path.join(backend_dir, '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

load_dotenv(os.path.join(backend_dir, '.env'), override=True)

try:
    from backend.notifications.change_detector import compute_change_hash
    from backend.new_scrapers.send_mail import send_email_direct
except ImportError:
    from notifications.change_detector import compute_change_hash
    from new_scrapers.send_mail import send_email_direct

def run_safe_registration_email_diagnostic():
    print("======================================================================")
    print("STUDENT SYNC — CONTROLLED SINGLE REAL-EMAIL DIAGNOSTIC")
    print("======================================================================\n")

    # 1. Strict Configuration Checks
    admin_email = (os.getenv("ADMIN_EMAIL") or "").strip()
    if not admin_email:
        print("[FAIL] ADMIN_EMAIL is not set in backend/.env.")
        print("       Please configure ADMIN_EMAIL with your authorized personal test mailbox.")
        sys.exit(1)

    if "@psgtech.ac.in" in admin_email.lower():
        print(f"[BLOCKED] Safety guard: ADMIN_EMAIL cannot be a student domain address.")
        sys.exit(1)

    smtp_user = (os.getenv("SMTP_USER") or "").strip()
    smtp_pass = (os.getenv("SMTP_PASSWORD") or "").strip()
    if not smtp_user or not smtp_pass:
        print("[FAIL] SMTP_USER or SMTP_PASSWORD is not set in backend/.env.")
        sys.exit(1)

    mongo_uri = os.getenv('MONGO_URI')
    if not mongo_uri:
        print("[FAIL] MONGO_URI is not set in backend/.env.")
        sys.exit(1)

    # Connect to MongoDB
    client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
    db = client['ecampus']
    notifs_col = db['notifications_log']

    # Synthetic test identifier
    sim_roll_no = "TEST_STUDENT_99"
    student_name = "Controlled Test Student"
    first_name = "Controlled"
    now_iso = datetime.now(timezone.utc).isoformat()

    print(f"1. [Safety Verification]")
    print(f"   - Target Mailbox: {admin_email} (Authorized test inbox)")
    print(f"   - Real Student Email Contacted: NONE (Guaranteed)")
    print(f"   - Synthetic Roll Number: {sim_roll_no}")
    print(f"   - Academic Records Modification: ZERO (Read-only / isolated)\n")

    welcome_hash = compute_change_hash(sim_roll_no, "welcome", "Account", "Welcome to Student Sync", f"welcome_{sim_roll_no}")
    welcome_title = "Welcome to Student Sync (Test Diagnostic)"
    welcome_msg = f"Welcome to Student Sync, {first_name}! This is a controlled real-email verification test."

    welcome_doc = {
        "rollNo": sim_roll_no,
        "studentRollNo": sim_roll_no,
        "category": "welcome",
        "type": "welcome",
        "title": welcome_title,
        "description": welcome_msg,
        "message": welcome_msg,
        "source": "Student Sync",
        "module": "Account",
        "timestamp": now_iso,
        "createdAt": now_iso,
        "read": False,
        "changeHash": welcome_hash,
        "changeData": {
            "event": "controlled_diagnostic_test",
            "studentName": student_name,
            "rollNo": sim_roll_no,
            "targetEmail": admin_email
        },
        "status": "pending",
        "is_diagnostic_test": True
    }

    w_notif_id = None
    try:
        # Insert initial pending record
        res_w = notifs_col.insert_one(welcome_doc)
        w_notif_id = res_w.inserted_id

        welcome_subject = "Welcome to Student Sync (Test Diagnostic)"
        welcome_body = f"""
        <!DOCTYPE html>
        <html>
        <body style="margin: 0; padding: 24px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0b0d13; color: #f3f4f6;">
          <div style="max-width: 520px; margin: 0 auto; background-color: #131620; border: 1px solid #232738; border-radius: 12px; padding: 24px;">
            <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #a78bfa; font-weight: 600; margin-bottom: 8px;">
              Student Sync • Diagnostic Verification
            </div>
            <h2 style="color: #ffffff; margin-top: 0;">Welcome to Student Sync</h2>
            <p style="color: #9ca3af; font-size: 14px; line-height: 1.6;">
              {welcome_msg}
            </p>
            <div style="padding: 12px; border-radius: 8px; background-color: #181c2b; border: 1px solid #222738; font-size: 12px; color: #9ca3af; margin: 16px 0;">
              Recipient: <strong style="color: #ffffff;">{admin_email}</strong><br>
              Simulated Student: <span style="font-family: monospace; color: #c4b5fd;">{sim_roll_no}</span>
            </div>
            <p style="color: #34d399; font-size: 13px; font-weight: 600;">
              ✔ SMTP authentication and socket transmission verified.
            </p>
            <div style="border-top: 1px solid #1c202e; padding-top: 14px; font-size: 11px; color: #6b7280; text-align: center;">
              © 2026 Student Sync | Controlled Test Verification
            </div>
          </div>
        </body>
        </html>
        """

        print("2. [Dispatching Controlled Single Test Email]")
        print(f"   - Calling send_email_direct to: {admin_email}")
        w_success, w_err = send_email_direct(
            admin_email,
            welcome_subject,
            welcome_body,
            rollNo=sim_roll_no,
            notif_type="welcome",
            notif_id=w_notif_id
        )

        if not w_success:
            print(f"\n[FAIL] SMTP Delivery Failed: {w_err}")
            sys.exit(1)

        print("   - SMTP Server Response: SUCCESS (Accepted by SMTP transport)")

        # Verify MongoDB record transition
        logged_doc = notifs_col.find_one({"_id": w_notif_id})
        status = logged_doc.get('status') if logged_doc else 'not_found'
        sent_at = logged_doc.get('sent_at') if logged_doc else None

        print("\n3. [Verifying Notification State Machine]")
        print(f"   - Database Status: '{status}'")
        print(f"   - Sent Timestamp: {sent_at}")
        print(f"   - Recipient Logged: {logged_doc.get('recipient_email')}")

        if status != "sent" or not sent_at:
            print("[FAIL] Notification record did not properly transition to 'sent' with sent_at timestamp.")
            sys.exit(1)

        print("   [PASS] MongoDB record successfully updated to 'sent' after SMTP acceptance.")

        print("\n======================================================================")
        print("CONTROLLED TEST EMAIL DISPATCHED SUCCESSFULLY!")
        print(f"Subject: {welcome_subject}")
        print(f"Sent To: {admin_email}")
        print("Please check your inbox (and spam folder) for the message.")
        print("======================================================================\n")

    finally:
        # Guarantee cleanup of synthetic test record
        if w_notif_id:
            notifs_col.delete_many({"rollNo": sim_roll_no})
            print("[CLEANUP] Deleted temporary test record from notifications_log.")
            print("[CLEANUP] Zero student academic records in MongoDB were affected.")

if __name__ == "__main__":
    run_safe_registration_email_diagnostic()
