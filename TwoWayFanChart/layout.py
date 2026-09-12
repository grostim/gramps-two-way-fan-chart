# SPDX-License-Identifier: GPL-3.0-or-later
"""Page canvas layout calculations for the two-way fan chart."""

from __future__ import annotations

import math
from dataclasses import dataclass

try:
    from TwoWayFanChart.geometry import PaperRegion, polar_to_cartesian, deg2rad
    from TwoWayFanChart.model import (
        DescendantBranch,
        SceneCircle,
        SceneImage,
        SceneMarker,
        SceneLegend,
        SceneNode,
        SceneRect,
        SceneSector,
        SceneText,
        ScenePathText,
        estimate_text_width,
    )
    from TwoWayFanChart.styles import (
        ancestor_fill,
        descendant_fill,
        MEDALLION_BORDER,
        MEDALLION_FILL,
        HIDDEN_FILL,
        TEXT_DARK,
        TEXT_GREY,
        CONTINUATION_DOT_FILL,
        SECTOR_STROKE,
        SECTOR_STROKE_WIDTH,
    )
except ModuleNotFoundError:
    from geometry import PaperRegion, polar_to_cartesian, deg2rad  # type: ignore[no-redef]
    from model import (  # type: ignore[no-redef]
        DescendantBranch,
        SceneCircle,
        SceneImage,
        SceneMarker,
        SceneLegend,
        SceneNode,
        SceneRect,
        SceneSector,
        SceneText,
        ScenePathText,
        estimate_text_width,
    )
    from styles import (  # type: ignore[no-redef]
        ancestor_fill,
        descendant_fill,
        MEDALLION_BORDER,
        MEDALLION_FILL,
        HIDDEN_FILL,
        TEXT_DARK,
        TEXT_GREY,
        CONTINUATION_DOT_FILL,
        SECTOR_STROKE,
        SECTOR_STROKE_WIDTH,
    )


# ---------------------------------------------------------------------------
# Layout constants (mm) — defaults from spec §5.6
# ---------------------------------------------------------------------------

_TITLE_ZONE_MM = 14.0  # title + subtitle area
_LEGEND_ZONE_MM = 18.0  # legend at bottom
_STATS_ZONE_MM = 6.0  # statistics line
_MIN_CENTER_RADIUS_MM = 8.0  # minimum medallion radius
_RING_GAP_MM = 0.3  # white space between generation rings
_ANCESTOR_TITLE_GAP_MM = 4.0
_DESCENDANT_TITLE_GAP_MM = 8.0
_DESCENDANT_FIRST_GEN_LINE_GAP_MM = 4.0  # minimum readable baseline gap
# When the target grandchild ring is widened, keep enough radial room in later
# rings for their identity labels before asking the direct-child ring to donate
# any remaining space. The value scales down on smaller paper sizes.
_DESCENDANT_LATER_RING_MIN_WIDTH_MM = 30.0
# Absolute lower bound for a later-generation identity lane after the
# grandchild transfer. The nominal floor above is allowed to scale down, but
# never below this amount, or the radial text capacity becomes zero.
_DESCENDANT_LATER_RING_MIN_LABEL_WIDTH_MM = 8.0
# The publication composition gives the descendant quarter a smaller visual
# footprint than the ancestor fan. Keep the ratio explicit so the A0 maquette
# and its regression probes share one geometric contract.
_DESCENDANT_OUTER_RADIUS_RATIO = 0.76
_DESCENDANT_MEDALLION_TARGET_RATIO = 28 / 600
_MEDALLION_EDGE_CLEARANCE_MM = 1.6
_MEDALLION_TEXT_RESERVE_RATIO = 0.58
_DIRECT_LABEL_MIN_FONT_SIZE_MM = 2.0
_DATE_FONT_STEP_MM = 1.0
_MIN_DATE_FONT_SIZE_MM = 0.25
_MIN_NAME_FONT_SIZE_MM = _MIN_DATE_FONT_SIZE_MM + _DATE_FONT_STEP_MM


@dataclass(frozen=True, slots=True)
class ChartCanvas:
    """Pre-calculated page regions for a two-way fan chart."""

    page_width_mm: float
    page_height_mm: float
    content_width_mm: float
    content_height_mm: float
    title_zone_mm: float
    legend_zone_mm: float
    center_radius_mm: float
    ancestor_inner_radius_mm: float
    ancestor_outer_radius_mm: float
    descendant_inner_radius_mm: float
    descendant_outer_radius_mm: float
    center_cx_mm: float
    center_cy_mm: float


def calculate_canvas(
    paper: PaperRegion,
    *,
    ancestor_generations: int,
    descendant_generations: int,
) -> ChartCanvas:
    """Calculate all page regions from paper size, margins, and generation counts.

    The layout fills the page: the center medallion occupies ~18% of the
    available radius, while the descendant quarter intentionally uses a
    compact outer radius so it does not visually compete with the ancestor fan.
    """
    content_w = paper.content_width_mm
    content_h = paper.content_height_mm

    title_zone = _TITLE_ZONE_MM
    legend_zone = _LEGEND_ZONE_MM + _STATS_ZONE_MM

    # Legend, stats card and family summary are intentionally omitted from the
    # publication scene. Keep their dimensions in ChartCanvas for API
    # compatibility, but do not reserve blank page bands for absent content.
    available_h = content_h
    available_w = content_w

    # Fill almost the complete content height while retaining enough room for
    # the two small-cap titles just outside the fan.
    max_radius = min(available_h / 2, available_w / 2) * 0.94

    # Center zone: the mockup uses 190 px inside a 600 px fan radius.
    # The ancestor/descendant rings start at this radius.
    center_radius = max(_MIN_CENTER_RADIUS_MM, max_radius * (190.0 / 600.0))

    # Ancestor generations use the full publication radius. Descendants remain
    # anchored on the same center ring but use a compact outer quarter; this
    # leaves useful breathing room below the chart and keeps the lower visual
    # mass subordinate to the accepted A0 ancestor composition.
    ancestor_outer = max_radius if ancestor_generations > 0 else center_radius
    descendant_outer = (
        max_radius * _DESCENDANT_OUTER_RADIUS_RATIO
        if descendant_generations > 0
        else center_radius
    )

    cx = paper.effective_margin_left_mm + content_w / 2

    # The two halves do not have the same visual height: the descendant fan
    # is intentionally compact while the ancestor fan fills the publication
    # radius. Center the visible composition bounds instead of the rosace
    # itself, so the lower paper margin is not needlessly oversized.
    top_extent = ancestor_outer + (
        _ANCESTOR_TITLE_GAP_MM if ancestor_generations > 0 else 0.0
    )
    bottom_extent = descendant_outer + (
        _DESCENDANT_TITLE_GAP_MM if descendant_generations > 0 else 0.0
    )
    cy = paper.effective_margin_top_mm + (
        content_h + top_extent - bottom_extent
    ) / 2

    return ChartCanvas(
        page_width_mm=paper.width_mm,
        page_height_mm=paper.height_mm,
        content_width_mm=content_w,
        content_height_mm=content_h,
        title_zone_mm=title_zone,
        legend_zone_mm=legend_zone,
        center_radius_mm=center_radius,
        ancestor_inner_radius_mm=center_radius,
        ancestor_outer_radius_mm=ancestor_outer,
        descendant_inner_radius_mm=center_radius,
        descendant_outer_radius_mm=descendant_outer,
        center_cx_mm=cx,
        center_cy_mm=cy,
    )


# ---------------------------------------------------------------------------
# Polar coordinate helpers (using the geometry module convention)
# ---------------------------------------------------------------------------

def _polar(cx: float, cy: float, r: float, angle_deg: float) -> tuple[float, float]:
    """Convert polar to cartesian. Angle 0=up, positive=clockwise (SVG convention)."""
    return polar_to_cartesian(r, deg2rad(angle_deg), cx, cy)


def _arc_text_path(
    cx: float, cy: float, r: float,
    start_angle: float, end_angle: float,
    *,
    lower: bool = False,
) -> str:
    """Build an SVG arc path suitable for textPath text placement.

    For upper-half sectors (ancestors), text reads left-to-right along the arc.
    For lower-half sectors (descendants), text is flipped to remain upright.
    """
    # Add a small margin so text doesn't touch sector boundaries
    margin = min(2.0, max(0.3, (end_angle - start_angle) * 0.06))
    a0 = start_angle + margin
    a1 = end_angle - margin
    if a1 <= a0:
        a0, a1 = start_angle, end_angle

    if lower:
        # For lower half, draw arc right-to-left so text is upright
        x1, y1 = _polar(cx, cy, r, a1)
        x2, y2 = _polar(cx, cy, r, a0)
        large = 1 if abs(a1 - a0) > 180 else 0
        return f"M {x1:.4f} {y1:.4f} A {r:.4f} {r:.4f} 0 {large} 0 {x2:.4f} {y2:.4f}"
    else:
        # For upper half, draw arc left-to-right
        x1, y1 = _polar(cx, cy, r, a0)
        x2, y2 = _polar(cx, cy, r, a1)
        large = 1 if abs(a1 - a0) > 180 else 0
        return f"M {x1:.4f} {y1:.4f} A {r:.4f} {r:.4f} 0 {large} 1 {x2:.4f} {y2:.4f}"


# ---------------------------------------------------------------------------
# Position ID parsing (extract.py uses "ancestor-{lineage}-{gen}-{index}")
# ---------------------------------------------------------------------------

def _parse_position_id(pid: str) -> tuple[str, int] | None:
    """Parse a position_id like 'ancestor-a-1-0' into (lineage, generation)."""
    if not pid:
        return None
    parts = pid.split("-")
    if len(parts) >= 4 and parts[0] == "ancestor":
        lineage = parts[1]
        try:
            gen = int(parts[2])
            return (lineage, gen)
        except ValueError:
            pass
    return None


def _extract_initials(label: str) -> str:
    """Extract initials from a display name like 'Doe, Jane' -> 'DJ'."""
    if not label:
        return ""
    if label in {"Personne privée", "Personnes privées"}:
        return "•"
    parts = label.replace(",", " ").split()
    parts = [p for p in parts if p and p[0].isalpha()]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0][:2].upper()
    # Use first letter of first name + first letter of last name
    return (parts[0][0] + parts[-1][0]).upper()


def _outward_radial_rotation(deg: float) -> float:
    """Rotate a horizontal baseline onto the sector's radial axis.

    Chart angles use 0° at the top while SVG text starts horizontally. The
    -90° correction aligns the baseline with the center-to-sector vector; the
    optional half-turn then keeps labels upright on the left side.
    """
    rot = deg - 90.0
    normalized = rot % 360
    if 90 < normalized < 270:
        rot += 180
    return rot


def _upright_tangent_rotation(deg: float) -> float:
    """Rotate a tangent label while keeping its baseline readable."""
    rot = deg
    normalized = rot % 360
    if 90 < normalized < 270:
        rot += 180
    return rot


def _tangent_offset(
    x: float,
    y: float,
    angle_deg: float,
    offset: float,
) -> tuple[float, float]:
    """Move a polar point along its local clockwise tangent."""
    angle = math.radians(angle_deg)
    return x + math.cos(angle) * offset, y + math.sin(angle) * offset


def _couple_line_offsets(
    angle_deg: float,
    separation: float,
) -> tuple[float, float]:
    """Return tangent offsets with the individual on the upper visual line."""
    # The SVG y component of the tangent changes sign on the lower fan's
    # vertical axis. Reverse the offsets on the left half so the spouse line
    # does not move above the individual there.
    if math.sin(math.radians(angle_deg)) < 0.0:
        return separation, -separation
    return -separation, separation


def _ancestor_radial_name_lane(
    *,
    medallion_position: float,
    medallion_radius: float,
    outer_radius: float,
) -> tuple[float, float]:
    """Return the center and width of the radial name lane in one cell.

    Generation-three names are turned 90° from the ring tangent. Their text
    width therefore consumes the radial space after the medallion, not the
    angular arc length used by curved labels in the nearer rings.
    """
    text_start = medallion_position + medallion_radius + 2.0
    text_end = outer_radius - 1.5
    width = max(0.0, text_end - text_start)
    return text_start + width / 2.0, width


def _ancestor_tangent_name_lane(
    *,
    name_radius: float,
    sweep_angle: float,
) -> tuple[float, float]:
    """Return the center and chord width of a tangent name lane."""
    half_chord = name_radius * math.sin(
        math.radians(max(sweep_angle, 0.0) / 2.0)
    )
    return name_radius, max(0.0, 2.0 * half_chord - 2.0)


def _ancestor_arc_text_capacity(
    *,
    text_radius: float,
    sweep_angle: float,
) -> float:
    """Return the usable arc length for one curved ancestor label."""
    margin = min(2.0, max(0.3, max(sweep_angle, 0.0) * 0.06))
    usable_sweep = max(0.0, sweep_angle - 2.0 * margin)
    return max(0.0, text_radius * math.radians(usable_sweep))


def _date_font_size(name_font_size: float) -> float:
    """Return the date size, exactly one scene unit below the name size."""
    if name_font_size < _MIN_NAME_FONT_SIZE_MM:
        # A date below the minimum readable date size is omitted by the
        # callers rather than forcing the generation's complete name below
        # its measured capacity or violating the one-step relationship.
        return 0.0
    return name_font_size - _DATE_FONT_STEP_MM


def _font_size_for_width(
    content: str,
    *,
    target_size: float,
    max_width: float,
) -> float:
    """Return the largest size that keeps complete content in its lane."""
    if not content or max_width <= 0.0:
        return max(_MIN_DATE_FONT_SIZE_MM, target_size)
    natural_at_one = estimate_text_width(content, 1.0)
    if natural_at_one <= 0.0:
        return max(_MIN_DATE_FONT_SIZE_MM, target_size)
    return max(
        _MIN_DATE_FONT_SIZE_MM,
        min(target_size, max_width / natural_at_one),
    )


def _fit_text_to_width(
    content: str,
    *,
    target_size: float,
    minimum_size: float,
    max_width: float,
    allow_ellipsis: bool = False,
) -> tuple[str, float, float]:
    """Fit text to a physical lane while retaining both identity ends."""
    available = max(max_width, 0.5 if not allow_ellipsis else 0.0)
    if not content or available <= 0:
        return "", max(minimum_size, 0.0), available

    natural_at_one = estimate_text_width(content, 1.0)
    size = target_size
    if natural_at_one > 0:
        size = min(target_size, available / natural_at_one)
    size = max(minimum_size, size)

    fitted = content
    if allow_ellipsis and estimate_text_width(fitted, size) > available:
        left = (len(content) + 1) // 2
        right = len(content) - left
        while left + right > 1:
            candidate = content[:left].rstrip() + "…" + content[len(content) - right:].lstrip()
            if estimate_text_width(candidate, size) <= available:
                fitted = candidate
                break
            if left >= right:
                left -= 1
            else:
                right -= 1
        else:
            fitted = "…" if estimate_text_width("…", size) <= available else ""
    return fitted, size, available


def _first_generation_line_layout(
    lines: list[tuple[str, bool, str]],
    *,
    text_start: float,
    text_end: float,
) -> list[tuple[tuple[str, bool, str], float]]:
    """Place first-generation text without collapsing readable radial lanes.

    Dates are optional when a compact page cannot sustain the requested
    spacing. Identity lines are retained first; if even those identities cannot
    occupy separate lanes, they are combined into one lane instead of sharing a
    radius. The latter keeps the data visible while avoiding an unreadable
    overlay on A4/A5 and custom small canvases.
    """
    radial_span = max(0.0, text_end - text_start)
    selected = list(lines)
    if len(selected) > 1:
        maximum_line_count = max(
            1,
            math.floor(
                (radial_span + 1e-9) / _DESCENDANT_FIRST_GEN_LINE_GAP_MM
            ) + 1,
        )
        if maximum_line_count < len(selected):
            identity_lines = [line for line in selected if line[1]]
            if len(identity_lines) > maximum_line_count:
                selected = [
                    (
                        " / ".join(line[0] for line in identity_lines),
                        True,
                        TEXT_DARK,
                    )
                ]
            else:
                # Drop optional date lanes before sacrificing either identity.
                selected = identity_lines

    if len(selected) <= 1:
        radii = [text_start + radial_span / 2.0] if selected else []
    elif radial_span / len(selected) >= _DESCENDANT_FIRST_GEN_LINE_GAP_MM:
        # Preserve the generous full-span composition when it is already
        # readable; this avoids shrinking the established A0 layout.
        radii = [
            text_start + radial_span * (index + 0.5) / len(selected)
            for index in range(len(selected))
        ]
    else:
        maximum_line_gap = radial_span / (len(selected) - 1)
        preferred_line_gap = max(
            _DESCENDANT_FIRST_GEN_LINE_GAP_MM,
            radial_span / (len(selected) + 1),
        )
        line_gap = min(preferred_line_gap, maximum_line_gap)
        first_line_offset = (
            radial_span - line_gap * (len(selected) - 1)
        ) / 2.0
        radii = [
            text_start + first_line_offset + line_gap * index
            for index in range(len(selected))
        ]

    return list(zip(selected, radii))


