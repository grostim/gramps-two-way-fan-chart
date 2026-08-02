import unittest

from TwoWayFanChart.facts import simple_name
from TwoWayFanChart.pipeline import _ancestor_short_label, _mockup_name_order


class FakeName:
    def __init__(self, *, first_name, call_name="", nick_name="", surnames=()):
        self.first_name = first_name
        self.call_name = call_name
        self.nick_name = nick_name
        self.surnames = tuple(surnames)

    def get_first_name(self):
        return self.first_name

    def get_call_name(self):
        return self.call_name

    def get_nick_name(self):
        return self.nick_name

    def get_surname_list(self):
        return tuple(FakeSurname(value) for value in self.surnames)


class FakeSurname:
    def __init__(self, value):
        self.value = value

    def get_surname(self):
        return self.value


class FakePerson:
    def __init__(self, name):
        self.name = name

    def get_primary_name(self):
        return self.name


class FakeDatabase:
    def __init__(self, person):
        self.person = person

    def get_person_from_handle(self, handle):
        return self.person if handle == "person-1" else None


class NicknameFormattingTests(unittest.TestCase):
    def test_nickname_is_inserted_between_call_name_and_surname(self):
        database = FakeDatabase(
            FakePerson(
                FakeName(
                    first_name="Alexandre Théodore",
                    call_name="Alexandre",
                    nick_name="Toto",
                    surnames=("Roche",),
                )
            )
        )

        self.assertEqual(
            simple_name(database, "person-1"),
            "Roche, Alexandre « Toto »",
        )
        self.assertEqual(
            _mockup_name_order("Roche, Alexandre « Toto »"),
            "Alexandre « Toto » Roche",
        )

    def test_nickname_is_trimmed_and_does_not_change_surname_order(self):
        database = FakeDatabase(
            FakePerson(
                FakeName(
                    first_name="Alexandre",
                    nick_name="  Toto  ",
                    surnames=("Roche", "Durand"),
                )
            )
        )

        self.assertEqual(
            simple_name(database, "person-1"),
            "Roche Durand, « Toto »",
        )

    def test_nickname_without_call_name_uses_nickname_only(self):
        database = FakeDatabase(
            FakePerson(
                FakeName(
                    first_name="Louis André Marie",
                    nick_name="Germain",
                    surnames=("Roque",),
                )
            )
        )

        self.assertEqual(
            _mockup_name_order(simple_name(database, "person-1")),
            "« Germain » Roque",
        )

    def test_call_name_without_nickname_is_call_name_plus_surname(self):
        database = FakeDatabase(
            FakePerson(
                FakeName(
                    first_name="Alexandre Théodore",
                    call_name="Alexandre",
                    surnames=("Roche",),
                )
            )
        )

        self.assertEqual(
            _mockup_name_order(simple_name(database, "person-1")),
            "Alexandre Roche",
        )

    def test_without_call_name_or_nickname_uses_last_given_name(self):
        database = FakeDatabase(
            FakePerson(
                FakeName(
                    first_name="Louis André Marie",
                    surnames=("Roque",),
                )
            )
        )

        self.assertEqual(
            _mockup_name_order(simple_name(database, "person-1")),
            "Marie Roque",
        )

    def test_missing_nickname_keeps_existing_label(self):
        database = FakeDatabase(
            FakePerson(
                FakeName(first_name="Alexandre", surnames=("Roche",))
            )
        )

        self.assertEqual(simple_name(database, "person-1"), "Roche, Alexandre")

    def test_ancestor_label_keeps_full_nickname_and_surname(self):
        label = "Roque, Louis « Germain »"

        self.assertEqual(
            _ancestor_short_label(label, generation=3),
            "Louis « Germain » Roque",
        )


if __name__ == "__main__":
    unittest.main()
