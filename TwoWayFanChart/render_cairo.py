# SPDX-License-Identifier: GPL-3.0-or-later
"""Cairo renderer for PDF and PNG output from the scene model.

Consumes the same SceneNode tree as the SVG renderer, producing
PDF and PNG files via pycairo.
"""

from __future__ import annotations

import math
from pathlib import Path

import cairo

try:
    from TwoWayFanChart.geometry import mm_to_pt, mm_to_px, deg2rad
    from TwoWayFanChart.model import (
        SceneCircle,
        SceneImage,
        SceneLegend,
        SceneNode,
        ScenePage,
        SceneSector,
        SceneText,
    )
except ModuleNotFoundError:
    from geometry import mm_to_pt, mm_to_px, deg2rad
    from model import (
        SceneCircle,
        SceneImage,
        SceneLegend,
        SceneNode,
        ScenePage,
        SceneSector,
        SceneText,
    )


def _parse_hex_color(hex_color: str) -> tuple[float, float, float]:
    """Parse a #RRGGBB hex color into (r, g, b) floats in 0..1."""
    if not hex_color.startswith("#") or len(hex_color) != 7:
        raise ValueError(f"invalid hex color: {hex_color!r}")
    r = int(hex_color[1:3], 16) / 255.0
    g = int(hex_color[3:5], 16) / 255.0
    b = int(hex_color[5:7], 16) / 255.0
    return (r, g, b)


def _render_sector(ctx: cairo.Context, sector: SceneSector) -> None:
    """Render an annular sector centered at origin."""
    r_in = sector.inner_radius
    r_out = sector.outer_radius
    a0 = deg2rad(sector.start_angle)
    a1 = deg2rad(sector.start_angle + sector.sweep_angle)

    if r_in <= 0:
        # Pie slice
        ctx.move_to(0, 0)
        ctx.line_to(r_out * math.cos(a0), r_out * math.sin(a0))
        ctx.arc(0, 0, r_out, a0, a1)
        ctx.close_path()
    else:
        # Annular sector
        ctx.arc(0, 0, r_out, a0, a1)
        ctx.arc_negative(0, 0, r_in, a1, a0)
        ctx.close_path()

    if sector.fill:
        r, g, b = _parse_hex_color(sector.fill)
        ctx.set_source_rgb(r, g, b)
        if sector.stroke:
            ctx.fill_preserve()
        else:
            ctx.fill()
    if sector.stroke:
        r, g, b = _parse_hex_color(sector.stroke)
        ctx.set_source_rgb(r, g, b)
        ctx.set_line_width(sector.stroke_width)
        ctx.stroke()


def _render_circle(ctx: cairo.Context, circle: SceneCircle) -> None:
    """Render a circle."""
    ctx.arc(circle.cx, circle.cy, circle.r, 0, 2 * math.pi)
    if circle.fill:
        r, g, b = _parse_hex_color(circle.fill)
        ctx.set_source_rgb(r, g, b)
        if circle.stroke:
            ctx.fill_preserve()
        else:
            ctx.fill()
    if circle.stroke:
        r, g, b = _parse_hex_color(circle.stroke)
        ctx.set_source_rgb(r, g, b)
        ctx.set_line_width(circle.stroke_width)
        ctx.stroke()


def _render_text(ctx: cairo.Context, text: SceneText) -> None:
    """Render text (basic, no Pango yet)."""
    if text.fill:
        r, g, b = _parse_hex_color(text.fill)
        ctx.set_source_rgb(r, g, b)
    ctx.set_font_size(text.font_size)
    ctx.move_to(text.x, text.y)
    ctx.show_text(text.content)


def _render_image(ctx: cairo.Context, img: SceneImage) -> None:
    """Render an image or fallback initials."""
    if img.data_uri:
        # Decode base64 data URI
        import base64
        header, _, data = img.data_uri.partition(",")
        try:
            raw = base64.b64decode(data)
        except Exception:
            raw = b""
        if raw:
            # Create a Cairo image surface from PNG data
            import io
            try:
                surface = cairo.ImageSurface.create_from_png(io.BytesIO(raw))
                # Clip to circle
                ctx.save()
                ctx.arc(img.cx, img.cy, img.r, 0, 2 * math.pi)
                ctx.clip()
                # Scale and position
                sw, sh = surface.get_width(), surface.get_height()
                scale = min(img.r * 2 / sw, img.r * 2 / sh) if sw > 0 and sh > 0 else 1
                ctx.translate(img.cx - img.r, img.cy - img.r)
                ctx.scale(scale, scale)
                ctx.set_source_surface(surface, 0, 0)
                ctx.paint()
                ctx.restore()
                return
            except Exception:
                pass  # Fall through to fallback

    # Fallback: background circle + initials
    if img.fallback_text:
        ctx.arc(img.cx, img.cy, img.r, 0, 2 * math.pi)
        ctx.set_source_rgb(0xF0 / 255, 0xEE / 255, 0xE6 / 255)
        ctx.fill()
        ctx.set_source_rgb(0x14 / 255, 0x14 / 255, 0x13 / 255)
        ctx.set_font_size(img.r * 0.8)
        ctx.move_to(img.cx, img.cy + img.r * 0.3)
        ctx.show_text(img.fallback_text)


