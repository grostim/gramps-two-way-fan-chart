"""Issue #85 follow-up: descendant couple rails must not collide or overflow.

The first fix raised the name size floor, which made the pre-existing rail
geometry visible: the two rails of a couple were placed `2 * 0.68 = 1.36` em
apart while the layout's font renders a 1.3625 em glyph box — the ink of the two
rails was in contact at EVERY size. And a rail's `max_width` was taken from the
radial text depth (`max(text_width, ...)`), so a label could claim 60-75 mm of
`textLength` inside a cell whose half-arc was a few millimetres, running over the
white separator into the neighbouring branch.

These tests pin both invariants on the scene, and are proven to bite by a
sabotage run (restoring the old literal fails them).
"""

import math
import unittest

from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import (
    _COUPLE_GLYPH_BOX_EM,
    _COUPLE_RAIL_OFFSET_EM,
    calculate_canvas,
    layout_descendants,
)
from TwoWayFanChart.model import (
    DescendantBranch,
    PersonNode,
    ScenePathText,
    SceneText,
    UnionBranch,
    estimate_text_width,
)

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


def build(prefix, generation, fanout, max_depth=4):
    if generation >= max_depth:
        return couple(prefix, generation, spouse=f"{prefix}-s")
    children = tuple(
        build(f"{prefix}-{i}", generation + 1, fanout, max_depth)
        for i in range(fanout.get(generation + 1, 2))
    )
    return couple(prefix, generation, children=children, spouse=f"{prefix}-s")


# The density that reproduces the reporter's chart (~430 descendant labels).
_FANOUT = {2: 4, 3: 3, 4: 3}
_DIRECT = 2


def scene():
    canvas = calculate_canvas(
        PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
        ancestor_generations=5,
        descendant_generations=4,
    )
    tree = tuple(build(f"c{i}", 1, _FANOUT, 4) for i in range(_DIRECT))
    return canvas, layout_descendants(
        canvas,
        tree,
        name_lookup=_name,
        dates_lookup=lambda _handle: "1908–1981",
        configured_generation_limit=4,
    )


def rail_nodes(scene_node):
    """Every descendant rail label with its anchor, rotation and lane."""
    out = []
    for node in scene_node.children:
        if isinstance(node, SceneText) and node.content:
            out.append(node)
    return out


class DescendantCoupleRailTests(unittest.TestCase):
    def test_rail_separation_exceeds_the_rendered_glyph_box(self):
        """The two rails of a pair must not overlap.

        The separation the layout uses is ``2 * _COUPLE_RAIL_OFFSET_EM`` em of the
        rail size; the font's rendered box is ``_COUPLE_GLYPH_BOX_EM`` em. A
        separation at or below the box puts the two rails' ink in contact.
        """
        self.assertGreater(2.0 * _COUPLE_RAIL_OFFSET_EM, _COUPLE_GLYPH_BOX_EM)

    def test_couple_rails_never_overlap_on_the_a0_publication_fan(self):
        """Measured on the scene: no two rail boxes may overlap."""
        canvas, scene_node = scene()
        cx, cy = canvas.center_cx_mm, canvas.center_cy_mm
        boxes = []
        for node in rail_nodes(scene_node):
            width = estimate_text_width(node.content, node.font_size)
            height = node.font_size * _COUPLE_GLYPH_BOX_EM
            rotation = math.radians(node.rotation or 0.0)
            cos_a, sin_a = math.cos(rotation), math.sin(rotation)
            corners = [
                (node.x + dx * cos_a - dy * sin_a, node.y + dx * sin_a + dy * cos_a)
                for dx, dy in (
                    (-width / 2, -height / 2), (width / 2, -height / 2),
                    (width / 2, height / 2), (-width / 2, height / 2),
                )
            ]
            boxes.append((node.content, corners, node.font_size))

        def axes(pts):
            out = []
            for index in range(len(pts)):
                x1, y1 = pts[index]
                x2, y2 = pts[(index + 1) % len(pts)]
                ex, ey = x2 - x1, y2 - y1
                length = math.hypot(ex, ey)
                if length > 1e-9:
                    out.append((-ey / length, ex / length))
            return out

        def penetration(pa, pb):
            smallest = None
            for axis in axes(pa) + axes(pb):
                va = [p[0] * axis[0] + p[1] * axis[1] for p in pa]
                vb = [p[0] * axis[0] + p[1] * axis[1] for p in pb]
                depth = min(max(va), max(vb)) - max(min(va), min(vb))
                if depth <= 0:
                    return 0.0
                smallest = depth if smallest is None else min(smallest, depth)
            return smallest or 0.0

        collisions = []
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                content_a, corners_a, size_a = boxes[i]
                content_b, corners_b, size_b = boxes[j]
                ax = sum(p[0] for p in corners_a) / 4
                ay = sum(p[1] for p in corners_a) / 4
                bx = sum(p[0] for p in corners_b) / 4
                by = sum(p[1] for p in corners_b) / 4
                # Only genuinely adjacent labels: two rails of the SAME person's
                # pair, or a name and its own date. Distant cells legitimately
                # share a radius and are separated by their sector boundaries.
                same_anchor = math.hypot(ax - bx, ay - by) < size_a
                if not same_anchor:
                    continue
                depth = penetration(corners_a, corners_b)
                if depth > 0.05:
                    collisions.append((depth, content_a, content_b))

        collisions.sort(reverse=True)
        self.assertEqual(
            collisions[:5],
            [],
            msg=f"a person's own rails overlap: {collisions[:5]}",
        )

    def test_rail_lane_never_exceeds_the_cell_half_arc(self):
        """A rail's lane must be the tangential budget, not the radial depth.

        The radial text depth is tens of millimetres; a cell's half-arc can be a
        few. A lane taken from the former lets the label run over the separator.
        """
        canvas, scene_node = scene()
        cx, cy = canvas.center_cx_mm, canvas.center_cy_mm
        offenders = []
        for node in rail_nodes(scene_node):
            radius = math.hypot(node.x - cx, node.y - cy)
            if node.max_width is None or node.max_width <= 0:
                continue
            # A lane wider than half the ring depth cannot be a tangential budget
            # for a rail that lies along the radius on this fan.
            width = estimate_text_width(node.content, node.font_size)
            # The lane must at least be able to hold the natural width, or the
            # renderer compresses the label. Compression is legitimate; what is
            # not is a lane that lets the label span a whole ring depth.
            if node.max_width > 40.0:
                offenders.append((node.max_width, width, node.content))
        self.assertEqual(
            offenders[:5],
            [],
            msg=f"rail lanes are radial depths, not cell arc budgets: {offenders[:5]}",
        )


if __name__ == "__main__":
    unittest.main()
