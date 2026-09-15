import math
import unittest

from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import (
    _ancestor_ring_weights,
    calculate_canvas,
    layout_ancestors,
)
from TwoWayFanChart.model import (
    ScenePathText,
    SceneSector,
    SceneText,
    estimate_text_width,
)


class ThirdGenerationAncestorLayoutTests(unittest.TestCase):
    def test_issue67_tuned_weights_reduce_g3_and_boost_g4(self):
        # Issue #67 tuning: G3 drops 10% below its original weight
        # (1.31 -> 1.179) and G4 rises 10% above the first correction
        # (1.90 -> 2.09). G1/G2 keep the original mockup proportions and
        # G5+ keep the original quadratic growth.
        three = _ancestor_ring_weights(3)
        self.assertEqual(three, [1.0, 1.105, 1.31 * 0.9])
        self.assertAlmostEqual(three[2], 1.179, places=3)
        self.assertTrue(three[0] < three[1] < three[2])

        four = _ancestor_ring_weights(4)
        self.assertEqual(four, [1.0, 1.105, 1.31 * 0.9, 1.90 * 1.1])
        self.assertAlmostEqual(four[2], 1.179, places=3)
        self.assertAlmostEqual(four[3], 2.09, places=3)
        self.assertTrue(four[0] < four[1] < four[2] < four[3])
        # The G4 boost must outpace the G3 reduction: with the tuning the
        # G4/G3 weight ratio (~1.77) exceeds the ratio from the first
        # fix (~1.45) and the original (~1.23).
        self.assertGreater(four[3] / four[2], 1.6)

        five = _ancestor_ring_weights(5)
        self.assertEqual(five[0], 1.0)
        self.assertEqual(five[1], 1.105)
        self.assertAlmostEqual(five[2], 1.179, places=3)
        self.assertAlmostEqual(five[3], 2.09, places=3)
        # G5 carries the original G5/G4 ratio above the tuned G4 so the
        # monotonic hierarchy holds in five-generation layouts.
        self.assertAlmostEqual(five[4], 2.09 * (2.02 / 1.90), places=3)
        self.assertTrue(five[0] < five[1] < five[2] < five[3] < five[4])

    def test_g4_sector_is_radially_wider_than_g3(self):
        slots = (
            ("ancestor-a-1-0", "Parent A", "1840–1900"),
            ("ancestor-b-1-0", "Parent B", "1840–1900"),
            ("ancestor-a-2-0", "Grandparent A1", "1800–1860"),
            ("ancestor-a-2-1", "Grandparent A2", "1800–1860"),
            ("ancestor-b-2-0", "Grandparent B1", "1800–1860"),
            ("ancestor-b-2-1", "Grandparent B2", "1800–1860"),
            ("ancestor-a-3-0", "Great-Grandparent A1", "1760–1820"),
            ("ancestor-a-3-1", "Great-Grandparent A2", "1760–1820"),
            ("ancestor-a-3-2", "Great-Grandparent A3", "1760–1820"),
            ("ancestor-a-3-3", "Great-Grandparent A4", "1760–1820"),
            ("ancestor-b-3-0", "Great-Grandparent B1", "1760–1820"),
            ("ancestor-b-3-1", "Great-Grandparent B2", "1760–1820"),
            ("ancestor-b-3-2", "Great-Grandparent B3", "1760–1820"),
            ("ancestor-b-3-3", "Great-Grandparent B4", "1760–1820"),
            *tuple(
                (f"ancestor-a-4-{index}", f"Great-Great A{index}", "1720–1780")
                for index in range(8)
            ),
            *tuple(
                (f"ancestor-b-4-{index}", f"Great-Great B{index}", "1720–1780")
                for index in range(8)
            ),
        )
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=4,
            descendant_generations=0,
        )
        sectors = [
            node
            for node in layout_ancestors(canvas, slots).children
            if isinstance(node, SceneSector) and node.sweep_angle > 0.0
        ]
        # Classify rings by their sector sweep: G3 sectors span ~21.5° with
        # four per lineage, G4 sectors ~10.75° with eight per lineage.
        g3 = [s for s in sectors if 15.0 <= s.sweep_angle < 30.0]
        g4 = [s for s in sectors if 8.0 <= s.sweep_angle < 15.0]
        self.assertEqual(len(g3), 8)
        self.assertEqual(len(g4), 16)
        # The tuned G4 ring is at least 60% deeper than G3: the weight
        # ratio is ~1.77 (2.09 / 1.179) versus ~1.45 before the tuning
        # (1.90 / 1.31) and ~1.23 originally (1.615 / 1.31).
        self.assertGreater(
            min(s.outer_radius - s.inner_radius for s in g4),
            max(s.outer_radius - s.inner_radius for s in g3) * 1.6,
        )

    def test_generation_three_names_are_radial_and_share_maximum_fitting_size(self):
        generation_three_labels = (
            "Alexandre Théodore de la Rochefoucauld",
            "Marie Louise de Montmorency",
            "Jean-Baptiste de Saint-Clair",
            "Élisabeth Charlotte de Villeneuve",
            "Nicolas de la Tour",
            "Louise de la Tour",
            "Philippe de la Tour",
            "Marguerite de la Tour",
        )
        slots = (
            ("ancestor-a-1-0", "Parent A", ""),
            ("ancestor-b-1-0", "Parent B", ""),
            ("ancestor-a-2-0", "Grandparent A1", ""),
            ("ancestor-a-2-1", "Grandparent A2", ""),
            ("ancestor-b-2-0", "Grandparent B1", ""),
            ("ancestor-b-2-1", "Grandparent B2", ""),
            *tuple(
                (
                    f"ancestor-{lineage}-3-{index}",
                    label,
                    "1740–1800",
                )
                for lineage, labels in (("a", generation_three_labels[:4]), ("b", generation_three_labels[4:]))
                for index, label in enumerate(labels)
            ),
        )
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=3,
            descendant_generations=0,
        )

        scene = layout_ancestors(canvas, slots)
        names = [
            node
            for node in scene.children
            if isinstance(node, SceneText)
            and node.content in set(generation_three_labels)
        ]

        self.assertEqual(
            {node.content for node in names},
            set(generation_three_labels),
        )
        self.assertEqual(
            len({round(node.font_size, 9) for node in names}),
            1,
        )
        self.assertTrue(all(node.rotation is not None for node in names))
        self.assertTrue(all(node.max_width is not None and node.max_width > 0 for node in names))
        dates = [
            node
            for node in scene.children
            if isinstance(node, ScenePathText) and node.content == "1740–1800"
        ]
        self.assertEqual(len(dates), len(generation_three_labels))
        self.assertTrue(all(node.font_size > 0 for node in dates))
        self.assertTrue(
            all(
                estimate_text_width(node.content, node.font_size)
                <= node.max_width + 1e-6
                for node in names
            )
        )

        # The name baseline must be radial, i.e. parallel to the center-to-cell
        # vector, rather than tangent to the ancestor ring.  The baseline may
        # be shifted tangentially to clear the date rail within its cell.
        expected_mid_angles = {
            label: -86.0 + (index + 0.5) * 21.5
            for index, label in enumerate(generation_three_labels[:4])
        }
        expected_mid_angles.update(
            {
                label: (index + 0.5) * 21.5
                for index, label in enumerate(generation_three_labels[4:])
            }
        )
        for node in names:
            angle = math.radians(expected_mid_angles[node.content])
            radial_x = math.sin(angle)
            radial_y = -math.cos(angle)
            baseline_x = math.cos(math.radians(node.rotation))
            baseline_y = math.sin(math.radians(node.rotation))
            cross_product = abs(radial_x * baseline_y - radial_y * baseline_x)
            self.assertLess(cross_product, 1e-6)

        longest = max(names, key=lambda node: estimate_text_width(node.content, 1.0))
        self.assertAlmostEqual(
            estimate_text_width(longest.content, longest.font_size),
            longest.max_width,
            places=6,
        )

    def test_five_generation_layout_rotates_only_narrow_g3_names(self):
        generation_three_labels = tuple(f"G3 Name {index}" for index in range(16))
        generation_three_dates = tuple(f"G3 Date {index}" for index in range(16))
        slots = []
        counts = {1: 1, 2: 2, 3: 8, 4: 16, 5: 32}
        g3_index = 0
        for generation, count in counts.items():
            for lineage in ("a", "b"):
                for index in range(count):
                    if generation == 3:
                        label = generation_three_labels[g3_index]
                        dates_label = generation_three_dates[g3_index]
                        g3_index += 1
                    else:
                        label = f"G{generation} {lineage} {index}"
                        dates_label = f"D{generation} {lineage} {index}"
                    slots.append(
                        (f"ancestor-{lineage}-{generation}-{index}", label, dates_label)
                    )

        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=0,
        )
        scene = layout_ancestors(canvas, tuple(slots))
        names = [
            node
            for node in scene.children
            if isinstance(node, SceneText)
            and node.content in set(generation_three_labels)
        ]
        dates = [
            node
            for node in scene.children
            if isinstance(node, ScenePathText)
            and node.content in set(generation_three_dates)
        ]

        self.assertEqual(len(names), len(generation_three_labels))
        self.assertEqual(len(dates), len(generation_three_dates))
        self.assertEqual(len({round(node.font_size, 9) for node in names}), 1)
        self.assertTrue(all(node.max_width is not None and node.max_width > 0 for node in names))
        self.assertTrue(
            all(
                estimate_text_width(node.content, node.font_size)
                <= node.max_width + 1e-6
                for node in names
            )
        )

        # With eight G3 slots per lineage the standard narrow-sector name is
        # radial. The requested 90-degree pivot makes the name tangent.
        for node in names:
            radial_x = node.x - canvas.center_cx_mm
            radial_y = node.y - canvas.center_cy_mm
            baseline_x = math.cos(math.radians(node.rotation))
            baseline_y = math.sin(math.radians(node.rotation))
            dot_product = abs(radial_x * baseline_x + radial_y * baseline_y)
            self.assertLess(dot_product, 1e-6)

        # Dates retain their established tangent rail on the ancestor ring.
        self.assertTrue(all(" A " in node.path for node in dates))


if __name__ == "__main__":
    unittest.main()
