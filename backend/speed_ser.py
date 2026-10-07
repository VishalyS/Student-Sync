import time
import logging
import os
import certifi
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from pymongo import MongoClient
from pymongo.errors import NetworkTimeout, ConnectionFailure, AutoReconnect, ServerSelectionTimeoutError, DuplicateKeyError
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
load_dotenv()

import sys

# Ensure backend directory and its parent directory are on sys.path
_backend_dir = os.path.abspath(os.path.dirname(__file__))
_root_dir = os.path.abspath(os.path.join(_backend_dir, '..'))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('speed_ser')

try:
    from backend.new_scrapers.login import login as modern_login
    from backend.scrapers.login import login_student_studzone2 as legacy_login
    from backend.new_scrapers.studzone1_scraper import scrape_studzone1_all
    from backend.scrapers.studzone2_scraper import scrape_studzone2_all
    from backend.new_scrapers.send_mail import queue_tracked_email
    from backend.notifications.change_detector import detect_granular_changes, process_normalized_event
    from backend.notifications.recovery import recover_stale_notifications
except ImportError:
    from new_scrapers.login import login as modern_login
    from scrapers.login import login_student_studzone2 as legacy_login
    from new_scrapers.studzone1_scraper import scrape_studzone1_all
    from scrapers.studzone2_scraper import scrape_studzone2_all
    from new_scrapers.send_mail import queue_tracked_email
    from notifications.change_detector import detect_granular_changes, process_normalized_event
    from notifications.recovery import recover_stale_notifications

MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DB_NAME', 'ecampus')


def get_db():
    try:
        client = MongoClient(
            MONGO_URI,
            connectTimeoutMS=30000,
            socketTimeoutMS=30000,
            serverSelectionTimeoutMS=30000,
            tlsCAFile=certifi.where()
        )
        return client[DB_NAME]
    except Exception as e:
        logger.error(f"Error connecting to MongoDB: {e}")
        return None


def process_detected_changes(roll_no, old_user, sz1_fresh, sz2_fresh, db):
    """
    Executes granular change detection against previous MongoDB snapshot.
    Persists structured notification cards into notifications_log and sends specific emails.
    Guarantees 100% duplicate prevention using deterministic changeHash.
    """
    notifs_col = db['notifications_log'] if db is not None else None
    if notifs_col is None:
        return

    detected_notifs = detect_granular_changes(roll_no, old_user, sz1_fresh, sz2_fresh)
    if not detected_notifs:
        return

    recipient_email = (old_user.get('email') or '').strip() or f"{roll_no.lower()}@psgtech.ac.in"
    student_name = old_user.get('name', roll_no)
    user_prefs = old_user.get('notifications', {})

    for notif in detected_notifs:
        ntype = notif.get('type')
        # Check user notification preferences (support both 'seatingArrangement' and 'seating')
        pref_key = "seatingArrangement" if ntype == "seating" else ntype
        if user_prefs and not user_prefs.get(pref_key, user_prefs.get(ntype, True)):
            continue

        chash = notif.get('changeHash')
        # Duplicate check using changeHash
        existing = notifs_col.find_one({"changeHash": chash})
        if existing:
            continue

        # Insert structured notification document into MongoDB with initial status 'pending'
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        notif_doc = {
            "rollNo": roll_no,
            "studentRollNo": roll_no,
            "recipient_email": recipient_email,
            "category": notif.get('category', notif.get('type', 'system')),
            "type": notif.get('type', 'system'),
            "title": notif.get('title', 'Academic Update'),
            "description": notif.get('description', notif.get('message', '')),
            "message": notif.get('message', notif.get('description', '')),
            "source": notif.get('source', 'Student Sync'),
            "module": notif.get('module', 'Academics'),
            "timestamp": notif.get('timestamp', now_iso),
            "createdAt": notif.get('createdAt', now_iso),
            "created_at": now,
            "updated_at": now,
            "read": False,
            "changeHash": chash,
            "changeData": notif.get('changeData', {}),
            "status": "pending",
            "error": None
        }

        try:
            res = notifs_col.insert_one(notif_doc)
            notif_id = res.inserted_id
            logger.info(f"Recorded specific notification for {roll_no}: {notif.get('title')} — {notif.get('message')}")
        except DuplicateKeyError:
            logger.info(f"Duplicate notification atomically suppressed by unique index for {roll_no} (changeHash: {chash})")
            continue
        except Exception as insert_err:
            logger.error(f"Error persisting notification for {roll_no}: {insert_err}")
            continue

        # Send specific email ONLY after successful atomic insertion
        try:
            subj = notif['changeData'].get('subject')
            if subj:
                email_subject = f"Student Sync — {notif.get('title')} ({subj})"
            else:
                email_subject = f"Student Sync — {notif.get('title')}"

            email_body = f"""
            <!DOCTYPE html>
            <html>
            <body style="margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0b0d13; color: #f3f4f6;">
              <div style="max-width: 520px; margin: 0 auto; background-color: #131620; border: 1px solid #232738; border-radius: 12px; padding: 24px;">
                <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #a78bfa; font-weight: 600; margin-bottom: 6px;">
                  {notif.get('source')} • {notif.get('module')}
                </div>
                <h2 style="color: #ffffff; font-size: 18px; margin-top: 0; margin-bottom: 12px;">{notif.get('title')}</h2>
                <p style="color: #e5e7eb; font-size: 14px; line-height: 1.6; margin-bottom: 16px;">
                  {notif.get('message')}
                </p>
                <div style="padding: 12px; border-radius: 8px; background-color: #181c2b; border: 1px solid #222738; font-size: 12px; color: #9ca3af; margin-bottom: 20px;">
                  Student: <strong style="color: #ffffff;">{student_name}</strong> (<span style="font-family: monospace; color: #c4b5fd;">{roll_no}</span>)
                </div>
                <div style="border-top: 1px solid #1c202e; padding-top: 14px; font-size: 11px; color: #6b7280; text-align: center;">
                  © 2026 Student Sync | PSG College of Technology
                </div>
              </div>
            </body>
            </html>
            """
            queue_tracked_email(roll_no, recipient_email, ntype, email_subject, email_body, notif_id=notif_id)
        except Exception as queue_err:
            logger.error(f"Error queueing email for {roll_no}: {queue_err}")


