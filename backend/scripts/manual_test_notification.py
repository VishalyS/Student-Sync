"""
Student Sync — Safe Manual Notification Tester CLI
Allows manual verification of notification email delivery directly to your inbox.

Usage examples:
  # Send a test attendance alert (below 75% threshold) to your email:
  python scripts/manual_test_notification.py --email your_email@gmail.com --type attendance_alert

  # Send a test attendance safe zone (safe bunks) to your email:
  python scripts/manual_test_notification.py --email your_email@gmail.com --type attendance_safe

  # Send a test CA marks email:
  python scripts/manual_test_notification.py --email your_email@gmail.com --type marks

  # Send a test exam timetable email:
  python scripts/manual_test_notification.py --email your_email@gmail.com --type timetable

  # Default run (sends to configured ADMIN_EMAIL):
  python scripts/manual_test_notification.py
"""

import os
import sys
import argparse
from datetime import datetime, timezone
from dotenv import load_dotenv

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

load_dotenv(os.path.join(backend_dir, '.env'))

from notifications.email_formatter import build_notification_email
from new_scrapers.send_mail import send_email_direct


def main():
    parser = argparse.ArgumentParser(description="Student Sync — Manual Notification Dispatcher")
    parser.add_argument("--roll", default="25MX227", help="Student Roll Number (default: 25MX227)")
    parser.add_argument("--name", default="SUDHERSON V", help="Student Name")
    parser.add_argument("--email", default="", help="Target recipient email (defaults to ADMIN_EMAIL in .env)")
    parser.add_argument(
        "--type",
        choices=["attendance_alert", "attendance_safe", "marks", "timetable", "seating"],
        default="attendance_alert",
        help="Notification type to test (default: attendance_alert)"
    )

    args = parser.parse_args()

    admin_email = os.getenv("ADMIN_EMAIL", "studentsync12@gmail.com").strip()
    target_email = args.email.strip() or admin_email

    print("======================================================================")
    print("STUDENT SYNC — MANUAL NOTIFICATION TEST DISPATCHER")
    print("======================================================================")
    print(f"Target Student:   {args.name} ({args.roll})")
    print(f"Recipient Email:  {target_email}")
    print(f"Selected Type:    {args.type}")
    print("======================================================================\n")

    # Construct mock notification payload based on selected type
    if args.type == "attendance_alert":
        notif = {
            "type": "attendance",
            "title": "Attendance Alert",
            "message": "CLOUD COMPUTING attendance dropped from 74% → 72%.",
            "source": "StudZone 1",
            "module": "Attendance",
            "changeData": {
                "subject": "CLOUD COMPUTING",
                "code": "23MX31",
                "previousValue": "74%",
                "newValue": "72%",
                "direction": "decreased",
                "attended": 28,
                "total": 39
            }
        }
    elif args.type == "attendance_safe":
        notif = {
            "type": "attendance",
            "title": "Attendance Updated",
            "message": "CLOUD COMPUTING LABORATORY attendance increased from 86% → 89%.",
            "source": "StudZone 1",
            "module": "Attendance",
            "changeData": {
                "subject": "CLOUD COMPUTING LABORATORY",
                "code": "23MX36",
                "previousValue": "86%",
                "newValue": "89%",
                "direction": "increased",
                "attended": 50,
                "total": 56
            }
        }
    elif args.type == "marks":
        notif = {
            "type": "marks",
            "title": "CA Marks Published",
            "message": "MACHINE LEARNING TECHNIQUES CA1 marks published: 46/50.",
            "source": "StudZone 1",
            "module": "CA Marks",
            "changeData": {
                "subject": "MACHINE LEARNING TECHNIQUES",
                "code": "23MX37",
                "test": "CA1",
                "previousValue": "-",
                "newValue": "46"
            }
        }
    elif args.type == "timetable":
        notif = {
            "type": "timetable",
            "title": "Exam Timetable Published",
            "message": "DISTRIBUTED SYSTEMS exam scheduled on 15-11-2026, FN session.",
            "source": "StudZone 2",
            "module": "Exam Timetable",
            "changeData": {
                "subject": "DISTRIBUTED SYSTEMS",
                "code": "23MXAE",
                "examDate": "15-11-2026",
                "session": "FN",
                "timing": "09:30 AM - 12:30 PM"
            }
        }
    elif args.type == "seating":
        notif = {
            "type": "seating",
            "title": "Exam Seating Allocated",
            "message": "CLOUD COMPUTING exam seating allocated: Hall E201, Seat 24.",
            "source": "StudZone 2",
            "module": "Seating Arrangement",
            "changeData": {
                "subject": "CLOUD COMPUTING",
                "code": "23MX31",
                "hall": "E201",
                "seat": "24"
            }
        }

    # 1. Format the email using the official email_formatter
    print("1. [Generating Meaningful Notification Email Card]")
    subject, html_body = build_notification_email(notif, args.name, args.roll, target_email)
    print(f"   - Subject: {subject}")
    print(f"   - Body Length: {len(html_body)} characters")

    # 2. Deliver directly via SMTP
    print(f"\n2. [Dispatching via Gmail SMTP to: {target_email}]")
    success, err_msg = send_email_direct(
        target_email,
        subject,
        html_body,
        rollNo=args.roll,
        notif_type=notif.get("type", "general")
    )

    if success:
        print("\n======================================================================")
        print(" SUCCESS: TEST NOTIFICATION EMAIL DELIVERED!")
        print("======================================================================")
        print(f"Please check the inbox for: {target_email}")
        print("Subject: " + subject)
        print("======================================================================\n")
    else:
        print("\n======================================================================")
        print(" FAILED: Could not deliver email.")
        print("======================================================================\n")
        print(f"Error: {err_msg}")


if __name__ == "__main__":
    main()
