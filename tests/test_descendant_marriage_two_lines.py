"""Issue #86 — descendant marriage bands carry the date and the place on two
lines from the second generation onward.

The band after each descendant crown shows the recorded marriage. Up to the
first generation it keeps one line; from generation 2 it stacks the date on the
first line and the place on the second, so a distant sector no longer has to
sacrifice the place when the pair cannot share one rail.
"""

import math
import re
import unittest

from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import (
    _DESCENDANT_MARRIAGE_LINE_LEADING_RATIO,
    _DESCENDANT_MARRIAGE_TWO_LINE_ENVELOPE_RATIO,
    _descendant_ring_layout,
    calculate_canvas,
    layout_descendants,
)
from TwoWayFanChart.model import (
    DescendantBranch,
    PersonNode,
    ScenePathText,
    UnionBranch,
    estimate_emblem_text_width,
)

_SEPARATOR = " · "
_PLACE = "Saint-Germain-en-Laye, Île-de-France, France"


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


def labels_for(max_depth, width=2):
    """Return the label map for a deterministic fan."""
    labels = {}
    leaves = width ** max_depth
    for depth in range(1, max_depth + 1):
        for index in range(leaves):
            labels[f"g{depth}-{index}"] = f"Prenom Nom G{depth} {index}"
            labels[f"g{depth}-{index}-sp"] = f"Conjoint G{depth} {index}"
    return labels


def build(max_depth, width=2):
    """Return a fan with ``width ** max_depth`` leaves per branch."""

    def rec(depth, index):
        spouse = f"g{depth}-{index}-sp"
        if depth == max_depth:
            return branch(f"g{depth}-{index}", depth, spouse=spouse)
        kids = tuple(rec(depth + 1, index * width + k) for k in range(width))
        return branch(f"g{depth}-{index}", depth, children=kids, spouse=spouse)

    return tuple(rec(1, i) for i in range(width))


def marriage_labels(max_depth, width=2):
    """Return one ``date · place`` union label per rendered marriage."""
    return {
        f"family-g{depth}-{index}": (
            f"⚭ 19{depth:02d}{_SEPARATOR}{_PLACE}",
            f"⚭ 19{depth:02d}",
        )
        for depth in range(1, max_depth + 1)
        for index in range(width ** max_depth)
    }


def band_lines(scene, canvas, generation_count):
    """Return the emitted text lines inside each marriage band, per crown."""
    _rings, bands = _descendant_ring_layout(
        canvas.descendant_inner_radius_mm,
        canvas.descendant_outer_radius_mm,
        generation_count,
        show_marriages=True,
    )
    cx = canvas.center_cx_mm
    cy = canvas.center_cy_mm
    result = {}
    for node in scene.children:
        if not isinstance(node, ScenePathText):
            continue
        match = re.match(r"^M ([\d.]+) ([\d.]+)", node.path)
        if match is None:
            continue
        radius = math.hypot(
            float(match.group(1)) - cx,
            float(match.group(2)) - cy,
        )
        for index, (band_inner, band_outer) in enumerate(bands):
            if band_inner - 1.0 <= radius <= band_outer + 1.0:
                result.setdefault(index + 1, []).append(
                    (radius, node.font_size, node.content)
                )
                break
    return result


def layout(paper=PaperSize.A0, generations=4, width=2):
    """Return ``(canvas, band lines)`` for the deterministic fan."""
    canvas = calculate_canvas(
        PaperRegion(paper, Orientation.LANDSCAPE),
        ancestor_generations=0,
        descendant_generations=generations,
    )
    return canvas, band_lines(_scene(generations, width, paper), canvas, generations)


def _scene(generations=4, width=2, paper=PaperSize.A0):
    """Return the descendant scene of the deterministic fan."""
    canvas = calculate_canvas(
        PaperRegion(paper, Orientation.LANDSCAPE),
        ancestor_generations=0,
        descendant_generations=generations,
    )
    labels = labels_for(generations, width)
    return layout_descendants(
        canvas,
        build(generations, width),
        name_lookup=labels.__getitem__,
        dates_lookup=lambda _handle: "° 1950 – † 2010",
        configured_generation_limit=generations,
        descendant_marriages=marriage_labels(generations, width),
        show_descendant_marriages=True,
    )


def band_radii(canvas, generation_count, generation):
    """Return the radial bounds of one marriage band."""
    _rings, bands = _descendant_ring_layout(
        canvas.descendant_inner_radius_mm,
        canvas.descendant_outer_radius_mm,
        generation_count,
        show_marriages=True,
    )
    return bands[generation - 1]


