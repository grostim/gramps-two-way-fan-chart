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
        SceneLegend,
        SceneNode,
        SceneRect,
        SceneSector,
        SceneText,
        ScenePathText,
    )
    from TwoWayFanChart.styles import (
        ancestor_fill,
        descendant_fill,
        MEDALLION_BORDER,
        MEDALLION_FILL,
        HIDDEN_FILL,
        TEXT_DARK,
        TEXT_GREY,
        SECTOR_STROKE,
        SECTOR_STROKE_WIDTH,
    )
except ModuleNotFoundError:
    from geometry import PaperRegion, polar_to_cartesian, deg2rad  # type: ignore[no-redef]
    from model import (  # type: ignore[no-redef]
        DescendantBranch,
        SceneCircle,
        SceneImage,
        SceneLegend,
        SceneNode,
        SceneRect,
        SceneSector,
        SceneText,
        ScenePathText,
    )
    from styles import (  # type: ignore[no-redef]
        ancestor_fill,
        descendant_fill,
        MEDALLION_BORDER,
        MEDALLION_FILL,
        HIDDEN_FILL,
        TEXT_DARK,
        TEXT_GREY,
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
    available radius, and ancestor/descendant rings share the remaining depth
    equally so both halves reach the same outer radius.
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

    # Each half-fan independently uses the complete radial depth. Ancestor and
    # descendant generations occupy different angular halves, so dividing the
    # depth by their combined generation count would shrink both fans.
    ancestor_outer = max_radius if ancestor_generations > 0 else center_radius
    descendant_outer = max_radius if descendant_generations > 0 else center_radius

    cx = paper.effective_margin_left_mm + content_w / 2
    cy = paper.effective_margin_top_mm + content_h / 2

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


def _radial_rotation(deg: float) -> float:
    """Compute rotation angle for radial text so it stays upright.

    Mirrors the mockup's radial_rotation(): angles in the bottom half
    (90°–270°) are flipped by 180° so text reads top-to-bottom.
    """
    rot = deg
    normalized = rot % 360
    if 90 < normalized < 270:
        rot += 180
    return rot


# ---------------------------------------------------------------------------
# Ancestor fan placement
# ---------------------------------------------------------------------------

_ANCESTOR_HALF_SPAN_DEG = 86.0  # mockup: 172° total, 4° waist gap per side


def layout_ancestors(
    canvas: ChartCanvas,
    ancestor_slots: tuple[tuple, ...],
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
    """
    if not ancestor_slots:
        return SceneNode(children=())

    cx = canvas.center_cx_mm
    cy = canvas.center_cy_mm
    inner_r = canvas.ancestor_inner_radius_mm
    outer_r = canvas.ancestor_outer_radius_mm

    # Parse all slots to get
    # (pid, lineage, generation, label, dates_label, portrait_data_uri).
    parsed: list[tuple[str, str, int, str, str, str | None]] = []
    for entry in ancestor_slots:
        if len(entry) >= 4:
            pid, label, dates_label, portrait = (
                entry[0], entry[1], entry[2], entry[3]
            )
        elif len(entry) == 3:
            pid, label, dates_label = entry[0], entry[1], entry[2]
            portrait = None
        elif len(entry) >= 2:
            # Backward-compatible 2-tuple (position_id, label)
            pid, label = entry[0], entry[1]
            dates_label = ""
            portrait = None
        else:
            continue
        info = _parse_position_id(pid)
        if info:
            lineage, gen = info
        else:
            # Fallback: determine from position in list
            lineage = "a"
            gen = 1
        parsed.append((pid, lineage, gen, label, dates_label, portrait))

    # Determine actual generations present
    max_gen = max(g for _, _, g, _, _, _ in parsed) if parsed else 1
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
    for pid, lineage, gen, label, _dates, _portrait in parsed:
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
            (pid, lin, lbl, dt, portrait)
            for pid, lin, g, lbl, dt, portrait in parsed
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

        # Place lineage a (paternal, left side: -90° to 0°)
        for i, (pid, _, label, dates_label, portrait) in enumerate(slots_a):
            start_angle = -_ANCESTOR_HALF_SPAN_DEG + i * sweep_a
            _emit_ancestor_sector(
                children, cx, cy, gen_inner, gen_outer,
                start_angle, sweep_a, outer_r,
                gen, "a", label, dates_label, portrait,
            )

        # Place lineage b (maternal, right side: 0° to 90°)
        for i, (pid, _, label, dates_label, portrait) in enumerate(slots_b):
            start_angle = 0.0 + i * sweep_b
            _emit_ancestor_sector(
                children, cx, cy, gen_inner, gen_outer,
                start_angle, sweep_b, outer_r,
                gen, "b", label, dates_label, portrait,
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

    # For narrow sectors (< 15°), use radial rotated text instead of arc text
    use_radial = sweep < 15.0
    # Exact mockup radii and type scale, normalized against its 600 px fan.
    name_ratios = {1: 285 / 600, 2: 397 / 600, 3: 538 / 600}
    life_ratios = {1: 304 / 600, 2: 417 / 600, 3: 558 / 600}
    portrait_ratios = {1: 250 / 600, 2: 355 / 600, 3: 485 / 600}
    portrait_size_ratios = {1: 24 / 600, 2: 20 / 600, 3: 15 / 600}
    name_size_ratios = {1: 12 / 600, 2: 12 / 600, 3: 10.5 / 600}
    life_size_ratios = {1: 9.5 / 600, 2: 9.5 / 600, 3: 8.5 / 600}

    name_r = name_ratios.get(
        gen, inner_r / fan_outer_r + 0.62 * (outer_r - inner_r) / fan_outer_r
    ) * fan_outer_r
    font_size = name_size_ratios.get(gen, 10 / 600) * fan_outer_r

    if use_radial:
        # Radial rotated text (like the mockup's radial_label)
        tx, ty = _polar(cx, cy, name_r, mid_angle)
        rot = _radial_rotation(mid_angle)
        children.append(SceneText(
            x=tx, y=ty,
            content=label,
            font_size=font_size,
            fill=TEXT_DARK,
            anchor="middle",
            rotation=rot,
        ))
    else:
        path = _arc_text_path(cx, cy, name_r, start_angle, end_angle, lower=False)
        children.append(ScenePathText(
            path=path,
            content=label,
            font_size=font_size,
            fill=TEXT_DARK,
        ))

    # Curved life-dates label — placed at 82% of ring depth (below the name).
    if dates_label:
        life_r = life_ratios.get(
            gen, inner_r / fan_outer_r + 0.82 * (outer_r - inner_r) / fan_outer_r
        ) * fan_outer_r
        life_font = life_size_ratios.get(gen, 8.5 / 600) * fan_outer_r
        if use_radial:
            ltx, lty = _polar(cx, cy, life_r, mid_angle)
            lrot = _radial_rotation(mid_angle)
            children.append(SceneText(
                x=ltx, y=lty,
                content=dates_label,
                font_size=life_font,
                fill=TEXT_GREY,
                anchor="middle",
                rotation=lrot,
            ))
        else:
            life_path = _arc_text_path(cx, cy, life_r, start_angle, end_angle, lower=False)
            children.append(ScenePathText(
                path=life_path,
                content=dates_label,
                font_size=life_font,
                fill=TEXT_GREY,
            ))

    # Portrait/fallback medallion at the mockup's generation-specific radius.
    image_r = portrait_size_ratios.get(gen, 15 / 600) * fan_outer_r
    med_r = image_r * (26 / 24) if portrait else image_r
    if med_r > 0.5:
        med_r_pos = portrait_ratios.get(
            gen, inner_r / fan_outer_r + 0.30 * (outer_r - inner_r) / fan_outer_r
        ) * fan_outer_r
        mx, my = _polar(cx, cy, med_r_pos, mid_angle)
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
                r=image_r,
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


# ---------------------------------------------------------------------------
# Center couple placement
# ---------------------------------------------------------------------------

_LABEL_FILL = TEXT_DARK
_STATS_FILL = TEXT_GREY


def layout_center(
    canvas: ChartCanvas,
    *,
    left_label: str,
    right_label: str | None = None,
    left_portrait: str | None = None,
    right_portrait: str | None = None,
    left_fallback: str = "",
    right_fallback: str = "",
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

        # "&" symbol between the two medallions (mockup uses clay color)
        children.append(SceneText(
            x=cx, y=med_cy + med_r * 0.20,
            content="&",
            font_size=r * (28.0 / 190.0),
            fill="#D97757",
            anchor="middle",
        ))

        # Combined name below the medallions
        combined = f"{left_label} & {right_label}"
        children.append(SceneText(
            x=cx, y=cy + r * (48.0 / 190.0),
            content=combined,
            font_size=r * (23.0 / 190.0),
            fill=_LABEL_FILL,
            anchor="middle",
            font_weight="500",
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
        children.append(SceneText(
            x=cx, y=cy + r * (48.0 / 190.0),
            content=left_label,
            font_size=r * (23.0 / 190.0),
            fill=_LABEL_FILL,
            anchor="middle",
            font_weight="500",
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
    outer_r = max(canvas.ancestor_outer_radius_mm, canvas.descendant_outer_radius_mm)

    children: list = []

    if ancestor_generations > 0:
        # Title above the top arc
        title_y = cy - outer_r - 4
        title_text = f"ASCENDANTS · {ancestor_generations} GÉNÉRATIONS"
        children.append(SceneText(
            x=cx, y=title_y,
            content=title_text,
            font_size=5.0,
            fill=TEXT_GREY,
            anchor="middle",
        ))

    if descendant_generations > 0:
        # Title below the bottom arc
        title_y = cy + outer_r + 8
        title_text = f"DESCENDANTS · {descendant_generations} GÉNÉRATIONS"
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


def _count_leaves(branch: DescendantBranch) -> int:
    """Count the total leaf nodes in a descendant branch tree."""
    if not branch.children:
        return 1
    return sum(_count_leaves(child) for child in branch.children)


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


def layout_descendants(
    canvas: ChartCanvas,
    branches: tuple[DescendantBranch, ...],
    *,
    name_lookup,
    dates_lookup=None,
    shortener=None,
    portrait_lookup=None,
) -> SceneNode:
    """Place all descendant medallions in the lower half-circle.

    Generates:
    - Colored annular sectors for each child branch
    - Sub-sectors for grandchildren
    - Curved text labels for children (shortened via *shortener*)
    - A second curved arc with the spouse name prefixed by ``×``
    - Medallions at the midpoint of each sector
    - Straight text for grandchildren
    """
    if not branches:
        return SceneNode(children=())

    # Match the publication mockup at the first generation: reserve a readable
    # base angle for every child and widen only branches with many children.
    child_counts = [len(branch.children) for branch in branches]
    allocations = _allocate_publication_branches(
        child_counts,
        start_angle=_DESC_START_ANGLE,
        total_sweep=_DESC_TOTAL_SWEEP,
    )

    all_children: list = []
    inner_r = canvas.descendant_inner_radius_mm
    outer_r = canvas.descendant_outer_radius_mm
    max_gen = max(_max_desc_depth(b) for b in branches) if branches else 1
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

    def _short(label: str, depth: int) -> str:
        if shortener is None or not label:
            return label
        try:
            return shortener(label, depth)
        except Exception:
            return label

    def _portrait(handle: str | None) -> str | None:
        if portrait_lookup is None or not handle:
            return None
        try:
            return portrait_lookup(handle)
        except Exception:
            return None

    def _emit_medallion(
        x: float,
        y: float,
        radius: float,
        label: str,
        portrait: str | None,
    ) -> None:
        all_children.append(SceneCircle(
            cx=x,
            cy=y,
            r=radius * (1.1 if portrait else 1.0),
            fill=MEDALLION_FILL,
            stroke=MEDALLION_BORDER,
            stroke_width=0.3,
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

    def _place_branch(
        branch: DescendantBranch,
        alloc_start: float,
        alloc_sweep: float,
        depth: int,
        branch_index: int,
    ) -> None:
        """Recursively place a branch and its children."""
        mid_angle = alloc_start + alloc_sweep / 2.0

        if max_gen == 2 and depth <= 2:
            exact_inner_ratios = (202 / 600, 355 / 600)
            exact_outer_ratios = (350 / 600, 598 / 600)
            gen_inner = outer_r * exact_inner_ratios[depth - 1]
            gen_outer = outer_r * exact_outer_ratios[depth - 1]
            ring_width = gen_outer - gen_inner
        else:
            gen_inner = inner_r + sum(ring_widths[: depth - 1])
            ring_width = ring_widths[min(depth - 1, len(ring_widths) - 1)]
            gen_outer = gen_inner + ring_width - _RING_GAP_MM

        # Emit sector for this branch
        fill = descendant_fill(branch_index)
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

        raw_label = _descendant_label(branch, name_lookup)
        child_label = _short(raw_label, depth)

        spouse_handle: str | None = None
        spouse_name: str | None = None
        spouse_medallion_label: str | None = None
        if depth == 1:
            for union in branch.unions:
                if union.spouse_handle:
                    sp_raw = _spouse_label(union, name_lookup)
                    if sp_raw:
                        spouse_handle = union.spouse_handle
                        spouse_medallion_label = sp_raw
                        spouse_name = _short(sp_raw, depth)
                        break

        if raw_label == "Personne privée" and spouse_medallion_label == "Personne privée":
            child_label = "Personnes privées"
            spouse_name = None

        # Place one portrait medallion, or a tangent child/spouse pair like
        # the reference mockup's first descendant ring.
        med_r = outer_r * ((20 / 600) if depth == 1 else (14 / 600))
        if med_r > 0.5:
            med_r_pos = outer_r * ((245 / 600) if depth == 1 else (397 / 600))
            mx, my = _polar(cx, cy, med_r_pos, mid_angle)
            if spouse_handle and spouse_medallion_label:
                angle_rad = math.radians(mid_angle)
                tangent_x = math.cos(angle_rad)
                tangent_y = math.sin(angle_rad)
                pair_offset = outer_r * (20 / 600)
                _emit_medallion(
                    mx - tangent_x * pair_offset,
                    my - tangent_y * pair_offset,
                    med_r,
                    child_label or raw_label,
                    _portrait(branch.person.handle if branch.person else None),
                )
                _emit_medallion(
                    mx + tangent_x * pair_offset,
                    my + tangent_y * pair_offset,
                    med_r,
                    spouse_medallion_label,
                    _portrait(spouse_handle),
                )
            else:
                _emit_medallion(
                    mx,
                    my,
                    med_r,
                    child_label or raw_label,
                    _portrait(branch.person.handle if branch.person else None),
                )

        # Curved label for depth 1 (children), straight for deeper
        if child_label:
            if depth == 1:
                label_r = outer_r * (290 / 600)
                font_size = outer_r * (12 / 600)
                path = _arc_text_path(
                    cx, cy, label_r,
                    alloc_start, alloc_start + alloc_sweep,
                    lower=True,
                )
                all_children.append(ScenePathText(
                    path=path,
                    content=child_label,
                    font_size=font_size,
                    fill=TEXT_DARK,
                ))

                # Spouse label as a second curved arc, prefixed with "×".
                # Placed slightly below (larger radius) the child's name.
                if spouse_name:
                    spouse_r = outer_r * (315 / 600)
                    spouse_path = _arc_text_path(
                        cx, cy, spouse_r,
                        alloc_start, alloc_start + alloc_sweep,
                        lower=True,
                    )
                    all_children.append(ScenePathText(
                        path=spouse_path,
                        content=f"× {spouse_name}",
                        font_size=font_size,
                        fill=TEXT_GREY,
                    ))

                dates_label = (
                    dates_lookup(branch.person.handle)
                    if dates_lookup is not None and branch.person
                    else ""
                )
                child_count = len(branch.children)
                metadata = (
                    f"{dates_label} · {child_count} enfant(s)"
                    if dates_label
                    else f"{child_count} enfant(s)"
                )
                metadata_path = _arc_text_path(
                    cx,
                    cy,
                    outer_r * (338 / 600),
                    alloc_start,
                    alloc_start + alloc_sweep,
                    lower=True,
                )
                all_children.append(ScenePathText(
                    path=metadata_path,
                    content=metadata,
                    font_size=outer_r * (9.5 / 600),
                    fill=TEXT_GREY,
                ))
            else:
                # Grandchildren in the mockup use radial labels, not horizontal text.
                text_r = outer_r * (487 / 600)
                tx, ty = _polar(cx, cy, text_r, mid_angle)
                rot = _radial_rotation(mid_angle)
                font_size = outer_r * (10.5 / 600)
                all_children.append(SceneText(
                    x=tx, y=ty,
                    content=child_label,
                    font_size=font_size,
                    fill=TEXT_DARK,
                    anchor="middle",
                    rotation=rot,
                ))

                # Grandchild life dates below the name when available.
                if dates_lookup is not None and branch.person:
                    dates_label = dates_lookup(branch.person.handle)
                    if dates_label:
                        dt_r = outer_r * (568 / 600)
                        dx, dy = _polar(cx, cy, dt_r, mid_angle)
                        all_children.append(SceneText(
                            x=dx, y=dy,
                            content=dates_label,
                            font_size=outer_r * (8.5 / 600),
                            fill=TEXT_GREY,
                            anchor="middle",
                            rotation=rot,
                        ))

        # Place children within the allocated sweep
        if branch.children:
            child_leaves = [_count_leaves(c) for c in branch.children]
            child_allocs = allocate_descendant_branches(
                canvas,
                leaf_counts=child_leaves,
                start_angle=alloc_start,
                total_sweep=alloc_sweep,
            )
            for child, child_alloc in zip(branch.children, child_allocs):
                _place_branch(
                    child,
                    child_alloc.start_angle,
                    child_alloc.sweep_angle,
                    depth + 1,
                    branch_index,
                )

    for bi, (branch, alloc) in enumerate(zip(branches, allocations)):
        _place_branch(branch, alloc.start_angle, alloc.sweep_angle, 1, bi)

    return SceneNode(children=tuple(all_children))