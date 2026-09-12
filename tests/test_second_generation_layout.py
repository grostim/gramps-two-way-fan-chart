import math
import unittest

from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import (
    _DESCENDANT_FIRST_GEN_LINE_GAP_MM,
    _DESCENDANT_TITLE_GAP_MM,
    _RING_GAP_MM,
    _descendant_ring_bounds,
    calculate_canvas,
    layout_descendants,
    layout_titles,
)
from TwoWayFanChart.model import DescendantBranch, PersonNode, ScenePathText, SceneSector, UnionBranch


_BASE_WEIGHTS_FOR_FOUR_GENERATIONS = (1.0, 1.35, 1.7, 2.05)


def branch(
    handle: str,
    generation: int,
    *,
    children: tuple[DescendantBranch, ...] = (),
    spouse: str | None = None,
) -> DescendantBranch:
    unions = ()
    if spouse is not None:
        unions = (
            UnionBranch(
                family_handle=f"family-{handle}",
                spouse_handle=spouse,
                child_handles=tuple(child.person.handle for child in children),
                child_relations=tuple("birth" for _child in children),
            ),
        )
    return DescendantBranch(
        position_id=f"descendant-{handle}",
        person=PersonNode(handle, handle.upper()),
        generation=generation,
        unions=unions,
        children=children,
    )


def canvas(descendant_generations: int):
    return calculate_canvas(
        PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
        ancestor_generations=5,
        descendant_generations=descendant_generations,
    )


def path_radius(path: str, cx: float, cy: float) -> float:
    """Recover the radius of the first point of a generated arc path."""
    _move, x_text, y_text, *_rest = path.split()
    return math.hypot(float(x_text) - cx, float(y_text) - cy)


