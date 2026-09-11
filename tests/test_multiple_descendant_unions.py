from __future__ import annotations

from dataclasses import dataclass, field
import math
import unittest

from TwoWayFanChart.extract import extract_descendant_branches
from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import (
    _allocate_descendant_branches_by_demand,
    _allocate_descendant_union_cells,
    _allocate_descendant_union_groups,
    _descendant_angle_demand,
    _descendant_group_angle_demand,
    _descendant_ring_bounds,
    _upright_tangent_rotation,
    calculate_canvas,
    layout_descendants,
)
from TwoWayFanChart.model import (
    DescendantBranch,
    PersonNode,
    SceneCircle,
    ScenePathText,
    SceneSector,
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
        self.assertFalse(any("Spouse F0335 / Spouse F0340" in label for label in labels))
        self.assertEqual(labels.count("I0893"), 2)
        first_generation_sectors = [
            node
            for node in scene.children
            if isinstance(node, SceneSector)
            and math.isclose(
                node.inner_radius,
                canvas.descendant_outer_radius_mm * (202 / 600),
            )
            and math.isclose(
                node.outer_radius,
                canvas.descendant_outer_radius_mm * (350 / 600),
            )
        ]
        self.assertEqual(len(first_generation_sectors), 2)

    def test_two_ring_union_medallions_stay_inside_fixed_label_lanes(self):
        child_a = DescendantBranch(
            "inner-lane-child-a",
            PersonNode("inner-lane-child-a", "I1001"),
            2,
            (),
            (),
        )
        child_b = DescendantBranch(
            "inner-lane-child-b",
            PersonNode("inner-lane-child-b", "I1002"),
            2,
            (),
            (),
        )
        person = branch(
            "inner-lane-person",
            1,
            spouse_handles=("inner-lane-spouse-a", "inner-lane-spouse-b"),
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
            name_lookup=lambda handle: handle,
            dates_lookup=lambda _handle: "1900–1950",
        )
        circles = [
            node for node in scene.children if isinstance(node, SceneCircle)
        ]
        self.assertEqual(len(circles), 4)
        first_ring_inner = canvas.descendant_outer_radius_mm * (202 / 600)
        first_ring_outer = canvas.descendant_outer_radius_mm * (350 / 600)
        spouse_label_radius = canvas.descendant_outer_radius_mm * (317 / 600)
        for circle in circles:
            radial_distance = math.hypot(
                circle.cx - canvas.center_cx_mm,
                circle.cy - canvas.center_cy_mm,
            )
            self.assertGreaterEqual(
                radial_distance - circle.r,
                first_ring_inner - 1e-6,
            )
            self.assertLessEqual(
                radial_distance + circle.r,
                first_ring_outer + 1e-6,
            )
            self.assertLess(
                radial_distance + circle.r,
                spouse_label_radius,
            )

    def test_layout_labels_each_nonempty_union_block(self):
        child_f0335 = DescendantBranch(
            "child-f0335",
            PersonNode("child-f0335", "I1001"),
            2,
            (),
            (),
        )
        child_f0335_b = DescendantBranch(
            "child-f0335-b",
            PersonNode("child-f0335-b", "I1002"),
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
            spouse_handles=(
                "spouse-0335",
                "spouse-empty-1",
                "spouse-empty-2",
                "spouse-0340",
            ),
            children=(child_f0335, child_f0335_b, child_f0340),
            children_by_union=(
                (child_f0335, child_f0335_b),
                (),
                (),
                (child_f0340,),
            ),
            family_gramps_ids=("F0335", None, None, "F0340"),
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

        self.assertEqual(sum("F0335" in label for label in labels), 1)
        self.assertEqual(sum("F0340" in label for label in labels), 1)
        self.assertTrue(any("spouse 0340" in label for label in labels))
        marker_nodes = {
            node.content.split(" · ", 1)[0]: node
            for node in scene.children
            if isinstance(node, SceneText)
            and node.content.split(" · ", 1)[0] in {"F0335", "F0340"}
        }
        self.assertEqual(set(marker_nodes), {"F0335", "F0340"})
        for marker in marker_nodes.values():
            radial_angle = math.degrees(
                math.atan2(
                    marker.x - canvas.center_cx_mm,
                    -(marker.y - canvas.center_cy_mm),
                )
            ) % 360.0
            tangent_rotation = _upright_tangent_rotation(radial_angle)
            rotation_delta = (
                (marker.rotation - tangent_rotation + 180.0) % 360.0
            ) - 180.0
            self.assertAlmostEqual(rotation_delta, 0.0, delta=1e-6)

        sectors = [
            node for node in scene.children if isinstance(node, SceneSector)
        ]
        self.assertGreaterEqual(len(sectors), 4)
        child_sectors = sectors[-3:]
        self.assertEqual(child_sectors[0].fill, child_sectors[1].fill)
        self.assertNotEqual(child_sectors[1].fill, child_sectors[2].fill)

        def angle(node):
            return math.atan2(
                node.x - canvas.center_cx_mm,
                -(node.y - canvas.center_cy_mm),
            )

        def mean_angle(nodes):
            return math.atan2(
                sum(math.sin(angle(node)) for node in nodes),
                sum(math.cos(angle(node)) for node in nodes),
            )

        for family_id, child_labels in (
            ("F0335", {"child f0335", "child f0335 b"}),
            ("F0340", {"child f0340"}),
        ):
            header = marker_nodes[family_id]
            children = [
                node
                for node in scene.children
                if isinstance(node, SceneText)
                and node.content in child_labels
            ]
            self.assertEqual(len(children), len(child_labels))
            delta = (
                angle(header) - mean_angle(children) + math.pi
            ) % (2.0 * math.pi) - math.pi
            self.assertLess(abs(delta), math.radians(1.0))
            self.assertGreaterEqual(header.font_size, 3.0)
        self.assertGreaterEqual(marker_nodes["F0340"].font_size, 3.6)

    def test_dense_layout_splits_multiple_union_cells(self):
        grandchild = DescendantBranch(
            "grandchild",
            PersonNode("grandchild", "I3001"),
            3,
            (),
            (),
        )
        child_a = DescendantBranch(
            "child-a",
            PersonNode("child-a", "I1001"),
            2,
            (),
            (grandchild,),
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
            descendant_generations=3,
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
        self.assertEqual(labels.count("i0893"), 2)
        self.assertFalse(any(" / " in label for label in labels))

    def test_multi_union_branch_demand_takes_max_of_ring_and_cell_demands(self):
        first_child = DescendantBranch(
            "demand-child-0",
            PersonNode("demand-child-0", "I1001"),
            2,
            (),
            (),
        )
        second_child = DescendantBranch(
            "demand-child-1",
            PersonNode("demand-child-1", "I1002"),
            2,
            (),
            (),
        )
        multi_union = branch(
            "demand-person",
            1,
            spouse_handles=("demand-spouse-0", "demand-spouse-1"),
            children=(first_child, second_child),
            children_by_union=((first_child,), (second_child,)),
        )
        siblings = tuple(
            DescendantBranch(
                f"demand-sibling-{index}",
                PersonNode(f"demand-sibling-{index}", f"I20{index}"),
                1,
                (),
                (),
            )
            for index in range(10)
        )

        self.assertAlmostEqual(_descendant_angle_demand(multi_union), 28.0)

        allocation = _allocate_descendant_branches_by_demand(
            (multi_union,) + siblings,
            start_angle=96.0,
            total_sweep=168.0,
        )[0]
        cells = _allocate_descendant_union_cells(
            multi_union,
            start_angle=allocation.start_angle,
            total_sweep=allocation.sweep_angle,
        )

        self.assertEqual(len(cells), 2)
        self.assertAlmostEqual(allocation.sweep_angle, 28.0)
        self.assertGreaterEqual(
            min(cell.sweep_angle for cell in cells),
            14.0 - 1e-6,
        )

    def test_unsplit_ancestor_propagates_nested_multi_union_demand(self):
        nested = branch(
            "nested-ten-unions",
            2,
            spouse_handles=tuple(
                f"nested-spouse-{index}"
                for index in range(10)
            ),
            children=(),
            children_by_union=tuple(() for _ in range(10)),
        )
        parent = branch(
            "unsplit-parent",
            1,
            spouse_handles=("parent-spouse",),
            children=(nested,),
            children_by_union=((nested,),),
        )
        siblings = tuple(
            DescendantBranch(
                f"unsplit-sibling-{index}",
                PersonNode(f"unsplit-sibling-{index}", f"I20{index}"),
                1,
                (),
                (),
            )
            for index in range(9)
        )

        self.assertAlmostEqual(_descendant_angle_demand(parent), 35.0)
        allocation = _allocate_descendant_branches_by_demand(
            (parent,) + siblings,
            start_angle=96.0,
            total_sweep=168.0,
        )[0]
        cells = _allocate_descendant_union_cells(
            nested,
            start_angle=allocation.start_angle,
            total_sweep=allocation.sweep_angle,
        )

        self.assertEqual(len(cells), 10)
        self.assertGreaterEqual(
            min(cell.sweep_angle for cell in cells),
            3.5 - 1e-6,
        )

    def test_nested_multi_union_demand_propagates_to_parent_union_group(self):
        nested_child_a = DescendantBranch(
            "nested-child-a",
            PersonNode("nested-child-a", "I5001"),
            5,
            (),
            (),
        )
        nested_child_b = DescendantBranch(
            "nested-child-b",
            PersonNode("nested-child-b", "I5002"),
            5,
            (),
            (),
        )
        nested = branch(
            "nested",
            4,
            spouse_handles=("nested-spouse-a", "nested-spouse-b"),
            children=(nested_child_a, nested_child_b),
            children_by_union=((nested_child_a,), (nested_child_b,)),
        )
        sparse_children = tuple(
            DescendantBranch(
                f"sparse-parent-group-child-{index}",
                PersonNode(
                    f"sparse-parent-group-child-{index}",
                    f"I50{index:02d}",
                ),
                4,
                (),
                (),
            )
            for index in range(97)
        )
        parent_groups = ((nested,),) + tuple(
            (child,)
            for child in sparse_children
        )
        parent = branch(
            "parent-with-nested-union",
            3,
            spouse_handles=tuple(
                f"parent-spouse-{index}"
                for index in range(len(parent_groups))
            ),
            children=(nested,) + sparse_children,
            children_by_union=parent_groups,
        )

        self.assertAlmostEqual(
            _descendant_group_angle_demand((nested,)),
            2.0,
        )
        parent_groups = _allocate_descendant_union_groups(
            parent,
            start_angle=96.0,
            total_sweep=168.0,
            include_empty=True,
        )
        nested_cells = _allocate_descendant_union_cells(
            nested,
            start_angle=parent_groups[0].start_angle,
            total_sweep=parent_groups[0].sweep_angle,
        )

        self.assertEqual(len(nested_cells), 2)
        self.assertGreaterEqual(parent_groups[0].sweep_angle, 2.0)
        self.assertGreaterEqual(
            min(cell.sweep_angle for cell in nested_cells),
            1.0,
        )

    def test_unmarried_branch_reserves_palette_slot_before_union_branch(self):
        unmarried = DescendantBranch(
            "unmarried",
            PersonNode("unmarried", "I1001"),
            1,
            (),
            (),
        )
        child = DescendantBranch(
            "married-child",
            PersonNode("married-child", "I1002"),
            2,
            (),
            (),
        )
        married = branch(
            "married",
            1,
            spouse_handles=("married-spouse",),
            children=(child,),
            children_by_union=((child,),),
        )
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=2,
        )

        scene = layout_descendants(
            canvas,
            (unmarried, married),
            name_lookup=lambda handle: handle,
            dates_lookup=lambda _handle: "",
        )
        first_ring = [
            node
            for node in scene.children
            if isinstance(node, SceneSector)
            and math.isclose(
                node.inner_radius,
                canvas.descendant_outer_radius_mm * (202 / 600),
            )
            and math.isclose(
                node.outer_radius,
                canvas.descendant_outer_radius_mm * (350 / 600),
            )
        ]

        self.assertEqual(len(first_ring), 2)
        self.assertNotEqual(first_ring[0].fill, first_ring[1].fill)

    def test_top_level_sibling_fill_is_reserved_before_nested_union_cells(self):
        nested_children = tuple(
            DescendantBranch(
                f"nested-child-{index}",
                PersonNode(f"nested-child-{index}", f"I30{index}"),
                3,
                (),
                (),
            )
            for index in range(2)
        )
        nested = branch(
            "nested",
            2,
            spouse_handles=("nested-spouse-a", "nested-spouse-b"),
            children=nested_children,
            children_by_union=(
                (nested_children[0],),
                (nested_children[1],),
            ),
        )
        first = branch(
            "first",
            1,
            spouse_handles=("first-spouse",),
            children=(nested,),
            children_by_union=((nested,),),
        )
        sibling_child = DescendantBranch(
            "sibling-child",
            PersonNode("sibling-child", "I4001"),
            2,
            (),
            (),
        )
        sibling = branch(
            "sibling",
            1,
            spouse_handles=("sibling-spouse",),
            children=(sibling_child,),
            children_by_union=((sibling_child,),),
        )
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=3,
        )

        scene = layout_descendants(
            canvas,
            (first, sibling),
            name_lookup=lambda handle: handle,
            dates_lookup=lambda _handle: "",
        )
        first_ring_inner, first_ring_outer = _descendant_ring_bounds(
            canvas.descendant_inner_radius_mm,
            canvas.descendant_outer_radius_mm,
            3,
            1,
        )
        first_ring = [
            node
            for node in scene.children
            if isinstance(node, SceneSector)
            and math.isclose(node.inner_radius, first_ring_inner)
            and math.isclose(node.outer_radius, first_ring_outer)
        ]

        self.assertEqual(len(first_ring), 2)
        self.assertNotEqual(first_ring[0].fill, first_ring[1].fill)

    def test_nested_union_cells_keep_adjacent_sibling_fills_distinct(self):
        nested_children = tuple(
            DescendantBranch(
                f"nested-child-{index}",
                PersonNode(f"nested-child-{index}", f"I30{index}"),
                3,
                (),
                (),
            )
            for index in range(3)
        )
        nested = branch(
            "nested-three-unions",
            2,
            spouse_handles=(
                "nested-spouse-a",
                "nested-spouse-b",
                "nested-spouse-c",
            ),
            children=nested_children,
            children_by_union=tuple((child,) for child in nested_children),
        )
        first = branch(
            "first-with-nested-split",
            1,
            spouse_handles=("first-spouse",),
            children=(nested,),
            children_by_union=((nested,),),
        )
        sibling_child = DescendantBranch(
            "sibling-child-after-nested-split",
            PersonNode("sibling-child-after-nested-split", "I4001"),
            2,
            (),
            (),
        )
        sibling = branch(
            "sibling-after-nested-split",
            1,
            spouse_handles=("sibling-spouse",),
            children=(sibling_child,),
            children_by_union=((sibling_child,),),
        )
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=3,
        )

        scene = layout_descendants(
            canvas,
            (first, sibling),
            name_lookup=lambda handle: handle,
            dates_lookup=lambda _handle: "",
        )
        second_ring_inner, second_ring_outer = _descendant_ring_bounds(
            canvas.descendant_inner_radius_mm,
            canvas.descendant_outer_radius_mm,
            3,
            2,
        )
        second_ring = [
            node
            for node in scene.children
            if isinstance(node, SceneSector)
            and math.isclose(node.inner_radius, second_ring_inner)
            and math.isclose(node.outer_radius, second_ring_outer)
        ]

        self.assertEqual(len(second_ring), 4)
        for previous, current in zip(second_ring, second_ring[1:]):
            self.assertNotEqual(previous.fill, current.fill)

    def test_childless_union_does_not_emit_a_descendant_header(self):
        first_child = DescendantBranch(
            "header-first-child",
            PersonNode("header-first-child", "I1001"),
            2,
            (),
            (),
        )
        last_child = DescendantBranch(
            "header-last-child",
            PersonNode("header-last-child", "I1002"),
            2,
            (),
            (),
        )
        person = branch(
            "header-person",
            1,
            spouse_handles=(
                "header-spouse-first",
                "header-spouse-empty",
                "header-spouse-last",
            ),
            children=(first_child, last_child),
            children_by_union=(
                (first_child,),
                (),
                (last_child,),
            ),
            family_gramps_ids=("FHEADER1", "FHEADER_EMPTY", "FHEADER2"),
        )
        scene = layout_descendants(
            calculate_canvas(
                PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
                ancestor_generations=5,
                descendant_generations=2,
            ),
            (person,),
            name_lookup=lambda handle: handle,
            dates_lookup=lambda _handle: "",
        )
        labels = [
            node.content
            for node in scene.children
            if isinstance(node, (SceneText, ScenePathText))
        ]

        self.assertTrue(any("FHEADER1" in label for label in labels))
        self.assertTrue(any("FHEADER2" in label for label in labels))
        self.assertFalse(any("FHEADER_EMPTY" in label for label in labels))

    def test_two_ring_multi_union_generation_two_cells_fit_spouses(self):
        grandchild = branch(
            "grandchild-multi-union",
            2,
            spouse_handles=("Very Long Spouse Name Alpha", "Very Long Spouse Name Beta"),
            children=(),
            children_by_union=((), ()),
        )
        parent_branch = DescendantBranch(
            "parent-branch",
            PersonNode("parent-branch", "I1000"),
            1,
            unions=(UnionBranch("f1", "child-spouse", ("grandchild-multi-union",), ("birth",)),),
            children=(grandchild,),
            children_by_union=((grandchild,),),
        )
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=2,
        )
        scene = layout_descendants(
            canvas,
            (parent_branch,),
            name_lookup=lambda handle: handle.replace("-", " "),
            dates_lookup=lambda _handle: "1900–1950",
        )
        texts = [
            node for node in scene.children if isinstance(node, SceneText)
        ]
        self.assertTrue(any("Very Long Spouse Name Alpha" in node.content for node in texts))
        self.assertTrue(any("Very Long Spouse Name Beta" in node.content for node in texts))

    def test_compact_multi_union_couples_share_generation_font_size(self):
        first_child = DescendantBranch(
            "compact-child-0",
            PersonNode("compact-child-0", "I1001"),
            3,
            (),
            (),
        )
        second_child = DescendantBranch(
            "compact-child-1",
            PersonNode("compact-child-1", "I1002"),
            3,
            (),
            (),
        )
        target = branch(
            "compact-target",
            2,
            spouse_handles=("compact-spouse-short", "compact-spouse-long"),
            children=(first_child, second_child),
            children_by_union=((first_child,), (second_child,)),
        )
        siblings = tuple(
            DescendantBranch(
                f"compact-sibling-{index}",
                PersonNode(f"compact-sibling-{index}", f"I30{index}"),
                2,
                (),
                (),
            )
            for index in range(200)
        )
        root = DescendantBranch(
            "compact-root",
            PersonNode("compact-root", "I0001"),
            1,
            (),
            (target,) + siblings,
        )
        labels = {
            "compact-root": "Compact Root",
            "compact-target": "Compact Target",
            "compact-spouse-short": "Short Spouse",
            "compact-spouse-long": "A Much Longer Spouse Name",
            "compact-child-0": "Compact Child 0",
            "compact-child-1": "Compact Child 1",
        }

        scene = layout_descendants(
            calculate_canvas(
                PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
                ancestor_generations=5,
                descendant_generations=3,
            ),
            (root,),
            name_lookup=lambda handle: labels.get(handle, handle),
            dates_lookup=lambda _handle: "",
        )
        compact_couples = [
            node
            for node in scene.children
            if isinstance(node, SceneText)
            and "Compact Target" in node.content
        ]

        self.assertEqual(len(compact_couples), 2)
        self.assertEqual(
            len({round(node.font_size, 9) for node in compact_couples}),
            1,
        )

    def test_stacked_multi_union_couples_share_generation_font_size(self):
        first_children = tuple(
            DescendantBranch(
                f"stacked-child-{index}",
                PersonNode(f"stacked-child-{index}", f"I10{index}"),
                3,
                (),
                (),
            )
            for index in range(3)
        )
        second_child = DescendantBranch(
            "stacked-child-last",
            PersonNode("stacked-child-last", "I103"),
            3,
            (),
            (),
        )
        target = branch(
            "stacked-target",
            2,
            spouse_handles=("stacked-spouse-a", "stacked-spouse-b"),
            children=first_children + (second_child,),
            children_by_union=(
                first_children,
                (second_child,),
            ),
        )
        siblings = tuple(
            DescendantBranch(
                f"stacked-sibling-{index}",
                PersonNode(f"stacked-sibling-{index}", f"I20{index}"),
                2,
                (),
                (),
            )
            for index in range(75)
        )
        root = DescendantBranch(
            "stacked-root",
            PersonNode("stacked-root", "I0001"),
            1,
            (),
            (target,) + siblings,
        )
        labels = {
            "stacked-target": "Stacked Target",
            "stacked-spouse-a": "Stacked Spouse A",
            "stacked-spouse-b": "Stacked Spouse B",
        }

        scene = layout_descendants(
            calculate_canvas(
                PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
                ancestor_generations=5,
                descendant_generations=3,
            ),
            (root,),
            name_lookup=lambda handle: labels.get(handle, handle),
            dates_lookup=lambda _handle: "",
        )
        stacked_couples = [
            node
            for node in scene.children
            if isinstance(node, SceneText)
            and node.content
            in {
                "Stacked Target",
                "× Stacked Spouse A",
                "× Stacked Spouse B",
            }
        ]

        self.assertEqual(len(stacked_couples), 4)
        self.assertEqual(
            len({round(node.font_size, 9) for node in stacked_couples}),
            1,
        )

    def test_union_cell_and_child_sector_keep_same_fill_with_empty_unions(self):
        first_child = DescendantBranch(
            "first-child",
            PersonNode("first-child", "I1001"),
            2,
            (),
            (),
        )
        last_child = DescendantBranch(
            "last-child",
            PersonNode("last-child", "I1002"),
            2,
            (),
            (),
        )
        person = branch(
            "person",
            1,
            spouse_handles=("spouse-0", "spouse-1", "spouse-2", "spouse-3"),
            children=(first_child, last_child),
            children_by_union=((first_child,), (), (), (last_child,)),
        )
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=2,
        )
        scene = layout_descendants(
            canvas,
            (person,),
            name_lookup=lambda handle: handle,
            dates_lookup=lambda _handle: "",
        )
        first_ring = [
            node
            for node in scene.children
            if isinstance(node, SceneSector)
            and math.isclose(
                node.inner_radius,
                canvas.descendant_outer_radius_mm * (202 / 600),
            )
            and math.isclose(
                node.outer_radius,
                canvas.descendant_outer_radius_mm * (350 / 600),
            )
        ]
        child_ring = [
            node
            for node in scene.children
            if isinstance(node, SceneSector)
            and math.isclose(
                node.inner_radius,
                canvas.descendant_outer_radius_mm * (355 / 600),
            )
            and math.isclose(
                node.outer_radius,
                canvas.descendant_outer_radius_mm * (598 / 600),
            )
        ]

        self.assertEqual(len(first_ring), 4)
        self.assertEqual(len(child_ring), 2)
        self.assertEqual(child_ring[0].fill, first_ring[0].fill)
        self.assertEqual(child_ring[1].fill, first_ring[3].fill)

    def test_empty_union_consumes_fill_index_before_following_union(self):
        child = DescendantBranch(
            "child-after-empty-union",
            PersonNode("child-after-empty-union", "I1001"),
            2,
            (),
            (),
        )
        person = branch(
            "empty-first-union",
            1,
            spouse_handles=("empty-spouse", "child-spouse"),
            children=(child,),
            children_by_union=((), (child,)),
        )
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=2,
        )
        scene = layout_descendants(
            canvas,
            (person,),
            name_lookup=lambda handle: handle,
            dates_lookup=lambda _handle: "",
        )
        first_ring = [
            node
            for node in scene.children
            if isinstance(node, SceneSector)
            and math.isclose(
                node.inner_radius,
                canvas.descendant_outer_radius_mm * (202 / 600),
            )
            and math.isclose(
                node.outer_radius,
                canvas.descendant_outer_radius_mm * (350 / 600),
            )
        ]
        child_ring = [
            node
            for node in scene.children
            if isinstance(node, SceneSector)
            and math.isclose(
                node.inner_radius,
                canvas.descendant_outer_radius_mm * (355 / 600),
            )
            and math.isclose(
                node.outer_radius,
                canvas.descendant_outer_radius_mm * (598 / 600),
            )
        ]

        self.assertEqual(len(first_ring), 2)
        self.assertEqual(len(child_ring), 1)
        self.assertNotEqual(first_ring[0].fill, first_ring[1].fill)
        self.assertEqual(child_ring[0].fill, first_ring[1].fill)

    def test_split_cells_keep_the_collapsed_private_couple_label(self):
        first_child = DescendantBranch(
            "private-child-0",
            PersonNode("private-child-0", "I1001"),
            2,
            (),
            (),
        )
        second_child = DescendantBranch(
            "private-child-1",
            PersonNode("private-child-1", "I1002"),
            2,
            (),
            (),
        )
        person = branch(
            "private-person",
            1,
            spouse_handles=("private-spouse-0", "private-spouse-1"),
            children=(first_child, second_child),
            children_by_union=((first_child,), (second_child,)),
        )
        scene = layout_descendants(
            calculate_canvas(
                PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
                ancestor_generations=5,
                descendant_generations=2,
            ),
            (person,),
            name_lookup=lambda _handle: "Personne privée",
            dates_lookup=lambda _handle: "",
        )
        labels = [
            node.content
            for node in scene.children
            if isinstance(node, (SceneText, ScenePathText))
        ]

        self.assertEqual(labels.count("Personnes privées"), 2)
        self.assertFalse(any("× Personne privée" in label for label in labels))

    def test_split_cells_collapse_each_private_union_independently(self):
        first_child = DescendantBranch(
            "mixed-private-child-0",
            PersonNode("mixed-private-child-0", "I1001"),
            2,
            (),
            (),
        )
        second_child = DescendantBranch(
            "mixed-private-child-1",
            PersonNode("mixed-private-child-1", "I1002"),
            2,
            (),
            (),
        )
        person = branch(
            "mixed-private-person",
            1,
            spouse_handles=("public-spouse", "private-spouse"),
            children=(first_child, second_child),
            children_by_union=((first_child,), (second_child,)),
        )
        names = {
            "mixed-private-person": "Personne privée",
            "public-spouse": "Conjoint public",
            "private-spouse": "Personne privée",
        }
        scene = layout_descendants(
            calculate_canvas(
                PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
                ancestor_generations=5,
                descendant_generations=2,
            ),
            (person,),
            name_lookup=lambda handle: names.get(handle, handle),
            dates_lookup=lambda _handle: "",
        )
        labels = [
            node.content
            for node in scene.children
            if isinstance(node, ScenePathText)
        ]

        self.assertEqual(
            labels,
            ["Personne privée", "× Conjoint public", "Personnes privées"],
        )

    def test_union_fill_is_inherited_by_all_descendant_generations(self):
        first_grandchild = DescendantBranch(
            "first-grandchild",
            PersonNode("first-grandchild", "I2001"),
            3,
            (),
            (),
        )
        second_grandchild = DescendantBranch(
            "second-grandchild",
            PersonNode("second-grandchild", "I2002"),
            3,
            (),
            (),
        )
        first_child = DescendantBranch(
            "first-child-deep",
            PersonNode("first-child-deep", "I1001"),
            2,
            (),
            (first_grandchild,),
        )
        second_child = DescendantBranch(
            "second-child-deep",
            PersonNode("second-child-deep", "I1002"),
            2,
            (),
            (second_grandchild,),
        )
        person = branch(
            "person-deep",
            1,
            spouse_handles=("spouse-0", "spouse-1"),
            children=(first_child, second_child),
            children_by_union=((first_child,), (second_child,)),
        )
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=3,
        )
        scene = layout_descendants(
            canvas,
            (person,),
            name_lookup=lambda handle: handle,
            dates_lookup=lambda _handle: "",
        )
        sectors = [
            node for node in scene.children if isinstance(node, SceneSector)
        ]
        union_cells = sectors[:2]

        self.assertEqual(len(sectors), 6)
        for sector in sectors[2:]:
            parent_cell = next(
                cell
                for cell in union_cells
                if math.isclose(cell.start_angle, sector.start_angle)
            )
            self.assertEqual(sector.fill, parent_cell.fill)

    def test_two_ring_union_portraits_stay_inside_their_outer_ring(self):
        first_child = DescendantBranch(
            "portrait-child-0",
            PersonNode("portrait-child-0", "I1001"),
            2,
            (),
            (),
        )
        second_child = DescendantBranch(
            "portrait-child-1",
            PersonNode("portrait-child-1", "I1002"),
            2,
            (),
            (),
        )
        person = branch(
            "portrait-person",
            1,
            spouse_handles=("portrait-spouse-0", "portrait-spouse-1"),
            children=(first_child, second_child),
            children_by_union=((first_child,), (second_child,)),
        )
        canvas = calculate_canvas(
            PaperRegion(PaperSize.A0, Orientation.LANDSCAPE),
            ancestor_generations=5,
            descendant_generations=2,
        )
        scene = layout_descendants(
            canvas,
            (person,),
            name_lookup=lambda handle: handle,
            dates_lookup=lambda _handle: "",
            portrait_lookup=lambda _handle: "data:image/png;base64,portrait",
        )
        circles = [
            node for node in scene.children if isinstance(node, SceneCircle)
        ]
        first_ring_outer = canvas.descendant_outer_radius_mm * (350 / 600)

        self.assertEqual(len(circles), 4)
        for circle in circles:
            center_distance = math.hypot(
                circle.cx - canvas.center_cx_mm,
                circle.cy - canvas.center_cy_mm,
            )
            self.assertLessEqual(
                center_distance + circle.r,
                first_ring_outer - 0.8 + 1e-6,
            )

    def test_union_cells_and_child_blocks_share_the_same_angular_intervals(self):
        dense_children = tuple(
            DescendantBranch(
                f"dense-child-{index}",
                PersonNode(f"dense-child-{index}", f"I10{index}"),
                2,
                (),
                tuple(
                    DescendantBranch(
                        f"dense-grandchild-{index}-{grandchild_index}",
                        PersonNode(
                            f"dense-grandchild-{index}-{grandchild_index}",
                            f"I20{index}{grandchild_index}",
                        ),
                        3,
                        (),
                        (),
                    )
                    for grandchild_index in range(4)
                ),
            )
            for index in range(3)
        )
        sparse_child = DescendantBranch(
            "sparse-child",
            PersonNode("sparse-child", "I1099"),
            2,
            (),
            (),
        )
        person = branch(
            "i0893",
            1,
            spouse_handles=("spouse-0335", "spouse-0340"),
            children=dense_children + (sparse_child,),
            children_by_union=(dense_children, (sparse_child,)),
        )

        cells = _allocate_descendant_union_cells(
            person,
            start_angle=96.0,
            total_sweep=168.0,
        )
        child_blocks = _allocate_descendant_union_groups(
            person,
            start_angle=96.0,
            total_sweep=168.0,
            include_empty=True,
        )

        self.assertEqual(
            [
                (allocation.union_index, allocation.start_angle, allocation.sweep_angle)
                for allocation in cells
            ],
            [
                (allocation.union_index, allocation.start_angle, allocation.sweep_angle)
                for allocation in child_blocks
            ],
        )
        self.assertGreater(cells[0].sweep_angle, cells[1].sweep_angle)


if __name__ == "__main__":
    unittest.main()
