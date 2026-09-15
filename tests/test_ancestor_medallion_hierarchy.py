import math
import unittest

from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import (
    _ancestor_content_geometry,
    calculate_canvas,
    layout_ancestors,
)
from TwoWayFanChart.model import SceneCircle, SceneImage


def _full_slots(num_gens, with_portraits=False):
    """Complete ancestor fixture: 2**gen slots per generation, both lineages."""
    slots = []
    for gen in range(1, num_gens + 1):
        count = 2 ** (gen - 1)
        for index in range(count):
            portrait = "data:image/png;base64,AAAA" if with_portraits else None
            slots.append(
                (
                    f"ancestor-a-{gen}-{index}",
                    f"Label A{gen}-{index}",
                    "",
                    portrait,
                )
            )
            slots.append(
                (
                    f"ancestor-b-{gen}-{index}",
                    f"Label B{gen}-{index}",
                    "",
                    portrait,
                )
            )
    return tuple(slots)


def _medallion_radii_by_generation(canvas, scene):
    """Group emitted medallions by generation via their ring distance.

    Each ring places its medallions at a single distinct center distance
    (``inner_radius + offset`` per ring), so grouping by distance and using
    the group size (2**gen medallions per ring) recovers the generation.
    Returns a dict {generation: min radius}.
    """
    by_distance: dict[float, list[float]] = {}
    for child in scene.children:
        if isinstance(child, SceneCircle):
            distance = math.hypot(
                child.cx - canvas.center_cx_mm,
                child.cy - canvas.center_cy_mm,
            )
            by_distance.setdefault(round(distance, 3), []).append(child.r)
    radii = {}
    for distance, radius_list in sorted(by_distance.items()):
        generation = round(math.log2(len(radius_list)))
        radii[generation] = min(radius_list)
    return radii


class AncestorMedallionHierarchyTests(unittest.TestCase):
    """Issue #76: G4/G5 medallions must never exceed the previous generation."""

    def _a0_canvas(self, ancestor_generations):
        return calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=ancestor_generations,
            descendant_generations=0,
        )

    def test_issue76_g4_and_g5_medallions_never_exceed_previous_generation(self):
        # Without portraits ``med_r == image_r``, so the emitted circle radii
        # are exactly the ``image_r`` values the issue constrains.
        canvas = self._a0_canvas(ancestor_generations=5)
        scene = layout_ancestors(canvas, _full_slots(5))
        radii = _medallion_radii_by_generation(canvas, scene)
        self.assertEqual(set(radii), {1, 2, 3, 4, 5})
        # G1-G3 keep their established proportions (G3 > G2 > G1 is the
        # intended publication presence); from G3 outward the hierarchy is
        # non-increasing: G4 <= G3 and G5 <= G4.
        self.assertLessEqual(radii[4], radii[3] + 1e-9)
        self.assertLessEqual(radii[5], radii[4] + 1e-9)

    def test_issue76_portrait_images_follow_the_same_chain(self):
        # Portrait path: G4+ renders SceneImage at ``image_r * 24/26`` below
        # the inner-edge border, G1-G3 at ``image_r``. The drawn portrait
        # radii must therefore never increase from G3 outward either.
        canvas = self._a0_canvas(ancestor_generations=5)
        scene = layout_ancestors(canvas, _full_slots(5, with_portraits=True))
        circles = _medallion_radii_by_generation(canvas, scene)
        images_by_distance: dict[float, list[float]] = {}
        for child in scene.children:
            if isinstance(child, SceneImage):
                distance = math.hypot(
                    child.cx - canvas.center_cx_mm,
                    child.cy - canvas.center_cy_mm,
                )
                images_by_distance.setdefault(round(distance, 3), []).append(child.r)
        image_min_by_gen = {}
        for distance, radius_list in sorted(images_by_distance.items()):
            generation = round(math.log2(len(radius_list)))
            image_min_by_gen[generation] = min(radius_list)
        self.assertEqual(set(image_min_by_gen), {1, 2, 3, 4, 5})
        self.assertLessEqual(image_min_by_gen[4], image_min_by_gen[3] + 1e-9)
        self.assertLessEqual(image_min_by_gen[5], image_min_by_gen[4] + 1e-9)
        # And each G4/G5 border stays strictly inside the sibling circles.
        self.assertLessEqual(image_min_by_gen[4], circles[4] + 1e-9)
        self.assertLessEqual(image_min_by_gen[5], circles[5] + 1e-9)

    def test_issue76_dense_sectors_keep_the_inner_edge_constraint(self):
        # Six generations on A0: the G6 ring is the narrowest (2.688° sweep).
        # The sector solve (edge="inner") must stay the binding constraint
        # there, so G6 shrinks below the chained G5 cap instead of growing.
        canvas = self._a0_canvas(ancestor_generations=6)
        scene = layout_ancestors(canvas, _full_slots(6))
        radii = _medallion_radii_by_generation(canvas, scene)
        self.assertEqual(set(radii), {1, 2, 3, 4, 5, 6})
        self.assertLessEqual(radii[6], radii[5] + 1e-9)
        # G6 is genuinely sector-limited: its solved radius must be smaller
        # than the chained cap inherited from the previous generation.
        self.assertLess(radii[6], radii[5])

    def test_issue76_g1_to_g3_geometry_is_unchanged_by_the_cap(self):
        # The relative cap is threaded only from generation four onward: the
        # G1-G3 circles emitted by a 5-generation layout must match the legacy
        # geometry (no ``max_image_r``) evaluated at the ring bounds the
        # layout really used — proving the mockup proportions are untouched.
        from TwoWayFanChart.model import SceneSector

        canvas = self._a0_canvas(ancestor_generations=5)
        scene = layout_ancestors(canvas, _full_slots(5))
        sectors = [
            node
            for node in scene.children
            if isinstance(node, SceneSector) and node.sweep_angle > 0.0
        ]
        rings: dict[int, tuple[float, float]] = {}
        for node in sectors:
            # G1: 86°, G2: 43°, G3: 21.5° sectors define each ring.
            generation = {86.0: 1, 43.0: 2, 21.5: 3}.get(
                round(node.sweep_angle, 1)
            )
            if generation is not None:
                rings[generation] = (node.inner_radius, node.outer_radius)
        radii = _medallion_radii_by_generation(canvas, scene)
        for gen in (1, 2, 3):
            inner_r, outer_r_ring = rings[gen]
            legacy = _ancestor_content_geometry(
                generation=gen,
                inner_radius=inner_r,
                outer_radius=outer_r_ring,
                fan_outer_radius=canvas.ancestor_outer_radius_mm,
                sweep_angle=86.0 / (2 ** (gen - 1)),
            )
            # Without a portrait, med_r == image_r, so the emitted circle is
            # the exact legacy image radius.
            self.assertAlmostEqual(
                radii[gen], legacy[3], places=6, msg=f"G{gen} changed by the cap"
            )


if __name__ == "__main__":
    unittest.main()