def _fit_couple_to_width(
    child_label: str,
    spouse_label: str,
    *,
    target_size: float,
    minimum_size: float,
    max_width: float,
) -> tuple[str, float, float]:
    """Fit a compact couple label while retaining both identities and ``×``."""
    separator = " × "
    combined = f"{child_label}{separator}{spouse_label}"
    natural_at_one = estimate_text_width(combined, 1.0)
    fitted_size = target_size
    if natural_at_one > 0:
        fitted_size = min(target_size, max_width / natural_at_one)
    if fitted_size >= minimum_size:
        return combined, fitted_size, max_width

    separator_width = estimate_text_width(separator, minimum_size)
    label_width = max(0.0, (max_width - separator_width) / 2.0)
    child_fitted, _size, _width = _fit_text_to_width(
        child_label,
        target_size=minimum_size,
        minimum_size=minimum_size,
        max_width=label_width,
    )
    spouse_fitted, _size, _width = _fit_text_to_width(
        spouse_label,
        target_size=minimum_size,
        minimum_size=minimum_size,
        max_width=label_width,
    )
    if not child_fitted or not spouse_fitted:
        return "", minimum_size, max_width
    return f"{child_fitted}{separator}{spouse_fitted}", minimum_size, max_width


def _maximum_medallion_radius(
    *,
    inner_radius: float,
    outer_radius: float,
    sweep_angle: float,
    occupants: int = 1,
    edge: str = "outer",
    margin: float = 0.8,
) -> float:
    """Solve the largest border radius fitting a sector at one ring edge."""
    radial_cap = max(0.0, (outer_radius - inner_radius - 2 * margin) / 2.0)
    low, high = 0.0, radial_cap
    occupants = max(1, occupants)
    for _ in range(32):
        radius = (low + high) / 2.0
        center_radius = (
            outer_radius - margin - radius
            if edge == "outer"
            else inner_radius + margin + radius
        )
        tangent_capacity = max(
            0.0,
            2.0 * center_radius * math.sin(math.radians(max(sweep_angle, 0.0) / 2.0))
            - 2.0 * margin,
        )
        required = 2.0 * radius if occupants == 1 else (4.3 * radius)
        if required <= tangent_capacity:
            low = radius
        else:
            high = radius
    return low


def _ancestor_content_geometry(
    *,
    generation: int,
    inner_radius: float,
    outer_radius: float,
    fan_outer_radius: float,
    sweep_angle: float,
) -> tuple[float, float, float, float, float, float, bool, bool]:
    """Return ring-relative placement and density-aware ancestor styling.

    The original mockup coordinates were global fractions of a three-ring fan.
    Reusing those fractions with a different generation count moved content into
    neighbouring rings. Local fractions preserve the three-ring hierarchy while
    adapting to every supported ring depth.
    """
    ring_depth = max(outer_radius - inner_radius, 0.0)
    portrait_fractions = {1: 0.365, 2: 0.353, 3: 0.280}
    name_fractions = {1: 0.652, 2: 0.684, 3: 0.630}
    life_fractions = {1: 0.826, 2: 0.841, 3: 0.761}
    portrait_r = inner_radius + ring_depth * portrait_fractions.get(generation, 0.28)
    name_r = inner_radius + ring_depth * name_fractions.get(generation, 0.58)
    life_r = inner_radius + ring_depth * life_fractions.get(generation, 0.78)

    # Give the publication-facing ancestor portraits more presence while
    # leaving the actual radius bounded by each ring's radial and tangent
    # capacity. The G2 reference was 20/600, which made portraits recede on A0.
    base_image_ratios = {1: 30 / 600, 2: 25 / 600, 3: 18 / 600}
    base_name_ratios = {1: 12 / 600, 2: 12 / 600, 3: 10.5 / 600}
    base_life_ratios = {1: 9.5 / 600, 2: 9.5 / 600, 3: 8.5 / 600}
    base_image_r = base_image_ratios.get(
        generation, (15 / 600) * (0.86 ** (generation - 3))
    ) * fan_outer_radius
    base_name_size = base_name_ratios.get(
        generation, (10 / 600) * (0.90 ** (generation - 3))
    ) * fan_outer_radius
    base_life_size = base_life_ratios.get(
        generation, (8.5 / 600) * (0.90 ** (generation - 3))
    ) * fan_outer_radius

    # Keep medallions inside both their radial ring and angular lane. For the
    # dense fourth and fifth rings, solve against the actual sector and hug the
    # inner edge so the remaining radial depth is reserved for labels.
    angular_lane = portrait_r * math.radians(max(sweep_angle, 0.0))
    if generation >= 4:
        image_r = _maximum_medallion_radius(
            inner_radius=inner_radius,
            outer_radius=outer_radius,
            sweep_angle=sweep_angle,
            edge="inner",
            margin=0.8,
        )
        portrait_r = inner_radius + 0.8 + image_r
    else:
        image_r = min(base_image_r, ring_depth * 0.24, angular_lane * 0.22)
    name_size = min(base_name_size, ring_depth * 0.12, angular_lane * 0.36)
    life_size = min(base_life_size, ring_depth * 0.10, angular_lane * 0.30)
    # Per-generation caps ensure a monotonic font hierarchy: deeper
    # generations always have a strictly smaller maximum name size than
    # shallower ones, regardless of how much radial width the medallion
    # leaves.  Without this, G4/G5 (small medallions, more text width)
    # can render at a larger font than G3 (large medallion, less width).
    _name_caps = {1: 7.0, 2: 6.0, 3: 5.0, 4: 4.2, 5: 3.5}
    _life_caps = {1: 5.5, 2: 4.8, 3: 4.0, 4: 3.4, 5: 2.8}
    name_cap = _name_caps.get(generation, 3.0)
    life_cap = _life_caps.get(generation, 2.5)
    name_size = max(min(name_size, name_cap), 2.8)
    life_size = max(min(life_size, life_cap), 2.5)

    text_start = portrait_r + image_r + 2.0
    text_available = max(0.0, outer_radius - 1.5 - text_start)
    # A0 has ample radial depth in generation five despite its 2.688° sweep.
    # Protect names through generation five whenever a useful radial lane exists;
    # deeper rings retain the stricter density degradation policy.
    show_text = (
        generation <= 4
    ) or (
        generation == 5 and text_available >= 12.0 and angular_lane >= 4.0
    ) or (
        generation > 5 and sweep_angle >= 4.0 and name_size >= 1.4
    )
    show_medallion = sweep_angle >= 2.0 and image_r >= 0.8
    return (
        portrait_r,
        name_r,
        life_r,
        image_r,
        name_size,
        life_size,
        show_text,
        show_medallion,
    )


# ---------------------------------------------------------------------------
# Ancestor fan placement
# ---------------------------------------------------------------------------

_ANCESTOR_HALF_SPAN_DEG = 86.0  # mockup: 172° total, 4° waist gap per side


def layout_ancestors(
    canvas: ChartCanvas,
    ancestor_slots: tuple[tuple, ...],
    *,
    show_highlight_markers: bool = False,
) -> SceneNode:
    """Place ancestor fan sectors in the upper half-circle.

    ancestor_slots is a flat tuple of (position_id, label, dates_label) triples.
    Position IDs following the pattern "ancestor-{lineage}-{gen}-{index}"
    are parsed to determine generation and lineage for coloring.
    Empty position_id means an empty/unknown slot (blank sector).

    Generates:
    - Colored annular sectors with mockup palette colors
    - Curved text labels (ScenePathText) along arc paths
    - A second curved arc with life-year dates
    - Small medallion circles with initials at the outer edge of each sector
    - Lineage labels (LIGNÉE <surname>) at the gap between the two halves

    Highlight markers are opt-in so publication views do not expose tag
    annotations unless explicitly requested.
    """
    if not ancestor_slots:
        return SceneNode(children=())

    cx = canvas.center_cx_mm
    cy = canvas.center_cy_mm
    inner_r = canvas.ancestor_inner_radius_mm
    outer_r = canvas.ancestor_outer_radius_mm

    # Parse all slots to get
    # (pid, lineage, generation, label, dates_label, portrait_data_uri).
    parsed: list[tuple[str, str, int, str, str, str | None, bool]] = []
    for entry in ancestor_slots:
        if len(entry) >= 4:
            pid, label, dates_label, portrait = (
                entry[0], entry[1], entry[2], entry[3]
            )
            highlighted = (
                bool(entry[4])
                if show_highlight_markers and len(entry) >= 5
                else False
            )
        elif len(entry) == 3:
            pid, label, dates_label = entry[0], entry[1], entry[2]
            portrait = None
            highlighted = False
        elif len(entry) >= 2:
            # Backward-compatible 2-tuple (position_id, label)
            pid, label = entry[0], entry[1]
            dates_label = ""
            portrait = None
            highlighted = False
        else:
            continue
        info = _parse_position_id(pid)
        if info:
            lineage, gen = info
        else:
            # Fallback: determine from position in list
            lineage = "a"
            gen = 1
        parsed.append((pid, lineage, gen, label, dates_label, portrait, highlighted))

    # Determine actual generations present
    max_gen = max(g for _, _, g, _, _, _, _ in parsed) if parsed else 1
    num_gens = max_gen

    total_depth = outer_r - inner_r
    # Mockup ancestor rings widen outwards: 113 px, 125 px, 148 px.
    # The formula reproduces those proportions for three generations and
    # degrades progressively for deeper configurations.
    if num_gens > 0:
        weights = [1.0 + 0.105 * i + 0.05 * i * (i - 1) for i in range(num_gens)]
        total_weight = sum(weights)
        ring_widths = [total_depth * weight / total_weight for weight in weights]
    else:
        ring_widths = [total_depth]

    children: list = []

    # Collect the gen-1 surname per lineage for the LIGNÉE labels.
    lineage_surnames: dict[str, str] = {}
    for pid, lineage, gen, label, _dates, _portrait, _highlighted in parsed:
        if gen == 1 and label:
            # Label is "Surname, Given…" — take the part before the comma.
            if ", " in label:
                surname = label.split(", ", 1)[0]
            elif "," in label:
                surname = label.split(",", 1)[0]
            else:
                # Plain "Given Surname" — last word is the surname.
                surname = label.split()[-1] if label.split() else ""
            surname = surname.strip()
            if surname:
                lineage_surnames.setdefault(lineage, surname)

    # Group slots by generation
    for gen in range(1, num_gens + 1):
        gen_inner = inner_r + sum(ring_widths[:gen-1])
        ring_width = ring_widths[gen - 1]
        gen_outer = gen_inner + ring_width - _RING_GAP_MM

        gen_slots = [
            (pid, lin, lbl, dt, portrait, highlighted)
            for pid, lin, g, lbl, dt, portrait, highlighted in parsed
            if g == gen
        ]
        if not gen_slots:
            continue

        # Split into lineage a (left: -90° to 0°) and lineage b (right: 0° to 90°)
        slots_a = [s for s in gen_slots if s[1] == "a"]
        slots_b = [s for s in gen_slots if s[1] == "b"]

        # If no lineage info (all same), split by index
        if not slots_b and slots_a:
            half = len(gen_slots) // 2
            slots_a = gen_slots[:half]
            slots_b = gen_slots[half:]

        sweep_a = _ANCESTOR_HALF_SPAN_DEG / max(len(slots_a), 1) if slots_a else 0
        sweep_b = _ANCESTOR_HALF_SPAN_DEG / max(len(slots_b), 1) if slots_b else 0

        # One name size is shared by every visible label in a generation.
        # Measure the complete label against its own cell first, then use the
        # most constrained result for the whole generation. This makes the
        # longest label (rather than a local fallback) determine readability.
        generation_name_sizes: dict[int, float] = {}
        generation_date_sizes: dict[int, float] = {}
        generation_candidates: list[float] = []
        for candidate_slots, candidate_sweep in (
            (slots_a, sweep_a),
            (slots_b, sweep_b),
        ):
            for (
                _pid,
                _lineage,
                candidate_label,
                _dates,
                candidate_portrait,
                _highlighted,
            ) in candidate_slots:
                if not candidate_label:
                    continue
                (
                    candidate_med_position,
                    candidate_name_r,
                    _candidate_life_r,
                    candidate_image_r,
                    candidate_font_size,
                    _candidate_life_font,
                    candidate_show_text,
                    _candidate_show_medallion,
                ) = _ancestor_content_geometry(
                    generation=gen,
                    inner_radius=gen_inner,
                    outer_radius=gen_outer,
                    fan_outer_radius=outer_r,
                    sweep_angle=candidate_sweep,
                )
                if not candidate_show_text:
                    continue
                candidate_medallion_r = (
                    candidate_image_r * (26 / 24)
                    if candidate_portrait and gen < 4
                    else candidate_image_r
                )
                if candidate_sweep < 15.0:
                    if gen == 3:
                        # G3 is tangent in narrow sectors after the accepted
                        # orientation change; other narrow rings stay radial.
                        _candidate_text_r, candidate_width = (
                            _ancestor_tangent_name_lane(
                                name_radius=candidate_name_r,
                                sweep_angle=candidate_sweep,
                            )
                            if gen == 3
                            else _ancestor_radial_name_lane(
                                medallion_position=candidate_med_position,
                                medallion_radius=candidate_medallion_r,
                                outer_radius=gen_outer,
                            )
                        )
                    else:
                        _candidate_text_r, candidate_width = _ancestor_radial_name_lane(
                            medallion_position=candidate_med_position,
                            medallion_radius=candidate_medallion_r,
                            outer_radius=gen_outer,
                        )
                elif gen == 3:
                    _candidate_text_r, candidate_width = _ancestor_radial_name_lane(
                        medallion_position=candidate_med_position,
                        medallion_radius=candidate_medallion_r,
                        outer_radius=gen_outer,
                    )
                else:
                    candidate_width = _ancestor_arc_text_capacity(
                        text_radius=candidate_name_r,
                        sweep_angle=candidate_sweep,
                    )
                generation_candidates.append(
                    _font_size_for_width(
                        candidate_label,
                        target_size=candidate_font_size,
                        max_width=candidate_width,
                    )
                )
        if generation_candidates:
            generation_name_sizes[gen] = min(generation_candidates)
            generation_date_sizes[gen] = _date_font_size(generation_name_sizes[gen])

        # Place lineage a (paternal, left side: -90° to 0°)
        for i, (pid, _, label, dates_label, portrait, highlighted) in enumerate(slots_a):
            start_angle = -_ANCESTOR_HALF_SPAN_DEG + i * sweep_a
            _emit_ancestor_sector(
                children, cx, cy, gen_inner, gen_outer,
                start_angle, sweep_a, outer_r,
                gen, "a", label, dates_label, portrait, highlighted,
                name_font_size=generation_name_sizes.get(gen),
                date_font_size=generation_date_sizes.get(gen),
            )

        # Place lineage b (maternal, right side: 0° to 90°)
        for i, (pid, _, label, dates_label, portrait, highlighted) in enumerate(slots_b):
            start_angle = 0.0 + i * sweep_b
            _emit_ancestor_sector(
                children, cx, cy, gen_inner, gen_outer,
                start_angle, sweep_b, outer_r,
                gen, "b", label, dates_label, portrait, highlighted,
                name_font_size=generation_name_sizes.get(gen),
                date_font_size=generation_date_sizes.get(gen),
            )

    return SceneNode(children=tuple(children))


