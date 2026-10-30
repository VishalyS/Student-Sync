"""
backend/crypto_service.py

Secure credential protection service for Student Sync:
1. Authenticated symmetric encryption at rest using Fernet (AES-128-CBC + HMAC-SHA256).
2. Environment-provided master key (STUDENT_SYNC_ENCRYPTION_KEY or ENCRYPTION_KEY).
3. Production guard: Refuses to run in production without explicit master key.
4. Safe backward-compatible migration of legacy plaintext records.
5. In-memory decryption only during active portal scraping or login verification.
6. Zero logging of credentials or cryptographic keys.
"""

import os
import sys
import base64
import hashlib
import logging
from typing import Optional, Dict, Any

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# Prefix to distinguish authenticated encrypted credentials from legacy plaintext
CIPHERTEXT_PREFIX = "enc:v1:"

_is_production = os.getenv('FLASK_ENV', os.getenv('ENV', 'development')).lower() == 'production'

_raw_key = os.getenv('STUDENT_SYNC_ENCRYPTION_KEY') or os.getenv('ENCRYPTION_KEY')
if not _raw_key:
    if _is_production:
        raise RuntimeError(
            "CRITICAL SECURITY ERROR: STUDENT_SYNC_ENCRYPTION_KEY environment variable MUST be "
            "explicitly set in production mode. Refusing to run with unencrypted or fallback credentials."
        )
    # Development/Test fallback key derived deterministically from secret
    _raw_key = os.getenv('SECRET_KEY', 'student_sync_dev_encryption_key_2026_psgtech')


def _derive_fernet_key(key_material: str) -> bytes:
    """Derives a standard 32-byte URL-safe base64-encoded key for Fernet."""
    if not key_material:
        raise ValueError("Encryption key material cannot be empty.")
    try:
        # Check if already a valid 32-byte base64 key
        decoded = base64.urlsafe_b64decode(key_material.strip().encode('utf-8'))
        if len(decoded) == 32:
            return key_material.strip().encode('utf-8')
    except Exception:
        pass
    # Derive deterministic 32-byte key using SHA-256
    digest = hashlib.sha256(key_material.strip().encode('utf-8')).digest()
    return base64.urlsafe_b64encode(digest)


_fernet_key = _derive_fernet_key(_raw_key)
_cipher_suite = Fernet(_fernet_key)


def is_encrypted(val: Any) -> bool:
    """Returns True if the value is an authenticated encrypted credential."""
    if not val or not isinstance(val, str):
        return False
    return val.startswith(CIPHERTEXT_PREFIX)


def encrypt_credential(plaintext: Optional[str]) -> str:
    """
    Encrypts a portal credential using authenticated Fernet encryption.
    If the value is already encrypted or empty, returns it safely.
    """
    if not plaintext:
        return ""
    str_val = str(plaintext).strip()
    if is_encrypted(str_val):
        return str_val

    token = _cipher_suite.encrypt(str_val.encode('utf-8')).decode('utf-8')
    return f"{CIPHERTEXT_PREFIX}{token}"


