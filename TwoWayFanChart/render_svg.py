# SPDX-License-Identifier: GPL-3.0-or-later
"""Standalone SVG renderer for the two-way fan chart scene model."""

from __future__ import annotations

import math
import re
from xml.sax.saxutils import escape as _xml_escape

try:
    from TwoWayFanChart.geometry import arc_path, mm_to_pt, AnnularSector
    from TwoWayFanChart.model import (
        SceneCircle,
        SceneImage,
        SceneMarker,
        SceneLegend,
        SceneNode,
        ScenePage,
        ScenePathText,
        SceneRect,
        SceneSector,
        SceneText,
        estimate_text_width,
    )
except ModuleNotFoundError:
    from geometry import arc_path, mm_to_pt, AnnularSector
    from model import (
        SceneCircle,
        SceneImage,
        SceneMarker,
        SceneLegend,
        SceneNode,
        ScenePage,
        ScenePathText,
        SceneRect,
        SceneSector,
        SceneText,
        estimate_text_width,
    )

_SVG_NS = "http://www.w3.org/2000/svg"
_XLINK_NS = "http://www.w3.org/1999/xlink"


def xml_escape(text: str) -> str:
    """Escape XML special characters for safe inclusion in SVG."""
    return _xml_escape(text, {'"': "&quot;"})


def _fmt(value: float) -> str:
    """Format a float for SVG, trimming unnecessary precision."""
    return f"{value:.4f}".rstrip("0").rstrip(".")


_ARC_PATH_RE = re.compile(
    r"^\s*M\s+"
    r"(?P<x0>[-+]?(?:\d+(?:\.\d*)?|\.\d+))\s+"
    r"(?P<y0>[-+]?(?:\d+(?:\.\d*)?|\.\d+))\s+"
    r"A\s+"
    r"(?P<rx>[-+]?(?:\d+(?:\.\d*)?|\.\d+))\s+"
    r"(?P<ry>[-+]?(?:\d+(?:\.\d*)?|\.\d+))\s+"
    r"(?P<rotation>[-+]?(?:\d+(?:\.\d*)?|\.\d+))\s+"
    r"(?P<large>[01])\s+"
    r"(?P<sweep>[01])\s+"
    r"(?P<x1>[-+]?(?:\d+(?:\.\d*)?|\.\d+))\s+"
    r"(?P<y1>[-+]?(?:\d+(?:\.\d*)?|\.\d+))\s*$"
)


def _upright_rotation(angle: float) -> float:
    """Keep a baseline tangent readable from left to right."""
    rotation = angle % 360.0
    if rotation > 180.0:
        rotation -= 360.0
    while rotation > 90.0:
        rotation -= 180.0
    while rotation <= -90.0:
        rotation += 180.0
    return rotation


def _arc_text_anchor(path: str) -> tuple[float, float, float] | None:
    """Return ``(x, y, rotation)`` for a generated circular arc path.

    The production layout emits one ``M … A …`` circular arc per
    ``ScenePathText``.  librsvg renders ordinary SVG text but ignores
    ``textPath``; this converts that known path form to an equivalent,
    renderer-portable vector text placement.  Unknown path syntax keeps the
    historical textPath fallback rather than guessing a position.
    """
    match = _ARC_PATH_RE.fullmatch(path)
    if match is None:
        return None
    values = {key: float(value) for key, value in match.groupdict().items() if key not in {"large", "sweep"}}
    x0, y0 = values["x0"], values["y0"]
    x1, y1 = values["x1"], values["y1"]
    radius_x, radius_y = values["rx"], values["ry"]
    large = bool(int(match.group("large")))
    sweep = bool(int(match.group("sweep")))
    if radius_x <= 0.0 or abs(radius_x - radius_y) > 1e-6:
        return None
    radius = radius_x
    chord = math.hypot(x1 - x0, y1 - y0)
    if chord <= 1e-9 or chord > 2.0 * radius + 1e-6:
        return None

    midpoint_x = (x0 + x1) / 2.0
    midpoint_y = (y0 + y1) / 2.0
    height = math.sqrt(max(0.0, radius * radius - (chord / 2.0) ** 2))
    normal_x = -(y1 - y0) / chord
    normal_y = (x1 - x0) / chord

    for sign in (-1.0, 1.0):
        cx = midpoint_x + sign * height * normal_x
        cy = midpoint_y + sign * height * normal_y
        start = math.atan2(y0 - cy, x0 - cx)
        end = math.atan2(y1 - cy, x1 - cx)
        if sweep:
            delta = (end - start) % (2.0 * math.pi)
            tangent = start + delta / 2.0 + math.pi / 2.0
        else:
            delta = -((start - end) % (2.0 * math.pi))
            tangent = start + delta / 2.0 - math.pi / 2.0
        if (abs(delta) > math.pi) != large:
            continue
        angle = start + delta / 2.0
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        return x, y, _upright_rotation(math.degrees(tangent))
    return None