def _render_legend(ctx: cairo.Context, legend: SceneLegend) -> None:
    """Render a legend block."""
    y = legend.y
    for label, color in legend.items:
        r, g, b = _parse_hex_color(color)
        ctx.set_source_rgb(r, g, b)
        ctx.rectangle(legend.x, y - 4, 8, 8)
        ctx.fill()
        ctx.set_source_rgb(0x3D / 255, 0x3D / 255, 0x3A / 255)
        ctx.set_font_size(5)
        ctx.move_to(legend.x + 12, y + 3)
        ctx.show_text(label)
        y += 8


def _render_child(ctx: cairo.Context, child) -> None:
    """Render one scene primitive."""
    if isinstance(child, SceneSector):
        _render_sector(ctx, child)
    elif isinstance(child, SceneCircle):
        _render_circle(ctx, child)
    elif isinstance(child, SceneText):
        _render_text(ctx, child)
    elif isinstance(child, SceneImage):
        _render_image(ctx, child)
    elif isinstance(child, SceneLegend):
        _render_legend(ctx, child)
    elif isinstance(child, SceneNode):
        for c in child.children:
            _render_child(ctx, c)


def _render_to_surface(
    surface: cairo.Surface,
    page: ScenePage,
    root: SceneNode,
    background_color: str = "#FAF9F5",
) -> None:
    """Render the scene to a Cairo surface (SVG/PDF/PNG)."""
    ctx = cairo.Context(surface)
    # Background
    r, g, b = _parse_hex_color(background_color)
    ctx.set_source_rgb(r, g, b)
    ctx.rectangle(0, 0, page.width_mm, page.height_mm)
    ctx.fill()
    # Children
    for child in root.children:
        _render_child(ctx, child)
    surface.show_page()


def render_cairo_pdf(
    path: str | Path,
    page: ScenePage,
    root: SceneNode,
    *,
    background_color: str = "#FAF9F5",
) -> None:
    """Render the scene to a PDF file."""
    w_pt = mm_to_pt(page.width_mm)
    h_pt = mm_to_pt(page.height_mm)
    surface = cairo.PDFSurface(str(path), w_pt, h_pt)
    # Cairo PDF uses points, so scale mm to pt
    ctx = cairo.Context(surface)
    ctx.scale(72 / 25.4, 72 / 25.4)  # mm to pt scale
    r, g, b = _parse_hex_color(background_color)
    ctx.set_source_rgb(r, g, b)
    ctx.rectangle(0, 0, page.width_mm, page.height_mm)
    ctx.fill()
    for child in root.children:
        _render_child(ctx, child)
    surface.show_page()
    surface.finish()


def render_cairo_png(
    path: str | Path,
    page: ScenePage,
    root: SceneNode,
    *,
    background_color: str = "#FAF9F5",
    dpi: int = 150,
) -> None:
    """Render the scene to a PNG file."""
    w_px = int(mm_to_px(page.width_mm, dpi=dpi))
    h_px = int(mm_to_px(page.height_mm, dpi=dpi))
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w_px, h_px)
    ctx = cairo.Context(surface)
    # Scale pixels to mm
    scale = dpi / 25.4
    ctx.scale(scale, scale)
    r, g, b = _parse_hex_color(background_color)
    ctx.set_source_rgb(r, g, b)
    ctx.rectangle(0, 0, page.width_mm, page.height_mm)
    ctx.fill()
    for child in root.children:
        _render_child(ctx, child)
    surface.write_to_png(str(path))


def render_cairo_svg(
    path: str | Path,
    page: ScenePage,
    root: SceneNode,
    *,
    background_color: str = "#FAF9F5",
) -> None:
    """Render the scene to an SVG file via Cairo."""
    surface = cairo.SVGSurface(str(path), page.width_mm, page.height_mm)
    ctx = cairo.Context(surface)
    r, g, b = _parse_hex_color(background_color)
    ctx.set_source_rgb(r, g, b)
    ctx.rectangle(0, 0, page.width_mm, page.height_mm)
    ctx.fill()
    for child in root.children:
        _render_child(ctx, child)
    surface.finish()