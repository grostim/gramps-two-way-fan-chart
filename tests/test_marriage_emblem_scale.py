import unittest

from TwoWayFanChart.layout import (
    _descendant_marriage_label_and_size,
    _font_size_for_width,
)
from TwoWayFanChart.model import (
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
        self.assertIn(f'<tspan font-size="{scaled:g}">⚭</tspan>', svg)
        self.assertIn(" 1900 · Lyon", svg)
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
        self.assertIn(f'<tspan font-size="{scaled:g}">⚭</tspan>', svg)
        self.assertIn(" 1620 · Paris", svg)
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