def _render_sector(sector: SceneSector) -> str:
    """Render an annular sector as an SVG path."""
    annular = AnnularSector(
        inner_radius=sector.inner_radius,
        outer_radius=sector.outer_radius,
        start_angle=sector.start_angle,
        sweep_angle=sector.sweep_angle,
        cx=sector.cx,
        cy=sector.cy,
    )
    path = arc_path(annular)
    attrs = [f'd="{path}"']
    if sector.fill:
        attrs.append(f'fill="{sector.fill}"')
    else:
        attrs.append('fill="none"')
    if sector.stroke:
        attrs.append(f'stroke="{sector.stroke}"')
        sw = sector.stroke_width if sector.stroke_width is not None else 0.5
        attrs.append(f'stroke-width="{_fmt(sw)}"')
    return f"<path {' '.join(attrs)} />"


def _render_circle(circle: SceneCircle) -> str:
    """Render a circle element."""
    attrs = [
        f'cx="{_fmt(circle.cx)}"',
        f'cy="{_fmt(circle.cy)}"',
        f'r="{_fmt(circle.r)}"',
    ]
    if circle.fill:
        attrs.append(f'fill="{circle.fill}"')
    else:
        attrs.append('fill="none"')
    if circle.stroke:
        attrs.append(f'stroke="{circle.stroke}"')
        sw = circle.stroke_width if circle.stroke_width is not None else 0.5
        attrs.append(f'stroke-width="{_fmt(sw)}"')
    return f"<circle {' '.join(attrs)} />"


def _render_text(text: SceneText) -> str:
    """Render a text element with proper escaping."""
    attrs = [
        f'x="{_fmt(text.x)}"',
        f'y="{_fmt(text.y)}"',
        f'font-size="{_fmt(text.font_size)}"',
        f'fill="{text.fill}"',
    ]
    if text.anchor:
        attrs.append(f'text-anchor="{text.anchor}"')
    if text.font_weight:
        attrs.append(f'font-weight="{text.font_weight}"')
    if text.rotation is not None:
        attrs.append(
            f'transform="rotate({_fmt(text.rotation)} {_fmt(text.x)} {_fmt(text.y)})"'
        )
    if text.max_width is not None and text.max_width > 0:
        fitted_width = min(
            estimate_text_width(text.content, text.font_size),
            text.max_width,
        )
        attrs.append(f'textLength="{_fmt(fitted_width)}"')
        attrs.append('lengthAdjust="spacingAndGlyphs"')
    content = xml_escape(text.content)
    return f"<text {' '.join(attrs)}>{content}</text>"


def _render_image(image: SceneImage) -> str:
    """Render a portrait image or fallback."""
    if image.data_uri:
        return (
            f'<clipPath id="clip-{id(image)}">'
            f'<circle cx="{_fmt(image.cx)}" cy="{_fmt(image.cy)}" r="{_fmt(image.r)}" />'
            f'</clipPath>'
            f'<image x="{_fmt(image.cx - image.r)}" y="{_fmt(image.cy - image.r)}" '
            f'width="{_fmt(image.r * 2)}" height="{_fmt(image.r * 2)}" '
            f'href="{image.data_uri}" clip-path="url(#clip-{id(image)})" />'
        )
    if image.fallback_text:
        return (
            f'<circle cx="{_fmt(image.cx)}" cy="{_fmt(image.cy)}" '
            f'r="{_fmt(image.r)}" fill="#F0EEE6" />'
            f'<text x="{_fmt(image.cx)}" y="{_fmt(image.cy + image.r * 0.25)}" '
            f'font-size="{_fmt(image.r * 0.5)}" fill="#87867F" '
            f'text-anchor="middle">{xml_escape(image.fallback_text)}</text>'
        )
    return ""



def _render_marker(marker: SceneMarker) -> str:
    """Render a diamond marker that remains distinct in grayscale."""
    r = marker.radius
    points = (
        (marker.cx, marker.cy - r),
        (marker.cx + r, marker.cy),
        (marker.cx, marker.cy + r),
        (marker.cx - r, marker.cy),
    )
    path = "M " + " L ".join(f"{_fmt(x)} {_fmt(y)}" for x, y in points) + " Z"
    fill = marker.fill if marker.fill else "none"
    return (
        f'<path d="{path}" fill="{fill}" stroke="{marker.stroke}" '
        f'stroke-width="{_fmt(marker.stroke_width)}" '
        'stroke-linejoin="round" />'
    )


_path_text_counter = 0


def _render_path_text(pt: ScenePathText, _path_id: str) -> str:
    """Render an arc label as portable vector text.

    librsvg (the PDF/PNG converter used by the publication pipeline) ignores
    SVG ``textPath`` content. The production layout uses circular ``M … A``
    arcs, so place ordinary text at the arc midpoint and rotate it onto the
    local tangent instead. This preserves the complete label and works in
    librsvg, Cairo, and browsers without rasterizing the graph. Unexpected
    path syntax fails closed instead of emitting invisible text.
    """
    anchor = _arc_text_anchor(pt.path)
    if anchor is None:
        raise ValueError("ScenePathText requires a generated circular arc path")

    escaped = xml_escape(pt.content)
    x, y, rotation = anchor
    attrs = (
        f'x="{_fmt(x)}" y="{_fmt(y)}" '
        f'font-size="{_fmt(pt.font_size)}" fill="{pt.fill}" '
        'text-anchor="middle" dominant-baseline="middle" '
        f'transform="rotate({_fmt(rotation)} {_fmt(x)} {_fmt(y)})"'
    )
    if pt.max_width is not None and pt.max_width > 0:
        fitted_width = min(
            estimate_text_width(pt.content, pt.font_size),
            pt.max_width,
        )
        attrs += (
            f' textLength="{_fmt(fitted_width)}"'
            ' lengthAdjust="spacingAndGlyphs"'
        )
    return f'<text {attrs} data-arc-label="true">{escaped}</text>'


