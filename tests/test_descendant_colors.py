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
from TwoWayFanChart.styles import DESCENDANT_FILLS, generation_shade


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

    def test_each_generation_step_is_perceptually_visible(self):
        # A ~8% per-generation step moved these pastel fills by only 3-4 RGB
        # units per ring, and only ~12 units across four generations — below
        # the visual threshold. The lightening must remain monotone and the
        # full progression must shift at least one channel by a clearly
        # perceptible amount so the gradient reads across the whole fan.
        for base in DESCENDANT_FILLS:
            previous = base
            for generation in (1, 2, 3, 4):
                current = generation_shade(base, generation=generation)
                shifts = [
                    int(current[index:index + 2], 16)
                    - int(previous[index:index + 2], 16)
                    for index in (1, 3, 5)
                ]
                self.assertTrue(
                    any(shift > 0 for shift in shifts),
                    msg=(
                        f"{base} generation {generation} is not lighter: "
                        f"{previous} -> {current}"
                    ),
                )
                previous = current
            final = generation_shade(base, generation=4)
            total_shifts = [
                int(final[index:index + 2], 16)
                - int(base[index:index + 2], 16)
                for index in (1, 3, 5)
            ]
            self.assertTrue(
                any(shift >= 20 for shift in total_shifts),
                msg=(
                    f"{base} progression over 4 generations is too faint: "
                    f"{base} -> {final}"
                ),
            )

    def test_deepest_generation_stays_distinct_from_background(self):
        # The supported maximum is five descendant generations, i.e. a
        # generation parameter of 4 here. An uncapped lightening pushed the
        # outer-ring fills into the page background (amber reached #FEFBF6
        # against #FAF9F5), so the deepest ring must keep a clearly visible
        # distance from the default background color.
        from TwoWayFanChart.styles import PaletteName, get_palette

        background = get_palette(PaletteName.MOCKUP).background
        bg = tuple(int(background[index:index + 2], 16) for index in (1, 3, 5))
        deepest = generation_shade(DESCENDANT_FILLS[0], generation=4)
        distance = math.sqrt(sum(
            (int(deepest[offset:offset + 2], 16) - bg[position]) ** 2
            for position, offset in enumerate((1, 3, 5))
        ))
        self.assertGreater(distance, 10)

    def test_each_central_child_keeps_its_branch_hue_across_generations(self):
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

        root_colors: list[list[set[str]]] = []
        source_allocations = tuple(reversed(allocations))
        for allocation in source_allocations:
            generations: list[set[str]] = []
            for depth in (1, 2, 3):
                ring_inner, ring_outer = _descendant_ring_bounds(
                    canvas.descendant_inner_radius_mm,
                    canvas.descendant_outer_radius_mm,
                    3,
                    depth,
                )
                generations.append({
                    sector.fill
                    for sector in sectors
                    if math.isclose(sector.inner_radius, ring_inner)
                    and math.isclose(sector.outer_radius, ring_outer)
                    and _in_interval(
                        _sector_mid_angle(sector),
                        allocation.start_angle,
                        allocation.sweep_angle,
                    )
                })
            root_colors.append(generations)

        self.assertTrue(all(len(colors) == 1 for colors in root_colors[0]))
        self.assertTrue(all(len(colors) <= 1 for colors in root_colors[1]))
        self.assertNotEqual(root_colors[0][0], root_colors[1][0])
        self.assertNotEqual(root_colors[0][0], root_colors[0][1])
        self.assertNotEqual(root_colors[0][1], root_colors[0][2])

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

    def test_each_generation_lightens_the_central_child_color(self):
        grandchild = branch("grandchild", 3)
        child = branch(
            "child",
            2,
            children_by_union=((grandchild,),),
            spouses=("child-spouse",),
        )
        root = branch("root", 1, children_by_union=((child,),), spouses=("spouse",))
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=3,
        )

        scene = layout_descendants(
            canvas,
            (root,),
            name_lookup=lambda handle: handle,
        )
        sectors = [node for node in scene.children if isinstance(node, SceneSector)]
        colors_by_generation = []
        for depth in (1, 2, 3):
            ring_inner, ring_outer = _descendant_ring_bounds(
                canvas.descendant_inner_radius_mm,
                canvas.descendant_outer_radius_mm,
                3,
                depth,
            )
            colors_by_generation.append({
                sector.fill
                for sector in sectors
                if math.isclose(sector.inner_radius, ring_inner)
                and math.isclose(sector.outer_radius, ring_outer)
            })

        self.assertEqual(colors_by_generation[0], {
            generation_shade(DESCENDANT_FILLS[0], generation=0),
        })
        self.assertEqual(colors_by_generation[1], {
            generation_shade(DESCENDANT_FILLS[0], generation=1),
        })
        self.assertEqual(colors_by_generation[2], {
            generation_shade(DESCENDANT_FILLS[0], generation=2),
        })
        self.assertNotEqual(colors_by_generation[0], colors_by_generation[1])
        self.assertNotEqual(colors_by_generation[1], colors_by_generation[2])


if __name__ == "__main__":
    unittest.main()
