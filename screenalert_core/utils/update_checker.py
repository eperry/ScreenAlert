"""Optional in-app update checker for ScreenAlert."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional
from urllib.request import Request, urlopen

from screenalert_core.utils.constants import APP_REPO_URL, APP_RELEASE_API_URL, APP_VERSION

logger = logging.getLogger(__name__)


@dataclass
class UpdateInfo:
    """Represents update availability information."""

    is_update_available: bool
    current_version: str
    latest_version: str
    release_url: str


def _normalize_version(version: str) -> tuple:
    """Normalize version strings like `v2.1.0` into comparable tuples."""
    cleaned = re.sub(r"^[^0-9]*", "", (version or "").strip())
    parts = [int(p) for p in re.findall(r"\d+", cleaned)]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def check_for_updates(timeout_sec: float = 2.5) -> Optional[UpdateInfo]:
    """Check GitHub releases API for a newer version.

    Returns None if the check cannot be completed.
    """
    try:
        api_url = APP_RELEASE_API_URL
        request = Request(
            api_url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "ScreenAlert-UpdateChecker",
            },
        )
        with urlopen(request, timeout=timeout_sec) as response:
            payload = json.loads(response.read().decode("utf-8"))

        latest = payload.get("tag_name") or payload.get("name") or APP_VERSION
        latest_url = payload.get("html_url") or APP_REPO_URL

        current_tuple = _normalize_version(APP_VERSION)
        latest_tuple = _normalize_version(latest)
        available = latest_tuple > current_tuple

        return UpdateInfo(
            is_update_available=available,
            current_version=APP_VERSION,
            latest_version=latest,
            release_url=latest_url,
        )
    except Exception as error:
        logger.debug(f"Update check failed: {error}")
        return None