def _emit_ancestor_sector(
    children: list,
    cx: float, cy: float,
    inner_r: float, outer_r: float,
    start_angle: float, sweep: float,
    fan_outer_r: float,
    gen: int, lineage: str,
    label: str,
    dates_label: str = "",
    portrait: str | None = None,
    highlighted: bool = False,
    name_font_size: float | None = None,
    date_font_size: float | None = None,
) -> None:
    """Emit one ancestor sector with fill, curved label, dates, and medallion."""
    end_angle = start_angle + sweep
    mid_angle = start_angle + sweep / 2.0

    fill = ancestor_fill(gen, lineage)
    if not label:
        # Empty slot — use a neutral light fill
        fill = "#F0EEE6"

    children.append(SceneSector(
        inner_radius=inner_r,
        outer_radius=outer_r,
        start_angle=start_angle,
        sweep_angle=sweep,
        fill=fill,
        stroke=SECTOR_STROKE,
        stroke_width=SECTOR_STROKE_WIDTH,
        cx=cx,
        cy=cy,
    ))

    if not label:
        return

    (
        med_r_pos,
        name_r,
        life_r,
        image_r,
        font_size,
        life_font,
        show_text,
        show_medallion,
    ) = _ancestor_content_geometry(
        generation=gen,
        inner_radius=inner_r,
        outer_radius=outer_r,
        fan_outer_radius=fan_outer_r,
        sweep_angle=sweep,
    )
    # Narrow sectors need true radial text; broad sectors retain curved labels.
    use_radial = sweep < 15.0
    adaptive_tracks = use_radial and gen >= 3
    if gen >= 4:
        med_r = image_r
        portrait_image_r = image_r * (24 / 26)
    else:
        med_r = image_r * (26 / 24) if portrait else image_r
        portrait_image_r = image_r

    effective_name_size = (
        name_font_size if name_font_size is not None else font_size
    )
    effective_date_size = (
        date_font_size
        if date_font_size is not None
        else _date_font_size(effective_name_size)
    )

    if show_text and gen == 3:
        # Rotate only the G3 name by 90 degrees from the standard orientation
        # for this sector. Dates keep their established tangent rail below.
        effective_name_size = (
            name_font_size if name_font_size is not None else font_size
        )
        standard_name_is_radial = use_radial
        target_name_is_radial = not standard_name_is_radial
        if target_name_is_radial:
            name_lane_r, name_lane_width = _ancestor_radial_name_lane(
                medallion_position=med_r_pos,
                medallion_radius=med_r,
                outer_radius=outer_r,
            )
            name_rotation = _outward_radial_rotation(mid_angle)
        else:
            name_lane_r, name_lane_width = _ancestor_tangent_name_lane(
                name_radius=name_r,
                sweep_angle=sweep,
            )
            name_rotation = _upright_tangent_rotation(mid_angle)
        name_x, name_y = _polar(cx, cy, name_lane_r, mid_angle)
        children.append(SceneText(
            x=name_x,
            y=name_y,
            content=label,
            font_size=effective_name_size,
            fill=TEXT_DARK,
            anchor="middle",
            rotation=name_rotation,
            max_width=name_lane_width,
        ))
        if dates_label and effective_date_size > 0.0:
            life_path = _arc_text_path(
                cx,
                cy,
                life_r,
                start_angle,
                end_angle,
                lower=False,
            )
            children.append(ScenePathText(
                path=life_path,
                content=dates_label,
                font_size=effective_date_size,
                fill=TEXT_GREY,
                max_width=_ancestor_arc_text_capacity(
                    text_radius=life_r,
                    sweep_angle=sweep,
                ),
            ))
    elif show_text and adaptive_tracks:
        text_start = med_r_pos + med_r + 2.0
        text_end = outer_r - 1.5
        text_width = max(0.0, text_end - text_start)
        text_r = (text_start + text_end) / 2.0
        base_x, base_y = _polar(cx, cy, text_r, mid_angle)
        rot = _outward_radial_rotation(mid_angle)
        lane_offset = max(effective_name_size, effective_date_size) * 0.58

        # --- Name fitting -------------------------------------------------
        # Fit the full label on one line first.  If the result is badly
        # shrunk (the large G3 medallion eats radial width), split into two
        # lines: given name above, surname below.  Each shorter line fits
        # at a larger font size, which keeps the hierarchy monotonic across
        # generations instead of letting G4/G5 (small medallions, more
        # text width) render larger than G3.
        fitted_name, fitted_name_size, name_width = _fit_text_to_width(
            label,
            target_size=effective_name_size,
            minimum_size=effective_name_size,
            max_width=text_width,
            allow_ellipsis=False,
        )
        use_two_lines = False
        two_line_size = 0.0
        fitted_given = ""
        fitted_surname = ""
        given_width = 0.0
        surname_width = 0.0
        if fitted_name_size < font_size * 0.75 and ", " in label:
            surname_part, given_part = label.split(", ", 1)
            fitted_given, given_size, given_width = _fit_text_to_width(
                given_part,
                target_size=effective_name_size,
                minimum_size=effective_name_size,
                max_width=text_width,
                allow_ellipsis=False,
            )
            fitted_surname, surname_size, surname_width = _fit_text_to_width(
                surname_part,
                target_size=effective_name_size,
                minimum_size=effective_name_size,
                max_width=text_width,
                allow_ellipsis=False,
            )
            two_line_size = min(given_size, surname_size)
            if two_line_size > fitted_name_size * 1.15:
                use_two_lines = True

        effective_name_size = (
            name_font_size
            if name_font_size is not None
            else (two_line_size if use_two_lines else fitted_name_size)
        )
        if use_two_lines:
            two_line_size = effective_name_size

        if use_two_lines:
            line_h = two_line_size * 1.3
            gx, gy = _tangent_offset(base_x, base_y, mid_angle, -line_h)
            sx, sy = _tangent_offset(base_x, base_y, mid_angle, 0.0)
            if fitted_given:
                children.append(SceneText(
                    x=gx, y=gy,
                    content=fitted_given,
                    font_size=two_line_size,
                    fill=TEXT_DARK,
                    anchor="middle",
                    rotation=rot,
                    max_width=given_width,
                ))
            if fitted_surname:
                children.append(SceneText(
                    x=sx, y=sy,
                    content=fitted_surname,
                    font_size=two_line_size,
                    fill=TEXT_DARK,
                    anchor="middle",
                    rotation=rot,
                    max_width=surname_width,
                ))
        elif fitted_name:
            name_x, name_y = _tangent_offset(
                base_x, base_y, mid_angle, -lane_offset,
            )
            children.append(SceneText(
                x=name_x,
                y=name_y,
                content=fitted_name,
                font_size=fitted_name_size,
                fill=TEXT_DARK,
                anchor="middle",
                rotation=rot,
                max_width=name_width,
            ))

        # --- Dates --------------------------------------------------------
        # Date font must never exceed the name font.
        if dates_label and effective_date_size > 0.0:
            date_target = effective_date_size
            if use_two_lines:
                dx, dy = _tangent_offset(
                    base_x, base_y, mid_angle, line_h,
                )
            else:
                dx, dy = _tangent_offset(
                    base_x, base_y, mid_angle, lane_offset,
                )
            fitted_dates, fitted_date_size, date_width = _fit_text_to_width(
                dates_label,
                target_size=date_target,
                minimum_size=effective_date_size,
                max_width=text_width,
                allow_ellipsis=False,
            )
            if fitted_dates:
                children.append(SceneText(
                    x=dx,
                    y=dy,
                    content=fitted_dates,
                    font_size=effective_date_size,
                    fill=TEXT_GREY,
                    anchor="middle",
                    rotation=rot,
                    max_width=date_width,
                ))
    elif show_text and use_radial:
        _radial_text_r, radial_width = _ancestor_radial_name_lane(
            medallion_position=med_r_pos,
            medallion_radius=med_r,
            outer_radius=outer_r,
        )
        tx, ty = _polar(cx, cy, name_r, mid_angle)
        rot = _outward_radial_rotation(mid_angle)
        children.append(SceneText(
            x=tx, y=ty,
            content=label,
            font_size=effective_name_size,
            fill=TEXT_DARK,
            anchor="middle",
            rotation=rot,
            max_width=radial_width,
        ))
        if dates_label and effective_date_size > 0.0:
            ltx, lty = _polar(cx, cy, life_r, mid_angle)
            children.append(SceneText(
                x=ltx, y=lty,
                content=dates_label,
                font_size=effective_date_size,
                fill=TEXT_GREY,
                anchor="middle",
                max_width=radial_width,
                rotation=rot,
            ))
    elif show_text:
        path = _arc_text_path(cx, cy, name_r, start_angle, end_angle, lower=False)
        children.append(ScenePathText(
            path=path,
            content=label,
            font_size=effective_name_size,
            fill=TEXT_DARK,
            max_width=_ancestor_arc_text_capacity(
                text_radius=name_r,
                sweep_angle=sweep,
            ),
        ))
        if dates_label and effective_date_size > 0.0:
            life_path = _arc_text_path(cx, cy, life_r, start_angle, end_angle, lower=False)
            children.append(ScenePathText(
                path=life_path,
                content=dates_label,
                font_size=effective_date_size,
                fill=TEXT_GREY,
                max_width=_ancestor_arc_text_capacity(
                    text_radius=life_r,
                    sweep_angle=sweep,
                ),
            ))

    # Portrait/fallback medallion sized for this ring and angular lane.
    marker_position: tuple[float, float, float] | None = None
    if show_medallion and med_r > 0.5:
        mx, my = _polar(cx, cy, med_r_pos, mid_angle)
        marker_position = (mx, my, med_r + 1.25)
        children.append(SceneCircle(
            cx=mx, cy=my, r=med_r,
            fill=MEDALLION_FILL,
            stroke=MEDALLION_BORDER,
            stroke_width=0.3,
        ))
        if portrait:
            children.append(SceneImage(
                cx=mx,
                cy=my,
                r=portrait_image_r,
                data_uri=portrait,
            ))
        else:
            # Add initials text inside the medallion
            initials = _extract_initials(label)
            if initials:
                children.append(SceneText(
                    x=mx, y=my + med_r * 0.25,
                    content=initials,
                    font_size=med_r * 0.55,
                    fill=TEXT_DARK,
                    anchor="middle",
                ))

    if highlighted:
        if marker_position is None:
            marker_x, marker_y = _polar(
                cx, cy, max(inner_r, outer_r - 1.5), mid_angle
            )
            marker_radius = min(2.0, max(0.9, sweep * 0.04))
        else:
            marker_x, marker_y, marker_radius = marker_position
        children.append(SceneMarker(
            cx=marker_x,
            cy=marker_y,
            radius=marker_radius,
        ))


# ---------------------------------------------------------------------------
# Center couple placement
# ---------------------------------------------------------------------------

_LABEL_FILL = TEXT_DARK
_STATS_FILL = TEXT_GREY
_CENTER_NAME_MIN_SIZE = 5.5


def _center_name_style(content: str, radius: float) -> tuple[float, float]:
    """Return an adaptive font size and the safe center-label width.

    The label sits below the center medallions. Its available width is the
    horizontal chord of the inner white circle at that baseline, minus a
    proportional side margin. Keeping the full label and passing this width
    to the renderer prevents long couples from being clipped at the circle's
    edge while avoiding a fixed-size label that only works for short names.
    """
    baseline_offset = radius * (48.0 / 190.0)
    inner_radius = radius * 0.94
    half_chord = math.sqrt(
        max(0.0, inner_radius**2 - baseline_offset**2)
    )
    max_width = max(1.0, 2.0 * half_chord - radius * 0.12)
    target_size = radius * (23.0 / 190.0)
    natural_at_one = estimate_text_width(content, 1.0)
    if natural_at_one > 0:
        target_size = min(target_size, max_width / natural_at_one)
    return max(_CENTER_NAME_MIN_SIZE, target_size), max_width


def layout_center(
    canvas: ChartCanvas,
    *,
    left_label: str,
    right_label: str | None = None,
    left_dates: str = "",
    right_dates: str = "",
    left_portrait: str | None = None,
    right_portrait: str | None = None,
    left_fallback: str = "",
    right_fallback: str = "",
    left_highlighted: bool = False,
    right_highlighted: bool = False,
    show_highlight_markers: bool = False,
    statistics: str | None = None,
) -> SceneNode:
    """Place the center family medallion with labels, portraits and stats.

    The center zone (canvas.center_radius_mm) creates a breathing area
    like the mockup's ivory circle.  The actual medallions are ~35% of
    this zone's radius, placed at the top, with the "&" between them and
    the combined name + stats below.
    """
    cx = canvas.center_cx_mm
    cy = canvas.center_cy_mm
    r = canvas.center_radius_mm  # the full center zone (ivory circle)
    left_highlighted = left_highlighted and show_highlight_markers
    right_highlighted = right_highlighted and show_highlight_markers

    children: list = []

    if right_label is not None:
        # Exact center proportions from the 190 px mockup center circle.
        med_r = r * (52.0 / 190.0)
        offset = r * (64.0 / 190.0)
        left_cx = cx - offset
        right_cx = cx + offset
        med_cy = cy - r * (28.0 / 190.0)

        # Outer ivory circle (the breathing zone)
        children.append(SceneCircle(
            cx=cx, cy=cy, r=r,
            fill="#FAF9F5",
            stroke="#D1CFC5",
            stroke_width=0.3,
        ))

        # Inner white circle (like mockup line 386)
        children.append(SceneCircle(
            cx=cx, cy=cy, r=r * 0.94,
            fill="#FFFFFF",
            stroke="#E3DACC",
            stroke_width=0.8,
        ))

        children.append(SceneCircle(
            cx=left_cx, cy=med_cy, r=med_r,
            fill=MEDALLION_FILL,
            stroke=MEDALLION_BORDER,
            stroke_width=0.4,
        ))
        children.append(SceneCircle(
            cx=right_cx, cy=med_cy, r=med_r,
            fill=MEDALLION_FILL,
            stroke=MEDALLION_BORDER,
            stroke_width=0.4,
        ))

        if left_portrait or left_fallback:
            children.append(SceneImage(
                cx=left_cx, cy=med_cy, r=med_r * 0.92,
                data_uri=left_portrait,
                fallback_text=left_fallback,
            ))
        if right_portrait or right_fallback:
            children.append(SceneImage(
                cx=right_cx, cy=med_cy, r=med_r * 0.92,
                data_uri=right_portrait,
                fallback_text=right_fallback,
            ))

        if left_highlighted:
            children.append(SceneMarker(cx=left_cx, cy=med_cy, radius=med_r + 1.25))
        if right_highlighted:
            children.append(SceneMarker(cx=right_cx, cy=med_cy, radius=med_r + 1.25))

        # "&" symbol between the two medallions (mockup uses clay color)
        children.append(SceneText(
            x=cx, y=med_cy + med_r * 0.20,
            content="&",
            font_size=r * (28.0 / 190.0),
            fill="#D97757",
            anchor="middle",
        ))

        # Combined name below the medallions. Fit against the actual white
        # circle chord instead of using one fixed size for every couple.
        combined = f"{left_label} & {right_label}"
        name_size, name_max_width = _center_name_style(combined, r)
        children.append(SceneText(
            x=cx, y=cy + r * (48.0 / 190.0),
            content=combined,
            font_size=name_size,
            fill=_LABEL_FILL,
            anchor="middle",
            font_weight="500",
            max_width=name_max_width,
        ))

        # One life-span line per partner, aligned beneath the shared name line.
        date_y = cy + r * (72.0 / 190.0)
        date_size = r * (13.0 / 190.0)
        if left_dates:
            children.append(SceneText(
                x=left_cx, y=date_y,
                content=left_dates,
                font_size=date_size,
                fill=TEXT_GREY,
                anchor="middle",
            ))
        if right_dates:
            children.append(SceneText(
                x=right_cx, y=date_y,
                content=right_dates,
                font_size=date_size,
                fill=TEXT_GREY,
                anchor="middle",
            ))
    else:
        # Single medallion for incomplete couple
        med_r = r * (52.0 / 190.0)
        children.append(SceneCircle(
            cx=cx, cy=cy, r=r,
            fill="#FAF9F5",
            stroke="#D1CFC5",
            stroke_width=0.3,
        ))
        children.append(SceneCircle(
            cx=cx, cy=cy - r * (28.0 / 190.0), r=med_r,
            fill=MEDALLION_FILL,
            stroke=MEDALLION_BORDER,
            stroke_width=0.4,
        ))
        if left_portrait or left_fallback:
            children.append(SceneImage(
                cx=cx,
                cy=cy - r * (28.0 / 190.0),
                r=med_r * 0.92,
                data_uri=left_portrait,
                fallback_text=left_fallback,
            ))
        if left_highlighted:
            children.append(SceneMarker(
                cx=cx,
                cy=cy - r * (28.0 / 190.0),
                radius=med_r + 1.25,
            ))
        name_size, name_max_width = _center_name_style(left_label, r)
        children.append(SceneText(
            x=cx, y=cy + r * (48.0 / 190.0),
            content=left_label,
            font_size=name_size,
            fill=_LABEL_FILL,
            anchor="middle",
            font_weight="500",
            max_width=name_max_width,
        ))
        if left_dates:
            children.append(SceneText(
                x=cx, y=cy + r * (72.0 / 190.0),
                content=left_dates,
                font_size=r * (13.0 / 190.0),
                fill=TEXT_GREY,
                anchor="middle",
            ))

    if statistics:
        children.append(SceneText(
            x=cx, y=cy + r * 2 + 5,
            content=statistics,
            font_size=r * 0.22,
            fill=_STATS_FILL,
            anchor="middle",
        ))

    return SceneNode(children=tuple(children))


