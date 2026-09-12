from __future__ import annotations

import unittest

from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import calculate_canvas, layout_descendants
from TwoWayFanChart.model import (
    DescendantBranch,
    PersonNode,
    ScenePathText,
    SceneText,
    UnionBranch,
)


def branch(
    handle: str,
    generation: int,
    *,
    children: tuple[DescendantBranch, ...] = (),
    spouse_handles: tuple[str, ...] = (),
    children_by_union: tuple[tuple[DescendantBranch, ...], ...] = (),
) -> DescendantBranch:
    unions = tuple(
        UnionBranch(
            family_handle=f"family-{handle}-{index}",
            spouse_handle=spouse_handle,
            child_handles=tuple(child.person.handle for child in union_children),
            child_relations=("birth",) * len(union_children),
        )
        for index, (spouse_handle, union_children) in enumerate(
            zip(spouse_handles, children_by_union)
        )
    )
    return DescendantBranch(
        position_id=f"descendant-{handle}",
        person=PersonNode(handle, handle.upper()),
        generation=generation,
        unions=unions,
        children=children,
        children_by_union=children_by_union,
    )


class DescendantCoupleOrderTests(unittest.TestCase):
    def test_oldest_source_child_is_rendered_left_of_youngest(self):
        oldest = branch("oldest", 1)
        youngest = branch("youngest", 1)
        chart = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=1,
        )

        scene = layout_descendants(
            chart,
            (oldest, youngest),
            name_lookup=lambda handle: handle,
            dates_lookup=lambda _handle: "",
        )
        labels = {
            node.content: node
            for node in scene.children
            if isinstance(node, ScenePathText)
            and node.content in {"oldest", "youngest"}
        }

        def path_midpoint_x(node):
            parts = node.path.split()
            return (float(parts[1]) + float(parts[-2])) / 2.0

        self.assertLess(path_midpoint_x(labels["oldest"]), chart.center_cx_mm)
        self.assertGreater(path_midpoint_x(labels["youngest"]), chart.center_cx_mm)

    def test_nested_source_children_keep_oldest_on_left(self):
        oldest = branch("oldest-child", 2)
        youngest = branch("youngest-child", 2)
        root = branch("root", 1, children=(oldest, youngest))
        chart = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=2,
        )

        scene = layout_descendants(
            chart,
            (root,),
            name_lookup=lambda handle: handle,
            dates_lookup=lambda _handle: "",
        )
        labels = {
            node.content: node
            for node in scene.children
            if isinstance(node, SceneText)
            and node.content in {"oldest-child", "youngest-child"}
        }

        self.assertLess(labels["oldest-child"].x, labels["youngest-child"].x)

    def test_left_side_stacked_multi_union_keeps_person_above_spouse(self):
        first_union_children = tuple(
            branch(f"first-child-{index}", 3)
            for index in range(3)
        )
        second_union_child = branch("second-child", 3)
        target = branch(
            "target",
            2,
            children=first_union_children + (second_union_child,),
            spouse_handles=("spouse-a", "spouse-b"),
            children_by_union=(
                first_union_children,
                (second_union_child,),
            ),
        )
        siblings = tuple(
            branch(f"sibling-{index}", 2)
            for index in range(75)
        )
        root = branch("root", 1, children=siblings + (target,))
        labels = {
            "target": "Target Person",
            "spouse-a": "Spouse A",
            "spouse-b": "Spouse B",
        }
        chart = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=3,
        )

        scene = layout_descendants(
            chart,
            (root,),
            name_lookup=lambda handle: labels.get(handle, handle),
            dates_lookup=lambda _handle: "",
        )
        couple_labels = [
            node
            for node in scene.children
            if isinstance(node, SceneText)
            and node.content
            in {
                "Target Person",
                "× Spouse A",
                "× Spouse B",
            }
        ]
        target_labels = [
            node for node in couple_labels if node.content == "Target Person"
        ]
        spouse_labels = [
            node
            for node in couple_labels
            if node.content.startswith("× Spouse")
        ]

        self.assertEqual(len(target_labels), 2)
        self.assertEqual(len(spouse_labels), 2)
        for target_label, spouse_label in zip(target_labels, spouse_labels):
            self.assertLess(target_label.y, spouse_label.y)


if __name__ == "__main__":
    unittest.main()
