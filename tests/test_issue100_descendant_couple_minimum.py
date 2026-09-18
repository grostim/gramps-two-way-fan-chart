"""Regression tests for issue #100 descendant angular allocation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from TwoWayFanChart.layout import (  # noqa: E402
    _DESC_MIN_SWEEP_BY_GENERATION,
    _allocate_descendant_branches_by_demand,
    _allocate_descendant_union_cells,
    calculate_canvas,
    layout_descendants,
)
from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize  # noqa: E402
from TwoWayFanChart.model import (  # noqa: E402
    DescendantBranch,
    PersonNode,
    SceneText,
    UnionBranch,
)


def branch(handle: str, *, generation: int, spouse: bool) -> DescendantBranch:
    unions = (
        UnionBranch(
            family_handle=f"family-{handle}",
            spouse_handle=f"spouse-{handle}" if spouse else None,
            child_handles=(),
            child_relations=(),
        ),
    )
    return DescendantBranch(
        position_id=f"descendant-{handle}",
        person=PersonNode(handle, handle),
        generation=generation,
        unions=unions,
        children=(),
    )


class Issue100DescendantMinimumTests(unittest.TestCase):
    def test_gen3_couples_keep_floor_when_singletons_must_shrink(self):
        branches = tuple(
            branch(f"couple-{index}", generation=3, spouse=True)
            for index in range(3)
        ) + tuple(
            branch(f"single-{index}", generation=3, spouse=False)
            for index in range(7)
        )

        allocations = _allocate_descendant_branches_by_demand(
            branches,
            start_angle=96.0,
            total_sweep=10.0,
        )
        couple_floor = _DESC_MIN_SWEEP_BY_GENERATION[3]
        couple_sweeps = [
            allocation.sweep_angle
            for branch_item, allocation in zip(branches, allocations)
            if branch_item.unions[0].spouse_handle
        ]
        single_sweeps = [
            allocation.sweep_angle
            for branch_item, allocation in zip(branches, allocations)
            if not branch_item.unions[0].spouse_handle
        ]

        self.assertTrue(couple_sweeps)
        self.assertTrue(single_sweeps)
        self.assertGreaterEqual(min(couple_sweeps), couple_floor - 1e-9)
        self.assertLess(max(single_sweeps), couple_floor)
        self.assertAlmostEqual(
            sum(allocation.sweep_angle for allocation in allocations),
            10.0,
            places=9,
        )

    def test_multi_union_gen3_branch_reserves_each_couple_cell(self):
        multi = DescendantBranch(
            "descendant-multi",
            PersonNode("multi", "Multi"),
            3,
            (
                UnionBranch("family-a", "spouse-a", (), ()),
                UnionBranch("family-b", "spouse-b", (), ()),
            ),
            (),
        )
        singletons = tuple(
            branch(f"single-{index}", generation=3, spouse=False)
            for index in range(2)
        )
        allocations = _allocate_descendant_branches_by_demand(
            (multi,) + singletons,
            start_angle=96.0,
            total_sweep=5.0,
        )
        couple_floor = _DESC_MIN_SWEEP_BY_GENERATION[3]
        cells = _allocate_descendant_union_cells(
            multi,
            start_angle=allocations[0].start_angle,
            total_sweep=allocations[0].sweep_angle,
        )

        self.assertEqual(len(cells), 2)
        self.assertGreaterEqual(
            min(cell.sweep_angle for cell in cells),
            couple_floor - 1e-9,
        )

    def test_promoted_multi_union_floor_survives_equal_demand_fallback(self):
        multi = DescendantBranch(
            "descendant-multi-equal",
            PersonNode("multi-equal", "Multi equal"),
            3,
            (
                UnionBranch("family-a-equal", "spouse-a-equal", (), ()),
                UnionBranch("family-b-equal", "spouse-b-equal", (), ()),
            ),
            (),
        )
        singletons = tuple(
            branch(f"equal-single-{index}", generation=3, spouse=False)
            for index in range(3)
        )
        allocations = _allocate_descendant_branches_by_demand(
            (multi,) + singletons,
            start_angle=96.0,
            total_sweep=11.0,
        )
        cells = _allocate_descendant_union_cells(
            multi,
            start_angle=allocations[0].start_angle,
            total_sweep=allocations[0].sweep_angle,
        )
        couple_floor = _DESC_MIN_SWEEP_BY_GENERATION[3]

        self.assertGreaterEqual(allocations[0].sweep_angle, 2 * couple_floor)
        self.assertGreaterEqual(
            min(cell.sweep_angle for cell in cells),
            couple_floor - 1e-9,
        )

    def test_infeasible_couple_floor_never_erases_singletons(self):
        demanding_children = tuple(
            DescendantBranch(
                f"descendant-grandchild-{index}",
                PersonNode(f"grandchild-{index}", f"Grandchild {index}"),
                4,
                (),
                (),
            )
            for index in range(10)
        )
        couple = DescendantBranch(
            "descendant-demanding-couple",
            PersonNode("demanding", "Demanding"),
            3,
            (UnionBranch("family-demanding", "spouse-demanding", tuple(
                child.person.handle for child in demanding_children
            ), tuple("birth" for _child in demanding_children)),),
            demanding_children,
        )
        singleton = branch("single", generation=3, spouse=False)
        allocations = _allocate_descendant_branches_by_demand(
            (couple, singleton),
            start_angle=96.0,
            total_sweep=5.0,
        )

        self.assertGreater(allocations[0].sweep_angle, 0.0)
        self.assertGreater(allocations[1].sweep_angle, 0.0)
        self.assertAlmostEqual(
            sum(allocation.sweep_angle for allocation in allocations),
            5.0,
            places=9,
        )

    def test_gen3_singleton_keeps_date_on_the_name_line(self):
        singles = tuple(
            branch(f"single-{index}", generation=3, spouse=False)
            for index in range(8)
        )
        parent = DescendantBranch(
            "descendant-parent",
            PersonNode("parent", "Parent"),
            2,
            (UnionBranch("family-parent", "parent-spouse", tuple(
                child.person.handle for child in singles
            ), tuple("birth" for _child in singles)),),
            singles,
        )
        root = DescendantBranch(
            "descendant-root",
            PersonNode("root", "Root"),
            1,
            (UnionBranch("family-root", "root-spouse", ("parent",), ("birth",)),),
            (parent,),
        )
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=4,
        )
        scene = layout_descendants(
            canvas,
            (root,),
            name_lookup=lambda handle: (
                "Damaris Gros" if handle == "single-0" else handle
            ),
            dates_lookup=lambda handle: "1890–1960" if handle.startswith("single-") else "",
            configured_generation_limit=4,
        )
        labels = [
            node.content for node in scene.children
            if isinstance(node, SceneText)
        ]
        self.assertIn("Damaris Gros · 1890–1960", labels)


if __name__ == "__main__":
    unittest.main()