# ---------------------------------------------------------------------------
# Title and legend placement
# ---------------------------------------------------------------------------

def layout_titles(
    canvas: ChartCanvas,
    *,
    ancestor_generations: int,
    descendant_generations: int,
) -> SceneNode:
    """Place the ASCENDANTS and DESCENDANTS titles above and below the fan."""
    cx = canvas.center_cx_mm
    cy = canvas.center_cy_mm
    children: list = []

    if ancestor_generations > 0:
        # Title above the top arc
        title_y = cy - canvas.ancestor_outer_radius_mm - _ANCESTOR_TITLE_GAP_MM
        generation_word = "GÉNÉRATION" if ancestor_generations == 1 else "GÉNÉRATIONS"
        title_text = f"ASCENDANTS · {ancestor_generations} {generation_word}"
        children.append(SceneText(
            x=cx, y=title_y,
            content=title_text,
            font_size=5.0,
            fill=TEXT_GREY,
            anchor="middle",
        ))

    if descendant_generations > 0:
        # Title below the bottom arc
        title_y = cy + canvas.descendant_outer_radius_mm + _DESCENDANT_TITLE_GAP_MM
        generation_word = "GÉNÉRATION" if descendant_generations == 1 else "GÉNÉRATIONS"
        title_text = f"DESCENDANTS · {descendant_generations} {generation_word}"
        children.append(SceneText(
            x=cx, y=title_y,
            content=title_text,
            font_size=5.0,
            fill=TEXT_GREY,
            anchor="middle",
        ))

    return SceneNode(children=tuple(children))


def layout_legend(
    canvas: ChartCanvas,
    *,
    show_legend: bool = True,
) -> SceneNode:
    """Place the legend block in the top-left corner."""
    if not show_legend:
        return SceneNode(children=())

    x = canvas.page_width_mm * 0.03
    y = canvas.page_height_mm * 0.05

    items = (
        ("portrait disponible", MEDALLION_BORDER),
        ("initiales si absent", "#D1CFC5"),
        ("vivant masqué", HIDDEN_FILL),
    )

    children: list = [SceneLegend(x=x, y=y, items=items)]
    return SceneNode(children=tuple(children))


def layout_stats(
    canvas: ChartCanvas,
    *,
    person_count: int = 0,
    ancestor_generations: int = 0,
    descendant_generations: int = 0,
    family_id: str = "",
    child_count: int = 0,
    grandchild_count: int = 0,
) -> SceneNode:
    """Place the publication info block in the top-right corner."""
    x = canvas.page_width_mm * 0.82
    y = canvas.page_height_mm * 0.05

    children: list = []
    # Background card
    children.append(SceneRect(
        x=x - 4, y=y - 6,
        width=52.0, height=32.0,
    ))
    # Title line
    children.append(SceneText(
        x=x, y=y,
        content="MODE PUBLICATION",
        font_size=4.0,
        fill=TEXT_GREY,
        anchor="start",
    ))
    # Stats lines
    lines = []
    if person_count:
        lines.append(f"{person_count} personnes")
    if ancestor_generations:
        lines.append(f"{ancestor_generations} générations ↑")
    if descendant_generations:
        lines.append(f"{descendant_generations} générations ↓")

    for i, line in enumerate(lines):
        children.append(SceneText(
            x=x, y=y + 6 + i * 5,
            content=line,
            font_size=3.5,
            fill=TEXT_DARK,
            anchor="start",
        ))

    return SceneNode(children=tuple(children))


# ---------------------------------------------------------------------------
# Descendant branch allocation
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class DescendantBranchAllocation:
    """Angle allocation for one descendant branch."""

    start_angle: float
    sweep_angle: float
    leaf_count: int


@dataclass(frozen=True, slots=True)
class _DescendantUnionAllocation:
    """One contiguous angular block belonging to one recorded union."""

    union_index: int
    children: tuple[DescendantBranch, ...]
    start_angle: float
    sweep_angle: float


def allocate_descendant_branches(
    canvas: ChartCanvas,
    *,
    leaf_counts: list[int],
    start_angle: float,
    total_sweep: float,
    minimum_angle: float = 3.0,
) -> tuple[DescendantBranchAllocation, ...]:
    """Allocate angular sweep to descendant branches.

    Uses weighted allocation proportional to leaf counts, with a minimum
    angle per branch. Results are deterministic for the same inputs.
    """
    n = len(leaf_counts)
    if n == 0:
        return ()

    total_leaves = sum(leaf_counts)
    # Reserve minimum angle for each branch, distribute the rest proportionally
    reserved = minimum_angle * n
    remaining = total_sweep - reserved
    if remaining < 0:
        remaining = 0

    allocations: list[DescendantBranchAllocation] = []
    angle = start_angle
    for i, count in enumerate(leaf_counts):
        if total_leaves > 0 and remaining > 0:
            proportional = remaining * count / total_leaves
        else:
            proportional = 0
        sweep = minimum_angle + proportional
        allocations.append(DescendantBranchAllocation(
            start_angle=angle,
            sweep_angle=sweep,
            leaf_count=count,
        ))
        angle += sweep

    # Normalise to ensure exact total sweep
    current_total = sum(a.sweep_angle for a in allocations)
    if current_total > 0 and abs(current_total - total_sweep) > 0.001:
        factor = total_sweep / current_total
        adjusted = []
        angle = start_angle
        for a in allocations:
            adjusted_sweep = a.sweep_angle * factor
            adjusted.append(DescendantBranchAllocation(
                start_angle=angle,
                sweep_angle=adjusted_sweep,
                leaf_count=a.leaf_count,
            ))
            angle += adjusted_sweep
        return tuple(adjusted)

    return tuple(allocations)


def _allocate_publication_branches(
    child_counts: list[int],
    *,
    start_angle: float,
    total_sweep: float,
    base_angle: float = 18.0,
) -> tuple[DescendantBranchAllocation, ...]:
    """Allocate first-generation branches with the reference mockup formula.

    Every child receives a readable base sector. Only grandchildren beyond the
    first two widen the branch, preventing childless branches from collapsing
    to the tiny slivers produced by pure leaf-proportional allocation.
    """
    if not child_counts:
        return ()

    base = min(base_angle, total_sweep / len(child_counts))
    extras = [max(0, count - 2) for count in child_counts]
    extra_total = sum(extras)
    remaining = max(0.0, total_sweep - base * len(child_counts))
    if extra_total:
        widths = [base + remaining * extra / extra_total for extra in extras]
    else:
        widths = [total_sweep / len(child_counts)] * len(child_counts)

    angle = start_angle
    allocations: list[DescendantBranchAllocation] = []
    for count, width in zip(child_counts, widths):
        allocations.append(DescendantBranchAllocation(angle, width, count))
        angle += width
    return tuple(allocations)


# ---------------------------------------------------------------------------
# Descendant node placement
# ---------------------------------------------------------------------------

_DESC_MEDALLION_R_FACTOR = 0.7  # relative to center radius


def layout_descendant_node(
    canvas: ChartCanvas,
    *,
    child_label: str,
    spouse_label: str | None = None,
    additional_spouses: tuple[str, ...] = (),
    child_portrait: str | None = None,
    spouse_portrait: str | None = None,
    child_fallback: str = "",
    spouse_fallback: str = "",
    child_highlighted: bool = False,
    spouse_highlighted: bool = False,
    cx: float | None = None,
    cy: float | None = None,
    r: float | None = None,
) -> SceneNode:
    """Place a descendant with optional spouse(s) as twin medallions.

    For multiple unions, additional spouse medallions are placed
    horizontally next to the primary spouse.
    """
    _cx = cx if cx is not None else canvas.center_cx_mm
    _cy = cy if cy is not None else canvas.center_cy_mm + canvas.center_radius_mm * 2
    _r = r if r is not None else canvas.center_radius_mm * _DESC_MEDALLION_R_FACTOR

    children: list = []

    all_spouses: list[str | None] = []
    if spouse_label is not None:
        all_spouses.append(spouse_label)
    all_spouses.extend(additional_spouses)

    n_medallions = 1 + len(all_spouses)  # child + spouses
    spacing = _r * 1.2
    total_width = (n_medallions - 1) * spacing
    start_x = _cx - total_width / 2

    # Child medallion (always first, leftmost)
    child_cx = start_x
    children.append(SceneCircle(
        cx=child_cx, cy=_cy, r=_r,
        fill=MEDALLION_FILL,
        stroke=MEDALLION_BORDER,
        stroke_width=0.5,
    ))
    if child_portrait or child_fallback:
        children.append(SceneImage(
            cx=child_cx, cy=_cy, r=_r * 0.8,
            data_uri=child_portrait,
            fallback_text=child_fallback,
        ))
    if child_highlighted:
        children.append(SceneMarker(cx=child_cx, cy=_cy, radius=_r + 1.25))
    children.append(SceneText(
        x=child_cx, y=_cy + _r + 2,
        content=child_label,
        font_size=_r * 0.28,
        fill=_LABEL_FILL,
        anchor="middle",
    ))

    # Spouse medallions
    for i, sp_label in enumerate(all_spouses):
        sp_cx = start_x + (i + 1) * spacing
        children.append(SceneCircle(
            cx=sp_cx, cy=_cy, r=_r,
            fill=MEDALLION_FILL,
            stroke=MEDALLION_BORDER,
            stroke_width=0.5,
        ))
        # Only primary spouse gets portrait/fallback
        sp_data = spouse_portrait if i == 0 else None
        sp_fb = spouse_fallback if i == 0 else ""
        if sp_data or sp_fb:
            children.append(SceneImage(
                cx=sp_cx, cy=_cy, r=_r * 0.8,
                data_uri=sp_data,
                fallback_text=sp_fb,
            ))
        if spouse_highlighted and i == 0:
            children.append(SceneMarker(cx=sp_cx, cy=_cy, radius=_r + 1.25))
        children.append(SceneText(
            x=sp_cx, y=_cy + _r + 2,
            content=sp_label,
            font_size=_r * 0.28,
            fill=_LABEL_FILL,
            anchor="middle",
        ))

    return SceneNode(children=tuple(children))


# ---------------------------------------------------------------------------
# Full descendant tree placement
# ---------------------------------------------------------------------------

_DESC_START_ANGLE = 96.0  # mockup: 6° waist gap on the right
_DESC_TOTAL_SWEEP = 168.0  # descendants end at 264°, leaving 6° on the left

# Minimum useful angular slot per descendant generation. Allocation is driven
# by the most demanding visible depth rather than immediate child count, so a
# branch with few children but many deep descendants receives enough room.
_DESC_MIN_SWEEP_BY_GENERATION = {
    1: 14.0,
    2: 3.5,
    3: 1.4,
    4: 1.0,
    5: 0.8,
}

# Below this radius a circle is perceived as a dot rather than a medallion on
# large-format output. Narrow sectors degrade to text-only instead of shrinking
# every medallion in the generation to an unreadable common minimum.
_MIN_INITIALS_MEDALLION_RADIUS_MM = 3.2
# A direct-child ring narrower than this cannot satisfy the adaptive dense
# medallion target while retaining its text lane. Keep it as a last-resort
# donor floor when widening the grandchild ring.
_DESCENDANT_DIRECT_MEDALLION_MIN_RING_WIDTH_MM = (
    2 * _MIN_INITIALS_MEDALLION_RADIUS_MM + _MEDALLION_EDGE_CLEARANCE_MM
) / (1.0 - _MEDALLION_TEXT_RESERVE_RATIO)
# Continuation marker: three small circles on the branch's outward ray.
_DESCENDANT_CONTINUATION_DOT_RADIUS_MM = 0.55
_DESCENDANT_CONTINUATION_DOT_OFFSET_MM = 2.0
# Keep the marker sequence within the title gap while retaining a visible
# radial separation between the three dots.
_DESCENDANT_CONTINUATION_DOT_SPACING_MM = 1.75


def _count_leaves(branch: DescendantBranch) -> int:
    """Count the total leaf nodes in a descendant branch tree."""
    if not branch.children:
        return 1
    return sum(_count_leaves(child) for child in branch.children)


def _descendant_generation_counts(branch: DescendantBranch) -> dict[int, int]:
    """Count visible nodes by absolute generation inside one branch."""
    counts: dict[int, int] = {}

    def _visit(node: DescendantBranch) -> None:
        counts[node.generation] = counts.get(node.generation, 0) + 1
        for child in node.children:
            _visit(child)

    _visit(branch)
    return counts


def _descendant_angle_demand(branch: DescendantBranch) -> float:
    """Return the branch sweep needed by its visible generations and cells."""
    demand = 0.0
    for generation, count in _descendant_generation_counts(branch).items():
        slot = _DESC_MIN_SWEEP_BY_GENERATION.get(generation, 0.8)
        demand = max(demand, count * slot)
    # Propagate the deepest group demand through unsplit ancestors as well.
    # Without this, a zero/one-union branch can receive enough room for its
    # own ring while starving a multi-union descendant in the next ring.
    groups = list(_children_grouped_by_union(branch))
    if branch.unions and len(groups) < len(branch.unions):
        groups.extend(() for _ in range(len(branch.unions) - len(groups)))
    if len(branch.unions) > 1:
        # A multi-union branch is split into one contiguous cell per union
        # after the branch-level sweep is allocated. The ring and cell demands
        # are competing lower bounds, not additive widths: reserve whichever
        # is larger, otherwise the outer allocator over-weights this branch.
        cell_floor = _DESC_MIN_SWEEP_BY_GENERATION.get(branch.generation, 0.8)
        demand = max(
            demand,
            sum(
                max(_descendant_group_angle_demand(group), cell_floor)
                for group in groups[: len(branch.unions)]
            ),
        )
    elif branch.children:
        child_group = groups[0] if groups else branch.children
        demand = max(demand, _descendant_group_angle_demand(child_group))
    return max(demand, _DESC_MIN_SWEEP_BY_GENERATION.get(branch.generation, 0.8))


def _children_grouped_by_union(
    branch: DescendantBranch,
) -> tuple[tuple[DescendantBranch, ...], ...]:
    """Return descendant children grouped by their recorded union.

    New extraction results carry the grouping explicitly. The fallback keeps
    older hand-built graph fixtures usable by matching the recorded child
    handles in each ``UnionBranch`` rather than assigning every child to the
    first union.
    """
    if branch.children_by_union:
        return branch.children_by_union
    if not branch.children:
        return tuple(() for _union in branch.unions)
    if not branch.unions:
        return (branch.children,)

    remaining = list(branch.children)
    groups: list[tuple[DescendantBranch, ...]] = []
    for union in branch.unions:
        group: list[DescendantBranch] = []
        for child_handle in union.child_handles:
            match_index = next(
                (
                    index
                    for index, child in enumerate(remaining)
                    if child.person.handle == child_handle
                ),
                None,
            )
            if match_index is not None:
                group.append(remaining.pop(match_index))
        groups.append(tuple(group))

    # Do not silently drop children from legacy fixtures whose union metadata
    # is incomplete. They remain visible under the final recorded union.
    if remaining:
        if groups:
            groups[-1] = groups[-1] + tuple(remaining)
        else:
            groups.append(tuple(remaining))
    return tuple(groups)


def _descendant_group_angle_demand(
    children: tuple[DescendantBranch, ...],
) -> float:
    """Return one union's demand, including nested split-cell demands."""
    counts: dict[int, int] = {}
    for child in children:
        for generation, count in _descendant_generation_counts(child).items():
            counts[generation] = counts.get(generation, 0) + count
    generation_demand = max(
        (
            count * _DESC_MIN_SWEEP_BY_GENERATION.get(generation, 0.8)
            for generation, count in counts.items()
        ),
        default=0.8,
    )
    nested_demand = sum(_descendant_angle_demand(child) for child in children)
    return max(generation_demand, nested_demand)


