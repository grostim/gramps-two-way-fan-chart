# SPDX-License-Identifier: GPL-3.0-or-later
"""Physical and radial geometry primitives for the two-way fan chart."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# Unit conversions
# ---------------------------------------------------------------------------

_PT_PER_MM = 72.0 / 25.4  # 1 inch = 25.4 mm = 72 pt


def mm_to_pt(mm: float) -> float:
    """Convert millimetres to PostScript points."""
    return mm * _PT_PER_MM


def mm_to_px(mm: float, *, dpi: int = 96) -> float:
    """Convert millimetres to pixels at the given DPI."""
    return mm * dpi / 25.4


def deg2rad(degrees: float) -> float:
    """Convert degrees to radians."""
    return math.radians(degrees)


# ---------------------------------------------------------------------------
# Paper sizes
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class _PaperDims:
    width_mm: float
    height_mm: float


class PaperSize(Enum):
    """Standard paper sizes with dimensions in millimetres."""

    A0 = _PaperDims(841, 1189)
    A1 = _PaperDims(594, 841)
    A2 = _PaperDims(420, 594)
    A3 = _PaperDims(297, 420)
    A4 = _PaperDims(210, 297)
    A5 = _PaperDims(148, 210)
    LETTER = _PaperDims(215.9, 279.4)
    LEGAL = _PaperDims(215.9, 355.6)
    TABLOID = _PaperDims(279.4, 431.8)
    CUSTOM = _PaperDims(0, 0)  # overridden at runtime

    @property
    def width_mm(self) -> float:
        return self.value.width_mm

    @property
    def height_mm(self) -> float:
        return self.value.height_mm


class Orientation(Enum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


# ---------------------------------------------------------------------------
# Page region with margins
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class PaperRegion:
    """A paper size, orientation, and margins yielding a content rectangle."""

    paper: PaperSize
    orientation: Orientation
    margin_mm: float = 12.0
    margin_left_mm: float | None = None
    margin_right_mm: float | None = None
    margin_top_mm: float | None = None
    margin_bottom_mm: float | None = None
    custom_width_mm: float | None = None
    custom_height_mm: float | None = None

    def _effective(self, override: float | None, fallback: float) -> float:
        return override if override is not None else fallback

    @property
    def width_mm(self) -> float:
        if self.paper is PaperSize.CUSTOM and self.custom_width_mm is not None:
            return self.custom_width_mm
        if self.orientation is Orientation.PORTRAIT:
            return self.paper.width_mm
        return self.paper.height_mm

    @property
    def height_mm(self) -> float:
        if self.paper is PaperSize.CUSTOM and self.custom_height_mm is not None:
            return self.custom_height_mm
        if self.orientation is Orientation.PORTRAIT:
            return self.paper.height_mm
        return self.paper.width_mm

    @property
    def effective_margin_left_mm(self) -> float:
        return self._effective(self.margin_left_mm, self.margin_mm)

    @property
    def effective_margin_right_mm(self) -> float:
        return self._effective(self.margin_right_mm, self.margin_mm)

    @property
    def effective_margin_top_mm(self) -> float:
        return self._effective(self.margin_top_mm, self.margin_mm)

    @property
    def effective_margin_bottom_mm(self) -> float:
        return self._effective(self.margin_bottom_mm, self.margin_mm)

    @property
    def content_width_mm(self) -> float:
        return self.width_mm - self.effective_margin_left_mm - self.effective_margin_right_mm

    @property
    def content_height_mm(self) -> float:
        return self.height_mm - self.effective_margin_top_mm - self.effective_margin_bottom_mm


# ---------------------------------------------------------------------------
# Polar / radial helpers
# ---------------------------------------------------------------------------

def polar_to_cartesian(
    radius: float,
    angle_rad: float,
    cx: float = 0,
    cy: float = 0,
) -> tuple[float, float]:
    """Convert polar coordinates to Cartesian.

    Convention: angle 0 = 12 o'clock (up), positive = clockwise.
    SVG coordinate system (y increases downward).
    """
    # Rotate so 0 = up instead of right, then flip for SVG y-down
    svg_angle = angle_rad - math.pi / 2
    x = cx + radius * math.cos(svg_angle)
    y = cy + radius * math.sin(svg_angle)
    return (x, y)


# ---------------------------------------------------------------------------
# Annular sector
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class AnnularSector:
    """A sector of an annular ring, defined by inner/outer radii and angles."""

    inner_radius: float
    outer_radius: float
    start_angle: float  # degrees, 0 = up, clockwise
    sweep_angle: float  # degrees, positive = clockwise
    cx: float = 0
    cy: float = 0

    @property
    def end_angle(self) -> float:
        return self.start_angle + self.sweep_angle

    @property
    def mid_angle(self) -> float:
        return self.start_angle + self.sweep_angle / 2


def arc_path(sector: AnnularSector) -> str:
    """Return an SVG path string for an annular sector.

    For inner_radius == 0, produces a pie slice.
    Angles are in degrees (0 = up, clockwise).
    """
    cx, cy = sector.cx, sector.cy
    r_outer = sector.outer_radius
    r_inner = sector.inner_radius
    start_rad = deg2rad(sector.start_angle)
    end_rad = deg2rad(sector.end_angle)
    sweep_rad = deg2rad(sector.sweep_angle)

    outer_start = polar_to_cartesian(r_outer, start_rad, cx, cy)
    outer_end = polar_to_cartesian(r_outer, end_rad, cx, cy)

    large_arc = 1 if abs(sweep_rad) > math.pi else 0

    if r_inner <= 0:
        # Pie slice: move to center, line to outer start, arc to outer end, close
        parts = [
            f"M {cx:.6g} {cy:.6g}",
            f"L {outer_start[0]:.6g} {outer_start[1]:.6g}",
            f"A {r_outer:.6g} {r_outer:.6g} 0 {large_arc} 1 {outer_end[0]:.6g} {outer_end[1]:.6g}",
            "Z",
        ]
    else:
        inner_start = polar_to_cartesian(r_inner, start_rad, cx, cy)
        inner_end = polar_to_cartesian(r_inner, end_rad, cx, cy)
        parts = [
            f"M {outer_start[0]:.6g} {outer_start[1]:.6g}",
            f"A {r_outer:.6g} {r_outer:.6g} 0 {large_arc} 1 {outer_end[0]:.6g} {outer_end[1]:.6g}",
            f"L {inner_end[0]:.6g} {inner_end[1]:.6g}",
            f"A {r_inner:.6g} {r_inner:.6g} 0 {large_arc} 0 {inner_start[0]:.6g} {inner_start[1]:.6g}",
            "Z",
        ]
    return " ".join(parts)