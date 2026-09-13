import ast
import math
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import (
    _DESCENDANT_FIRST_GEN_LINE_GAP_MM,
    _DESCENDANT_CONTINUATION_DOT_OFFSET_MM,
    _DESCENDANT_CONTINUATION_DOT_RADIUS_MM,
    _DESCENDANT_CONTINUATION_DOT_SPACING_MM,
    _DESCENDANT_MEDALLION_TARGET_RATIO,
    _DESCENDANT_OUTER_RADIUS_RATIO,
    _DESC_TOTAL_SWEEP,
    _allocate_descendant_union_cells,
    _descendant_ring_bounds,
    _MIN_INITIALS_MEDALLION_RADIUS_MM,
    _allocate_descendant_branches_by_demand,
    calculate_canvas,
    layout_ancestors,
    layout_descendants,
    layout_titles,
)
from TwoWayFanChart.model import (
    DescendantBranch,
    PersonNode,
    SceneCircle,
    SceneImage,
    ScenePage,
    SceneSector,
    ScenePathText,
    SceneText,
    UnionBranch,
)
from TwoWayFanChart.styles import CONTINUATION_DOT_FILL, TEXT_DARK, TEXT_GREY
from TwoWayFanChart.render_svg import render_svg


def person(handle: str) -> PersonNode:
    return PersonNode(handle=handle, gramps_id=handle.upper())


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
        person=person(handle),
        generation=generation,
        unions=unions,
        children=children,
    )


def a0_canvas(descendant_generations: int = 4):
    return calculate_canvas(
        PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
        ancestor_generations=5,
        descendant_generations=descendant_generations,
    )


def _path_radius(path: str, cx: float, cy: float) -> float:
    """Recover the radius of the first point of an SVG arc path."""
    _move, x_text, y_text, *_rest = path.split()
    return math.hypot(float(x_text) - cx, float(y_text) - cy)


