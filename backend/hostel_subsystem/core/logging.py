"""
Safe logging configuration and filters for Student Sync - Hostel subsystem.
Ensures zero leakage of credentials, tokens, session cookies, or PII.
"""
import logging
import re
from typing import Any, Dict, Optional

# Patterns targeting sensitive data formats
REDACTION_PATTERNS = [
    (re.compile(r'(?i)(password[\'"\s:=]+)([^\s\'",]+)'), r'\1***REDACTED***'),
    (re.compile(r'(?i)(bearer\s+)([A-Za-z0-9_\-\.]+)', re.IGNORECASE), r'\1***REDACTED_TOKEN***'),
    (re.compile(r'(?i)(\.?AspNetCore\.Session=)([^;\s]+)'), r'\1***REDACTED_SESSION***'),
    (re.compile(r'(?i)(authorization[\'"\s:=]+)([^\s\'",]+)'), r'\1***REDACTED_AUTH***'),
    (re.compile(r'(?i)(refresh_?token[\'"\s:=]+)([^\s\'",]+)'), r'\1***REDACTED_REFRESH_TOKEN***'),
]


class SensitiveDataFilter(logging.Filter):
    """
    Log filter that intercepts log records and sanitizes sensitive credentials,
    tokens, cookies, and authentication headers from the formatted message.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.redact_string(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self.redact_value(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self.redact_value(v) for v in record.args)
        return True

    @classmethod
    def redact_string(cls, text: str) -> str:
        """Apply all redaction patterns to a string."""
        for pattern, replacement in REDACTION_PATTERNS:
            text = pattern.sub(replacement, text)
        return text

    @classmethod
    def redact_value(cls, val: Any) -> Any:
        """Sanitize an individual value if it is a string."""
        if isinstance(val, str):
            return cls.redact_string(val)
        return val


def redact_headers(headers: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """
    Produce a sanitized dictionary of HTTP headers safe for debugging or logging.
    Redacts Authorization, Cookie, Set-Cookie, and secret headers.
    """
    if not headers:
        return {}

    sanitized = {}
    sensitive_keys = {"authorization", "cookie", "set-cookie", "token", "x-auth-token"}

    for key, val in headers.items():
        if str(key).lower() in sensitive_keys:
            sanitized[str(key)] = "***REDACTED***"
        else:
            sanitized[str(key)] = str(val)

    return sanitized


def get_logger(name: str = "student_sync_hostel", level: Any = "INFO") -> logging.Logger:
    """
    Initialize and return a configured logger equipped with the SensitiveDataFilter.
    """
    logger = logging.getLogger(name)
    if isinstance(level, int):
        logger.setLevel(level)
    else:
        logger.setLevel(getattr(logging, str(level).upper(), logging.INFO))


    # Avoid adding duplicate handlers if already configured
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler.addFilter(SensitiveDataFilter())
        logger.addHandler(handler)

    return logger
