import os
import sys

_backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_root_dir = os.path.abspath(os.path.join(_backend_dir, '..'))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

try:
    from backend.new_scrapers.send_mail import send_email as tracked_send_email, queue_tracked_email
except ImportError:
    from new_scrapers.send_mail import send_email as tracked_send_email, queue_tracked_email

def send_email(recipient_email, subject, body, rollNo=None, notif_type='general', notif_id=None):
    """Forward to tracked thread-safe email sender"""
    return tracked_send_email(recipient_email, subject, body, rollNo=rollNo, notif_type=notif_type, notif_id=notif_id)
