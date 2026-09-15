import unittest

from TwoWayFanChart.config import ChartConfig
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

    def test_marriage_cap_preserves_the_measured_year_fallback(self):
        # Issue #56 follow-up: when the shared marriage size is capped by a
        # dense generation's name size, the render pass must keep the label
        # choice made during measurement (year-only) instead of re-selecting
        # the full date-and-place string at the tiny capped size.
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A5, Orientation.LANDSCAPE),
            ancestor_generations=0,
            descendant_generations=2,
        )
        labels = {"child": "Child", "spouse": "Spouse"}
        children = []
        marriage_labels = {}
        for index in range(6):
            labels[f"c{index}"] = f"Alexandre Guillaume De La Rochefoucauld {index}"
            labels[f"c{index}-sp"] = f"Bernadette Charlotte De La Rochefoucauld {index}"
            children.append(branch(f"c{index}", 2, spouse=f"c{index}-sp"))
            marriage_labels[f"family-c{index}"] = (
                f"x 19{index:02d} · Saint-Germain-en-Laye, Île-de-France, France",
                f"x 19{index:02d}",
            )
        root = branch("child", 1, spouse="spouse", children=tuple(children))
        scene = layout_descendants(
            canvas,
            (root,),
            name_lookup=labels.__getitem__,
            dates_lookup=lambda _handle: "",
            show_descendant_marriages=True,
            descendant_marriages=marriage_labels,
        )
        marriage_nodes = [
            node
            for node in scene.children
            if isinstance(node, (SceneText, ScenePathText))
            and node.content.startswith("x 19")
        ]
        self.assertEqual(len(marriage_nodes), 6)
        self.assertTrue(
            all(node.content in {f"x 19{i:02d}" for i in range(6)} for node in marriage_nodes),
            msg="the capped render must keep the measured year-only labels",
        )

    def test_marriage_bands_emit_sectors_even_without_any_label(self):
        # P2 follow-up on issue #56: a lineage whose families carry no
        # marriage label must still get its colored sectors; the band width
        # is reserved and an unlabeled band is a transparent hole otherwise.
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=0,
            descendant_generations=2,
        )
        labels = {"child": "Child", "spouse": "Spouse"}
        children = []
        marriage_labels = {}
        for index in range(4):
            labels[f"c{index}"] = f"Child {index}"
            labels[f"c{index}-sp"] = f"Spouse {index}"
            children.append(branch(f"c{index}", 2, spouse=f"c{index}-sp"))
            marriage_labels[f"family-c{index}"] = ("", "")
        root = branch("child", 1, spouse="spouse", children=tuple(children))
        scene = layout_descendants(
            canvas,
            (root,),
            name_lookup=labels.__getitem__,
            dates_lookup=lambda _handle: "",
            show_descendant_marriages=True,
            descendant_marriages=marriage_labels,
        )
        self.assertGreaterEqual(
            sum(isinstance(node, SceneSector) for node in scene.children),
            5,
            msg="unlabeled marriage bands must still emit their sectors",
        )

    def test_option_defaults_to_enabled(self):
        self.assertTrue(ChartConfig().show_descendant_marriages)

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

    def test_dense_marriage_rings_keep_year_fallback_at_shared_minimum(self):
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A5, Orientation.LANDSCAPE),
            ancestor_generations=0,
            descendant_generations=1,
        )
        year = "1920-1922"
        long_label = "1920-1922 · Un lieu extrêmement long pour ce secteur étroit"
        unions = tuple(
            UnionBranch(f"family-{index}", f"spouse-{index}", (), ())
            for index in range(100)
        )
        root = DescendantBranch(
            position_id="desc-root",
            person=PersonNode("root", "ROOT"),
            generation=1,
            unions=unions,
            children=(),
        )
        scene = layout_descendants(
            canvas,
            (root,),
            name_lookup=(
                {"root": "Root Person"} | {f"spouse-{index}": f"Spouse {index}" for index in range(100)}
            ).__getitem__,
            show_descendant_marriages=True,
            descendant_marriages={
                f"family-{index}": (long_label, year)
                for index in range(100)
            },
        )
        marriage_texts = [
            node
            for node in scene.children
            if isinstance(node, ScenePathText) and node.content.startswith("19")
        ]
        # The shared minimum size is wider than these 1.8° sectors; the year
        # fallback must still be emitted and let the renderer compress it.
        self.assertGreaterEqual(len(marriage_texts), 100)
        self.assertTrue(
            all(node.content == year for node in marriage_texts),
            msg="dense marriage sectors must keep the year label",
        )

    def test_marriage_font_never_exceeds_the_concerned_names(self):
        # Issue #56: the marriage label must stay at or below the font size
        # of the individuals it concerns. With six crowded second-generation
        # branches carrying long names, the shared generation name size
        # collapses while the marriage band could still fit a much larger
        # label; the band must follow the names instead.
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A5, Orientation.LANDSCAPE),
            ancestor_generations=0,
            descendant_generations=2,
        )
        labels = {"child": "Child", "spouse": "Spouse"}
        children = []
        marriage_labels = {}
        for index in range(6):
            labels[f"c{index}"] = f"Alexandre Guillaume De La Rochefoucauld {index}"
            labels[f"c{index}-sp"] = f"Bernadette Charlotte De La Rochefoucauld {index}"
            children.append(branch(f"c{index}", 2, spouse=f"c{index}-sp"))
            marriage_labels[f"family-c{index}"] = (
                f"x 19{index:02d} · Lyon",
                f"x 19{index:02d}",
            )
        root = branch("child", 1, spouse="spouse", children=tuple(children))
        scene = layout_descendants(
            canvas,
            (root,),
            name_lookup=labels.__getitem__,
            dates_lookup=lambda _handle: "",
            show_descendant_marriages=True,
            descendant_marriages=marriage_labels,
        )
        name_nodes = [
            node
            for node in scene.children
            if isinstance(node, (SceneText, ScenePathText))
            and "Rochefoucauld" in node.content
        ]
        marriage_nodes = [
            node
            for node in scene.children
            if isinstance(node, ScenePathText) and node.content.startswith("x 19")
        ]
        self.assertTrue(name_nodes)
        self.assertEqual(len(marriage_nodes), 6)
        shared_name_size = min(node.font_size for node in name_nodes)
        for node in marriage_nodes:
            self.assertLessEqual(
                node.font_size,
                shared_name_size,
                msg=(
                    "marriage font must not exceed the concerned names' font "
                    f"(marriage {node.font_size:.3f}, name {shared_name_size:.3f})"
                ),
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
