import tempfile
import unittest
from pathlib import Path

from TwoWayFanChart.layout import (
    _descendant_marriage_label_and_size,
    _font_size_for_width,
)
from TwoWayFanChart.model import (
    MARRIAGE_EMBLEM_DY_RATIO,
    MARRIAGE_EMBLEM_SCALE,
    SceneNode,
    ScenePage,
    ScenePathText,
    SceneText,
    estimate_emblem_text_width,
    estimate_text_width,
    split_marriage_emblem,
)
from TwoWayFanChart.render_svg import render_svg


class SplitMarriageEmblemTests(unittest.TestCase):
    def test_split_keeps_occurrence_digits_with_the_emblem(self):
        self.assertEqual(split_marriage_emblem("⚭ 1900"), ("⚭", " 1900"))
        self.assertEqual(split_marriage_emblem("⚭2 1902"), ("⚭2", " 1902"))
        self.assertEqual(split_marriage_emblem("⚭3 1905"), ("⚭3", " 1905"))
        self.assertEqual(split_marriage_emblem("⚭"), ("⚭", ""))

    def test_split_is_identity_without_emblem(self):
        for content in ("", "Louis", "1900 · Lyon", "° 1800 – † 1860"):
            self.assertEqual(split_marriage_emblem(content), ("", content))


class EstimateEmblemWidthTests(unittest.TestCase):
    def test_emblem_scales_up_only_the_leading_glyph(self):
        base = estimate_emblem_text_width("⚭ 1900", 2.0)
        plain = estimate_text_width("⚭ 1900", 2.0)
        self.assertGreater(base, plain)
        # The glyph plus its trailing space widen by (scale-1) times the
        # glyph width only; the digits keep their natural size.
        self.assertAlmostEqual(
            base,
            estimate_emblem_text_width("⚭", 2.0)
            + estimate_text_width(" 1900", 2.0),
        )

    def test_emblem_free_text_measures_identically(self):
        plain = estimate_text_width("1900 · Lyon", 2.0)
        self.assertEqual(estimate_emblem_text_width("1900 · Lyon", 2.0), plain)

    def test_font_size_fitting_accounts_for_the_scaled_emblem(self):
        # The same label at the plain width fits more capacity than at the
        # scaled width; the fitting must use the scaled width so the
        # enlarged symbol never overflows its sector.
        fit_scaled = _font_size_for_width(
            "⚭ 1900",
            target_size=3.0,
            max_width=12.0,
        )
        self.assertGreater(fit_scaled, 0.0)
        self.assertLessEqual(
            estimate_emblem_text_width("⚭ 1900", fit_scaled),
            12.0 + 1e-9,
        )


class SvgEmblemRenderingTests(unittest.TestCase):
    def test_scene_text_emits_enlarged_tspan(self):
        svg = render_svg(
            ScenePage(100, 100),
            SceneNode(
                (
                    SceneText(
                        x=50,
                        y=50,
                        content="⚭ 1900 · Lyon",
                        font_size=3.0,
                        anchor="middle",
                    ),
                )
            ),
        )
        scaled = 3.0 * MARRIAGE_EMBLEM_SCALE
        dy = scaled * MARRIAGE_EMBLEM_DY_RATIO
        self.assertIn(f'<tspan font-size="{scaled:g}" dy="{dy:g}">⚭</tspan>', svg)
        self.assertIn(f'<tspan dy="{-dy:g}"> 1900 · Lyon</tspan>', svg)
        self.assertNotIn("textLength", svg)

    def test_scene_text_without_emblem_stays_plain(self):
        svg = render_svg(
            ScenePage(100, 100),
            SceneNode((SceneText(x=50, y=50, content="Louis 1800", font_size=3.0),)),
        )
        self.assertNotIn("tspan", svg)
        self.assertIn("Louis 1800", svg)

    def test_arc_label_emits_enlarged_tspan_without_text_length(self):
        svg = render_svg(
            ScenePage(100, 100),
            SceneNode(
                (
                    ScenePathText(
                        path="M 10 80 A 30 30 0 0 1 70 80",
                        content="⚭ 1620 · Paris",
                        font_size=3.0,
                        max_width=40.0,
                    ),
                )
            ),
        )
        scaled = 3.0 * MARRIAGE_EMBLEM_SCALE
        dy = scaled * MARRIAGE_EMBLEM_DY_RATIO
        self.assertIn(f'<tspan font-size="{scaled:g}" dy="{dy:g}">⚭</tspan>', svg)
        self.assertIn(f'<tspan dy="{-dy:g}"> 1620 · Paris</tspan>', svg)
        self.assertNotIn("textLength", svg)

    def test_arc_label_without_emblem_keeps_text_length(self):
        svg = render_svg(
            ScenePage(100, 100),
            SceneNode(
                (
                    ScenePathText(
                        path="M 10 80 A 30 30 0 0 1 70 80",
                        content="Full Name 1781–1846",
                        font_size=3.0,
                        max_width=40.0,
                    ),
                )
            ),
        )
        self.assertNotIn("tspan", svg)
        self.assertIn("textLength", svg)


