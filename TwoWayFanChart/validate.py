# SPDX-License-Identifier: GPL-3.0-or-later
"""Privacy validation for serialized report outputs."""

from __future__ import annotations

import base64
import binascii
import html
import re
import unicodedata
from urllib.parse import unquote


_DATA_URI_BASE64 = re.compile(
    r"data:[^\s\"'<>]*?;base64,([A-Za-z0-9+/]+={0,2})",
    re.IGNORECASE,
)


class PrivacyLeakError(RuntimeError):
    """Raised without echoing the sensitive values that were detected."""


def _decoded_views(text: str) -> tuple[str, ...]:
    views = {text}
    frontier = {text}
    for _ in range(3):
        expanded: set[str] = set()
        for value in frontier:
            expanded.add(html.unescape(value))
            expanded.add(unquote(value))
        expanded -= views
        if not expanded:
            break
        views.update(expanded)
        frontier = expanded

    for value in tuple(views):
        for payload in _DATA_URI_BASE64.findall(value):
            try:
                decoded = base64.b64decode(payload, validate=True).decode(
                    "utf-8", errors="replace"
                )
            except (binascii.Error, ValueError):
                continue
            views.add(decoded)
    return tuple(views)


def _normalized(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def count_privacy_leaks(
    output: str | bytes,
    forbidden_values: tuple[str, ...] | list[str],
) -> int:
    """Count distinct forbidden values visible in decoded output representations."""
    if isinstance(output, bytes):
        text = output.decode("utf-8", errors="replace")
    elif isinstance(output, str):
        text = output
    else:
        raise TypeError("output must be text or bytes")

    values = tuple(forbidden_values)
    if any(not isinstance(value, str) or not value for value in values):
        raise ValueError("forbidden values must be non-empty strings")

    views = tuple(_normalized(view) for view in _decoded_views(text))
    return sum(
        1
        for value in set(values)
        if any(_normalized(value) in view for view in views)
    )


def assert_no_privacy_leaks(
    output: str | bytes,
    forbidden_values: tuple[str, ...] | list[str],
) -> None:
    """Reject leaking output while keeping sensitive values out of diagnostics."""
    count = count_privacy_leaks(output, forbidden_values)
    if count:
        raise PrivacyLeakError(
            f"privacy leak detected ({count} forbidden value(s)); output rejected"
        )


# ---------------------------------------------------------------------------
# SVG structural validation
# ---------------------------------------------------------------------------

import xml.etree.ElementTree as ET


def validate_svg_output(svg: str) -> list[str]:
    """Validate a standalone SVG string for structural integrity.

    Returns a list of error messages; empty list means valid.
    """
    errors: list[str] = []

    # XML well-formedness
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        errors.append(f"XML parse error: {exc}")
        return errors

    tag = root.tag
    if not tag.endswith("}svg"):
        errors.append("root element is not <svg>")

    # viewBox required
    viewBox = root.attrib.get("viewBox")
    if not viewBox:
        errors.append("missing viewBox attribute")

    # Duplicate IDs
    id_counts: dict[str, int] = {}
    for elem in root.iter():
        elem_id = elem.attrib.get("id")
        if elem_id:
            id_counts[elem_id] = id_counts.get(elem_id, 0) + 1
    for eid, count in id_counts.items():
        if count > 1:
            errors.append(f"duplicate id: {eid} ({count} occurrences)")

    # External resources
    for elem in root.iter():
        for attr_name, attr_val in elem.attrib.items():
            lowered = attr_val.lower()
            if lowered.startswith("http://") or lowered.startswith("https://"):
                if not attr_val.startswith("data:"):
                    errors.append(f"external HTTP resource in {attr_name}")
            if lowered.startswith("file://"):
                errors.append(f"file:// resource in {attr_name}")

    # No scripts
    for elem in root.iter():
        if elem.tag.endswith("}script"):
            errors.append("script element found — SVG must be static")

    return errors
