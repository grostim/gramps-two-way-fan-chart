"""Issue #85: couple cells receive a real final angular floor.

The existing allocator stores a minimum sweep in the demand, then normalises all
demands proportionally. Under pressure that turns an absolute floor (2.1 deg for
G3) into 0.57 deg. A couple's two radial rails then have no tangential room and
its names cross neighbouring separator lines.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize  # noqa: E402

from TwoWayFanChart.layout import (  # noqa: E402
    _DESC_MIN_SWEEP_BY_GENERATION,
    _allocate_descendant_union_groups, calculate_canvas, layout_descendants,
)
from TwoWayFanChart.model import (  # noqa: E402
    DescendantBranch, PersonNode, SceneSector, SceneText, UnionBranch,
)


def branch(handle: str, generation: int, *, unions: int = 1) -> DescendantBranch:
    """Build a branch with `unions` recorded marriages and no children."""
    union_data = tuple(
        UnionBranch(
            family_handle=f"family-{handle}-{index}",
            spouse_handle=f"spouse-{handle}-{index}",
            child_handles=(),
            child_relations=(),
        )
        for index in range(unions)
    )
    return DescendantBranch(
        position_id=f"descendant-{handle}",
        person=PersonNode(handle, handle.upper()),
        generation=generation,
        unions=union_data,
        children=(),
    )


class DescendantCoupleAngleTest(unittest.TestCase):
    def test_multi_union_couple_cells_keep_their_final_minimum_sweep(self):
        """A demand normalisation must not scale an absolute couple floor away."""
        demanding_children = tuple(
            DescendantBranch(
                f"child-{index}",
                PersonNode(f"child-{index}", f"I{index}"),
                4,
                (),
                (),
            )
            for index in range(10)
        )
        target = DescendantBranch(
            position_id="descendant-target",
            person=PersonNode("target", "I0001"),
            generation=3,
            unions=tuple(
                UnionBranch(
                    family_handle=f"family-target-{index}",
                    spouse_handle=f"spouse-target-{index}",
                    child_handles=tuple(
                        child.person.handle
                        for child in (demanding_children if index == 0 else ())
                    ),
                    child_relations=tuple(
                        "birth"
                        for child in (demanding_children if index == 0 else ())
                    ),
                )
                for index in range(3)
            ),
            children=demanding_children,
            children_by_union=(demanding_children, (), ()),
        )
        allocations = _allocate_descendant_union_groups(
            target,
            start_angle=96.0,
            total_sweep=10.0,
            include_empty=True,
        )
        floor = _DESC_MIN_SWEEP_BY_GENERATION[3]
        self.assertEqual(len(allocations), 3)
        self.assertGreaterEqual(
            min(allocation.sweep_angle for allocation in allocations),
            floor - 1e-9,
            "normalisation scaled the absolute couple angle floor away",
        )
        self.assertAlmostEqual(
            sum(allocation.sweep_angle for allocation in allocations),
            10.0,
            places=9,
        )

    def test_too_narrow_couple_keeps_sector_but_omits_crossing_text(self):
        """Impossible cells do not draw a couple through their separator."""
        target = DescendantBranch(
            position_id="descendant-target",
            person=PersonNode("target", "I0001"),
            generation=2,
            unions=(UnionBranch(
                family_handle="family-target",
                spouse_handle="target-spouse",
                child_handles=(),
                child_relations=(),
            ),),
            children=(),
        )
        siblings = tuple(
            DescendantBranch(
                f"sibling-{index}",
                PersonNode(f"sibling-{index}", f"I{index}"),
                2,
                (),
                (),
            )
            for index in range(200)
        )
        root = DescendantBranch(
            position_id="descendant-root",
            person=PersonNode("root", "I0000"),
            generation=1,
            unions=(),
            children=(target,) + siblings,
        )
        labels = {
            "target": "Margaux Mirieu de Labarre",
            "target-spouse": "Jean Kouji Decourt",
        }
        scene = layout_descendants(
            calculate_canvas(
                PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
                ancestor_generations=5,
                descendant_generations=4,
            ),
            (root,),
            name_lookup=lambda handle: labels.get(handle, handle),
            dates_lookup=lambda _handle: "",
        )
        couple_text = [
            node for node in scene.children
            if isinstance(node, SceneText)
            and node.content in {
                "Margaux Mirieu de Labarre",
                "× Jean Kouji Decourt",
            }
        ]
        self.assertEqual(
            couple_text, [],
            "a sub-minimum couple cell still emitted text over its separator",
        )
        # The target remains represented by its descendant sector; only the
        # impossible text block is omitted.
        target_sectors = [
            node for node in scene.children
            if isinstance(node, SceneSector)
            and node.sweep_angle < _DESC_MIN_SWEEP_BY_GENERATION[2]
        ]
        self.assertTrue(target_sectors, "the narrow target sector was removed with its text")

