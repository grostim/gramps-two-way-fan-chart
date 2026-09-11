import math
import unittest

from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import (
    _RING_GAP_MM,
    _descendant_ring_bounds,
    calculate_canvas,
    layout_descendants,
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


class SecondGenerationLayoutTests(unittest.TestCase):
    def test_visual_generation_two_ring_is_doubled_in_a_four_generation_chart(self):
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
        first_ring = next(
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
        total_depth = (
            chart.descendant_outer_radius_mm - chart.descendant_inner_radius_mm
        )
        total_weight = sum(_BASE_WEIGHTS_FOR_FOUR_GENERATIONS)
        previous_visible_depth = (
            total_depth * _BASE_WEIGHTS_FOR_FOUR_GENERATIONS[0] / total_weight
            - _RING_GAP_MM
        )

        self.assertAlmostEqual(
            first_ring.outer_radius - first_ring.inner_radius,
            previous_visible_depth * 2,
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


if __name__ == "__main__":
    unittest.main()
