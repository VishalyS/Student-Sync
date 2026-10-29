from flask import Flask, request, jsonify
from pymongo import MongoClient
from bson import ObjectId
import requests
from bs4 import BeautifulSoup
from flask_cors import CORS
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
import certifi
import os
import sys
import hmac
import hashlib
import base64
from datetime import datetime, timezone
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
load_dotenv()

from pymongo.errors import DuplicateKeyError

app = Flask(__name__)
_cors_origins = os.getenv('CORS_ORIGINS', os.getenv('ALLOWED_ORIGINS'))
if _cors_origins:
    origins_list = [o.strip() for o in _cors_origins.split(',') if o.strip()]
    CORS(app, origins=origins_list, supports_credentials=True)
elif os.getenv('FLASK_ENV', os.getenv('ENV', 'development')).lower() == 'production':
    # In production without CORS_ORIGINS configured, restrict to empty list to prevent wildcard access
    CORS(app, origins=[], supports_credentials=True)
else:
    # In local development, permit Vite and local dev server origins
    CORS(app, origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5000", "http://127.0.0.1:5000"], supports_credentials=True)

MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DB_NAME', 'ecampus')
USERS_COLLECTION = os.getenv('USERS_COLLECTION', 'new_users')

client = MongoClient(
    MONGO_URI,
    connectTimeoutMS=60000,
    socketTimeoutMS=60000,
    serverSelectionTimeoutMS=60000,
    maxPoolSize=50,
    minPoolSize=10,
    maxIdleTimeMS=45000,
    waitQueueTimeoutMS=10000,
    retryWrites=True,
    retryReads=True,
    tlsCAFile=certifi.where()
) if MONGO_URI else None
db = client[DB_NAME] if client else None
users_collection = db[USERS_COLLECTION] if db is not None else None
sub_collection = db['subjects'] if db is not None else None
notifications_collection = db['notifications_log'] if db is not None else None

try:
    from backend.database import ensure_database_indexes
except ImportError:
    try:
        from database import ensure_database_indexes
    except ImportError:
        ensure_database_indexes = None

if ensure_database_indexes and db is not None:
    ensure_database_indexes(db)

# Import dual-portal authentication & scrapers with resilient paths
_current_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_current_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

try:
    from backend.new_scrapers.login import login as modern_login
    from backend.new_scrapers.send_mail import send_email, queue_tracked_email, send_email_direct
    from backend.scrapers.login import login_student_studzone2 as legacy_login
    from backend.new_scrapers.studzone1_scraper import scrape_studzone1_all
    from backend.scrapers.studzone2_scraper import scrape_studzone2_all
    from backend.notifications.change_detector import compute_change_hash
    from backend.attendance_calculator import (
        calculate_attendance,
        calculate_safe_bunks,
        calculate_required_classes,
        calculate_simulated_attendance,
        get_attendance_status,
        parse_daily_schedule,
        summarize_student_attendance,
        resolve_student_attendance_records
    )
    from backend.academic_calculator import (
        summarize_student_academics,
        simulate_projected_cgpa
    )
    from backend.timetable_calculator import (
        parse_weekly_schedule_matrix,
        parse_exam_schedule_records,
        parse_circulars,
        simulate_day_bunks,
        get_unified_subject_summary
    )
    from backend.planner_calculator import synthesize_academic_planner
    from backend.services_calculator import synthesize_campus_services
    from backend.speed_ser import process_detected_changes
except ImportError:
    from new_scrapers.login import login as modern_login
    from new_scrapers.send_mail import send_email, queue_tracked_email, send_email_direct
    from scrapers.login import login_student_studzone2 as legacy_login
    from new_scrapers.studzone1_scraper import scrape_studzone1_all
    from scrapers.studzone2_scraper import scrape_studzone2_all
    from notifications.change_detector import compute_change_hash
    from attendance_calculator import (
        calculate_attendance,
        calculate_safe_bunks,
        calculate_required_classes,
        calculate_simulated_attendance,
        get_attendance_status,
        parse_daily_schedule,
        summarize_student_attendance,
        resolve_student_attendance_records
    )
    from academic_calculator import (
        summarize_student_academics,
        simulate_projected_cgpa
    )
    from timetable_calculator import (
        parse_weekly_schedule_matrix,
        parse_exam_schedule_records,
        parse_circulars,
        simulate_day_bunks,
        get_unified_subject_summary
    )
    from planner_calculator import synthesize_academic_planner
    from services_calculator import synthesize_campus_services
    try:
        from speed_ser import process_detected_changes
    except ImportError:
        process_detected_changes = None

try:
    from residential_service import determine_residential_status
except ImportError:
    try:
        from backend.residential_service import determine_residential_status
    except ImportError:
        determine_residential_status = None




def sync_student_dual_portal(rollNo, password):
    """
    Authenticates independently to BOTH StudZone 1 and StudZone 2,
    extracts all academic, examination, administrative, and student services modules,
    and updates the single student document in MongoDB with granular module sync statuses.
    """
    user_credentials = {'rollNo': rollNo, 'password': password}
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # 1. Authenticate & Scrape StudZone 1 (Modern)
    modern_session_res = modern_login(user_credentials)
    if isinstance(modern_session_res, tuple) or not modern_session_res:
        return None, "Modern StudZone authentication failed. Please check credentials."
    
    modern_session = modern_session_res
    sz1_data = scrape_studzone1_all(modern_session, rollNo, sub_collection)
    
    student_name = (sz1_data.get('profile', {}).get('Name') or rollNo).strip()

    # 2. Authenticate & Scrape StudZone 2 (Legacy)
    legacy_session_res = legacy_login(user_credentials)
    sz2_data = {}
    if not isinstance(legacy_session_res, tuple) and legacy_session_res:
        legacy_session = legacy_session_res
        sz2_data = scrape_studzone2_all(legacy_session, rollNo)
        
        # If full name was in legacy menu, clean and update
        try:
            menu_resp = legacy_session.get("https://ecampus.psgtech.ac.in/studzone2/AttWfStudMenu.aspx", timeout=10, verify=False)
            menu_soup = BeautifulSoup(menu_resp.content, 'html.parser')
            name_tag = menu_soup.find('span', {'id': 'Title1_LblStaffName'})
            if name_tag and name_tag.text.strip():
                clean_name = re.sub(r'\s*\(\s*[^)]*\)\s*', '', name_tag.text.strip()).strip()
                clean_name = re.sub(r'\s+', ' ', clean_name)
                if clean_name:
                    student_name = clean_name
        except Exception:
            pass
    else:
        print(f"StudZone 2 secondary session unavailable for {rollNo}: {legacy_session_res}")

    # Check existing user preferences & fields
    # Check existing user preferences & fields
    existing_user = users_collection.find_one({"rollNo": rollNo}) if users_collection is not None else None
    existing_notifications = existing_user.get('notifications') if existing_user else None

    # Robust fallback: preserve existing attendance baseline if portal attendance is currently updating / empty
    has_fresh_att = bool(sz1_data and sz1_data.get('parsed_attendance') and len(sz1_data.get('parsed_attendance')) > 0)
    prev_att_records = None
    if existing_user:
        prev_att_records, _, _ = resolve_student_attendance_records(existing_user)

    if sz1_data:
        if has_fresh_att:
            sz1_data['is_previous_attendance'] = False
        elif prev_att_records:
            # Portal is updating or transiently empty; keep stored previous data
            sz1_data['parsed_attendance'] = prev_att_records
            sz1_data['is_previous_attendance'] = True
            if not sz1_data.get('attendance_html') or '<td' not in sz1_data.get('attendance_html', ''):
                sz1_data['attendance_html'] = existing_user.get('attendance_table') or existing_user.get('attendance', '')

    sync_status = {
        "profile": {"status": "synced", "timestamp": now_iso, "portal": "StudZone 1"},
        "attendance": {"status": "synced" if has_fresh_att else ("updating" if prev_att_records else "no_data"), "timestamp": now_iso, "portal": "StudZone 1"},
        "marks": {"status": "synced" if sz1_data.get("ca_marks_html") else "no_data", "timestamp": now_iso, "portal": "StudZone 1"},
        "results": {"status": "synced" if sz2_data.get("results_html") else "no_data", "timestamp": now_iso, "portal": "StudZone 2"},
        "cgpa": {"status": "synced" if sz2_data.get("cgpa") is not None else "no_data", "timestamp": now_iso, "portal": "StudZone 2"},
        "timetable": {"status": "synced" if sz2_data.get("timetable_html") or sz1_data.get("class_timetable_html") else "no_data", "timestamp": now_iso, "portal": "StudZone 2"},
        "seating": {"status": "synced" if sz2_data.get("seating_html") else "not_published_yet", "timestamp": now_iso, "portal": "StudZone 2"},
        "fees": {"status": "synced" if sz1_data.get("fees_html") else "no_data", "timestamp": now_iso, "portal": "StudZone 1"},
        "hostel": {"status": "synced" if sz1_data.get("hostel_html") else "no_data", "timestamp": now_iso, "portal": "StudZone 1"},
        "scholarships": {"status": "synced", "timestamp": now_iso, "portal": "StudZone 1"},
        "feedback": {"status": "synced", "timestamp": now_iso, "portal": "StudZone 1"},
        "leave": {"status": "synced" if sz1_data.get("leave_html") else "no_data", "timestamp": now_iso, "portal": "StudZone 1"},
        "library": {"status": "not_available_on_portal", "timestamp": now_iso, "portal": "External OPAC"}
    }

    # Determine monitoring_enabled:
    # If the student already had an initialized baseline, preserve their custom preference;
    # otherwise (new registration or initial baseline initialization), enable monitoring.
    if existing_user and existing_user.get('baseline_initialized') is True:
        monitoring_enabled = existing_user.get('monitoring_enabled', True)
    else:
        monitoring_enabled = True

    welcome_email_flag = bool(existing_user and existing_user.get('welcomeEmailSent'))

    # Build comprehensive student document with portal fallback preservation
    student_email = (existing_user.get('email') if existing_user else None) or f"{rollNo.lower()}@psgtech.ac.in"
    merged_user = {
        "rollNo": rollNo,
        "email": student_email,
        "password": password,
        "name": student_name,
        "monitoring_enabled": monitoring_enabled,
        "profile": sz1_data.get("profile", {}) if sz1_data else (existing_user.get('profile', {}) if existing_user else {}),
        "cgpa": sz2_data.get("cgpa") if (sz2_data and sz2_data.get("cgpa") is not None) else (existing_user.get('cgpa') if existing_user else None),
        "attendance": sz1_data.get("attendance_html", "") if sz1_data else (existing_user.get('attendance', '') if existing_user else ""),
        "marks": sz1_data.get("ca_marks_html", "") if sz1_data else (existing_user.get('marks', '') if existing_user else ""),
        "results": sz2_data.get("results_html", "") if sz2_data else (existing_user.get('results', '') if existing_user else ""),
        "result_table": sz2_data.get("results_html", "") if sz2_data else (existing_user.get('result_table', '') if existing_user else ""),
        "timetable": (sz2_data.get("timetable_html", "") or sz1_data.get("class_timetable_html", "")) if (sz2_data or sz1_data) else (existing_user.get('timetable', '') if existing_user else ""),
        "seating": sz2_data.get("seating_html") if sz2_data else (existing_user.get('seating') if existing_user else None),
        "fees": sz1_data.get("fees_html", "") if sz1_data else (existing_user.get('fees', '') if existing_user else ""),
        "feedback": sz1_data.get("feedback", []) if sz1_data else (existing_user.get('feedback', []) if existing_user else []),
        "hostel": sz1_data.get("hostel_html", "") if sz1_data else (existing_user.get('hostel', '') if existing_user else ""),
        "scholarships": sz1_data.get("scholarships", {}) if sz1_data else (existing_user.get('scholarships', {}) if existing_user else {}),
        "leave": sz1_data.get("leave_html", "") if sz1_data else (existing_user.get('leave', '') if existing_user else ""),
        "library": None,
        "applications": sz2_data.get("applications", {}) if sz2_data else (existing_user.get('applications', {}) if existing_user else {}),
        "circulars": sz2_data.get("circulars", []) if sz2_data else (existing_user.get('circulars', []) if existing_user else []),
        "studzone1": sz1_data if sz1_data else (existing_user.get('studzone1', {}) if existing_user else {}),
        "studzone2": sz2_data if sz2_data else (existing_user.get('studzone2', {}) if existing_user else {}),
        "previous_parsed_attendance": (sz1_data.get('parsed_attendance') if has_fresh_att else prev_att_records) or (existing_user.get('previous_parsed_attendance') if existing_user else None),
        "attendance_table": (sz1_data.get('attendance_html') if has_fresh_att else (existing_user.get('attendance_table') if existing_user else sz1_data.get('attendance_html', ''))),
        "notifications": existing_notifications or {
            "attendance": True,
            "marks": True,
            "timetable": True,
            "seatingArrangement": True,
            "results": True,
            "fees": True,
            "hostel": True
        },
        "lastAttemptAt": now_iso,
        "lastSuccessfulSyncAt": now_iso,
        "lastSyncedAt": now_iso,
        "last_synced_studzone1": now_iso,
        "last_synced_studzone2": now_iso if sz2_data else (existing_user.get('last_synced_studzone2') if existing_user else None),
        "last_successful_studzone1": now_iso,
        "last_successful_studzone2": now_iso if sz2_data else (existing_user.get('last_successful_studzone2') if existing_user else None),
        "syncStatus": sync_status,
        "portalStatus": {
            "studzone1": "connected",
            "studzone2": "connected" if sz2_data else "unreachable"
        },
        "baseline_initialized": True,
        "welcomeEmailSent": welcome_email_flag
    }

    # CRITICAL: Detect granular changes against existing stored student baseline and dispatch email notifications
    if existing_user and existing_user.get('baseline_initialized') is True and (sz1_data or sz2_data):
        try:
            if process_detected_changes:
                process_detected_changes(rollNo, existing_user, sz1_data or {}, sz2_data or {}, db)
        except Exception as change_err:
            print(f"[CHANGE DETECTION ERROR] Failed during portal sync for {rollNo}: {change_err}")

    if users_collection is not None:
        users_collection.update_one(
            {"rollNo": rollNo},
            {"$set": merged_user},
            upsert=True
        )
        saved_doc = users_collection.find_one({"rollNo": rollNo})
        return saved_doc, None

    return merged_user, None


def dispatch_welcome_email_to_student(roll_no, student_email=None, student_name=None, force=False):
    """
    Idempotently and reliably dispatches the official welcome email to the student's email address.
    Sets welcomeEmailSent: True and logs to notifications_log.
    If force is True, bypasses welcomeEmailSent check (e.g. user updated email or requested resend).
    """
    if users_collection is None:
        return False, "Database unavailable"

    roll_clean = roll_no.strip().upper()
    user = users_collection.find_one({"rollNo": roll_clean})
    if not user:
        return False, "Student record not found in database"

    if not force and user.get('welcomeEmailSent') is True:
        return False, "Welcome email already sent"

    target_email = (student_email or user.get('email') or f"{roll_clean.lower()}@psgtech.ac.in").strip()
    name = (student_name or user.get('name') or roll_clean).strip()
    first_name = name.split()[0].capitalize() if name else roll_clean
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    welcome_hash = compute_change_hash(roll_clean, "welcome", "Account", "Welcome to Student Sync 🎓", f"welcome_{roll_clean}_{target_email.lower() if force else ''}")

    welcome_title = "Welcome to Student Sync 🎓"
    welcome_msg = f"Thank you for registering with Student Sync, {first_name}! From now on, you will receive meaningful notifications when relevant information changes in your connected student portals."

    notif_doc = {
        "rollNo": roll_clean,
        "studentRollNo": roll_clean,
        "recipient_email": target_email,
        "category": "welcome",
        "type": "welcome",
        "title": welcome_title,
        "description": welcome_msg,
        "message": welcome_msg,
        "source": "Student Sync",
        "module": "Account",
        "timestamp": now_iso,
        "createdAt": now_iso,
        "created_at": now,
        "updated_at": now,
        "read": False,
        "changeHash": welcome_hash,
        "changeData": {
            "event": "welcome",
            "studentName": name,
            "rollNo": roll_clean,
            "studentEmail": target_email
        },
        "status": "pending",
        "error": None
    }

    notif_id = None
    if notifications_collection is not None:
        try:
            res = notifications_collection.insert_one(notif_doc)
            notif_id = res.inserted_id
        except DuplicateKeyError:
            if not force:
                return False, "Duplicate welcome notification suppressed"
            existing = notifications_collection.find_one({"changeHash": welcome_hash})
            if existing:
                notif_id = existing.get('_id')

    welcome_subject = "Welcome to Student Sync 🎓"
    welcome_body = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin: 0; padding: 24px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0b0d13; color: #f3f4f6;">
      <div style="max-width: 560px; margin: 0 auto; background-color: #131620; border: 1px solid #232738; border-radius: 12px; padding: 28px;">
        <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #a78bfa; font-weight: 600; margin-bottom: 6px;">
          Student Sync • Registration Confirmed
        </div>
        <h2 style="color: #ffffff; font-size: 20px; margin-top: 0; margin-bottom: 12px;">Welcome to Student Sync 🎓</h2>
        <p style="color: #e5e7eb; font-size: 14px; line-height: 1.6; margin-bottom: 16px;">
          Hi <strong style="color: #ffffff;">{name}</strong> (<span style="font-family: monospace; color: #c4b5fd;">{roll_clean}</span>),
        </p>
        <p style="color: #9ca3af; font-size: 14px; line-height: 1.6; margin-bottom: 16px;">
          Thank you for registering with Student Sync! Your PSG Tech student portals (StudZone 1 & StudZone 2) have been successfully linked and synchronized.
        </p>
        <p style="color: #9ca3af; font-size: 14px; line-height: 1.6; margin-bottom: 20px;">
          From now on, you will receive meaningful notifications when relevant information changes in your connected student portals:
        </p>

        <table style="width: 100%; border-collapse: collapse; font-size: 13px; color: #d1d5db; margin-bottom: 24px; background-color: #181c2b; border-radius: 8px; border: 1px solid #222738; overflow: hidden;">
          <tr style="border-bottom: 1px solid #222738;">
            <td style="padding: 10px 14px; color: #9ca3af; width: 40%;">📊 Attendance Tracking</td>
            <td style="padding: 10px 14px; color: #ffffff;">Real-time percentage alerts & safe bunk predictions</td>
          </tr>
          <tr style="border-bottom: 1px solid #222738;">
            <td style="padding: 10px 14px; color: #9ca3af;">📝 CA Marks</td>
            <td style="padding: 10px 14px; color: #ffffff;">Instant notifications when internal test marks are posted</td>
          </tr>
          <tr style="border-bottom: 1px solid #222738;">
            <td style="padding: 10px 14px; color: #9ca3af;">📅 Exam Schedules</td>
            <td style="padding: 10px 14px; color: #ffffff;">Timetable publications and slot changes</td>
          </tr>
          <tr style="border-bottom: 1px solid #222738;">
            <td style="padding: 10px 14px; color: #9ca3af;">🪑 Seating Arrangements</td>
            <td style="padding: 10px 14px; color: #ffffff;">Hall allocations & exam seat assignments</td>
          </tr>
          <tr style="border-bottom: 1px solid #222738;">
            <td style="padding: 10px 14px; color: #9ca3af;">💳 Academic Fees</td>
            <td style="padding: 10px 14px; color: #ffffff;">Dues alerts and receipt status updates</td>
          </tr>
          <tr>
            <td style="padding: 10px 14px; color: #9ca3af;">📈 Semester Results</td>
            <td style="padding: 10px 14px; color: #ffffff;">Grade announcements & CGPA updates</td>
          </tr>
        </table>

        <div style="padding: 14px; border-radius: 8px; background-color: #181c2b; border: 1px solid #222738; font-size: 13px; color: #9ca3af; margin-bottom: 24px;">
          <div style="margin-bottom: 6px;"><strong style="color: #ffffff;">Monitoring Status:</strong> <span style="color: #34d399; font-weight: 600;">Active & Synchronized (monitoring is now active)</span></div>
          <div><strong style="color: #ffffff;">Primary Alert Email:</strong> <span style="font-family: monospace; color: #93c5fd;">{target_email}</span></div>
        </div>

        <div style="text-align: center; margin-bottom: 24px;">
          <a href="http://localhost:3000/login" style="display: inline-block; padding: 12px 24px; background-color: #8b5cf6; color: #ffffff; text-decoration: none; font-size: 13px; font-weight: 600; border-radius: 8px;">
            Open Student Sync Dashboard →
          </a>
        </div>

        <div style="border-top: 1px solid #1c202e; padding-top: 16px; font-size: 12px; color: #6b7280; text-align: center;">
          © 2026 Student Sync | PSG College of Technology
        </div>
      </div>
    </body>
    </html>
    """
    print(f"[WELCOME EMAIL] Dispatching welcome email to {target_email} for {roll_clean}")
    w_success, w_err = send_email_direct(target_email, welcome_subject, welcome_body, rollNo=roll_clean, notif_type="welcome", notif_id=notif_id)
    if not w_success:
        print(f"[WELCOME EMAIL] Direct send failed ({w_err}); enqueueing into tracked background worker queue...")
        queue_tracked_email(roll_clean, target_email, "welcome", welcome_subject, welcome_body, notif_id=notif_id)

    users_collection.update_one(
        {"rollNo": roll_clean},
        {"$set": {
            "email": target_email,
            "welcomeEmailSent": True,
            "welcome_email_sent_at": now_iso
        }}
    )
    return True, None


@app.route('/register', methods=['POST'])
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    rollNo = (data.get('rollNo') or data.get('rollno') or '').strip().upper()
    password = (data.get('password') or '').strip()
    custom_email = (data.get('email') or '').strip()

    if not rollNo or not password:
        return jsonify({"message": "Invalid credentials. Please check your roll number and password."}), 400

    try:
        # 1. Check whether student is already registered in MongoDB
        existing_user_doc = users_collection.find_one({
            "rollNo": {"$regex": f"^{re.escape(rollNo)}$", "$options": "i"}
        }) if users_collection is not None else None

        if existing_user_doc:
            print(f"[REGISTRATION] Duplicate registration blocked for existing student: {rollNo}")
            return jsonify({
                "message": "This student is already registered.",
                "detail": "Already registered. Please Login.",
                "already_registered": True
            }), 409

        is_new_registration = True
        now_iso = datetime.now(timezone.utc).isoformat()
        student_email = custom_email or f"{rollNo.lower()}@psgtech.ac.in"

        # Step 1: Save user placeholder with uninitialized baseline to prevent race condition.
        if users_collection is not None:
            print(f"[REGISTRATION] New student detected: {rollNo}. Saving initial uninitialized record.")
            users_collection.update_one(
                {"rollNo": rollNo},
                {"$set": {
                    "rollNo": rollNo,
                    "password": password,
                    "email": student_email,
                    "baseline_initialized": False,
                    "monitoring_enabled": False,
                    "welcomeEmailSent": False,
                    "createdAt": now_iso
                }},
                upsert=True
            )

        # Step 2 & 3: Authenticate with portals and scrape current academic data
        user_doc, err = sync_student_dual_portal(rollNo, password)
        if err or not user_doc:
            if is_new_registration and users_collection is not None:
                users_collection.delete_one({"rollNo": rollNo, "baseline_initialized": False})
            return jsonify({"message": err or "Invalid credentials. Please check your roll number and password."}), 401

        # Step 4 & 5: Store initial baseline and custom email if specified
        if custom_email and users_collection is not None:
            users_collection.update_one({"rollNo": rollNo}, {"$set": {"email": custom_email}})
            user_doc["email"] = custom_email

        student_name = user_doc.get('name', rollNo)
        student_email = user_doc.get('email') or student_email
        admin_email = os.getenv("ADMIN_EMAIL", "studentsync12@gmail.com").strip()

        # Step 6: Dispatch welcome email reliably
        dispatch_welcome_email_to_student(rollNo, student_email=student_email, student_name=student_name)

        # B. Admin Registration Email (independent non-blocking notification)
        if is_new_registration and notifications_collection is not None:
            try:
                admin_hash = compute_change_hash(rollNo, "system", "Admin Alert", "New Student Registration", f"admin_reg_{rollNo}")
                existing_admin = notifications_collection.find_one({
                    "changeHash": admin_hash
                })

                if not existing_admin:
                    admin_title = f"New Student Registration: {student_name} ({rollNo})"
                    admin_msg = f"Student {student_name} ({rollNo}) has successfully registered. Derived email: {student_email}."
                    
                    now_utc = datetime.now(timezone.utc)
                    admin_doc = {
                        "rollNo": rollNo,
                        "studentRollNo": rollNo,
                        "recipient_email": admin_email,
                        "category": "system",
                        "type": "system",
                        "title": admin_title,
                        "description": admin_msg,
                        "message": admin_msg,
                        "source": "Student Sync",
                        "module": "Admin",
                        "timestamp": now_iso,
                        "createdAt": now_iso,
                        "created_at": now_utc,
                        "updated_at": now_utc,
                        "read": False,
                        "changeHash": admin_hash,
                        "changeData": {
                            "event": "admin_registration_alert",
                            "studentName": student_name,
                            "rollNo": rollNo,
                            "studentEmail": student_email,
                            "adminEmail": admin_email
                        },
                        "status": "pending",
                        "error": None
                    }
                    try:
                        res_admin = notifications_collection.insert_one(admin_doc)
                    except DuplicateKeyError:
                        print(f"[REGISTRATION] Duplicate admin alert suppressed by unique index for {rollNo}")
                        res_admin = None

                    sz1 = user_doc.get('studzone1', {})
                    sz2 = user_doc.get('studzone2', {})
                    att_count = len(sz1.get('parsed_attendance', []))
                    marks_count = len(sz1.get('parsed_marks', []))
                    res_count = len(sz2.get('parsed_results', []))
                    tt_count = len(sz2.get('parsed_timetable', []))
                    cgpa_val = user_doc.get('cgpa', 'N/A')

                    admin_subject = f"Student Sync — New Registration: {student_name} ({rollNo})"
                    admin_body = f"""
                    <!DOCTYPE html>
                    <html>
                    <body style="margin: 0; padding: 24px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0b0d13; color: #f3f4f6;">
                      <div style="max-width: 560px; margin: 0 auto; background-color: #131620; border: 1px solid #232738; border-radius: 12px; padding: 28px;">
                        <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #a78bfa; font-weight: 600; margin-bottom: 6px;">
                          Admin Notification • New Student Registration
                        </div>
                        <h2 style="color: #ffffff; font-size: 20px; margin-top: 0; margin-bottom: 16px;">New Student Registered</h2>
                        
                        <table style="width: 100%; border-collapse: collapse; font-size: 13px; color: #d1d5db; margin-bottom: 20px;">
                          <tr style="border-bottom: 1px solid #232738;">
                            <td style="padding: 8px 0; color: #9ca3af;">Student Name:</td>
                            <td style="padding: 8px 0; font-weight: 600; color: #ffffff;">{student_name}</td>
                          </tr>
                          <tr style="border-bottom: 1px solid #232738;">
                            <td style="padding: 8px 0; color: #9ca3af;">Roll Number:</td>
                            <td style="padding: 8px 0; font-family: monospace; color: #c4b5fd;">{rollNo}</td>
                          </tr>
                          <tr style="border-bottom: 1px solid #232738;">
                            <td style="padding: 8px 0; color: #9ca3af;">Derived PSG Tech Email:</td>
                            <td style="padding: 8px 0; font-family: monospace; color: #93c5fd;">{student_email}</td>
                          </tr>
                          <tr style="border-bottom: 1px solid #232738;">
                            <td style="padding: 8px 0; color: #9ca3af;">Registration Time:</td>
                            <td style="padding: 8px 0; color: #ffffff;">{now_iso}</td>
                          </tr>
                          <tr style="border-bottom: 1px solid #232738;">
                            <td style="padding: 8px 0; color: #9ca3af;">Registration Status:</td>
                            <td style="padding: 8px 0; color: #34d399; font-weight: 600;">Verified & Registered</td>
                          </tr>
                          <tr style="border-bottom: 1px solid #232738;">
                            <td style="padding: 8px 0; color: #9ca3af;">StudZone 1 Scrape:</td>
                            <td style="padding: 8px 0; color: #ffffff;">Connected ({att_count} courses, {marks_count} CA marks, Fees, Hostel)</td>
                          </tr>
                          <tr>
                            <td style="padding: 8px 0; color: #9ca3af;">StudZone 2 Scrape:</td>
                            <td style="padding: 8px 0; color: #ffffff;">Connected ({res_count} results, CGPA {cgpa_val}, {tt_count} exam slots)</td>
                          </tr>
                        </table>

                        <div style="border-top: 1px solid #1c202e; padding-top: 16px; font-size: 12px; color: #6b7280; text-align: center;">
                          © 2026 Student Sync | Admin Notification System
                        </div>
                      </div>
                    </body>
                    </html>
                    """
                    if res_admin:
                        print(f"[EMAIL] Admin recipient: {admin_email}")
                        a_success, a_err = send_email_direct(admin_email, admin_subject, admin_body, rollNo=rollNo, notif_type="system", notif_id=res_admin.inserted_id)
                        if a_success:
                            print(f"[EMAIL] Admin send result: SUCCESS")
                        else:
                            print(f"[EMAIL] Admin send result: FAILED ({a_err})")
                else:
                    print(f"[EMAIL] Admin registration email already sent for {rollNo}; skipping duplicate.")

            except Exception as email_err:
                print(f"[EMAIL] Non-blocking admin registration email error: {email_err}")

        return jsonify({
            "message": "Registration successful! Welcome to Student Sync.",
            "rollNo": rollNo,
            "email": student_email,
            "user": {
                "rollNo": user_doc["rollNo"],
                "email": student_email,
                "name": user_doc["name"],
                "cgpa": user_doc.get("cgpa")
            }
        }), 201

    except Exception as e:
        print(f"Error during registration: {str(e)}")
        return jsonify({
            "message": "Server error. Please try again later."
        }), 500


# Real Dashboard & Platform Statistics Endpoint
@app.route('/stats', methods=['GET'])
@app.route('/api/stats', methods=['GET'])
def get_platform_stats():
    try:
        students_count = users_collection.count_documents({}) if users_collection is not None else 0
        total_notifs = notifications_collection.count_documents({}) if notifications_collection is not None else 0
        notifications_sent = notifications_collection.count_documents({"status": "sent"}) if notifications_collection is not None else 0
        notifications_failed = notifications_collection.count_documents({"status": "failed"}) if notifications_collection is not None else 0
        unread_count = notifications_collection.count_documents({"read": False}) if notifications_collection is not None else 0
        
        attendance_sent = notifications_collection.count_documents({"type": "attendance"}) if notifications_collection is not None else 0
        marks_sent = notifications_collection.count_documents({"type": "marks"}) if notifications_collection is not None else 0
        results_sent = notifications_collection.count_documents({"type": "results"}) if notifications_collection is not None else 0
        timetable_sent = notifications_collection.count_documents({"type": "timetable"}) if notifications_collection is not None else 0
        seating_sent = notifications_collection.count_documents({"type": "seating"}) if notifications_collection is not None else 0
        fees_sent = notifications_collection.count_documents({"type": "fees"}) if notifications_collection is not None else 0
        welcome_sent = notifications_collection.count_documents({"type": "welcome"}) if notifications_collection is not None else 0

        latest_notif = None
        if notifications_collection is not None:
            latest = notifications_collection.find_one({}, sort=[("createdAt", -1)])
            if latest:
                latest["_id"] = str(latest["_id"])
                latest_notif = latest

        return jsonify({
            "studentsRegistered": students_count,
            "notificationsDelivered": notifications_sent,
            "totalNotifications": total_notifs,
            "unreadNotifications": unread_count,
            "students_registered": students_count,
            "notifications_sent": notifications_sent,
            "notifications_failed": notifications_failed,
            "total_notifications_logged": total_notifs,
            "latestNotification": latest_notif,
            "breakdown": {
                "attendance": attendance_sent,
                "marks": marks_sent,
                "results": results_sent,
                "timetable": timetable_sent,
                "seating": seating_sent,
                "fees": fees_sent,
                "welcome": welcome_sent
            }
        }), 200
    except Exception as e:
        print(f"Error fetching stats: {e}")
        return jsonify({
            "studentsRegistered": 0,
            "notificationsDelivered": 0,
            "totalNotifications": 0,
            "unreadNotifications": 0,
            "students_registered": 0,
            "notifications_sent": 0,
            "notifications_failed": 0,
            "total_notifications_logged": 0,
            "breakdown": {
                "attendance": 0,
                "marks": 0,
                "results": 0,
                "timetable": 0,
                "seating": 0,
                "fees": 0,
                "welcome": 0
            },
            "error": str(e)
        }), 500


# Fetch Student Specific Notifications
@app.route('/notifications', methods=['GET'])
@app.route('/api/notifications', methods=['GET'])
def get_student_notifications():
    rollNo = (request.args.get('rollNo') or '').strip().upper()
    user, status_code, err = get_authenticated_student(request)
    if err:
        is_prod = os.getenv('FLASK_ENV', os.getenv('ENV', 'development')).lower() == 'production'
        has_auth_attempt = bool(request.headers.get('Authorization') or request.args.get('auth_token') or request.headers.get('X-Roll-No'))
        if is_prod or has_auth_attempt:
            return jsonify({"notifications": [], "unreadCount": 0, "error": err}), status_code
        if not rollNo:
            return jsonify({"notifications": [], "unreadCount": 0, "error": err}), status_code
    else:
        rollNo = user.get('rollNo')
    try:
        query = {"rollNo": rollNo} if rollNo else {}
        if notifications_collection is None:
            return jsonify({"notifications": [], "unreadCount": 0}), 200

        cursor = notifications_collection.find(query).sort("createdAt", -1).limit(50)
        notifs = []
        unread_count = 0
        for doc in cursor:
            doc['_id'] = str(doc['_id'])
            if not doc.get('read', False):
                unread_count += 1
            notifs.append(doc)

        return jsonify({
            "notifications": notifs,
            "unreadCount": unread_count,
            "total": len(notifs)
        }), 200
    except Exception as e:
        print(f"Error fetching notifications: {e}")
        return jsonify({"notifications": [], "unreadCount": 0, "error": str(e)}), 500


# Mark Notification as Read
@app.route('/notifications/mark-read', methods=['POST'])
@app.route('/api/notifications/mark-read', methods=['POST'])
def mark_notification_read():
    data = request.get_json() or {}
    rollNo = (data.get('rollNo') or '').strip().upper()
    notif_id = data.get('notificationId')
    mark_all = data.get('all', False)

    if notifications_collection is None:
        return jsonify({"message": "Database not connected."}), 500

    try:
        if mark_all and rollNo:
            res = notifications_collection.update_many({"rollNo": rollNo}, {"$set": {"read": True}})
            return jsonify({"message": f"Marked {res.modified_count} notifications as read."}), 200
        elif notif_id:
            try:
                oid = ObjectId(notif_id)
                res = notifications_collection.update_one({"_id": oid}, {"$set": {"read": True}})
                return jsonify({"message": "Notification marked as read."}), 200
            except Exception:
                res = notifications_collection.update_one({"changeHash": notif_id}, {"$set": {"read": True}})
                return jsonify({"message": "Notification marked as read."}), 200
        else:
            return jsonify({"message": "Invalid parameters."}), 400
    except Exception as e:
        print(f"Error marking notification read: {e}")
        return jsonify({"error": str(e)}), 500


_secret_key = os.getenv('SECRET_KEY')
_is_production = os.getenv('FLASK_ENV', os.getenv('ENV', 'development')).lower() == 'production'

if not _secret_key:
    if _is_production:
        raise RuntimeError("CRITICAL SECURITY ERROR: SECRET_KEY environment variable MUST be explicitly set in production mode. Refusing to run with fallback default.")
    _secret_key = 'student_sync_attendance_token_secret_2026'

AUTH_SECRET = _secret_key.encode('utf-8')


def generate_auth_token(roll_no):
    """Generates an HMAC-SHA256 signed bearer token for authenticated student identity."""
    if not roll_no:
        return None
    roll_clean = roll_no.strip().upper()
    sig = hmac.new(AUTH_SECRET, roll_clean.encode('utf-8'), hashlib.sha256).hexdigest()
    raw = f"{roll_clean}:{sig}"
    return base64.urlsafe_b64encode(raw.encode('utf-8')).decode('utf-8')


def verify_auth_token(token):
    """Validates token HMAC signature and returns the verified student roll number or None."""
    if not token or not isinstance(token, str):
        return None
    try:
        raw = base64.urlsafe_b64decode(token.strip().encode('utf-8')).decode('utf-8')
        if ':' not in raw:
            return None
        roll_clean, sig = raw.split(':', 1)
        expected = hmac.new(AUTH_SECRET, roll_clean.encode('utf-8'), hashlib.sha256).hexdigest()
        if hmac.compare_digest(sig, expected):
            return roll_clean
        return None
    except Exception:
        return None


def get_authenticated_student(req):
    """
    Safely identifies and authorizes the student making the request.
    Verifies:
      1. Authorization header ('Bearer <auth_token>')
      2. 'auth_token' query parameter or request body field
      3. Direct credentials ('X-Roll-No' & 'X-Password' headers)
    Enforces user isolation:
      If a client supplies a conflicting rollNo in query params or body,
      the mismatch is detected as an unauthorized cross-user attempt and rejected with 403 Forbidden.
    Returns:
      (user_doc, status_code, error_message)
    """
    auth_header = req.headers.get('Authorization', '')
    token = None
    if auth_header.startswith('Bearer '):
        token = auth_header.split(' ', 1)[1].strip()
    elif req.args.get('auth_token'):
        token = req.args.get('auth_token').strip()
    elif req.is_json and req.get_json(silent=True) and req.get_json(silent=True).get('auth_token'):
        token = str(req.get_json(silent=True).get('auth_token')).strip()

    authenticated_roll = None
    if token:
        authenticated_roll = verify_auth_token(token)

    # Programmatic / test credentials fallback
    if not authenticated_roll:
        x_roll = req.headers.get('X-Roll-No', '').strip().upper()
        x_pwd = req.headers.get('X-Password', '').strip()
        if x_roll and x_pwd and users_collection is not None:
            user = users_collection.find_one({"rollNo": x_roll, "password": x_pwd})
            if user:
                authenticated_roll = x_roll

    if not authenticated_roll:
        return None, 401, "Authentication required. Please log in to access your attendance records."

    # Detect cross-user access attempts (e.g. attempting to query another rollNo)
    requested_roll = (
        req.args.get('rollNo') or
        req.headers.get('X-Target-Roll-No') or
        (req.get_json(silent=True).get('rollNo') if req.is_json and req.get_json(silent=True) else None)
    )
    if requested_roll:
        requested_roll_clean = str(requested_roll).strip().upper()
        if requested_roll_clean != authenticated_roll:
            return None, 403, f"Cross-user access denied. Authenticated as {authenticated_roll}, cannot access {requested_roll_clean}."

    if users_collection is None:
        return None, 500, "Database unavailable."

    try:
        user_doc = users_collection.find_one({"rollNo": authenticated_roll})
    except Exception as db_err:
        print(f"MongoDB connection glitch in get_authenticated_student: {db_err}")
        return None, 503, "Database connection is temporarily reconnecting. Please retry in a moment."

    if not user_doc:
        return None, 404, f"Student record for {authenticated_roll} not found."

    return user_doc, 200, None


# Login route
@app.route('/login', methods=['POST'])
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    rollNo = (data.get('rollNo') or '').strip().upper()
    password = (data.get('password') or '').strip()

    try:
        user = users_collection.find_one({"rollNo": rollNo, "password": password})

        if user:
            # Auto-sync fresh portal data if last sync was more than 3 minutes ago
            last_sync_iso = user.get('last_successful_studzone1') or user.get('lastSyncedAt')
            needs_sync = True
            if last_sync_iso:
                try:
                    sync_time = datetime.fromisoformat(last_sync_iso.replace('Z', '+00:00'))
                    if (datetime.now(timezone.utc) - sync_time).total_seconds() < 180:
                        needs_sync = False
                except Exception:
                    needs_sync = True

            if needs_sync:
                try:
                    updated_doc, err = sync_student_dual_portal(rollNo, password)
                    if updated_doc:
                        user = updated_doc
                except Exception as sync_e:
                    print(f"[LOGIN SYNC] Fallback to cached user doc: {sync_e}")

            sz1 = user.get('studzone1')
            if isinstance(sz1, dict) and not sz1.get('parsed_attendance'):
                prev_att, is_prev, _ = resolve_student_attendance_records(user)
                if prev_att:
                    user['studzone1']['parsed_attendance'] = prev_att
                    user['is_previous_attendance'] = True
                    user['previous_parsed_attendance'] = prev_att

            if '_id' in user:
                user['_id'] = str(user['_id'])
            user.pop('password', None)
            user['auth_token'] = generate_auth_token(rollNo)
            if determine_residential_status:
                res_info = determine_residential_status(user)
                user['residential_status'] = res_info['status']
                user['is_hosteller'] = res_info['is_hosteller']
                user['is_day_scholar'] = res_info['is_day_scholar']
                user['can_access_hostel'] = res_info['can_access_hostel']
                user['room_number'] = res_info['room_number']
            return jsonify(user)

        # Fallback: attempt direct portal authentication if not found in db
        user_doc, err = sync_student_dual_portal(rollNo, password)
        if user_doc and not err:
            # Automatically dispatch welcome email for first-time account linking
            if not user_doc.get('welcomeEmailSent'):
                try:
                    dispatch_welcome_email_to_student(rollNo, student_email=user_doc.get('email'), student_name=user_doc.get('name'))
                except Exception as w_err:
                    print(f"[LOGIN WELCOME EMAIL] Error: {w_err}")

            if '_id' in user_doc:
                user_doc['_id'] = str(user_doc['_id'])
            user_doc.pop('password', None)
            user_doc['auth_token'] = generate_auth_token(rollNo)
            if determine_residential_status:
                res_info = determine_residential_status(user_doc)
                user_doc['residential_status'] = res_info['status']
                user_doc['is_hosteller'] = res_info['is_hosteller']
                user_doc['is_day_scholar'] = res_info['is_day_scholar']
                user_doc['can_access_hostel'] = res_info['can_access_hostel']
                user_doc['room_number'] = res_info['room_number']
            return jsonify(user_doc)

        return jsonify({"message": "Invalid credentials. Please try again."}), 401

    except Exception as e:
        print(f"Error during login: {str(e)}")
        return jsonify({"message": "Server error. Please try again later."}), 500


# Endpoint to trigger or resend Welcome Email on demand
@app.route('/resend-welcome', methods=['POST'])
@app.route('/api/resend-welcome', methods=['POST'])
def resend_welcome_email():
    data = request.get_json() or {}
    rollNo = (data.get('rollNo') or data.get('rollno') or '').strip().upper()
    custom_email = (data.get('email') or '').strip()

    if not rollNo:
        return jsonify({"message": "Roll number is required."}), 400

    if users_collection is None:
        return jsonify({"message": "Database not connected."}), 500

    try:
        user = users_collection.find_one({"rollNo": rollNo})
        if not user:
            return jsonify({"message": "Student not found in database. Please log in or register first."}), 404

        target_email = custom_email or user.get('email') or f"{rollNo.lower()}@psgtech.ac.in"
        if custom_email:
            users_collection.update_one({"rollNo": rollNo}, {"$set": {"email": custom_email}})

        ok, err = dispatch_welcome_email_to_student(rollNo, student_email=target_email, student_name=user.get('name'), force=True)
        if ok:
            return jsonify({
                "message": f"Welcome email sent successfully to {target_email}!",
                "rollNo": rollNo,
                "email": target_email
            }), 200
        else:
            return jsonify({"message": err or "Failed to send welcome email."}), 400

    except Exception as e:
        print(f"Error resending welcome email: {e}")
        return jsonify({"message": "Server error while sending welcome email."}), 500


# Profile fetching and manual refresh route
@app.route('/profile', methods=['GET'])
@app.route('/api/profile', methods=['GET'])
def profile():
    rollNo = (request.args.get('rollNo') or '').strip().upper()
    refresh = request.args.get('refresh', '').lower() == 'true'

    user, status_code, err = get_authenticated_student(request)
    if err:
        is_prod = os.getenv('FLASK_ENV', os.getenv('ENV', 'development')).lower() == 'production'
        has_auth_attempt = bool(request.headers.get('Authorization') or request.args.get('auth_token') or request.headers.get('X-Roll-No'))
        if is_prod or has_auth_attempt:
            return jsonify({"message": err}), status_code
        if not rollNo:
            return jsonify({"message": err}), status_code
    else:
        rollNo = user.get('rollNo')

    try:
        user = users_collection.find_one({"rollNo": rollNo})

        if not user:
            return jsonify({"message": "User not found."}), 404

        # If manual refresh requested, re-sync from both portals
        if refresh and user.get('password'):
            updated_doc, err = sync_student_dual_portal(rollNo, user['password'])
            if updated_doc:
                user = updated_doc

        sz1 = user.get('studzone1')
        if isinstance(sz1, dict) and not sz1.get('parsed_attendance'):
            prev_att, is_prev, _ = resolve_student_attendance_records(user)
            if prev_att:
                user['studzone1']['parsed_attendance'] = prev_att
                user['is_previous_attendance'] = True
                user['previous_parsed_attendance'] = prev_att

        if '_id' in user:
            user['_id'] = str(user['_id'])
        user.pop('password', None)
        user['auth_token'] = generate_auth_token(rollNo)
        if determine_residential_status:
            res_info = determine_residential_status(user)
            user['residential_status'] = res_info['status']
            user['is_hosteller'] = res_info['is_hosteller']
            user['is_day_scholar'] = res_info['is_day_scholar']
            user['can_access_hostel'] = res_info['can_access_hostel']
            user['room_number'] = res_info['room_number']
        return jsonify(user)

    except Exception as e:
        print(f"Error fetching profile: {str(e)}")
        return jsonify({"message": "Server error. Please try again later."}), 500


# Update notification preferences and/or email address
@app.route('/notifications', methods=['POST'])
@app.route('/api/notifications', methods=['POST'])
def update_notifications():
    data = request.get_json() or {}
    rollNo = (data.get('rollNo') or data.get('rollno') or '').strip().upper()
    notifications = data.get('notifications')
    email = (data.get('email') or '').strip()
    monitoring_enabled = data.get('monitoring_enabled')

    if not rollNo:
        return jsonify({"message": "Roll number is required."}), 400

    if users_collection is None:
        return jsonify({"message": "Database not connected."}), 500

    try:
        user = users_collection.find_one({"rollNo": rollNo})
        if not user:
            return jsonify({"message": "User not found."}), 404

        update_fields = {}
        changes_detected = []

        # Check email change
        old_email = (user.get('email') or '').strip()
        if email and email.lower() != old_email.lower():
            update_fields["email"] = email
            changes_detected.append(f"Notification email updated from {old_email or 'default'} to {email}")

        # Check monitoring toggle
        old_monitoring = user.get('monitoring_enabled', True)
        if monitoring_enabled is not None and bool(monitoring_enabled) != old_monitoring:
            update_fields["monitoring_enabled"] = bool(monitoring_enabled)
            changes_detected.append(f"Automated monitoring {'enabled' if monitoring_enabled else 'disabled'}")

        # Check notification categories
        if notifications is not None and isinstance(notifications, dict):
            old_notifs = user.get('notifications') or {}
            changed_channels = []
            for channel, state in notifications.items():
                if old_notifs.get(channel) != state:
                    changed_channels.append(f"{channel}: {'ON' if state else 'OFF'}")
            if changed_channels:
                changes_detected.append(f"Alert channels modified ({', '.join(changed_channels)})")
            update_fields["notifications"] = notifications

        if not update_fields:
            return jsonify({"message": "No settings changed.", "email": old_email or None}), 200

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        update_fields["settingsUpdatedAt"] = now_iso

        users_collection.update_one({"rollNo": rollNo}, {"$set": update_fields})

        # If settings were genuinely changed, log notification and dispatch confirmation email
        if changes_detected:
            recipient_email = email or old_email or f"{rollNo.lower()}@psgtech.ac.in"
            student_name = user.get('name', rollNo)
            title = "Account Settings Updated"
            change_summary = "; ".join(changes_detected)
            message = f"Your Student Sync account settings were updated on {now_iso[:19].replace('T', ' ')} UTC: {change_summary}."
            chash = compute_change_hash(rollNo, "preferences", "Settings", title, message, f"pref_{now_iso[:19]}")

            notif_doc = {
                "rollNo": rollNo,
                "studentRollNo": rollNo,
                "recipient_email": recipient_email,
                "category": "preferences",
                "type": "system",
                "title": title,
                "description": message,
                "message": message,
                "source": "Student Sync",
                "module": "Settings",
                "timestamp": now_iso,
                "createdAt": now_iso,
                "created_at": now,
                "updated_at": now,
                "read": False,
                "changeHash": chash,
                "changeData": {
                    "event": "settings_updated",
                    "changes": changes_detected,
                    "updatedAt": now_iso
                },
                "status": "pending",
                "error": None
            }

            notif_id = None
            if notifications_collection is not None:
                try:
                    res = notifications_collection.insert_one(notif_doc)
                    notif_id = res.inserted_id
                except DuplicateKeyError:
                    pass

            email_subject = "Student Sync — Notification Preferences & Settings Updated"
            items_html = "".join([f"<li style='margin-bottom: 6px; color: #e5e7eb;'>{item}</li>" for item in changes_detected])
            email_body = f"""
            <!DOCTYPE html>
            <html>
            <body style="margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0b0d13; color: #f3f4f6;">
              <div style="max-width: 520px; margin: 0 auto; background-color: #131620; border: 1px solid #232738; border-radius: 12px; padding: 24px;">
                <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #818cf8; font-weight: 600; margin-bottom: 6px;">
                  Account Notification • Settings Update
                </div>
                <h2 style="color: #ffffff; font-size: 18px; margin-top: 0; margin-bottom: 12px;">{title}</h2>
                <p style="color: #9ca3af; font-size: 13px; line-height: 1.5; margin-bottom: 14px;">
                  The following updates were applied to your Student Sync account:
                </p>
                <ul style="padding-left: 20px; font-size: 13px; line-height: 1.6; margin-bottom: 20px;">
                  {items_html}
                </ul>
                <div style="padding: 12px; border-radius: 8px; background-color: #181c2b; border: 1px solid #222738; font-size: 12px; color: #9ca3af; margin-bottom: 20px;">
                  Student: <strong style="color: #ffffff;">{student_name}</strong> (<span style="font-family: monospace; color: #c4b5fd;">{rollNo}</span>)<br/>
                  Primary Alert Email: <span style="font-family: monospace; color: #93c5fd;">{recipient_email}</span>
                </div>
                <div style="border-top: 1px solid #1c202e; padding-top: 14px; font-size: 11px; color: #6b7280; text-align: center;">
                  © 2026 Student Sync | Academic Notification Platform
                </div>
              </div>
            </body>
            </html>
            """
            try:
                queue_tracked_email(rollNo, recipient_email, "system", email_subject, email_body, notif_id=notif_id)
            except Exception as q_err:
                print(f"[SETTINGS EMAIL] Error queueing preferences email for {rollNo}: {q_err}")

        return jsonify({"message": "Settings updated successfully!", "email": email or old_email or None})

    except Exception as e:
        print(f"Error updating notifications: {str(e)}")
        return jsonify({"message": "Server error. Please try again later."}), 500


# Update StudZone Portal Password Route
@app.route('/update', methods=['POST'])
@app.route('/api/update', methods=['POST'])
def update_password():
    data = request.get_json() or {}
    rollNo = (data.get('rollno') or data.get('rollNo') or '').strip().upper()
    password = (data.get('password') or '').strip()

    if not rollNo or not password:
        return jsonify({"message": "Roll number and password are required."}), 400

    if users_collection is None:
        return jsonify({"message": "Database not connected."}), 500

    try:
        user = users_collection.find_one({"rollNo": rollNo})
        if not user:
            return jsonify({"message": "Student not found. Please verify roll number."}), 404

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        users_collection.update_one(
            {"rollNo": rollNo},
            {"$set": {"password": password, "passwordUpdatedAt": now_iso}}
        )

        recipient_email = (user.get('email') or '').strip() or f"{rollNo.lower()}@psgtech.ac.in"
        student_name = user.get('name', rollNo)

        title = "Security Alert: Portal Password Updated"
        message = f"Your StudZone portal password for account {rollNo} was updated successfully on {now_iso[:19].replace('T', ' ')} UTC."
        chash = compute_change_hash(rollNo, "security", "Security", title, message, f"pwd_{now_iso[:19]}")

        notif_doc = {
            "rollNo": rollNo,
            "studentRollNo": rollNo,
            "recipient_email": recipient_email,
            "category": "security",
            "type": "security",
            "title": title,
            "description": message,
            "message": message,
            "source": "Student Sync",
            "module": "Account Security",
            "timestamp": now_iso,
            "createdAt": now_iso,
            "created_at": now,
            "updated_at": now,
            "read": False,
            "changeHash": chash,
            "changeData": {
                "event": "password_updated",
                "timestamp": now_iso
            },
            "status": "pending",
            "error": None
        }

        notif_id = None
        if notifications_collection is not None:
            try:
                res = notifications_collection.insert_one(notif_doc)
                notif_id = res.inserted_id
            except DuplicateKeyError:
                pass

        email_subject = "Student Sync — Security Alert: Password Updated"
        email_body = f"""
        <!DOCTYPE html>
        <html>
        <body style="margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0b0d13; color: #f3f4f6;">
          <div style="max-width: 520px; margin: 0 auto; background-color: #131620; border: 1px solid #232738; border-radius: 12px; padding: 24px;">
            <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #f87171; font-weight: 600; margin-bottom: 6px;">
              Security Notification • Account Protection
            </div>
            <h2 style="color: #ffffff; font-size: 18px; margin-top: 0; margin-bottom: 12px;">{title}</h2>
            <p style="color: #e5e7eb; font-size: 14px; line-height: 1.6; margin-bottom: 16px;">
              {message}
            </p>
            <div style="padding: 12px; border-radius: 8px; background-color: #181c2b; border: 1px solid #222738; font-size: 12px; color: #9ca3af; margin-bottom: 20px;">
              Student: <strong style="color: #ffffff;">{student_name}</strong> (<span style="font-family: monospace; color: #c4b5fd;">{rollNo}</span>)<br/>
              Timestamp: <span style="color: #ffffff;">{now_iso[:19].replace('T', ' ')} UTC</span>
            </div>
            <p style="color: #9ca3af; font-size: 12px; margin-bottom: 16px;">
              If you initiated this change, no further action is required. If you did not update your password, please verify your account and contact your administrator immediately.
            </p>
            <div style="border-top: 1px solid #1c202e; padding-top: 14px; font-size: 11px; color: #6b7280; text-align: center;">
              © 2026 Student Sync | Security Team
            </div>
          </div>
        </body>
        </html>
        """
        try:
            queue_tracked_email(rollNo, recipient_email, "security", email_subject, email_body, notif_id=notif_id)
        except Exception as q_err:
            print(f"[SECURITY EMAIL] Error queueing password update email for {rollNo}: {q_err}")

        return jsonify({"message": "Password updated successfully!", "rollNo": rollNo}), 200

    except Exception as e:
        print(f"Error updating password: {e}")
        return jsonify({"message": "Server error. Please try again later."}), 500


@app.route('/send-message', methods=['POST'])
@app.route('/api/send-message', methods=['POST'])
def send_message():
    data = request.json or {}
    name = data.get('name')
    email = data.get('email')
    message = data.get('message')

    smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', 587))
    smtp_user = (os.getenv('SMTP_USER') or '').strip()
    raw_password = (os.getenv('SMTP_PASSWORD') or '').strip().strip('"').strip("'")
    smtp_password = raw_password.replace(" ", "")
    admin_email = (os.getenv('ADMIN_EMAIL') or '').strip()

    if not smtp_user or not smtp_password or not admin_email:
        return jsonify({'error': 'SMTP or admin email not configured on server.'}), 500

    msg = MIMEMultipart()
    msg['From'] = smtp_user
    msg['To'] = admin_email
    msg['Subject'] = f'Message from {name}'

    body = f'Name: {name}\nEmail: {email}\nMessage: {message}'
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

        return jsonify({'message': 'Email sent successfully!'}), 200
    except Exception as e:
        print(f"Error sending contact message: {e}")
        return jsonify({'error': 'Failed to send message via email.'}), 500


# =========================================================================
# ATTENDANCE & BUNK PLANNER APIS (PHASE 2)
# =========================================================================

@app.route('/attendance/summary', methods=['GET'])
@app.route('/api/attendance/summary', methods=['GET'])
def attendance_summary():
    """
    Returns the authenticated student's overall attendance aggregation,
    subject-wise breakdown with safe bunks and recovery requirements,
    and today's class lecture schedule.
    Enforces user isolation: students can only access their own records.
    """
    user, status_code, err = get_authenticated_student(request)
    if err:
        return jsonify({"error": err}), status_code

    roll_no = user.get('rollNo', '')
    try:
        raw_target = request.args.get('target', 75.0)
        target = float(raw_target)
        if target <= 0.0 or target >= 100.0:
            target = 75.0
    except (ValueError, TypeError):
        target = 75.0

    # Support manual refresh on demand from attendance dashboard
    refresh = request.args.get('refresh', '').lower() == 'true'
    if refresh and user.get('password'):
        try:
            updated_doc, err = sync_student_dual_portal(roll_no, user['password'])
            if updated_doc:
                user = updated_doc
        except Exception as sync_err:
            print(f"[ATTENDANCE REFRESH] Error: {sync_err}")

    studzone1 = user.get('studzone1', {})
    parsed_attendance, is_previous_data, is_updating = resolve_student_attendance_records(user)
    class_schedule = studzone1.get('class_schedule', [])
    class_timetable_html = studzone1.get('class_timetable_html', '')

    # 1. Calculate overall summary & subject breakdown (read-only, resolving student-specific course titles)
    summary = summarize_student_attendance(parsed_attendance, target=target, user_doc=user)

    # 2. Parse today's classroom lecture schedule matching day
    day_query = request.args.get('day')
    today_schedule = parse_daily_schedule(class_schedule, day_name=day_query, class_timetable_html=class_timetable_html)

    response_payload = {
        "rollNo": roll_no,
        "name": user.get('name', roll_no),
        "total_attended": summary["overall"]["attended"],
        "total_conducted": summary["overall"]["conducted"],
        "overall_percentage": summary["overall"]["percentage"],
        "overall_status": summary["overall"]["status"],
        "overall_safe_bunks": summary["overall"]["safe_bunks"],
        "overall_required_classes": summary["overall"]["required_classes"],
        "target": target,
        "subjects": summary["subjects"],
        "counts": summary["counts"],
        "today_schedule": today_schedule,
        "last_synced": user.get("last_synced_studzone1") or user.get("lastSyncedAt"),
        "is_previous_data": is_previous_data,
        "is_updating": is_updating
    }

    return jsonify(response_payload), 200


@app.route('/attendance/simulate', methods=['POST'])
@app.route('/api/attendance/simulate', methods=['POST'])
def attendance_simulate():
    """
    Interactive in-memory attendance simulator.
    Evaluates hypothetical future classes attended or missed for a given subject.
    Operates strictly in-memory: NEVER mutates MongoDB or official baselines.
    """
    user, status_code, err = get_authenticated_student(request)
    if err:
        return jsonify({"error": err}), status_code

    if not request.is_json:
        return jsonify({"error": "Malformed request. JSON body required."}), 400

    data = request.get_json() or {}
    subject_code = str(data.get('subject_code', '')).strip().upper()
    if not subject_code:
        return jsonify({"error": "Missing required field: 'subject_code'."}), 400

    # Parse and validate numerical inputs
    try:
        raw_att = data.get('additional_attended', 0)
        raw_bunk = data.get('additional_bunked', 0)
        raw_target = data.get('target', 75.0)

        if not isinstance(raw_att, (int, float)) or not isinstance(raw_bunk, (int, float)):
            return jsonify({"error": "'additional_attended' and 'additional_bunked' must be numbers."}), 400

        add_att = int(raw_att)
        add_bunk = int(raw_bunk)

        if add_att < 0 or add_bunk < 0:
            return jsonify({"error": "Values for 'additional_attended' and 'additional_bunked' cannot be negative."}), 400

        target = float(raw_target)
        if target <= 0.0 or target >= 100.0:
            return jsonify({"error": "'target' must be a valid percentage between 1 and 99.9."}), 400

    except (ValueError, TypeError):
        return jsonify({"error": "Invalid numerical parameters."}), 400

    studzone1 = user.get('studzone1', {})
    parsed_attendance, _, _ = resolve_student_attendance_records(user)

    matched_subj = None
    for subj in parsed_attendance:
        if str(subj.get('code', '')).strip().upper() == subject_code:
            matched_subj = subj
            break

    if not matched_subj:
        return jsonify({"error": f"Subject '{subject_code}' not found in your registered attendance records."}), 404

    try:
        orig_att = int(float(matched_subj.get('attended', 0)))
        orig_cond = int(float(matched_subj.get('total_classes', matched_subj.get('conducted', 0))))
    except (ValueError, TypeError):
        orig_att, orig_cond = 0, 0

    # Pure in-memory calculation: NEVER writes to MongoDB
    sim_result = calculate_simulated_attendance(
        attended=orig_att,
        conducted=orig_cond,
        additional_attended=add_att,
        additional_bunked=add_bunk,
        target=target
    )

    response_payload = {
        "subject_code": subject_code,
        "subject_name": matched_subj.get('name', subject_code),
        "target": target,
        "original_attendance": {
            "attended": sim_result["initial"]["attended"],
            "conducted": sim_result["initial"]["conducted"],
            "percentage": sim_result["initial"]["percentage"],
            "status": sim_result["initial"]["status"],
            "safe_bunks": sim_result["initial"]["safe_bunks"],
            "required_classes": sim_result["initial"]["required_classes"]
        },
        "original": {
            "attended": sim_result["initial"]["attended"],
            "conducted": sim_result["initial"]["conducted"],
            "percentage": sim_result["initial"]["percentage"],
            "status": sim_result["initial"]["status"],
            "safe_bunks": sim_result["initial"]["safe_bunks"],
            "required_classes": sim_result["initial"]["required_classes"]
        },
        "simulated_attended": sim_result["simulation"]["attended"],
        "simulated_conducted": sim_result["simulation"]["conducted"],
        "simulated_percentage": sim_result["simulation"]["percentage"],
        "simulated_status": sim_result["simulation"]["status"],
        "simulated_safe_bunks": sim_result["simulation"]["safe_bunks"],
        "simulated_required_classes": sim_result["simulation"]["required_classes"],
        "simulated": {
            "additional_attended": add_att,
            "additional_bunked": add_bunk,
            "attended": sim_result["simulation"]["attended"],
            "conducted": sim_result["simulation"]["conducted"],
            "percentage": sim_result["simulation"]["percentage"],
            "status": sim_result["simulation"]["status"],
            "safe_bunks": sim_result["simulation"]["safe_bunks"],
            "required_classes": sim_result["simulation"]["required_classes"],
            "percentage_change": sim_result["simulation"]["percentage_change"]
        }
    }

    return jsonify(response_payload), 200


# =========================================================================
# ACADEMIC MARKS & WHAT-IF CGPA SIMULATOR APIS (PHASE 5)
# =========================================================================

@app.route('/academic/marks-summary', methods=['GET'])
@app.route('/api/academic/marks-summary', methods=['GET'])
def academic_marks_summary():
    """
    Returns the authenticated student's Continuous Assessment (CA) breakdown
    across theory, lab, project, and audit courses, along with historical
    semester examination results, earned credits, grade distribution, and verified CGPA.
    Enforces user isolation: students can only access their own records.
    """
    user, status_code, err = get_authenticated_student(request)
    if err:
        return jsonify({"error": err}), status_code

    summary = summarize_student_academics(user)
    return jsonify(summary), 200


@app.route('/academic/cgpa-simulate', methods=['POST'])
@app.route('/api/academic/cgpa-simulate', methods=['POST'])
def academic_cgpa_simulate():
    """
    Interactive in-memory What-If CGPA simulator.
    Evaluates projected cumulative GPA when hypothetical courses, credits,
    and grades are introduced against the verified baseline.
    Operates strictly in-memory: NEVER mutates MongoDB, academic records, or CGPA.
    """
    user, status_code, err = get_authenticated_student(request)
    if err:
        return jsonify({"error": err}), status_code

    if not request.is_json:
        return jsonify({"error": "Malformed request. JSON body required."}), 400

    data = request.get_json() or {}
    simulated_courses = data.get('simulated_courses', [])
    if not isinstance(simulated_courses, list):
        return jsonify({"error": "'simulated_courses' must be a list of course specifications."}), 400

    user_academics = summarize_student_academics(user)
    base_credits = data.get('base_credits', user_academics.get('base_credits', 0.0))
    base_cgpa = data.get('base_cgpa', user_academics.get('base_cgpa', 0.0))

    try:
        sim_result = simulate_projected_cgpa(
            base_credits=base_credits,
            base_cgpa=base_cgpa,
            simulated_courses=simulated_courses
        )
        return jsonify(sim_result), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": f"Simulation failed: {str(e)}"}), 500


# =========================================================================
# TIMETABLE INTELLIGENCE, EXAM PLANNER & DAY-BUNK SIMULATOR APIS (PHASE 6)
# =========================================================================

@app.route('/schedule/weekly', methods=['GET'])
@app.route('/api/schedule/weekly', methods=['GET'])
def schedule_weekly():
    """
    Returns the authenticated student's full Monday-Friday weekly class schedule
    matrix with period numbers, timings, course codes, course titles, section tags,
    and free period indicators.
    Enforces user isolation: students can only access their own schedule.
    """
    user, status_code, err = get_authenticated_student(request)
    if err:
        return jsonify({"error": err}), status_code

    studzone1 = user.get('studzone1', {})
    class_schedule = studzone1.get('class_schedule', [])
    class_timetable_html = studzone1.get('class_timetable_html', '')
    parsed = parse_weekly_schedule_matrix(class_schedule, class_timetable_html=class_timetable_html)
    parsed["rollNo"] = user.get('rollNo')
    return jsonify(parsed), 200


@app.route('/schedule/exams', methods=['GET'])
@app.route('/api/schedule/exams', methods=['GET'])
def schedule_exams():
    """
    Returns the authenticated student's end-semester examination timetable
    and official CoE examination circulars.
    Preserves exact official portal status (e.g. 'Schedule Pending', 'TBA')
    without fabricating or guessing exam dates.
    Enforces user isolation: students can only access their own records.
    """
    user, status_code, err = get_authenticated_student(request)
    if err:
        return jsonify({"error": err}), status_code

    studzone2 = user.get('studzone2', {})
    parsed_timetable = studzone2.get('parsed_timetable', [])
    circulars = studzone2.get('circulars', [])
    parsed = parse_exam_schedule_records(parsed_timetable, circulars)
    parsed["rollNo"] = user.get('rollNo')
    return jsonify(parsed), 200


@app.route('/schedule/day-bunk-simulate', methods=['POST'])
@app.route('/api/schedule/day-bunk-simulate', methods=['POST'])
def schedule_day_bunk_simulate():
    """
    Interactive in-memory Day-Bunk Simulator:
    Evaluates attendance percentage and safe-bunk shifts when a student
    bunks selected class periods on a given weekday.
    Strictly in-memory: NEVER writes or modifies MongoDB documents.
    """
    user, status_code, err = get_authenticated_student(request)
    if err:
        return jsonify({"error": err}), status_code

    if not request.is_json:
        return jsonify({"error": "Malformed request. JSON body required."}), 400

    data = request.get_json() or {}
    day = data.get('day')
    if not day or not isinstance(day, str):
        return jsonify({"error": "Missing or invalid required field: 'day'."}), 400

    periods = data.get('periods')
    if periods is not None and not isinstance(periods, list):
        return jsonify({"error": "'periods' must be a list of integer period numbers."}), 400

    try:
        raw_target = data.get('target', 75.0)
        target = float(raw_target)
        if target <= 0.0 or target >= 100.0:
            return jsonify({"error": "'target' must be a valid percentage between 1.0 and 99.9."}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid target percentage value."}), 400

    studzone1 = user.get('studzone1', {})
    parsed_attendance, _, _ = resolve_student_attendance_records(user)
    class_schedule = studzone1.get('class_schedule', [])
    class_timetable_html = studzone1.get('class_timetable_html', '')

    try:
        sim_result = simulate_day_bunks(
            parsed_attendance_list=parsed_attendance,
            class_schedule_matrix=class_schedule,
            day=day,
            periods=periods,
            target=target,
            class_timetable_html=class_timetable_html
        )
        return jsonify(sim_result), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": f"Day bunk simulation failed: {str(e)}"}), 500


@app.route('/courses/unified-summary', methods=['GET'])
@app.route('/api/courses/unified-summary', methods=['GET'])
def courses_unified_summary():
    """
    Returns a unified subject intelligence overview combining Attendance,
    CA Marks, Weekly Schedule Slots, and Exam Status per registered course.
    Operates strictly read-only and in-memory.
    """
    user, status_code, err = get_authenticated_student(request)
    if err:
        return jsonify({"error": err}), status_code

    unified = get_unified_subject_summary(user)
    unified["rollNo"] = user.get('rollNo')
    return jsonify(unified), 200


@app.route('/planner/intelligence', methods=['GET'])
@app.route('/api/planner/intelligence', methods=['GET'])
def planner_intelligence():
    """
    Returns personalized cross-module academic intelligence, combining
    Attendance, Timetable, CA Marks, Historical Results, CGPA, and Exam Schedule.
    Supports optional ?day=<Weekday> query parameter to inspect any weekday.
    Operates strictly read-only and in-memory (ZERO database writes).
    """
    user, status_code, err = get_authenticated_student(request)
    if err:
        return jsonify({"error": err}), status_code

    target_day = request.args.get('day')
    intelligence = synthesize_academic_planner(user, target_day=target_day)
    return jsonify(intelligence), 200


@app.route('/campus-services/overview', methods=['GET'])
@app.route('/api/campus-services/overview', methods=['GET'])
@app.route('/services/overview', methods=['GET'])
@app.route('/api/services/overview', methods=['GET'])
def campus_services_overview():
    """
    Returns normalized Campus Services & Student Dossier Hub data:
    - Student Identity Dossier
    - Institutional Fee Ledger
    - Hostel & Accommodation Records
    - Scholarships Summary (Applied vs Received/Disbursed distinct)
    - Course & Institutional Feedback Cycles
    Operates strictly read-only and in-memory (ZERO database writes).
    """
    user, status_code, err = get_authenticated_student(request)
    if err:
        return jsonify({"error": err}), status_code

    try:
        from services_calculator import synthesize_campus_services
    except ImportError:
        from backend.services_calculator import synthesize_campus_services

    return jsonify(synthesize_campus_services(user)), 200

# =========================================================================
# Standalone Hostel Subsystem API Endpoints (/api/v1/hostel)
# =========================================================================
try:
    from hostel_service import hostel_service
except ImportError:
    try:
        from backend.hostel_service import hostel_service
    except ImportError:
        hostel_service = None

try:
    from residential_service import (
        determine_residential_status,
        STATUS_HOSTELLER,
        STATUS_DAY_SCHOLAR,
        STATUS_UNKNOWN,
    )
except ImportError:
    try:
        from backend.residential_service import (
            determine_residential_status,
            STATUS_HOSTELLER,
            STATUS_DAY_SCHOLAR,
            STATUS_UNKNOWN,
        )
    except ImportError:
        determine_residential_status = None
        STATUS_HOSTELLER = "HOSTELLER"
        STATUS_DAY_SCHOLAR = "DAY_SCHOLAR"
        STATUS_UNKNOWN = "UNKNOWN"


def check_hostel_authorization(user, target_rollno=None):
    """
    Enforces two-tier backend authorization for hostel records:
    1. Identity verification: Student A cannot access Student B's data (anti-IDOR).
    2. Residential eligibility: Day scholars and unknown/unverified statuses are strictly forbidden.
    Returns: (is_authorized, error_response, status_code)
    """
    auth_roll = (user.get('rollNo') or '').strip().upper()
    if target_rollno:
        req_roll = target_rollno.strip().upper()
        if auth_roll != req_roll:
            return False, jsonify({
                "success": False,
                "error": "Forbidden: You are not authorized to view another student's hostel records."
            }), 403

    if determine_residential_status:
        res_status = determine_residential_status(user)
        if res_status["status"] == STATUS_DAY_SCHOLAR:
            return False, jsonify({
                "success": False,
                "error": "Forbidden: Access Denied. You are registered as a Day Scholar. Hostel services are exclusively available to verified hostel residents.",
                "residential_status": res_status["status"],
                "can_access_hostel": False
            }), 403
        elif res_status["status"] != STATUS_HOSTELLER:
            return False, jsonify({
                "success": False,
                "error": "Forbidden: Access Denied. Your residential eligibility could not be verified from institutional records. Please refresh your profile or contact campus administration.",
                "residential_status": res_status["status"],
                "can_access_hostel": False
            }), 403

    return True, None, 200


@app.route('/api/v1/hostel/status', methods=['GET'])
@app.route('/api/hostel/status', methods=['GET'])
@app.route('/v1/hostel/status', methods=['GET'])
@app.route('/hostel/status', methods=['GET'])
@app.route('/api/v1/student/residential-status', methods=['GET'])
@app.route('/api/student/residential-status', methods=['GET'])
@app.route('/v1/student/residential-status', methods=['GET'])
@app.route('/student/residential-status', methods=['GET'])
def hostel_residential_status():
    """
    Returns the verified residential status of the authenticated student
    derived strictly from StudZone 1 portal records.
    Never defaults to HOSTELLER for missing or unverified data.
    """
    user, status_code, err = get_authenticated_student(request)
    if err:
        return jsonify({"success": False, "error": err}), status_code

    auth_roll = (user.get('rollNo') or '').strip().upper()
    if not determine_residential_status:
        return jsonify({"success": False, "error": "Residential status service not available."}), 503

    res_status = determine_residential_status(user)
    return jsonify({
        "success": True,
        "rollNo": auth_roll,
        "status": res_status["status"],
        "isHosteller": res_status["is_hosteller"],
        "isDayScholar": res_status["is_day_scholar"],
        "canAccessHostel": res_status["can_access_hostel"],
        "roomNumber": res_status["room_number"],
        "verifiedSource": res_status["verified_source"],
        "rawStatus": res_status["raw_status"]
    }), 200


@app.route('/api/v1/hostel/student/<rollno>', methods=['GET'])
@app.route('/api/hostel/student/<rollno>', methods=['GET'])
@app.route('/v1/hostel/student/<rollno>', methods=['GET'])
@app.route('/hostel/student/<rollno>', methods=['GET'])
@app.route('/api/v1/hostel/student/<rollno>/summary', methods=['GET'])
@app.route('/api/hostel/student/<rollno>/summary', methods=['GET'])
@app.route('/v1/hostel/student/<rollno>/summary', methods=['GET'])
@app.route('/hostel/student/<rollno>/summary', methods=['GET'])
def hostel_student_summary(rollno):
    """
    Returns complete normalized hostel records for an authenticated resident.
    Enforces student isolation and residential eligibility.
    """
    user, status_code, err = get_authenticated_student(request)
    if err:
        return jsonify({"success": False, "error": err}), status_code

    is_auth, auth_err, auth_status = check_hostel_authorization(user, target_rollno=rollno)
    if not is_auth:
        return auth_err, auth_status

    if not hostel_service:
        return jsonify({"success": False, "error": "Hostel service not available."}), 503

    req_roll = rollno.strip().upper()
    refresh = request.args.get('refresh', '').lower() == 'true'
    res, status, err_msg = hostel_service.get_student_hostel_overview(
        roll_number=req_roll,
        force_refresh=refresh,
        password=user.get('password')
    )
    if err_msg:
        return jsonify({"success": False, "error": err_msg}), status
    return jsonify(res), 200


@app.route('/api/v1/hostel/student/<rollno>/room', methods=['GET'])
@app.route('/api/hostel/student/<rollno>/room', methods=['GET'])
@app.route('/v1/hostel/student/<rollno>/room', methods=['GET'])
@app.route('/hostel/student/<rollno>/room', methods=['GET'])
def hostel_student_room(rollno):
    """Returns room allocation and warden oversight for authenticated resident."""
    user, status_code, err = get_authenticated_student(request)
    if err:
        return jsonify({"success": False, "error": err}), status_code

    is_auth, auth_err, auth_status = check_hostel_authorization(user, target_rollno=rollno)
    if not is_auth:
        return auth_err, auth_status

    if not hostel_service:
        return jsonify({"success": False, "error": "Hostel service not available."}), 503

    req_roll = rollno.strip().upper()
    refresh = request.args.get('refresh', '').lower() == 'true'
    res, status, err_msg = hostel_service.get_student_room(
        roll_number=req_roll,
        force_refresh=refresh,
        password=user.get('password')
    )
    if err_msg:
        return jsonify({"success": False, "error": err_msg}), status
    return jsonify(res), 200


@app.route('/api/v1/hostel/student/<rollno>/mess', methods=['GET'])
@app.route('/api/hostel/student/<rollno>/mess', methods=['GET'])
@app.route('/v1/hostel/student/<rollno>/mess', methods=['GET'])
@app.route('/hostel/student/<rollno>/mess', methods=['GET'])
def hostel_student_mess(rollno):
    """Returns mess subscription and token authorizations for authenticated resident."""
    user, status_code, err = get_authenticated_student(request)
    if err:
        return jsonify({"success": False, "error": err}), status_code

    is_auth, auth_err, auth_status = check_hostel_authorization(user, target_rollno=rollno)
    if not is_auth:
        return auth_err, auth_status

    if not hostel_service:
        return jsonify({"success": False, "error": "Hostel service not available."}), 503

    req_roll = rollno.strip().upper()
    refresh = request.args.get('refresh', '').lower() == 'true'
    res, status, err_msg = hostel_service.get_student_mess(
        roll_number=req_roll,
        force_refresh=refresh,
        password=user.get('password')
    )
    if err_msg:
        return jsonify({"success": False, "error": err_msg}), status
    return jsonify(res), 200


@app.route('/api/v1/hostel/student/<rollno>/fees', methods=['GET'])
@app.route('/api/hostel/student/<rollno>/fees', methods=['GET'])
@app.route('/v1/hostel/student/<rollno>/fees', methods=['GET'])
@app.route('/hostel/student/<rollno>/fees', methods=['GET'])
def hostel_student_fees(rollno):
    """Returns hostel fee balance, deposits, and pending dues for authenticated resident."""
    user, status_code, err = get_authenticated_student(request)
    if err:
        return jsonify({"success": False, "error": err}), status_code

    is_auth, auth_err, auth_status = check_hostel_authorization(user, target_rollno=rollno)
    if not is_auth:
        return auth_err, auth_status

    if not hostel_service:
        return jsonify({"success": False, "error": "Hostel service not available."}), 503

    req_roll = rollno.strip().upper()
    refresh = request.args.get('refresh', '').lower() == 'true'
    res, status, err_msg = hostel_service.get_student_fees(
        roll_number=req_roll,
        force_refresh=refresh,
        password=user.get('password')
    )
    if err_msg:
        return jsonify({"success": False, "error": err_msg}), status
    return jsonify(res), 200


@app.route('/api/v1/hostel/student/<rollno>/leave', methods=['GET'])
@app.route('/api/hostel/student/<rollno>/leave', methods=['GET'])
@app.route('/v1/hostel/student/<rollno>/leave', methods=['GET'])
@app.route('/hostel/student/<rollno>/leave', methods=['GET'])
def hostel_student_leave(rollno):
    """Returns leave quotas, designated approvers, and application history for authenticated resident."""
    user, status_code, err = get_authenticated_student(request)
    if err:
        return jsonify({"success": False, "error": err}), status_code

    is_auth, auth_err, auth_status = check_hostel_authorization(user, target_rollno=rollno)
    if not is_auth:
        return auth_err, auth_status

    if not hostel_service:
        return jsonify({"success": False, "error": "Hostel service not available."}), 503

    req_roll = rollno.strip().upper()
    refresh = request.args.get('refresh', '').lower() == 'true'
    res, status, err_msg = hostel_service.get_student_leave(
        roll_number=req_roll,
        force_refresh=refresh,
        password=user.get('password')
    )
    if err_msg:
        return jsonify({"success": False, "error": err_msg}), status
    return jsonify(res), 200


@app.route('/api/v1/hostel/overview', methods=['GET'])
@app.route('/api/hostel/overview', methods=['GET'])
@app.route('/v1/hostel/overview', methods=['GET'])
@app.route('/hostel/overview', methods=['GET'])
def hostel_authenticated_overview():
    """Convenience endpoint returning the authenticated student's own hostel records."""
    user, status_code, err = get_authenticated_student(request)
    if err:
        return jsonify({"success": False, "error": err}), status_code

    is_auth, auth_err, auth_status = check_hostel_authorization(user)
    if not is_auth:
        return auth_err, auth_status

    auth_roll = (user.get('rollNo') or '').strip().upper()
    if not hostel_service:
        return jsonify({"success": False, "error": "Hostel service not available."}), 503

    refresh = request.args.get('refresh', '').lower() == 'true'
    res, status, err_msg = hostel_service.get_student_hostel_overview(
        roll_number=auth_roll,
        force_refresh=refresh,
        password=user.get('password')
    )
    if err_msg:
        return jsonify({"success": False, "error": err_msg}), status
    return jsonify(res), 200




# =========================================================================
# Chatbot & Interactive Academic Navigator Engine
# =========================================================================
try:
    from chatbot import process_chatbot_query
except ImportError:
    from backend.chatbot import process_chatbot_query

@app.route('/api/chat', methods=['POST'])
@app.route('/api/chatbot', methods=['POST'])
@app.route('/chat', methods=['POST'])
@app.route('/chatbot', methods=['POST'])
def chatbot_endpoint():
    """
    Intelligent Assistant & Page Navigator for Student Sync.
    Accepts student query, resolves intent, retrieves live/stored student academic details,
    calculates bunks and percentages, and provides direct page navigation deep-links.
    """
    if not request.is_json:
        return jsonify({"error": "Malformed request. JSON body required."}), 400

    data = request.get_json() or {}
    message = str(data.get('message') or data.get('query') or '').strip()
    if not message:
        return jsonify({"error": "Message cannot be empty."}), 400

    # Extract roll number from auth session or request payload
    roll_no = None
    user, status_code, err = get_authenticated_student(request)
    if user:
        roll_no = user.get('rollNo')
    else:
        # Fallback to rollNo in body or X-Roll-No header
        roll_no = data.get('rollNo') or request.headers.get('X-Roll-No')

    if not roll_no:
        return jsonify({
            "reply": "Hi! Please log in with your PSG Tech roll number so I can fetch your personalized attendance, marks, and timetable. How can I help you navigate?",
            "intent": "unauthenticated",
            "navigation": {"path": "/login", "label": "Go to Login Page →"},
            "suggestions": ["Take me to Login", "How do I register?", "What is Student Sync?"]
        }), 200

    history = data.get('history', [])
    response = process_chatbot_query(message, roll_no, conversation_history=history)
    return jsonify(response), 200


@app.route('/health', methods=['GET'])
@app.route('/api/health', methods=['GET'])
def health_check():
    """Safe system and service health check endpoint."""
    is_db_connected = False
    if client is not None and db is not None:
        try:
            client.admin.command('ping')
            is_db_connected = True
        except Exception:
            is_db_connected = False

    return jsonify({
        "status": "healthy" if is_db_connected else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "database": "connected" if is_db_connected else "disconnected",
        "services": {
            "studzone1": "operational",
            "studzone2": "operational",
            "hostel": "operational" if hostel_service is not None else "unavailable",
            "chatbot": "operational"
        }
    }), 200


if __name__ == "__main__":
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '127.0.0.1')
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() in ('true', '1', 'yes')
    app.run(debug=debug_mode, use_reloader=False, port=port, host=host)