def dispatch_normalized_notification(roll_no, user, event_data, db=None):
    """
    Extensible entry point for future website scrapers to trigger normalized notifications.
    Accepts normalized event format:
    {
        "category": "...",
        "type": "...",
        "title": "...",
        "message": "...",
        "source": "...",
        "module": "...",
        "change_key": "...",
        "changeData": {...}
    }
    Guarantees user isolation, preference checks, and idempotent deduplication via changeHash.
    """
    if db is None:
        db = get_db()
    if db is None:
        return None

    notifs_col = db['notifications_log']

    if not user:
        user = db['new_users'].find_one({"rollNo": roll_no.strip().upper()}) or {}

    # Check student monitoring preference and baseline status
    if user.get('monitoring_enabled') is False or user.get('baseline_initialized') is False:
        logger.info(f"Monitoring disabled or uninitialized baseline for {roll_no}; skipping normalized event.")
        return None

    # Normalize into standard notification payload
    notif = process_normalized_event(roll_no, event_data, user)
    if not notif:
        return None

    ntype = notif.get('type')
    pref_key = "seatingArrangement" if ntype == "seating" else ntype
    user_prefs = user.get('notifications', {})
    if user_prefs and not user_prefs.get(pref_key, user_prefs.get(ntype, True)):
        logger.info(f"Normalized notification {ntype} suppressed by user preferences for {roll_no}")
        return None

    chash = notif.get('changeHash')
    existing = notifs_col.find_one({"changeHash": chash})
    if existing:
        logger.info(f"Normalized notification already logged for {roll_no} (changeHash: {chash})")
        return None

    recipient_email = (user.get('email') or '').strip() or f"{roll_no.lower()}@psgtech.ac.in"
    student_name = user.get('name', roll_no)
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    notif_doc = {
        "rollNo": roll_no.strip().upper(),
        "studentRollNo": roll_no.strip().upper(),
        "recipient_email": recipient_email,
        "category": notif.get('category', 'general'),
        "type": ntype,
        "title": notif.get('title', 'System Update'),
        "description": notif.get('description', ''),
        "message": notif.get('message', ''),
        "source": notif.get('source', 'Student Sync'),
        "module": notif.get('module', 'Academics'),
        "timestamp": notif.get('timestamp', now_iso),
        "createdAt": now_iso,
        "created_at": now,
        "updated_at": now,
        "read": False,
        "changeHash": chash,
        "changeData": notif.get('changeData', {}),
        "status": "pending",
        "error": None
    }

    try:
        res = notifs_col.insert_one(notif_doc)
        notif_id = res.inserted_id
        logger.info(f"Recorded normalized notification for {roll_no}: {notif.get('title')} — {notif.get('message')}")
    except DuplicateKeyError:
        logger.info(f"Duplicate normalized notification atomically suppressed for {roll_no} (changeHash: {chash})")
        return None
    except Exception as insert_err:
        logger.error(f"Error persisting normalized notification for {roll_no}: {insert_err}")
        return None

    try:
        subj = notif['changeData'].get('subject') if isinstance(notif.get('changeData'), dict) else None
        if subj:
            email_subject = f"Student Sync — {notif.get('title')} ({subj})"
        else:
            email_subject = f"Student Sync — {notif.get('title')}"

        email_body = f"""
        <!DOCTYPE html>
        <html>
        <body style="margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0b0d13; color: #f3f4f6;">
          <div style="max-width: 520px; margin: 0 auto; background-color: #131620; border: 1px solid #232738; border-radius: 12px; padding: 24px;">
            <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #a78bfa; font-weight: 600; margin-bottom: 6px;">
              {notif.get('source')} • {notif.get('module')}
            </div>
            <h2 style="color: #ffffff; font-size: 18px; margin-top: 0; margin-bottom: 12px;">{notif.get('title')}</h2>
            <p style="color: #e5e7eb; font-size: 14px; line-height: 1.6; margin-bottom: 16px;">
              {notif.get('message')}
            </p>
            <div style="padding: 12px; border-radius: 8px; background-color: #181c2b; border: 1px solid #222738; font-size: 12px; color: #9ca3af; margin-bottom: 20px;">
              Student: <strong style="color: #ffffff;">{student_name}</strong> (<span style="font-family: monospace; color: #c4b5fd;">{roll_no}</span>)
            </div>
            <div style="border-top: 1px solid #1c202e; padding-top: 14px; font-size: 11px; color: #6b7280; text-align: center;">
              © 2026 Student Sync | PSG College of Technology
            </div>
          </div>
        </body>
        </html>
        """
        queue_tracked_email(roll_no, recipient_email, ntype, email_subject, email_body, notif_id=notif_id)
        return notif_id
    except Exception as queue_err:
        logger.error(f"Error queueing normalized email for {roll_no}: {queue_err}")
        return notif_id


