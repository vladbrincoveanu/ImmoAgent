"""Optional telemetry setup shared by the Python job entrypoints."""

import logging
import os
from typing import Any, Optional


logger = logging.getLogger(__name__)
_initialized = False


def init_sentry(sdk: Optional[Any] = None) -> bool:
    """Initialize Sentry when ``SENTRY_DSN`` is configured.

    Telemetry is deliberately optional: local runs and test environments do not
    need a Sentry account, and a telemetry setup failure must never prevent the
    scraper or alert poll from running. ``sdk`` is injectable so this contract
    can be tested without requiring sentry-sdk in the local test environment.
    """
    global _initialized
    if _initialized:
        return True

    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False

    if sdk is None:
        try:
            import sentry_sdk
        except ImportError:
            logger.warning("SENTRY_DSN is set but sentry-sdk is not installed")
            return False
        sdk = sentry_sdk

    options = {
        "dsn": dsn,
        "send_default_pii": True,
    }
    environment = os.getenv("SENTRY_ENVIRONMENT", "").strip()
    if environment:
        options["environment"] = environment

    try:
        sdk.init(**options)
    except Exception:
        logger.exception("Failed to initialize Sentry; continuing without telemetry")
        return False

    _initialized = True
    return True
