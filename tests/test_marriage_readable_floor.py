"""Issue #90 — marriage dates keep a readable floor in every crown.

The marriage band never had a readability floor. ``_font_size_for_width`` falls
back to ``_MIN_DATE_FONT_SIZE_MM`` (0.25 mm) when the caller names no minimum,
so a crown whose sectors are narrow rendered every one of its marriage dates at
a fraction of a millimetre — the reporter's "les dates de mariage de la
troisième couronne sont tous petits".

This is the same collapse #85 fixed for the descendant couple NAMES, left in
place for the marriage dates: the crown shares one measured size (``min`` over
its sectors), so a narrow ring flattens every date it carries.

The floor reuses the name floor instead of inventing a constant: a marriage
label must never outgrow the individuals it concerns (issue #56), and #85
already pinned those names at 2.0 mm.
"""

import math
import re
import unittest

from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import (
    _DESCENDANT_MARRIAGE_FLOOR_MM,
    _DESCENDANT_NAME_FLOOR_MM,
    _descendant_marriage_plan,
    _descendant_ring_layout,
    _marriage_line_capacities,
    calculate_canvas,
    layout_ancestors,
    layout_descendants,
)
from TwoWayFanChart.model import (
    AncestorMarriage,
    DescendantBranch,
    PersonNode,
    ScenePathText,
    SceneText,
    UnionBranch,
    estimate_emblem_text_width,
    split_marriage_emblem,
)

SEPARATOR = " · "
PLACE = "Saint-Germain-en-Laye, Île-de-France, France"
YEAR = "⚭ 1984"
FULL = YEAR + SEPARATOR + PLACE


def person(handle):
    return PersonNode(handle=handle, gramps_id=handle.upper())


def branch(handle, generation, *, children=(), spouse=None):
    unions = ()
    if spouse is not None:
        unions = (
            UnionBranch(
                family_handle=f"family-{handle}",
                spouse_handle=spouse,
                child_handles=tuple(child.person.handle for child in children),
                child_relations=tuple("birth" for _ in children),
            ),
        )
    return DescendantBranch(
        position_id=f"descendant-{handle}",
        person=person(handle),
        generation=generation,
        unions=unions,
        children=children,
    )


def balanced(depth, width, prefix="g"):
    """Return ``width`` first-generation branches, ``width`` children each."""

    def rec(d, index):
        handle = f"{prefix}{d}-{index}"
        if d == depth:
            return branch(handle, d, spouse=handle + "-sp")
        return branch(
            handle,
            d,
            spouse=handle + "-sp",
            children=tuple(rec(d + 1, index * width + k) for k in range(width)),
        )

    return tuple(rec(1, i) for i in range(width))


def labels_and_marriages(branches):
    labels, marriages = {}, {}

    def walk(node):
        labels[node.person.handle] = f"Prenom Nom-{node.person.handle}"
        for union in node.unions:
            labels[union.spouse_handle] = f"Conjoint-{union.spouse_handle}"
            marriages[union.family_handle] = (FULL, YEAR)
        for child in node.children:
            walk(child)

    for root in branches:
        walk(root)
    return labels, marriages


def a0(generations):
    return calculate_canvas(
        PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
        ancestor_generations=5,
        descendant_generations=generations,
    )


def descendant_scene(branches, canvas, generations):
    labels, marriages = labels_and_marriages(branches)
    return layout_descendants(
        canvas,
        branches,
        name_lookup=labels.__getitem__,
        dates_lookup=lambda _handle: "° 1950 – † 2010",
        configured_generation_limit=generations,
        descendant_marriages=marriages,
        show_descendant_marriages=True,
    )


def emitted_marriages(scene, canvas, generations):
    """Return ``{crown: [font_size, ...]}`` for the emitted marriage labels."""
    _rings, bands = _descendant_ring_layout(
        canvas.descendant_inner_radius_mm,
        canvas.descendant_outer_radius_mm,
        generations,
        show_marriages=True,
    )
    cx, cy = canvas.center_cx_mm, canvas.center_cy_mm
    result = {}
    for node in scene.children:
        if not isinstance(node, ScenePathText):
            continue
        if not node.content.startswith("⚭"):
            continue
        match = re.match(r"^M ([\d.]+) ([\d.]+)", node.path)
        if match is None:
            continue
        radius = math.hypot(
            float(match.group(1)) - cx,
            float(match.group(2)) - cy,
        )
        for index, (band_inner, band_outer) in enumerate(bands):
            if band_inner - 1.5 <= radius <= band_outer + 1.5:
                result.setdefault(index + 1, []).append(node.font_size)
                break
    return result


