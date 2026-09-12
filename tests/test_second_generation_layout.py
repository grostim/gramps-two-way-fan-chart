import math
import unittest

from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import (
    _DESCENDANT_FIRST_GEN_LINE_GAP_MM,
    _MEDALLION_EDGE_CLEARANCE_MM,
    _MIN_INITIALS_MEDALLION_RADIUS_MM,
    _RING_GAP_MM,
    _descendant_ring_bounds,
    calculate_canvas,
    layout_descendants,
)
from TwoWayFanChart.model import (
    DescendantBranch,
    PersonNode,
    SceneCircle,
    SceneImage,
    SceneText,
    ScenePathText,
    SceneSector,
    UnionBranch,
)


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

    def test_deeper_rings_fit_inside_descendant_outer_radius(self):
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
        self.assertLessEqual(max(ring_outers), chart.descendant_outer_radius_mm)

    def test_a1_deep_layout_keeps_direct_child_portrait_medallions(self):
        for generations in (3, 4):
            branch_at_depth = branch(f"g{generations}", generations)
            for depth in range(generations - 1, 0, -1):
                branch_at_depth = branch(
                    f"g{depth}",
                    depth,
                    children=(branch_at_depth,),
                    spouse=f"s{depth}",
                )
            chart = calculate_canvas(
                PaperRegion(PaperSize.A1, Orientation.LANDSCAPE),
                ancestor_generations=5,
                descendant_generations=generations,
            )
            scene = layout_descendants(
                chart,
                (branch_at_depth,),
                name_lookup=lambda handle: handle,
                dates_lookup=lambda _handle: "",
                portrait_lookup=lambda handle: f"data:image/png;base64,{handle}",
            )
            circles = [
                node for node in scene.children if isinstance(node, SceneCircle)
            ]
            images = [
                node for node in scene.children if isinstance(node, SceneImage)
            ]

            self.assertGreaterEqual(
                len(circles),
                2,
                msg=f"A1 generation {generations} lost direct-child medallions",
            )
            self.assertGreaterEqual(
                len(images),
                2,
                msg=f"A1 generation {generations} lost direct-child portraits",
            )
            self.assertGreaterEqual(
                min(circle.r for circle in circles),
                _MIN_INITIALS_MEDALLION_RADIUS_MM,
            )

    def test_a1_and_a2_keep_the_doubled_grandchild_ring(self):
        for paper_size in (PaperSize.A1, PaperSize.A2):
            for generations in (3, 4):
                chart = calculate_canvas(
                    PaperRegion(paper_size, Orientation.LANDSCAPE),
                    ancestor_generations=5,
                    descendant_generations=generations,
                )
                _direct_inner, _direct_outer = _descendant_ring_bounds(
                    chart.descendant_inner_radius_mm,
                    chart.descendant_outer_radius_mm,
                    generations,
                    1,
                )
                grandchild_inner, grandchild_outer = _descendant_ring_bounds(
                    chart.descendant_inner_radius_mm,
                    chart.descendant_outer_radius_mm,
                    generations,
                    2,
                )
                total_depth = (
                    chart.descendant_outer_radius_mm
                    - chart.descendant_inner_radius_mm
                )
                weights = _BASE_WEIGHTS_FOR_FOUR_GENERATIONS[:generations]
                baseline_grandchild_width = (
                    total_depth * weights[1] / sum(weights) - _RING_GAP_MM
                )

                self.assertAlmostEqual(
                    grandchild_outer - grandchild_inner,
                    baseline_grandchild_width * 2.0,
                    places=6,
                    msg=f"{paper_size.value} generation {generations}",
                )

    def test_compact_later_rings_keep_a_visible_generation_three_label(self):
        for paper_size in (PaperSize.A3, PaperSize.A4, PaperSize.A5):
            root = branch(
                "g1",
                1,
                children=(
                    branch(
                        "g2",
                        2,
                        children=(branch("g3", 3),),
                    ),
                ),
            )
            chart = calculate_canvas(
                PaperRegion(paper_size, Orientation.LANDSCAPE),
                ancestor_generations=5,
                descendant_generations=3,
            )
            scene = layout_descendants(
                chart,
                (root,),
                name_lookup={
                    "g1": "Generation One",
                    "g2": "Generation Two",
                    "g3": "G3",
                }.__getitem__,
                dates_lookup=lambda _handle: "",
            )
            _later_inner, later_outer = _descendant_ring_bounds(
                chart.descendant_inner_radius_mm,
                chart.descendant_outer_radius_mm,
                3,
                3,
            )
            later_labels = [
                node
                for node in scene.children
                if isinstance(node, SceneText) and node.content == "G3"
            ]

            self.assertGreaterEqual(
                later_outer - _later_inner,
                8.0 - 1e-3,
                msg=f"{paper_size.value} generation-three ring lost its label lane",
            )
            self.assertEqual(
                len(later_labels),
                1,
                msg=f"{paper_size.value} dropped the generation-three label",
            )

    def test_two_generation_direct_labels_clear_portrait_medallions(self):
        for paper_size in (
            PaperSize.A0,
            PaperSize.A1,
            PaperSize.A2,
            PaperSize.A3,
            PaperSize.A4,
            PaperSize.A5,
        ):
            direct_child = branch(
                "child",
                1,
                children=(branch("grandchild", 2),),
                spouse="spouse",
            )
            chart = calculate_canvas(
                PaperRegion(paper_size, Orientation.LANDSCAPE),
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
                portrait_lookup=lambda _handle: "data:image/png;base64,AA==",
            )
            couple_label = next(
                node
                for node in scene.children
                if isinstance(node, ScenePathText)
                and node.content == "Child × Spouse"
            )
            label_radius = path_radius(
                couple_label.path,
                chart.center_cx_mm,
                chart.center_cy_mm,
            )
            medallions = [
                node for node in scene.children if isinstance(node, SceneCircle)
            ]
            if medallions:
                medallion_outer_radius = max(
                    math.hypot(
                        node.cx - chart.center_cx_mm,
                        node.cy - chart.center_cy_mm,
                    )
                    + node.r
                    for node in medallions
                )
                self.assertGreaterEqual(
                    label_radius - couple_label.font_size * 0.50,
                    medallion_outer_radius
                    + _MEDALLION_EDGE_CLEARANCE_MM
                    - 1e-3,
                    msg=f"{paper_size.value} label crosses a direct-child portrait",
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

    def test_two_line_intermediate_couples_keep_person_first_on_both_halves(self):
        def intermediate(prefix):
            return branch(
                f"{prefix}-child",
                2,
                children=(branch(f"{prefix}-grandchild", 3),),
                spouse=f"{prefix}-spouse",
            )

        right_branch = branch(
            "right-root",
            1,
            children=(intermediate("right"),),
        )
        left_branch = branch(
            "left-root",
            1,
            children=(intermediate("left"),),
        )
        scene = layout_descendants(
            canvas(3),
            (right_branch, left_branch),
            name_lookup=lambda handle: handle,
            dates_lookup=lambda _handle: "",
        )
        labels = {
            node.content: node
            for node in scene.children
            if isinstance(node, SceneText)
        }

        for prefix in ("right", "left"):
            self.assertLess(
                labels[f"{prefix}-child"].y,
                labels[f"× {prefix}-spouse"].y,
                msg=f"{prefix} half puts spouse above the individual",
            )

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
            glyph_half_height = couple_label.font_size * 0.50
            self.assertGreaterEqual(
                radius - glyph_half_height,
                chart.center_radius_mm + _RING_GAP_MM - 1e-3,
                msg=f"{name} label glyphs intersect the center circle",
            )
            self.assertLessEqual(
                radius + glyph_half_height,
                ring_outer - _RING_GAP_MM + 1e-3,
                msg=f"{name} label glyphs leave the direct-child ring",
            )


if __name__ == "__main__":
    unittest.main()
