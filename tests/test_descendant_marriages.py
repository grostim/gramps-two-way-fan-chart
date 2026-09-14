import unittest

from TwoWayFanChart.config import ChartConfig
from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import calculate_canvas, layout_descendants
from TwoWayFanChart.model import (
    DescendantBranch,
    PersonNode,
    ScenePathText,
    SceneSector,
    UnionBranch,
)


def branch(handle, generation, *, spouse=None, children=()):
    unions = ()
    if spouse is not None:
        unions = (
            UnionBranch(
                family_handle=f"family-{handle}",
                spouse_handle=spouse,
                child_handles=tuple(child.person.handle for child in children),
                child_relations=("birth",) * len(children),
            ),
        )
    return DescendantBranch(
        position_id=f"desc-{handle}",
        person=PersonNode(handle, handle.upper()),
        generation=generation,
        unions=unions,
        children=tuple(children),
    )


class DescendantMarriageTests(unittest.TestCase):
    def _scene(self, *, paper=PaperSize.A0, generations=1, enabled=False, labels=None):
        canvas = calculate_canvas(
            PaperRegion(paper, Orientation.LANDSCAPE),
            ancestor_generations=0,
            descendant_generations=generations,
        )
        root = branch("child", 1, spouse="spouse")
        return layout_descendants(
            canvas,
            (root,),
            name_lookup={"child": "Child", "spouse": "Spouse"}.__getitem__,
            dates_lookup=lambda _handle: "",
            show_descendant_marriages=enabled,
            descendant_marriages=labels or {},
        )

    def test_option_defaults_to_disabled(self):
        self.assertFalse(ChartConfig().show_descendant_marriages)

    def test_descendant_marriage_sectors_are_opt_in(self):
        labels = {"family-child": ("x 1900 · Lyon", "x 1900")}
        disabled = self._scene(enabled=False, labels=labels)
        self.assertFalse(
            any(
                isinstance(node, ScenePathText) and "Lyon" in node.content
                for node in disabled.children
            )
        )

        enabled = self._scene(enabled=True, labels=labels)
        contents = [
            node.content for node in enabled.children if isinstance(node, ScenePathText)
        ]
        self.assertIn("x 1900 · Lyon", contents)
        self.assertGreaterEqual(
            sum(isinstance(node, SceneSector) for node in enabled.children),
            2,
        )

    def test_narrow_descendant_marriage_sector_keeps_only_the_year(self):
        long_place = "Saint-Germain-en-Laye, Île-de-France, France " * 8
        labels = {
            "family-child": (
                f"x 1900 · {long_place}",
                "x 1900",
            )
        }
        scene = self._scene(paper=PaperSize.A5, enabled=True, labels=labels)
        contents = [
            node.content for node in scene.children if isinstance(node, ScenePathText)
        ]
        self.assertIn("x 1900", contents)
        self.assertNotIn(
            f"x 1900 · {long_place}",
            contents,
        )

    def test_each_recorded_union_gets_its_own_sector(self):
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=0,
            descendant_generations=1,
        )
        root = DescendantBranch(
            position_id="desc-child",
            person=PersonNode("child", "CHILD"),
            generation=1,
            unions=(
                UnionBranch("family-first", "spouse-first", (), ()),
                UnionBranch("family-second", "spouse-second", (), ()),
            ),
            children=(),
        )
        scene = layout_descendants(
            canvas,
            (root,),
            name_lookup={
                "child": "Child",
                "spouse-first": "First spouse",
                "spouse-second": "Second spouse",
            }.__getitem__,
            show_descendant_marriages=True,
            descendant_marriages={
                "family-first": ("x 1900 · Lyon", "x 1900"),
                "family-second": ("x 1920 · Paris", "x 1920"),
            },
        )
        contents = [
            node.content for node in scene.children if isinstance(node, ScenePathText)
        ]
        self.assertIn("x 1900 · Lyon", contents)
        self.assertIn("x 1920 · Paris", contents)
        self.assertGreaterEqual(
            sum(isinstance(node, SceneSector) for node in scene.children),
            3,
        )


if __name__ == "__main__":
    unittest.main()
