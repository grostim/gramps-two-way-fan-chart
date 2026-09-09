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


if __name__ == "__main__":
    unittest.main()
