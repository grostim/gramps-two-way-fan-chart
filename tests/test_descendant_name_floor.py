# SPDX-License-Identifier: GPL-3.0-or-later
"""Issue #85: a descendant generation never renders a NAME below the floor.

The reporter's PDF renders the very same crown at two name sizes -- 35 labels at
1.76 mm and 22 at 2.00 mm, interleaved at identical radii (measured from the
PDF's own text matrices). 1.76 mm sits *below* the declared floor
(`_DESCENDANT_NAME_FLOOR_MM` = 2.0 mm), so the generation-wide aggregation

    generation_name_sizes = {depth: min(candidates) ...}

was allowed to adopt an under-floor candidate and drag the whole ring down.

These tests pin the invariant at the point of aggregation: whatever a fitting
path measures, the shared size a generation is rendered at is never below the
floor, and one generation renders exactly one name size.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize  # noqa: E402
from TwoWayFanChart.layout import (  # noqa: E402
    _DESCENDANT_NAME_FLOOR_MM, calculate_canvas, layout_descendants,
)
from TwoWayFanChart.model import (  # noqa: E402
    DescendantBranch, PersonNode, ScenePathText, SceneText, UnionBranch,
)

LONG_NAMES = (
    "Margaux Mirieu de Labarre", "Jean Kouji Decourt", "Alexandre de Villeneuve",
    "Clothilde Bernard", "Victoria de Beaumont", "Sixte Mirieu de Labarre",
    "Domitille Mussat", "Guillaume Cresson", "Ombeline Mussat", "Théophane Gros",
    "Hortense Bonnet de Carnavet", "Pierre-Alexis Cresson", "Delphine Cresson",
    "Sabine Peillon", "Nicolas Tharreau", "Agnès Teppe",
)


class _Fan:
    """Build a descendant fan whose cells get progressively narrower."""

    def __init__(self, unions_per_person: int, depth: int, kids: int) -> None:
        self.names: dict[str, str] = {}
        self.dates: dict[str, str] = {}
        self._counter = 0
        self._unions = unions_per_person
        self._depth = depth
        self._kids = kids

    def _name(self, seed: int) -> str:
        return LONG_NAMES[seed % len(LONG_NAMES)]

    def node(self, level: int, seed: int) -> DescendantBranch:
        self._counter += 1
        handle = f"p{self._counter}"
        self.names[handle] = self._name(seed)
        self.dates[handle] = "1900–1980"
        unions: list[UnionBranch] = []
        children: list[DescendantBranch] = []
        if level < self._depth:
            for index in range(self._unions):
                spouse_handle = f"{handle}-sp{index}"
                self.names[spouse_handle] = self._name(seed + index + 3)
                self.dates[spouse_handle] = "1902–1985"
                # Only the first marriage continues the line: the fan stays
                # small while the deeper person still carries many cells.
                branch_kids = (
                    [self.node(level + 1, seed + index + 1) for _ in range(self._kids)]
                    if index == 0 else []
                )
                children.extend(branch_kids)
                unions.append(UnionBranch(
                    family_handle=f"f-{handle}-{index}",
                    spouse_handle=spouse_handle,
                    child_handles=tuple(k.person.handle for k in branch_kids),
                    child_relations=tuple("birth" for _ in branch_kids),
                ))
        return DescendantBranch(
            position_id=f"d-{handle}", person=PersonNode(handle, handle.upper()),
            generation=level, unions=tuple(unions), children=tuple(children))

    def render(self) -> list[tuple[float, str, float]]:
        branches = tuple(self.node(1, index * 5)
                         for index in range(self._unions))
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=5, descendant_generations=4)
        scene = layout_descendants(
            canvas, branches, name_lookup=lambda h: self.names.get(h, ""),
            dates_lookup=lambda h: self.dates.get(h, ""),
            configured_generation_limit=4)
        cx, cy = canvas.center_cx_mm, canvas.center_cy_mm
        rows: list[tuple[float, str, float]] = []
        for node in scene.children:
            if isinstance(node, ScenePathText):
                _move, xt, yt, *_rest = node.path.split()
                x, y = float(xt), float(yt)
            elif isinstance(node, SceneText):
                x, y = node.x, node.y
            else:
                continue
            if not node.content:
                continue
            rows.append((node.font_size, node.content, math.hypot(x - cx, y - cy)))
        return rows


def _name_rows(rows):
    """Keep identity labels: a marriage emblem or a digit means not a name."""
    return [row for row in rows if not any(ch.isdigit() for ch in row[1])]


class DescendantNameFloorTest(unittest.TestCase):
    def test_generation_name_sizes_never_adopt_an_under_floor_candidate(self):
        """Every rendered name respects the declared floor.

        The aggregation takes `min(candidates)`; a single fitting path that
        measures below the floor used to become the size of the whole ring.
        """
        for unions, depth, kids in ((3, 3, 1), (8, 3, 2), (16, 3, 2), (32, 3, 2)):
            with self.subTest(unions=unions, kids=kids):
                rows = _Fan(unions, depth, kids).render()
                names = _name_rows(rows)
                self.assertTrue(names, "the fixture must render some names")
                under = sorted({round(size, 3) for size, _text, _r in names
                                if size < _DESCENDANT_NAME_FLOOR_MM - 1e-9})
                self.assertEqual(
                    under, [],
                    f"names rendered below the {_DESCENDANT_NAME_FLOOR_MM} mm "
                    f"floor: {under}",
                )

    def test_one_generation_renders_one_name_size(self):
        """The declared contract: one font size per generation.

        `min(candidates)` is only sound while every candidate is itself
        admissible; this pins the observable consequence.
        """
        for unions, depth, kids in ((3, 3, 1), (8, 3, 2), (16, 3, 2), (32, 3, 2)):
            with self.subTest(unions=unions, kids=kids):
                rows = _Fan(unions, depth, kids).render()
                names = _name_rows(rows)
                by_radius: dict[int, set[float]] = {}
                for size, _text, radius in names:
                    by_radius.setdefault(round(radius), set()).add(round(size, 3))
                mixed = {radius: sorted(sizes)
                         for radius, sizes in by_radius.items() if len(sizes) > 1}
                self.assertEqual(
                    mixed, {},
                    "labels of one generation rendered at different sizes "
                    f"(same radius, several sizes): {mixed}",
                )

    def test_an_under_floor_candidate_cannot_drag_a_generation_down(self):
        """The invariant that matters: aggregation only takes admissible input.

        The reporter's PDF renders one crown at 1.76 mm *and* 2.00 mm (measured
        from the PDF's own text matrices at identical radii), i.e. an under-floor
        candidate reached `min(candidates)` and lowered the whole ring. The
        escaping fitting path is not reachable from a synthetic fixture, so its
        effect is injected here: whichever path measures below the floor, the
        shared size a generation renders at must not follow it down.
        """
        from TwoWayFanChart import layout as layout_module

        original = layout_module._font_size_for_width
        # 18% below the floor -- exactly the reporter's observed ratio
        # (1.76 mm = 2.00 mm * 0.88).
        poisoned = _DESCENDANT_NAME_FLOOR_MM * 0.88

        def poisoned_fit(content, **kwargs):
            """Simulate the escaping path: a NAME measured below the floor."""
            if any(ch.isdigit() for ch in content):
                return original(content, **kwargs)
            return poisoned

        layout_module._font_size_for_width = poisoned_fit
        try:
            rows = _Fan(8, 3, 2).render()
        finally:
            layout_module._font_size_for_width = original

        names = _name_rows(rows)
        self.assertTrue(names, "the fixture must render some names")
        sizes = sorted({round(size, 3) for size, _text, _r in names})
        under = [s for s in sizes if s < _DESCENDANT_NAME_FLOOR_MM - 1e-9]
        self.assertEqual(under, [],
                         f"names below the {_DESCENDANT_NAME_FLOOR_MM} mm floor: {under}")
        self.assertNotIn(
            round(poisoned, 3), sizes,
            f"the under-floor candidate ({poisoned} mm) was adopted as a "
            f"rendered size; rendered sizes were {sizes}",
        )
        # Each crown must still render at a single size: the clamp must not let
        # an injected candidate split one generation across two sizes.
        by_radius: dict[int, set[float]] = {}
        for size, _text, radius in names:
            by_radius.setdefault(round(radius), set()).add(round(size, 3))
        mixed = {radius: sorted(values)
                 for radius, values in by_radius.items() if len(values) > 1}
        self.assertEqual(mixed, {}, f"one crown rendered at several sizes: {mixed}")

    def test_the_floor_is_the_direct_label_floor(self):
        """The name floor is the same 2.0 mm contract as direct labels."""
        self.assertEqual(_DESCENDANT_NAME_FLOOR_MM, 2.0)


if __name__ == "__main__":
    unittest.main()
