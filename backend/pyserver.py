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
CORS(app, supports_credentials=True)  

MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DB_NAME', 'ecampus')
USERS_COLLECTION = os.getenv('USERS_COLLECTION', 'new_users')

client = MongoClient(
    MONGO_URI,
    connectTimeoutMS=30000,
    socketTimeoutMS=30000,
    serverSelectionTimeoutMS=30000,
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
        summarize_student_attendance
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
        summarize_student_attendance
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
    existing_user = users_collection.find_one({"rollNo": rollNo}) if users_collection is not None else None
    existing_notifications = existing_user.get('notifications') if existing_user else None

    sync_status = {
        "profile": {"status": "synced", "timestamp": now_iso, "portal": "StudZone 1"},
        "attendance": {"status": "synced" if sz1_data.get("attendance_html") else "no_data", "timestamp": now_iso, "portal": "StudZone 1"},
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

    if users_collection is not None:
        users_collection.update_one(
            {"rollNo": rollNo},
            {"$set": merged_user},
            upsert=True
        )
        saved_doc = users_collection.find_one({"rollNo": rollNo})
        return saved_doc, None

    return merged_user, None


@app.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    rollNo = (data.get('rollNo') or '').strip().upper()
    password = (data.get('password') or '').strip()
    custom_email = (data.get('email') or '').strip()

    if not rollNo or not password:
        return jsonify({"message": "Invalid credentials. Please check your roll number and password."}), 400

    try:
        # 1. Check whether student is genuinely new BEFORE creating/upserting the MongoDB user
        existing_user_doc = users_collection.find_one({"rollNo": rollNo}) if users_collection is not None else None
        is_new_registration = existing_user_doc is None

        now_iso = datetime.now(timezone.utc).isoformat()
        student_email = custom_email or (existing_user_doc.get('email') if existing_user_doc else None) or f"{rollNo.lower()}@psgtech.ac.in"

        # Step 1: Save user placeholder with uninitialized baseline to prevent race condition.
        # If the background synchronizer runs concurrently while portal authentication and scraping occur,
        # baseline_initialized: False and monitoring_enabled: False guarantee the worker skips this user.
        if is_new_registration and users_collection is not None:
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
        elif not is_new_registration:
            print(f"[REGISTRATION] Existing student re-authenticating/updating: {rollNo}")

        # Step 2 & 3: Authenticate with portals and scrape current academic data
        user_doc, err = sync_student_dual_portal(rollNo, password)
        if err or not user_doc:
            if is_new_registration and users_collection is not None:
                # Clean up uninitialized placeholder if authentication fails
                users_collection.delete_one({"rollNo": rollNo, "baseline_initialized": False})
            return jsonify({"message": err or "Invalid credentials. Please check your roll number and password."}), 401

        # Step 4 & 5: Store initial baseline and Mark monitoring active
        # sync_student_dual_portal has stored the scraped data as the baseline,
        # set sync timestamps, baseline_initialized=True, and monitoring_enabled=True.
        if custom_email and users_collection is not None:
            users_collection.update_one({"rollNo": rollNo}, {"$set": {"email": custom_email}})
            user_doc["email"] = custom_email

        student_name = user_doc.get('name', rollNo)
        first_name = student_name.split()[0].capitalize() if student_name else rollNo
        student_email = user_doc.get('email') or student_email
        admin_email = os.getenv("ADMIN_EMAIL", "studentsync12@gmail.com").strip()

        # Step 6: Send exactly ONE welcome email to that user's registered email address
        # Store persistent flag welcomeEmailSent: True
        already_sent = bool(existing_user_doc and existing_user_doc.get('welcomeEmailSent')) or bool(user_doc.get('welcomeEmailSent'))
        if is_new_registration and not already_sent and notifications_collection is not None:
            try:
                # A. Welcome Email
                welcome_hash = compute_change_hash(rollNo, "welcome", "Account", "Welcome to Student Sync 🎓", f"welcome_{rollNo}")
                existing_welcome = notifications_collection.find_one({
                    "changeHash": welcome_hash
                })

                if not existing_welcome:
                    welcome_title = "Welcome to Student Sync 🎓"
                    welcome_msg = f"Thank you for registering with Student Sync, {first_name}! Student Sync monitoring is now active for your account."
                    now_utc = datetime.now(timezone.utc)
                    welcome_doc = {
                        "rollNo": rollNo,
                        "studentRollNo": rollNo,
                        "recipient_email": student_email,
                        "category": "welcome",
                        "type": "welcome",
                        "title": welcome_title,
                        "description": welcome_msg,
                        "message": welcome_msg,
                        "source": "Student Sync",
                        "module": "Account",
                        "timestamp": now_iso,
                        "createdAt": now_iso,
                        "created_at": now_utc,
                        "updated_at": now_utc,
                        "read": False,
                        "changeHash": welcome_hash,
                        "changeData": {
                            "event": "welcome",
                            "studentName": student_name,
                            "rollNo": rollNo,
                            "studentEmail": student_email
                        },
                        "status": "pending",
                        "error": None
                    }
                    try:
                        res_welcome = notifications_collection.insert_one(welcome_doc)
                    except DuplicateKeyError:
                        print(f"[REGISTRATION] Duplicate welcome notification suppressed by unique index for {rollNo}")
                        res_welcome = None

                    if res_welcome:
                        welcome_subject = "Welcome to Student Sync 🎓"
                        welcome_body = f"""
                        <!DOCTYPE html>
                        <html>
                        <body style="margin: 0; padding: 24px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0b0d13; color: #f3f4f6;">
                          <div style="max-width: 560px; margin: 0 auto; background-color: #131620; border: 1px solid #232738; border-radius: 12px; padding: 28px;">
                            <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #a78bfa; font-weight: 600; margin-bottom: 6px;">
                              Student Sync • Registration Confirmation
                            </div>
                            <h2 style="color: #ffffff; font-size: 20px; margin-top: 0; margin-bottom: 12px;">Welcome to Student Sync 🎓</h2>
                            <p style="color: #9ca3af; font-size: 14px; line-height: 1.6; margin-bottom: 16px;">
                              Hi <strong style="color: #ffffff;">{student_name}</strong> (<span style="font-family: monospace; color: #c4b5fd;">{rollNo}</span>),
                            </p>
                            <p style="color: #9ca3af; font-size: 14px; line-height: 1.6; margin-bottom: 16px;">
                              Thank you for registering with Student Sync! Student Sync monitoring is now active for your account.
                            </p>
                            <p style="color: #9ca3af; font-size: 14px; line-height: 1.6; margin-bottom: 20px;">
                              We have created your initial monitoring baseline from your current StudZone 1 and StudZone 2 academic records. You will receive real-time, user-specific notifications directly to this email address whenever genuine updates occur for your attendance, CA marks, exam timetable, seat allocations, fees, or semester results.
                            </p>
                            <div style="padding: 14px; border-radius: 8px; background-color: #181c2b; border: 1px solid #222738; font-size: 13px; color: #9ca3af; margin-bottom: 20px;">
                              <div style="margin-bottom: 4px;"><strong style="color: #ffffff;">Monitoring Status:</strong> <span style="color: #34d399;">Active & Synchronized</span></div>
                              <div><strong style="color: #ffffff;">Notification Email:</strong> <span style="font-family: monospace; color: #93c5fd;">{student_email}</span></div>
                            </div>
                            <div style="border-top: 1px solid #1c202e; padding-top: 16px; font-size: 12px; color: #6b7280; text-align: center;">
                              © 2026 Student Sync | PSG College of Technology
                            </div>
                          </div>
                        </body>
                        </html>
                        """
                        print(f"[EMAIL] Welcome recipient: {student_email}")
                        w_success, w_err = send_email_direct(student_email, welcome_subject, welcome_body, rollNo=rollNo, notif_type="welcome", notif_id=res_welcome.inserted_id)
                        if w_success:
                            print(f"[EMAIL] Welcome send result: SUCCESS")
                        else:
                            print(f"[EMAIL] Welcome send result: FAILED ({w_err})")

                    # Set persistent flag welcomeEmailSent: True on the user document
                    if users_collection is not None:
                        users_collection.update_one({"rollNo": rollNo}, {"$set": {"welcomeEmailSent": True, "welcome_email_sent_at": now_iso}})
                        user_doc["welcomeEmailSent"] = True
                else:
                    print(f"[EMAIL] Welcome email already sent for {rollNo}; skipping duplicate.")
                    if users_collection is not None:
                        users_collection.update_one({"rollNo": rollNo}, {"$set": {"welcomeEmailSent": True}})
                        user_doc["welcomeEmailSent"] = True
            except Exception as w_err:
                print(f"[EMAIL] Welcome notification handling error: {w_err}")

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


AUTH_SECRET = os.getenv('SECRET_KEY', 'student_sync_attendance_token_secret_2026').encode('utf-8')


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

    user_doc = users_collection.find_one({"rollNo": authenticated_roll})
    if not user_doc:
        return None, 404, f"Student record for {authenticated_roll} not found."

    return user_doc, 200, None


# Login route
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    rollNo = (data.get('rollNo') or '').strip().upper()
    password = (data.get('password') or '').strip()

    try:
        user = users_collection.find_one({"rollNo": rollNo, "password": password})

        if user:
            if '_id' in user:
                user['_id'] = str(user['_id'])
            user.pop('password', None)
            user['auth_token'] = generate_auth_token(rollNo)
            return jsonify(user)

        # Fallback: attempt direct portal authentication if not found in db
        user_doc, err = sync_student_dual_portal(rollNo, password)
        if user_doc and not err:
            if '_id' in user_doc:
                user_doc['_id'] = str(user_doc['_id'])
            user_doc.pop('password', None)
            user_doc['auth_token'] = generate_auth_token(rollNo)
            return jsonify(user_doc)

        return jsonify({"message": "Invalid credentials. Please try again."}), 401

    except Exception as e:
        print(f"Error during login: {str(e)}")
        return jsonify({"message": "Server error. Please try again later."}), 500


# Profile fetching and manual refresh route
@app.route('/profile', methods=['GET'])
def profile():
    rollNo = (request.args.get('rollNo') or '').strip().upper()
    refresh = request.args.get('refresh', '').lower() == 'true'

    try:
        user = users_collection.find_one({"rollNo": rollNo})

        if not user:
            return jsonify({"message": "User not found."}), 404

        # If manual refresh requested, re-sync from both portals
        if refresh and user.get('password'):
            updated_doc, err = sync_student_dual_portal(rollNo, user['password'])
            if updated_doc:
                user = updated_doc

        if '_id' in user:
            user['_id'] = str(user['_id'])
        user.pop('password', None)
        user['auth_token'] = generate_auth_token(rollNo)
        return jsonify(user)

    except Exception as e:
        print(f"Error fetching profile: {str(e)}")
        return jsonify({"message": "Server error. Please try again later."}), 500


# Update notification preferences and/or email address
@app.route('/notifications', methods=['POST'])
def update_notifications():
    data = request.get_json() or {}
    rollNo = (data.get('rollNo') or '').strip().upper()
    notifications = data.get('notifications')
    email = (data.get('email') or '').strip()

    try:
        update_fields = {}
        if notifications is not None:
            update_fields["notifications"] = notifications
        if email:
            update_fields["email"] = email
        monitoring_enabled = data.get('monitoring_enabled')
        if monitoring_enabled is not None:
            update_fields["monitoring_enabled"] = bool(monitoring_enabled)

        if not update_fields:
            return jsonify({"message": "No update fields provided."}), 400

        result = users_collection.update_one({"rollNo": rollNo}, {"$set": update_fields})

        if result.matched_count > 0:
            return jsonify({"message": "Settings updated successfully!", "email": email if email else None})
        else:
            return jsonify({"message": "User not found."}), 404

    except Exception as e:
        print(f"Error updating notifications: {str(e)}")
        return jsonify({"message": "Server error. Please try again later."}), 500


@app.route('/send-message', methods=['POST'])
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

    studzone1 = user.get('studzone1', {})
    parsed_attendance = studzone1.get('parsed_attendance', [])
    class_schedule = studzone1.get('class_schedule', [])

    # 1. Calculate overall summary & subject breakdown (read-only, resolving student-specific course titles)
    summary = summarize_student_attendance(parsed_attendance, target=target, user_doc=user)

    # 2. Parse today's classroom lecture schedule matching day
    day_query = request.args.get('day')
    today_schedule = parse_daily_schedule(class_schedule, day_name=day_query)

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
        "last_synced": user.get("last_synced_studzone1") or user.get("lastSyncedAt")
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
    parsed_attendance = studzone1.get('parsed_attendance', [])

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
    parsed = parse_weekly_schedule_matrix(class_schedule)
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
    parsed_attendance = studzone1.get('parsed_attendance', [])
    class_schedule = studzone1.get('class_schedule', [])

    try:
        sim_result = simulate_day_bunks(
            parsed_attendance_list=parsed_attendance,
            class_schedule_matrix=class_schedule,
            day=day,
            periods=periods,
            target=target
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

    overview = synthesize_campus_services(user)
    return jsonify(overview), 200


if __name__ == "__main__":
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, use_reloader=False, port=port, host='127.0.0.1')

