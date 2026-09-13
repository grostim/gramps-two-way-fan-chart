import unittest

from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import calculate_canvas, layout_center
from TwoWayFanChart.model import SceneText, estimate_text_width


class CenterLayoutTests(unittest.TestCase):
    def setUp(self):
        self.canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=3,
        )

    def test_page_layout_centers_visible_composition_bounds(self):
        paper = PaperRegion(PaperSize.A0, Orientation.LANDSCAPE)
        canvas = calculate_canvas(
            paper,
            ancestor_generations=5,
            descendant_generations=4,
        )

        top_extent = canvas.ancestor_outer_radius_mm
        bottom_extent = canvas.descendant_outer_radius_mm
        top_clearance = (
            canvas.center_cy_mm
            - top_extent
            - paper.effective_margin_top_mm
        )
        bottom_clearance = (
            paper.height_mm
            - paper.effective_margin_bottom_mm
            - canvas.center_cy_mm
            - bottom_extent
        )

        self.assertAlmostEqual(top_clearance, bottom_clearance, places=6)
        self.assertGreater(
            canvas.center_cy_mm,
            paper.effective_margin_top_mm + paper.content_height_mm / 2,
        )

    def _name_node(self, **kwargs):
        scene = layout_center(**kwargs)
        return next(
            node
            for node in scene.children
            if isinstance(node, SceneText) and " & " in node.content
        )

    def test_long_center_couple_gets_smaller_font_and_keeps_full_label(self):
        short = self._name_node(
            canvas=self.canvas,
            left_label="Louis Roque",
            right_label="Lucie Roque",
        )
        long_label = "Louis « Germain » Roque & Marie Sophie Hélène Lucie « Lucy » Roque"
        long = self._name_node(
            canvas=self.canvas,
            left_label="Louis « Germain » Roque",
            right_label="Marie Sophie Hélène Lucie « Lucy » Roque",
        )

        self.assertLess(long.font_size, short.font_size)
        self.assertEqual(long.content, long_label)
        self.assertIsNotNone(long.max_width)
        self.assertLessEqual(
            estimate_text_width(long.content, long.font_size),
            long.max_width,
        )

    def test_center_label_width_is_available_only_inside_white_circle(self):
        node = self._name_node(
            canvas=self.canvas,
            left_label="François Gros",
            right_label="Barbe-Marie Ruau",
        )

        self.assertIsNotNone(node.max_width)
        self.assertLess(node.max_width, self.canvas.center_radius_mm * 1.8)
        self.assertGreater(node.max_width, self.canvas.center_radius_mm)


if __name__ == "__main__":
    unittest.main()