def _allocate_descendant_union_groups(
    branch: DescendantBranch,
    *,
    start_angle: float,
    total_sweep: float,
    include_empty: bool = False,
) -> tuple[_DescendantUnionAllocation, ...]:
    """Allocate one contiguous angular block per recorded union.

    The same allocations are used for the first-generation marriage cells and
    for their child sectors. Keeping one interval per union is essential: if
    those two passes use different demand models, a marriage cell can straddle
    the children of another marriage and the chart looks like one shared box.

    ``include_empty`` is used by the first-generation cell pass so a recorded
    marriage without visible children still receives its own block. Child
    placement also enables it, preserving the radial alignment while leaving
    the block empty in later rings.
    """
    groups = list(_children_grouped_by_union(branch))
    if branch.unions:
        if len(groups) < len(branch.unions):
            groups.extend(() for _ in range(len(branch.unions) - len(groups)))
        indexed_groups = list(enumerate(groups[: len(branch.unions)]))
        if not include_empty:
            indexed_groups = [
                (union_index, group)
                for union_index, group in indexed_groups
                if group
            ]
    elif branch.children:
        indexed_groups = [(-1, branch.children)]
    else:
        return ()

    if not indexed_groups:
        return ()

    demands = []
    for _union_index, group in indexed_groups:
        demand = _descendant_group_angle_demand(group) if group else 0.0
        if len(branch.unions) > 1:
            # A sparse/empty union still needs enough angular room for its
            # first-generation couple label. All later child sectors inherit
            # this same floor so their radial boundaries remain aligned.
            demand = max(
                demand,
                _DESC_MIN_SWEEP_BY_GENERATION.get(branch.generation, 0.8),
            )
        demands.append(demand or 0.8)
    total_demand = sum(demands) or float(len(indexed_groups))
    allocations: list[_DescendantUnionAllocation] = []
    angle = start_angle
    for group_index, ((union_index, group), demand) in enumerate(
        zip(indexed_groups, demands)
    ):
        if group_index == len(indexed_groups) - 1:
            group_sweep = start_angle + total_sweep - angle
        else:
            group_sweep = total_sweep * demand / total_demand
        allocations.append(
            _DescendantUnionAllocation(
                union_index,
                tuple(group),
                angle,
                group_sweep,
            )
        )
        angle += group_sweep
    return tuple(allocations)


def _allocate_descendant_union_cells(
    branch: DescendantBranch,
    *,
    start_angle: float,
    total_sweep: float,
) -> tuple[_DescendantUnionAllocation, ...]:
    """Allocate one cell per recorded union at any descendant depth.

    Unlike child-sector allocation, a marriage with no visible children still
    needs a cell. This keeps each generation's person/spouse presentation
    one-to-one with the recorded unions. The child allocations deliberately
    reuse these exact intervals so every union is a continuous radial cell.
    """
    if len(branch.unions) <= 1:
        return _allocate_descendant_union_groups(
            branch,
            start_angle=start_angle,
            total_sweep=total_sweep,
        )
    return _allocate_descendant_union_groups(
        branch,
        start_angle=start_angle,
        total_sweep=total_sweep,
        include_empty=True,
    )


def _allocate_descendant_children(
    branch: DescendantBranch,
    *,
    start_angle: float,
    total_sweep: float,
) -> tuple[DescendantBranchAllocation, ...]:
    """Allocate children in contiguous angular blocks per union.

    Each union receives a block sized from the demand of its own children;
    children from different spouses therefore cannot interleave in the same
    descendant sector.
    """
    allocations: list[DescendantBranchAllocation] = []
    for group in _allocate_descendant_union_groups(
        branch,
        start_angle=start_angle,
        total_sweep=total_sweep,
        include_empty=True,
    ):
        allocations.extend(
            _allocate_descendant_branches_by_demand(
                group.children,
                start_angle=group.start_angle,
                total_sweep=group.sweep_angle,
            )
        )
    return tuple(allocations)


def _allocate_descendant_branches_by_demand(
    branches: tuple[DescendantBranch, ...],
    *,
    start_angle: float,
    total_sweep: float,
) -> tuple[DescendantBranchAllocation, ...]:
    """Allocate siblings in proportion to their deepest-generation demand."""
    if not branches:
        return ()
    demands = [_descendant_angle_demand(branch) for branch in branches]
    total_demand = sum(demands)
    if total_demand <= 0:
        demands = [1.0] * len(branches)
        total_demand = float(len(branches))

    allocations: list[DescendantBranchAllocation] = []
    angle = start_angle
    for index, (branch, demand) in enumerate(zip(branches, demands)):
        if index == len(branches) - 1:
            sweep = start_angle + total_sweep - angle
        else:
            sweep = total_sweep * demand / total_demand
        allocations.append(DescendantBranchAllocation(
            start_angle=angle,
            sweep_angle=sweep,
            leaf_count=_count_leaves(branch),
        ))
        angle += sweep
    return tuple(allocations)


def _max_desc_depth(branch: DescendantBranch) -> int:
    """Return the maximum visible descendant depth for one branch."""
    if not branch.children:
        return 1
    return 1 + max(_max_desc_depth(child) for child in branch.children)


def _descendant_label(branch: DescendantBranch, name_lookup) -> str:
    """Get a short label for a descendant branch via the name lookup callable."""
    return name_lookup(branch.person.handle) if branch.person else ""


def _spouse_label(union, name_lookup) -> str | None:
    """Get a short label for a union's spouse via the name lookup callable."""
    if not union.spouse_handle:
        return None
    return name_lookup(union.spouse_handle)


def _descendant_ring_bounds(
    inner_radius: float,
    outer_radius: float,
    generation_count: int,
    depth: int,
) -> tuple[float, float]:
    """Return ring-local descendant bounds for one supported depth."""
    if generation_count < 1 or depth < 1 or depth > generation_count:
        raise ValueError("descendant depth must be inside the configured generation range")
    total_depth = outer_radius - inner_radius
    if generation_count == 1:
        widths = [total_depth]
    elif generation_count == 2:
        # ``depth=1`` is the direct child of the central couple and
        # ``depth=2`` is the grandchild. Keep the direct-child lane compact,
        # and give the grandchild lane the requested 2x radial depth while
        # preserving the fixed outer boundary of the descendant fan.
        exact_inner = (202 / 600, 302 / 600)
        exact_outer = (297 / 600, 598 / 600)
        return (
            outer_radius * exact_inner[depth - 1],
            outer_radius * exact_outer[depth - 1],
        )
    else:
        weights = [1.0 + 0.35 * index for index in range(generation_count)]
        total_weight = sum(weights)
        widths = [total_depth * weight / total_weight for weight in weights]

        # The extracted root branch is already a child of the central couple:
        # ``depth=1`` is therefore the direct-child ring and ``depth=2`` is
        # the grandchild ring. Transfer the extra depth needed to double the
        # grandchild lane from later rings so the full descendant composition
        # remains contained within the original outer radius.
        grandchild_visible_width = max(widths[1] - _RING_GAP_MM, 0.0)
        remaining_transfer = grandchild_visible_width
        minimum_direct_visible_width = max(
            8.0,
            total_depth * 0.05,
            _DESCENDANT_DIRECT_MEDALLION_MIN_RING_WIDTH_MM,
        )
        minimum_later_visible_width = min(
            _DESCENDANT_LATER_RING_MIN_WIDTH_MM,
            max(8.0, total_depth * 0.30),
        )
        # On smaller pages, the normal later-ring floor can consume the space
        # needed to complete the target doubling. Scale that floor before
        # taking more from the direct-child ring; the latter must retain its
        # medallion capacity whenever the total radial budget allows it.
        direct_donor_capacity = max(
            widths[0] - _RING_GAP_MM - minimum_direct_visible_width,
            0.0,
        )
        later_ring_count = len(widths) - 2
        needed_later_transfer = max(
            remaining_transfer - direct_donor_capacity,
            0.0,
        )
        if later_ring_count and needed_later_transfer > 0.0:
            later_visible_budget = sum(
                max(width - _RING_GAP_MM, 0.0)
                for width in widths[2:]
            )
            scaled_later_floor = max(
                _DESCENDANT_LATER_RING_MIN_LABEL_WIDTH_MM,
                (later_visible_budget - needed_later_transfer)
                / later_ring_count,
            )
            minimum_later_visible_width = min(
                minimum_later_visible_width,
                scaled_later_floor,
            )
        # Preserve the generations immediately following the target whenever
        # possible: the outermost rings are the least identity-dense and can
        # donate their excess width without collapsing intermediate unions.
        for offset in range(len(widths) - 1, 1, -1):
            reducible = max(
                widths[offset] - _RING_GAP_MM - minimum_later_visible_width,
                0.0,
            )
            transfer = min(remaining_transfer, reducible)
            widths[offset] -= transfer
            widths[1] += transfer
            remaining_transfer -= transfer
            if remaining_transfer <= 0.0:
                break
        if remaining_transfer > 0.0:
            # A three-generation layout has only one later ring. Preserve a
            # small direct-child lane as well, but use it as the final donor so
            # the grandchild target remains exact whenever the page can hold it.
            reducible = max(
                widths[0] - _RING_GAP_MM - minimum_direct_visible_width,
                0.0,
            )
            transfer = min(remaining_transfer, reducible)
            widths[0] -= transfer
            widths[1] += transfer
    ring_inner = inner_radius + sum(widths[: depth - 1])
    return ring_inner, ring_inner + widths[depth - 1] - _RING_GAP_MM


