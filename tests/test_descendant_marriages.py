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

    def test_marriage_bands_keep_first_generation_life_dates(self):
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=0,
            descendant_generations=2,
        )
        root = branch(
            "child",
            1,
            spouse="spouse",
            children=(branch("grandchild", 2, spouse="grandchild-spouse"),),
        )
        scene = layout_descendants(
            canvas,
            (root,),
            name_lookup={
                "child": "Child",
                "spouse": "Spouse",
                "grandchild": "Grandchild",
                "grandchild-spouse": "Grandchild Spouse",
            }.__getitem__,
            dates_lookup=lambda _handle: "1950-2000",
            show_descendant_marriages=True,
            descendant_marriages={"family-child": ("x 1900 · Lyon", "x 1900")},
        )
        contents = [
            node.content for node in scene.children if isinstance(node, ScenePathText)
        ]
        self.assertIn("1950-2000", contents)

    def test_marriages_share_one_font_size_per_generation(self):
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A5, Orientation.LANDSCAPE),
            ancestor_generations=0,
            descendant_generations=3,
        )
        labels = {
            "child": "Child",
            "spouse": "Spouse",
            "crowded-a": "Crowded A",
            "crowded-a-sp": "Crowded A Spouse",
            "crowded-b": "Crowded B",
            "crowded-b-sp": "Crowded B Spouse",
            "crowded-c": "Crowded C",
            "crowded-c-sp": "Crowded C Spouse",
            "sparse": "Sparse",
            "sparse-sp": "Sparse Spouse",
            "grandchild": "Grandchild",
            "grandchild-spouse": "Grandchild Spouse",
        }
        root = branch(
            "child",
            1,
            spouse="spouse",
            children=(
                branch(
                    "crowded-a",
                    2,
                    spouse="crowded-a-sp",
                    children=(
                        branch("crowded-b", 3, spouse="crowded-b-sp"),
                        branch("crowded-c", 3, spouse="crowded-c-sp"),
                    ),
                ),
                branch("sparse", 2, spouse="sparse-sp"),
                branch("grandchild", 2, spouse="grandchild-spouse"),
            ),
        )
        # The three generation-two marriages sit in sectors of widely
        # different sweeps; they must still share one font size.
        mariage_labels = {
            "family-crowded-a": ("m 1920 · Un lieu très long partagé", "m 1920"),
            "family-sparse": ("m 1930 · Autre lieu complet", "m 1930"),
            "family-grandchild": ("m 1940 · Dernier lieu", "m 1940"),
        }
        scene = layout_descendants(
            canvas,
            (root,),
            name_lookup=labels.__getitem__,
            show_descendant_marriages=True,
            descendant_marriages=mariage_labels,
        )
        marriage_paths = [
            node
            for node in scene.children
            if isinstance(node, ScenePathText) and node.content.startswith("m ")
        ]
        self.assertEqual(len(marriage_paths), 3)
        first_size = marriage_paths[0].font_size
        self.assertTrue(
            all(node.font_size == first_size for node in marriage_paths),
            msg=f"marriage fonts differ: {[n.font_size for n in marriage_paths]}",
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
