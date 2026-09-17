"""Issue #85: a rail's lane must never squash its text.

A descendant rail runs along the RADIUS, so the length of its label is radial and
the budget that bounds it must be the ring's text depth. Issue #91 set that
budget to the cell's ARC instead:

    rail_lane_width = max(rail_arc / 2.0 - 1.0, ...)

For a narrow cell the arc is a few millimetres while a long name needs tens, and
Cairo turns that ratio into `scale_x = max_width / natural_width` inside
`_render_path_text`. The exported PDF therefore carried labels squashed to
`scale_x` 0.075-0.15 — unreadable smears that read as overflowing text. The
reporter's own PDF shows exactly that: its text matrices encode the ratio.

These tests pin the invariant at the scene level, using the real font advances,
and are proven to bite by a sabotage run.
"""

import unittest

from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import calculate_canvas, layout_descendants
from TwoWayFanChart.model import (
    DescendantBranch,
    PersonNode,
    ScenePathText,
    SceneText,
    UnionBranch,
    estimate_text_width,
)

# The longest names present in the reporter's chart: a lane that cannot hold one
# of these is a lane that will be squashed by the renderer.
LONG_NAMES = [
    "Margaux Mirieu de Labarre",
    "Quentin Mirieu de Labarre",
    "Roland Augier De Crémiers",
    "Jean-Claude Bonnet de Carnavet",
    "Andéol Bonnet de Carnavet",
    "Hortense Bonnet de Carnavet",
    "Valentin Augier De Crémiers",
    "Faustine de Frescheville",
    "Juliette de Villeneuve",
    "Augustine Mirieu de Labarre",
]


def couple(handle, generation, *, children=(), spouse=None):
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


def build(prefix, generation, fanout, max_depth=4):
    if generation >= max_depth:
        return couple(prefix, generation, spouse=f"{prefix}-s")
    children = tuple(
        build(f"{prefix}-{i}", generation + 1, fanout, max_depth)
        for i in range(fanout.get(generation + 1, 2))
    )
    return couple(prefix, generation, children=children, spouse=f"{prefix}-s")


def name_lookup(handle):
    token = abs(hash(handle))
    if token % 3:
        return LONG_NAMES[token % len(LONG_NAMES)]
    return ("Alba", "Yves Peillon", "Rosine Peillon")[token % 3]


def scene(fanout, direct, descendant_generations=4):
    canvas = calculate_canvas(
        PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
        ancestor_generations=5,
        descendant_generations=descendant_generations,
    )
    tree = tuple(
        build(f"c{i}", 1, fanout, descendant_generations) for i in range(direct)
    )
    return canvas, layout_descendants(
        canvas,
        tree,
        name_lookup=name_lookup,
        dates_lookup=lambda _handle: "1908–1981",
        configured_generation_limit=descendant_generations,
    )


class DescendantLaneSquashTests(unittest.TestCase):
    """A lane that forces the renderer to compress text below half its width is
    not a lane: it is an unreadable smear in the PDF."""

    # Cairo/SVG compress a label to `max_width / natural_width`. Below this ratio
    # the glyphs are visibly destroyed.
    MIN_ACCEPTABLE_RATIO = 0.5

    def _squash_ratios(self, scene_node):
        ratios = []
        for node in scene_node.children:
            if not isinstance(node, (SceneText, ScenePathText)) or not node.content:
                continue
            if node.max_width is None or node.max_width <= 0:
                continue
            natural = estimate_text_width(node.content, node.font_size)
            if natural <= 0:
                continue
            ratios.append((node.max_width / natural, node.content, node.font_size))
        return ratios

    def test_dense_fan_never_squashes_a_rail_below_half_its_width(self):
        # The density that reproduces the reporter's chart.
        _canvas, scene_node = scene({2: 4, 3: 3, 4: 3}, 2)
        ratios = self._squash_ratios(scene_node)

        self.assertTrue(ratios)
        worst = sorted(ratios)[:5]
        self.assertGreaterEqual(
            min(ratio for ratio, _content, _size in ratios),
            self.MIN_ACCEPTABLE_RATIO,
            msg=(
                "a rail's lane squashes its label below half its width, which the "
                f"renderers draw as an unreadable smear: {worst}"
            ),
        )

    def test_very_dense_fan_never_squashes_a_rail_below_half_its_width(self):
        _canvas, scene_node = scene({2: 8, 3: 8, 4: 4}, 3)
        ratios = self._squash_ratios(scene_node)

        self.assertTrue(ratios)
        squashed = [r for r in ratios if r[0] < self.MIN_ACCEPTABLE_RATIO]
        self.assertEqual(
            squashed[:5],
            [],
            msg=f"{len(squashed)} rails are squashed below half their width: {squashed[:3]}",
        )

    def test_rail_lane_is_a_radial_budget_not_the_cell_arc(self):
        """The lane must be able to hold a long name at its rendered size.

        The cell's arc is a tangential quantity; a rail's text is laid out
        radially, so the lane has to come from the ring's text depth. A lane that
        equals a few millimetres while the name is tens cannot be right.
        """
        _canvas, scene_node = scene({2: 4, 3: 3, 4: 3}, 2)
        offenders = []
        for node in scene_node.children:
            if not isinstance(node, SceneText) or not node.content:
                continue
            if node.max_width is None or node.max_width <= 0:
                continue
            natural = estimate_text_width(node.content, node.font_size)
            # A lane narrower than half the name is the arc-budget signature.
            if natural > 0 and node.max_width < natural / 2.0:
                offenders.append((node.max_width, round(natural, 2), node.content))

        self.assertEqual(
            offenders[:5],
            [],
            msg=f"lanes sized by the cell arc instead of the radial depth: {offenders[:5]}",
        )


if __name__ == "__main__":
    unittest.main()