def layout_descendants(
    canvas: ChartCanvas,
    branches: tuple[DescendantBranch, ...],
    *,
    name_lookup,
    dates_lookup=None,
    shortener=None,
    portrait_lookup=None,
    highlight_lookup=None,
    show_highlight_markers: bool = False,
    configured_generation_limit: int | None = None,
) -> SceneNode:
    """Place all descendant medallions in the lower half-circle.

    Generates:
    - Colored annular sectors for each child branch
    - Sub-sectors for grandchildren
    - Curved text labels for children (shortened via *shortener*)
    - A second curved arc with the spouse name prefixed by ``×``
    - Medallions at the midpoint of first-generation sectors only
    - Straight text for grandchildren
    - Three radial continuation dots when the final displayed person has
      recorded children beyond the configured depth

    Highlight markers are opt-in so publication views do not expose tag
    annotations unless explicitly requested.

    ``configured_generation_limit`` is the report's requested descendant
    depth. The production pipeline passes it explicitly; ``None`` preserves
    compatibility for low-level callers that provide only a materialized
    scene.
    """
    if not branches:
        return SceneNode(children=())

    # Allocate every first-generation branch from the densest visible depth,
    # not merely its immediate child count. This prevents deep lineages from
    # collapsing into sub-degree outer sectors while sparse branches stay wide.
    allocations = _allocate_descendant_branches_by_demand(
        branches,
        start_angle=_DESC_START_ANGLE,
        total_sweep=_DESC_TOTAL_SWEEP,
    )

    all_children: list = []
    measure_only = True
    # Assign colors once per semantic union, including unions without visible
    # children, and reuse the assignment for the union cell and every
    # descendant sector placed below that union. The render pass repeats the
    # traversal, keeping this map across both passes prevents nested
    # branches from shifting the palette.
    union_fill_indices: dict[tuple[str, int], int] = {}
    branch_fill_indices: dict[str, int] = {}
    next_union_fill_index = 0
    last_populated_union_fill: str | None = None
    name_size_candidates: dict[int, list[float]] = {}
    generation_name_sizes: dict[int, float] = {}
    generation_date_sizes: dict[int, float] = {}
    name_cache: dict[str, str] = {}
    date_cache: dict[str, str] = {}
    inner_r = canvas.descendant_inner_radius_mm
    outer_r = canvas.descendant_outer_radius_mm
    max_gen = max(_max_desc_depth(b) for b in branches) if branches else 1
    displayed_generation_limit = (
        max_gen
        if configured_generation_limit is None
        else configured_generation_limit
    )
    total_depth = outer_r - inner_r
    if max_gen <= 1:
        ring_widths = [total_depth]
    elif max_gen == 2:
        # Match the mockup: children ring narrower, grandchildren ring wider.
        ring_widths = [total_depth * 0.38, total_depth * 0.62]
    else:
        # Grow outer descendant rings progressively when deeper trees appear.
        weights = [1.0 + 0.35 * i for i in range(max_gen)]
        total_w = sum(weights)
        ring_widths = [total_depth * w / total_w for w in weights]

    cx = canvas.center_cx_mm
    cy = canvas.center_cy_mm

    def _name_label(handle: str | None) -> str:
        if not handle:
            return ""
        if handle not in name_cache:
            name_cache[handle] = name_lookup(handle)
        return name_cache[handle]

    def _date_label(handle: str | None) -> str:
        if dates_lookup is None or not handle:
            return ""
        if handle not in date_cache:
            date_cache[handle] = dates_lookup(handle)
        return date_cache[handle]

    def _short(label: str, depth: int) -> str:
        if shortener is None or not label:
            return label
        try:
            return shortener(label, depth)
        except Exception:
            return label

    def _portrait(handle: str | None) -> str | None:
        if measure_only or portrait_lookup is None or not handle:
            return None
        try:
            return portrait_lookup(handle)
        except Exception:
            return None

    def _highlight(handle: str | None) -> bool:
        if (
            measure_only
            or not show_highlight_markers
            or highlight_lookup is None
            or not handle
        ):
            return False
        try:
            return bool(highlight_lookup(handle))
        except Exception:
            return False

    def _stable_union_fill_index(
        branch: DescendantBranch,
        union_index: int,
    ) -> int:
        """Return one deterministic palette index for a recorded union.

        Every recorded union consumes a slot, including unions without visible
        children, so a later union cannot inherit the empty union's color. If
        the cycling palette would repeat the previous populated union, skip to
        the next palette slot so adjacent populated groups remain distinct.
        """
        nonlocal last_populated_union_fill, next_union_fill_index
        key = (branch.position_id, union_index)
        if key not in union_fill_indices:
            groups = _children_grouped_by_union(branch)
            has_children = (
                0 <= union_index < len(groups)
                and bool(groups[union_index])
            )
            fill_index = next_union_fill_index
            next_union_fill_index += 1
            if has_children and last_populated_union_fill is not None:
                while descendant_fill(fill_index) == last_populated_union_fill:
                    fill_index += 1
                    next_union_fill_index = fill_index + 1
            union_fill_indices[key] = fill_index
            if has_children:
                last_populated_union_fill = descendant_fill(fill_index)
        return union_fill_indices[key]

    def _branch_fill_index(
        branch: DescendantBranch,
        branch_index: int,
        inherited_union_fill_index: int | None,
    ) -> int:
        """Resolve the fill inherited by a non-split descendant branch."""
        if inherited_union_fill_index is not None:
            return inherited_union_fill_index
        if len(branch.unions) == 1:
            return _stable_union_fill_index(branch, 0)
        if not branch.unions:
            if branch.position_id not in branch_fill_indices:
                nonlocal last_populated_union_fill, next_union_fill_index
                fill_index = next_union_fill_index
                next_union_fill_index += 1
                if last_populated_union_fill is not None:
                    while descendant_fill(fill_index) == last_populated_union_fill:
                        fill_index += 1
                        next_union_fill_index = fill_index + 1
                branch_fill_indices[branch.position_id] = fill_index
                last_populated_union_fill = descendant_fill(fill_index)
            return branch_fill_indices[branch.position_id]
        return branch_index

    def _group_fill_index(
        group_key: tuple[str, str, int],
    ) -> int | None:
        """Return the reserved palette index for one semantic group."""
        if group_key[0] == "union":
            return union_fill_indices.get((group_key[1], group_key[2]))
        return branch_fill_indices.get(group_key[1])

    def _reserve_fill_index(
        group_key: tuple[str, str, int],
        previous_group: tuple[str, str, int] | None,
        next_group: tuple[str, str, int] | None,
    ) -> None:
        """Reserve one group slot while avoiding its ring neighbors."""
        nonlocal next_union_fill_index
        if _group_fill_index(group_key) is not None:
            return
        forbidden_fills: set[str] = set()
        for neighbor_group in (previous_group, next_group):
            if neighbor_group is None or neighbor_group == group_key:
                continue
            neighbor_index = _group_fill_index(neighbor_group)
            if neighbor_index is not None:
                forbidden_fills.add(descendant_fill(neighbor_index))
        fill_index = next_union_fill_index
        next_union_fill_index += 1
        while descendant_fill(fill_index) in forbidden_fills:
            fill_index += 1
            next_union_fill_index = fill_index + 1
        if group_key[0] == "union":
            union_fill_indices[(group_key[1], group_key[2])] = fill_index
        else:
            branch_fill_indices[group_key[1]] = fill_index

    def _current_fill_groups(
        branch: DescendantBranch,
        inherited_group: tuple[str, str, int] | None,
    ) -> tuple[tuple[str, str, int], ...]:
        """Return the semantic groups emitted by a branch at its ring."""
        if len(branch.unions) > 1:
            return tuple(
                ("union", branch.position_id, union_index)
                for union_index in range(len(branch.unions))
            )
        if inherited_group is not None:
            return (inherited_group,)
        if len(branch.unions) == 1:
            return (("union", branch.position_id, 0),)
        return (("branch", branch.position_id, -1),)

    def _reserve_fill_indices_by_depth() -> None:
        """Reserve colors in visual order independently for every ring."""
        current = [
            (branch, None)
            for branch in branches
        ]
        while current:
            level_entries: list[tuple[tuple[str, str, int], bool]] = []
            next_level: list[
                tuple[DescendantBranch, tuple[str, str, int] | None]
            ] = []
            for branch, inherited_group in current:
                current_groups = _current_fill_groups(branch, inherited_group)
                groups = list(_children_grouped_by_union(branch))
                if branch.unions and len(groups) < len(branch.unions):
                    groups.extend(
                        () for _ in range(len(branch.unions) - len(groups))
                    )
                if len(branch.unions) > 1:
                    group_activity = [
                        bool(group)
                        for group in groups[: len(branch.unions)]
                    ]
                elif inherited_group is not None:
                    group_activity = [True]
                elif branch.unions:
                    group_activity = [bool(groups[0])]
                else:
                    group_activity = [True]
                level_entries.extend(
                    zip(current_groups, group_activity)
                )
                if not branch.children:
                    continue
                if branch.unions:
                    for union_index, group in enumerate(
                        groups[: len(branch.unions)]
                    ):
                        child_group = (
                            current_groups[union_index]
                            if len(branch.unions) > 1
                            else current_groups[0]
                        )
                        next_level.extend(
                            (child, child_group)
                            for child in group
                        )
                else:
                    next_level.extend(
                        (child, current_groups[0])
                        for child in branch.children
                    )
            active_indexes = [
                index
                for index, (_group_key, active) in enumerate(level_entries)
                if active
            ]
            active_positions = {
                index: position
                for position, index in enumerate(active_indexes)
            }
            for index, (group_key, active) in enumerate(level_entries):
                if active:
                    position = active_positions[index]
                    previous_group = (
                        level_entries[active_indexes[position - 1]][0]
                        if position > 0
                        else None
                    )
                    next_group = (
                        level_entries[active_indexes[position + 1]][0]
                        if position + 1 < len(active_indexes)
                        else None
                    )
                else:
                    previous_group = None
                    next_group = None
                _reserve_fill_index(group_key, previous_group, next_group)
            current = next_level

    def _fit_generation_name(
        content: str,
        depth: int,
        *,
        target_size: float,
        minimum_size: float,
        max_width: float,
        allow_ellipsis: bool = False,
    ) -> tuple[str, float, float]:
        """Fit a name while keeping one measured size for its generation."""
        common_size = generation_name_sizes.get(depth)
        if not measure_only and common_size is not None:
            fitted, _ignored_size, width_limit = _fit_text_to_width(
                content,
                target_size=common_size,
                minimum_size=common_size,
                max_width=max_width,
                allow_ellipsis=allow_ellipsis,
            )
            return fitted, common_size, width_limit

        fitted, fitted_size, width_limit = _fit_text_to_width(
            content,
            target_size=target_size,
            minimum_size=minimum_size,
            max_width=max_width,
            allow_ellipsis=allow_ellipsis,
        )
        if measure_only:
            if content:
                measured_size = _font_size_for_width(
                    content,
                    target_size=target_size,
                    max_width=max_width,
                )
                name_size_candidates.setdefault(depth, []).append(measured_size)
                return content, measured_size, width_limit
            return fitted, fitted_size, width_limit
        return fitted, fitted_size, width_limit

    def _fit_generation_couple(
        child_label: str,
        spouse_label: str,
        depth: int,
        *,
        target_size: float,
        minimum_size: float,
        max_width: float,
    ) -> tuple[str, float, float]:
        """Fit a compact couple label at the common generation size."""
        combined = f"{child_label} × {spouse_label}"
        common_size = generation_name_sizes.get(depth)
        if not measure_only and common_size is not None:
            fitted, _ignored_size, width_limit = _fit_text_to_width(
                combined,
                target_size=common_size,
                minimum_size=common_size,
                max_width=max_width,
                allow_ellipsis=False,
            )
            return fitted, common_size, width_limit

        fitted, fitted_size, width_limit = _fit_text_to_width(
            combined,
            target_size=target_size,
            minimum_size=minimum_size,
            max_width=max_width,
            allow_ellipsis=False,
        )
        if measure_only:
            measured_size = _font_size_for_width(
                combined,
                target_size=target_size,
                max_width=max_width,
            )
            name_size_candidates.setdefault(depth, []).append(measured_size)
            return combined, measured_size, width_limit
        return fitted, fitted_size, width_limit

    def _fit_generation_stacked_couple(
        depth: int,
        text_radius: float,
        sweep_angle: float,
        *,
        child_label: str,
        spouse_label: str,
        target_size: float,
        minimum_size: float,
        max_width: float,
    ) -> float | None:
        """Fit stacked couple lanes against the common generation size."""
        half_arc = (
            text_radius
            * math.radians(max(sweep_angle, 0.0))
            / 2.0
        )
        local_size = min(
            target_size,
            (half_arc - 0.3) / 1.12,
        )
        local_size = min(
            local_size,
            _font_size_for_width(
                child_label,
                target_size=local_size,
                max_width=max_width,
            ),
            _font_size_for_width(
                f"× {spouse_label}",
                target_size=local_size,
                max_width=max_width,
            ),
        )
        stack_floor = minimum_size * 0.75
        if local_size < stack_floor or max_width < local_size * 2.1:
            return None
        if measure_only:
            name_size_candidates.setdefault(depth, []).append(local_size)
            return local_size
        return generation_name_sizes.get(depth, local_size)

    def _generation_date_size(depth: int, fallback_name_size: float) -> float:
        """Return one shared date size, one step below its name generation."""
        if depth in generation_date_sizes:
            return generation_date_sizes[depth]
        return _date_font_size(
            generation_name_sizes.get(depth, fallback_name_size)
        )

    def _target_medallion_radius(depth: int, ring_depth: float) -> float:
        """Return a readable target; individual narrow sectors may omit it."""
        ideal = {1: 8.2, 2: 5.4, 3: 4.0, 4: 3.4, 5: 3.2}.get(depth, 3.2)
        reserved_text_depth = (
            min(36.0, ring_depth * _MEDALLION_TEXT_RESERVE_RATIO)
            if depth == 1
            else min(max(28.0, ring_depth * 0.45), ring_depth * 0.58)
        )
        radial_cap = max(
            0.0,
            (ring_depth - _MEDALLION_EDGE_CLEARANCE_MM - reserved_text_depth) / 2.0,
        )
        return min(ideal, radial_cap)

    def _emit_medallion(
        x: float,
        y: float,
        radius: float,
        label: str,
        portrait: str | None,
        highlighted: bool = False,
    ) -> None:
        if measure_only:
            return
        all_children.append(SceneCircle(
            cx=x,
            cy=y,
            r=radius * (1.1 if portrait else 1.0),
            fill=MEDALLION_FILL,
            stroke=MEDALLION_BORDER,
            stroke_width=0.3,
        ))
        if highlighted:
            all_children.append(SceneMarker(
                cx=x,
                cy=y,
                radius=radius + 1.25,
            ))
        if portrait:
            all_children.append(SceneImage(
                cx=x,
                cy=y,
                r=radius,
                data_uri=portrait,
            ))
            return
        initials = _extract_initials(label) if label else ""
        if initials:
            all_children.append(SceneText(
                x=x,
                y=y + radius * 0.25,
                content=initials,
                font_size=radius * 0.55,
                fill=TEXT_DARK,
                anchor="middle",
            ))

    def _emit_continuation_dots(
        start_angle: float,
        sweep_angle: float,
        ring_outer: float,
    ) -> None:
        """Render three small dots beyond one final descendant cell."""
        if measure_only or sweep_angle <= 0.0:
            return
        mid_angle = start_angle + sweep_angle / 2.0
        for index in range(3):
            dot_radius = (
                ring_outer
                + _DESCENDANT_CONTINUATION_DOT_OFFSET_MM
                + index * _DESCENDANT_CONTINUATION_DOT_SPACING_MM
            )
            dot_x, dot_y = _polar(cx, cy, dot_radius, mid_angle)
            all_children.append(SceneCircle(
                cx=dot_x,
                cy=dot_y,
                r=_DESCENDANT_CONTINUATION_DOT_RADIUS_MM,
                fill=CONTINUATION_DOT_FILL,
            ))

    def _place_branch(
        branch: DescendantBranch,
        alloc_start: float,
        alloc_sweep: float,
        depth: int,
        branch_index: int,
        union_fill_index: int | None = None,
    ) -> None:
        """Recursively place a branch and its children."""
        mid_angle = alloc_start + alloc_sweep / 2.0
        union_cells = (
            _allocate_descendant_union_cells(
                branch,
                start_angle=alloc_start,
                total_sweep=alloc_sweep,
            )
            if len(branch.unions) > 1
            else ()
        )
        inherited_fill_index = _branch_fill_index(
            branch,
            branch_index,
            union_fill_index,
        )
        union_cell_fill_indices = {
            cell.union_index: _stable_union_fill_index(
                branch,
                cell.union_index,
            )
            for cell in union_cells
        }

        if max_gen >= 2 and depth <= max_gen:
            gen_inner, gen_outer = _descendant_ring_bounds(
                inner_r, outer_r, max_gen, depth
            )
            ring_width = gen_outer - gen_inner
        else:
            gen_inner = inner_r + sum(ring_widths[: depth - 1])
            ring_width = ring_widths[min(depth - 1, len(ring_widths) - 1)]
            gen_outer = gen_inner + ring_width - _RING_GAP_MM

        # Emit sector for this branch
        if not measure_only:
            if union_cells:
                for cell in union_cells:
                    all_children.append(SceneSector(
                        inner_radius=gen_inner,
                        outer_radius=gen_outer,
                        start_angle=cell.start_angle,
                        sweep_angle=cell.sweep_angle,
                        fill=descendant_fill(
                            union_cell_fill_indices[cell.union_index]
                        ),
                        stroke=SECTOR_STROKE,
                        stroke_width=SECTOR_STROKE_WIDTH,
                        cx=cx,
                        cy=cy,
                    ))
            else:
                fill = descendant_fill(inherited_fill_index)
                all_children.append(SceneSector(
                    inner_radius=gen_inner,
                    outer_radius=gen_outer,
                    start_angle=alloc_start,
                    sweep_angle=alloc_sweep,
                    fill=fill,
                    stroke=SECTOR_STROKE,
                    stroke_width=SECTOR_STROKE_WIDTH,
                    cx=cx,
                    cy=cy,
                ))

        raw_label = _descendant_label(branch, _name_label)
        child_label = _short(raw_label, depth)

        spouse_entries: list[tuple[str, str, str]] = []
        # Every displayed descendant generation keeps its couple label. This
        # includes the final ring, where there is no child ring to associate
        # with the union but the spouse remains part of the displayed couple.
        for union in branch.unions:
            if union.spouse_handle:
                sp_raw = _spouse_label(union, _name_label)
                if sp_raw:
                    spouse_entries.append(
                        (
                            union.spouse_handle,
                            sp_raw,
                            _short(sp_raw, depth),
                        )
                    )

        spouse_handle = spouse_entries[0][0] if spouse_entries else None
        spouse_medallion_label = spouse_entries[0][1] if spouse_entries else None
        spouse_display_name = " / ".join(
            entry[2] for entry in spouse_entries if entry[2]
        )
        collapsed_private_couple = (
            raw_label == "Personne privée"
            and spouse_medallion_label == "Personne privée"
        )
        if collapsed_private_couple:
            child_label = "Personnes privées"
            spouse_display_name = ""

        def _spouse_entry_for_union(
            union_index: int,
        ) -> tuple[str, str, str] | None:
            if not 0 <= union_index < len(branch.unions):
                return None
            union = branch.unions[union_index]
            if not union.spouse_handle:
                return None
            raw = _spouse_label(union, _name_label)
            if not raw:
                return None
            return (
                union.spouse_handle,
                raw,
                _short(raw, depth),
            )

        def _union_cell_content(
            union_index: int,
        ) -> tuple[str, tuple[str, str, str] | None]:
            """Return the privacy-safe child/spouse content for one union cell."""
            entry = _spouse_entry_for_union(union_index)
            if (
                raw_label == "Personne privée"
                and entry is not None
                and entry[1] == "Personne privée"
            ):
                return "Personnes privées", None
            return _short(raw_label, depth), entry

        def _emit_highlight_markers(
            marker_start: float,
            marker_sweep: float,
            marker_spouse_handle: str | None,
        ) -> None:
            """Render highlight markers in one branch or union cell."""
            if measure_only:
                return
            marker_radius = min(2.0, max(1.1, ring_width * 0.08))
            marker_distance = max(
                gen_inner + marker_radius + 1.0,
                gen_outer - marker_radius - 1.0,
            )
            marker_mid_angle = marker_start + marker_sweep / 2.0
            highlighted_angles = []
            if _highlight(branch.person.handle if branch.person else None):
                highlighted_angles.append(marker_mid_angle)
            if _highlight(marker_spouse_handle):
                highlighted_angles.append(
                    marker_mid_angle + min(2.0, marker_sweep * 0.12)
                )
            for marker_angle in highlighted_angles:
                marker_x, marker_y = _polar(
                    cx,
                    cy,
                    marker_distance,
                    marker_angle,
                )
                all_children.append(SceneMarker(
                    cx=marker_x,
                    cy=marker_y,
                    radius=marker_radius,
                ))

        def _emit_dense_first_generation_lines(
            start_angle: float,
            sweep_angle: float,
            dense_lines: list[tuple[str, bool, str]],
        ) -> None:
            """Render one dense first-generation union cell."""
            dense_lines = [line for line in dense_lines if line[0]]
            if not dense_lines:
                return
            text_start = gen_inner + 2.0
            text_end = med_text_inner - 2.0
            radial_span = max(0.0, text_end - text_start)
            if len(dense_lines) == 1:
                first_line_offset = radial_span / 2.0
                line_gap = 0.0
            else:
                maximum_line_gap = radial_span / (len(dense_lines) - 1)
                preferred_line_gap = max(
                    _DESCENDANT_FIRST_GEN_LINE_GAP_MM,
                    radial_span / (len(dense_lines) + 1),
                )
                line_gap = min(preferred_line_gap, maximum_line_gap)
                first_line_offset = (
                    radial_span - line_gap * (len(dense_lines) - 1)
                ) / 2.0
            for line_index, (content, is_name, fill_color) in enumerate(dense_lines):
                line_r = text_start + first_line_offset + line_gap * line_index
                angular_width = max(
                    0.0,
                    line_r * math.radians(max(sweep_angle - 1.0, 0.0)) - 2.0,
                )
                if is_name:
                    fitted, fitted_size, width_limit = _fit_generation_name(
                        content,
                        depth,
                        target_size=4.5,
                        minimum_size=3.2,
                        max_width=angular_width,
                    )
                else:
                    date_size = _generation_date_size(depth, 3.4)
                    if date_size <= 0.0:
                        continue
                    fitted, fitted_size, width_limit = _fit_text_to_width(
                        content,
                        target_size=date_size,
                        minimum_size=date_size,
                        max_width=angular_width,
                        allow_ellipsis=False,
                    )
                if not fitted or measure_only:
                    continue
                all_children.append(ScenePathText(
                    path=_arc_text_path(
                        cx,
                        cy,
                        line_r,
                        start_angle,
                        start_angle + sweep_angle,
                        lower=True,
                    ),
                    content=fitted,
                    font_size=fitted_size,
                    fill=fill_color,
                    max_width=width_limit,
                ))

        def _emit_single_generation_lines(
            start_angle: float,
            sweep_angle: float,
            single_lines: list[tuple[str, bool, str]],
        ) -> None:
            """Render one first-generation cell in the single-ring mode."""
            single_lines = [line for line in single_lines if line[0]]
            if not single_lines:
                return
            text_start = gen_inner + 4.0
            text_end = max(text_start, med_text_inner - 2.0)
            radial_span = max(0.0, text_end - text_start)
            for line_index, (content, is_name, fill_color) in enumerate(single_lines):
                line_r = (
                    text_start
                    + radial_span * (line_index + 0.5) / len(single_lines)
                )
                angular_width = max(
                    0.0,
                    line_r * math.radians(max(sweep_angle - 1.0, 0.0)) - 2.0,
                )
                if is_name:
                    fitted, fitted_size, width_limit = _fit_generation_name(
                        content,
                        depth,
                        target_size=outer_r * (12 / 600),
                        minimum_size=4.0,
                        max_width=angular_width,
                    )
                else:
                    date_size = _generation_date_size(depth, outer_r * (9.5 / 600))
                    if date_size <= 0.0:
                        continue
                    fitted, fitted_size, width_limit = _fit_text_to_width(
                        content,
                        target_size=date_size,
                        minimum_size=date_size,
                        max_width=angular_width,
                        allow_ellipsis=False,
                    )
                if not fitted or measure_only:
                    continue
                all_children.append(ScenePathText(
                    path=_arc_text_path(
                        cx,
                        cy,
                        line_r,
                        start_angle,
                        start_angle + sweep_angle,
                        lower=True,
                    ),
                    content=fitted,
                    font_size=fitted_size,
                    fill=fill_color,
                    max_width=width_limit,
                ))

        # Place one portrait medallion or a tangent couple pair when the local
        # sector can sustain a readable circle. A narrow sector falls back to
        # text-only without shrinking every other medallion in its generation.
        # The requested default keeps the descendant GEN1 medallions as the
        # visual entry points, but removes every medallion from GEN2 onward.
        # Text and couple labels remain available in those rings.
        # A multi-union branch gets one local couple pair per cell; the single
        # branch-level pair would straddle the union boundary. Deep-generation
        # cells stay text-only, matching their ring's medallion policy.
        show_medallion = depth == 1 and not union_cells
        adaptive_single_generation = max_gen == 1
        adaptive_dense = max_gen >= 3
        if show_medallion and adaptive_single_generation:
            has_spouse = bool(spouse_handle and spouse_medallion_label)
            med_capacity = _maximum_medallion_radius(
                inner_radius=gen_inner,
                outer_radius=gen_outer,
                sweep_angle=alloc_sweep,
                occupants=2 if has_spouse else 1,
                edge="outer",
                margin=0.8,
            )
            # Reserve the portrait border as well as the enlarged image radius.
            # The larger portrait remains in the outer crown, where it no
            # longer competes with the text lanes.
            med_visual_target = outer_r * _DESCENDANT_MEDALLION_TARGET_RATIO * 1.1
            med_visual_r = min(med_capacity, med_visual_target)
            med_border_r = (
                med_visual_r / 1.1
                if med_visual_r / 1.1 >= _MIN_INITIALS_MEDALLION_RADIUS_MM
                else 0.0
            )
            pair_offset = med_visual_r * 1.075 if has_spouse else 0.0
            if med_border_r > 0:
                target_center_radius = max(
                    0.0,
                    gen_outer - 0.8 - med_visual_r,
                )
                med_text_inner = max(
                    gen_inner,
                    target_center_radius - med_visual_r - 6.0,
                )
                med_r_pos = (
                    math.sqrt(max(0.0, target_center_radius**2 - pair_offset**2))
                    if has_spouse
                    else target_center_radius
                )
            else:
                med_text_inner = gen_outer
                med_r_pos = gen_outer
        elif show_medallion and adaptive_dense:
            has_spouse = bool(spouse_handle and spouse_medallion_label)
            med_capacity = _maximum_medallion_radius(
                inner_radius=gen_inner,
                outer_radius=gen_outer,
                sweep_angle=alloc_sweep,
                occupants=2 if has_spouse else 1,
                edge="outer",
                margin=0.8,
            )
            med_target = _target_medallion_radius(depth, gen_outer - gen_inner)
            if min(med_capacity, med_target) >= _MIN_INITIALS_MEDALLION_RADIUS_MM:
                med_border_r = min(med_capacity, med_target)
            else:
                med_border_r = 0.0
            pair_offset = med_border_r * 1.075
            if med_border_r > 0:
                target_center_radius = gen_outer - 0.8 - med_border_r
                med_text_inner = target_center_radius - med_border_r
                med_r_pos = (
                    math.sqrt(max(0.0, target_center_radius**2 - pair_offset**2))
                    if has_spouse
                    else target_center_radius
                )
            else:
                med_text_inner = gen_outer
                med_r_pos = gen_outer
        elif show_medallion:
            med_border_r = outer_r * ((20 / 600) if depth == 1 else (14 / 600))
            med_r_pos = outer_r * ((245 / 600) if depth == 1 else (397 / 600))
            pair_offset = outer_r * (20 / 600)
            med_text_inner = med_r_pos - med_border_r

            # The direct-child couple label is rendered after these portraits.
            # On compact two-ring pages, keep both primitives only when a
            # readable label lane can clear the portrait envelope; otherwise
            # prefer the complete identity label over a hidden or overpainted
            # medallion.
            if depth == 1 and med_border_r > 0.5:
                medallion_radial_extent = (
                    math.hypot(med_r_pos, pair_offset)
                    + med_border_r * 1.1
                )
                label_font_capacity = (
                    gen_outer
                    - _RING_GAP_MM
                    - _MEDALLION_EDGE_CLEARANCE_MM
                    - medallion_radial_extent
                )
                if label_font_capacity < _DIRECT_LABEL_MIN_FONT_SIZE_MM:
                    med_border_r = 0.0
                    med_r_pos = gen_outer
                    pair_offset = 0.0
                    med_text_inner = gen_outer
        else:
            med_border_r = 0.0
            med_r_pos = gen_outer
            pair_offset = 0.0
            # Without a GEN2+ medallion, let the text use the complete ring.
            med_text_inner = gen_outer

        if med_border_r > 0.5:
            mx, my = _polar(cx, cy, med_r_pos, mid_angle)
            child_portrait_data = _portrait(
                branch.person.handle if branch.person else None
            )
            if spouse_handle and spouse_medallion_label:
                angle_rad = math.radians(mid_angle)
                tangent_x = math.cos(angle_rad)
                tangent_y = math.sin(angle_rad)
                spouse_portrait_data = _portrait(spouse_handle)
                child_radius = (
                    med_border_r / 1.1
                    if adaptive_dense and child_portrait_data
                    else med_border_r
                )
                spouse_radius = (
                    med_border_r / 1.1
                    if adaptive_dense and spouse_portrait_data
                    else med_border_r
                )
                _emit_medallion(
                    mx - tangent_x * pair_offset,
                    my - tangent_y * pair_offset,
                    child_radius,
                    child_label or raw_label,
                    child_portrait_data,
                    _highlight(branch.person.handle),
                )
                _emit_medallion(
                    mx + tangent_x * pair_offset,
                    my + tangent_y * pair_offset,
                    spouse_radius,
                    spouse_medallion_label,
                    spouse_portrait_data,
                    _highlight(spouse_handle),
                )
            else:
                child_radius = (
                    med_border_r / 1.1
                    if adaptive_dense and child_portrait_data
                    else med_border_r
                )
                _emit_medallion(
                    mx,
                    my,
                    child_radius,
                    child_label or raw_label,
                    child_portrait_data,
                    _highlight(branch.person.handle),
                )
        elif not union_cells:
            # Later-generation people are text-only by design. When highlight
            # markers are enabled, keep their citation signal visible with a
            # small diamond in the same sector instead of dropping it.
            _emit_highlight_markers(alloc_start, alloc_sweep, spouse_handle)

        if union_cells and depth == 1:
            union_text_inners: list[float] = []
            for cell in union_cells:
                cell_child_label, entry = _union_cell_content(cell.union_index)
                cell_spouse_handle = entry[0] if entry else None
                cell_spouse_label = entry[2] if entry else ""
                cell_has_spouse = bool(cell_spouse_handle and cell_spouse_label)
                cell_med_capacity = _maximum_medallion_radius(
                    inner_radius=gen_inner,
                    outer_radius=gen_outer,
                    sweep_angle=cell.sweep_angle,
                    occupants=2 if cell_has_spouse else 1,
                    edge="inner" if max_gen == 2 else "outer",
                    margin=0.8,
                )
                if adaptive_single_generation:
                    cell_visual_target = (
                        outer_r * _DESCENDANT_MEDALLION_TARGET_RATIO * 1.1
                    )
                    cell_visual_r = min(cell_med_capacity, cell_visual_target)
                    cell_border_r = (
                        cell_visual_r / 1.1
                        if cell_visual_r / 1.1 >= _MIN_INITIALS_MEDALLION_RADIUS_MM
                        else 0.0
                    )
                    cell_pair_offset = (
                        cell_visual_r * 1.075 if cell_has_spouse else 0.0
                    )
                    if cell_border_r > 0:
                        cell_center_radius = max(
                            0.0,
                            gen_outer - 0.8 - cell_visual_r,
                        )
                        cell_text_inner = max(
                            gen_inner,
                            cell_center_radius - cell_visual_r - 6.0,
                        )
                        cell_med_r_pos = (
                            math.sqrt(
                                max(
                                    0.0,
                                    cell_center_radius**2 - cell_pair_offset**2,
                                )
                            )
                            if cell_has_spouse
                            else cell_center_radius
                        )
                    else:
                        cell_text_inner = gen_outer
                        cell_med_r_pos = gen_outer
                else:
                    cell_target = (
                        _target_medallion_radius(depth, gen_outer - gen_inner)
                        if adaptive_dense
                        else outer_r * (20 / 600)
                    )
                    cell_border_r = min(cell_med_capacity, cell_target)
                    if cell_border_r < _MIN_INITIALS_MEDALLION_RADIUS_MM:
                        cell_border_r = 0.0
                    cell_pair_offset = (
                        cell_border_r * 1.075 if cell_has_spouse else 0.0
                    )
                    if cell_border_r > 0:
                        if max_gen == 2:
                            # The fixed two-ring label rails occupy the outer
                            # lane (317/600 and 337/600). Keep union-cell
                            # medallions in the original inner lane instead of
                            # placing them through those labels.
                            cell_med_r_pos = outer_r * (245 / 600)
                            cell_text_inner = min(
                                gen_outer,
                                cell_med_r_pos + cell_border_r + 1.0,
                            )
                        else:
                            cell_center_radius = gen_outer - 0.8 - cell_border_r
                            cell_text_inner = max(
                                gen_inner,
                                cell_center_radius - cell_border_r - 1.0,
                            )
                            cell_med_r_pos = (
                                math.sqrt(
                                    max(
                                        0.0,
                                        cell_center_radius**2 - cell_pair_offset**2,
                                    )
                                )
                                if cell_has_spouse
                                else cell_center_radius
                            )
                    else:
                        cell_text_inner = gen_outer
                        cell_med_r_pos = gen_outer
                cell_mid_angle = cell.start_angle + cell.sweep_angle / 2.0
                union_text_inners.append(cell_text_inner)
                if cell_border_r <= 0.5:
                    _emit_highlight_markers(
                        cell.start_angle,
                        cell.sweep_angle,
                        cell_spouse_handle,
                    )
                    continue
                if measure_only:
                    continue
                cell_mx, cell_my = _polar(
                    cx,
                    cy,
                    cell_med_r_pos,
                    cell_mid_angle,
                )
                cell_child_portrait = _portrait(
                    branch.person.handle if branch.person else None
                )
                if cell_has_spouse:
                    angle_rad = math.radians(cell_mid_angle)
                    tangent_x = math.cos(angle_rad)
                    tangent_y = math.sin(angle_rad)
                    cell_spouse_portrait = _portrait(cell_spouse_handle)
                    cell_child_radius = (
                        cell_border_r / 1.1
                        if cell_child_portrait
                        else cell_border_r
                    )
                    cell_spouse_radius = (
                        cell_border_r / 1.1
                        if cell_spouse_portrait
                        else cell_border_r
                    )
                    _emit_medallion(
                        cell_mx - tangent_x * cell_pair_offset,
                        cell_my - tangent_y * cell_pair_offset,
                        cell_child_radius,
                        cell_child_label or raw_label,
                        cell_child_portrait,
                        _highlight(branch.person.handle),
                    )
                    _emit_medallion(
                        cell_mx + tangent_x * cell_pair_offset,
                        cell_my + tangent_y * cell_pair_offset,
                        cell_spouse_radius,
                        cell_spouse_label,
                        cell_spouse_portrait,
                        _highlight(cell_spouse_handle),
                    )
                else:
                    cell_child_radius = (
                        cell_border_r / 1.1
                        if cell_child_portrait
                        else cell_border_r
                    )
                    _emit_medallion(
                        cell_mx,
                        cell_my,
                        cell_child_radius,
                        cell_child_label or raw_label,
                        cell_child_portrait,
                        _highlight(branch.person.handle),
                    )
            if union_text_inners:
                med_text_inner = min(union_text_inners)

        if union_cells and depth > 1:
            # Multi-union cells at deeper generations are intentionally
            # text-only, so preserve one highlight marker pair per cell rather
            # than falling back to a marker at the shared branch midpoint.
            for cell in union_cells:
                entry = _spouse_entry_for_union(cell.union_index)
                _emit_highlight_markers(
                    cell.start_angle,
                    cell.sweep_angle,
                    entry[0] if entry else None,
                )

        # Labels use ring-local capacity in dense reports. The standard two-ring
        # publication geometry remains byte-for-byte compatible below.
        if child_label and adaptive_single_generation:
            child_dates = (
                _date_label(branch.person.handle)
                if dates_lookup is not None and branch.person
                else ""
            )
            if union_cells:
                cell_specs = []
                for cell in union_cells:
                    cell_child_label, entry = _union_cell_content(cell.union_index)
                    lines = [
                        (cell_child_label, True, TEXT_DARK),
                        (child_dates, False, TEXT_GREY),
                    ]
                    if entry:
                        lines.append((f"× {entry[2]}", True, TEXT_DARK))
                        spouse_date = (
                            _date_label(entry[0])
                            if dates_lookup is not None
                            else ""
                        )
                        lines.append((spouse_date, False, TEXT_GREY))
                    cell_specs.append((cell.start_angle, cell.sweep_angle, lines))
            else:
                spouse_date_parts: list[str] = []
                if dates_lookup is not None:
                    for handle, _spouse_raw, _spouse_short in spouse_entries:
                        date_label = _date_label(handle)
                        if date_label:
                            spouse_date_parts.append(date_label)
                spouse_dates = " / ".join(spouse_date_parts)
                lines = [
                    (child_label, True, TEXT_DARK),
                    (child_dates, False, TEXT_GREY),
                    (
                        f"× {spouse_display_name}" if spouse_display_name else "",
                        True,
                        TEXT_DARK,
                    ),
                    (
                        spouse_dates if spouse_display_name else "",
                        False,
                        TEXT_GREY,
                    ),
                ]
                cell_specs = [(alloc_start, alloc_sweep, lines)]
            for cell_start, cell_sweep, lines in cell_specs:
                _emit_single_generation_lines(cell_start, cell_sweep, lines)
        elif child_label and (
            depth > 1
            or adaptive_dense
        ):
            child_dates = (
                _date_label(branch.person.handle)
                if dates_lookup is not None and branch.person
                else ""
            )
            if depth == 1 and adaptive_dense:
                if union_cells:
                    cell_specs = []
                    for cell in union_cells:
                        cell_child_label, entry = _union_cell_content(cell.union_index)
                        lines = [
                            (cell_child_label, True, TEXT_DARK),
                            (child_dates, False, TEXT_GREY),
                        ]
                        if entry:
                            lines.append((f"× {entry[2]}", True, TEXT_DARK))
                            spouse_date = (
                                _date_label(entry[0])
                                if dates_lookup is not None
                                else ""
                            )
                            lines.append((spouse_date, False, TEXT_GREY))
                        cell_specs.append((cell.start_angle, cell.sweep_angle, lines))
                    for cell_start, cell_sweep, lines in cell_specs:
                        _emit_dense_first_generation_lines(
                            cell_start,
                            cell_sweep,
                            lines,
                        )
                else:
                    lines = [
                        (child_label, True, TEXT_DARK),
                        (child_dates, False, TEXT_GREY),
                    ]
                    for spouse_handle, _spouse_raw, spouse_short in spouse_entries:
                        lines.append((f"× {spouse_short}", True, TEXT_DARK))
                        spouse_dates = (
                            _date_label(spouse_handle)
                            if dates_lookup is not None
                            else ""
                        )
                        if spouse_dates:
                            lines.append((spouse_dates, False, TEXT_GREY))
                    lines = [line for line in lines if line[0]]
                    text_start = gen_inner + 2.0
                    text_end = med_text_inner - 2.0
                    for (content, is_name, fill_color), line_r in _first_generation_line_layout(
                        lines,
                        text_start=text_start,
                        text_end=text_end,
                    ):
                        angular_width = max(
                            0.0,
                            line_r * math.radians(max(alloc_sweep - 1.0, 0.0)) - 2.0,
                        )
                        if is_name:
                            fitted, fitted_size, width_limit = _fit_generation_name(
                                content,
                                depth,
                                target_size=4.5,
                                minimum_size=3.2,
                                max_width=angular_width,
                            )
                        else:
                            date_size = _generation_date_size(depth, 4.5)
                            if date_size <= 0.0:
                                continue
                            fitted, fitted_size, width_limit = _fit_text_to_width(
                                content,
                                target_size=date_size,
                                minimum_size=date_size,
                                max_width=angular_width,
                                allow_ellipsis=False,
                            )
                        if not fitted:
                            continue
                        if not measure_only:
                            all_children.append(ScenePathText(
                                path=_arc_text_path(
                                    cx,
                                    cy,
                                    line_r,
                                    alloc_start,
                                    alloc_start + alloc_sweep,
                                    lower=True,
                                ),
                                content=fitted,
                                font_size=fitted_size,
                                fill=fill_color,
                                max_width=width_limit,
                            ))
            else:
                text_start = gen_inner + 2.0
                text_end = med_text_inner - 2.0
                text_width = max(0.0, text_end - text_start)
                name_target = {2: 4.2, 3: 3.6, 4: 3.2, 5: 3.0}.get(depth, 3.0)
                name_minimum = 3.2 if depth == 2 else (1.8 if depth >= 3 else 2.8)

                def _render_intermediate_block(
                    block_mid_angle: float,
                    block_sweep: float,
                    block_child_label: str,
                    block_spouse: str,
                ) -> None:
                    """Render one intermediate-generation block or union cell."""
                    text_r = (text_start + text_end) / 2.0
                    base_x, base_y = _polar(cx, cy, text_r, block_mid_angle)
                    rotation = _outward_radial_rotation(block_mid_angle)
                    angular_capacity = max(
                        0.0,
                        text_r * math.radians(max(block_sweep - 0.25, 0.0)) - 1.0,
                    )

                    if block_spouse:
                        # Medium sectors use two parallel radial rails. Narrower
                        # sectors preserve both identities and the union marker in
                        # one compact rail; dates are sacrificed before either name.
                        parallel_capacity = name_target * 2.35
                        if angular_capacity >= parallel_capacity:
                            child_fit, child_size, child_width = _fit_generation_name(
                                block_child_label,
                                depth,
                                target_size=name_target,
                                minimum_size=name_minimum,
                                max_width=text_width,
                            )
                            spouse_fit, spouse_size, spouse_width = _fit_generation_name(
                                f"\u00d7 {block_spouse}",
                                depth,
                                target_size=name_target,
                                minimum_size=name_minimum,
                                max_width=text_width,
                            )
                            child_offset, spouse_offset = _couple_line_offsets(
                                block_mid_angle,
                                max(child_size, spouse_size) * 0.68,
                            )
                            for content, size, width, offset, color in (
                                (child_fit, child_size, child_width, child_offset, TEXT_DARK),
                                (spouse_fit, spouse_size, spouse_width, spouse_offset, TEXT_DARK),
                            ):
                                if not content:
                                    continue
                                tx, ty = _tangent_offset(
                                    base_x, base_y, block_mid_angle, offset
                                )
                                if not measure_only:
                                    all_children.append(SceneText(
                                        x=tx,
                                        y=ty,
                                        content=content,
                                        font_size=size,
                                        fill=color,
                                        anchor="middle",
                                        rotation=rotation,
                                        max_width=width,
                                    ))
                        else:
                            # A multi-union cell keeps full identities even when the
                            # couple does not fit side by side: stack the person and
                            # spouse onto separate radial lanes at a reduced common
                            # size instead of truncating either name. The stacked
                            # size is derived from the cell's own tangential arc so
                            # neither rail can cross the union boundary.
                            if union_cells:
                                stack_size = _fit_generation_stacked_couple(
                                    depth,
                                    text_r,
                                    block_sweep,
                                    child_label=block_child_label,
                                    spouse_label=block_spouse,
                                    target_size=name_target,
                                    minimum_size=name_minimum,
                                    max_width=text_width,
                                )
                                if stack_size is not None:
                                    child_offset, spouse_offset = _couple_line_offsets(
                                        block_mid_angle,
                                        stack_size * 0.62,
                                    )
                                    for content, offset in (
                                        (block_child_label, child_offset),
                                        (f"\u00d7 {block_spouse}", spouse_offset),
                                    ):
                                        if not content:
                                            continue
                                        tx, ty = _tangent_offset(
                                            base_x, base_y, block_mid_angle, offset
                                        )
                                        if not measure_only:
                                            all_children.append(SceneText(
                                                x=tx,
                                                y=ty,
                                                content=content,
                                                font_size=stack_size,
                                                fill=TEXT_DARK,
                                                anchor="middle",
                                                rotation=rotation,
                                                max_width=text_width,
                                            ))
                                else:
                                    couple_fit, couple_size, couple_width = _fit_generation_couple(
                                        block_child_label,
                                        block_spouse,
                                        depth,
                                        target_size=name_target,
                                        minimum_size=name_minimum,
                                        max_width=text_width,
                                    )
                                    if couple_fit:
                                        if not measure_only:
                                            all_children.append(SceneText(
                                                x=base_x,
                                                y=base_y,
                                                content=couple_fit,
                                                font_size=couple_size,
                                                fill=TEXT_DARK,
                                                anchor="middle",
                                                rotation=rotation,
                                                max_width=couple_width,
                                            ))
                            else:
                                couple_fit, couple_size, couple_width = _fit_generation_couple(
                                    block_child_label,
                                    block_spouse,
                                    depth,
                                    target_size=name_target,
                                    minimum_size=name_minimum,
                                    max_width=text_width,
                                )
                                if couple_fit:
                                    if not measure_only:
                                        all_children.append(SceneText(
                                            x=base_x,
                                            y=base_y,
                                            content=couple_fit,
                                            font_size=couple_size,
                                            fill=TEXT_DARK,
                                            anchor="middle",
                                            rotation=rotation,
                                            max_width=couple_width,
                                        ))
                    else:
                        fitted_name, name_size, name_width = _fit_generation_name(
                            block_child_label,
                            depth,
                            target_size=name_target,
                            minimum_size=name_minimum,
                            max_width=text_width,
                        )
                        date_target = _generation_date_size(depth, name_size)
                        date_fit, date_size, date_width = _fit_text_to_width(
                            child_dates,
                            target_size=date_target,
                            minimum_size=date_target,
                            max_width=text_width,
                            allow_ellipsis=False,
                        )
                        show_date_lane = bool(
                            date_fit
                            and date_target > 0.0
                            and angular_capacity >= (name_size + date_size) * 1.18
                        )
                        lane_offset = max(name_size, date_size) * 0.58 if show_date_lane else 0.0
                        if fitted_name:
                            name_x, name_y = _tangent_offset(
                                base_x, base_y, block_mid_angle, -lane_offset
                            )
                            if not measure_only:
                                all_children.append(SceneText(
                                    x=name_x,
                                    y=name_y,
                                    content=fitted_name,
                                    font_size=name_size,
                                    fill=TEXT_DARK,
                                    anchor="middle",
                                    rotation=rotation,
                                    max_width=name_width,
                                ))
                        if show_date_lane:
                            date_x, date_y = _tangent_offset(
                                base_x, base_y, block_mid_angle, lane_offset
                            )
                            if not measure_only:
                                all_children.append(SceneText(
                                    x=date_x,
                                    y=date_y,
                                    content=date_fit,
                                    font_size=_generation_date_size(depth, name_size),
                                    fill=TEXT_GREY,
                                    anchor="middle",
                                    rotation=rotation,
                                    max_width=date_width,
                                ))

                if union_cells:
                    for cell in union_cells:
                        cell_child_label, entry = _union_cell_content(cell.union_index)
                        _render_intermediate_block(
                            cell.start_angle + cell.sweep_angle / 2.0,
                            cell.sweep_angle,
                            cell_child_label,
                            entry[2] if entry else "",
                        )
                else:
                    _render_intermediate_block(
                        mid_angle,
                        alloc_sweep,
                        child_label,
                        spouse_display_name,
                    )
        elif child_label:
            if depth == 1:
                # Keep direct-child labels outside the opaque center node;
                # cap the clearance so compact paper sizes stay in the ring.
                label_r = max(
                    gen_inner + ring_width * 0.50,
                    canvas.center_radius_mm
                    + min(
                        _DESCENDANT_FIRST_GEN_LINE_GAP_MM,
                        max(gen_outer - canvas.center_radius_mm, 0.0) * 0.50,
                    ),
                )
                font_size = outer_r * (12 / 600)
                label_font_capacity = None
                if med_border_r > 0.5:
                    medallion_radial_extent = (
                        math.hypot(med_r_pos, pair_offset)
                        + med_border_r * 1.1
                    )
                    label_font_capacity = max(
                        0.0,
                        gen_outer
                        - _RING_GAP_MM
                        - _MEDALLION_EDGE_CLEARANCE_MM
                        - medallion_radial_extent,
                    )
                    font_size = max(
                        font_size,
                        min(4.0, label_font_capacity),
                    )
                    label_r = max(
                        label_r,
                        medallion_radial_extent
                        + _MEDALLION_EDGE_CLEARANCE_MM
                        + font_size * 0.50,
                    )
                    label_r = min(
                        label_r,
                        gen_outer - _RING_GAP_MM - font_size * 0.50,
                    )
                radial_text_capacity = max(
                    0.0,
                    2.0
                    * min(
                        label_r - canvas.center_radius_mm,
                        gen_outer - label_r,
                    )
                    - 2.0 * _RING_GAP_MM,
                )
                couple_minimum_size = min(4.0, radial_text_capacity)
                if label_font_capacity is not None:
                    couple_minimum_size = min(
                        couple_minimum_size,
                        label_font_capacity,
                    )
                child_dates = (
                    _date_label(branch.person.handle)
                    if dates_lookup is not None and branch.person
                    else ""
                )
                if union_cells:
                    cell_specs = []
                    for cell in union_cells:
                        cell_child_label, entry = _union_cell_content(cell.union_index)
                        cell_specs.append((
                            cell.start_angle,
                            cell.sweep_angle,
                            entry,
                            cell_child_label,
                        ))
                else:
                    cell_specs = [(alloc_start, alloc_sweep, None, child_label)]
                for cell_start, cell_sweep, cell_entry, cell_child_label in cell_specs:
                    cell_spouse = (
                        cell_entry[2]
                        if cell_entry
                        else ("" if union_cells else spouse_display_name)
                    )
                    couple_label = (
                        f"{cell_child_label} × {cell_spouse}"
                        if cell_spouse
                        else cell_child_label
                    )
                    couple_width = max(
                        0.0,
                        label_r
                        * math.radians(max(cell_sweep - 1.0, 0.0))
                        - 2.0,
                    )
                    if cell_spouse:
                        fitted_couple, fitted_size, fitted_width = _fit_generation_couple(
                            cell_child_label,
                            cell_spouse,
                            depth,
                            target_size=font_size,
                            minimum_size=couple_minimum_size,
                            max_width=couple_width,
                        )
                    else:
                        fitted_couple, fitted_size, fitted_width = _fit_generation_name(
                            cell_child_label,
                            depth,
                            target_size=font_size,
                            minimum_size=couple_minimum_size,
                            max_width=couple_width,
                        )
                    if not measure_only:
                        all_children.append(ScenePathText(
                            path=_arc_text_path(
                                cx, cy, label_r,
                                cell_start, cell_start + cell_sweep,
                                lower=True,
                            ),
                            content=fitted_couple,
                            font_size=fitted_size,
                            fill=TEXT_DARK,
                            max_width=fitted_width,
                        ))
                    generation_date_size = _generation_date_size(depth, fitted_size)
                    if (
                        child_dates
                        and not measure_only
                        and generation_date_size > 0.0
                    ):
                        date_radius = gen_inner + ring_width * 0.68
                        all_children.append(ScenePathText(
                            path=_arc_text_path(
                                cx,
                                cy,
                                date_radius,
                                cell_start, cell_start + cell_sweep,
                                lower=True,
                            ),
                            content=child_dates,
                            font_size=generation_date_size,
                            fill=TEXT_GREY,
                            max_width=_ancestor_arc_text_capacity(
                                text_radius=date_radius,
                                sweep_angle=cell_sweep,
                            ),
                        ))
                    if cell_spouse:
                        spouse_dates = ""
                        if dates_lookup is not None:
                            if cell_entry:
                                date_label = _date_label(cell_entry[0])
                                spouse_dates = date_label
                            elif not union_cells:
                                spouse_date_parts = [
                                    _date_label(handle)
                                    for handle, _raw, _short_name in spouse_entries
                                ]
                                spouse_dates = " / ".join(
                                    date for date in spouse_date_parts if date
                                )
                        if (
                            spouse_dates
                            and not measure_only
                            and generation_date_size > 0.0
                        ):
                            spouse_date_radius = gen_inner + ring_width * 0.84
                            all_children.append(ScenePathText(
                                path=_arc_text_path(
                                    cx,
                                    cy,
                                    spouse_date_radius,
                                    cell_start, cell_start + cell_sweep,
                                    lower=True,
                                ),
                                content=spouse_dates,
                                font_size=generation_date_size,
                                fill=TEXT_GREY,
                                max_width=_ancestor_arc_text_capacity(
                                    text_radius=spouse_date_radius,
                                    sweep_angle=cell_sweep,
                                ),
                            ))

        # Place children within the allocated sweep. Reuse the same deep-demand
        # allocator as the capacity pass so geometry and rendering stay aligned.
        if branch.children:
            union_allocations = _allocate_descendant_union_groups(
                branch,
                start_angle=alloc_start,
                total_sweep=alloc_sweep,
                include_empty=True,
            )
            for union_allocation in union_allocations:
                if len(branch.unions) > 1:
                    child_fill_index = _stable_union_fill_index(
                        branch,
                        union_allocation.union_index,
                    )
                else:
                    child_fill_index = inherited_fill_index
                child_allocs = _allocate_descendant_branches_by_demand(
                    union_allocation.children,
                    start_angle=union_allocation.start_angle,
                    total_sweep=union_allocation.sweep_angle,
                )
                for child, child_alloc in zip(
                    union_allocation.children,
                    child_allocs,
                ):
                    _place_branch(
                        child,
                        child_alloc.start_angle,
                        child_alloc.sweep_angle,
                        depth + 1,
                        branch_index,
                        child_fill_index,
                    )

            # Union boundaries and the couple labels already identify each
            # marriage cell. Do not repeat the family Gramps ID and spouse
            # name in a second header lane below the child ring.

        # The extraction deliberately keeps the child handles of the final
        # displayed generation even though their branches are not materialized.
        # Use that metadata to signal that the visible descendant continues.
        # Multi-union people get one marker per union cell, so a continuation
        # cannot be mistaken for a neighboring spouse's branch.
        if depth == displayed_generation_limit:
            if union_cells:
                for cell in union_cells:
                    if (
                        0 <= cell.union_index < len(branch.unions)
                        and branch.unions[cell.union_index].child_handles
                    ):
                        _emit_continuation_dots(
                            cell.start_angle,
                            cell.sweep_angle,
                            gen_outer,
                        )
            elif (
                len(branch.unions) == 1
                and branch.unions[0].child_handles
            ):
                _emit_continuation_dots(
                    alloc_start,
                    alloc_sweep,
                    gen_outer,
                )

    # Measure every name once so the smallest fitting size becomes the
    # generation-wide contract. The second pass then renders all names in that
    # generation with the same font size; the renderer may still apply the
    # physical width constraint without changing the hierarchy.
    _reserve_fill_indices_by_depth()
    for bi, (branch, alloc) in enumerate(zip(branches, allocations)):
        _place_branch(branch, alloc.start_angle, alloc.sweep_angle, 1, bi)
    generation_name_sizes = {
        depth: min(sizes)
        for depth, sizes in name_size_candidates.items()
        if sizes
    }
    generation_date_sizes = {
        depth: _date_font_size(name_size)
        for depth, name_size in generation_name_sizes.items()
    }
    measure_only = False
    all_children = []
    for bi, (branch, alloc) in enumerate(zip(branches, allocations)):
        _place_branch(branch, alloc.start_angle, alloc.sweep_angle, 1, bi)

    # The SVG backend renders circular arc labels as ordinary text at the arc
    # midpoint. Keep those labels above later-generation sectors: otherwise a
    # child ring can paint over the tangent ends of a first-generation label on
    # compact pages, making a complete identity look truncated.
    arc_labels = [node for node in all_children if isinstance(node, ScenePathText)]
    scene_geometry = [node for node in all_children if not isinstance(node, ScenePathText)]
    return SceneNode(children=tuple(scene_geometry + arc_labels))