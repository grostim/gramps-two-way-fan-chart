from __future__ import annotations

import math
import unittest

from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import (
    _DESC_START_ANGLE,
    _DESC_TOTAL_SWEEP,
    _allocate_descendant_branches_by_demand,
    _descendant_ring_bounds,
    calculate_canvas,
    layout_descendants,
)
from TwoWayFanChart.model import DescendantBranch, PersonNode, SceneSector, UnionBranch
from TwoWayFanChart.styles import DESCENDANT_FILLS


def branch(
    handle: str,
    generation: int,
    *,
    children_by_union: tuple[tuple[DescendantBranch, ...], ...] = (),
    spouses: tuple[str | None, ...] = (),
) -> DescendantBranch:
    children = tuple(child for group in children_by_union for child in group)
    unions = tuple(
        UnionBranch(
            family_handle=f"family-{handle}-{index}",
            spouse_handle=spouse,
            child_handles=tuple(child.person.handle for child in group),
            child_relations=tuple("birth" for _child in group),
        )
        for index, (spouse, group) in enumerate(zip(spouses, children_by_union))
    )
    return DescendantBranch(
        position_id=f"descendant-{handle}",
        person=PersonNode(handle, handle.upper()),
        generation=generation,
        unions=unions,
        children=children,
        children_by_union=children_by_union,
    )


def _sector_mid_angle(sector: SceneSector) -> float:
    return sector.start_angle + sector.sweep_angle / 2.0


def _in_interval(angle: float, start: float, sweep: float) -> bool:
    return start - 1e-9 <= angle <= start + sweep + 1e-9


class DescendantColorTests(unittest.TestCase):
    def test_descendant_palette_is_distinct_and_replaces_old_neutral_fills(self):
        self.assertGreaterEqual(len(DESCENDANT_FILLS), 5)
        self.assertEqual(len(DESCENDANT_FILLS), len(set(DESCENDANT_FILLS)))
        self.assertNotIn("#F3EEE5", DESCENDANT_FILLS)
        self.assertNotIn("#EEF1E8", DESCENDANT_FILLS)
        self.assertNotIn("#F7EBE6", DESCENDANT_FILLS)

    def test_each_central_child_keeps_one_fill_across_its_whole_dependency(self):
        a_grandchild = branch("a-grandchild", 3)
        a_child_one = branch(
            "a-child-one",
            2,
            children_by_union=((a_grandchild,),),
            spouses=("a-child-one-spouse",),
        )
        a_child_two = branch("a-child-two", 2)
        root_a = branch(
            "root-a",
            1,
            children_by_union=((a_child_one,), (a_child_two,)),
            spouses=("a-spouse-one", "a-spouse-two"),
        )

        b_child_one = branch("b-child-one", 2)
        b_child_two = branch("b-child-two", 2)
        root_b = branch(
            "root-b",
            1,
            children_by_union=((b_child_one,), (b_child_two,)),
            spouses=("b-spouse-one", "b-spouse-two"),
        )

        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=3,
        )
        roots = (root_a, root_b)
        allocations = _allocate_descendant_branches_by_demand(
            roots,
            start_angle=_DESC_START_ANGLE,
            total_sweep=_DESC_TOTAL_SWEEP,
        )
        scene = layout_descendants(
            canvas,
            roots,
            name_lookup=lambda handle: handle,
            dates_lookup=lambda _handle: "",
        )
        sectors = [node for node in scene.children if isinstance(node, SceneSector)]
        self.assertTrue(sectors)

        root_colors: list[set[str]] = []
        for allocation in allocations:
            colors = {
                sector.fill
                for sector in sectors
                if _in_interval(
                    _sector_mid_angle(sector),
                    allocation.start_angle,
                    allocation.sweep_angle,
                )
            }
            root_colors.append(colors)

        self.assertEqual(len(root_colors[0]), 1)
        self.assertEqual(len(root_colors[1]), 1)
        self.assertNotEqual(root_colors[0], root_colors[1])

        first_ring_inner, first_ring_outer = _descendant_ring_bounds(
            canvas.descendant_inner_radius_mm,
            canvas.descendant_outer_radius_mm,
            3,
            1,
        )
        first_ring = [
            sector
            for sector in sectors
            if math.isclose(sector.inner_radius, first_ring_inner)
            and math.isclose(sector.outer_radius, first_ring_outer)
        ]
        self.assertGreaterEqual(len(first_ring), 4)
        self.assertTrue(all(sector.fill in DESCENDANT_FILLS for sector in first_ring))


if __name__ == "__main__":
    unittest.main()
