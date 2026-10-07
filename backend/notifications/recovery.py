"""
Stale Notification Recovery Module for Student Sync

Safely audits and reconciles notification documents that remain stuck in 'pending'
or 'retrying' status after an unhandled process crash, network partition, or power loss.

Guarantees:
1. Reconciles ONLY records older than a configurable threshold (default: 3600 seconds / 1 hour).
2. NEVER blindly resends emails: SMTP acceptance and database status updates cannot be an atomic
   transaction. Automatically re-sending could cause duplicate student emails if SMTP had accepted
   the message right before the process crashed.
3. NEVER marks an unverified record as 'sent'.
4. Transitions ambiguous records to an explicit recovery status: 'delivery_uncertain' with
   'requires_reconciliation': True and a descriptive audit explanation in 'error'.
5. Atomic document updates prevent race conditions and ensure safe single-execution even if
   invoked concurrently.
6. Preserves all existing notification fields, recipient info, roll number, changeData, and history.
"""

import os
import sys
import logging
from datetime import datetime, timezone, timedelta
from bson import ObjectId

logger = logging.getLogger('notification_recovery')

DEFAULT_STALE_THRESHOLD_SECONDS = 3600  # 1 hour threshold


def recover_stale_notifications(db, threshold_seconds=DEFAULT_STALE_THRESHOLD_SECONDS):
    """
    Scans notifications_log for records stuck in 'pending' or 'retrying' whose
    updated_at/created_at is older than threshold_seconds.

    Transitions them to 'delivery_uncertain' with detailed audit context.
    Returns the number of reconciled records.
    """
    if db is None:
        return 0

    notifs_col = db.get_collection('notifications_log') if hasattr(db, 'get_collection') else db['notifications_log']
    if notifs_col is None:
        return 0

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=threshold_seconds)

    # Stale candidate filter:
    # Status is 'pending' or 'retrying' AND updated_at (or created_at) < cutoff
    query = {
        "status": {"$in": ["pending", "retrying"]},
        "$or": [
            {"updated_at": {"$lt": cutoff}},
            {"updated_at": {"$exists": False}, "created_at": {"$lt": cutoff}},
            {"updated_at": {"$exists": False}, "created_at": {"$exists": False}, "createdAt": {"$lt": cutoff.isoformat()}}
        ]
    }

    update_payload = {
        "$set": {
            "status": "delivery_uncertain",
            "requires_reconciliation": True,
            "stale_recovered_at": now,
            "updated_at": now,
            "error": (
                f"Recovered by stale-notification auditor after exceeding {threshold_seconds}s timeout. "
                "Delivery status ambiguous following process crash; withheld automatic resend to prevent duplicate student emails."
            )
        }
    }

    try:
        res = notifs_col.update_many(query, update_payload)
        if res.modified_count > 0:
            logger.warning(
                f"[RECOVERY] Reconciled {res.modified_count} stale notification(s) to 'delivery_uncertain' (threshold: {threshold_seconds}s)."
            )
        return res.modified_count
    except Exception as e:
        logger.error(f"[RECOVERY] Error during stale notification reconciliation: {e}")
        return 0


def get_unreconciled_notifications(db):
    """Returns list of all notifications requiring manual reconciliation"""
    if db is None:
        return []
    notifs_col = db['notifications_log']
    return list(notifs_col.find({"status": "delivery_uncertain"}).sort("updated_at", -1))


def reconcile_notification(db, notif_id, action="mark_failed", reason=""):
    """
    Safe manual-reconciliation handler for delivery_uncertain notifications.
    Actions supported:
      - 'mark_failed': Confirms delivery was not completed, records failure reason.
      - 'mark_sent': Confirms external delivery succeeded, records sent_at.
    """
    if db is None:
        return False, "Database not available"

    notifs_col = db['notifications_log']
    now = datetime.now(timezone.utc)

    query = {"_id": notif_id}
    if isinstance(notif_id, str):
        try:
            query = {"_id": ObjectId(notif_id)}
        except Exception:
            query = {"_id": notif_id}

    doc = notifs_col.find_one(query)
    if not doc:
        return False, f"Notification {notif_id} not found"

    if action == "mark_failed":
        update = {
            "$set": {
                "status": "failed",
                "requires_reconciliation": False,
                "reconciled_at": now,
                "updated_at": now,
                "error": reason or "Manually reconciled as failed delivery."
            }
        }
    elif action == "mark_sent":
        update = {
            "$set": {
                "status": "sent",
                "requires_reconciliation": False,
                "reconciled_at": now,
                "sent_at": now,
                "updated_at": now,
                "error": None
            }
        }
    else:
        return False, f"Unsupported action: {action}"

    res = notifs_col.update_one(query, update)
    return res.modified_count > 0, "Updated successfully"