def band_of(canvas, generations, crown):
    _rings, bands = _descendant_ring_layout(
        canvas.descendant_inner_radius_mm,
        canvas.descendant_outer_radius_mm,
        generations,
        show_marriages=True,
    )
    return bands[crown - 1]


class DescendantMarriageReadableFloorTests(unittest.TestCase):
    """Contract after #90: a marriage label is either READABLE or ABSENT.

    Before the fix the third crown rendered every one of its dates at 0.326 mm
    — "tous petits". Three options were open: keep an unreadable date, render a
    readable date wider than its sector, or omit it. The emblem forbids
    ``textLength`` (it would rescale the glyphs and cancel the 1.5x
    enlargement), so a readably-sized label is *not* compressed by the
    renderer: option two would really overflow the sector. The repository
    already treats an unreadable date as omitted, so #90 makes the marriage
    band follow that rule and keeps its colored sector either way.

    These tests hold both halves of that contract: never below the floor, and
    never wider than the arc it sits on.
    """

    def assert_band_contract(self, scene, canvas, generations):
        """Assert every emitted marriage label is readable and cannot overflow.

        The renderer compresses a label through ``textLength`` *unless* it leads
        with the marriage emblem (a textLength would rescale the glyphs and
        cancel the 1.5x enlargement). So an emblem line must fit its arc on its
        own; a line without an emblem is allowed to rely on the renderer.
        """
        checked = 0
        for node in scene.children:
            if not isinstance(node, ScenePathText):
                continue
            if not node.content.startswith("⚭"):
                continue
            match = re.match(r"^M ([\d.]+) ([\d.]+)", node.path)
            self.assertIsNotNone(match, "marriage text must sit on an arc")
            self.assertGreaterEqual(
                node.font_size,
                _DESCENDANT_MARRIAGE_FLOOR_MM,
                msg=f"{node.content!r} rendered at {node.font_size:.3f} mm",
            )
            if split_marriage_emblem(node.content)[0]:
                natural = estimate_emblem_text_width(node.content, node.font_size)
                self.assertLessEqual(
                    natural,
                    (node.max_width or 0.0) + 1e-9,
                    msg=(
                        f"{node.content!r} at {node.font_size:.3f} mm is "
                        f"{natural:.2f} mm wide but its arc is only "
                        f"{node.max_width:.2f} mm; an emblem label cannot be "
                        "compressed by the renderer"
                    ),
                )
            checked += 1
        self.assertTrue(checked, "no marriage label was emitted at all")

    def test_narrow_crown_either_reads_or_omits_its_dates(self):
        # The reported symptom: A0 crown 3 of a six-wide fan. Its tightest
        # sector offers 1.18 mm of arc — 6x less than the year label needs at
        # the floor — so the band is honest and omits it.
        canvas = a0(3)
        scene = descendant_scene(balanced(3, 6), canvas, 3)
        self.assert_band_contract(scene, canvas, 3)

    def test_deepest_crown_either_reads_or_omits_its_dates(self):
        canvas = a0(4)
        scene = descendant_scene(balanced(4, 4), canvas, 4)
        self.assert_band_contract(scene, canvas, 4)

    def test_intermediate_crown_in_a_dense_fan_reads_its_dates(self):
        # Crown 2 of the dense fan still has ample sectors (20 mm of arc): its
        # dates must be PRESENT and readable, not omitted. This is the half of
        # the contract that forbids a lazy blanket omission.
        canvas = a0(3)
        scene = descendant_scene(balanced(3, 6), canvas, 3)
        labels = emitted_marriages(scene, canvas, 3)
        self.assertIn(2, labels)
        self.assertGreaterEqual(min(labels[2]), _DESCENDANT_MARRIAGE_FLOOR_MM)
        self.assertGreater(min(labels[2]), _DESCENDANT_MARRIAGE_FLOOR_MM)

    def test_ample_crowns_keep_every_date(self):
        # A sparse fan must be untouched: every crown keeps its dates and no
        # crown is emptied by the floor.
        canvas = a0(3)
        scene = descendant_scene(balanced(3, 2), canvas, 3)
        labels = emitted_marriages(scene, canvas, 3)
        self.assertEqual(sorted(labels), [1, 2, 3])
        for crown, sizes in labels.items():
            self.assertTrue(sizes, f"crown {crown} lost all its dates")
        self.assertGreater(
            max(max(sizes) for sizes in labels.values()),
            _DESCENDANT_MARRIAGE_FLOOR_MM,
        )

    def test_no_marriage_label_is_ever_wider_than_its_arc(self):
        # The measured regression this contract exists to prevent: without it
        # the A0 crown-3 dates were emitted at 2.0 mm inside a 1.18 mm arc, a
        # 6.14x overflow, because the emblem disables the renderer's
        # horizontal compression.
        for generations, width in ((3, 4), (3, 6), (4, 3), (4, 4)):
            with self.subTest(generations=generations, width=width):
                canvas = a0(generations)
                scene = descendant_scene(
                    balanced(generations, width), canvas, generations
                )
                self.assert_band_contract(scene, canvas, generations)

    def test_marriage_floor_reuses_the_name_floor(self):
        # Issue #56 contract: a marriage label must not outgrow the names it
        # concerns. Sharing #85's name floor keeps that true by construction;
        # assert it so a future edit cannot silently separate the two.
        self.assertEqual(_DESCENDANT_MARRIAGE_FLOOR_MM, _DESCENDANT_NAME_FLOOR_MM)

    def test_plan_omits_the_label_when_the_arc_cannot_carry_it(self):
        # Direct unit check of the decision, independent of the scene walk.
        canvas = a0(3)
        inner, outer = band_of(canvas, 3, 3)
        lines, size = _descendant_marriage_plan(
            FULL, YEAR, inner_r=inner, outer_r=outer, sweep=0.778, depth=3
        )
        self.assertEqual(lines, ())
        self.assertEqual(size, 0.0)

    def test_plan_keeps_the_year_on_a_sector_that_can_carry_it(self):
        # The same band with a wider sweep must still render, at the floor or
        # above, and fit the arc each line is actually drawn on.
        canvas = a0(3)
        inner, outer = band_of(canvas, 3, 3)
        text_radius = (inner + outer) / 2.0
        lines, size = _descendant_marriage_plan(
            FULL, YEAR, inner_r=inner, outer_r=outer, sweep=10.5, depth=3
        )
        self.assertTrue(lines)
        self.assertGreaterEqual(size, _DESCENDANT_MARRIAGE_FLOOR_MM)
        capacities = _marriage_line_capacities(text_radius, 10.5, size)
        for index, line in enumerate(lines):
            # `_marriage_line_capacities` already discounts the renderer's own
            # sweep margin; add it back so this check bounds the raw arc.
            self.assertLessEqual(
                estimate_emblem_text_width(line, size),
                capacities[index] + 2.0,
            )

    def test_a4_narrow_crown_either_reads_or_omits_its_dates(self):
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A4, Orientation.LANDSCAPE),
            ancestor_generations=4,
            descendant_generations=3,
        )
        scene = descendant_scene(balanced(3, 6), canvas, 3)
        self.assert_band_contract(scene, canvas, 3)


