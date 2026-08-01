import ast
import math
import unittest
from pathlib import Path

from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import (
    _DESC_TOTAL_SWEEP,
    _MIN_INITIALS_MEDALLION_RADIUS_MM,
    _allocate_descendant_branches_by_demand,
    calculate_canvas,
    layout_descendants,
)
from TwoWayFanChart.model import (
    DescendantBranch,
    PersonNode,
    SceneCircle,
    ScenePathText,
    SceneText,
    UnionBranch,
)
from TwoWayFanChart.styles import TEXT_DARK, TEXT_GREY


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


class DescendantReadabilityTests(unittest.TestCase):
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

    def test_intermediate_couple_uses_radial_text_and_last_generation_has_no_spouse(self):
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
        self.assertFalse(any("Last Spouse" in content for content in straight + curved))
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


if __name__ == "__main__":
    unittest.main()