def sync_single_user(user, db):
    """
    Background worker that syncs both portals for a single student,
    detects actual granular changes, updates MongoDB, and emits specific notifications.
    """
    roll_no = user.get('rollNo', '').strip().upper()
    password = user.get('password', '')
    
    if not roll_no or not password:
        return None

    # Check student monitoring preference and baseline status
    if user.get('monitoring_enabled') is False or user.get('baseline_initialized') is False:
        logger.info(f"Background monitoring disabled or baseline initializing for {roll_no}; skipping sync cycle.")
        return None

    try:
        user_credentials = {'rollNo': roll_no, 'password': password}
        now_iso = datetime.now(timezone.utc).isoformat()
        
        # 1. Scrape StudZone 1 (Modern)
        modern_session_res = modern_login(user_credentials)
        sz1_fresh = {}
        if not isinstance(modern_session_res, tuple) and modern_session_res:
            sz1_fresh = scrape_studzone1_all(modern_session_res, roll_no, db['subjects'])
        else:
            logger.warning(f"StudZone 1 login unavailable for {roll_no} in sync cycle")

        # 2. Scrape StudZone 2 (Legacy)
        legacy_session_res = legacy_login(user_credentials)
        sz2_fresh = {}
        if not isinstance(legacy_session_res, tuple) and legacy_session_res:
            sz2_fresh = scrape_studzone2_all(legacy_session_res, roll_no)
        else:
            logger.warning(f"StudZone 2 login unavailable for {roll_no} in sync cycle")

        # 3. Detect granular changes and queue notifications only on genuine updates
        if sz1_fresh or sz2_fresh:
            process_detected_changes(roll_no, user, sz1_fresh, sz2_fresh, db)

        # 4. Build updated document
        sync_status = {
            "profile": {"status": "synced" if sz1_fresh.get("profile") else "cached", "timestamp": now_iso, "portal": "StudZone 1"},
            "attendance": {"status": "synced" if sz1_fresh.get("attendance_html") else "cached", "timestamp": now_iso, "portal": "StudZone 1"},
            "marks": {"status": "synced" if sz1_fresh.get("ca_marks_html") else "cached", "timestamp": now_iso, "portal": "StudZone 1"},
            "results": {"status": "synced" if sz2_fresh.get("results_html") else "cached", "timestamp": now_iso, "portal": "StudZone 2"},
            "cgpa": {"status": "synced" if sz2_fresh.get("cgpa") is not None else "cached", "timestamp": now_iso, "portal": "StudZone 2"},
            "timetable": {"status": "synced" if sz2_fresh.get("timetable_html") or sz1_fresh.get("class_timetable_html") else "cached", "timestamp": now_iso, "portal": "StudZone 2"},
            "seating": {"status": "synced" if sz2_fresh.get("seating_html") else "not_published_yet", "timestamp": now_iso, "portal": "StudZone 2"},
            "fees": {"status": "synced" if sz1_fresh.get("fees_html") else "cached", "timestamp": now_iso, "portal": "StudZone 1"},
            "hostel": {"status": "synced" if sz1_fresh.get("hostel_html") else "cached", "timestamp": now_iso, "portal": "StudZone 1"},
            "scholarships": {"status": "synced", "timestamp": now_iso, "portal": "StudZone 1"},
            "feedback": {"status": "synced", "timestamp": now_iso, "portal": "StudZone 1"},
            "leave": {"status": "synced" if sz1_fresh.get("leave_html") else "cached", "timestamp": now_iso, "portal": "StudZone 1"},
            "library": {"status": "not_available_on_portal", "timestamp": now_iso, "portal": "External OPAC"}
        }

        update_fields = {
            "lastAttemptAt": now_iso,
            "lastSyncedAt": now_iso,
            "syncStatus": sync_status,
            "portalStatus": {
                "studzone1": "connected" if sz1_fresh else "unreachable",
                "studzone2": "connected" if sz2_fresh else "unreachable"
            }
        }
        if sz1_fresh or sz2_fresh:
            update_fields["lastSuccessfulSyncAt"] = now_iso

        # Update StudZone 1 data only if fresh data was retrieved
        if sz1_fresh:
            # Preserve existing parsed sub-tables if scraper returned empty during a transient portal hiccup
            old_sz1 = user.get("studzone1") or {}
            for parsed_key in ["parsed_attendance", "parsed_marks", "parsed_fees"]:
                if not sz1_fresh.get(parsed_key) and old_sz1.get(parsed_key):
                    sz1_fresh[parsed_key] = old_sz1[parsed_key]

            update_fields["studzone1"] = sz1_fresh
            if sz1_fresh.get("parsed_attendance"):
                logger.info(f"Attendance parsed for {roll_no}: {len(sz1_fresh.get('parsed_attendance'))} courses")
            else:
                logger.warning(f"Scraper returned no attendance for {roll_no}; keeping existing data")
            # Update ancillary fields
            update_fields["attendance"] = sz1_fresh.get("attendance_html") or user.get("attendance", "")
            update_fields["marks"] = sz1_fresh.get("ca_marks_html") or user.get("marks", "")
            update_fields["fees"] = sz1_fresh.get("fees_html") or user.get("fees", "")
            update_fields["hostel"] = sz1_fresh.get("hostel_html") or user.get("hostel", "")
            update_fields["scholarships"] = sz1_fresh.get("scholarships") or user.get("scholarships", {})
            update_fields["feedback"] = sz1_fresh.get("feedback") or user.get("feedback", [])
            update_fields["leave"] = sz1_fresh.get("leave_html") or user.get("leave", "")
            update_fields["last_synced_studzone1"] = now_iso
            update_fields["last_successful_studzone1"] = now_iso

        if sz2_fresh:
            # Preserve existing parsed sub-tables if scraper returned empty during a transient portal hiccup
            old_sz2 = user.get("studzone2") or {}
            for parsed_key in ["parsed_results", "parsed_timetable", "parsed_seating"]:
                if not sz2_fresh.get(parsed_key) and old_sz2.get(parsed_key):
                    sz2_fresh[parsed_key] = old_sz2[parsed_key]

            update_fields["studzone2"] = sz2_fresh
            if sz2_fresh.get("cgpa") is not None:
                update_fields["cgpa"] = sz2_fresh.get("cgpa")
            update_fields["results"] = sz2_fresh.get("results_html") or user.get("results", "")
            update_fields["result_table"] = sz2_fresh.get("results_html") or user.get("result_table", "")
            update_fields["timetable"] = sz2_fresh.get("timetable_html") or user.get("timetable", "")
            update_fields["seating"] = sz2_fresh.get("seating_html") if sz2_fresh.get("seating_html") is not None else user.get("seating")
            update_fields["applications"] = sz2_fresh.get("applications") or user.get("applications", {})
            update_fields["circulars"] = sz2_fresh.get("circulars") or user.get("circulars", [])
            update_fields["last_synced_studzone2"] = now_iso
            update_fields["last_successful_studzone2"] = now_iso

        db['new_users'].update_one({"rollNo": roll_no}, {"$set": update_fields})
        logger.info(f"Successfully refreshed dual-portal data for {roll_no}")
        return None

    except Exception as e:
        logger.error(f"Error syncing student {roll_no}: {e}")
        return user