class SecondGenerationLayoutTests(unittest.TestCase):
    def test_grandchild_ring_is_doubled_without_widening_direct_children(self):
        fourth = branch("fourth", 4)
        third = branch("third", 3, children=(fourth,))
        second = branch("second", 2, children=(third,))
        root = branch("root", 1, children=(second,))
        chart = canvas(4)

        scene = layout_descendants(
            chart,
            (root,),
            name_lookup=lambda handle: handle,
            dates_lookup=lambda _handle: "",
        )
        direct_child_ring = next(
            sector
            for sector in scene.children
            if isinstance(sector, SceneSector)
            and math.isclose(
                sector.inner_radius,
                _descendant_ring_bounds(
                    chart.descendant_inner_radius_mm,
                    chart.descendant_outer_radius_mm,
                    4,
                    1,
                )[0],
            )
        )
        grandchild_ring = next(
            sector
            for sector in scene.children
            if isinstance(sector, SceneSector)
            and math.isclose(
                sector.inner_radius,
                _descendant_ring_bounds(
                    chart.descendant_inner_radius_mm,
                    chart.descendant_outer_radius_mm,
                    4,
                    2,
                )[0],
            )
        )
        total_depth = (
            chart.descendant_outer_radius_mm - chart.descendant_inner_radius_mm
        )
        total_weight = sum(_BASE_WEIGHTS_FOR_FOUR_GENERATIONS)
        baseline_direct_depth = (
            total_depth * _BASE_WEIGHTS_FOR_FOUR_GENERATIONS[0] / total_weight
            - _RING_GAP_MM
        )
        baseline_grandchild_depth = (
            total_depth * _BASE_WEIGHTS_FOR_FOUR_GENERATIONS[1] / total_weight
            - _RING_GAP_MM
        )

        self.assertAlmostEqual(
            direct_child_ring.outer_radius - direct_child_ring.inner_radius,
            baseline_direct_depth,
            places=6,
        )
        self.assertAlmostEqual(
            grandchild_ring.outer_radius - grandchild_ring.inner_radius,
            baseline_grandchild_depth * 2,
            places=6,
        )
        for depth in (1, 2, 3, 4):
            _inner, ring_outer = _descendant_ring_bounds(
                chart.descendant_inner_radius_mm,
                chart.descendant_outer_radius_mm,
                4,
                depth,
            )
            self.assertLessEqual(ring_outer, chart.descendant_outer_radius_mm)

    def test_deeper_rings_leave_clearance_for_descendant_title(self):
        chart = canvas(4)
        ring_outers = [
            _descendant_ring_bounds(
                chart.descendant_inner_radius_mm,
                chart.descendant_outer_radius_mm,
                4,
                depth,
            )[1]
            for depth in (1, 2, 3, 4)
        ]
        titles = layout_titles(
            chart,
            ancestor_generations=5,
            descendant_generations=4,
        )
        descendant_title = next(
            node
            for node in titles.children
            if node.content.startswith("DESCENDANTS")
        )

        self.assertLessEqual(max(ring_outers), chart.descendant_outer_radius_mm)
        self.assertGreaterEqual(
            descendant_title.y,
            chart.center_cy_mm
            + max(ring_outers)
            + _DESCENDANT_TITLE_GAP_MM,
        )

    def test_two_generation_chart_doubles_the_grandchild_ring(self):
        grandchild = branch("grandchild", 2)
        direct_child = branch("child", 1, children=(grandchild,))
        chart = canvas(2)
        scene = layout_descendants(
            chart,
            (direct_child,),
            name_lookup=lambda handle: handle,
            dates_lookup=lambda _handle: "",
        )
        rings = []
        for depth in (1, 2):
            inner, _outer = _descendant_ring_bounds(
                chart.descendant_inner_radius_mm,
                chart.descendant_outer_radius_mm,
                2,
                depth,
            )
            rings.append(
                next(
                    sector
                    for sector in scene.children
                    if isinstance(sector, SceneSector)
                    and math.isclose(sector.inner_radius, inner)
                )
            )

        self.assertAlmostEqual(
            rings[0].outer_radius - rings[0].inner_radius,
            chart.descendant_outer_radius_mm * (95 / 600),
            places=6,
        )
        self.assertAlmostEqual(
            rings[1].outer_radius - rings[1].inner_radius,
            chart.descendant_outer_radius_mm * (296 / 600),
            places=6,
        )

    def test_second_generation_couple_name_is_one_line(self):
        direct_child = branch(
            "gregoire",
            1,
            children=(branch("alexis", 2),),
            spouse="blandine",
        )
        scene = layout_descendants(
            canvas(2),
            (direct_child,),
            name_lookup={
                "gregoire": "Grégoire Mussat",
                "blandine": "Blandine Pouchard",
                "alexis": "Alexis Mussat",
            }.__getitem__,
            dates_lookup=lambda _handle: "",
        )
        couple_labels = [
            node
            for node in scene.children
            if isinstance(node, ScenePathText)
            and (
                "Grégoire Mussat" in node.content
                or "Blandine Pouchard" in node.content
            )
        ]

        self.assertEqual(
            [node.content for node in couple_labels],
            ["Grégoire Mussat × Blandine Pouchard"],
        )
        self.assertEqual(len(couple_labels), 1)

    def test_two_generation_direct_child_label_clears_center_circle(self):
        direct_child = branch(
            "gregoire",
            1,
            children=(branch("alexis", 2),),
            spouse="blandine",
        )
        chart = canvas(2)
        scene = layout_descendants(
            chart,
            (direct_child,),
            name_lookup={
                "gregoire": "Grégoire Mussat",
                "blandine": "Blandine Pouchard",
                "alexis": "Alexis Mussat",
            }.__getitem__,
            dates_lookup=lambda _handle: "",
        )
        couple_label = next(
            node
            for node in scene.children
            if isinstance(node, ScenePathText)
            and node.content == "Grégoire Mussat × Blandine Pouchard"
        )

        self.assertGreaterEqual(
            path_radius(
                couple_label.path,
                chart.center_cx_mm,
                chart.center_cy_mm,
            ),
            chart.center_radius_mm + _DESCENDANT_FIRST_GEN_LINE_GAP_MM - 1e-3,
        )

    def test_two_generation_direct_child_label_stays_inside_small_page_ring(self):
        for name, region in (
            ("A5", PaperRegion(PaperSize.A5, Orientation.LANDSCAPE)),
            (
                "custom",
                PaperRegion(
                    PaperSize.CUSTOM,
                    Orientation.LANDSCAPE,
                    custom_width_mm=160,
                    custom_height_mm=160,
                ),
            ),
        ):
            direct_child = branch(
                "child",
                1,
                children=(branch("grandchild", 2),),
                spouse="spouse",
            )
            chart = calculate_canvas(
                region,
                ancestor_generations=5,
                descendant_generations=2,
            )
            scene = layout_descendants(
                chart,
                (direct_child,),
                name_lookup={
                    "child": "Child",
                    "spouse": "Spouse",
                    "grandchild": "Grandchild",
                }.__getitem__,
                dates_lookup=lambda _handle: "",
            )
            couple_label = next(
                node
                for node in scene.children
                if isinstance(node, ScenePathText)
                and node.content == "Child × Spouse"
            )
            _inner, ring_outer = _descendant_ring_bounds(
                chart.descendant_inner_radius_mm,
                chart.descendant_outer_radius_mm,
                2,
                1,
            )
            radius = path_radius(
                couple_label.path,
                chart.center_cx_mm,
                chart.center_cy_mm,
            )

            self.assertGreater(
                radius,
                chart.center_radius_mm,
                msg=f"{name} label remains under the center circle",
            )
            self.assertLessEqual(
                radius,
                ring_outer + 1e-3,
                msg=f"{name} label leaves its direct-child ring",
            )


if __name__ == "__main__":
    unittest.main()
