# SPDX-License-Identifier: GPL-3.0-or-later
"""Backend-neutral text measurement for the two-way fan chart."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class TextMeasurement:
    """Measured dimensions of a text string in millimetres."""

    width_mm: float
    height_mm: float


class TextMeasurer(Protocol):
    """Protocol for backend-neutral text measurement."""

    def measure(self, text: str, *, font_size: float) -> TextMeasurement:
        ...


class FakeTextMeasurer:
    """Deterministic fake measurer for testing without a font backend.

    Assumes a fixed character width and line height, scaled by font_size
    relative to a base size of 10pt.
    """

    def __init__(self, *, char_width_mm: float = 0.5, line_height_mm: float = 2.0) -> None:
        self._char_width_mm = char_width_mm
        self._line_height_mm = line_height_mm

    def measure(self, text: str, *, font_size: float) -> TextMeasurement:
        scale = font_size / 10.0
        lines = text.split("\n")
        max_chars = max((len(line) for line in lines), default=0)
        width = max_chars * self._char_width_mm * scale
        height = len(lines) * self._line_height_mm * scale
        return TextMeasurement(width_mm=width, height_mm=height)


def measure_text(
    measurer: TextMeasurer,
    text: str,
    *,
    font_size: float,
) -> TextMeasurement:
    """Measure a text string using the provided measurer."""
    return measurer.measure(text, font_size=font_size)


def fit_text(
    measurer: TextMeasurer,
    text: str,
    *,
    font_size: float,
    max_width_mm: float,
) -> str:
    """Truncate text with ellipsis if it exceeds max_width_mm.

    Returns the original text if it fits, otherwise a truncated version
    ending with '…' that fits within the constraint.
    """
    if not text:
        return ""

    m = measurer.measure(text, font_size=font_size)
    if m.width_mm <= max_width_mm:
        return text

    # Binary search for the longest prefix that fits
    lo, hi = 1, len(text)
    best = 1
    while lo <= hi:
        mid = (lo + hi) // 2
        candidate = text[:mid] + "…"
        m2 = measurer.measure(candidate, font_size=font_size)
        if m2.width_mm <= max_width_mm:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1

    return text[:best] + "…"