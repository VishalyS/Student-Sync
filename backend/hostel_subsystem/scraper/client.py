"""
HTTP Client foundation for Student Sync - Hostel subsystem.
Wraps synchronous httpx.Client with lifecycle management, safe logging,
error translation, and deterministic mock transport support.
"""
import time
from typing import Any, Dict, Optional
import httpx

from config.settings import HostelConfig
from core.exceptions import NetworkError, TimeoutError
from core.logging import get_logger, redact_headers

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class HostelHttpClient:
    """
    Synchronous HTTP client managing connections, headers, timeouts,
    and safe logging for the Hostel subsystem.
    """

    def __init__(
        self,
        config: HostelConfig,
        transport: Optional[httpx.BaseTransport] = None,
        logger: Optional[Any] = None,
    ) -> None:
        self.config = config
        self.logger = logger or get_logger("student_sync_hostel.http")

        default_headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
        }

        timeout = httpx.Timeout(
            timeout=config.request_timeout,
            connect=5.0,
        )

        self._client = httpx.Client(
            base_url=config.base_url,
            headers=default_headers,
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
        )
        self._is_closed = False
        self._auth_session: Optional[Any] = None

    @property
    def is_closed(self) -> bool:
        """Return True if the underlying HTTP client connection is closed."""
        return self._is_closed

    @property
    def base_url(self) -> str:
        """Return the configured base URL string."""
        return str(self._client.base_url)

    @property
    def auth_session(self) -> Optional[Any]:
        """Return the current active AuthenticatedSession if set."""
        return self._auth_session

    def set_session(self, session: Any) -> None:
        """Attach an active AuthenticatedSession to automatically inject Authorization headers."""
        self._auth_session = session

    def clear_session(self) -> None:
        """Clear active session and release tokens from memory."""
        self._auth_session = None

    def authenticate(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Any:
        """
        Execute authentication and attach the resulting session to this client.
        """
        from scraper.auth import HostelAuthenticator
        authenticator = HostelAuthenticator(client=self, logger=self.logger)
        session = authenticator.login(username=username, password=password)
        self.set_session(session)
        return session

    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """
        Execute an HTTP request with error translation and safe event logging.

        Raises:
            TimeoutError: If the request exceeds the configured timeout.
            NetworkError: If a connection error or transport failure occurs.
        """
        if self._is_closed:
            raise NetworkError("Cannot execute request: HTTP client is closed")

        start_time = time.perf_counter()
        request_headers = dict(headers) if headers else {}
        if self._auth_session and "Authorization" not in request_headers and "authorization" not in request_headers:
            request_headers.update(self._auth_session.auth_headers)

        sanitized_headers = redact_headers(request_headers)

        try:
            response = self._client.request(
                method=method.upper(),
                url=path,
                params=params,
                data=data,
                json=json,
                headers=request_headers,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            self.logger.debug(
                "HTTP %s %s -> Status: %d (%.1fms)",
                method.upper(),
                path,
                response.status_code,
                duration_ms,
            )
            return response

        except httpx.TimeoutException as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self.logger.error("HTTP %s %s TIMEOUT after %.1fms", method.upper(), path, duration_ms)
            raise TimeoutError(f"HTTP request to '{path}' timed out after {self.config.request_timeout}s") from exc

        except (httpx.NetworkError, httpx.TransportError) as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self.logger.error("HTTP %s %s NETWORK ERROR (%.1fms)", method.upper(), path, duration_ms)
            raise NetworkError(f"Network error communicating with '{path}': {type(exc).__name__}") from exc

    def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Perform an HTTP GET request."""
        return self.request("GET", path, params=params, headers=headers)

    def post(
        self,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Perform an HTTP POST request."""
        return self.request("POST", path, data=data, json=json, headers=headers)

    def close(self) -> None:
        """Safely close underlying connection pools and clear session."""
        if not self._is_closed:
            self.clear_session()
            self._client.close()
            self._is_closed = True

    def __enter__(self) -> "HostelHttpClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
