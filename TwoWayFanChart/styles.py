# SPDX-License-Identifier: GPL-3.0-or-later
"""Color systems and palettes for the two-way fan chart."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PaletteName(Enum):
    MOCKUP = "mockup"
    MONOCHROME = "monochrome"


@dataclass(frozen=True, slots=True)
class Palette:
    """A complete color palette for the chart."""

    background: str
    card_fill: str
    primary_text: str
    lineage_a: str
    lineage_b: str
    neutral_warm: str
    light_gray: str
    borders: str
    secondary_text: str
    body_text: str


_MOCKUP_PALETTE = Palette(
    background="#FAF9F5",
    card_fill="#FFFFFF",
    primary_text="#141413",
    lineage_a="#D97757",
    lineage_b="#788C5D",
    neutral_warm="#E3DACC",
    light_gray="#F0EEE6",
    borders="#D1CFC5",
    secondary_text="#87867F",
    body_text="#3D3D3A",
)


def get_palette(name: PaletteName) -> Palette:
    """Return the palette for the given name."""
    if name is PaletteName.MONOCHROME:
        return monochrome_palette()
    return _MOCKUP_PALETTE


def monochrome_palette() -> Palette:
    """Return a grayscale palette that remains readable without color."""
    return Palette(
        background="#FFFFFF",
        card_fill="#FFFFFF",
        primary_text="#141413",
        lineage_a="#8C8C8C",
        lineage_b="#B0B0B0",
        neutral_warm="#D9D9D9",
        light_gray="#F0F0F0",
        borders="#C0C0C0",
        secondary_text="#878787",
        body_text="#3D3D3D",
    )


def lineage_color(palette: Palette, lineage: str) -> str:
    """Return the color for a lineage identifier (A, B, or unknown)."""
    if lineage.upper() == "A":
        return palette.lineage_a
    if lineage.upper() == "B":
        return palette.lineage_b
    return palette.neutral_warm


def _clamp_byte(value: int) -> int:
    return max(0, min(255, value))


def _lighten(hex_color: str, factor: float) -> str:
    """Lighten a hex color by the given factor (0 = unchanged, 1 = white)."""
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    r = _clamp_byte(int(r + (255 - r) * factor))
    g = _clamp_byte(int(g + (255 - g) * factor))
    b = _clamp_byte(int(b + (255 - b) * factor))
    return f"#{r:02X}{g:02X}{b:02X}"


def generation_shade(base_color: str, *, generation: int) -> str:
    """Lighten a color based on generation depth.

    Generation 0 is the base color; higher generations are progressively lighter.
    """
    if generation <= 0:
        return base_color
    # Each generation lightens by ~8%, capped at white
    factor = min(generation * 0.08, 1.0)
    return _lighten(base_color, factor)


# ---------------------------------------------------------------------------
# Mockup fan-chart sector fills (from reference mockup)
# ---------------------------------------------------------------------------

# Ancestor sector fills per generation and lineage.
# Paternal (lineage "a") = coral shades; Maternal (lineage "b") = sage shades.
# Generation 1 (parents), 2 (grandparents), 3 (great-grandparents).
ANCESTOR_FILLS: dict[tuple[int, str], str] = {
    (1, "a"): "#F8ECE7",
    (1, "b"): "#EEF2E8",
    (2, "a"): "#F4E3DB",
    (2, "b"): "#E7EDDD",
    (3, "a"): "#EED8CD",
    (3, "b"): "#DCE5CF",
}

# Descendant sector fills (very light, alternating subtly).
DESCENDANT_FILLS: tuple[str, ...] = (
    "#F3EEE5",
    "#EEF1E8",
    "#F7EBE6",
)

# Additional visual constants from mockup.
MEDALLION_BORDER = "#A08060"
MEDALLION_FILL = "#FFFFFF"
HIDDEN_FILL = "#D0D0D0"
TEXT_DARK = "#4A4A4A"
TEXT_GREY = "#888888"
SECTOR_STROKE = "#FFFFFF"
SECTOR_STROKE_WIDTH = 0.3
RING_GAP = 0.3  # mm between rings


def ancestor_fill(generation: int, lineage: str) -> str:
    """Return the sector fill color for an ancestor at the given generation and lineage."""
    key = (generation, lineage.lower())
    return ANCESTOR_FILLS.get(key, "#F0EEE6")


def descendant_fill(index: int) -> str:
    """Return a descendant sector fill, cycling through the palette."""
    return DESCENDANT_FILLS[index % len(DESCENDANT_FILLS)]