class DescendantReadabilityTests(unittest.TestCase):
    def test_continuation_dots_use_dark_gray_fill(self):
        self.assertEqual(CONTINUATION_DOT_FILL, TEXT_DARK)
        self.assertEqual(CONTINUATION_DOT_FILL, "#4A4A4A")

    def test_descendant_quarter_is_compact_relative_to_ancestor_fan(self):
        canvas = a0_canvas(descendant_generations=1)

        self.assertAlmostEqual(
            canvas.descendant_outer_radius_mm,
            canvas.ancestor_outer_radius_mm * 0.76,
            places=6,
        )
        self.assertAlmostEqual(_DESCENDANT_OUTER_RADIUS_RATIO, 0.76, places=6)
        self.assertLess(
            canvas.descendant_outer_radius_mm,
            canvas.ancestor_outer_radius_mm,
        )

    def test_section_titles_are_not_rendered(self):
        canvas = a0_canvas(descendant_generations=1)
        scene = layout_titles(
            canvas,
            ancestor_generations=2,
            descendant_generations=1,
        )

        self.assertEqual(scene.children, ())

    def test_ancestor_portrait_medallion_is_larger_than_v128_generation_two(self):
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=2,
            descendant_generations=1,
        )
        scene = layout_ancestors(
            canvas,
            (
                ("ancestor-a-1-0", "Parent, Jeanne", "1800–1870", "portrait-a", False),
                ("ancestor-a-2-0", "Grandparent, Louise", "1770–1840", "portrait-b", False),
            ),
        )

        images = [child for child in scene.children if isinstance(child, SceneImage)]

        self.assertEqual(len(images), 2)
        # v1.2.8 rendered the G2 portrait at 20/600 of the fan radius.
        self.assertGreater(images[-1].r, canvas.ancestor_outer_radius_mm * (20 / 600))

    def test_single_generation_descendants_use_outer_crown_and_radial_lanes(self):
        root = branch("root", 1, spouse="root-spouse")
        canvas = a0_canvas(descendant_generations=1)
        scene = layout_descendants(
            canvas,
            (root,),
            name_lookup=lambda handle: {
                "root": "Alexandre Théodore de la Rochefoucauld",
                "root-spouse": "Marie Louise de Montmorency",
            }[handle],
            dates_lookup=lambda handle: "1800–1880" if handle == "root" else "1805–1890",
            portrait_lookup=lambda _handle: "data:image/svg+xml;base64,PHN2Zy8+",
        )

        circles = [child for child in scene.children if isinstance(child, SceneCircle)]
        circle_distances = [
            math.hypot(circle.cx - canvas.center_cx_mm, circle.cy - canvas.center_cy_mm)
            for circle in circles
        ]
        paths = [child for child in scene.children if isinstance(child, ScenePathText)]
        path_distances = [
            _path_radius(path.path, canvas.center_cx_mm, canvas.center_cy_mm)
            for path in paths
        ]

        self.assertEqual(len(circles), 2)
        self.assertGreater(min(circle_distances), canvas.descendant_outer_radius_mm * 0.9)
        self.assertGreater(max(path_distances), canvas.descendant_outer_radius_mm * 0.81)
        self.assertGreater(
            max(path_distances) - min(path_distances),
            canvas.descendant_outer_radius_mm * 0.30,
        )

    def test_first_generation_dense_text_lines_have_readable_radial_gaps(self):
        root = branch(
            "root",
            1,
            children=(
                branch(
                    "child",
                    2,
                    children=(
                        branch(
                            "grandchild",
                            3,
                            children=(branch("great-grandchild", 4),),
                        ),
                    ),
                ),
            ),
            spouse="root-spouse",
        )
        canvas = a0_canvas()
        labels = {
            "root": "Jacqueline Berloty",
            "root-spouse": "Jean Berloty",
            "child": "Middle Person",
            "grandchild": "Last Person",
            "great-grandchild": "Last Person",
        }
        dates = {
            "root": "1908–1981",
            "root-spouse": "1906–1980",
            "child": "1930–2000",
            "grandchild": "1960–2020",
            "great-grandchild": "1980–2020",
        }
        scene = layout_descendants(
            canvas,
            (root,),
            name_lookup=labels.__getitem__,
            dates_lookup=dates.__getitem__,
        )

        first_generation = [
            (
                node.content,
                _path_radius(
                    node.path,
                    canvas.center_cx_mm,
                    canvas.center_cy_mm,
                ),
            )
            for node in scene.children
            if isinstance(node, ScenePathText)
            and node.content in {
                "Jacqueline Berloty",
                "1908–1981",
                "× Jean Berloty",
                "1906–1980",
            }
        ]

        self.assertCountEqual(
            [content for content, _radius in first_generation],
            {
                "Jacqueline Berloty",
                "1908–1981",
                "× Jean Berloty",
                "1906–1980",
            },
        )
        self.assertEqual(len(first_generation), 4)
        radii = sorted(radius for _content, radius in first_generation)
        self.assertTrue(
            all(
                later - earlier >= _DESCENDANT_FIRST_GEN_LINE_GAP_MM - 1e-3
                for earlier, later in zip(radii, radii[1:])
            ),
            msg=f"first-generation line radii are too close: {radii}",
        )

    def test_first_generation_text_spacing_handles_one_and_two_lines(self):
        root = branch(
            "root",
            1,
            children=(branch("child", 2, children=(branch("grandchild", 3),)),),
        )
        canvas = a0_canvas(descendant_generations=3)
        labels = {
            "root": "GEN1 Root",
            "child": "GEN2 Child",
            "grandchild": "GEN3 Grandchild",
        }

        for date_label, expected in (
            ("", ["GEN1 Root"]),
            ("1908–1981", ["GEN1 Root", "1908–1981"]),
        ):
            scene = layout_descendants(
                canvas,
                (root,),
                name_lookup=labels.__getitem__,
                dates_lookup=lambda _handle: date_label,
            )
            paths = [
                node for node in scene.children
                if isinstance(node, ScenePathText)
                and node.content in set(expected)
            ]

            self.assertCountEqual([node.content for node in paths], expected)
            self.assertEqual(len(paths), len(expected))
            if len(paths) == 2:
                radii = sorted(
                    _path_radius(
                        node.path,
                        canvas.center_cx_mm,
                        canvas.center_cy_mm,
                    )
                    for node in paths
                )
                self.assertGreaterEqual(
                    radii[1] - radii[0],
                    _DESCENDANT_FIRST_GEN_LINE_GAP_MM - 1e-3,
                )

    def test_first_generation_fallback_avoids_overlapping_lines_on_small_pages(self):
        root = branch(
            "root",
            1,
            children=(
                branch(
                    "child",
                    2,
                    children=(
                        branch(
                            "grandchild",
                            3,
                            children=(branch("great-grandchild", 4),),
                        ),
                    ),
                ),
            ),
            spouse="root-spouse",
        )
        labels = {
            "root": "GEN1 Root",
            "root-spouse": "GEN1 Spouse",
            "child": "GEN2 Child",
            "grandchild": "GEN3 Grandchild",
            "great-grandchild": "GEN4 Great Grandchild",
        }
        dates = {
            handle: "1908–1981"
            for handle in labels
        }
        regions = (
            ("A5", PaperRegion(PaperSize.A5, Orientation.LANDSCAPE)),
            ("A4", PaperRegion(PaperSize.A4, Orientation.LANDSCAPE)),
            (
                "custom",
                PaperRegion(
                    PaperSize.CUSTOM,
                    Orientation.LANDSCAPE,
                    custom_width_mm=160,
                    custom_height_mm=160,
                ),
            ),
        )

        for name, region in regions:
            canvas = calculate_canvas(
                region,
                ancestor_generations=5,
                descendant_generations=4,
            )
            scene = layout_descendants(
                canvas,
                (root,),
                name_lookup=labels.__getitem__,
                dates_lookup=dates.__getitem__,
            )
            paths = [
                node for node in scene.children
                if isinstance(node, ScenePathText)
                and "GEN1" in node.content
            ]

            self.assertEqual(
                len(paths),
                1,
                msg=f"{name} kept overlapping first-generation lines",
            )
            self.assertIn("GEN1 Root", paths[0].content)
            self.assertIn("GEN1 Spouse", paths[0].content)
            self.assertNotIn("1908", paths[0].content)

    def test_descendant_arc_labels_are_foreground_of_later_generation_sectors(self):
        root = branch(
            "root",
            1,
            children=(branch("child", 2, children=(branch("grandchild", 3),)),),
            spouse="root-spouse",
        )
        scene = layout_descendants(
            calculate_canvas(
                PaperRegion(PaperSize.A5, Orientation.LANDSCAPE),
                ancestor_generations=5,
                descendant_generations=3,
            ),
            (root,),
            name_lookup={
                "root": "GEN1 Root",
                "root-spouse": "GEN1 Spouse",
                "child": "GEN2 Child",
                "grandchild": "GEN3 Grandchild",
            }.__getitem__,
            dates_lookup=lambda _handle: "1908–1981",
        )
        sector_indexes = [
            index for index, node in enumerate(scene.children)
            if isinstance(node, SceneSector)
        ]
        arc_label_indexes = [
            index for index, node in enumerate(scene.children)
            if isinstance(node, ScenePathText)
        ]

        self.assertTrue(sector_indexes)
        self.assertTrue(arc_label_indexes)
        self.assertGreater(min(arc_label_indexes), max(sector_indexes))

    def test_single_generation_descendant_portraits_are_larger_than_previous_target(self):
        root = branch("root", 1, spouse="root-spouse")
        canvas = a0_canvas(descendant_generations=1)
        scene = layout_descendants(
            canvas,
            (root,),
            name_lookup=lambda handle: {
                "root": "Alexandre Théodore de la Rochefoucauld",
                "root-spouse": "Marie Louise de Montmorency",
            }[handle],
            dates_lookup=lambda _handle: "1800–1880",
            portrait_lookup=lambda _handle: "data:image/svg+xml;base64,PHN2Zy8+",
        )

        circles = [child for child in scene.children if isinstance(child, SceneCircle)]

        self.assertEqual(len(circles), 2)
        # The preceding maquette targeted 24/600. This iteration raises the
        # target again while the compact outer radius is applied independently.
        new_target = canvas.descendant_outer_radius_mm * _DESCENDANT_MEDALLION_TARGET_RATIO * 1.1
        previous_target = (
            canvas.ancestor_outer_radius_mm * 0.80 * (24 / 600) * 1.1
        )
        self.assertGreater(min(circle.r for circle in circles), previous_target)
        self.assertGreaterEqual(min(circle.r for circle in circles), new_target - 1e-6)

    def test_deep_demand_gets_more_angle_than_shallow_sibling(self):
        deep_leaves = tuple(branch(f"deep-leaf-{index}", 3) for index in range(20))
        deep = branch(
            "deep",
            1,
            children=(branch("deep-child", 2, children=deep_leaves),),
        )
        shallow = branch(
            "shallow",
            1,
            children=tuple(branch(f"shallow-{index}", 2) for index in range(4)),
        )

        allocations = _allocate_descendant_branches_by_demand(
            (deep, shallow),
            start_angle=96.0,
            total_sweep=_DESC_TOTAL_SWEEP,
        )

        self.assertGreater(allocations[0].sweep_angle, allocations[1].sweep_angle)
        self.assertAlmostEqual(
            sum(allocation.sweep_angle for allocation in allocations),
            _DESC_TOTAL_SWEEP,
            places=6,
        )
        self.assertAlmostEqual(allocations[1].start_angle, allocations[0].start_angle + allocations[0].sweep_angle)

    def test_dense_layout_never_emits_point_sized_medallions(self):
        leaves = tuple(branch(f"leaf-{index}", 4) for index in range(36))
        grandchildren = tuple(
            branch(
                f"grandchild-{index}",
                3,
                children=leaves[index * 6 : (index + 1) * 6],
                spouse=f"grandchild-spouse-{index}",
            )
            for index in range(6)
        )
        children = tuple(
            branch(
                f"child-{index}",
                2,
                children=grandchildren[index * 2 : (index + 1) * 2],
                spouse=f"child-spouse-{index}",
            )
            for index in range(3)
        )
        root = branch("root", 1, children=children, spouse="root-spouse")

        scene = layout_descendants(
            a0_canvas(),
            (root,),
            name_lookup=lambda handle: handle.replace("-", " ").title(),
            dates_lookup=lambda _handle: "1900–1980",
        )
        circles = [node for node in scene.children if isinstance(node, SceneCircle)]

        self.assertTrue(circles)
        self.assertGreaterEqual(
            min(circle.r for circle in circles),
            _MIN_INITIALS_MEDALLION_RADIUS_MM,
        )

    def test_intermediate_and_last_generation_couples_use_radial_text(self):
        last = branch("last", 3, spouse="last-spouse")
        middle = branch("middle", 2, children=(last,), spouse="middle-spouse")
        root = branch("root", 1, children=(middle,), spouse="root-spouse")
        labels = {
            "root": "Root Person",
            "root-spouse": "Root Spouse",
            "middle": "Middle Person",
            "middle-spouse": "Middle Spouse",
            "last": "Last Person",
            "last-spouse": "Last Spouse",
        }

        scene = layout_descendants(
            a0_canvas(descendant_generations=3),
            (root,),
            name_lookup=labels.__getitem__,
            dates_lookup=lambda _handle: "1900–1980",
        )
        straight_nodes = [node for node in scene.children if isinstance(node, SceneText)]
        curved_nodes = [node for node in scene.children if isinstance(node, ScenePathText)]
        straight = [node.content for node in straight_nodes]
        curved = [node.content for node in curved_nodes]

        self.assertTrue(any("Middle Spouse" in content for content in straight))
        self.assertFalse(any("Middle Spouse" in content for content in curved))
        self.assertTrue(any("Last Spouse" in content for content in straight))
        self.assertFalse(any("Last Spouse" in content for content in curved))
        spouse_nodes = [
            node
            for node in (*straight_nodes, *curved_nodes)
            if "Spouse" in node.content
        ]
        self.assertTrue(spouse_nodes)
        self.assertTrue(all(node.fill == TEXT_DARK for node in spouse_nodes))
        date_nodes = [
            node
            for node in (*straight_nodes, *curved_nodes)
            if "1900–1980" in node.content
        ]
        self.assertTrue(date_nodes)
        self.assertTrue(all(node.fill == TEXT_GREY for node in date_nodes))

    def test_descendant_medallions_stop_before_generation_two(self):
        last = branch("last", 3)
        middle = branch("middle", 2, children=(last,), spouse="middle-spouse")
        root = branch("root", 1, children=(middle,), spouse="root-spouse")
        portrait_calls = []

        def portrait_lookup(handle):
            portrait_calls.append(handle)
            return f"data:image/png;base64,{handle}"

        scene = layout_descendants(
            a0_canvas(descendant_generations=3),
            (root,),
            name_lookup=lambda handle: handle.replace("-", " ").title(),
            dates_lookup=lambda _handle: "1900–1980",
            portrait_lookup=portrait_lookup,
        )
        circles = [node for node in scene.children if isinstance(node, SceneCircle)]

        self.assertEqual(len(circles), 2)  # root person + root spouse only
        self.assertEqual(
            portrait_calls,
            ["root", "root-spouse"],
        )

    def test_narrow_couple_label_keeps_both_names_dark(self):
        roots = tuple(
            branch(
                f"root-{index}",
                1,
                children=(
                    branch(
                        f"child-{index}",
                        2,
                        children=(branch(f"leaf-{index}", 3),),
                        spouse=f"child-spouse-{index}",
                    ),
                ),
                spouse=f"root-spouse-{index}",
            )
            for index in range(64)
        )
        scene = layout_descendants(
            a0_canvas(descendant_generations=4),
            roots,
            name_lookup=lambda handle: handle,
            dates_lookup=lambda _handle: "",
        )
        compact = [
            node
            for node in scene.children
            if isinstance(node, SceneText) and " × " in node.content
        ]

        self.assertTrue(compact)
        self.assertTrue(all(node.fill == TEXT_DARK for node in compact))

    def test_pipeline_preserves_full_descendant_name_for_layout(self):
        source = Path("TwoWayFanChart/pipeline.py").read_text(encoding="utf-8")
        module = ast.parse(source)
        function = next(
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_descendant_short_label"
        )
        isolated = ast.Module(body=[function], type_ignores=[])
        ast.fix_missing_locations(isolated)
        namespace = {"_mockup_name_order": lambda value: value}
        exec(compile(isolated, "pipeline.py", "exec"), namespace)

        label = "Alexandre Théodore de la Rochefoucauld"
        self.assertEqual(namespace["_descendant_short_label"](label, 4), label)

    def test_last_generation_continuation_emits_three_radial_dots(self):
        root = DescendantBranch(
            "last-visible",
            person("last-visible"),
            1,
            (
                UnionBranch(
                    "family-last-visible",
                    "last-visible-spouse",
                    ("not-rendered-child",),
                    ("birth",),
                ),
            ),
            (),
        )
        canvas = a0_canvas(descendant_generations=1)

        scene = layout_descendants(
            canvas,
            (root,),
            name_lookup=lambda handle: {
                "last-visible": "Last Visible",
                "last-visible-spouse": "Visible Spouse",
            }[handle],
            dates_lookup=lambda _handle: "",
            configured_generation_limit=1,
        )
        dots = [
            node
            for node in scene.children
            if isinstance(node, SceneCircle)
            and node.fill == CONTINUATION_DOT_FILL
            and math.isclose(node.r, _DESCENDANT_CONTINUATION_DOT_RADIUS_MM)
        ]

        self.assertEqual(len(dots), 3)
        _ring_inner, ring_outer = _descendant_ring_bounds(
            canvas.descendant_inner_radius_mm,
            canvas.descendant_outer_radius_mm,
            1,
            1,
        )
        radii = sorted(
            math.hypot(
                dot.cx - canvas.center_cx_mm,
                dot.cy - canvas.center_cy_mm,
            )
            for dot in dots
        )
        self.assertGreaterEqual(
            radii[0] - _DESCENDANT_CONTINUATION_DOT_RADIUS_MM,
            ring_outer
            + _DESCENDANT_CONTINUATION_DOT_OFFSET_MM
            - _DESCENDANT_CONTINUATION_DOT_RADIUS_MM
            - 1e-6,
        )
        self.assertEqual(
            [
                round(radii[index + 1] - radii[index], 9)
                for index in range(len(radii) - 1)
            ],
            [round(_DESCENDANT_CONTINUATION_DOT_SPACING_MM, 9)] * 2,
        )

        radial_cross_products = [
            (
                dot.cx - canvas.center_cx_mm,
                dot.cy - canvas.center_cy_mm,
            )
            for dot in dots
        ]
        first_x, first_y = radial_cross_products[0]
        for x, y in radial_cross_products[1:]:
            self.assertAlmostEqual(first_x * y - first_y * x, 0.0, places=6)

    def test_terminal_last_generation_does_not_emit_continuation_dots(self):
        root = branch("terminal", 1, spouse="terminal-spouse")
        scene = layout_descendants(
            a0_canvas(descendant_generations=1),
            (root,),
            name_lookup=lambda handle: handle,
            dates_lookup=lambda _handle: "",
        )

        self.assertFalse(
            any(
                isinstance(node, SceneCircle)
                and node.fill == CONTINUATION_DOT_FILL
                and math.isclose(node.r, _DESCENDANT_CONTINUATION_DOT_RADIUS_MM)
                for node in scene.children
            )
        )

    def test_unresolved_child_before_configured_limit_does_not_emit_dots(self):
        root = DescendantBranch(
            "unresolved-before-limit",
            person("unresolved-before-limit"),
            1,
            (
                UnionBranch(
                    "unresolved-family",
                    "unresolved-spouse",
                    ("missing-child",),
                    ("birth",),
                ),
            ),
            (),
        )
        scene = layout_descendants(
            a0_canvas(descendant_generations=3),
            (root,),
            name_lookup=lambda handle: handle,
            dates_lookup=lambda _handle: "",
            configured_generation_limit=3,
        )

        self.assertFalse(
            any(
                isinstance(node, SceneCircle)
                and node.fill == CONTINUATION_DOT_FILL
                and math.isclose(node.r, _DESCENDANT_CONTINUATION_DOT_RADIUS_MM)
                for node in scene.children
            )
        )

    def test_continuation_dots_do_not_create_section_titles(self):
        root = DescendantBranch(
            "title-clearance-last-visible",
            person("title-clearance-last-visible"),
            1,
            (
                UnionBranch(
                    "title-clearance-family",
                    "title-clearance-spouse",
                    ("not-rendered-child",),
                    ("birth",),
                ),
            ),
            (),
        )
        canvas = a0_canvas(descendant_generations=1)
        descendant_scene = layout_descendants(
            canvas,
            (root,),
            name_lookup=lambda handle: handle,
            dates_lookup=lambda _handle: "",
        )
        title_scene = layout_titles(
            canvas,
            ancestor_generations=0,
            descendant_generations=1,
        )
        dots = [
            node
            for node in descendant_scene.children
            if isinstance(node, SceneCircle)
            and node.fill == CONTINUATION_DOT_FILL
            and math.isclose(node.r, _DESCENDANT_CONTINUATION_DOT_RADIUS_MM)
        ]
        self.assertEqual(len(dots), 3)
        self.assertFalse(
            any(isinstance(node, SceneText) for node in title_scene.children)
        )

    def test_continuation_dots_follow_the_populated_last_generation_union(self):
        root = DescendantBranch(
            "multi-union-last-visible",
            person("multi-union-last-visible"),
            1,
            (
                UnionBranch(
                    "family-with-continuation",
                    "spouse-with-continuation",
                    ("not-rendered-child",),
                    ("birth",),
                ),
                UnionBranch(
                    "terminal-family",
                    "terminal-spouse",
                    (),
                    (),
                ),
            ),
            (),
            children_by_union=((), ()),
        )
        canvas = a0_canvas(descendant_generations=1)
        scene = layout_descendants(
            canvas,
            (root,),
            name_lookup=lambda handle: handle,
            dates_lookup=lambda _handle: "",
        )
        dots = [
            node
            for node in scene.children
            if isinstance(node, SceneCircle)
            and node.fill == CONTINUATION_DOT_FILL
            and math.isclose(node.r, _DESCENDANT_CONTINUATION_DOT_RADIUS_MM)
        ]
        self.assertEqual(len(dots), 3)

        cells = _allocate_descendant_union_cells(
            root,
            start_angle=96.0,
            total_sweep=_DESC_TOTAL_SWEEP,
        )
        continuation_cell = cells[0]
        expected_angle = (
            continuation_cell.start_angle + continuation_cell.sweep_angle / 2.0
        )
        for dot in dots:
            dot_angle = math.degrees(
                math.atan2(
                    dot.cx - canvas.center_cx_mm,
                    -(dot.cy - canvas.center_cy_mm),
                )
            ) % 360.0
            self.assertAlmostEqual(dot_angle, expected_angle % 360.0, places=6)

    def test_svg_serializes_continuation_dots_as_filled_circles(self):
        root = DescendantBranch(
            "svg-last-visible",
            person("svg-last-visible"),
            1,
            (
                UnionBranch(
                    "svg-family",
                    "svg-spouse",
                    ("svg-child-not-shown",),
                    ("birth",),
                ),
            ),
            (),
        )
        canvas = a0_canvas(descendant_generations=1)
        scene = layout_descendants(
            canvas,
            (root,),
            name_lookup=lambda handle: handle,
            dates_lookup=lambda _handle: "",
        )
        svg = render_svg(
            ScenePage(canvas.page_width_mm, canvas.page_height_mm),
            scene,
        )

        svg_root = ET.fromstring(svg)
        dot_circles = [
            element
            for element in svg_root.iter()
            if element.tag.rsplit("}", 1)[-1] == "circle"
            and element.attrib.get("fill") == CONTINUATION_DOT_FILL
        ]
        self.assertEqual(len(dot_circles), 3)
        self.assertEqual([dot.attrib.get("r") for dot in dot_circles], ["0.55"] * 3)


if __name__ == "__main__":
    unittest.main()
