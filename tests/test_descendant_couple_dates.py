# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression tests for issue #83: descendant couples keep their life years.

Intermediate descendant generations (2 and deeper) render each couple on two
parallel radial rails. Before this fix the rail budget only ever held the two
identities, so a displayed couple had no dates at all while a single person in
the same generation still had them. Each rail now carries its own life years
inline, right after the name.

Design decision (Timothee, issue #83): a couple is always given two rails, and
the dates travel on the same rail as the name they belong to.
"""

from __future__ import annotations

import math
import unittest

from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import calculate_canvas, layout_descendants
from TwoWayFanChart.model import (
    DescendantBranch,
    PersonNode,
    SceneText,
    UnionBranch,
    estimate_text_width,
)
from TwoWayFanChart.styles import TEXT_DARK, TEXT_GREY

_DATES = "° 1950 – † 2020"

_LABELS = {
    "root": "Root",
    "root-spouse": "Root Spouse",
    "second": "Second",
    "second-spouse": "Second Spouse",
    "third": "Third",
    "third-spouse": "Third Spouse",
    "leaf": "Leaf",
    "leaf-spouse": "Leaf Spouse",
}

# Couple rails of generation 2 and deeper. Generation 1 keeps its own
# four-lane stack and is covered by test_generation_font_sizes.
_INTERMEDIATE_RAILS = (
    "Second",
    "× Second Spouse",
    "Third",
    "× Third Spouse",
    "Leaf",
    "× Leaf Spouse",
)

_ANGLE_TOLERANCE = 0.05


def person(handle: str) -> PersonNode:
    return PersonNode(handle=handle, gramps_id=handle.upper())


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
        person=person(handle),
        generation=generation,
        unions=unions,
        children=children,
    )


def couple_tree() -> DescendantBranch:
    """One lineage whose four displayed generations all carry a spouse."""
    leaf = branch("leaf", 4, spouse="leaf-spouse")
    third = branch("third", 3, children=(leaf,), spouse="third-spouse")
    second = branch("second", 2, children=(third,), spouse="second-spouse")
    return branch("root", 1, children=(second,), spouse="root-spouse")


class IntermediateCoupleDatesTests(unittest.TestCase):
    def _scene(self, paper: PaperSize = PaperSize.A0, generations: int = 4):
        canvas = calculate_canvas(
            PaperRegion(paper, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=generations,
        )
        scene = layout_descendants(
            canvas,
            (couple_tree(),),
            name_lookup=_LABELS.__getitem__,
            dates_lookup=lambda _handle: _DATES,
            configured_generation_limit=generations,
        )
        return canvas, scene

    @staticmethod
    def _rail_line(node):
        """Return the rail unit direction of one radial run."""
        angle = math.radians(node.rotation)
        return math.cos(angle), math.sin(angle)

    def _runs(self, canvas, scene):
        """Return (rail label, name run, matching date run) for every couple.

        Both runs of a rail lie on the same line through the rail's origin with
        the sector's radial direction, so a date belongs to the name it shares
        that line with (its projection on the rail is larger than the name's).
        """
        texts = [node for node in scene.children if isinstance(node, SceneText)]
        names = {node.content: node for node in texts if node.content in _INTERMEDIATE_RAILS}
        dates = [node for node in texts if node.content == _DATES]
        self.assertEqual(
            sorted(names),
            sorted(_INTERMEDIATE_RAILS),
            msg="every intermediate-generation couple rail must stay displayed",
        )
        runs = []
        for label, name in names.items():
            axis_x, axis_y = self._rail_line(name)
            rail_dates = []
            for node in dates:
                dx, dy = node.x - name.x, node.y - name.y
                projection = dx * axis_x + dy * axis_y
                perpendicular = abs(dx * axis_y - dy * axis_x)
                if perpendicular < 0.05 and projection > 0.0:
                    rail_dates.append((node, projection))
            rail_dates.sort(key=lambda item: item[1])
            runs.append((label, name, [node for node, _p in rail_dates]))
        return runs

    def test_every_intermediate_couple_rail_carries_its_dates(self):
        canvas, scene = self._scene()

        for label, name, rail_dates in self._runs(canvas, scene):
            self.assertEqual(
                len(rail_dates),
                1,
                msg=f"{label!r} must carry exactly one date label on its rail",
            )
            self.assertEqual(name.fill, TEXT_DARK)
            self.assertEqual(rail_dates[0].fill, TEXT_GREY)

    def test_dates_follow_the_name_on_the_same_rail(self):
        canvas, scene = self._scene()

        for label, name, rail_dates in self._runs(canvas, scene):
            self.assertEqual(
                len(rail_dates),
                1,
                msg=f"{label!r} must carry exactly one date label on its rail",
            )
            dates = rail_dates[0]
            name_width = estimate_text_width(label, name.font_size)
            dates_width = estimate_text_width(dates.content, dates.font_size)
            advance = math.hypot(dates.x - name.x, dates.y - name.y)
            self.assertGreaterEqual(
                advance,
                name_width / 2.0 + dates_width / 2.0,
                msg=f"{label!r} dates must follow the name without overlapping it",
            )
            self.assertGreater(
                dates.font_size,
                0.0,
                msg=f"{label!r} dates must be rendered at a readable size",
            )
            self.assertLessEqual(
                dates.font_size,
                name.font_size + 1e-9,
                msg=f"{label!r} dates must never exceed their name's size",
            )

    def test_couple_keeps_two_distinct_rails(self):
        # The two people of a couple stay on two parallel rails: same radius
        # and rotation, separated along the sector's tangential axis.
        canvas, scene = self._scene()
        texts = {node.content: node for node in scene.children if isinstance(node, SceneText)}

        person = texts["Second"]
        spouse = texts["× Second Spouse"]
        self.assertAlmostEqual(person.rotation, spouse.rotation, places=9)

        angle = math.radians(person.rotation)
        axis_x, axis_y = math.cos(angle), math.sin(angle)
        dx, dy = spouse.x - person.x, spouse.y - person.y
        radial = dx * axis_x + dy * axis_y
        tangential = dx * axis_y - dy * axis_x

        self.assertAlmostEqual(
            radial,
            0.0,
            places=6,
            msg="both rails of a couple sit at the same radius",
        )
        self.assertGreater(
            abs(tangential),
            0.5,
            msg="the two people of a couple stay on two parallel rails",
        )

    def test_missing_dates_still_keep_two_rails(self):
        # A person with no known life years must not collapse the rail layout:
        # the couple stays on two rails, it simply shows no date run.
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=4,
        )
        scene = layout_descendants(
            canvas,
            (couple_tree(),),
            name_lookup=_LABELS.__getitem__,
            dates_lookup=lambda _handle: "",
            configured_generation_limit=4,
        )
        texts = [node for node in scene.children if isinstance(node, SceneText)]

        self.assertEqual(
            sorted(node.content for node in texts if node.content in _INTERMEDIATE_RAILS),
            sorted(_INTERMEDIATE_RAILS),
        )
        self.assertFalse(any(node.content == _DATES for node in texts))


if __name__ == "__main__":
    unittest.main()
