import unittest

from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import calculate_canvas, layout_descendants
from TwoWayFanChart.model import (
    DescendantBranch,
    PersonNode,
    ScenePathText,
    SceneText,
    UnionBranch,
)


_ONE_TYPOGRAPHIC_POINT_MM = 25.4 / 72.0


def branch(
    handle: str,
    generation: int,
    *,
    children: tuple[DescendantBranch, ...] = (),
    spouse: str | None = None,
) -> DescendantBranch:
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


def canvas():
    return calculate_canvas(
        PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
        ancestor_generations=5,
        descendant_generations=3,
    )


class GenerationFontSizeTests(unittest.TestCase):
    def test_generation_two_names_and_spouses_share_one_font_size(self):
        children = (
            branch(
                "short",
                2,
                children=(branch("short-leaf", 3),),
                spouse="short-spouse",
            ),
            branch(
                "long",
                2,
                children=(branch("long-leaf", 3),),
                spouse="long-spouse",
            ),
        )
        root = branch("root", 1, children=children)
        labels = {
            "root": "Root Person",
            "short": "Short",
            "short-spouse": "Short Spouse",
            "short-leaf": "Short Leaf",
            "long": "Long Generation Two Name",
            "long-spouse": "Long Generation Two Spouse",
            "long-leaf": "Long Generation Three Name",
        }

        scene = layout_descendants(
            canvas(),
            (root,),
            name_lookup=labels.__getitem__,
            dates_lookup=lambda _handle: "",
        )
        generation_two_names = {
            "Short",
            "× Short Spouse",
            "Long Generation Two Name",
            "× Long Generation Two Spouse",
        }
        generation_three_names = {
            "Short Leaf",
            "Long Generation Three Name",
        }
        rendered = {
            node.content: node.font_size
            for node in scene.children
            if isinstance(node, SceneText)
            and node.content in generation_two_names | generation_three_names
        }

        self.assertEqual(set(rendered), generation_two_names | generation_three_names)
        for names in (generation_two_names, generation_three_names):
            self.assertEqual(
                len({round(rendered[name], 9) for name in names}),
                1,
            )

    def test_single_generation_names_share_one_font_size(self):
        branches = (
            branch("short", 1, spouse="short-spouse"),
            branch("long", 1, spouse="long-spouse"),
        )
        labels = {
            "short": "Short",
            "short-spouse": "Short Spouse",
            "long": "Long Single Generation Name",
            "long-spouse": "Long Single Generation Spouse",
        }

        scene = layout_descendants(
            calculate_canvas(
                PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
                ancestor_generations=5,
                descendant_generations=1,
            ),
            branches,
            name_lookup=labels.__getitem__,
            dates_lookup=lambda _handle: "",
        )
        names = [
            node
            for node in scene.children
            if isinstance(node, ScenePathText)
        ]

        self.assertEqual(len(names), 4)
        self.assertEqual(len({round(node.font_size, 9) for node in names}), 1)

    def test_generation_one_names_share_one_font_size(self):
        roots = []
        labels = {}
        for index in range(10):
            root_handle = f"root-{index}"
            child_handle = f"child-{index}"
            leaf_handle = f"leaf-{index}"
            roots.append(
                branch(
                    root_handle,
                    1,
                    children=(
                        branch(
                            child_handle,
                            2,
                            children=(branch(leaf_handle, 3),),
                        ),
                    ),
                )
            )
            labels[root_handle] = (
                "Long First Generation Name" if index == 0 else f"Root {index}"
            )
            labels[child_handle] = f"Child {index}"
            labels[leaf_handle] = f"Leaf {index}"

        scene = layout_descendants(
            canvas(),
            tuple(roots),
            name_lookup=labels.__getitem__,
            dates_lookup=lambda _handle: "",
        )
        names = [
            node
            for node in scene.children
            if isinstance(node, ScenePathText)
        ]

        self.assertEqual(len(names), 10)
        self.assertEqual(len({round(node.font_size, 9) for node in names}), 1)

    def test_measurement_caches_name_and_date_lookups(self):
        root = branch(
            "root",
            1,
            children=(branch("child", 2),),
            spouse="root-spouse",
        )
        labels = {
            "root": "Root",
            "root-spouse": "Root Spouse",
            "child": "Child",
        }
        name_calls = []
        date_calls = []

        def name_lookup(handle):
            name_calls.append(handle)
            return labels[handle]

        def dates_lookup(handle):
            date_calls.append(handle)
            return "1900–1980"

        scene = layout_descendants(
            canvas(),
            (root,),
            name_lookup=name_lookup,
            dates_lookup=dates_lookup,
        )

        self.assertTrue(scene.children)
        self.assertEqual(set(name_calls), set(labels))
        self.assertEqual(len(name_calls), len(set(name_calls)))
        self.assertEqual(set(date_calls), set(labels))
        self.assertEqual(len(date_calls), len(set(date_calls)))

    def test_ancestor_generation_sizes_are_shared_and_dates_are_smaller(self):
        from TwoWayFanChart.layout import layout_ancestors

        slots = (
            (
                "ancestor-a-1-0",
                "A Very Long First Generation Ancestor Name",
                "1800–1870",
            ),
            ("ancestor-b-1-0", "Short Parent", "1810–1880"),
            ("ancestor-b-1-1", "Medium Parent", "1820–1890"),
            ("ancestor-b-1-2", "Another Parent", "1830–1900"),
            (
                "ancestor-a-2-0",
                "A Very Long Second Generation Ancestor Name",
                "1760–1830",
            ),
            ("ancestor-b-2-0", "Short Grandparent", "1770–1840"),
            ("ancestor-b-2-1", "Medium Grandparent", "1780–1850"),
        )
        scene = layout_ancestors(canvas(), slots)
        names = {
            node.content: node
            for node in scene.children
            if isinstance(node, (SceneText, ScenePathText))
            and node.content in {slot[1] for slot in slots}
        }
        dates = {
            node.content: node
            for node in scene.children
            if isinstance(node, (SceneText, ScenePathText))
            and "–" in node.content
        }

        self.assertEqual(len(names), 7)
        self.assertEqual(len(dates), 7)
        self.assertEqual(
            len({round(names[label].font_size, 9) for label in names if "First" in label or "Parent" in label}),
            1,
        )
        self.assertEqual(
            len({round(names[label].font_size, 9) for label in names if "Second" in label or "Grandparent" in label}),
            1,
        )
        self.assertEqual(
            len({round(dates[label].font_size, 9) for label in dates if int(label[:4]) >= 1800}),
            1,
        )
        self.assertEqual(
            len({round(dates[label].font_size, 9) for label in dates if int(label[:4]) < 1800}),
            1,
        )
        self.assertAlmostEqual(
            next(dates[label].font_size for label in dates if label.startswith("1800")),
            next(names[label].font_size for label in names if "First" in label) - 1.0,
            places=9,
        )
        self.assertAlmostEqual(
            next(dates[label].font_size for label in dates if label.startswith("1760")),
            next(names[label].font_size for label in names if "Second" in label) - 1.0,
            places=9,
        )
        self.assertTrue(all("…" not in node.content for node in names.values()))

    def test_descendant_generation_names_and_dates_keep_full_content(self):
        roots = (
            branch(
                "root-long",
                1,
                children=(branch("child-long", 2),),
                spouse="root-long-spouse",
            ),
            branch(
                "root-short",
                1,
                children=(
                    branch("child-short-a", 2),
                    branch("child-short-b", 2),
                    branch("child-short-c", 2),
                ),
                spouse="root-short-spouse",
            ),
        )
        labels = {
            "root-long": "A Very Long First Descendant Name",
            "root-long-spouse": "A Very Long First Descendant Spouse",
            "root-short": "Short First Descendant",
            "root-short-spouse": "Short First Descendant Spouse",
            "child-long": "A Very Long Second Descendant Name",
            "child-short-a": "Short Second A",
            "child-short-b": "Short Second B",
            "child-short-c": "Short Second C",
        }
        dates = {
            handle: (
                "1900–1970" if handle.startswith("root") else "1870–1940"
            )
            for handle in labels
        }
        scene = layout_descendants(
            canvas(),
            roots,
            name_lookup=labels.__getitem__,
            dates_lookup=dates.__getitem__,
        )
        name_tokens = set(labels.values())
        name_nodes = [
            node
            for node in scene.children
            if isinstance(node, (SceneText, ScenePathText))
            and any(token in node.content for token in name_tokens)
        ]
        date_nodes = [
            node
            for node in scene.children
            if isinstance(node, (SceneText, ScenePathText))
            and node.content in {"1900–1970", "1870–1940"}
        ]

        self.assertTrue(name_nodes)
        self.assertTrue(date_nodes)
        self.assertTrue(all("…" not in node.content for node in name_nodes))
        first_names = [node for node in name_nodes if "First" in node.content]
        second_names = [node for node in name_nodes if "Second" in node.content]
        first_dates = [node for node in date_nodes if node.content == "1900–1970"]
        second_dates = [node for node in date_nodes if node.content == "1870–1940"]
        self.assertTrue(first_names)
        self.assertTrue(second_names)
        self.assertTrue(first_dates)
        self.assertTrue(second_dates)
        self.assertEqual(len({round(node.font_size, 9) for node in first_names}), 1)
        self.assertEqual(len({round(node.font_size, 9) for node in second_names}), 1)
        self.assertEqual(len({round(node.font_size, 9) for node in first_dates}), 1)
        self.assertEqual(len({round(node.font_size, 9) for node in second_dates}), 1)
        self.assertAlmostEqual(
            first_dates[0].font_size,
            first_names[0].font_size - _ONE_TYPOGRAPHIC_POINT_MM,
            places=9,
        )
        self.assertAlmostEqual(
            second_dates[0].font_size,
            second_names[0].font_size - _ONE_TYPOGRAPHIC_POINT_MM,
            places=9,
        )

    def test_dense_first_generation_dates_are_one_point_below_names(self):
        root = branch(
            "root",
            1,
            children=(
                branch(
                    "child",
                    2,
                    children=(branch("grandchild", 3, children=(branch("leaf", 4),)),),
                ),
            ),
        )
        labels = {
            "root": "A Very Long First Generation Name",
            "child": "Second Generation Name",
            "grandchild": "Third Generation Name",
            "leaf": "Fourth Generation Name",
        }
        dates = {handle: "1900–1970" for handle in labels}
        scene = layout_descendants(
            canvas(),
            (root,),
            name_lookup=labels.__getitem__,
            dates_lookup=dates.__getitem__,
        )

        name = next(
            node
            for node in scene.children
            if isinstance(node, ScenePathText)
            and node.content == labels["root"]
        )
        date = next(
            node
            for node in scene.children
            if isinstance(node, ScenePathText)
            and node.content == dates["root"]
        )

        self.assertAlmostEqual(
            date.font_size,
            name.font_size - _ONE_TYPOGRAPHIC_POINT_MM,
            places=9,
        )
        self.assertNotIn("…", name.content)
        self.assertNotIn("…", date.content)


if __name__ == "__main__":
    unittest.main()
