import ast
import tempfile
import unittest
from pathlib import Path

from TwoWayFanChart.config import ChartConfig
from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import calculate_canvas, layout_ancestors, layout_descendants
from TwoWayFanChart.model import (
    DescendantBranch,
    PersonNode,
    SceneMarker,
    SceneNode,
    ScenePage,
    ScenePathText,
    UnionBranch,
)
from TwoWayFanChart.highlight import resolve_highlight_tag_handle
from TwoWayFanChart.privacy import highlighted_for_state
from TwoWayFanChart.render_svg import render_svg


ROOT = Path(__file__).parents[1]
OPTIONS_PATH = ROOT / "TwoWayFanChart" / "options.py"


def person(handle: str) -> PersonNode:
    return PersonNode(handle=handle, gramps_id=handle.upper())


def branch(handle: str, generation: int, *, children=(), spouse=None):
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


class HighlightContractTests(unittest.TestCase):
    def test_highlight_tag_is_optional_and_does_not_change_default(self):
        config = ChartConfig()
        self.assertEqual(config.highlight_tag, "")
        self.assertEqual(config.with_changes(highlight_tag="Cité").highlight_tag, "Cité")

    def test_highlight_tag_is_resolved_by_name_not_a_fixed_handle(self):
        class Tag:
            def get_handle(self):
                return "dynamic-tag-handle"

        class Database:
            def __init__(self):
                self.calls = []

            def get_tag_from_name(self, name):
                self.calls.append(name)
                return Tag()

        db = Database()
        tag_name = "Cité dans les Mémoires de Benoît Coste"
        self.assertEqual(resolve_highlight_tag_handle(db, tag_name), "dynamic-tag-handle")
        self.assertEqual(db.calls, [tag_name])
        self.assertIsNone(resolve_highlight_tag_handle(db, ""))

    def test_menu_exposes_the_same_highlight_tag_field(self):
        source = OPTIONS_PATH.read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn('"highlight_tag"', source)
        self.assertIn('StringOption(_("Highlight tag"), "")', source)

    def test_privacy_clears_highlight_for_masked_and_excluded_people(self):
        from TwoWayFanChart.model import VisibilityState

        self.assertTrue(highlighted_for_state(True, VisibilityState.VISIBLE))
        self.assertTrue(highlighted_for_state(True, VisibilityState.NAME_ONLY))
        self.assertFalse(highlighted_for_state(True, VisibilityState.MASKED))
        self.assertFalse(highlighted_for_state(True, VisibilityState.EXCLUDED))
        self.assertFalse(highlighted_for_state(False, VisibilityState.VISIBLE))

    def test_ancestor_marker_is_opt_in_for_the_fan_view(self):
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=1,
            descendant_generations=0,
        )
        scene = layout_ancestors(
            canvas,
            (("ancestor-a-1-0", "Coste, Benoît", "1781–1846", None, True),),
        )
        markers = [node for node in scene.children if isinstance(node, SceneMarker)]
        self.assertEqual(markers, [])

        scene = layout_ancestors(
            canvas,
            (("ancestor-a-1-0", "Coste, Benoît", "1781–1846", None, True),),
            show_highlight_markers=True,
        )
        markers = [node for node in scene.children if isinstance(node, SceneMarker)]
        self.assertEqual(len(markers), 1)
        self.assertGreater(markers[0].radius, 0)

    def test_descendant_markers_are_opt_in_for_the_fan_view(self):
        root = branch("root", 1, spouse="root-spouse", children=(branch("child", 2),))
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=0,
            descendant_generations=2,
        )
        scene = layout_descendants(
            canvas,
            (root,),
            name_lookup=lambda handle: handle.replace("-", " "),
            highlight_lookup=lambda handle: handle in {"root", "root-spouse", "child"},
        )
        markers = [node for node in scene.children if isinstance(node, SceneMarker)]
        self.assertEqual(markers, [])

        scene = layout_descendants(
            canvas,
            (root,),
            name_lookup=lambda handle: handle.replace("-", " "),
            highlight_lookup=lambda handle: handle in {"root", "root-spouse", "child"},
            show_highlight_markers=True,
        )
        markers = [node for node in scene.children if isinstance(node, SceneMarker)]
        self.assertGreaterEqual(len(markers), 3)

    def test_split_descendant_cells_do_not_duplicate_branch_markers(self):
        child_a = branch("child-a", 2)
        child_b = branch("child-b", 2)
        root = DescendantBranch(
            "descendant-root",
            person("root"),
            1,
            (
                UnionBranch(
                    "family-a",
                    "spouse-a",
                    ("child-a",),
                    ("birth",),
                ),
                UnionBranch(
                    "family-b",
                    "spouse-b",
                    ("child-b",),
                    ("birth",),
                ),
            ),
            (child_a, child_b),
            children_by_union=((child_a,), (child_b,)),
        )
        scene = layout_descendants(
            calculate_canvas(
                PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
                ancestor_generations=0,
                descendant_generations=2,
            ),
            (root,),
            name_lookup=lambda handle: handle,
            dates_lookup=lambda _handle: "",
            highlight_lookup=lambda handle: handle in {
                "root",
                "spouse-a",
                "spouse-b",
            },
            show_highlight_markers=True,
        )
        markers = [node for node in scene.children if isinstance(node, SceneMarker)]

        self.assertEqual(len(markers), 4)
        self.assertTrue(all(marker.radius > 2.0 for marker in markers))

    def test_deep_split_descendant_cells_keep_their_markers(self):
        child = DescendantBranch(
            "split-child",
            person("split-child"),
            2,
            (
                UnionBranch(
                    "family-a",
                    "split-spouse-a",
                    (),
                    (),
                ),
                UnionBranch(
                    "family-b",
                    "split-spouse-b",
                    (),
                    (),
                ),
            ),
            (),
            children_by_union=((), ()),
        )
        root = branch(
            "root",
            1,
            spouse="root-spouse",
            children=(child,),
        )
        scene = layout_descendants(
            calculate_canvas(
                PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
                ancestor_generations=0,
                descendant_generations=2,
            ),
            (root,),
            name_lookup=lambda handle: handle,
            highlight_lookup=lambda handle: handle in {
                "split-child",
                "split-spouse-a",
                "split-spouse-b",
            },
            show_highlight_markers=True,
        )
        markers = [node for node in scene.children if isinstance(node, SceneMarker)]

        self.assertEqual(len(markers), 4)
        self.assertTrue(all(marker.radius > 0 for marker in markers))

    def test_svg_serializes_highlight_marker_as_shape_plus_color(self):
        svg = render_svg(
            ScenePage(100, 100),
            SceneNode((SceneMarker(cx=50, cy=50, radius=8),)),
        )
        self.assertIn("7C2F3A", svg)
        self.assertIn("stroke-linejoin", svg)
        self.assertIn("<path", svg)

    def test_svg_serializes_arc_labels_as_visible_vector_text(self):
        svg = render_svg(
            ScenePage(100, 100),
            SceneNode((
                ScenePathText(
                    path="M 10 80 A 30 30 0 0 1 70 80",
                    content="Full Name 1781–1846",
                    font_size=6,
                ),
            )),
        )
        self.assertNotIn("<textPath", svg)
        self.assertRegex(svg, r'<text x="[^"]+" y="[^"]+"')
        self.assertIn('transform="rotate(', svg)
        self.assertIn("Full Name 1781–1846", svg)

    def test_svg_rejects_non_circular_arc_paths_instead_of_hiding_labels(self):
        with self.assertRaises(ValueError):
            render_svg(
                ScenePage(100, 100),
                SceneNode((
                    ScenePathText(
                        path="M 10 80 L 70 80",
                        content="Unsupported path",
                        font_size=6,
                    ),
                )),
            )

    def test_cairo_serializes_highlight_marker_when_available(self):
        try:
            from TwoWayFanChart.render_cairo import render_cairo_png
        except ModuleNotFoundError as error:
            if error.name == "cairo":
                self.skipTest("pycairo is not installed")
            raise
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "marker.png"
            render_cairo_png(
                path,
                ScenePage(100, 100),
                SceneNode((SceneMarker(cx=50, cy=50, radius=8),)),
                dpi=20,
            )
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
