import unittest

try:
    from gramps.gen.lib import EventType
    from TwoWayFanChart.facts import extract_union
    from TwoWayFanChart.model import VisibilityState
    from TwoWayFanChart.pipeline import _ancestor_marriage_label
except ModuleNotFoundError:  # pragma: no cover - exercised in CI with Gramps
    EventType = None
    extract_union = None
    VisibilityState = None
    _ancestor_marriage_label = None


class FakeDate:
    def is_valid(self):
        return True

    def get_year(self):
        return 1899


class FakeEventRef:
    def __init__(self, handle):
        self.handle = handle

    def get_reference_handle(self):
        return self.handle


class FakeEvent:
    def __init__(self, handle, private, *, place_handle=None):
        self.handle = handle
        self.private = private
        self.place_handle = place_handle

    def get_type(self):
        return EventType.MARRIAGE

    def get_handle(self):
        return self.handle

    def get_privacy(self):
        return self.private

    def get_date_object(self):
        return FakeDate()

    def get_place_handle(self):
        return self.place_handle

    def get_description(self):
        return ""


class FakeFamily:
    def __init__(self, event, *, private=False):
        self.event = event
        self.private = private

    def get_father_handle(self):
        return "father"

    def get_mother_handle(self):
        return "mother"

    def get_privacy(self):
        return self.private

    def get_event_ref_list(self):
        return [FakeEventRef(self.event.handle)]


class FakePlace:
    def __init__(self, private, *, parents=()):
        self.private = private
        self.parents = parents

    def get_privacy(self):
        return self.private

    def get_placeref_list(self):
        return [type("PlaceRef", (), {"ref": handle})() for handle in self.parents]


class FakeDatabase:
    def __init__(self, event, *, family=None, place=None, places=None):
        self.event = event
        self.family = family
        self.place = place
        self.places = {"place-1": place, **(places or {})}

    def get_event_from_handle(self, handle):
        return self.event if handle == self.event.handle else None

    def get_family_from_handle(self, handle):
        return self.family if handle == "family-1" else None

    def get_place_from_handle(self, handle):
        return self.places.get(handle)


class PrivateMarriageTests(unittest.TestCase):
    @unittest.skipUnless(EventType is not None, "Gramps is not installed")
    def test_private_marriage_is_filtered_when_private_facts_are_disabled(self):
        event = FakeEvent("marriage-1", private=True)
        family = FakeFamily(event)
        database = FakeDatabase(event)
        displayer = type(
            "Displayer",
            (),
            {"display_event": lambda _self, _database, _event: "Lyon"},
        )()

        self.assertIsNone(
            extract_union(
                database,
                family,
                "years",
                "gramps",
                displayer=displayer,
                include_private=False,
            )
        )
        self.assertIsNotNone(
            extract_union(
                database,
                family,
                "years",
                "gramps",
                displayer=displayer,
                include_private=True,
            )
        )

    @unittest.skipUnless(EventType is not None, "Gramps is not installed")
    def test_private_marriage_place_is_omitted_when_private_facts_are_disabled(self):
        event = FakeEvent("marriage-1", private=False, place_handle="place-1")
        family = FakeFamily(event)
        database = FakeDatabase(event, place=FakePlace(private=True))
        displayer = type(
            "Displayer",
            (),
            {"display_event": lambda _self, _database, _event: "Secret locality"},
        )()

        fact = extract_union(
            database,
            family,
            "years",
            "gramps",
            displayer=displayer,
            include_private=False,
        )

        self.assertIsNotNone(fact)
        self.assertEqual(fact.place, "")

    @unittest.skipUnless(EventType is not None, "Gramps is not installed")
    def test_private_ancestor_place_is_omitted_when_direct_place_is_public(self):
        event = FakeEvent("marriage-1", private=False, place_handle="place-1")
        family = FakeFamily(event)
        direct_place = FakePlace(False, parents=("place-parent",))
        parent_place = FakePlace(True)
        database = FakeDatabase(
            event,
            family=family,
            place=direct_place,
            places={"place-parent": parent_place},
        )
        displayer = type(
            "Displayer",
            (),
            {"display_event": lambda _self, _database, _event: "Secret hierarchy"},
        )()

        fact = extract_union(
            database,
            family,
            "years",
            "gramps",
            displayer=displayer,
            include_private=False,
        )

        self.assertIsNotNone(fact)
        self.assertEqual(fact.place, "")

    @unittest.skipUnless(
        _ancestor_marriage_label is not None,
        "Gramps is not installed",
    )
    def test_private_family_is_filtered_before_rendering_public_marriage_event(self):
        event = FakeEvent("marriage-1", private=False)
        family = FakeFamily(event, private=True)
        database = FakeDatabase(event, family=family)

        label = _ancestor_marriage_label(
            database,
            "family-1",
            lambda _handle: (object(), VisibilityState.VISIBLE),
            include_private=False,
        )

        self.assertEqual(label, "")


if __name__ == "__main__":
    unittest.main()
