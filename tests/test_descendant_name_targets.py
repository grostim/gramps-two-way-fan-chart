import unittest

from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import (
    _DESCENDANT_DENSE_FIRST_GEN_TARGET_MM,
    _DESCENDANT_NAME_TARGETS_MM,
    calculate_canvas,
    layout_descendants,
)
from TwoWayFanChart.model import (
    DescendantBranch,
    PersonNode,
    ScenePathText,
    SceneText,
    UnionBranch,
)


def branch(handle, generation, *, children=(), spouse=None):
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


# Short couple labels so every crown is bounded by its nominal target and not
# by the measured lane: the test then reads the ladder itself.
LABELS = {
    "g1-a": "Aline Roy",
    "g1a-s": "Marc Petit",
    "g2-a": "Viviane Finaz",
    "g2a-s": "Gilbert Viel",
    "g3-a": "Carole Trichard",
    "g3a-s": "Hugues Finaz",
    "g4-a": "Nathalie Aubert",
    "g4a-s": "Nicolas Bregazzi",
}
DATES = {
    handle: {"g1": "1918–2003", "g2": "1938–2015", "g3": "1975–", "g4": "2005–"}[
        handle[:2]
    ]
    for handle in LABELS
}


def tree(max_depth: int):
    """Return one lineage truncated to ``max_depth`` visible generations.

    The production pipeline materializes exactly the configured depth, so the
    fixture mirrors it instead of always building four crowns.
    """

    def node(depth: int) -> DescendantBranch:
        children = (node(depth + 1),) if depth < max_depth else ()
        return branch(f"g{depth}-a", depth, children=children, spouse=f"g{depth}a-s")

    return (node(1),)


def rendered_sizes(canvas, max_depth: int) -> dict[int, list[float]]:
    """Return the sorted rendered name sizes per crown depth."""
    scene = layout_descendants(
        canvas,
        tree(max_depth),
        name_lookup=lambda handle: LABELS.get(handle, ""),
        dates_lookup=lambda handle: DATES.get(handle, ""),
        show_descendant_marriages=True,
    )
    sizes: dict[int, set[float]] = {}
    for node in scene.children:
        if not isinstance(node, (SceneText, ScenePathText)) or not node.content:
            continue
        for handle, label in LABELS.items():
            if label in node.content:
                sizes.setdefault(int(handle[1]), set()).add(round(node.font_size, 6))
                break
    return {depth: sorted(values) for depth, values in sizes.items()}


def a0(descendant_generations: int):
    return calculate_canvas(
        PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
        ancestor_generations=5,
        descendant_generations=descendant_generations,
    )


class DescendantNameTargetTests(unittest.TestCase):
    """Crown name sizes must come from the measured lane, not a stale constant.

    Issue #82: crown 3 was pinned at 3.6 mm. Once the descendant fan grew to the
    full ancestor radius (#71) and gained its tuned ring profile (#77), the A0
    lane for that crown reached ~65 mm while its longest label needed ~8.7 mm:
    the absolute constant — not the geometry — decided the rendered size.
    """

    def test_a0_crowns_render_at_their_nominal_targets(self):
        """Literals, not constants read back from the layout.

        A regression that lowers the ladder changes the expectation with it if
        the test imports the same table, so the values are spelled out here.
        """
        sizes = rendered_sizes(a0(4), 4)

        self.assertEqual(sizes[1], [5.4])
        self.assertEqual(sizes[2], [5.4])
        self.assertEqual(sizes[3], [4.9])
        self.assertEqual(sizes[4], [4.4])

    def test_crown_ladder_holds_the_accepted_profile(self):
        self.assertEqual(_DESCENDANT_DENSE_FIRST_GEN_TARGET_MM, 5.4)
        self.assertEqual(
            _DESCENDANT_NAME_TARGETS_MM,
            {2: 5.4, 3: 4.9, 4: 4.4, 5: 4.0},
        )

    def test_third_crown_is_no_longer_pinned_to_the_legacy_size(self):
        sizes = rendered_sizes(a0(4), 4)

        # 3.6 mm was the pre-#82 crown-3 constant; the fully grown fan has
        # ample lane capacity, so the crown must now render above it.
        self.assertGreater(sizes[3][0], 3.6)

    def test_crowns_shrink_with_depth_and_stay_below_the_ancestor_ceiling(self):
        sizes = rendered_sizes(a0(4), 4)
        ordered = [sizes[depth][0] for depth in (1, 2, 3, 4)]

        # Non-increasing from the first crown onward, strictly past crown 2.
        self.assertEqual(ordered, sorted(ordered, reverse=True))
        self.assertEqual(len(set(ordered[1:])), 3)

        # One visual weight with the ancestor fan: its first-generation name
        # ceiling is 7.0 mm, so no descendant crown may overtake it.
        self.assertLessEqual(max(ordered), 7.0)

    def test_compact_paper_still_degrades_through_measured_capacity(self):
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A4, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=3,
        )
        sizes = rendered_sizes(canvas, 3)

        # A4 cannot honour the nominal targets: the measured lane — not the
        # raised ceiling — decides, so crown 3 stays well below its A0 value.
        self.assertIn(3, sizes)
        self.assertLess(sizes[3][0], 4.9 * 0.5)
        self.assertGreater(sizes[3][0], 0.0)


if __name__ == "__main__":
    unittest.main()