def run_sync_cycle():
    """Runs a complete background synchronization pass across all registered students"""
    db = get_db()
    if db is None:
        return False

    # 1. Recover any stale pending/retrying notifications from unhandled previous crashes
    try:
        recover_stale_notifications(db, threshold_seconds=3600)
    except Exception as rec_err:
        logger.error(f"Error during stale notification recovery: {rec_err}")

    all_users = list(db['new_users'].find({}))
    if not all_users:
        logger.info("No registered students to sync.")
        return True

    logger.info(f"Starting background dual-portal sync for {len(all_users)} students...")
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(sync_single_user, user, db) for user in all_users]
        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                logger.error(f"Sync worker exception: {e}")

    logger.info("Dual-portal sync cycle completed.")
    return True


LOCK_FILE = os.path.join(_backend_dir, ".synchronizer.lock")

def acquire_instance_lock():
    try:
        if os.path.exists(LOCK_FILE):
            try:
                with open(LOCK_FILE, "r") as f:
                    old_pid = int(f.read().strip())
                import subprocess
                check = subprocess.run(f'tasklist /FI "PID eq {old_pid}"', capture_output=True, text=True, shell=True)
                if str(old_pid) in check.stdout:
                    logger.error(f"Single synchronizer guard: Another instance is already active (PID: {old_pid}). Exiting to prevent duplicate polling.")
                    return False
            except Exception:
                pass
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))
        return True
    except Exception as e:
        logger.warning(f"Could not verify synchronizer lock: {e}")
        return True

def release_instance_lock():
    try:
        if os.path.exists(LOCK_FILE):
            with open(LOCK_FILE, "r") as f:
                content = f.read().strip()
            if content == str(os.getpid()):
                os.remove(LOCK_FILE)
    except Exception:
        pass

import atexit
atexit.register(release_instance_lock)


if __name__ == "__main__":
    if not acquire_instance_lock():
        sys.exit(0)
    logger.info("Background dual-portal synchronizer started (single-instance verified).")
    while True:
        try:
            run_sync_cycle()
            time.sleep(300)  # Wait 5 minutes between background cycles
        except KeyboardInterrupt:
            logger.info("Background synchronization stopped by user.")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(60)
    release_instance_lock()