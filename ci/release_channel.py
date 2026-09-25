"""Channel-specific metadata for one shared Gramps add-on ID."""

from __future__ import annotations

import os
import re

_CHANNELS = {
    "stable": ("STABLE", 3),
    "experimental": ("EXPERIMENTAL", 2),
}
_STATUS_PATTERN = re.compile(r"\bstatus\s*=\s*(?:STABLE|EXPERIMENTAL)\b")


def channel_status(channel: str) -> tuple[str, int]:
    """Return the Gramps registration token and listing status for a channel."""
    try:
        return _CHANNELS[channel]
    except (KeyError, TypeError) as error:
        raise ValueError(
            f"channel must be one of: {', '.join(_CHANNELS)}"
        ) from error


def channel_from_env() -> str:
    """Read and validate the build channel, defaulting to the stable channel."""
    channel = os.environ.get("TWFC_CHANNEL", "stable").strip().lower()
    channel_status(channel)
    return channel


def transform_registration(source: str, channel: str) -> str:
    """Set the archived registration's status without modifying source files."""
    status, _ = channel_status(channel)
    matches = list(_STATUS_PATTERN.finditer(source))
    if len(matches) != 1:
        raise ValueError(
            "registration must contain exactly one STABLE/EXPERIMENTAL status"
        )
    return _STATUS_PATTERN.sub(f"status={status}", source)
