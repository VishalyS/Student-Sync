"""
Authentication management for Student Sync - Hostel subsystem.
Handles credentials, executes POST /Hostel/Login/Authenticate,
manages session tokens, and produces safe AuthenticatedSession instances.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import httpx

from core.exceptions import AuthenticationError, NetworkError, SchemaError, TimeoutError
from core.logging import get_logger

LOGIN_PATH = "/Hostel/Login/Authenticate"


@dataclass(frozen=True)
class AuthenticatedSession:
    """
    Immutable container representing an active authenticated session.
    Guarantees secrets are masked in any string representation.
    """
    student_roll: str
    _token: str = field(repr=False)
    _refresh_token: Optional[str] = field(default=None, repr=False)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def token(self) -> str:
        """Internal accessor for the Bearer token."""
        return self._token

    @property
    def refresh_token(self) -> Optional[str]:
        """Internal accessor for the Refresh token."""
        return self._refresh_token

    @property
    def auth_headers(self) -> Dict[str, str]:
        """Produce the Authorization header required for authenticated endpoints."""
        return {"Authorization": f"Bearer {self._token}"}

    def __repr__(self) -> str:
        masked_user = f"{self.student_roll[:2]}***" if len(self.student_roll) > 2 else "***"
        return (
            f"AuthenticatedSession(student_roll={masked_user!r}, "
            f"token='***REDACTED***', "
            f"has_refresh_token={bool(self._refresh_token)}, "
            f"created_at={self.created_at.isoformat()!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()


class HostelAuthenticator:
    """
    Executes authentication against the Hostel portal and validates the response.
    """

    def __init__(self, client: Any, logger: Optional[Any] = None) -> None:
        self.client = client
        self.logger = logger or get_logger("student_sync_hostel.auth")

    def login(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> AuthenticatedSession:
        """
        Authenticate against /Hostel/Login/Authenticate using provided or configured credentials.

        Raises:
            AuthenticationError: If credentials are invalid, dummy roll number ('nil') is returned,
                                or HTTP 401/403 is received.
            SchemaError: If response is not valid JSON or lacks the required 'Token' field.
            NetworkError / TimeoutError: On transport or timeout failures.
        """
        user_val = username if username is not None else self.client.config.username
        pwd_val = password if password is not None else self.client.config.password
        user = str(user_val).strip().upper()
        pwd = str(pwd_val).strip()

        if not user:
            raise AuthenticationError("Cannot authenticate: username is missing or empty")
        if not pwd:
            raise AuthenticationError("Cannot authenticate: password is missing or empty")

        payload = {
            "name": user,
            "password": pwd,
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{self.client.base_url}/Hostel",
        }

        self.logger.info("Attempting authentication for user %s", f"{user[:2]}***")

        try:
            response = self.client.post(
                LOGIN_PATH,
                data=payload,
                headers=headers,
            )
        except TimeoutError:
            raise
        except NetworkError:
            raise

        return self._process_response(response, user)

    def _process_response(self, response: httpx.Response, user: str) -> AuthenticatedSession:
        """Validate HTTP status, parse JSON, and extract session tokens."""
        status = response.status_code

        if status == 401:
            self.logger.warning("Authentication failed: HTTP 401 Unauthorized for user %s", f"{user[:2]}***")
            raise AuthenticationError("Authentication failed: Invalid username or password (HTTP 401)")
        elif status == 403:
            self.logger.warning("Authentication failed: HTTP 403 Forbidden for user %s", f"{user[:2]}***")
            raise AuthenticationError("Authentication failed: Access forbidden (HTTP 403)")
        elif status >= 500:
            self.logger.error("Authentication failed: Server error (HTTP %d)", status)
            raise NetworkError(f"Hostel server error during authentication (HTTP {status})")
        elif status != 200:
            self.logger.error("Authentication failed: Unexpected HTTP status %d", status)
            raise AuthenticationError(f"Authentication failed with unexpected HTTP status {status}")

        try:
            body = response.json()
        except Exception as exc:
            self.logger.error("Authentication failed: Response is not valid JSON")
            raise SchemaError("Authentication response body is not valid JSON") from exc

        if not isinstance(body, dict):
            self.logger.error("Authentication failed: JSON root is not an object")
            raise SchemaError("Authentication response JSON root must be an object")

        if "Token" not in body:
            self.logger.error("Authentication failed: 'Token' field missing from response")
            raise SchemaError("Authentication response missing required 'Token' field")

        raw_token = str(body["Token"]).strip()
        if raw_token == "nil":
            self.logger.warning("Authentication rejected: Server returned dummy rollno token 'nil'")
            raise AuthenticationError("Authentication rejected: Enter your original Roll Number (Token is 'nil')")
        elif not raw_token:
            self.logger.error("Authentication failed: 'Token' field is empty")
            raise AuthenticationError("Authentication failed: Empty token received from server")

        raw_refresh = body.get("RefreshToken")
        refresh_token = str(raw_refresh).strip() if raw_refresh else None

        self.logger.info("Authentication successful for user %s", f"{user[:2]}***")

        return AuthenticatedSession(
            student_roll=user,
            _token=raw_token,
            _refresh_token=refresh_token,
        )
