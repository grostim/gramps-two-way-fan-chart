import unittest
from pathlib import Path

from TwoWayFanChart.config import ChartConfig
from TwoWayFanChart.extract import extract_ancestor_data
from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
from TwoWayFanChart.layout import layout_ancestors
from TwoWayFanChart.model import AncestorMarriage, AncestorSlot, PersonNode, ScenePathText, SceneSector


class FakePerson:
    def __init__(self, handle, parent_families=()):
        self.handle = handle
        self.parent_families = tuple(parent_families)

    def get_handle(self):
        return self.handle

    def get_gramps_id(self):
        return self.handle.upper()

    def get_parent_family_handle_list(self):
        return list(self.parent_families)

    def get_main_parents_family_handle(self):
        return self.parent_families[0] if self.parent_families else None


class FakeFamily:
    def __init__(self, handle, father=None, mother=None):
        self.handle = handle
        self.father = father
        self.mother = mother

    def get_handle(self):
        return self.handle

    def get_father_handle(self):
        return self.father

    def get_mother_handle(self):
        return self.mother

    def get_child_ref_list(self):
        return []


class FakeDatabase:
    def __init__(self, people, families):
        self.people = {person.handle: person for person in people}
        self.families = {family.handle: family for family in families}

    def get_person_from_handle(self, handle):
        return self.people.get(handle)

    def get_family_from_handle(self, handle):
        return self.families.get(handle)


class AncestorMarriageTests(unittest.TestCase):
    def test_ancestor_extraction_keeps_the_family_for_each_parent_couple(self):
        database = FakeDatabase(
            people=(
                FakePerson("center", ("center-parents",)),
                FakePerson("father", ("father-parents",)),
                FakePerson("mother", ("mother-parents",)),
                FakePerson("grandfather", ()),
                FakePerson("grandmother", ()),
                FakePerson("grandfather-maternal", ()),
                FakePerson("grandmother-maternal", ()),
            ),
            families=(
                FakeFamily("center-parents", "father", "mother"),
                FakeFamily("father-parents", "grandfather", "grandmother"),
                FakeFamily(
                    "mother-parents",
                    "grandfather-maternal",
                    "grandmother-maternal",
                ),
            ),
        )

        slots, diagnostics, marriages = extract_ancestor_data(
            database,
            (PersonNode("center", "CENTER"), None),
            2,
        )

        self.assertEqual(diagnostics, ())
        self.assertEqual(
            [(marriage.generation, marriage.lineage, marriage.index, marriage.family_handle)
             for marriage in marriages],
            [
                (1, "a", 0, "center-parents"),
                (2, "a", 0, "father-parents"),
                (2, "a", 1, "mother-parents"),
            ],
        )
        self.assertEqual(len(slots), 12)

    def test_marriage_sectors_are_opt_in_and_render_their_label(self):
        paper = PaperRegion(PaperSize.A0, Orientation.LANDSCAPE)
        from TwoWayFanChart.layout import calculate_canvas

        canvas = calculate_canvas(
            paper,
            ancestor_generations=2,
            descendant_generations=0,
        )
        slots = (
            ("ancestor-a-1-0", "Father", "1800–1860", None, False),
            ("ancestor-a-1-1", "Mother", "1805–1870", None, False),
            ("ancestor-a-2-0", "Grandfather", "1770–1830", None, False),
            ("ancestor-a-2-1", "Grandmother", "1775–1840", None, False),
        )
        marriages = (
            AncestorMarriage(1, "a", 0, "family-1", "1799 · Lyon"),
            AncestorMarriage(2, "a", 0, "family-2", "1768 · Vienne"),
        )

        disabled = layout_ancestors(canvas, slots, ancestor_marriages=marriages)
        self.assertFalse(
            any(isinstance(node, ScenePathText) and node.content == "1799 · Lyon"
                for node in disabled.children)
        )

        enabled = layout_ancestors(
            canvas,
            slots,
            ancestor_marriages=marriages,
            show_ancestor_marriages=True,
        )
        contents = [
            node.content for node in enabled.children if isinstance(node, ScenePathText)
        ]
        for expected in (
            "1799 · Lyon",
            "1768 · Vienne",
            "1800–1860",
            "1805–1870",
            "1770–1830",
            "1775–1840",
        ):
            self.assertIn(expected, contents)
        self.assertGreaterEqual(
            sum(isinstance(node, SceneSector) for node in enabled.children),
            6,
        )

    def test_marriage_option_defaults_to_disabled(self):
        self.assertFalse(ChartConfig().show_ancestor_marriages)


if __name__ == "__main__":
    unittest.main()