class EmblemVerticalAlignmentTests(unittest.TestCase):
    """The enlarged U+26AD glyph floats above the digits' axis at the same
    baseline; the renderers lower it so its ink center aligns with the
    digits (issue #43, reopened for vertical centering)."""

    def _render_cairo_text(self, dpi: int = 150) -> "tuple[int, int]":
        try:
            from TwoWayFanChart.render_cairo import render_cairo_png
        except ModuleNotFoundError as error:
            if error.name == "cairo":
                self.skipTest("pycairo is not installed")
            raise
        import cairo

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "emblem.png"
            render_cairo_png(
                path,
                ScenePage(100, 40),
                SceneNode(
                    (
                        SceneText(
                            x=30,
                            y=20,
                            content="⚭ 1900",
                            font_size=10.0,
                            anchor="start",
                        ),
                    )
                ),
                dpi=dpi,
            )
            surface = cairo.ImageSurface.create_from_png(str(path))
            buf = surface.get_data()
            width = surface.get_width()
            height = surface.get_height()
            stride = surface.get_stride()
            # ARGB32 little-endian: byte order B,G,R,A per pixel.
            columns: dict[int, list[int]] = {}
            for row in range(height):
                for col in range(width):
                    offset = row * stride + col * 4
                    alpha = buf[offset + 3]
                    blue = buf[offset]
                    if alpha > 200 and blue < 200:
                        columns.setdefault(col, []).append(row)
            if not columns:
                self.fail("no dark pixels rendered by the cairo backend")
            runs = []
            previous_col = None
            for col in sorted(columns):
                if previous_col is None or col - previous_col > 4:
                    runs.append([col, col])
                else:
                    runs[-1][1] = col
                previous_col = col
            emblem = runs[0]
            emblem_rows = [
                row
                for col in range(emblem[0], emblem[1])
                for row in columns.get(col, [])
            ]
            digits_rows: list[int] = []
            for run in runs[1:]:
                for col in range(run[0], run[1]):
                    digits_rows.extend(columns.get(col, []))
                break
            if not emblem_rows or not digits_rows:
                self.fail("emblem or digits not rendered")
            emblem_center = (min(emblem_rows) + max(emblem_rows)) / 2
            digits_center = (min(digits_rows) + max(digits_rows)) / 2
            return emblem_center, digits_center

    def test_cairo_emblem_center_matches_digit_axis(self):
        emblem_center, digits_center = self._render_cairo_text()
        # The emblem ink center must sit within 0.05em of the digits'
        # centerline, expressed in rendered pixels (dpi=150, em=10mm).
        em_px = 10.0 * 150 / 25.4
        self.assertAlmostEqual(emblem_center, digits_center, delta=0.05 * em_px)

    def test_cairo_arc_emblem_center_matches_digit_axis(self):
        try:
            from TwoWayFanChart.render_cairo import render_cairo_png
        except ModuleNotFoundError as error:
            if error.name == "cairo":
                self.skipTest("pycairo is not installed")
            raise
        import cairo

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "emblem_arc.png"
            render_cairo_png(
                path,
                ScenePage(100, 100),
                SceneNode(
                    (
                        ScenePathText(
                            path="M 10 50 A 400 400 0 0 1 90 50",
                            content="⚭ 1900",
                            font_size=10.0,
                            fill="#141413",
                        ),
                    )
                ),
                dpi=150,
            )
            surface = cairo.ImageSurface.create_from_png(str(path))
            buf = surface.get_data()
            width = surface.get_width()
            height = surface.get_height()
            stride = surface.get_stride()
            columns: dict[int, list[int]] = {}
            for row in range(height):
                for col in range(width):
                    offset = row * stride + col * 4
                    alpha = buf[offset + 3]
                    blue = buf[offset]
                    if alpha > 200 and blue < 200:
                        columns.setdefault(col, []).append(row)
            if not columns:
                self.fail("no dark pixels rendered by the cairo arc backend")
            runs = []
            previous_col = None
            for col in sorted(columns):
                if previous_col is None or col - previous_col > 4:
                    runs.append([col, col])
                else:
                    runs[-1][1] = col
                previous_col = col
            emblem = runs[0]
            emblem_rows = [
                row
                for col in range(emblem[0], emblem[1])
                for row in columns.get(col, [])
            ]
            digits_rows: list[int] = []
            for run in runs[1:]:
                for col in range(run[0], run[1]):
                    digits_rows.extend(columns.get(col, []))
                break
            if not emblem_rows or not digits_rows:
                self.fail("emblem or digits not rendered on the arc")
            emblem_center = (min(emblem_rows) + max(emblem_rows)) / 2
            digits_center = (min(digits_rows) + max(digits_rows)) / 2
        em_px = 10.0 * 150 / 25.4
        self.assertAlmostEqual(emblem_center, digits_center, delta=0.05 * em_px)


class MarriageLabelFittingTests(unittest.TestCase):
    def test_emblem_scale_keeps_full_label_when_it_fits(self):
        # A label that fits at the threshold with the scaled emblem stays
        # the full date-and-place label; a too-long one degrades to year.
        short = "⚭ 1900"
        label, size = _descendant_marriage_label_and_size(
            short,
            "⚭ 1900",
            30.0,
            inner_r=10.0,
            outer_r=30.0,
        )
        self.assertEqual(label, short)
        self.assertGreater(size, 0.0)

    def test_emblem_scale_degrades_to_year_when_tight(self):
        long_label = "⚭ 1900 · Saint-Germain-en-Laye, Île-de-France, France"
        label, _size = _descendant_marriage_label_and_size(
            long_label,
            "⚭ 1900",
            25.0,
            inner_r=3.0,
            outer_r=9.0,
        )
        self.assertEqual(label, "⚭ 1900")


if __name__ == "__main__":
    unittest.main()