class AncestorMarriageReadableFloorTests(unittest.TestCase):
    """The ancestor half is deliberately OUT of scope for #90.

    While instrumenting the ancestor path this test suite found that its
    marriage labels cannot be floored by a marriage-local change: the measured
    `marriage_name_cap` is the ancestor NAME size, and on a dense ancestor fan
    those names themselves collapse (0.25 mm measured on A5 / 3 generations,
    where the descendant half was fixed by #85). The issue #56 cap — a marriage
    label must not outgrow the names it concerns — would then mask any floor
    applied to the label alone, and raising the ancestor NAME floor is a
    different change with its own visual contract. Documented here so the
    follow-up is not lost; see the PR body of #90.
    """

    def slots(self, generations):
        entries = []
        for lineage in ("a", "b"):
            for generation in range(1, generations + 1):
                for index in range(2 ** (generation - 1)):
                    entries.append((
                        f"ancestor-{lineage}-{generation}-{index}",
                        f"Grandparent {lineage}{generation}{index}",
                        "1800–1860",
                        None,
                        False,
                    ))
        return tuple(entries)

    def marriages(self, generations):
        return tuple(
            AncestorMarriage(
                generation,
                lineage,
                index,
                f"family-{lineage}-{generation}-{index}",
                f"{1800 + generation} · Lyon",
            )
            for lineage in ("a", "b")
            for generation in range(1, generations + 1)
            for index in range(2 ** (generation - 1))
        )

    def test_ancestor_marriage_still_never_exceeds_its_names(self):
        # The #56 contract must survive the descendant-side change: the ancestor
        # cap keeps winning, and no descendant floor leaks into this path.
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A5, Orientation.LANDSCAPE),
            ancestor_generations=2,
            descendant_generations=0,
        )
        slots = tuple(
            (
                f"ancestor-a-1-{index}",
                "Alexandre Guillaume De La Rochefoucauld " + str(index),
                "1800–1860",
                None,
                False,
            )
            for index in range(4)
        ) + tuple(
            (
                f"ancestor-b-1-{index}",
                "Bernadette Charlotte De La Rochefoucauld " + str(index),
                "1805–1870",
                None,
                False,
            )
            for index in range(4)
        )
        marriages = tuple(
            AncestorMarriage(
                1, lineage, index, f"f-{lineage}-{index}", f"17{90 + index} · Lyon"
            )
            for lineage in ("a", "b")
            for index in range(2)
        )
        scene = layout_ancestors(
            canvas,
            slots,
            ancestor_marriages=marriages,
            show_ancestor_marriages=True,
        )
        name_nodes = [
            node
            for node in scene.children
            if isinstance(node, ScenePathText) and "Rochefoucauld" in node.content
        ]
        marriage_nodes = [
            node
            for node in scene.children
            if isinstance(node, ScenePathText) and node.content.startswith("17")
        ]
        self.assertTrue(name_nodes)
        self.assertTrue(marriage_nodes)
        smallest_name = min(node.font_size for node in name_nodes)
        for node in marriage_nodes:
            self.assertLessEqual(node.font_size, smallest_name + 1e-9)

    def test_ancestor_marriage_collapse_originates_in_the_ancestor_name_fit(self):
        # Characterisation of the measured root cause, so the follow-up starts
        # from evidence: on a dense A5 ancestor fan the gen-3 NAMES themselves
        # come back at 0.25 mm. `_font_size_for_width` has no caller-owned floor
        # on that path, so a NAME takes `_MIN_DATE_FONT_SIZE_MM` — the exact
        # defect #85 fixed for the descendant half only. The marriage label then
        # follows that collapsed cap, because issue #56 forbids it from growing
        # past the names it concerns. Floors on the marriage label alone cannot
        # fix this; the ancestor NAME floor is a separate change.
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A5, Orientation.LANDSCAPE),
            ancestor_generations=3,
            descendant_generations=0,
        )
        scene = layout_ancestors(
            canvas,
            self.slots(3),
            ancestor_marriages=self.marriages(3),
            show_ancestor_marriages=True,
        )
        name_sizes = [
            node.font_size
            for node in scene.children
            if isinstance(node, (ScenePathText, SceneText))
            and node.content.startswith("Grandparent")
        ]
        marriage_sizes = [
            node.font_size
            for node in scene.children
            if isinstance(node, (ScenePathText, SceneText))
            and node.content.startswith("18")
        ]
        self.assertTrue(name_sizes)
        self.assertTrue(marriage_sizes)

        smallest_name = min(name_sizes)
        smallest_marriage = min(marriage_sizes)

        # The #56 contract holds: a marriage never outgrows its names.
        self.assertLessEqual(smallest_marriage, smallest_name + 1e-9)
        # And the collapse originates upstream of the marriage band: the names
        # are already below the floor, so flooring the label alone would break
        # #56 instead of fixing the chart.
        self.assertLess(
            smallest_name,
            _DESCENDANT_MARRIAGE_FLOOR_MM,
            msg=(
                "ancestor names no longer collapse; if this fails the "
                "ancestor-side name floor was added and the marriage label "
                "should now be floored too"
            ),
        )


if __name__ == "__main__":
    unittest.main()
