"""Regression tests for issue #109 content-aware descendant angles."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize  # noqa: E402
from TwoWayFanChart.layout import (  # noqa: E402
    _allocate_descendant_branches_by_demand,
    _descendant_angular_budget_profile,
    _descendant_branch_angular_budget,
    _descendant_ring_layout,
    calculate_canvas,
    layout_descendants,
)
from TwoWayFanChart.model import (  # noqa: E402
    DescendantBranch,
    PersonNode,
    SceneText,
    UnionBranch,
)


def person_branch(
    handle: str,
    generation: int,
    *,
    spouse: str | None = None,
    children: tuple[DescendantBranch, ...] = (),
) -> DescendantBranch:
    unions = (
        UnionBranch(
            family_handle=f"family-{handle}",
            spouse_handle=spouse,
            child_handles=tuple(child.person.handle for child in children),
            child_relations=tuple("birth" for _child in children),
        ),
    ) if spouse or children else ()
    return DescendantBranch(
        position_id=f"descendant-{handle}",
        person=PersonNode(handle, handle),
        generation=generation,
        unions=unions,
        children=children,
        children_by_union=(children,) if unions else (),
    )


class Issue109ContentAwareAnglesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=4,
        )
        rings, _bands = _descendant_ring_layout(
            self.canvas.descendant_inner_radius_mm,
            self.canvas.descendant_outer_radius_mm,
            4,
            show_marriages=True,
        )
        self.profile = _descendant_angular_budget_profile(rings)

    def test_a0_budgets_match_the_renderer_footprint(self):
        expected = {
            2: (2.53, 4.97),
            3: (1.81, 3.47),
            4: (1.39, 2.59),
        }
        for depth, (single_expected, couple_expected) in expected.items():
            singleton, couple = self.profile[depth]
            self.assertAlmostEqual(singleton.preferred_sweep, single_expected, delta=0.02)
            self.assertAlmostEqual(couple.preferred_sweep, couple_expected, delta=0.02)
            self.assertLess(singleton.preferred_sweep, couple.preferred_sweep)

    def test_couple_receives_more_sweep_than_same_generation_singleton(self):
        singleton = person_branch("armand", 2)
        couple = person_branch("arthur", 2, spouse="vera")
        allocations = _allocate_descendant_branches_by_demand(
            (singleton, couple),
            start_angle=96.0,
            total_sweep=6.0,
            angular_budgets=self.profile,
        )

        self.assertLess(allocations[0].sweep_angle, allocations[1].sweep_angle)
        self.assertAlmostEqual(
            sum(allocation.sweep_angle for allocation in allocations),
            6.0,
            places=9,
        )

    def test_overflow_preserves_couple_minima_before_squeezing_singletons(self):
        couples = (
            person_branch("couple-a", 3, spouse="spouse-a"),
            person_branch("couple-b", 3, spouse="spouse-b"),
        )
        dense_singleton = person_branch(
            "dense-singleton",
            3,
            children=tuple(
                person_branch(f"leaf-{index}", 4)
                for index in range(10)
            ),
        )

        allocations = _allocate_descendant_branches_by_demand(
            couples + (dense_singleton,),
            start_angle=96.0,
            total_sweep=5.0,
            angular_budgets=self.profile,
        )
        couple_minimum = self.profile[3][1].minimum_sweep

        self.assertGreaterEqual(allocations[0].sweep_angle, couple_minimum)
        self.assertGreaterEqual(allocations[1].sweep_angle, couple_minimum)
        self.assertGreater(allocations[2].sweep_angle, 0.0)
        self.assertAlmostEqual(
            sum(allocation.sweep_angle for allocation in allocations),
            5.0,
            places=9,
        )

    def test_first_generation_budget_keeps_union_labels_aligned_with_children(self):
        dense_children = (
            person_branch("dense-child-a", 2, spouse="spouse-a"),
            person_branch("dense-child-b", 2, spouse="spouse-b"),
        )
        root = DescendantBranch(
            position_id="descendant-multi-root",
            person=PersonNode("multi-root", "multi-root"),
            generation=1,
            unions=(
                UnionBranch("wide-label-union", "wide-spouse", (), ()),
                UnionBranch(
                    "dense-union",
                    "short-spouse",
                    tuple(child.person.handle for child in dense_children),
                    ("birth", "birth"),
                ),
            ),
            children=dense_children,
            children_by_union=((), dense_children),
        )
        per_union_demands = (10.0, 1.0)

        budget = _descendant_branch_angular_budget(
            root,
            angular_budgets=self.profile,
            text_demands={root.position_id: sum(per_union_demands)},
            union_text_demands={root.position_id: per_union_demands},
        )
        dense_preferred = sum(
            _descendant_branch_angular_budget(
                child,
                angular_budgets=self.profile,
            ).preferred_sweep
            for child in dense_children
        )

        self.assertAlmostEqual(
            budget.preferred_sweep,
            10.0 + max(1.0, dense_preferred),
            places=9,
        )
        self.assertGreater(
            budget.preferred_sweep,
            max(sum(per_union_demands), dense_preferred),
        )

    def test_one_child_singleton_chain_does_not_accumulate_ring_floors(self):
        final_singleton = person_branch("mathis", 3)
        sparse_chain = person_branch(
            "delphine",
            2,
            children=(final_singleton,),
        )
        plain_singleton = person_branch("xavier", 2)

        chain_budget = _descendant_branch_angular_budget(
            sparse_chain,
            angular_budgets=self.profile,
        )
        plain_budget = _descendant_branch_angular_budget(
            plain_singleton,
            angular_budgets=self.profile,
        )

        self.assertAlmostEqual(
            chain_budget.preferred_sweep,
            plain_budget.preferred_sweep,
            places=9,
        )

    def test_generation_two_singleton_name_and_date_share_one_radial_rail(self):
        singleton = person_branch("armand", 2)
        root = person_branch("root", 1, children=(singleton,))
        scene = layout_descendants(
            self.canvas,
            (root,),
            name_lookup=lambda handle: "Armand Mussat" if handle == "armand" else handle,
            dates_lookup=lambda handle: "1980–2020" if handle == "armand" else "",
            configured_generation_limit=4,
            show_descendant_marriages=True,
        )
        text_nodes = [node for node in scene.children if isinstance(node, SceneText)]
        name = next(node for node in text_nodes if node.content == "Armand Mussat")
        date = next(node for node in text_nodes if node.content == "1980–2020")
        dx = date.x - name.x
        dy = date.y - name.y
        rail_angle = math.radians(name.rotation)

        self.assertAlmostEqual(
            dx * math.sin(rail_angle) - dy * math.cos(rail_angle),
            0.0,
            places=6,
        )


if __name__ == "__main__":
    unittest.main()
