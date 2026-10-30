"""
Configuration loading and validation for Student Sync - Hostel subsystem.
Loads settings from local .env while enforcing strict secret protection.
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Union
from dotenv import dotenv_values

from core.exceptions import ConfigurationError

DEFAULT_BASE_URL = "https://edviewx.psgtech.ac.in"
DEFAULT_TIMEOUT = 10.0


@dataclass(frozen=True)
class HostelConfig:
    """
    Immutable application configuration container.
    Guarantees secrets are masked in any string representation.
    """
    base_url: str
    username: str
    password: str
    request_timeout: float = DEFAULT_TIMEOUT

    def __repr__(self) -> str:
        # Strictly mask credentials
        masked_user = f"{self.username[:2]}***" if len(self.username) > 2 else "***"
        return (
            f"HostelConfig(base_url={self.base_url!r}, "
            f"username={masked_user!r}, "
            f"password='***REDACTED***', "
            f"request_timeout={self.request_timeout})"
        )

    def __str__(self) -> str:
        return self.__repr__()


def load_config(
    env_path: Optional[Union[str, Path]] = None,
    overrides: Optional[Dict[str, Any]] = None,
) -> HostelConfig:
    """
    Load, validate, and construct a HostelConfig instance.

    Priority:
    1. Explicit overrides passed directly to function
    2. Values loaded from the specified or discovered .env file
    3. Existing os.environ variables
    4. Default fallbacks (for optional fields only)

    Raises:
        ConfigurationError: If any required setting is missing or invalid.
                            Errors never include sensitive credential values.
    """
    env_values: Dict[str, Any] = {}

    # Discover .env path if not specified
    if env_path is None:
        # Default to workspace root .env
        default_env = Path(__file__).resolve().parent.parent / ".env"
        if default_env.is_file():
            env_path = default_env

    # Load from file if path exists
    if env_path and Path(env_path).is_file():
        loaded = dotenv_values(dotenv_path=Path(env_path))
        for k, v in loaded.items():
            if v is not None:
                env_values[k] = v

    # Layer with process environment
    for k in ["HOSTEL_BASE_URL", "HOSTEL_USERNAME", "HOSTEL_PASSWORD", "REQUEST_TIMEOUT"]:
        if k in os.environ and k not in env_values:
            env_values[k] = os.environ[k]

    # Layer with explicit overrides
    if overrides:
        env_values.update(overrides)

    # 1. Base URL validation
    base_url = env_values.get("HOSTEL_BASE_URL", DEFAULT_BASE_URL)
    if not base_url or not str(base_url).strip():
        raise ConfigurationError("HOSTEL_BASE_URL is missing or empty")
    base_url = str(base_url).strip().rstrip("/")

    # 2. Username validation
    username = env_values.get("HOSTEL_USERNAME")
    if username is None or not str(username).strip():
        raise ConfigurationError("HOSTEL_USERNAME is missing or empty")
    username = str(username).strip().upper()

    # 3. Password validation
    password = env_values.get("HOSTEL_PASSWORD")
    if password is None or not str(password).strip():
        raise ConfigurationError("HOSTEL_PASSWORD is missing or empty")
    password = str(password).strip()

    # 4. Request timeout validation
    raw_timeout = env_values.get("REQUEST_TIMEOUT", DEFAULT_TIMEOUT)
    try:
        request_timeout = float(raw_timeout)
        if request_timeout <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        raise ConfigurationError("REQUEST_TIMEOUT must be a positive number")

    return HostelConfig(
        base_url=base_url,
        username=username,
        password=password,
        request_timeout=request_timeout,
    )
