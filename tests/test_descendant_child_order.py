from __future__ import annotations

import unittest

from gramps.gen.lib import Date

from TwoWayFanChart.extract import extract_descendant_branches


class FakeChildRef:
    def __init__(self, handle: str):
        self.handle = handle

    def get_reference_handle(self):
        return self.handle

    def get_father_relation(self):
        return "Birth"

    def get_mother_relation(self):
        return "Birth"


class FakePerson:
    def __init__(self, handle: str, birth_year: int | None = None):
        self.handle = handle
        self.birth_year = birth_year

    def get_handle(self):
        return self.handle

    def get_gramps_id(self):
        return self.handle.upper()

    def get_family_handle_list(self):
        return []

    def get_birth_ref(self):
        return None


class FakeFamily:
    def __init__(self, handle: str, children=(), father="parent"):
        self.handle = handle
        self.children = tuple(children)
        self.father = father

    def get_handle(self):
        return self.handle

    def get_gramps_id(self):
        return self.handle.upper()

    def get_father_handle(self):
        return self.father

    def get_mother_handle(self):
        return None

    def get_child_ref_list(self):
        return tuple(FakeChildRef(handle) for handle in self.children)


class FakeEvent:
    def __init__(self, date: Date):
        self.date = date

    def get_date_object(self):
        return self.date


class FakeDatabase:
    def __init__(self, people, center_family, births):
        self.people = {person.handle: person for person in people}
        self.families = {center_family.handle: center_family}
        self.births = births

    def get_family_from_handle(self, handle):
        return self.families.get(handle)

    def get_person_from_handle(self, handle):
        return self.people.get(handle)

    def get_event_from_handle(self, handle):
        return self.births.get(handle)


class DescendantChildOrderTests(unittest.TestCase):
    def test_children_are_sorted_by_birth_date_with_unknowns_in_attachment_order(self):
        parent = FakePerson("parent")
        children = [
            FakePerson("unknown-a"),
            FakePerson("born-1900", 1900),
            FakePerson("born-1890", 1890),
            FakePerson("unknown-b"),
        ]
        births = {
            "birth-born-1900": FakeEvent(Date(1900)),
            "birth-born-1890": FakeEvent(Date(1890)),
        }
        for child in children:
            if child.birth_year is not None:
                child.get_birth_ref = lambda child=child: type(
                    "BirthRef", (), {"get_reference_handle": lambda self: f"birth-{child.handle}"}
                )()
        family = FakeFamily("center", [child.handle for child in children])
        database = FakeDatabase([parent, *children], family, births)

        branches, diagnostics = extract_descendant_branches(database, "center", 1)

        self.assertEqual(diagnostics, ())
        self.assertEqual(
            [branch.person.handle for branch in branches],
            ["born-1890", "born-1900", "unknown-a", "unknown-b"],
        )


if __name__ == "__main__":
    unittest.main()
