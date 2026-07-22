# SPDX-License-Identifier: GPL-3.0-or-later
"""Standalone SVG renderer for the two-way fan chart scene model."""

from __future__ import annotations

from xml.sax.saxutils import escape as _xml_escape

try:
    from TwoWayFanChart.geometry import arc_path, mm_to_pt, AnnularSector
    from TwoWayFanChart.model import (
        SceneCircle,
        SceneImage,
        SceneLegend,
        SceneNode,
        ScenePage,
        ScenePathText,
        SceneRect,
        SceneSector,
        SceneText,
    )
except ModuleNotFoundError:
    from geometry import arc_path, mm_to_pt, AnnularSector
    from model import (
        SceneCircle,
        SceneImage,
        SceneLegend,
        SceneNode,
        ScenePage,
        ScenePathText,
        SceneRect,
        SceneSector,
        SceneText,
    )

_SVG_NS = "http://www.w3.org/2000/svg"
_XLINK_NS = "http://www.w3.org/1999/xlink"


def xml_escape(text: str) -> str:
    """Escape XML special characters for safe inclusion in SVG."""
    return _xml_escape(text, {'"': "&quot;"})


def _fmt(value: float) -> str:
    """Format a float for SVG, trimming unnecessary precision."""
    return f"{value:.4f}".rstrip("0").rstrip(".")


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


_path_text_counter = 0


def _render_path_text(pt: ScenePathText, path_id: str) -> str:
    """Render text along an SVG arc path.

    The path is emitted inside <defs> and referenced via textPath.
    Uses xlink:href for broad compatibility (Chromium, Firefox, Safari).
    """
    escaped = xml_escape(pt.content)
    return (
        f'<defs><path id="{path_id}" d="{pt.path}" fill="none" /></defs>'
        f'<text font-size="{_fmt(pt.font_size)}" fill="{pt.fill}">'
        f'<textPath xlink:href="#{path_id}" href="#{path_id}" startOffset="50%" text-anchor="middle">'
        f'{escaped}</textPath></text>'
    )


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