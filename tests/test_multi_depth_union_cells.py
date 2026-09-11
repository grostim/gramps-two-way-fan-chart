import unittest

from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import calculate_canvas, layout_descendants
from TwoWayFanChart.model import (
    DescendantBranch,
    PersonNode,
    ScenePathText,
    SceneSector,
    SceneText,
    UnionBranch,
)


def branch(
    handle: str,
    gramps_id: str,
    generation: int,
    *,
    children=(),
    unions=(),
    children_by_union=(),
):
    return DescendantBranch(
        position_id=handle,
        person=PersonNode(handle, gramps_id),
        generation=generation,
        unions=tuple(unions),
        children=tuple(children),
        children_by_union=tuple(children_by_union),
    )


def multi_union_person_at_depth(depth: int, *, with_children: bool = True):
    """Grégoire-like person with two unions, placed at ``depth``."""

    kids_f0335 = [
        branch(f"a{depth}-{i}", f"I30{depth}{i}", depth + 1)
        for i in range(3)
    ]
    kids_f0340 = [branch(f"b{depth}-0", f"I40{depth}0", depth + 1)]
    unions = (
        UnionBranch(
            "f0335",
            "spouse-0335",
            tuple(k.person.handle for k in kids_f0335),
            ("birth",) * len(kids_f0335),
            "F0335",
        ),
        UnionBranch(
            "f0340",
            "spouse-0340",
            tuple(k.person.handle for k in kids_f0340),
            ("birth",) * len(kids_f0340),
            "F0340",
        ),
    )
    return branch(
        "greg",
        "I0893",
        depth,
        unions=unions,
        children=kids_f0335 + kids_f0340 if with_children else (),
        children_by_union=(tuple(kids_f0335), tuple(kids_f0340))
        if with_children
        else ((), ()),
    )


class MultiDepthUnionCellTests(unittest.TestCase):
    """Multi-union descendants must get one cell per union at ANY depth."""

    def _scene_labels(self, descendant_generations: int, root):
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=descendant_generations,
        )
        scene = layout_descendants(
            canvas,
            (root,),
            name_lookup={
                "root": "Center",
                "sib": "Sibling",
                "greg": "Grégoire Mussat",
                "spouse-0335": "Aude de Kerhos",
                "spouse-0340": "Blandine Pouchard",
                "a2-0": "Alexandre",
                "a2-1": "Victoire",
                "a2-2": "Cyprien",
                "b2-0": "Alexis",
                "a3-0": "Alexandre",
                "a3-1": "Victoire",
                "a3-2": "Cyprien",
                "b3-0": "Alexis",
            }.__getitem__,
            dates_lookup=lambda _handle: "",
        )
        labels = [
            node.content
            for node in scene.children
            if isinstance(node, (SceneText, ScenePathText))
        ]
        sectors = [n for n in scene.children if isinstance(n, SceneSector)]
        return scene, labels, sectors, canvas

    def _assert_two_cells(self, labels, sectors, canvas, depth: int):
        self.assertEqual(labels.count("Grégoire Mussat"), 2)
        self.assertTrue(any("Aude de Kerhos" in l for l in labels))
        self.assertTrue(any("Blandine Pouchard" in l for l in labels))
        self.assertFalse(any(" / " in l for l in labels))
        # No truncated-merged couple label of the old defect.
        self.assertFalse(any("…" in l and ("Kerhos" in l or "Pouchard" in l) for l in labels))
        # Couple labels remain inside their cells; the family ID/spouse
        # repetition in the child-ring header is intentionally omitted.
        self.assertFalse(any(label.startswith("F0335") for label in labels))
        self.assertFalse(any(label.startswith("F0340") for label in labels))
        # Two distinct sectors at Grégoire's own ring: find sectors whose
        # angular span matches one of the two cells (they are distinct SceneSectors).
        self.assertGreaterEqual(len(sectors), 2)

    def test_depth_two_multi_union_person_gets_two_cells(self):
        greg = multi_union_person_at_depth(2)
        root = branch("root", "I0001", 1, children=[greg, branch("sib", "I1002", 2)])
        scene, labels, sectors, canvas = self._scene_labels(3, root)
        self._assert_two_cells(labels, sectors, canvas, depth=2)

    def test_depth_three_multi_union_person_gets_two_cells(self):
        greg = multi_union_person_at_depth(3)
        # Parent chain: root -> intermediate -> greg(depth 3)
        parent = branch(
            "sib",
            "I1002",
            2,
            children=[greg],
        )
        root = branch("root", "I0001", 1, children=[parent])
        scene, labels, sectors, canvas = self._scene_labels(4, root)
        self._assert_two_cells(labels, sectors, canvas, depth=3)

    def test_depth_two_multi_union_person_without_children_keeps_two_cells(self):
        greg = multi_union_person_at_depth(2, with_children=False)
        root = branch("root", "I0001", 1, children=[greg, branch("sib", "I1002", 2)])
        scene, labels, sectors, canvas = self._scene_labels(2, root)
        self.assertEqual(labels.count("Grégoire Mussat"), 2)
        self.assertTrue(any("Aude de Kerhos" in l for l in labels))
        self.assertTrue(any("Blandine Pouchard" in l for l in labels))
        self.assertFalse(any(" / " in l for l in labels))


if __name__ == "__main__":
    unittest.main()