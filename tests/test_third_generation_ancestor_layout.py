import math
import unittest

from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import calculate_canvas, layout_ancestors
from TwoWayFanChart.model import ScenePathText, SceneText, estimate_text_width


class ThirdGenerationAncestorLayoutTests(unittest.TestCase):
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
