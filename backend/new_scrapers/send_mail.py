import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import threading
import time
import atexit
import logging
from queue import Queue, Empty
from datetime import datetime, timezone
from dotenv import load_dotenv
from pymongo.errors import DuplicateKeyError

import sys

# Ensure backend directory and its parent directory are on sys.path
_backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_root_dir = os.path.abspath(os.path.join(_backend_dir, '..'))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

# Find and load .env dynamically with override=True
env_path = os.path.join(_backend_dir, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
load_dotenv(override=True)

# Alias module across dual namespace imports to ensure a single singleton EmailSender
if __name__ == 'backend.new_scrapers.send_mail':
    sys.modules.setdefault('new_scrapers.send_mail', sys.modules[__name__])
elif __name__ == 'new_scrapers.send_mail':
    sys.modules.setdefault('backend.new_scrapers.send_mail', sys.modules[__name__])

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
email_logger = logging.getLogger('email_sender')


class EmailSender:
    def __init__(self, max_retries=2, num_workers=2):
        self.max_retries = max_retries
        self.num_workers = num_workers
        self.email_queue = Queue()
        self.is_running = False
        self.worker_threads = []
        self.lock = threading.Lock()
        self._notifications_col = None
        
        # Start background workers immediately
        self.start_workers()
        
        # Register cleanup function
        atexit.register(self.stop_workers)
    
    @property
    def sender_email(self):
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        if os.path.exists(env_path):
            load_dotenv(env_path, override=True)
        return (os.getenv("SMTP_USER") or "").strip()

    @property
    def password(self):
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        if os.path.exists(env_path):
            load_dotenv(env_path, override=True)
        raw_password = (os.getenv("SMTP_PASSWORD") or "").strip().strip('"').strip("'")
        return raw_password.replace(" ", "")

    @property
    def admin_email(self):
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        if os.path.exists(env_path):
            load_dotenv(env_path, override=True)
        return (os.getenv("ADMIN_EMAIL") or "studentsync12@gmail.com").strip()

    
    @property
    def notifications_collection(self):
        if self._notifications_col is None:
            try:
                from backend.database import notifications_collection
                self._notifications_col = notifications_collection
            except Exception:
                try:
                    from database import notifications_collection
                    self._notifications_col = notifications_collection
                except Exception as e:
                    email_logger.error(f"Failed to load notifications_collection in EmailSender: {e}")
                    self._notifications_col = None
        return self._notifications_col

    def _log_notification_status(self, notif_id, roll_no, notif_type, recipient_email, subject, status, error=None, is_sent=False, retry_count=None):
        """Helper to create or update notification record in MongoDB"""
        try:
            col = self.notifications_collection
            if col is None:
                email_logger.error(f"Cannot log notification status to MongoDB for {roll_no} ({notif_type}): notifications_collection unavailable.")
                return

            now = datetime.now(timezone.utc)
            update_data = {
                "rollNo": (roll_no or "UNKNOWN").upper(),
                "recipient_email": recipient_email,
                "type": notif_type or "general",
                "category": notif_type or "general",
                "subject": subject,
                "status": status,
                "updated_at": now,
            }
            if retry_count is not None:
                update_data["retry_count"] = retry_count
            if is_sent:
                update_data["sent_at"] = now
                update_data["error"] = None
            elif error:
                update_data["error"] = str(error)

            if notif_id:
                query = {"_id": notif_id}
                if isinstance(notif_id, str):
                    try:
                        from bson import ObjectId
                        query = {"_id": ObjectId(notif_id)}
                    except Exception:
                        query = {"_id": notif_id}

                set_on_insert = {"created_at": now}
                if "retry_count" not in update_data:
                    set_on_insert["retry_count"] = 0

                col.update_one(
                    query,
                    {"$set": update_data, "$setOnInsert": set_on_insert},
                    upsert=True
                )
            else:
                update_data["created_at"] = now
                if "retry_count" not in update_data:
                    update_data["retry_count"] = 0
                res = col.insert_one(update_data)
                return res.inserted_id
        except Exception as e:
            email_logger.error(f"Could not log notification state to MongoDB for {roll_no}: {e}")

    def start_workers(self):
        """Start the email worker threads"""
        with self.lock:
            if not self.is_running:
                self.is_running = True
                self.worker_threads = []
                
                for i in range(self.num_workers):
                    worker = threading.Thread(target=self._email_worker, args=(i,), daemon=True)
                    worker.start()
                    self.worker_threads.append(worker)
                
                email_logger.info(f"Started {self.num_workers} email worker threads")
    
    def stop_workers(self):
        """Stop all email worker threads"""
        with self.lock:
            if self.is_running:
                self.is_running = False
                
                for _ in range(self.num_workers):
                    self.email_queue.put(None)
                
                for worker in self.worker_threads:
                    if worker.is_alive():
                        worker.join(timeout=5)
                
                self.worker_threads = []
                email_logger.info("All email worker threads stopped")
    
    def _email_worker(self, worker_id):
        """Worker thread that processes emails from the queue and updates MongoDB records"""
        email_logger.info(f"Email worker {worker_id} ready")
        
        while self.is_running:
            try:
                item = self.email_queue.get(timeout=1)
                if item is None:
                    break
                
                roll_no, recipient_email, notif_type, subject, body, retry_count, notif_id = item
                
                try:
                    email_logger.info(f"Worker {worker_id} processing {notif_type} email for {roll_no} -> {recipient_email} (attempt {retry_count + 1})")
                    
                    success, error_msg = self._send_email_attempt(recipient_email, subject, body)
                    
                    if success:
                        email_logger.info(f"Worker {worker_id}: Successfully sent {notif_type} email to {recipient_email}")
                        self._log_notification_status(notif_id, roll_no, notif_type, recipient_email, subject, "sent", is_sent=True, retry_count=retry_count)
                    else:
                        if "Authentication failed" in error_msg or retry_count >= self.max_retries:
                            email_logger.error(f"Worker {worker_id}: Permanent failure for {recipient_email}: {error_msg}")
                            self._log_notification_status(notif_id, roll_no, notif_type, recipient_email, subject, "failed", error=error_msg, retry_count=retry_count)
                        else:
                            retry_count += 1
                            email_logger.warning(f"Worker {worker_id}: Retrying {recipient_email} ({retry_count}/{self.max_retries}) after backoff...")
                            self._log_notification_status(notif_id, roll_no, notif_type, recipient_email, subject, "retrying", error=error_msg, retry_count=retry_count)
                            
                            time.sleep(min(2 ** retry_count, 10))
                            self.email_queue.put((roll_no, recipient_email, notif_type, subject, body, retry_count, notif_id))
                except Exception as proc_err:
                    email_logger.error(f"Worker {worker_id} unexpected processing error for {recipient_email}: {proc_err}")
                    if notif_id:
                        self._log_notification_status(notif_id, roll_no, notif_type, recipient_email, subject, "failed", error=str(proc_err))
                finally:
                    self.email_queue.task_done()
                
            except Empty:
                continue
            except Exception as e:
                if self.is_running:
                    email_logger.error(f"Worker {worker_id} queue loop error: {e}")
                continue
    
    def _send_email_attempt(self, recipient_email, subject, body):
        """Send email (single attempt). Returns (bool success, str error_message)"""
        sender_email = (os.getenv("SMTP_USER") or self.sender_email or "").strip()
        # Clean password of any surrounding spaces or quotes
        raw_password = (os.getenv("SMTP_PASSWORD") or self.password or "").strip().strip('"').strip("'")
        password = raw_password.replace(" ", "")  # Google app passwords may have 4-block spaces
        
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com").strip()
        smtp_port = int(os.getenv("SMTP_PORT", 587))

        if not sender_email or not password:
            return False, "SMTP credentials not configured in .env (SMTP_USER / SMTP_PASSWORD required)."

        try:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=15) as server:
                server.set_debuglevel(0)
                server.starttls()
                server.login(sender_email, password)
                
                msg = MIMEText(body, 'html')
                msg['Subject'] = subject
                msg['From'] = sender_email
                msg['To'] = recipient_email
                
                server.sendmail(sender_email, recipient_email, msg.as_string())
                return True, ""
                
        except smtplib.SMTPAuthenticationError as e:
            # Helpful diagnosis for Google App Passwords without leaking passwords
            hint = " [Note: Gmail requires a 16-character Google App Password from https://myaccount.google.com/apppasswords, not your standard account password]"
            return False, f"SMTP Authentication failed (535): {e}{hint}"
        except smtplib.SMTPRecipientsRefused as e:
            return False, f"Recipient refused: {e}"
        except Exception as e:
            return False, f"SMTP error: {str(e)}"
    
    def send_direct(self, recipient_email, subject, body, roll_no=None, notif_type='general', notif_id=None):
        """
        Direct, immediate email delivery via SMTP.
        Updates MongoDB notifications_log with status 'sent' or 'failed'.
        Returns (bool success, str error_message).
        """
        success, error_msg = self._send_email_attempt(recipient_email, subject, body)
        if success:
            email_logger.info(f"Direct send SUCCESS to {recipient_email} ({notif_type})")
            self._log_notification_status(notif_id, roll_no, notif_type, recipient_email, subject, "sent", is_sent=True)
            return True, ""
        else:
            email_logger.error(f"Direct send FAILED to {recipient_email} ({notif_type}): {error_msg}")
            self._log_notification_status(notif_id, roll_no, notif_type, recipient_email, subject, "failed", error=error_msg)
            return False, error_msg

    def queue_email(self, recipient_email, subject, body, roll_no=None, notif_type='general', notif_id=None):
        """Queue a tracked email to be sent by worker threads"""
        try:
            now = datetime.now(timezone.utc)
            col = self.notifications_collection
            
            if col is not None and notif_id is None:
                clean_title = subject.replace('Student Sync — ', '').replace('Student Sync: ', '').strip()
                source = "StudZone 1" if notif_type in ['attendance', 'marks', 'fees', 'hostel', 'scholarships', 'feedback', 'leave'] else ("StudZone 2" if notif_type in ['results', 'timetable', 'seating', 'circulars'] else "Student Sync")
                record = {
                    "rollNo": (roll_no or "UNKNOWN").upper(),
                    "studentRollNo": (roll_no or "UNKNOWN").upper(),
                    "recipient_email": recipient_email,
                    "category": notif_type or "general",
                    "type": notif_type or "general",
                    "title": clean_title,
                    "description": clean_title,
                    "message": clean_title,
                    "source": source,
                    "subject": subject,
                    "read": False,
                    "status": "pending",
                    "retry_count": 0,
                    "created_at": now,
                    "updated_at": now,
                    "timestamp": now.isoformat(),
                    "createdAt": now.isoformat()
                }
                res = col.insert_one(record)
                notif_id = res.inserted_id

            self.email_queue.put((roll_no, recipient_email, notif_type, subject, body, 0, notif_id), timeout=5)
            return True
        except DuplicateKeyError:
            email_logger.info(f"Duplicate email queue suppressed by unique index for {roll_no} -> {recipient_email}")
            return False
        except Exception as e:
            email_logger.error(f"Failed to queue email for {recipient_email}: {e}")
            return False


# Global singleton email sender
_email_sender = EmailSender()

def send_email(recipient_email, subject, body, rollNo=None, notif_type='general', notif_id=None):
    """
    Thread-safe, MongoDB-tracked email queuing function.
    """
    return _email_sender.queue_email(recipient_email, subject, body, roll_no=rollNo, notif_type=notif_type, notif_id=notif_id)


def queue_tracked_email(rollNo, recipient_email, notif_type, subject, body, notif_id=None):
    """
    Explicitly queue an academic or welcome notification with student roll number & category.
    """
    return _email_sender.queue_email(recipient_email, subject, body, roll_no=rollNo, notif_type=notif_type, notif_id=notif_id)


def send_email_direct(recipient_email, subject, body, rollNo=None, notif_type='general', notif_id=None):
    """
    Direct, synchronous/immediate email delivery. Returns (bool success, str error_message).
    """
    return _email_sender.send_direct(recipient_email, subject, body, roll_no=rollNo, notif_type=notif_type, notif_id=notif_id)