def decrypt_credential(ciphertext: Optional[str]) -> str:
    """
    Decrypts an encrypted portal credential in memory.
    If the value is legacy plaintext (does not have prefix), returns it safely
    for backwards compatibility during rolling migrations.
    Raises ValueError on token tampering or key mismatch.
    """
    if not ciphertext:
        return ""
    str_val = str(ciphertext).strip()
    if not is_encrypted(str_val):
        # Legacy plaintext credential
        return str_val

    token = str_val[len(CIPHERTEXT_PREFIX):]
    try:
        decrypted_bytes = _cipher_suite.decrypt(token.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')
    except InvalidToken:
        logger.error("Credential decryption failed: invalid token signature or encryption key mismatch.")
        raise ValueError("Credential decryption failed: authentication tag verification failed.")
    except Exception as e:
        logger.error(f"Unexpected decryption error: {type(e).__name__}")
        raise ValueError("Credential decryption failed.")


def get_student_portal_password(user_doc: Optional[Dict[str, Any]]) -> str:
    """
    Extracts and decrypts student portal password in memory.
    Returns empty string if document or password is missing.
    """
    if not user_doc or not isinstance(user_doc, dict):
        return ""
    raw_pwd = user_doc.get('password') or user_doc.get('pass_word') or ""
    return decrypt_credential(raw_pwd)


def migrate_student_credentials(users_collection) -> int:
    """
    Safely migrates all existing unencrypted student passwords to encrypted format.
    Atomic per-student updates; never overwrites empty or already encrypted passwords.
    Returns the count of successfully migrated student records.
    """
    if users_collection is None:
        return 0

    migrated_count = 0
    try:
        # Find all students where password does not start with CIPHERTEXT_PREFIX
        query = {
            "password": {
                "$exists": True,
                "$ne": None,
                "$not": {"$regex": f"^{CIPHERTEXT_PREFIX}"}
            }
        }
        students_to_migrate = list(users_collection.find(query, {"rollNo": 1, "password": 1}))
        for student in students_to_migrate:
            raw_password = student.get('password')
            if raw_password and not is_encrypted(raw_password):
                encrypted = encrypt_credential(raw_password)
                users_collection.update_one(
                    {"_id": student["_id"]},
                    {"$set": {"password": encrypted}}
                )
                migrated_count += 1

        if migrated_count > 0:
            logger.info(f"Successfully migrated {migrated_count} student portal credentials to encrypted storage.")
    except Exception as e:
        logger.error(f"Error during student credential migration: {e}")

    return migrated_count


def validate_production_key(key: Optional[str] = None, is_production: bool = True) -> bool:
    """
    Validates presence of encryption key in production mode.
    Raises RuntimeError if missing or empty when is_production=True.
    Returns True if valid key provided.
    """
    check_key = key if key is not None else (os.getenv('STUDENT_SYNC_ENCRYPTION_KEY') or os.getenv('ENCRYPTION_KEY'))
    if not check_key or not str(check_key).strip():
        if is_production:
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: STUDENT_SYNC_ENCRYPTION_KEY environment variable MUST be "
                "explicitly set in production mode. Refusing to run with unencrypted or fallback credentials."
            )
        return False
    return True


def reencrypt_credential(ciphertext: str, old_key: str, new_key: str) -> str:
    """
    Re-encrypts a credential ciphertext from old master key to new master key.
    Verifies authentication tag with old_key, then encrypts with new_key.
    Returns new ciphertext with CIPHERTEXT_PREFIX.
    """
    if not ciphertext or not is_encrypted(ciphertext):
        return ciphertext
    old_cipher = Fernet(_derive_fernet_key(old_key))
    new_cipher = Fernet(_derive_fernet_key(new_key))
    token = ciphertext[len(CIPHERTEXT_PREFIX):]
    plaintext_bytes = old_cipher.decrypt(token.encode('utf-8'))
    new_token = new_cipher.encrypt(plaintext_bytes).decode('utf-8')
    return f"{CIPHERTEXT_PREFIX}{new_token}"


def rotate_master_key(users_collection, old_key: str, new_key: str) -> int:
    """
    Rotates encryption key for all stored student portal credentials in users_collection.
    Safely re-encrypts records from old_key to new_key atomically per document.
    Returns the count of successfully rotated student credentials.
    """
    if users_collection is None or not old_key or not new_key:
        return 0

    rotated_count = 0
    query = {"password": {"$regex": f"^{CIPHERTEXT_PREFIX}"}}
    for student in users_collection.find(query, {"rollNo": 1, "password": 1}):
        old_ct = student.get("password")
        if old_ct and is_encrypted(old_ct):
            try:
                new_ct = reencrypt_credential(old_ct, old_key, new_key)
                users_collection.update_one(
                    {"_id": student["_id"]},
                    {"$set": {"password": new_ct}}
                )
                rotated_count += 1
            except Exception as e:
                logger.error(f"Failed rotating credential for student {student.get('rollNo')}: {e}")

    logger.info(f"Master key rotation complete: {rotated_count} credentials re-encrypted.")
    return rotated_count