def _render_legend(legend: SceneLegend) -> str:
    """Render a legend block with background card, color circles and labels."""
    # Background card (white with border, like the mockup)
    card_w = 52.0
    card_h = 32.0
    parts = [
        f'<rect x="{_fmt(legend.x - 4)}" y="{_fmt(legend.y - 6)}" '
        f'width="{_fmt(card_w)}" height="{_fmt(card_h)}" '
        f'rx="3" fill="#FFFFFF" stroke="#D1CFC5" stroke-width="0.3" />',
        f'<text x="{_fmt(legend.x)}" y="{_fmt(legend.y)}" '
        f'font-size="4" fill="#87867F" font-weight="bold">LÉGENDE</text>'
    ]
    y = legend.y + 6
    for label, color in legend.items:
        parts.append(
            f'<circle cx="{_fmt(legend.x + 4)}" cy="{_fmt(y)}" '
            f'r="3" fill="{color}" stroke="#D1CFC5" stroke-width="0.3" />'
        )
        parts.append(
            f'<text x="{_fmt(legend.x + 10)}" y="{_fmt(y + 1)}" '
            f'font-size="3" fill="#3D3D3A">{xml_escape(label)}</text>'
        )
        y += 6
    return "\n".join(parts)


def _render_rect(rect) -> str:
    """Render a rectangle (background card)."""
    attrs = [
        f'x="{_fmt(rect.x)}"',
        f'y="{_fmt(rect.y)}"',
        f'width="{_fmt(rect.width)}"',
        f'height="{_fmt(rect.height)}"',
        f'rx="{_fmt(rect.rx)}"',
        f'fill="{rect.fill}"',
        f'stroke="{rect.stroke}"',
        f'stroke-width="{_fmt(rect.stroke_width)}"',
    ]
    return f"<rect {' '.join(attrs)} />"


def _render_child(child) -> str:
    """Render one scene primitive."""
    if isinstance(child, SceneSector):
        return _render_sector(child)
    if isinstance(child, SceneCircle):
        return _render_circle(child)
    if isinstance(child, SceneText):
        return _render_text(child)
    if isinstance(child, SceneImage):
        return _render_image(child)
    if isinstance(child, SceneMarker):
        return _render_marker(child)
    if isinstance(child, ScenePathText):
        global _path_text_counter
        _path_text_counter += 1
        return _render_path_text(child, f"arc-path-{_path_text_counter}")
    if isinstance(child, SceneLegend):
        return _render_legend(child)
    if isinstance(child, SceneNode):
        return "\n".join(_render_child(c) for c in child.children)
    if isinstance(child, SceneRect):
        return _render_rect(child)
    return ""


def render_svg(
    page: ScenePage,
    root_node: SceneNode,
    *,
    background_color: str = "#FAF9F5",
    title: str | None = None,
    description: str | None = None,
    metadata: dict[str, str] | None = None,
) -> str:
    """Render the scene model as a standalone SVG string."""
    parts = [
        f'<svg xmlns="{_SVG_NS}" '
        f'xmlns:xlink="{_XLINK_NS}" '
        f'width="{_fmt(page.width_mm)}mm" '
        f'height="{_fmt(page.height_mm)}mm" '
        f'viewBox="0 0 {_fmt(page.width_mm)} {_fmt(page.height_mm)}">'
    ]

    # Title and description for accessibility and metadata
    if title:
        parts.append(f"<title>{xml_escape(title)}</title>")
    if description:
        parts.append(f"<desc>{xml_escape(description)}</desc>")

    # Metadata as SVG comment
    if metadata:
        meta_lines = [f"  {k}: {v}" for k, v in metadata.items()]
        parts.append("<!--\n" + "\n".join(meta_lines) + "\n-->")

    # CSS styles for fonts
    parts.append(
        "<style>"
        "text { font-family: system-ui, -apple-system, 'Segoe UI', sans-serif; }"
        ".smallcaps { font-family: ui-monospace, 'SF Mono', Menlo, monospace; letter-spacing: 0.12em; text-transform: uppercase; }"
        "</style>"
    )

    # Background
    parts.append(
        f'<rect x="0" y="0" width="{_fmt(page.width_mm)}" '
        f'height="{_fmt(page.height_mm)}" fill="{background_color}" />'
    )

    # Scene children in order
    for child in root_node.children:
        rendered = _render_child(child)
        if rendered:
            parts.append(rendered)

    parts.append("</svg>")
    return "\n".join(parts)