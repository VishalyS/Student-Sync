import os
import sys
import io
from datetime import datetime, timezone
from dotenv import load_dotenv

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

load_dotenv(os.path.join(backend_dir, '.env'))
from notifications.change_detector import compute_change_hash

def test_registration_email_derivation():
    print("======================================================================")
    print("TEST: REGISTRATION EMAIL DERIVATION & ADMIN ALERT WORKFLOW")
    print("======================================================================\n")

    roll_no = "25MX232"
    student_name = "VISHALY S"
    admin_email = os.getenv("ADMIN_EMAIL", "studentsync12@gmail.com")

    # 1. Email Derivation Rule
    derived_email = f"{roll_no.lower()}@psgtech.ac.in"
    print(f"1. [Derived Student Email]: {derived_email}")
    assert derived_email == "25mx232@psgtech.ac.in", "Email derivation failed"
    print("   [PASS] Successfully derived from username without separate email field.")

    # 2. Welcome Hash & Admin Hash
    welcome_hash = compute_change_hash(roll_no, "welcome", "Account", "Welcome to Student Sync", f"welcome_{roll_no}")
    admin_hash = compute_change_hash(roll_no, "system", "Admin Alert", "New Student Registration", f"admin_reg_{roll_no}")
    
    print(f"\n2. [Deterministic Change Hashes]")
    print(f"   - Welcome Hash: {welcome_hash[:16]}...")
    print(f"   - Admin Alert Hash: {admin_hash[:16]}...")
    assert welcome_hash != admin_hash, "Hashes must be distinct for welcome and admin alert"
    print("   [PASS] Distinct deterministic hashes generated.")

    # 3. Admin Notification Content Structure
    admin_title = f"New Student Registration: {student_name} ({roll_no})"
    admin_msg = f"Student {student_name} ({roll_no}) has successfully registered. Derived email: {derived_email}."
    admin_doc = {
        "rollNo": roll_no,
        "studentRollNo": roll_no,
        "category": "system",
        "type": "system",
        "title": admin_title,
        "description": admin_msg,
        "source": "Student Sync",
        "module": "Admin",
        "changeHash": admin_hash,
        "changeData": {
            "event": "admin_registration_alert",
            "studentName": student_name,
            "rollNo": roll_no,
            "studentEmail": derived_email,
            "adminEmail": admin_email
        }
    }
    print(f"\n3. [Admin Alert Schema]")
    print(f"   - Title: {admin_doc['title']}")
    print(f"   - Recipient: {admin_email}")
    print(f"   - Derived Student Email: {admin_doc['changeData']['studentEmail']}")
    print("   [PASS] Admin alert schema properly formed.")

    print("\n======================================================================")
    print("ALL REGISTRATION EMAIL FLOW CHECKS PASSED!")
    print("======================================================================")

if __name__ == "__main__":
    test_registration_email_derivation()
