from __future__ import annotations

from dataclasses import dataclass, field
import unittest

from TwoWayFanChart.extract import extract_descendant_branches
from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import calculate_canvas, layout_descendants
from TwoWayFanChart.model import (
    DescendantBranch,
    PersonNode,
    ScenePathText,
    SceneText,
    UnionBranch,
)


@dataclass
class FakeChildRef:
    handle: str
    father_relation: str = "birth"
    mother_relation: str = "birth"

    def get_reference_handle(self) -> str:
        return self.handle

    def get_father_relation(self) -> str:
        return self.father_relation

    def get_mother_relation(self) -> str:
        return self.mother_relation


@dataclass
class FakePerson:
    handle: str
    gramps_id: str
    parent_families: list[str] = field(default_factory=list)
    families: list[str] = field(default_factory=list)

    def get_handle(self) -> str:
        return self.handle

    def get_gramps_id(self) -> str:
        return self.gramps_id

    def get_parent_family_handle_list(self) -> list[str]:
        return list(self.parent_families)

    def get_family_handle_list(self) -> list[str]:
        return list(self.families)


@dataclass
class FakeFamily:
    handle: str
    gramps_id: str
    father_handle: str | None
    mother_handle: str | None
    child_refs: list[FakeChildRef] = field(default_factory=list)

    def get_handle(self) -> str:
        return self.handle

    def get_gramps_id(self) -> str:
        return self.gramps_id

    def get_father_handle(self) -> str | None:
        return self.father_handle

    def get_mother_handle(self) -> str | None:
        return self.mother_handle

    def get_child_ref_list(self) -> list[FakeChildRef]:
        return list(self.child_refs)


@dataclass
class FakeDatabase:
    people: dict[str, FakePerson]
    families: dict[str, FakeFamily]

    def get_person_from_handle(self, handle: str | None) -> FakePerson | None:
        return self.people.get(handle) if handle else None

    def get_family_from_handle(self, handle: str | None) -> FakeFamily | None:
        return self.families.get(handle) if handle else None


def make_multiple_union_database() -> FakeDatabase:
    people = {
        "central-a": FakePerson("central-a", "I0001"),
        "central-b": FakePerson("central-b", "I0002"),
        "i0893": FakePerson(
            "i0893",
            "I0893",
            families=["f0335", "f0340"],
        ),
        "child-0335-a": FakePerson("child-0335-a", "I1001"),
        "child-0335-b": FakePerson("child-0335-b", "I1002"),
        "child-0340-a": FakePerson("child-0340-a", "I1003"),
        "spouse-0335": FakePerson("spouse-0335", "I2001"),
        "spouse-0340": FakePerson("spouse-0340", "I2002"),
    }
    families = {
        "center": FakeFamily(
            "center",
            "F0001",
            "central-a",
            "central-b",
            [FakeChildRef("i0893")],
        ),
        "f0335": FakeFamily(
            "f0335",
            "F0335",
            "i0893",
            "spouse-0335",
            [
                FakeChildRef("child-0335-a"),
                FakeChildRef("child-0335-b"),
            ],
        ),
        "f0340": FakeFamily(
            "f0340",
            "F0340",
            "i0893",
            "spouse-0340",
            [FakeChildRef("child-0340-a")],
        ),
    }
    return FakeDatabase(people, families)


def branch(
    handle: str,
    generation: int,
    *,
    spouse_handles: tuple[str, ...],
    children: tuple[DescendantBranch, ...],
    children_by_union: tuple[tuple[DescendantBranch, ...], ...],
    family_gramps_ids: tuple[str | None, ...] = (),
) -> DescendantBranch:
    unions = tuple(
        UnionBranch(
            family_handle=f"family-{index}",
            spouse_handle=spouse,
            child_handles=tuple(child.person.handle for child in group),
            child_relations=tuple("birth" for _child in group),
            family_gramps_id=(
                family_gramps_ids[index]
                if index < len(family_gramps_ids)
                else None
            ),
        )
        for index, (spouse, group) in enumerate(zip(spouse_handles, children_by_union))
    )
    return DescendantBranch(
        position_id=f"descendant-{handle}",
        person=PersonNode(handle, handle.upper()),
        generation=generation,
        unions=unions,
        children=children,
        children_by_union=children_by_union,
    )


class MultipleDescendantUnionTests(unittest.TestCase):
    def test_children_remain_assigned_to_their_recorded_union(self):
        branches, diagnostics = extract_descendant_branches(
            make_multiple_union_database(),
            "center",
            generations=2,
        )

        self.assertEqual(diagnostics, ())
        person = branches[0]
        self.assertEqual(person.person.gramps_id, "I0893")
        self.assertEqual(
            [union.family_handle for union in person.unions],
            ["f0335", "f0340"],
        )
        self.assertEqual(
            [union.family_gramps_id for union in person.unions],
            ["F0335", "F0340"],
        )
        self.assertEqual(
            [
                [child.person.gramps_id for child in union_children]
                for union_children in person.children_by_union
            ],
            [["I1001", "I1002"], ["I1003"]],
        )

    def test_layout_keeps_all_union_spouses_visible(self):
        child_a = DescendantBranch(
            "child-a",
            PersonNode("child-a", "I1001"),
            2,
            (),
            (),
        )
        child_b = DescendantBranch(
            "child-b",
            PersonNode("child-b", "I1003"),
            2,
            (),
            (),
        )
        person = branch(
            "i0893",
            1,
            spouse_handles=("spouse-0335", "spouse-0340"),
            children=(child_a, child_b),
            children_by_union=((child_a,), (child_b,)),
        )
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=2,
        )

        scene = layout_descendants(
            canvas,
            (person,),
            name_lookup={
                "i0893": "I0893",
                "spouse-0335": "Spouse F0335",
                "spouse-0340": "Spouse F0340",
                "child-a": "Child F0335",
                "child-b": "Child F0340",
            }.__getitem__,
            dates_lookup=lambda _handle: "",
        )
        labels = [
            node.content
            for node in scene.children
            if isinstance(node, (SceneText, ScenePathText))
        ]

        self.assertTrue(any("Spouse F0335" in label for label in labels))
        self.assertTrue(any("Spouse F0340" in label for label in labels))

    def test_layout_labels_each_nonempty_union_block(self):
        child_f0335 = DescendantBranch(
            "child-f0335",
            PersonNode("child-f0335", "I1001"),
            2,
            (),
            (),
        )
        child_f0340 = DescendantBranch(
            "child-f0340",
            PersonNode("child-f0340", "I1003"),
            2,
            (),
            (),
        )
        person = branch(
            "i0893",
            1,
            spouse_handles=("spouse-0335", "spouse-0340"),
            children=(child_f0335, child_f0340),
            children_by_union=((child_f0335,), (child_f0340,)),
            family_gramps_ids=("F0335", "F0340"),
        )
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=2,
        )

        scene = layout_descendants(
            canvas,
            (person,),
            name_lookup=lambda handle: handle.replace("-", " "),
            dates_lookup=lambda _handle: "",
        )
        labels = [
            node.content
            for node in scene.children
            if isinstance(node, (SceneText, ScenePathText))
        ]

        self.assertEqual(labels.count("F0335"), 1)
        self.assertEqual(labels.count("F0340"), 1)


if __name__ == "__main__":
    unittest.main()