class DescendantMarriageTwoLineTests(unittest.TestCase):
    def test_first_generation_band_keeps_one_line(self):
        # Issue #86 is scoped "from G2": the direct-child band closes the ring
        # whose couple stack already owns that radial room, so it keeps the
        # single date-and-place line.
        _canvas, bands = layout(generations=2)
        contents = {content for _r, _s, content in bands[1]}
        self.assertEqual(contents, {f"⚭ 1901{_SEPARATOR}{_PLACE}"})

    def test_second_generation_band_splits_date_and_place(self):
        _canvas, bands = layout(generations=2)
        contents = {content for _r, _s, content in bands[2]}
        self.assertEqual(contents, {"⚭ 1902", _PLACE})

    def test_second_line_sits_outside_the_first_on_the_place_lane(self):
        canvas, bands = layout(generations=2)
        inner, outer = band_radii(canvas, 2, 2)
        date_radii = {r for r, _s, c in bands[2] if c == "⚭ 1902"}
        place_radii = {r for r, _s, c in bands[2] if c == _PLACE}
        self.assertTrue(date_radii)
        self.assertTrue(place_radii)
        self.assertLess(max(date_radii), min(place_radii))
        for radius, font_size, _content in bands[2]:
            self.assertGreaterEqual(radius - font_size / 2.0, inner)
            self.assertLessEqual(radius + font_size / 2.0, outer)
        font_size = bands[2][0][1]
        half_leading = font_size * _DESCENDANT_MARRIAGE_LINE_LEADING_RATIO / 2.0
        # The radii are read back from the serialized arc path, which is
        # rounded to four decimals, so compare at that precision.
        self.assertAlmostEqual(
            min(place_radii) - max(date_radii),
            2 * half_leading,
            places=3,
        )

    def test_every_two_line_generation_shares_one_font_size(self):
        _canvas, bands = layout(generations=4)
        for generation in (2, 3, 4):
            sizes = {size for _radius, size, _content in bands[generation]}
            self.assertEqual(
                len(sizes),
                1,
                msg=f"generation {generation} mixes sizes: {sorted(sizes)}",
            )
        # One crown size per generation, non-increasing with depth: the four
        # crowns of the acceptance fixture land at 2.8 / 2.8 / 2.8 / 2.68 mm.
        # Issue #90 nudged the deepest crown from 2.67 to 2.68 mm: the date and
        # place lines are now measured on the arc each is DRAWN on (one
        # half-leading inside/outside the mid radius) instead of on the band's
        # mid radius, which was under-stating the inner line's capacity.
        crown_sizes = [
            round(max(size for _radius, size, _content in bands[generation]), 2)
            for generation in (1, 2, 3, 4)
        ]
        self.assertEqual(crown_sizes, [2.80, 2.80, 2.80, 2.68])
        self.assertTrue(
            all(
                left >= right
                for left, right in zip(crown_sizes, crown_sizes[1:])
            )
        )

    def test_both_lines_stay_inside_the_band_radially(self):
        # The two-line stack must fit the reserved band: never overlapping the
        # crown's own dates inward, never spilling past the band outward.
        canvas, bands = layout(generations=4)
        rings, _bands = _descendant_ring_layout(
            canvas.descendant_inner_radius_mm,
            canvas.descendant_outer_radius_mm,
            4,
            show_marriages=True,
        )
        for generation in (2, 3, 4):
            inner, outer = band_radii(canvas, 4, generation)
            self.assertLessEqual(rings[generation - 1][1], inner)
            for radius, font_size, _content in bands[generation]:
                self.assertGreaterEqual(
                    radius - font_size / 2.0,
                    inner,
                    msg=f"generation {generation}: line overlaps the crown",
                )
                self.assertLessEqual(
                    radius + font_size / 2.0,
                    outer,
                    msg=f"generation {generation}: line spills past the band",
                )
            self.assertTrue(
                all(
                    radius + font_size * _DESCENDANT_MARRIAGE_LINE_LEADING_RATIO
                    / 2.0
                    <= outer
                    for radius, font_size, _content in bands[generation]
                ),
                msg=f"generation {generation}: stack envelope exceeds the band",
            )

    def test_narrow_band_keeps_the_single_line_year_fallback(self):
        # Issue #46's degradation policy survives: when the band cannot stack
        # two readable lines, it keeps one line and the year alone rather than
        # truncating the place.
        _canvas, bands = layout(paper=PaperSize.A5, generations=4)
        for generation in (1, 2, 3, 4):
            contents = {content for _r, _s, content in bands[generation]}
            self.assertTrue(
                all(_SEPARATOR not in content for content in contents),
                msg=f"generation {generation} kept a joined label on A5: {contents}",
            )
            self.assertTrue(
                all(content.startswith("⚭") for content in contents),
                msg=f"generation {generation} lost its date: {contents}",
            )

    def test_second_generation_keeps_both_lines_on_a_dense_fan(self):
        # A denser fan narrows every sector; the place must still reach its own
        # line on the second crown instead of collapsing back to the year.
        canvas, bands = layout(generations=3, width=4)
        contents = {content for _r, _s, content in bands[2]}
        self.assertIn(_PLACE, contents)
        self.assertTrue(
            any(content.startswith("⚭") for content in contents),
            "the second crown lost its date line",
        )

    def test_each_line_fits_its_own_arc(self):
        # Every emitted two-line sector must keep both lines inside the arc
        # their own radius offers. The usable arc is read from the node's own
        # serialized path, whose endpoints `_arc_text_path` has already inset
        # by the margin, so subtracting the margin again would double-count it.
        canvas, _bands = layout(generations=4)
        cx = canvas.center_cx_mm
        cy = canvas.center_cy_mm
        scene = _scene(generations=4)
        checked = 0
        worst_ratio = 0.0
        for node in scene.children:
            if not isinstance(node, ScenePathText):
                continue
            match = re.match(
                r"^M ([\d.]+) ([\d.]+) A ([\d.]+) [\d.]+ [\d.]+ [01] [01] "
                r"([\d.]+) ([\d.]+)$",
                node.path,
            )
            if match is None:
                continue
            x0, y0 = float(match.group(1)), float(match.group(2))
            radius = float(match.group(3))
            x1, y1 = float(match.group(4)), float(match.group(5))
            node_radius = math.hypot(x0 - cx, y0 - cy)
            generation = next(
                (
                    index
                    for index in (2, 3, 4)
                    if (
                        band_radii(canvas, 4, index)[0] - 1.0
                        <= node_radius
                        <= band_radii(canvas, 4, index)[1] + 1.0
                    )
                ),
                None,
            )
            if generation is None:
                continue
            a0 = math.atan2(y0 - cy, x0 - cx)
            a1 = math.atan2(y1 - cy, x1 - cx)
            usable_sweep = abs(math.degrees(a1 - a0)) % 360.0
            capacity = radius * math.radians(usable_sweep)
            width = estimate_emblem_text_width(node.content, node.font_size)
            # The layout measures this same arc, minus the renderer's own
            # sweep margin (up to 2 mm of arc, 0.3 mm at minimum); the residual
            # is that margin, so allow it explicitly rather than hiding it in a
            # larger tolerance.
            self.assertLessEqual(
                width,
                capacity + 2.0,
                msg=(
                    f"generation {generation}: line {node.content[:24]!r} "
                    f"is {width:.3f} mm wide against {capacity:.3f} mm of arc"
                ),
            )
            worst_ratio = max(worst_ratio, width / capacity if capacity else 0.0)
            checked += 1
        self.assertGreaterEqual(checked, 20, "expected two-line sectors to check")
        # The guard must be doing work, not merely be satisfied by luck: at the
        # deepest crown the place line fills most of its arc, which is exactly
        # the case that would overflow without the envelope bound.
        self.assertGreater(
            worst_ratio,
            0.9,
            msg=f"the tightest line only fills {worst_ratio:.3f} of its arc",
        )

    def test_two_line_stack_is_bounded_by_the_band_envelope(self):
        # The band's radial depth is the binding constraint that admits the
        # split, so assert it as the contract: at the shared size the
        # (leading + one em) envelope must fit the band, and the leading must
        # move each line by exactly half the leading ratio times the size.
        canvas, bands = layout(generations=4)
        for generation in (2, 3, 4):
            inner, outer = band_radii(canvas, 4, generation)
            sizes = {size for _r, size, _c in bands[generation]}
            self.assertEqual(len(sizes), 1)
            size = sizes.pop()
            self.assertLessEqual(
                size * _DESCENDANT_MARRIAGE_TWO_LINE_ENVELOPE_RATIO,
                outer - inner + 1e-9,
                msg=(
                    f"generation {generation}: envelope "
                    f"{size * _DESCENDANT_MARRIAGE_TWO_LINE_ENVELOPE_RATIO:.3f} "
                    f"exceeds the {outer - inner:.3f} mm band"
                ),
            )
            # Every line of the generation shares the size, so the envelope
            # test above is the whole family's contract. Confirm the emitted
            # radii actually straddle the band the way the helper says.
            mid = (inner + outer) / 2.0
            half = size * _DESCENDANT_MARRIAGE_LINE_LEADING_RATIO / 2.0
            radii = sorted(r for r, _s, _c in bands[generation])
            self.assertAlmostEqual(min(radii), mid - half, places=3)
            self.assertAlmostEqual(max(radii), mid + half, places=3)

    def test_disabled_option_emits_no_marriage_line(self):
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=0,
            descendant_generations=3,
        )
        labels = labels_for(3)
        scene = layout_descendants(
            canvas,
            build(3),
            name_lookup=labels.__getitem__,
            dates_lookup=lambda _handle: "",
            configured_generation_limit=3,
            descendant_marriages=marriage_labels(3),
            show_descendant_marriages=False,
        )
        contents = [
            node.content
            for node in scene.children
            if isinstance(node, ScenePathText)
        ]
        self.assertNotIn(_PLACE, contents)
        self.assertFalse(any(content.startswith("⚭") for content in contents))


if __name__ == "__main__":
    unittest.main()
