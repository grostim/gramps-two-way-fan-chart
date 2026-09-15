"""Issue #85: descendant labels must never collapse below a readable size.

A dense descendant fan (a couple on every crown) used to render its deep-crown
names and dates at a fraction of the declared readability floor: the couple rail
budget `angular_capacity / _COUPLE_RAIL_TANGENTIAL_EM` could reach 0 for a narrow
cell, and the measuring pass then fell back to the DATE floor because the size
estimator applies `_MIN_DATE_FONT_SIZE_MM` without distinguishing a name from a
date. One collapsed name then fixed the WHOLE generation through `min(sizes)`.

These tests pin the floor at the scene level, on the couple path (the only one
that regresses) and on the single-rail path (the control), and check that the
degradation no longer reaches dates either.
"""

import unittest

from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import (
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

# The readability floor this issue establishes for descendant names, in mm.
# 2.0 mm is the repository's existing direct-label floor
# (`_DIRECT_LABEL_MIN_FONT_SIZE_MM`), reused so both labels in a cell share one
# visual contract.
READABLE_NAME_FLOOR_MM = 2.0

_SURNAMES = ["Jarlot", "Peillon", "Cojean", "Durand", "Olivier", "Berthault"]
_GIVEN = ["Charlotte", "Tanguy", "Fabien", "Mathias", "Erwan", "Corentin"]


def _name(handle: str) -> str:
    token = abs(hash(handle))
    return f"{_GIVEN[token % len(_GIVEN)]} {_SURNAMES[(token // 7) % len(_SURNAMES)]}"


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


def build(prefix, generation, fanout, max_depth, spouse=True):
    if generation >= max_depth:
        return couple(prefix, generation, spouse=f"{prefix}-s" if spouse else None)
    children = tuple(
        build(f"{prefix}-{i}", generation + 1, fanout, max_depth, spouse)
        for i in range(fanout.get(generation + 1, 2))
    )
    return couple(
        prefix, generation, children=children, spouse=f"{prefix}-s" if spouse else None
    )


def dense_tree(fanout, direct_children, spouse=True, max_depth=4):
    return tuple(
        build(f"c{i}", 1, fanout, max_depth, spouse) for i in range(direct_children)
    )


def a0(descendant_generations=4):
    return calculate_canvas(
        PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
        ancestor_generations=5,
        descendant_generations=descendant_generations,
    )


def rendered_sizes(scene):
    """Return every rendered descendant size with its content."""
    out = []
    for node in scene.children:
        if isinstance(node, (SceneText, ScenePathText)) and node.content:
            out.append((node.content, node.font_size))
    return out


def is_date(content):
    return any(token in content for token in ("°", "†", "–"))


class DescendantReadableFloorTests(unittest.TestCase):
    def _scene(self, fanout, direct, spouse=True):
        # 8x8x4 is denser than the reporter's chart and reproduces the collapse;
        # it is the shape that made the deep crowns unreadable.
        return layout_descendants(
            a0(),
            dense_tree(fanout, direct, spouse),
            name_lookup=_name,
            dates_lookup=lambda _handle: "1908–1981",
            configured_generation_limit=4,
        )

    def test_dense_couple_crowns_keep_names_above_the_readable_floor(self):
        scene = self._scene({2: 8, 3: 8, 4: 4}, 3, spouse=True)
        names = [
            size
            for content, size in rendered_sizes(scene)
            if not is_date(content)
        ]

        self.assertTrue(names)
        self.assertGreaterEqual(
            min(names),
            READABLE_NAME_FLOOR_MM - 1e-9,
            msg=f"descendant names collapsed to {min(names):.4f} mm",
        )

    def test_dense_couple_crowns_keep_dates_above_their_own_floor(self):
        scene = self._scene({2: 8, 3: 8, 4: 4}, 3, spouse=True)
        dates = [
            size
            for content, size in rendered_sizes(scene)
            if is_date(content)
        ]

        self.assertTrue(dates)
        # A date rides one typographic point below its name, so once names hold
        # the readable floor their dates hold that floor minus one point.
        date_floor = READABLE_NAME_FLOOR_MM - 25.4 / 72.0
        self.assertGreaterEqual(
            min(dates),
            date_floor - 1e-9,
            msg=f"descendant dates collapsed to {min(dates):.4f} mm",
        )

    def test_single_rail_crowns_are_unaffected_control(self):
        """The regression is specific to the couple path.

        Without a spouse every crown takes the single-rail path, which never
        collapsed, so the floor must not change that rendering.
        """
        scene = self._scene({2: 8, 3: 8, 4: 4}, 3, spouse=False)
        names = [
            size
            for content, size in rendered_sizes(scene)
            if not is_date(content)
        ]

        self.assertTrue(names)
        self.assertGreaterEqual(min(names), READABLE_NAME_FLOOR_MM - 1e-9)

    def test_a_single_crowded_cell_no_longer_sets_the_whole_generation(self):
        """One collapsed label used to become the generation-wide size.

        A fan with one very narrow couple cell beside ample ones must keep every
        crown readable: the generation-wide minimum is a floor, not a global
        shrink that drags down names that had ample room.
        """
        scene = self._scene({2: 8, 3: 8, 4: 4}, 3, spouse=True)
        names = [
            size
            for content, size in rendered_sizes(scene)
            if not is_date(content)
        ]

        self.assertTrue(names)
        self.assertGreaterEqual(
            min(names),
            READABLE_NAME_FLOOR_MM - 1e-9,
            msg=f"a crowded cell dragged the generation to {min(names):.4f} mm",
        )
        # Names that had ample room must still render well above the floor, so
        # the floor is not being applied as a blanket shrink.
        self.assertGreater(
            max(names),
            READABLE_NAME_FLOOR_MM + 1.0,
            msg="ample cells were flattened to the floor instead of keeping size",
        )

    def test_floor_holds_on_compact_paper_too(self):
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A4, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=3,
        )
        scene = layout_descendants(
            canvas,
            dense_tree({2: 4, 3: 3}, 2, spouse=True, max_depth=3),
            name_lookup=_name,
            dates_lookup=lambda _handle: "1908–1981",
            configured_generation_limit=3,
        )
        names = [
            size
            for content, size in rendered_sizes(scene)
            if not is_date(content)
        ]

        self.assertTrue(names)
        self.assertGreater(
            min(names),
            0.0,
            msg="A4 must still render descendant names (compressed if needed)",
        )
        self.assertGreaterEqual(
            min(names),
            min(READABLE_NAME_FLOOR_MM, max(names)),
            msg=f"A4 collapsed a crown below the readable floor: {min(names):.4f} mm",
        )


if __name__ == "__main__":
    unittest.main()
